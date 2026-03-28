#!/usr/bin/env python3
"""
Sovereign Sentinel Intelligence  -  MCP Server
=============================================
Any LLM with MCP support connects with one command:
  py -3.12 C:\\KAI\\sovran_v2\\mcp_server\\run_server.py

This replaces the IPC file protocol. The LLM IS the trader.
5 clean signals (OFI/VPIN, VWAP structure, momentum, volatility, session context).
LLM adversarial reasoning is the brain. Python computes signals, LLM decides.
Obsidian is the persistent memory.

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
from datetime import datetime, timezone, timedelta
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
            description="Record your reasoning BEFORE placing a trade. This is mandatory for every trade  -  logged to obsidian for cross-session learning.",
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
        # No IPC files  -  return simulated snapshot for testing
        return _simulated_snapshot(contract_id)

    # Get most recent request(s)
    snapshots = []
    seen_contracts = set()
    for f in reversed(request_files[-20:]):  # check last 20 files
        try:
            with open(f) as fp:
                data = json.load(fp)
            # IPC files from decision.py nest fields under "snapshot_data"
            # Fall back to top-level if snapshot_data is absent (legacy format)
            sd = data.get("snapshot_data", data)
            cid = sd.get("contract_id", data.get("contract_id", ""))
            if cid and cid not in seen_contracts:
                age_secs = time.time() - f.stat().st_mtime
                # Flatten snapshot_data into snap; normalize IPC field names
                snap = dict(sd)
                snap["contract_id"] = cid
                snap["_age_seconds"] = round(age_secs, 1)
                snap["_file"] = f.name
                # Normalize: IPC uses last_price/atr_points/ofi_zscore; _compute_signals uses price/atr_ticks/ofi_z
                if "price" not in snap:
                    snap["price"] = snap.get("last_price", snap.get("mid_price", 0.0))
                if "atr_ticks" not in snap:
                    snap["atr_ticks"] = snap.get("atr_points", 12.0)
                if "ofi_z" not in snap:
                    snap["ofi_z"] = snap.get("ofi_zscore", 0.0)
                snap.setdefault("vpin", 0.5)
                snap.setdefault("vwap", 0.0)
                snap.setdefault("prices_history", [])
                snap.setdefault("high_of_session", snap["price"])
                snap.setdefault("low_of_session", snap["price"])
                snapshots.append(snap)
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
        return {"error": "No credentials  -  cannot place trade",
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

            result = await broker.place_market_order(
                contract_id=contract_id,
                side=side,
                size=n_contracts,
                stop_loss_ticks=sl_ticks,
                take_profit_ticks=tp_ticks
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


def _compute_signals(snap: dict) -> dict:
    """
    Compute 5 clean signals from an enriched market snapshot.
    Returns a dict with labeled signal strings and direction/conviction per signal.
    Replaces run_all_models()  -  only OFI/VPIN has proven signal; others add context.
    """
    ofi_z = snap.get("ofi_z", 0.0)
    vpin = snap.get("vpin", 0.5)
    price = snap.get("price", 0.0)
    vwap = snap.get("vwap", 0.0)
    atr = snap.get("atr_ticks", 12.0)
    avg_atr = snap.get("avg_atr_ticks", atr)
    high_sess = snap.get("high_of_session", price)
    low_sess = snap.get("low_of_session", price)
    prices_history = snap.get("prices_history", [price])

    # --- Signal 1: Order Flow (OFI + VPIN)  -  primary oracle ---
    if ofi_z > 1.5 and vpin > 0.60:
        of_label = f"STRONG BULLISH (OFI {ofi_z:+.1f}s, VPIN {vpin:.2f}  -  informed buying confirmed)"
        of_dir, of_conv = "LONG", min(90, 60 + int(abs(ofi_z) * 10))
    elif ofi_z > 0.8:
        of_label = f"MILD BULLISH (OFI {ofi_z:+.1f}s  -  buy pressure building)"
        of_dir, of_conv = "LONG", int(50 + abs(ofi_z) * 8)
    elif ofi_z < -1.5 and vpin > 0.60:
        of_label = f"STRONG BEARISH (OFI {ofi_z:+.1f}s, VPIN {vpin:.2f}  -  informed selling confirmed)"
        of_dir, of_conv = "SHORT", min(90, 60 + int(abs(ofi_z) * 10))
    elif ofi_z < -0.8:
        of_label = f"MILD BEARISH (OFI {ofi_z:+.1f}s  -  sell pressure building)"
        of_dir, of_conv = "SHORT", int(50 + abs(ofi_z) * 8)
    else:
        of_label = f"NEUTRAL (OFI {ofi_z:+.1f}s  -  no informed flow detected)"
        of_dir, of_conv = "NEUTRAL", 25

    # --- Signal 2: Price Structure (VWAP + session range) ---
    range_size = high_sess - low_sess
    range_pct = ((price - low_sess) / range_size * 100) if range_size > 0.01 else 50.0
    if vwap > 0.01:
        vwap_dev_pct = (price - vwap) / vwap * 100
        if vwap_dev_pct > 0.10:
            ps_label = f"ABOVE VWAP +{vwap_dev_pct:.2f}% (bullish structure, {range_pct:.0f}% of session range)"
            ps_dir = "LONG"
        elif vwap_dev_pct < -0.10:
            ps_label = f"BELOW VWAP {vwap_dev_pct:.2f}% (bearish structure, {range_pct:.0f}% of session range)"
            ps_dir = "SHORT"
        else:
            ps_label = f"AT VWAP (+-{abs(vwap_dev_pct):.2f}%, {range_pct:.0f}% of session range  -  balanced)"
            ps_dir = "NEUTRAL"
    else:
        ps_label = f"VWAP unavailable  -  session range {range_pct:.0f}% consumed (H:{high_sess:.1f} L:{low_sess:.1f})"
        ps_dir = "NEUTRAL"

    # --- Signal 3: Momentum (from prices_history rolling buffer) ---
    if len(prices_history) >= 5:
        recent = prices_history[-5:]
        roc = (recent[-1] - recent[0]) / recent[0] * 100 if recent[0] > 0 else 0
        up_bars = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i-1])
        if roc > 0.05 and up_bars >= 3:
            mom_label = f"UPWARD MOMENTUM ({roc:+.3f}%, {up_bars}/4 bars up)"
            mom_dir = "LONG"
        elif roc < -0.05 and up_bars <= 1:
            mom_label = f"DOWNWARD MOMENTUM ({roc:+.3f}%, {4-up_bars}/4 bars down)"
            mom_dir = "SHORT"
        else:
            mom_label = f"FLAT/MIXED ({roc:+.3f}%, {up_bars}/4 bars up  -  choppy)"
            mom_dir = "NEUTRAL"
    else:
        mom_label = "UNAVAILABLE (live_session must run >5 bars before momentum is valid)"
        mom_dir = "NEUTRAL"

    # --- Signal 4: Volatility Regime ---
    vol_ratio = atr / avg_atr if avg_atr > 0.01 else 1.0
    if vol_ratio > 1.5:
        vol_label = f"HIGH ({atr:.1f}t vs {avg_atr:.1f}t avg = {vol_ratio:.1f}x)  -  widen stops, reduce size"
        vol_regime = "high"
    elif vol_ratio < 0.7:
        vol_label = f"LOW ({atr:.1f}t vs {avg_atr:.1f}t avg = {vol_ratio:.1f}x)  -  tighter spreads, normal size"
        vol_regime = "low"
    else:
        vol_label = f"NORMAL ({atr:.1f}t vs {avg_atr:.1f}t avg)"
        vol_regime = "normal"

    # --- Signal 5: Session Context (CT time) ---
    now_ct = datetime.now(timezone(timedelta(hours=-5)))
    ct_mins = now_ct.hour * 60 + now_ct.minute
    if 510 <= ct_mins < 525:
        sess_label = "ORB WINDOW (8:30-8:45 CT)  -  establishing range, await breakout confirmation"
        sess_ctx = "orb_window"
    elif 525 <= ct_mins < 600:
        sess_label = "POWER HOUR (8:45-10:00 CT)  -  highest probability setups, full aggression"
        sess_ctx = "power_hour"
    elif 600 <= ct_mins < 840:
        sess_label = "MID-SESSION (10:00 AM-2:00 PM CT)  -  mean reversion favored"
        sess_ctx = "mid_session"
    elif 840 <= ct_mins < 935:
        sess_label = "PRE-CLOSE (2:00-3:55 PM CT)  -  watch for late squeezes"
        sess_ctx = "pre_close"
    else:
        sess_label = f"OUTSIDE HOURS ({now_ct.strftime('%H:%M')} CT)"
        sess_ctx = "outside_hours"

    return {
        "of_label": of_label, "of_dir": of_dir, "of_conv": of_conv,
        "ps_label": ps_label, "ps_dir": ps_dir,
        "mom_label": mom_label, "mom_dir": mom_dir,
        "vol_label": vol_label, "vol_regime": vol_regime,
        "sess_label": sess_label, "sess_ctx": sess_ctx,
    }


def _build_hunt_context(snap: dict, signals: dict, memory: dict,
                        all_results: list, daily_pnl: float) -> str:
    """
    Build a semantic English context packet for LLM reasoning.
    Uses doubled-text technique: role instruction repeated at top AND bottom
    to counteract lost-in-the-middle effect and improve LLM decision quality.
    """
    contract = snap.get("contract_id", "?")
    price = snap.get("price", 0.0)
    atr = snap.get("atr_ticks", 12.0)
    tick_val = snap.get("tick_value", 0.50)

    sl_ticks = max(8, round(atr * 0.8))
    tp_ticks = round(sl_ticks * 1.8)
    risk_per_contract = sl_ticks * tick_val
    reward_per_contract = tp_ticks * tick_val

    perf = memory.get("performance_by_contract", {}).get(contract, {})
    wins = perf.get("wins", 0)
    losses = perf.get("losses", 0)
    hist_summary = f"{wins}W/{losses}L on this contract" if (wins + losses) > 0 else "No history on this contract"

    alts = [r for r in all_results if r.get("contract_id") != contract]
    alt_summary = "; ".join(
        f"{r['name']} {r['signal']} conv={r['conviction']}"
        for r in alts[:3]
    ) if alts else "No alternatives"

    # Doubled-text: same role+task instruction at BOTH top and bottom
    header = (
        "You are an expert intraday futures trader with deep knowledge of order flow and market "
        "microstructure. Analyze this market snapshot and decide: LONG, SHORT, or a LOW-conviction "
        "probe trade. Never idle  -  always find the best available setup."
    )
    footer = (
        "You are an expert intraday futures trader with deep knowledge of order flow and market "
        "microstructure. Your decision: LONG / SHORT / NO_TRADE. "
        "Conviction: HIGH / MEDIUM / LOW. "
        "State your BEAR CASE, BULL CASE, SYNTHESIS, and one-sentence THESIS."
    )

    return f"""{header}

MARKET SNAPSHOT  -  {contract} @ {price:.2f}  [{datetime.now().strftime('%H:%M CT')}]
===============================================================

ORDER FLOW (PRIMARY SIGNAL):
  {signals['of_label']}

PRICE STRUCTURE:
  {signals['ps_label']}

MOMENTUM:
  {signals['mom_label']}

VOLATILITY REGIME:
  {signals['vol_label']}

SESSION CONTEXT:
  {signals['sess_label']}{(chr(10) + chr(10) + "ORB SIGNAL:" + chr(10) + "  " + signals['orb_bonus']) if signals.get('orb_bonus') else ""}

SUGGESTED TRADE PARAMETERS (Python math  -  LLM may adjust):
  Stop: {sl_ticks} ticks (${risk_per_contract:.0f}/contract)
  Target: {tp_ticks} ticks (${reward_per_contract:.0f}/contract)
  R:R = 1:{tp_ticks/sl_ticks:.1f}

ACCOUNT CONTEXT:
  Daily PnL today: ${daily_pnl:+.0f} (cap: $2,700  -  DO NOT exceed)
  Historical: {hist_summary}

OTHER CONTRACTS (ranked by conviction):
  {alt_summary}

{footer}""".strip()


def _calculate_position_size(conviction: str, account_balance: float,
                              starting_balance: float = 147000.0,
                              daily_pnl: float = 0.0) -> int:
    """
    TopStepX Express Funded Account scaling tiers:
      Starting balance: 2 contracts
      +$1,500 above starting: 3 contracts
      +$2,000 above starting: 5 contracts
    Conviction multiplier: HIGH=platform max, MEDIUM=half (min 2), LOW=1 probe.
    """
    gain = account_balance - starting_balance

    if gain >= 2000:
        platform_max = 5
    elif gain >= 1500:
        platform_max = 3
    else:
        platform_max = 2

    # Approaching daily cap → cap at 1 contract regardless of conviction
    if daily_pnl >= 2500 * 0.75:  # $1,875
        platform_max = min(platform_max, 1)

    conviction_fraction = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.25}.get(conviction, 0.0)
    if conviction_fraction == 0.0:
        return 0

    raw = max(1, int(platform_max * conviction_fraction + 0.5))  # +0.5 avoids banker's rounding (e.g. 2.5 -> 3 not 2)
    return min(raw, platform_max)


def _check_news_veto() -> str:
    """
    NEW-2: Macro Event Gate.
    Returns a non-empty string (event name) if within 30 min of a high-impact event.
    Returns '' if safe to trade.
    Hardcoded 2026 calendar. Update monthly.
    """
    now_ct = datetime.now(timezone(timedelta(hours=-5)))
    # Minutes since midnight CT
    ct_mins = now_ct.hour * 60 + now_ct.minute
    today = now_ct.strftime("%Y-%m-%d")

    # High-impact 2026 event schedule (CT times, format: "YYYY-MM-DD": [(hhmm, "Name")])
    # FOMC: 1:00 PM CT announcement + 1:30 PM press conf
    # CPI: 7:30 AM CT release
    # NFP: 7:30 AM CT (first Friday of month)
    # PPI: 7:30 AM CT
    EVENTS_2026: Dict[str, list] = {
        # FOMC decisions (1:00 PM CT)
        "2026-01-29": [(780, "FOMC Rate Decision")],
        "2026-03-18": [(780, "FOMC Rate Decision")],
        "2026-05-07": [(780, "FOMC Rate Decision")],
        "2026-06-10": [(780, "FOMC Rate Decision")],
        "2026-07-29": [(780, "FOMC Rate Decision")],
        "2026-09-16": [(780, "FOMC Rate Decision")],
        "2026-11-04": [(780, "FOMC Rate Decision")],
        "2026-12-16": [(780, "FOMC Rate Decision")],
        # CPI releases (7:30 AM CT)
        "2026-01-15": [(450, "CPI Release")],
        "2026-02-11": [(450, "CPI Release")],
        "2026-03-11": [(450, "CPI Release")],
        "2026-04-10": [(450, "CPI Release")],
        "2026-05-13": [(450, "CPI Release")],
        "2026-06-10": [(450, "CPI Release")],
        "2026-07-14": [(450, "CPI Release")],
        "2026-08-12": [(450, "CPI Release")],
        "2026-09-11": [(450, "CPI Release")],
        "2026-10-14": [(450, "CPI Release")],
        "2026-11-12": [(450, "CPI Release")],
        "2026-12-10": [(450, "CPI Release")],
        # NFP (first Friday of month, 7:30 AM CT)
        "2026-01-09": [(450, "NFP Jobs Report")],
        "2026-02-06": [(450, "NFP Jobs Report")],
        "2026-03-06": [(450, "NFP Jobs Report")],
        "2026-04-03": [(450, "NFP Jobs Report")],
        "2026-05-01": [(450, "NFP Jobs Report")],
        "2026-06-05": [(450, "NFP Jobs Report")],
        "2026-07-10": [(450, "NFP Jobs Report")],
        "2026-08-07": [(450, "NFP Jobs Report")],
        "2026-09-04": [(450, "NFP Jobs Report")],
        "2026-10-02": [(450, "NFP Jobs Report")],
        "2026-11-06": [(450, "NFP Jobs Report")],
        "2026-12-04": [(450, "NFP Jobs Report")],
    }

    VETO_WINDOW = 30  # minutes before and after event
    for event_time_mins, event_name in EVENTS_2026.get(today, []):
        if abs(ct_mins - event_time_mins) <= VETO_WINDOW:
            delta = ct_mins - event_time_mins
            timing = f"{abs(delta)}min {'after' if delta > 0 else 'before'}"
            return f"{event_name} ({timing})"

    return ""


async def _hunt_and_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full autonomous trade cycle in a single call.
    - Handles TopStepX single-connection constraint (stops running session if needed)
    - Scans all contracts, computes 5 clean signals, builds semantic context for LLM
    - dry_run=True: returns semantic context for LLM reasoning (2-step skill flow)
    - dry_run=False: places trade directly using Python conviction score
    - Returns complete decision audit trail
    """
    import subprocess, time as time_mod

    conviction_threshold = args.get("conviction_threshold", 65)
    dry_run = args.get("dry_run", False)

    # ── Step 1: Kill ai_decision_engine (NOT live_session) ──────────────────
    # live_session_v5 must keep running  -  it is the OFI/VPIN data provider.
    # We only kill ai_decision_engine.py so the LLM (us) can be the brain.
    # live_session will continue writing IPC request files; we respond to them.
    session_mode = "direct"
    pid_file = SOVRAN_DIR / "trading.pid"

    # Kill ai_decision_engine if running (it competes with LLM for IPC responses)
    engine_pid_file = SOVRAN_DIR / "ipc" / "ai_engine.pid"
    if not engine_pid_file.exists():
        engine_pid_file = SOVRAN_DIR / "ipc_responder.pid"
    if engine_pid_file.exists():
        try:
            pid = int(engine_pid_file.read_text().strip())
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, timeout=5)
            engine_pid_file.unlink(missing_ok=True)
            logger.info(f"Killed ai_decision_engine (PID {pid})  -  LLM is now the brain")
        except Exception as e:
            logger.warning(f"Could not kill ai_decision_engine: {e} (may not be running)")

    # Check for fresh IPC request files (live_session is actively running)
    fresh_ipc = False
    ipc_snapshot: Dict[str, Any] = {}
    request_files = sorted(IPC_DIR.glob("request_*.json"), key=lambda p: p.stat().st_mtime)
    if request_files:
        age = time_mod.time() - request_files[-1].stat().st_mtime
        fresh_ipc = age < 120  # < 2 minutes old
        if fresh_ipc:
            try:
                with open(request_files[-1]) as f:
                    ipc_snapshot = json.load(f)
                session_mode = "live_session_ipc"
                logger.info(f"Reading live OFI/VPIN from IPC: age={age:.0f}s")
            except Exception:
                pass

    if not fresh_ipc:
        if pid_file.exists():
            session_mode = "live_session_no_data"
            logger.warning("live_session running but no fresh IPC data  -  OFI/VPIN will be cold")
        else:
            session_mode = "direct_cold"
            logger.warning("live_session not running  -  start it for live OFI/VPIN data")

    # ── Step 2: Get market snapshot for all contracts ───────────────────────
    # If we have a live IPC snapshot, inject its OFI/VPIN into the market data
    snapshots_result = await _get_market_snapshot("all")
    contract_snaps = snapshots_result.get("contracts", []) if isinstance(snapshots_result, dict) else []

    # Enrich snapshots with IPC OFI/VPIN/VWAP if available
    if ipc_snapshot and contract_snaps:
        ipc_sd = ipc_snapshot.get("snapshot_data", ipc_snapshot)  # support both formats
        ipc_contract = ipc_sd.get("contract_id", ipc_snapshot.get("contract_id", ""))
        for snap in contract_snaps:
            if snap.get("contract_id") == ipc_contract or not snap.get("contract_id"):
                snap["ofi_z"] = ipc_sd.get("ofi_zscore", ipc_sd.get("ofi_z", snap.get("ofi_z", 0.0)))
                snap["vpin"] = ipc_sd.get("vpin", snap.get("vpin", 0.5))
                snap["atr_ticks"] = ipc_sd.get("atr_points", ipc_sd.get("atr_ticks", snap.get("atr_ticks", 12.0)))
                snap["vwap"] = ipc_sd.get("vwap", snap.get("vwap", 0.0))
                snap["high_of_session"] = ipc_sd.get("high_of_session", snap.get("high_of_session", snap.get("price", 0.0)))
                snap["low_of_session"] = ipc_sd.get("low_of_session", snap.get("low_of_session", snap.get("price", 0.0)))
                snap["prices_history"] = ipc_sd.get("prices_history", snap.get("prices_history", []))
                snap["_ipc_enriched"] = True

    if not contract_snaps:
        return {
            "action": "NO_TRADE",
            "reason": "No market data available (market closed or no IPC files)",
            "session_mode": session_mode,
            "hint": "Market must be open and live_session_v5.py running to get live data"
        }

    # ── Step 3: Compute 5 clean signals on each contract ────────────────────
    # Replaces 12-model voting (8/12 were broken/correlated).
    # Order Flow (OFI+VPIN) is the oracle. VWAP/momentum/vol/session add context.
    memory = _load_memory()
    best = {"conviction": 0, "contract_id": None, "signal": "NEUTRAL", "snap": {}, "signals": {}}
    all_results = []

    for snap in contract_snaps:
        if not snap.get("price") or snap.get("price", 0) <= 0:
            continue
        try:
            signals = _compute_signals(snap)
            of_conv = signals["of_conv"]
            of_dir = signals["of_dir"]

            # Alignment bonuses: other signals confirming order flow direction
            alignment_bonus = 10 if signals["ps_dir"] == of_dir and of_dir != "NEUTRAL" else 0
            mom_bonus = 5 if signals["mom_dir"] == of_dir and of_dir != "NEUTRAL" else 0
            vol_penalty = -10 if signals["vol_regime"] == "high" else 0
            conv = max(0, min(100, of_conv + alignment_bonus + mom_bonus + vol_penalty))

            contract_name = CONTRACT_NAMES.get(snap.get("contract_id", ""), snap.get("contract_id", ""))
            all_results.append({
                "contract_id": snap.get("contract_id"),
                "name": contract_name,
                "price": snap.get("price"),
                "conviction": conv,
                "signal": of_dir,
                "ofi_z": round(snap.get("ofi_z", 0), 3),
                "vpin": round(snap.get("vpin", 0.5), 3),
                "signals_summary": signals,
            })

            if conv > best["conviction"]:
                best = {
                    "conviction": conv,
                    "contract_id": snap.get("contract_id"),
                    "signal": of_dir,
                    "snap": snap,
                    "signals": signals,
                }
        except Exception as e:
            logger.warning(f"Signal computation failed for {snap.get('contract_id')}: {e}")
            continue

    # Sort by conviction descending
    all_results.sort(key=lambda x: x["conviction"], reverse=True)

    # ── Step 3b: ORB bonus — boost conviction if price breaks opening range ─────
    # Uses session high/low as ORB proxy (valid after ORB window closes at 8:45 CT)
    if best.get("signals") and best.get("snap"):
        _orb_ctx = best["signals"].get("sess_ctx", "")
        if _orb_ctx == "power_hour":  # 8:45-10:00 CT — post-ORB breakout window
            _orb_price = best["snap"].get("price", 0)
            _orb_high  = best["snap"].get("high_of_session", _orb_price)
            _orb_low   = best["snap"].get("low_of_session", _orb_price)
            _orb_range = _orb_high - _orb_low
            _orb_atr   = best["snap"].get("atr_ticks", 12.0)
            if _orb_range > 0.3 * _orb_atr:  # range is meaningful (not flat)
                if best["signal"] == "LONG" and _orb_price >= _orb_high:
                    best["conviction"] = min(100, best["conviction"] + 8)
                    best["signals"]["orb_bonus"] = f"ORB BREAKOUT LONG (price at/above {_orb_high:.2f} session high)"
                elif best["signal"] == "SHORT" and _orb_price <= _orb_low:
                    best["conviction"] = min(100, best["conviction"] + 8)
                    best["signals"]["orb_bonus"] = f"ORB BREAKDOWN SHORT (price at/below {_orb_low:.2f} session low)"

    # ── Step 4: Decision ────────────────────────────────────────────────────
    phase = _current_session_phase()

    # NEW-2: Macro Event Gate — veto trades within 30 min of high-impact news
    news_veto = _check_news_veto()
    if news_veto:
        return {
            "action": "NO_TRADE",
            "reason": f"NEWS VETO: {news_veto}. Wait 30 min after event.",
            "all_scanned": all_results,
        }

    # TopStep Consistency Rule check (max $2,700/day on $150K/9K target)
    daily_pnl = _get_daily_pnl_from_memory()
    MAX_DAILY_PROFIT = 2500.0
    CAUTION_THRESHOLD = MAX_DAILY_PROFIT * 0.75  # $1,875
    if daily_pnl >= MAX_DAILY_PROFIT:
        return {
            "action": "NO_TRADE",
            "reason": f"Daily profit cap reached: ${daily_pnl:.2f} >= ${MAX_DAILY_PROFIT:.0f}. STOP for today  -  TopStep consistency rule.",
            "daily_pnl": daily_pnl,
            "all_scanned": all_results
        }
    in_caution = daily_pnl >= CAUTION_THRESHOLD
    effective_threshold = max(conviction_threshold, 80) if in_caution else conviction_threshold

    if phase == "outside_hours":
        return {
            "action": "NO_TRADE",
            "reason": "Outside market hours (8am-4pm CT)",
            "phase": phase,
            "all_scanned": all_results,
            "best_setup": best.get("contract_id"),
            "best_conviction": best["conviction"]
        }

    # Build semantic context (always  -  returned in both dry_run and low-conviction responses)
    semantic_context = _build_hunt_context(
        best["snap"], best["signals"], memory, all_results, daily_pnl
    ) if best.get("snap") else "No best contract found  -  all signals neutral."

    # Pre-compute suggested stops for dry_run response
    best_atr = best["snap"].get("atr_ticks", 12.0) if best.get("snap") else 12.0
    suggested_sl = max(8, round(best_atr * 0.8))
    suggested_tp = round(suggested_sl * 1.8)

    if best["conviction"] < effective_threshold:
        return {
            "action": "NO_TRADE",
            "reason": f"Best conviction {best['conviction']} < threshold {effective_threshold}" +
                      (" [CAUTION MODE: daily PnL near cap]" if in_caution else ""),
            "best_setup": best.get("contract_id"),
            "best_conviction": best["conviction"],
            "best_signal": best["signal"],
            "all_scanned": all_results,
            "session_mode": session_mode,
            "daily_pnl": daily_pnl,
            "semantic_context": semantic_context,
            "advice": "Conviction below threshold  -  but LLM may override using semantic_context above."
        }

    if dry_run:
        return {
            "action": "DRY_RUN",
            "would_trade": best.get("contract_id"),
            "would_direction": best["signal"],
            "conviction_score": best["conviction"],
            "semantic_context": semantic_context,
            "suggested_sl_ticks": suggested_sl,
            "suggested_tp_ticks": suggested_tp,
            "all_scanned": all_results,
            "session_mode": session_mode,
            "daily_pnl": daily_pnl,
            "note": "dry_run=True  -  LLM should reason about semantic_context and call place_trade if confirmed"
        }

    # ── Step 5: Place the trade ─────────────────────────────────────────────
    contract = best["contract_id"]
    signal = best["signal"]
    snap = best["snap"]
    sl = suggested_sl
    tp = suggested_tp

    sigs = best.get("signals", {})
    reasoning = (
        f"hunt_and_trade: {signal} conv={best['conviction']} "
        f"| OF: {sigs.get('of_label', 'n/a')[:60]} "
        f"| {sigs.get('ps_label', '')[:40]}"
    )

    # Conviction-based position sizing (TopStepX scaling tiers)
    if best["conviction"] >= 75:
        conviction_label = "HIGH"
    elif best["conviction"] >= 55:
        conviction_label = "MEDIUM"
    else:
        conviction_label = "LOW"

    # Use account balance from broker if available, fallback to config default
    try:
        from src.broker import BrokerClient as _BC
        _broker = _BC()
        acct_balance = getattr(_broker, "account_balance", None) or 147000.0
    except Exception:
        acct_balance = 147000.0

    n_contracts = _calculate_position_size(
        conviction=conviction_label,
        account_balance=acct_balance,
        starting_balance=147000.0,
        daily_pnl=daily_pnl,
    )

    trade_result = await _place_trade({
        "action": "LONG" if signal == "LONG" else "SHORT",
        "contract_id": contract,
        "sl_ticks": sl,
        "tp_ticks": tp,
        "contracts": n_contracts,
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
            models_summary=sigs,
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
        "conviction_label": conviction_label,
        "contracts": n_contracts,
        "sl_ticks": sl,
        "tp_ticks": tp,
        "entry_price": snap.get("price"),
        "trade_result": trade_result,
        "all_scanned": all_results,
        "session_mode": session_mode,
        "reasoning": reasoning
    }


def _get_daily_pnl_from_memory() -> float:
    """Best-effort daily PnL from trade history. Used for consistency cap check."""
    try:
        from datetime import date
        today = date.today().isoformat()
        history_file = SOVRAN_DIR / "state" / "trade_history.json"
        if not history_file.exists():
            return 0.0
        with open(history_file) as f:
            trades = json.load(f)
        daily = sum(
            t.get("pnl", 0) or 0
            for t in trades
            if isinstance(t, dict) and t.get("timestamp", "")[:10] == today and t.get("outcome") in ("WIN", "LOSS", "BREAKEVEN")
        )
        return round(daily, 2)
    except Exception:
        return 0.0


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
        "note": "Real-time data unavailable  -  using cached state"
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
        "_note": "No IPC files found  -  this is a cold-start or test snapshot"
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
        logger.info("No current thesis  -  AI should call save_thesis after first assessment")

    # Run server via stdio transport (LLM connects via stdin/stdout)
    async with stdio_server() as streams:
        await app.run(*streams, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
