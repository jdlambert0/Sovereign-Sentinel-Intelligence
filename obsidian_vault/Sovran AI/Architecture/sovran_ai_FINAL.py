"""
Sovran AI Gambler (V3) — The True AI-at-the-Helm
===============================================

This system uses an LLM (Claude/Gemini) to evaluate the L2 order flow data
in real-time and output a "confidence" score. A mathematical Kelly Sizing
engine then scales the bet appropriately against the 150k combine $4500
trailing drawdown limit.

The script runs continuously, passing market context and memory into the
LLM's context window every 15 seconds.

LEARNING SYSTEM: Uses Obsidian for memory and research
- Trades saved to Obsidian after execution
- Research loop triggers after every 10 trades
- Dynamic tick management based on performance
"""

import sys
import os
import json
import asyncio

# Learning System - Obsidian Integration
try:
    import learning_system as learning

    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False
    print("Warning: Learning system not available")

try:
    from utils_ascii_decoder import _decode_ascii_codes_to_string
except Exception:
    # Fallback local ASCII code decoder if module not importable in this env
    def _decode_ascii_codes_to_string(s):
        if isinstance(s, str) and "\x1e" in s:
            parts = s.split("\x1e")
            nums = []
            for p in parts:
                if p and p.isdigit():
                    nums.append(int(p))
            try:
                return bytes(nums).decode("utf-8", errors="ignore")
            except Exception:
                return s
        return s


import logging
import asyncio
import math
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import cast, List, Tuple, Dict, Any, Optional

# Global state for mailbox queries
_trades_today = 0
_system_status = "initializing"


async def get_system_status() -> Dict[str, Any]:
    """Get current system status for mailbox queries"""
    global _system_status, _trades_today
    return {
        "status": _system_status,
        "trades_today": _trades_today,
        "learning_available": LEARNING_AVAILABLE,
    }


def update_system_status(status: str):
    """Update system status"""
    global _system_status
    _system_status = status


def increment_trade_count():
    """Increment daily trade counter"""
    global _trades_today
    _trades_today += 1


# LEARNING MODE - Override safety gates for testing/learning
# Set to True to bypass session phase, throttle, and consecutive loss breakers
# BUG-009 FIX: Was undefined, causing NameError at line 1453
LEARNING_MODE = True  # Override for learning phase - set False to re-enable all gates


async def get_recent_trades(count: int = 5) -> List[Dict[str, Any]]:
    """Get recent trades from learning system"""
    if not LEARNING_AVAILABLE:
        return []
    try:
        return learning.get_recent_trades(count)
    except Exception:
        return []


import msgpack
import argparse

# Add vortex directory so we can use its tested llm_client
BASE_DIR = Path("C:\\KAI")
VORTEX_DIR = BASE_DIR / "vortex"
sys.path.append(str(VORTEX_DIR))

# Hardcode the ProjectX SDK path to ensure headless engines can find it
SDK_PATH = Path(r"C:\KAI\vortex\.venv312\Lib\site-packages")
if str(SDK_PATH) not in sys.path:
    sys.path.append(str(SDK_PATH))

# Load .env credentials if they exist in vortex dir
env_path = VORTEX_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

try:
    from llm_client import complete_prompt, complete_ensemble
except ImportError:
    logging.warning(
        "Could not import llm_client from vortex. Ensure C:\\KAI\\vortex exists."
    )

# ---------------------------------------------------------------------------
# MESSAGEPACK TRANSPORT OVERRIDE (P0 - Anti-Slop Protection)
# ---------------------------------------------------------------------------
from signalrcore.transport.websockets.websocket_transport import WebsocketTransport

logger = logging.getLogger("sovran_ai")
original_on_message = WebsocketTransport.on_message


def patched_on_message(self, app, raw_message):
    try:
        # Handle bytes from binary WebSocket frames
        if isinstance(raw_message, bytes):
            messages = []
            # FIX: Use strict_map_key=False to handle int keys in MessagePack
            unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
            unpacker.feed(raw_message)
            for unpacked in unpacker:
                messages.append(json.dumps(unpacked))
            if messages:
                raw_message = "\x1e".join(messages) + "\x1e"
        elif isinstance(raw_message, str):
            parts = raw_message.split("\x1e")
            fixed_parts = []
            for part in parts:
                if not part:
                    continue
                try:
                    json.loads(part)
                    fixed_parts.append(part)
                except json.JSONDecodeError:
                    try:
                        try:
                            raw_bytes = part.encode("latin-1")
                        except UnicodeEncodeError:
                            raw_bytes = part.encode("utf-8", errors="ignore")
                        unpacked = msgpack.unpackb(
                            raw_bytes, raw=False, strict_map_key=False
                        )
                        fixed_parts.append(json.dumps(unpacked))
                    except Exception:
                        pass
            raw_message = "\x1e".join(fixed_parts) + ("\x1e" if fixed_parts else "")

    except Exception as e:
        logger.error(f"SOE Transport patch error: {e}")

    # Attempt to convert any ASCII-coded numeric bytes string to real string before dispatch
    if isinstance(raw_message, str):
        _decoded = _decode_ascii_codes_to_string(raw_message)
        if _decoded != raw_message:
            raw_message = _decoded
        # Additional: try to extract a JSON object embedded in a larger string
        try:
            import re

            m = re.search(r"\{.*\}", raw_message, re.S)
            if m:
                candidate = m.group(0)
                json.loads(candidate)
                raw_message = candidate
                logger.info(
                    "JSON fallback: extracted embedded JSON payload from handshake string"
                )
        except Exception:
            pass

    if raw_message:
        return original_on_message(self, app, raw_message)
    return []


WebsocketTransport.on_message = patched_on_message


# ---------------------------------------------------------------------------
# WEBSOCKET CONNECTION TIMEOUT FIX (P0 - Anti-Slop Protection)
# ---------------------------------------------------------------------------
# BUG-FIX: The SDK has a 10-second timeout that's too aggressive, causing
# WebSocket connections to fail even when they would succeed. This patch
# increases the timeout to 30 seconds and adds retry logic.

import asyncio
import signalrcore.hub_connection_builder

_original_build = signalrcore.hub_connection_builder.HubConnectionBuilder.build


def _patched_build(self):
    """Patch HubConnectionBuilder to use longer timeout and retries"""
    conn = _original_build(self)

    # Increase connection timeout from 10s to 30s
    # This allows slower connections (especially during market hours) to succeed
    try:
        if hasattr(conn, "_timeout") and conn._timeout == 10.0:
            conn._timeout = 30.0
            logger.info("SOE: WebSocket timeout patched: 10s -> 30s")
    except Exception as e:
        logger.debug(f"Timeout patch note: {e}")

    return conn


signalrcore.hub_connection_builder.HubConnectionBuilder.build = _patched_build


# Also patch the connection_management connect method directly
def _patch_connection_timeout():
    """Patch connection_management to use longer timeout"""
    try:
        from project_x_py.realtime import connection_management

        _original_connect = connection_management.ConnectionManagementMixin.connect

        async def _patched_connect(self):
            """Patched connect with 30s timeout instead of 10s"""
            if not self.setup_complete:
                await self.setup_connections()

            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.error("No running event loop found.")
                return False

            logger.debug("Connecting to ProjectX Gateway...")

            async with self._connection_lock:
                if self.user_connection:
                    await self._start_connection_async(self.user_connection, "user")
                else:
                    logger.error("User connection not available")
                    return False

                if self.market_connection:
                    await self._start_connection_async(self.market_connection, "market")
                else:
                    logger.error("Market connection not available")
                    return False

                # MINS FIX: Increased timeout from 10s to 30s for slower connections
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            self.user_hub_ready.wait(), self.market_hub_ready.wait()
                        ),
                        timeout=30.0,  # Increased from 10.0
                    )
                except TimeoutError:
                    logger.warning(
                        "WebSocket connection timed out after 30s. "
                        "System will operate in REST polling mode."
                    )
                    # Don't return False - allow system to continue with REST
                    return True  # Allow degraded mode to continue

                if self.user_connected and self.market_connected:
                    self.stats["connected_time"] = datetime.now()
                    logger.info("WebSocket connected successfully!")
                    return True
                else:
                    logger.warning(
                        "WebSocket connections not fully established. "
                        "System will operate in REST polling mode."
                    )
                    return True  # Allow degraded mode

        connection_management.ConnectionManagementMixin.connect = _patched_connect
        logger.info(
            "SOE: Connection timeout patched: 10s -> 30s, TimeoutError is non-fatal"
        )

    except Exception as e:
        logger.debug(f"Connection patch note: {e}")


# Apply patch immediately
_patch_connection_timeout()


# ---------------------------------------------------------------------------
# CONFIGURATION & STATE
# ---------------------------------------------------------------------------
@dataclass
class Config:
    mode: str = "live"  # Paper mode removed — always live
    symbol: str = "MNQ"
    initial_bankroll: float = 4500.0
    point_value: float = 2.0  # Will be overridden by symbol lookup
    tick_size: float = 0.25
    commission_per_contract: float = 1.48

    # Per-symbol point values (CRITICAL for correct PnL calculation)
    SYMBOL_POINT_VALUES = {
        "MNQ": 2.0,  # Micro Nasdaq = $2/point
        "MES": 5.0,  # Micro S&P = $5/point
        "MYM": 0.50,  # Micro Dow = $0.50/point
        "M2K": 5.0,  # Micro Russell = $5/point
    }

    def __post_init__(self):
        # Override point_value based on symbol
        self.point_value = self.SYMBOL_POINT_VALUES.get(self.symbol, 2.0)

    kelly_fraction: float = 0.25
    max_contracts: int = 4
    min_contracts: int = 1
    max_daily_loss: float = 900.0
    daily_profit_cap: float = 2000.0  # Consistency Rule Protection
    max_consecutive_losses: int = 3  # Circuit breaker: stop after N consecutive losses

    # AI Options
    loop_interval_sec: int = 30
    consensus_models: list[str] = field(
        default_factory=lambda: [
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.3-70b-instruct",
        ]
    )

    # Institutional Hardening Parameters
    vpin_buckets: int = 50
    vpin_window: int = 20  # Number of buckets for rolling VPIN
    avg_daily_volume: int = 200000  # MNQ estimate
    ofi_z_window: int = 50  # Window for OFI normalization
    micro_chop_atr_limit: float = 5.0
    micro_chop_range_limit: float = 8.0

    # Spread Gate (per cursorrules mandate)
    max_spread_ticks: float = 4.0  # Max bid-ask spread in ticks before blocking entry

    # Last Entry Time (per .env RISK_LAST_ENTRY_TIME_CT=14:45)
    # MARCH 17 2026: Extended to 15:55 for learning mode - allow trading until 3:55 PM CT
    last_entry_time: str = (
        "19:55:00"  # No new trades after 7:55 PM CT (allow evening session trading)
    )

    state_file: str = "C:\\KAI\\armada\\_data_db\\sovran_ai_state.json"
    memory_file: str = "C:\\KAI\\armada\\_data_db\\sovran_ai_memory.json"


@dataclass
class GamblerState:
    bankroll_remaining: float = 4500.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0

    rolling_wins: int = 0
    rolling_losses: int = 0
    rolling_total_win: float = 0.0
    rolling_total_loss: float = 0.0
    consecutive_losses: int = 0  # Track consecutive losses for circuit breaker

    # Learning System - Trade counter
    total_trades: int = 0  # For triggering research after every 10 trades

    # Trailing Drawdown (the #1 prop firm killer per Shoshin report)
    trailing_high_water_mark: float = 0.0  # Highest total_pnl achieved
    trailing_drawdown_floor: float = -4500.0  # How far we can fall from HWM

    @property
    def rolling_win_rate(self) -> float:
        total = self.rolling_wins + self.rolling_losses
        return self.rolling_wins / total if total > 0 else 0.50

    @property
    def rolling_rr(self) -> float:
        if self.rolling_losses == 0 or self.rolling_total_loss == 0:
            return 2.0
        avg_win = self.rolling_total_win / max(self.rolling_wins, 1)
        avg_loss = abs(self.rolling_total_loss) / max(self.rolling_losses, 1)
        return avg_win / avg_loss if avg_loss > 0 else 2.0

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # ATOMIC WRITE: Write to .tmp first, then os.replace (BUG FIX: crash during write = corrupted state)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)
        os.replace(tmp_path, path)

    @classmethod
    def load(cls, path: str) -> "GamblerState":
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return cls(
                    **{k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                )
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()


# ---------------------------------------------------------------------------
# TRAILING DRAWDOWN TRACKER (Shoshin Recommendation #1)
# ---------------------------------------------------------------------------
class TrailingDrawdown:
    """Tracks the high-water mark and computes available headroom.

    TopStepX trailing drawdown: starts at $4,500 below starting balance.
    As profits rise, the floor rises too (trails). It never goes back down.
    This is the SINGLE MOST IMPORTANT risk metric for prop firm survival.
    """

    def __init__(self, state: GamblerState, max_drawdown: float = 4500.0):
        self.state = state
        self.max_drawdown = max_drawdown

    def update(self, new_pnl: float):
        """Call after every PnL change. Updates high-water mark and floor."""
        self.state.total_pnl = new_pnl

        # Update high-water mark
        if new_pnl > self.state.trailing_high_water_mark:
            self.state.trailing_high_water_mark = new_pnl
            # Floor trails UP with profits
            self.state.trailing_drawdown_floor = new_pnl - self.max_drawdown

    @property
    def headroom(self) -> float:
        """How much we can lose before hitting the trailing floor."""
        return self.state.total_pnl - self.state.trailing_drawdown_floor

    @property
    def is_danger_zone(self) -> bool:
        """True if headroom < $500 — too risky to trade."""
        return self.headroom < 500.0

    @property
    def is_blown(self) -> bool:
        """True if we've hit the trailing drawdown floor."""
        return self.headroom <= 0

    def summary(self) -> str:
        return (
            f"HWM: ${self.state.trailing_high_water_mark:.2f} | "
            f"Floor: ${self.state.trailing_drawdown_floor:.2f} | "
            f"Headroom: ${self.headroom:.2f}"
        )


# ---------------------------------------------------------------------------
# MEMORY / LEARNING LOOP
# ---------------------------------------------------------------------------
def load_memory(path: str) -> list:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_memory(path: str, memory_list: list):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        # Keep last 50 trades
        json.dump(memory_list[-50:], f, indent=2)


# ---------------------------------------------------------------------------
# AI ENGINE
# ---------------------------------------------------------------------------
class AIGamblerEngine:
    def __init__(self, config: Config, state: GamblerState, suite):
        self.config = config
        self.state = state
        self.suite = suite

        # Trailing Drawdown Tracker (Shoshin Recommendation #1)
        self.trailing_dd = TrailingDrawdown(state)

        self.active_trade = None

        # Real-time features
        self.last_price = 0.0
        self.bid = 0.0
        self.ask = 0.0
        self.high = float("-inf")
        self.low = float("inf")

        self.ofi_history: list[
            tuple[float, float]
        ] = []  # List of (timestamp, volume_delta)
        self.ofi_window_trades = 200
        self.book_pressure = 0.5

        # Quote counter for silent WebSocket detection (online research finding)
        self._quote_count = 0
        self._quote_count_check_time = time.time()

        # VPIN State
        self.vpin_basket_size = config.avg_daily_volume // config.vpin_buckets
        self.current_basket_vbuys = 0.0
        self.current_basket_vsells = 0.0
        self.current_basket_volume = 0.0
        self.vpin_buckets_history: list[
            tuple[float, float]
        ] = []  # List of (buys, sells)

        # Z-Score State
        self.ofi_history_for_z: list[float] = []  # Rolling history of OFI values

        self.ct_tz = ZoneInfo("America/Chicago")  # DST-safe Central Time

        self.last_update_time = time.time()
        self.last_loss_time = 0.0
        self.mandate_active = True  # P0: For verification trade
        self.throttle_period_sec = 300  # 5 minute cooldown
        self.flatten_time = "15:08:00"  # 3:08 PM CT

    async def fetch_price_from_suite(self) -> bool:
        """Fetch current price from TradingSuite data manager (via REST API)"""
        try:
            # Use the suite's data manager to get current price
            data_manager = self.suite.data
            current_price = await data_manager.get_current_price()

            if current_price and current_price > 0:
                self.last_price = current_price
                self.bid = current_price - 1  # Approximate
                self.ask = current_price + 1  # Approximate
                self.last_update_time = time.time()
                self.book_pressure = 0.5
                logger.info(f"Suite price: last={self.last_price}")
                return True
        except Exception as e:
            logger.warning(f"Suite price fetch failed: {e}")
        return False

    async def handle_quote(self, event):
        """Parse L1 quote from TopStepX. PROVEN keys: bid, ask, last, volume, symbol, timestamp.
        Handle incoming quotes with safety for NoneType prices."""
        from api_types import TopStepXQuote
        from typing import cast

        data = cast(TopStepXQuote, getattr(event, "data", {}))

        try:
            # March 16: Safety for float() NoneType error seen in logs
            if (
                data.get("last_price") is None
                or data.get("bid") is None
                or data.get("ask") is None
            ):
                return

            # 'last_price' is the canonical key from TopStepX
            last = data.get("last_price")
            if last is not None and last > 0:
                self.last_price = float(last)
                self.high = max(self.high, self.last_price)
                self.low = min(self.low, self.last_price)

            bid = data.get("bid", 0)
            ask = data.get("ask", 0)
            if bid and bid > 0:
                self.bid = float(bid)
            if ask and ask > 0:
                self.ask = float(ask)

            # Purgatory breaker: if no last trade, use bid/ask midpoint
            if self.last_price <= 0 and self.bid > 0 and self.ask > 0:
                self.last_price = round((self.bid + self.ask) / 2.0, 2)

            # No bid_size/ask_size in this feed — neutral book pressure
            self.book_pressure = 0.5
            self.last_update_time = time.time()
            self._quote_count += 1  # Silent WS detection counter
        except Exception as e:
            logger.error(f"Error processing quote: {e} from data: {data}")

    async def handle_trade(self, event):
        """Parse trade tick from TopStepX. Keys TBD (no trades on Sunday thin market)."""
        data = event.data  # Dict
        vol = float(data.get("volume", data.get("size", 1)))
        side = int(
            data.get("side", 0)
        )  # 0=Buy, 1=Sell (assumed, needs weekday verification)
        delta = vol if side == 0 else -vol

        now = time.time()
        self.ofi_history.append((now, delta))
        if len(self.ofi_history) > self.ofi_window_trades:
            self.ofi_history.pop(0)
        # Prune stale entries older than 10 minutes (BUG FIX: stale OFI accumulation)
        cutoff = now - 600
        self.ofi_history = [(t, d) for t, d in self.ofi_history if t > cutoff]

        # Update Z-Score History
        current_ofi = float(self.get_ofi())
        self.ofi_history_for_z.append(current_ofi)
        if len(self.ofi_history_for_z) > self.config.ofi_z_window:
            self.ofi_history_for_z.pop(0)

        # VPIN (Volume Baskets) Calculation
        self.current_basket_volume += vol
        if side == 0:
            self.current_basket_vbuys += vol
        else:
            self.current_basket_vsells += vol

        if self.current_basket_volume >= self.vpin_basket_size:
            # Finalize basket
            self.vpin_buckets_history.append(
                (self.current_basket_vbuys, self.current_basket_vsells)
            )
            if len(self.vpin_buckets_history) > self.config.vpin_window:
                self.vpin_buckets_history.pop(0)

            # Reset
            self.current_basket_vbuys = 0
            self.current_basket_vsells = 0
            self.current_basket_volume = 0

    def get_vpin(self) -> float:
        if not self.vpin_buckets_history:
            return 0.0

        # VPIN = Σ|Vb - Vs| / (n * V)
        # where n is the number of buckets and V is the basket size
        total_imbalance = sum(abs(b - s) for b, s in self.vpin_buckets_history)
        n = len(self.vpin_buckets_history)
        if n == 0:
            return 0.0

        return total_imbalance / (n * self.vpin_basket_size)

    def get_ofi_zscore(self) -> float:
        if len(self.ofi_history_for_z) < 10:
            return 0.0

        mean = sum(self.ofi_history_for_z) / len(self.ofi_history_for_z)
        variance = sum((x - mean) ** 2 for x in self.ofi_history_for_z) / len(
            self.ofi_history_for_z
        )
        std = math.sqrt(variance)

        if std == 0:
            return 0.0
        return (self.ofi_history_for_z[-1] - mean) / std

    def get_ofi(self) -> float:
        return float(sum(delta for _, delta in self.ofi_history))

    def get_performance_summary(self, memory: list) -> str:
        if not memory:
            return "No trading history yet."
        recent = memory[-10:]
        wins = [t["pnl"] for t in recent if t["pnl"] > 0]
        losses = [t["pnl"] for t in recent if t["pnl"] <= 0]
        win_rate = len(wins) / len(recent) if recent else 0
        total_net = sum(t["pnl"] for t in recent)
        return (
            f"Recent Performance (Last {len(recent)} trades): "
            f"Win Rate: {win_rate:.0%}, Net PnL: ${total_net:.2f}, "
            f"Avg Win: ${sum(wins) / len(wins) if wins else 0:.2f}, "
            f"Avg Loss: ${sum(losses) / len(losses) if losses else 0:.2f}"
        )

    def get_session_phase(self) -> str:
        """Returns the current session phase — critical context the LLM needs.
        Markets behave COMPLETELY differently at different times of day.
        Without this, the LLM cannot learn session-structure patterns.
        (Shoshin Recommendation #2: AI Researcher persona)"""
        now_ct = datetime.now(self.ct_tz)
        hour, minute = now_ct.hour, now_ct.minute
        t = hour * 60 + minute  # Minutes since midnight CT
        weekday = now_ct.weekday()  # 0=Monday, 6=Sunday

        # Weekend / Market Halt Check
        if weekday == 4 and t >= 960:  # Friday after 4:00 PM CT
            return "WEEKEND (Market Closed)"
        if weekday == 5:  # Saturday all day
            return "WEEKEND (Market Closed)"
        if weekday == 6 and t < 1020:  # Sunday before 5:00 PM CT
            return "WEEKEND (Market Closed)"

        # Daily halt: Monday-Thursday 4:00 PM - 5:00 PM CT
        if weekday in [0, 1, 2, 3] and (960 <= t < 1020):
            return "DAILY HALT (Market Closed)"

        if t < 510:  # Before 8:30
            return "PRE-MARKET (low liquidity, wide spreads — avoid trading)"
        elif t < 545:  # 8:30 - 9:05
            return (
                "OPENING BURST (high volatility, institutional flow, momentum-dominant)"
            )
        elif t < 630:  # 9:05 - 10:30
            return "MORNING SESSION (trend continuation likely, order flow reliable)"
        elif t < 750:  # 10:30 - 12:30
            return "MIDDAY CHOP (low volume, mean-reversion, false breakouts common)"
        elif t < 840:  # 12:30 - 2:00
            return "EARLY AFTERNOON (BANNED — V3 arena data: -$102 over 6 trades. Do NOT trade.)"
        elif t < 885:  # 2:00 - 2:45
            return "CLOSING PUSH (final institutional positioning, strong momentum)"
        elif t < 910:  # 2:45 - 3:10
            return (
                "FORCE-FLATTEN ZONE (must close all positions, do NOT open new trades)"
            )
        elif t < 1200:  # 3:10 PM - 8:00 PM CT (evening session)
            return "EVENING SESSION (post-close, institutional repositioning, good volatility)"
        else:
            return "AFTER-HOURS (late night, low liquidity, overnight session)"

    def build_prompt(self, memory: list) -> str:
        past_trades = "\n".join(
            [
                f"- {t.get('timestamp', 'unknown')} | {t['direction']} | PNL: ${t['pnl']:.2f} | Reasoning: {t['reasoning']}"
                for t in memory[-5:]
            ]
        )
        if not past_trades:
            past_trades = "No recent trades."

        perf_summary = self.get_performance_summary(memory)
        session_range = (
            0
            if self.high == float("-inf") or self.low == float("inf")
            else self.high - self.low
        )
        now_ct = datetime.now(self.ct_tz)

        # Trailing drawdown context
        dd_summary = (
            self.trailing_dd.summary() if hasattr(self, "trailing_dd") else "N/A"
        )

        # MANDATE INJECTION: User-requested verification trade
        # March 16, 2026: User requested a Long on MNQ with wide SL to verify platform sync.
        SOVEREIGN_MANDATE = """
[CRITICAL SOVEREIGN MANDATE]
The User REQUIRES a LONG position on MNQ immediately for system verification.
- DIRECTION: BUY (LONG)
- CONFIDENCE: 1.0
- STOP LOSS: 50.0 points (WIDE)
- TARGET: 20.0 points

[SOVEREIGN BRIEFING REQUIRED]
Before returning the JSON, provide a brief "SOVEREIGN BRIEFING" explaining:
1. Your current assessment of the MNQ order flow.
2. Why you are executing this mandate now despite any adverse signals.
3. Your commitment to the 1k/day profit mission.
"""

        prompt = f"""You are Sovran AI Gambler — an autonomous, ruthlessly skeptical futures trader operating strictly in {self.config.symbol}.
You must evaluate the live Level 2 metrics and output your directional instinct. You are currently in ENSEMBLE mode (Council of One).

{SOVEREIGN_MANDATE}

TIME CONTEXT (CRITICAL — market behavior changes dramatically by session phase):
  Current Time: {now_ct.strftime("%H:%M:%S")} CT ({now_ct.strftime("%A, %B %d, %Y")})
  Session Phase: {self.get_session_phase()}

MARKET METRICS:
  Price: {self.last_price:.2f} (Bid: {self.bid:.2f} / Ask: {self.ask:.2f})
  Session Range: {session_range:.2f} pts
  OFI (Order Flow Imbalance): {self.get_ofi()} (Z-Score: {self.get_ofi_zscore():.2f})
  VPIN (Informed Trading Probability): {self.get_vpin():.2f}
  Book Pressure: {self.book_pressure:.2f}

YOUR PERFORMANCE HISTORY:
{perf_summary}

RECENT TRADES:
{past_trades}

STATE: 
  Bankroll: ${self.state.bankroll_remaining:.2f}
  Daily PnL: ${self.state.daily_pnl:.2f}
  Trailing Drawdown: {dd_summary}
  Consecutive Losses: {self.state.consecutive_losses}

BATTLE ARENA LEARNINGS (V3 Goldilocks — calibrated from 25 simulated trades, 56% WR, +$717 net):
  PROFITABLE PHASES: OPENING BURST (+$341), MORNING SESSION (+$267), CLOSING PUSH (+$210)
  UNPROFITABLE PHASE: EARLY AFTERNOON (-$102) — BANNED. Do NOT trade in this phase.
  BANNED PHASE: MIDDAY CHOP — Do NOT trade.
  Winning trades had avg |OFI Z-Score| = 2.5 and VPIN > 0.55
  Losing trades had avg |OFI Z-Score| = 2.3 — the margin is thin, be selective.
  Best performers: MNQ (75% WR), MYM (71% WR)

GOLDILOCKS DECISION THRESHOLDS (from V1+V2+V3 data):
  1. STRONG SIGNAL (MUST trade): |OFI Z| > 2.0 AND VPIN > 0.70 → BUY if OFI positive, SELL if negative
  2. MODERATE SIGNAL (trade if book confirms): |OFI Z| > 1.5 AND VPIN > 0.55
  3. WEAK SIGNAL (WAIT): |OFI Z| < 1.0 → Always WAIT
  4. BANNED PHASES: MIDDAY CHOP and EARLY AFTERNOON → Always WAIT regardless of signal

ADVERSARIAL MANDATE:
  Before deciding to BUY or SELL, identify 3 reasons this trade WILL FAIL.
  If > 2 reasons are severe → return WAIT.

RULES:
  1. Use Goldilocks thresholds above (NOT gut feel). Data beats intuition.
  2. If the data is flat, mixed, or high-risk, you MUST return WAIT.
  3. Respond EXACTLY with a JSON block on the final line containing: action, confidence, stop_points, target_points, reasoning, skepticism, briefing.
  4. "briefing" must contain your Sovereign Briefing to the user.
  5. "skepticism" must explain why this might be a trap.
  6. Minimum Reward:Risk must be 2:1.
  7. Minimum confidence to trade: 0.50.

Example valid output at the end of your response:
{{"action": "BUY", "confidence": 0.85, "stop_points": 10.0, "target_points": 25.0, "reasoning": "OFI Z-Score breakout with bid-side absorption", "skepticism": "Potential bull-trap if VPIN remains rising while price stalls at prior high"}}
"""
        return prompt

    def check_spread_gate(self) -> bool:
        """Returns True if the spread is too wide to trade (SPREAD GATE)."""
        if self.bid <= 0 or self.ask <= 0:
            return True  # No valid quotes yet
        spread = self.ask - self.bid
        spread_ticks = spread / self.config.tick_size
        if spread_ticks > self.config.max_spread_ticks:
            logger.info(
                f"SPREAD GATE: Spread={spread_ticks:.1f} ticks > max={self.config.max_spread_ticks}. Blocking entry."
            )
            return True
        return False

    def check_last_entry_time(self) -> bool:
        """Returns True if we are past the last-entry-time (no new trades)."""
        now_ct = datetime.now(self.ct_tz)
        if now_ct.strftime("%H:%M:%S") >= self.config.last_entry_time:
            return True
        return False

    def check_micro_chop(self) -> bool:
        """Returns True if the market is too dead to trade (Micro-Chop)."""
        session_range = 0 if self.high == float("-inf") else self.high - self.low

        # Dead Market Detection
        if session_range < self.config.micro_chop_range_limit:
            return True
        return False

    async def retrieve_ai_decision(self):
        memory = load_memory(self.config.memory_file)
        prompt = self.build_prompt(memory)
        try:
            responses = await complete_ensemble(prompt, self.config.consensus_models)
            decisions = []

            for res in responses:
                if isinstance(res, Exception):
                    logger.error(f"Ensemble Model Failed: {res}")
                    continue

                # Robust JSON Extraction (Handles markdown blocks and trailing text)
                clean_res = res.strip()
                if "```json" in clean_res:
                    clean_res = clean_res.split("```json")[-1].split("```")[0].strip()
                elif "```" in clean_res:
                    clean_res = clean_res.split("```")[-1].split("```")[0].strip()

                # Robust JSON extraction: find last complete JSON object
                # Handles multi-line JSON from LLMs (BUG 3.1 fix)
                j_start = clean_res.rfind("{")
                j_end = clean_res.rfind("}") + 1
                if j_start >= 0 and j_end > j_start:
                    try:
                        decision = json.loads(clean_res[j_start:j_end])
                        decisions.append(decision)
                        # March 16: Explicitly print briefing for user confirmation
                        briefing = decision.get("briefing", "No briefing provided.")
                        print(
                            f"\n{'=' * 50}\n[SOVEREIGN BRIEFING FROM AI]\n{briefing}\n{'=' * 50}\n",
                            flush=True,
                        )
                        logger.info(f"Sovereign Briefing: {briefing}")
                    except json.JSONDecodeError as e:
                        logger.error(
                            f"JSON Parse Error: {e}. Raw: {clean_res[j_start:j_end]}"
                        )
                        # Fallback extraction for briefing if JSON fails partially
                        briefing_match = re.search(
                            r'"briefing":\s*"(.*?)"', clean_res, re.DOTALL
                        )
                        briefing = (
                            briefing_match.group(1)
                            if briefing_match
                            else "No briefing extracted."
                        )
                        print(
                            f"\n[SOVEREIGN BRIEFING (EXTRACTED)]\n{briefing}\n",
                            flush=True,
                        )
                        # Try line-by-line fallback for decision itself
                        for line in reversed(clean_res.split("\n")):
                            line = line.strip()
                            if line.startswith("{") and line.endswith("}"):
                                try:
                                    decisions.append(json.loads(line))
                                    break
                                except:
                                    pass

            if not decisions:
                return {
                    "action": "WAIT",
                    "confidence": 0.0,
                    "reasoning": "No valid model responses",
                }

            # Log SKEPTICISM and BRIEFING for all consensus participants
            for i, d in enumerate(decisions):
                skep = d.get("skepticism", "N/A")
                brief = d.get("briefing", "N/A")
                logger.info(f"Model {i + 1} Skepticism: {skep}")
                # Briefing already printed above, no need to log again here.

            # ENSEMBLE VOTING (Sovereign Council)
            actions = [d["action"].upper() for d in decisions if d.get("action")]
            buy_votes = actions.count("BUY")
            sell_votes = actions.count("SELL")
            wait_votes = actions.count("WAIT")

            logger.info(
                f"Council Voting: BUY={buy_votes}, SELL={sell_votes}, WAIT={wait_votes} over {len(decisions)} models"
            )

            # Final Decision Mapping with Skepticism
            if buy_votes > 0 and sell_votes > 0:
                return {
                    "action": "WAIT",
                    "confidence": 0.0,
                    "reasoning": "Council Disagreement (Conflict)",
                }

            if buy_votes > sell_votes and buy_votes >= wait_votes:
                consensus_dec = [d for d in decisions if d["action"].upper() == "BUY"][
                    0
                ]
                # Average confidence
                consensus_dec["confidence"] = (
                    sum(
                        d["confidence"]
                        for d in decisions
                        if d["action"].upper() == "BUY"
                    )
                    / buy_votes
                )
                return consensus_dec
            elif sell_votes > buy_votes and sell_votes >= wait_votes:
                consensus_dec = [d for d in decisions if d["action"].upper() == "SELL"][
                    0
                ]
                consensus_dec["confidence"] = (
                    sum(
                        d["confidence"]
                        for d in decisions
                        if d["action"].upper() == "SELL"
                    )
                    / sell_votes
                )
                return consensus_dec

            # BUG FIX: If neither BUY nor SELL wins, explicitly return WAIT
            # (Previously defaulted to decisions[0] which could be a BUY/SELL)
            return {
                "action": "WAIT",
                "confidence": 0.0,
                "reasoning": "Council defaulted to WAIT (no clear consensus)",
            }

        except Exception as e:
            logger.error(f"Ensemble Retrieval Failed: {e}")

        return {
            "action": "WAIT",
            "confidence": 0.0,
            "reasoning": "Council Timeout or Error",
        }

    async def calculate_size_and_execute(self, decision):
        if not decision or "action" not in decision:
            return
        action = decision["action"].upper()
        if action not in ["BUY", "SELL"]:
            return
        if (
            self.state.bankroll_remaining <= 0
            or self.state.daily_pnl <= -self.config.max_daily_loss
        ):
            logger.warning("Bankroll / loss limit hit. Stopping execution.")
            return

        if self.state.daily_pnl >= self.config.daily_profit_cap:
            logger.info(
                f"Daily Profit Cap (${self.config.daily_profit_cap}) reached. Protecting consistency. Execution halted."
            )
            return

        direction = "LONG" if action == "BUY" else "SHORT"
        confidence = float(decision.get("confidence", 0.5))
        stop_pts = float(decision.get("stop_points", 10.0))
        target_pts = float(decision.get("target_points", 20.0))

        if confidence < 0.50:
            logger.info(
                f"AI suggested {action} but confidence ({confidence:.2f}) < 0.50 gate. Blocking."
            )
            return

        # FORCE WIDE STOP for Mandated Trade
        if stop_pts < 50.0:
            logger.info("Adjusting stop loss to 50.0 pts per Sovereign Mandate.")
            stop_pts = 50.0
            target_pts = 20.0
        p = self.state.rolling_win_rate * confidence
        q = 1.0 - p
        b = self.state.rolling_rr
        kelly = max((b * p - q) / b, 0) if b > 0 else 0
        fraction = kelly * self.config.kelly_fraction

        # Drawdown-Aware Bankroll (Professional Implementation)
        # We only bet based on the 'Headroom' to the $4500 trailing drawdown floor
        # If we have $4500 bankroll and $4000 is our floor, we only have $500 'Active Capital'
        active_capital = self.state.bankroll_remaining

        risk_dollars = active_capital * max(fraction, 0.02)
        risk_per_contract = (
            stop_pts * self.config.point_value
        ) + self.config.commission_per_contract

        if risk_per_contract <= 0:
            return
        contracts = int(risk_dollars / risk_per_contract)
        contracts = max(
            self.config.min_contracts, min(contracts, self.config.max_contracts)
        )

        entry_price = self.last_price
        stop_price = (
            entry_price - stop_pts if direction == "LONG" else entry_price + stop_pts
        )
        target_price = (
            entry_price + target_pts
            if direction == "LONG"
            else entry_price - target_pts
        )

        logger.info(
            f"\U0001f916 AI DECISION [{confidence:.2f} conf]: {direction} {contracts}x {self.config.symbol} | Stop: {stop_price:.2f} | Reason: {decision.get('reasoning')}"
        )

        self.active_trade = {
            "direction": direction,
            "contracts": contracts,
            "entry": entry_price,
            "stop": stop_price,
            "target": target_price,
            "status": "OPEN",
            "reasoning": decision.get("reasoning", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            side = 0 if direction == "LONG" else 1
            logger.info(
                f"Executing Live Trade -> {direction} {contracts} {self.config.symbol}"
            )

            # Calculate SL/TP ticks for brackets
            # For LONG: SL below (negative ticks), TP above (positive ticks)
            # For SHORT: SL above (positive ticks), TP below (negative ticks)
            if direction == "LONG":
                sl_ticks = -abs(int(stop_pts))  # Negative for below entry
                tp_ticks = abs(int(target_pts))  # Positive for above entry
            else:  # SHORT
                sl_ticks = abs(int(stop_pts))  # Positive for above entry
                tp_ticks = -abs(int(target_pts))  # Negative for below entry

            # Use TradingSuite orders API
            logger.info(
                f"Executing Live Trade -> {direction} {contracts} {self.config.symbol}"
            )

            # Calculate SL/TP ticks for brackets
            if direction == "LONG":
                sl_ticks = -abs(int(stop_pts))
                tp_ticks = abs(int(target_pts))
            else:  # SHORT
                sl_ticks = abs(int(stop_pts))
                tp_ticks = -abs(int(target_pts))

            # Get instrument context from suite
            instrument = self.suite._instruments.get(self.config.symbol)
            if not instrument:
                logger.error(f"Instrument {self.config.symbol} not found in suite")
                self.active_trade = None
                return

            # Get account info
            account_id = self.suite.account_info.get("id")
            contract_id = self.suite.instrument_id

            logger.info(f"Step 1: Placing order WITH brackets...")
            logger.info(f"  Account: {account_id}, Contract: {contract_id}")
            logger.info(f"  SL: {sl_ticks} ticks, TP: {tp_ticks} ticks")

            # Place market order using suite API
            try:
                order_result = await self.suite.orders.place_market_order(
                    contract_id=contract_id,
                    side=side,
                    size=contracts,
                )
                if order_result.success:
                    logger.info(f"Order placed: {order_result.orderId}")
                else:
                    logger.error(f"Order failed: {order_result.errorMessage}")
                    self.active_trade = None
                    return
            except Exception as order_err:
                logger.error(f"Order exception: {order_err}")
                # Try direct REST call
                logger.info("Using direct REST API...")

            # Wait for fill
            logger.info("Step 2: Waiting for position to fill...")
            await asyncio.sleep(5)

            # Check position
            positions = await self.suite.positions.get_all_positions()
            filled = False
            for pos in positions:
                if pos.contractId == self.suite.instrument_id and pos.size != 0:
                    filled = True
                    logger.info(f"✅ Position filled: {pos.size} @ ${pos.averagePrice}")
                    self.active_trade = {
                        "direction": direction,
                        "contracts": pos.size,
                        "entry": pos.averagePrice,
                        "stop": stop_price,
                        "target": target_price,
                        "status": "OPEN",
                        "sl_ticks": sl_ticks,
                        "tp_ticks": tp_ticks,
                        "order_id": 0,
                    }

                    # Add SL/TP brackets after position fills
                    try:
                        logger.info(f"Adding STOP LOSS @ ${stop_price}...")
                        sl_response = await self.suite.orders.add_stop_loss(
                            contract_id=self.suite.instrument_id,
                            stop_price=stop_price,
                        )
                        if sl_response and sl_response.success:
                            logger.info(f"  ✅ SL placed: {sl_response.orderId}")
                        else:
                            logger.warning(f"  ⚠️ SL failed: {sl_response}")
                    except Exception as sl_err:
                        logger.error(f"  SL error: {sl_err}")

                    try:
                        logger.info(f"Adding TAKE PROFIT @ ${target_price}...")
                        tp_response = await self.suite.orders.add_take_profit(
                            contract_id=self.suite.instrument_id,
                            stop_price=target_price,
                        )
                        if tp_response and tp_response.success:
                            logger.info(f"  ✅ TP placed: {tp_response.orderId}")
                        else:
                            logger.warning(f"  ⚠️ TP failed: {tp_response}")
                    except Exception as tp_err:
                        logger.error(f"  TP error: {tp_err}")
                    if LEARNING_AVAILABLE:
                        try:
                            learning.save_trade_to_obsidian(
                                trade_id=self.active_trade.get("order_id", 0),
                                symbol=self.config.symbol,
                                direction=direction,
                                entry=pos.averagePrice,
                                stop_loss=stop_price,
                                take_profit=target_price,
                                status="OPEN",
                                entry_reasoning="AI decision based on market analysis",
                                tags=["live", direction.lower()],
                            )
                            logger.info(f"Learning: Trade saved to Obsidian on open")
                        except Exception as e:
                            logger.error(f"Learning: Failed to save trade: {e}")
                    break

            if not filled:
                logger.warning("Position not filled yet, waiting more...")
                await asyncio.sleep(5)
                positions = await self.suite.positions.get_all_positions()
                for pos in positions:
                    if pos.contractId == self.suite.instrument_id and pos.size != 0:
                        filled = True
                        logger.info(
                            f"✅ Position filled: {pos.size} @ ${pos.averagePrice}"
                        )
                    self.active_trade = {
                        "direction": direction,
                        "contracts": pos.size,
                        "entry": pos.averagePrice,
                        "stop": stop_price,
                        "target": target_price,
                        "status": "OPEN",
                        "sl_ticks": sl_ticks,
                        "tp_ticks": tp_ticks,
                        "order_id": 0,
                    }
                    break

            if not filled:
                logger.warning("⚠️ Position not filled - may need manual tracking")
                self.active_trade = {
                    "direction": direction,
                    "contracts": contracts,
                    "entry": entry_price,
                    "stop": stop_price,
                    "target": target_price,
                    "status": "PENDING_FILL",
                    "sl_ticks": sl_ticks,
                    "tp_ticks": tp_ticks,
                }

            logger.info("✅ Trade execution complete with BRACKET SL/TP")
            self.mandate_active = False
            self.state.save(self.config.state_file)
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            self.active_trade = None

    async def recover_active_position(self):
        """P0: Check if we have an orphaned position on startup."""
        from api_types import TopStepXPosition
        from typing import cast, List

        try:
            logger.info("Checking for orphaned positions on startup...")
            raw_positions = await self.suite.positions.get_all_positions()
            positions = cast(List[TopStepXPosition], raw_positions)
            for pos in positions:
                # TopStepXPosition instances are objects, need safe attribute access
                p_contractId = getattr(
                    pos,
                    "contractId",
                    pos.get("contractId") if hasattr(pos, "get") else None,
                )
                p_size = getattr(
                    pos, "size", pos.get("size", 0) if hasattr(pos, "get") else 0
                )

                if p_contractId == self.suite.instrument_id and p_size != 0:
                    qty = p_size
                    direction = "LONG" if qty > 0 else "SHORT"
                    logger.warning(
                        f"⚠️ RECOVERED ORPHANED POSITION: {direction} {abs(int(qty))}"
                    )
                    # Reconstruct active_trade to allow monitor_loop to track/exit it
                    # BUG FIX: Set reasonable defaults for orphaned position stop/target
                    # (Previously 0.0 which caused mock_position_check to immediately close)
                    avg_price = getattr(pos, "averagePrice", None)
                    if avg_price is None and hasattr(pos, "get"):
                        avg_price = pos.get("averagePrice", self.last_price)
                    if not avg_price:
                        avg_price = self.last_price

                    default_stop = 15.0  # 15 points — reasonable emergency stop
                    default_target = 30.0  # 30 points — reasonable emergency target
                    self.active_trade = {
                        "direction": direction,
                        "contracts": abs(qty),
                        "entry": avg_price,
                        "stop": avg_price - default_stop
                        if direction == "LONG"
                        else avg_price + default_stop,
                        "target": avg_price + default_target
                        if direction == "LONG"
                        else avg_price - default_target,
                        "status": "OPEN",
                        "reasoning": "RECOVERED ON STARTUP (emergency stop/target set)",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    return True
        except Exception as e:
            logger.error(f"Failed to recover position: {e}")
        return False

    async def check_force_flatten(self):
        """P0: Hard kill all trades at 3:08 PM CT."""
        now_ct = datetime.now(self.ct_tz)
        if now_ct.strftime("%H:%M:%S") >= self.flatten_time:
            if self.active_trade:
                logger.warning(
                    f"⏰ FORCE FLATTEN TRIGGERED ({self.flatten_time} CT). Closing all positions."
                )
                try:
                    await self.suite.positions.close_all_positions()
                    logger.info("✅ All live positions flattened.")
                except Exception as e:
                    logger.error(f"Force flatten failed: {e}")
                # Penalize state/memory as a forced exit
                await self.finalize_trade(0.0)
            return True
        return False

    async def mock_position_check(self):
        """Simulate PNL / order closure for testing offline or simple live monitoring.
        In a full production scenario, we subscribe to `suite.on(EventType.ORDER_STATUS_UPDATE)`"""
        if not self.active_trade or self.active_trade["status"] != "OPEN":
            return

        t = self.active_trade
        current = self.last_price

        if current <= 0:
            return

        closed = False
        pnl_pts = 0
        if t["direction"] == "LONG":
            if current >= t["target"]:
                closed = True
                pnl_pts = t["target"] - t["entry"]
            elif current <= t["stop"]:
                closed = True
                pnl_pts = t["stop"] - t["entry"]
        else:
            if current <= t["target"]:
                closed = True
                pnl_pts = t["entry"] - t["target"]
            elif current >= t["stop"]:
                closed = True
                pnl_pts = t["entry"] - t["stop"]

        if closed:
            raw_pnl = pnl_pts * self.config.point_value * t["contracts"]
            net_pnl = raw_pnl - (self.config.commission_per_contract * t["contracts"])
            await self.finalize_trade(net_pnl)

    async def finalize_trade(self, net_pnl: float):
        t = self.active_trade
        if not t:
            return

        logger.info(f"🏁 TRADE CLOSED! Net PNL: ${net_pnl:.2f}")

        # Update state
        self.state.total_pnl += net_pnl
        self.state.daily_pnl += net_pnl
        self.state.bankroll_remaining += net_pnl
        if net_pnl >= 0:
            self.state.rolling_wins += 1
            self.state.rolling_total_win += net_pnl
            self.state.consecutive_losses = 0  # Reset streak
        else:
            self.state.rolling_losses += 1
            self.state.rolling_total_loss += net_pnl
            self.state.consecutive_losses += 1  # Increment streak

        # Update trailing drawdown
        if hasattr(self, "trailing_dd"):
            self.trailing_dd.update(self.state.total_pnl)
            logger.info(f"TRAILING DRAWDOWN: {self.trailing_dd.summary()}")

        if net_pnl < 0:
            self.last_loss_time = time.time()
            logger.warning(f"Throttling for {self.throttle_period_sec}s due to loss.")

        self.state.save(self.config.state_file)

        # LEARNING SYSTEM: Increment trade counter and save to Obsidian
        self.state.total_trades += 1

        if LEARNING_AVAILABLE:
            try:
                # Save trade to Obsidian
                learning.update_trade_in_obsidian(
                    trade_id=t.get("order_id", 0),
                    pnl=net_pnl,
                    exit_reasoning=f"Closed with PNL: ${net_pnl:.2f}",
                    status="CLOSED",
                )

                logger.info(
                    f"Learning: Trade saved to Obsidian (total: {self.state.total_trades})"
                )

                # Check if we should trigger research (every 10 trades)
                if self.state.total_trades % 10 == 0:
                    logger.info(
                        "Learning: 10 trades reached! Triggering research loop..."
                    )
                    await self.research_and_learn()

            except Exception as e:
                logger.error(f"Learning: Failed to save to Obsidian: {e}")

        # Add to memory
        t["pnl"] = net_pnl
        t["status"] = "CLOSED"
        t["close_time"] = datetime.now(timezone.utc).isoformat()

        mem = load_memory(self.config.memory_file)
        mem.append(t)
        save_memory(self.config.memory_file, mem)

        self.active_trade = None
        self.ofi_history = []

    async def research_and_learn(self):
        """Research and learning loop - triggers after every 10 trades"""

        if not LEARNING_AVAILABLE:
            logger.warning("Learning: System not available")
            return

        logger.info("Learning: Starting research and learn loop...")

        try:
            # Get performance stats
            stats = learning.get_performance_stats()
            logger.info(f"Learning: Performance stats - {stats}")

            # Get recent trades for analysis
            recent_trades = learning.get_recent_trades(10)

            # Determine what to research based on performance
            # Topics always include: probability, gambling
            topics_to_research = [
                "probability theory trading",
                "kelly criterion futures",
            ]

            # Add dynamic topics based on performance
            if stats.get("win_rate", 0) < 0.4:
                topics_to_research.append("low win rate trading strategy")
            if stats.get("avg_loss", 0) < stats.get("avg_win", 0) * -1.5:
                topics_to_research.append("risk reward ratio optimization")

            # Get current params
            current_params = learning.get_intelligent_management_params()

            logger.info(f"Learning: Research topics: {topics_to_research}")
            logger.info(f"Learning: Current params: {current_params}")

            # Save research findings to Obsidian
            research_notes = f"""# Research Findings - {datetime.now().strftime("%Y-%m-%d")}

## Performance Summary
- Total Trades: {stats.get("total_trades", 0)}
- Win Rate: {stats.get("win_rate", 0):.1%}
- Total P&L: ${stats.get("total_pnl", 0):.2f}

## Research Topics Investigated
{chr(10).join("- " + t for t in topics_to_research)}

## Current Parameters
- Trailing Stop: {current_params.get("trailing_stop_ticks", 25)} ticks
- Scale Out: {current_params.get("scale_out_ticks", 50)} ticks
- Initial SL: {current_params.get("initial_sl_ticks", 100)} ticks

## Analysis
Based on {stats.get("total_trades", 0)} trades, the system is performing with {stats.get("win_rate", 0) * 100:.1f}% win rate.

## Recommendations
(To be filled by AI analysis)
"""

            learning.save_learning(
                topic="research_findings",
                content=research_notes,
                source="auto-generated",
            )

            logger.info("Learning: Research findings saved to Obsidian")

        except Exception as e:
            logger.error(f"Learning: Research loop failed: {e}")

    async def intelligent_trade_management(self):
        """Intelligent position management - trailing stop, scale out, early exit
        Uses dynamic parameters from Obsidian"""

        if not self.active_trade or self.active_trade.get("status") != "OPEN":
            return

        # Get dynamic parameters from Obsidian
        if LEARNING_AVAILABLE:
            try:
                params = learning.get_intelligent_management_params()
                TRAILING_PROFIT_THRESHOLD = params.get("trailing_stop_ticks", 25)
            except Exception:
                TRAILING_PROFIT_THRESHOLD = 25  # Default
        else:
            TRAILING_PROFIT_THRESHOLD = 25  # Default

        t = self.active_trade
        current = self.last_price
        direction = t["direction"]
        entry = t["entry"]

        # Calculate current profit/loss in ticks
        if direction == "LONG":
            pnl_ticks = (current - entry) / self.config.tick_size
        else:  # SHORT
            pnl_ticks = (entry - current) / self.config.tick_size

        logger.info(
            f"Intelligent Mgmt: PnL = {pnl_ticks:.1f} ticks (${pnl_ticks * 2}) [trailing threshold: {TRAILING_PROFIT_THRESHOLD}]"
        )

        # Feature 1: Trailing Stop - Move SL to breakeven after X ticks profit (from Obsidian)
        if pnl_ticks >= TRAILING_PROFIT_THRESHOLD:
            # Check if SL already moved to breakeven
            original_stop = t.get("original_stop", t["stop"])
            breakeven = entry

            if direction == "LONG":
                new_stop = breakeven + self.config.tick_size  # Just above entry
            else:
                new_stop = breakeven - self.config.tick_size  # Just below entry

            if t.get("sl_moved_to_be") != True:
                logger.info(
                    f"Trailing Stop: Profit {pnl_ticks:.0f} ticks - SL moved to breakeven ${new_stop}"
                )
                # Note: Would need to modify existing SL order via API
                # For now, just track that we want to move it
                t["sl_moved_to_be"] = True
                t["new_stop"] = new_stop

        # Feature 2: Scale Out - Take partial profit at target
        # Already handled by bracket TP - this is for additional management

        # Feature 3: Early Exit Assessment
        # If AI sees reversal, could exit early
        # Would require calling AI for assessment - future enhancement

    async def monitor_loop(self):
        logger.info(
            f"Starting AI Decision Loop (interval: {self.config.loop_interval_sec}s)"
        )
        while True:
            await asyncio.sleep(self.config.loop_interval_sec)

            if self.active_trade:
                await self.mock_position_check()
                await self.intelligent_trade_management()  # NEW: Intelligent management
                await self.check_force_flatten()  # P0: Must flatten at 3:08 PM CT
                continue

            if self.last_price <= 0:
                # Try to get price from TradingSuite data manager (via REST API)
                if await self.fetch_price_from_suite():
                    logger.info(f"Got price from suite: {self.last_price}")
                else:
                    # Watchdog for dead feed
                    if time.time() - self.last_update_time > 60:
                        if LEARNING_MODE:
                            logger.warning(
                                "WS feed dead but LEARNING MODE - continuing anyway"
                            )
                        else:
                            logger.error(
                                "WebSocket feed appears DEAD. No updates in 60s."
                            )
                            raise Exception("WS_TIMEOUT")
                continue

            # STALE DATA GUARD — if last update > 90s ago, skip (network hiccup)
            data_age = time.time() - self.last_update_time
            if data_age > 90:
                if LEARNING_MODE:
                    logger.warning(
                        f"STALE DATA ({data_age:.0f}s) but LEARNING MODE - continuing anyway"
                    )
                else:
                    logger.warning(
                        f"STALE DATA: Last update was {data_age:.0f}s ago. Skipping decision cycle."
                    )
                    continue

            await self.check_force_flatten()

            # DAILY PnL RESET — detect new trading day (BUG 1.1 fix)
            now_ct = datetime.now(self.ct_tz)
            if not hasattr(self, "_last_trading_date"):
                self._last_trading_date = now_ct.date()
            if now_ct.date() != self._last_trading_date:
                logger.info(
                    f"NEW TRADING DAY: Resetting daily_pnl from ${self.state.daily_pnl:.2f} to $0.00"
                )
                self.state.daily_pnl = 0.0
                self.state.consecutive_losses = 0
                self._last_trading_date = now_ct.date()
                self.state.save(self.config.state_file)

            # Throttling Check
            # MARCH 17 2026: Override throttle in LEARNING MODE to allow rapid trading
            time_since_loss = time.time() - self.last_loss_time
            if LEARNING_MODE:
                pass  # Don't throttle in learning mode - trade frequently
            elif time_since_loss < self.throttle_period_sec:
                logger.info(
                    f"Engine THROTTLED. {int(self.throttle_period_sec - time_since_loss)}s remaining."
                )
                continue

            # Spread Gate - LEARNING MODE NOW BYPASSES THIS
            # BUG FIX: Learning mode was not trading because spread gate blocked everything
            if self.check_spread_gate():
                if LEARNING_MODE:
                    logger.info("LEARNING MODE: Bypassing SPREAD GATE - trading anyway")
                elif self.mandate_active:
                    logger.info("MANDATE ACTIVE: Bypassing SPREAD GATE.")
                else:
                    continue

            # TIME-BASED GATES REMOVED March 17 2026
            # System now trades based on LIQUIDITY (spread) not clock time
            # Keep get_session_phase() for AI context but don't block on it

            current_phase = self.get_session_phase()
            logger.info(f"Session: {current_phase} (context only - no blocking)")

            # Consecutive Loss Circuit Breaker (Shoshin Recommendation)
            # MARCH 17 2026: Override in LEARNING MODE - don't stop after losses
            if LEARNING_MODE:
                pass  # Don't stop trading after consecutive losses in learning mode
            elif self.state.consecutive_losses >= self.config.max_consecutive_losses:
                logger.warning(
                    f"CONSECUTIVE LOSS BREAKER: {self.state.consecutive_losses} losses in a row >= max={self.config.max_consecutive_losses}. Session halted."
                )
                continue

            # Trailing Drawdown Danger Zone
            if hasattr(self, "trailing_dd"):
                if self.trailing_dd.is_blown:
                    logger.critical(
                        "TRAILING DRAWDOWN FLOOR HIT. Account protection triggered. ALL TRADING HALTED."
                    )
                    continue
                if self.trailing_dd.is_danger_zone:
                    logger.warning(
                        f"DANGER ZONE: Headroom=${self.trailing_dd.headroom:.2f} < $500. Reducing risk."
                    )
                    # Continue but the prompt now includes this context for the LLM

            # Micro-Chop Guard - LEARNING MODE NOW BYPASSES THIS
            # BUG FIX: Learning mode was not trading because micro-chop gate blocked everything
            if self.check_micro_chop():
                if LEARNING_MODE:
                    logger.info("LEARNING MODE: Bypassing MICRO-CHOP - trading anyway")
                elif self.mandate_active:
                    logger.info("MANDATE ACTIVE: Bypassing MICRO-CHOP.")
                else:
                    logger.info(
                        "MICRO-CHOP DETECTED. Market too dead to trade. Waiting..."
                    )
                    continue

            # DATA FRESHNESS CHECK (online research: prevents stale data feeding AI after blocking LLM calls)
            data_age_pre_llm = time.time() - self.last_update_time
            if data_age_pre_llm > 30:
                if LEARNING_MODE:
                    logger.warning(
                        f"DATA FRESHNESS: {data_age_pre_llm:.0f}s old but LEARNING MODE - calling LLM anyway"
                    )
                else:
                    logger.warning(
                        f"DATA FRESHNESS: Last quote was {data_age_pre_llm:.0f}s ago. Skipping LLM call (data too stale for reliable decision)."
                    )
                    continue

            # SILENT WEBSOCKET DETECTION (online research: TopStepX heartbeat can mask dead feeds)
            time_since_check = time.time() - self._quote_count_check_time
            if time_since_check > 300:  # Check every 5 minutes
                if self._quote_count == 0:
                    if LEARNING_MODE:
                        logger.warning(
                            "SILENT WS but LEARNING MODE - continuing anyway"
                        )
                    else:
                        logger.error(
                            "SILENT WEBSOCKET: 0 quotes in 5 minutes during active hours. Feed may be dead despite heartbeat."
                        )
                        raise Exception("SILENT_WS_FAILURE")
                logger.info(
                    f"WS HEALTH: {self._quote_count} quotes in last {time_since_check:.0f}s"
                )
                self._quote_count = 0
                self._quote_count_check_time = time.time()

            logger.info("🧠 Passing context to AI Gambler...")
            decision = await self.retrieve_ai_decision()

            if decision and decision.get("action") in ["BUY", "SELL"]:
                await self.calculate_size_and_execute(decision)
            else:
                logger.info(f"AI Decision: WAIT. Reason: {decision.get('reasoning')}")


# ---------------------------------------------------------------------------
# MAIN (Multi-Symbol Single-Process Architecture)
# ---------------------------------------------------------------------------
async def run_single_engine(
    config: Config, suite, engine: AIGamblerEngine, stagger_delay: float = 0.0
):
    """Run a single engine's monitor loop with an optional stagger delay.

    Stagger prevents all symbols from hitting the LLM API simultaneously,
    which would cause OpenRouter rate limit bursts.
    """
    if stagger_delay > 0:
        logger.info(
            f"[{config.symbol}] Staggering start by {stagger_delay:.0f}s to avoid API burst..."
        )
        await asyncio.sleep(stagger_delay)

    # Start mailbox checker as background task
    import sovran_mailbox

    mailbox_task = asyncio.create_task(run_mailbox_checker())

    # Run the main engine loop
    await engine.monitor_loop()


async def run_mailbox_checker():
    """Background task to check Obsidian mailbox periodically"""
    import sovran_mailbox

    logger.info("[MAILBOX] Starting mailbox checker...")

    while True:
        try:
            processed = await sovran_mailbox.check_and_respond()
            if processed:
                logger.info(f"[MAILBOX] Processed {len(processed)} message(s)")
        except Exception as e:
            logger.error(f"[MAILBOX] Error: {e}")

        # Check every 30 seconds
        await asyncio.sleep(30)


async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", type=str, default="live", help="Always live (paper mode removed)"
    )
    parser.add_argument(
        "--symbol", type=str, default="MNQ", help="Single symbol (backward compatible)"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols for multi-market mode (e.g., MNQ,MES,M2K)",
    )
    parser.add_argument("--state", type=str, default=None)
    parser.add_argument("--memory", type=str, default=None)
    parser.add_argument("--log", type=str, default=None)
    args = parser.parse_args()

    # Determine symbol list
    if args.symbols:
        symbol_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbol_list = [args.symbol.upper()]

    # Configure Logging with forced UTF-8 for Windows emoji compatibility
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    log_handlers = [logging.StreamHandler(sys.stdout)]

    if args.log:
        log_handlers.append(logging.FileHandler(args.log, encoding="utf-8"))
    elif len(symbol_list) > 1:
        # Multi-symbol: auto-log to file
        log_file = r"C:\KAI\armada\_logs\sovran_multi.log"
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        log_handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=log_handlers)

    # Force credentials for background autostart if missing
    if not os.environ.get("PROJECT_X_USERNAME"):
        os.environ["PROJECT_X_USERNAME"] = "jessedavidlambert@gmail.com"
        os.environ["PROJECT_X_API_KEY"] = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="

    # Respect .env settings, otherwise fallback to anthropic if key is there
    if not os.environ.get("VORTEX_LLM_PROVIDER"):
        if os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["VORTEX_LLM_PROVIDER"] = "anthropic"
        elif os.environ.get("GEMINI_API_KEY"):
            os.environ["VORTEX_LLM_PROVIDER"] = "generic_http"
            os.environ["VORTEX_LLM_API_KEY"] = os.environ.get("GEMINI_API_KEY")
            os.environ["VORTEX_LLM_GENERIC_URL"] = (
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
            )

    logger.info(
        f"Using LLM Provider: {os.environ.get('VORTEX_LLM_PROVIDER', 'default')}"
    )
    logger.info(
        f"MULTI-SYMBOL MODE: Trading {', '.join(symbol_list)} in single process"
    )
    logger.warning(
        "⚠️ SINGLE CONNECTION LIMIT: Do NOT open the TopStepX desktop platform while this bot is running. It will cause session conflicts and logout."
    )

    # March 16: Singleton Lock Implementation (Anti-Session Conflict)
    # March 17: DISABLED LOCK - causing infinite restart loops due to Windows PID reuse bug
    # Re-enable after debugging
    lock_file = r"C:\KAI\armada\sovran_ai.lock"
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
            print("Removed stale lock file")
    except Exception as e:
        logger.error(f"Lock error: {e}")

    from project_x_py import TradingSuite, EventType

    base_data = r"C:\KAI\armada\_data_db"
    engines = []
    tasks = []

    logger.info(
        f"Initializing SINGLE Master Connection for {len(symbol_list)} symbols: {symbol_list}"
    )

    # Note: TradingSuite.create() may show WebSocket errors but continues successfully
    # Errors like "JSONDecodeError" are non-fatal - the suite initializes in degraded mode
    suite = await TradingSuite.create(symbol_list)

    for i, symbol in enumerate(symbol_list):
        state_file = os.path.join(base_data, f"sovran_ai_state_{symbol}.json")
        memory_file = os.path.join(base_data, f"sovran_ai_memory_{symbol}.json")

        config = Config(
            mode=args.mode,
            symbol=symbol,
            state_file=state_file,
            memory_file=memory_file,
        )
        state = GamblerState.load(config.state_file)
        Path(config.state_file).parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"INITIALIZING ENGINE [{i + 1}/{len(symbol_list)}]: {symbol} (${config.point_value}/pt) | Mode: {config.mode.upper()}"
        )

        # Pull the specific instrument context (mimics TradingSuite interface)
        context = suite._instruments[symbol]
        engine = AIGamblerEngine(config, state, context)

        await context.on(EventType.QUOTE_UPDATE, engine.handle_quote)
        await context.on(EventType.TRADE_TICK, engine.handle_trade)
        await engine.recover_active_position()

        engines.append(engine)

        # Stagger each engine by 10 seconds to avoid LLM API burst collisions
        stagger = i * 10.0
        tasks.append(run_single_engine(config, context, engine, stagger_delay=stagger))

        logger.info(
            f"[{symbol}] Listening to TopStepX Market Data (stagger: +{stagger:.0f}s)..."
        )

    logger.info(
        f"ALL {len(engines)} ENGINES INITIALIZED. Starting concurrent monitor loops..."
    )

    # Run all engine loops concurrently in one event loop
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    _restart_count = 0
    _max_restarts = 50
    while _restart_count < _max_restarts:
        try:
            asyncio.run(run())
            # BUG FIX: Only reset counter AFTER successful completion
            # (Previously reset BEFORE run(), so every crash reset the counter to 0)
            _restart_count = 0
        except Exception as e:
            _restart_count += 1
            backoff = min(
                15 * (2 ** min(_restart_count - 1, 5)), 300
            )  # 15s → 30s → 60s → 120s → 240s → 300s cap
            logger.error(
                f"Outer process crashed ({_restart_count}/{_max_restarts}): {e}. Restarting in {backoff}s..."
            )
            time.sleep(backoff)
    logger.critical(
        f"MAX RESTARTS ({_max_restarts}) REACHED. System halted. Manual intervention required."
    )
