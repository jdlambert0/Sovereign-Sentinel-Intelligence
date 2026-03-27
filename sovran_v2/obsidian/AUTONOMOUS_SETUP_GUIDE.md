---
title: Sovereign Sentinel — Autonomous Setup Guide
type: setup-guide
updated: 2026-03-27
---

# HOW TO SET IT AND FORGET IT

This is the complete guide to running Sovereign Sentinel autonomously.
Read this once, run the setup commands, then just say "go trade" or "/trade".

---

## ARCHITECTURE OVERVIEW

```
Windows Task Scheduler (8am CT)
         │
         ▼
ralph_ai_loop.py  ← Python trading orchestrator (runs all day)
         │
         ├─ live_session_v5.py  ← executes trades via TopStepX API
         │
         └─ ipc/ai_decision_engine.py  ← fallback AI brain (Python)

Claude Code / Gemini CLI  ← YOU (or any LLM) as the intelligent trader
         │
         └─ MCP Server (sovereign-sentinel)
              ├─ get_market_snapshot
              ├─ run_probability_models  ← 12 models, live
              ├─ query_memory  ← obsidian knowledge base
              ├─ place_trade  ← direct API execution
              ├─ log_trade_thesis  ← pre-trade reasoning log
              ├─ log_trade_outcome  ← post-trade learning
              ├─ save_thesis  ← persist market view
              └─ get_account_status
```

---

## MCP COMPATIBILITY — WHICH LLMs CAN TRADE

| LLM Tool | MCP Support | How to Connect |
|----------|-------------|----------------|
| **Claude Code** | Native ✅ | Auto-loads from `~/.claude/settings.json` |
| **Gemini CLI** | Native ✅ | See Gemini Setup below |
| **OpenAI Agents SDK** | Native ✅ | Use `mcp` module, same server |
| **Continue.dev** | Native ✅ | Works with local LLMs too |
| **Ollama** | Via bridge | Use `ollama-mcp-bridge` (needs tool-call model) |

**MCP is universal.** One server, any LLM. The server is already registered for Claude Code.

---

## CLAUDE CODE SETUP (DONE — JUST USE IT)

The MCP server is already registered in `~/.claude/settings.json`.

Three skills are ready globally (work in any project):

| Command | What it does |
|---------|-------------|
| `/trade` | Start autonomous trading session |
| `/learn` | Off-hours learning and memory consolidation |
| `/status` | Quick system health check |

**To trade:** Open Claude Code, type `/trade`, hit enter. Done.

The system will:
1. Read your thesis and memory from obsidian
2. Scan all 6 contracts every 3 minutes
3. Run all 12 probability models on promising setups
4. Place trades when conviction ≥ 65
5. Log every trade and lesson to obsidian
6. Continue until 4pm CT or daily loss limit

---

## GEMINI CLI SETUP

**One-time setup:**
```bash
# Copy the MCP config
copy C:\KAI\sovran_v2\gemini_mcp_config.json %USERPROFILE%\.gemini\settings.json

# OR add via CLI:
gemini mcp add sovereign-sentinel --command "py -3.12 C:\KAI\sovran_v2\mcp_server\run_server.py"
```

**Then trade:**
```bash
gemini
> go trade
```

Gemini will auto-discover the sovereign-sentinel MCP tools and use them.

---

## SET AND FORGET — AUTOMATIC DAILY TRADING

To have the system start and stop trading automatically every weekday:

```bash
# One-time setup (run as Administrator):
py C:\KAI\sovran_v2\scripts\schedule_trading.py --setup

# Verify:
py C:\KAI\sovran_v2\scripts\schedule_trading.py --status
```

This creates two Windows Task Scheduler jobs:
- **SovranSentinel_StartTrading**: Runs at 8:00 AM CT, Mon-Fri
- **SovranSentinel_StopTrading**: Runs at 4:05 PM CT, Mon-Fri

After this runs once, you never need to touch it again.

**Check what it's doing:**
```bash
# Today's trading log:
type C:\KAI\sovran_v2\logs\trading_session_<YYYYMMDD>.log

# Loop status:
py -c "import json; print(json.load(open(r'C:\KAI\sovran_v2\ai_loop_status.json')))"
```

---

## WEEKEND LEARNING (OFF-HOURS)

The system learns on weekends automatically, or you can trigger it:

**In Claude Code:**
```
/learn
```

**Directly:**
```bash
# Full learning session:
py C:\KAI\sovran_v2\scripts\weekend_learning.py --mode full

# Just analysis:
py C:\KAI\sovran_v2\scripts\weekend_learning.py --mode analyze

# Calibration:
py C:\KAI\sovran_v2\scripts\weekend_learning.py --mode calibrate

# Simulation (replay recent trades, score model accuracy):
py C:\KAI\sovran_v2\scripts\weekend_learning.py --mode simulate
```

---

## MANUAL CONTROL

```bash
# Start trading now (full autonomous loop):
py C:\KAI\sovran_v2\ralph_ai_loop.py --max-iterations 999 --sleep-between 300

# Start single V5 session:
py C:\KAI\sovran_v2\live_session_v5.py

# Check account:
py -c "
import sys; sys.path.insert(0,'C:/KAI/sovran_v2')
import asyncio
from src.broker import BrokerClient
async def check():
    async with BrokerClient('jessedavidlambert@gmail.com', '9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=') as b:
        await b.connect()
        print('Balance:', b.account_balance)
asyncio.run(check())
"

# Emergency stop ALL python processes:
py -c "import subprocess; subprocess.run(['powershell','Get-Process python | Stop-Process -Force'])"
```

---

## MONITORING WITHOUT TOUCHING IT

**GitHub:** https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence
The loop auto-commits every 2 iterations. Watch the repo for live updates.

**State file:**
```bash
py -c "import json; d=json.load(open(r'C:\KAI\sovran_v2\state\ai_trading_memory.json')); print('Trades:', d['trades_executed'], '| PnL: $'+str(round(d['total_pnl'],2)))"
```

**Balance check:**
```bash
py -c "import json; d=json.load(open(r'C:\KAI\sovran_v2\ai_loop_status.json')); print(d)"
```

---

## WHAT THE SYSTEM LEARNS OVER TIME

Every trade updates `state/ai_trading_memory.json`:
- Win rate by contract (Bayesian Beta-Binomial update)
- Win rate by regime (trending/ranging/volatile)
- Win rate by session phase (us_open/us_core/us_close)
- Lesson text from each trade

After 100+ trades:
- The Bayesian memory becomes statistically meaningful
- Contract priorities self-adjust based on live results
- Monte Carlo projections become accurate

After 500+ trades:
- The system knows its edge precisely
- Regime-specific TP thresholds can be tuned
- Information theory model reveals true market predictability

---

## THE GOAL: COME BACK TO PROFITS

Set it up once. The system:
1. Wakes up every weekday at 8am CT
2. Reads its thesis from obsidian (what it learned last session)
3. Scans all 6 contracts every 3 minutes
4. Runs 12 probability models on the best setups
5. Places trades when conviction ≥ 65 (adaptive)
6. Logs everything — every trade, every lesson, every observation
7. Auto-commits to GitHub so you can check remotely
8. Shuts down at 4pm CT
9. On weekends: runs `/learn` for memory consolidation
10. Repeats

You come back to: trade history, performance summary, and (target) profits.

---

*Written: 2026-03-27 by Claude Sonnet 4.6*
*System version: V3 MCP Architecture*
