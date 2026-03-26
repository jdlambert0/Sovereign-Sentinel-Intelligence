# LEARNING_MODE and Sovran Launch Guide

**Date**: 2026-03-18  
**Updated**: 2026-03-18

---

## What is LEARNING_MODE?

`LEARNING_MODE` is a module-level flag in `sovran_ai.py` that, when set to `True`, bypasses safety gates to allow the AI to trade freely and collect learning data.

### Location
```python
# Line 92 in sovran_ai.py
LEARNING_MODE = True  # Override for learning phase - set False to re-enable all gates
```

### What LEARNING_MODE Does

| Gate | Without Learning Mode | With Learning Mode |
|------|----------------------|-------------------|
| Throttle Period | Waits between trades | ✅ Bypassed |
| Consecutive Loss Breaker | Stops after N losses | ✅ Bypassed |
| Stale Data Warning | Warns but continues | ✅ Bypassed |
| **Spread Gate** | **Blocks if spread > 4 ticks** | **✅ NOW BYPASSED** |
| **Micro-Chop Guard** | **Blocks if range < 50 pts** | **✅ NOW BYPASSED** |
| Drawdown Floor | Hard stop | ❌ Hard stop (can't override) |

### Why We Need LEARNING_MODE

The original system had too many gates - the AI would never trade because conditions were never "perfect." LEARNING_MODE lets the AI:
1. Trade even with wide spreads
2. Trade even in "dead" markets
3. Continue after losses
4. Build statistical data for learning

### How to Enable/Disable

```python
# In sovran_ai.py, Line 92:
LEARNING_MODE = True   # Enable learning mode
# or
LEARNING_MODE = False  # Disable - use normal trading rules
```

---

## The ONE Way to Launch Sovran Without Errors

After extensive debugging, there is **ONE reliable method** to start Sovran:

### Step 1: Kill Any Existing Processes

```batch
taskkill /F /IM python.exe
```

### Step 2: Use the VBS Launcher (Silent)

```batch
cd C:\KAI\armada
start_armada.bat
```

Or directly:
```batch
wscript "C:\KAI\armada\StartArmada.vbs"
```

### Why This Works

1. **VBS bypasses console window issues** - The pythonw.exe runs without any visible window
2. **Proper process isolation** - No stdout/stderr interference
3. **Background execution** - Doesn't block your terminal

### Why Other Methods Fail

| Method | Problem |
|--------|---------|
| Direct `python sovran_ai.py` | Unicode encoding errors in console |
| `start "" pythonw.exe` | PID not tracked properly |
| `pythonw.exe` directly | No working directory context |

### Files to Use

| File | Purpose |
|------|---------|
| `start_armada.bat` | **RECOMMENDED** - Uses VBS for silent launch |
| `StartArmada.vbs` | The actual launcher script |
| `stop_sovran.bat` | Graceful shutdown |
| `start_sovran.bat` | Alternative with PID tracking (may have issues) |

### Quick Start Command

```batch
cd C:\KAI\armada
wscript StartArmada.vbs
```

### Verify It's Running

Check the log file:
```batch
type C:\KAI\armada\_logs\sovran_today.log
```

Or check for Python process:
```batch
tasklist | findstr python
```

### Stop Sovran

```batch
cd C:\KAI\armada
stop_sovran.bat
```

Or manually:
```batch
taskkill /F /IM python.exe
```

---

## Common Launch Errors

### Error: "Another instance is already running"

**Cause**: Lock file from crashed/stale process

**Fix**:
```batch
del C:\KAI\armada\sovran_ai.lock
taskkill /F /IM python.exe
```

### Error: UnicodeEncodeError

**Cause**: Emojis in logs can't encode to cp1252

**Fix**: Use VBS launcher (start_armada.bat) - it redirects output properly

### Error: WebSocket errors (WARNING - NOT FATAL)

**Cause**: WebSocket connection may fail, but system continues via REST API

**Fix**: None needed - system operates in REST polling mode (this is normal)

---

## Testing LEARNING_MODE

To verify LEARNING_MODE is working:

```batch
cd C:\KAI\armada
python test_learning_mode_verification.py
```

Look for these log messages:
```
LEARNING MODE: Bypassing SPREAD GATE
LEARNING MODE: Bypassing MICRO-CHOP
```

---

## Summary

1. **LEARNING_MODE** = True allows unrestricted trading for data collection
2. **Launch via VBS**: `wscript StartArmada.vbs` for clean startup
3. **Stop via**: `stop_sovran.bat` or `taskkill /F /IM python.exe`

