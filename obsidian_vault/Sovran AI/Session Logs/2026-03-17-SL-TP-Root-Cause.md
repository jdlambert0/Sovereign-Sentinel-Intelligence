# SL/TP - Root Cause Analysis & Solution

## Date
March 17, 2026

## Problem Discovered
All previous attempts placed SL/TP as SEPARATE orders AFTER the entry filled. This creates regular independent orders, NOT bracket orders.

## Why It Failed
- We placed entry order first
- Then added SL/TP as separate orders after fill
- These appear as "stop market buys" and "limit buys" in the platform
- NOT recognized as SL/TP bracket lines

## Root Cause
TopStepX bracket orders must be sent WITH the entry order as `stopLossBracket` and `takeProfitBracket` parameters. This creates "suspended" bracket orders that:
1. Activate only when entry fills
2. Display as proper SL/TP lines in the platform
3. Have OCO (One Cancels Other) behavior

## Solution: Place Order WITH Brackets

### Correct API Payload
```json
{
  "accountId": 18410777,
  "contractId": "CON.F.US.MNQ.M26",
  "type": 2,
  "side": 1,
  "size": 1,
  "stopLossBracket": {
    "ticks": 50,
    "type": 4
  },
  "takeProfitBracket": {
    "ticks": 30,
    "type": 1
  }
}
```

### Key Points
- `stopLossBracket` and `takeProfitBracket` are passed WITH the initial order
- `ticks` = number of ticks from entry price
- `type` = order type (4=Stop, 1=Limit)
- Brackets become "suspended" until entry fills
- When one bracket fills, other automatically cancels (OCO)

## Options Tested (All Failed)

### Option A: REST API Separate Orders
- Placed SL/TP after entry filled
- Result: Regular orders, not brackets

### Option B: SDK place_stop_order/place_limit_order
- Used SDK methods after entry filled
- Result: Regular orders, not brackets

### Option C: SDK place_bracket_order()
- Uses WebSocket (binary data issue)
- Result: WebSocket fails, can't complete

## New Implementation
Place order WITH brackets in single API call using REST API.

## Reference
- ProjectX API Docs: https://gateway.docs.projectx.com/docs/api-reference/order/order-place/
- Auto-OCO Brackets: https://help.topstepx.com/settings/risk-settings/auto-oco-brackets
