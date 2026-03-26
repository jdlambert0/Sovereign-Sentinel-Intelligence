# Complete Bug History & Fix Attempts
**Last Updated**: 2026-03-18
**Purpose**: Document every bug, fix attempt, and outcome for future AI sessions

---

## BUG-001: WebSocket MessagePack Protocol
**Severity**: MEDIUM
**Status**: ✅ FIXED (2026-03-18)

### Issue
- JSONDecodeError when receiving market data via WebSocket
- Server sends MessagePack (binary) after JSON handshake
- signalrcore's JSON protocol cannot parse binary data

### Fix Attempts

| Date | Attempt | Result |
|------|---------|--------|
| 03-16 | Patched prepare_data() in websocket_client.py | Partial |
| 03-17 | Tried MessagePackHubProtocol | Failed - broke connection |
| 03-18 | **SUCCESS**: Patched on_message() in websocket_transport.py | ✅ Works |

### Final Fix (2026-03-18)
**File**: `C:\KAI\vortex\.venv312\Lib\site-packages\signalrcore\transport\websockets\websocket_transport.py`

```python
# Lines 85-113 - Added binary MessagePack handling
def on_message(self, app, raw_message):
    # HANDLE BINARY MESSAGEPACK FROM TOPStepX
    if isinstance(raw_message, bytes):
        try:
            import msgpack
            unpacked = msgpack.unpackb(raw_message, raw=False, strict_map_key=False)
            raw_message = json.dumps(unpacked)
        except Exception:
            try:
                raw_message = raw_message.decode("utf-8")
            except Exception:
                return []
    # ... rest of method
```

### Note
- WebSocket still doesn't connect during market hours (paper account limitation)
- REST API works for all operations
- Patch will be overwritten if signalrcore is updated

---

## BUG-002: Missing Stop Loss / Take Profit
**Severity**: CRITICAL
**Status**: ❌ REOCCURRING

### Issue
- Trade placed at 8:30am had NO SL/TP attached
- This is a CRITICAL risk management failure
- Previous fixes may have been overwritten or not working

### Fix Attempts History

| Date | Attempt | Result |
|------|---------|--------|
| 03-16 | Added add_stop_loss/take_profit code | Unknown |
| 03-17 | Account-level Position Brackets recommended | Configured? |
| 03-18 | **Trade still missing SL/TP** | ❌ FAILING |

### Code Location
- `sovran_ai.py` lines ~1064-1095: SL/TP bracket code
- `sovran_ai.py` line 1026: `suite.orders.place_market_order()`

### Investigation Needed
1. Check if `add_stop_loss()` and `add_take_profit()` are being called
2. Verify TopStepX account-level brackets are configured
3. Check order response for errors
4. Add logging to SL/TP code path

---

## BUG-003: Lock File Infinite Loop
**Severity**: HIGH
**Status**: ✅ MITIGATED (Lock disabled)

### Issue
- Bot crashes and restarts infinitely
- Lock file not being cleaned up properly

### Fix
- Lock file mechanism DISABLED in sovran_ai.py
- Line 1846: Lock disabled, can re-enable after debugging

---

## BUG-004: Timezone Miscalculation
**Severity**: LOW
**Status**: ✅ DOCUMENTED

### Issue
- Session times miscalculated due to timezone

### Fix
- Use system time directly
- DST handling in SDK covers edge cases

---

## BUG-005: Last Entry Time Gate
**Severity**: CRITICAL
**Status**: ✅ FIXED

### Issue
- Bot stopped trading before 14:45 (too early)

### Fix
- Line 251: Extended to 15:55
```python
"last_entry_time": "15:55:00"
```

---

## BUG-006: Throttle Period
**Severity**: HIGH
**Status**: ✅ FIXED

### Issue
- Bot waited too long between trades

### Fix
- Line ~1453: LEARNING_MODE override bypasses throttle

---

## BUG-007: Consecutive Loss Breaker
**Severity**: HIGH
**Status**: ✅ FIXED

### Issue
- Bot stopped after consecutive losses

### Fix
- Line ~1510: LEARNING_MODE override bypasses loss breaker

---

## BUG-008: Session Phase Gate
**Severity**: MEDIUM
**Status**: ✅ FIXED

### Issue
- Bot only traded during specific phases

### Fix
- LEARNING_MODE override at line ~1510

---

## BUG-009: LEARNING_MODE Undefined
**Severity**: CRITICAL
**Status**: ✅ FIXED

### Issue
- LEARNING_MODE flag not defined at module level

### Fix
- Line 92: Added `LEARNING_MODE = True`

---

## BUG-010: Missing import re
**Severity**: MEDIUM
**Status**: ✅ FIXED

### Issue
- `import re` missing

### Fix
- Line 54: Added `import re`

---

## BUG-011: instrument.orders Wrong API
**Severity**: CRITICAL
**Status**: ✅ FIXED

### Issue
- Used `instrument.orders` instead of `suite.orders`

### Fix
- Line 1026: Changed to `suite.orders.place_market_order()`

---

## BUG-012: Missing SL/TP Brackets
**Severity**: CRITICAL
**Status**: ❌ REOPENED (See BUG-002)

### Issue
- SL/TP not attached to orders

### Fix
- Lines ~1064-1095: Added bracket code
- Still not working - needs investigation

---

## BUG-013: Spread/Micro-Chop Gates
**Severity**: HIGH
**Status**: ✅ FIXED

### Issue
- LEARNING_MODE didn't bypass Spread Gate or Micro-Chop Guard

### Fix
- Lines ~1529-1537: Added Spread Gate bypass
- Lines ~1567-1575: Added Micro-Chop Guard bypass

---

## COMMAND WINDOWS ISSUE (2026-03-18)

**Severity**: LOW (UX)
**Status**: ✅ IDENTIFIED

### Issue
- PowerShell commands spawn visible windows
- User sees flickering command windows

### Root Cause
- Running `python.exe` directly instead of `pythonw.exe`
- Using `Start-Process` without `-WindowStyle Hidden`

### Fix (for future sessions)
**ALWAYS use**:
```batch
wscript "C:\KAI\armada\StartArmada.vbs"
```

**NEVER** use:
- `python.exe` in PowerShell
- Interactive Python

---

## FILES TO CHECK FOR SL/TP BUG

1. `C:\KAI\armada\sovran_ai.py` lines 1020-1100
2. `C:\KAI\obsidian_vault\Sovran AI\Architecture\sovran_ai_FINAL.py`
3. TopStepX account settings (Position Brackets)

---

*Document: 2026-03-18*
*Next: Investigate SL/TP failure (BUG-002)*
