# Deep Audit: Failure Points & Risk Analysis (March 2026)

## 1. WebSocket / Connectivity Risks
- **Silent WS Failure**: SignalR remains connected but stops sending `Trade` or `Quote` updates. 
  - *Mitigation*: Implemented `SILENT_WS_FAILURE` check (300s window). 
  - *Hardening*: Reduce window to 60s for high-conviction periods.
- **Handshake Hang**: `TradingSuite.create()` can hang for 45s+ during high-load periods.
  - *Mitigation*: Implemented `asyncio.wait_for` timeout in `run()` (sovran_ai.py:2404).

## 2. API / Substrate Risks
- **Model Identifier Drift**: Providers (Anthropic/Google) changing stable naming conventions.
  - *Fix*: Locked to `claude-sonnet-4-20250514` and `gemini-2.5-flash`.
- **404 Endpoint Shifts**: Google Gemini shifting `v1beta` to `v1`.
  - *Fix*: Switched to stable `v1` endpoint.

## 3. Operational / Market Risks
- **Rollover Volatility**: MNQ March 20 rollover. Hardcoded contract IDs in `sovran_ai.py` (lines 666-672) must be manually updated or dynamically resolved.
  - *Observation*: Current hardcoded `M26` (June) is correct for post-March 20.
- **Weekend API Leak**: Research loop consuming credits when market is closed.
  - *Mitigation*: Implement `WEEKEND` session phase gate for LLM calls.

## 4. Logic / Safety Risks
- **Trailing Stop Mockup**: Intelligent management logs SL moves but does NOT execute them.
  - *Mitigation*: Implement `modify_bracket_order` via `Order/modify` REST API.
- **Global PnL Drift**: `bankroll_remaining` desyncing from actual broker balance.
  - *Mitigation*: Implemented `finalize_trade` sync at line 1819.
- **Logic Crash (Trade Initiation)**: `warwick_cycle` and `gamble_cycle` can fail if `self.active_trade` is not initialized as an empty dict before key access (fixed in recent audit).
- **JSON Confusion (Ensemble)**: `retrieve_ai_decision` regex might catch a "Sovereign Briefing" JSON block instead of the "Trade" JSON if the LLM outputs multiple blocks.
- **Contract Time-Bomb**: Hardcoded `CON.F.US.MNQ.M26` will expire in June 2026.
  - *Action*: Need dynamic contract resolution via `api/Instrument/search`.
- **Emergency Flatten Crash**: `calculate_size_and_execute` calling `emergency_flatten` before `self.active_trade` is guaranteed to be a dict (risk of `AttributeError`).
- **PnL Over-Sync**: `finalize_trade` calls `trailing_dd.update` twice, once directly and once via `PnL RECONCILIATION`. Harmless but inefficient.
- **Recover Active Position False-Positive**: The `try/except` around Obsidian logging (line 1729) catches errors but might mask recovery failures.
- **Process Crash (Exception Bubbling)**: `monitor_loop` raises exceptions that aren't caught within `init_and_run_engine`. Because `asyncio.gather` is used in `run()`, a single engine's crash could potentially take down all 9 engines and the Risk Vault.
- **Suite/Handshake Hang**: `TradingSuite.create` timeout (45s) might result in a `MagicMock` being used even if the real suite would have succeeded with 5 more seconds, leading to a "degraded mode" that isn't necessary.
- **Risk Vault Stale Check**: `GlobalRiskVault` doesn't verify if an engine instance is still "alive" or if its data feed is fresh before deciding NOT to flatten it (or vice-versa).

# Emergency Fallback SOP (The "Smooth Tomorrow" Plan)

### Symptom: Engine Restart Loop
1. Check `_logs/autonomous_sovran_engine.log`.
2. If `401 Unauthorized`: API Token expired. Restart full loop to trigger re-auth.
3. If `404 Not Found`: Model ID retired. Update `.env` with latest stable from `list_api_models.py`.

### Symptom: Frozen Market Data
1. Check `heartbeat.txt` for `Last Update`.
2. If > 60s since update AND NOT weekend: Manual WebSocket Reset.
3. Command: `python flatten_all_positions.py` then `start_sovran.bat`.

### Symptom: Trailing Drawdown Trigger
1. Global Risk Vault will flatten all (Mandate: -$450).
2. **DO NOT RESTART** until a "Post-Mortem Research" note is added to Obsidian.
3. Review `Trades/` to identify the failure pattern (e.g., Slop, News, Whipsaw).
