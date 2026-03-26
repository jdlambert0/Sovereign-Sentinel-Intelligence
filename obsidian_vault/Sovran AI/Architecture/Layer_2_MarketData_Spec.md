# Layer 2: The Eyes (Market Data Pipeline) — Technical Specification

> **Author**: CIO Agent  
> **Date**: 2026-03-25  
> **For**: Coding Agent  
> **Depends On**: Layer 0 (`src/broker.py`) for auth token  
> **Output Files**: `src/market_data.py`, `tests/test_market_data.py`

---

## 1. Overview

The Eyes provide clean, real-time market data and derived signals for the AI brain. This layer connects to the TopStepX Market Hub via WebSocket (SignalR JSON protocol), maintains a rolling temporal buffer of price data, and computes derived signals (ATR, VPIN, OFI, regime detection).

**Critical constraint**: Only ONE WebSocket connection is allowed per account. This layer owns that connection.

## 2. SignalR Protocol Reference

### Connection
- **URL**: `wss://rtc.topstepx.com/hubs/market?access_token={jwt_token}`
- **Handshake**: Send `{"protocol":"json","version":1}\x1e` immediately on open
- **Record separator**: Every JSON message ends with `\x1e` (ASCII 30)
- **Ping**: Server sends type-6 messages as keep-alive. Client should send pings every 15 seconds.

### Subscriptions (Type 1 Invocations)
```json
{"type":1,"target":"SubscribeContractQuotes","arguments":["CON.F.US.MNQM26"],"invocationId":"q1"}\x1e
{"type":1,"target":"SubscribeContractTrades","arguments":["CON.F.US.MNQM26"],"invocationId":"t1"}\x1e
{"type":1,"target":"SubscribeContractMarketDepth","arguments":["CON.F.US.MNQM26"],"invocationId":"d1"}\x1e
```

### Incoming Events
**GatewayQuote** (L1 data):
```json
{"type":1,"target":"GatewayQuote","arguments":["CON.F.US.MNQM26",{
  "contractId":"CON.F.US.MNQM26",
  "lastPrice":18200.25,
  "bestBid":18200.00,
  "bestAsk":18200.50,
  "volume":123456,
  "timestamp":"2026-03-25T15:30:00Z"
}]}
```

**GatewayTrade** (individual ticks):
```json
{"type":1,"target":"GatewayTrade","arguments":["CON.F.US.MNQM26",[{
  "price":18200.25,
  "volume":1,
  "side":0,
  "timestamp":"2026-03-25T15:30:00.123Z"
}]]}
```

**GatewayMarketDepth** (L2 book):
```json
{"type":1,"target":"GatewayMarketDepth","arguments":["CON.F.US.MNQM26",{
  "bids":[{"price":18200.00,"size":45},{"price":18199.75,"size":32},...],
  "asks":[{"price":18200.50,"size":38},{"price":18200.75,"size":27},...],
  "timestamp":"2026-03-25T15:30:00Z"
}]}
```

### Message Types
- 1 = Invocation (subscription call or incoming event)
- 3 = Completion (response to invocation, may contain error)
- 6 = Ping (keep-alive, respond with `{"type":6}\x1e`)

## 3. Data Structures

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import time

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    CHOPPY = "choppy"
    BREAKOUT = "breakout"
    LOW_VOLUME = "low_volume"
    UNKNOWN = "unknown"

@dataclass
class Quote:
    """A single L1 quote update."""
    timestamp: float          # Unix timestamp
    last_price: float
    best_bid: float
    best_ask: float
    volume: int               # Cumulative daily volume
    spread: float = 0.0       # ask - bid

    def __post_init__(self):
        self.spread = self.best_ask - self.best_bid

@dataclass
class TradeTick:
    """A single trade execution."""
    timestamp: float
    price: float
    volume: int
    side: int                 # 0=buy, 1=sell

@dataclass
class MarketSnapshot:
    """Complete market state at a point in time. Fed to Layer 3 (Mind)."""
    timestamp: float
    contract_id: str
    
    # Current prices
    last_price: float
    best_bid: float
    best_ask: float
    spread: float
    
    # Derived signals
    atr_points: float         # Average True Range in points (14-period)
    vpin: float               # Volume-Synchronized Probability of Informed Trading (0-1)
    ofi_zscore: float         # Order Flow Imbalance Z-score
    volume_rate: float        # Current volume rate vs average (e.g., 1.5 = 50% above avg)
    bid_ask_imbalance: float  # (bid_size - ask_size) / (bid_size + ask_size), range -1 to 1
    
    # Regime
    regime: MarketRegime
    trend_strength: float     # ADX-like measure, 0-100
    
    # Buffer stats
    bar_count: int            # Number of bars in the temporal buffer
    tick_count: int           # Number of trade ticks in the buffer
    
    # Price action
    high_of_session: float
    low_of_session: float
    price_change_pct: float   # Price change % over the buffer window

@dataclass
class Bar:
    """OHLCV bar aggregated from trade ticks."""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    tick_count: int
    buy_volume: int = 0      # Volume from buy-side trades
    sell_volume: int = 0     # Volume from sell-side trades
```

## 4. Class Design

```python
class MarketDataPipeline:
    """
    Real-time market data pipeline.
    
    Connects to TopStepX Market Hub via SignalR WebSocket.
    Maintains a rolling temporal buffer of bars and ticks.
    Computes derived signals on demand.
    
    Thread-safe: WebSocket runs in a background thread,
    data is accessed from async context via locks.
    """
    
    def __init__(self, jwt_token: str, contract_id: str, 
                 buffer_minutes: int = 30,
                 bar_seconds: int = 15,
                 max_reconnect_attempts: int = 10):
        """
        jwt_token: Bearer token from BrokerClient authentication
        contract_id: e.g., "CON.F.US.MNQM26"
        buffer_minutes: Rolling window size (default 30 min)
        bar_seconds: Aggregate ticks into bars of this duration (default 15s)
        max_reconnect_attempts: Max reconnect tries before giving up
        """
    
    # --- Lifecycle ---
    
    async def start(self) -> None:
        """Start the WebSocket connection in a background thread."""
    
    async def stop(self) -> None:
        """Cleanly close the WebSocket connection."""
    
    @property
    def is_connected(self) -> bool:
        """True if WebSocket is connected and receiving data."""
    
    @property
    def seconds_since_last_update(self) -> float:
        """Seconds since the last quote/trade was received."""
    
    # --- Data Access ---
    
    def get_snapshot(self) -> MarketSnapshot:
        """
        Build and return a complete MarketSnapshot.
        
        This is the main interface to Layer 3. It computes all derived
        signals from the current buffer state. Thread-safe.
        
        Raises MarketDataError if not connected or no data available.
        """
    
    def get_latest_quote(self) -> Quote:
        """Get the most recent L1 quote."""
    
    def get_bars(self, count: int = 0) -> list[Bar]:
        """Get bars from the temporal buffer. 0 = all bars in buffer."""
    
    def get_ticks(self, count: int = 0) -> list[TradeTick]:
        """Get recent trade ticks. 0 = all ticks in buffer."""
    
    # --- Signal Calculations ---
    
    def calculate_atr(self, period: int = 14) -> float:
        """
        Calculate Average True Range from bars in the buffer.
        
        TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
        ATR = SMA of TR over `period` bars.
        
        Returns ATR in points. Returns 0.0 if not enough bars.
        """
    
    def calculate_vpin(self, bucket_size: int = 50) -> float:
        """
        Calculate VPIN (Volume-Synchronized Probability of Informed Trading).
        
        Simplified VPIN:
        1. Classify each trade tick as buy or sell (using tick rule: price > prev = buy)
        2. Group ticks into volume buckets of `bucket_size` contracts
        3. For each bucket: imbalance = |buy_volume - sell_volume| / total_volume
        4. VPIN = mean(imbalance) over all buckets in buffer
        
        Returns 0-1. Higher = more informed/toxic flow.
        Returns 0.0 if not enough data.
        """
    
    def calculate_ofi_zscore(self, window: int = 100) -> float:
        """
        Calculate Order Flow Imbalance Z-score.
        
        OFI = sum of signed volume (buy volume - sell volume) over recent ticks.
        Z-score = (OFI - mean(OFI_history)) / std(OFI_history)
        
        Uses rolling windows within the buffer.
        Returns 0.0 if not enough data.
        """
    
    def detect_regime(self) -> tuple[MarketRegime, float]:
        """
        Detect current market regime and trend strength.
        
        Uses a simplified ADX-like calculation:
        1. Calculate directional movement (+DM, -DM) from bars
        2. Smooth over 14 periods
        3. DI+ = +DM / ATR, DI- = -DM / ATR
        4. ADX = smoothed abs(DI+ - DI-) / (DI+ + DI-)
        
        Regime classification:
        - ADX > 25 and DI+ > DI-: TRENDING_UP
        - ADX > 25 and DI- > DI+: TRENDING_DOWN
        - ADX < 20: CHOPPY
        - ATR expanding > 2x recent average: BREAKOUT
        - Volume < 50% of average: LOW_VOLUME
        
        Returns (regime, trend_strength as 0-100).
        """
    
    # --- Internal WebSocket Handling ---
    # (These are internal methods, not part of the public API)
    
    def _on_open(self, ws):
        """Send handshake and subscribe to contract streams."""
    
    def _on_message(self, ws, message):
        """Parse SignalR frames, update buffer. Handle \x1e separator and multiple frames."""
    
    def _on_close(self, ws, code, msg):
        """Log and attempt reconnection with exponential backoff."""
    
    def _on_error(self, ws, error):
        """Log WebSocket errors."""
    
    def _process_quote(self, data: dict) -> None:
        """Process a GatewayQuote event. Update latest quote and session high/low."""
    
    def _process_trade(self, trades: list) -> None:
        """Process GatewayTrade events. Add to tick buffer, update current bar."""
    
    def _age_buffer(self) -> None:
        """Remove bars and ticks older than buffer_minutes from the rolling window."""


class MarketDataError(Exception):
    """Error in market data pipeline."""
    pass
```

## 5. Implementation Notes

### Threading Model
The WebSocket runs in a **daemon thread** (not asyncio). This is the proven pattern from v1 and avoids complex async WebSocket library issues. The data structures (bars, ticks, quotes) are protected with `threading.Lock`. The public methods (`get_snapshot`, `get_bars`, etc.) acquire the lock, copy the data, and release.

### Buffer Management
- Bars are aggregated from trade ticks every `bar_seconds` (default 15s)
- The buffer holds `buffer_minutes` worth of bars (default 30 min = 120 bars at 15s each)
- Oldest data is aged out on every new bar
- Session high/low track the extremes since pipeline start

### Reconnection
- On disconnect: exponential backoff (1s, 2s, 4s, 8s, 16s, 32s, max 60s)
- On reconnect: re-subscribe to all streams
- After `max_reconnect_attempts`: stop trying, set `is_connected = False`
- Token refresh: if token is near expiry, call broker to re-auth before reconnecting

### Signal Computation
- ATR, VPIN, OFI, and regime detection are computed **on demand** when `get_snapshot()` is called
- They are NOT computed on every tick (that would waste CPU)
- If there aren't enough bars for a calculation (e.g., <14 bars for ATR), return 0.0 / UNKNOWN

## 6. Test Requirements

### Unit Tests (no network, no WebSocket)
- `test_quote_creation` — Quote dataclass, spread calculation
- `test_bar_aggregation` — Feed ticks → verify OHLCV bar is correct
- `test_bar_buy_sell_volume` — Buy ticks classified correctly, sell ticks classified correctly
- `test_buffer_aging` — Bars older than buffer_minutes are removed
- `test_atr_calculation` — Known 14 bars → hand-computed ATR matches
- `test_atr_insufficient_data` — Less than 2 bars → returns 0.0
- `test_vpin_calculation` — Known tick sequence → hand-computed VPIN matches
- `test_vpin_all_buys` — All buy ticks → VPIN = 1.0 (max toxicity)
- `test_vpin_balanced` — Equal buy/sell → VPIN near 0.0
- `test_ofi_zscore_calculation` — Known sequence → verify Z-score sign and magnitude
- `test_regime_trending_up` — ADX > 25, DI+ > DI- → TRENDING_UP
- `test_regime_choppy` — ADX < 20 → CHOPPY
- `test_regime_unknown_insufficient_data` — Too few bars → UNKNOWN
- `test_snapshot_creation` — Build a snapshot from known buffer state

### WebSocket Protocol Tests (mock WebSocket)
- `test_handshake_sent_on_open` — Verify handshake JSON is sent
- `test_subscription_sent_after_handshake` — Verify SubscribeContractQuotes/Trades sent
- `test_parse_gateway_quote` — Feed a GatewayQuote frame → quote stored
- `test_parse_gateway_trade` — Feed a GatewayTrade frame → tick stored  
- `test_parse_multiple_frames` — Multiple frames in one message (split by \x1e)
- `test_ping_response` — Type 6 message → respond with type 6
- `test_reconnect_on_close` — WebSocket close → reconnect attempt

## 7. Dependencies

Add to `requirements.txt`:
```
websocket-client>=1.7.0
```

## 8. Acceptance Criteria

- [ ] WebSocket connects to TopStepX Market Hub with JWT token
- [ ] Handshake (`{"protocol":"json","version":1}\x1e`) sent on open
- [ ] Subscribes to SubscribeContractQuotes and SubscribeContractTrades
- [ ] Parses GatewayQuote events correctly (including `\x1e` separator)
- [ ] Parses GatewayTrade events correctly (including multi-trade arrays)
- [ ] Handles multiple frames in a single message
- [ ] Responds to type-6 pings
- [ ] Reconnects with exponential backoff on disconnect
- [ ] Temporal buffer correctly ages out old data
- [ ] ATR calculation matches hand-computed values
- [ ] VPIN calculation matches expected values for known sequences
- [ ] OFI Z-score has correct sign (positive for buy pressure)
- [ ] Regime detection classifies trending/choppy/unknown correctly
- [ ] `get_snapshot()` returns complete MarketSnapshot with all fields
- [ ] Thread-safe: concurrent access to buffer doesn't crash
- [ ] `is_connected` accurately reflects WebSocket state
- [ ] All unit tests pass (14+)
- [ ] All protocol tests pass (7+)
- [ ] No `except: pass` anywhere
- [ ] Code is under 500 lines

---
#specification #layer-2 #market-data #eyes #coding-agent
