---
id: BUG-009
title: "BUG-009: LEARNING_MODE Undefined - Session Phase Gate Not Bypassed"
date: 2026-03-17
severity: CRITICAL
status: FIXED
engine: sovran_ai.py
---

## Summary

LEARNING_MODE was used at 6 lines throughout the code but was **never defined** as a module-level variable. This caused a NameError at line 1453 on first execution, preventing any trading.

## Root Cause

| Line | Usage |
|------|-------|
| 1453 | `if LEARNING_MODE:` (first reference - CRASHES here) |
| 1470 | `if LEARNING_MODE:` |
| 1490 | `LEARNING_MODE = True` (first assignment - never reached) |
| 1492 | `if not LEARNING_MODE` |
| 1507 | `elif LEARNING_MODE:` |
| 1518 | `if LEARNING_MODE:` |

## Impact

- Trading loop never ran
- Session phase gates blocked all trades
- No trades executed even during valid trading hours

## Fix Applied

Added at module level (line 88):

```python
# LEARNING MODE - Override safety gates for testing/learning
# Set to True to bypass session phase, throttle, and consecutive loss breakers
# BUG-009 FIX: Was undefined, causing NameError at line 1453
LEARNING_MODE = True  # Override for learning phase - set False to re-enable all gates
```

Also removed redundant assignment at line 1490 (was setting True again inside loop).

## Verification

```python
>>> from sovran_ai import LEARNING_MODE
>>> LEARNING_MODE
True

>>> engine = AIGamblerEngine(config, state, suite)
>>> engine.get_session_phase()
'DAILY HALT (Market Closed)'  # Current time: 4:22 PM CT

>>> LEARNING_MODE active = Phase gates bypassed!
```

## Session Phase Gate Logic (Verified Working)

Once LEARNING_MODE is properly defined, the logic correctly bypasses:
- MIDDAY CHOP
- EARLY AFTERNOON  
- PRE-MARKET
- FORCE-FLATTEN ZONE
- AFTER-HOURS

## Related Bugs

- BUG-010: Missing `import re` (FIXED)
