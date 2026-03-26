# ProjectX broker API fix (balance + realized PnL)

**Date:** 2026-03-23 (late evening CT)

## Source of truth
- TopStepX OpenAPI: `https://api.topstepx.com/swagger/v1/swagger.json`
- ProjectX docs: `SearchAccountRequest` requires `onlyActiveAccounts`; `TradingAccountModel.balance`; `Trade/search` → `HalfTradeModel.profitAndLoss`, `voided`.

## Code
- **`C:\KAI\armada\projectx_broker_api.py`** — single implementation used by Sovran and monitor.
- **`sovran_ai.py`** — imports `sync_broker_truth_api` from module (removed inline duplicate).
- **`monitor_sovereign.py`** — broker spot-check uses `fetch_broker_truth_sync()` with `.env` credentials.

## Behavior
1. `POST /api/Account/search` with `{"onlyActiveAccounts": true}` (not `{}`).
2. Account selection: optional `PROJECT_X_ACCOUNT_ID`; else `canTrade`, prefer non-`simulated`, name heuristics (`COMBINE` / `TOPSTEP`).
3. `POST /api/Trade/search` with `accountId`, `startTimestamp` / `endTimestamp` for **America/Chicago** calendar day through now; sum `profitAndLoss` excluding `voided`.

## Verification
- `python preflight.py` → 45/45
- `python projectx_broker_api.py` → prints balance, realized PnL, `account_id`, `account_name`
- `python monitor_sovereign.py --once` → broker line includes account tag + realized

## Ops
- **Stale `.env`:** `PROJECT_X_ACCOUNT_ID=18410777` not in active accounts → warning; heuristic selected live combine (`20560125`, ~$149.8k balance in test run). Update id or remove variable.
- **State file drift:** `bankroll_remaining` in JSON updates on **parent** `sovran_ai.py` restart when broker sync runs — do not run a second Sovran while one is locked.
- **“Live run” this session:** Monitor showed existing Sovran process; no duplicate start. Restart production path when ready to persist state.

## Next (profit path)
- Restart Sovran via normal watchdog path after hours; confirm `[SYNC]` log shows new account + balance.
- Paper-then-live discipline: Phase 4 safety tests, size caps, session PnL vs combine rules.
