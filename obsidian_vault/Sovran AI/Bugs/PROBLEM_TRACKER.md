# Sovereign Problem Tracker
**Last Updated:** 2026-03-23 (late CT)

## Active Issues

### P0. OpenRouter Credit Exhaustion (HTTP 402)
- **Symptom:** `Strategic Veto Audit failed: OpenRouter HTTP 402 Error`.
- **Impact:** Blocks all automated trading (veto loop failure). Manual commands bypass this but require a stable credit balance for full autonomy.
- **Root Cause:** OpenRouter account balance at zero.
- **Fix Required:** Deposit credits at https://openrouter.ai/settings/credits.
- **Date Found:** 2026-03-23

### P8. Stale `PROJECT_X_ACCOUNT_ID` in `.env` (WARN noise)
- **Symptom:** Log line `PROJECT_X_ACCOUNT_ID=… not found in Account/search; using heuristic`.
- **Impact:** None if heuristic selects the correct combine; confusing if you expect a pinned ID.
- **Root Cause:** Legacy account id (`18410777`) no longer appears in **active** `Account/search` results after `onlyActiveAccounts: true`.
- **Fix:** Set `PROJECT_X_ACCOUNT_ID` to the current account id from monitor (e.g. `20560125`) **or** remove the line to rely on heuristic (combine name / `canTrade` / non-simulated).
- **Date Found:** 2026-03-23


### P1. Log Routing Mismatch (CRITICAL)
- **Symptom:** `sovran_run.log` stopped updating March 16. System was actually alive, but logging to `_logs/watchdog_restart_stderr.log` instead.
- **Impact:** 7 days of invisible operation. No alerts. No monitoring coverage.
- **Root Cause:** Watchdog spawns `sovran_ai.py` with `stdout/stderr` redirected to `_logs/watchdog_restart_*.log`, but `sovran_ai.py`'s internal logger writes to `sovran_run.log` via a `FileHandler`. The singleton guard blocked "direct" runs (which would write to `sovran_run.log`), but watchdog-spawned instances logged to stderr only.
- **Fix Required:** Unify log output. Either: (A) Have `sovran_ai.py` always write to `sovran_run.log` regardless of how it's launched, or (B) Update `monitor_sovereign.py` to check ALL log targets.
- **Mitigation (2026-03-23):** Set `SOVRAN_EXTRA_LOG_PATH` to duplicate engine logs to a second file (e.g. `_logs/sovran_extra.log`). Treat `watchdog_restart_stderr.log` as live when `sovran_run.log` is stale.
- **Date Found:** 2026-03-23

### P2. Singleton Guard Stale Lock (CRITICAL)
- **Symptom:** `FATAL: Another instance is already running (PID 57292). Aborting.` — blocks all direct launches since March 16.
- **Impact:** System can ONLY be launched via watchdog. Direct `python sovran_ai.py` commands fail silently.
- **Root Cause:** `sovran_ai.py` uses psutil to scan for other instances of itself. When watchdog-spawned instances are running, direct launches see them and abort. But: PID 57292 was stale (process long dead), yet the check still found a process with `sovran_ai` in cmdline.
- **Fix Required:** Implement proper PID file locking instead of psutil process scanning. Or: add `--force` flag to skip singleton check.
- **Date Found:** 2026-03-23

### P3. Log Spam (Bridge Received Trade Batch)
- **Symptom:** Hundreds of identical `Bridge received trade batch (size: X)` lines per second in stderr log.
- **Impact:** Log files grow to Multi-MB in hours. Obscures real errors. Makes log analysis impossible.
- **Root Cause:** Every WebSocket trade tick triggers a log line. At market open, this can be 50-100+ messages/second.
- **Fix Required:** Reduce logging level for trade batch to DEBUG, or add a cooldown/summary log (e.g., "Received 500 trade batches in last 60s").
- **Date Found:** 2026-03-23

### P4. "ALL TRADING HALTED" Circuit Breaker
- **Symptom:** Spotted `"on triggered. ALL TRADING HALTED"` in stderr log tail.
- **Impact:** System may be receiving data but refusing to trade due to a safety circuit breaker.
- **Root Cause:** Unknown — likely daily loss limit, session phase restriction, or a risk gate.
- **Investigation:** Need to search `sovran_ai.py` for "ALL TRADING HALTED" to identify the exact trigger condition.
- **Mitigation (2026-03-23):** See [[Architecture/Trading_Halt_Sources]] for halt sources and grep commands.
- **Date Found:** 2026-03-23

## Resolved Issues
| # | Issue | Root Cause | Fix | Date |
|---|---|---|---|---|
| P5 | **Monitor Checks Wrong Log Files** | Monitor only watched `sovran_run` / `sovran_output`. | `monitor_sovereign.py` now checks `watchdog_restart_stderr.log`, `sovran_fresh_stderr.log`, and summarizes newest activity; see `Architecture/Test_and_Monitoring_Suites.md`. | 2026-03-23 |
| P7 | **Live broker equity vs placeholder** | Startup could proceed without API truth. | `sync_broker_truth_api()` required for live: process **exits** if sync fails unless `--allow-missing-broker-sync`. Sovereign state **saved** after API reconciliation on boot. | 2026-03-23 |
| P9 | **Wrong balance / PnL from API usage** | `Account/search` called with `{}` (missing required `onlyActiveAccounts`); `accounts[0]` could be wrong account; UTC midnight for trades vs Chicago day; voided trades summed. | New module `armada/projectx_broker_api.py`: swagger `onlyActiveAccounts: true`, `select_trading_account()` (+ optional `PROJECT_X_ACCOUNT_ID`), `Trade/search` with Chicago day window + `endTimestamp`, skip `voided` half-trades. `sovran_ai.py` + `monitor_sovereign.py` use shared helper. | 2026-03-23 |
| P10 | **State JSON not updated when lock-lost** | Sovereign disk write ran only after `portalocker` success; watchdog spawns many overlapping `sovran_ai` processes — all but one fail at lock and never wrote state. | Persist API-aligned sovereign state **before** singleton lock (section 1a); reset `trailing_high_water_mark` / `trailing_drawdown_floor` from API PnL (no stale 50k HWM). Monitor broker check **OK** after restart. | 2026-03-23 |
| P11 | **Dashboard RPNL vs Sovran `daily_pnl`** | `Trade/search` sum used **Chicago calendar midnight→now**; TopStep combine “day” is often **17:00 CT** session. User saw **-218.82** vs smaller calendar sum. | `projectx_broker_api.py`: compute **both** `net_pnl_session` and `net_pnl_calendar_day`; primary `net_pnl` via `SOVRAN_REALIZED_PNL_MODE` (default **`session`**). Docs: `Architecture/Broker_API_Realized_PnL.md`. | 2026-03-23 |
| P12 | **WS connect patch vs `strict_websocket` + RiskVault veto model** | `connection_management` patch logged “REST polling” and returned `True` on WS timeout/incomplete hubs. `GlobalRiskVault` used deprecated OpenRouter model id. | `_patched_connect` returns **`False`** when `Config.strict_websocket` and hubs not ready/timeout. Risk veto uses `VORTEX_AUDIT_MODEL` or **`gemini-2.5-flash`**. Session log: [[2026-03-23_StrictWS_GlobalRiskVault_Verification]]. | 2026-03-23 |
| P13 | **Gemini unusable / OpenRouter-only stack** | Defaults and Gambler overlay used Gemini slugs; monitor could probe Gemini under `generic_http`. | `sovran_ai` OpenRouter defaults + `diag_openrouter_ping.py`; monitor prefers OpenRouter when `VORTEX_LLM_PROVIDER=openrouter` or `sk-or-` key; vault [[Protocols/LLM_TRADER_PROTOCOL]]. | 2026-03-23 |
| P14 | **Missing Account ID / Heuristic Warning (P8)** | `PROJECT_X_ACCOUNT_ID` missing in `.env`. | Restored required credentials and confirmed API handshake. | 2026-03-23 |
| P15 | **Silent Authentication Failure** | `PROJECT_X_API_KEY` and `USER` missing in host env. | Variables restored to host environment; verified with `test_fixed_bracket.py`. | 2026-03-23 |
| 1 | **REST Polling Detection** | SDK and Engine had silent REST fallbacks. | Raised `RuntimeError` in SDK `core.py` and removed fallbacks in `sovran_ai.py`. | 2026-03-23 |
| 2 | **$50k Bankroll Placeholder** | Hardcoded initial balance causing drift. | Implemented `sync_broker_truth_api()` for real-time API truth. | 2026-03-23 |
| 3 | **Corrupted State File** | Legacy PnL in state file. | Resolved by syncing from API truth. | 2026-03-23 |
| 4 | **UI Popups** | Multiprocessing spawning console windows. | Forced `spawn` method in `sovran_ai.py`. | 2026-03-23 |
| 5 | **REST Fallback** | SDK handshake fails -> silent fallback to REST polling | `--force-direct` bypass | 2026-03-23 |
| 6 | **PnL Invisibility** | `broker_sync.py` reads from manual CSV export, not API | Refactor `broker_sync.py` to use API | 2026-03-23 |
| 7 | **Silent Veto Failure** | Gemini API 404 (wrong endpoint) went undetected for hours | Patched `google_gemini.py` | 2026-03-23 |
| 8 | **Gemini 404** | `v1` endpoint -> `v1beta` | Patched `google_gemini.py` | 2026-03-22 |
| 9 | **Data Lag** | SDK handshake hang in isolated workers | `--force-direct` bypass | 2026-03-23 |
| 10 | **PnL Distortion (-$192k)** | Legacy `MNQ_WARWICK.json` in `_data_db` | Deleted file; refactored RiskVault | 2026-03-23 |
| 11 | **Gemini API 404 (audit_model)** | `audit_model` defaulted to `gemini-1.5-flash` (deprecated/404). Gambler used `google/gemini-2.0-flash-exp:free` (also 404). | Both updated to `gemini-2.5-flash` in `sovran_ai.py`. | 2026-03-23 |

## Architectural Debt
- **Handshake Fragility:** TopStepX SignalR hub unstable for SDK connections.
- **CSV Dependency:** `broker_sync.py` relies on manual/scripted exports.
- **Process Sprawl:** Multiple isolated workers hard to monitor without unified logging.

## Monitoring Suite (Active)
- **Script:** `C:\KAI\armada\monitor_sovereign.py`
- **Run:** `python monitor_sovereign.py --once` for snapshot, or without flag for 60s polling.
- **Checks:** Provider-aware LLM health (OpenRouter/Gemini/Anthropic), process persistence, multi-log freshness (watchdog + sovran_run + stderr), WebSocket/Gambler signals, broker API vs state drift, Obsidian research, error patterns (incl. 429).
- **Output:** `C:\KAI\armada\_logs\monitor_snapshot.log`
- **Detail:** See `Architecture/Test_and_Monitoring_Suites.md`.

## Knowledge Graph Integration (Planned)
- See `Research/InfraNodus_Knowledge_Graph_Transcript.md` for strategy
- See `Plans/Obsidian_Knowledge_Graph_Strategy.md` for implementation plan

## March 23 Afternoon Findings (API Fixes)
### TopStepX API Order Visibility & Account Balance Root Cause
- **Orders Not Visible in UI:** Bracket orders placed directly via the API use raw Matching Engine parameters. The TopStepX UI requires specific, frontend-generated Auto-OCO grouping IDs to render the brackets visually on the chart. As a result, API-placed brackets are active and working on the exchange, but are "invisible" to the React UI.
- **Account Balance Endpoint:** The actual account balance visibility issue is because the system currently reads from a manual CSV (`broker_sync.py`). The true API endpoint to fetch live equity is the TopStepX/Tradovate REST endpoint.

### OpenRouter Stealth Model & Paralyzation Fix
- **Stealth Model:** The optimal current "stealth" model (high capability with zero data retention and strict privacy routing) is `meta-llama/llama-3.3-70b-instruct`. To ensure proper stealth and zero-retention routing through OpenRouter, the system must properly pass the `HTTP-Referer` and `X-Title` headers.
- **Rate Limit Paralyzation (Error 429):** OpenRouter free tiers aggressively reject high-throughput traffic (18,000+ failures). The solution requires wrapping the OpenRouter integration in `llm_client.py` and `openrouter.py` with an exponential backoff specifically targeting HTTP 429 and 500 errors.
