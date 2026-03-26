# 📜 Historical Success: 2026-01-12 L2 WebSocket Setup

**Status:** VERIFIED HISTORICAL SUCCESS (March 12, 2026)
**Log Evidence:** `C:\KAI\vortex\logs\fleet_manager.log` @ 17:57:34
**Achievement:** 100% Reliable L1 Quote + L2 Depth receipt.

---

## 🏗️ The "Direct WS" Architecture
On March 12, the system achieved stability by **bypassing the project-x-py SDK's managed websocket** and using a raw `signalrcore` connection.

### 1. Connection Parameters (The Secret Sauce)
The system used `HubConnectionBuilder` with these specific flags:
- **Skip Negotiation:** `True` (CRITICAL)
- **Token:** Fresh JWT passed in query string `?access_token={jwt}`
- **URL:** `https://rtc.topstepx.com/hubs/market`
- **Builder Code:**
```python
market_conn = (
    HubConnectionBuilder()
    .with_url(market_url, options={"skip_negotiation": True})
    .with_automatic_reconnect({
        "type": "raw", 
        "keep_alive_interval": 5,
        "reconnect_interval": 3, 
        "max_attempts": None
    })
    .build()
)
```

### 2. Manual Subscriptions
Instead of relying on SDK feature flags, the code manually sent subscription commands after the `on_open` event:
- `market_conn.send("SubscribeContractQuotes", [cid])`
- `market_conn.send("SubscribeContractTrades", [cid])`
- `market_conn.send("SubscribeContractMarketDepth", [cid])`

### 3. Depth (L2) Message Schema
The system successfully parsed `GatewayDepth` messages in this specific format:
- **Structure:** `[contractId, [list_of_entries]]`
- **Entry Type Mapping:**
  - `1, 10`: Ask / NewBestAsk
  - `2, 9`: Bid / NewBestBid
- **Handler:** `vortex_v2.py` lines 8192-8210 (Archived version).

---

## 🚫 Why It's Currently Broken (March 19)
The switch to the `project-x-py` SDK as a wrapper for connections introduced a "negotiation" phase and a "Managed WebSocket" layer that:
1.  **Fails on Protocol:** TopStepX now frequently pushes **MessagePack (binary)** frames. The SDK expects JSON by default.
2.  **Negotiation Conflicts:** The SDK tries to negotiate the hub connection, which often hangs or results in the `Internal error: Realtime client not connected`.
3.  **Patch Drift:** The global `WebsocketTransport` patch currently in `sovran_ai.py` is trying to catch these binary frames and force them into JSON strings. This is a "brute force" fix that often results in `JSONDecodeError` during the initial handshake.

## 💡 Recommendation for Other AI Agents
To restore L2 data, **revert to the "Direct WS" pattern** found in `vortex_v2.py` (Archive):
1.  Use raw `signalrcore`.
2.  Set `skip_negotiation=True`.
3.  Manually handle the `GatewayDepth` list-of-dicts parsing.
4.  Do NOT use the SDK's `TradingSuite.create(features=['orderbook'])` until the underlying SDK transport supports MessagePack natively without patches.

---
*Created: 2026-03-19 by Antigravity*
