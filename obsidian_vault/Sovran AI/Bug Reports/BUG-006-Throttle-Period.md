# 🐛 BUG-006: Throttle Period Blocking Rapid Trading
**Date:** 2026-03-17  
**Severity:** HIGH  
**Status:** ✅ FIXED

---

## Description
After any loss, the system waited 5 minutes before allowing new trades (throttle_period_sec = 300).

## Root Cause
- Line 423 in sovran_ai.py: `self.throttle_period_sec = 300`
- Lines 1450-1456: Throttling check in monitor_loop

## Fix Applied
- Added LEARNING_MODE override at lines ~1453-1456
- When `LEARNING_MODE = True`, throttle is bypassed

## Code Change
```python
# Throttling Check
# MARCH 17 2026: Override throttle in LEARNING MODE to allow rapid trading
time_since_loss = time.time() - self.last_loss_time
if LEARNING_MODE:
    pass  # Don't throttle in learning mode - trade frequently
elif time_since_loss < self.throttle_period_sec:
    logger.info(...)
    continue
```

---
*Fixed: 2026-03-17*
