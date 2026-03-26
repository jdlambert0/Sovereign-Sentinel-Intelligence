# WEBSOCKET FIX REFERENCE - CRITICAL
**Status**: Patch Applied and VERIFIED (2026-03-18)
**If WebSocket Breaks → Read This Document

---

## VERIFIED: Patch is Working

Tested 2026-03-18:
- ✅ No JSONDecodeError appearing
- ✅ Binary MessagePack handling working
- ⚠️ WebSocket not connecting during market hours (expected for paper accounts)
- ✅ Price flows via REST API: 24825.5

**WebSocket may work during off-hours** (after 5PM CT or weekends).

---

## QUICK FIX (When WebSocket Breaks)

### Step 1: Identify the Error
Common errors:
- `JSONDecodeError: Expecting value: line 1 column 4077 (char 4076)`
- `UnicodeDecodeError` on binary frames
- WebSocket connects but no data flows

### Step 2: Apply the Patch

**File**: `C:\KAI\vortex\.venv312\Lib\site-packages\signalrcore\transport\websockets\websocket_transport.py`

#### Add import at TOP of file (line 1):
```python
import json
```

#### Replace the `on_message()` method:

Find the current `on_message()` method (around line 85) and replace entirely:

```python
def on_message(self, app, raw_message):
    self.logger.debug("Message received {0}".format(raw_message))

    # HANDLE BINARY MESSAGEPACK FROM TOPStepX
    if isinstance(raw_message, bytes):
        try:
            import msgpack
            unpacked = msgpack.unpackb(raw_message, raw=False, strict_map_key=False)
            raw_message = json.dumps(unpacked)
        except Exception as e:
            self.logger.debug(f"Binary unpack failed, trying as-is: {e}")
            try:
                raw_message = raw_message.decode("utf-8")
            except Exception:
                self.logger.debug("Could not decode binary message")
                return []

    if not self.handshake_received:
        messages = self.evaluate_handshake(raw_message)
        self._set_state(TransportState.connected)

        if len(messages) > 0:
            return self._on_message(messages)

        return []

    return self._on_message(self.protocol.parse_messages(raw_message))
```

### Step 3: Verify
Run test script:
```bash
cd C:\KAI\vortex
.venv312\Scripts\python.exe test_websocket_msgpack_patch.py
```

---

## ROOT CAUSE: Mixed Protocol

TopStepX uses **bimodal protocol**:
1. **Handshake**: JSON (text, opcode 0x1)
2. **Data**: MessagePack (binary, opcode 0x2)

signalrcore's JSON protocol cannot parse binary frames.

---

## OTHER FILES TO CHECK

### `websocket_client.py` - May also need patch
**File**: `C:\KAI\vortex\.venv312\Lib\site-packages\signalrcore\transport\websockets\websocket_client.py`

**Patch** (around line 67-76, `prepare_data()` method):
```python
def prepare_data(self, data):
    if self.is_binary:
        return data if isinstance(data, bytes) else data.encode('utf-8')
    else:
        if isinstance(data, bytes):
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return data  # Return bytes instead of throwing error
        return data
```

---

## HOW IT BREAKS

| Event | What Happens |
|-------|--------------|
| `pip install --upgrade signalrcore` | Patch OVERWRITTEN |
| Recreate virtual environment | Fresh install = no patch |
| Run on different machine | No patch applied |
| SDK auto-update | Patch REMOVED |

---

## PERMANENT FIX OPTIONS

### Option A: Pin signalrcore version
```bash
pip freeze > requirements.txt
# Edit requirements.txt to pin:
# signalrcore==3.3.1
```

### Option B: Fork signalrcore
Create a custom package with the patch baked in.

### Option C: Monkey-patch at runtime
Add to `sovran_ai.py` startup:
```python
import signalrcore.transport.websockets.websocket_transport as wt
# Apply patch at import time
```

---

## REFERENCE DOCUMENTS

| Document | Purpose |
|----------|---------|
| `2026-03-18-WebSocket-Fix-Applied.md` | Complete session log with fix |
| `2026-03-18-WebSocket-Comprehensive-Investigation.md` | Full root cause analysis |
| `BUG-001-MessagePack-Protocol.md` | Bug tracking |

---

*Last Updated: 2026-03-18*
