# BUG-013: LEARNING_MODE Not Bypassing Spread/Micro-Chop Gates
**Date:** 2026-03-18  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

## Issue
Hunter Alpha never traded despite `LEARNING_MODE = True` being enabled.

## Root Cause
LEARNING_MODE only bypassed:
- Throttle period
- Consecutive loss breaker
- Stale data warnings

It did NOT bypass:
- **Spread Gate** - Blocked if spread > 4 ticks
- **Micro-Chop Guard** - Blocked if session range < 50 pts

## Fix Applied
**File:** `sovran_ai.py`

### Before (Spread Gate):
```python
if self.check_spread_gate():
    if self.mandate_active:
        logger.info("MANDATE ACTIVE: Bypassing SPREAD GATE.")
    else:
        continue
```

### After (Spread Gate):
```python
if self.check_spread_gate():
    if LEARNING_MODE:
        logger.info("LEARNING MODE: Bypassing SPREAD GATE - trading anyway")
    elif self.mandate_active:
        logger.info("MANDATE ACTIVE: Bypassing SPREAD GATE.")
    else:
        continue
```

### Before (Micro-Chop Gate):
```python
if self.check_micro_chop():
    if self.mandate_active:
        logger.info("MANDATE ACTIVE: Bypassing MICRO-CHOP.")
    else:
        logger.info("MICRO-CHOP DETECTED. Market too dead to trade. Waiting...")
        continue
```

### After (Micro-Chop Gate):
```python
if self.check_micro_chop():
    if LEARNING_MODE:
        logger.info("LEARNING MODE: Bypassing MICRO-CHOP - trading anyway")
    elif self.mandate_active:
        logger.info("MANDATE ACTIVE: Bypassing MICRO-CHOP.")
    else:
        logger.info("MICRO-CHOP DETECTED. Market too dead to trade. Waiting...")
        continue
```

## Verification
Check logs for:
- "LEARNING MODE: Bypassing SPREAD GATE"
- "LEARNING MODE: Bypassing MICRO-CHOP"

---

## Complete LEARNING_MODE Behavior

| Gate | LEARNING_MODE | MANDATE_MODE |
|------|---------------|--------------|
| Throttle Period | ✅ Bypassed | ✅ Bypassed |
| Consecutive Loss Breaker | ✅ Bypassed | ✅ Bypassed |
| Stale Data Warning | ✅ Bypassed | ✅ Bypassed |
| **Spread Gate** | **✅ NOW BYPASSED** | ✅ Bypassed |
| **Micro-Chop Guard** | **✅ NOW BYPASSED** | ✅ Bypassed |
| Drawdown Floor | ❌ Hard Stop | ❌ Hard Stop |

---
*Documented: 2026-03-18*
