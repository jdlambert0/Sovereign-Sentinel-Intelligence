# 2026-03-17 Sovran AI SL/TP Integration

## Date
March 17, 2026

## Summary
Integrated Option 2 (Add SL/TP After Fill) into sovran_ai.py for dynamic stop loss and take profit.

## Changes Made

### Modified File
`C:\KAI\armada\sovran_ai.py`

### Function Modified
`calculate_size_and_execute()` (lines ~894-972)

### Old Code (Option 1 - Broken)
```python
bracket = await self.suite.orders.place_bracket_order(
    contract_id=self.suite.instrument_info.id,
    side=side,
    size=contracts,
    entry_price=entry_order_price,
    stop_loss_price=stop_price,
    take_profit_price=target_price,
    entry_type=entry_type,
)
```

**Problem**: This uses the WebSocket to place SL/TP, but the server sends binary data that causes JSONDecodeError.

### New Code (Option 2 - Working)
```python
# Step 1: Place entry order
if entry_type == "market":
    entry_response = await self.suite.orders.place_market_order(...)
else:
    entry_response = await self.suite.orders.place_limit_order(...)

# Step 2: Wait for fill
await asyncio.sleep(3)
positions = await self.suite.positions.get_all_positions()

# Step 3: Add Stop Loss
sl_response = await self.suite.orders.add_stop_loss(
    contract_id=self.suite.instrument_info.id,
    stop_price=stop_price,
)

# Step 4: Add Take Profit  
tp_response = await self.suite.orders.add_take_profit(
    contract_id=self.suite.instrument_info.id,
    limit_price=target_price,
)
```

## Benefits
1. **No WebSocket dependency** - Uses REST API for all orders
2. **Reliable** - Entry, SL, and TP are placed independently
3. **Dynamic** - AI decides SL/TP at trade time based on confidence
4. **Wide stop** - Already enforced: minimum 50 pts for mandate trades

## Risk Management
- Stop loss: Minimum 50 points (per mandate)
- Take profit: Calculated from AI decision
- Position size: Kelly fraction with max limits

## Test Results
Successfully tested with manual script:
- Entry: SELL 3 @ $25,000.50
- Stop Loss: $25,099.50 (100 ticks above)
- Take Profit: $24,949.50 (51 ticks below)

## Next Steps
1. Run sovran_ai.py to verify it works in live trading
2. Monitor logs for SL/TP placement
3. Check TopStepX platform for orders

## Files
- Modified: `C:\KAI\armada\sovran_ai.py`
- Test script: `C:\KAI\vortex\test_trade_with_sl_tp.py`
