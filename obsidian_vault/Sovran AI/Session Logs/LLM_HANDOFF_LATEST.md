# Sovereign LLM Handoff: LATEST
**Last Updated:** 2026-03-23 (OpenRouter-only + protocol + stand-in plan vault sync)

> **READ THIS AT THE START OF EVERY SESSION AND EVERY TURN.**

**Stand-in plan + completed work (vault mirror):** [[2026-03-23_Stand_In_Plan_Status_And_Work_Done]] — external Path C, P1–P4, pending todos, risk/unattended notes.

**Optional paste-prompt (trading focus):** [[PROMPT_NEXT_SESSION_GET_TO_TRADING]] — `Session Logs/PROMPT_NEXT_SESSION_GET_TO_TRADING.md`

## 🟢 Mandates for the Next Turn (STRICT)

1.  **STEALTH EXECUTION**: Never run commands that steal focus or open visible Chrome windows.
2.  **LIGHTPANDA RESEARCH**: Use `python lightpanda_harness.py "<url>"` for ALL documentation/API research.
3.  **WEBSOCKET-ONLY**: Enforce `strict_websocket = True`. System MUST halt if WS is lost. No REST polling.
4.  **ACTUAL BROKER TRUTH**: Fetch real-time balance via API; do NOT set $50k or other baselines.
5.  **TURN-BY-TURN UPDATES**: Problem Tracker, Bug Tracker, and this Handoff updated every turn.
6.  **NEVER GUESS**: Research or ask user before moving on assumptions.
7.  **BRACKET / PnL TRUTH**: Verify orders and RPNL via **API + trade log**, not TopStepX chart UI for API-placed brackets.
8.  **OPENROUTER LLM**: Primary stack is **OpenRouter** (`VORTEX_LLM_PROVIDER=openrouter`, `sk-or-` key). Verify with `python diag_openrouter_ping.py`. Do not rely on Gemini for audits when credits are unavailable.

## 🛠️ Active Implementation Plan
- **Plan**: [Hardened_Stealth_Implementation.md](file:///C:/KAI/obsidian_vault/Sovran%20AI/Action%20Plans/Hardened_Stealth_Implementation.md)
- [x] **Corrupted State File (-$244k)**: `sovran_ai_state_MNQ_SOVEREIGN.json` reported legacy PnL.
    - **Remediation**: Reset to clean $50k bankroll; superseded by API sync + pre-lock persist.
- [x] **REST Polling Fallback (connection bootstrap)**: `connection_management` patch logged degraded “REST polling” on WS timeout; contradicted mandate.
    - **Remediation (2026-03-23)**: `_patched_connect` in `sovran_ai.py` now **returns `False`** on timeout / incomplete hubs when `Config.strict_websocket` is **True**; removed misleading REST-polling wording for that path. *Monitor loop / SDK may still log other REST strings — grep if they reappear.*
- [x] **Gemini 404 Veto Error**: 404s detected in audit endpoint results.
    - **Remediation**: Fixed "Fail-Open" vulnerability in `sovran_ai.py` where 404s bypassed the audit and allowed Alpha trades. Now strictly FAILS CLOSED.
- [x] **Actual Account Inaccuracy**: $50,000 baseline is incorrect for real PnL tracking.
    - **Remediation**: `sync_broker_truth_api()` in `projectx_broker_api.py`; fail-closed without `--allow-missing-broker-sync`. Sovereign state persisted **before** singleton lock (see below).
- [x] **OpenRouter-only LLM defaults (2026-03-23)**: Hardcoded Gemini / generic_http bias in `sovran_ai.py` defaults and startup.
    - **Remediation**: `SOVRAN_CONSENSUS_MODELS` or primary+audit OpenRouter slugs; startup prefers `sk-or-` → `openrouter`; `diag_openrouter_ping.py`; vault [[Protocols/LLM_TRADER_PROTOCOL]] + [[2026-03-23_OpenRouter_Migration]].

---

## 📦 What This Multi-Session Work Delivered (2026-03-23)

### Broker API (`C:\KAI\armada\projectx_broker_api.py`)
- Swagger-aligned: `POST /api/Account/search` with **`{"onlyActiveAccounts": true}`** (not `{}`).
- **`select_trading_account()`** — avoids wrong `accounts[0]`; optional **`PROJECT_X_ACCOUNT_ID`** in `.env` (user aligned to **20560125**).
- **`Trade/search`**: sum `profitAndLoss`, skip **`voided`**; two windows:
  - **`net_pnl_session`** — since last **17:00 America/Chicago** (typical combine / futures “day”; matches dashboard RPNL better than calendar-only).
  - **`net_pnl_calendar_day`** — midnight Chicago → now.
- Primary **`net_pnl`** for state/monitor: **`SOVRAN_REALIZED_PNL_MODE`** = `session` (default) or `calendar`.
- **Docs:** [[Broker_API_Realized_PnL]] (`Architecture/Broker_API_Realized_PnL.md`).

### Sovran (`sovran_ai.py`)
- **`sync_broker_truth_api()`** imported from `projectx_broker_api` (single source of truth).
- **Order of operations:** (1) broker API sync + log → (2) **persist all `sovran_ai_state_{SYM}_SOVEREIGN.json` on disk (section 1a)** → (3) **then** `portalocker` → (4) TradingSuite / workers.  
  *Reason:* Watchdog spawns many overlapping processes; lock-losers used to exit **without** ever writing state; JSON stayed at $50k placeholder.
- **Trailing fields** reset when applying API truth: `trailing_high_water_mark` / `trailing_drawdown_floor` from API PnL + `TrailingDrawdown.max_drawdown` (fixes stale 50k HWM).
- Startup log line includes session + calendar RPNL and mode.

### Monitor (`monitor_sovereign.py`)
- Broker spot-check uses **`fetch_broker_truth_sync()`**; shows **session vs calendar** and mode on the snapshot line.

### Ops / duplicate stacks
- **`C:\KAI\armada\enforce_venv_armada.py`** — detects non-venv `python.exe` running Armada Sovran; optional **`--kill`**.  
- **Docs:** [[Single_Venv_Stack]] (`Ops/Single_Venv_Stack.md`).  
- *Issue seen:* `launch_armada.py` (venv) + **system** `Python312\python.exe` both running watchdog/sovran → portalocker spam in `watchdog_restart_stderr.log`.

### Testing / vault
- **`Testing/PHASE_4_RUNBOOK.md`** — Phase 4 safety/recovery checklist for LLMs (manual / RTH).
- **`Session Logs/2026-03-23_LLM_Trading_Pipeline_Audit.md`** — pipeline map, what code does/doesn’t prove, verification ideas.
- **`Testing/TEST_RESULTS.md`**, **`Testing/Comprehensive_Test_Plan.md`**, **`Architecture/Test_and_Monitoring_Suites.md`** updated.
- **`Bugs/PROBLEM_TRACKER.md`**: resolved **P9–P11** (API usage, pre-lock state, RPNL semantics); **P8** note on account id; P1–P4 still open where applicable.
- **`Bugs/BUG_INVENTORY_SYNC.md`**: duplicate-stack warning + broker RPNL doc link.

### Verification run
- **`preflight.py`**: **45/45** after changes.
- **`monitor_sovereign.py --once`**: broker **OK** when state aligned with API (within $20).
- **Smoke risk:** TopStepX **`429`** on auth possible during heavy testing — retry with backoff; not a logic failure in our module.

---

## 📈 Recent Sessions (chronological)
- [[Session_2026-03-23]] — 404s, monitor, March 16 stall, knowledge graph notes.
- [[Session_2026-03-23_Part2]] — multi-market, logging, portalocker.
- [[2026-03-23_Preflight_Monitor_Verification]] — preflight + monitor; Phase 4–5.2 deferred.
- [[2026-03-23_ProjectX_Broker_API_Fix]] — `projectx_broker_api`, `.env` account id.
- [[2026-03-23_Preload_State_Lock_Order]] — persist sovereign state **before** lock; trailing reset.
- [[2026-03-23_LLM_Trading_Pipeline_Audit]] — ensemble/veto/limits; [[Broker_API_Realized_PnL]]; [[Single_Venv_Stack]]; [[PHASE_4_RUNBOOK]].

---

## 📊 Current System State (snapshot)

| Area | State |
|------|--------|
| **Preflight** | Run from `C:\KAI\armada`: `python preflight.py` → expect **45/45** |
| **Monitor** | `python monitor_sovereign.py --once` → `_logs/monitor_snapshot.log` |
| **Broker truth** | `projectx_broker_api` + optional `PROJECT_X_ACCOUNT_ID`; RPNL **session** default |
| **State files** | `_data_db/sovran_ai_state_*_SOVEREIGN.json` — should track API after any process runs sync + pre-lock persist |
| **Open risks** | Duplicate **venv vs system Python** stacks (enforce_venv still WARN); P1 log routing; Phase 4 not executed; occasional **429** on Gemini / TopStepX auth under load |

---

## ➡️ Next steps (for the next LLM — prioritized)

1. **Run `enforce_venv_armada.py`** (no kill first). If offenders: coordinate with user → **`--kill`** when flat, then **single** `launch_armada.py` via venv only; remove duplicate Task Scheduler / startup entries.
2. **Run `preflight.py`** and **`monitor_sovereign.py --once`** at session start; fix any regression before trading work.
3. **RPNL sanity:** If user’s dashboard RPNL still ≠ Sovran, compare **`net_pnl_session`** vs **`net_pnl_calendar_day`** in logs; adjust **`SOVRAN_REALIZED_PNL_MODE`** only if intentional. See [[Broker_API_Realized_PnL]]. If API returns **429**, backoff and retry — don’t treat as wrong math.
4. **Execute [[PHASE_4_RUNBOOK]]** in a planned RTH window (small size): disconnect, SL/TP, drawdown, restart — append evidence to **TEST_RESULTS.md**.
5. **P1 log unification:** Either unify file handlers so watchdog runs show up in `sovran_run.log`, or treat watchdog stderr as canonical in docs (already partially done in monitor).
6. **LLM “thinking” eval (optional):** Shadow logging, confidence calibration, veto-rate review — see [[2026-03-23_LLM_Trading_Pipeline_Audit]].
7. **Keep this file current** after material code or ops changes; link new session logs (e.g. [[2026-03-23_StrictWS_GlobalRiskVault_Verification]] — preflight 45/45, enforce_venv + monitor evidence).

---

## Quick file index
| Artifact | Path |
|----------|------|
| Broker module | `C:\KAI\armada\projectx_broker_api.py` |
| Sovran engine | `C:\KAI\armada\sovran_ai.py` |
| Monitor | `C:\KAI\armada\monitor_sovereign.py` |
| Venv guard | `C:\KAI\armada\enforce_venv_armada.py` |
| Problem tracker | `Bugs/PROBLEM_TRACKER.md` |
| Bug inventory | `Bugs/BUG_INVENTORY_SYNC.md` |
| RPNL semantics | `Architecture/Broker_API_Realized_PnL.md` |
| Phase 4 runbook | `Testing/PHASE_4_RUNBOOK.md` |
| Pipeline audit | `Session Logs/2026-03-23_LLM_Trading_Pipeline_Audit.md` |
| Next-session trading prompt | `Session Logs/PROMPT_NEXT_SESSION_GET_TO_TRADING.md` |
| OpenRouter ping | `C:\KAI\armada\diag_openrouter_ping.py` |
| Env template | `C:\KAI\armada\.env.example` |
| LLM + vault protocol | `Protocols/LLM_TRADER_PROTOCOL.md` |

- **Bug Tracker:** [BUG_INVENTORY_SYNC.md](file:///C:/KAI/obsidian_vault/Sovran%20AI/Bugs/BUG_INVENTORY_SYNC.md)
- **Heartbeat:** `C:\KAI\armada\_logs\heartbeat.txt`
- **Knowledge Graph Strategy:** `Plans/Obsidian_Knowledge_Graph_Strategy.md` / InfraNodus notes
