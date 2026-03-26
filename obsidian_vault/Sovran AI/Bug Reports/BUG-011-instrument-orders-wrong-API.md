# BUG-011: instrument.orders.place_market_order() Wrong API
**Date:** 2026-03-17  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

## Issue
Code was using `instrument.orders.place_market_order()` but should have been using `self.suite.orders.place_market_order()`.

## Root Cause
The code was trying to use the instrument context directly, but the correct API is through the TradingSuite's orders manager.

## Fix Applied
**File:** `sovran_ai.py`  
**Line:** ~1026

Changed:
```python
order_result = await instrument.orders.place_market_order(
    contract_id=contract_id,
    side=side,
    size=contracts,
)
```

To:
```python
order_result = await self.suite.orders.place_market_order(
    contract_id=contract_id,
    side=side,
    size=contracts,
)
```

## Verification
Reference: `vortex/test_trade_with_sl_tp.py` line 62 shows correct usage:
```python
entry_response = await suite.orders.place_market_order(
    contract_id=suite.instrument_id,
    side=1,  # Sell
    size=1,
)
```

---
*Documented: 2026-03-17*
