# Phase 4 — Safety & recovery (runbook for LLMs)

**Purpose:** Controlled verification of disconnect, SL/TP, drawdown, restart — **small size**, **RTH** when applicable.

## Preconditions
- `python preflight.py` → 45/45 (`C:\KAI\armada`)
- `python monitor_sovereign.py --once` — broker OK; note `net_pnl_session` vs `net_pnl_calendar_day`
- `enforce_venv_armada.py` → exit 0 (or clean duplicates)
- Combine rules + daily loss limits understood

## 4.1 WebSocket disconnect
1. Note baseline: `quote` / bridge lines in `watchdog_restart_stderr.log` or `sovran_run.log`.
2. Induce disconnect (network toggle **or** approved dev flag if present) **once**.
3. Pass: logs show recovery path, trading resumes or **controlled halt** per `strict_websocket` / engine policy.
4. Record: timestamp, log excerpt path, whether positions were flat.

## 4.2 Stop loss hit
1. **Micro size** (1 MNQ or paper policy).
2. Bracket with SL only (or known distance); **verify fills via API** (`Order/search`, `Trade/search`) — not chart UI.
3. Pass: position flat, PnL in API matches expectation within fees.
4. Record: order ids, R-multiple estimate.

## 4.3 Take profit hit
Same as 4.2 with TP; verify API/trade log.

## 4.4 Drawdown protection ($450 / combine rules)
1. Confirm `GlobalRiskVault` / gates in `sovran_ai.py` with **paper or minimal size**.
2. Pass: engine halts or flattens when limit hit; log line identifiable.
3. Record: trigger condition found in code + log string.

## 4.5 Process restart
1. Clean restart: `enforce_venv_armada.py`, single `launch_armada.py`, wait for `[SYNC]` and state JSON.
2. Pass: no duplicate stacks; `sovran_ai_state_*_SOVEREIGN.json` matches API within policy.

## Evidence
Append results to `Testing/TEST_RESULTS.md` and bump `Comprehensive_Test_Plan.md` tables with **date** and **log paths**.

## What we cannot automate here
Full Phase 4 requires **live** or **simulated** market conditions and **human** judgment on risk. This runbook is the checklist; execution is session-based.
