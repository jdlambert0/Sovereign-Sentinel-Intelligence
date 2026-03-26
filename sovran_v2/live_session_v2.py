#!/usr/bin/env python3
"""
Sovran V2 — Live Trading Session v2
Enhanced with:
  - Position monitoring with trailing stops
  - Smarter multi-timeframe scoring  
  - Cross-asset confirmation
  - Session PnL tracking
  - Auto-close before session end
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
    "CON.F.US.MGC.J26",
    "CON.F.US.MCLE.K26",
]

CONTRACT_META = {
    "CON.F.US.MNQ.M26": {"name": "MNQ", "tick_size": 0.25, "tick_value": 0.50, "point_value": 2.00, "asset": "equity_index"},
    "CON.F.US.MES.M26": {"name": "MES", "tick_size": 0.25, "tick_value": 1.25, "point_value": 5.00, "asset": "equity_index"},
    "CON.F.US.MYM.M26": {"name": "MYM", "tick_size": 1.00, "tick_value": 0.50, "point_value": 0.50, "asset": "equity_index"},
    "CON.F.US.M2K.M26": {"name": "M2K", "tick_size": 0.10, "tick_value": 0.50, "point_value": 5.00, "asset": "equity_index"},
    "CON.F.US.MGC.J26": {"name": "MGC", "tick_size": 0.10, "tick_value": 1.00, "point_value": 10.00, "asset": "metals"},
    "CON.F.US.MCLE.K26": {"name": "MCL", "tick_size": 0.01, "tick_value": 1.00, "point_value": 100.00, "asset": "energy"},
}

# Risk parameters
MAX_POSITION_SIZE = 1
MAX_CONCURRENT_POSITIONS = 2  # Allow 2 non-correlated positions
MAX_DAILY_LOSS = 500.0
MAX_TRADES_SESSION = 6
TRADE_COOLDOWN = 60  # seconds between trades
MIN_CONVICTION = 55

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("live_session_v2.log"),
    ],
)
logger = logging.getLogger("sovran_v2")


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
    book_imbalance: float = 0.0
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


@dataclass
class PositionInfo:
    contract_id: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    size: int
    sl_price: float
    tp_price: float
    entry_time: float
    order_id: int
    mfe: float = 0.0  # Max favorable excursion in ticks
    mae: float = 0.0  # Max adverse excursion in ticks
    trail_active: bool = False
    trail_stop: float = 0.0


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
            logger.info(f"  ✅ Filled! Order ID: {data.get('orderId')}")
        else:
            logger.error(f"  ❌ Failed: code={data.get('errorCode')} msg={data.get('errorMessage')}")
        return data

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
            logger.info(f"WS subscribed to {len(self.contracts)} contracts (quotes + trades)")
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

    def _process_quote(self, tick: MarketTick, q: Dict):
        now = time.time()
        if "lastPrice" in q:
            p = float(q["lastPrice"])
            tick.last_price = p
            tick.price_history.append(p)
            if len(tick.price_history) > 1000:
                tick.price_history = tick.price_history[-1000:]
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
                    if len(tick.bars) > 60:
                        tick.bars = tick.bars[-60:]
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
            if len(tick.recent_trades) > 300:
                tick.recent_trades = tick.recent_trades[-300:]

    def get_snapshot(self, cid: str) -> Optional[MarketTick]:
        with self._lock:
            t = self.ticks.get(cid)
            return t if t and t.last_price > 0 else None


# ── Enhanced Market Scoring ─────────────────────────────────────────────
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
    """Average True Range from OHLC bars."""
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


def analyze_market(tick: MarketTick, meta: Dict, active_assets: set = None,
                    equity_consensus: float = 0.0) -> Dict:
    """Multi-signal market analysis with conviction scoring.
    
    Args:
        equity_consensus: -1 to +1, aggregate equity index flow direction.
                         Used to veto counter-trend entries on equity contracts.
    """
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

    if tick.tick_count < 10 or tick.last_price <= 0:
        result["thesis"] = ["Insufficient data"]
        return result

    if tick.spread_ticks > 4:
        result["thesis"] = [f"Spread too wide ({tick.spread_ticks}t)"]
        return result

    # Require minimum trade count for reliable flow signals
    total_trades = tick.buy_volume + tick.sell_volume
    if total_trades < 30:
        result["thesis"] = [f"Too few trades ({total_trades}) for reliable signal"]
        return result

    score = 0.0
    direction_score = 0.0
    signals = []

    # ── Signal 1: Trade Flow Imbalance (0-30 pts) ──
    total_flow = tick.buy_volume + tick.sell_volume
    if total_flow > 20:  # Need meaningful sample
        flow_ratio = (tick.buy_volume - tick.sell_volume) / total_flow
        flow_pts = min(30, 30 * abs(flow_ratio) / 0.4)
        score += flow_pts
        direction_score += flow_ratio * 2
        if abs(flow_ratio) > 0.15:
            signals.append(f"Flow {'buy' if flow_ratio>0 else 'sell'} {flow_ratio:+.2f}")

    # ── Signal 2: Price Momentum (0-20 pts) ──
    if len(tick.price_history) >= 30:
        ema_fast = compute_ema(tick.price_history, 10)
        ema_slow = compute_ema(tick.price_history, 30)
        current = tick.last_price

        mom = (current - ema_slow) / ema_slow if ema_slow > 0 else 0
        if abs(mom) > 0.0002:
            mom_pts = min(20, 20 * abs(mom) / 0.001)
            score += mom_pts
            direction_score += 1.0 if mom > 0 else -1.0
            signals.append(f"Momentum {mom:+.4%}")

        # EMA cross
        if ema_fast > ema_slow and current > ema_fast:
            score += 5
            direction_score += 0.5
            signals.append("EMA bullish")
        elif ema_fast < ema_slow and current < ema_fast:
            score += 5
            direction_score -= 0.5
            signals.append("EMA bearish")

    # ── Signal 3: Flow Acceleration (0-15 pts) ──
    if len(tick.recent_trades) >= 20:
        recent = tick.recent_trades[-10:]
        older = tick.recent_trades[-20:-10]
        recent_buy_vol = sum(t["volume"] for t in recent if t["side"] == "buy")
        recent_sell_vol = sum(t["volume"] for t in recent if t["side"] == "sell")
        older_buy_vol = sum(t["volume"] for t in older if t["side"] == "buy")
        older_sell_vol = sum(t["volume"] for t in older if t["side"] == "sell")

        buy_accel = recent_buy_vol - older_buy_vol
        sell_accel = recent_sell_vol - older_sell_vol
        net_accel = buy_accel - sell_accel

        if abs(net_accel) > 3:
            acc_pts = min(15, 15 * abs(net_accel) / 10)
            score += acc_pts
            direction_score += 0.5 if net_accel > 0 else -0.5
            signals.append(f"Flow accel {'buy' if net_accel>0 else 'sell'} Δ{net_accel:+d}")

    # ── Signal 4: Volatility Sweet Spot (0-10 pts) ──
    if len(tick.bars) >= 3:
        atr = compute_atr(tick.bars)
        tick_size = meta.get("tick_size", 0.25)
        atr_ticks = atr / tick_size if tick_size > 0 else 0

        # Sweet spot: ATR between 5-30 ticks (enough movement, not chaotic)
        if 5 <= atr_ticks <= 30:
            vol_pts = 10 - abs(atr_ticks - 15) * 0.5
            score += max(0, vol_pts)
            signals.append(f"ATR {atr_ticks:.1f}t")

            # Dynamic SL/TP based on ATR — floor of 15 ticks for overnight safety
            result["sl_ticks"] = max(15, min(30, int(atr_ticks * 1.5)))
            result["tp_ticks"] = max(30, min(60, int(atr_ticks * 3.0)))

    # ── Signal 5: Activity Level (0-10 pts) ──
    if tick.tick_count > 100:
        score += 10
        signals.append("Active market")
    elif tick.tick_count > 30:
        score += 5

    # ── Signal 6: Cross-Asset Correlation Penalty ──
    asset = meta.get("asset")
    if active_assets and asset in active_assets:
        score *= 0.5
        signals.append("Correlated position penalty")

    # ── Signal 7: Spread Cost Penalty ──
    if tick.spread_ticks >= 3:
        score -= 5
        signals.append(f"Wide spread penalty ({tick.spread_ticks}t)")

    # ── Signal 8: Cross-Market Consensus (equity indices) ──
    asset = meta.get("asset")
    if asset == "equity_index" and abs(equity_consensus) > 0.15:
        # Reward trading WITH consensus, penalize AGAINST
        if (direction_score > 0 and equity_consensus > 0) or \
           (direction_score < 0 and equity_consensus < 0):
            score += 15
            signals.append(f"Equity consensus confirms ({equity_consensus:+.2f})")
        elif (direction_score > 0 and equity_consensus < -0.15) or \
             (direction_score < 0 and equity_consensus > 0.15):
            score *= 0.3  # Heavy penalty for counter-trend
            signals.append(f"⚠️ AGAINST equity consensus ({equity_consensus:+.2f})")

    # ── Determine Direction ──
    if direction_score > 0.3:
        direction = "long"
    elif direction_score < -0.3:
        direction = "short"
    else:
        direction = "neutral"

    conviction = min(score, 100)
    threshold = MIN_CONVICTION

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
    })
    return result


# ── Main Session ────────────────────────────────────────────────────────
class LiveSessionV2:
    def __init__(self, max_cycles: int = 60, cycle_interval: int = 5):
        self.api = TopStepXClient()
        self.stream: Optional[MarketDataStream] = None
        self.trades: List[TradeResult] = []
        self.active_position: Optional[PositionInfo] = None
        self.active_positions: Dict[str, PositionInfo] = {}  # contract_id -> PositionInfo
        self.session_pnl = 0.0
        self.start_balance = 0.0
        self.running = True
        self.last_trade_time = 0.0
        self.max_cycles = max_cycles
        self.cycle_interval = cycle_interval

    def run(self) -> Dict:
        logger.info("=" * 60)
        logger.info("SOVRAN V2 — LIVE SESSION v2")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Cycles: {self.max_cycles} × {self.cycle_interval}s")
        logger.info("=" * 60)

        # Auth
        if not self.api.authenticate():
            return self._results("auth_failed")

        # Account check
        self.start_balance = self.api.get_account_balance()
        logger.info(f"Balance: ${self.start_balance:,.2f}")

        # Check existing positions
        positions = self.api.get_positions()
        orders = self.api.get_open_orders() if positions else []
        for p in positions:
            cid = p["contractId"]
            meta = CONTRACT_META.get(cid, {})
            side = "LONG" if p["type"] == 1 else "SHORT"
            pos_info = PositionInfo(
                contract_id=cid,
                side=side,
                entry_price=p["averagePrice"],
                size=p["size"],
                sl_price=0, tp_price=0,
                entry_time=time.time(),
                order_id=0,
            )
            # Get bracket prices for this position
            for o in orders:
                if o.get("contractId") == cid:
                    if o.get("type") == 4:  # SL
                        pos_info.sl_price = o.get("stopPrice", 0)
                    elif o.get("type") == 1:  # TP
                        pos_info.tp_price = o.get("limitPrice", 0)
            self.active_positions[cid] = pos_info
            self.active_position = pos_info  # Keep backward compat
            logger.info(f"Existing position: {side} {p['size']}x {meta.get('name','')} @ {p['averagePrice']}")
            logger.info(f"  SL: {pos_info.sl_price} | TP: {pos_info.tp_price}")

        # Start WebSocket
        logger.info(f"Starting market data for {len(SCAN_CONTRACTS)} contracts...")
        self.stream = MarketDataStream(self.api.token, SCAN_CONTRACTS)
        self.stream.start()

        # Wait for initial data
        t0 = time.time()
        while time.time() - t0 < 15:
            if self.stream.message_count > 50:
                break
            time.sleep(0.5)
        logger.info(f"Initial data: {self.stream.message_count} messages in {time.time()-t0:.1f}s")

        # ── Main Loop ──
        for cycle in range(1, self.max_cycles + 1):
            if not self.running:
                break
            time.sleep(self.cycle_interval)

            # Check for position closures
            try:
                api_positions = self.api.get_positions()
            except:
                api_positions = None

            if api_positions is not None:
                # Build set of currently open contract IDs
                open_cids = {p["contractId"] for p in api_positions}
                # Check for closed positions
                for cid in list(self.active_positions.keys()):
                    if cid not in open_cids:
                        self._handle_position_closed(cid)
                # Update excursion tracking for remaining
                for cid in self.active_positions:
                    self._update_position_tracking(cid)
                # Update backward compat
                if self.active_positions:
                    self.active_position = list(self.active_positions.values())[0]
                else:
                    self.active_position = None

            # Scan markets
            analyses = self._scan_markets()

            # Log
            if cycle % 3 == 0 or cycle <= 3:  # Log every 3rd cycle + first 3
                self._log_scan(cycle, analyses)

            # Trade logic — allow up to MAX_CONCURRENT_POSITIONS
            num_open = len(self.active_positions)
            if num_open < MAX_CONCURRENT_POSITIONS and api_positions is not None:
                if len(self.trades) >= MAX_TRADES_SESSION:
                    continue
                if self.session_pnl < -MAX_DAILY_LOSS:
                    continue
                if time.time() - self.last_trade_time < TRADE_COOLDOWN:
                    continue

                # Find best signal that isn't in an asset class we already hold
                held_assets = set()
                for cid in self.active_positions:
                    m = CONTRACT_META.get(cid, {})
                    held_assets.add(m.get("asset"))

                for a in analyses:
                    if a["signal"] not in ("LONG", "SHORT"):
                        continue
                    cid = a["contract_id"]
                    if cid in self.active_positions:
                        continue  # Already have this contract
                    asset = CONTRACT_META.get(cid, {}).get("asset")
                    if asset in held_assets:
                        continue  # Same asset class
                    self._execute_trade(a)
                    break  # One trade per cycle

        # Cleanup
        if self.stream:
            self.stream.stop()

        return self._results("complete")

    def _scan_markets(self) -> List[Dict]:
        active_assets = set()
        for cid in self.active_positions:
            meta = CONTRACT_META.get(cid, {})
            active_assets.add(meta.get("asset"))

        # Compute equity index consensus (aggregate flow direction)
        equity_flows = []
        for cid in SCAN_CONTRACTS:
            meta = CONTRACT_META.get(cid, {})
            if meta.get("asset") != "equity_index":
                continue
            tick = self.stream.get_snapshot(cid)
            if tick:
                total = tick.buy_volume + tick.sell_volume
                if total > 20:
                    flow_ratio = (tick.buy_volume - tick.sell_volume) / total
                    equity_flows.append(flow_ratio)
        equity_consensus = sum(equity_flows) / len(equity_flows) if equity_flows else 0.0

        analyses = []
        for cid in SCAN_CONTRACTS:
            tick = self.stream.get_snapshot(cid)
            if tick:
                meta = CONTRACT_META.get(cid, {})
                a = analyze_market(tick, meta, active_assets, equity_consensus)
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
                pos_str += f" | {pos.side} {meta.get('name','')} ${unrealized:+.2f}"

        logger.info(f"\n[{cycle}/{self.max_cycles}] msgs={self.stream.message_count} session_pnl=${self.session_pnl:+.2f}{pos_str}")
        for a in analyses[:6]:
            sig = a["signal"]
            emoji = "🟢" if sig == "LONG" else "🔴" if sig == "SHORT" else "⚪"
            thesis = "; ".join(a.get("thesis", [])) if isinstance(a.get("thesis"), list) else str(a.get("thesis",""))
            logger.info(
                f"  {emoji} {a['contract']:4s} ${a['price']:>10,.2f} | "
                f"spr={a['spread_ticks']:.0f}t B:{a.get('buy_vol',0)} S:{a.get('sell_vol',0)} | "
                f"score={a['score']:.0f} conv={a['conviction']:.0f} | {sig}"
            )
            if thesis and sig != "NO_TRADE":
                logger.info(f"       → {thesis}")

    def _execute_trade(self, analysis: Dict):
        cid = analysis["contract_id"]
        meta = CONTRACT_META.get(cid, {})
        side = "BUY" if analysis["signal"] == "LONG" else "SELL"
        sl_ticks = analysis.get("sl_ticks", 20)
        tp_ticks = analysis.get("tp_ticks", 40)
        tick_value = meta.get("tick_value", 0.50)

        risk = sl_ticks * tick_value
        if risk > MAX_DAILY_LOSS - abs(self.session_pnl):
            logger.warning(f"Risk ${risk:.2f} exceeds remaining daily budget")
            return

        thesis = "; ".join(analysis.get("thesis", []))
        logger.info(f"\n🎯 TRADE: {side} {MAX_POSITION_SIZE}x {meta.get('name',cid)}")
        logger.info(f"   Price: ${analysis['price']:,.2f} | SL: {sl_ticks}t (${risk:.2f}) | TP: {tp_ticks}t | Conv: {analysis['conviction']:.0f}")
        logger.info(f"   Thesis: {thesis}")

        result = self.api.place_order(cid, side, MAX_POSITION_SIZE, sl_ticks, tp_ticks)
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

            pos_info = PositionInfo(
                contract_id=cid, side="LONG" if side == "BUY" else "SHORT",
                entry_price=entry, size=MAX_POSITION_SIZE,
                sl_price=sl_price, tp_price=tp_price,
                entry_time=time.time(), order_id=result.get("orderId", 0),
            )
            self.active_positions[cid] = pos_info
            self.active_position = pos_info
        else:
            # Record failed attempt
            self.trades.append(TradeResult(
                contract_id=cid, side=side, entry_price=analysis["price"],
                exit_price=0, size=MAX_POSITION_SIZE, pnl=0, ticks=0,
                hold_time=0, exit_reason=f"ORDER_FAILED:{result.get('errorCode')}",
                mfe=0, mae=0, thesis=thesis,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

    def _update_position_tracking(self, cid: str = None):
        pos = self.active_positions.get(cid) if cid else self.active_position
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

    def _handle_position_closed(self, cid: str = None):
        pos = self.active_positions.get(cid) if cid else self.active_position
        if not pos:
            return

        meta = CONTRACT_META.get(pos.contract_id, {})
        tv = meta.get("tick_value", 0.50)
        ts = meta.get("tick_size", 1.0)

        # Try to get fill price from balance change
        new_balance = self.api.get_account_balance()
        trade_pnl = new_balance - self.start_balance - self.session_pnl

        # Determine exit reason
        if trade_pnl > 0:
            exit_reason = "TARGET_HIT"
        elif trade_pnl < 0:
            exit_reason = "STOP_HIT"
        else:
            exit_reason = "UNKNOWN"

        # Approximate exit price
        if pos.side == "LONG":
            exit_price = pos.entry_price + (trade_pnl / tv) * ts
        else:
            exit_price = pos.entry_price - (trade_pnl / tv) * ts

        hold_time = time.time() - pos.entry_time
        ticks = trade_pnl / tv

        result = TradeResult(
            contract_id=pos.contract_id,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size=pos.size,
            pnl=trade_pnl,
            ticks=ticks,
            hold_time=hold_time,
            exit_reason=exit_reason,
            mfe=pos.mfe,
            mae=pos.mae,
            thesis="",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.trades.append(result)
        self.session_pnl += trade_pnl

        emoji = "💰" if trade_pnl > 0 else "💀"
        logger.info(f"\n{emoji} TRADE CLOSED: {result.side} {meta.get('name','')} | PnL: ${trade_pnl:+.2f} ({ticks:+.0f}t) | {exit_reason} | Hold: {hold_time:.0f}s")
        logger.info(f"   MFE: {pos.mfe:+.0f}t | MAE: {pos.mae:+.0f}t | Balance: ${new_balance:,.2f}")

        # Remove from active positions
        if cid and cid in self.active_positions:
            del self.active_positions[cid]
        self.active_position = list(self.active_positions.values())[0] if self.active_positions else None
        self.start_balance = new_balance - self.session_pnl

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
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=60, help="Number of scan cycles")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between cycles")
    args = parser.parse_args()

    session = LiveSessionV2(max_cycles=args.cycles, cycle_interval=args.interval)
    results = session.run()

    with open("live_session_v2_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"\nSession: {results['status']}")
    logger.info(f"Trades: {len(results['trades'])} | PnL: ${results['session_pnl']:+.2f}")
    logger.info(f"Balance: ${results.get('end_balance',0):,.2f}")
