# Bug Report: TEST TRADE RESULTS - 2026-03-18

## Test Trade Summary

**Test**: Wide stop mandate trade
**Script**: `test_mandate_wide.py`
**Time**: 2026-03-18 16:05 CT
**Result**: ✅ TRADE EXECUTED - Position OPEN

### Trade Details
- **Action**: BUY
- **Size**: 1 contract
- **Entry**: $24,934.50
- **Side**: LONG
- **Contract**: MNQ (CON.F.US.MNQ.M26)

---

## Bugs Found

### BUG-006: Unicode Encoding Error in Logging ❌

**Severity**: Medium
**Impact**: Logging errors in console, but doesn't affect trading

**Error**:
```
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f50c' in position 163
```

**Cause**: Windows console (cp1252) can't encode emoji characters

**Affected**: All logging output from `project_x_py` SDK

**Fix Needed**: 
1. Either suppress emoji logging OR
2. Configure logging to use UTF-8 encoding
3. Or run in a proper terminal that supports UTF-8

---

### BUG-007: WebSocket Connection Failed (Expected) ⚠️

**Severity**: Informational
**Status**: EXPECTED - This is why we built the Node.js sidecar

**Error**:
```
WARNING: WebSocket connection timed out after 30s. System will operate in REST polling mode.
ERROR: WebSocket error - subscribe_user_updates
ERROR: WebSocket error - subscribe_market_data
```

**Cause**: TopStepX server blocking Python WebSocket connections

**Fix Applied**: ✅ Node.js sidecar implemented and running on port 8765

**Note**: The sidecar provides real-time data to Python via HTTP

---

### BUG-008: '_instruments' Attribute Error ⚠️

**Severity**: Medium
**Impact**: Order may have been placed WITHOUT proper context

**Error**:
```
ERROR: Failed to place order: 'InstrumentContext' object has no attribute '_instruments'
```

**Location**: In `calculate_size_and_execute()` method

**Root Cause**: The code is trying to access `context._instruments` but `InstrumentContext` doesn't have this attribute

**Impact**: Trade was placed but may have issues with subsequent operations

**Fix Needed**: Update `calculate_size_and_execute()` to use correct API

---

## What Worked ✅

1. ✅ TradingSuite connected successfully
2. ✅ AI made decision (BUY with 1.00 confidence)
3. ✅ REST API authentication worked
4. ✅ Position opened successfully
5. ✅ Position confirmed: Size 1, Entry $24,934.50, LONG
6. ✅ Node.js sidecar running on port 8765

---

## What Needs Investigation

### SL/TP Bracket Status ❌ CONFIRMED MISSING

**Question**: Did the SL/TP brackets get attached?
**Answer**: **NO - Brackets were NOT attached!**

**Order Details**:
```json
{
  "id": 2656526329,
  "contractId": "CON.F.US.MNQ.M26",
  "status": 2,        // Filled
  "type": 2,          // Market
  "side": 0,          // Buy
  "size": 1,
  "filledPrice": 24934.5,
  "limitPrice": null,
  "stopPrice": null   // NO STOP LOSS!
}
```

**Root Cause Identified**:

The error `'InstrumentContext' object has no attribute '_instruments'` occurred BEFORE the SL/TP brackets could be attached.

The code at line 1122:
```python
instrument = self.suite._instruments.get(self.config.symbol)
```

In `test_mandate_wide.py`:
- Line 45: `engine = AIGamblerEngine(config, state, context)` - passes `context` (which is `suite._instruments[symbol]`)
- The engine stores `context` as `self.suite`
- Then `calculate_size_and_execute()` tries to access `self.suite._instruments` which doesn't exist on `InstrumentContext`

**Same issue in main sovran_ai.py run() function (line 1889-1890)**:
```python
context = suite._instruments[symbol]
engine = AIGamblerEngine(config, state, context)
```

**Fix Needed**:
1. Store BOTH `TradingSuite` and `InstrumentContext` in `AIGamblerEngine`
2. OR pass `suite` (TradingSuite) to the engine, not just `context`
3. Update `calculate_size_and_execute()` to use correct object

---

## Test Trade Log Location

Full log output saved in session output.

---

## Next Steps

1. **Verify SL/TP**: Check TopStepX platform manually
2. **Fix BUG-006**: Add UTF-8 encoding to logging
3. **Fix BUG-008**: Update `calculate_size_and_execute()` method
4. **Integrate Sidecar**: The realtime bridge needs full integration testing

---

## Files Modified

- `C:\KAI\armada\sovran_ai.py` - Added realtime bridge integration
- `C:\KAI\armada\realtime_bridge.py` - New bridge module
- `C:\KAI\armada\realtime_data.py` - New client library
- `C:\KAI\armada\topstep_sidecar\src\` - Node.js sidecar

---

Created: 2026-03-18
