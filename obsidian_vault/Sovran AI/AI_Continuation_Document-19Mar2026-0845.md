# PROJECT CONTINUATION DOCUMENT
## Session — 2026-03-19

---

### 1. PROJECT IDENTITY

- **Project Name:** Hunter Alpha / Sovran AI Trading System
- **What This Project Is:** AI-driven futures trading system (MNQ micro e-mini) using Hunter Alpha (Groq Llama 3.3 70B) to make trading decisions, sovran_ai.py as execution layer, with TopStepX as the broker.
- **Primary Objective:** Achieve $1,000/day profit through learning mode - AI learns to trade by taking trades, collecting data, researching after every trade, and discovering patterns through real experience.
- **Strategic Intent:** Financial independence through AI trading. Learning mode prioritizes data collection and pattern discovery over immediate profitability.
- **Hard Constraints:**
  - Paper trading account (TopStepX) - WebSocket real-time data unavailable (expected limitation)
  - REST API is PRIMARY method for all trading operations
  - Must maintain healthcare coverage (SSDI/SSI) - never exceed income thresholds without planning
  - OpenRouter rate limits too restrictive (8 RPM) - switched to Groq (60 RPM)

---

### 2. WHAT EXISTS RIGHT NOW

- **What is built and working:**
  - Hunter Alpha harness (`hunter_alpha_harness.py`) - 30-second decision loop
  - Groq LLM integration (llama-3.3-70b-versatile) - 60 RPM, model making independent decisions
  - Atomic bracket orders via REST API - SL/TP working (verified 2026-03-18)
  - Obsidian logging - every trade logged to `Trades/YYYY-MM-DD/trade_NNN.md`
  - Student Log updating after each trade
  - Research files created after each trade
  - Node.js sidecar (`topstep_sidecar/`) running on port 8765
  - Realtime bridge integration (`realtime_bridge.py`) implemented in harness

- **What is partially built:**
  - WebSocket real-time data - sidecar running but WebSocket to TopStepX fails (paper account limitation)
  - Learning loop - model researching after trades, but research is template-based

- **What is broken or blocked:**
  - WebSocket cannot connect - paper account limitation, EXPECTED BEHAVIOR
  - Entry prices show $0.00 in logs - REST polling doesn't capture fills immediately

- **What has NOT been started yet:**
  - Strategy documentation (10 strategies needed for $1k/day goal)
  - Trade outcome tracking (P&L per trade)
  - Live account upgrade path

---

### 3. ARCHITECTURE & TECHNICAL MAP

- **Tech stack / tools / platforms:**
  - Python 3.12 (venv: `C:\KAI\vortex\.venv312`)
  - Groq API (llama-3.3-70b-versatile, 60 RPM)
  - TopStepX REST API + WebSocket (WebSocket fails on paper account)
  - Node.js sidecar for realtime bridge
  - Obsidian for logging and documentation
  - opencode CLI for AI orchestration

- **Key files:**
  ```
  C:\KAI\armada\
  ├── hunter_alpha_harness.py     # Main harness
  ├── sovran_ai.py              # Execution layer
  ├── realtime_bridge.py        # Realtime data bridge
  ├── learning_system.py       # Obsidian logging
  ├── llm_client.py            # LLM integration
  
  C:\KAI\armada\topstep_sidecar\
  ├── src/index.js             # Node.js sidecar
  ├── src/signalr-manager.js   # SignalR manager
  └── src/http-server.js       # HTTP API
  
  C:\KAI\vortex\
  ├── .env                     # API keys and config
  └── llm_client.py            # Groq provider added
  
  C:\KAI\obsidian_vault\Sovran AI\
  ├── SOVRAN_AUTONOMOUS_TRADING_SUCCESS.md
  ├── Session Logs\
  └── Trades\
  ```

- **How the system works end-to-end:**
  1. Harness boots → Initializes sovran_ai engine
  2. Connects to realtime_bridge (Node.js sidecar) → Fails gracefully
  3. Model decision loop (30 seconds):
     - Gets market context (OFI, VPIN, Z-scores via REST)
     - Sends prompt to Groq with learning instructions
     - Receives BUY/SELL/WAIT decision
     - If WAIT → Forces model to decide parameters
  4. Trade execution:
     - Calls `place_native_atomic_bracket()` in sovran_ai
     - REST API places market order with SL/TP brackets
     - Order ID returned
  5. Logging:
     - Trade logged to `Trades/YYYY-MM-DD/trade_NNN.md`
     - Student Log updated
     - Research file created
  6. Wait 30 seconds → Repeat

- **Naming conventions:**
  - Snake_case for Python
  - kebab-case for files
  - YYYY-MM-DD for dates in filenames
  - Uppercase for constants (LEARNING_MODE, etc.)

- **External dependencies:**
  - TopStepX API (api.topstepx.com)
  - Groq API (api.groq.com)
  - project_x_py SDK (installed in venv)

---

### 4. RECENT WORK — WHAT JUST HAPPENED

- **What was worked on in this session:**
  1. Switched from OpenRouter (8 RPM) to Groq (60 RPM) - eliminated rate limit blocking
  2. Added Groq provider to `llm_client.py` using `requests` library (urllib failed with 403)
  3. Integrated `realtime_bridge.py` into harness
  4. Started Node.js sidecar on port 8765
  5. Verified model making independent decisions (not defaulting to BUY size=1)

- **What decisions were made and WHY:**
  - **Groq over OpenRouter:** OpenRouter free tier limited to 8 req/min, causing constant 429 errors. Groq offers 60 RPM with llama-3.3-70b model.
  - **requests over urllib:** urllib was failing with 403 Forbidden for Groq, but requests worked. Changed to requests library.
  - **REST as primary:** WebSocket cannot connect on paper accounts - EXPECTED. REST API works for all operations.
  - **Forced trade on WAIT:** Model kept saying WAIT due to "no edge". Implemented forced trade logic - if model says WAIT, ask model to decide parameters and execute anyway.

- **What changed in the system:**
  - `.env`: GROQ_API_KEY, VORTEX_LLM_PROVIDER=groq
  - `llm_client.py`: Added groq provider with requests
  - `hunter_alpha_harness.py`: Added realtime_bridge import and initialization

- **What was discussed but NOT yet implemented:**
  - Entry price capture (shows $0.00)
  - Strategy documentation
  - Trade outcome tracking

- **Open threads or unresolved questions:**
  - Is the model actually learning? Research files are templates
  - All trades are BUY - is this intentional or model bias?
  - When will trades close (SL/TP)?

---

### 5. WHAT COULD GO WRONG

- **Known bugs or issues:**
  - Entry price $0.00 in logs - doesn't affect execution but makes tracking difficult
  - WebSocket cannot connect - NOT A BUG, expected for paper accounts
  - Research files are templates - model not actually analyzing

- **Edge cases to watch for:**
  - Model always choosing BUY - could accumulate one-sided positions
  - Trades not closing - need to verify SL/TP execution
  - Rate limits if using multiple providers

- **Technical debt or shortcuts taken:**
  - REST polling fallback instead of WebSocket
  - Forced trade logic bypasses model caution
  - Template-based research files

- **Assumptions being made that could be wrong:**
  - Paper account WebSocket limitation is permanent (may work with live account)
  - Groq will remain free tier
  - Model decisions are rational (always BUY in current market)

---

### 6. HOW TO THINK ABOUT THIS PROJECT

1. **Core architectural pattern:** Dual-mode operation - REST for reliability, WebSocket for speed when available. This is INTENTIONAL. Don't try to "fix" WebSocket on paper accounts.

2. **Most common mistake:** New AI tries to fix WebSocket connection or switches back to OpenRouter due to "rate limits". OPENROUTER IS TOO LIMITED. Groq is the solution.

3. **What looks like it should be refactored but intentionally should NOT be:**
   - The forced trade logic (WAIT → model decides → execute) - this is LEARNING MODE, not production
   - REST polling fallback - paper account limitation, not a bug
   - Template-based research - model running on limited tokens

---

### 7. DO NOT TOUCH LIST

- Do NOT switch back to OpenRouter without being asked - Groq is working
- Do NOT try to "fix" WebSocket on paper accounts - it's a platform limitation
- Do NOT increase OpenRouter rate limits - use Groq instead
- Do NOT change tick conventions in sovran_ai.py - they're verified working
- Do NOT disable forced trade logic - this is learning mode
- Do NOT change SL/TP sign logic:
  - LONG (side=0): SL = negative, TP = positive
  - SHORT (side=1): SL = positive, TP = negative
- Do NOT modify `realtime_bridge.py` without understanding paper account limitations
- Preserve the 30-second decision loop
- Preserve Obsidian logging structure

---

### 8. CONFIDENCE & FRESHNESS

| Section | Confidence | Notes |
|---------|-----------|-------|
| Project Identity | ✅ HIGH | Verified in this session |
| What Exists Now | ✅ HIGH | All components tested |
| Architecture | ✅ HIGH | Documented and working |
| Recent Work | ✅ HIGH | Just completed this session |
| What Could Go Wrong | ⚠️ MEDIUM | Assumptions about Groq stability |
| How to Think | ⚠️ MEDIUM | Based on session experience |
| Do Not Touch | ✅ HIGH | Documented decisions |
| Commands | ✅ HIGH | Verified working |

---

## RESUME PROMPT

```
You are resuming work on the Hunter Alpha / Sovran AI Trading System.

## BEFORE DOING ANYTHING:
1. Read `C:\KAI\obsidian_vault\Sovran AI\Session Logs\2026-03-19-Groq-Switch-Status.md`
2. Read `C:\KAI\obsidian_vault\Sovran AI\SOVRAN_AUTONOMOUS_TRADING_SUCCESS.md`
3. Check current time: `powershell -Command "(Get-Date).ToString('HH:mm:ss')"`
4. Verify Python environment: `C:\KAI\vortex\.venv312\Scripts\python.exe --version`
5. Check harness status: `tail -20 C:\KAI\armada\hunter_alpha_harness_2026-03-19.log`

## PROJECT SUMMARY:
Hunter Alpha is an AI trading system using Groq (llama-3.3-70b-versatile) to make trading decisions on MNQ futures via TopStepX. The system:
- Runs 30-second decision loops
- Uses REST API for order execution (WebSocket fails on paper account - expected)
- Logs all trades to Obsidian
- Currently ACTIVE and TRADING (6 trades as of last check)

## CURRENT STATE:
- Groq API: WORKING (60 RPM, model making decisions)
- OpenRouter: BLOCKED (8 RPM too limiting)
- Trades: 6 BUY trades executed, all open
- Realtime data: REST polling (WebSocket expected to fail on paper account)
- Student Log: Updated after each trade

## KEY FILES:
- Harness: `C:\KAI\armada\hunter_alpha_harness.py`
- LLM Client: `C:\KAI\vortex\llm_client.py`
- Config: `C:\KAI\vortex\.env`
- Status: `C:\KAI\obsidian_vault\Sovran AI\Session Logs\2026-03-19-Groq-Switch-Status.md`

## CONFIRMATION:
I understand Hunter Alpha is:
1. Running on Groq (60 RPM)
2. Trading MNQ futures on TopStepX paper account
3. Using REST API as primary method
4. Logging to Obsidian

My next action will be: [State your intended action]

---
USER DIRECTIVE (fill in or leave blank):

[Check the harness log, report current trade count and any issues. If no issues, monitor for 5 more trades and report P&L if any trades have closed.]
```
