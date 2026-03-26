# Plan Mode: SL/TP Fix for Sovran
**Date**: 2026-03-18
**Priority**: CRITICAL

---

## THE PROBLEM

**2026-03-18 8:30am**: Trade was opened with **NO STOP LOSS and NO TAKE PROFIT**.

This is a CRITICAL risk management failure. A trade without SL/TP can:
- Lose unlimited money on a bad move
- Miss profit targets
- Cause emotional trading decisions

---

## IMMEDIATE ACTIONS REQUIRED

### 1. Investigate SL/TP Code (Lines 1020-1100 in sovran_ai.py)

Find and analyze:
```python
# Lines ~1064-1095
# SL/TP bracket code - IS THIS RUNNING?
await engine.add_stop_loss(...)
await engine.add_take_profit(...)
```

### 2. Check Order Response

After placing an order, check:
```python
response = await suite.orders.place_market_order(...)
# Log the ENTIRE response
print(f"ORDER RESPONSE: {response}")
```

### 3. Verify TopStepX Account Settings

1. Log into TopStepX desktop platform
2. Go to Settings → Risk Settings
3. Check if Position Brackets are configured
4. If not, configure default SL/TP there as backup

### 4. Add Debug Logging

Before attempting fix, add logging to:
- `calculate_size_and_execute()`
- `add_stop_loss()` call
- `add_take_profit()` call
- Order response parsing

---

## CODE INVESTIGATION CHECKLIST

- [ ] Read `sovran_ai.py` lines 1020-1100
- [ ] Check if `add_stop_loss()` is actually called
- [ ] Check if `add_take_profit()` is actually called
- [ ] Log order response to see if brackets are accepted
- [ ] Check TopStepX order history for bracket status

---

## TECHNICAL NOTES

### How SL/TP Should Work

1. Place market order
2. Get order ID back
3. Add stop loss with order ID
4. Add take profit with order ID

### Why It Might Fail

1. Order ID not returned correctly
2. `add_stop_loss()` called BEFORE order fills
3. SDK method signature changed
4. WebSocket response parsing fails (BUG-001 related)

### Order Response to Log

```python
response = await suite.orders.place_market_order(...)
logger.info(f"FULL ORDER RESPONSE: {vars(response)}")
```

---

## VERIFICATION TEST

After fix, run:
```batch
wscript "C:\KAI\armada\StartArmada.vbs"
```

Then check:
1. Order history shows brackets attached
2. Position shows SL/TP levels
3. Console shows "SL added" / "TP added" logs

---

## FILES TO REFERENCE

- `C:\KAI\obsidian_vault\Sovran AI\Bug Reports\COMPLETE_BUG_HISTORY.md`
- `C:\KAI\obsidian_vault\Sovran AI\Bug Reports\MASTER_BUG_SUMMARY.md`
- `C:\KAI\obsidian_vault\Sovran AI\Architecture\sovran_ai_FINAL.py`

---

*Plan created: 2026-03-18*
*Ready for execution*
