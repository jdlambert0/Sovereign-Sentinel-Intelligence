# TopStepX Real-Time WebSocket Investigation

## Date: 2026-03-19

## Summary

**Real-time data via WebSocket is WORKING** - Pure Python implementation integrated into sovran_ai.py.

## Key Findings

### 1. signalrcore Library Issues

The signalrcore library has issues connecting to TopStepX WebSocket hubs:

- **Handshake Issue**: The library's patched `evaluate_handshake` was never called because the WebSocket wasn't receiving handshake responses properly
- **Negotiate URL**: The negotiate endpoint works at `https://rtc.topstepx.com/hubs/user/negotiate`
- **Root Cause**: signalrcore's internal message handling doesn't properly process the handshake response from TopStepX

### 2. Pure Python WebSocket Solution (WORKING)

Created `websocket_bridge.py` using raw `websocket-client` library:

```
URL: wss://rtc.topstepx.com/hubs/user?access_token={JWT}
```

**Handshake Protocol:**
```json
{"protocol":"json","version":1}
```
Send as text with record separator `\x1e`

**Handshake Response:**
```json
{}
```
(Empty JSON object = success)

### 3. Subscription Methods (Verified Working)

All subscriptions require **numeric account ID**, not string:

| Method | Arguments | Status |
|--------|-----------|--------|
| SubscribeAccounts | `[]` | ✅ Works |
| SubscribeOrders | `[18410777]` | ✅ Works |
| SubscribePositions | `[18410777]` | ✅ Works |
| SubscribeTrades | `[18410777]` | ✅ Works |

### 4. Event Types Received

| Event | Description | Example |
|-------|-------------|---------|
| GatewayUserOrder | Order updates | `{"action":1,"data":{...}}` |
| GatewayUserTrade | Trade executions | `{"action":0,"data":{...}}` |
| GatewayUserPosition | Position updates | `{"action":1,"data":{...}}` |
| GatewayUserAccount | Account updates | `{"action":1,"data":{...}}` |

### 5. Market Hub Issue

Market hub returns 401 "signature key not found" - this is an **entitlement issue**:

- The JWT token lacks the market data entitlement claim
- Check ProjectX dashboard: API Subscriptions → Real-time Market Data
- This requires a separate API subscription purchase

## Integration Status

### ✅ COMPLETED

**File: `websocket_bridge.py`** - Pure Python WebSocket client

**File: `sovran_ai.py`** - Updated to use websocket_bridge

**File: `test_websocket_bridge_integration.py`** - Integration test

### Test Results

```
2026-03-19 12:55:33 - [WS] WebSocket thread started!
2026-03-19 12:55:34 - Websocket connected
2026-03-19 12:55:34 - [WS] Connected! Sending SignalR handshake...
2026-03-19 12:55:34 - [WS] Subscribing to data streams...
2026-03-19 12:55:34 - [WS] Invocation 1 result: 0  (SubscribeAccounts)
2026-03-19 12:55:34 - [WS] Invocation 2 result: 0  (SubscribeOrders)
2026-03-19 12:55:35 - [WS] Invocation 3 result: 0  (SubscribePositions)
2026-03-19 12:55:35 - [WS] Invocation 4 result: 0  (SubscribeTrades)
2026-03-19 12:55:35 - [WS] All subscriptions sent!
```

**All 4 subscriptions confirmed successful!**

Events will be received when there are actual order/position changes.

## Files Created

| File | Description |
|------|-------------|
| `websocket_bridge.py` | **INTEGRATED** - Pure Python WebSocket client |
| `test_websocket_working.py` | Raw WebSocket test (received live data) |
| `test_websocket_bridge_integration.py` | Integration test |
| `topstep_websocket.py` | Standalone WebSocket client class |

## Recommendations

1. ✅ **Use websocket_bridge.py** - Pure Python, no Node.js sidecar required
2. ✅ **Keep REST API for order placement** - Works fine
3. ✅ **Real-time events via WebSocket** - Ready for order/position updates
4. ❓ **Market data subscription** - Check TopStepX dashboard for entitlement

## Next Steps

1. ✅ Integrate `websocket_bridge.py` into sovran_ai.py - **DONE**
2. ✅ Test connection and subscription - **CONFIRMED WORKING**
3. ⏳ Verify order fills stream during live trading
4. ⏳ Check market hub subscription status
