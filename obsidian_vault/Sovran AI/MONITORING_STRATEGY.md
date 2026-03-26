# SOVRAN HUNT: Active Trade Monitoring Strategy

## 📡 The Monitoring Paradigm
To ensure 100% execution reliability, Sovran Hunt uses a **dual-layer monitoring strategy** that prioritizes API "Source of Truth" over log-based heuristics.

---

### 1. Active Position Tracking (The "Source of Truth")
- **Method**: REST Polling via `client.search_open_positions()`.
- **Logic**: Every 30 seconds, the system queries the broker for all open positions.
- **Goal**: Detect if a position is open, its current size, and unrealized PnL.
- **Closure Event**: If the position list is empty, the trade is marked as **Closed**.

### 2. Execution Audit (The "Fill History")
- **Method**: REST Polling via `client.search_trades()`.
- **Logic**: Once a position closure is detected, the system searches for the corresponding "SELL" or "BUY" fill event to calculate the final realized PnL.
- **Advantage**: This identifies if the trade hit a Stop Loss (SL) or Take Profit (TP) bracket by matching prices against the initial order parameters.

### 3. Safety Circuit Breakers (The "Watchdog")
- **Method**: `monitor_sovereign.py` heartbeat check.
- **Logic**: If the engine stops updating its heartbeat for >60s, a system-level alert is triggered.
- **Action**: The watchdog attempts to restart the engine to regain synchronization with the broker.

---

## 🛠️ Why This Works
- **WebSocket (SignalR)**: Fast, but can "miss" messages during network drops.
- **REST (HTTP)**: Slower, but **state-persistent**. If the trade happened, the REST API *will* have the record.
- **Intentional Audit**: By pointing the LLM directly to these endpoints, we eliminate the need to "grep" through gigabyte-scale logs.
