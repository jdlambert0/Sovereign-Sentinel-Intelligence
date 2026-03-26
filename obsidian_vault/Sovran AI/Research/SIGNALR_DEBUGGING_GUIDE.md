# Real-Time Data: Debugging Guide

**Date**: 2026-03-19  
**Source**: Multi-LLM Investigation  
**Status**: Ready to Test

---

## Key Insights from LLM Investigation

### 1. Core Problem (Timing Issue)

> "The server accepts your valid JWT handshake but immediately closes (type 7 message) because subscriptions aren't sent fast enough post-handshake—the server expects them within ~1s."

**Solution**: Subscribe to events IMMEDIATELY in `on_open()` callback, before any other logic.

### 2. SDKs Delay Subscriptions

The ProjectX SDKs (Python, Node) delay subscriptions, causing the server to close the connection.  
**Fix**: Use raw SignalR (`signalrcore` or `@microsoft/signalr`) directly, not SDK wrappers.

### 3. The 401 Is the Real Signal

All our configuration changes were adding noise. The **first configuration** that matters is:
```
https:// + skipNegotiation:false → 401 Unauthorized
```

This 401 is what we need to debug. Everything else is secondary.

### 4. Token Delivery Method

| Transport | Token Delivery |
|----------|---------------|
| REST | `Authorization: Bearer <token>` |
| SignalR | `accessTokenFactory` (injects into negotiate + WebSocket) |

**Must use `accessTokenFactory`** - headers alone won't work for SignalR.

---

## Tested Configurations (What We Tried)

| Config | Result | Notes |
|--------|--------|-------|
| `https://` + `skipNegotiation:false` | ❌ 401 Unauthorized | Token not being sent correctly |
| `https://` + `skipNegotiation:true` | ❌ "Negotiation required" | Library requires negotiation |
| `https://` + `skipNegotiation:true` + `transport:WebSockets` | ❌ "WebSocket endpoint not found" | Skip negotiation broken |
| `wss://` + `skipNegotiation:true` | ❌ "Cannot resolve DNS" | SignalR library issue |
| Python SDK | ❌ WebSocket error | SDK delays subscriptions |

---

## Solutions to Try

### Solution 1: Raw SignalR with Immediate Subscription

Use `signalrcore` (Python) or `@microsoft/signalr` (Node.js) directly with IMMEDIATE subscription in `on_open()`.

#### Python (signalrcore)

```python
from signalrcore.hub_connection_builder import HubConnectionBuilder
import asyncio

async def main():
    token = "YOUR_JWT_HERE"  # Valid 24h token
    
    builder = HubConnectionBuilder() \
        .with_url("wss://rtc.topstepx.com/hubs/market", options={
            "skip_negotiation": True,
            "access_token_factory": lambda: token
        })
    connection = builder.build()
    
    @connection.on_open
    async def on_open():
        # IMMEDIATELY subscribe - before any other logic!
        await connection.invoke("SubscribeQuotes", ["ESZ25"])
    
    await connection.start()
    await asyncio.sleep(3600)

asyncio.run(main())
```

#### Node.js (@microsoft/signalr)

```javascript
import * as signalR from "@microsoft/signalr";

const token = "YOUR_JWT_HERE";

const connection = new signalR.HubConnectionBuilder()
  .withUrl("https://rtc.topstepx.com/hubs/market", {
    accessTokenFactory: () => token,
    skipNegotiation: false,  // Let it negotiate
  })
  .withAutomaticReconnect([0, 1000, 5000])
  .configureLogging(signalR.LogLevel.Information)
  .build();

// Subscribe IMMEDIATELY on open
connection.onopen(() => {
  console.log("Connected - subscribing now!");
  connection.invoke("SubscribeQuotes", "CON.F.US.MNQ.M26");
});

connection.onclose(err => {
  console.error("Connection closed", err);
});

connection.onerror(err => {
  console.error("Connection error", err);
});

await connection.start();
```

### Solution 2: Debug with Curl (Negotiate Test)

Test the `/negotiate` endpoint directly to see exact error:

```bash
# Test user hub negotiate
curl -i -X POST "https://rtc.topstepx.com/hubs/user/negotiate?negotiateVersion=1" \
  -H "Authorization: Bearer YOUR_JWT_HERE"

# Test market hub negotiate  
curl -i -X POST "https://rtc.topstepx.com/hubs/market/negotiate?negotiateVersion=1" \
  -H "Authorization: Bearer YOUR_JWT_HERE"
```

**Expected success response**:
```json
{
  "connectionId": "abc123",
  "availableTransports": [
    { "transport": "WebSockets", "transferFormats": ["Text", "Binary"] }
  ]
}
```

**If 401**: Token/entitlement issue  
**If 404**: Wrong URL/path

### Solution 3: Use accessTokenFactory (Not Query String)

Wrong:
```javascript
const url = `https://rtc.topstepx.com/hubs/market?access_token=${token}`;
```

Correct:
```javascript
.withUrl("https://rtc.topstepx.com/hubs/market", {
  accessTokenFactory: () => token,
  skipNegotiation: false,
})
```

---

## Subscription Sequence (Critical Timing)

1. Start connection
2. **ON OPEN: Subscribe immediately** (within ~1 second!)
3. Add reconnect handler that re-subscribes on recovery

```javascript
// CORRECT - Subscribe on open
connection.onopen = async () => {
  await connection.invoke("SubscribeQuotes", contractId);
  await connection.invoke("SubscribeOrders", accountId);
  await connection.invoke("SubscribePositions", accountId);
};

// Also re-subscribe on reconnect
connection.onreconnected = async () => {
  await connection.invoke("SubscribeQuotes", contractId);
};
```

---

## Questions Answered

### Q: Why wss:// DNS fails in SignalR library?
**A**: SignalR clients expect `https://`, not `wss://`. They call `/negotiate` over HTTP first, then upgrade to WebSocket. Using `wss://` directly confuses internal HTTP logic.

### Q: Why WebSocket endpoint not found?
**A**: Usually wrong path (`/user-hub` vs `/user_hub`, missing prefix, etc.) OR trying to skip negotiation when server requires it.

### Q: Firewall issue?
**A**: Unlikely - REST works, WebSockets to other hosts work, handshake succeeds.

### Q: Token format different for SignalR?
**A**: Same JWT, but **delivery method** differs. REST uses headers, SignalR needs `accessTokenFactory`.

### Q: API subscription tier needed?
**A**: Possible. Check negotiate response body for entitlement errors.

---

## Next Steps

1. **Run curl negotiate tests** to identify exact error
2. **Test Python minimal example** with signalrcore + immediate subscription
3. **Test Node.js minimal example** with accessTokenFactory
4. **Check ProjectX dashboard** for API subscription status
5. **Contact TopStep support** if negotiate returns entitlement error

---

## References

- TradingAgents: https://github.com/TauricResearch/TradingAgents
- ProjectX Docs: https://gateway.docs.projectx.com/docs/realtime
