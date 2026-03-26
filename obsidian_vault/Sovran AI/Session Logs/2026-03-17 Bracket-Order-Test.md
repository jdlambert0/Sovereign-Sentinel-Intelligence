# 2026-03-17 Live Trading - Bracket Orders Test

## Date
March 17, 2026

## Summary
SUCCESS: TradingSuite connects and places orders! Position opened. SL/TP still problematic due to binary data handling.

## Test Results

### ✅ What Works
1. **Authentication**: Working with API key
2. **HTTP REST API**: Placing orders works
3. **WebSocket Connection**: User hub and Market hub connect successfully with JSON protocol
4. **Order Placement**: Entry orders execute successfully
5. **Position Tracking**: Can see open positions

### Current Position
- **Contract**: MNQ (CON.F.US.MNQ.M26)
- **Size**: 6 lots
- **Entry Price**: $24,898.625

### Issues Remaining

#### Issue 1: JSONDecodeError on Market Data
- **Status**: PARTIALLY FIXED - Connection works, but server sends binary data after handshake
- **Error**: `JSONDecodeError: Expecting value: line 1 column 4088 (char 4087)`
- **Cause**: Server sends MessagePack/binary data that JSON protocol can't parse
- **Impact**: SL/TP bracket orders fail to place because response parsing fails

#### Issue 2: Bracket Orders Without SL/TP
- **Status**: CONFIRMED - When WebSocket fails, orders place without SL/TP
- **Previous Order**: 2646279415 - No stop loss or take profit attached

## Technical Details

### Connection Settings That Work
```python
# connection_management.py
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.types import HttpTransportType

options={
    "skip_negotiation": False,
    "transport": HttpTransportType.web_sockets,
}
.with_hub_protocol(JsonHubProtocol())
```

### Root Cause Analysis
1. Server uses JSON for handshake negotiation
2. After successful handshake, server switches to binary MessagePack
3. signalrcore's JSON protocol can't parse binary data
4. This causes JSONDecodeError when receiving market data

### Potential Solutions
1. Use MessagePack for handshake (requires fixing signalrcore's handshake parser)
2. Implement fallback - use REST API for order status when WebSocket fails
3. Enable Position Brackets in TopStepX platform settings (account-level)

## Files Modified
- `C:\KAI\vortex\.venv312\Lib\site-packages\project_x_py\realtime\connection_management.py`
  - Changed to JsonHubProtocol
  - Added HttpTransportType.web_sockets
  - Thread safety for asyncio events (already applied)

## Next Steps
1. Enable Position Brackets in TopStepX platform as workaround
2. Or implement REST API polling for order fills instead of WebSocket
3. Or patch signalrcore to handle binary data after handshake
