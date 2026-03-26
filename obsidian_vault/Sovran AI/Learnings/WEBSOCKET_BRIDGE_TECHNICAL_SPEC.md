# WEBSOCKET BRIDGE - COMPLETE TECHNICAL SPECIFICATION
## Date: 2026-03-19 | Status: ✅ WORKING - REAL-TIME DATA CONFIRMED

---

## Executive Summary

**Problem**: signalrcore library fails to complete SignalR handshake with TopStepX WebSocket hubs, causing 60ms disconnects.

**Solution**: Pure Python WebSocket implementation using `websocket-client` library.

**Status**: ✅ INTEGRATED into sovran_ai.py | ✅ VERIFIED - Real-time data flowing

---

## Test Results (2026-03-19 13:11 UTC)

```
[WS] Connected! Sending SignalR handshake...
[WS] Subscribing to data streams...
[WS] Invocation 1 result: 0  (SubscribeAccounts)
[WS] Invocation 2 result: 0  (SubscribeOrders)
[WS] Invocation 3 result: 0  (SubscribePositions)
[WS] Invocation 4 result: 0  (SubscribeTrades)
[WS] All subscriptions sent!

--- TRADE PLACED ---
Trade placed: Order ID 2669189964

[WS] EVENT GatewayUserOrder: BUY #2669189964 status=6 (Working)
[WS] EVENT GatewayUserOrder: #2669189964 status=2 (Filled!) price=24466.5
[WS] EVENT GatewayUserTrade: Filled @ $24466.5 side=BUY
[WS] EVENT GatewayUserPosition: Size=12 avg=$24445.23
[WS] EVENT GatewayUserAccount: Balance=$88115.08

Final: Orders=6, Trades=2, Events=14
```

**CONFIRMED: Real-time data flowing with < 1 second latency!**

---

## Root Cause Analysis

### Why signalrcore Failed

1. **Handshake Not Received**: The `evaluate_handshake()` method was never called because signalrcore's WebSocket transport didn't properly receive the handshake response.

2. **Negotiate URL Mismatch**: 
   - signalrcore builds negotiate URL from `wss://rtc.topstepx.com/hubs/user`
   - Converts to HTTP: `https://api.topstepx.com/hubs/user/negotiate`
   - **Correct URL**: `https://rtc.topstepx.com/hubs/user/negotiate`

3. **Message Handling**: signalrcore expects specific message formats that TopStepX doesn't send exactly.

### Why Raw WebSocket Works

1. **Direct Connection**: Bypasses negotiation phase
2. **Manual Handshake**: Sends `{"protocol":"json","version":1}\x1e` directly
3. **Simple Message Parsing**: Handles raw SignalR messages correctly

---

## Protocol Details

### SignalR Message Format

```
{JSON}\x1e
```

The record separator (`\x1e`, hex `0x1E`) terminates each message.

### Handshake

**Client → Server:**
```json
{"protocol":"json","version":1}
```
Send as text with record separator.

**Server → Client:**
```json
{}
```
Empty JSON object = handshake successful.

### Invocation Messages

**Client → Server (Type 1):**
```json
{
  "type": 1,
  "target": "SubscribeOrders",
  "arguments": [18410777],
  "invocationId": "1"
}
```

**Server → Client (Type 3 - Completion):**
```json
{
  "type": 3,
  "invocationId": "1",
  "result": 0
}
```
`result: 0` = success.

### Event Messages

**Server → Client (Type 1 with target):**
```json
{
  "type": 1,
  "target": "GatewayUserOrder",
  "arguments": [{"action": 1, "data": {...}}]
}
```

### Message Types

| Type | Name | Direction | Purpose |
|------|------|-----------|---------|
| 1 | Invocation | Both | Method calls and event dispatches |
| 2 | StreamItem | S→C | Stream data |
| 3 | Completion | S→C | Invocation response |
| 4 | StreamInvocation | C→S | Stream subscription |
| 5 | CancelInvocation | C→S | Cancel stream |
| 6 | Ping | Both | Keep-alive |
| 7 | Close | S→C | Close connection |

---

## Subscription Methods

### Account ID Requirement

**CRITICAL**: Account ID must be a **number**, not a string.

```python
# WRONG
SubscribeOrders(["18410777"])  # String - will fail

# CORRECT
SubscribeOrders([18410777])  # Number - works
```

### All Subscriptions

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `SubscribeAccounts` | `[]` | `{"result": 0}` | Account updates |
| `SubscribeOrders` | `[accountId]` | `{"result": 0}` | Order updates |
| `SubscribePositions` | `[accountId]` | `{"result": 0}` | Position updates |
| `SubscribeTrades` | `[accountId]` | `{"result": 0}` | Trade executions |

---

## Event Payloads

### GatewayUserOrder

```json
{
  "type": 1,
  "target": "GatewayUserOrder",
  "arguments": [{
    "action": 1,
    "data": {
      "id": 2669189964,
      "accountId": 18410777,
      "contractId": "CON.F.US.MNQ.M26",
      "symbolId": "F.US.MNQ",
      "status": 6,
      "type": 2,
      "side": 0,
      "size": 1,
      "filledPrice": 24466.5,
      "fillVolume": 1
    }
  }]
}
```

**Action Values:**
- `0` = Removed
- `1` = Added/Updated

**Status Values:**
- `1` = Pending
- `2` = PartiallyFilled/Filled
- `3` = Filled
- `4` = Cancelled
- `6` = Working (has SL/TP)
- `8` = Attached (SL/TP bracket)

### GatewayUserTrade

```json
{
  "type": 1,
  "target": "GatewayUserTrade",
  "arguments": [{
    "action": 0,
    "data": {
      "id": 2314563086,
      "accountId": 18410777,
      "price": 24466.5,
      "fees": 0.37,
      "side": 0,
      "size": 1,
      "orderId": 2669189964
    }
  }]
}
```

### GatewayUserPosition

```json
{
  "type": 1,
  "target": "GatewayUserPosition",
  "arguments": [{
    "action": 1,
    "data": {
      "id": 636628522,
      "accountId": 18410777,
      "contractDisplayName": "MNQM26",
      "type": 1,
      "size": 12,
      "averagePrice": 24445.23
    }
  }]
}
```

### GatewayUserAccount

```json
{
  "type": 1,
  "target": "GatewayUserAccount",
  "arguments": [{
    "action": 1,
    "data": {
      "id": 18410777,
      "name": "150KTC-V2-423406-16429504",
      "balance": 88115.08,
      "canTrade": true
    }
  }]
}
```

---

## Implementation

### websocket_bridge.py

**Location**: `C:\KAI\armada\websocket_bridge.py`

**Key Classes:**
- `TopStepWebSocketBridge` - Main WebSocket client
- `initialize_websocket_bridge()` - Factory function

**Usage:**
```python
from websocket_bridge import initialize_websocket_bridge

bridge = await initialize_websocket_bridge(
    engine=engine,
    contract_id="CON.F.US.MNQ.M26",
    api_key="YOUR_API_KEY",
    username="YOUR_USERNAME",
    auto_start=True
)
```

### Engine Handlers

The bridge dispatches events to engine methods:

```python
async def handle_realtime_order(self, data: dict):
    """Called on GatewayUserOrder events"""
    pass

async def handle_realtime_trade(self, data: dict):
    """Called on GatewayUserTrade events"""
    pass

async def handle_realtime_position(self, data: dict):
    """Called on GatewayUserPosition events"""
    pass

async def handle_realtime_account(self, data: dict):
    """Called on GatewayUserAccount events"""
    pass
```

---

## sovran_ai.py Integration

**Line ~2034:**
```python
# REAL-TIME DATA BRIDGE: Pure Python WebSocket (no Node.js sidecar!)
from websocket_bridge import initialize_websocket_bridge

bridge = await initialize_websocket_bridge(
    engine=engine,
    contract_id=contract_id,
    api_key=api_key,
    username=username,
    auto_start=True,
)

if bridge:
    engine._realtime_bridge = bridge
```

---

## Market Hub Status

**Issue**: Market hub returns `401 "signature key not found"`

**Cause**: Missing market data entitlement in JWT token

**Solution**: Check ProjectX dashboard → API Subscriptions → Real-time Market Data

**Same pattern works once entitlement is added:**
```
wss://rtc.topstepx.com/hubs/market?access_token={JWT}
```

---

## Dependencies

```
websocket-client>=1.9.0
```

Automatically installed if not present:
```python
try:
    import websocket
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "websocket-client"])
    import websocket
```

---

## Test Files

| File | Purpose |
|------|---------|
| `test_simple.py` | Basic 2-minute stability test |
| `test_trade_ws.py` | Live trade + WebSocket verification |
| `test_websocket_bridge_integration.py` | Full integration test |

---

## Checklist

- [x] Create pure Python WebSocket bridge
- [x] Integrate into sovran_ai.py
- [x] Verify connection stays open (2+ minutes)
- [x] Verify real-time data flows during trades
- [ ] Check market hub subscription entitlement
- [ ] Implement engine handlers for real-time events
