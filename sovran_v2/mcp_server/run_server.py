#!/usr/bin/env python3
"""
Sovereign Sentinel Intelligence — MCP Server
=============================================
Any LLM with MCP support connects with one command:
  py -3.12 C:\\KAI\\sovran_v2\\mcp_server\\run_server.py

This replaces the IPC file protocol. The LLM IS the trader.
All 12 probability models run live. Obsidian is the persistent memory.

Tools exposed:
  - get_market_snapshot   : current market state for all 6 contracts
  - run_probability_models: run all 12 models on a contract
  - query_memory          : query obsidian (philosophy, trades, thesis, rules)
  - place_trade           : execute a trade via TopStepX API
  - get_account_status    : balance, positions, open orders
  - log_trade_thesis      : record reasoning before a trade
  - log_trade_outcome     : record result after a trade
  - save_thesis           : persist the AI's current market thesis
  - write_observation     : log a market observation to obsidian
"""
import asyncio
import json
import os
import sys
import time
import logging
import glob as glob_module
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add sovran_v2 to path so we can import src modules
SOVRAN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SOVRAN_DIR))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Sovereign modules
from mcp_server.probability_models import run_all_models
from mcp_server.obsidian_memory import (
    query_memory, get_current_thesis, save_current_thesis,
    log_trade_thesis, log_trade_outcome, get_recent_trades,
    get_philosophy, get_performance_summary, write_observation
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SOVEREIGN-MCP] %(message)s',
    handlers=[
        logging.FileHandler(SOVRAN_DIR / "logs" / "mcp_server.log"),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

IPC_DIR = SOVRAN_DIR / "ipc"
STATE_DIR = SOVRAN_DIR / "state"
MEMORY_FILE = STATE_DIR / "ai_trading_memory.json"

# Credentials (loaded from env or secrets file)
def _load_credentials() -> Dict[str, str]:
    creds = {
        "username": os.environ.get("TOPSTEPX_USERNAME", ""),
        "api_key": os.environ.get("TOPSTEPX_API_KEY", ""),
    }
    if not creds["username"]:
        secrets_file = SOVRAN_DIR.parent / "sovran_v2_secrets" / "credentials.env"
        if secrets_file.exists():
            with open(secrets_file) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        if "USERNAME" in k.upper():
                            creds["username"] = v.strip()
                        elif "API_KEY" in k.upper() or "APIKEY" in k.upper():
                            creds["api_key"] = v.strip()
    return creds

CREDS = _load_credentials()

# ─────────────────────────────────────────────────────────────
# MCP Server
# ─────────────────────────────────────────────────────────────

app = Server("sovereign-sentinel")

CONTRACTS = [
    "CON.F.US.MNQ.M26",
    "CON.F.US.MES.M26",
    "CON.F.US.MYM.M26",
    "CON.F.US.M2K.M26",
    "CON.F.US.MGC.M26",
    "CON.F.US.MCL.M26"
]

CONTRACT_NAMES = {
    "CON.F.US.MNQ.M26": "MNQ (Nasdaq micro)",
    "CON.F.US.MES.M26": "MES (S&P micro)",
    "CON.F.US.MYM.M26": "MYM (Dow micro)",
    "CON.F.US.M2K.M26": "M2K (Russell 2000 micro)",
    "CON.F.US.MGC.M26": "MGC (Gold micro)",
    "CON.F.US.MCL.M26": "MCL (Crude Oil micro)"
}

CONTRACT_PRIORITY = {
    "CON.F.US.MNQ.M26": "HIGH",
    "CON.F.US.MES.M26": "HIGH",
    "CON.F.US.MYM.M26": "NEUTRAL",
    "CON.F.US.M2K.M26": "REDUCE",
    "CON.F.US.MGC.M26": "PRIORITY+10%",
    "CON.F.US.MCL.M26": "PRIORITY+10%"
}


@app.list_tools()
async def list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="get_market_snapshot",
            description="Get the current market snapshot from the latest IPC request file. Returns price, OFI, VPIN, ATR, regime, session phase, and account info for one or all contracts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "Contract ID (e.g. CON.F.US.MNQ.M26) or 'all' for all contracts",
                        "default": "all"
                    }
                }
            }
        ),
        types.Tool(
            name="run_probability_models",
            description="Run all 12 probability models on a contract snapshot. Returns signals, conviction scores, and reasoning from: Kelly, Poker EV, Casino Edge, Market Making, Stat Arb, Volatility, Momentum, Order Flow, Bayesian, Monte Carlo, Risk of Ruin, Information Theory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "Contract ID to analyze"
                    },
                    "snapshot": {
                        "type": "object",
                        "description": "Market snapshot dict (from get_market_snapshot). If omitted, reads latest IPC file."
                    }
                },
                "required": ["contract_id"]
            }
        ),
        types.Tool(
            name="query_memory",
            description="Query the obsidian persistent memory. Returns trading philosophy, recent trades, current thesis, trading rules, or performance summary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": ["recent_trades", "philosophy", "handoff", "trading_rules", "thesis", "performance"],
                        "description": "What to query",
                        "default": "recent_trades"
                    }
                }
            }
        ),
        types.Tool(
            name="place_trade",
            description="Execute a trade via TopStepX API. Requires action, contract_id, and risk parameters. Always include reasoning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["LONG", "SHORT", "CLOSE"],
                        "description": "Trade direction"
                    },
                    "contract_id": {
                        "type": "string",
                        "description": "Contract to trade"
                    },
                    "sl_ticks": {
                        "type": "number",
                        "description": "Stop loss in ticks"
                    },
                    "tp_ticks": {
                        "type": "number",
                        "description": "Take profit in ticks"
                    },
                    "contracts": {
                        "type": "integer",
                        "description": "Number of contracts (default 1)",
                        "default": 1
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why you're making this trade (logged to obsidian)"
                    },
                    "conviction": {
                        "type": "integer",
                        "description": "0-100 conviction score",
                        "default": 70
                    }
                },
                "required": ["action", "contract_id", "sl_ticks", "tp_ticks", "reasoning"]
            }
        ),
        types.Tool(
            name="get_account_status",
            description="Get current account balance, open positions, daily PnL, and trading limits from TopStepX.",
            inputSchema={
                "type": "object",
                "properties": {
                    "refresh": {
                        "type": "boolean",
                        "description": "Force fresh API call (default: use cached)",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="log_trade_thesis",
            description="Record your reasoning BEFORE placing a trade. This is mandatory for every trade — logged to obsidian for cross-session learning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract": {"type": "string"},
                    "action": {"type": "string", "enum": ["LONG", "SHORT"]},
                    "thesis": {"type": "string", "description": "Full reasoning for this trade"},
                    "conviction": {"type": "integer"},
                    "entry_price": {"type": "number"},
                    "sl_ticks": {"type": "number"},
                    "tp_ticks": {"type": "number"},
                    "models_summary": {"type": "object", "description": "Output from run_probability_models summary"}
                },
                "required": ["contract", "action", "thesis", "conviction", "entry_price", "sl_ticks", "tp_ticks"]
            }
        ),
        types.Tool(
            name="log_trade_outcome",
            description="Record the result of a trade after it closes. Updates Bayesian memory for future learning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trade_id": {"type": "integer", "description": "Trade ID from log_trade_thesis"},
                    "outcome": {"type": "string", "enum": ["WIN", "LOSS", "BREAKEVEN"]},
                    "pnl": {"type": "number", "description": "Realized PnL in dollars"},
                    "exit_price": {"type": "number"},
                    "lesson": {"type": "string", "description": "What you learned from this trade"}
                },
                "required": ["outcome", "pnl", "exit_price"]
            }
        ),
        types.Tool(
            name="save_thesis",
            description="Persist your current market thesis to obsidian. Next LLM session will start with this context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thesis": {"type": "string", "description": "Your current market thesis"},
                    "market_bias": {"type": "string", "enum": ["LONG", "SHORT", "NEUTRAL"]},
                    "key_levels": {"type": "array", "items": {"type": "number"}, "description": "Key price levels to watch"},
                    "watch_contracts": {"type": "array", "items": {"type": "string"}, "description": "Contracts to prioritize"},
                    "reasoning": {"type": "string"}
                },
                "required": ["thesis"]
            }
        ),
        types.Tool(
            name="write_observation",
            description="Log a real-time market observation to obsidian memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "observation": {"type": "string"},
                    "category": {"type": "string", "enum": ["market", "signal", "learning", "system"], "default": "market"}
                },
                "required": ["observation"]
            }
        ),
        types.Tool(
            name="hunt_and_trade",
            description=(
                "ONE-CALL autonomous trade hunt. Scans all 6 contracts, runs all 12 probability "
                "models, places the best trade if conviction >= threshold. Handles TopStepX single-"
                "connection constraint automatically (stops any running session first). "
                "Returns full decision with reasoning. Use this instead of calling get_market_snapshot + "
                "run_probability_models + place_trade separately."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "conviction_threshold": {
                        "type": "integer",
                        "description": "Minimum conviction (0-100) to place a trade. Default: 65.",
                        "default": 65
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, run all analysis but do NOT place any trade. Useful for checking current setup.",
                        "default": False
                    }
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    try:
        result = await _dispatch_tool(name, arguments)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e), "tool": name}))]


async def _dispatch_tool(name: str, args: Dict[str, Any]) -> Any:
    if name == "get_market_snapshot":
        return await _get_market_snapshot(args.get("contract_id", "all"))

    elif name == "run_probability_models":
        contract_id = args["contract_id"]
        snapshot = args.get("snapshot")
        if not snapshot:
            snapshots = await _get_market_snapshot(contract_id)
            snapshot = snapshots if isinstance(snapshots, dict) and "price" in snapshots else (
                snapshots.get("contracts", [{}])[0] if isinstance(snapshots, dict) else {}
            )
        memory = _load_memory()
        return run_all_models(snapshot, memory)

    elif name == "query_memory":
        topic = args.get("topic", "recent_trades")
        return query_memory(topic)

    elif name == "place_trade":
        return await _place_trade(args)

    elif name == "get_account_status":
        return await _get_account_status(args.get("refresh", False))

    elif name == "log_trade_thesis":
        return log_trade_thesis(
            contract=args["contract"],
            action=args["action"],
            thesis=args["thesis"],
            conviction=args["conviction"],
            models_summary=args.get("models_summary", {}),
            entry_price=args["entry_price"],
            sl_ticks=args["sl_ticks"],
            tp_ticks=args["tp_ticks"]
        )

    elif name == "log_trade_outcome":
        return log_trade_outcome(
            trade_id=args.get("trade_id", -1),
            outcome=args["outcome"],
            pnl=args["pnl"],
            exit_price=args["exit_price"],
            lesson=args.get("lesson", "")
        )

    elif name == "save_thesis":
        return save_current_thesis(
            thesis=args["thesis"],
            market_bias=args.get("market_bias", "NEUTRAL"),
            key_levels=args.get("key_levels"),
            watch_contracts=args.get("watch_contracts"),
            reasoning=args.get("reasoning", "")
        )

    elif name == "write_observation":
        return write_observation(args["observation"], args.get("category", "market"))

    elif name == "hunt_and_trade":
        return await _hunt_and_trade(args)

    else:
        return {"error": f"Unknown tool: {name}"}


# ─────────────────────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────────────────────

async def _get_market_snapshot(contract_id: str = "all") -> Dict[str, Any]:
    """Read the latest IPC request file(s) to get market state."""
    IPC_DIR.mkdir(exist_ok=True)

    request_files = sorted(IPC_DIR.glob("request_*.json"), key=lambda p: p.stat().st_mtime)

    if not request_files:
        # No IPC files — return simulated snapshot for testing
        return _simulated_snapshot(contract_id)

    # Get most recent request(s)
    snapshots = []
    seen_contracts = set()
    for f in reversed(request_files[-20:]):  # check last 20 files
        try:
            with open(f) as fp:
                data = json.load(fp)
            cid = data.get("contract_id", "")
            if cid and cid not in seen_contracts:
                age_secs = time.time() - f.stat().st_mtime
                data["_age_seconds"] = round(age_secs, 1)
                data["_file"] = f.name
                snapshots.append(data)
                seen_contracts.add(cid)
        except Exception:
            continue

    if contract_id == "all":
        return {
            "contracts": snapshots,
            "count": len(snapshots),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contracts_available": list(seen_contracts),
            "priority_guide": CONTRACT_PRIORITY
        }
    else:
        # Filter to requested contract
        for s in snapshots:
            if s.get("contract_id") == contract_id:
                s["name"] = CONTRACT_NAMES.get(contract_id, contract_id)
                s["priority"] = CONTRACT_PRIORITY.get(contract_id, "NEUTRAL")
                return s
        return {"error": f"No recent data for {contract_id}",
                "available": list(seen_contracts),
                **_simulated_snapshot(contract_id)}


async def _get_account_status(refresh: bool = False) -> Dict[str, Any]:
    """Get account status from TopStepX API."""
    if not CREDS["username"] or not CREDS["api_key"]:
        return {"error": "No credentials found",
                "hint": "Set TOPSTEPX_USERNAME and TOPSTEPX_API_KEY env vars, or create C:\\KAI\\sovran_v2_secrets\\credentials.env"}

    try:
        import sys
        sys.path.insert(0, str(SOVRAN_DIR))
        from src.broker import BrokerClient

        async with BrokerClient(CREDS["username"], CREDS["api_key"]) as broker:
            await broker.connect()
            account_info = await broker.get_account_info()
            try:
                positions = await broker.get_open_positions()
            except Exception:
                positions = []

            return {
                "account_id": broker.account_id,
                "balance": broker.account_balance,
                "account_info": account_info,
                "open_positions": positions,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        logger.error(f"Account status failed: {e}")
        # Fall back to state file
        return _cached_account_status(str(e))


async def _place_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a trade via TopStepX API."""
    action = args["action"]
    contract_id = args["contract_id"]
    sl_ticks = args["sl_ticks"]
    tp_ticks = args["tp_ticks"]
    n_contracts = args.get("contracts", 1)
    reasoning = args.get("reasoning", "")
    conviction = args.get("conviction", 70)

    logger.info(f"TRADE REQUEST: {action} {contract_id} SL={sl_ticks} TP={tp_ticks} conviction={conviction}")

    if not CREDS["username"] or not CREDS["api_key"]:
        return {"error": "No credentials — cannot place trade",
                "hint": "Set credentials in C:\\KAI\\sovran_v2_secrets\\credentials.env"}

    # Safety checks
    if conviction < 65:
        return {"status": "BLOCKED", "reason": f"Conviction {conviction} below threshold 65. No trade."}

    # Get current price for logging
    snapshot = await _get_market_snapshot(contract_id)
    current_price = snapshot.get("price", 0) if isinstance(snapshot, dict) else 0

    try:
        from src.broker import BrokerClient

        async with BrokerClient(CREDS["username"], CREDS["api_key"]) as broker:
            await broker.connect()

            # Place the order
            side = "BUY" if action == "LONG" else "SELL"

            result = await broker.place_bracket_order(
                contract_id=contract_id,
                side=side,
                size=n_contracts,
                sl_ticks=sl_ticks,
                tp_ticks=tp_ticks
            )

            trade_result = {
                "status": "PLACED",
                "action": action,
                "contract_id": contract_id,
                "contracts": n_contracts,
                "sl_ticks": sl_ticks,
                "tp_ticks": tp_ticks,
                "conviction": conviction,
                "entry_price": current_price,
                "broker_response": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reasoning": reasoning[:200]
            }
            logger.info(f"TRADE PLACED: {trade_result}")
            return trade_result

    except Exception as e:
        logger.error(f"Trade placement failed: {e}")
        return {"status": "FAILED", "error": str(e),
                "action": action, "contract_id": contract_id}


async def _hunt_and_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full autonomous trade cycle in a single call.
    - Handles TopStepX single-connection constraint (stops running session if needed)
    - Scans all contracts, runs all 12 models, places best trade
    - Returns complete decision audit trail
    """
    import subprocess, time as time_mod

    conviction_threshold = args.get("conviction_threshold", 65)
    dry_run = args.get("dry_run", False)

    # ── Step 1: Connection conflict detection ───────────────────────────────
    session_mode = "direct"
    pid_file = SOVRAN_DIR / "trading.pid"
    stop_signal_path = SOVRAN_DIR / "stop_signal.txt"

    # Check for fresh IPC files (session is actively running)
    fresh_ipc = False
    request_files = sorted(IPC_DIR.glob("request_*.json"), key=lambda p: p.stat().st_mtime)
    if request_files:
        age = time_mod.time() - request_files[-1].stat().st_mtime
        fresh_ipc = age < 120  # < 2 minutes old

    if fresh_ipc and pid_file.exists():
        if dry_run:
            session_mode = "ipc_read_only"  # dry run: just read, don't conflict
        else:
            # Stop the running session so we can take the connection
            try:
                pid = int(pid_file.read_text().strip())
                stop_signal_path.write_text("STOP")
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=5)
                time_mod.sleep(2)
                session_mode = "direct_took_over"
                logger.info(f"Stopped running session (PID {pid}) to take connection")
            except Exception as e:
                session_mode = "ipc_fallback"
                logger.warning(f"Could not stop session: {e} — using IPC snapshot only")
    elif not fresh_ipc and not pid_file.exists():
        session_mode = "direct_cold"

    # ── Step 2: Get market snapshot for all contracts ───────────────────────
    snapshots_result = await _get_market_snapshot("all")
    contract_snaps = snapshots_result.get("contracts", []) if isinstance(snapshots_result, dict) else []

    if not contract_snaps:
        return {
            "action": "NO_TRADE",
            "reason": "No market data available (market closed or no IPC files)",
            "session_mode": session_mode,
            "hint": "Market must be open and live_session_v5.py running to get live data"
        }

    # ── Step 3: Run all 12 models on each contract ──────────────────────────
    memory = _load_memory()
    best = {"conviction": 0, "contract_id": None, "signal": "NEUTRAL", "snap": {}, "models": {}}
    all_results = []

    for snap in contract_snaps:
        if not snap.get("price") or snap.get("price", 0) <= 0:
            continue
        try:
            result = run_all_models(snap, memory)
            summary = result.get("summary", {})
            conv = summary.get("consensus_strength", 0)
            signal = summary.get("dominant_signal", "NEUTRAL")
            ofi_z = snap.get("ofi_z", 0)
            vpin = snap.get("vpin", 0)

            all_results.append({
                "contract": snap.get("contract_id"),
                "name": snap.get("name", snap.get("contract_id", "")),
                "price": snap.get("price"),
                "conviction": conv,
                "signal": signal,
                "ofi_z": round(ofi_z, 3),
                "vpin": round(vpin, 3),
                "data_age_secs": snap.get("_age_seconds", 999)
            })

            if conv > best["conviction"]:
                best = {
                    "conviction": conv,
                    "contract_id": snap.get("contract_id"),
                    "signal": signal,
                    "snap": snap,
                    "models": result,
                    "ofi_z": ofi_z,
                    "vpin": vpin
                }
        except Exception as e:
            logger.warning(f"Model run failed for {snap.get('contract_id')}: {e}")
            continue

    # Sort by conviction descending
    all_results.sort(key=lambda x: x["conviction"], reverse=True)

    # ── Step 4: Decision ────────────────────────────────────────────────────
    phase = _current_session_phase()

    if phase == "outside_hours":
        return {
            "action": "NO_TRADE",
            "reason": "Outside market hours (8am-4pm CT)",
            "phase": phase,
            "all_scanned": all_results,
            "best_setup": best.get("contract_id"),
            "best_conviction": best["conviction"]
        }

    if best["conviction"] < conviction_threshold:
        return {
            "action": "NO_TRADE",
            "reason": f"Best conviction {best['conviction']} < threshold {conviction_threshold}",
            "best_setup": best.get("contract_id"),
            "best_conviction": best["conviction"],
            "best_signal": best["signal"],
            "all_scanned": all_results,
            "session_mode": session_mode,
            "advice": "Wait for higher conviction setup. Models are uncertain right now."
        }

    if dry_run:
        return {
            "action": "DRY_RUN",
            "would_trade": best.get("contract_id"),
            "would_direction": best["signal"],
            "conviction": best["conviction"],
            "all_scanned": all_results,
            "note": "dry_run=True — no trade placed"
        }

    # ── Step 5: Place the trade ─────────────────────────────────────────────
    contract = best["contract_id"]
    signal = best["signal"]
    snap = best["snap"]
    atr = snap.get("atr_ticks", 12.0)
    sl = max(8, round(atr * 0.8))
    tp = round(sl * 1.8)

    models_summary = best["models"].get("summary", {})
    reasoning = (
        f"hunt_and_trade: {signal} conv={best['conviction']} "
        f"OFI_Z={best['ofi_z']:.2f} VPIN={best['vpin']:.3f} "
        f"| {models_summary.get('reasoning', '')}"
    )

    trade_result = await _place_trade({
        "action": "LONG" if signal == "LONG" else "SHORT",
        "contract_id": contract,
        "sl_ticks": sl,
        "tp_ticks": tp,
        "contracts": 1,
        "conviction": best["conviction"],
        "reasoning": reasoning
    })

    # Log thesis to obsidian
    try:
        log_trade_thesis(
            contract=contract,
            action="LONG" if signal == "LONG" else "SHORT",
            thesis=reasoning,
            conviction=best["conviction"],
            models_summary=models_summary,
            entry_price=snap.get("price", 0),
            sl_ticks=sl,
            tp_ticks=tp
        )
    except Exception:
        pass

    return {
        "action": "LONG" if signal == "LONG" else "SHORT",
        "contract": contract,
        "conviction": best["conviction"],
        "sl_ticks": sl,
        "tp_ticks": tp,
        "entry_price": snap.get("price"),
        "trade_result": trade_result,
        "all_scanned": all_results,
        "session_mode": session_mode,
        "reasoning": reasoning
    }


def _load_memory() -> Dict[str, Any]:
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"trades_executed": 0, "total_pnl": 0, "performance_by_contract": {}}


def _cached_account_status(error: str = "") -> Dict[str, Any]:
    """Return cached/estimated account status when API fails."""
    memory = _load_memory()
    return {
        "status": "cached",
        "error": error,
        "estimated_balance": 149276.0,  # last known from handoff
        "trades_executed": memory.get("trades_executed", 0),
        "total_pnl": memory.get("total_pnl", 0),
        "note": "Real-time data unavailable — using cached state"
    }


def _simulated_snapshot(contract_id: str) -> Dict[str, Any]:
    """Return a minimal snapshot when no IPC files exist (for testing/cold start)."""
    base_prices = {
        "CON.F.US.MNQ.M26": 18500.0,
        "CON.F.US.MES.M26": 5250.0,
        "CON.F.US.MYM.M26": 42000.0,
        "CON.F.US.M2K.M26": 2100.0,
        "CON.F.US.MGC.M26": 2950.0,
        "CON.F.US.MCL.M26": 72.0
    }
    price = base_prices.get(contract_id, 1000.0)
    return {
        "contract_id": contract_id,
        "name": CONTRACT_NAMES.get(contract_id, contract_id),
        "price": price,
        "ofi_z": 0.0,
        "vpin": 0.5,
        "atr_ticks": 12.0,
        "regime": "ranging",
        "session_phase": _current_session_phase(),
        "account_balance": 149276.0,
        "open_positions": 0,
        "_source": "simulated",
        "_note": "No IPC files found — this is a cold-start or test snapshot"
    }


def _current_session_phase() -> str:
    """Determine trading session phase based on CT time."""
    from datetime import datetime
    import zoneinfo
    try:
        ct = datetime.now(zoneinfo.ZoneInfo("America/Chicago"))
        hour = ct.hour + ct.minute / 60
        if 8.0 <= hour < 10.0:
            return "us_open"
        elif 10.0 <= hour < 14.0:
            return "us_core"
        elif 14.0 <= hour < 16.0:
            return "us_close"
        else:
            return "outside_hours"
    except Exception:
        return "us_core"


# ─────────────────────────────────────────────────────────────
# Resources (obsidian docs accessible via obsidian:// URI)
# ─────────────────────────────────────────────────────────────

@app.list_resources()
async def list_resources() -> List[types.Resource]:
    return [
        types.Resource(
            uri="obsidian://philosophy",
            name="AI Trading Philosophy",
            description="Jesse's trading philosophy, 7 commandments, and AI trader vision",
            mimeType="text/markdown"
        ),
        types.Resource(
            uri="obsidian://thesis",
            name="Current Market Thesis",
            description="The AI's current market thesis (persists across sessions)",
            mimeType="application/json"
        ),
        types.Resource(
            uri="obsidian://recent-trades",
            name="Recent Trade History",
            description="Last 10 trades with outcomes and lessons",
            mimeType="application/json"
        ),
        types.Resource(
            uri="obsidian://performance",
            name="Performance Summary",
            description="Win rates, PnL by contract, Bayesian memory state",
            mimeType="application/json"
        ),
        types.Resource(
            uri="obsidian://handoff",
            name="Session Handoff",
            description="Current session state for LLM handoff",
            mimeType="text/markdown"
        )
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    resource_map = {
        "obsidian://philosophy": lambda: get_philosophy(),
        "obsidian://thesis": lambda: get_current_thesis(),
        "obsidian://recent-trades": lambda: get_recent_trades(10),
        "obsidian://performance": lambda: get_performance_summary(),
        "obsidian://handoff": lambda: query_memory("handoff")
    }

    handler = resource_map.get(uri)
    if handler:
        result = handler()
        if isinstance(result, dict):
            return result.get("content", json.dumps(result, indent=2, default=str))
        return str(result)
    return json.dumps({"error": f"Unknown resource: {uri}"})


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

async def main():
    # Ensure logs dir exists
    (SOVRAN_DIR / "logs").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("SOVEREIGN SENTINEL MCP SERVER STARTING")
    logger.info(f"Sovran dir: {SOVRAN_DIR}")
    logger.info(f"Credentials: {'LOADED' if CREDS['username'] else 'MISSING'}")
    logger.info(f"IPC dir: {IPC_DIR} ({'exists' if IPC_DIR.exists() else 'will create'})")
    logger.info("=" * 60)

    # Load and announce thesis
    thesis = get_current_thesis()
    if not thesis.get("_stale"):
        logger.info(f"Current thesis: {thesis.get('thesis', '')[:100]}")
    else:
        logger.info("No current thesis — AI should call save_thesis after first assessment")

    # Run server via stdio transport (LLM connects via stdin/stdout)
    async with stdio_server() as streams:
        await app.run(*streams, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
