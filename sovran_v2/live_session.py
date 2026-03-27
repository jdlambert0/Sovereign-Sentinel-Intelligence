#!/usr/bin/env python3
"""
Sovran V2 — Live Trading Session
Connects to TopStepX, streams market data, scans for setups, and trades.
"""
import asyncio
import json
import logging
import os
import sys
import time
import signal
import threading
import websocket
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

# Add pylibs
sys.path.insert(0, "/tmp/pylibs")

import httpx

# ── Config ──────────────────────────────────────────────────────────────
API_KEY = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="
USERNAME = "jessedavidlambert@gmail.com"
BASE_URL = "https://api.topstepx.com"
WS_URL = "wss://rtc.topstepx.com/hubs/market"
RECORD_SEP = "\x1e"
ACCOUNT_ID = 20560125

# Micro contracts to scan (low risk, good liquidity)
SCAN_CONTRACTS = [
    "CON.F.US.MNQ.M26",  # Micro Nasdaq
    "CON.F.US.MES.M26",  # Micro S&P
    "CON.F.US.MYM.M26",  # Micro Dow
    "CON.F.US.M2K.M26",  # Micro Russell
    "CON.F.US.MGC.J26",  # Micro Gold
    "CON.F.US.MCLE.K26", # Micro Crude
]

CONTRACT_META = {
    "CON.F.US.MNQ.M26": {"name": "MNQ", "tick_size": 0.25, "tick_value": 0.50, "point_value": 2.00, "asset": "equity_index"},
    "CON.F.US.MES.M26": {"name": "MES", "tick_size": 0.25, "tick_value": 1.25, "point_value": 5.00, "asset": "equity_index"},
    "CON.F.US.MYM.M26": {"name": "MYM", "tick_size": 1.00, "tick_value": 0.50, "point_value": 0.50, "asset": "equity_index"},
    "CON.F.US.M2K.M26": {"name": "M2K", "tick_size": 0.10, "tick_value": 0.50, "point_value": 5.00, "asset": "equity_index"},
    "CON.F.US.MGC.J26": {"name": "MGC", "tick_size": 0.10, "tick_value": 1.00, "point_value": 10.00, "asset": "metals"},
    "CON.F.US.MCLE.K26":{"name": "MCL", "tick_size": 0.01, "tick_value": 1.00, "point_value": 100.00, "asset": "energy"},
}

# Risk parameters — conservative
MAX_POSITION_SIZE = 1      # 1 micro lot only
MAX_DAILY_LOSS = 500.0     # $500 daily loss cap
MAX_TRADES_SESSION = 8     # max trades per session
MIN_SPREAD_TICKS = 0       # minimum acceptable spread
MAX_SPREAD_TICKS = 4       # max acceptable spread in ticks

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("live_session.log"),
    ],
)
logger = logging.getLogger("live_session")


# ── Data Structures ─────────────────────────────────────────────────────
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
    # L2 depth
    l2_bids: List[Tuple[float, int]] = field(default_factory=list)  # (price, vol)
    l2_asks: List[Tuple[float, int]] = field(default_factory=list)
    # Derived
    spread: float = 0.0
    spread_ticks: float = 0.0
    book_imbalance: float = 0.0
    # Trade flow tracking
    buy_volume: int = 0
    sell_volume: int = 0
    recent_trades: List[Dict] = field(default_factory=list)
    # Price history for simple analysis
    price_history: List[float] = field(default_factory=list)
    high: float = 0.0
    low: float = float('inf')


@dataclass
class TradeRecord:
    contract_id: str
    side: str  # "BUY" or "SELL"
    entry_price: float
    size: int
    sl_ticks: int
    tp_ticks: int
    order_id: int = 0
    entry_time: float = 0.0
    exit_price: float = 0.0
    exit_time: float = 0.0
    pnl: float = 0.0
    status: str = "pending"  # pending, open, closed, error
    thesis: str = ""


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
                self.token_expiry = time.time() + 3600  # 1hr
                logger.info("Authenticated successfully")
                return True
            else:
                logger.error(f"Auth failed: errorCode={data.get('errorCode')}")
                return False
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return False

    def _headers(self) -> Dict[str, str]:
        if time.time() > self.token_expiry - 60:
            self.authenticate()  # refresh
        return {"Authorization": f"Bearer {self.token}"}

    def get_account_info(self) -> Dict:
        r = self.client.post("/api/Account/search",
                            json={"onlyActiveAccounts": True},
                            headers=self._headers())
        return r.json()

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
        """Place a bracket order. side = 'BUY' or 'SELL'.
        
        TopStepX bracket tick convention:
        - BUY (long):  SL ticks negative (below entry), TP ticks positive (above)
        - SELL (short): SL ticks positive (above entry), TP ticks negative (below)
        """
        order_side = 0 if side == "BUY" else 1  # 0=Bid, 1=Ask
        
        # Sign convention: SL is adverse direction, TP is favorable
        if side == "BUY":
            sl_signed = -abs(sl_ticks)   # SL below for longs
            tp_signed = abs(tp_ticks)    # TP above for longs
        else:
            sl_signed = abs(sl_ticks)    # SL above for shorts
            tp_signed = -abs(tp_ticks)   # TP below for shorts
        
        payload = {
            "accountId": ACCOUNT_ID,
            "contractId": contract_id,
            "type": 2,  # Market
            "side": order_side,
            "size": size,
            "stopLossBracket": {"ticks": sl_signed, "type": 4},    # Stop
            "takeProfitBracket": {"ticks": tp_signed, "type": 1},  # Limit
        }
        logger.info(f"Placing order: {side} {size}x {contract_id} SL={sl_ticks}t TP={tp_ticks}t")
        r = self.client.post("/api/Order/place", json=payload, headers=self._headers())
        data = r.json()
        logger.info(f"Order response: {json.dumps(data)}")
        return data

    def close_position(self, contract_id: str) -> Dict:
        r = self.client.post("/api/Position/closeContract",
                            json={"accountId": ACCOUNT_ID, "contractId": contract_id},
                            headers=self._headers())
        return r.json()

    def get_recent_trades(self) -> List[Dict]:
        """Get recent trade fills."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=24)
        r = self.client.post("/api/Trade/search",
                            json={
                                "accountId": ACCOUNT_ID,
                                "startTimestamp": start.isoformat(),
                            },
                            headers=self._headers())
        return r.json().get("trades", [])


# ── Market Data WebSocket ───────────────────────────────────────────────
class MarketDataStream:
    def __init__(self, token: str, contracts: List[str]):
        self.token = token
        self.contracts = contracts
        self.ticks: Dict[str, MarketTick] = {c: MarketTick(contract_id=c) for c in contracts}
        self.ws: Optional[websocket.WebSocketApp] = None
        self.connected = False
        self.message_count = 0
        self._lock = threading.Lock()
        self._l2_books: Dict[str, Dict] = {c: {"bids": {}, "asks": {}} for c in contracts}

    def start(self):
        """Start WebSocket in a background thread."""
        url = f"{WS_URL}?access_token={self.token}"
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        thread.start()
        logger.info("WebSocket thread started")

    def stop(self):
        if self.ws:
            self.ws.close()

    def _on_open(self, ws):
        logger.info("WebSocket connected, sending handshake...")
        ws.send('{"protocol":"json","version":1}' + RECORD_SEP)

        # Delayed subscribe
        def _subscribe():
            time.sleep(0.5)
            for cid in self.contracts:
                meta = CONTRACT_META.get(cid, {})
                name = meta.get("name", cid[-10:])
                for target in ["SubscribeContractQuotes", "SubscribeContractTrades", "SubscribeContractDepth"]:
                    ws.send(json.dumps({
                        "type": 1,
                        "target": target,
                        "arguments": [cid],
                        "invocationId": f"{target[9:12].lower()}-{name}"
                    }) + RECORD_SEP)
                logger.info(f"Subscribed to {name} ({cid})")
            self.connected = True

        threading.Thread(target=_subscribe, daemon=True).start()

    def _on_message(self, ws, message):
        frames = message.split(RECORD_SEP)
        for frame in frames:
            frame = frame.strip()
            if not frame:
                continue
            try:
                data = json.loads(frame)
                msg_type = data.get("type")

                if msg_type == 6:  # Ping
                    ws.send(json.dumps({"type": 6}) + RECORD_SEP)
                elif msg_type == 1:  # Event
                    self._process_event(data)
                elif msg_type == 3:  # Completion
                    inv_id = data.get("invocationId", "")
                    err = data.get("error")
                    if err:
                        logger.warning(f"Subscription error [{inv_id}]: {err}")
                elif msg_type == 7:  # Close
                    logger.warning(f"Server closing connection: {data}")
                elif msg_type is None:  # Handshake
                    pass  # OK

                self.message_count += 1
            except json.JSONDecodeError:
                pass

    def _process_event(self, data: Dict):
        target = data.get("target", "")
        args = data.get("arguments", [])
        if len(args) < 2:
            return

        contract_id = args[0]
        payload = args[1]

        if contract_id not in self.ticks:
            return

        with self._lock:
            tick = self.ticks[contract_id]

            if target == "GatewayQuote":
                self._process_quote(tick, payload)
            elif target == "GatewayTrade":
                self._process_trades(tick, payload)
            elif target == "GatewayDepth":
                self._process_depth(tick, contract_id, payload)

    def _process_quote(self, tick: MarketTick, q: Dict):
        if "lastPrice" in q:
            tick.last_price = float(q["lastPrice"])
            tick.price_history.append(tick.last_price)
            if len(tick.price_history) > 500:
                tick.price_history = tick.price_history[-500:]
            tick.high = max(tick.high, tick.last_price)
            if tick.low == float('inf'):
                tick.low = tick.last_price
            tick.low = min(tick.low, tick.last_price)
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
        tick.timestamp = time.time()

        # Compute spread
        if tick.best_bid > 0 and tick.best_ask > 0:
            tick.spread = tick.best_ask - tick.best_bid
            meta = CONTRACT_META.get(tick.contract_id, {})
            ts = meta.get("tick_size", 0.25)
            tick.spread_ticks = round(tick.spread / ts) if ts > 0 else 0

    def _process_trades(self, tick: MarketTick, trades):
        """Process GatewayTrade events.
        
        TopStepX trade structure: {symbolId, price, timestamp, type, volume, contractId}
        type: 0 = aggressive buy (lifted the ask), 1 = aggressive sell (hit the bid)
        No 'side' field — 'type' is the aggressor indicator.
        """
        trade_list = trades if isinstance(trades, list) else [trades]
        for t in trade_list:
            if not isinstance(t, dict):
                continue
            # 'type' field = aggressor: 0=buy, 1=sell
            trade_type = t.get("type", -1)
            vol = int(t.get("volume", 1))
            price = float(t.get("price", 0))
            
            if trade_type == 0:  # Aggressive buyer
                tick.buy_volume += vol
                side_str = "buy"
            elif trade_type == 1:  # Aggressive seller
                tick.sell_volume += vol
                side_str = "sell"
            else:
                # Unknown type — skip classification
                side_str = "unknown"
            
            tick.recent_trades.append({
                "price": price,
                "volume": vol,
                "side": side_str,
                "time": time.time(),
            })
            if len(tick.recent_trades) > 200:
                tick.recent_trades = tick.recent_trades[-200:]

    def _process_depth(self, tick: MarketTick, contract_id: str, levels):
        book = self._l2_books[contract_id]
        if isinstance(levels, list):
            for lvl in levels:
                price = float(lvl.get("price", 0))
                volume = int(lvl.get("volume", 0))
                lvl_type = int(lvl.get("type", 0))

                if lvl_type == 6:  # Reset
                    book["bids"].clear()
                    book["asks"].clear()
                    continue

                side = "bids" if lvl_type in (0, 2) else "asks"
                if volume == 0:
                    book[side].pop(price, None)
                else:
                    book[side][price] = volume

            # Update tick with sorted L2
            tick.l2_bids = sorted(book["bids"].items(), key=lambda x: -x[0])[:10]
            tick.l2_asks = sorted(book["asks"].items(), key=lambda x: x[0])[:10]

            # Book imbalance
            total_bid_vol = sum(v for _, v in tick.l2_bids[:5])
            total_ask_vol = sum(v for _, v in tick.l2_asks[:5])
            total = total_bid_vol + total_ask_vol
            tick.book_imbalance = (total_bid_vol - total_ask_vol) / total if total > 0 else 0.0

    def get_snapshot(self, contract_id: str) -> Optional[MarketTick]:
        with self._lock:
            tick = self.ticks.get(contract_id)
            if tick and tick.last_price > 0:
                return tick
        return None

    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, code, msg):
        self.connected = False
        logger.warning(f"WebSocket closed: code={code}, msg={msg}")


# ── Market Analysis ─────────────────────────────────────────────────────
def analyze_market(tick: MarketTick, meta: Dict) -> Dict:
    """Simple but effective market analysis without needing external AI."""
    result = {
        "contract": meta.get("name", tick.contract_id),
        "contract_id": tick.contract_id,
        "price": tick.last_price,
        "spread_ticks": tick.spread_ticks,
        "book_imbalance": tick.book_imbalance,
        "signal": "NO_TRADE",
        "conviction": 0,
        "direction": "neutral",
        "thesis": "",
        "score": 0.0,
    }

    # Need enough data
    if tick.tick_count < 10 or tick.last_price <= 0:
        result["thesis"] = "Insufficient data"
        return result

    # Spread check
    if tick.spread_ticks > MAX_SPREAD_TICKS:
        result["thesis"] = f"Spread too wide ({tick.spread_ticks} ticks)"
        return result

    # ── Compute signals ──
    score = 0.0
    signals = []

    # 1. Order flow imbalance (buy vs sell volume)
    total_flow = tick.buy_volume + tick.sell_volume
    if total_flow > 0:
        flow_ratio = (tick.buy_volume - tick.sell_volume) / total_flow
    else:
        flow_ratio = 0.0

    if abs(flow_ratio) > 0.15:
        score += 25 * abs(flow_ratio) / 0.5  # Scale to max 25
        signals.append(f"Flow {'buy' if flow_ratio > 0 else 'sell'} bias {flow_ratio:+.2f}")

    # 2. L2 book imbalance
    if abs(tick.book_imbalance) > 0.2:
        score += 20 * abs(tick.book_imbalance)
        signals.append(f"Book imbalance {tick.book_imbalance:+.2f}")

    # 3. Price momentum (simple: compare last price to recent average)
    if len(tick.price_history) >= 20:
        recent_avg = sum(tick.price_history[-20:]) / 20
        longer_avg = sum(tick.price_history[-50:]) / min(50, len(tick.price_history))
        momentum = (tick.last_price - recent_avg) / recent_avg if recent_avg > 0 else 0

        if abs(momentum) > 0.0003:  # Small but real move
            score += 15
            signals.append(f"Momentum {momentum:+.4%}")

        # Trend: short MA above long MA
        if len(tick.price_history) >= 50:
            trend = (recent_avg - longer_avg) / longer_avg if longer_avg > 0 else 0
            if abs(trend) > 0.0002:
                score += 15
                signals.append(f"Trend {trend:+.4%}")

    # 4. Recent trade flow acceleration
    if len(tick.recent_trades) >= 10:
        recent_5 = tick.recent_trades[-5:]
        recent_10 = tick.recent_trades[-10:-5]
        recent_buy = sum(1 for t in recent_5 if t["side"] == "buy")
        older_buy = sum(1 for t in recent_10 if t["side"] == "buy")
        if recent_buy >= 4 and older_buy <= 2:
            score += 10
            signals.append("Buy acceleration")
        elif recent_buy <= 1 and older_buy >= 3:
            score += 10
            signals.append("Sell acceleration")

    # 5. Volume activity
    if tick.tick_count > 50:
        score += 5  # Active market bonus

    # Determine direction
    direction_score = 0.0
    if flow_ratio > 0.1:
        direction_score += flow_ratio * 2
    if tick.book_imbalance > 0.15:
        direction_score += tick.book_imbalance
    if len(tick.price_history) >= 20:
        recent_avg = sum(tick.price_history[-20:]) / 20
        if tick.last_price > recent_avg:
            direction_score += 0.3
        elif tick.last_price < recent_avg:
            direction_score -= 0.3

    if direction_score > 0.25:
        direction = "long"
    elif direction_score < -0.25:
        direction = "short"
    else:
        direction = "neutral"

    # Conviction = score capped at 100
    conviction = min(score, 100)

    result.update({
        "signal": "LONG" if direction == "long" and conviction >= 45 else
                  "SHORT" if direction == "short" and conviction >= 45 else "NO_TRADE",
        "conviction": conviction,
        "direction": direction,
        "thesis": "; ".join(signals) if signals else "No clear setup",
        "score": score,
        "flow_ratio": flow_ratio,
        "momentum": (tick.last_price - sum(tick.price_history[-20:]) / 20) /
                    (sum(tick.price_history[-20:]) / 20) if len(tick.price_history) >= 20 else 0,
        "l2_bids_top5": tick.l2_bids[:5],
        "l2_asks_top5": tick.l2_asks[:5],
        "buy_vol": tick.buy_volume,
        "sell_vol": tick.sell_volume,
        "ticks_received": tick.tick_count,
        "change_pct": tick.change_pct,
    })
    return result


# ── Main Session ────────────────────────────────────────────────────────
class LiveSession:
    def __init__(self):
        self.api = TopStepXClient()
        self.stream: Optional[MarketDataStream] = None
        self.trades: List[TradeRecord] = []
        self.session_pnl = 0.0
        self.running = True
        self.scan_results: List[Dict] = []
        self.start_time = time.time()
        self.last_trade_time = 0.0
        self.trade_cooldown = 30  # seconds between trade attempts

    def run(self):
        """Main session loop."""
        logger.info("=" * 60)
        logger.info("SOVRAN V2 — LIVE TRADING SESSION")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # Phase 1: Authenticate
        if not self.api.authenticate():
            logger.error("Authentication failed!")
            return self._results()

        # Phase 2: Get account state
        acct_info = self.api.get_account_info()
        accounts = acct_info.get("accounts", [])
        if accounts:
            acct = accounts[0]
            logger.info(f"Account: {acct['name']}")
            logger.info(f"Balance: ${acct['balance']:,.2f}")
            logger.info(f"Can Trade: {acct['canTrade']}")

        # Check existing positions
        positions = self.api.get_positions()
        logger.info(f"Open positions: {len(positions)}")
        for p in positions:
            logger.info(f"  {p['contractId']} | {p.get('type')} | size={p.get('size')} | avg={p.get('averagePrice')}")

        # Phase 3: Start market data
        logger.info(f"\nStarting market data for {len(SCAN_CONTRACTS)} contracts...")
        self.stream = MarketDataStream(self.api.token, SCAN_CONTRACTS)
        self.stream.start()

        # Wait for data to flow
        logger.info("Waiting for market data...")
        wait_start = time.time()
        while time.time() - wait_start < 30:
            if self.stream.message_count > 50:
                break
            time.sleep(0.5)

        if self.stream.message_count < 10:
            logger.warning("Very little market data received — market may be closed")

        logger.info(f"Received {self.stream.message_count} messages in {time.time() - wait_start:.1f}s")

        # Phase 4: Scan & Trade loop
        logger.info("\n--- SCANNING MARKETS ---")
        scan_cycles = 0
        max_scan_cycles = 40  # Run 40 scan cycles

        while self.running and scan_cycles < max_scan_cycles:
            scan_cycles += 1
            time.sleep(5)  # 5 seconds between scans

            # Refresh positions
            try:
                positions = self.api.get_positions()
            except:
                positions = []

            # Scan all markets
            analyses = []
            for cid in SCAN_CONTRACTS:
                tick = self.stream.get_snapshot(cid)
                if tick:
                    meta = CONTRACT_META.get(cid, {})
                    analysis = analyze_market(tick, meta)
                    analyses.append(analysis)

            # Sort by score
            analyses.sort(key=lambda x: -x["score"])
            self.scan_results = analyses

            # Log scan results
            logger.info(f"\n[Scan {scan_cycles}/{max_scan_cycles}] Messages: {self.stream.message_count}")
            for a in analyses:
                sig = a["signal"]
                emoji = "🟢" if sig == "LONG" else ("🔴" if sig == "SHORT" else "⚪")
                logger.info(
                    f"  {emoji} {a['contract']:4s} | ${a['price']:>10,.2f} | "
                    f"spread={a['spread_ticks']:.0f}t | book={a['book_imbalance']:+.2f} | "
                    f"flow B:{a.get('buy_vol',0)} S:{a.get('sell_vol',0)} | "
                    f"score={a['score']:.0f} | {sig}"
                )
                if a.get("thesis") and sig != "NO_TRADE":
                    logger.info(f"       Thesis: {a['thesis']}")

            # Check if we should trade
            if len(positions) > 0:
                logger.info("  [WAIT] Position already open — monitoring")
                continue

            if len(self.trades) >= MAX_TRADES_SESSION:
                logger.info("  🛑 Max trades reached for session")
                continue

            if self.session_pnl < -MAX_DAILY_LOSS:
                logger.info(f"  🛑 Daily loss limit hit (${self.session_pnl:,.2f})")
                continue

            # Find best setup (with cooldown)
            best = analyses[0] if analyses else None
            if best and best["signal"] in ("LONG", "SHORT") and best["conviction"] >= 45:
                if time.time() - self.last_trade_time > self.trade_cooldown:
                    self._execute_trade(best)
                else:
                    remaining = self.trade_cooldown - (time.time() - self.last_trade_time)
                    logger.info(f"  [WAIT] Trade cooldown: {remaining:.0f}s remaining")

        # Phase 5: Cleanup
        logger.info("\n--- SESSION COMPLETE ---")
        if self.stream:
            self.stream.stop()

        return self._results()

    def _execute_trade(self, analysis: Dict):
        """Execute a trade based on analysis."""
        cid = analysis["contract_id"]
        meta = CONTRACT_META.get(cid, {})
        side = "BUY" if analysis["signal"] == "LONG" else "SELL"
        tick_size = meta.get("tick_size", 0.25)
        tick_value = meta.get("tick_value", 0.50)

        # Conservative stops: 20 ticks SL, 40 ticks TP (2:1 R:R)
        sl_ticks = 20
        tp_ticks = 40

        # Risk check
        risk_dollars = sl_ticks * tick_value * MAX_POSITION_SIZE
        if risk_dollars > MAX_DAILY_LOSS - abs(self.session_pnl):
            logger.warning(f"Trade risk ${risk_dollars:.2f} exceeds remaining daily budget")
            return

        logger.info(f"\n[TRADE] EXECUTING TRADE: {side} {MAX_POSITION_SIZE}x {meta.get('name', cid)}")
        logger.info(f"   Price: ${analysis['price']:,.2f} | SL: {sl_ticks}t (${risk_dollars:.2f}) | TP: {tp_ticks}t | Conv: {analysis['conviction']:.0f}")
        logger.info(f"   Thesis: {analysis.get('thesis', 'N/A')}")

        trade = TradeRecord(
            contract_id=cid,
            side=side,
            entry_price=analysis["price"],
            size=MAX_POSITION_SIZE,
            sl_ticks=sl_ticks,
            tp_ticks=tp_ticks,
            entry_time=time.time(),
            thesis=analysis.get("thesis", ""),
        )

        try:
            result = self.api.place_order(cid, side, MAX_POSITION_SIZE, sl_ticks, tp_ticks)
            if result.get("success"):
                trade.order_id = result.get("orderId", 0)
                trade.status = "open"
                logger.info(f"   [OK] Order placed! ID: {trade.order_id}")
            else:
                error_code = result.get("errorCode", -1)
                error_msg = result.get("errorMessage", "Unknown")
                trade.status = "error"
                trade.thesis += f" | ERROR: code={error_code} {error_msg}"
                logger.error(f"   [FAIL] Order failed: code={error_code} msg={error_msg}")
        except Exception as e:
            trade.status = "error"
            trade.thesis += f" | EXCEPTION: {e}"
            logger.error(f"   [FAIL] Order exception: {e}")

        self.trades.append(trade)
        self.last_trade_time = time.time()

    def _results(self) -> Dict:
        """Compile session results."""
        elapsed = time.time() - self.start_time
        return {
            "duration_seconds": elapsed,
            "messages_received": self.stream.message_count if self.stream else 0,
            "scan_results": self.scan_results,
            "trades": [
                {
                    "contract": t.contract_id,
                    "side": t.side,
                    "entry_price": t.entry_price,
                    "size": t.size,
                    "sl_ticks": t.sl_ticks,
                    "tp_ticks": t.tp_ticks,
                    "order_id": t.order_id,
                    "status": t.status,
                    "thesis": t.thesis,
                }
                for t in self.trades
            ],
            "session_pnl": self.session_pnl,
        }


# ── Entry Point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    session = LiveSession()
    results = session.run()

    # Save results
    with open("live_session_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"\nResults saved to live_session_results.json")
    logger.info(f"Total messages: {results['messages_received']}")
    logger.info(f"Trades: {len(results['trades'])}")
    logger.info(f"Session PnL: ${results['session_pnl']:,.2f}")
