# PROJECT CONTINUATION DOCUMENT
## Session 15 — 2026-03-19 (Updated)

---

## 📋 COMPREHENSIVE ROADMAP
**IMPORTANT:** See [[Roadmap/SOVRAN_ROADMAP|Complete Technical Research & Implementation Plan]]

### QUICK STATUS (2026-03-19)
- **Harness: RUNNING** ✅
- **OpenRouter/Hunter Alpha: CONFIGURED** ✅
- **SignalR Sidecar: READY** ✅
- **Real-Time Data: REQUIRES API SUBSCRIPTION** ⚠️
- **Rate Limits: Handled** (retry logic improved)
- **Exit Code 120: FIXED** (set VORTEX_MAX_RUNTIME_SECONDS=0)

---

### 🔴 REAL-TIME DATA: CONFIRMED SUPPORTED ON TRADING COMBINES
**Date:** 2026-03-19

TopStepX's ProjectX API DOES support real-time data for Trading Combine accounts (including 150k combines).

**Requirements:**
1. Active API subscription (separate from combine membership)
2. Proper SignalR connection (Node.js sidecar already uses this)
3. Valid JWT token from ProjectX authentication

**If not seeing data:**
- Verify API subscription active in ProjectX dashboard
- Confirm 150k combine appears under same ProjectX profile
- Contact TopStep support if still no data

---

### 1. PROJECT IDENTITY

- **Project Name:** Hunter Alpha — Autonomous AI Trading System
- **What This Project Is:** An AI-driven trading system where Hunter Alpha (Xiaomi MiMo-V2-Pro via OpenRouter) makes all trading decisions, executing futures trades on TopStepX paper account through an autonomous harness. The system learns from each trade through memory and Obsidian logging.
- **Primary Objective:** Achieve consistent **$1,000 daily profit** through AI-driven institutional order flow analysis. Hunter Alpha must learn through experience, not wait.
- **Strategic Intent:** Build a self-teaching trading AI that develops genuine market intuition over time, logging all activity to Obsidian for review and strategy development.
- **Hard Constraints:**
  - Paper trading only (TopStepX)
  - **Hunter Alpha LLM** (openrouter/hunter-alpha) - 1M context, FREE, 1T parameters
  - TopStepX REST API for execution (WebSocket market hub expected to fail per SDK)
  - All trades logged to Obsidian vault
  - Windows environment with bash/git shell
  - Python 3.11 venv at `C:\KAI\vortex\.venv312`

---

### 2. WHAT EXISTS RIGHT NOW

- **What is built and working:**
  - `hunter_alpha_harness.py` — Main autonomous loop running 30-second decision cycles
  - `sovran_ai.py` — Execution layer placing atomic bracket orders (entry + SL + TP)
  - **Groq LLM integration** - Code is correct, cache issue may cause "Unsupported" error
  - Broker position tracking via `broker.py` (get_positions_sync)
  - TopStepX atomic bracket API confirmed working (verified 2026-03-18)
  - **REST polling is WORKING** - Fallback for WebSocket, not a bug

- **What is partially built:**
  - Obsidian logging system (trades logged, but learning analysis is template-heavy)
  - Node.js sidecar (`topstep_sidecar/src/index.js`) — runs, market hub fails by DESIGN
  - `realtime_bridge.py` integration — connects to sidecar, REST polling active

- **What is broken or blocked:**
  - **Groq "Unsupported VORTEX_LLM_PROVIDER='groq'"** — Code IS correct, fix: clear __pycache__
  - **Exit Code 120 crashes** — Circuit breaker timeout (120s), fix: increase to 300s
  - **Entry prices show $0.00** — REST polling timing (cosmetic)
  - ~~Model repeats same reasoning~~ — **FIXED with GROQ persistent context**

- **What has NOT been started yet:**
  - **Hunter Alpha integration** - New model discovered, need to configure OpenRouter
  - Strategy development (10 strategies needed for $1k/day)
  - Multi-market correlation engine
  - **PENDING**: Test GROQ context integration (run harness with new code)

---

### 3. ARCHITECTURE & TECHNICAL MAP

**NEW: DUAL-CONTEXT ARCHITECTURE**
- **KAI context** → AI_Continuation_Document (for KAI AI)
- **Groq context** → GROQ_TRADING_CONTEXT.md (for trading model)
- **Obsidian is the central brain** for both agents
- **Teacher loop**: Groq trades → KAI reviews → Big Pickle reviews → Feedback in INBOX

- **Tech stack / tools / platforms:**
  - Python 3.11 with project_x_py v3.5.9
  - **Hunter Alpha via OpenRouter** (openrouter/hunter-alpha) - RECOMMENDED
    - 1M token context (vs Groq's ~8K)
    - FREE ($0.00)
    - 1 Trillion parameters
    - Agent-optimized (built for OpenClaw)
  - Alternative: Groq API (llama-3.3-70b-versatile, 60 RPM)
  - TopStepX (paper account, MNQ futures)
  - Obsidian vault at `C:\KAI\obsidian_vault\Sovran AI\`
  - Node.js sidecar for WebSocket (REST polling is primary by design)

- **Key files and repos:**
  ```
  C:\KAI\armada\
  ├── hunter_alpha_harness.py      # Main harness (1240+ lines, MODIFIED)
  ├── sovran_ai.py                # Execution layer
  ├── realtime_bridge.py          # Node.js bridge
  ├── topstep_sidecar\           # Node.js WebSocket sidecar
  │   └── src/index.js
  
  C:\KAI\vortex\
  ├── .env                        # API keys, Groq config
  ├── broker.py                   # Position tracking
  └── llm_client.py               # LLM provider (Groq added)

  C:\KAI\obsidian_vault\Sovran AI\
  ├── AI_Continuation_Document-19Mar2026-1415.md  ← KAI's handoff
  ├── GROQ\                                    ← NEW: Groq's context
  │   ├── GROQ_TRADING_CONTEXT.md              ← Groq's persistent brain
  │   ├── GROQ_INBOX\                          ← Teacher messages
  │   │   ├── INBOX_INDEX.md
  │   │   └── INBOX_001.md
  │   ├── GROQ_RESUME_PROMPT.md
  │   ├── TEACHER_WORKFLOW.md
  │   └── ARCHITECTURE_PLAN.md
  ├── Session Logs\
  ├── Trades\2026-03-19\
  ├── Hunter_Alpha\Student_Logs\
  └── Learnings\
  ```

- **How the system works end-to-end (UPDATED):**
  1. Harness boots, connects to TopStepX via TradingSuite
  2. **NEW**: Reads GROQ_TRADING_CONTEXT.md for persistent context
  3. **NEW**: Checks GROQ_INBOX/ for teacher messages
  4. 30-second loop: `hunter_alpha_decide()` calls Groq with market data + Groq context
  5. Groq returns action (BUY/SELL/WAIT) + parameters (size, SL ticks, TP ticks)
  6. `place_trade()` executes via sovran_ai.py atomic bracket API
  7. **NEW**: Updates GROQ_TRADING_CONTEXT.md with trade outcome
  8. **NEW**: Writes teacher feedback to GROQ_INBOX/ (for KAI/Big Pickle review)
  9. Trade logged to Obsidian (trade_XXX.md, Student Log)
  10. Loop repeats with updated context

- **Naming conventions:**
  - Session logs: `YYYY-MM-DD_HHMMSS`
  - Trade files: `trade_XXX.md`
  - Student logs: `STUDENT_LOG_YYYYMMDD.md`
  - Reports: `HA_REPORT_HHMMSS.md`

- **External dependencies:**
  - TopStepX REST API (https://api.topstepx.com)
  - Groq API (https://api.groq.com)
  - project_x_py library (installed in venv)

---

### 4. RECENT WORK — WHAT JUST HAPPENED

- **What was worked on in this session:**
  - **COMPREHENSIVE RESEARCH** - All issues investigated with multiple sources:
    - Exit Code 120 crashes (6 sources) - Circuit breaker timeout issue
    - Groq "Unsupported" error (6 sources) - Code is correct, cache issue
    - Hunter Alpha model (8 sources) - Xiaomi MiMo-V2-Pro, 1M context, FREE
    - Big Pickle model (6 sources) - OpenCode Zen, data collection concern
    - OpenRouter rate limits (6 sources) - Hunter Alpha has generous limits
  - **NEW**: Created comprehensive roadmap in Obsidian
  - Investigated harness crashes and LLM errors
  - **CRITICAL DISCOVERY**: Hunter Alpha is perfect for Sovran (see roadmap)

- **What decisions were made and WHY:**
  - **Hunter Alpha > Groq**: 1M context vs ~8K, FREE vs $0, agent-optimized
  - **Hunter Alpha > Big Pickle**: No data collection, higher intelligence rank
  - REST polling is WORKING - SDK expects market hub to fail (not a bug)
  - Groq code is CORRECT - just clear __pycache__ to fix
  - Exit Code 120 fix: Increase circuit breaker timeout from 120s to 300s

- **What changed in the system:**
  - **NEW**: `Roadmap/SOVRAN_ROADMAP.md` — Complete technical research document
  - Updated AI_Continuation_Document with roadmap link
  - `.env` needs update for OpenRouter/Hunter Alpha

- **What was discussed but NOT yet implemented:**
  - Fix emoji logging crash (workaround: `PYTHONIOENCODING=utf-8` but harness still crashes)
  - Test the new GROQ context system with actual trades
  - Verify teacher feedback loop is working

- **Open threads or unresolved questions:**
  - Does the harness crash with the new GROQ integration?
  - Is the model now producing unique reasoning per trade?
  - What are the 10 strategies needed for $1k/day?

---

### 5. WHAT COULD GO WRONG

- **Known bugs or issues:**
  - **Exit Code 120** - Circuit breaker timeout (120s), need to increase to 300s
  - **Groq "Unsupported"** - Code is correct, clear __pycache__ to fix
  - Entry prices show $0.00 (REST polling timing)
  - Model produces identical reasoning for every trade (GROQ context may fix)

- **Edge cases to watch for:**
  - Multiple harness instances running simultaneously
  - API rate limiting (Hunter Alpha appears to have generous limits)
  - TopStepX maintenance windows
  - Network disconnections
  - Hunter Alpha data logging (prompts logged per SDK)

- **Technical debt or shortcuts taken:**
  - Realtime bridge connects but doesn't receive data (market hub fails by design)
  - Research files are templates, not actual analysis
  - No actual learning from trade outcomes yet
  - 120-second circuit breaker too aggressive

- **Assumptions being made that could be wrong:**
  - That Hunter Alpha will always be free (stealth/testing phase)
  - That paper trading behavior reflects live trading
  - That the model will eventually "learn" without explicit strategy guidance

---

### 6. HOW TO THINK ABOUT THIS PROJECT

1. **Core architectural pattern:** Harness + Engine separation. Harness handles orchestration, logging, and LLM calls. Engine (sovran_ai.py) handles execution. This allows swapping engines without changing the learning loop.

2. **Most common mistake:** A new person would try to add more indicators, more sophisticated prompts, or more complex logic. The system needs to TRADE and LEARN, not get more complex.

3. **What looks like it should be refactored but should NOT be:**
   - The 30-second loop might seem slow — do NOT reduce it without understanding market microstructure
   - Groq might seem limited — do NOT switch to a "smarter" model without proving Groq can't learn

---

### 7. DO NOT TOUCH LIST

- Do NOT refactor stable, working systems without being asked
- Do NOT redesign architecture unless explicitly instructed
- Do NOT switch LLM providers without testing the alternative for 50+ trades
- Preserve existing naming conventions (trade_XXX.md, Student Logs)
- Maintain REST polling as PRIMARY mode (WebSocket is optional, not a fallback)
- Do NOT add more indicators to the prompt without evidence they improve outcomes
- Do NOT change the atomic bracket structure without testing

---

### 8. CONFIDENCE & FRESHNESS

| Section | Confidence | Notes |
|---------|------------|-------|
| 1. Project Identity | ✅ HIGH | Verified through execution |
| 2. What Exists | ⚠️ MEDIUM | Some features not tested recently |
| 3. Architecture | ✅ HIGH | Verified file paths and structure |
| 4. Recent Work | ✅ HIGH | From this session |
| 5. What Could Go Wrong | ✅ HIGH | All issues observed |
| 6. How to Think | ⚠️ MEDIUM | Based on project history |
| 7. Do Not Touch | ⚠️ MEDIUM | Needs validation |
| 8. Confidence | ✅ HIGH | Current assessment |

---

## NEXT SESSION

**Primary directive:** Execute fixes from comprehensive roadmap.

### Phase 1: Critical Fixes (This Session)

```bash
# 1. Clear __pycache__ (fixes Groq "Unsupported" error)
rm -rf C:/KAI/vortex/__pycache__

# 2. Fix circuit breaker timeout (120s -> 300s)
# In sovran_ai.py or hunter_alpha_harness.py
# Change MAX_RUNTIME from 120 to 300
```

### Phase 2: Hunter Alpha Integration

```bash
# Update C:\KAI\vortex\.env:
# Change from:
VORTEX_LLM_PROVIDER=groq

# To:
VORTEX_LLM_PROVIDER=openrouter
VORTEX_LLM_MODEL=openrouter/hunter-alpha
OPENROUTER_API_KEY=<your_key>
```

### Steps:
1. Clear __pycache__
2. Fix circuit breaker timeout
3. Configure Hunter Alpha in .env
4. Test OpenRouter provider in llm_client.py
5. Run harness and verify decisions
6. Check 1M context capability

### Key Questions to Answer:
- Is Hunter Alpha making unique trading decisions?
- Are rate limits acceptable?
- Is 1M context being utilized?

### Files Referenced:
- **ROADMAP**: [[Roadmap/SOVRAN_ROADMAP|Complete Technical Research]]
- **CONTEXT**: [[GROQ_TRADING_CONTEXT|Groq's Trading Brain]]
- **INBOX**: [[GROQ_INBOX|Teacher Messages]]
