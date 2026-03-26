---
title: GROQ Trading Context
date: 2026-03-19
tags: [hunter-alpha, context, active, openrouter, signalr]
status: in-progress
---

# Hunter Alpha — Groq Trading Context

**Last Updated:** 2026-03-19 15:17:00 UTC
**Total Trades:** 12
**Session:** NEW SESSION NEEDED
**Teacher:** KAI (Big Pickle)

---

## 🔴 REAL-TIME DATA: BLOCKED (17:15 UTC)

### What WORKS
- REST API: Auth, accounts, orders ✅
- User Hub negotiate: 200 OK, connectionId ✅
- WebSocket connect: Opens successfully ✅

### What FAILS
- **User Hub**: Server closes in 58ms (before subscriptions)
- **Market Hub**: 401 "signature key not found"

### Timeline
```
[17:13:00.565] WebSocket connected
[17:13:00.623] Server sends Close frame (58ms later)
Connection closed
```

### Root Cause
Server closes connections within 60ms window - subscription too slow.

### Next Steps
1. Investigate 60ms close behavior
2. Market hub auth needs different token
3. Consider contacting TopStepX support

---

## Current Model Configuration

### OpenRouter + Hunter Alpha (2026-03-19)
```
Provider: OpenRouter
Model: hunters/Hunter-Alpha-Xiaomi-MiMo-V2-Pro
API Key: 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
```

---

## Current Market State

### Observations
*[Groq: Record what you're observing in the market]*

### Hypotheses
*[Groq: What you think might happen, what you want to test]*

---

## SignalR vs WebSocket (CRITICAL FIX)

### The Problem
- Node.js sidecar was using raw WebSocket (`ws://`/`wss://`)
- ProjectX requires **SignalR protocol** over WebSocket transport
- This is why real-time data never arrived

### The Solution
```javascript
// WRONG - Raw WebSocket
const ws = new WebSocket('wss://rtc.topstepx.com/hubs/market');

// CORRECT - SignalR
const { HubConnectionBuilder } = require('@microsoft/signalr');
const connection = new HubConnectionBuilder()
    .withUrl('https://rtc.topstepx.com/hubs/market', {
        skipNegotiation: false,
        transport: HttpTransportType.WebSockets
    })
    .withAutomaticReconnect()
    .build();
```

### Files Updated
- `C:\KAI\armada\topstep_sidecar\src\signalr-manager.js` - Already uses SignalR ✅
- `C:\KAI\obsidian_vault/Sovran AI/Research/BUG_REPORT_REALTIME_SIGNALR.md`

---

## Circuit Breaker Pattern

Four circuit breakers protecting Hunter Alpha:

| Breaker | Trigger | Action |
|---------|---------|--------|
| Runtime | Unlimited (0) | Process runs until market close |
| L2 Staleness | 60+ seconds stale | Block new entries |
| Volatility | ATR spike | Lock 120 seconds |
| PNL | Daily loss < -$500 | Halt all trading |

**File:** `C:\KAI\obsidian_vault/Sovran AI/Research/CIRCUIT_BREAKER_PATTERN.md`

---

## Questions for Teacher

1. *[Groq: Add questions here for KAI/Big Pickle to answer]*

---

## Teacher Responses

*[KAI/Big Pickle will add responses here after reviewing your work]*

---

## Strategies Being Developed

### Strategy 1: [Name]
- **Status:** testing | confirmed | invalidated
- **Edge:** [What makes it work]
- **Conditions:** [When to use]
- **Evidence:** [Trades that support it]

---

## Recent Activity

| Time | Trade | Direction | Outcome | What I Learned |
|------|-------|-----------|---------|----------------|

---

## Lessons Learned

*[Document key learnings here after each trade]*

---

## Mental Model Applications

*[Record which mental models applied to recent trades]*

---

## Notes from Teacher

*[Feedback and corrections from Big Pickle]*

---

## Context Update Log

| Date/Time | Update |
|-----------|--------|
| 2026-03-19 15:05 | Context initialized |

---

*This context is your persistent memory. Update it after every trade.*

| 2026-03-19 09:49:11 UTC | Trade #1 | BUY | OPEN | Forced boot trade - model chose WAIT, defaulting t |

| 2026-03-19 09:52:02 UTC | Trade #2 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 09:55:48 UTC | Trade #3 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 09:59:44 UTC | Trade #4 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:03:36 UTC | Trade #5 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:07:33 UTC | Trade #6 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:11:26 UTC | Trade #7 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:15:04 UTC | Trade #8 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:18:45 UTC | Trade #9 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:22:24 UTC | Trade #10 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:26:05 UTC | Trade #11 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:30:14 UTC | Trade #12 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:34:21 UTC | Trade #13 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:38:39 UTC | Trade #14 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:41:36 UTC | Trade #15 | SELL | OPEN | MIDDAY CHOP session phase with low volume, mean-re |

| 2026-03-19 10:45:32 UTC | Trade #16 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:49:10 UTC | Trade #17 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:53:06 UTC | Trade #18 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 10:57:19 UTC | Trade #19 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 11:01:27 UTC | Trade #20 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 11:05:48 UTC | Trade #21 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 11:09:40 UTC | Trade #22 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 11:13:17 UTC | Trade #23 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 11:16:55 UTC | Trade #24 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 11:20:32 UTC | Trade #25 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 11:37:26 UTC | Trade #1 | BUY | OPEN | Forced boot trade - model chose WAIT, defaulting t |

| 2026-03-19 11:57:08 UTC | Trade #2 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 12:17:51 UTC | Trade #3 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 12:38:34 UTC | Trade #4 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 12:50:36 UTC | Trade #5 | SELL | OPEN | MIDDAY CHOP session phase with low volume, suggest |

| 2026-03-19 13:11:34 UTC | Trade #6 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 13:32:23 UTC | Trade #7 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 13:53:15 UTC | Trade #8 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 14:14:15 UTC | Trade #9 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 14:35:00 UTC | Trade #10 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 14:55:43 UTC | Trade #11 | BUY | OPEN | Forced trade - model chose WAIT, defaulting to BUY |

| 2026-03-19 15:17:00 UTC | Trade #12 | SELL | FAILED | MIDDAY CHOP session phase with low volume, suggest |
