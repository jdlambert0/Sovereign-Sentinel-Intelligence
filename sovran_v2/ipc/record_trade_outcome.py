#!/usr/bin/env python3
"""
Record trade outcomes to AI trading memory.
Called from live_session_v5.py after each trade closes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict

# Memory file location
MEMORY_FILE = Path(__file__).parent.parent / "state" / "ai_trading_memory.json"


def load_memory() -> Dict:
    """Load AI trading memory."""
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "trades_executed": 0,
        "total_pnl": 0.0,
        "strategies_tested": {},
        "market_patterns": {},
        "performance_by_contract": {},
        "performance_by_time": {},
        "performance_by_regime": {},
        "lessons_learned": [],
        "last_update": None
    }


def save_memory(data: Dict):
    """Save AI trading memory."""
    data["last_update"] = datetime.now(timezone.utc).isoformat()
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def record_outcome(contract: str, strategy: str, regime: str, pnl: float, hold_time: float,
                  mfe: float = 0.0, mae: float = 0.0):
    """
    Record trade outcome to memory.

    Args:
        contract: Contract ID (e.g., "CON.F.US.MNQ.M26")
        strategy: Strategy used ("momentum" or "mean_reversion")
        regime: Market regime ("trending_up", "trending_down", "choppy", etc.)
        pnl: Profit/loss in dollars
        mfe: Maximum Favorable Excursion (best profit during trade)
        mae: Maximum Adverse Excursion (worst loss during trade)
        hold_time: Hold time in seconds
    """
    memory = load_memory()
    is_win = pnl > 0

    # Ensure contract exists
    if contract not in memory["performance_by_contract"]:
        memory["performance_by_contract"][contract] = {
            "trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0
        }

    # Ensure strategy exists
    if strategy not in memory["strategies_tested"]:
        memory["strategies_tested"][strategy] = {
            "trades": 0, "wins": 0, "total_pnl": 0.0, "avg_hold_time": 0.0
        }

    # Ensure regime exists
    if regime not in memory["performance_by_regime"]:
        memory["performance_by_regime"][regime] = {
            "trades": 0, "wins": 0, "total_pnl": 0.0
        }

    # Update contract performance
    memory["performance_by_contract"][contract]["total_pnl"] += pnl
    if is_win:
        memory["performance_by_contract"][contract]["wins"] += 1
    elif pnl < 0:
        memory["performance_by_contract"][contract]["losses"] += 1

    # Track MFE/MAE for diagnostics
    if "mfe_mae_data" not in memory:
        memory["mfe_mae_data"] = []
    memory["mfe_mae_data"].append({
        "contract": contract,
        "strategy": strategy,
        "regime": regime,
        "pnl": pnl,
        "mfe": mfe,
        "mae": mae,
        "hold_time": hold_time,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_win": is_win
    })
    # Keep last 100 trades for analysis
    if len(memory["mfe_mae_data"]) > 100:
        memory["mfe_mae_data"] = memory["mfe_mae_data"][-100:]

    # Update strategy performance
    memory["strategies_tested"][strategy]["total_pnl"] += pnl
    if is_win:
        memory["strategies_tested"][strategy]["wins"] += 1

    # Update average hold time
    strat_data = memory["strategies_tested"][strategy]
    current_avg = strat_data.get("avg_hold_time", 0.0)
    current_count = strat_data["trades"]
    if current_count > 0:
        new_avg = ((current_avg * current_count) + hold_time) / (current_count + 1)
        strat_data["avg_hold_time"] = new_avg

    # Update regime performance
    memory["performance_by_regime"][regime]["total_pnl"] += pnl
    if is_win:
        memory["performance_by_regime"][regime]["wins"] += 1

    # Update total P&L
    memory["total_pnl"] += pnl

    save_memory(memory)
    print(f"[OK] Outcome recorded: {strategy} {contract} {'WIN' if is_win else 'LOSS'} ${pnl:+.2f}")


if __name__ == "__main__":
    # Can be called from command line: python record_trade_outcome.py MNQ momentum trending_up 10.5 180 [mfe] [mae]
    if len(sys.argv) >= 6:
        contract = sys.argv[1]
        strategy = sys.argv[2]
        regime = sys.argv[3]
        pnl = float(sys.argv[4])
        hold_time = float(sys.argv[5])
        mfe = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
        mae = float(sys.argv[7]) if len(sys.argv) > 7 else 0.0
        record_outcome(contract, strategy, regime, pnl, hold_time, mfe, mae)
    else:
        print("Usage: python record_trade_outcome.py <contract> <strategy> <regime> <pnl> <hold_time> [mfe] [mae]")
        print("Example: python record_trade_outcome.py MNQ momentum trending_up 10.5 180 15.2 -8.3")
        sys.exit(1)
