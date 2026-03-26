# TopStepX API Research Plan - SL/TP Bracket Orders

**Date:** 2026-03-18
**Status:** ✅ RESEARCH COMPLETE - TESTED AND CONFIRMED
**Mode:** Extensive Research (24 agents)

## Research Goal

Find confirmed working solutions for attaching SL/TP brackets to positions using TopStepX API (ProjectX SDK).

## Problem Statement

The ProjectX SDK (`project_x_py`) cannot reliably create OCO-linked SL/TP brackets:
- `place_bracket_order()` - SDK places orders sequentially, not atomically
- Sequential `add_stop_loss()` + `add_take_profit()` - Creates orphaned orders
- Manual `linked_order_id` - SDK shows `{}` for linked orders
- TopStepX UI only shows 1 of 2 expected exit orders

## Root Cause Identified

### SDK Uses Sequential Order Placement
From `project_x_py/order_manager/bracket_orders.py` lines 398-566, the SDK:
1. Places entry order
2. Waits for fill (up to 60 seconds)
3. Places stop loss (separate API call)
4. Places take profit (separate API call)
5. Tries to record OCO relationship in recovery manager

**Problem:** This is NOT atomic. If Position Brackets are enabled, account-level brackets conflict with API brackets.

## Solution Found: Native REST API Brackets

The ProjectX REST API supports atomic brackets in a SINGLE API call:

```json
{
  "accountId": 18410777,
  "contractId": "CON.F.US.MNQ.M26",
  "type": 2,
  "side": 0,
  "size": 1,
  "stopLossBracket": {
    "ticks": -400,
    "type": 4
  },
  "takeProfitBracket": {
    "ticks": 200,
    "type": 1
  }
}
```

## Key Discoveries

### 1. API URL
`https://api.topstepx.com/api` (NOT `thefuturesdesk.projectx.com`)

### 2. Tick Signs
- LONG positions: SL ticks must be NEGATIVE (-400)
- SHORT positions: SL ticks must be POSITIVE (+400)

### 3. Order Types
- SL: `type: 4` (Stop Market) - Limit causes error
- TP: `type: 1` (Limit)

### 4. Authentication
Must use SDK to get token via `suite.client.session_token`

## Error Messages Encountered

| Error | Cause | Fix |
|-------|-------|-----|
| "Invalid stop loss type (Limit)" | Used type=1 for SL | Use type=4 |
| "Ticks should be less than zero when longing" | Used positive ticks for LONG | Use -400 |

## ✅ Solution Verified - TEST PASSED

### Test Results
```python
response = await client.post(
    "https://api.topstepx.com/api/Order/place",
    json={
        "side": 0,  # Buy
        "stopLossBracket": {"ticks": -400, "type": 4},
        "takeProfitBracket": {"ticks": 200, "type": 1}
    }
)
# Result: {"orderId":2660039654,"success":true,"errorCode":0}
```

### Orders Created
- ID:2660039656 - Stop @ 24766.0 (SL)
- ID:2660039657 - Limit @ 24916.0 (TP)

## Implementation Checklist

- [x] Research completed
- [x] Solution identified (Native API brackets)
- [x] Test executed successfully
- [ ] Integrate into Sovran AI
- [ ] Test during market hours
- [ ] Verify OCO behavior

## Files Created

- `C:\KAI\armada\native_bracket_test.py` - First attempt
- `C:\KAI\armada\native_bracket_test_v2.py` - Working version
- `C:\KAI\armada\get_token.py` - Token extraction utility
- `Research/TopStepX-API-SLTP-Research-Results.md` - Solutions
- `Research/TopStepX-SLTP-Complete-Research-Log.md` - Full log

## Next Steps (When User Approves)

1. Integrate `place_atomic_bracket()` into sovran_ai.py
2. Test during market hours
3. Verify OCO linking works (SL triggers → TP cancels)

