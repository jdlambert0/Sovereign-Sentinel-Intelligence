# 📥 [FIRST READ] Sovran Hunt Master Entry Point

## Current Status (INTELLIGENT TRADER REDESIGN - 20:30 CT)
- **Account State**: **FLAT** (No Exposure).
- **Architecture**: **AI-as-Intelligent-Trader** (Temporal Buffer + Thesis Persistence + WATCH mode).
- **Engine Protocol**: **NEVER use REST polling.** Direct WebSocket only.
- **Gemini CLI Bridge**: [[Architecture/GEMINI_CLI_BRIDGE]] — How to run and resume from Gemini CLI.
- **First Principles Analysis**: [[Architecture/FIRST_PRINCIPLES_AI_TRADER]]


## 📡 System Identity: SOVRAN HUNT
**Paradigm**: Natural Language Command Execution (NLCE).
**Objective**: LLMs directly hunt for trades and execute via the high-speed trade bridge.

---

## 🛠️ How to Trade (For LLMs)
To execute a trade, you MUST use the **Manual Command Bridge**. Do not wait for autonomous loops.

### 2. Formulate & Execute ("Infinite Turn" Paradigm)
Draft the trade via `C:\KAI\armada\sovran_ai.py`. **DO NOT STOP AND WAIT FOR PROMPTS.** You must maintain an "Infinite Turn," continuously chaining tool calls (Observation -> Hypothesis -> Execution -> Reflection) over a multi-hour span. Intelligently manage the trade from entry to exit in a tight, unbroken loop using your token memory.

### 3. The Singleton & Failsafe Rules
- **Singleton Lock:** You MUST govern your own execution so that you NEVER run auxiliary REST scripts (`projectx_broker_api.py`, `check_active_positions.py`) while the primary WebSocket stream (`sovran_ai.py`) is running. This will trigger a `GatewayLogout` collision.
- **Fail-Flatten Dead Man's Switch:** If the Direct WebSocket disconnects, logs out, or fails for ANY reason, you must immediately execute `emergency_flatten.py` to wipe all exposure, then wait for the 5-minute server cool-down. DO NOT rely on REST polling.
```json
{
    "timestamp": <current_unix>,
    "action": "BUY",
    "symbol": "MNQ",
    "size": 10,
    "sl_ticks": 100,
    "tp_ticks": 50,
    "reasoning": "Standard Sovran Hunt execution at liquidity zone.",
    "processed": false
}
```

### 3. Execute & Verify
- Write to `manual_commands.json`.
- Run `C:\KAI\armada\sovran_ai.py` (ensure environment keys `PROJECT_X_API_KEY` and `PROJECT_X_USERNAME` are set).
- **Verify via API**: Run a trade history query (e.g., `audit_trade_api.py`) to confirm the fill and final PnL. Avoid "grepping" through large logs unless the API fails.
- **Phase D: Reflection**: Log the rationale and result to the [[Traders_Diary.md]].

---

## 🚫 Legacy Systems (DO NOT USE)
- **OpenRouter Veto**: Deprecated. The LLM is the authority; the manual bridge bypasses credit blocks.
- **Autonomous Background Loops**: Phased out. Execution is now intentional and command-driven.

---

## 📂 Key Resources
- **Core Engine**: `C:\KAI\armada\sovran_ai.py`
- **Manual Bridge**: `C:\KAI\armada\_data_db\manual_commands.json`
- **Bug Inventory**: [[Bugs/BUG_INVENTORY_SYNC]]
- **Problem Tracker**: [[Bugs/PROBLEM_TRACKER]]
