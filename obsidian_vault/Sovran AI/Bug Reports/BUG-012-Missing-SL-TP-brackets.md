# BUG-012: Missing SL/TP Bracket Code After Position Fill
**Date:** 2026-03-17  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

## Issue
After a position was filled, the code was NOT adding stop loss and take profit brackets.

## Root Cause
The `calculate_size_and_execute()` method was placing the market order but never calling `add_stop_loss()` or `add_take_profit()` after position fill.

## Fix Applied
**File:** `sovran_ai.py`  
**Lines:** ~1064-1095

Added code after position is detected as filled:
```python
# Add SL/TP brackets after position fills
try:
    logger.info(f"Adding STOP LOSS @ ${stop_price}...")
    sl_response = await self.suite.orders.add_stop_loss(
        contract_id=self.suite.instrument_id,
        stop_price=stop_price,
    )
    if sl_response and sl_response.success:
        logger.info(f"  ✅ SL placed: {sl_response.orderId}")
    else:
        logger.warning(f"  ⚠️ SL failed: {sl_response}")
except Exception as sl_err:
    logger.error(f"  SL error: {sl_err}")

try:
    logger.info(f"Adding TAKE PROFIT @ ${target_price}...")
    tp_response = await self.suite.orders.add_take_profit(
        contract_id=self.suite.instrument_id,
        stop_price=target_price,
    )
    if tp_response and tp_response.success:
        logger.info(f"  ✅ TP placed: {tp_response.orderId}")
    else:
        logger.warning(f"  ⚠️ TP failed: {tp_response}")
except Exception as tp_err:
    logger.error(f"  TP error: {tp_err}")
```

## Reference
Working implementation in `vortex/test_trade_with_sl_tp.py` lines 91-112

---
*Documented: 2026-03-17*
