# Pre-Launch Verification Checklist

## Priority 1: Prove the Data Shape (BLOCKING)
- [ ] Write `test_quote_shape.py`
  - Connect to TopStepX
  - Subscribe to MNQ quotes
  - Print first 5 raw `event.data` payloads
  - Save output to `C:\KAI\armada\_logs\quote_shape_dump.txt`
- [ ] Confirm exact key names in the dict
- [ ] Update `handle_quote` and `handle_trade` to use correct keys

## Priority 2: Single-Symbol Smoke Test
- [ ] Run `sovran_ai.py --symbols MNQ` only
- [ ] Verify log shows "Passing context to AI Gambler" within 60s
- [ ] Verify log shows AI decision output (BUY/SELL/WAIT)
- [ ] Check `sovran_state_MNQ.json` is being written

## Priority 3: Multi-Symbol Launch
- [ ] Run `sovran_ai.py --symbols MNQ,MES,M2K`
- [ ] Verify all 3 engines start with stagger
- [ ] Verify no `SILENT_WS_FAILURE` or `WS_TIMEOUT`
- [ ] Run `monitor_health.py` — all 3 symbols reporting

## Priority 4: Session Phase Verification
- [ ] Confirm `get_session_phase()` returns correct phase for current CT time
- [ ] Verify trading is NOT blocked during expected active hours (8:30-11:00 CT, 13:00-15:00 CT)

## Priority 5: LLM Pipeline Audit
- [ ] Verify OpenRouter API key is valid and not rate-limited
- [ ] Confirm `retrieve_ai_decision()` returns valid JSON
- [ ] Check that the ensemble voting logic works end-to-end

---

## Anti-Patterns to Avoid
> [!CAUTION]
> 1. Do NOT make multiple edits to `handle_quote` in one session without verifying each one
> 2. Do NOT launch multi-symbol before single-symbol works
> 3. Do NOT assume `hasattr()` works on dicts — always use `isinstance(data, dict)` first
> 4. Do NOT ignore `[project_x_py.event_bus] Error` messages — they ARE your bugs

## Tags
#action-plan #pre-launch #checklist
