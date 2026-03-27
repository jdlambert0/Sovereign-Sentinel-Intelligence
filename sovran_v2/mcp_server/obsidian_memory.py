"""
Obsidian Memory Module
=====================
Read from and write to the Sovereign Obsidian vault.
This is the AI's persistent memory across LLM sessions.

Jesse's rule: "If it's not in obsidian, it didn't happen."
"""
import json
import os
import glob
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

OBSIDIAN_DIR = Path(r"C:\KAI\sovran_v2\obsidian")
STATE_DIR = Path(r"C:\KAI\sovran_v2\state")
THESIS_FILE = STATE_DIR / "current_thesis.json"
TRADE_HISTORY_FILE = STATE_DIR / "trade_history.json"
MEMORY_FILE = STATE_DIR / "ai_trading_memory.json"

# Key obsidian files
PHILOSOPHY_FILE = OBSIDIAN_DIR / "ai_trading_philosophy.md"
HANDOFF_FILE = OBSIDIAN_DIR / "SESSION_HANDOFF_CURRENT.md"
TRADING_RULES_FILE = OBSIDIAN_DIR / "trading_rules.md"


def query_memory(topic: str = "recent_trades") -> Dict[str, Any]:
    """
    Query obsidian memory for trading context.
    topic: "recent_trades" | "philosophy" | "handoff" | "trading_rules" | "thesis" | "performance"
    """
    if topic == "recent_trades":
        return _get_recent_trades(n=10)
    elif topic == "philosophy":
        return _read_file_safe(PHILOSOPHY_FILE)
    elif topic == "handoff":
        return _read_file_safe(HANDOFF_FILE)
    elif topic == "trading_rules":
        return _read_file_safe(TRADING_RULES_FILE)
    elif topic == "thesis":
        return get_current_thesis()
    elif topic == "performance":
        return _get_performance_summary()
    else:
        # Try to find file by topic name
        matches = list(OBSIDIAN_DIR.glob(f"*{topic}*"))
        if matches:
            return _read_file_safe(matches[0])
        return {"error": f"Unknown topic: {topic}",
                "available": ["recent_trades", "philosophy", "handoff", "trading_rules", "thesis", "performance"]}


def get_current_thesis() -> Dict[str, Any]:
    """
    Get the current AI trading thesis (persists across sessions).
    This is the 'temporal context buffer' — what the AI believes right now.
    """
    if THESIS_FILE.exists():
        try:
            with open(THESIS_FILE) as f:
                data = json.load(f)
            # Add staleness check
            updated_at = data.get("updated_at", "")
            if updated_at:
                dt = datetime.fromisoformat(updated_at)
                age_hours = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else datetime.now(timezone.utc) - dt).total_seconds() / 3600
                data["_age_hours"] = round(age_hours, 1)
                data["_stale"] = age_hours > 4
            return data
        except Exception as e:
            return {"error": str(e), "thesis": "No thesis loaded"}
    return {
        "thesis": "No thesis yet — this is a fresh start.",
        "updated_at": None,
        "session_number": 0,
        "_stale": True
    }


def save_current_thesis(thesis: str, market_bias: str = "NEUTRAL",
                        key_levels: Optional[List[float]] = None,
                        watch_contracts: Optional[List[str]] = None,
                        reasoning: str = "") -> Dict[str, Any]:
    """
    Persist the AI's current market thesis.
    Called at start of each trading session and when thesis changes.
    """
    STATE_DIR.mkdir(exist_ok=True)
    existing = get_current_thesis()
    session_n = existing.get("session_number", 0) + 1

    data = {
        "thesis": thesis,
        "market_bias": market_bias,
        "key_levels": key_levels or [],
        "watch_contracts": watch_contracts or ["MNQ", "MES", "MGC", "MCL"],
        "reasoning": reasoning,
        "session_number": session_n,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "sovereign_mcp"
    }

    with open(THESIS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return {"status": "saved", "session_number": session_n, "thesis": thesis[:100] + "..."}


def log_trade_thesis(contract: str, action: str, thesis: str,
                     conviction: int, models_summary: Dict[str, Any],
                     entry_price: float, sl_ticks: float, tp_ticks: float) -> Dict[str, Any]:
    """
    Log the AI's reasoning BEFORE a trade is placed.
    This is the pre-trade decision record.
    """
    STATE_DIR.mkdir(exist_ok=True)

    entry = {
        "type": "trade_thesis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contract": contract,
        "action": action,
        "thesis": thesis,
        "conviction": conviction,
        "entry_price": entry_price,
        "sl_ticks": sl_ticks,
        "tp_ticks": tp_ticks,
        "models_summary": models_summary,
        "outcome": None  # filled later by log_trade_outcome
    }

    # Append to trade history
    history = _load_json_list(TRADE_HISTORY_FILE)
    history.append(entry)
    _save_json_list(TRADE_HISTORY_FILE, history)

    # Also write to obsidian for cross-session memory
    _write_obsidian_trade_log(entry)

    return {"status": "logged", "trade_id": len(history), "contract": contract, "action": action}


def log_trade_outcome(trade_id: int, outcome: str, pnl: float,
                      exit_price: float, lesson: str = "") -> Dict[str, Any]:
    """
    Record the outcome of a trade and update Bayesian memory.
    outcome: "WIN" | "LOSS" | "BREAKEVEN"
    """
    history = _load_json_list(TRADE_HISTORY_FILE)

    # Find the trade (1-indexed)
    idx = trade_id - 1
    if 0 <= idx < len(history):
        history[idx]["outcome"] = outcome
        history[idx]["pnl"] = pnl
        history[idx]["exit_price"] = exit_price
        history[idx]["lesson"] = lesson
        history[idx]["closed_at"] = datetime.now(timezone.utc).isoformat()
        _save_json_list(TRADE_HISTORY_FILE, history)

        # Update Bayesian memory
        _update_bayesian_memory(history[idx])

        return {"status": "updated", "trade_id": trade_id, "outcome": outcome, "pnl": pnl}
    else:
        # Try to update last open trade
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("outcome") is None:
                history[i]["outcome"] = outcome
                history[i]["pnl"] = pnl
                history[i]["exit_price"] = exit_price
                history[i]["lesson"] = lesson
                history[i]["closed_at"] = datetime.now(timezone.utc).isoformat()
                _save_json_list(TRADE_HISTORY_FILE, history)
                _update_bayesian_memory(history[i])
                return {"status": "updated_last_open", "trade_id": i + 1, "pnl": pnl}

        return {"error": f"Trade {trade_id} not found"}


def get_recent_trades(n: int = 10) -> Dict[str, Any]:
    """Get the N most recent trades with outcomes for LLM context."""
    return _get_recent_trades(n)


def get_philosophy() -> Dict[str, Any]:
    """Get the AI trading philosophy and commandments."""
    return _read_file_safe(PHILOSOPHY_FILE)


def get_performance_summary() -> Dict[str, Any]:
    """Get current performance metrics from Bayesian memory."""
    return _get_performance_summary()


def write_observation(observation: str, category: str = "market") -> Dict[str, Any]:
    """
    Log a real-time observation to obsidian.
    category: "market" | "signal" | "learning" | "system"
    """
    obs_dir = OBSIDIAN_DIR / "observations"
    obs_dir.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = obs_dir / f"{category}_{ts}.md"

    content = f"""---
type: observation
category: {category}
timestamp: {datetime.now(timezone.utc).isoformat()}
---

{observation}
"""
    with open(filename, 'w') as f:
        f.write(content)

    return {"status": "written", "file": str(filename)}


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _read_file_safe(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            with open(path, encoding='utf-8') as f:
                content = f.read()
            return {"content": content, "file": path.name, "size": len(content)}
        except Exception as e:
            return {"error": str(e), "file": str(path)}
    return {"error": f"File not found: {path}", "file": str(path)}


def _load_json_list(path: Path) -> List[Dict]:
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _save_json_list(path: Path, data: List[Dict]):
    path.parent.mkdir(exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _get_recent_trades(n: int = 10) -> Dict[str, Any]:
    history = _load_json_list(TRADE_HISTORY_FILE)
    recent = history[-n:] if len(history) >= n else history
    wins = sum(1 for t in recent if t.get("outcome") == "WIN")
    losses = sum(1 for t in recent if t.get("outcome") == "LOSS")
    total_pnl = sum(t.get("pnl", 0) for t in recent if t.get("pnl") is not None)

    return {
        "trades": recent,
        "count": len(recent),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / (wins + losses), 3) if (wins + losses) > 0 else None,
        "total_pnl": round(total_pnl, 2),
        "total_trades_all_time": len(history)
    }


def _get_performance_summary() -> Dict[str, Any]:
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE) as f:
                memory = json.load(f)
            return {
                "trades_executed": memory.get("trades_executed", 0),
                "total_pnl": memory.get("total_pnl", 0),
                "performance_by_contract": memory.get("performance_by_contract", {}),
                "performance_by_regime": memory.get("performance_by_regime", {}),
                "lessons_learned": memory.get("lessons_learned", [])[-5:],  # last 5
                "last_update": memory.get("last_update")
            }
        except Exception as e:
            return {"error": str(e)}
    return {"error": "No memory file found", "trades_executed": 0}


def _write_obsidian_trade_log(entry: Dict[str, Any]):
    """Append trade to the obsidian trade log for cross-session memory."""
    log_file = OBSIDIAN_DIR / "trade_log.md"
    ts = entry.get("timestamp", "")[:16]
    line = f"\n| {ts} | {entry.get('contract')} | {entry.get('action')} | conv={entry.get('conviction')} | {entry.get('thesis', '')[:60]}... |"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line)


def _update_bayesian_memory(trade: Dict[str, Any]):
    """Update ai_trading_memory.json with trade outcome."""
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE) as f:
                memory = json.load(f)
        except Exception:
            memory = {"trades_executed": 0, "total_pnl": 0, "performance_by_contract": {},
                      "performance_by_regime": {}, "lessons_learned": []}
    else:
        memory = {"trades_executed": 0, "total_pnl": 0, "performance_by_contract": {},
                  "performance_by_regime": {}, "lessons_learned": []}

    contract = trade.get("contract", "")
    outcome = trade.get("outcome")
    pnl = trade.get("pnl", 0) or 0
    regime = trade.get("regime", "unknown")

    # Update by contract
    if contract not in memory["performance_by_contract"]:
        memory["performance_by_contract"][contract] = {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0}

    c = memory["performance_by_contract"][contract]
    c["trades"] = c.get("trades", 0) + 1
    c["total_pnl"] = round(c.get("total_pnl", 0) + pnl, 2)
    if outcome == "WIN":
        c["wins"] = c.get("wins", 0) + 1
    elif outcome == "LOSS":
        c["losses"] = c.get("losses", 0) + 1

    # Update totals
    memory["trades_executed"] = memory.get("trades_executed", 0) + 1
    memory["total_pnl"] = round(memory.get("total_pnl", 0) + pnl, 2)

    # Save lesson if provided
    lesson = trade.get("lesson", "")
    if lesson:
        memory.setdefault("lessons_learned", []).append({
            "timestamp": trade.get("closed_at", ""),
            "contract": contract,
            "lesson": lesson
        })

    memory["last_update"] = datetime.now(timezone.utc).isoformat()
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)
