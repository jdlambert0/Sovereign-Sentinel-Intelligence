# Bug Report: Harness Boot Trade Crash

**Date:** 2026-03-19  
**Severity:** High  
**Status:** Investigating

---

## Summary

The Hunter Alpha harness crashes during boot trade execution, causing repeated restarts. The harness initializes successfully, connects to TopStepX, but fails to complete the mandatory first trade, then restarts.

---

## Symptoms

1. Harness initializes and connects to TopStepX ✅
2. Realtime bridge connects successfully ✅
3. "30-second decision loop starting..." logged ✅
4. "[BOOT TRADE] Mandatory first trade on boot" logged ✅
5. **Harness crashes/restarts WITHOUT completing trade** ❌

---

## Log Evidence

```
[11:25:26] HUNTER ALPHA HARNESS INITIALIZING
[11:25:26] LEARNING_MODE: True
[11:25:26] Engine initialized
[11:25:26] Initial bankroll: $4500.00
[11:25:26] Connecting to realtime bridge (Node.js sidecar)...
[11:25:28] [OK] Realtime bridge connected!
[11:25:28] Harness ready
[11:25:28] HUNTER ALPHA HARNESS READY - LEARNING MODE ACTIVE
[11:25:28] 30-second decision loop starting...
[11:25:28] [BOOT TRADE] Mandatory first trade on boot...
[11:27:48] === HARNESS RESTARTS ===
```

**Gap:** 2+ minutes between boot trade message and restart, suggesting timeout or silent crash.

---

## Previous State (Working)

Before this issue:
- Trades #1-25 executed successfully
- Groq LLM was making decisions (model returned WAIT, forced BUY)
- All logging working correctly

---

## Possible Causes

1. **LLM Rate Limiting**: Groq 429 errors preventing decision
2. **SignalR Connection Lost**: Market hub disconnection causing crash
3. **Memory Issue**: Large context accumulation
4. **Timeout**: Extended LLM response time (>60s timeout)
5. **TopStepX Connection**: Auth token expiry during boot

---

## Previous Fixes Applied (This Session)

| Fix | Status |
|-----|--------|
| Clear __pycache__ | ✅ |
| Fix VORTEX_LLM_MODEL setting | ✅ |
| Fix VORTEX_MAX_RUNTIME_SECONDS=0 | ✅ |
| Improve rate limit retry | ✅ |

---

## Next Investigation Steps

1. Add more verbose logging around boot trade execution
2. Check if LLM call is timing out
3. Verify TopStepX connection remains active
4. Test with shorter decision interval

---

## Related Issues

- Exit Code 120 (resolved - was graceful shutdown, not crash)
- Groq "Unsupported" error (resolved - wrong model in .env)
- Rate limiting (partially resolved - improved retry logic)

---

**Reported by:** KAI  
**Last Updated:** 2026-03-19
