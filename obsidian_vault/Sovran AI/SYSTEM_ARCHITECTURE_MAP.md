# Sovereign Sentinel System Map

## Core Operating Environment
**Primary Execution Directory:** `C:\KAI\armada\`  
**Python Environment:** `C:\KAI\vortex\.venv312\Scripts\python.exe`  
**Knowledge Base (Memory):** `C:\KAI\obsidian_vault\Sovran AI\`  

---

## 🏗️ Architecture & Component Map

### 1. The Trading Engine (The Sentinel)
- **`C:\KAI\armada\sovran_ai.py`**  
  *The absolute core of the Sovereign Sentinel.* This file contains the `AIGamblerEngine` and `Config` classes. It dictates the main trading loop, Kelly criterion sizing, bracket generation, and API dispatch logic.
- **`C:\KAI\armada\sovran_council_skill.py`**  
  *The Intelligence Layer.* Contains the LLM prompts and role-playing logic for the "Macro Strategist", "Microstructure Quant", and "Risk Management Officer" that dictate trade conviction.
- **`C:\KAI\armada\start_sovran.bat`** & **`C:\KAI\armada\enforce_venv_armada.py`**  
  *The Launchers.* Ensure the system boots natively in the background and explicitly uses the `vortex\.venv312` environment rather than system-level Python.

### 2. The Data & Execution Bridge
- **`C:\KAI\armada\projectx_broker_api.py`**  
  *Broker Truth.* Custom wrapper for TopstepX/ProjectX REST API authentication and fetching live PnL, resolving contract IDs, and obtaining session tokens.
- **`C:\KAI\armada\topstep_sidecar\`** (Node.js)  
  *Market Data Veins.* A standalone Node.js WebSocket service designed to bypass Python-level `SignalR` connection issues and feed Level 2 (Order Book) data into the Python engine.
- **`C:\KAI\armada\execute_test_bracket.py`**  
  *Direct execution hook.* A hardened script proving structural REST atomic bracket dispatches (SL/TP) directly to TopstepX.

### 3. The Shadow Codebase (Legacy / Parallel)
- **`C:\KAI\sovran_v2\`**  
  Contains remnants of the "Alpha Force" or previous iteration (`risk.py`). This directory may cause namespace collision or confusion during debugging, as the current Sentinel operates entirely out of `armada`.
- **`C:\KAI\vortex\`**  
  Contains `.env` and the virtual environment (`.venv312`) housing the broken/deprecated `project_x_py` package, which is slowly being phased out for native REST requests in `armada`.

### 4. Memory & Logging
- **`C:\KAI\obsidian_vault\Sovran AI\PROBLEM_TRACKER.md`**  
  The persistent issue queue for recursive engine debugging.
- **`C:\KAI\armada\_logs\`**  
  Contains heartbeat texts and real-time outputs of the `AIGamblerEngine` when running silently in the background.
