# Emergency Fallback SOP: Sovereign Alpha (March 2026)

This document provides the "Smooth Tomorrow" contingency plan for the Sovereign Alpha engine.

## 1. Connectivity Failure (Silent WebSocket)
- **Symptom:** Logs show "Data Freshness Crisis" or `_quote_count` remains static.
- **Auto-Fix:** System should trigger `WS_TIMEOUT` recovery and internally reconnect.
- **Manual Intervention:** 
    1. Run `C:\KAI\armada\stop_sovran.bat`
    2. Run `C:\KAI\armada\start_sovran.bat`
    3. Verify heartbeat in `_logs/heartbeat.txt`.

## 2. API 404 / Endpoint Shift
- **Symptom:** Rapid sequence of 404 errors in `sovran_errors.log`.
- **Mitigation:**
    1. Check `llm_client.py` for updated provider endpoints.
    2. Switch to the redundant provider in `.env` (e.g., if Anthropic is down, switch to Gemini).
    3. Run `preflight.py` to confirm connectivity.

## 3. High Volatility / Liquidity Gap
- **Symptom:** Engine reports "Micro-Chop" or "VPIN Spike".
- **Action:** System automatically enters "Force WAIT" mode. 
- **Manual Flatten:** If the engine hangs during extreme volatility:
    1. Run `C:\KAI\armada\flatten_all_positions.py`.
    2. Monitor `check_positions.py` for broker truth.

## 4. Contract Expiration (Time Bomb)
- **Symptom:** "Invalid Instrument" errors during trade execution.
- **Fix:** 
    1. The system now uses `resolve_contract_id` for dynamic lookup.
    2. If lookup fails, manually update the `DEFAULT_CONTRACT_ID` in `sovran_ai.py` (Line ~650).
    3. Use `get_mnq_id.py` to find the correct active contract string.

## 5. Global Risk Breach
- **Symptom:** `GlobalRiskVault` log shows "HARD LOCK: Daily Limit Hit".
- **Policy:** **NO MORE TRADING UNTIL NEXT SESSION.** 
- **Exception:** Only the USER can reset the state by deleting `_data_db/gambler_state_MES.json` (or appropriate symbol file). **CAUTION: This bypasses all safety protocols.**

---
*Status: HARDENED | "Smooth Tomorrow" Plan Active.*
