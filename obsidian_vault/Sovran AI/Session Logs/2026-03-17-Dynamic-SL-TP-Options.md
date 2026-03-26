# ProjectX API - Dynamic Stop Loss / Take Profit Options

## Date
March 17, 2026

## Overview
Sovran AI needs to dynamically set stop loss and take profit at the time of each trade. This document outlines all available options from the ProjectX API.

---

## Option 1: Place Bracket Orders with Entry

### Description
Pass SL/TP directly in the initial order request using `stopLossBracket` and `takeProfitBracket` parameters.

### API Payload
```json
{
  "accountId": 18410777,
  "contractId": "CON.F.US.MNQ.M26",
  "type": 2,
  "side": 0,
  "size": 1,
  "stopLossBracket": {
    "ticks": 40,
    "type": 4
  },
  "takeProfitBracket": {
    "ticks": 40,
    "type": 1
  }
}
```

### SDK Code
```python
bracket = await suite.orders.place_bracket_order(
    contract_id=suite.instrument_id,
    side=0,  # Buy
    size=1,
    entry_price=current_price,
    stop_loss_price=current_price - 40,  # Dynamic SL
    take_profit_price=current_price + 40,  # Dynamic TP
    entry_type="market",
)
```

### Pros
- Single API call for entry + SL + TP
- Atomic operation - all orders placed together

### Cons
- **Currently broken**: WebSocket sends binary response that JSON can't parse
- SL/TP fails to place, entry order may succeed but without protection

### Status
❌ NOT WORKING - Needs WebSocket fix

---

## Option 2: Add SL/TP After Position Opens (RECOMMENDED)

### Description
Place entry order first, then add stop loss and take profit as separate orders AFTER the position is filled.

### Workflow
1. Place entry order (market/limit)
2. Poll REST API or wait for fill notification
3. After fill confirmed, add stop loss order
4. Add take profit order

### SDK Code
```python
# Step 1: Place entry order
entry_response = await suite.orders.place_market_order(
    contract_id=suite.instrument_id,
    side=0,  # Buy
    size=1,
)

# Step 2: Wait for fill (poll or wait)
await asyncio.sleep(2)  # Simple wait

# Step 3: Get current price for SL/TP levels
current_price = await suite.data.get_current_price()
stop_loss_price = current_price - 50  # Wide stop!
take_profit_price = current_price + 50

# Step 4: Add stop loss
sl_response = await suite.orders.add_stop_loss(
    contract_id=suite.instrument_id,
    stop_price=stop_loss_price,
)

# Step 5: Add take profit
tp_response = await suite.orders.add_take_profit(
    contract_id=suite.instrument_id,
    limit_price=take_profit_price,
)
```

### Alternative: Direct REST API
```python
import httpx

# After entry fills via REST:
url = "https://api.thefuturesdesk.projectx.com/api/Order/place"
headers = {
    "Authorization": f"Bearer {session_token}",
    "Content-Type": "application/json",
}

# Stop loss order
sl_payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 4,  # Stop
    "side": 1,  # Sell
    "size": 1,
    "stopPrice": entry_price - 50,
}

# Take profit order
tp_payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 1,  # Limit
    "side": 1,  # Sell
    "size": 1,
    "limitPrice": entry_price + 50,
}
```

### Pros
- Works reliably via REST API
- No WebSocket dependency
- Full control over SL/TP levels at runtime
- Can adjust SL/TP based on market conditions

### Cons
- Requires 3 separate API calls (entry + SL + TP)
- Small delay between entry and SL/TP placement
- Position is briefly unprotected

### Status
✅ RECOMMENDED - Being implemented

---

## Option 3: Enable Auto-OCO Brackets

### Description
Enable Auto-OCO brackets in TopStepX platform settings, then API can set brackets per-order.

### Platform Settings
1. Settings > Risk Settings
2. Switch from Position Brackets to Auto OCO Brackets
3. Set default values (or let API override)

### API Usage
Same as Option 1 - brackets are created as "suspended" orders and become active when entry fills.

### Key Differences from Position Brackets
| Feature | Position Brackets | Auto-OCO Brackets |
|---------|------------------|-------------------|
| Scope | Per position | Per order entry |
| Scaling | Single aggregation | Multiple entries |
| Updates | Auto-update | Per-order |
| Flexibility | Less flexible | More flexible |

### Pros
- Built-in OCO behavior (when one fills, other cancels)
- Can scale in/out with multiple entries

### Cons
- Requires account-level enable
- May need default values set in platform

### Status
⚠️ PARTIAL - Account has Auto-OCO enabled, but needs testing

---

## Comparison Matrix

| Option | Reliability | Control | Complexity | Status |
|--------|-------------|---------|------------|--------|
| 1: Bracket Orders | ❌ Broken | High | Low | Needs fix |
| 2: Add After Fill | ✅ Working | High | Medium | RECOMMENDED |
| 3: Auto-OCO | ⚠️ Unknown | Medium | Low | Test needed |

---

## Implementation Notes

### Current Position (March 17, 2026)
- 6 lots MNQ @ $24,898.625 - NO SL/TP!
- Need to add SL/TP urgently

### SUCCESS! Option 2 Implementation

**Test Date**: March 17, 2026
**Trade**: SELL 3 MNQ @ $25,000.50
**Stop Loss**: Order 2648393420 @ $25,099.50 (100 ticks above entry - for SHORT)
**Take Profit**: Order 2648393435 @ $24,949.50 (51 ticks below entry - for SHORT)

**Second Trade**: SELL 1 MNQ
**Stop Loss**: $25,094.75 (100 ticks above)
**Take Profit**: $24,944.75 (56 ticks below)

✅ **WORKING!** The pattern places entry order, waits for fill, then adds SL/TP.

### Recommended Implementation (Option 2)
```python
async def place_trade_with_protection(suite, symbol, side, size, sl_ticks, tp_ticks):
    """Place trade with dynamic SL/TP - Option 2"""
    
    # Get current price
    current_price = await suite.data.get_current_price()
    
    # Calculate SL/TP prices
    if side == 0:  # Buy
        stop_loss = current_price - sl_ticks
        take_profit = current_price + tp_ticks
    else:  # Sell
        stop_loss = current_price + sl_ticks
        take_profit = current_price - tp_ticks
    
    # Place entry order
    entry = await suite.orders.place_market_order(
        contract_id=suite.instrument_id,
        side=side,
        size=size,
    )
    
    # Wait for fill
    await asyncio.sleep(3)
    
    # Add stop loss
    sl_order = await suite.orders.add_stop_loss(
        contract_id=suite.instrument_id,
        stop_price=stop_loss,
    )
    
    # Add take profit
    tp_order = await suite.orders.add_take_profit(
        contract_id=suite.instrument_id,
        limit_price=take_profit,
    )
    
    return {
        "entry_id": entry.orderId,
        "sl_id": sl_order.orderId if sl_order else None,
        "tp_id": tp_order.orderId if tp_order else None,
    }
```

---

## References
- ProjectX API Docs: https://gateway.docs.projectx.com/docs/api-reference/order/order-place/
- TopStepX Brackets: https://help.topstepx.com/settings/risk-settings/auto-oco-brackets
- SDK Trading API: https://project-x-py.readthedocs.io/en/stable/api/trading.html
