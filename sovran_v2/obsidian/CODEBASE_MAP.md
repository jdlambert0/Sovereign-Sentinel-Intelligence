---
title: Sovereign Sentinel V2 — Complete Codebase Map
type: codebase-reference
updated: 2026-03-27 (evening — LLM-as-brain architecture)
purpose: Find root causes fast. Every file, what it does, when to touch it.
---

# SOVEREIGN SENTINEL V2 — CODEBASE MAP

Use this file to find root causes fast. If something breaks, start here.

---

## DIRECTORY STRUCTURE

```
C:\KAI\sovran_v2\
├── ralph_ai_loop.py          ← ORCHESTRATOR: starts/stops sessions, applies Kaizen
├── ralph_meta_loop.py        ← CODE IMPROVER: reads kaizen_backlog, patches files
├── live_session_v5.py        ← MAIN TRADER: V5 Goldilocks Edition (current version)
├── live_session_v4.py        ← DEPRECATED: V4 session (kept for reference)
├── run.py                    ← Simple entry point
│
├── ipc/                      ← IPC FILE PROTOCOL (LLM bridge)
│   ├── ai_decision_engine.py      ← AI BRAIN: reads requests, writes responses
│   ├── autonomous_responder.py    ← ZOMBIE PROCESS: kills itself on sight
│   ├── record_trade_outcome.py    ← Records outcomes to Bayesian memory
│   ├── mfe_mae_diagnostics.py     ← MFE/MAE analysis tool
│   └── request_*.json / response_*.json  ← IPC files (clean if > 20 files)
│
├── mcp_server/               ← MCP SERVER (V3 — universal LLM bridge)
│   ├── run_server.py              ← ENTRY POINT: `py -3.12 mcp_server/run_server.py`
│   ├── probability_models.py      ← 12 MODELS: all return {signal, conviction, reasoning}
│   ├── obsidian_memory.py         ← MEMORY: read/write obsidian, Bayesian updates
│   └── __init__.py
│
├── src/                      ← CORE LIBRARY
│   ├── broker.py              ← TopStepX API client (auth, orders, positions)
│   ├── decision.py            ← IPC file provider + snapshot builder
│   ├── market_data.py         ← Market snapshot structures, regime detection
│   ├── risk.py                ← Risk checks, RoR calculation, position sizing
│   ├── learning.py            ← Trade outcome recording, Bayesian updates
│   ├── performance.py         ← PnL tracking, stats
│   ├── position_manager.py    ← Open position tracking
│   ├── scanner.py             ← Contract scanner, round-robin logic
│   ├── sentinel.py            ← Main entry class (ties layers together)
│   ├── trustgraph_client.py   ← TrustGraph knowledge graph client (optional)
│   └── problem_tracker.py     ← Problem logging utilities
│
├── scripts/                  ← UTILITIES & AUTOMATION
│   ├── weekend_learning.py    ← OFF-HOURS: analyze, calibrate, simulate
│   ├── schedule_trading.py    ← WINDOWS TASK SCHEDULER: auto start/stop
│   ├── monte_carlo_sweep.py   ← Run 10K path MC simulation
│   └── trustgraph_loader.py   ← Load obsidian into TrustGraph
│
├── state/                    ← PERSISTENT STATE
│   ├── ai_trading_memory.json     ← BAYESIAN MEMORY: per-contract win rates, PnL
│   ├── trade_history.json         ← FULL TRADE LOG: all trades with thesis + outcome
│   ├── current_thesis.json        ← LLM THESIS: persists market view across sessions
│   ├── monte_carlo_results.json   ← Last MC run results
│   └── kaizen_log.json            ← Kaizen improvement log
│
├── config/
│   ├── sovran_config.json         ← Main config (API keys, timeouts)
│   ├── decision_config.json       ← AI engine config (conviction threshold, max trades)
│   └── risk_config.json           ← Risk params (max daily loss, position size)
│
├── obsidian/                 ← PRIMARY MEMORY (see obsidian files below)
│   └── ... (see OBSIDIAN MAP section)
│
├── logs/                     ← LOG FILES
│   ├── mcp_server.log             ← MCP server logs
│   └── trading_session_*.log      ← Daily trading session logs
│
├── gemini_mcp_config.json    ← Gemini CLI MCP config (copy to ~/.gemini/settings.json)
├── ralph_ai_loop.log         ← Ralph orchestrator log
├── live_session_v5.log       ← V5 session log (most recent trades here)
├── ai_engine.log             ← AI decision engine log
└── requirements.txt          ← Python dependencies
```

---

## KEY FILES — WHAT EACH DOES

### TRADING ENTRY POINTS

| File | Purpose | When to edit |
|------|---------|-------------|
| `ralph_ai_loop.py` | Orchestrates sessions + Kaizen | Change session parameters, sleep duration |
| `live_session_v5.py` | Executes trades on TopStepX | Change conviction threshold, SL/TP, scan interval |
| `mcp_server/run_server.py` | MCP server for LLM trading | Add new tools, change tool behavior |
| `ipc/ai_decision_engine.py` | Fallback AI brain (Python) | Fallback when no LLM connected |

### BROKER & API

| File | Purpose | Common Issues |
|------|---------|--------------|
| `src/broker.py` | All TopStepX API calls | Auth failures → check credentials in config; 401 → re-auth |
| `src/decision.py` | Builds IPC requests | Wrong field names → trade not placed; add fields here |
| `config/sovran_config.json` | API key, base URL | If auth fails, check this first |

### MARKET DATA

| File | Purpose | Root Cause For |
|------|---------|---------------|
| `src/market_data.py` | Snapshot struct, regime detection | Wrong regime → bad model signals |
| `src/scanner.py` | Contract scanner, round-robin | Missing contracts → add here |
| `live_session_v5.py:SCAN_CONTRACTS` | List of active contracts | Wrong expiry → trade rejection |

### RISK & DECISIONS

| File | Purpose | Root Cause For |
|------|---------|---------------|
| `src/risk.py` | RoR, position sizing | System not trading → check RoR > 5% |
| `src/decision.py:DecisionConfig` | Conviction threshold, trade limits | All NO_TRADE → check `min_conviction_to_trade`, `max_trades_per_session` |
| `live_session_v5.py:MIN_CONVICTION_FIRST` | Session-level conviction | Lower if system not trading |

### MEMORY & LEARNING

| File | Purpose | Root Cause For |
|------|---------|---------------|
| `state/ai_trading_memory.json` | Bayesian per-contract memory | Wrong win rates → run `backfill_outcomes.py` |
| `mcp_server/obsidian_memory.py` | Obsidian read/write | MCP memory tools failing |
| `ipc/record_trade_outcome.py` | Records outcomes | Memory not updating → check this |
| `backfill_outcomes.py` | Backfill memory from logs | Use when memory was reset |

### SIGNAL COMPUTATION (NEW ARCHITECTURE — 2026-03-27)

| File | Location | What it does |
|------|---------|--------------|
| `mcp_server/run_server.py:_compute_signals()` | 5 clean signals | Order Flow (OFI+VPIN), Price Structure (VWAP), Momentum (prices_history), Volatility Regime (ATR ratio), Session Context (time-of-day) |
| `mcp_server/run_server.py:_build_hunt_context()` | Semantic English packet | Translates signals to English labels for LLM. Uses doubled-text (role+task at top AND bottom of context). |
| `mcp_server/run_server.py:_calculate_position_size()` | Contract sizing | TopStepX tiers: +$1500→3 contracts, +$2000→5 contracts. HIGH=max, MEDIUM=half, LOW=1 probe. |
| `mcp_server/probability_models.py` | UTILITY LIBRARY ONLY | Individual model functions available. `run_all_models()` is NO LONGER CALLED by hunt_and_trade. 8/12 models were broken or correlated. |

**Hunt flow (2-step skill):**
```
hunt_and_trade(dry_run=True) → semantic_context
  ↓ LLM reasons: BEAR CASE / BULL CASE / SYNTHESIS / DECISION / CONVICTION / THESIS
  ↓ LLM calls place_trade() with conviction level
  → trade placed
```
The calling LLM IS the brain. hunt_and_trade is the data collector + context builder.

---

## OBSIDIAN FILE MAP

```
obsidian/
├── SESSION_HANDOFF_CURRENT.md     ← START HERE: current state for any LLM
├── LLM_HANDOFF_KIT.md             ← SECOND: full briefing, architecture, credentials ref
├── AUTONOMOUS_SETUP_GUIDE.md      ← HOW TO: set-and-forget instructions
├── CODEBASE_MAP.md                ← THIS FILE
│
├── ai_trading_philosophy.md       ← Jesse's 7 commandments + Q&A
├── trading_rules.md               ← Full entry/exit ruleset
├── kaizen_backlog.md              ← Improvement queue
├── problem_tracker.md             ← Known bugs + fixes
│
├── SOVEREIGN_ARCHITECTURE_V3_MCP.md  ← V3 MCP architecture plan
├── MCP_IMPLEMENTATION_PLAN.md     ← Phase-by-phase MCP build checklist
│
├── system_state.md                ← Current parameter values
├── CREDENTIALS_REFERENCE.md       ← Where API keys live (never push to git)
├── TRUSTGRAPH_INTEGRATION.md      ← TrustGraph knowledge graph docs
│
├── trade_log.md                   ← Auto-appended trade log (all trades)
├── observations/                  ← Market observations (auto-written by AI)
│   └── market_*.md
│
└── ai_loop_log_*.md               ← Ralph loop session logs
```

---

## COMMON ROOT CAUSES & WHERE TO LOOK

### "System not trading at all"
1. Check `ai_loop_status.json` — is ralph running? iteration number?
2. Check `live_session_v5.log` — "Session trade limit reached"? → raise `max_trades_per_session`
3. Check `src/decision.py:DecisionConfig.max_trades_per_session` (should be 50)
4. Check RoR: `src/risk.py` — if balance < ruin threshold, no trades
5. Check session phase: outside 8am-4pm CT → won't trade

### "All trades are NO_TRADE"
1. Check IPC files: are requests being written? `ls ipc/request_*.json`
2. Check ai_decision_engine.py is running (PID in `ipc_responder.pid`)
3. Check conviction threshold: `live_session_v5.py:MIN_CONVICTION_FIRST` (default 60)
4. Check OFI/VPIN gates: `ofi_z > 1.5` and `vpin > 0.55` required in V5

### "Wrong contract IDs / trade rejection"
1. Check `live_session_v5.py:SCAN_CONTRACTS` — expiry is M26 (June 2026)
2. Rollover needed in mid-May 2026: M26 → U26

### "Memory shows wrong win rates"
1. Run: `py backfill_outcomes.py` — rebuilds from trade log
2. Check `state/trade_history.json` — outcomes should be "WIN"/"LOSS"/"BREAKEVEN"

### "IPC files piling up (> 50)"
1. `autonomous_responder.py` may be zombie-running → kill it
2. Clean: `py -c "from pathlib import Path; [f.unlink() for f in sorted(Path('ipc').glob('response_*.json'), key=lambda p: p.stat().st_mtime)[:-5]]"`

### "JSONDecodeError in ai_decision_engine.py"
1. Caused by stale/partial IPC response files
2. Fix: clean IPC dir (see above)
3. Root: multiple AI engine instances running simultaneously → kill duplicates

### "Balance not updating in memory"
1. Check `record_trade_outcome.py` is writing to `state/ai_trading_memory.json`
2. Check `mcp_server/obsidian_memory.py:_update_bayesian_memory` is being called

---

## PROCESS MAP — WHAT'S RUNNING

```
NORMAL OPERATION (3 Python processes):
  PID A: ralph_ai_loop.py       ← Low CPU, orchestrates
  PID B: live_session_v5.py     ← Medium CPU, trading + IPC reads
  PID C: ai_decision_engine.py  ← High CPU, writing IPC responses

MCP MODE (when LLM is connected):
  PID A: ralph_ai_loop.py       ← Optional (can run without)
  PID B: live_session_v5.py     ← Still runs for order execution
  Stdio: mcp_server/run_server.py ← Managed by Claude Code/Gemini CLI

ZOMBIE TO KILL:
  autonomous_responder.py       ← Kill on sight (appears randomly)
```

**Check running:** `py find_pids.py` or PowerShell `Get-Process python`

---

## API REFERENCE

### TopStepX (ProjectX)
- Base URL: `https://api.topstepx.com`
- Auth: POST `/api/Auth/loginKey` → `{userName, apiKey}` → token
- Orders: POST `/api/Order/place`
- Positions: GET `/api/Position/search`
- Account: POST `/api/Account/search`

### IPC Protocol (legacy, still used by V5)
- Request: `ipc/request_{timestamp}.json` — market snapshot
- Response: `ipc/response_{timestamp}.json` — trade decision
- Fields: `{action, conviction, sl_ticks, tp_ticks, kelly_fraction, reasoning, ev}`

### MCP Tools (V3 — updated 2026-03-27)
- Server: `py -3.12 mcp_server/run_server.py`
- Config: `~/.claude/settings.json` (registered as `sovereign-sentinel`)
- Tools: get_market_snapshot, hunt_and_trade (dry_run=True for 2-step flow), query_memory, place_trade, get_account_status, log_trade_thesis, log_trade_outcome, save_thesis, write_observation
- NOTE: `run_probability_models` still exists but `hunt_and_trade` no longer calls `run_all_models()` internally. Use `hunt_and_trade(dry_run=True)` to get `semantic_context` for LLM reasoning.

**VWAP data flow:**
```
live_session_v5.py MarketTick._vwap_cum_pv/vol
  → _build_snapshot() → MarketSnapshot.vwap (field added 2026-03-27)
  → IPC request file snapshot_data.vwap
  → hunt_and_trade IPC enrichment → snap["vwap"]
  → _compute_signals() Signal 2 (Price Structure)
```

---

## CREDENTIALS

| Key | Value | Location |
|-----|-------|----------|
| TopStepX API key | `9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=` | `~/.claude/settings.json` (env), `sovran_v2_secrets/credentials.env` |
| Username | `jessedavidlambert@gmail.com` | Same |
| GitHub | `https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence` | Push: `git push origin genspace:main --no-verify` |

**NEVER push credentials to GitHub.**

---

*Generated: 2026-03-27 by Claude Sonnet 4.6*
*Update this file when adding new modules or changing file purposes.*
