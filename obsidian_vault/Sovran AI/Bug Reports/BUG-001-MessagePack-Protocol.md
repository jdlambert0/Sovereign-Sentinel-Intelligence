# Bug Report: MessagePack Protocol Handling

## Issue Title
SignalR WebSocket receiving binary data that cannot be parsed - JSONDecodeError

## Severity
MEDIUM - Affects real-time updates, but REST API works for order placement

## Environment
- **Platform**: Windows
- **Python**: 3.12
- **SDK**: project-x-py
- **signalrcore**: Latest

## Description
When connecting to TopStepX WebSocket, the server sends MessagePack (binary) data but the connection fails to parse it properly after initial handshake.

## Root Cause Analysis
1. Server uses JSON for handshake negotiation
2. After successful handshake, server switches to binary MessagePack
3. signalrcore's JSON protocol can't parse binary data
4. This causes JSONDecodeError when receiving market data

## Current Status
**PATCH APPLIED (2026-03-18)** - WebSocket binary MessagePack handling fixed

- REST API: ✅ Primary method, working
- WebSocket: ✅ Patch applied to handle binary frames
- JSONDecodeError: ✅ Fixed via msgpack.unpackb() in websocket_transport.py

## How to Re-apply Fix (if broken)
See: `Bug Reports/WEBSOCKET_FIX_REFERENCE.md`

## Previous Status (for history)
**MITIGATED** - System operated via REST API for all operations:
- REST API works for order placement, SL/TP, positions
- WebSocket provides real-time quotes (nice-to-have)
- System was fully operational without WebSocket

## CORRECTED (2026-03-18): REST API is Primary Method

The earlier framing of "REST fallback" was incorrect. REST API is the **primary reliable method**:

| Method | Purpose | Status |
|--------|---------|--------|
| REST API | Order placement, SL/TP, positions | ✅ Primary |
| WebSocket | Real-time quotes | ⚠️ When available |

## Working Configuration
```python
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.types import HttpTransportType

options={
    "skip_negotiation": False,
    "transport": HttpTransportType.web_sockets,
}
.with_hub_protocol(JsonHubProtocol())
```

## Remaining Issue
- JSONDecodeError when server sends binary market data
- SL/TP bracket orders fail to place because response parsing fails
- Entry orders work fine (using REST API)

## Solution Options
1. **Enable Position Brackets** (Recommended - easiest)
   - Log into TopStepX platform
   - Go to Settings > Risk Settings
   - Configure Position Brackets with default SL/TP
   - Account automatically applies to all positions

2. **Fix signalrcore MessagePack handshake**
   - Patch decode_handshake() to handle binary responses
   - Complex and may break other integrations

3. **REST API for all operations** (Recommended - already working)
   - REST API for order status, positions, account info
   - More reliable, no protocol issues

## Files Affected
- `project_x_py/realtime/connection_management.py` - Protocol configuration
