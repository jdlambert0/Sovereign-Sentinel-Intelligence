# Test and Monitoring Suites Architecture

**Last Updated:** 2026-03-23 (monitor hardening pass)

## 1. Monitoring Suite
The monitoring suite acts as a sentry over the Sovereign engine, ensuring it is healthy, active, and functioning outside of just "did it crash?" checks.

### Core Components
- **`monitor_sovereign.py`**: The primary diagnostic tool (`C:\KAI\armada\monitor_sovereign.py`). Writes snapshots to `_logs\monitor_snapshot.log`.
  - **LLM API Health (provider-aware)**: Uses `VORTEX_LLM_PROVIDER` and `.env` to ping **OpenRouter** (`https://openrouter.ai/api/v1/chat/completions`), **Anthropic**, or **Gemini** as configured. HTTP **429** responses are reported as **WARN** (rate limit), not hard FAIL.
  - **Process Persistence**: Ensures `sovran_ai.py` (or `launch_armada.py`) is running (`psutil`).
  - **Log Freshness**: Checks each of:
    - `_logs\sovran_run.log`
    - `_logs\watchdog_restart_stderr.log`
    - `_logs\sovran_fresh_stderr.log`
    - `_logs\sovran_output.log`  
    Plus a **summary** line: newest activity across those files (600s threshold).
  - **Live Data Stream Test**: Scans the best non-empty log (prefers `sovran_run.log`, else watchdog stderr) for `quote` and `GAMBLER` signals; flags `REST` in watchdog tail as possible WS fallback.
  - **State Sanity Check**: Verifies `sovran_ai_state_MNQ_SOVEREIGN.json` daily PnL is plausible.
  - **Broker Spot-Check**: `projectx_broker_api.fetch_broker_truth_sync()` — `Account/search` + **`Trade/search`** sums (half-turn `profitAndLoss`, skip `voided`). Reports **session** (since 17:00 CT) and **calendar-day** RPNL; primary `net_pnl` follows `SOVRAN_REALIZED_PNL_MODE` (default `session`). Compare balance vs state `bankroll_remaining` (warn if drift > $20).
  - **Knowledge Output Check**: Obsidian `Research\` and `Session Logs\` freshness (24h).
  - **Error Pattern Recognition**: Recent `404`, `Traceback`, `Gemini Brain offline`, `HTTPError`, `429` in run/output/watchdog logs.

### Launch & Operation
```text
cd C:\KAI\armada
python monitor_sovereign.py --once
```
Continuous polling every 60s without `--once`.

---

## 2. Test Suite
The testing ecosystem ensures that logic holds before deployment and that the broker API remains functional.

### Core Components
- **`preflight.py`**: The Zero-Bug Infinity gate. Runs ~45 compilation, structural, and sanity checks on `sovran_ai.py` before any major run.
- **`test_l2_live.py`** & **`test_2_2_quote_flow.py`**: Raw WebSocket and market data ingestion tests to ensure TopStepX SignalR is working.
- **`test_native_bracket_integration.py`** & **`test_fixed_bracket.py`**: Validates the atomic bracket placement API guarantees against the broker.
- **`final_test.py`** / **`test_final_fix.py`**: Specialized execution tests run during the final leg of a session to guarantee readiness.

### Continuous Validation (CI/CD via LLM)
- Every major code edit mandates a run of `preflight.py`.
- System will not progress unless 45/45 tests pass.
