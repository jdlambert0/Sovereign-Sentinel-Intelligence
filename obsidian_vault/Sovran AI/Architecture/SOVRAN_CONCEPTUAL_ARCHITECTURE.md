# Sovran AI: Conceptual Node Architecture

This document maps the core architecture of the Sovran AI (V3) trading system. Rather than providing a raw code dump, this conceptual map outlines the interfaces, data structures, state machines, and key algorithms that govern the system.

## 1. The Core Engine (`AIGamblerEngine`)

The engine is the central nervous system of the bot, orchestrating market data ingestion, AI decision-making, risk management, and order execution.

### Key Algorithms & Logic
*   **The Sovereign Learning Loop:** Employs an LLM (Claude/Gemini) to evaluate Level 2 order flow data every `loop_interval_sec`. The LLM's response dictates the trading action (BUY, SELL, WAIT) and provides a "Sovereign Briefing."
*   **Kelly Sizing Engine:** Calculates optimal position sizing based on rolling win rate, rolling reward-to-risk (RR) ratio, and an institutional hardening parameter (`kelly_fraction`). It sizes the bet strictly against the available "headroom" within the trailing drawdown floor.
*   **Ensemble Consensus (Council of One):** The engine queries multiple LLMs concurrently. If there are conflicting signals (e.g., both BUY and SELL votes), the engine defaults to WAIT. If a clear consensus emerges, the highest confidence signal dictates the trade.

### Critical Interfaces
*   `retrieve_ai_decision()`: Gathers market context (OFI, VPIN, Price, Range), assembles the prompt, queries the ensemble, parses JSON responses, and enforces the consensus rules.
*   `calculate_size_and_execute(decision)`: Takes the AI's decision, applies risk gates, calculates the Kelly criteria for position sizing, and triggers order placement via REST or SDK fallback.

## 2. The Bridge (Data & Execution)

The system utilizes a hybrid approach for interacting with the TopStepX (ProjectX) platform, bridging real-time data ingestion with RESTful execution capabilities.

### Interfaces & Data Structures
*   **Market Data Bridge (Direct WS):** Establishes a pure Python WebSocket connection to the TopStepX SignalR hubs to receive high-frequency Level 1 and Level 2 data without relying on the heavier SDK wrapper.
*   **Execution Fallback Chain:**
    1.  **Native Atomic Bracket (REST):** The primary execution method. Sends a complete payload to `https://api.topstepx.com/api/Order/place` containing the entry side, size, and configured Stop Loss/Take Profit brackets defined in ticks.
    2.  **Legacy SDK Path:** If the REST call fails, the system falls back to placing a market entry via the SDK, waiting 5 seconds for a fill confirmation, and then manually placing OCO-linked Stop Loss and Take Profit orders.

## 3. The State Manager (`GamblerState` & `TrailingDrawdown`)

State management is localized to ensure the bot can recover gracefully from crashes and accurately track its performance against prop firm rules.

### Key Data Structures
*   `GamblerState` (Dataclass): Stores the `bankroll_remaining`, `total_pnl`, `daily_pnl`, rolling win/loss statistics, and the currently `active_trade`. It persists state to a local JSON file (`_data_db/sovran_ai_state_MNQ.json`).
*   `TrailingDrawdown` (Class): Implements the critical TopStepX drawdown logic. It tracks the `trailing_high_water_mark` (HWM). As total PnL rises, the `trailing_drawdown_floor` rises with it ($4500 below the HWM), but never decreases.

### State Machines
*   **Daily Reset Protocol:** The engine monitors the system clock. Upon detecting a new calendar day (`now_ct.date() != self._last_trading_date`), it resets `daily_pnl` and `consecutive_losses` to zero.
*   **Trade Lifecycle (`active_trade`):**
    *   `OPEN`: Trade executed, awaiting exit criteria.
    *   `CLOSED`: Trade exited, PnL calculated, state updated, memory logged to Obsidian.
