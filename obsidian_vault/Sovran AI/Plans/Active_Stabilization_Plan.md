# Active Stabilization Plan: Sovereign Reliability Lockdown
**Date:** 2026-03-23 | **Status:** IN PROGRESS

## Phase 1: Stealth Protocol (P0 — IMMEDIATE)
- **Problem:** AI agent's `run_command` tool spawns visible PowerShell windows. The `multiprocessing.Process` in `sovran_ai.py` may also flash console windows on Windows.
- **Fix:** 
  1. Agent must use silent file tools (`write_to_file`, `view_file`) instead of `run_command` for all filesystem operations.
  2. For essential commands, use `SafeToAutoRun` background mode only.
  3. Audit `multiprocessing.Process` for `CREATE_NO_WINDOW` compatibility.
- **Verification:** Zero UI popups during fleet startup/operation.

## Phase 2: High-Fidelity Data (WebSocket-Only + API Truth)
- **Problem:** REST polling fallback degrades trading data. CSV-based PnL sync is stale.
- **Fix:**
  1. Remove REST fallback — if WS fails, HALT and let watchdog restart.
  2. Replace `broker_sync.py` CSV parsing with direct ProjectX API calls:
     - **Balance:** `POST /api/Account/search` → `accounts[0].balance`
     - **Realized PnL:** `POST /api/Trade/search` → `sum(trades[].profitAndLoss)`
     - **Real-time:** SignalR `user` hub → `GatewayUserAccount` and `GatewayUserTrade` events
  3. Deploy `--strict-websocket` flag in `Config`.
- **Verification:** `heartbeat.txt` matches TopStepX dashboard values.

## Phase 3: Diagnostic Sentinel (Test Suite)
- **Problem:** Silent errors (Gemini veto 404, stale state files) go undetected.
- **Fix:** Build `diagnose_fleet.py` that checks:
  1. All fleet processes alive and responsive.
  2. WebSocket connection health (last message timestamp).
  3. LLM learning loop activity (recent entries in memory files).
  4. API connectivity (auth token validity).
  5. PnL truth alignment (state file vs API).
  6. Log entropy (detect "slop loops" and repeated errors).
- **Verification:** Suite detects 100% of known failure modes.

## Status History
- **2026-03-23 08:42:** Plan created. Stealth Protocol prioritized.
