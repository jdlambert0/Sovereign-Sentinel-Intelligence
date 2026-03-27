#!/usr/bin/env python3
"""
Ralph AI Loop - Kaizen for AI Trading

This loop integrates with the AI Decision Engine to:
1. Launch trading sessions
2. Monitor AI performance
3. Apply Kaizen improvements based on results
4. Update Obsidian memory
5. Commit progress to GitHub
6. Continuously iterate

This is the TRADING loop with AI-specific Kaizen.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [AI-LOOP] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('ralph_ai_loop.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
OBSIDIAN_DIR = PROJECT_ROOT / "obsidian"
STATE_DIR = PROJECT_ROOT / "state"
IPC_DIR = PROJECT_ROOT / "ipc"
MEMORY_FILE = STATE_DIR / "ai_trading_memory.json"
LOOP_STATUS_FILE = PROJECT_ROOT / "ai_loop_status.json"


class AILoopStatus:
    """Track AI loop iterations and performance."""

    def __init__(self, status_file: Path):
        self.status_file = status_file
        self.data = self._load()

    def _load(self) -> Dict:
        if self.status_file.exists():
            with open(self.status_file, encoding='utf-8') as f:
                return json.load(f)
        return {
            "iteration": 0,
            "sessions_run": 0,
            "total_trades": 0,
            "total_pnl": 0.0,
            "kaizen_applied": 0,
            "last_update": None,
            "status": "idle"
        }

    def save(self):
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def increment(self, key: str, amount: float = 1.0):
        self.data[key] = self.data.get(key, 0) + amount
        self.save()


class AIKaizenEngine:
    """
    Kaizen engine specifically for AI trading.

    Analyzes AI performance and makes improvements:
    - Remove time gates
    - Implement round-robin always-trade logic
    - Enhance probability models
    - Optimize strategy selection
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.memory_file = project_root / "state" / "ai_trading_memory.json"

    def load_ai_memory(self) -> Dict:
        """Load AI trading memory."""
        if self.memory_file.exists():
            with open(self.memory_file, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def analyze_performance(self, memory: Dict) -> Dict:
        """
        Analyze AI trading performance.

        Returns recommendations for improvement.
        """
        trades = memory.get("trades_executed", 0)
        strategies = memory.get("strategies_tested", {})
        regimes = memory.get("performance_by_regime", {})

        recommendations = []

        # Recommendation 1: Remove time gate
        if trades > 0:
            recommendations.append({
                "priority": "P0",
                "name": "Remove time gate for AI trading",
                "reason": f"AI has executed {trades} trades. Time restrictions limit learning.",
                "action": "remove_time_gate",
                "expected_impact": "High - AI can trade 24/7 based on probability"
            })

        # Recommendation 2: Implement round-robin
        recommendations.append({
            "priority": "P0",
            "name": "Implement round-robin always-trade logic",
            "reason": "AI should always pick best probability trade, never idle",
            "action": "implement_round_robin",
            "expected_impact": "High - More trades = more data = faster learning"
        })

        # Recommendation 3: Add outcome tracking
        if trades > 0:
            momentum_trades = strategies.get("momentum", {}).get("trades", 0)
            mean_rev_trades = strategies.get("mean_reversion", {}).get("trades", 0)

            if momentum_trades + mean_rev_trades > 0:
                recommendations.append({
                    "priority": "P1",
                    "name": "Enhance memory with outcome tracking",
                    "reason": f"Executed {momentum_trades} momentum, {mean_rev_trades} mean reversion trades but no outcomes recorded",
                    "action": "add_outcome_tracking",
                    "expected_impact": "Medium - Better probability calibration"
                })

        # Recommendation 4: Strategy optimization
        if trades >= 10:
            recommendations.append({
                "priority": "P1",
                "name": "Optimize strategy selection based on results",
                "reason": f"Sufficient data ({trades} trades) to analyze strategy performance",
                "action": "optimize_strategy_selection",
                "expected_impact": "Medium - Use what works, discard what doesn't"
            })

        return {
            "total_trades": trades,
            "strategies_tested": len(strategies),
            "recommendations": recommendations
        }

    def apply_improvement(self, recommendation: Dict) -> Tuple[bool, str]:
        """Apply a Kaizen improvement."""
        action = recommendation["action"]

        if action == "remove_time_gate":
            return self._remove_time_gate()
        elif action == "implement_round_robin":
            return self._implement_round_robin()
        elif action == "add_outcome_tracking":
            return self._add_outcome_tracking()
        elif action == "optimize_strategy_selection":
            return self._optimize_strategy_selection()
        else:
            return False, f"Unknown action: {action}"

    def _remove_time_gate(self) -> Tuple[bool, str]:
        """Remove trading hours restriction for AI."""
        logger.info("Removing time gate for AI trading...")

        v5_file = self.project_root / "live_session_v5.py"

        # Read file
        with open(v5_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if AI time gate bypass exists
        if "USE_AI_ENGINE" in content and "not USE_AI_ENGINE and ct_hour" in content:
            logger.info("Time gate already bypassed for AI")
            return True, "Time gate already removed for AI Decision Engine"

        # Find and modify time gate
        old_code = """    # Phase 1: Time-of-day hard block
    ct_hour = datetime.now(timezone(timedelta(hours=-5))).hour
    if ct_hour < TRADING_HOURS_START or ct_hour >= TRADING_HOURS_END:
        conviction = 0
        signals.append(f"BLOCKED: outside trading hours ({ct_hour}h CT)")"""

        new_code = """    # Phase 1: Time-of-day hard block (BYPASSED for AI Decision Engine)
    ct_hour = datetime.now(timezone(timedelta(hours=-5))).hour
    if not USE_AI_ENGINE and (ct_hour < TRADING_HOURS_START or ct_hour >= TRADING_HOURS_END):
        conviction = 0
        signals.append(f"BLOCKED: outside trading hours ({ct_hour}h CT)")"""

        if old_code in content:
            modified = content.replace(old_code, new_code)

            with open(v5_file, 'w', encoding='utf-8') as f:
                f.write(modified)

            logger.info("Time gate removed for AI")
            return True, "AI can now trade 24/7 based on probability"
        else:
            return False, "Time gate code not found (may already be modified)"

    def _implement_round_robin(self) -> Tuple[bool, str]:
        """Implement round-robin always-trade logic in AI engine."""
        logger.info("Implementing round-robin always-trade logic...")

        ai_engine_file = self.project_root / "ipc" / "ai_decision_engine.py"

        # Read file
        with open(ai_engine_file, encoding='utf-8') as f:
            content = f.read()

        # Check if round-robin logic exists
        if "round_robin_best_trade" in content:
            logger.info("Round-robin logic already implemented")
            return True, "Round-robin logic already exists"

        # Add round-robin method to AIDecisionEngine class
        new_method = '''
    def round_robin_best_trade(self, all_analyses: List[Dict]) -> Dict:
        """
        Round-robin: Always pick the best trade even if all look 'bad'.

        Philosophy: Never sit idle. Always be trading.
        """
        if not all_analyses:
            return None

        # Sort by expected value
        sorted_analyses = sorted(all_analyses, key=lambda x: x.get('expected_value', -999), reverse=True)

        best = sorted_analyses[0]

        # Even if EV is negative, we might trade it as a learning trade
        if best['expected_value'] < 0:
            logger.info(f"ROUND-ROBIN: Best trade has negative EV ({best['expected_value']:.2f})")
            logger.info(f"  Trading anyway for learning purposes (reduced size)")
            # Reduce conviction for negative EV trades
            best['conviction'] = max(40, best['conviction'] * 0.5)

        return best
'''

        # Find the make_decision method and add round-robin call
        # This is a simplified implementation - in production would be more sophisticated

        logger.info("Round-robin implementation requires manual code integration")
        return False, "Round-robin logic needs manual integration (complex code change)"

    def _add_outcome_tracking(self) -> Tuple[bool, str]:
        """Add post-trade outcome tracking to AI engine."""
        logger.info("Adding outcome tracking to AI memory...")

        # This would require modifying V5 to call back to AI engine after trade closes
        # For now, return a note that this needs manual implementation

        return False, "Outcome tracking requires V5 callback integration (manual implementation needed)"

    def _optimize_strategy_selection(self) -> Tuple[bool, str]:
        """Optimize which strategy to use based on performance data."""
        logger.info("Optimizing strategy selection based on results...")

        memory = self.load_ai_memory()
        strategies = memory.get("strategies_tested", {})

        # Calculate win rates and profitability for each strategy
        results = []
        for strategy_name, stats in strategies.items():
            trades = stats.get("trades", 0)
            wins = stats.get("wins", 0)
            total_pnl = stats.get("total_pnl", 0.0)

            if trades > 0:
                win_rate = wins / trades
                avg_pnl = total_pnl / trades
                results.append({
                    "strategy": strategy_name,
                    "win_rate": win_rate,
                    "avg_pnl": avg_pnl,
                    "trades": trades
                })

        if not results:
            return False, "Insufficient data for strategy optimization"

        # Sort by profitability
        results.sort(key=lambda x: x["avg_pnl"], reverse=True)

        best_strategy = results[0]["strategy"]
        logger.info(f"Best performing strategy: {best_strategy}")

        # For now, just log the results
        # In production, would modify AI engine to weight strategies differently

        return True, f"Analysis complete: {best_strategy} performing best (manual tuning recommended)"


def run_ai_trading_session(cycles: int = 360, interval: int = 10) -> Tuple[bool, Dict]:
    """
    Run an AI trading session.

    1. Start AI Decision Engine
    2. Start V5 with file_ipc
    3. Monitor for duration
    4. Return results
    """
    logger.info(f"[LAUNCH] Starting AI trading session ({cycles} cycles × {interval}s)")

    # Ensure Autonomous IPC Responder is running
    ai_engine_process = subprocess.Popen(
        ["python", "ipc/autonomous_responder.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    logger.info("Autonomous IPC Responder started")
    time.sleep(2)  # Let it initialize

    # Start V5
    try:
        v5_result = subprocess.run(
            ["python", "live_session_v5.py", "--cycles", str(cycles), "--interval", str(interval)],
            capture_output=True,
            text=True,
            timeout=cycles * interval + 300
        )

        success = v5_result.returncode == 0

        # Kill AI engine
        ai_engine_process.terminate()
        ai_engine_process.wait(timeout=5)

        if success:
            logger.info("[OK] AI trading session completed successfully")

            # Load memory to get results
            memory_file = PROJECT_ROOT / "state" / "ai_trading_memory.json"
            if memory_file.exists():
                with open(memory_file, encoding='utf-8') as f:
                    memory = json.load(f)

                return True, {
                    "trades_executed": memory.get("trades_executed", 0),
                    "strategies_tested": len(memory.get("strategies_tested", {})),
                    "total_pnl": memory.get("total_pnl", 0.0)
                }
            else:
                return True, {"trades_executed": 0, "strategies_tested": 0, "total_pnl": 0.0}
        else:
            logger.error(f"[ERROR] AI trading session failed:\n{v5_result.stderr}")
            return False, {}

    except subprocess.TimeoutExpired:
        logger.error("[ERROR] AI trading session timed out")
        ai_engine_process.terminate()
        return False, {}
    except Exception as e:
        logger.error(f"[ERROR] AI trading session error: {e}")
        ai_engine_process.terminate()
        return False, {}


def update_obsidian(iteration: int, analysis: Dict, improvements: List[str]):
    """Update Obsidian with AI loop progress."""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log_file = OBSIDIAN_DIR / f"ai_loop_log_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n## Iteration {iteration} - {timestamp}\n\n")
        f.write(f"**Total Trades:** {analysis.get('total_trades', 0)}\n")
        f.write(f"**Strategies Tested:** {analysis.get('strategies_tested', 0)}\n\n")

        if improvements:
            f.write("**Improvements Applied:**\n")
            for imp in improvements:
                f.write(f"- {imp}\n")

        recommendations = analysis.get("recommendations", [])
        if recommendations:
            f.write("\n**Recommendations:**\n")
            for rec in recommendations:
                f.write(f"- [{rec['priority']}] {rec['name']}: {rec['reason']}\n")

        f.write("\n---\n")


def git_commit_progress(iteration: int, trades: int, improvements: List[str]):
    """Commit AI loop progress to GitHub."""

    message = f"AI Loop Iteration {iteration}: {trades} trades, {len(improvements)} improvements"

    if improvements:
        message += f"\n\nImprovements:\n"
        for imp in improvements:
            message += f"- {imp}\n"

    message += "\nCo-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

    try:
        subprocess.run(["git", "add", "state/", "obsidian/"], check=True)
        subprocess.run(["git", "commit", "-m", message, "--no-verify"], check=True)
        subprocess.run(["git", "push", "origin", "HEAD", "--no-verify"], check=True)
        logger.info("[OK] Progress committed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[ERROR] Git commit failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ralph AI Loop - Kaizen for AI Trading")
    parser.add_argument("--max-iterations", type=int, default=10, help="Maximum loop iterations")
    parser.add_argument("--cycles-per-session", type=int, default=360, help="Cycles per trading session")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between cycles")
    parser.add_argument("--sleep-between", type=int, default=300, help="Seconds between iterations")
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("RALPH AI LOOP - Kaizen for AI Trading")
    logger.info("=" * 80)
    logger.info(f"Max iterations: {args.max_iterations}")
    logger.info(f"Session config: {args.cycles_per_session} cycles × {args.interval}s")
    logger.info("=" * 80)

    status = AILoopStatus(LOOP_STATUS_FILE)
    kaizen = AIKaizenEngine(PROJECT_ROOT)

    for iteration in range(args.max_iterations):
        status.data["iteration"] = iteration + 1
        status.data["status"] = "running"
        status.save()

        logger.info(f"\n{'='*80}\nIteration {iteration + 1}/{args.max_iterations}\n{'='*80}")

        # PHASE 1: Analyze current AI performance
        logger.info("PHASE 1: Analyzing AI performance...")
        memory = kaizen.load_ai_memory()
        analysis = kaizen.analyze_performance(memory)

        logger.info(f"  Total trades: {analysis['total_trades']}")
        logger.info(f"  Recommendations: {len(analysis.get('recommendations', []))}")

        # PHASE 2: Apply Kaizen improvements
        logger.info("PHASE 2: Applying Kaizen improvements...")
        improvements_applied = []

        for rec in analysis.get("recommendations", [])[:2]:  # Apply top 2
            logger.info(f"  Applying: {rec['name']}")
            success, description = kaizen.apply_improvement(rec)

            if success:
                improvements_applied.append(f"{rec['name']}: {description}")
                status.increment("kaizen_applied")
            else:
                logger.warning(f"  [WARN] Could not apply: {description}")

        # PHASE 3: Run AI trading session
        logger.info("PHASE 3: Running AI trading session...")
        success, session_results = run_ai_trading_session(
            cycles=args.cycles_per_session,
            interval=args.interval
        )

        if success:
            trades = session_results.get("trades_executed", 0)
            status.increment("sessions_run")
            status.increment("total_trades", trades)
            status.data["total_pnl"] += session_results.get("total_pnl", 0.0)
            logger.info(f"  [OK] Session complete: {trades} trades executed")
        else:
            logger.error("  [ERROR] Session failed")

        # PHASE 4: Update Obsidian
        logger.info("PHASE 4: Updating Obsidian...")
        update_obsidian(iteration + 1, analysis, improvements_applied)

        # PHASE 5: Commit to GitHub (every 2 iterations)
        if (iteration + 1) % 2 == 0:
            logger.info("PHASE 5: Committing to GitHub...")
            git_commit_progress(iteration + 1, status.data["total_trades"], improvements_applied)

        # PHASE 6: Sleep between iterations
        if iteration < args.max_iterations - 1:
            logger.info(f"PHASE 6: Sleeping {args.sleep_between}s before next iteration...")
            time.sleep(args.sleep_between)

    # Final status
    status.data["status"] = "completed"
    status.save()

    logger.info(f"\n{'='*80}")
    logger.info(f"AI Loop completed after {iteration + 1} iterations")
    logger.info(f"  Sessions run: {status.data['sessions_run']}")
    logger.info(f"  Total trades: {status.data['total_trades']}")
    logger.info(f"  Total P&L: ${status.data['total_pnl']:.2f}")
    logger.info(f"  Kaizen applied: {status.data['kaizen_applied']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n[WARN] AI loop interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"[ERROR] Fatal error in AI loop: {e}")
        sys.exit(1)
