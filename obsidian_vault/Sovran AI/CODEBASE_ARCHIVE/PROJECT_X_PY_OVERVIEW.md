# project_x_py SDK Overview
**Purpose**: Explain SDK structure for future AI sessions
**Why Important**: TopStepX connection, order execution, market data

---

## 📁 SDK STRUCTURE

```
project_x_py/
├── __init__.py                      ← Main exports
├── trading_suite.py                 ← ⚠️ PRIMARY ENTRY POINT
├── client/
│   └── base.py                      ← Authentication
├── config.py                        ← Configuration
├── exceptions.py                    ← Custom exceptions
├── realtime/
│   ├── connection_management.py    ← ⚠️ WebSocket connections
│   ├── subscriptions.py            ← Market data subscriptions
│   └── events.py                   ← Event types
├── order_manager/
│   └── core.py                     ← ⚠️ Order placement
├── position_manager/
│   └── core.py                     ← Position tracking
├── realtime_data_manager/
│   └── core.py                     ← ⚠️ Market data (prices)
├── utils/
│   ├── environment.py              ← Env var handling
│   ├── error_handler.py            ← Error wrapping
│   └── logging.py                  ← Logging setup
└── venv312/Lib/site-packages/signalrcore/
    ├── websocket_transport.py      ← ⚠️ CRITICAL - WE MODIFIED THIS
    ├── websocket_client.py         ← ⚠️ WE MODIFIED THIS
    └── protocol/
        ├── json_hub_protocol.py   ← JSON parsing
        └── messagepack_protocol.py ← MessagePack parsing
```

---

## 🎯 KEY CLASSES YOU NEED TO KNOW

### 1. `TradingSuite` - Main Entry Point
**File**: `trading_suite.py`
**Usage**: Create once, access everything through it

```python
from project_x_py import TradingSuite

# Create connection
suite = await TradingSuite.create(["MNQ"])

# Access components
suite['MNQ'].data        # RealtimeDataManager (prices)
suite.orders             # OrderManager (place orders)
suite.positions          # PositionManager (track positions)
suite.instrument_id      # Contract ID
```

---

### 2. `RealtimeDataManager` - Market Data
**File**: `realtime_data_manager/core.py`
**Purpose**: Get price data (bid, ask, last)

```python
# Get current price
price = await suite['MNQ'].data.get_current_price()

# Get quote (more details)
quote = await suite['MNQ'].data.get_quote()
# Returns: {'bid': 24800, 'ask': 24801, 'last_price': 24800.5, ...}
```

---

### 3. `OrderManager` - Order Placement
**File**: `order_manager/core.py`
**Purpose**: Place trades, add SL/TP brackets

```python
# Place market order
response = await suite.orders.place_market_order(
    contract_id=suite.instrument_id,
    side=0,  # 0=BUY, 1=SELL
    size=2
)

# Add stop loss (AFTER order fills)
await suite.orders.add_stop_loss(
    order_id=response.orderId,
    points=50  # 50 points = $100 for MNQ
)

# Add take profit
await suite.orders.add_take_profit(
    order_id=response.orderId,
    points=25  # 25 points = $50 for MNQ
)
```

---

### 4. `PositionManager` - Position Tracking
**File**: `position_manager/core.py`
**Purpose**: Track open positions, get P&L

```python
# Get all positions
positions = await suite.positions.get_all_positions()

# Find specific position
for pos in positions:
    if pos.contractId == suite.instrument_id:
        print(f"Size: {pos.size}, Entry: {pos.averagePrice}")
```

---

### 5. `connection_management.py` - WebSocket
**File**: `realtime/connection_management.py`
**Purpose**: Manage WebSocket connections

```python
# Connect (happens automatically in TradingSuite.create)
await suite.realtime.connect()

# Check status
is_connected = suite.realtime.is_connected()

# Subscribe to market data
await suite.realtime.subscribe(['MNQ'])
```

---

## 🔧 THE CRITICAL FILES WE MODIFIED

### 1. `websocket_transport.py` (signalrcore)
**Path**: `site-packages/signalrcore/transport/websockets/websocket_transport.py`
**Lines Modified**: 85-113

**Problem**:
- TopStepX sends MessagePack (binary) after JSON handshake
- signalrcore expected all messages as JSON text
- Binary frames caused: `JSONDecodeError`

**Solution**:
```python
def on_message(self, app, raw_message):
    # Check if message is bytes (MessagePack)
    if isinstance(raw_message, bytes):
        import msgpack
        unpacked = msgpack.unpackb(raw_message, raw=False, ...)
        raw_message = json.dumps(unpacked)
    # Continue processing as JSON...
```

**⚠️ WARNING**: This patch will be overwritten if you:
- Run `pip install --upgrade signalrcore`
- Recreate virtual environment
- Copy files to new machine

**See**: `Bug Reports/WEBSOCKET_FIX_REFERENCE.md`

---

### 2. `websocket_client.py` (signalrcore)
**Path**: `site-packages/signalrcore/transport/websockets/websocket_client.py`
**Lines Modified**: 67-79

**Problem**:
- UTF-8 decode fails on binary MessagePack
- SDK threw UnicodeDecodeError

**Solution**:
```python
def prepare_data(self, data):
    if self.is_binary:
        return data
    try:
        return data.decode(DEFAULT_ENCODING)
    except UnicodeDecodeError:
        # Return bytes instead of throwing error
        return data
```

---

## 📊 DATA FLOW

```
TOPSTEPDX SERVER
       │
       │ WebSocket (binary MessagePack)
       ▼
websocket_transport.py (PATCHED - converts MessagePack to JSON)
       │
       │ JSON messages
       ▼
connection_management.py
       │
       ├──► subscriptions.py ──► RealtimeDataManager ──► Your Code
       │                                (get_current_price)
       │
       ├──► order_manager.py ──► TradingSuite.orders
       │                     (place_market_order, add_stop_loss)
       │
       └──► position_manager.py ──► TradingSuite.positions
                              (get_all_positions)
```

---

## 🔍 HOW TO DEBUG

### Enable Debug Logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check WebSocket Status:
```python
# In sovran_ai.py or tests
realtime = suite.realtime
print(f"Connected: {realtime.is_connected()}")
print(f"User hub: {realtime.user_connected}")
print(f"Market hub: {realtime.market_connected}")
```

### Log Order Responses:
```python
response = await suite.orders.place_market_order(...)
logger.info(f"ORDER RESPONSE: {vars(response)}")
```

### Check Quote Data:
```python
quote = await suite['MNQ'].data.get_quote()
logger.info(f"QUOTE: {quote}")
```

---

## ❌ COMMON ERRORS

### 1. `JSONDecodeError: Expecting value`
**Cause**: Binary MessagePack not converted to JSON
**Fix**: Check `websocket_transport.py` patch (lines 85-113)

### 2. `ValueError: Required environment variable 'PROJECT_X_API_KEY' not found`
**Cause**: Env vars not loaded
**Fix**: Load `.env` file before importing project_x_py

### 3. `UnicodeEncodeError: 'charmap' codec can't encode`
**Cause**: Emojis in SDK logging on Windows
**Fix**: Configure logging with UTF-8:
```python
sys.stdout.reconfigure(encoding="utf-8")
```

### 4. `WebSocket timeout after 30s`
**Cause**: Paper account limitations or network issues
**Fix**: System continues in REST polling mode (slower but works)

---

## 📝 API REFERENCE

### TradingSuite.create()
```python
suite = await TradingSuite.create(
    symbols: List[str],  # ["MNQ", "ES"]
    config: Optional[Config] = None
)
```

### place_market_order()
```python
response = await suite.orders.place_market_order(
    contract_id: str,  # e.g., "CON.F.US.MNQ.M26"
    side: int,         # 0=BUY, 1=SELL
    size: int,          # Number of contracts
    purpose: str = "open"  # "open" or "close"
)
# Returns: PlaceOrderResponse with orderId
```

### add_stop_loss()
```python
await suite.orders.add_stop_loss(
    order_id: str,     # From place_market_order response
    points: float,     # Stop distance in points
    type: str = "stop" # "stop" or "trailing"
)
```

### add_take_profit()
```python
await suite.orders.add_take_profit(
    order_id: str,     # From place_market_order response
    points: float,     # Target distance in points
)
```

### get_all_positions()
```python
positions = await suite.positions.get_all_positions()
# Returns: List of Position objects
# Each has: contractId, size, averagePrice, marketValue
```

### get_current_price()
```python
price = await suite['MNQ'].data.get_current_price()
# Returns: float (last trade price)
```

### get_quote()
```python
quote = await suite['MNQ'].data.get_quote()
# Returns: dict with bid, ask, last_price, high, low, etc.
```

---

## 🎓 TIPS FOR FUTURE SESSIONS

1. **Always check TradingSuite first** - it's the main entry point
2. **Log order responses** - debug SL/TP issues
3. **Understand the bimodal protocol** - JSON handshake, MessagePack data
4. **Keep WebSocket patch backed up** - it gets overwritten
5. **Use REST as backup** - works when WebSocket fails

---

## 📚 MORE INFO

- **Bug History**: `Bug Reports/COMPLETE_BUG_HISTORY.md`
- **WebSocket Fix**: `Bug Reports/WEBSOCKET_FIX_REFERENCE.md`
- **Main Code**: `CODEBASE_ARCHIVE/sovran_ai/sovran_ai.py`

---

*Document created: 2026-03-18*
*For AI session reference*
