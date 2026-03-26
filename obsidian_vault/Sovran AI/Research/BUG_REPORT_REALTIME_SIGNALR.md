# Bug Report: Real-Time Data Connection Failure

**Date**: 2026-03-19  
**Severity**: CRITICAL  
**Status**: INVESTIGATING - Server Closes Connections Immediately

## Summary

User hub **negotiate works** (200 OK), but WebSocket connections **close within 60ms**. Both Node.js and Python silently fail to maintain connections.

## Negotiate Test Results

| Hub | Result | Error |
|-----|--------|-------|
| User Hub | ✅ 200 OK | connectionId returned |
| Market Hub | ❌ 401 | "signature key not found" |

## Connection Test Results

| Method | Result | Details |
|--------|--------|---------|
| Node.js (`@microsoft/signalr`) | ❌ Closes in 38-60ms | Server sends close frame |
| Python (`signalrcore`) | ❌ Silent failure | No callbacks fired |

## Timeline of Connection

```
[17:13:00.565] WebSocket connected to wss://...
[17:13:00.566] Using HubProtocol 'json'
[17:13:00.623] Close message received from server
[17:13:00.623] Connection disconnected
```

**Server closes in 58ms** - before subscriptions can be sent!

## Working Config (Negotiate)

```bash
# User hub negotiate WORKS
curl -i -X POST "https://rtc.topstepx.com/hubs/user/negotiate?negotiateVersion=1" \
  -H "Authorization: Bearer <JWT>"
```

Response:
```json
{"negotiateVersion":1,"connectionId":"xxx","availableTransports":[{"transport":"WebSockets","transferFormats":["Text","Binary"]}]}
```

## Failed Config (Market Hub)

```bash
# Market hub negotiate FAILS
curl -i -X POST "https://rtc.topstepx.com/hubs/market/negotiate?negotiateVersion=1" \
  -H "Authorization: Bearer <JWT>"
```

Response:
```
401 Unauthorized
WWW-Authenticate: Bearer error="invalid_token", error_description="The signature key was not found"
```

## Root Causes

1. **Market Hub**: Different authentication - "signature key not found"
2. **User Hub**: Server closes connection before subscriptions can be sent (~60ms window)

## What We Tried

- ✅ Negotiate (user hub works)
- ✅ WebSocket connect (opens but immediately closes)
- ❌ Subscribe (too slow - server closes first)
- ❌ Market hub (auth fails)

## Next Steps

1. Contact TopStepX support with negotiate logs
2. Ask about market hub authentication requirements
3. Ask about subscription requirements for real-time data

## References

- `SIGNALR_DEBUGGING_GUIDE.md` - Full debugging steps
- ProjectX Real-Time Docs: https://gateway.docs.projectx.com/docs/realtime
