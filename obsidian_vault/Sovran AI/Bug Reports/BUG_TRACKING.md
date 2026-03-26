# Sovran AI - Bug Tracking

## Active Bugs

### BUG-001: SL/TP Orders Not Appearing as Brackets
- **Status**: ✅ FIXED
- **Severity**: Critical
- **Date**: 2026-03-17
- **Issue**: Orders placed as separate orders, not brackets
- **Root Cause**: SL/TP added AFTER entry fill, not WITH entry
- **Fix**: Use REST API with stopLossBracket/takeProfitBracket parameters

### BUG-002: Position Brackets vs Auto OCO Conflict
- **Status**: ✅ FIXED  
- **Severity**: High
- **Date**: 2026-03-17
- **Issue**: API returned "Brackets cannot be used with Position Brackets"
- **Fix**: User enabled Auto OCO brackets in TopStepX platform

### BUG-003: Invalid Tick Signs for Short Trades
- **Status**: ✅ FIXED
- **Severity**: High
- **Date**: 2026-03-17
- **Issue**: "Invalid take profit ticks (30). Ticks should be less than zero when going short"
- **Fix**: Use negative ticks for take profit on short positions

### BUG-004: Intelligent Trade Management Not Implemented
- **Status**: ✅ FIXED
- **Severity**: Medium
- **Date**: 2026-03-17
- **Issue**: Sovran just waits for SL/TP to hit
- **Fix Applied**:
  - Added `intelligent_trade_management()` function
  - Trailing stop logic (moves SL to breakeven after X ticks)
  - Added to monitor_loop
  - Dynamic params from Obsidian

### BUG-005: Memory System Limited
- **Status**: ✅ FIXED
- **Severity**: Medium
- **Date**: 2026-03-17
- **Issue**: Basic JSON memory, no Obsidian integration
- **Fix Applied**:
  - Created learning_system.py module
  - Trades saved to Obsidian on open/close
  - Research loop triggers after every 10 trades
  - Dynamic tick parameters from Obsidian

---

## New Features Implemented (March 17, 2026)

### 1. Obsidian Integration
- ✅ Trades saved to `Sovran AI/Trades/` folder
- ✅ Performance stats tracked
- ✅ Config stored in `Sovran AI/Config/`

### 2. Research Loop
- ✅ Triggers after every 10 trades
- ✅ Researches probability, Kelly criterion
- ✅ Dynamic topics based on performance

### 3. Dynamic Tick Management
- ✅ Reads params from Obsidian
- ✅ Can adjust trailing stop, scale out, initial SL
- ✅ Stored in `Config/intelligent_management.md`

---

## Latest Trade (March 17, 2026)
- **Order ID**: 2649679298
- **Position**: SELL 1 @ $25044.25
- **Stop Loss**: BUY @ $25119.25 (300 ticks = $600)
- **Take Profit**: BUY @ $25006.75 (150 ticks = $300)
- **Status**: Saved to Obsidian ✅
