---
title: TopStepX WebSocket Research and Fix
date: 2026-03-19
tags: [websocket, realtime, topstepx, critical, fixed]
status: fix-applied
---

# TopStepX WebSocket Research and Fix

**Date:** 2026-03-19
**Status:** Fix Applied - Testing Required
**Priority:** CRITICAL

---

## Executive Summary

The Node.js sidecar cannot connect to TopStepX WebSocket/SignalR due to URL format. This document contains research findings, the fix applied, and testing procedures.

---

## Problem Description

### Symptoms

```
Error: Cannot resolve 'wss://rtc.topstepx.com/hubs/market'.
```

```
Sidecar status:
curl http://localhost:8765/connection
{"connected":false,"subscribedContracts":[]}
```

### Impact

- **No real-time market data** reaching the trading system
- AI trading blind with stale REST polling data
- Cannot capture L2 order flow, VPIN, OFI in real-time

---

## Research Findings

### DNS Check (PASSED)

```
DNS lookup: 35.71.158.18 ✓
Ping: 16ms TTL=244 ✓
```

### HTTP/REST Check (PASSED)

```
REST API: Working ✓
Order placement: Working ✓
Authentication: Working ✓
```

### WebSocket Check (FAILED)

```
SignalR Connection: FAILED ✗
Error: Cannot resolve 'wss://rtc.topstepx.com/hubs/market'
```

### Root Cause

The Microsoft SignalR library (`@microsoft/signalr`) has strict URL validation in `HttpConnection._resolveUrl()`.

| URL Format | Result |
|------------|--------|
| `wss://rtc.topstepx.com/hubs/market` | ❌ FAILED |
| `https://rtc.topstepx.com/hubs/market` | ⏳ TEST |

**Hypothesis:** SignalR expects HTTPS base URL and auto-upgrades to WebSocket. Direct `wss://` is rejected by the library's validation.

---

## The Fix

### File: `C:\KAI\armada\topstep_sidecar\src\signalr-manager.js`

### Change (Line 3-4)

```javascript
// BEFORE (FAILS):
const MARKET_HUB_URL = 'wss://rtc.topstepx.com/hubs/market';
const USER_HUB_URL = 'wss://rtc.topstepx.com/hubs/user';

// AFTER (APPLIED):
const MARKET_HUB_URL = 'https://rtc.topstepx.com/hubs/market';
const USER_HUB_URL = 'https://rtc.topstepx.com/hubs/user';
```

### Rationale

The `@microsoft/signalr` library expects an HTTP(S) URL and handles WebSocket upgrade internally. By passing `https://`, the library will:
1. Use HTTPS for the HTTP handshake
2. Automatically upgrade to WSS for real-time transport

---

## Implementation

### Step 1: Apply Fix

```bash
# Edit signalr-manager.js line 3-4
# Change wss:// to https://
```

### Step 2: Restart Sidecar

```bash
# Kill existing sidecar
taskkill //F //IM node.exe

# Restart sidecar
cd /c/KAI/armada/topstep_sidecar
node src/index.js
```

### Step 3: Authenticate and Connect

```bash
# Get JWT token from TopStepX
curl -X POST https://api.topstepx.com/api/Auth/loginKey \
  -H "Content-Type: application/json" \
  -d '{"userName":"jessedavidlambert@gmail.com","apiKey":"YOUR_API_KEY"}'

# Send to sidecar (if endpoint exists)
curl -X POST http://localhost:8765/auth \
  -H "Content-Type: application/json" \
  -d '{"token":"JWT_TOKEN"}'

# Trigger connection
curl -X POST http://localhost:8765/connect
```

### Step 4: Verify Connection

```bash
# Check connection status
curl http://localhost:8765/connection

# Expected: {"connected":true,"subscribedContracts":["CON.F.US.MNQ.M26"]}
```

---

## Testing Procedures

### Test 1: Basic Connection

```bash
curl http://localhost:8765/health
```

Expected: `{"status":"ok",...}`

### Test 2: Quote Data

```bash
curl http://localhost:8765/quotes
```

Expected: `{"quotes":{"CON.F.US.MNQ.M26":{"lastPrice":...}}}`

### Test 3: Harness Integration

Start harness and verify:
1. `HUNTER ALPHA HARNESS READY`
2. Realtime bridge connected: `[OK] Realtime bridge connected!`
3. Live price updates in engine

---

## Alternative Approaches (If Fix Fails)

### Option A: HTTP Long-Polling Fallback

SignalR supports HTTP long-polling as fallback:

```javascript
.withUrl(HUB_URL, {
  transport: HttpTransportType.LongPolling,
  skipNegotiation: false
})
```

### Option B: Contact TopStepX Support

If WebSocket doesn't work, contact TopStepX:
- Ask about API/WebSocket access for Trading Combine accounts
- Verify no firewall/network issues
- Ask about connection timing (market hours vs off-hours)

### Option C: Continue with REST Polling

If all else fails, REST polling works:
- Add retry logic with exponential backoff
- Poll every 1-2 seconds for quotes
- Accept higher latency

---

## Architecture: Desired State

```
┌─────────────────────────────────────────────────────────────────┐
│                      TOPSTEPX                                   │
│                                                                  │
│   ┌─────────────┐         ┌─────────────────────────────────┐  │
│   │  Market    │         │  User Hub                       │  │
│   │  (wss://) │◄────────│  (wss://)                       │  │
│   └─────────────┘         └─────────────────────────────────┘  │
│         │                           │                            │
│         │    HTTPS + Auto-upgrade │                            │
│         └─────────────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NODE.JS SIDECAR                               │
│                                                                  │
│   SignalR Manager ───► HTTP Server (port 8765)                  │
│         │                          │                             │
│         │                  ┌─────┴─────┐                      │
│         │                  │ Quotes     │                       │
│         │                  │ Trades    │                       │
│         │                  │ Positions │                       │
│         │                  └───────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PYTHON (HARNESS)                             │
│                                                                  │
│   RealtimeDataBridge ──► Engine ──► Groq Decision ──► Trade      │
│         │                     │                                   │
│         │              Real-time data                           │
│         │              for AI decisions                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Success Criteria

| Metric | Target | Current |
|--------|--------|---------|
| Sidecar connected | `true` | `false` |
| Quote latency | < 100ms | N/A |
| Real-time VPIN/OFI | Available | No |
| Harness realtime flag | `true` | `false` |

---

## Related Documents

- [[sovran_ai_FINAL.py]]
- [[websocket_transport_PATCHED.py]]
- [[System Architecture]]

---

## Updates

### 2026-03-19 16:30 UTC
- Fix applied: Changed `wss://` to `https://` in signalr-manager.js
- Testing in progress

---

*Document created: 2026-03-19*
