#!/usr/bin/env python3
"""
Sovran V2 — Live Trading Session v4 (Kaizen Edition)

All 4 Kaizen phases integrated:

Phase 1 — Eliminate Waste (Muda):
  - Partial take-profit at 0.6× SL (close half, SL to breakeven)
  - Hard flow/bars conflict block (conviction → 0)
  - Minimum hold time 120s before trailing
  - Time-of-day hard block (no trades outside 8:00-16:00 CT)

Phase 2 — Level the Flow (Heijunka):
  - Regime-adaptive SL/TP profiles (trending/ranging/volatile)
  - Conviction-based position sizing (1-2 contracts)

Phase 3 — Standardize (Hyojunka):
  - Rolling 20-trade performance windows with adaptive thresholds
  - Per-trade Kaizen instrumentation log (state/kaizen_log.json)
  - Profit capture ratio tracking

Phase 4 — Continuous Flow (Jidoka):
  - KaizenEngine: post-trade self-correction of parameters
  - Rolling market performance ranking (focus on top performers)
  - Automated parameter adaptation (trail, conviction, SL)
"""
import asyncio
import json
import logging
import os
import sys
import time
import signal
import threading
import math
import websocket
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from collections import deque

sys.path.insert(0, "/tmp/pylibs")
import httpx

# ── Config ──────────────────────────────────────────────────────────────
API_KEY = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="
USERNAME = "jessedavidlambert@gmail.com"
BASE_URL = "https://api.topstepx.com"
WS_URL = "wss://rtc.topstepx.com/hubs/market"
RECORD_SEP = "\x1e"
ACCOUNT_ID = 20560125

SCAN_CONTRACTS = [
    "CON.F.US.MNQ.M26",
    "CON.F.US.MES.M26",
    "CON.F.US.MYM.M26",
    "CON.F.US.M2K.M26",
    "CON.F.US.MGC.M26",
    "CON.F.US.MCLE.M26",
]

CONTRACT_META = {
    "CON.F.US.MNQ.M26": {"name": "MNQ", "tick_size": 0.25, "tick_value": 0.50, "point_value": 2.00, "asset": "equity_index"},
    "CON.F.US.MES.M26": {"name": "MES", "tick_size": 0.25, "tick_value": 1.25, "point_value": 5.00, "asset": "equity_index"},
    "CON.F.US.MYM.M26": {"name": "MYM", "tick_size": 1.00, "tick_value": 0.50, "point_value": 0.50, "asset": "equity_index"},
    "CON.F.US.M2K.M26": {"name": "M2K", "tick_size": 0.10, "tick_value": 0.50, "point_value": 5.00, "asset": "equity_index"},
    "CON.F.US.MGC.M26": {"name": "MGC", "tick_size": 0.10, "tick_value": 1.00, "point_value": 10.00, "asset": "metals"},
    "CON.F.US.MCLE.M26": {"name": "MCL", "tick_size": 0.01, "tick_value": 1.00, "point_value": 100.00, "asset": "energy"},
}

# Risk parameters
MAX_POSITION_SIZE = 1          # Base size; Phase 2 scales by conviction
MAX_POSITION_SIZE_BOOSTED = 2  # Phase 2: high-conviction trades
MAX_CONCURRENT_POSITIONS = 2
MAX_DAILY_LOSS = 500.0
MAX_TRADES_SESSION = 999
TRADE_COOLDOWN = 90
MIN_CONVICTION_FIRST = 60
MIN_CONVICTION_AFTER = 65
MIN_FLOW_TRADES = 50

# Phase 1: Trailing stop config
TRAIL_ACTIVATION_MULT = 0.5
TRAIL_BREAKEVEN_TICKS = 2
TRAIL_OFFSET_TICKS = 8

# Phase 1: Partial take-profit
PARTIAL_TP_MULT = 0.6          # Close half at MFE >= SL_ticks × 0.6
MIN_HOLD_BEFORE_TRAIL = 120    # Don't trail/partial TP before 120s

# Phase 1: Time-of-day hard blocks
TRADING_HOURS_START = 8        # 8 AM CT
TRADING_HOURS_END = 16         # 4 PM CT

# Phase 2: Regime-adaptive profiles
REGIME_PROFILES = {
    "trending": {"sl_mult": 2.0, "tp_mult": 5.0, "trail_offset": 6, "trail_act": 0.4},
    "ranging":  {"sl_mult": 1.5, "tp_mult": 2.5, "trail_offset": 4, "trail_act": 0.3},
    "volatile": {"sl_mult": 0.0, "tp_mult": 0.0, "trail_offset": 0, "trail_act": 0.0},  # BLOCKED
    "unknown":  {"sl_mult": 0.0, "tp_mult": 0.0, "trail_offset": 0, "trail_act": 0.0},  # BLOCKED
}

# Phase 2: Conviction-based sizing thresholds
CONVICTION_SIZE_BOOST = 80     # Score >= 80 → can use 2 contracts

# Session time windows (Central Time)
# RTH = Regular Trading Hours, best for our strategy
SESSION_PHASES = {
    "overnight": (0, 7),     # 12am-7am CT — thin, avoid
    "premarket": (7, 8),     # 7am-8am CT — warming up
    "us_open":   (8, 10),    # 8am-10am CT — high volume, volatile
    "us_core":   (10, 14),   # 10am-2pm CT — best for flow trading
    "us_close":  (14, 16),   # 2pm-4pm CT — end-of-day moves
    "evening":   (16, 24),   # 4pm-12am CT — thin again
}

def get_session_phase() -> Tuple[str, float]:
    """Get current session phase and conviction multiplier."""
    ct = datetime.now(timezone(timedelta(hours=-5)))  # CDT = UTC-5
    hour = ct.hour
    
    if 0 <= hour < 7:
        return "overnight", 0.5     # Halve conviction overnight
    elif 7 <= hour < 8:
        return "premarket", 0.7     # Cautious premarket
    elif 8 <= hour < 10:
        return "us_open", 1.0       # Full conviction
    elif 10 <= hour < 14:
        return "us_core", 1.2       # BEST session — boost
    elif 14 <= hour < 16:
        return "us_close", 0.9      # Good but watch for reversals
    else:
        return "evening", 0.6       # Cautious evening

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("live_session_v4.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("sovran_v4")


# ── Market Data Types ───────────────────────────────────────────────────
@dataclass
class MarketTick:
    contract_id: str
    last_price: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    timestamp: float = 0.0
    tick_count: int = 0
    spread: float = 0.0
    spread_ticks: float = 0.0
    buy_volume: int = 0
    sell_volume: int = 0
    recent_trades: List[Dict] = field(default_factory=list)
    price_history: List[float] = field(default_factory=list)
    high: float = 0.0
    low: float = float('inf')
    # 1-minute OHLC bars
    bars: List[Dict] = field(default_factory=list)
    _bar_start: float = 0.0
    _bar_open: float = 0.0
    _bar_high: float = 0.0
    _bar_low: float = float('inf')
    _bar_vol: int = 0
    # VWAP tracking
    _vwap_cum_pv: float = 0.0   # cumulative price * volume
    _vwap_cum_vol: int = 0       # cumulative volume
    vwap: float = 0.0            # current VWAP


@dataclass
class PositionInfo:
    contract_id: str
    side: str
    entry_price: float
    size: int
    sl_price: float
    tp_price: float
    entry_time: float
    order_id: int
    sl_ticks: int = 20
    tp_ticks: int = 40
    mfe: float = 0.0
    mae: float = 0.0
    trail_active: bool = False
    trail_stop: float = 0.0
    thesis: str = ""
    partial_taken: bool = False      # Phase 1: half position closed
    original_size: int = 1           # Phase 2: track pre-partial size
    conviction_at_entry: float = 0.0 # Phase 3: instrumentation
    regime_at_entry: str = ""        # Phase 3: instrumentation


@dataclass
class TradeResult:
    contract_id: str
    side: str
    entry_price: float
    exit_price: float
    size: int
    pnl: float
    ticks: float
    hold_time: float
    exit_reason: str
    mfe: float
    mae: float
    thesis: str
    timestamp: str
    # Phase 3: Kaizen instrumentation
    conviction: float = 0.0
    regime: str = ""
    partial_taken: bool = False
    profit_capture_ratio: float = 0.0  # actual_pnl / mfe_potential


# ── API Client ──────────────────────────────────────────────────────────
class TopStepXClient:
    def __init__(self):
        self.client = httpx.Client(base_url=BASE_URL, timeout=20.0)
        self.token: Optional[str] = None
        self.token_expiry: float = 0.0

    def authenticate(self) -> bool:
        try:
            r = self.client.post("/api/Auth/loginKey", json={
                "userName": USERNAME, "apiKey": API_KEY
            })
            data = r.json()
            if data.get("success"):
                self.token = data["token"]
                self.token_expiry = time.time() + 3600
                logger.info("Authenticated OK")
                return True
            logger.error(f"Auth failed: {data.get('errorCode')}")
            return False
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return False

    def _headers(self) -> Dict[str, str]:
        if time.time() > self.token_expiry - 120:
            self.authenticate()
        return {"Authorization": f"Bearer {self.token}"}

    def get_account_balance(self) -> float:
        r = self.client.post("/api/Account/search",
                            json={"onlyActiveAccounts": True},
                            headers=self._headers())
        accts = r.json().get("accounts", [])
        return accts[0]["balance"] if accts else 0.0

    def get_positions(self) -> List[Dict]:
        r = self.client.post("/api/Position/searchOpen",
                            json={"accountId": ACCOUNT_ID},
                            headers=self._headers())
        return r.json().get("positions", [])

    def get_open_orders(self) -> List[Dict]:
        r = self.client.post("/api/Order/searchOpen",
                            json={"accountId": ACCOUNT_ID},
                            headers=self._headers())
        return r.json().get("orders", [])

    def place_order(self, contract_id: str, side: str, size: int,
                    sl_ticks: int, tp_ticks: int) -> Dict:
        order_side = 0 if side == "BUY" else 1
        if side == "BUY":
            sl_signed = -abs(sl_ticks)
            tp_signed = abs(tp_ticks)
        else:
            sl_signed = abs(sl_ticks)
            tp_signed = -abs(tp_ticks)

        payload = {
            "accountId": ACCOUNT_ID,
            "contractId": contract_id,
            "type": 2,
            "side": order_side,
            "size": size,
            "stopLossBracket": {"ticks": sl_signed, "type": 4},
            "takeProfitBracket": {"ticks": tp_signed, "type": 1},
        }
        meta = CONTRACT_META.get(contract_id, {})
        logger.info(f"ORDER: {side} {size}x {meta.get('name',contract_id)} SL={sl_signed}t TP={tp_signed}t")
        r = self.client.post("/api/Order/place", json=payload, headers=self._headers())
        data = r.json()
        if data.get("success"):
            logger.info(f"  [OK] Filled! Order ID: {data.get('orderId')}")
        else:
            logger.error(f"  [FAIL] Failed: code={data.get('errorCode')} msg={data.get('errorMessage')}")
        return data

    def cancel_order(self, order_id: int) -> Dict:
        """Cancel a specific order by ID."""
        r = self.client.post("/api/Order/cancel", json={
            "accountId": ACCOUNT_ID,
            "orderId": order_id,
        }, headers=self._headers())
        return r.json()

    def modify_order(self, order_id: int, stop_price: float = None, limit_price: float = None) -> Dict:
        """Modify an existing order's price."""
        payload = {"accountId": ACCOUNT_ID, "orderId": order_id}
        if stop_price is not None:
            payload["stopPrice"] = stop_price
        if limit_price is not None:
            payload["limitPrice"] = limit_price
        r = self.client.post("/api/Order/modify", json=payload, headers=self._headers())
        return r.json()

    def close_position(self, contract_id: str) -> Dict:
        r = self.client.post("/api/Position/closeContract",
                            json={"accountId": ACCOUNT_ID, "contractId": contract_id},
                            headers=self._headers())
        return r.json()


# ── WebSocket Data Stream ───────────────────────────────────────────────
class MarketDataStream:
    def __init__(self, token: str, contracts: List[str]):
        self.token = token
        self.contracts = contracts
        self.ticks: Dict[str, MarketTick] = {c: MarketTick(contract_id=c) for c in contracts}
        self.ws: Optional[websocket.WebSocketApp] = None
        self.connected = False
        self.message_count = 0
        self._lock = threading.Lock()

    def start(self):
        url = f"{WS_URL}?access_token={self.token}"
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=lambda ws, e: logger.error(f"WS error: {e}"),
            on_close=lambda ws, c, m: setattr(self, 'connected', False),
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    def stop(self):
        if self.ws:
            self.ws.close()

    def _on_open(self, ws):
        ws.send('{"protocol":"json","version":1}' + RECORD_SEP)
        def _subscribe():
            time.sleep(0.5)
            for cid in self.contracts:
                for target in ["SubscribeContractQuotes", "SubscribeContractTrades"]:
                    ws.send(json.dumps({
                        "type": 1, "target": target,
                        "arguments": [cid],
                        "invocationId": f"{target[:5]}-{cid[-8:]}"
                    }) + RECORD_SEP)
            self.connected = True
            logger.info(f"WS subscribed to {len(self.contracts)} contracts")
        threading.Thread(target=_subscribe, daemon=True).start()

    def _on_message(self, ws, message):
        for frame in message.split(RECORD_SEP):
            frame = frame.strip()
            if not frame:
                continue
            try:
                data = json.loads(frame)
                if data.get("type") == 6:
                    ws.send(json.dumps({"type": 6}) + RECORD_SEP)
                elif data.get("type") == 1:
                    self._process_event(data)
                self.message_count += 1
            except json.JSONDecodeError:
                pass

    def _process_event(self, data: Dict):
        target = data.get("target", "")
        args = data.get("arguments", [])
        if len(args) < 2:
            return
        cid = args[0]
        if cid not in self.ticks:
            return
        with self._lock:
            tick = self.ticks[cid]
            if target == "GatewayQuote":
                self._process_quote(tick, args[1])
            elif target == "GatewayTrade":
                self._process_trades(tick, args[1])
                # Debug: log first trade for each contract
                if tick.buy_volume + tick.sell_volume == 1:
                    logger.info(f"  [DATA] First trade on {CONTRACT_META.get(cid, {}).get('name', cid)}: B:{tick.buy_volume} S:{tick.sell_volume}")

    def _process_quote(self, tick: MarketTick, q: Dict):
        now = time.time()
        if "lastPrice" in q:
            p = float(q["lastPrice"])
            tick.last_price = p
            tick.price_history.append(p)
            if len(tick.price_history) > 2000:
                tick.price_history = tick.price_history[-2000:]
            tick.high = max(tick.high, p) if tick.high > 0 else p
            if tick.low == float('inf'):
                tick.low = p
            tick.low = min(tick.low, p)
            # Update 1-min bar
            if tick._bar_start == 0 or now - tick._bar_start >= 60:
                if tick._bar_start > 0:
                    tick.bars.append({
                        "o": tick._bar_open, "h": tick._bar_high,
                        "l": tick._bar_low, "c": p, "v": tick._bar_vol,
                        "t": tick._bar_start
                    })
                    if len(tick.bars) > 120:
                        tick.bars = tick.bars[-120:]
                tick._bar_start = now
                tick._bar_open = p
                tick._bar_high = p
                tick._bar_low = p
                tick._bar_vol = 0
            else:
                tick._bar_high = max(tick._bar_high, p)
                tick._bar_low = min(tick._bar_low, p)

        if "bestBid" in q:
            tick.best_bid = float(q["bestBid"])
        if "bestAsk" in q:
            tick.best_ask = float(q["bestAsk"])
        if "totalVolume" in q:
            tick.volume = int(q["totalVolume"])
        elif "volume" in q:
            tick.volume = int(q["volume"])
        if "change" in q:
            tick.change = float(q["change"])
        if "changePercent" in q:
            tick.change_pct = float(q["changePercent"])

        tick.tick_count += 1
        tick.timestamp = now

        if tick.best_bid > 0 and tick.best_ask > 0:
            tick.spread = tick.best_ask - tick.best_bid
            meta = CONTRACT_META.get(tick.contract_id, {})
            ts = meta.get("tick_size", 0.25)
            tick.spread_ticks = round(tick.spread / ts) if ts > 0 else 0

    def _process_trades(self, tick: MarketTick, trades):
        trade_list = trades if isinstance(trades, list) else [trades]
        for t in trade_list:
            if not isinstance(t, dict):
                continue
            trade_type = t.get("type", -1)
            vol = int(t.get("volume", 1))
            price = float(t.get("price", 0))

            if trade_type == 0:
                tick.buy_volume += vol
                side_str = "buy"
            elif trade_type == 1:
                tick.sell_volume += vol
                side_str = "sell"
            else:
                side_str = "unknown"

            tick.recent_trades.append({
                "price": price, "volume": vol,
                "side": side_str, "time": time.time(),
            })
            tick._bar_vol += vol
            # Update VWAP
            if price > 0:
                tick._vwap_cum_pv += price * vol
                tick._vwap_cum_vol += vol
                if tick._vwap_cum_vol > 0:
                    tick.vwap = tick._vwap_cum_pv / tick._vwap_cum_vol
            if len(tick.recent_trades) > 500:
                tick.recent_trades = tick.recent_trades[-500:]

    def check_health(self):
        """Re-subscribe if trade data appears stalled (B:0 S:0 everywhere)."""
        if not self.ws or not self.connected:
            return
        total_trades = sum(t.buy_volume + t.sell_volume for t in self.ticks.values())
        if total_trades == 0 and self.message_count > 200:
            logger.warning("Trade feed stalled (B:0 S:0) — re-subscribing")
            try:
                for cid in self.contracts:
                    self.ws.send(json.dumps({
                        "type": 1, "target": "SubscribeContractTrades",
                        "arguments": [cid],
                        "invocationId": f"resub-{cid[-8:]}"
                    }) + RECORD_SEP)
            except Exception as e:
                logger.error(f"Re-subscribe failed: {e}")

    def get_snapshot(self, cid: str) -> Optional[MarketTick]:
        with self._lock:
            t = self.ticks.get(cid)
            return t if t and t.last_price > 0 else None


# ── Enhanced Analytics ──────────────────────────────────────────────────
def compute_ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    if len(values) <= period:
        return sum(values) / len(values)
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = (v - ema) * multiplier + ema
    return ema


def compute_atr(bars: List[Dict], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i-1]["c"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    if not trs:
        return 0.0
    return sum(trs[-period:]) / min(period, len(trs))


def get_bar_trend(bars: List[Dict], lookback: int = 5) -> float:
    """Compute bar-based trend direction.
    Returns -1 to +1: positive = uptrend, negative = downtrend.
    Uses close-to-close comparison over last N bars.
    """
    if len(bars) < max(lookback, 2):
        return 0.0
    recent = bars[-lookback:]
    ups = 0
    downs = 0
    total_move = 0.0
    for i in range(1, len(recent)):
        diff = recent[i]["c"] - recent[i-1]["c"]
        if diff > 0:
            ups += 1
        elif diff < 0:
            downs += 1
        total_move += diff
    
    # Combine direction count with magnitude
    direction = (ups - downs) / lookback  # -1 to +1 based on bar count
    # Weight by total movement relative to first bar
    if recent[0]["c"] > 0:
        magnitude = total_move / recent[0]["c"]
        # Amplify if consistent direction
        if abs(direction) > 0.6:
            direction *= 1.3
    return max(-1.0, min(1.0, direction))


def get_windowed_flow(trades: List[Dict], window_seconds: int = 60) -> Tuple[int, int, float]:
    """Get buy/sell flow in a time window.
    Returns (buy_vol, sell_vol, ratio).
    """
    now = time.time()
    cutoff = now - window_seconds
    buy = 0
    sell = 0
    for t in reversed(trades):
        if t["time"] < cutoff:
            break
        if t["side"] == "buy":
            buy += t["volume"]
        elif t["side"] == "sell":
            sell += t["volume"]
    total = buy + sell
    ratio = (buy - sell) / total if total > 0 else 0.0
    return buy, sell, ratio


def detect_regime(bars: List[Dict], atr: float) -> str:
    """Detect market regime: trending, ranging, or volatile.
    Uses ATR vs bar range to determine regime.
    """
    if len(bars) < 10:
        return "unknown"
    
    # Average bar range
    recent = bars[-10:]
    ranges = [b["h"] - b["l"] for b in recent]
    avg_range = sum(ranges) / len(ranges)
    
    # Directional movement
    closes = [b["c"] for b in recent]
    net_move = abs(closes[-1] - closes[0])
    total_path = sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes)))
    
    # Efficiency ratio: net move / total path
    efficiency = net_move / total_path if total_path > 0 else 0
    
    if efficiency > 0.5:
        return "trending"
    elif avg_range > atr * 1.5:
        return "volatile"
    else:
        return "ranging"


def analyze_market(tick: MarketTick, meta: Dict, 
                   active_assets: set = None,
                   equity_consensus: float = 0.0,
                   equity_bar_trend: float = 0.0,
                   has_losses: bool = False) -> Dict:
    """Multi-signal analysis with regime awareness and multi-timeframe confirmation."""
    name = meta.get("name", tick.contract_id[-8:])
    result = {
        "contract": name,
        "contract_id": tick.contract_id,
        "price": tick.last_price,
        "spread_ticks": tick.spread_ticks,
        "signal": "NO_TRADE",
        "conviction": 0,
        "direction": "neutral",
        "thesis": [],
        "score": 0.0,
        "sl_ticks": 20,
        "tp_ticks": 40,
    }

    # ── Gate checks ──
    if tick.tick_count < 10 or tick.last_price <= 0:
        result["thesis"] = ["Insufficient data"]
        return result

    if tick.spread_ticks > 4:
        result["thesis"] = [f"Spread too wide ({tick.spread_ticks}t)"]
        return result

    total_trades = tick.buy_volume + tick.sell_volume
    if total_trades < MIN_FLOW_TRADES:
        result["thesis"] = [f"Too few trades ({total_trades}/{MIN_FLOW_TRADES})"]
        return result

    # Gate: need at least 10 bars so regime detection works (not "unknown")
    if len(tick.bars) < 10:
        result["thesis"] = [f"Bars forming ({len(tick.bars)}/10 min)"]
        return result

    score = 0.0
    direction_score = 0.0
    signals = []

    # ── Signal 1: Windowed Flow (last 60s) — 0-25 pts ──
    w_buy, w_sell, w_ratio = get_windowed_flow(tick.recent_trades, 60)
    w_total = w_buy + w_sell
    if w_total > 10:
        flow_pts = min(25, 25 * abs(w_ratio) / 0.35)
        score += flow_pts
        direction_score += w_ratio * 1.5
        if abs(w_ratio) > 0.15:
            signals.append(f"Flow(60s) {'buy' if w_ratio>0 else 'sell'} {w_ratio:+.2f} (B:{w_buy} S:{w_sell})")

    # ── Signal 2: Cumulative Flow Confirmation — 0-15 pts ──
    total_flow = tick.buy_volume + tick.sell_volume
    if total_flow > 50:
        cum_ratio = (tick.buy_volume - tick.sell_volume) / total_flow
        # Only award if same direction as windowed flow
        if (cum_ratio > 0.05 and w_ratio > 0.05) or (cum_ratio < -0.05 and w_ratio < -0.05):
            score += min(15, 15 * abs(cum_ratio) / 0.3)
            signals.append(f"Cum flow confirms {cum_ratio:+.2f}")

    # ── Signal 3: Bar Trend (multi-timeframe) — 0-20 pts ──
    bar_trend = get_bar_trend(tick.bars, lookback=5)
    if abs(bar_trend) > 0.2:
        trend_pts = min(20, 20 * abs(bar_trend) / 0.6)
        score += trend_pts
        direction_score += bar_trend * 1.5
        signals.append(f"Bars {'+' if bar_trend>0 else '-'} {bar_trend:+.2f}")
        
        # Phase 1: HARD BLOCK if windowed flow contradicts bar trend
        if (w_ratio > 0.15 and bar_trend < -0.3) or (w_ratio < -0.15 and bar_trend > 0.3):
            score = 0
            signals.append("BLOCKED: flow/bars conflict")

    # ── Signal 4: Price Momentum (EMA) — 0-15 pts ──
    if len(tick.price_history) >= 30:
        ema_fast = compute_ema(tick.price_history, 10)
        ema_slow = compute_ema(tick.price_history, 30)
        current = tick.last_price

        mom = (current - ema_slow) / ema_slow if ema_slow > 0 else 0
        if abs(mom) > 0.0002:
            mom_pts = min(15, 15 * abs(mom) / 0.001)
            score += mom_pts
            direction_score += 0.8 if mom > 0 else -0.8
            signals.append(f"Mom {mom:+.4%}")

        if ema_fast > ema_slow and current > ema_fast:
            score += 5
            direction_score += 0.3
        elif ema_fast < ema_slow and current < ema_fast:
            score += 5
            direction_score -= 0.3

    # ── Signal 5: ATR + Regime — 0-10 pts ──
    atr = 0.0
    tick_size = meta.get("tick_size", 0.25)
    atr_ticks = 0.0
    regime = "unknown"
    if len(tick.bars) >= 5:
        atr = compute_atr(tick.bars)
        atr_ticks = atr / tick_size if tick_size > 0 else 0
        regime = detect_regime(tick.bars, atr)

        if 5 <= atr_ticks <= 30:
            vol_pts = 8 - abs(atr_ticks - 12) * 0.4
            score += max(0, vol_pts)
            signals.append(f"ATR {atr_ticks:.1f}t [{regime}]")

            # Phase 2: Regime-adaptive SL/TP profiles
            profile = REGIME_PROFILES.get(regime, REGIME_PROFILES["unknown"])
            if profile["sl_mult"] == 0:
                score = 0
                signals.append(f"BLOCKED: regime={regime}")
            else:
                result["sl_ticks"] = max(15, min(35, int(atr_ticks * profile["sl_mult"])))
                result["tp_ticks"] = max(25, min(80, int(atr_ticks * profile["tp_mult"])))
                result["trail_offset"] = profile["trail_offset"]
                result["trail_act"] = profile["trail_act"]
                if regime == "trending":
                    score += 5
                    signals.append("Trending TP boost")

    # ── Signal 6: Flow Acceleration — 0-10 pts ──
    if len(tick.recent_trades) >= 20:
        recent = tick.recent_trades[-10:]
        older = tick.recent_trades[-20:-10]
        recent_buy = sum(t["volume"] for t in recent if t["side"] == "buy")
        recent_sell = sum(t["volume"] for t in recent if t["side"] == "sell")
        older_buy = sum(t["volume"] for t in older if t["side"] == "buy")
        older_sell = sum(t["volume"] for t in older if t["side"] == "sell")
        net_accel = (recent_buy - recent_sell) - (older_buy - older_sell)

        if abs(net_accel) > 5:
            acc_pts = min(10, 10 * abs(net_accel) / 15)
            score += acc_pts
            direction_score += 0.3 if net_accel > 0 else -0.3
            signals.append(f"Accel {'+' if net_accel>0 else '-'} Δ{net_accel:+d}")

    # ── Signal 7: VWAP Positioning — 0-10 pts ──
    if tick.vwap > 0 and tick.last_price > 0:
        vwap_pct = (tick.last_price - tick.vwap) / tick.vwap
        # Price above VWAP = bullish; below = bearish
        if abs(vwap_pct) > 0.0005:
            vwap_pts = min(10, 10 * abs(vwap_pct) / 0.002)
            if (vwap_pct > 0 and direction_score > 0) or (vwap_pct < 0 and direction_score < 0):
                score += vwap_pts  # Confirming VWAP
                signals.append(f"VWAP {'above' if vwap_pct>0 else 'below'} ({vwap_pct:+.3%})")
            elif (vwap_pct > 0 and direction_score < -0.3) or (vwap_pct < 0 and direction_score > 0.3):
                score *= 0.85  # Slight penalty for going against VWAP
                signals.append(f"[WARN] Against VWAP ({vwap_pct:+.3%})")

    # ── Signal 7b: Activity Level — 0-5 pts ──
    if tick.tick_count > 200:
        score += 5
    elif tick.tick_count > 50:
        score += 3

    # ── Signal 8: Cross-Asset Penalty ──
    asset = meta.get("asset")
    if active_assets and asset in active_assets:
        score *= 0.4
        signals.append("Correlated penalty (×0.4)")

    # ── Signal 9: Spread Cost ──
    if tick.spread_ticks >= 3:
        score -= 5
        signals.append(f"Spread cost ({tick.spread_ticks}t)")

    # ── Signal 10: Equity Consensus (flow + bar trend) ──
    if asset == "equity_index":
        # Combined consensus from flow AND bar trend
        combined = (equity_consensus + equity_bar_trend) / 2
        
        if abs(combined) > 0.15:
            if (direction_score > 0 and combined > 0) or \
               (direction_score < 0 and combined < 0):
                score += 15
                signals.append(f"Equity consensus [OK] (f:{equity_consensus:+.2f} b:{equity_bar_trend:+.2f})")
            elif (direction_score > 0 and combined < -0.2) or \
                 (direction_score < 0 and combined > 0.2):
                score *= 0.2  # 80% penalty for counter-trend
                signals.append(f"[BLOCK] AGAINST consensus (f:{equity_consensus:+.2f} b:{equity_bar_trend:+.2f})")

    # ── Price Trend Veto ──
    # If bars consistently decline but flow says BUY, veto the long.
    # This prevents "buying the dip" in a downtrend.
    if len(tick.bars) >= 5:
        price_trend = get_bar_trend(tick.bars, lookback=5)
        if price_trend < -0.4 and direction_score > 0:
            # Bars falling but flow says buy → likely catching a falling knife
            score *= 0.3  # 70% penalty
            signals.append(f"[BLOCK] Price veto: bars-{price_trend:+.2f} vs flow+")
        elif price_trend > 0.4 and direction_score < 0:
            # Bars rising but flow says sell → likely selling into strength
            score *= 0.3
            signals.append(f"[BLOCK] Price veto: bars+{price_trend:+.2f} vs flow-")

    # ── Determine Direction ──
    if direction_score > 0.3:
        direction = "long"
    elif direction_score < -0.3:
        direction = "short"
    else:
        direction = "neutral"

    # Apply conviction threshold (higher after losses)
    # Session time multiplier — boost during RTH, dampen overnight
    phase, phase_mult = get_session_phase()
    score *= phase_mult
    if phase_mult < 1.0:
        signals.append(f"Session: {phase} (×{phase_mult})")
    elif phase_mult > 1.0:
        signals.append(f"Session: {phase} (×{phase_mult})")
    
    conviction = min(score, 100)
    # Note: threshold is applied by the session class using KaizenEngine adaptive values
    threshold = MIN_CONVICTION_AFTER if has_losses else MIN_CONVICTION_FIRST

    # Hard block: never trade with unknown or volatile regime (safety net)
    if regime in ("unknown", "volatile"):
        conviction = 0
        signals.append(f"BLOCKED: regime {regime}")

    # Phase 1: Time-of-day hard block
    ct_hour = datetime.now(timezone(timedelta(hours=-5))).hour
    if ct_hour < TRADING_HOURS_START or ct_hour >= TRADING_HOURS_END:
        conviction = 0
        signals.append(f"BLOCKED: outside trading hours ({ct_hour}h CT)")

    result.update({
        "signal": "LONG" if direction == "long" and conviction >= threshold else
                  "SHORT" if direction == "short" and conviction >= threshold else "NO_TRADE",
        "conviction": conviction,
        "direction": direction,
        "thesis": signals,
        "score": score,
        "buy_vol": tick.buy_volume,
        "sell_vol": tick.sell_volume,
        "ticks": tick.tick_count,
        "change_pct": tick.change_pct,
        "regime": regime,
        "bar_trend": bar_trend if 'bar_trend' in dir() else 0.0,
        "w_flow": w_ratio if 'w_ratio' in dir() else 0.0,
    })
    return result


# ── Phase 3+4: Kaizen Engine ─────────────────────────────────────────────
class KaizenEngine:
    """Post-trade self-correction and performance tracking."""

    def __init__(self):
        self.log_path = "state/kaizen_log.json"
        self.rolling_window = 20
        # Phase 4: adaptive parameters (start at defaults)
        self.trail_activation_mult = TRAIL_ACTIVATION_MULT
        self.min_conviction_adjustment = 0
        self.sl_mult_adjustment = 1.0
        # Phase 4: per-market performance
        self.market_stats: Dict[str, Dict] = {}
        self._load_history()

    def _load_history(self):
        """Load existing trade history for rolling window analysis."""
        try:
            path = "state/trade_history.json"
            if os.path.exists(path):
                with open(path) as f:
                    history = json.load(f)
                for t in history:
                    cid = t.get("contract", "")
                    if cid not in self.market_stats:
                        self.market_stats[cid] = {"wins": 0, "losses": 0, "total_pnl": 0.0, "trades": 0}
                    stats = self.market_stats[cid]
                    stats["trades"] += 1
                    stats["total_pnl"] += t.get("pnl", 0)
                    if t.get("pnl", 0) > 0:
                        stats["wins"] += 1
                    else:
                        stats["losses"] += 1
        except Exception:
            pass

    def get_rolling_stats(self, trades: List[TradeResult]) -> Dict:
        """Phase 3: Rolling window performance metrics."""
        window = trades[-self.rolling_window:] if len(trades) >= self.rolling_window else trades
        if not window:
            return {"win_rate": 0, "profit_factor": 0, "avg_rr": 0, "count": 0}

        wins = [t for t in window if t.pnl > 0]
        losses = [t for t in window if t.pnl < 0]
        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0.001
        avg_capture = sum(t.profit_capture_ratio for t in window) / len(window) if window else 0

        return {
            "win_rate": len(wins) / len(window) if window else 0,
            "profit_factor": gross_profit / gross_loss,
            "avg_capture_ratio": avg_capture,
            "count": len(window),
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
        }

    def post_trade_review(self, trade: TradeResult):
        """Phase 4: Automated self-correction after every trade."""
        meta = CONTRACT_META.get(trade.contract_id, {})
        tv = meta.get("tick_value", 0.50)
        ts = meta.get("tick_size", 1.0)

        # Update per-market stats
        cid = trade.contract_id
        if cid not in self.market_stats:
            self.market_stats[cid] = {"wins": 0, "losses": 0, "total_pnl": 0.0, "trades": 0}
        stats = self.market_stats[cid]
        stats["trades"] += 1
        stats["total_pnl"] += trade.pnl
        if trade.pnl > 0:
            stats["wins"] += 1
        else:
            stats["losses"] += 1

        # Profit capture ratio
        mfe_potential = trade.mfe * tv if trade.mfe > 0 else 0.001
        ratio = trade.pnl / mfe_potential if mfe_potential > 0.001 else 0

        # Self-correction rules
        adjustments = []

        if ratio < 0.15 and trade.mfe > 5:
            # Found edge but didn't capture → trail too slow
            self.trail_activation_mult = max(0.2, self.trail_activation_mult * 0.92)
            adjustments.append(f"trail_act → {self.trail_activation_mult:.2f} (missed profit)")

        if trade.mfe < trade.sl_ticks * 0.3:
            # Never moved in our favor → signal was wrong
            self.min_conviction_adjustment = min(10, self.min_conviction_adjustment + 1)
            adjustments.append(f"min_conv +{self.min_conviction_adjustment} (bad signal)")

        if trade.hold_time < 60 and trade.pnl < 0:
            # Stopped out too fast → SL too tight
            self.sl_mult_adjustment = min(1.3, self.sl_mult_adjustment * 1.05)
            adjustments.append(f"sl_mult → {self.sl_mult_adjustment:.2f} (fast stop)")

        if trade.pnl > 0:
            # Winning trade — slightly relax parameters toward defaults
            self.trail_activation_mult = min(TRAIL_ACTIVATION_MULT, self.trail_activation_mult * 1.02)
            self.min_conviction_adjustment = max(0, self.min_conviction_adjustment - 0.5)
            self.sl_mult_adjustment = max(1.0, self.sl_mult_adjustment * 0.98)

        if adjustments:
            logger.info(f"  KAIZEN: {'; '.join(adjustments)}")

        # Save to Kaizen log
        self._save_kaizen_entry(trade, ratio, adjustments)

    def _save_kaizen_entry(self, trade: TradeResult, ratio: float, adjustments: List[str]):
        """Phase 3: Persist per-trade instrumentation."""
        try:
            entries = []
            if os.path.exists(self.log_path):
                with open(self.log_path) as f:
                    entries = json.load(f)

            entry = {
                "trade_id": len(entries) + 1,
                "timestamp": trade.timestamp,
                "contract": trade.contract_id,
                "side": trade.side,
                "pnl": trade.pnl,
                "mfe": trade.mfe,
                "mae": trade.mae,
                "hold_time": trade.hold_time,
                "conviction": trade.conviction,
                "regime": trade.regime,
                "profit_capture_ratio": ratio,
                "partial_taken": trade.partial_taken,
                "exit_reason": trade.exit_reason,
                "adjustments": adjustments,
                "adaptive_state": {
                    "trail_act_mult": self.trail_activation_mult,
                    "conv_adj": self.min_conviction_adjustment,
                    "sl_adj": self.sl_mult_adjustment,
                },
            }
            entries.append(entry)
            entries = entries[-500:]
            os.makedirs("state", exist_ok=True)
            with open(self.log_path, "w") as f:
                json.dump(entries, f, indent=2)
        except Exception as e:
            logger.error(f"Kaizen log save error: {e}")

    def get_market_ranking(self) -> List[str]:
        """Phase 4: Return contracts ranked by performance (best first)."""
        if not self.market_stats:
            return list(SCAN_CONTRACTS)

        ranked = []
        for cid, stats in self.market_stats.items():
            if stats["trades"] < 2:
                score = 0
            else:
                win_rate = stats["wins"] / stats["trades"]
                score = stats["total_pnl"] + (win_rate - 0.4) * 50
            ranked.append((cid, score))

        ranked.sort(key=lambda x: -x[1])
        ranked_cids = [c for c, _ in ranked]
        # Always include all contracts but put best first
        for cid in SCAN_CONTRACTS:
            if cid not in ranked_cids:
                ranked_cids.append(cid)
        return ranked_cids

    def get_effective_conviction_threshold(self, has_losses: bool) -> int:
        """Phase 4: Adaptive conviction threshold."""
        base = MIN_CONVICTION_AFTER if has_losses else MIN_CONVICTION_FIRST
        return int(base + self.min_conviction_adjustment)

    def get_effective_sl_mult(self, regime_profile: Dict) -> float:
        """Phase 4: Adaptive SL multiplier."""
        return regime_profile.get("sl_mult", 2.0) * self.sl_mult_adjustment


# ── Main Session ────────────────────────────────────────────────────────
class LiveSessionV4:
    def __init__(self, max_cycles: int = 120, cycle_interval: int = 5):
        self.api = TopStepXClient()
        self.stream: Optional[MarketDataStream] = None
        self.trades: List[TradeResult] = []
        self.active_positions: Dict[str, PositionInfo] = {}
        self.session_pnl = 0.0
        self.start_balance = 0.0
        self.running = True
        self.last_trade_time = 0.0
        self.max_cycles = max_cycles
        self.cycle_interval = cycle_interval
        self.consecutive_losses = 0
        self.kaizen = KaizenEngine()  # Phase 3+4

    def run(self) -> Dict:
        logger.info("=" * 60)
        logger.info("SOVRAN V4 — KAIZEN LIVE SESSION")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Cycles: {self.max_cycles} x {self.cycle_interval}s")
        logger.info(f"Kaizen: trail_act={self.kaizen.trail_activation_mult:.2f} conv_adj={self.kaizen.min_conviction_adjustment} sl_adj={self.kaizen.sl_mult_adjustment:.2f}")
        logger.info("=" * 60)

        if not self.api.authenticate():
            return self._results("auth_failed")

        self.start_balance = self.api.get_account_balance()
        logger.info(f"Balance: ${self.start_balance:,.2f}")

        # Pick up existing positions
        positions = self.api.get_positions()
        orders = self.api.get_open_orders() if positions else []
        for p in positions:
            cid = p["contractId"]
            meta = CONTRACT_META.get(cid, {})
            side = "LONG" if p["type"] == 1 else "SHORT"
            pos_info = PositionInfo(
                contract_id=cid, side=side,
                entry_price=p["averagePrice"], size=p["size"],
                sl_price=0, tp_price=0,
                entry_time=time.time(), order_id=0,
            )
            for o in orders:
                if o.get("contractId") == cid:
                    if o.get("type") == 4:
                        pos_info.sl_price = o.get("stopPrice", 0)
                    elif o.get("type") == 1:
                        pos_info.tp_price = o.get("limitPrice", 0)
            self.active_positions[cid] = pos_info
            logger.info(f"Existing: {side} {p['size']}x {meta.get('name','')} @ {p['averagePrice']} | SL: {pos_info.sl_price} TP: {pos_info.tp_price}")

        # Start WebSocket
        self.stream = MarketDataStream(self.api.token, SCAN_CONTRACTS)
        self.stream.start()

        t0 = time.time()
        while time.time() - t0 < 15:
            if self.stream.message_count > 50:
                break
            time.sleep(0.5)
        logger.info(f"Initial: {self.stream.message_count} messages in {time.time()-t0:.1f}s")

        # ── Main Loop ──
        for cycle in range(1, self.max_cycles + 1):
            if not self.running:
                break
            time.sleep(self.cycle_interval)

            # Check positions
            try:
                api_positions = self.api.get_positions()
            except:
                api_positions = None

            if api_positions is not None:
                open_cids = {p["contractId"] for p in api_positions}
                for cid in list(self.active_positions.keys()):
                    if cid not in open_cids:
                        self._handle_position_closed(cid)
                for cid in self.active_positions:
                    self._update_position_tracking(cid)
                    self._check_trailing_stop(cid)

            # WebSocket health check every 20 cycles
            if cycle % 20 == 0 and self.stream:
                self.stream.check_health()

            # Scan
            analyses = self._scan_markets()

            # Log every 3rd cycle
            if cycle % 3 == 0 or cycle <= 3:
                self._log_scan(cycle, analyses)

            # WebSocket health: check if trade feed is alive
            if cycle > 10 and cycle % 10 == 0:
                total_bsvol = sum(
                    t.buy_volume + t.sell_volume
                    for t in self.stream.ticks.values()
                )
                if total_bsvol == 0:
                    logger.warning("[WARN] Trade feed dead — 0 buy/sell volume. Re-subscribing...")
                    try:
                        for cid in SCAN_CONTRACTS:
                            self.stream.ws.send(json.dumps({
                                "type": 1, "target": "SubscribeContractTrades",
                                "arguments": [cid],
                                "invocationId": f"resub-{cid[-8:]}"
                            }) + RECORD_SEP)
                    except Exception as e:
                        logger.error(f"Re-subscribe failed: {e}")

            # Trade logic
            num_open = len(self.active_positions)
            if num_open < MAX_CONCURRENT_POSITIONS and api_positions is not None:
                if len(self.trades) >= MAX_TRADES_SESSION:
                    continue
                if self.session_pnl < -MAX_DAILY_LOSS:
                    if cycle % 10 == 0:
                        logger.warning(f"Daily loss limit hit: ${self.session_pnl:+.2f}")
                    continue
                if time.time() - self.last_trade_time < TRADE_COOLDOWN:
                    continue
                # Circuit breaker: 3 consecutive losses → wait 5 min
                if self.consecutive_losses >= 3:
                    if time.time() - self.last_trade_time < 1800:
                        if cycle % 20 == 0:
                            logger.warning(f"Circuit breaker: {self.consecutive_losses} consecutive losses, cooling down")
                        continue
                    else:
                        self.consecutive_losses = 0

                held_assets = set()
                for cid in self.active_positions:
                    m = CONTRACT_META.get(cid, {})
                    held_assets.add(m.get("asset"))

                # Phase 4: Use Kaizen-adaptive conviction threshold
                eff_threshold = self.kaizen.get_effective_conviction_threshold(self.consecutive_losses > 0)

                for a in analyses:
                    if a["signal"] not in ("LONG", "SHORT"):
                        continue
                    # Re-check conviction against adaptive threshold
                    if a.get("conviction", 0) < eff_threshold:
                        continue
                    cid = a["contract_id"]
                    if cid in self.active_positions:
                        continue
                    asset = CONTRACT_META.get(cid, {}).get("asset")
                    if asset in held_assets:
                        continue
                    self._execute_trade(a)
                    break

        # Cleanup
        if self.stream:
            self.stream.stop()

        return self._results("complete")

    def _scan_markets(self) -> List[Dict]:
        active_assets = set()
        for cid in self.active_positions:
            meta = CONTRACT_META.get(cid, {})
            active_assets.add(meta.get("asset"))

        # Compute equity consensus: flow + bar trend
        equity_flows = []
        equity_trends = []
        for cid in SCAN_CONTRACTS:
            meta = CONTRACT_META.get(cid, {})
            if meta.get("asset") != "equity_index":
                continue
            tick = self.stream.get_snapshot(cid)
            if not tick:
                continue
            # Windowed flow
            _, _, w_ratio = get_windowed_flow(tick.recent_trades, 60)
            total = tick.buy_volume + tick.sell_volume
            if total > 20:
                equity_flows.append(w_ratio)
            # Bar trend
            if len(tick.bars) >= 3:
                bt = get_bar_trend(tick.bars, lookback=min(5, len(tick.bars)))
                equity_trends.append(bt)

        equity_consensus = sum(equity_flows) / len(equity_flows) if equity_flows else 0.0
        equity_bar_trend = sum(equity_trends) / len(equity_trends) if equity_trends else 0.0
        has_losses = self.consecutive_losses > 0

        analyses = []
        for cid in SCAN_CONTRACTS:
            tick = self.stream.get_snapshot(cid)
            if tick:
                meta = CONTRACT_META.get(cid, {})
                a = analyze_market(tick, meta, active_assets, equity_consensus, equity_bar_trend, has_losses)
                analyses.append(a)

        analyses.sort(key=lambda x: -x["score"])
        return analyses

    def _log_scan(self, cycle: int, analyses: List[Dict]):
        pos_str = ""
        for cid, pos in self.active_positions.items():
            tick = self.stream.get_snapshot(cid)
            if tick:
                meta = CONTRACT_META.get(cid, {})
                tv = meta.get("tick_value", 0.50)
                ts = meta.get("tick_size", 1.0)
                if pos.side == "LONG":
                    unrealized = (tick.last_price - pos.entry_price) / ts * tv
                else:
                    unrealized = (pos.entry_price - tick.last_price) / ts * tv
                trail = " [LOCK]" if pos.trail_active else ""
                pos_str += f" | {pos.side} {meta.get('name','')} ${unrealized:+.2f}{trail}"

        phase, _ = get_session_phase()
        eff_thresh = self.kaizen.get_effective_conviction_threshold(self.consecutive_losses > 0)
        logger.info(f"\n[{cycle}/{self.max_cycles}] msgs={self.stream.message_count} pnl=${self.session_pnl:+.2f} losses={self.consecutive_losses} phase={phase} thresh={eff_thresh}{pos_str}")
        for a in analyses[:6]:
            sig = a["signal"]
            emoji = "[LONG]" if sig == "LONG" else "[SHORT]" if sig == "SHORT" else "[--]"
            logger.info(
                f"  {emoji} {a['contract']:4s} ${a['price']:>10,.2f} | "
                f"spr={a['spread_ticks']:.0f}t B:{a.get('buy_vol',0)} S:{a.get('sell_vol',0)} | "
                f"score={a['score']:.0f} conv={a['conviction']:.0f} | {sig}"
            )
            if sig != "NO_TRADE":
                thesis = "; ".join(a.get("thesis", [])) if isinstance(a.get("thesis"), list) else str(a.get("thesis",""))
                logger.info(f"       → {thesis}")

    def _execute_trade(self, analysis: Dict):
        cid = analysis["contract_id"]
        meta = CONTRACT_META.get(cid, {})
        side = "BUY" if analysis["signal"] == "LONG" else "SELL"
        sl_ticks = analysis.get("sl_ticks", 20)
        tp_ticks = analysis.get("tp_ticks", 40)
        tick_value = meta.get("tick_value", 0.50)

        # Phase 4: Apply Kaizen SL adjustment
        sl_ticks = max(15, int(sl_ticks * self.kaizen.sl_mult_adjustment))

        # Phase 2: Conviction-based sizing
        conviction = analysis.get("conviction", 0)
        size = MAX_POSITION_SIZE
        if conviction >= CONVICTION_SIZE_BOOST and len(self.active_positions) == 0:
            size = MAX_POSITION_SIZE_BOOSTED

        risk = sl_ticks * tick_value * size
        if risk > MAX_DAILY_LOSS - abs(self.session_pnl):
            if size > 1:
                size = 1
                risk = sl_ticks * tick_value
            if risk > MAX_DAILY_LOSS - abs(self.session_pnl):
                logger.warning(f"Risk ${risk:.2f} exceeds remaining daily budget")
                return

        thesis = "; ".join(analysis.get("thesis", []))
        regime = analysis.get("regime", "?")
        logger.info(f"\n>> TRADE: {side} {size}x {meta.get('name',cid)}")
        logger.info(f"   Price: ${analysis['price']:,.2f} | SL: {sl_ticks}t (${risk:.2f}) | TP: {tp_ticks}t | Conv: {conviction:.0f} | Regime: {regime}")
        logger.info(f"   Thesis: {thesis}")

        result = self.api.place_order(cid, side, size, sl_ticks, tp_ticks)
        self.last_trade_time = time.time()

        if result.get("success"):
            tick_size = meta.get("tick_size", 1.0)
            entry = analysis["price"]
            if side == "BUY":
                sl_price = entry - sl_ticks * tick_size
                tp_price = entry + tp_ticks * tick_size
            else:
                sl_price = entry + sl_ticks * tick_size
                tp_price = entry - tp_ticks * tick_size

            # Phase 2: regime-aware trail offset
            trail_offset = analysis.get("trail_offset", TRAIL_OFFSET_TICKS)

            pos_info = PositionInfo(
                contract_id=cid, side="LONG" if side == "BUY" else "SHORT",
                entry_price=entry, size=size,
                sl_price=sl_price, tp_price=tp_price,
                entry_time=time.time(), order_id=result.get("orderId", 0),
                sl_ticks=sl_ticks, tp_ticks=tp_ticks,
                thesis=thesis,
                original_size=size,
                conviction_at_entry=conviction,
                regime_at_entry=regime,
            )
            pos_info._trail_offset = trail_offset
            self.active_positions[cid] = pos_info

    def _update_position_tracking(self, cid: str):
        pos = self.active_positions.get(cid)
        if not pos:
            return
        tick = self.stream.get_snapshot(pos.contract_id)
        if not tick:
            return
        meta = CONTRACT_META.get(pos.contract_id, {})
        ts = meta.get("tick_size", 1.0)

        if pos.side == "LONG":
            excursion = (tick.last_price - pos.entry_price) / ts
        else:
            excursion = (pos.entry_price - tick.last_price) / ts

        pos.mfe = max(pos.mfe, excursion)
        pos.mae = min(pos.mae, excursion)

    def _check_trailing_stop(self, cid: str):
        """Enhanced trailing stop with Phase 1 partial TP and min hold time.
        
        1. Phase 1: No trailing before MIN_HOLD_BEFORE_TRAIL seconds
        2. Phase 1: Partial TP at 0.6x SL → close half, SL to breakeven
        3. Trail activation at adaptive threshold (Phase 4)
        4. Trail tightening with regime-aware offset
        """
        pos = self.active_positions.get(cid)
        if not pos:
            return

        # Phase 1: minimum hold time — let brackets handle risk early on
        if time.time() - pos.entry_time < MIN_HOLD_BEFORE_TRAIL:
            return

        meta = CONTRACT_META.get(pos.contract_id, {})
        ts = meta.get("tick_size", 1.0)
        tv = meta.get("tick_value", 0.50)

        # Phase 1: Partial take-profit at PARTIAL_TP_MULT × SL_ticks
        partial_threshold = pos.sl_ticks * PARTIAL_TP_MULT
        if pos.mfe >= partial_threshold and not pos.partial_taken and pos.original_size >= 1:
            # Close half the position by placing a market order to reduce size
            # (only if we have more than 1 contract, otherwise just move SL to breakeven)
            if pos.side == "LONG":
                be_sl = pos.entry_price + TRAIL_BREAKEVEN_TICKS * ts
            else:
                be_sl = pos.entry_price - TRAIL_BREAKEVEN_TICKS * ts

            try:
                orders = self.api.get_open_orders()
                sl_modified = False
                for o in orders:
                    if o.get("contractId") == cid and o.get("type") == 4:
                        # Validate stop price is on the correct side
                        tick = self.stream.get_snapshot(cid)
                        current_price = tick.last_price if tick else pos.entry_price
                        if pos.side == "LONG" and be_sl >= current_price:
                            be_sl = current_price - 2 * ts  # safety: keep SL below price
                        elif pos.side == "SHORT" and be_sl <= current_price:
                            be_sl = current_price + 2 * ts  # safety: keep SL above price
                        
                        result = self.api.modify_order(o["id"], stop_price=be_sl)
                        if result.get("success"):
                            pos.sl_price = be_sl
                            sl_modified = True
                        break
                
                if sl_modified:
                    pos.partial_taken = True
                    logger.info(f"  PARTIAL TP: {meta.get('name','')} | MFE={pos.mfe:+.0f}t | SL -> breakeven @ {be_sl}")
            except Exception as e:
                logger.error(f"Partial TP error: {e}")
            return  # Don't also trail in the same cycle

        # Phase 4: Use adaptive trail activation from KaizenEngine
        activation_threshold = pos.sl_ticks * self.kaizen.trail_activation_mult

        if pos.mfe >= activation_threshold and not pos.trail_active:
            if pos.side == "LONG":
                new_sl = pos.entry_price + TRAIL_BREAKEVEN_TICKS * ts
            else:
                new_sl = pos.entry_price - TRAIL_BREAKEVEN_TICKS * ts

            try:
                orders = self.api.get_open_orders()
                for o in orders:
                    if o.get("contractId") == cid and o.get("type") == 4:
                        # Validate stop price direction
                        tick = self.stream.get_snapshot(cid)
                        current_price = tick.last_price if tick else pos.entry_price
                        if pos.side == "LONG" and new_sl >= current_price:
                            new_sl = current_price - 2 * ts
                        elif pos.side == "SHORT" and new_sl <= current_price:
                            new_sl = current_price + 2 * ts

                        result = self.api.modify_order(o["id"], stop_price=new_sl)
                        if result.get("success"):
                            pos.trail_active = True
                            pos.trail_stop = new_sl
                            pos.sl_price = new_sl
                            logger.info(f"  TRAIL ON: {meta.get('name','')} | SL -> BE+{TRAIL_BREAKEVEN_TICKS}t @ {new_sl}")
                        else:
                            logger.warning(f"Trail SL modify failed: {result}")
                        break
            except Exception as e:
                logger.error(f"Trail stop error: {e}")

        elif pos.trail_active:
            # Trail tightening — use regime-aware offset
            trail_offset = getattr(pos, '_trail_offset', TRAIL_OFFSET_TICKS)

            if pos.side == "LONG":
                ideal_sl = pos.entry_price + (pos.mfe - trail_offset) * ts
            else:
                ideal_sl = pos.entry_price - (pos.mfe - trail_offset) * ts

            should_update = False
            if pos.side == "LONG" and ideal_sl > pos.sl_price + ts:
                # Validate: SL must be below current price for LONG
                tick = self.stream.get_snapshot(cid)
                if tick and ideal_sl < tick.last_price:
                    should_update = True
            elif pos.side == "SHORT" and ideal_sl < pos.sl_price - ts:
                # Validate: SL must be above current price for SHORT
                tick = self.stream.get_snapshot(cid)
                if tick and ideal_sl > tick.last_price:
                    should_update = True

            if should_update:
                try:
                    orders = self.api.get_open_orders()
                    for o in orders:
                        if o.get("contractId") == cid and o.get("type") == 4:
                            result = self.api.modify_order(o["id"], stop_price=ideal_sl)
                            if result.get("success"):
                                pos.trail_stop = ideal_sl
                                pos.sl_price = ideal_sl
                                logger.info(f"  TRAIL >>: {meta.get('name','')} | SL -> {ideal_sl} (MFE: {pos.mfe:+.0f}t)")
                            break
                except Exception as e:
                    logger.error(f"Trail tighten error: {e}")

    def _handle_position_closed(self, cid: str):
        pos = self.active_positions.get(cid)
        if not pos:
            return

        meta = CONTRACT_META.get(pos.contract_id, {})
        tv = meta.get("tick_value", 0.50)
        ts = meta.get("tick_size", 1.0)

        new_balance = self.api.get_account_balance()
        trade_pnl = new_balance - self.start_balance - self.session_pnl

        if trade_pnl > 0:
            exit_reason = "TARGET_HIT" if not pos.trail_active else "TRAIL_STOP"
            self.consecutive_losses = 0
        elif trade_pnl < 0:
            exit_reason = "STOP_HIT"
            self.consecutive_losses += 1
        else:
            exit_reason = "BREAKEVEN"

        if pos.side == "LONG":
            exit_price = pos.entry_price + (trade_pnl / tv) * ts
        else:
            exit_price = pos.entry_price - (trade_pnl / tv) * ts

        hold_time = time.time() - pos.entry_time
        ticks = trade_pnl / tv

        # Phase 3: compute profit capture ratio
        mfe_potential = pos.mfe * tv if pos.mfe > 0 else 0.001
        capture_ratio = trade_pnl / mfe_potential if mfe_potential > 0.001 else 0

        result = TradeResult(
            contract_id=pos.contract_id, side=pos.side,
            entry_price=pos.entry_price, exit_price=exit_price,
            size=pos.size, pnl=trade_pnl, ticks=ticks,
            hold_time=hold_time, exit_reason=exit_reason,
            mfe=pos.mfe, mae=pos.mae, thesis=pos.thesis,
            timestamp=datetime.now(timezone.utc).isoformat(),
            conviction=pos.conviction_at_entry,
            regime=pos.regime_at_entry,
            partial_taken=pos.partial_taken,
            profit_capture_ratio=capture_ratio,
        )
        self.trades.append(result)
        self.session_pnl += trade_pnl

        emoji = "W" if trade_pnl > 0 else "L" if trade_pnl < 0 else "-"
        logger.info(f"\n[{emoji}] CLOSED: {result.side} {meta.get('name','')} | PnL: ${trade_pnl:+.2f} ({ticks:+.0f}t) | {exit_reason}")
        logger.info(f"   MFE: {pos.mfe:+.0f}t | MAE: {pos.mae:+.0f}t | Trail: {'Y' if pos.trail_active else 'N'} | Partial: {'Y' if pos.partial_taken else 'N'} | Capture: {capture_ratio:.1%}")
        logger.info(f"   Hold: {hold_time:.0f}s | Balance: ${new_balance:,.2f} | Losses: {self.consecutive_losses}")

        # Phase 3+4: Kaizen post-trade review
        self.kaizen.post_trade_review(result)

        # Phase 3: Log rolling stats
        stats = self.kaizen.get_rolling_stats(self.trades)
        if stats["count"] >= 3:
            logger.info(f"   ROLLING({stats['count']}): WR={stats['win_rate']:.0%} PF={stats['profit_factor']:.2f} Capture={stats['avg_capture_ratio']:.1%}")

        # Record outcome to AI trading memory (Bayesian learning)
        try:
            _strategy = "momentum" if "P(continuation)" in pos.thesis else "mean_reversion"
            _regime = pos.regime_at_entry if pos.regime_at_entry else "unknown"
            import subprocess as _sp
            _sp.run([
                sys.executable,
                str(Path(__file__).parent / "ipc" / "record_trade_outcome.py"),
                pos.contract_id,
                _strategy,
                _regime,
                str(trade_pnl),
                str(hold_time),
                str(getattr(pos, "mfe", 0.0)),
                str(getattr(pos, "mae", 0.0)),
            ], check=False, timeout=10)
        except Exception as _e:
            logger.warning(f"Failed to record AI outcome: {_e}")

        # Save to trade history
        self._save_trade_history(result)

        if cid in self.active_positions:
            del self.active_positions[cid]
        self.start_balance = new_balance - self.session_pnl

    def _save_trade_history(self, trade: TradeResult):
        """Persist trade to state/trade_history.json."""
        path = "state/trade_history.json"
        try:
            if os.path.exists(path):
                with open(path) as f:
                    history = json.load(f)
            else:
                history = []
            history.append({
                "contract": trade.contract_id,
                "side": trade.side,
                "entry": trade.entry_price,
                "exit": trade.exit_price,
                "pnl": trade.pnl,
                "ticks": trade.ticks,
                "hold_time": trade.hold_time,
                "exit_reason": trade.exit_reason,
                "mfe": trade.mfe,
                "mae": trade.mae,
                "thesis": trade.thesis,
                "timestamp": trade.timestamp,
            })
            history = history[-200:]
            os.makedirs("state", exist_ok=True)
            with open(path, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Save history error: {e}")

    def _results(self, status: str) -> Dict:
        final_balance = self.api.get_account_balance() if self.api.token else 0
        return {
            "status": status,
            "duration_seconds": time.time() - (self.stream.ticks[SCAN_CONTRACTS[0]].timestamp or time.time()) if self.stream else 0,
            "messages_received": self.stream.message_count if self.stream else 0,
            "trades": [
                {
                    "contract": t.contract_id,
                    "side": t.side,
                    "entry": t.entry_price,
                    "exit": t.exit_price,
                    "pnl": t.pnl,
                    "ticks": t.ticks,
                    "hold_time": t.hold_time,
                    "exit_reason": t.exit_reason,
                    "mfe": t.mfe,
                    "mae": t.mae,
                }
                for t in self.trades
            ],
            "session_pnl": self.session_pnl,
            "start_balance": self.start_balance,
            "end_balance": final_balance,
            "consecutive_losses": self.consecutive_losses,
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=120, help="Number of scan cycles")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between cycles")
    args = parser.parse_args()

    session = LiveSessionV4(max_cycles=args.cycles, cycle_interval=args.interval)
    results = session.run()

    with open("live_session_v4_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"\nSession: {results['status']}")
    logger.info(f"Trades: {len(results['trades'])} | PnL: ${results['session_pnl']:+.2f}")
    logger.info(f"Balance: ${results.get('end_balance',0):,.2f}")
