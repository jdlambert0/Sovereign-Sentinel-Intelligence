# Bug Report: Orders Placed Without Stop Loss / Take Profit

## Issue Title
Market orders placed via API have no risk protection - missing SL/TP brackets

## Severity
CRITICAL - Risk management failure

## Status
**WORKAROUND AVAILABLE** - Enable Position Brackets in TopStepX platform

## Environment
- **Platform**: Windows
- **Python**: 3.12
- **SDK**: project-x-py
- **Account**: TopStepX Simulated Trading Combine ($91,926 balance)

## Root Cause
When placing bracket orders via SDK:
1. Entry order places successfully via REST API
2. WebSocket sends binary response for SL/TP placement
3. JSON protocol can't parse binary → JSONDecodeError
4. SL/TP orders fail to place

## Current Position
- **Contract**: MNQ (CON.F.US.MNQ.M26)
- **Size**: 6 lots  
- **Entry**: $24,898.625
- **No SL/TP attached** (vulnerable!)

## Solutions

### Option 1: Enable Position Brackets (RECOMMENDED)
Log into TopStepX platform:
1. Settings > Risk Settings
2. Configure Position Brackets:
   - Risk: $25-50 per trade
   - Profit: $25-50 per trade
3. Enable "Automatically apply Risk/Profit bracket to new Positions"
4. Account-level setting - applies to ALL orders automatically

### Option 2: Use REST API for Bracket Orders
The SDK does support bracket orders via REST API:
```python
bracket = await suite.orders.place_bracket_order(
    contract_id=suite.instrument_id,
    side=0,  # Buy
    size=1,
    entry_price=current_price,
    stop_loss_price=current_price - 40,
    take_profit_price=current_price + 40,
    entry_type="market",
)
```
Currently fails due to WebSocket issue - needs fix from BUG-001

### Option 3: Add SL/TP After Fill
```python
await suite.orders.add_stop_loss_to_position(
    contract_id=contract_id,
    stop_loss_price=price,
    take_profit_price=target,
)
```

## Impact Assessment
- **Current Risk**: 6 contracts ($24,898) exposed with no stop loss
- **Without SL**: Single adverse move could lose significant capital
- **Action Required**: Enable Position Brackets immediately

## Files Affected
- Trading order placement code
- sovran_ai.py trading logic

## Priority
**CRITICAL** - Must enable Position Brackets before next trade
