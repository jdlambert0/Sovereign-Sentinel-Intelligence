# Sovran AI — Full Architecture & SL/TP Audit
*Status: Live-Only Single-Process Multi-Market Architecture*

## 1. The Core Loop
The system operates asynchronously, maintaining a single live WebSocket connection to TopStepX per engine. The core `monitor_loop` runs every 30 seconds for each symbol (MNQ, MES, M2K), staggered by 10 seconds to avoid API bursts.
1. **Data Ingestion:** L1 Quotes and L2 Trade Ticks flow into `handle_quote` and `handle_trade`.
2. **Signal Generation:** OFI (Order Flow Imbalance) and VPIN (Informed Trading) are calculated continuously on a rolling window.
3. **Execution Gate:** If the market is too quiet (Micro-Chop Gate), the spread is too wide (Spread Gate), or data is stale (Silent WS Gate), the LLM call is bypassed entirely.
4. **AI Decision:** State is passed to the Ensemble (Llama 70B + Gemini). They must achieve consensus (BUY/SELL) with >0.50 confidence.

## 2. Stop Loss (SL) & Take Profit (TP) Management

The system uses a **Hybrid Delegate Model** for Risk Management. It delegates execution to the exchange, but tracks state locally.

### Step 1: AI Parameter Generation
The AI decides the initial risk parameters. In its JSON response, it must provide `stop_points` and `target_points`.
*Example: The prompt strictly instructs the AI to look at `session_range` and maintain a minimum 2:1 Reward-to-Risk ratio.*

### Step 2: Bracket Order Execution (The TopStepX Handoff)
Once the trade passes the Kelly Sizer (determining contracts), the `calculate_size_and_execute` function does this:
```python
stop_price = entry_price - stop_pts if direction == "LONG" else entry_price + stop_pts
target_price = entry_price + target_pts if direction == "LONG" else entry_price - target_pts

bracket = await suite.orders.place_bracket_order(
    ..., stop_loss_price=stop_price, take_profit_price=target_price, ...
)
```
**CRITICAL STRENGTH:** The system uses `place_bracket_order` instead of managing stops in Python. The moment this order is accepted successfully, **TopStepX's matching engine owns your Stop Loss.** 
* If your internet drops? TopStepX executes the stop.
* If the LLM API crashes? TopStepX executes the stop.
* If Windows reboots? TopStepX executes the stop.

### Step 3: Local Tracking (`mock_position_check`)
Because the bot currently does **not** process TopStepX `ORDER_STATUS_UPDATE` WebSocket callbacks, it must figure out when a trade closes by watching the live price feed.
Every tick, `mock_position_check` runs:
1. Is `current_price` >= `target_price`? → Mark Closed as Win.
2. Is `current_price` <= `stop_price`? → Mark Closed as Loss.
3. Upon closure, calculate PnL, update local `GamblerState.total_pnl`, compute the new Trailing Drawdown floor, and save the state file.

**THE VULNERABILITY (Slippage Desync):** 
Because closure is tracked *locally* based on L1 feed crossover rather than broker confirmation, your local PnL will drift slightly from actual TopStepX PnL due to slippage (e.g., local says "-10.0 pts", actual fill was "-10.25 pts"). This is acceptable for analytics, but means your local Trailing Drawdown tracker might be off by a few dollars compared to reality.

## 3. Position Recovery & Flattening

### Startup Orphan Recovery
If the script restarts while a trade is active on the exchange, the `recover_active_position` function queries TopStepX.
If it finds an open trade, it reconstructs a local tracker with a strict **15-point emergency SL** and **30-point emergency TP**. 
*Note: The actual original bracket order still exists on TopStepX and will fire exactly as originally programmed. The emergency local tracker simply ensures the Python loop knows it's in a trade so it resumes tracking.*

### The 3:08 PM CT Force Flatten
Every tick, `check_force_flatten` checks the time. At 15:08:00 CT, it fires a ruthless, blind command to the API:
```python
await self.suite.positions.close_all_positions()
```
This guarantees no positions cross the 3:10 PM margin settlement window, ensuring compliance with Prop Firm overnight rules.

## Summary Verdict
1. **Risk Execution:** Bulletproof. Handled natively by TopStepX exchange brackets.
2. **State Tracking:** Functional, but relies on local mock pricing rather than broker confirmation events.
3. **Safety Fallbacks:** Excellent. Force flatten and orphan recovery are active and tested.
