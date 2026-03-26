# Test Results Tracker

## Summary
- **Total Tests:** 18
- **Passed:** 11 (incl. 5.3 partial verification 2026-03-23)
- **Failed:** 0
- **Pending:** 7 (Phase 4–5 except 5.3; require RTH / controlled scenarios)

### Session verification (2026-03-23 night CT)
- **RPNL semantics:** `projectx_broker_api` now returns **session** (17:00 America/Chicago → now) and **calendar-day** sums; primary `net_pnl` for state/monitor defaults to **`SOVRAN_REALIZED_PNL_MODE=session`** to align with typical combine “day” (user dashboard **-218.82** vs earlier calendar-only figure). See `Architecture/Broker_API_Realized_PnL.md`.
- **Single venv:** `armada/enforce_venv_armada.py` documents duplicate-stack detection; `Ops/Single_Venv_Stack.md`.
- **Phase 4:** Runbook for LLMs: `Testing/PHASE_4_RUNBOOK.md` (execution still manual / RTH).
- **LLM pipeline audit:** `Session Logs/2026-03-23_LLM_Trading_Pipeline_Audit.md`.

### Session verification (2026-03-23 ~15:18 CT)
- **preflight.py:** 45/45 PASS (`C:\KAI\armada`, venv `vortex\.venv312`).
- **monitor_sovereign.py --once:** Snapshot appended to `_logs/monitor_snapshot.log`. WARN: Gemini health 429 (rate limit — expected WARN tier). WARN: API balance **$47,812.50** vs state `bankroll_remaining` **$50,000.00** (`_data_db/sovran_ai_state_MNQ_SOVEREIGN.json`) — manual $50k reset vs live API; **no second Sovran start** while process already running (lock + duplicate risk). Reconcile on **controlled parent restart** so `sync_broker_truth_api()` runs in `run()` before workers. STALE `sovran_run.log` with fresh `watchdog_restart_stderr.log` — expected when watchdog holds stderr.
- **Phase 4 / 5.1–5.2:** Not executed this session (manual safety/recovery + 24h + multi-market require dedicated runbook time; 5.2 multi-market partially covered by live `--symbols MNQ,MES,M2K` watchdog path — full sign-off still pending).

---

## Phase 2: Component Verification

| # | Test | Date | Result | Notes |
|---|------|------|--------|-------|
| 2.1 | TopStepX Connection | 2026-03-17 | ✅ PASS | Connected, got price $24960, account 18410777 |
| 2.2 | Quote Data Flow | 2026-03-17 | ✅ PASS | Quotes flow, last_price=None fallback to mid-price works |
| 2.3 | SL/TP Bracket Orders | 2026-03-17 | ✅ PASS | Verified in burst test (9/9 trades had SL/TP active) |
| 2.4 | Position Management | 2026-03-17 | ✅ PASS | Verified in burst test - positions open/close correctly |
| 2.5 | Learning System | 2026-03-17 | ✅ PASS | 14 trades recorded in Obsidian, burst test verified |

## Phase 3: End-to-End Trading

| # | Test | Date | Result | Notes |
|---|------|------|--------|-------|
| 3.1 | Single Trade Cycle | 2026-03-17 | ✅ PASS | Verified in burst test |
| 3.2 | 5-Trade Burst | 2026-03-17 | ✅ PASS | 9/10 trades executed in burst test |
| 3.3 | 10-Trade Research | 2026-03-17 | ✅ PASS | Research triggered at trade 10, 14 total trades |
| 3.4 | Mailbox Integration | 2026-03-17 | ✅ PASS | Inbox->Outbox works, response generated |
| 3.5 | Dynamic Parameters | 2026-03-17 | ✅ PASS | Reads from Obsidian Config/intelligent_management.md |

## Phase 4: Safety & Recovery

| # | Test | Date | Result | Notes |
|---|------|------|--------|-------|
| 4.1 | WebSocket Disconnect | - | ⏳ | - |
| 4.2 | Stop Loss Hit | - | ⏳ | - |
| 4.3 | Take Profit Hit | - | ⏳ | - |
| 4.4 | Drawdown Protection | - | ⏳ | - |
| 4.5 | Process Restart | - | ⏳ | - |

## Phase 5: Production Readiness

| # | Test | Date | Result | Notes |
|---|------|------|--------|-------|
| 5.1 | 24-Hour Run | - | ⏳ | - |
| 5.2 | Multi-Market | - | ⏳ | - |
| 5.3 | LLM Rate Limits | 2026-03-23 | partial PASS | `monitor_sovereign.py` treats HTTP 429 as WARN (Gemini/OpenRouter); OpenRouter backoff in `vortex/providers/openrouter.py`; preflight 45/45 |

---
*Last Updated: 2026-03-23 (night CT — RPNL session mode, venv guard, Phase 4 runbook, pipeline audit)*
