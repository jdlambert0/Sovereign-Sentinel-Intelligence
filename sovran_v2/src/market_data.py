"""
Layer 2 — The Eyes (Market Data Pipeline)

Real-time L1 + L2 market data via TopStepX SignalR WebSocket.
Maintains rolling buffers, computes derived signals (ATR, VPIN, OFI, regime).

WebSocket Message Formats (TopStepX/ProjectX API):
  - GatewayQuote: L1 top-of-book. Fields: lastPrice, bestBid, bestAsk,
        totalVolume, change, changePercent.  Contract ID = arguments[0],
        data = arguments[1].
  - GatewayTrade: trade prints. arguments[0] = contractId,
        arguments[1] = list of {price, volume, side, timestamp}.
  - GatewayDepth: L2 order-book updates. arguments[0] = contractId,
        arguments[1] = list of {price, volume, type, timestamp}.
        type: 1 = bid level, 2 = ask level, 6 = reset entire book.
"""

import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import math

import websocket

# --- Data Structures ---

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
    change: float = 0.0       # Daily price change
    change_pct: float = 0.0   # Daily price change %

    def __post_init__(self):
        if self.best_ask > 0 and self.best_bid > 0:
            self.spread = self.best_ask - self.best_bid


@dataclass
class TradeTick:
    """A single trade execution."""
    timestamp: float
    price: float
    volume: int
    side: int                 # 0=buy, 1=sell


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


@dataclass
class DepthLevel:
    """A single price level in the L2 order book."""
    price: float
    volume: int
    side: int                 # 1=bid, 2=ask


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
    bid_ask_imbalance: float  # (bid_vol - ask_vol) / (bid_vol + ask_vol), range -1 to 1

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

    # L2 Depth (populated when GatewayDepth data is flowing)
    l2_bid_levels: List[DepthLevel] = field(default_factory=list)
    l2_ask_levels: List[DepthLevel] = field(default_factory=list)
    l2_bid_total_volume: int = 0
    l2_ask_total_volume: int = 0


class RollingStats:
    """Online mean/variance using Welford's algorithm. O(1) per update."""
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0

    def update(self, x: float):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += delta * delta2

    @property
    def std(self) -> float:
        if self.n < 2:
            return 1.0
        return math.sqrt(self.M2 / (self.n - 1))

    def reset(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0


class MarketDataError(Exception):
    """Error in market data pipeline."""
    pass


class MarketDataPipeline:
    """
    Real-time market data pipeline.

    Connects to TopStepX Market Hub via SignalR WebSocket.
    Subscribes to L1 quotes, trade prints, AND L2 depth.
    Maintains a rolling temporal buffer of bars and ticks.
    Computes derived signals on demand.

    Thread-safe: WebSocket runs in a background thread,
    data is accessed from async context via locks.
    """

    def __init__(self, jwt_token: str, contract_id: str,
                 buffer_minutes: int = 30,
                 bar_seconds: int = 15,
                 max_reconnect_attempts: int = 10):
        self.jwt_token = jwt_token
        self.contract_id = contract_id
        self.buffer_minutes = buffer_minutes
        self.bar_seconds = bar_seconds
        self.max_reconnect_attempts = max_reconnect_attempts

        self.logger = logging.getLogger("sovran.market_data")
        self.lock = threading.Lock()

        # State
        self.ws: Optional[websocket.WebSocketApp] = None
        self._is_connected = False
        self._reconnect_count = 0
        self._last_update_time = 0.0
        self._stop_event = threading.Event()

        # L1 Buffer
        self._latest_quote: Optional[Quote] = None
        self._bars: List[Bar] = []
        self._ticks: List[TradeTick] = []
        self._current_bar: Optional[Bar] = None

        # L2 Depth Book  — price → volume, maintained from GatewayDepth
        self._l2_bids: OrderedDict = OrderedDict()   # price → volume (descending)
        self._l2_asks: OrderedDict = OrderedDict()   # price → volume (ascending)
        self._l2_message_count: int = 0

        # Session Extremes
        self._high_of_session = -float('inf')
        self._low_of_session = float('inf')

        # OFI rolling stats (Welford algorithm for O(1) Z-score)
        self._ofi_rolling = RollingStats()
        self._ofi_accumulator: float = 0.0  # Running OFI since last sample
        self._ofi_ticks_in_window: int = 0
        self._ofi_window_size: int = 100    # Ticks per OFI sample

    # --- Lifecycle ---

    async def start(self) -> None:
        """Start the WebSocket connection in a background thread."""
        self._stop_event.clear()
        self._reconnect_count = 0
        thread = threading.Thread(target=self._run_websocket_loop, daemon=True)
        thread.start()

    async def stop(self) -> None:
        """Cleanly close the WebSocket connection."""
        self._stop_event.set()
        if self.ws:
            self.ws.close()
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """True if WebSocket is connected and receiving data."""
        return self._is_connected

    @property
    def seconds_since_last_update(self) -> float:
        """Seconds since the last quote/trade was received."""
        if self._last_update_time == 0:
            return float('inf')
        return time.time() - self._last_update_time

    # --- Data Access ---

    def get_snapshot(self) -> MarketSnapshot:
        """Build and return a complete MarketSnapshot."""
        with self.lock:
            if not self._latest_quote:
                raise MarketDataError("No market data available")

            timestamp = time.time()

            # Compute signals
            atr = self.calculate_atr()
            vpin = self.calculate_vpin()
            ofi = self.calculate_ofi_zscore()
            regime, strength = self.detect_regime()

            # Volume rate — compare current bar volume to recent average
            if len(self._bars) >= 10:
                avg_vol = sum(b.volume for b in self._bars[-10:]) / 10
                curr_vol = self._current_bar.volume if self._current_bar else 0
                volume_rate = curr_vol / avg_vol if avg_vol > 0 else 1.0
            else:
                volume_rate = 1.0

            # Price change % over buffer
            price_change_pct = 0.0
            if self._bars:
                first_price = self._bars[0].open
                last_price = self._latest_quote.last_price
                if first_price > 0:
                    price_change_pct = (last_price - first_price) / first_price * 100

            # Bid/ask imbalance — prefer L2 depth when available, fallback to L1
            bid_ask_imb = self._compute_bid_ask_imbalance()

            # Build L2 snapshot lists
            l2_bid_levels = [DepthLevel(price=p, volume=v, side=1) for p, v in self._l2_bids.items() if v > 0]
            l2_ask_levels = [DepthLevel(price=p, volume=v, side=2) for p, v in self._l2_asks.items() if v > 0]
            l2_bid_total = sum(v for v in self._l2_bids.values())
            l2_ask_total = sum(v for v in self._l2_asks.values())

            return MarketSnapshot(
                timestamp=timestamp,
                contract_id=self.contract_id,
                last_price=self._latest_quote.last_price,
                best_bid=self._latest_quote.best_bid,
                best_ask=self._latest_quote.best_ask,
                spread=self._latest_quote.spread,
                atr_points=atr,
                vpin=vpin,
                ofi_zscore=ofi,
                volume_rate=volume_rate,
                bid_ask_imbalance=bid_ask_imb,
                regime=regime,
                trend_strength=strength,
                bar_count=len(self._bars),
                tick_count=len(self._ticks),
                high_of_session=self._high_of_session if self._high_of_session != -float('inf') else self._latest_quote.last_price,
                low_of_session=self._low_of_session if self._low_of_session != float('inf') else self._latest_quote.last_price,
                price_change_pct=price_change_pct,
                l2_bid_levels=l2_bid_levels[:10],  # Top 10 levels
                l2_ask_levels=l2_ask_levels[:10],
                l2_bid_total_volume=l2_bid_total,
                l2_ask_total_volume=l2_ask_total,
            )

    def get_latest_quote(self) -> Quote:
        with self.lock:
            if not self._latest_quote:
                raise MarketDataError("No quote available")
            return self._latest_quote

    def get_bars(self, count: int = 0) -> list[Bar]:
        with self.lock:
            bars = self._bars.copy()
            if count > 0:
                return bars[-count:]
            return bars

    def get_ticks(self, count: int = 0) -> list[TradeTick]:
        with self.lock:
            ticks = self._ticks.copy()
            if count > 0:
                return ticks[-count:]
            return ticks

    def get_l2_depth(self, levels: int = 10) -> Dict[str, List[DepthLevel]]:
        """Return current L2 order book depth."""
        with self.lock:
            bids = [DepthLevel(price=p, volume=v, side=1) for p, v in self._l2_bids.items() if v > 0][:levels]
            asks = [DepthLevel(price=p, volume=v, side=2) for p, v in self._l2_asks.items() if v > 0][:levels]
            return {"bids": bids, "asks": asks}

    # --- Signal Calculations (must be called within lock) ---

    def calculate_atr(self, period: int = 14) -> float:
        """Calculate ATR (14-period SMA of TR)."""
        if len(self._bars) < period + 1:
            return 0.0

        tr_list = []
        for i in range(1, len(self._bars)):
            curr = self._bars[i]
            prev = self._bars[i-1]
            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close)
            )
            tr_list.append(tr)

        if len(tr_list) < period:
            return 0.0

        return sum(tr_list[-period:]) / period

    def calculate_vpin(self, bucket_size: int = 50) -> float:
        """Calculate VPIN."""
        if not self._ticks:
            return 0.0

        imbalances = []
        current_bucket_buy = 0
        current_bucket_sell = 0
        current_bucket_total = 0

        for tick in self._ticks:
            if tick.side == 0:  # Buy
                current_bucket_buy += tick.volume
            else:
                current_bucket_sell += tick.volume

            current_bucket_total += tick.volume

            if current_bucket_total >= bucket_size:
                imbalance = abs(current_bucket_buy - current_bucket_sell) / current_bucket_total
                imbalances.append(imbalance)
                current_bucket_buy = 0
                current_bucket_sell = 0
                current_bucket_total = 0

        if not imbalances:
            return 0.0

        return sum(imbalances) / len(imbalances)

    def calculate_ofi_zscore(self, window: int = 100) -> float:
        """Calculate OFI Z-score using Welford rolling statistics. O(1) per call.

        The rolling stats are updated incrementally as ticks arrive (via _update_ofi_rolling).
        This method just reads the current OFI and computes the Z-score against the
        rolling mean/std.
        """
        if len(self._ticks) < window:
            return 0.0

        # Current OFI over the last `window` ticks
        recent_ticks = self._ticks[-window:]
        current_ofi = sum(t.volume if t.side == 0 else -t.volume for t in recent_ticks)

        # Need enough samples for meaningful statistics
        if self._ofi_rolling.n < 5:
            return 0.0

        std = self._ofi_rolling.std
        if std == 0:
            return 0.0

        return (current_ofi - self._ofi_rolling.mean) / std

    def _update_ofi_rolling(self, tick: TradeTick) -> None:
        """Incrementally update OFI rolling stats as new ticks arrive."""
        ofi_contrib = tick.volume if tick.side == 0 else -tick.volume
        self._ofi_accumulator += ofi_contrib
        self._ofi_ticks_in_window += 1

        if self._ofi_ticks_in_window >= self._ofi_window_size:
            self._ofi_rolling.update(self._ofi_accumulator)
            self._ofi_accumulator = 0.0
            self._ofi_ticks_in_window = 0

    def _compute_bid_ask_imbalance(self) -> float:
        """Compute order book imbalance.

        Prefers L2 depth data when available (real book imbalance).
        Falls back to L1 tick-based estimate when L2 is empty.

        Returns: float in range [-1.0, +1.0]
            Positive = more buying (bid-side) pressure
            Negative = more selling (ask-side) pressure
        """
        # Try L2 first — real order book imbalance
        if self._l2_bids or self._l2_asks:
            bid_vol = sum(v for v in self._l2_bids.values())
            ask_vol = sum(v for v in self._l2_asks.values())
            total = bid_vol + ask_vol
            if total > 0:
                return (bid_vol - ask_vol) / total

        # Fallback: estimate from recent L1 trade tick direction
        return self.estimate_bid_ask_imbalance()

    def estimate_bid_ask_imbalance(self) -> float:
        """Estimate order book imbalance from L1 tick patterns.

        Since L2 depth data may not be available, we estimate imbalance
        from recent trade tick direction. A preponderance of buy-side trades
        suggests bid pressure; sell-side suggests ask pressure.

        Returns: float in range [-1.0, +1.0]
        """
        if len(self._ticks) < 20:
            return 0.0
        recent = self._ticks[-50:] if len(self._ticks) >= 50 else self._ticks[-20:]
        buys = sum(1 for t in recent if t.side == 0)
        sells = len(recent) - buys
        total = buys + sells
        if total == 0:
            return 0.0
        return (buys - sells) / total

    def detect_regime(self) -> Tuple[MarketRegime, float]:
        """Detect current market regime and trend strength."""
        period = 14
        if len(self._bars) < period + 1:
            return MarketRegime.UNKNOWN, 0.0

        # Simplified ADX
        plus_dm = []
        minus_dm = []
        tr_list = []

        for i in range(1, len(self._bars)):
            curr = self._bars[i]
            prev = self._bars[i-1]

            move_up = curr.high - prev.high
            move_down = prev.low - curr.low

            if move_up > move_down and move_up > 0:
                plus_dm.append(move_up)
                minus_dm.append(0)
            elif move_down > move_up and move_down > 0:
                plus_dm.append(0)
                minus_dm.append(move_down)
            else:
                plus_dm.append(0)
                minus_dm.append(0)

            tr = max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
            tr_list.append(tr)

        if len(tr_list) < period:
            return MarketRegime.UNKNOWN, 0.0

        smooth_tr = sum(tr_list[-period:])
        smooth_plus_dm = sum(plus_dm[-period:])
        smooth_minus_dm = sum(minus_dm[-period:])

        if smooth_tr == 0:
            return MarketRegime.UNKNOWN, 0.0

        di_plus = 100 * (smooth_plus_dm / smooth_tr)
        di_minus = 100 * (smooth_minus_dm / smooth_tr)

        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus) if (di_plus + di_minus) > 0 else 0
        adx = dx  # Snapshot approximation

        # Regime logic
        regime = MarketRegime.CHOPPY
        if adx > 25:
            if di_plus > di_minus:
                regime = MarketRegime.TRENDING_UP
            else:
                regime = MarketRegime.TRENDING_DOWN
        elif adx < 20:
            regime = MarketRegime.CHOPPY

        # Volatility check for breakout
        atr = self.calculate_atr(period)
        if len(tr_list) >= period * 2:
            prev_atr = sum(tr_list[-(period*2):-period]) / period
            if prev_atr > 0 and atr > 2 * prev_atr:
                regime = MarketRegime.BREAKOUT

        return regime, adx

    # --- Internal WebSocket Handling ---

    def _run_websocket_loop(self):
        while not self._stop_event.is_set() and self._reconnect_count < self.max_reconnect_attempts:
            try:
                url = f"wss://rtc.topstepx.com/hubs/market?access_token={self.jwt_token}"
                self.ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws.run_forever(ping_interval=10, ping_timeout=5)
            except Exception as e:
                self.logger.error(f"WebSocket execution error: {e}")

            if self._stop_event.is_set():
                break

            self._reconnect_count += 1
            delay = min(60, 2**(self._reconnect_count - 1))
            self.logger.info(f"Reconnecting in {delay}s (Attempt {self._reconnect_count}/{self.max_reconnect_attempts})")
            time.sleep(delay)

        if self._reconnect_count >= self.max_reconnect_attempts:
            self.logger.error("Max reconnect attempts reached. Market data pipeline stopped.")
            self._is_connected = False

    def _on_open(self, ws):
        self.logger.info("WebSocket connected. Sending handshake...")
        ws.send('{"protocol":"json","version":1}\x1e')
        self._reconnect_count = 0

        # CRITICAL: Delay subscriptions to let the server process the handshake.
        def _delayed_subscribe():
            time.sleep(0.5)
            self.logger.info(f"Subscribing to {self.contract_id} streams (L1 + L2)...")
            subs = [
                {"type": 1, "target": "SubscribeContractQuotes", "arguments": [self.contract_id], "invocationId": "q1"},
                {"type": 1, "target": "SubscribeContractTrades", "arguments": [self.contract_id], "invocationId": "t1"},
                {"type": 1, "target": "SubscribeContractDepth", "arguments": [self.contract_id], "invocationId": "d1"},
            ]
            for sub in subs:
                ws.send(json.dumps(sub) + '\x1e')
            self.logger.info("Market subscriptions sent (quotes + trades + depth).")
            self._is_connected = True

        threading.Thread(target=_delayed_subscribe, daemon=True).start()

    def _on_message(self, ws, message):
        self._last_update_time = time.time()
        frames = message.split('\x1e')
        for frame in frames:
            if not frame:
                continue
            try:
                data = json.loads(frame)
                msg_type = data.get("type")

                if msg_type == 6:  # Ping
                    ws.send('{"type":6}\x1e')
                elif msg_type == 1:  # Invocation (Event)
                    target = data.get("target")
                    args = data.get("arguments", [])
                    if target == "GatewayQuote" and len(args) >= 2:
                        # args[0] = contractId, args[1] = quote data dict
                        self._process_quote(args[1])
                    elif target == "GatewayTrade" and len(args) >= 2:
                        # args[0] = contractId, args[1] = list of trade dicts
                        self._process_trade(args[1])
                    elif target == "GatewayDepth" and len(args) >= 2:
                        # args[0] = contractId, args[1] = list of depth level dicts
                        self._process_depth(args[1])
                elif msg_type == 3:  # Completion
                    if data.get("error"):
                        self.logger.error(f"Invocation error: {data.get('error')}")
            except Exception as e:
                self.logger.error(f"Error parsing frame: {e}")

    def _on_close(self, ws, code, msg):
        self.logger.warning(f"WebSocket closed: {code} - {msg}")
        self._is_connected = False

    def _on_error(self, ws, error):
        self.logger.error(f"WebSocket error: {error}")

    # --- Message Processors ---

    def _parse_timestamp(self, ts_str: str) -> float:
        """Parse ISO timestamp from the API."""
        if not ts_str:
            return time.time()
        try:
            if ts_str.endswith("Z"):
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            return datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            return time.time()

    def _process_quote(self, data: dict) -> None:
        """Process a GatewayQuote message.

        API field names:
          lastPrice, bestBid, bestAsk, totalVolume, change, changePercent
        The API sends partial updates — only changed fields are populated.
        We merge with the last known quote to preserve unchanged values.
        """
        with self.lock:
            ts = self._parse_timestamp(data.get("timestamp", ""))
            prev = self._latest_quote

            # Merge with previous — API only sends fields that changed
            last_price = _float_or(data, "lastPrice", prev.last_price if prev else 0.0)
            best_bid = _float_or(data, "bestBid", prev.best_bid if prev else 0.0)
            best_ask = _float_or(data, "bestAsk", prev.best_ask if prev else 0.0)
            # Accept both "volume" and "totalVolume" (the API uses totalVolume)
            volume_val = data.get("totalVolume") if data.get("totalVolume") is not None else data.get("volume")
            volume = int(volume_val) if volume_val is not None else (prev.volume if prev else 0)
            change = _float_or(data, "change", prev.change if prev else 0.0)
            change_pct = _float_or(data, "changePercent", prev.change_pct if prev else 0.0)

            quote = Quote(
                timestamp=ts,
                last_price=last_price,
                best_bid=best_bid,
                best_ask=best_ask,
                volume=volume,
                change=change,
                change_pct=change_pct,
            )
            self._latest_quote = quote

            # Update session extremes
            if quote.last_price > 0:
                if quote.last_price > self._high_of_session:
                    self._high_of_session = quote.last_price
                if quote.last_price < self._low_of_session:
                    self._low_of_session = quote.last_price

    def _process_trade(self, trades: list) -> None:
        """Process GatewayTrade messages (list of trade prints)."""
        with self.lock:
            now = time.time()
            for t_data in trades:
                ts = self._parse_timestamp(t_data.get("timestamp", ""))
                price = float(t_data.get("price") or 0)
                volume = int(t_data.get("volume") or 0)

                # TopStepX GatewayTrade sends aggressor as "type" field:
                #   type=0 = aggressive buyer (lifted the ask)
                #   type=1 = aggressive seller (hit the bid)
                # Fallback: check "side" field, then use tick rule
                raw_side = t_data.get("type")  # Primary: aggressor type
                if raw_side is None:
                    raw_side = t_data.get("side")  # Fallback: side field
                if raw_side is not None:
                    side = int(raw_side)
                else:
                    # Tick rule: compare to last tick price
                    if self._ticks:
                        side = 0 if price >= self._ticks[-1].price else 1
                    else:
                        side = 0  # First tick defaults to buy

                tick = TradeTick(timestamp=ts, price=price, volume=volume, side=side)
                self._ticks.append(tick)
                self._update_ofi_rolling(tick)

                # Update current bar
                if not self._current_bar or ts >= self._current_bar.timestamp + self.bar_seconds:
                    if self._current_bar:
                        self._bars.append(self._current_bar)

                    self._current_bar = Bar(
                        timestamp=ts - (ts % self.bar_seconds),
                        open=tick.price,
                        high=tick.price,
                        low=tick.price,
                        close=tick.price,
                        volume=0,
                        tick_count=0,
                        buy_volume=0,
                        sell_volume=0
                    )

                b = self._current_bar
                b.high = max(b.high, tick.price)
                b.low = min(b.low, tick.price)
                b.close = tick.price
                b.volume += tick.volume
                b.tick_count += 1
                if tick.side == 0:
                    b.buy_volume += tick.volume
                else:
                    b.sell_volume += tick.volume

            self._age_buffer()

    def _process_depth(self, levels: list) -> None:
        """Process GatewayDepth messages — L2 order book updates.

        Each element: {price: float, volume: int, type: int, timestamp: str}
        type: 1 = bid level, 2 = ask level, 6 = reset entire book.

        Volume of 0 at a price means that level has been removed.
        """
        with self.lock:
            for entry in levels:
                level_type = int(entry.get("type", 0))

                if level_type == 6:
                    # Reset entire book
                    self._l2_bids.clear()
                    self._l2_asks.clear()
                    continue

                price = float(entry.get("price", 0))
                volume = int(entry.get("volume", 0))

                if price <= 0:
                    continue

                if level_type == 1:  # Bid
                    if volume == 0:
                        self._l2_bids.pop(price, None)
                    else:
                        self._l2_bids[price] = volume
                elif level_type == 2:  # Ask
                    if volume == 0:
                        self._l2_asks.pop(price, None)
                    else:
                        self._l2_asks[price] = volume

            self._l2_message_count += 1

            # Keep bids sorted descending, asks sorted ascending (periodically)
            if self._l2_message_count % 50 == 0:
                self._sort_l2_book()

    def _sort_l2_book(self) -> None:
        """Re-sort the L2 book. Bids descending, asks ascending."""
        if self._l2_bids:
            sorted_bids = OrderedDict(sorted(self._l2_bids.items(), key=lambda x: -x[0]))
            self._l2_bids = sorted_bids
        if self._l2_asks:
            sorted_asks = OrderedDict(sorted(self._l2_asks.items(), key=lambda x: x[0]))
            self._l2_asks = sorted_asks

    def _age_buffer(self) -> None:
        """Remove old data from buffer."""
        cutoff = time.time() - (self.buffer_minutes * 60)

        # Age bars
        while self._bars and self._bars[0].timestamp < cutoff:
            self._bars.pop(0)

        # Age ticks
        while self._ticks and self._ticks[0].timestamp < cutoff:
            self._ticks.pop(0)


# --- Utilities ---

def _float_or(data: dict, key: str, default: float) -> float:
    """Get a float from a dict, using default if key is missing or None."""
    val = data.get(key)
    if val is not None:
        return float(val)
    return default
