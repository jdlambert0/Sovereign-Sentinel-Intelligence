# System Resources & Operational Limits (Phase 27)

## 1. Trade Cooling Periods
The Sovran AI system uses a "Turn-Based" execution model:
- **Primary Interval (`loop-interval-sec`):** The delay between trade evaluations. Default is **30s** (per relaunch command) or **45s** (config default).
- **Evaluation Loop:** Each engine waits for the full interval before calling the LLM or evaluating a trade cycle.
- **Circuit Breakers:**
  - `max_consecutive_losses`: Default **3**. Stops the engine if 3 losses occur in a row.
  - `max_daily_loss`: Default **$900**. Stops all trading if hit.
  - `GlobalRiskVault`: Hard-locks all engines at **-$450** total aggregate loss.

## 2. Resource Footprint (9-Slot Grid)
- **CPU:** Near **0%** idle; minor spikes during LLM payload generation every 30s. Well within the 70% OS stability mandate.
- **RAM:** Estimated **1.0 - 1.5 GB** total. Python `asyncio` handles 9 concurrent tasks efficiently within a single process.
- **Network/API:** 
  - **Market Data:** 3 WebSocket streams (MNQ, MES, MYM) + 1 User Data stream. Shared across all 9 engines.
  - **REST API Calls:** ~18-30 calls per minute (LLM + Orders). This is very safe for TopStepX and OpenRouter limits.

## 3. Position Brackets (UI vs API)
- **Status:** Brackets are placed via API (Atomic Brackets).
- **UI Visibility:** Since "Position Brackets" are now ON in your settings, TopStepX will visualize the SL/TP lines on the chart when they are attached to an open position, even if "Auto-Apply" is OFF (which is correct—the AI maintains control).

## 4. Weekend / Market-Closed Behavior
- **Data Freshness Guard:** The system checks `time.time() - last_update_time`. If quotes are >30s old (which they will be all weekend), the system skips all LLM and Trade calls.
- **Result:** The system will run in an "Idle Heartbeat" state until 5 PM CT Sunday, consuming almost no resources and making **zero** billable LLM calls.

---
*Status: AUDIT COMPLETE | System Ready for Sunday Open | Date: March 20, 2026*
