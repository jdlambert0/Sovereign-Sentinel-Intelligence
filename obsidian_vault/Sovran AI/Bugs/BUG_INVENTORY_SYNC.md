# Sovereign Bug Inventory Sync
**Snapshot:** 2026-03-23 (updated evening CT)

## 🚨 Critical Failures (P0)
- [x] **Corrupted State File (-$244k)**: `sovran_ai_state_MNQ_SOVEREIGN.json` was reporting absurd PnL from legacy artifacts.
    - **Remediation**: Reset to clean $50k bankroll.
- [ ] **REST Polling Fallback**: Detected 6x in recent logs. `strict_websocket` should have halted the system.
    - **Next Step**: Verify `strict_websocket` enforcement logic in `sovran_ai.py`.
- [ ] **Gemini 404 Veto Error**: 404s detected in `stderr` log.
    - **Next Step**: Check `llm_client.py` for endpoint stability.

## ⚠️ Active Warnings (P1)
- [ ] **Stale Gambler State**: `MNQ_GAMBLER` state 532 min old.
- [x] **Diagnostic UI Crash**: `diagnose_fleet.py` crashed on Unicode emoji.
    - **Remediation**: Switched to ASCII status tags.
- [ ] **Duplicate Python stacks**: System `python.exe` + venv both running `sovran_ai.py` → lock spam.
    - **Tool**: `C:\KAI\armada\enforce_venv_armada.py` — see [[Single_Venv_Stack]] in `Ops/`.

## ✅ Verified Working (Passes Diagnostic)
- [x] **Heartbeat**: ACTIVE (recency < 30s)
- [x] **Process Liveness**: ACTIVE (Sovereign + Gambler running)
- [x] **WebSocket Health**: ACTIVE (SignalR Bridge messages receipt verified)
- [x] **API Auth**: ACTIVE (TopStepX token acquired)
- [x] **Environment**: ACTIVE (Required keys `PROJECT_X_API_KEY` and `PROJECT_X_USERNAME` restored)
- [ ] **Strategic Veto (LLM Credit Exhaustion)**: OpenRouter 402 Error detected.
    - **Status**: Blocking *automated* trading (veto loop failure); bypassed for *manual* commands.
- [x] **Broker RPNL semantics**: Session (17:00 CT) vs calendar documented — [[Broker_API_Realized_PnL]]

## 🛠️ Recently Resolved
| # | Issue | Root Cause | Fix | Date |
|---|---|---|---|---|
| 11 | **Gemini API 404 (audit_model)** | `audit_model` defaulted to `gemini-1.5-flash` | Updated to `gemini-2.5-flash` | 2026-03-23 |
| 12 | **Missing Environment Credentials** | `PROJECT_X_API_KEY` / `USER` missing | Restored variables to host env | 2026-03-23 |
| 13 | **Stale Manual Command Detection** | `processed: true` flag in JSON | Reset to `false` + engine re-trigger | 2026-03-23 |
