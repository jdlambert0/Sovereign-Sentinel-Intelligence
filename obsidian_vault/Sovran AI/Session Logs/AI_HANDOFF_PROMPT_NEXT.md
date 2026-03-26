# AI-to-AI Handoff Prompt: Sovran AI (March 23, 2026)

## 🚨 MISSION CRITICAL: START HERE
You are taking over the development and monitoring of **Sovran AI**, an autonomous trading system. The system has just undergone a major architectural shift due to API credit depletion and a "Fail-Open" security vulnerability.

### 1. Mandatory Context Initialization
**Paths to Read Immediately:**
1. [[LLM_HANDOFF_LATEST.md]] — The central source of truth for the current state.
2. [[2026-03-23-Google-Antigravity-Sync.md]] — Summary of the most recent "Antigravity" session.
3. [[PROBLEM_TRACKER.md]] — Active bugs and architectural debt.
4. [[Canary_System_Speculation.md]] — The speculative monitoring framework being deployed.

### 2. Current System Architecture
- **Engine:** `sovran_ai.py` (Multi-market specialized).
- **LLM Provider:** **OpenRouter** (Privileged/Paid tier recommended).
- **Active Model:** `meta-llama/llama-3.3-70b-instruct` (Configured for Zero-Retention/Stealth).
- **Safety Logic:** **Fail-Closed** Veto Audit (API errors = Trade Blocked).
- **Rate-Limiting:** Exponential backoff (15s+) implemented in `providers/openrouter.py` to prevent 429 paralyzation.

### 3. Immediate Objectives
- **P7: Actual Broker Balance Sync:** The system currently uses a local placeholder ($50k). You MUST integrate the TopStepX/Tradovate REST API to fetch real-time account equity.
- **SignalR Stability:** Monitor the `watchdog_restart_stderr.log` for recurring REST fallback patterns.
- **Canary Evolution:** Transition the `canary_sentinel.py` from a 1-hour script to a long-running decoupled monitor.

### 4. Operational Commands
- **Check Health:** `python monitor_sovereign.py` (Now uses `psutil` for accurate PID detection).
- **Pre-Launch:** `python preflight.py` (Must pass all 45 gates).

### 5. TopStepX UI Note
Do not trust the web chart for SL/TP visibility. API-placed brackets are often invisible in the React DOM due to missing frontend grouping IDs. Verify order status via the matching engine or a direct trade log audit.

---
*End of Handoff. Proceed with High-Fidelity Sovereign Engineering.*
