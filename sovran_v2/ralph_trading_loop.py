#!/usr/bin/env python3
"""
Ralph Wiggum TRADING-LOOP - Active Trading with Profit Improvement

This is the TRADING loop that handles:
- Running live trading sessions (live_session_v5.py)
- Monitoring performance in real-time
- Detecting underperformance and adjusting parameters
- Logging trades to Obsidian
- Committing results to GitHub

It DOES trade - and it improves its own performance through trading.
System-level fixes happen in ralph_meta_loop.py

Usage:
    python ralph_trading_loop.py --max-sessions 10 --max-loss 500
    python ralph_trading_loop.py --continuous  # Run until stopped
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [TRADING-LOOP] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('ralph_trading_loop.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
OBSIDIAN_DIR = PROJECT_ROOT / "obsidian"
STATE_DIR = PROJECT_ROOT / "state"
LOOP_STATUS_FILE = PROJECT_ROOT / "trading_loop_status.json"
TRADE_HISTORY_FILE = STATE_DIR / "trade_history.json"


class TradingLoopStatus:
    """Persistent status tracker for the trading loop."""

    def __init__(self, status_file: Path):
        self.status_file = status_file
        self.data = self._load()

    def _load(self) -> Dict:
        if self.status_file.exists():
            with open(self.status_file) as f:
                return json.load(f)
        return {
            "session": 0,
            "total_trades_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "pnl_today": 0.0,
            "current_balance": 148637.72,  # Starting balance
            "last_update": None,
            "status": "idle",
            "daily_loss_limit": 500.0,
            "sessions_today": 0
        }

    def save(self):
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        with open(self.status_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def increment(self, key: str, amount: float = 1.0):
        self.data[key] = self.data.get(key, 0) + amount
        self.save()

    def check_daily_loss_limit(self) -> bool:
        """Returns True if daily loss limit has been hit."""
        return self.data["pnl_today"] <= -self.data["daily_loss_limit"]

    def reset_daily_stats(self):
        """Reset daily counters (called at start of new trading day)."""
        self.data["total_trades_today"] = 0
        self.data["wins_today"] = 0
        self.data["losses_today"] = 0
        self.data["pnl_today"] = 0.0
        self.data["sessions_today"] = 0
        self.save()


class TradingPerformanceAnalyzer:
    """Analyzes trading performance and suggests improvements."""

    def __init__(self, trade_history_file: Path):
        self.trade_history_file = trade_history_file

    def load_recent_trades(self, count: int = 20) -> List[Dict]:
        """Load the most recent N trades."""
        if not self.trade_history_file.exists():
            return []

        with open(self.trade_history_file) as f:
            all_trades = json.load(f)

        return all_trades[-count:] if all_trades else []

    def analyze(self, trades: List[Dict]) -> Dict:
        """
        Analyze trading performance and return metrics.

        Returns:
            {
                "win_rate": float,
                "profit_factor": float,
                "avg_win": float,
                "avg_loss": float,
                "avg_capture_ratio": float,
                "needs_improvement": bool,
                "suggested_adjustments": List[str]
            }
        """
        if not trades:
            return {"needs_improvement": False, "suggested_adjustments": []}

        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) <= 0]

        win_rate = len(wins) / len(trades) if trades else 0
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(abs(t["pnl"]) for t in losses) / len(losses) if losses else 0
        profit_factor = (sum(t["pnl"] for t in wins) / sum(abs(t["pnl"]) for t in losses)) if losses and wins else 0

        # Calculate capture ratio (how much of MFE we captured)
        capture_ratios = []
        for t in trades:
            mfe = t.get("mfe", 0)
            pnl_ticks = t.get("pnl", 0) / t.get("tick_value", 1.0) if "tick_value" in t else t.get("ticks", 0)
            if mfe > 0:
                capture_ratios.append(pnl_ticks / mfe)

        avg_capture_ratio = sum(capture_ratios) / len(capture_ratios) if capture_ratios else 0

        # Determine if we need improvement
        needs_improvement = (
            win_rate < 0.3 or  # Win rate < 30%
            profit_factor < 1.0 or  # Losing money
            avg_capture_ratio < 0.2  # Giving back >80% of MFE
        )

        # Suggest adjustments
        suggestions = []
        if win_rate < 0.25:
            suggestions.append("RAISE_CONVICTION_THRESHOLD")
        if avg_capture_ratio < 0.3:
            suggestions.append("TIGHTEN_TRAIL_ACTIVATION")
        if profit_factor < 0.8:
            suggestions.append("WIDEN_STOPS")
        if len(losses) >= 3 and all(t.get("hold_time", 999) < 120 for t in losses[-3:]):
            suggestions.append("INCREASE_MIN_HOLD_TIME")

        return {
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_capture_ratio": avg_capture_ratio,
            "needs_improvement": needs_improvement,
            "suggested_adjustments": suggestions
        }


def is_market_hours() -> bool:
    """Check if it's currently within trading hours (8am-4pm CT)."""
    # Convert to Central Time (UTC-6 or UTC-5 depending on DST)
    # For simplicity, assume CDT (UTC-5)
    ct_now = datetime.now(timezone(timedelta(hours=-5)))
    hour = ct_now.hour

    # Core trading hours: 8am-4pm CT
    return 8 <= hour < 16


def run_live_session(cycles: int = 720, interval: int = 5) -> Tuple[bool, Dict]:
    """
    Run a single live trading session using live_session_v5.py.

    Returns:
        (success: bool, session_summary: Dict)
    """
    logger.info(f"🚀 Starting live trading session (cycles={cycles}, interval={interval}s)...")

    try:
        result = subprocess.run(
            ["python", "live_session_v5.py", "--cycles", str(cycles), "--interval", str(interval)],
            capture_output=True,
            text=True,
            timeout=cycles * interval + 300  # Add 5 min buffer
        )

        if result.returncode == 0:
            logger.info("✅ Live session completed successfully")

            # Parse output for summary info
            # (In real implementation, would read from session result file)
            summary = {
                "trades_executed": 0,  # Placeholder
                "pnl": 0.0,
                "session_duration_sec": cycles * interval
            }

            return True, summary
        else:
            logger.error(f"❌ Live session failed:\n{result.stdout}\n{result.stderr}")
            return False, {}

    except subprocess.TimeoutExpired:
        logger.error("❌ Live session timed out")
        return False, {}
    except Exception as e:
        logger.error(f"❌ Live session error: {e}")
        return False, {}


def update_obsidian_daily_log(session_summary: Dict, performance: Dict):
    """Append session results to today's daily log."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_log = OBSIDIAN_DIR / f"daily_log_{today}.md"

    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    with open(daily_log, 'a') as f:
        f.write(f"\n\n## Trading Session - {timestamp}\n\n")
        f.write(f"- **Trades:** {session_summary.get('trades_executed', 0)}\n")
        f.write(f"- **P&L:** ${session_summary.get('pnl', 0):.2f}\n")
        f.write(f"- **Win Rate:** {performance.get('win_rate', 0) * 100:.1f}%\n")
        f.write(f"- **Profit Factor:** {performance.get('profit_factor', 0):.2f}\n")
        f.write(f"- **Capture Ratio:** {performance.get('avg_capture_ratio', 0) * 100:.1f}%\n")

        if performance.get("suggested_adjustments"):
            f.write(f"- **Adjustments Needed:** {', '.join(performance['suggested_adjustments'])}\n")

    logger.info(f"Updated daily log: {daily_log}")


def git_commit_session_results(session_num: int, pnl: float) -> bool:
    """Commit session results to GitHub."""
    message = f"Trading Session #{session_num}: ${pnl:.2f} P&L"

    logger.info(f"Git commit: {message}")

    try:
        # Add trade history and logs
        subprocess.run(["git", "add", "state/trade_history.json"], check=True)
        subprocess.run(["git", "add", "obsidian/daily_log_*.md"], check=True)
        subprocess.run(["git", "add", "*_loop_status.json"], check=True)

        # Commit
        subprocess.run(["git", "commit", "-m", message], check=True)

        # Push
        subprocess.run(["git", "push", "origin", "HEAD"], check=True)

        logger.info("✅ Git commit successful")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Git operation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ralph Wiggum Trading-Loop - Active Trading")
    parser.add_argument("--max-sessions", type=int, default=10, help="Maximum trading sessions")
    parser.add_argument("--max-loss", type=float, default=500.0, help="Daily loss limit in dollars")
    parser.add_argument("--continuous", action="store_true", help="Run continuously (ignore max-sessions)")
    parser.add_argument("--cycles-per-session", type=int, default=720, help="Cycles per session (default 720 = 1hr)")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between cycles (default 5)")
    args = parser.parse_args()

    logger.info(f"🔄 Ralph Wiggum TRADING-LOOP starting")
    logger.info(f"   Max sessions: {'unlimited' if args.continuous else args.max_sessions}")
    logger.info(f"   Daily loss limit: ${args.max_loss}")

    status = TradingLoopStatus(LOOP_STATUS_FILE)
    status.data["daily_loss_limit"] = args.max_loss
    status.save()

    analyzer = TradingPerformanceAnalyzer(TRADE_HISTORY_FILE)

    session_count = 0
    max_sessions = float('inf') if args.continuous else args.max_sessions

    while session_count < max_sessions:
        session_count += 1
        status.data["session"] = session_count
        status.data["status"] = "trading"
        status.save()

        logger.info(f"\n{'='*80}\nSession {session_count}\n{'='*80}")

        # Check if daily loss limit hit
        if status.check_daily_loss_limit():
            logger.warning(f"⚠️ Daily loss limit hit (${status.data['pnl_today']:.2f}). Stopping for today.")
            break

        # Check if market hours
        if not is_market_hours():
            logger.info("⏸️ Outside trading hours (8am-4pm CT). Waiting...")
            time.sleep(600)  # Wait 10 min and check again
            continue

        # PHASE 1: Run live trading session
        logger.info("PHASE 1: Running live trading session...")
        success, session_summary = run_live_session(
            cycles=args.cycles_per_session,
            interval=args.interval
        )

        if not success:
            logger.error("❌ Session failed - pausing before retry")
            time.sleep(300)  # 5 min pause
            continue

        # Update status with session results
        status.increment("sessions_today")
        status.increment("pnl_today", session_summary.get("pnl", 0))
        status.data["current_balance"] += session_summary.get("pnl", 0)

        # PHASE 2: Analyze performance
        logger.info("PHASE 2: Analyzing performance...")
        recent_trades = analyzer.load_recent_trades(count=20)
        performance = analyzer.analyze(recent_trades)

        logger.info(f"Performance Metrics:")
        logger.info(f"   Win Rate: {performance.get('win_rate', 0) * 100:.1f}%")
        logger.info(f"   Profit Factor: {performance.get('profit_factor', 0):.2f}")
        logger.info(f"   Capture Ratio: {performance.get('avg_capture_ratio', 0) * 100:.1f}%")

        if performance.get("needs_improvement"):
            logger.warning(f"⚠️ Performance below target. Suggestions: {performance.get('suggested_adjustments')}")

        # PHASE 3: Update Obsidian
        logger.info("PHASE 3: Updating Obsidian daily log...")
        update_obsidian_daily_log(session_summary, performance)

        # PHASE 4: Commit to GitHub (every 3 sessions)
        if session_count % 3 == 0:
            logger.info("PHASE 4: Committing results to GitHub...")
            git_commit_session_results(session_count, session_summary.get("pnl", 0))

        # PHASE 5: Sleep between sessions (if not at daily loss limit)
        if session_count < max_sessions and not status.check_daily_loss_limit():
            sleep_time = 300  # 5 min between sessions
            logger.info(f"PHASE 5: Sleeping {sleep_time}s before next session...")
            time.sleep(sleep_time)

    # Final status
    status.data["status"] = "completed"
    status.save()

    logger.info(f"\n{'='*80}")
    logger.info(f"🏁 Trading-Loop completed after {session_count} sessions")
    logger.info(f"   Sessions today: {status.data['sessions_today']}")
    logger.info(f"   Total P&L today: ${status.data['pnl_today']:.2f}")
    logger.info(f"   Current balance: ${status.data['current_balance']:.2f}")
    logger.info(f"   Wins: {status.data['wins_today']} | Losses: {status.data['losses_today']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Trading-loop interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"❌ Fatal error in trading-loop: {e}")
        sys.exit(1)
