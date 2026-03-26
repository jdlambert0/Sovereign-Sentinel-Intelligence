# Sovran Hunt: Real-Time Master Hunter Strategy

## 🎯 The Vision
To transform the trading system into a high-speed, intentional "Hunter" that identifies institutional liquidity zones, detects iceberg orders, and executes trades with zero-latency synchronization. This system will move away from 30s REST polling to real-time SignalR (WebSocket) streaming.

## 📡 The Real-Time Stack
The **Sovran Hunt** architecture leverages the `project_x_py` V3 SDK's `TradingSuite` to unify all data streams:

1.  **L2 Orderbook (Market Depth)**:
    - **Component**: `suite.orderbook`
    - **Capability**: Real-time bid/ask depth up to 100 levels.
    - **Hunter Logic**: Detects **Iceberg Orders** and **Order Clusters** to identify where major players are hiding volume.
2.  **Trade Flow (Tick-by-Tick)**:
    - **Component**: `suite.data` (RealtimeDataManager)
    - **Capability**: Processes every single execution (tick) with millisecond precision.
    - **Hunter Logic**: Tracks **Cumulative Delta** to identify aggressive buying/selling pressure before price moves.
3.  **Unified Event Bus**:
    - **Component**: `suite.events`
    - **Hook**: `@suite.events.on(EventType.MARKET_DEPTH_UPDATE)`
    - **Advantage**: Zero lag between a market change and the Hunter's reaction.

---

## 🛠️ The Hunter Process (Step-by-Step)

### Phase 1: Market Context (Near Real-Time)
- **Tool**: `get_bars(interval=1, unit=2)` (1-minute bars).
- **Goal**: Establish the high-level bias (Trend, Support/Resistance).

### Phase 2: The Hunt (Real-Time L2)
- **Tool**: `suite.orderbook.detect_iceberg_orders()` + `get_market_imbalance()`.
- **Logic**: 
    - If Imbalance > 1.5 and Iceberg detected at Bid, the Hunter identifies a "Long Liquidity Zone".
    - If aggressive selling (Red Delta) hits the Iceberg without breaking it, a "Buy Signal" is generated.

### Phase 3: Intentional Execution
- **Tool**: `manual_commands.json` (The Bridge).
- **Logic**: The LLM Hunter writes the order parameters (Size, SL, TP) based on the L2 context.
- **Verification**: The Hunter listens for `EventType.ORDER_FILLED` via the WebSocket to confirm immediate entry.

### Phase 4: Precision Management
- **Tool**: WebSocket `PositionUpdate`.
- **Logic**: Rather than polling `search_open_positions()`, the Hunter reacts **instantly** to position changes.
- **Final Audit**: Once the position closure event is received, `client.search_trades()` is queried for the official ledger entry (The Source of Truth).

---

## 🔍 Master API Usage (For LLMs)

### 1. Initializing the Hunter
```python
suite = await TradingSuite.create(
    "MNQ", 
    features=["orderbook", "risk_manager"], 
    timeframes=["1min", "5min"]
)
```

### 2. Hunting for Profit (L2 Depth)
```python
# Check for institutional walls
imbalance = await suite.orderbook.get_market_imbalance(levels=5)
# Detect hidden liquidity
icebergs = await suite.orderbook.detect_iceberg_orders()
```

### 3. Real-Time Monitoring (No Polling)
```python
@suite.events.on(EventType.POSITION_UPDATE)
async def handle_position(event):
    data = event.data
    if data['size'] == 0:
        print("Trade Closed. Triggering final audit.")
```

---

## 🚧 What is Still Lacking?
1.  **Low-Latency Command Bridge**: `manual_commands.json` is a file-based bridge which adds ~50-100ms disk I/O lag. For "Master Hunter" status, moving to a shared memory or socket-based command handler would be ideal.
2.  **L2 Visualization**: The Obsidian logs currently track PnL but not orderbook depth clusters. We need a "Liquidity Snapshot" in the trade logs.
3.  **Automated SL/TP Hardening**: Ensure the `risk_manager` feature in `TradingSuite` is fully configured to prevent "fat finger" errors in the manual bridge.

## 🚀 Future Roadmap
- [ ] Implement `LiquiditySnapshot` in Obsidian `Trade_Logs`.
- [ ] Migrate `manual_commands.json` to an async `CommandQueue`.
- [ ] Add `detect_spoofing()` logic to the Hunter's pre-flight checklist.
