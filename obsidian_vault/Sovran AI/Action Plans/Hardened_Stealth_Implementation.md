# Plan: Hardened Stealth Implementation (Phase 2/3)

This plan outlines the steps to achieve 100% background (stealth) execution, enforce WebSocket-only trading data, restore accurate PnL/balance truth from the API, and resolve Gemini 404 errors.

## User Review Required

> [!IMPORTANT]
> - **Model Upgrade**: We are upgrading Gemini from 1.5 to 2.5 (as per 2026 API inventory) to resolve 404 errors.
> - **Bankroll Sync**: The system will now force-sync `bankroll_remaining` from the TopStepX API on startup, overriding any local $50k placeholders.
> - **Strict WebSocket**: If the SignalR connection fails, the system will HALT rather than falling back to REST polling.

## Proposed Changes

### 1. Data Integrity & API Truth
Integrating the actual broker bankroll and realized PnL to eliminate state drift.

#### [MODIFY] [sovran_ai.py](file:///C:/KAI/armada/sovran_ai.py)
 - Update `sync_broker_truth_api()` to return `balance` as well as `net_pnl`.
 - Update the startup sequence (line 2718+) to sync `state.bankroll_remaining` with the API `balance`.
 - Update `finalize_trade()` to use the same logic for mid-session reconciliation.

### 2. Stealth & Background Execution
Enforcing the "No UI" and "Lightpanda Only" mandate.

#### [MODIFY] [llm_client.py](file:///C:/KAI/vortex/llm_client.py)
 - Ensure all external calls are backgrounded.
 - (Already done) Ensure `lightpanda_harness.py` is the primary research tool.

### 3. WebSocket Enforcement
Eliminating REST polling for market data.

#### [MODIFY] [realtime_bridge.py](file:///C:/KAI/armada/realtime_bridge.py) / [realtime_data.py](file:///C:/KAI/armada/realtime_data.py)
 - Audit and remove any implicit REST fallbacks in the polling loops.
 - Ensure `strict_websocket = True` in `Config` triggers a hard-halt if SignalR disconnects.

### 4. LLM Reliability (Gemini 404)
Fixing the 404 errors by updating the model strings and verifying the endpoint.

#### [MODIFY] [.env](file:///C:/KAI/armada/.env)
 - Update `VORTEX_LLM_MODEL` to `gemini-2.5-flash`.
 - Update `VORTEX_AUDIT_MODEL` to `gemini-2.5-flash`.

#### [MODIFY] [google_gemini.py](file:///C:/KAI/vortex/providers/google_gemini.py)
 - Verify the endpoint URL matches `v1beta` or `v1` requirements for the 2.5 models.

## Verification Plan

### Automated Tests
 - Run `diagnose_fleet.py` to confirm "REST Polling" and "Gemini 404" are cleared.
 - Run `preflight.py` to ensure all 37 gates pass.
 - Run a dedicated `test_broker_sync.py` to verify the actual balance is fetched.

### Manual Verification
 - Observe the console for 10 minutes to ensure NO Chrome/Command windows pop up.
 - Verify that the $50k bankroll in Obsidian/State is replaced by the actual broker value.
