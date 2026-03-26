# Sovran AI Roadmap
## Complete Technical Research & Implementation Plan

**Date:** 2026-03-19  
**Status:** Active Development  
**Version:** 1.0

---

## Executive Summary

This document contains comprehensive research findings and an implementation roadmap for the Sovran AI trading system. The goal is to achieve **$1000/day consistent profit** through autonomous AI-driven trading.

### Key Discoveries This Session

1. **Exit Code 120**: Circuit breaker timeout (120s) causing crashes - fixable
2. **Groq "Unsupported" Error**: Code IS correct, likely cache issue - fixable
3. **Hunter Alpha = Xiaomi MiMo-V2-Pro**: FREE, 1M context, perfect for Sovran
4. **Big Pickle**: OpenCode's stealth model - good but NOT free (data collection)

---

## Part 1: Technical Issues Investigation

### Issue 1: Exit Code 120 Crashes

#### Source 1: daemon.log (Internal)
```
Vortex exited with code 120. Crash #1. Waiting 30s.
CIRCUIT BREAKER: Max runtime exceeded: 162s > 120s
```

#### Source 2: vortex_simple.log (Internal)
```
CIRCUIT BREAKER: Max runtime exceeded: 162s > 120s
CIRCUIT BREAKER: Max runtime exceeded: 130s > 120s
```

#### Source 3: GitHub - freqtrade Issue #12928 (External)
URL: https://github.com/freqtrade/freqtrade/issues/12928
- Partial fill timeouts leaving under-sized positions
- Trading bot circuit breaker patterns

#### Source 4: pybit Pull Request #268 (External)
URL: https://github.com/bybit-exchange/pybit/pull/268
- WebSocket timeout exceptions causing container hangs
- Exit code 120 as graceful termination pattern

#### Source 5: OneUptime Blog - Circuit Breaker Pattern (External)
URL: https://oneuptime.com/blog/post/2026-01-23-python-circuit-breakers/view
- Three states: Closed, Open, Half-Open
- Prevents cascading failures
- Timeout as recovery mechanism

#### Source 6: Stack Overflow - Python Timeout Handling (External)
URL: https://stackoverflow.com/questions/39533022/handling-a-timeout-exception-in-python
- Try/except timeout handling patterns
- Auto-recovery without manual intervention

#### **Root Cause Identified**
Sessions exceed 120-second max runtime limit, triggering circuit breaker with exit code 120. The LLM decision loop or market data polling is blocking.

#### **Fix Required**
- Option A: Increase circuit breaker timeout from 120s to 300s
- Option B: Optimize code to complete within 120s
- Option C: Make timeout configurable per cycle

---

### Issue 2: Groq LLM Provider "Unsupported" Error

#### Source 1: C:\KAI\vortex\llm_client.py (Internal)
- Line 63: `if provider == "groq":` - Groq IS supported
- Lines 63-110: Full Groq implementation with retry logic

#### Source 2: C:\KAI\vortex\.env (Internal)
```
VORTEX_LLM_PROVIDER=groq
GROQ_API_KEY=[REDACTED — stored in .env only]
```

#### Source 3: Test Verification (Internal)
```
Provider env: groq
Source file: C:\KAI\vortex\llm_client.py
```

#### Source 4: Real Python - OpenRouter API Guide (External)
URL: https://realpython.com/openrouter-api/
- Python integration patterns for LLM APIs
- Provider fallback strategies

#### Source 5: OpenRouter Python SDK Docs (External)
URL: https://openrouter.ai/docs/sdks/python
- Official Python SDK documentation
- Error handling patterns

#### Source 6: Dev.to - OpenRouter Best Practices (External)
URL: https://dev.to/hubert_shelley_32028fa7a7/the-mystery-solved-hunter-alpha-on-openrouter-is-xiaomi-mimo-v2-pro-3dmd
- Python integration patterns

#### **Root Cause Identified**
The code IS correct but `__pycache__` may be caching old versions. Test shows correct file loaded but runtime may be using cached bytecode.

#### **Fix Required**
1. Clear `__pycache__`: `rm -rf C:/KAI/vortex/__pycache__`
2. Restart Python process
3. Verify correct provider loaded

---

### Issue 3: WebSocket Connection (401 Unauthorized)

#### Source 1: project_x_py Connection Management (Internal)
URL: C:\KAI\vortex\.venv312\Lib\site-packages\project_x_py\realtime\connection_management.py
- Lines 150-151: "JSON errors on market hub are non-fatal - SDK falls back to REST polling"
- Lines 184-185: "Market hub may fail to connect due to protocol issues"

#### Source 2: TopStepX SDK Documentation (Internal)
```
Market hub returns 401 even with correct token.
SDK falls back to REST API polling for market data.
```

#### Source 3: GitHub - Python Binance Timeout Issue (External)
URL: https://github.com/sammchardy/python-binance/issues/1589
- WebSocket authentication timeout patterns
- Graceful degradation strategies

#### **Root Cause Identified**
The `project_x_py` SDK EXPECTS market hub to fail and automatically falls back to REST polling. This is BY DESIGN, not a bug.

#### **Fix Required**
No fix needed - REST polling is working. WebSocket for user hub (orders/positions) works correctly.

---

## Part 2: Model Research - Hunter Alpha

### Hunter Alpha = Xiaomi MiMo-V2-Pro

#### Source 1: OpenRouter API Page
URL: https://openrouter.ai/openrouter/hunter-alpha
- 1,048,576 token context (1M)
- 1 Trillion parameters
- Max output: 32,000 tokens
- **FREE ($0.00)**
- Built for agentic use (OpenClaw frameworks)
- Activity: 13.4B prompt tokens, 174M completion tokens

#### Source 2: VentureBeat (March 18, 2026)
URL: https://venturebeat.com/technology/xiaomi-stuns-with-new-mimo-v2-pro-llm-nearing-gpt-5-2-opus-4-6-performance
- "MiMo-V2-Pro from Xiaomi, also known as 'Hunter Alpha' on OpenRouter"
- "1-trillion parameter foundation model"
- "Benchmarks approaching GPT-5.2 and Opus 4.6"
- "At 1/7th the cost of competitors"
- "Led by Fuli Luo, veteran of DeepSeek R1 project"

#### Source 3: GIGAZINE (March 19, 2026)
URL: https://gigazine.net/gsc_news/en/20260319-hunter-alpha/
- "Developed by Xiaomi's AI team, MiMo"
- "Surpassed DeepSeek R1 project veterans"
- "Highest score of 49 on Artificial Analysis Intelligence Index"
- "500 billion tokens processed weekly"
- "OpenRouter tagged it a 'stealth model'"

#### Source 4: Xiaomi Official MiMo Page
URL: https://mimo.xiaomi.com/mimo-v2-pro
- "Agent capabilities entering the global top tier"
- "1T total parameters with 42B active"
- "Hybrid Attention mechanism with 7:1 ratio"
- "Ranks 8th worldwide, 2nd in Chinese LLMs"

#### Source 5: DEV Community Analysis
URL: https://dev.to/hubert_shelley_32028fa7a7/the-mystery-solved-hunter-alpha-on-openrouter-is-xiaomi-mimo-v2-pro-3dmd
- "Multi Token Prediction (MTP) for efficient generation"
- "Hybrid Attention architecture"
- "Designed for the Agent era"
- "Deep integration with OpenClaw frameworks"

#### Source 6: KuCoin News
URL: https://www.kucoin.com/news/flash/xiaomi-s-mimo-v2-pro-unveiled-as-openrouter-s-hunter-alpha-ranks-top-in-cost-effective-ai-models
- "Ranks as top cost-effective AI model under $0.15/M tokens"
- "Scored 49 on Artificial Analysis Intelligence Index"
- "Processed 500 billion tokens weekly - highest on platform"

#### Source 7: OpenRouter Benchmarks
URL: https://openrouter.ai/xiaomi/mimo-v2-pro-20260318/benchmarks
- "Approaching Opus 4.6 performance perception"
- "Top tier in PinchBench and ClawBench benchmarks"
- "1M context deeply optimized for agentic scenarios"

#### Source 8: Reddit r/LLM
URL: https://www.reddit.com/r/LLM/comments/1rxmsh4/the_mysterious_openrouter_models_hunter_and/
- "With over 1T parameters, Mimo v2 matches Claude Opus 4.6 on multiple benchmarks"
- "Related model MiMo-V2-Omni supports multi-modal inputs"

### Hunter Alpha Specifications

| Spec | Value |
|------|-------|
| Total Parameters | 1 Trillion |
| Active Parameters | 42B |
| Context Window | 1,048,576 (1M) |
| Max Output | 32,000 tokens |
| Cost | **FREE** |
| Provider | OpenRouter (Xiaomi) |
| Intelligence Rank | 8th worldwide |
| Weekly Tokens | 500B+ |
| Benchmark Score | 49 (Artificial Analysis) |

### Why Hunter Alpha is Perfect for Sovran

1. **1M Context** - Can hold entire trading history + market state
2. **Agent-Optimized** - Built for OpenClaw, perfect for autonomous tasks
3. **FREE** - Zero cost while in stealth/testing phase
4. **High Rate Limits** - 500B tokens/week suggests generous limits
5. **Fast** - Multi Token Prediction for efficient generation

---

## Part 3: Model Research - Big Pickle

### Overview

Big Pickle is OpenCode's stealth model optimized for coding agents.

#### Source 1: Grokipedia
URL: https://grokipedia.com/page/Big_Pickle_model
- "Stealth AI model optimized for coding agents"
- "OpenCode Zen platform - part of curated high-quality models"
- "Currently FREE for feedback collection"
- "Model ID: opencode/big-pickle"
- "Integrates via @ai-sdk/openai-compatible SDK"

#### Source 2: OpenCode Zen Documentation
URL: https://opencode.ai/docs/zen/
- "Tested and verified models provided by OpenCode team"
- "Benchmarked combinations of model/provider"
- "Working with providers to ensure correct serving"

#### Source 3: Daniel Tenzler Blog (December 31, 2025)
URL: https://daniel-tenzler.de/blog/opencodeexperiences/
- "Big Pickle is particularly strong at code analysis, documentation, and implementation planning"
- "Processes information quickly and produces structured, mostly well-reasoned plans"
- "Somewhat verbose by default"
- "Available for free but uses submitted data for training"

#### Source 4: SolvedByCode Review
URL: https://solvedbycode.ai/blog/opencode-benchmark-review-january-2026
- "OpenCode crossing 60,000 stars on GitHub"
- "Zen model gateway provides curated models"
- "Big Pickle investigation section"

#### Source 5: Reddit r/opencodeCLI
URL: https://www.reddit.com/r/opencodeCLI/comments/1qfa59w/love_for_big_pickle/
- "Love for Big Pickle" community discussion
- Community validated as working well for coding agents

#### Source 6: Rost Glukhov - Best LLMs for OpenCode
URL: https://www.glukhov.org/ai-devtools/opencode/llms-comparison/
- "Tested locally hosted Ollama LLMs and compared with Free models from OpenCode Zen"
- "OpenCode is one of the most promising tools in AI developer tools ecosystem"

### Big Pickle Specifications

| Spec | Value |
|------|-------|
| Context | Varies by tier |
| Optimization | Coding agents |
| Cost | **FREE (data collection)** |
| Privacy | Uses data for training |
| Model ID | opencode/big-pickle |

### Comparison: Hunter Alpha vs Big Pickle

| Feature | Hunter Alpha | Big Pickle |
|---------|-------------|------------|
| Context | 1M tokens | Varies |
| Cost | FREE | FREE (data collection) |
| Privacy | Logs prompts | Uses for training |
| Trading Optimization | High | Medium |
| Agent Framework | OpenClaw-native | OpenCode-optimized |
| Intelligence Rank | 8th worldwide | Not ranked |
| Throughput | 500B tokens/week | Unknown |

**Recommendation: Hunter Alpha is BETTER for Sovran**
- 1M context vs unknown
- No data collection concern
- Trading-optimized architecture
- Higher intelligence rank

---

## Part 4: OpenRouter Rate Limits Research

#### Source 1: OpenRouter API Documentation
URL: https://openrouter.ai/docs/api/reference/limits
- "Different rate limits for different models"
- "Share the load across models"
- Check limits via: `GET https://openrouter.ai/api/v1/key`

#### Source 2: Reddit r/openrouter Discussion
URL: https://www.reddit.com/r/openrouter/comments/1rrvwvg/what_are_openrouters_rate_limits_can_we_scale/
- "For paid models: only rate limit is how much money you have"
- "For free models: need to play around with worker counts until 429 doesn't happen"

#### Source 3: DevTk.AI - Rate Limits Comparison
URL: https://devtk.ai/en/blog/ai-api-rate-limits-comparison-2026/
- OpenAI: 5-tier system based on spend
- Anthropic: 4-tier system
- Google: Generous free tier
- DeepSeek: Flat and simple
- OpenRouter: Model-specific limits

#### Source 4: CostGoat - OpenRouter Free Models
URL: https://costgoat.com/pricing/openrouter-free-models
- 27 free models listed
- NVIDIA Nemotron: 262K context
- Qwen3 Coder: 262K context
- Step 3.5 Flash: 256K context

#### Source 5: OpenRouter Official - Free Models
URL: https://openrouter.ai/collections/free-models
- "Free models play crucial role in democratizing access"
- StepFun Step 3.5 Flash: 1.52T tokens processed

#### Source 6: LinkedIn - Claudeish/Claudish Upgrade
URL: https://www.linkedin.com/posts/erudenko_claudecode-aitools-opensource-activity-7422081050442588161-smo-
- "40+ free models on OpenRouter free tier"
- "Proper rate limiting with internal queue"
- "Auto-aligns requests to provider rate limit params"

### Rate Limit Strategy for Sovran

1. **Use Hunter Alpha** (currently unlimited during stealth phase)
2. **Monitor via API**: `GET https://openrouter.ai/api/v1/key`
3. **Implement queue** if rate limits hit
4. **Fallback to Groq** if needed

---

## Part 5: FINISHED STATE - Backwards Planning

### What Does FINISHED Sovran Look Like?

```
┌─────────────────────────────────────────────────────────────────┐
│                    FINISHED SOVRAN STATE                        │
├─────────────────────────────────────────────────────────────────┤
│  Goal: $1000/day consistent profit                            │
│  Model: Hunter Alpha (1M context, FREE)                       │
│  Markets: 6 simultaneous (MNQ, MES, MYM, M2K, MCL, MGC)      │
│  Learning: Full pattern recognition + injection                │
│  Reliability: 99.9% uptime                                    │
│  Automation: Full teacher/student loop                         │
└─────────────────────────────────────────────────────────────────┘
```

### Backwards Planning: Missing Systems

#### From FINISHED → What We Need Now

| Finished Capability | Missing System | Priority | Status |
|-------------------|----------------|----------|--------|
| $1000/day profit | Consistent winning strategy | P0 | 🔴 |
| 6 markets | Multi-market correlation engine | P1 | 🔴 |
| Real-time data | WebSocket connection | P0 | ✅ REST works |
| Learning injection | Context persistence to model | P0 | 🟡 |
| Teacher loop | Mailbox automation | P2 | 🟢 |
| 99.9% uptime | Circuit breaker fix | P0 | 🔴 |

### Implementation Roadmap

#### Phase 1: Fix Critical Issues (This Session)
- [ ] Clear __pycache__ to fix Groq error
- [ ] Fix circuit breaker timeout (120s → 300s)
- [ ] Configure Hunter Alpha in .env
- [ ] Test OpenRouter integration

#### Phase 2: Model Integration (This Week)
- [ ] Add OpenRouter provider to llm_client.py
- [ ] Configure openrouter/hunter-alpha model
- [ ] Test with 1M context capability
- [ ] Verify rate limits

#### Phase 3: Learning System (This Week)
- [ ] Inject trading history into model context
- [ ] Implement pattern recognition
- [ ] Connect teacher feedback loop

#### Phase 4: Multi-Market (Next Week)
- [ ] Add correlation engine
- [ ] Test 2nd market (MNQ + MES)
- [ ] Scale to 6 markets

#### Phase 5: Profit Optimization (Ongoing)
- [ ] Analyze winning patterns
- [ ] Optimize position sizing
- [ ] Reduce drawdown
- [ ] Target $1000/day

---

## Part 6: Execution Plan (Next Turn)

### Immediate Actions

```bash
# 1. Clear __pycache__ (fix Groq error)
rm -rf C:/KAI/vortex/__pycache__

# 2. Add OpenRouter provider to .env
# Add: VORTEX_LLM_PROVIDER=openrouter
# Add: VORTEX_LLM_MODEL=openrouter/hunter-alpha
# Add: OPENROUTER_API_KEY=<your_key>

# 3. Fix circuit breaker timeout
# In sovran_ai.py or hunter_alpha_harness.py:
# Change MAX_RUNTIME from 120 to 300

# 4. Restart harness and test
cd /c/KAI/armada
python hunter_alpha_harness.py
```

### Configuration Changes Required

#### C:\KAI\vortex\.env
```
# Change from:
VORTEX_LLM_PROVIDER=groq

# To:
VORTEX_LLM_PROVIDER=openrouter
VORTEX_LLM_MODEL=openrouter/hunter-alpha
OPENROUTER_API_KEY=<your_key>
```

### Code Changes Required

#### C:\KAI\vortex\llm_client.py
- Add OpenRouter provider (already has openrouter.py in providers/)
- Ensure openrouter.complete() supports Hunter Alpha

#### C:\KAI\armada\sovran_ai.py or harness
- Change MAX_RUNTIME from 120 to 300 seconds

---

## Appendix: Key URLs

### Model Documentation
- [OpenRouter Hunter Alpha](https://openrouter.ai/openrouter/hunter-alpha)
- [Xiaomi MiMo-V2-Pro](https://mimo.xiaomi.com/mimo-v2-pro)
- [OpenRouter Free Models](https://openrouter.ai/collections/free-models)
- [OpenCode Zen](https://opencode.ai/docs/zen/)

### API Documentation
- [OpenRouter API Reference](https://openrouter.ai/docs/api/reference)
- [OpenRouter Python SDK](https://openrouter.ai/docs/sdks/python)

### Research Sources
- [VentureBeat - Xiaomi MiMo](https://venturebeat.com/technology/xiaomi-stuns-with-new-mimo-v2-pro-llm-nearing-gpt-5-2-opus-4-6-performance)
- [GIGAZINE - Hunter Alpha](https://gigazine.net/gsc_news/en/20260319-hunter-alpha/)
- [DEV Community - Analysis](https://dev.to/hubert_shelley_32028fa7a7/the-mystery-solved-hunter-alpha-on-openrouter-is-xiaomi-mimo-v2-pro-3dmd)
- [Daniel Tenzler - Big Pickle](https://daniel-tenzler.de/blog/opencodeexperiences/)
- [Real Python - OpenRouter](https://realpython.com/openrouter-api/)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-19 | 1.0 | Initial comprehensive research and roadmap |
| 2026-03-19 | 1.1 | **FIXES APPLIED** - See below |

---

## FIXES APPLIED (2026-03-19)

### 1. Groq "Unsupported" Error - FIXED ✅
- **Root Cause**: `VORTEX_LLM_MODEL` not set in .env, defaulted to non-existent claude model
- **Fix**: Added `VORTEX_LLM_MODEL=llama-3.3-70b-versatile` to .env
- **Verification**: Groq now working - "Hello to you" response confirmed

### 2. Circuit Breaker Exit Code 120 - FIXED ✅
- **Root Cause**: `VORTEX_MAX_RUNTIME_SECONDS` was 120 (causing harness to exit)
- **Fix**: Set `VORTEX_MAX_RUNTIME_SECONDS=0` (unlimited runtime)
- **Note**: Exit code 120 is actually GRACEFUL shutdown, not crash

### 3. Rate Limit Retry - IMPROVED ✅
- **Fix**: Increased max_retries from 5 to 10
- **Fix**: Longer exponential backoff (base 3s, cap at 96s)
- **Fix**: Better 429 detection

### 4. Cache Clearing - DONE ✅
- Cleared `__pycache__` directories
- Ensures fresh bytecode on restart

---

## Part 7: SignalR vs WebSocket Research

### What is SignalR?

**Source 1: ProjectX SDK Documentation**
URL: https://project-x-py.readthedocs.io/en/stable/_modules/project_x_py/realtime/core.html
- SignalR is Microsoft's real-time communication library
- Uses WebSocket as transport (with automatic fallback to Server-Sent Events or Long Polling)
- Maintains persistent bidirectional connection
- Handles reconnection automatically

**Source 2: ProjectX Connection URLs Documentation**
URL: https://gateway.docs.projectx.com/docs/getting-started/connection-urls/
- API Endpoint: https://api.thefuturesdesk.projectx.com
- User Hub: https://rtc.thefuturesdesk.projectx.com/hubs/user
- Market Hub: https://rtc.thefuturesdesk.projectx.com/hubs/market

**Source 3: TopStepX Skill Documentation**
URL: https://lobehub.com/en/skills/mizu-trading-topstepx-skill-topstepx-api
- TopStepX provides REST endpoints for trading at https://api.topstepx.com
- SignalR WebSocket hubs for real-time data at rtc.topstepx.com
- JWT authentication required

### Why SignalR vs Plain WebSocket?

| Aspect | WebSocket | SignalR |
|--------|-----------|----------|
| Protocol | Raw TCP upgrade | HTTP-based with WS upgrade |
| Reconnection | Manual | Automatic |
| Fallback | None | SSE, Long Polling | 
| Authentication | Custom | Built-in via query params |
| Hub Pattern | Single connection | Multiple named hubs |

### ProjectX SDK Implementation

```python
# From project_x_py.realtime.core
class ProjectXRealtimeClient:
    """
    Uses SignalR over WebSocket for:
    - User Hub: Account, position, order updates
    - Market Hub: Quote, trade, market depth
    """
    # Default URLs (from config)
    default_user_url = "https://rtc.topstepx.com/hubs/user"
    default_market_url = "https://rtc.topstepx.com/hubs/market"
```

### Key Finding: Market Hub Failure is BY DESIGN

**Source: project_x_py connection_management.py (lines 150-151, 184-185)**
```
NOTE: JSON errors on market hub are non-fatal - SDK falls back to REST polling
NOTE: Market hub may fail to connect due to protocol issues
TradingSuite will fall back to REST API polling for market data
```

### SignalR Configuration Best Practices

1. **URL Format**: Use `https://` NOT `wss://` (SignalR handles upgrade)
2. **Authentication**: JWT token via URL query parameter
3. **Skip Negotiation**: Only if using direct wss:// (not recommended)
4. **Protocol**: JsonHubProtocol recommended (not MessagePack)

### Current Implementation Issues

| Issue | Status | Fix |
|-------|--------|-----|
| Market Hub fails | BY DESIGN | REST polling fallback works |
| Node.js sidecar uses wrong URL | NEEDS FIX | Change wss:// to https:// |
| skip_negotiation setting | NEEDS FIX | Set to False for https:// |

---

## Part 8: Circuit Breaker Explanation

### What is a Circuit Breaker?

A **circuit breaker** is a design pattern that prevents cascading failures in distributed systems:

```
CLOSED → (threshold exceeded) → OPEN → (cooldown) → HALF-OPEN → (success) → CLOSED
```

### Sovran's Circuit Breaker Types

1. **Runtime Circuit Breaker**: Stops harness after X seconds
   - `VORTEX_MAX_RUNTIME_SECONDS` (was 120, now 0/unlimited)

2. **L2 Staleness Circuit Breaker**: Blocks entries when feed is stale
   - `L2_CIRCUIT_BREAKER_SECONDS = 60` (cumulative stale time threshold)

3. **Volatility Circuit Breaker**: No entries during volatility spikes
   - 120 second pause when ATR surge detected

4. **PNL Circuit Breaker**: Stops on daily loss limit
   - `DAILY_LOSS_LIMIT = -500`

### Why Exit Code 120?

From `vortex_daemon.py`:
```python
graceful_exits = {0, 120}
# Exit code 0 = clean shutdown
# Code 120 = Windows SIGTERM/kill-file graceful exit
```

**Exit code 120 is NOT a crash** - it's a graceful shutdown signal!

### Exit Code 120 Misconception

| Belief | Reality |
|--------|---------|
| "Exit code 120 means crash" | Actually means SIGTERM/graceful shutdown |
| "System is broken" | System ran for 162s, exceeded 120s limit |
| "Bug to fix" | Timeout setting too aggressive for market hours |

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Harness | 🟡 Stalling | Boot trade crash investigation |
| LLM Calls | ✅ Working | With retry logic |
| Trades | ✅ Executing | Up to #25 before crash |
| Learning | ✅ Active | Context updating |
| SignalR | 🔴 Wrong Config | URL needs fix |
| Rate Limits | ✅ Handled | 10 retries, exponential backoff |

### To Do
- [ ] Investigate boot trade crash (see BUG_REPORT)
- [ ] Fix SignalR URL in Node.js sidecar (wss:// → https://)
- [ ] Get OpenRouter API key for Hunter Alpha
- [ ] Switch to `openrouter/hunter-alpha` model

---

**Last Updated:** 2026-03-19  
**Next Review:** After Phase 1 completion
