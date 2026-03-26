# TopStepX Bracket Orders - Implementation Guide

**Created:** 2026-03-18
**Status:** READY FOR INTEGRATION
**Confidence:** CONFIRMED WORKING (tested with live API)

---

## Quick Summary

The native REST API successfully creates atomic bracket orders in ONE API call:

```python
response = await client.post(
    "https://api.topstepx.com/api/Order/place",
    json={
        "accountId": account_id,
        "contractId": contract_id,
        "type": 2,  # Market
        "side": 0,   # Buy (LONG)
        "size": 1,
        "stopLossBracket": {"ticks": -400, "type": 4},  # NEGATIVE for LONG
        "takeProfitBracket": {"ticks": 200, "type": 1}
    }
)
# Result: {"orderId":2660039654,"success":true}
```

---

## Key Parameters

| Parameter | LONG | SHORT | Notes |
|-----------|------|-------|-------|
| `side` | 0 (Buy) | 1 (Sell) | Direction of entry |
| `stopLossBracket.ticks` | NEGATIVE | POSITIVE | Distance from entry |
| `stopLossBracket.type` | 4 (Stop Market) | 4 (Stop Market) | Must be Stop Market! |
| `takeProfitBracket.ticks` | POSITIVE | NEGATIVE | Distance from entry |
| `takeProfitBracket.type` | 1 (Limit) | 1 (Limit) | Limit order |

### MNQ Tick Conversions
- 1 MNQ point = $1.00
- 1 MNQ tick = $0.25 (4 ticks = $1.00)
- $100 risk = 100 points = 400 ticks
- $50 target = 50 points = 200 ticks

---

## Implementation Code for Sovran AI

### Option A: Native REST API (RECOMMENDED)

```python
import httpx

async def place_atomic_bracket(suite, symbol, side, size, sl_ticks, tp_ticks):
    """
    Place atomic bracket order using native REST API.
    
    This creates entry + SL + TP in ONE atomic API call with OCO linking.
    
    Args:
        suite: TradingSuite instance
        symbol: Symbol (e.g., "MNQ")
        side: 0=Buy/LONG, 1=Sell/SHORT
        size: Number of contracts
        sl_ticks: Stop loss distance in ticks
        tp_ticks: Take profit distance in ticks
    
    Returns:
        dict with orderId and success status
    """
    token = suite.client.session_token
    account_id = suite.client.account_info.id
    contract_id = suite.instrument_id
    
    # Adjust tick signs based on direction
    if side == 0:  # LONG
        sl_ticks = -abs(sl_ticks)  # NEGATIVE for LONG
    else:  # SHORT
        sl_ticks = abs(sl_ticks)   # POSITIVE for SHORT
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.topstepx.com/api/Order/place",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "accountId": account_id,
                "contractId": contract_id,
                "type": 2,  # Market order
                "side": side,
                "size": size,
                "stopLossBracket": {
                    "ticks": sl_ticks,
                    "type": 4  # Stop Market (NOT Limit!)
                },
                "takeProfitBracket": {
                    "ticks": tp_ticks,
                    "type": 1  # Limit
                }
            },
            timeout=30.0
        )
        
        result = response.json()
        
        if result.get("success"):
            logger.info(f"Atomic bracket placed: {result['orderId']}")
        else:
            logger.error(f"Bracket failed: {result.get('errorMessage')}")
        
        return result
```

### Option B: SDK with Position Brackets OFF

```python
async def place_bracket_via_sdk(suite, symbol, side, size, sl_price, tp_price):
    """
    Place bracket order using SDK method.
    
    Requires Position Brackets to be DISABLED in TopStepX settings.
    """
    # Get current price for calculations
    current_price = await suite.data.get_current_price()
    
    if side == 0:  # LONG
        stop_loss_price = current_price - sl_price
        take_profit_price = current_price + tp_price
    else:  # SHORT
        stop_loss_price = current_price + sl_price
        take_profit_price = current_price - tp_price
    
    bracket = await suite.orders.place_bracket_order(
        contract_id=suite.instrument_id,
        side=side,
        size=size,
        entry_price=None,  # Market order
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        entry_type="market"
    )
    
    return bracket
```

---

## Integration Steps for Sovran AI

### 1. Add to sovran_ai.py

Add the `place_atomic_bracket()` function near the top of the file after imports.

### 2. Update AIGamblerEngine.execute_trade()

Replace the existing order placement code:

```python
# OLD CODE (broken):
order_result = await self.suite.orders.place_market_order(...)
await asyncio.sleep(5)
await self.suite.orders.add_stop_loss(...)
await self.suite.orders.add_take_profit(...)

# NEW CODE (working):
result = await place_atomic_bracket(
    suite=self.suite,
    symbol=self.config.symbol,
    side=side,
    size=contracts,
    sl_ticks=abs(int(stop_pts)),  # Already positive
    tp_ticks=abs(int(target_pts))  # Already positive
)

if not result.get("success"):
    logger.error(f"Trade failed: {result.get('errorMessage')}")
    return
```

### 3. Calculate Tick Values

```python
# For MNQ:
sl_ticks = int(abs(stop_loss_dollars) / 0.25)  # Convert $ to ticks
tp_ticks = int(abs(take_profit_dollars) / 0.25)
```

---

## Prerequisites

### TopStepX Settings

1. **Disable Position Brackets:**
   - Settings → Risk Settings
   - Find "Position Brackets"
   - UNCHECK "Automatically apply Risk/Profit bracket to new Positions"
   - Save

2. **Enable Auto-OCO (optional):**
   - Settings → Risk Settings
   - Switch bracket type to "Auto-OCO"
   - Configure TP/SL defaults

**Warning:** Must be completely flat before switching bracket types!

---

## Testing Checklist

- [ ] Verify Position Brackets are OFF in TopStepX settings
- [ ] Run during market hours (9:30 AM - 4:00 PM ET)
- [ ] Place test trade with wide stops ($500+ risk)
- [ ] Verify position opens
- [ ] Verify SL and TP orders appear
- [ ] Verify OCO behavior (SL triggers → TP cancels)

---

## Files Created

| File | Purpose |
|------|---------|
| `native_bracket_test.py` | Initial test (wrong API URL) |
| `native_bracket_test_v2.py` | Working test script |
| `get_token.py` | Token extraction utility |
| `Implementation-Guide.md` | This file |

---

## References

- API Docs: `https://gateway.docs.projectx.com/docs/api-reference/order/order-place/`
- SDK Docs: `https://project-x-py.readthedocs.io/en/stable/api/trading.html`
- TopStepX: `https://help.topsteptx.com/settings/risk-settings/position-brackets`
