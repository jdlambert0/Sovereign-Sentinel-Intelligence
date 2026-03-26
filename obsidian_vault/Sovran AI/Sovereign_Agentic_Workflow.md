# 🚀 Sovereign Agentic Workflow: The Antigravity Protocol

This document defines the high-fidelity operational flow for **Autonomous Agentic Trading**. Unlike a background bot, this workflow focuses on the **AI Agent as the active Pilot**, executing complex multi-step turns without stalling for user prompts.

## 🔄 The Continuous Turn Cycle

The protocol MANDATES that the Agent chains all four phases into a single execution turn to maintain market responsiveness.

### 1. Observation (The Tape)
- **Tool**: `run_command` (polling `sovran_early_boot.log`).
- **Focus**: Real-time WebSocket telemetry (`GatewayUserPosition`, `GatewayUserOrder`), Order Flow Imbalance (OFI), and VPIN metrics.
- **MANDATE**: **NEVER use REST polling data for trading or observation.** The Direct WebSocket is the only source of truth authorized for the Sovereign Hunt.
- **Goal**: Establish the "Ground Truth" of the current account state and market microstructure.

### 2. Research & Hypothesis (The Edge)
- **Tool**: `search_web`.
- **Focus**: Global macro trends, mathematical models (LPPL, Kelly), and institutional footprints.
- **Goal**: Synthesize raw data into a falsifiable trading thesis. Document this in the [[Traders_Diary]].

### 3. Execution (The Strike)
- **Tool**: `write_to_file` (targeting `manual_commands.json`).
- **Focus**: Strategic bracket placement (SL/TP) using volatility-adjusted metrics (e.g., ATR or LPPL volatility expansion).
- **Goal**: Commit the trade to the exchange via the Direct WS bridge.

### 4. Reflection (The Evolution)
- **Tool**: `multi_replace_file_content`.
- **Focus**: Match the outcome against the hypothesis.
- **Goal**: Log lessons learned into the [[Traders_Diary]] to update the Agent's "Recursive Alpha" (self-correcting logic).

## 🛡️ Operational Safeguards

- **No User Stalling**: The Agent must NOT hand control back to the USER via `notify_user` during an active hunt cycle unless a catastrophic system failure (e.g., API 403, Socket Closure) occurs.
- **Static Anchoring**: Periodic sync with `projectx_broker_api.py` to reconcile drift and hard-code localized PnL baselines to bypass persistent state corruption.
- **Unicode Armor**: Strict scrubbing of emojis and non-ASCII characters in execution logs to prevent terminal crashes.

## ⚠️ Known Issues: The Session Collision

TopStepX enforces a **Single Session WebSocket** policy. 
- **The Conflict**: Running `projectx_broker_api.py` (REST) simultaneously with `sovran_ai.py` (WS) or keeping the Web Dashboard/Mobile App open will trigger an immediate `GatewayLogout` for the engine.
- **The Protocol**: Before launching the Hunt, the Agent must aggressively terminate all local `python`, `pwsh`, and `cmd` processes and enforce a 60-second cooldown to let server-side states expire.

---
*Protocol established by Antigravity Agentic Hub - 2026-03-24.*
