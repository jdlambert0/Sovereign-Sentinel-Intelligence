"""
Sovereign Sentinel — Off-Hours / Weekend Learning Engine
=========================================================
Safe to run anytime. No real trades. Analyzes performance,
updates calibration, and prepares the system for next session.

Usage:
  py scripts/weekend_learning.py --mode analyze
  py scripts/weekend_learning.py --mode calibrate
  py scripts/weekend_learning.py --mode simulate
  py scripts/weekend_learning.py --mode full
"""
import json
import sys
import math
import statistics
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).parent.parent
STATE_DIR = BASE_DIR / "state"
OBSIDIAN_DIR = BASE_DIR / "obsidian"

logging.basicConfig(level=logging.INFO, format='%(asctime)s [LEARN] %(message)s')
logger = logging.getLogger(__name__)


def load_memory():
    f = STATE_DIR / "ai_trading_memory.json"
    if f.exists():
        with open(f) as fp:
            return json.load(fp)
    return {"trades_executed": 0, "total_pnl": 0, "performance_by_contract": {}}


def load_trade_history():
    f = STATE_DIR / "trade_history.json"
    if f.exists():
        with open(f) as fp:
            return json.load(fp)
    return []


def save_memory(memory):
    with open(STATE_DIR / "ai_trading_memory.json", 'w') as f:
        json.dump(memory, f, indent=2)


# ─────────────────────────────────────────────────────────────
# 1. ANALYSIS MODE — review performance
# ─────────────────────────────────────────────────────────────

def run_analysis():
    logger.info("=" * 60)
    logger.info("PERFORMANCE ANALYSIS")
    logger.info("=" * 60)

    memory = load_memory()
    history = load_trade_history()

    print(f"\n{'='*60}")
    print(f"SOVEREIGN SENTINEL — LEARNING REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # Overall stats
    total_trades = memory.get("trades_executed", 0)
    total_pnl = memory.get("total_pnl", 0)
    print(f"OVERALL PERFORMANCE")
    print(f"  Total trades: {total_trades}")
    print(f"  Total PnL: ${total_pnl:,.2f}")

    # Per-contract analysis
    print(f"\nPER-CONTRACT PERFORMANCE")
    contracts = memory.get("performance_by_contract", {})
    contract_stats = []
    for contract, stats in contracts.items():
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total = wins + losses
        wr = wins / total if total > 0 else 0
        pnl = stats.get("total_pnl", 0)
        short_name = contract.split(".")[-2] if "." in contract else contract
        contract_stats.append((short_name, wins, losses, wr, pnl, total))
        print(f"  {short_name:6}: {wins}W/{losses}L = {wr:.0%} WR, PnL=${pnl:>8.2f} ({total} trades)")

    # Best/worst
    if contract_stats:
        best = max(contract_stats, key=lambda x: x[3] if x[5] >= 5 else 0)
        worst = min(contract_stats, key=lambda x: x[3] if x[5] >= 5 else 1)
        print(f"\n  BEST:  {best[0]} ({best[3]:.0%} WR)")
        print(f"  WORST: {worst[0]} ({worst[3]:.0%} WR)")

    # Recent trade analysis (last 20)
    recent = [t for t in history if t.get("outcome") is not None][-20:]
    if recent:
        r_wins = sum(1 for t in recent if t.get("outcome") == "WIN")
        r_losses = sum(1 for t in recent if t.get("outcome") == "LOSS")
        r_pnl = sum(t.get("pnl", 0) for t in recent)
        print(f"\nRECENT 20 TRADES")
        print(f"  {r_wins}W / {r_losses}L = {r_wins/(r_wins+r_losses):.0%} WR")
        print(f"  PnL: ${r_pnl:.2f}")

    # Lesson extraction
    lessons = memory.get("lessons_learned", [])
    if lessons:
        print(f"\nRECENT LESSONS ({len(lessons)} total)")
        for lesson in lessons[-5:]:
            print(f"  [{lesson.get('contract', '?')}] {lesson.get('lesson', '')[:80]}")

    # Recommendations
    print(f"\nRECOMMENDATIONS")
    for contract, stats in contracts.items():
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total = wins + losses
        wr = wins / total if total > 0 else 0.5
        short = contract.split(".")[-2] if "." in contract else contract

        if total >= 10:
            if wr < 0.35:
                print(f"  [REDUCE] {short}: {wr:.0%} WR — avoid or reduce size")
            elif wr > 0.65:
                print(f"  [PRIORITIZE] {short}: {wr:.0%} WR — increase focus")

    print(f"\n{'='*60}")
    return memory


# ─────────────────────────────────────────────────────────────
# 2. CALIBRATION MODE — update model weights
# ─────────────────────────────────────────────────────────────

def run_calibration():
    logger.info("Running calibration...")
    memory = load_memory()
    history = load_trade_history()

    # Analyze which regimes perform best
    regime_stats = {}
    phase_stats = {}

    for trade in history:
        if trade.get("outcome") is None:
            continue
        regime = trade.get("regime", "unknown")
        phase = trade.get("session_phase", "unknown")
        win = 1 if trade.get("outcome") == "WIN" else 0

        if regime not in regime_stats:
            regime_stats[regime] = {"wins": 0, "total": 0}
        regime_stats[regime]["wins"] += win
        regime_stats[regime]["total"] += 1

        if phase not in phase_stats:
            phase_stats[phase] = {"wins": 0, "total": 0}
        phase_stats[phase]["wins"] += win
        phase_stats[phase]["total"] += 1

    print("\nCALIBRATION RESULTS")
    print("\nBy Regime:")
    for regime, stats in regime_stats.items():
        wr = stats["wins"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {regime:20}: {wr:.0%} WR ({stats['total']} trades)")

    print("\nBy Session Phase:")
    for phase, stats in phase_stats.items():
        wr = stats["wins"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {phase:20}: {wr:.0%} WR ({stats['total']} trades)")

    # Update performance_by_regime in memory
    if regime_stats:
        perf_regime = {}
        for regime, stats in regime_stats.items():
            perf_regime[regime] = {
                "wins": stats["wins"],
                "losses": stats["total"] - stats["wins"],
                "total": stats["total"],
                "win_rate": round(stats["wins"] / stats["total"], 3) if stats["total"] > 0 else 0.5
            }
        memory["performance_by_regime"] = perf_regime
        memory["performance_by_session_phase"] = {}
        for phase, stats in phase_stats.items():
            memory["performance_by_session_phase"][phase] = {
                "wins": stats["wins"],
                "losses": stats["total"] - stats["wins"],
                "win_rate": round(stats["wins"] / stats["total"], 3) if stats["total"] > 0 else 0.5
            }
        save_memory(memory)
        print("\nCalibration saved to memory.")

    return memory


# ─────────────────────────────────────────────────────────────
# 3. SIMULATION MODE — paper trading replay
# ─────────────────────────────────────────────────────────────

def run_simulation(n_trades: int = 50):
    """
    Replay recent trade decisions using current probability models.
    Compare predicted signals vs actual outcomes.
    No real trades — pure learning.
    """
    logger.info(f"Running simulation with {n_trades} replays...")
    sys.path.insert(0, str(BASE_DIR))

    from mcp_server.probability_models import run_all_models

    history = load_trade_history()
    memory = load_memory()

    # Take last N completed trades
    completed = [t for t in history if t.get("outcome") and t.get("outcome") != "BREAKEVEN"]
    replay_trades = completed[-n_trades:] if len(completed) >= n_trades else completed

    if not replay_trades:
        print("No completed trades to replay.")
        return

    correct_signals = 0
    total_replayed = 0
    model_accuracy = {}  # track per-model accuracy

    print(f"\nSIMULATION: Replaying {len(replay_trades)} trades")
    print("-" * 60)

    for trade in replay_trades:
        actual_action = trade.get("action", "")
        actual_outcome = trade.get("outcome", "")
        entry_price = trade.get("entry_price", 0)
        contract = trade.get("contract", "")

        # Build a minimal snapshot from trade data
        snapshot = {
            "contract_id": contract,
            "price": entry_price,
            "ofi_z": 0.5 if actual_action == "LONG" else -0.5,  # reconstruct from action
            "vpin": 0.6,
            "atr_ticks": 12,
            "regime": trade.get("regime", "trending_up" if actual_action == "LONG" else "trending_down"),
            "session_phase": trade.get("session_phase", "us_core"),
            "account_balance": 149276,
            "prices_history": [entry_price]
        }

        models_result = run_all_models(snapshot, memory)
        predicted = models_result["summary"]["dominant_signal"]

        # Did our models agree with the actual trade AND outcome?
        predicted_correct = (predicted == actual_action)
        outcome_correct = predicted_correct and actual_outcome == "WIN"

        total_replayed += 1
        if outcome_correct:
            correct_signals += 1

        # Track model-level accuracy
        for model_name, model_result in models_result["models"].items():
            if model_name not in model_accuracy:
                model_accuracy[model_name] = {"correct": 0, "total": 0}
            model_accuracy[model_name]["total"] += 1
            if model_result["signal"] == actual_action and actual_outcome == "WIN":
                model_accuracy[model_name]["correct"] += 1

    if total_replayed > 0:
        accuracy = correct_signals / total_replayed
        print(f"\nSimulation Results:")
        print(f"  Signal accuracy: {accuracy:.0%} ({correct_signals}/{total_replayed})")

        print(f"\nModel Accuracy Ranking:")
        model_acc_list = [
            (name, stats["correct"] / stats["total"] if stats["total"] > 0 else 0)
            for name, stats in model_accuracy.items()
        ]
        model_acc_list.sort(key=lambda x: x[1], reverse=True)
        for name, acc in model_acc_list[:6]:
            print(f"  {name:30}: {acc:.0%}")

    return model_accuracy


# ─────────────────────────────────────────────────────────────
# 4. MEMORY CONSOLIDATION — distill short-term to long-term
# ─────────────────────────────────────────────────────────────

def run_consolidation():
    """
    FinMem-style memory consolidation.
    Promote high-novelty, high-importance lessons to long-term memory.
    """
    logger.info("Running memory consolidation...")
    memory = load_memory()
    history = load_trade_history()

    # Identify patterns in recent trades
    recent_40 = [t for t in history if t.get("outcome")][-40:]
    if len(recent_40) < 10:
        print("Need at least 10 trades for consolidation.")
        return

    # Streak analysis
    outcomes = [t.get("outcome") for t in recent_40]
    longest_win_streak = 0
    longest_loss_streak = 0
    current_streak = 1
    for i in range(1, len(outcomes)):
        if outcomes[i] == outcomes[i-1]:
            current_streak += 1
        else:
            current_streak = 1
        if outcomes[i] == "WIN":
            longest_win_streak = max(longest_win_streak, current_streak)
        else:
            longest_loss_streak = max(longest_loss_streak, current_streak)

    # Hour-of-day analysis (if timestamp available)
    hour_performance = {}
    for trade in recent_40:
        ts = trade.get("timestamp", "")
        if ts:
            try:
                hour = int(ts[11:13])  # UTC hour from ISO timestamp
                ct_hour = (hour - 6) % 24  # rough CT conversion
                if ct_hour not in hour_performance:
                    hour_performance[ct_hour] = {"wins": 0, "total": 0}
                hour_performance[ct_hour]["total"] += 1
                if trade.get("outcome") == "WIN":
                    hour_performance[ct_hour]["wins"] += 1
            except Exception:
                pass

    # Write consolidated insight to obsidian
    best_hour = max(hour_performance.items(), key=lambda x: x[1]["wins"] / x[1]["total"] if x[1]["total"] >= 3 else 0, default=(None, {}))
    insight = f"""
## Memory Consolidation — {datetime.now().strftime('%Y-%m-%d')}

- Recent 40 trades analyzed
- Longest win streak: {longest_win_streak}
- Longest loss streak: {longest_loss_streak}
- Best hour (CT): {best_hour[0]}:00 ({best_hour[1].get('wins', 0)}/{best_hour[1].get('total', 0)} = {best_hour[1].get('wins', 0)/best_hour[1].get('total', 1):.0%} WR) if valid

Key insight: {"Win streaks possible — momentum compounds" if longest_win_streak >= 3 else "Mixed results — reversion dominant"}
"""

    obs_file = OBSIDIAN_DIR / f"consolidation_{datetime.now().strftime('%Y%m%d')}.md"
    with open(obs_file, 'w') as f:
        f.write(insight)
    print(f"Consolidation written to {obs_file.name}")
    print(insight)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sovereign Sentinel Learning Engine")
    parser.add_argument("--mode", choices=["analyze", "calibrate", "simulate", "consolidate", "full"],
                        default="analyze")
    parser.add_argument("--n-trades", type=int, default=50)
    args = parser.parse_args()

    if args.mode == "analyze" or args.mode == "full":
        run_analysis()

    if args.mode == "calibrate" or args.mode == "full":
        run_calibration()

    if args.mode == "simulate" or args.mode == "full":
        run_simulation(args.n_trades)

    if args.mode == "consolidate" or args.mode == "full":
        run_consolidation()

    if args.mode == "full":
        print("\n[LEARN] Full learning session complete.")
        print("Run /trade tomorrow during market hours.\n")
