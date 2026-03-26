# Sovran AI — Project Overview

## 0. LLM Handoff Protocol (START HERE)
> **MANDATORY FOR EVERY NEW SESSION:**
> 1. Read `C:\KAI\obsidian_vault\Sovran AI\User_Guidance.md` to understand the user's intent, behavioral boundaries, and workflow preferences.
> 2. Read `C:\KAI\obsidian_vault\Sovran AI\Architecture\Sovereign_Agent_Workflow.md` to establish the correct agentic execution rules.
> 3. Read the latest file in the `Session Logs/` folder.
> 4. **CHECK THE LOOP:** Tail `C:\KAI\armada\_logs\autonomous_sovran_engine.log` and verify `C:\KAI\armada\_logs\heartbeat.txt` is fresh (<60s).
> 5. **CHECK THE WATCHDOG:** Tail `C:\KAI\armada\_logs\watchdog_report.txt` for any alerts.

## Mission
AI-driven futures trading on TopStepX prop firm accounts. Claude/LLM makes every decision. Mathematical sizing (Kelly Criterion) provides the brakes. The goal is **$1k daily profit**.

## Current Status
🟢 **Phase 13: BTS Integration & Float Hardening Complete.** Broker Truth Sync (BTS) successfully integrated via `broker_sync.py` to reconcile -$118.88 PnL. Critical `NoneType` float conversion bugs in `handle_quote` and `handle_trade` resolved via `safe_float` hardening. Pre-flight 45/45 PASS. System integrity verified for NQ session.

## Architecture Stack
| Layer | Component | Status |
|-------|-----------|--------|
| Safety | `GlobalRiskVault` (-$450 daily kill-switch) | ✅ Active |
| Audit | `VetoAuditor` (secondary LLM trade validation) | ✅ Active |
| Training | `marl_gymnasium.py` (offline historical study) | ✅ Ready |
| Monitoring | `sovereign_watchdog.py` (loop health + bug patrol) | ✅ Active |
| Engine | `sovran_ai.py` (consensus ensemble + execution) | ✅ Active |

## Workspace
- **Code:** `C:\KAI\armada\sovran_ai.py`
- **Wrapper:** `C:\KAI\armada\autonomous_sovereign_loop.py`
- **Watchdog:** `C:\KAI\armada\sovereign_watchdog.py`
- **Python:** `C:\KAI\vortex\.venv312\Scripts\python.exe`
- **Logs:** `C:\KAI\armada\_logs\autonomous_sovran_engine.log`
- **Watchdog Log:** `C:\KAI\armada\_logs\watchdog_report.txt`
- **State:** `C:\KAI\armada\_data_db\sovran_ai_state_<SYMBOL>.json`
- **Memory:** `C:\KAI\armada\_data_db\sovran_ai_memory_<SYMBOL>.json`

## Markets
| Symbol | Name | Size | $/Point | Status |
|--------|------|------|---------|--------|
| MNQ | Micro Nasdaq | 10 contracts | $20 | Primary |
| MES | Micro S&P 500 | 1 contract | $5 | Shadow |
| M2K | Micro Russell 2000 | 1 contract | $5 | Shadow |

## Key Decisions
1. **Live-only** — Paper mode deleted entirely
2. **Single process** — All symbols share one WebSocket via `TradingSuite.create()`
3. **Free LLM models** — OpenRouter (gemini-2.5-pro-exp, audit via gemini-2.0-flash)
4. **Background execution** — All processes headless, output to files
5. **15s loop interval** — Optimized for microstructure reaction speed
6. **Veto Auditor** — Every trade double-checked by secondary AI
7. **Watchdog daemon** — Continuous monitoring of all background processes

## Scaling Roadmap to $1k/Day
| Phase | Target | Timeline |
|-------|--------|----------|
| Shadow Validation | 10 MNQ, verify Veto rate | March 20-24 |
| Live Scaling | Full 10 MNQ execution | March 25-31 |
| Goal Achievement | $1k/day x 5 consecutive | April 1-3 |

## Tags
#sovran-ai #project-overview #topstepx
