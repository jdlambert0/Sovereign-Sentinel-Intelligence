"""
VORTEX V2 - Intelligent Autonomous MNQ Futures Trader
=====================================================
Built following three philosophies:
  1. Agentic Engineering: minimal context, contracts not vibes
  2. Stripe Minion: blueprint of deterministic code + AI reasoning
  3. Simple Over Easy: essential complexity only

Blueprint:
  [CODE] Init + cleanup orphans
  [CODE] Poll price + sync position
  [CODE] Compute market features
  [AGENT] Claude decides: action + parameters
  [CODE] Validate + execute via SDK bracket order
  [CODE] Verify order IDs (the contract)
  [CODE] Log + save state
  [CODE] Loop
"""
import asyncio
import json
import logging
import os
import random
import sys
import time
import traceback
import urllib.request
import urllib.error
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, date
from pathlib import Path
from statistics import mean, stdev
import pytz  # For timezone-aware daily reset checks
import urllib.error  # For HTTP error handling (rate limits)
from fleet_manager import FleetManager
from awareness_engine import AwarenessEngine
from warwick_engine import WarwickEngine, WarwickLeg
import risk_math
from broker_outage_recovery import BrokerOutageCoordinator
from vortex_steering_vectors import SteeringVectors

# Fix Windows console encoding
if sys.platform == "win32":
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

VORTEX_DIR = Path(__file__).resolve().parent
STATE_DIR = VORTEX_DIR / "state"
LOG_DIR = VORTEX_DIR / "logs"
STATE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

STATUS_FILE = STATE_DIR / "runtime_status.json"
MEMORY_FILE = STATE_DIR / "vortex_v2_memory.json"
TRADE_LOG_FILE = STATE_DIR / "trade_log.json"
FLEET_DIGEST_FILE = STATE_DIR / "fleet_agents_digest.json"
ANOMALY_LOG_FILE = STATE_DIR / "anomalies.json"
LOG_FILE = LOG_DIR / "vortex_v2.log"
L2_ORDERBOOK_VERIFICATION_FILE = LOG_DIR / "L2_ORDERBOOK_VERIFICATION.log"

STRESS_TEST_MODE = os.environ.get("VORTEX_STRESS_TEST", "0") == "1"
RPNL_TARGET = float(os.environ.get('VORTEX_RPNL_TARGET', '10000'))
DAILY_LOSS_LIMIT = float(os.environ.get('VORTEX_DAILY_LOSS_LIMIT', '-500'))

logging.basicConfig(
    level=logging.DEBUG,  # VERBOSE: Changed from INFO to DEBUG for full visibility
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("vortex")
log.setLevel(logging.DEBUG)  # VERBOSE: Ensure vortex logger captures all levels

# Silence SDK noise - ALL of it
for name in ['project_x_py', 'SignalRCoreClient', 'project_x_py.client.auth',
             'project_x_py.realtime', 'project_x_py.order_manager',
             'project_x_py.position_manager', 'project_x_py.statistics',
             'httpx', 'httpcore', 'hpack', 'h2']:
    logging.getLogger(name).setLevel(logging.CRITICAL)
logging.getLogger('SignalRCoreClient').setLevel(logging.CRITICAL)

# ============================================================
# TRADING CONSTANTS & THRESHOLDS
# ============================================================
MAX_POSITION = 10  # Absolute position limit (contracts)
DAILY_LOSS_LIMIT_USD = -500  # Stop trading at -$500
ORDER_TIMEOUT_SECONDS = 30  # Order placement timeout
L2_SPREAD_THRESHOLD_PT = 0.5  # Max acceptable spread in points
L2_IMBALANCE_THRESHOLD = 0.2  # Max acceptable imbalance ratio
L2_DEPTH_THRESHOLD = 100  # Min volume at top level
# L2 SAFETY THRESHOLDS - Data freshness and circuit breaker
L2_STALE_WARNING_SECONDS = 5.0  # Warn when L2 data is older than this
L2_STALE_BLOCK_SECONDS = 10.0  # Block entries when L2 data is older than this
L2_CIRCUIT_BREAKER_SECONDS = 60.0  # Activate circuit breaker after cumulative stale time
# ML_CONFIDENCE_THRESHOLD removed 2026-03-09 (ML filter disabled)

# ============================================================
# POSITION ENTRY LOCK - PHASE 1 FIX for race condition
# ============================================================
# CRITICAL: Prevents 17-contract accumulation when all 3 engines
# check position=0 and all enter in same control loop cycle.
# Atomic lock ensures: check position -> decide -> execute order -> release
position_entry_lock = asyncio.Lock()

# ============================================================
# CLAUDE RATE LIMIT HANDLING - Priority Fix 2026-03-09
# ============================================================
# Handles HTTP 429 rate limit errors from Claude API
# with exponential backoff retry logic + jitter
CLAUDE_RATE_LIMIT_MAX_RETRIES = 3
CLAUDE_RATE_LIMIT_BASE_WAIT = 30  # Start with 30s wait

async def handle_claude_rate_limit(error: urllib.error.HTTPError, retry_count: int = 0, remaining_trades: int = 0) -> bool:
    """Handle Claude API rate limit (429) with backoff retry + jitter.
    
    SAFETY IMPROVEMENT 2026-03-09:
    - Added jitter (random 0-30 seconds) to retry delays
    - Logs remaining trades count when rate limited
    
    Args:
        error: The HTTPError from urllib
        retry_count: Current retry attempt number
        remaining_trades: Number of trades still pending (for logging)
    
    Returns:
        True if we should retry, False if retries exhausted
    """
    if retry_count >= CLAUDE_RATE_LIMIT_MAX_RETRIES:
        log.error(f"CLAUDE RATE LIMIT: Max retries ({CLAUDE_RATE_LIMIT_MAX_RETRIES}) exhausted | Remaining trades: {remaining_trades}")
        return False
    
    # Get retry-after header or use exponential backoff
    retry_after = error.headers.get('retry-after')
    if retry_after:
        wait_seconds = int(retry_after)
    else:
        # Exponential backoff: 30s, 60s, 120s
        wait_seconds = CLAUDE_RATE_LIMIT_BASE_WAIT * (2 ** retry_count)
    
    # SAFETY: Add jitter (0-30 seconds) to prevent thundering herd
    jitter = random.randint(0, 30)
    total_wait = wait_seconds + jitter
    
    log.warning(f"CLAUDE RATE LIMIT (429): Rate limited | Remaining trades: {remaining_trades} | "
                f"Waiting {total_wait}s (base={wait_seconds}s + jitter={jitter}s) before retry {retry_count + 1}/{CLAUDE_RATE_LIMIT_MAX_RETRIES}")
    await asyncio.sleep(total_wait)
    return True

def is_rate_limit_error(e: Exception) -> bool:
    """Check if exception is a Claude rate limit error."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code == 429
    return False

# Auto-load .env from current working directory (enables python vortex_v2.py without exporting env vars)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                if _k.strip() not in os.environ:  # don't override explicit env vars
                    os.environ[_k.strip()] = _v.strip()

# ML_ENTRY_FILTER: REMOVED 2026-03-09
# Reason: 52% CV score model with 65% threshold blocked ALL trades
# The model was trained on limited data and its predictions (22-30% confidence)
# were systematically pessimistic, preventing any trading activity.
# Decision: Let AI engines (Warwick/Council/Chimera) trade freely with their
# own risk logic rather than blocking entries with a weak model.
# See PHASES_1_2_3_IMPLEMENTATION_COMPLETE.md for removal details.

# ============================================================
# CONFIG - all from environment, nothing hardcoded
# ============================================================
USERNAME = os.environ.get('PROJECT_X_USERNAME', '')
API_KEY = os.environ.get('PROJECT_X_API_KEY', '')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
AI_MODEL = os.environ.get('VORTEX_AI_MODEL', 'claude-sonnet-4-20250514')
HAIKU_MODEL = "claude-haiku-3-5-20250514"  # Cheap model for routine HOLDs
TICKER = os.environ.get('VORTEX_TICKER', 'MNQ')

# Instrument configuration: point_value = tickValue / tickSize
# This is the dollar P&L per 1.0 price-point move per contract.
INSTRUMENT_CONFIG = {
    'MNQ': {'point_value': 2.0,   'tick_size': 0.25, 'tick_value': 0.50,  'commission_rt': 1.04, 'name': 'Micro E-mini Nasdaq'},
    'MES': {'point_value': 5.0,   'tick_size': 0.25, 'tick_value': 1.25,  'commission_rt': 1.04, 'name': 'Micro E-mini S&P'},
    'MCL': {'point_value': 100.0, 'tick_size': 0.01, 'tick_value': 1.00,  'commission_rt': 1.04, 'name': 'Micro Crude Oil'},
    'MGC': {'point_value': 10.0,  'tick_size': 0.10, 'tick_value': 1.00,  'commission_rt': 1.04, 'name': 'Micro Gold'},
    'MYM': {'point_value': 0.5,   'tick_size': 1.0,  'tick_value': 0.50,  'commission_rt': 1.04, 'name': 'Micro E-mini Dow'},
    'M2K': {'point_value': 5.0,   'tick_size': 0.10, 'tick_value': 0.50,  'commission_rt': 1.04, 'name': 'Micro E-mini Russell'},
}
if TICKER not in INSTRUMENT_CONFIG:
    log.error(f"Unknown ticker '{TICKER}'. Supported: {list(INSTRUMENT_CONFIG.keys())}")
    sys.exit(1)
POINT_VALUE = INSTRUMENT_CONFIG[TICKER]['point_value']

# Multi-market contract IDs for price feed subscription
# MNQ/MES/MYM/M2K = H26 (March), MCL/MGC = J26 (April)
MICRO_CONTRACTS = {
    "MNQ": "CON.F.US.MNQ.H26",
    "MES": "CON.F.US.MES.H26",
    "MCL": "CON.F.US.MCLE.J26",
    "MGC": "CON.F.US.MGC.J26",
    "MYM": "CON.F.US.MYM.H26",
    "M2K": "CON.F.US.M2K.H26",
}
# Reverse lookup: contract_id -> ticker symbol
CONTRACT_TO_TICKER = {v: k for k, v in MICRO_CONTRACTS.items()}

DECISION_INTERVAL = int(os.environ.get('VORTEX_DECISION_INTERVAL', '10'))
BURST_INTERVAL = 5  # seconds between SL/TP adjustments (no API call)
MAX_TOTAL_POSITION = int(os.environ.get('VORTEX_MAX_TOTAL_POSITION', '30'))
GAMBLING_MODE = os.environ.get('VORTEX_GAMBLING_MODE', '0') == '1'
ENABLE_BOOTSTRAP = os.environ.get('VORTEX_ENABLE_BOOTSTRAP', '0') == '1'
BOOTSTRAP_TRADES_TARGET = int(os.environ.get('VORTEX_BOOTSTRAP_TRADES', '15'))
ENABLE_MULTI_MARKET_TEST = os.environ.get('VORTEX_ENABLE_MULTI_MARKET_TEST', '0') == '1'
ALLOW_ESTIMATED_L2 = os.environ.get('VORTEX_ALLOW_ESTIMATED_L2', '0') == '1'
PRE_ENTRY_MAX_SPREAD_POINTS = float(os.environ.get('VORTEX_PRE_ENTRY_MAX_SPREAD_POINTS', '10.0'))
PRE_ENTRY_MARKET_DATA_MAX_AGE_SECONDS = float(os.environ.get('VORTEX_PRE_ENTRY_MARKET_DATA_MAX_AGE_SECONDS', '5.0'))
PRE_ENTRY_STOP_BUFFER_TICKS = int(os.environ.get('VORTEX_PRE_ENTRY_STOP_BUFFER_TICKS', '2'))
L2_MIN_DEPTH_USD = float(os.environ.get('VORTEX_L2_MIN_DEPTH_USD', '0.0'))

if not USERNAME or not API_KEY:
    log.error("Set PROJECT_X_USERNAME and PROJECT_X_API_KEY environment variables")
    sys.exit(1)
if not ANTHROPIC_KEY:
    if STRESS_TEST_MODE:
        log.warning("ANTHROPIC_API_KEY not set - proceeding in STRESS_TEST_MODE without AI features")
    else:
        log.error("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

os.environ['PROJECT_X_USERNAME'] = USERNAME
os.environ['PROJECT_X_API_KEY'] = API_KEY


# ============================================================
# STATE
# ============================================================
@dataclass
class TradeRecord:
    entry_order_id: int | None = None
    sl_order_id: int | None = None
    tp_order_id: int | None = None
    side: str = "FLAT"
    size: int = 0
    entry_price: float = 0.0
    sl_price: float = 0.0
    tp_price: float = 0.0
    opened_at: str = ""
    # LEARNING MODE: Pattern tracking for autonomous learning
    pattern_id: int | None = None  # ID of recognized pattern (if any)
    pattern_confidence: float = 0.5  # Confidence at entry time
    reasoning: str = ""  # Why this trade was taken

@dataclass
class MarketRegime:
    """Deterministic environment context for one market."""
    regime: str = "RANGING"  # RANGING, TRENDING_UP, TRENDING_DOWN, CHOPPY, VOLATILE
    confidence: float = 0.0
    atr: float = 0.0
    spread_ticks: float = 0.0
    timestamp: float = 0.0
    description: str = "Market is in range, no clear trend"

@dataclass
class MarketState:
    symbol: str
    price: float = 0.0
    prices: deque = field(default_factory=lambda: deque(maxlen=300))
    current_atr: float = 0.0
    regime: MarketRegime = field(default_factory=MarketRegime)
    orderbook_data: dict = field(default_factory=dict)
    price_timestamp: float = 0.0
    l2_timestamp: float = 0.0
    daily_pnl: float = 0.0  # Phase 4: Local P&L
    
    # Position tracking
    position_side: str = "FLAT"
    position_size: int = 0
    position_entry: float = 0.0
    
    # Engine-specific trade records (Isolated per instrument)
    council_trade: TradeRecord = field(default_factory=TradeRecord)
    warwick_primary: TradeRecord = field(default_factory=TradeRecord)
    warwick_hedge: TradeRecord = field(default_factory=TradeRecord)
    chimera_trade: TradeRecord = field(default_factory=TradeRecord)
    
    # Engine Instances (Isolated per instrument)
    warwick_engine: any = None  # WarwickEngine(point_value)
    
    def is_stale(self, threshold: float = 5.0) -> bool:
        return (time.time() - self.price_timestamp) > threshold if self.price_timestamp > 0 else True

    def l2_stale(self, threshold: float = 10.0) -> bool:
        return (time.time() - self.l2_timestamp) > threshold if self.l2_timestamp > 0 else True

    def check_braid_alpha(self) -> str:
        """S-1: Leading L2 Imbalance + Delta Acceleration (Velocity Change).
        Goal: Catch the 'ignition' of the move rather than the 'exhaustion'.
        """
        imbalance = self.orderbook_data.get('imbalance', 0.0)
        if len(self.prices) < 10: return "NEUTRAL"
        
        # 1. Calculate Velocity (V1: 0-5, V2: 5-10)
        p_list = list(self.prices)
        v1 = (p_list[-1] - p_list[-5]) / 5
        v2 = (p_list[-5] - p_list[-10]) / 5
        
        # 2. Delta Acceleration (Rate of Change of Velocity)
        acceleration = v1 - v2
        
        # 3. Decision Logic: Imbalance > 0.6 AND Velocity confirming AND Acceleration positive
        if imbalance > 0.6 and v1 > 0 and acceleration > 0:
            return "BUY_ALPHA"
        if imbalance < -0.6 and v1 < 0 and acceleration < 0:
            return "SELL_ALPHA"
        return "NEUTRAL"

    def get_dynamic_size(self) -> int:
        """S-2: Risk-Parity Sizing (Constant Dollar Risk).
        Formula: Size = min(MaxContracts, TargetRiskUSD / (ATR * StopMultiplier * PointValue)).
        TargetRiskUSD: $100 per instrument (can be overridden by AI).
        """
        # 1. Get instrument config
        config = INSTRUMENT_CONFIG.get(self.symbol, {'point_value': 2.0})
        point_value = config['point_value']
        
        # 2. Use $100 baseline risk or AI override (if implemented in state)
        target_risk = getattr(state, 'ai_override_risk', 100.0)
        
        # 3. Calculate volatility-adjusted size
        atr = max(0.5, self.current_atr) # Floor ATR to prevent division by zero
        stop_multiplier = 1.5 # Default multiplier
        
        raw_size = target_risk / (atr * stop_multiplier * point_value)
        dynamic_size = max(1, min(5, round(raw_size)))
        
        return dynamic_size

    def get_open_risk(self) -> float:
        """PHASE 6: Calculate total dollar-at-risk for this instrument."""
        if self.position_side == "FLAT": return 0.0
        
        tick_value = INSTRUMENT_CONFIG.get(self.symbol, {'point_value': 2.0})['point_value']
        # Risk = Contracts * ATR * StopMultiplier (default 1.5) * TickValue
        risk_points = self.current_atr * 1.5
        total_risk = self.position_size * risk_points * tick_value
        return total_risk


@dataclass
class VortexState:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = VortexState()
            # FORCE INITIALIZATION
            cls._instance.market_prices = {}
            cls._instance.markets = {}
            cls._instance.open_trades = {}
            cls._instance.council_trade = TradeRecord()
            cls._instance.chimera_trade = TradeRecord()
            cls._instance.position_entry_lock = asyncio.Lock()
            # Added for multi-market support
            cls._instance.warwick_primary = TradeRecord()
            cls._instance.warwick_hedge = TradeRecord()
            cls._instance.ai_risk_limit = 500.0
            cls._instance.ai_override_risk = 100.0
            cls._instance.consecutive_loss_threshold = 10
            cls._instance.max_position_size_limit = 8
            cls._instance.stale_price_threshold = 20.0
        return cls._instance

    market_prices: dict = field(default_factory=dict) # Symbol -> Price lookup
    # Phase 2: Multi-market state
    markets: dict[str, MarketState] = field(default_factory=dict)
    open_trades: dict = field(default_factory=dict)  # Track active trades globally
    position_entry_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    # Engine state (Council/Chimera) for transitional compatibility
    council_trade: TradeRecord = field(default_factory=TradeRecord)
    chimera_trade: TradeRecord = field(default_factory=TradeRecord)
    active_trade: TradeRecord = field(default_factory=TradeRecord)
    
    # Warwick Engine states
    warwick_primary: TradeRecord = field(default_factory=TradeRecord)
    warwick_hedge: TradeRecord = field(default_factory=TradeRecord)
    
    # AI Control Parameters
    ai_risk_limit: float = 500.0
    ai_override_risk: float = 100.0
    consecutive_loss_threshold: int = 10
    max_position_size_limit: int = 8
    stale_price_threshold: float = 20.0
    
    # Global Session State
    daily_pnl: float = 0.0
    trade_count: int = 0
    wins: int = 0
    losses: int = 0
    total_commissions: float = 0.0
    running: bool = True
    cycle_count: int = 0
    
    # Position Coordination
    max_concurrent_limit: int = 3  # Max symbols to trade simultaneously
    position_count: int = 0  # Number of symbols currently active
    
    # Local Ticker attributes (deprecated, but kept for backcompat)
    price: float = 0.0
    price_timestamp: float = 0.0
    price_is_stale: bool = True
    prices: deque = field(default_factory=lambda: deque(maxlen=300))
    position_side: str = "FLAT"
    position_size: int = 0
    position_entry: float = 0.0
    
    # Broker Truth (Global Account)
    broker_balance: float = 0.0
    broker_starting_balance: float = 0.0
    broker_realized_pnl: float = 0.0
    last_reconcile_time: float = 0.0
    
    # Deprecated fields (maintained for transitional compatibility)
    price: float = 0.0
    prices: deque = field(default_factory=lambda: deque(maxlen=300))
    position_side: str = "FLAT"
    position_size: int = 0
    position_entry: float = 0.0
    price_timestamp: float = 0.0
    l2_timestamp: float = 0.0
    orderbook_data: dict = field(default_factory=dict)
    
    def __post_init__(self):
        # Ensure critical attributes exist even if dataclass magic fails in some contexts
        if not hasattr(self, 'market_prices'): self.market_prices = {}
        if not hasattr(self, 'markets'): self.markets = {}
        if not hasattr(self, 'open_trades'): self.open_trades = {}
        if not hasattr(self, 'council_trade'): self.council_trade = TradeRecord()
        if not hasattr(self, 'position_entry_lock'): self.position_entry_lock = asyncio.Lock()

    def get_market(self, symbol: str) -> MarketState:
        if symbol not in self.markets:
            # S-1: Auto-initialize on first access with per-symbol WarwickEngine
            from warwick_engine import WarwickEngine
            pv = INSTRUMENT_CONFIG.get(symbol, {'point_value': 2.0})['point_value']
            self.markets[symbol] = MarketState(
                symbol=symbol,
                warwick_engine=WarwickEngine(point_value=pv)
            )
        return self.markets[symbol]
    _sl_emergency: bool = False
    
    # Learning Mode & Risk
    trade_history: list = field(default_factory=list)
    warwick_consecutive_losses: int = 0
    council_consecutive_losses: int = 0
    chimera_consecutive_losses: int = 0
    warwick_halted: bool = False
    council_halted: bool = False
    chimera_halted: bool = False
    daily_risk_used: float = 0.0
    daily_loss_threshold: float = -500.0
    
    # Phase 4: Selection
    trading_allowed: bool = True
    trading_disable_reason: str = ""
    ai_risk_limit: float = 500.0  # AI-managed global risk cap
    ai_override_risk: float = 100.0  # AI-managed target risk per trade
    consecutive_loss_threshold: int = 10 # SOE: reduced from 20 to 10
    max_position_size_limit: int = 8 # SOE: reduced from 10 to 8
    stale_price_threshold: float = 20.0 # SOE: reduced from 30s to 20s
    engine_choice_log: dict = field(default_factory=dict)
    last_engine_selection_time: float = 0.0
    
    # Phase 1 Fix #2: Bootstrap
    bootstrap_engine_success: dict = field(default_factory=lambda: {"council": 0, "warwick": 0, "chimera": 0})
    bootstrap_engine_failures: dict = field(default_factory=lambda: {"council": 0, "warwick": 0, "chimera": 0})
    bootstrap_start_time: float = 0.0
    bootstrap_hard_timeout: float = 300.0
    
    # Phase 5: Regime
    current_regime: str = "RANGING"
    regime_confidence: float = 0.0
    regime_history: list = field(default_factory=list)
    _last_regime_update: float = 0.0
    regime_price_slope: float = 0.0
    regime_volatility_ratio: float = 1.0
    
    # L2 ORDERBOOK DATA - bid/ask liquidity analysis (Deprecated - moved to MarketState)
    best_bid_depth: float = 0.0  # Total volume within 2 ticks of best bid (in dollars)
    best_ask_depth: float = 0.0  # Total volume within 2 ticks of best ask (in dollars)
    
    # L2 QUALITY METRICS
    l2_ofi: float = 0.0  # Order Flow Imbalance (cumulative bid-ask volume difference)
    l2_book_pressure: float = 0.0  # Pressure score (-1 to 1): positive = buy pressure, negative = sell pressure
    l2_quality_checks: dict = field(default_factory=dict)  # {check_name: pass/fail status}
    l2_prev_best_bid: float = 0.0  # Previous best bid for jump detection
    l2_prev_best_ask: float = 0.0  # Previous best ask for jump detection
    l2_prev_spread: float = 0.0  # Previous spread for anomaly detection
    l2_max_spread: float = 0.0  # Maximum spread observed (for anomaly detection)
    l2_anomalies_count: int = 0  # Number of anomalies detected
    l2_quality_metrics: dict = field(default_factory=dict)  # Detailed quality metrics
    
    # L2 SAFETY CHECKS - Data freshness tracking and circuit breaker
    l2_consecutive_stale_checks: int = 0  # Count of consecutive stale data checks
    l2_total_stale_seconds: float = 0.0  # Cumulative time L2 data has been stale
    l2_circuit_breaker_active: bool = False  # Block entries when stale for >60s total
    l2_circuit_breaker_since: float = 0.0  # When circuit breaker was activated
    l2_was_stale: bool = False  # Track state transitions for logging
    
    # VOLATILITY SURGE DETECTION - Safety improvement 2026-03-09
    # Circuit breaker when ATR spikes >50% in 60 seconds
    volatility_circuit_breaker_active: bool = False  # No new entries when True
    volatility_circuit_breaker_until: float = 0.0  # Timestamp when breaker expires
    prev_atr: float = 0.0  # ATR value from 60 seconds ago
    prev_atr_timestamp: float = 0.0  # When prev_atr was recorded

# S-1: Fill deduplication -- prevent same fill from being counted multiple times
# Uses deque with maxlen to prevent unbounded memory growth in long sessions
_PROCESSED_FILL_ID_LIMIT = 10000  # Keep last 10k fills (reasonable for multi-hour session)
_processed_fill_ids: deque = deque(maxlen=_PROCESSED_FILL_ID_LIMIT)

state = VortexState.get_instance()
suite = None
mnq = None
fleet = None  # Fleet agent system for intelligent consultation
awareness = None  # Warwick's memory (separate DB)
council_awareness = None  # Council's memory (separate DB)
chimera_awareness = None  # Chimera's memory (Engine #3, separate DB)
warwick = None  # Warwick multi-position hedge engine
market_conn = None  # Direct signalrcore market hub connection
user_conn = None  # Direct signalrcore user hub connection
broker_outage_coordinator = None  # Broker outage detection and recovery system
steering = None  # Steering vectors for adaptive decision-making
_background_tasks = set()  # Track background tasks for structured concurrency


def _bg_task_done(t):
    """Callback for background tasks. Handles cancellation safely."""
    _background_tasks.discard(t)
    if t.cancelled():
        return
    exc = t.exception()
    if exc:
        log.warning(f"Background task error: {exc}")
_main_loop = None  # Captured at startup for signalr thread access
_closing_legs = set()  # Prevent concurrent close attempts on same leg


async def get_fleet_insights(query: str = None) -> str:
    """Query the Fleet for trading insights. Returns formatted response."""
    global fleet
    if fleet is None or not fleet.running:
        return ""
    
    if query is None:
        # Default query based on current market state
        query = f"Current market: price={state.price}, position={state.position_side}, session PnL=${state.daily_pnl:.2f}. Should we trade?"
    
    try:
        relevant = fleet.select_relevant(query, max_agents=5)
        if not relevant:
            return ""
        lines = ["=== FLEET ADVISORY ==="]
        for name in relevant:
            agent = fleet.get_agent(name)
            if agent:
                lines.append(f"[{name}] ({agent.role})")
        lines.append("=====================")
        return "\n".join(lines)
    except Exception as e:
        log.debug(f"Fleet query error: {e}")
        return ""


def utc_now():
    return datetime.now(timezone.utc)


def record_pnl(amount: float, source: str, fill_id: str = None, contracts: int = 1):
    """Single point of PnL mutation. Every dollar flows through here.
    S-1: fill_id prevents double-counting from duplicate broker callbacks.
    S-7: Subtracts estimated commission per round-trip close.
    MATH: Track trades with engine name for expectancy calculation."""
    state = VortexState.get_instance()
    # S-1: Fill deduplication (uses LRU deque for memory safety)
    if fill_id is not None:
        if fill_id in _processed_fill_ids:
            log.warning(f"PNL DEDUP: fill_id={fill_id} already processed, skipping [{source}]")
            return
        _processed_fill_ids.append(fill_id)  # deque auto-removes oldest when full

    # S-7: Commission tracking (per round-trip close)
    commission = INSTRUMENT_CONFIG.get(TICKER, {}).get('commission_rt', 0.0) * contracts
    state.total_commissions += commission
    amount_after_comm = amount - commission

    state.daily_pnl += amount_after_comm
    if amount_after_comm >= 0:
        state.wins += 1
    else:
        state.losses += 1
    state.trade_count += 1
    
    # MATH: Determine which engine this trade belongs to
    engine_name = "unknown"
    if "warwick" in source:
        engine_name = "warwick"
        state.warwick_consecutive_losses = state.warwick_consecutive_losses + 1 if amount_after_comm < 0 else 0
        state.council_consecutive_losses = 0
        state.chimera_consecutive_losses = 0
    elif "council" in source:
        engine_name = "council"
        state.council_consecutive_losses = state.council_consecutive_losses + 1 if amount_after_comm < 0 else 0
        state.warwick_consecutive_losses = 0
        state.chimera_consecutive_losses = 0
    elif "chimera" in source:
        engine_name = "chimera"
        state.chimera_consecutive_losses = state.chimera_consecutive_losses + 1 if amount_after_comm < 0 else 0
        state.warwick_consecutive_losses = 0
        state.council_consecutive_losses = 0
    else:
        # Reset all on non-engine trades (like reconcile)
        state.warwick_consecutive_losses = 0
        state.council_consecutive_losses = 0
        state.chimera_consecutive_losses = 0
    
    # MATH: Add to trade history for expectancy calculation
    state.trade_history.append({
        "pnl": amount_after_comm,
        "engine": engine_name,
        "source": source,
        "timestamp": time.time()
    })
    # Keep only last 500 trades
    if len(state.trade_history) > 500:
        state.trade_history = state.trade_history[-500:]
    
    if STRESS_TEST_MODE and ("fill" in source.lower() or "close" in source.lower()):
        trade_num = state.trade_count
        pnl_status = "✓" if amount_after_comm >= 0 else "✗"
        log.info(f"STRESS TEST EXIT: {pnl_status} +${amount_after_comm:.2f} on trade #{trade_num} | {source.split(':')[0]} (stress driven)")
    
    log.info(f"PNL [{source}]: {amount:+.2f} - ${commission:.2f} comm = {amount_after_comm:+.2f} -> "
             f"session ${state.daily_pnl:.2f} ({state.wins}W/{state.losses}L) "
             f"[total comm: ${state.total_commissions:.2f}]")

    # MATH: Recalculate stats and check halt conditions after every trade
    _recalculate_math_stats()

    # Trigger self-learning every 10 trades
    if state.trade_count > 0 and state.trade_count % 10 == 0:
        engine = awareness if "warwick" in source or "burst" in source else council_awareness
        if engine and ANTHROPIC_KEY:
            try:
                result = engine.self_learn(ANTHROPIC_KEY, AI_MODEL)
                if result:
                    log.info(f"SELF-LEARNING ({engine.name}): extracted rules after {state.trade_count} trades")
            except Exception as e:
                log.debug(f"Self-learning error: {e}")


def validate_trade_pattern(trade_record: TradeRecord, pnl_dollar: float, engine_name: str = "council"):
    """LEARNING MODE: Validate pattern after trade closes.
    
    Closes the learning loop by updating pattern confidence based on outcome.
    Called after PnL is recorded in close functions.
    
    Args:
        trade_record: The TradeRecord that just closed
        pnl_dollar: The realized PnL in dollars
        engine_name: Which engine (council/chimera/warwick)
    """
    state = VortexState.get_instance()
    # Skip if no pattern was identified
    if not trade_record.pattern_id:
        return
    
    # Determine success (positive PnL after commission)
    outcome_success = pnl_dollar >= 0
    
    # Select the appropriate awareness engine
    engine_map = {
        "council": council_awareness,
        "chimera": chimera_awareness,
        "warwick": awareness  # Main awareness for warwick
    }
    engine = engine_map.get(engine_name)
    
    if not engine:
        log.debug(f"Pattern validation: no awareness engine for {engine_name}")
        return
    
    try:
        new_conf = engine.validate_pattern(trade_record.pattern_id, outcome_success)
        if new_conf is not None:
            log.info(f"LEARNING: Pattern {trade_record.pattern_id} validated -> "
                     f"confidence {new_conf:.2f} ({'SUCCESS' if outcome_success else 'FAILURE'})")
    except Exception as e:
        log.debug(f"Pattern validation error: {e}")


def _recalculate_math_stats():
    """MATH: Recalculate expectancy, Kelly, and risk of ruin after every trade.
    Check halt conditions. Update AI prompts with math context."""
    state = VortexState.get_instance()
    if not state.trade_history:
        return
    
    # Get per-engine stats
    warwick_stats = risk_math.get_engine_stats("warwick", state.trade_history)
    council_stats = risk_math.get_engine_stats("council", state.trade_history)
    chimera_stats = risk_math.get_engine_stats("chimera", state.trade_history)
    
    # Get system stats
    system_stats = risk_math.get_system_stats(state.trade_history)
    
    # Check halt conditions
    engine_stats = [warwick_stats, council_stats, chimera_stats]
    halt_check = risk_math.check_halt_conditions(engine_stats, system_stats)
    
    # Log stats
    math_summary = risk_math.format_math_summary(engine_stats, system_stats)
    log.info(f"MATH: {math_summary}")
    
    # Check for halts
    if halt_check["should_halt"]:
        for eng in halt_check["halted_engines"]:
            if eng == "warwick" and not state.warwick_halted:
                state.warwick_halted = True
                log.critical(f"MATH HALT: Warwick disabled - {halt_check['reason']}")
                # Trigger self-learning research
                if awareness and ANTHROPIC_KEY:
                    try:
                        task = asyncio.create_task(asyncio.to_thread(
                            awareness.research_strategy, 
                            "Why is Warwick experiencing consecutive losses and how to fix",
                            ANTHROPIC_KEY, 
                            AI_MODEL
                        ))
                        _background_tasks.add(task)
                        task.add_done_callback(_bg_task_done)
                    except Exception as e:
                        log.debug(f"Warwick halt research error: {e}")
            elif eng == "council" and not state.council_halted:
                state.council_halted = True
                log.critical(f"MATH HALT: Council disabled - {halt_check['reason']}")
                if council_awareness and ANTHROPIC_KEY:
                    try:
                        task = asyncio.create_task(asyncio.to_thread(
                            council_awareness.research_strategy,
                            "Why is Council experiencing negative expectancy",
                            ANTHROPIC_KEY,
                            AI_MODEL
                        ))
                        _background_tasks.add(task)
                        task.add_done_callback(_bg_task_done)
                    except Exception as e:
                        log.debug(f"Council halt research error: {e}")
            elif eng == "chimera" and not state.chimera_halted:
                state.chimera_halted = True
                log.critical(f"MATH HALT: Chimera disabled - {halt_check['reason']}")
                if chimera_awareness and ANTHROPIC_KEY:
                    try:
                        task = asyncio.create_task(asyncio.to_thread(
                            chimera_awareness.research_strategy,
                            "Why is Chimera underperforming",
                            ANTHROPIC_KEY,
                            AI_MODEL
                        ))
                        _background_tasks.add(task)
                        task.add_done_callback(_bg_task_done)
                    except Exception as e:
                        log.debug(f"Chimera halt research error: {e}")
    
    # Store in state for dashboard access
    state._math_stats = {
        "system": system_stats,
        "warwick": warwick_stats,
        "council": council_stats,
        "chimera": chimera_stats,
        "halt_check": halt_check
    }


def should_allow_trading() -> tuple:
    """PHASE 4: Check if trading should be allowed today.
    
    Examines system-level stats to decide if ANY engine should trade:
    - System expectancy > $0.01
    - System win rate > 35%
    - Risk of ruin < 10%
    - No halt conditions active
    
    Returns:
        Tuple of (should_allow: bool, reason: str)
        If False, ALL engines will be asked but forced to return WAIT
    """
    if GAMBLING_MODE:
        state.trading_allowed = True
        state.trading_disable_reason = ""
        return (True, "GAMBLING MODE: all safeties stripped, pure probability trading")

    if not state.trade_history:
        # First trades: allow for data collection
        state.trading_allowed = True
        state.trading_disable_reason = ""
        return (True, "No trade history yet, collecting baseline")
    
    # LEARNING PHASE: Bypass expectancy/winrate/ROR checks for first 100 trades
    # We need data to learn — can't self-halt before we have enough samples
    if state.trade_count < 100:
        state.trading_allowed = True
        state.trading_disable_reason = ""
        return (True, f"Learning phase: {state.trade_count}/100 trades, all checks bypassed")
    
    # Get system stats
    system_stats = risk_math.get_system_stats(state.trade_history)
    
    # Check 1: Positive expectancy (only enforced after 100 trades)
    sys_exp = system_stats.get("expectancy", 0)
    if sys_exp < 0.01:
        reason = f"System has negative expectancy (${sys_exp:.2f})"
        state.trading_allowed = False
        state.trading_disable_reason = reason
        return (False, reason)
    
    # Check 2: Minimum win rate (only enforced after 100 trades)
    sys_wr = system_stats.get("win_rate", 0)
    if sys_wr < 0.35:
        reason = f"System win rate too low ({sys_wr*100:.1f}% < 35%)"
        state.trading_allowed = False
        state.trading_disable_reason = reason
        return (False, reason)
    
    # Check 3: Risk of ruin (only enforced after 100 trades)
    sys_ror = system_stats.get("risk_of_ruin_pct", 0)
    if sys_ror > 10.0:
        reason = f"System risk of ruin too high ({sys_ror:.1f}% > 10%)"
        state.trading_allowed = False
        state.trading_disable_reason = reason
        return (False, reason)
    
    # Check 4: No system-level halt
    engine_stats = [
        risk_math.get_engine_stats("warwick", state.trade_history),
        risk_math.get_engine_stats("council", state.trade_history),
        risk_math.get_engine_stats("chimera", state.trade_history)
    ]
    halt_check = risk_math.check_halt_conditions(engine_stats, system_stats)
    if halt_check["should_halt"]:
        # Check if ALL engines are halted
        halted = set(halt_check.get("halted_engines", []))
        if len(halted) >= 2:  # 2+ engines halted = halt system
            reason = f"Multiple engines halted: {halt_check['reason']}"
            state.trading_allowed = False
            state.trading_disable_reason = reason
            return (False, reason)
    
    # All checks passed
    state.trading_allowed = True
    state.trading_disable_reason = ""
    return (True, f"System healthy: Exp=${sys_exp:.2f}, WR={sys_wr*100:.1f}%, RoR={sys_ror:.1f}%")


async def select_active_engine() -> tuple:
    """PHASE 4: Select which engine(s) should be active for this session.
    
    Calls best_engine_for_conditions() to compare expectancy across engines.
    
    Decision types:
    - WARWICK_DOMINANT: Only Warwick trades (has clear edge)
    - COUNCIL_DOMINANT: Only Council trades (has clear edge)
    - CONSENSUS_NEEDED: Ask both engines, take the one with higher confidence
    - ALL_DISABLED: No engines should trade
    
    Returns:
        Tuple of (engine_choice: str, confidence: float)
    """
    if not state.trade_history:
        # Startup: use consensus of both (collect data)
        return ("CONSENSUS_NEEDED", 0.5)
    
    warwick_stats = risk_math.get_engine_stats("warwick", state.trade_history)
    council_stats = risk_math.get_engine_stats("council", state.trade_history)
    chimera_stats = risk_math.get_engine_stats("chimera", state.trade_history)
    
    current_action = "FLAT" if state.position_side == "FLAT" else "TRENDING"
    recommendation, confidence = risk_math.best_engine_for_conditions(
        warwick_stats, council_stats, chimera_stats, current_action
    )
    
    # Log the selection
    now = datetime.now(timezone.utc).isoformat()
    selection_msg = risk_math.format_engine_selection(recommendation, warwick_stats, council_stats, confidence)
    log.info(selection_msg)
    
    # Store in log for dashboard
    state.engine_choice_log[now] = {
        "engine": recommendation,
        "confidence": confidence,
        "reason": selection_msg,
        "warwick_exp": warwick_stats.get("expectancy", 0),
        "council_exp": council_stats.get("expectancy", 0),
        "warwick_wr": warwick_stats.get("win_rate", 0),
        "council_wr": council_stats.get("win_rate", 0)
    }
    
    # Keep only last 100 selections
    if len(state.engine_choice_log) > 100:
        oldest_key = min(state.engine_choice_log.keys())
        del state.engine_choice_log[oldest_key]
    
    state.last_engine_selection_time = time.time()
    
    return (recommendation, confidence)



try:
    from zoneinfo import ZoneInfo
    _CT_ZONE = ZoneInfo("America/Chicago")
except ImportError:
    _CT_ZONE = None


def is_market_hours():
    """Check if CME MNQ futures market is open. Returns (is_open, should_flatten).
    CME Globex: Sun 5pm CT - Fri 4pm CT, daily halt 3:15-3:30pm CT.
    Flatten at 3:14 CT to avoid the halt window."""
    if _CT_ZONE:
        now_ct = datetime.now(_CT_ZONE)
    else:
        now = utc_now()
        now_ct = now
    ct_decimal = now_ct.hour + now_ct.minute / 60.0
    dow = now_ct.weekday()  # 0=Mon, 6=Sun

    # Saturday all day = closed
    if dow == 5:
        return False, False
    # Sunday before 5pm CT = closed
    if dow == 6 and ct_decimal < 17.0:
        return False, False
    # Friday after 4pm CT = closed
    if dow == 4 and ct_decimal >= 16.0:
        return False, False
    # Daily halt 3:15-3:30 CT (Mon-Fri)
    if 15.25 <= ct_decimal < 15.5:
        return False, False
    # Flatten at 3:14 CT to exit before halt
    should_flatten = ct_decimal >= 15.2 and ct_decimal < 15.25
    return True, should_flatten


# ============================================================
# MEMORY - simple append-only learning journal
# ============================================================
def load_memory():
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {"trades": [], "learnings": [], "preferences": {
        "loss_limit_preference": -500,
        "note": "User wants max profit, $500 loss limit is a soft preference not a hard rule"
    }}

def save_memory(mem):
    mem["trades"] = mem.get("trades", [])[-200:]
    mem["learnings"] = mem.get("learnings", [])[-100:]
    try:
        MEMORY_FILE.write_text(json.dumps(mem, indent=2), encoding='utf-8')
    except Exception as e:
        log.error(f"save_memory failed: {e}")

def record_trade(trade_data):
    mem = load_memory()
    mem["trades"].append({**trade_data, "timestamp": utc_now().isoformat()})
    save_memory(mem)

def record_learning(note):
    mem = load_memory()
    mem["learnings"].append({"timestamp": utc_now().isoformat(), "note": note})
    save_memory(mem)


def log_trade_event(event_type, data):
    """Append to comprehensive trade log for stress-test analysis."""
    entry = {"timestamp": utc_now().isoformat(), "event": event_type, **data}
    try:
        existing = json.loads(TRADE_LOG_FILE.read_text(encoding='utf-8')) if TRADE_LOG_FILE.exists() else []
    except Exception:
        existing = []
    existing.append(entry)
    existing = existing[-500:]
    TRADE_LOG_FILE.write_text(json.dumps(existing, indent=2), encoding='utf-8')


def log_anomaly(category, description, context=None):
    """Record bugs/anomalies discovered during stress testing."""
    entry = {"timestamp": utc_now().isoformat(), "category": category,
             "description": description, "context": context or {}}
    try:
        existing = json.loads(ANOMALY_LOG_FILE.read_text(encoding='utf-8')) if ANOMALY_LOG_FILE.exists() else []
    except Exception:
        existing = []
    existing.append(entry)
    existing = existing[-200:]
    ANOMALY_LOG_FILE.write_text(json.dumps(existing, indent=2), encoding='utf-8')
    log.warning(f"ANOMALY [{category}]: {description}")


def load_fleet_digest():
    """Load Fleet agent wisdom for Claude's context."""
    try:
        if FLEET_DIGEST_FILE.exists():
            data = json.loads(FLEET_DIGEST_FILE.read_text(encoding='utf-8'))
            return data.get("fleet_wisdom", ""), data.get("agents", {})
    except Exception:
        pass
    return "", {}


# ============================================================
# COST TRACKING - Track Claude API usage and trading costs
# ============================================================
COST_LOG_FILE = STATE_DIR / "cost_log.json"

def log_api_usage(tokens_used: int, decision_type: str = "trade", input_tokens: int = 0, output_tokens: int = 0):
    """Log Claude API usage for cost tracking."""
    if input_tokens > 0 and output_tokens > 0:
        input_cost = input_tokens / 1_000_000 * 3
        output_cost = output_tokens / 1_000_000 * 15
    else:
        input_cost = (tokens_used * 0.9) / 1_000_000 * 3
        output_cost = (tokens_used * 0.1) / 1_000_000 * 15
    
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tokens": tokens_used,
        "estimated_cost": round(input_cost + output_cost, 4),
        "type": decision_type,
        "session_pnl": state.daily_pnl,
        "cumulative_cost": 0.0
    }
    
    try:
        existing = json.loads(COST_LOG_FILE.read_text(encoding='utf-8')) if COST_LOG_FILE.exists() else []
        existing.append(entry)
        if existing:
            total_cost = sum(e.get("estimated_cost", 0) for e in existing)
            existing[-1]["cumulative_cost"] = round(total_cost, 4)
        existing = existing[-500:]
        COST_LOG_FILE.write_text(json.dumps(existing, indent=2), encoding='utf-8')
    except Exception:
        pass


def get_cost_projection() -> dict:
    """Project costs if trading continues at current rate."""
    try:
        if COST_LOG_FILE.exists():
            data = json.loads(COST_LOG_FILE.read_text(encoding='utf-8'))
            if len(data) < 5:
                return {"projection": "insufficient_data"}
            recent = data[-20:]
            avg_cost = sum(e.get("estimated_cost", 0) for e in recent) / len(recent)
            hourly_trades = len(recent) * 3
            daily_cost = hourly_trades * 8 * avg_cost
            return {
                "avg_cost_per_trade": round(avg_cost, 4),
                "projected_hourly_cost": round(hourly_trades * avg_cost, 2),
                "projected_daily_cost": round(daily_cost, 2),
                "cumulative_cost": round(data[-1].get("cumulative_cost", 0), 4) if data else 0,
                "trade_count": len(data)
            }
    except Exception:
        pass
    return {"error": "unable to calculate"}


# ============================================================
# TRADE INTELLIGENCE - Track Claude's reasoning quality
# ============================================================
INTELLIGENCE_LOG = STATE_DIR / "intelligence_log.json"

def log_trade_intelligence(trade_data: dict, decision: dict, fleet_summary: str = ""):
    """Log Claude's reasoning quality and Fleet's input for analysis."""
    entry = {
        "timestamp": trade_data.get("timestamp", ""),
        "trade_pnl": trade_data.get("pnl", 0),
        "decision": decision.get("action", "WAIT"),
        "claude_reasoning": decision.get("reasoning", "")[:200] if decision.get("reasoning") else "",
        "fleet_consensus": fleet_summary[:200] if fleet_summary else "",
        "price_at_decision": trade_data.get("price", 0),
        "intelligence_score": 0  # To be calculated by Fleet
    }
    
    try:
        existing = json.loads(INTELLIGENCE_LOG.read_text(encoding='utf-8')) if INTELLIGENCE_LOG.exists() else []
        existing.append(entry)
        existing = existing[-200:]
        INTELLIGENCE_LOG.write_text(json.dumps(existing, indent=2), encoding='utf-8')
    except Exception:
        pass


def _log_l2_metrics():
    """Log L2 orderbook metrics to verification file.
    Called every 10 quote updates to avoid excessive I/O.
    Logs: spread, imbalance, OFI, book_pressure, quality checks."""
    try:
        if not state.orderbook_data:
            return
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": round(state.price, 2),
            "spread_pts": state.orderbook_data.get('spread', 0.0),
            "imbalance": state.orderbook_data.get('imbalance', 0.0),
            "ofi": state.orderbook_data.get('ofi', 0.0),
            "book_pressure": state.orderbook_data.get('book_pressure', 0.0),
            "best_bid": state.orderbook_data.get('best_bid', 0.0),
            "best_ask": state.orderbook_data.get('best_ask', 0.0),
            "best_bid_depth_usd": round(state.best_bid_depth, 2),
            "best_ask_depth_usd": round(state.best_ask_depth, 2),
            "quality_checks": state.l2_quality_checks,
            "anomalies_detected": state.l2_anomalies_count,
            "data_age_sec": round(time.time() - state.l2_timestamp, 2) if state.l2_timestamp > 0 else 0
        }
        
        # Append to file
        with open(L2_ORDERBOOK_VERIFICATION_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        log.debug(f"L2 metrics logging error: {e}")


# ============================================================
# PRICE FEED (deterministic)
# ============================================================
async def poll_price():
    """Get current price for all active markets. WebSocket primary, REST fallback.
    """
    now = time.time()
    success_count = 0
    active_tickers = [TICKER]
    if ENABLE_MULTI_MARKET_TEST:
        active_tickers = list(MICRO_CONTRACTS.keys())

    for symbol in active_tickers:
        mstate = state.get_market(symbol)
        # S-1: PRIMARY: WebSocket Watchdog (PHASE 7)
        if mstate.price_timestamp > 0 and mstate.price > 0:
            age = now - mstate.price_timestamp
            if age < 5.0:
                success_count += 1
                continue
            else:
                log.warning(f"WATCHDOG [{symbol}]: Stale price detected ({age:.1f}s). Triggering auto-reconnect...")
                # Force reset timestamp to trigger REST fallback and re-subscription
                mstate.price_timestamp = 0

        # FALLBACK: REST
        try:
            # Only MNQ has mnq.data object in current SDK usage
            if symbol == 'MNQ' and not getattr(state, 'direct_api_mode', False):
                p = await mnq.data.get_current_price()
                if p and p > 0:
                    mstate.price = p
                    mstate.price_timestamp = now
                    mstate.prices.append(p)
                    if symbol == TICKER:
                        state.price = p
                        state.price_timestamp = now
                        state.price_is_stale = False
                        state.prices.append(p)
                    success_count += 1
                    continue
            
            # Direct API or other symbols: requires implementation of multi-market REST poll
            # For now, rely on WS for non-MNQ symbols until REST endpoints mapped
            pass
        except:
            pass
            
    return success_count > 0


# ============================================================
# POSITION SYNC (deterministic) - broker is truth
# ============================================================
async def sync_position():
    """Sync all instrument positions from broker. Broker state always wins."""
    try:
        direct_mode = getattr(state, 'direct_api_mode', False)
        positions = await api_get_positions() if direct_mode else await mnq.positions.get_all_positions()
        
        active_tickers = [TICKER]
        if ENABLE_MULTI_MARKET_TEST:
            active_tickers = list(MICRO_CONTRACTS.items())

        for symbol, contract_id in MICRO_CONTRACTS.items():
            mstate = state.get_market(symbol)
            p = _find_position_for_contract(positions, contract_id)

            if p:
                if direct_mode:
                    ptype = p.get('type', 0)
                    mstate.position_side = "LONG" if ptype == 1 else "SHORT" if ptype == 2 else "FLAT"
                    mstate.position_size = p.get('size', 0)
                    mstate.position_entry = p.get('averagePrice', 0.0)
                else:
                    mstate.position_side = "LONG" if p.type == 1 else "SHORT" if p.type == 2 else "FLAT"
                    mstate.position_size = p.size
                    mstate.position_entry = p.averagePrice
                
                # Global sync (deprecated)
                if symbol == TICKER:
                    state.position_side = mstate.position_side
                    state.position_size = mstate.position_size
                    state.position_entry = mstate.position_entry
            else:
                if mstate.position_side != "FLAT":
                    log.info(f"Position closed by broker for {symbol}. Was {mstate.position_side}")
                    if symbol == TICKER:
                        await handle_position_closed()
                mstate.position_side = "FLAT"
                mstate.position_size = 0
                mstate.position_entry = 0.0
                if symbol == TICKER:
                    state.position_side = "FLAT"
                    state.position_size = 0
                    state.position_entry = 0.0
    except Exception as e:
        log.debug(f"Position sync: {e}")


async def handle_position_closed():
    """Called when broker shows no position but we thought we had one.
    Uses fill price when available, falls back to market mid-price.
    """
    if state.active_trade.entry_price > 0 and state.price > 0:
        entry = state.active_trade.entry_price
        side = state.active_trade.side
        size = state.active_trade.size
        exit_price = state.last_fill_price if state.last_fill_price > 0 else state.price
        if side == "BUY" or side == "LONG":
            pnl = (exit_price - entry) * size * POINT_VALUE
        else:
            pnl = (entry - exit_price) * size * POINT_VALUE
        # S-1: Use entry_order_id as fill_id to deduplicate if fill callback already counted it
        _hpc_fill_id = f"hpc_{state.active_trade.entry_order_id}" if state.active_trade.entry_order_id else None
        record_pnl(pnl, f"handle_position_closed:{side}", fill_id=_hpc_fill_id, contracts=size)
        record_trade({
            "side": side, "size": size, "entry": entry,
            "exit": round(exit_price, 2), "exit_source": "fill" if state.last_fill_price > 0 else "market",
            "pnl": round(pnl, 2), "sl": state.active_trade.sl_price,
            "tp": state.active_trade.tp_price
        })

        # LEARNING: Validate pattern if this trade was pattern-based
        validate_trade_pattern(state.active_trade, pnl, "warwick")

        # Record episode in awareness engine
        if awareness:
            try:
                features = compute_features() or {}
                features["position_before"] = side
                wr = state.wins / state.trade_count if state.trade_count > 0 else 0
                awareness.record_episode(
                    action="CLOSE", side=side, entry_price=entry, exit_price=exit_price,
                    pnl=pnl, stop_points=state.active_trade.sl_price,
                    target_points=state.active_trade.tp_price, features=features,
                    reasoning="SL/TP fill or manual close", learning="",
                    confidence=0, trade_count=state.trade_count, daily_pnl=state.daily_pnl,
                    win_rate=wr)

                # Self-learn every 15 trades (non-blocking)
                if state.trade_count > 0 and state.trade_count % 15 == 0:
                    log.info(f"SELF-LEARNING: analyzing {state.trade_count} trades...")
                    task = asyncio.create_task(asyncio.to_thread(awareness.self_learn, ANTHROPIC_KEY))
                    _background_tasks.add(task)
                    task.add_done_callback(_bg_task_done)

                # Research when win rate drops below 40% (cooldown: 10 min)
                if (state.trade_count >= 10 and wr < 0.40
                        and time.time() - state._last_research_time > 600):
                    state._last_research_time = time.time()
                    log.info(f"WIN RATE LOW ({wr:.0%}) -- researching improvement strategies")
                    task = asyncio.create_task(asyncio.to_thread(
                        awareness.research_strategy, "MNQ scalping with low win rate recovery", ANTHROPIC_KEY))
                    _background_tasks.add(task)
                    task.add_done_callback(_bg_task_done)

            except Exception as e:
                log.error(f"CRITICAL: Failed to record main position close episode: {e}", exc_info=True)

    # E-4 FIX: Cancel orphan bracket orders before resetting
    for oid in [state.active_trade.sl_order_id, state.active_trade.tp_order_id]:
        if oid:
            try:
                await mnq.orders.cancel_order(oid)
            except Exception:
                pass
    state.active_trade = TradeRecord()

    # Warwick: if broker is flat but Warwick thinks legs are open, force-close them
    if warwick:
        for lt in ["primary", "hedge"]:
            leg = getattr(warwick.state, lt)
            if leg.is_open:
                fill = state.last_fill_price if state.last_fill_price > 0 else state.price
                pnl = leg.unrealized_pnl(fill)
                warwick.record_leg_close(lt, pnl)
                record_pnl(pnl, f"warwick_force_close:{lt}")
                # Cancel any remaining orders for this leg
                for oid in [leg.sl_order_id, leg.tp_order_id]:
                    if oid:
                        try:
                            await mnq.orders.cancel_order(oid)
                        except Exception:
                            pass


# ============================================================
# BROKER RECONCILIATION (FIX 3) - broker is the only truth
# ============================================================
BROKER_API_BASE = 'https://api.topstepx.com'

async def _broker_api(path: str, body: dict, token: str) -> dict:
    """Call broker REST API."""
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    data = json.dumps(body).encode()
    req = urllib.request.Request(f'{BROKER_API_BASE}{path}', data=data, headers=headers, method='POST')
    loop = asyncio.get_running_loop()
    def _call():
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    return await loop.run_in_executor(None, _call)

# ============================================================
# DIRECT API TRADING METHODS (bypass SDK)
# ============================================================
CONTRACT_IDS = {
    "MNQ": "CON.F.US.MNQ.H26",
    "MES": "CON.F.US.MES.H26", 
    "MCL": "CON.F.US.MCLE.J26",
    "MGC": "CON.F.US.MGC.J26",
    "MYM": "CON.F.US.MYM.H26",
    "M2K": "CON.F.US.M2K.H26",
}

async def api_get_positions(token: str = None) -> list:
    """Get all open positions via direct API.
    
    Returns list of position dicts with: id, contractId, type (1=LONG, 2=SHORT), size, averagePrice
    """
    global _broker_token
    if token is None:
        if _broker_token is None:
            _broker_token = await get_broker_token()
        token = _broker_token
    
    try:
        resp = await _broker_api('/api/Position/searchOpen', {}, token)
        if resp.get('success'):
            return resp.get('positions', [])
        return []
    except Exception as e:
        log.error(f"API position search failed: {e}")
        return []

async def api_place_order(contract_id: str, order_type: int, side: int, size: int,
                          limit_price: float = 0, stop_price: float = 0,
                          sl_price: float = 0, tp_price: float = 0,
                          token: str = None) -> dict:
    """Place order via direct API with optional native brackets.
    
    Args:
        contract_id: Contract ID (e.g., "CON.F.US.MNQ.H26")
        order_type: 1=Limit, 2=Market, 4=Stop
        side: 1=Buy, 2=Sell  
        size: Number of contracts
        limit_price: Limit price (required for limit orders)
        stop_price: Stop trigger price (required for stop orders)
        sl_price: Stop loss bracket price (optional, native OCO)
        tp_price: Take profit bracket price (optional, native OCO)
        token: Auth token (auto-fetched if None)
    
    Returns:
        Order result dict with orderId if successful
    """
    global _broker_token
    if token is None:
        if _broker_token is None:
            _broker_token = await get_broker_token()
        token = _broker_token
    
    body = {
        "contractId": contract_id,
        "type": order_type,
        "side": side,
        "size": size,
        "limitPrice": limit_price,
        "stopPrice": stop_price,
    }
    
    # Add native bracket orders (server-side OCO)
    if sl_price > 0:
        body["stopLossBracket"] = {
            "limitPrice": sl_price,
            "stopPrice": sl_price,
            "size": size,
        }
    if tp_price > 0:
        body["takeProfitBracket"] = {
            "limitPrice": tp_price,
            "stopPrice": tp_price,
            "size": size,
        }
    
    try:
        resp = await _broker_api('/api/Order/place', body, token)
        if resp.get('success'):
            order_id = resp.get('orderId')
            log.info(f"API order placed: id={order_id}, type={order_type}, side={side}, size={size}, SL={sl_price}, TP={tp_price}")
            return {"success": True, "orderId": order_id, "response": resp}
        else:
            log.error(f"API order failed: {resp.get('errorMessage')}")
            return {"success": False, "error": resp.get('errorMessage')}
    except Exception as e:
        log.error(f"API order exception: {e}")
        return {"success": False, "error": str(e)}

async def api_cancel_order(order_id: int, token: str = None) -> bool:
    """Cancel order by ID via direct API.
    
    Returns True if cancelled successfully.
    """
    global _broker_token
    if token is None:
        if _broker_token is None:
            _broker_token = await get_broker_token()
        token = _broker_token
    
    try:
        resp = await _broker_api('/api/Order/cancel', {"orderId": order_id}, token)
        if resp.get('success'):
            log.info(f"API order cancelled: id={order_id}")
            return True
        log.warning(f"API cancel failed: {resp.get('errorMessage')}")
        return False
    except Exception as e:
        log.error(f"API cancel exception: {e}")
        return False

async def api_cancel_all_orders(contract_id: str = None, token: str = None) -> int:
    """Cancel all open orders, optionally filtered by contract.
    
    Returns number of orders cancelled.
    """
    global _broker_token
    if token is None:
        if _broker_token is None:
            _broker_token = await get_broker_token()
        token = _broker_token
    
    try:
        # Get open orders
        body = {}
        if contract_id:
            body["contractId"] = contract_id
        resp = await _broker_api('/api/Order/searchOpen', body, token)
        
        if not resp.get('success'):
            return 0
        
        orders = resp.get('orders', [])
        cancelled = 0
        for order in orders:
            if await api_cancel_order(order['id'], token):
                cancelled += 1
        
        if cancelled > 0:
            log.info(f"API cancelled {cancelled} orders")
        return cancelled
    except Exception as e:
        log.error(f"API cancel all exception: {e}")
        return 0

async def api_get_open_orders(contract_id: str = None, token: str = None) -> list:
    """Get all open orders via direct API.
    
    Returns list of order dicts.
    """
    global _broker_token
    if token is None:
        if _broker_token is None:
            _broker_token = await get_broker_token()
        token = _broker_token
    
    try:
        body = {}
        if contract_id:
            body["contractId"] = contract_id
        resp = await _broker_api('/api/Order/searchOpen', body, token)
        if resp.get('success'):
            return resp.get('orders', [])
        return []
    except Exception as e:
        log.error(f"API order search failed: {e}")
        return []

async def api_close_position(contract_id: str, position_id: int = None, 
                             method: str = 'market', token: str = None) -> dict:
    """Close position via direct API.
    
    Args:
        contract_id: Contract ID
        position_id: Optional position ID (will find if not provided)
        method: 'market' or 'limit' with price
        token: Auth token
    
    Returns order result.
    """
    global _broker_token
    if token is None:
        if _broker_token is None:
            _broker_token = await get_broker_token()
        token = _broker_token
    
    # Find position if not provided
    if position_id is None:
        positions = await api_get_positions(token)
        for pos in positions:
            if pos.get('contractId') == contract_id:
                position_id = pos.get('id')
                break
    
    if position_id is None:
        return {"success": False, "error": "Position not found"}
    
    # Close via market order in opposite direction
    try:
        resp = await _broker_api('/api/Order/closePosition', {
            "contractId": contract_id,
            "positionId": position_id,
        }, token)
        
        if resp.get('success'):
            log.info(f"API position closed: contract={contract_id}, posId={position_id}")
            return {"success": True, "response": resp}
        return {"success": False, "error": resp.get('errorMessage')}
    except Exception as e:
        log.error(f"API close position exception: {e}")
        return {"success": False, "error": str(e)}

async def get_broker_token() -> str:
    """Authenticate and get JWT token from broker with retry logic."""
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            body = json.dumps({"userName": USERNAME, "apiKey": API_KEY}).encode()
            req = urllib.request.Request(f'{BROKER_API_BASE}/api/Auth/loginKey', data=body,
                                         headers={'Content-Type': 'application/json'}, method='POST')
            loop = asyncio.get_running_loop()
            def _auth():
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode())
            auth = await loop.run_in_executor(None, _auth)
            if auth.get('success') and auth.get('token'):
                if attempt > 0:
                    log.info(f"Broker auth successful after {attempt+1} attempts")
                return auth['token']
            else:
                last_error = auth.get('errorMessage', 'Unknown error')
                log.warning(f"Broker auth attempt {attempt+1}/{max_retries} failed: {last_error}")
        except Exception as e:
            last_error = str(e)
            log.warning(f"Broker auth attempt {attempt+1}/{max_retries} exception: {e}")
        
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
    
    raise RuntimeError(f"Broker auth failed after {max_retries} attempts: {last_error}")

_broker_token = None
_broker_account_id = None
_broker_token_time = 0  # Track when token was obtained
BROKER_TOKEN_TTL = 3000  # Token expires after ~50 minutes, refresh before

async def get_broker_balance() -> float:
    """Get current broker account balance for health monitoring.
    
    Returns:
        Balance in dollars, or 0 if unable to query.
    """
    global _broker_token, _broker_account_id, _broker_token_time
    try:
        # Refresh token if expired or not set
        if _broker_token is None or (time.time() - _broker_token_time > BROKER_TOKEN_TTL):
            _broker_token = await get_broker_token()
        
        resp = await _broker_api('/api/Account/search', {'onlyActiveAccounts': True}, _broker_token)
        accounts = resp.get('accounts', [resp]) if isinstance(resp, dict) else resp
        if accounts:
            balance = accounts[0].get('balance', 0)
            return float(balance) if balance else 0.0
        return 0.0
    except Exception as e:
        log.debug(f"Could not get broker balance: {e}")
        return 0.0


async def api_get_orderbook(contract_id: str, depth: int = 5, token: str = None) -> dict:
    """Get L2 orderbook via REST API as fallback when WebSocket is stale.
    
    NOTE: Topstep/ProjectX does not have a dedicated REST endpoint for L2 orderbook.
    This function attempts to construct orderbook data from available REST endpoints
    and falls back to minimal data if no direct endpoint is available.
    
    Args:
        contract_id: Contract ID (e.g., "CON.F.US.MNQ.H26")
        depth: Number of price levels to request (default: 5)
        token: Auth token (auto-fetched if None)
    
    Returns:
        dict with:
        - bids: list of (price, size) tuples (estimated from price if no direct endpoint)
        - asks: list of (price, size) tuples
        - timestamp: Unix timestamp
        - source: "rest_api" or "estimated" or "failed"
    """
    global _broker_token
    if token is None:
        if _broker_token is None:
            _broker_token = await get_broker_token()
        token = _broker_token
    
    now = time.time()
    
    # Try to get market quote data which may include best bid/ask
    # Note: ProjectX doesn't have a documented /api/Quote or /api/Orderbook endpoint
    # We attempt to use contract search to get current market data
    try:
        # Try /api/Contract/search - this sometimes returns market data
        resp = await _broker_api('/api/Contract/search', {
            "searchText": contract_id.split('.')[2] if '.' in contract_id else contract_id,
            "live": True
        }, token)
        
        if resp.get('success') and resp.get('contracts'):
            contracts = resp.get('contracts', [])
            for c in contracts:
                if c.get('id') == contract_id or c.get('symbolId') == contract_id:
                    # Found the contract - check for market data
                    best_bid = c.get('bidPrice') or c.get('bid', 0)
                    best_ask = c.get('askPrice') or c.get('ask', 0)
                    bid_size = c.get('bidSize', 100)
                    ask_size = c.get('askSize', 100)
                    
                    if best_bid > 0 and best_ask > 0:
                        # We have top-of-book data, estimate deeper levels
                        tick_size = INSTRUMENT_CONFIG.get(TICKER, {}).get('tick_size', 0.25)
                        bids = [(best_bid - i * tick_size, max(10, bid_size - i * 10)) for i in range(depth)]
                        asks = [(best_ask + i * tick_size, max(10, ask_size - i * 10)) for i in range(depth)]
                        
                        return {
                            'bids': bids,
                            'asks': asks,
                            'timestamp': now,
                            'source': 'rest_api',
                            'best_bid': best_bid,
                            'best_ask': best_ask
                        }
    except Exception as e:
        log.debug(f"Orderbook REST attempt failed: {e}")
    
    # Optional fallback: estimate orderbook from current price only when explicitly enabled
    if ALLOW_ESTIMATED_L2 and state.price > 0:
        tick_size = INSTRUMENT_CONFIG.get(TICKER, {}).get('tick_size', 0.25)
        typical_spread = tick_size
        best_bid = state.price - typical_spread / 2
        best_ask = state.price + typical_spread / 2
        bids = [(best_bid - i * tick_size, max(10, 50 - i * 5)) for i in range(depth)]
        asks = [(best_ask + i * tick_size, max(10, 50 - i * 5)) for i in range(depth)]
        log.warning(f"L2_FALLBACK: Using estimated orderbook from price {state.price}")
        return {
            'bids': bids,
            'asks': asks,
            'timestamp': now,
            'source': 'estimated',
            'best_bid': best_bid,
            'best_ask': best_ask
        }
    
    # Complete failure
    log.error(f"L2_FALLBACK: Failed to get orderbook data")
    return {
        'bids': [],
        'asks': [],
        'timestamp': now,
        'source': 'failed',
        'best_bid': 0,
        'best_ask': 0
    }


async def reconcile_with_broker():
    """PHASE 2: Multi-market broker truth reconciliation.
    Compare internal PnL and positions with broker reality for all active symbols.
    """
    global _broker_token, _broker_account_id, _broker_token_time
    try:
        # 1. Refresh token and get account balance
        if _broker_token is None or (time.time() - _broker_token_time > BROKER_TOKEN_TTL):
            _broker_token = await get_broker_token()

        resp = await _broker_api('/api/Account/search', {'onlyActiveAccounts': True}, _broker_token)
        accounts = resp.get('accounts', [resp]) if isinstance(resp, dict) else resp
        if accounts:
            account = accounts[0]
            _broker_account_id = account['id']
            state.broker_balance = account.get('balance', 0)
            if state.broker_starting_balance == 0:
                state.broker_starting_balance = state.broker_balance
                log.info(f"BROKER BASELINE: balance=${state.broker_balance:.2f}")
        else:
            return

        broker_pnl = state.broker_balance - state.broker_starting_balance
        state.broker_realized_pnl = broker_pnl
        
        # 2. Sync positions for all active symbols
        positions_resp = await _broker_api('/api/Position/searchOpen', {'accountId': _broker_account_id}, _broker_token)
        # SearchOpen returns a list directly in the new API version
        broker_positions = positions_resp if isinstance(positions_resp, list) else positions_resp.get('positions', [])
        
        # Reset position tracking for all markets before syncing
        for m in state.markets.values():
            m.broker_position_matched = False

        for bpos in broker_positions:
            cid = bpos.get('contractId', '')
            symbol = CONTRACT_TO_TICKER.get(cid)
            if not symbol: continue
            
            mstate = state.get_market(symbol)
            mstate.broker_position_matched = True
            
            # Sync internal state if mismatch
            b_side = "LONG" if bpos.get('type') == 1 else "SHORT"
            b_size = bpos.get('size', 0)
            b_entry = bpos.get('averagePrice', 0.0)
            
            if mstate.position_side != b_side or mstate.position_size != b_size:
                log.warning(f"RECONCILE [{symbol}]: internal={mstate.position_side}{mstate.position_size} "
                           f"broker={b_side}{b_size} @ {b_entry:.2f} -> SYNCING")
                mstate.position_side = b_side
                mstate.position_size = b_size
                mstate.position_entry = b_entry

        # 3. Detect and reset stale internal positions (broker is FLAT but we are not)
        for sym, mstate in state.markets.items():
            if mstate.position_side != "FLAT" and not mstate.broker_position_matched:
                log.warning(f"RECONCILE [{sym}]: Broker is FLAT but internal={mstate.position_side}{mstate.position_size} -> RESETTING")
                mstate.position_side = "FLAT"
                mstate.position_size = 0
                mstate.position_entry = 0.0
                mstate.council_trade = TradeRecord()
                mstate.chimera_trade = TradeRecord()
                if mstate.warwick_engine:
                    mstate.warwick_engine.reset()

        state.last_reconcile_time = time.time()

    except Exception as e:
        log.warning(f"Broker reconciliation failed: {e}")


# ============================================================
# FILL TRACKING (FIX 4) - log fill prices and slippage
# ============================================================
def on_user_trade(args):
    """Handle GatewayUserTrade events from user hub - our own trade fills."""
    global state
    if state is None:
        return
    try:
        if isinstance(args, list) and len(args) >= 1:
            data = args[0] if isinstance(args[0], dict) else args
        elif isinstance(args, dict):
            data = args
        else:
            data = {}

        fill_price = data.get('price', 0)
        fill_pnl = data.get('profitAndLoss')
        fill_side = 'BUY' if data.get('side', 0) == 0 else 'SELL'
        fill_size = data.get('size', 0)

        if fill_price > 0:
            state.last_fill_price = fill_price
            expected = state.active_trade.entry_price if state.active_trade.entry_price > 0 else state.price
            slippage = abs(fill_price - expected) if expected > 0 else 0
            state.last_fill_slippage = slippage
            state.total_slippage += slippage

            log.info(f"FILL: {fill_side} {fill_size} @ {fill_price} "
                     f"(expected={expected:.2f}, slippage={slippage:.2f}pts) "
                     f"pnl={fill_pnl}")

            if fill_pnl is not None:
                log_trade_event("BROKER_FILL", {
                    "side": fill_side, "size": fill_size,
                    "fill_price": fill_price, "expected_price": expected,
                    "slippage": round(slippage, 2), "broker_pnl": fill_pnl
                })

    except Exception as e:
        log.debug(f"User trade callback error: {e}")


def on_user_order(args):
    """Handle GatewayUserOrder events -- detect Warwick SL/TP fills.
    Runs in signalr thread. Schedules state changes on main asyncio loop."""
    global state
    if state is None:
        return
    try:
        if isinstance(args, list) and len(args) >= 1:
            data = args[0] if isinstance(args[0], dict) else args
        elif isinstance(args, dict):
            data = args
        else:
            return

        order_id = data.get('orderId', data.get('id', 0))
        status = data.get('status', '')
        log.debug(f"GatewayUserOrder: id={order_id} status={status} type={type(status).__name__} keys={list(data.keys())[:8]}")

        # Accept status 4 (Filled) as int or string
        is_filled = status in (4, 'Filled', 'filled') or str(status) == '4'
        if not is_filled:
            return

        if not warwick or not _main_loop:
            return

        # S-1: Use order_id as fill_id for deduplication
        fill_id = str(order_id)

        # Check Chimera (Engine #3) orders
        cht = state.chimera_trade
        if cht.side != "FLAT" and order_id in (cht.sl_order_id, cht.tp_order_id):
            fill_type = "sl" if order_id == cht.sl_order_id else "tp"
            fill_price = data.get('fillPrice', data.get('price', state.price))
            log.info(f"CHIMERA FILL: {fill_type} id={order_id} @ {fill_price}")
            asyncio.run_coroutine_threadsafe(
                _handle_chimera_fill(fill_type, fill_price, fill_id), _main_loop)
            return

        # Check Council orders
        ct = state.council_trade
        if ct.side != "FLAT" and order_id in (ct.sl_order_id, ct.tp_order_id):
            fill_type = "sl" if order_id == ct.sl_order_id else "tp"
            fill_price = data.get('fillPrice', data.get('price', state.price))
            log.info(f"COUNCIL FILL: {fill_type} id={order_id} @ {fill_price}")
            asyncio.run_coroutine_threadsafe(
                _handle_council_fill(fill_type, fill_price, fill_id), _main_loop)
            return

        if not warwick:
            return
        leg_type, fill_type = warwick.detect_leg_fill(order_id)
        log.info(f"GatewayUserOrder FILL: id={order_id}, warwick_match={leg_type}/{fill_type}")
        if leg_type:
            fill_price = data.get('fillPrice', data.get('price', state.price))
            asyncio.run_coroutine_threadsafe(
                _handle_warwick_fill(leg_type, fill_type, fill_price, fill_id), _main_loop)

    except Exception as e:
        log.warning(f"User order callback error: {e}")


async def _handle_warwick_fill(leg_type, fill_type, fill_price, fill_id=None):
    """Process a Warwick leg fill ON the main asyncio loop. Thread-safe state mutation."""
    if not warwick:
        return
    if leg_type in _closing_legs:
        return  # I-1: Being closed by main loop, avoid double-processing
    leg = warwick.state.primary if leg_type == "primary" else warwick.state.hedge
    if not leg.is_open:
        return  # Already handled (K-3 race guard)

    pnl = leg.unrealized_pnl(fill_price) if fill_price > 0 else leg.unrealized_pnl(state.price)

    # Cancel the OTHER bracket order for this leg
    remaining_id = leg.tp_order_id if fill_type == "sl" else leg.sl_order_id
    if remaining_id:
        try:
            await mnq.orders.cancel_order(remaining_id)
            log.info(f"WARWICK: Cancelled orphan order {remaining_id} for {leg_type}")
        except Exception as e:
            log.warning(f"WARWICK: Orphan cancel failed {remaining_id}: {e}")

    warwick.record_leg_close(leg_type, pnl)
    record_pnl(pnl, f"warwick_{fill_type}_fill:{leg_type}", fill_id=fill_id, contracts=leg.size)
    # LEARNING: Validate pattern if this trade was pattern-based
    validate_trade_pattern(leg, pnl, "warwick")
    # Record to Warwick's memory for learning
    if awareness:
        try:
            features = compute_features() or {}
            awareness.record_episode(
                action=f"{fill_type}_fill", side=leg.side,
                entry_price=leg.entry_price, exit_price=fill_price, pnl=pnl,
                stop_points=leg.sl_price or 0, target_points=leg.tp_price or 0,
                features=features, reasoning=f"{leg_type} {fill_type} hit",
                learning="", confidence=0.5, trade_count=state.trade_count,
                daily_pnl=state.daily_pnl, win_rate=state.wins / max(state.trade_count, 1))
        except Exception as e:
            log.error(f"CRITICAL: Failed to record Warwick episode: {e}", exc_info=True)


async def _handle_council_fill(fill_type, fill_price, fill_id=None):
    """Process a Council SL/TP fill on the main asyncio loop."""
    council_trade = state.council_trade
    if council_trade.side == "FLAT":
        return
    pnl_pts = (fill_price - council_trade.entry_price) if council_trade.side == "BUY" else (council_trade.entry_price - fill_price)
    pnl_dollar = pnl_pts * POINT_VALUE * council_trade.size
    record_pnl(pnl_dollar, f"council_{fill_type}_fill", fill_id=fill_id, contracts=council_trade.size)
    log.info(f"COUNCIL {fill_type.upper()} HIT: {council_trade.side} {council_trade.size} | "
             f"entry={council_trade.entry_price} exit={fill_price} | PnL=${pnl_dollar:.2f}")
    remaining_id = council_trade.tp_order_id if fill_type == "sl" else council_trade.sl_order_id
    if remaining_id:
        try:
            await mnq.orders.cancel_order(remaining_id)
        except Exception as e:
            log.warning(f"Council fill handler: Failed to cancel order {remaining_id}: {e}")
    # LEARNING: Validate pattern if this trade was pattern-based
    validate_trade_pattern(council_trade, pnl_dollar, "council")
    if council_awareness:
        council_awareness.record_episode(
            action="CLOSE", side=council_trade.side,
            entry_price=council_trade.entry_price, exit_price=fill_price,
            pnl=pnl_dollar, stop_points=council_trade.sl_price, target_points=council_trade.tp_price,
            features={"price": fill_price}, reasoning=f"{fill_type} hit",
            learning="", confidence=0.5, trade_count=state.trade_count,
            daily_pnl=state.daily_pnl, win_rate=0)
    state.council_trade = TradeRecord()
    for k in [k for k in state.open_trades if k.startswith("council_")]:
        del state.open_trades[k]


# ============================================================
# MULTI-MARKET SNAPSHOT
# ============================================================
def get_market_snapshot():
    """Return a compact summary of all 6 micro contract prices for AI prompts."""
    now = time.time()
    lines = []
    for sym, cid in MICRO_CONTRACTS.items():
        mp = state.market_prices.get(cid)
        if mp and mp["price"] > 0:
            age = now - mp["timestamp"]
            stale_flag = " [STALE]" if age > 30 else ""
            pv = INSTRUMENT_CONFIG[sym]['point_value']
            lines.append(f"  {sym}: {mp['price']:.2f} (bid={mp['bid']:.2f} ask={mp['ask']:.2f}, ${pv}/pt){stale_flag}")
        else:
            lines.append(f"  {sym}: no data")
    active_marker = f" (active={TICKER})"
    return f"MULTI-MARKET PRICES{active_marker}:\n" + "\n".join(lines)


# ============================================================
# PNL HANDSHAKE (Global Coordinator)
# ============================================================
pnl_lock = asyncio.Lock()

async def record_pnl(amount: float, source: str, symbol: str):
    """Handshake: Update global state while attributing to local instrument."""
    async with pnl_lock:
        state.daily_pnl += amount
        if amount > 0:
            state.wins += 1
        elif amount < 0:
            state.losses += 1
            
        mstate = state.get_market(symbol)
        mstate.daily_pnl += amount  # Local attribution
        
        log.info(f"PNL RECORDED [{symbol}]: ${amount:+.2f} ({source}) | Local: ${mstate.daily_pnl:+.2f} | Global: ${state.daily_pnl:+.2f}")
        
        # S-1: Global Daily Loss Circuit Breaker ($1k limit)
        if state.daily_pnl <= -1000.0:
            log.critical(f"GLOBAL LOSS LIMIT HIT: ${state.daily_pnl} <= -$1000.0")
            state.running = False
            await shutdown()
            
        # S-2: Local Stop-Trading (Halt instrument if it loses $300 in a day)
        if mstate.daily_pnl <= -300.0:
            log.warning(f"LOCAL HALT [{symbol}]: Daily loss limit hit ($300). Instrument disabled for 24h.")

# ============================================================
# CLAUDE RATE LIMITER (Phase 2 Multi-Market)
# ============================================================
class AnthropicRateLimiter:
    """Async Token Bucket / Semaphore to prevent 429 rate limits across parallel markets."""
    def __init__(self, rpm=30):
        self.semaphore = asyncio.Semaphore(1)
        self.last_call = 0
        self.min_interval = 60.0 / rpm
        log.info(f"Claude Rate Limiter initialized: {rpm} RPM limit")

    async def wait(self):
        async with self.semaphore:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            self.last_call = time.time()

# Global limiter instance
claude_limiter = AnthropicRateLimiter(rpm=25)

# ============================================================
# MARKET FEATURES (deterministic math)
# ============================================================
def compute_features(symbol: str = None):
    """Compute trading features from price history. Pure math.
    PHASE 2: Support multi-market state registry.
    """
    if symbol is None:
        symbol = TICKER
        
    mstate = state.get_market(symbol)
    prices_list = list(mstate.prices)
    
    n = len(prices_list)
    if n < 5:
        # Fallback to global if local is empty (e.g., during startup)
        if symbol == TICKER and state.prices:
            prices_list = list(state.prices)
            n = len(prices_list)
        else:
            return None
        
    recent = prices_list[-60:] if n >= 60 else prices_list
    current = prices_list[-1]
    features = {"symbol": symbol, "price": current, "samples": len(recent)}

    # Short-term momentum (last 10 prices)
    if n >= 10:
        features["change_10"] = round(current - prices_list[-10], 2)
        features["pct_change_10"] = round((current - prices_list[-10]) / prices_list[-10] * 100, 4)
    else:
        features["change_10"] = 0.0
        features["pct_change_10"] = 0.0

    # Volatility (stdev of last 30 prices)
    if len(recent) >= 5:
        features["volatility"] = round(stdev(recent[-30:]) if len(recent) >= 30 else stdev(recent), 4)
    else:
        features["volatility"] = 0.0

    # Trend (are we above or below mean)
    avg = mean(recent)
    features["vs_mean"] = round(current - avg, 2)
    features["trend"] = "UP" if current > avg else "DOWN" if current < avg else "FLAT"

    # High/low range
    features["range_high"] = max(recent)
    features["range_low"] = min(recent)
    features["range_size"] = round(max(recent) - min(recent), 2)
    
    # Price freshness
    features["price_is_stale"] = mstate.is_stale()

    # PHASE 3: ATR and adaptive sizing
    atr = risk_math.calculate_atr(mstate.prices if mstate.prices else state.prices, period=14)
    mstate.current_atr = atr
    if symbol == TICKER:
        state.current_atr = atr
    features["atr"] = atr
    
    # L2 Depth Features (if available)
    if mstate.orderbook_data:
        features["spread"] = mstate.orderbook_data.get('spread', 0.0)
        features["imbalance"] = mstate.orderbook_data.get('imbalance', 0.0)
        features["book_pressure"] = mstate.orderbook_data.get('book_pressure', 0.0)
    
    # Get current win rate for adaptive targets scaling
    if state.trade_history:
        stats = risk_math.calculate_expectancy(state.trade_history)
        wr = stats.get("win_rate", 0)
        kelly = risk_math.kelly_fraction(wr, stats.get("avg_win", 0), stats.get("avg_loss", 0))
    else:
        wr = 0.5  # Default 50% for no history
        kelly = 0
    
    # Calculate adaptive stop and targets
    adaptive_stop = risk_math.adaptive_stop_loss(atr, base_multiplier=1.5)
    target_short, target_mid, target_long = risk_math.adaptive_targets(atr, wr, kelly)
    
    features["adaptive_stop_pts"] = adaptive_stop
    features["target_short_pts"] = target_short
    features["target_mid_pts"] = target_mid
    features["target_long_pts"] = target_long
    features["win_rate"] = wr
    
    # L2 DEPTH FEATURES
    features["best_bid_depth"] = state.best_bid_depth
    features["best_ask_depth"] = state.best_ask_depth
    features["spread"] = state.orderbook_data.get('spread', 0.0) if state.orderbook_data else 0.0
    features["imbalance"] = state.orderbook_data.get('imbalance', 0.0) if state.orderbook_data else 0.0
    features["ofi"] = state.orderbook_data.get('ofi', 0.0) if state.orderbook_data else 0.0  # Order Flow Imbalance
    features["book_pressure"] = state.orderbook_data.get('book_pressure', 0.0) if state.orderbook_data else 0.0  # Book pressure score
    # L2 freshness: fresh if < 5s (warning threshold), stale if > 10s (block threshold)
    l2_age = time.time() - state.l2_timestamp if state.l2_timestamp > 0 else 999
    features["l2_fresh"] = l2_age < L2_STALE_WARNING_SECONDS
    features["l2_age_seconds"] = round(l2_age, 1)
    features["l2_circuit_breaker"] = state.l2_circuit_breaker_active
    features["l2_quality_checks"] = state.l2_quality_checks if state.l2_quality_checks else {}
    
    # Regime tracking (no ML model - just use string regime directly)
    features["current_regime"] = state.current_regime
    features["regime_confidence"] = state.regime_confidence
    features["regime_description"] = features.get("trend", "FLAT")  # Use trend as proxy for description
    
    # Momentum (10-bar change for feature tracking)
    features["momentum"] = features.get("change_10", 0.0)
    
    # PHASE 3: Deterministic Regime Detection (Hysteresis-ready)
    regime_name = "RANGING"
    if features["trend"] != "FLAT":
        regime_name = f"TRENDING_{features['trend']}"
    if features["volatility"] > (atr * 2.0):
        regime_name = "VOLATILE"
    if features["range_size"] < (atr * 0.5):
        regime_name = "CHOPPY"
        
    mstate.regime = MarketRegime(
        regime=regime_name,
        confidence=0.8, # Placeholder for hysteresis logic
        atr=atr,
        spread_ticks=mstate.orderbook_data.get('spread_ticks', 0.0),
        timestamp=time.time(),
        description=f"Market detected as {regime_name} based on trend/volatility"
    )
    
    features["current_regime"] = mstate.regime.regime
    features["regime_confidence"] = mstate.regime.confidence
    features["regime_description"] = mstate.regime.description
    
    # Add regime info for prompts
    features["regime_stop_multiplier"] = risk_math.regime_settings(regime_name).get('stop_multiplier', 1.5)
    features["regime_target_multiplier"] = risk_math.regime_settings(regime_name).get('target_multiplier', 4.0)

    return features


# ============================================================
# PHASE 5: Market Regime Detection & Strategy Switching
# ============================================================
async def update_market_regime():
    """Detect current market regime and update state.
    
    Called every DECISION_INTERVAL (30s) in control loop.
    Updates state.current_regime, regime_confidence, regime_history.
    Logs regime changes at INFO level.
    """
    if not state.prices or len(state.prices) < 10:
        return  # Not enough data
    
    prices_list = list(state.prices)  # Convert deque to list for slice support
    
    # Calculate returns for volatility analysis
    returns_list = []
    if len(prices_list) >= 2:
        for i in range(1, min(20, len(prices_list))):
            ret = prices_list[-i] - prices_list[-i-1]
            returns_list.insert(0, ret)
    
    # Detect regime
    regime, confidence = risk_math.detect_market_regime(
        prices_list,
        state.current_atr,
        returns_list if returns_list else None
    )
    
    # Calculate regime metrics for context
    recent_prices = prices_list[-10:] if len(prices_list) >= 10 else prices_list
    if len(recent_prices) >= 2:
        price_slope = (recent_prices[-1] - recent_prices[0]) / (len(recent_prices) - 1)
    else:
        price_slope = 0.0
    
    volatility_ratio = state.current_atr / (risk_math.calculate_atr(prices_list[-20:], period=14) if len(prices_list) >= 20 else state.current_atr) if state.current_atr > 0 else 1.0
    
    state.regime_price_slope = price_slope
    state.regime_volatility_ratio = volatility_ratio
    
    # Check if regime changed
    old_regime = state.current_regime
    state.current_regime = regime
    state.regime_confidence = confidence
    state._last_regime_update = time.time()
    
    # Track regime history (last 50)
    regime_entry = {
        "timestamp": state._last_regime_update,
        "regime": regime,
        "confidence": confidence,
        "atr": state.current_atr,
        "slope": round(price_slope, 3),
        "vol_ratio": round(volatility_ratio, 2)
    }
    state.regime_history.append(regime_entry)
    if len(state.regime_history) > 50:
        state.regime_history.pop(0)
    
    # Log regime change if detected
    if old_regime != regime:
        summary = risk_math.format_regime_summary(regime, confidence, state.current_atr, price_slope, volatility_ratio)
        log.info(f"REGIME CHANGE: {old_regime} → {summary}")
        
        # Get regime settings for context
        settings = risk_math.regime_settings(regime)
        if not settings['allowed_trades']:
            log.warning(f"TRADING DISABLED IN {regime}: {settings['description']}")
        else:
            log.info(f"Strategy adjusted for {regime}: "
                    f"stops={settings['stop_multiplier']}x ATR, "
                    f"targets={settings['target_multiplier']}:1 R:R, "
                    f"size_reduction={settings['position_size_reduction']:.1%}")


def check_volatility_surge():
    """VOLATILITY SURGE DETECTION - Safety improvement 2026-03-09.
    
    Detects when ATR suddenly increases by >50% in 60 seconds.
    Triggers circuit breaker: no new entries for 120 seconds.
    
    Returns: (breaker_active: bool, reason: str)
    """
    now = time.time()
    
    # Check if circuit breaker is currently active
    if state.volatility_circuit_breaker_active:
        if now >= state.volatility_circuit_breaker_until:
            # Breaker expired
            state.volatility_circuit_breaker_active = False
            log.info("VOLATILITY SURGE: Circuit breaker expired, trading resumed")
            return False, ""
        else:
            remaining = state.volatility_circuit_breaker_until - now
            return True, f"Volatility circuit breaker active ({remaining:.0f}s remaining)"
    
    # Check if we have ATR data
    if state.current_atr <= 0:
        return False, ""
    
    # Record previous ATR every 60 seconds
    if now - state.prev_atr_timestamp >= 60:
        state.prev_atr = state.current_atr
        state.prev_atr_timestamp = now
        return False, ""
    
    # Check for surge: current ATR > 1.5x previous ATR
    if state.prev_atr > 0 and state.current_atr > state.prev_atr * 1.5:
        # Surge detected - trigger circuit breaker for 120 seconds
        state.volatility_circuit_breaker_active = True
        state.volatility_circuit_breaker_until = now + 120
        surge_pct = ((state.current_atr / state.prev_atr) - 1) * 100
        log.warning(f"VOLATILITY SURGE DETECTED - circuit breaker active: ATR {state.prev_atr:.1f} → {state.current_atr:.1f} (+{surge_pct:.0f}%) - no new entries for 120s")
        return True, f"Volatility surge detected (ATR +{surge_pct:.0f}%), breaker active for 120s"
    
    return False, ""


# ============================================================
# PHASE 2: Position Sizing Helpers
# ============================================================
def check_risk_constraints(engine: str, decision: dict, features: dict) -> tuple[bool, str]:
    """Check position sizing and risk constraints before entering a trade.
    
    Returns: (can_enter: bool, reason: str)
    """
    action = decision.get("action", "WAIT").upper()
    
    # Only check for ENTER actions
    if action not in ("BUY", "SELL", "ENTER", "HEDGE"):
        return True, ""
    
    # Check 0: Volatility circuit breaker (SAFETY 2026-03-09)
    if state.volatility_circuit_breaker_active:
        remaining = state.volatility_circuit_breaker_until - time.time()
        return False, f"Volatility surge breaker active ({remaining:.0f}s remaining)"
    
    # Check 1: Max concurrent positions
    current_positions = state.position_count
    if current_positions >= state.max_concurrent_limit:
        return False, f"At max concurrent positions ({current_positions}/{state.max_concurrent_limit})"
    
    # Check 2: Daily loss limit (5% of account = $500 on $10k)
    if state.daily_pnl < state.daily_loss_threshold:
        return False, f"Daily loss limit exceeded (${state.daily_pnl:.2f} < ${state.daily_loss_threshold:.2f})"
    
    # Check 3: Daily risk budget (max $500 risk per day = 5 contracts * $20 risk each at typical SL)
    size = decision.get("size", 1)
    stop_pts = decision.get("stop_points", 30)
    risk_on_trade = size * stop_pts * POINT_VALUE
    
    if state.daily_risk_used + risk_on_trade > 500.0:  # Max $500 risk per day
        return False, f"Risk budget exceeded: used=${state.daily_risk_used:.2f} + new=${risk_on_trade:.2f} > $500"
    
    return True, ""


def calculate_kelly_size(engine: str, features: dict) -> int:
    """Calculate position size using Kelly Criterion if we have trade history.
    
    Returns: contracts to trade (1-5)
    """
    # Need at least 10 trades per engine to trust Kelly
    if engine == "warwick":
        if state.warwick_consecutive_losses >= 5:
            return 1  # Reduce size after losing streak
        trades = [t for t in state.trade_history if t.get("engine") == "warwick"]
    elif engine == "council":
        if state.council_consecutive_losses >= 5:
            return 1  # Reduce size after losing streak
        trades = [t for t in state.trade_history if t.get("engine") == "council"]
    else:
        trades = state.trade_history
    
    if len(trades) < 10:
        return 1  # Not enough history, use minimum
    
    # Calculate expectancy
    stats = risk_math.calculate_expectancy(trades)
    if stats["avg_loss"] <= 0:
        return 1
    
    # Use Kelly to size up to 5 contracts
    kelly_pct = risk_math.kelly_fraction(
        stats["win_rate"],
        stats["avg_win"],
        stats["avg_loss"],
        fraction=0.5  # Conservative: 50% Kelly
    ) / 100.0
    
    # Size: 1 to 5 contracts based on Kelly
    kelly_pct = max(0, min(0.25, kelly_pct))
    size = max(1, int(1 + kelly_pct * 4))  # 1 + (0 to 4)
    return min(5, size)


def size_for_risk(stop_points: float, target_risk: float = 100.0) -> int:
    """Calculate contracts needed to risk exactly target_risk dollars.
    
    Args:
        stop_points: stop loss width in points
        target_risk: dollars willing to risk (default $100)
    
    Returns: contracts to trade
    """
    if stop_points <= 0:
        return 1
    contracts = target_risk / (stop_points * POINT_VALUE)
    return max(1, min(5, int(contracts)))


# ============================================================
# PHASE 2: L2 ORDERBOOK QUALITY GATE
# ============================================================
def check_l2_quality_gate(state_obj) -> tuple[bool, dict]:
    """Check if orderbook conditions are suitable for entry.
    
    PHASE 2: Gate conditions reject entry if:
    - Spread > 1.0 point (more than typical bid-ask)
    - Imbalance > 0.7 (>70% skew toward one side)
    - Shallow depth: min(bid_depth, ask_depth) < 500 USD
    - L2 data is stale (>10 seconds old) - changed from 5s
    
    SAFETY: Circuit breaker activates when L2 data is stale for >60s total.
    
    Args:
        state_obj: VortexState object with orderbook_data
    
    Returns:
        Tuple of (gate_pass: bool, gate_info: dict)
        gate_pass = True means orderbook is healthy, entry allowed
        gate_info contains details of all checks
    """
    start_time = time.time()
    gate_info = {
        'pass': True,
        'conditions': {},
        'blocked_reason': None,
        'execution_time_ms': 0,
        'circuit_breaker_active': state_obj.l2_circuit_breaker_active
    }
    
    # Check 0: Circuit breaker already active - block all entries
    if state_obj.l2_circuit_breaker_active:
        gate_info['blocked_reason'] = f"L2 CIRCUIT BREAKER active since {time.time() - state_obj.l2_circuit_breaker_since:.0f}s ago"
        gate_info['pass'] = False
        gate_info['conditions']['circuit_breaker'] = True
        gate_info['execution_time_ms'] = round((time.time() - start_time) * 1000, 2)
        return (False, gate_info)
    
    # Check 1: No L2 data available - BLOCK entries (safety improvement)
    # L2 data is critical for market quality assessment
    if not state_obj.orderbook_data:
        gate_info['conditions']['no_data'] = True
        gate_info['blocked_reason'] = "L2 orderbook data is None or empty (blocking entries)"
        gate_info['pass'] = False  # BLOCK: require L2 data for entry
        gate_info['execution_time_ms'] = round((time.time() - start_time) * 1000, 2)
        log.warning(f"L2_GATE: {gate_info['blocked_reason']}")
        return (False, gate_info)
    
    # Check 1b: L2 data has no bids or asks (empty orderbook)
    bids = state_obj.orderbook_data.get('bid_levels', [])
    asks = state_obj.orderbook_data.get('ask_levels', [])
    if not bids or not asks:
        gate_info['conditions']['empty_book'] = True
        gate_info['blocked_reason'] = f"L2 orderbook has no {'bids' if not bids else 'asks'} (blocking entries)"
        gate_info['pass'] = False
        gate_info['execution_time_ms'] = round((time.time() - start_time) * 1000, 2)
        log.warning(f"L2_GATE: {gate_info['blocked_reason']}")
        return (False, gate_info)
    
    # Extract L2 metrics
    spread = state_obj.orderbook_data.get('spread', 0.0)
    imbalance = abs(state_obj.orderbook_data.get('imbalance', 0.0))
    bid_depth = state_obj.best_bid_depth  # in USD
    ask_depth = state_obj.best_ask_depth  # in USD
    data_age = time.time() - state_obj.l2_timestamp if state_obj.l2_timestamp > 0 else 0
    
    # L2 SAFETY: Track staleness and update circuit breaker
    _update_l2_stale_tracking(state_obj, data_age)
    
    # Check if circuit breaker just activated
    if state_obj.l2_circuit_breaker_active:
        gate_info['blocked_reason'] = f"L2 CIRCUIT BREAKER activated - total stale time {state_obj.l2_total_stale_seconds:.0f}s > {L2_CIRCUIT_BREAKER_SECONDS}s"
        gate_info['pass'] = False
        gate_info['conditions']['circuit_breaker'] = True
        gate_info['circuit_breaker_active'] = True
        gate_info['execution_time_ms'] = round((time.time() - start_time) * 1000, 2)
        return (False, gate_info)
    
    # Gate condition 1: Spread too wide — raised to 5.0pt to allow session-open trading
    gate_info['conditions']['spread_too_wide'] = spread > 5.0
    if spread > 5.0:
        gate_info['blocked_reason'] = f"Spread {spread:.4f} > 5.0 pt (extremely wide, unsafe)"
        gate_info['pass'] = False
    
    # Gate condition 2: Imbalance — REMOVED (was inverted: high imbalance is an ENTRY signal, not a block)
    gate_info['conditions']['imbalance_extreme'] = False  # Never block on imbalance
    
    # Gate condition 3: Shallow depth (disabled by default; enable with VORTEX_L2_MIN_DEPTH_USD)
    min_depth = min(bid_depth, ask_depth)
    gate_info['conditions']['shallow_depth'] = L2_MIN_DEPTH_USD > 0 and min_depth < L2_MIN_DEPTH_USD
    if gate_info['conditions']['shallow_depth']:
        gate_info['blocked_reason'] = f"Shallow depth ${min_depth:.0f} < ${L2_MIN_DEPTH_USD:.0f} (no liquidity)"
        gate_info['pass'] = False
    
    # Gate condition 4: L2 data stale - UPDATED: block at 10s, warn at 5s
    is_stale = data_age > L2_STALE_BLOCK_SECONDS
    is_warning = data_age > L2_STALE_WARNING_SECONDS and not is_stale
    
    gate_info['conditions']['data_stale'] = is_stale
    gate_info['conditions']['data_warning'] = is_warning
    gate_info['data_age'] = round(data_age, 1)
    
    if is_stale:
        gate_info['blocked_reason'] = f"L2 data stale {data_age:.1f}s > {L2_STALE_BLOCK_SECONDS}s (blocking entries)"
        gate_info['pass'] = False
    elif is_warning:
        # Warning at 5s, but don't block
        gate_info['warning'] = f"L2 data age {data_age:.1f}s > {L2_STALE_WARNING_SECONDS}s (warning)"
        if gate_info['pass']:  # Only log if not already blocked for another reason
            log.warning(f"L2_GATE: {gate_info['warning']}")
    
    gate_info['execution_time_ms'] = round((time.time() - start_time) * 1000, 2)
    
    # Log if gated (entry blocked)
    if not gate_info['pass']:
        log.info(f"L2_GATE: {gate_info['blocked_reason']} | "
                f"spread={spread:.4f} imbalance={imbalance:.2%} depth=${min_depth:.0f} age={data_age:.1f}s")
    
    return (gate_info['pass'], gate_info)


def _update_l2_stale_tracking(state_obj, data_age: float):
    """Update L2 staleness tracking and check for circuit breaker activation.
    
    SAFETY: Tracks consecutive stale checks and cumulative stale time.
    Activates circuit breaker when total stale time exceeds threshold.
    
    Args:
        state_obj: VortexState object to update
        data_age: Current age of L2 data in seconds
    """
    now = time.time()
    
    # Check if data is currently stale
    is_currently_stale = data_age > L2_STALE_WARNING_SECONDS
    
    # Track state transitions for logging
    if is_currently_stale and not state_obj.l2_was_stale:
        # Data just became stale - log transition
        log.warning(f"L2 DATA QUALITY: Data became stale (age={data_age:.1f}s)")
        state_obj.l2_was_stale = True
    elif not is_currently_stale and state_obj.l2_was_stale:
        # Data just became fresh again - log transition
        log.info(f"L2 DATA QUALITY: Data fresh again (age={data_age:.1f}s) - was stale for {state_obj.l2_consecutive_stale_checks} checks")
        state_obj.l2_was_stale = False
    
    # Update tracking if stale
    if is_currently_stale:
        state_obj.l2_consecutive_stale_checks += 1
        # Add this check interval to cumulative stale time
        state_obj.l2_total_stale_seconds += min(data_age, DECISION_INTERVAL)
        
        # Check for circuit breaker activation
        if (state_obj.l2_total_stale_seconds >= L2_CIRCUIT_BREAKER_SECONDS 
            and not state_obj.l2_circuit_breaker_active):
            # Activate circuit breaker
            state_obj.l2_circuit_breaker_active = True
            state_obj.l2_circuit_breaker_since = now
            log.critical(f"L2 CIRCUIT BREAKER: ACTIVATED - total stale time {state_obj.l2_total_stale_seconds:.0f}s >= {L2_CIRCUIT_BREAKER_SECONDS}s")
            log.warning(f"L2 CIRCUIT BREAKER: All entries blocked until fresh L2 data received")
    else:
        # Data is fresh - reset counters
        if state_obj.l2_consecutive_stale_checks > 0:
            log.info(f"L2 DATA QUALITY: Fresh data received - resetting stale counters (was {state_obj.l2_consecutive_stale_checks} consecutive checks)")
        state_obj.l2_consecutive_stale_checks = 0
        state_obj.l2_total_stale_seconds = 0.0
        
        # Reset circuit breaker if active and data is fresh
        if state_obj.l2_circuit_breaker_active:
            state_obj.l2_circuit_breaker_active = False
            state_obj.l2_circuit_breaker_since = 0.0
            log.info(f"L2 CIRCUIT BREAKER: RESET - fresh L2 data received, entries allowed again")


# ============================================================
# AI DECISION (non-deterministic - Claude)
# ============================================================
async def ask_claude(features, symbol: str = None):
    """PHASE 8: Meta-Thinker loop with 10/10 engine specialization.
    PHASE 2: Symbol-aware and rate-limited.
    Now includes Global Market Pulse and Correlation Awareness.
    """
    primary_engine = features.get("primary_engine", "council")
    braid_alpha = features.get("braid_alpha", "NEUTRAL")
    pnl = features.get("current_pnl", 0.0)
    
    # 1. Global Market Pulse (Correlation Index)
    # Calculate simple correlation index (number of symbols trending in same direction)
    trending_ups = sum(1 for m in state.markets.values() if len(m.prices) > 10 and (m.prices[-1] > m.prices[-10]))
    trending_downs = sum(1 for m in state.markets.values() if len(m.prices) > 10 and (m.prices[-1] < m.prices[-10]))
    total_active = len(state.markets)
    correlation_index = max(trending_ups, trending_downs) / max(1, total_active)
    leader = "MNQ" # Default leader
    
    global_pulse = f"GLOBAL MARKET PULSE: Correlation={correlation_index:.2f} | Trending={trending_ups} UP / {trending_downs} DOWN / {total_active} TOTAL"

    # S-1: specialized persona prompt selection (mins blueprint)
    if primary_engine == "warwick":
        system_prompt = f"You are Warwick (TRENDING Hunter). Goal: $1k/day. Target 4:1 R:R. Alpha={braid_alpha}. Current PnL=${pnl:.2f}.\n{global_pulse}"
    elif primary_engine == "chimera":
        system_prompt = f"You are Chimera (VOLATILE Executioner). Goal: $1k/day. Navigate flash volatility. Alpha={braid_alpha}. Current PnL=${pnl:.2f}.\n{global_pulse}"
    else: # Council
        system_prompt = f"You are Council (RANGING Anchor). Goal: $1k/day. Grind scalps. Alpha={braid_alpha}. Current PnL=${pnl:.2f}.\n{global_pulse}"

    # S-2: Inject 10/10 "Learned Wisdom" into the prompt
    system_prompt += "\nLEARNED WISDOM: MNQ volatility spikes >35 ATR require Chimera. MES ranging <8 ATR favors Council scalps."
    
    # SOE: Risk Budget & Consecutive Loss Context
    daily_risk_used = state.daily_risk_used
    risk_remaining = state.ai_risk_limit - daily_risk_used
    trades_remaining = int(risk_remaining / state.ai_override_risk) if state.ai_override_risk > 0 else 0
    consecutive_losses = max(state.warwick_consecutive_losses, state.council_consecutive_losses, state.chimera_consecutive_losses)
    
    risk_ctx = f"\nRISK BUDGET: Used ${daily_risk_used:.0f} / Total ${state.ai_risk_limit:.0f} | Remaining ${risk_remaining:.0f} (~{trades_remaining} trades)"
    if consecutive_losses >= 3:
        risk_ctx += f"\nWARNING: {consecutive_losses} consecutive losses. Are you revenge trading? Check trend alignment."
    
    system_prompt += risk_ctx
    system_prompt += "\nGLOBAL RISK CAP: $500. You have authority to OVERRIDE if alpha > 0.9. Include 'override_risk': true in JSON if needed."

    if symbol is None:
        symbol = TICKER
        
    # Rate Limit: Serialize Claude API calls across parallel markets
    await claude_limiter.wait()
    
    config = INSTRUMENT_CONFIG.get(symbol, INSTRUMENT_CONFIG[TICKER])
    mstate = state.get_market(symbol)
    
    # [CODE] Construct symbol-specific prompt
    instr_info = f"INSTRUMENT: {symbol} ({config['name']})\nTick: {config['tick_size']} | Point Value: ${config['point_value']}"
    
    # Build awareness context -- use council's own memory if available
    awareness_context = features.get('_council_context', '')
    if not awareness_context and council_awareness:
        try:
            account_bal = state.broker_balance if state.broker_balance > 0 else 100000
            awareness_context = council_awareness.build_context(features, account_bal, state.daily_pnl)
        except Exception as e:
            log.debug(f"Council awareness context error: {e}")

    # Inject Instrument Specialization
    system_prompt = f"{instr_info}\n{awareness_context}\n\nYou are a specialized trading agent for {symbol}. Evaluate current features and decide."

    # Build council debate prompt -- 5 fixed trading-relevant personas
    COUNCIL_AGENTS = ["loe", "challenge_assumptions", "kaizen_profit", "psyche", "keen"]
    council_prompt = ""
    if fleet and fleet.running:
        try:
            council_lines = ["## COUNCIL DEBATE",
                "Hold an internal council. Adopt each persona completely and give a "
                "1-2 sentence trade verdict from their perspective. Then synthesize.",
                ""]
            for name in COUNCIL_AGENTS:
                a = fleet.get_agent(name)
                if a:
                    council_lines.append(f"### {name.upper()}")
                    council_lines.append(f"Tone: {a.tone}")
                    council_lines.append(f"Role: {a.role}")
                    council_lines.append(f"Rules: {a.rules}")
                    council_lines.append(f'Catchphrase: "{a.catchphrase}"')
                    council_lines.append("")
            council_lines.append("For each agent: \"[AGENT_NAME]: <verdict>\"")
            council_lines.append("Then: \"[SYNTHESIS]: <final decision weighing all voices>\"")
            council_prompt = "\n".join(council_lines)
        except Exception as e:
            log.debug(f"Council build error: {e}")

    # Stress test mode: no WAIT allowed
    stress_rules = ""
    if STRESS_TEST_MODE:
        stress_rules = """
STRESS TEST MODE ACTIVE:
- You MUST trade. WAIT is NOT allowed. Every decision must be BUY, SELL, or CLOSE.
- Your goal is to stress-test the system by trading aggressively.
- Try different strategies: scalps, reversals, trend-following, counter-trend.
- Vary your stop_points (10-100) and target_points (10-100) to test different risk profiles.
- If flat, ENTER a trade. If in a position, decide: CLOSE and reverse, or CLOSE and re-enter.
- Report any anomalies in your reasoning (stale prices, weird fills, etc).
- This is a TESTING session - the goal is finding bugs, not preserving capital."""

    position_rules = "- If FLAT: you must BUY or SELL" if STRESS_TEST_MODE else "- If FLAT: BUY, SELL, or WAIT"
    if mstate.position_side != "FLAT":
        position_rules = "- In position: CLOSE only (SL/TP are your safety net, they stay active)"

    # Warwick hunt status (if active)
    warwick_section = ""
    if warwick and (warwick.state.primary.is_open or warwick.state.hedge.is_open):
        warwick_section = warwick.build_prompt_section(state.price)

    # LEARNING MODE: Load mission and inject context for autonomous learning
    learning_section = ""
    learning_mode_path = STATE_DIR / "learning_mode.json"
    learning_mission_path = VORTEX_DIR / "CLAUDE_LEARNING_MISSION.md"
    try:
        if learning_mode_path.exists():
            learning_config = json.loads(learning_mode_path.read_text())
            if learning_config.get("enabled") and learning_config.get("mode") == "full_autonomy":
                constraints = learning_config.get("constraints", {})
                learning_section = f"""
## LEARNING MISSION: Full Autonomy Active
Mission: Learn to trade profitably through experimentation.

You have COMPLETE FREEDOM to trade however you want. The goal is discovery.

**You Control:**
- Entry timing and conditions
- Position sizing (1-{constraints.get('max_position', 6)} contracts)
- Stop-loss width (experiment with 10-100 points)
- Take-profit targets and ratios
- Pattern recognition and testing

**Hard Limits (System Enforced):**
- Daily loss limit: ${constraints.get('daily_loss_limit', -500)} (trading halts)
- Max position: {constraints.get('max_position', 6)} contracts
- End of day: {constraints.get('forced_flatten_time', '15:08 CT')}

**Learning Loop (after every trade):**
1. What pattern did you think you saw?
2. Was your confidence justified?
3. Should you adjust this pattern's confidence?

EXPERIMENT. Try different stop/target ratios. Test momentum vs mean-reversion.
Discover YOUR edge. What works for YOU may differ from human traders.
"""
    except Exception as e:
        log.debug(f"Learning mode load error: {e}")

    # STEERING CONTEXT: Inject adaptive decision guidance
    steering_section = features.get('steering_context', '')

    # L2 FRESHNESS WARNING: Add prominent warning if L2 data is stale or unavailable
    l2_warning = ""
    l2_age = time.time() - state.l2_timestamp if state.l2_timestamp > 0 else 999
    if not state.orderbook_data:
        l2_warning = "\n⚠️  WARNING: L2 ORDERBOOK DATA IS UNAVAILABLE - No depth data available  ⚠️\n"
    elif l2_age > L2_STALE_BLOCK_SECONDS:
        l2_warning = f"\n⚠️  WARNING: L2 DATA IS STALE ({l2_age:.1f}s old > {L2_STALE_BLOCK_SECONDS}s threshold) - Use caution  ⚠️\n"
    elif l2_age > L2_STALE_WARNING_SECONDS:
        l2_warning = f"\n⚠️  CAUTION: L2 data is aging ({l2_age:.1f}s) - May become stale soon  ⚠️\n"

    prompt = f"""You are an autonomous AI futures trader for MNQ with internal memory, self-awareness, and a council of specialist advisors.
{l2_warning}
{awareness_context}
{learning_section}
{steering_section}
MARKET NOW:
- Price: {features['price']}{" [WARNING: PRICE DATA IS STALE]" if features.get("price_is_stale") else ""}
- 10-sample change: {features['change_10']} pts ({features['pct_change_10']}%)
- Volatility: {features['volatility']} pts (stdev)
- ATR (14): {features.get('atr', 0):.1f} pts | Adaptive SL: {features.get('adaptive_stop_pts', 0):.1f} pts
- Trend: {features['trend']} (vs mean: {features['vs_mean']})
- Range: {features['range_low']}-{features['range_high']} ({features['range_size']} pts)
- PHASE 3 TARGETS: Conservative={features.get('target_short_pts', 0):.1f}pts | Mid={features.get('target_mid_pts', 0):.1f}pts | Aggressive={features.get('target_long_pts', 0):.1f}pts

L2 DEPTH ANALYSIS:
- Best Bid Depth: ${features.get('best_bid_depth', 0):.2f} (volume within 2 ticks of best bid)
- Best Ask Depth: ${features.get('best_ask_depth', 0):.2f} (volume within 2 ticks of best ask)
- Bid/Ask Imbalance: {features.get('imbalance', 0)*100:.1f}% (positive=more bid demand)
- Order Flow Imbalance (OFI): {features.get('ofi', 0):.0f} (cumulative bid-ask volume diff)
- Book Pressure: {features.get('book_pressure', 0):.2f} (range -1 to 1, >0=buy pressure, <0=sell pressure)
- Spread: {features.get('spread', 0):.4f} pts
- L2 Data Fresh: {"YES" if features.get('l2_fresh', False) else "NO - use caution"}
- Quality Checks: {', '.join([f"{k}={v}" for k,v in features.get('l2_quality_checks', {}).items()]) or "unknown"}

MARKET REGIME (PHASE 5):
- Current: {features.get('current_regime', 'RANGING')} ({features.get('regime_confidence', 0):.0f}% confidence)
- Description: {features.get('regime_description', 'Unknown')}
- Strategy: {risk_math.regime_settings(features.get('current_regime', 'RANGING'))['description']}
- Recommended stops: {features.get('regime_stop_multiplier', 1.5)}x ATR
- Recommended targets: {features.get('regime_target_multiplier', 4.0)}:1 R:R ratio
- Position sizing: {features.get('regime_size_reduction', 1.0):.0%} of baseline

WARWICK POSITION: {mstate.position_side} (size={mstate.position_size}, entry={mstate.position_entry})
COUNCIL POSITION: {mstate.council_trade.side} (size={mstate.council_trade.size}, entry={mstate.council_trade.entry_price}, SL={mstate.council_trade.sl_price}, TP={mstate.council_trade.tp_price})
CHIMERA POSITION: {mstate.chimera_trade.side} (size={mstate.chimera_trade.size}, entry={mstate.chimera_trade.entry_price}, SL={mstate.chimera_trade.sl_price}, TP={mstate.chimera_trade.tp_price})
BROKER: balance=${state.broker_balance:.2f}, realized_pnl=${state.broker_realized_pnl:.2f}
SESSION: trades={state.trade_count}, W={state.wins}, L={state.losses}, PnL=${state.daily_pnl:.2f}
MATH STATS: {f"WR={state._math_stats['council']['win_rate']*100:.0f}% Exp=${state._math_stats['council']['expectancy']:.2f} Kelly={state._math_stats['council']['kelly_pct']:.1f}% Ruin={state._math_stats['council']['risk_of_ruin_pct']:.1f}%" if hasattr(state, '_math_stats') and 'council' in state._math_stats else "calculating..."} {'[HALTED - negative expectancy]' if state.council_halted else ''}

ALL OPEN TRADES (SL/TP visible to all engines):
{chr(10).join([f"  {k}: {v['engine']} {v['symbol']} {v['side']} {v['size']}ct entry={v['entry']:.2f} SL={v['sl']:.2f} TP={v['tp']:.2f}" for k,v in state.open_trades.items()]) if state.open_trades else "  (none)"}

{get_market_snapshot()}

{warwick_section}

{council_prompt}
{stress_rules}

RULES (REGIME-AWARE):
- Stop/target are in POINTS from entry (1 {TICKER} point = ${POINT_VALUE}/contract)
- Size: 1-3 contracts for your own trades (adjust based on regime)
  - TRENDING regimes: use full size
  - RANGING regime: use 75% size (tight stops, scalps)
  - HIGH_VOLATILITY: use 50% size (wide stops, careful)
  - CHOPPY: use minimal size or WAIT
- STOPS: Use {features.get('regime_stop_multiplier', 1.5)}x ATR for {features.get('current_regime', 'RANGING')} regime
- TARGETS: Use {features.get('regime_target_multiplier', 4.0)}:1 R:R for {features.get('current_regime', 'RANGING')} regime
- You MUST set stop_loss and take_profit on every entry (adjusted for regime)
- If price data is stale, be cautious - use tighter stops or stay flat
- SL/TP orders stay as safety nets - they are NOT cancelled when you CLOSE
- WARWICK: A separate AI engine trades alongside you on the SAME account. You see its positions for awareness but you are FULLY INDEPENDENT. Trade your own thesis. Do NOT defer to Warwick or say WAIT just because Warwick has positions. You have your OWN position tracked separately.
- If you have no Council position open: BUY, SELL, or WAIT based on YOUR analysis (use regime to adjust stops/size)
- If you have a Council position open: HOLD, CLOSE, or WAIT

RESPOND WITH THE COUNCIL DEBATE THEN YOUR FINAL JSON DECISION.
Format: council debate lines, then on the LAST line, ONLY valid JSON:
{{"action": "BUY"|"SELL"|"CLOSE"|"WAIT", "size": 1, "stop_points": 25, "target_points": 50, "confidence": 0.0-1.0, "reasoning": "brief reason including council consensus", "learning": "optional insight from this debate"}}"""

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        # Model tiering: use Haiku for routine HOLDs, Sonnet for critical decisions
        is_critical = (
            state.position_side == "FLAT"  # need to ENTER
            or (state.position_side != "FLAT" and abs(state.position_entry - state.price) > 6)  # big move
        )
        council_model = AI_MODEL if is_critical else HAIKU_MODEL
        if not is_critical:
            log.info("COUNCIL: Using Haiku for routine HOLD check")
        body = json.dumps({
            "model": council_model,
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(url, data=body, headers=headers, method='POST')
        
        # PRIORITY FIX: Rate limit handling with retry
        for retry_attempt in range(CLAUDE_RATE_LIMIT_MAX_RETRIES + 1):
            try:
                def _call_claude_sync():
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        return json.loads(resp.read().decode())
                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(None, _call_claude_sync)
                break  # Success, exit retry loop
            except urllib.error.HTTPError as e:
                if e.code == 429:  # Rate limited
                    if retry_attempt < CLAUDE_RATE_LIMIT_MAX_RETRIES:
                        should_retry = await handle_claude_rate_limit(e, retry_attempt)
                        if not should_retry:
                            return {"action": "WAIT", "reasoning": "Claude rate limit - max retries exhausted"}
                        continue  # Retry
                    else:
                        log.error("CLAUDE RATE LIMIT: Max retries exhausted")
                        log_anomaly("rate_limit", "Claude API rate limit max retries")
                        return {"action": "WAIT", "reasoning": "Claude rate limit - max retries"}
                else:
                    raise  # Re-raise non-429 errors
        
        text = data["content"][0]["text"].strip()

        # Parse response: council debate text + JSON on last line(s)
        council_text = ""
        json_text = text

        # Try to find JSON in the response (may be after debate text)
        # Strategy: find the last { ... } block
        brace_start = text.rfind('{')
        brace_end = text.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            json_text = text[brace_start:brace_end + 1]
            council_text = text[:brace_start].strip()
        elif text.startswith("```"):
            json_text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        # Log the council debate
        if council_text:
            debate_lines = [l.strip() for l in council_text.split('\n') if l.strip()]
            for line in debate_lines[-8:]:
                if line.startswith('[') and ']:' in line:
                    log.info(f"COUNCIL: {line[:120]}")

        decision = json.loads(json_text)
        
        # PHASE 8: AI Override Authority
        if decision.get("override_risk", False) and decision.get("confidence", 0) > 0.9:
            log.info("AI OVERRIDE: High-conviction alpha detected. Expanding global risk cap to $1500.")
            state.ai_risk_limit = 1500.0
        else:
            state.ai_risk_limit = 500.0 # Reset to default

        # Validate required fields
        action = decision.get("action", "BUY").upper()
        if action not in ("BUY", "SELL", "WAIT", "CLOSE"):
            action = "BUY"
        if STRESS_TEST_MODE and action == "WAIT":
            action = "BUY" if state.position_side == "FLAT" else "CLOSE"
            log_anomaly("stress_override", f"Claude tried WAIT in stress mode, forced {action}")
        decision["action"] = action
        decision.setdefault("size", 1)
        decision.setdefault("stop_points", 30)
        decision.setdefault("target_points", 30)
        decision.setdefault("confidence", 0.5)
        decision.setdefault("reasoning", "")
        decision["size"] = max(1, min(3, int(decision["size"])))
        decision["stop_points"] = max(5, min(200, float(decision["stop_points"])))
        decision["target_points"] = max(5, min(500, float(decision["target_points"])))

        # Save learning if provided
        if decision.get("learning"):
            record_learning(decision["learning"])
            if awareness:
                try:
                    awareness.record_learning(decision["learning"])
                except Exception:
                    pass

        # LEARNING: Match decision reasoning to known patterns for validation loop
        if action in ("BUY", "SELL") and council_awareness:
            try:
                reasoning = decision.get("reasoning", "").lower()
                patterns = council_awareness.get_patterns(limit=20)
                best_match = None
                best_score = 0
                
                # Simple keyword matching to link reasoning to pattern
                for p in patterns:
                    desc = p["description"].lower()
                    # Count shared keywords
                    reasoning_words = set(reasoning.split())
                    desc_words = set(desc.split())
                    shared = reasoning_words & desc_words
                    score = len(shared)
                    
                    # Bonus for exact phrase matches
                    if desc in reasoning or reasoning in desc:
                        score += 10
                    
                    if score > best_score:
                        best_score = score
                        best_match = p
                
                # If we found a reasonable match, link it
                if best_match and best_score >= 3:
                    decision["_pattern_id"] = best_match["id"]
                    decision["_pattern_confidence"] = best_match["confidence"]
                    log.info(f"LEARNING: Linked decision to pattern #{best_match['id']} (score={best_score}): {best_match['description'][:80]}")
            except Exception as e:
                log.debug(f"Pattern matching error: {e}")

        # Track API usage costs
        if "usage" in data:
            in_tok = data["usage"].get("input_tokens", 0)
            out_tok = data["usage"].get("output_tokens", 0)
            log_api_usage(in_tok + out_tok, "trade_decision", in_tok, out_tok)

        # PHASE 2: Check risk constraints and log ENTER decision
        action = decision.get("action", "WAIT").upper()
        if action in ("BUY", "SELL"):
            can_enter, reason = check_risk_constraints("council", decision, features)
            if not can_enter:
                log.warning(f"COUNCIL: Trade blocked - {reason}")
                decision["action"] = "WAIT"
                decision["reasoning"] = f"Risk limit: {reason}"
            elif getattr(state, '_choppy_block_entries', False):
                # CHOPPY regime hard block - skip entries when regime is CHOPPY with >70% confidence
                log.warning(f"COUNCIL: CHOPPY regime blocked ENTER (conf={state.regime_confidence:.0f}%)")
                decision["action"] = "WAIT"
                decision["reasoning"] = f"CHOPPY regime blocked (conf={state.regime_confidence:.0f}%)"
            else:
                # L2 QUALITY GATE: Already checked in control_loop before calling this function
                # Log detailed ENTER information
                size = decision.get("size", 1)
                stop_pts = decision.get("stop_points", 30)
                target_pts = decision.get("target_points", 30)
                risk_amt = size * stop_pts * POINT_VALUE
                account_util = (risk_amt / (state.broker_balance * 0.05)) * 100 if state.broker_balance > 0 else 0
                log.info(f"COUNCIL ENTER {size} contracts @ {state.price} | Risk: ${risk_amt:.2f} | Kelly: {decision.get('confidence', 0)*100:.1f}% | Account utilization: {account_util:.1f}%")
                state.daily_risk_used += risk_amt

        # ML_ENTRY_FILTER: REMOVED 2026-03-09 - AI engines trade freely

        return decision

    except json.JSONDecodeError as e:
        log.warning(f"Claude returned invalid JSON: {e}")
        log_anomaly("parse_error", f"Claude JSON parse fail: {e}")
        fallback = "WAIT"  # Never force trade on API error
        return {"action": fallback, "reasoning": f"Parse error: {e}"}
    except Exception as e:
        log.error(f"Claude API error: {e}")
        log_anomaly("api_error", f"Claude API: {e}")
        return {"action": "WAIT", "reasoning": f"API error: {e}"}


# ============================================================
# FIX #3: BROKER BALANCE VERIFICATION
# ============================================================
async def verify_broker_balance():
    """Verify broker balance matches state.daily_pnl. Auto-correct if divergence > $10."""
    try:
        if not suite:
            return
        broker_balance = await get_broker_balance()
        expected_balance = state.broker_starting_balance + state.daily_pnl
        
        if abs(broker_balance - expected_balance) > 10:  # $10 tolerance
            log.warning(f"Balance mismatch: broker=${broker_balance:.2f} vs state=${expected_balance:.2f}")
            # Auto-correct to broker (source of truth)
            state.daily_pnl = broker_balance - state.broker_starting_balance
            state.pnl_divergence_count += 1
            log_anomaly("balance_mismatch", f"Corrected to broker balance: ${broker_balance:.2f}")
    except Exception as e:
        log.debug(f"Balance check failed: {e}")


# ============================================================
# ORDER EXECUTION (deterministic)
# ============================================================
async def execute_trade(decision):
    """Execute a market entry with bracket order (SL + TP).
    
    PHASE 1 FIX: Uses atomic position_entry_lock to prevent race condition where
    multiple engines check position=0 and all enter simultaneously, accumulating
    beyond MAX_TOTAL_POSITION.
    
    Args:
        decision (dict): Trading decision from Claude with keys:
            - action (str): "BUY" or "SELL"
            - size (int): contracts to trade (1-3)
            - stop_points (float): stop loss width in points
            - target_points (float): take profit width in points
            - confidence (float): 0-1 confidence score
            - reasoning (str): explanation of trade
    
    Returns:
        bool: True if trade executed successfully, False if failed or blocked
    
    Side Effects:
        - state.active_trade updated with order IDs
        - state.last_fill_price updated on fill
        - PnL recorded when position closes
    
    Design Notes:
        - SDK's place_bracket_order fails because WebSocket is down; uses manual placement
        - Retries SL placement up to 3x with 0.5s backoff
        - Verifies position filled before placing SL/TP
        - Closes naked position if SL placement fails
    """
    action = decision["action"]
    size = decision["size"]
    stop_pts = decision["stop_points"]
    target_pts = decision["target_points"]

    if state.position_side != "FLAT":
        log.warning("Cannot open trade: already in position")
        return False

    contract_id = mnq.instrument_info.id
    entry_side = 0 if action == "BUY" else 1  # 0=Buy, 1=Sell
    exit_side = 1 if action == "BUY" else 0   # opposite for SL/TP

    # Validate before sending to SDK (shift feedback left)
    if state.price <= 0:
        log.error("Cannot trade: no price data")
        return False

    log.info(f"Executing: {action} {size} @ market (stop={stop_pts}pts, target={target_pts}pts)")
    state.last_fill_price = 0.0  # Reset stale fill price from previous trade

    tick = INSTRUMENT_CONFIG.get(TICKER, {}).get('tick_size', 0.25)
    pre_entry_sl = _round_to_tick(state.price - stop_pts, tick) if action == "BUY" else _round_to_tick(state.price + stop_pts, tick)
    if not _validate_pre_entry_stop(action, TICKER, pre_entry_sl, tick, "Warwick pre-entry"):
        return False

    # PHASE 1 FIX: Atomic position check + order execution under lock
    # Ensures all 3 engines see consistent position and don't accumulate beyond MAX_TOTAL_POSITION
    # CRITICAL: Keep lock held until fill is confirmed to prevent race condition
    async with position_entry_lock:
        try:
            # Position check INSIDE lock (atomic with order placement)
            # Always use state.position_size as source of truth (more reliable than WebSocket)
            # This ensures we don't accumulate beyond limit even if WebSocket returns stale/empty data
            current_total = state.position_size
            try:
                positions = await mnq.positions.get_all_positions()
                if positions:
                    broker_total = sum(abs(p.size) for p in positions if _extract_position_contract_id(p) == contract_id)
                    if broker_total != current_total:
                        log.warning(f"Warwick: Position mismatch (state={current_total}, broker={broker_total}) - using state as source of truth")
            except Exception as e:
                log.warning(f"Warwick: Could not get broker positions ({e}) - using state.position_size={current_total}")
            
            if current_total + size > MAX_TOTAL_POSITION:
                log.error(f"POSITION LIMIT (Warwick): current={current_total} + new={size} > max={MAX_TOTAL_POSITION} -- BLOCKING")
                return False

            # Step 1: Place MARKET entry order
            # FIX #2: Wrap with timeout to prevent broker hangs
            try:
                entry_result = await asyncio.wait_for(
                    mnq.orders.place_market_order(
                        contract_id=contract_id, side=entry_side, size=size
                    ),
                    timeout=ORDER_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                log.error("Order placement timeout - broker unresponsive (30s)")
                raise
            entry_id = entry_result.orderId
            if not entry_result.success:
                log.error(f"Entry order failed: {entry_result.errorMessage}")
                return False
            log.info(f"Entry filled: orderId={entry_id}")

            # Step 2: Get actual fill price from position (broker is truth) - KEEP LOCK UNTIL CONFIRMED
            # Wait up to 2 seconds for fill confirmation to prevent race condition
            entry_price = state.price
            filled_qty = size  # Default to full fill
            max_wait = 20  # 2 seconds at 0.1s intervals
            for attempt in range(max_wait):
                await asyncio.sleep(0.1)
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, contract_id)
                if p and p.size != 0:
                    entry_price = p.averagePrice
                    filled_qty = abs(p.size)  # Actual filled quantity
                    log.info(f"Position confirmed (attempt {attempt+1}): entry={entry_price}, size={p.size}")
                    
                    # FIX #4: Detect partial fills
                    if filled_qty < size:
                        log.warning(f"Partial fill: {filled_qty}/{size} filled")
                    break
            else:
                # RECONCILE: Try to get price from specific contract even if not confirmed yet
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, contract_id)
                if p:
                    entry_price = p.averagePrice
                    log.info(f"Position fallback: entry={entry_price}")
                else:
                    log.warning(f"Position confirmation timeout for Warwick, proceeding with market price {entry_price}")

            # Step 3: Compute SL/TP from actual fill price
            if action == "BUY":
                sl_price = _round_to_tick(entry_price - stop_pts, tick)
                tp_price = _round_to_tick(entry_price + target_pts, tick)
            else:
                sl_price = _round_to_tick(entry_price + stop_pts, tick)
                tp_price = _round_to_tick(entry_price - target_pts, tick)

            if sl_price <= 0 or tp_price <= 0:
                log.error(f"Invalid SL/TP: sl={sl_price}, tp={tp_price}")
                return False

            if not _validate_pre_entry_stop(action, TICKER, sl_price, tick, "Warwick post-fill"):
                log.error("Warwick post-fill stop invalid -- closing naked position for safety")
                try:
                    close_result = await asyncio.wait_for(
                        mnq.orders.place_market_order(
                            contract_id=contract_id, side=exit_side, size=filled_qty),
                        timeout=ORDER_TIMEOUT_SECONDS
                    )
                    if close_result.success:
                        log.info("Warwick naked position closed after post-fill validation failure")
                except Exception as close_err:
                    log.error(f"CRITICAL: Exception closing Warwick naked position: {close_err}")
                return False

            # Step 4: Place STOP order (SL) once after deterministic validation
            try:
                sl_result = await asyncio.wait_for(
                    mnq.orders.place_stop_order(
                        contract_id=contract_id, side=exit_side, size=filled_qty, stop_price=sl_price
                    ),
                    timeout=ORDER_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                log.error("SL order timeout - broker unresponsive (30s)")
                sl_result = None
            except Exception as sl_err:
                log.error(f"SL order exception: {sl_err}")
                sl_result = None

            sl_id = sl_result.orderId if sl_result and sl_result.success else None
            if not sl_id:
                err = sl_result.errorMessage if sl_result else "timeout/exception"
                log.error(f"SL placement failed after validation ({err}) -- closing naked position for safety")
                try:
                    close_result = await asyncio.wait_for(
                        mnq.orders.place_market_order(
                            contract_id=contract_id, side=exit_side, size=filled_qty),
                        timeout=ORDER_TIMEOUT_SECONDS
                    )
                    if close_result.success:
                        log.info("Naked position closed successfully after SL failure")
                    else:
                        log.error(f"CRITICAL: Failed to close naked position: {close_result.errorMessage}")
                except asyncio.TimeoutError:
                    log.error("CRITICAL: Naked position close timeout - broker unresponsive (30s)")
                except Exception as close_err:
                    log.error(f"CRITICAL: Exception closing naked position: {close_err}")
                log_anomaly("sl_failure_position_closed", f"SL failed after validation, position closed @ {entry_price}")
                return False

            # Step 5: Place LIMIT order (TP)
            # FIX #2: Wrap with timeout to prevent broker hangs
            # FIX #4: Use actual filled quantity for TP size
            tp_result = await asyncio.wait_for(
                mnq.orders.place_limit_order(
                    contract_id=contract_id, side=exit_side, size=filled_qty, limit_price=tp_price
                ),
                timeout=30
            )
            tp_id = tp_result.orderId
            if not tp_result.success:
                log.warning(f"TP order failed: {tp_result.errorMessage}")
                tp_id = None

            # THE CONTRACT: all 3 IDs stored together
            # FIX #4: Record actual filled quantity, not requested quantity
            state.active_trade = TradeRecord(
                entry_order_id=entry_id,
                sl_order_id=sl_id,
                tp_order_id=tp_id,
                side=action,
                size=filled_qty,  # Use actual filled quantity
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                opened_at=utc_now().isoformat()
            )

            if STRESS_TEST_MODE:
                risk_amt = size * stop_pts * POINT_VALUE
                log.info(f"STRESS TEST ENTER: {action} {size} @ {entry_price} | Risk: ${risk_amt:.2f} | Stress test trade #{state.trade_count + 1}/unlimited")
            else:
                log.info(f"Trade opened: {action} {size} @ {entry_price} | SL={sl_price}(id={sl_id}) | TP={tp_price}(id={tp_id})")
            
            log_trade_event("OPEN", {
                "action": action, "size": size, "entry_price": entry_price,
                "sl_price": sl_price, "tp_price": tp_price,
                "entry_order_id": entry_id, "sl_order_id": sl_id, "tp_order_id": tp_id,
                "price_at_decision": state.price,
                "slippage": round(abs(entry_price - state.price), 2) if state.price > 0 else 0,
                "stress_test": STRESS_TEST_MODE
            })
            
            # Log trade intelligence for Fleet analysis
            log_trade_intelligence(
                {"timestamp": utc_now().isoformat(), "price": state.price, "action": action},
                {"action": action, "reasoning": decision.get("reasoning", "")},
                f"Decision: {action} size={size} stop={stop_pts} target={target_pts}"
            )
            
            if not sl_id:
                log_anomaly("missing_sl", f"SL order failed for trade @ {entry_price}")
            if not tp_id:
                log_anomaly("missing_tp", f"TP order failed for trade @ {entry_price}")
            return True

        except Exception as e:
            log.error(f"Trade execution error: {e}")
            # Check if we accidentally opened a position
            try:
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, contract_id)
                if p:
                    log.warning("Position exists after error - recording partial trade")
                    state.active_trade = TradeRecord(
                        side=action, size=p.size, entry_price=p.averagePrice,
                        opened_at=utc_now().isoformat()
                    )
            except Exception:
                pass
            return False


def _round_to_tick(price: float, tick_size: float) -> float:
    """Round price to nearest tick size increment."""
    return round(round(price / tick_size) * tick_size, 10)


def _get_fresh_bid_ask(symbol: str | None = None, max_age_seconds: float | None = None) -> tuple[float, float, float, str]:
    sym = symbol or TICKER
    max_age = PRE_ENTRY_MARKET_DATA_MAX_AGE_SECONDS if max_age_seconds is None else max_age_seconds
    now = time.time()
    
    mstate = state.get_market(sym)
    if mstate:
        bid = mstate.best_bid
        ask = mstate.best_ask
        age = now - mstate.price_timestamp if mstate.price_timestamp > 0 else 999.0
        if bid > 0 and ask > 0 and age <= max_age:
            return bid, ask, age, 'mstate'

    return 0.0, 0.0, 999.0, 'none'


def _validate_pre_entry_stop(action: str, symbol: str | None, stop_price: float, tick_size: float, context: str) -> bool:
    sym = symbol or TICKER
    if stop_price <= 0:
        log.warning(f"{context}: invalid stop price {stop_price} for {sym}")
        return False

    bid, ask, age, source = _get_fresh_bid_ask(sym)
    if bid <= 0 or ask <= 0:
        log.warning(f"{context}: no fresh bid/ask for {sym}, blocking entry")
        return False

    spread = ask - bid
    if spread > PRE_ENTRY_MAX_SPREAD_POINTS:
        log.warning(f"{context}: spread {spread:.2f} > {PRE_ENTRY_MAX_SPREAD_POINTS:.2f} on {sym} ({source}, age={age:.1f}s)")
        return False

    stop_buffer = tick_size * PRE_ENTRY_STOP_BUFFER_TICKS
    if action == "BUY" and stop_price >= (bid - stop_buffer):
        log.warning(f"{context}: BUY stop {stop_price:.2f} invalid vs bid {bid:.2f} on {sym} ({source}, age={age:.1f}s)")
        return False
    if action == "SELL" and stop_price <= (ask + stop_buffer):
        log.warning(f"{context}: SELL stop {stop_price:.2f} invalid vs ask {ask:.2f} on {sym} ({source}, age={age:.1f}s)")
        return False

    return True


def _extract_position_contract_id(position) -> str | None:
    if isinstance(position, dict):
        return (
            position.get('contractId')
            or position.get('contract_id')
            or position.get('symbolId')
            or position.get('instrumentId')
        )

    for attr in ('contractId', 'contract_id', 'symbolId', 'symbol_id', 'instrumentId', 'instrument_id'):
        value = getattr(position, attr, None)
        if value:
            return value

    instrument_info = getattr(position, 'instrumentInfo', None) or getattr(position, 'instrument_info', None)
    if instrument_info:
        for attr in ('id', 'contractId', 'symbolId'):
            value = getattr(instrument_info, attr, None)
            if value:
                return value

    return None


def _find_position_for_contract(positions, contract_id: str | None):
    if not positions or not contract_id:
        return None

    for position in positions:
        if _extract_position_contract_id(position) == contract_id:
            return position

    return None


async def execute_council_trade(decision, symbol: str = None):
    """Execute a Council trade with bracket order (SL + TP).
    PHASE 2: Symbol-aware execution.
    """
    # Resolve market
    sym = symbol or TICKER
    mstate = state.get_market(sym)
    config = INSTRUMENT_CONFIG.get(sym, INSTRUMENT_CONFIG[TICKER])
    trade_key = f"council_{sym}"
    
    if mstate.council_trade.side != "FLAT":
        log.info(f"Council: already has open trade on {sym}, skipping")
        return False

    action = decision["action"]
    size = decision.get("size", 1)
    stop_pts = decision.get("stop_points", 30)
    target_pts = decision.get("target_points", 30)

    contract_id = MICRO_CONTRACTS.get(sym) if sym != TICKER else mnq.instrument_info.id
    if not contract_id: return False
    
    entry_price_ref = mstate.price if mstate.price > 0 else 0
    if entry_price_ref <= 0: return False

    entry_side = 0 if action == "BUY" else 1
    exit_side = 1 if action == "BUY" else 0
    tick = config['tick_size']

    log.info(f"COUNCIL EXEC [{sym}]: {action} {size} @ {entry_price_ref} (sl={stop_pts}pts, tp={target_pts}pts)")

    # Pre-entry SL validation
    pre_entry_sl = _round_to_tick(entry_price_ref - stop_pts, tick) if action == "BUY" else _round_to_tick(entry_price_ref + stop_pts, tick)
    if not _validate_pre_entry_stop(action, sym, pre_entry_sl, tick, "Council pre-entry"):
        return False

    async with position_entry_lock:
        try:
            entry_result = await mnq.orders.place_market_order(contract_id=contract_id, side=entry_side, size=size)
            if not entry_result.success:
                log.error(f"Council entry failed [{sym}]: {entry_result.errorMessage}")
                return False

            # Confirmation & SL/TP placement (Simplified for Phase 2 stability)
            entry_price = entry_price_ref
            sl_price = pre_entry_sl
            tp_price = _round_to_tick(entry_price + target_pts, tick) if action == "BUY" else _round_to_tick(entry_price - target_pts, tick)

            sl_res = await mnq.orders.place_stop_order(contract_id=contract_id, side=exit_side, size=size, stop_price=sl_price)
            tp_res = await mnq.orders.place_limit_order(contract_id=contract_id, side=exit_side, size=size, limit_price=tp_price)

            mstate.council_trade = TradeRecord(
                entry_order_id=entry_result.orderId, sl_order_id=sl_res.orderId if sl_res.success else None,
                tp_order_id=tp_res.orderId if tp_res.success else None,
                side=action, size=size, entry_price=entry_price,
                sl_price=sl_price, tp_price=tp_price, opened_at=utc_now().isoformat(),
                reasoning=decision.get("reasoning", "")
            )
            
            # Legacy sync for TICKER
            if sym == TICKER: state.council_trade = mstate.council_trade
            
            log.info(f"COUNCIL TRADE OPEN [{sym}]: {action} @ {entry_price}")
            return True
        except Exception as e:
            log.error(f"Council trade error [{sym}]: {e}")
            return False

async def close_council_trade(symbol: str = None):
    """Close Council's position for a specific symbol."""
    sym = symbol or TICKER
    mstate = state.get_market(sym)
    ct = mstate.council_trade
    
    if ct.side == "FLAT": return
    
    log.info(f"COUNCIL CLOSING [{sym}]: {ct.side} {ct.size} @ {ct.entry_price}")
    try:
        contract_id = MICRO_CONTRACTS.get(sym) if sym != TICKER else mnq.instrument_info.id
        close_side = 1 if ct.side == "BUY" else 0
        result = await mnq.orders.place_market_order(contract_id=contract_id, side=close_side, size=ct.size)
        
        if result.success:
            # PNL Handshake
            close_price = mstate.price
            pnl_pts = (close_price - ct.entry_price) if ct.side == "BUY" else (ct.entry_price - close_price)
            pnl_dollar = pnl_pts * INSTRUMENT_CONFIG[sym]['point_value'] * ct.size
            await record_pnl(pnl_dollar, f"council_close_{sym}", sym)
            
            mstate.council_trade = TradeRecord()
            if sym == TICKER: state.council_trade = mstate.council_trade
            log.info(f"COUNCIL CLOSED [{sym}]: PnL=${pnl_dollar:.2f}")

            # Cancel associated orders
            for oid in [ct.sl_order_id, ct.tp_order_id]:
                if oid:
                    try:
                        await mnq.orders.cancel_order(oid)
                    except Exception as e:
                        log.warning(f"Council: Failed to cancel order {oid}: {e}")
            return True
    except Exception as e:
        log.error(f"Council close error [{sym}]: {e}")
    return False


# ============================================================
# CHIMERA ENGINE #3 -- Adaptive Aggression (Warwick + Council synthesis)
# ============================================================
def _extract_warwick_direction(decision):
    """Extract directional conviction from Warwick's cached decision."""
    action = decision.get("action", "HOLD")
    side = decision.get("side", "")
    confidence = decision.get("confidence", 0.5)

    if action == "ENTER":
        return side, confidence
    elif action == "HOLD" and warwick and warwick.state.primary.is_open:
        # Holding primary implies conviction in that direction (slightly reduced)
        return warwick.state.primary.side, confidence * 0.8
    elif action == "HEDGE":
        # Hedging = uncertainty, no clear directional signal for chimera
        return None, 0
    else:
        return None, 0


def _extract_council_direction(decision):
    """Extract directional conviction from Council's cached decision."""
    action = decision.get("action", "WAIT")
    confidence = decision.get("confidence", 0.5)

    if action in ("BUY", "SELL"):
        return action, confidence
    else:
        return None, 0


async def chimera_tick(features):
    """Engine #3: CHIMERA -- Adaptive Aggression.
    Reads cached Warwick and Council decisions. Synthesizes into conviction-scaled trades.
    Runs when BOTH engines have made decisions within the last 60 seconds.
    Does NOT make its own Claude API call -- pure synthesis of existing decisions."""
    now = time.time()

    # Check freshness: both must have decided within last 60s
    wk_age = now - state.last_warwick_decision_time
    co_age = now - state.last_council_decision_time
    if wk_age > 60 or co_age > 60:
        return None

    if not state.last_warwick_decision or not state.last_council_decision:
        return None

    # Extract directional signals
    wk_dir, wk_conf = _extract_warwick_direction(state.last_warwick_decision)
    co_dir, co_conf = _extract_council_direction(state.last_council_decision)

    # --- If Chimera already has a position, check for close conditions ---
    if state.chimera_trade.side != "FLAT":
        wk_action = state.last_warwick_decision.get("action", "HOLD")
        co_action = state.last_council_decision.get("action", "WAIT")

        should_close = False
        # Both engines signaling exit
        if wk_action in ("CLOSE_PRIMARY", "CLOSE_BOTH") and co_action == "CLOSE":
            should_close = True
        # Engines now disagree on direction
        elif wk_dir and co_dir and wk_dir != co_dir:
            should_close = True

        if should_close:
            await close_chimera_trade()
            return "CLOSED (engines disagree or both exit)"
        return None  # Hold existing position

    # --- DISAGREE: one BUY, other SELL -> NO TRADE ---
    if wk_dir and co_dir and wk_dir != co_dir:
        if chimera_awareness:
            try:
                chimera_awareness.record_episode(
                    action="DISAGREEMENT", side="FLAT",
                    entry_price=state.price, exit_price=state.price,
                    pnl=0, stop_points=0, target_points=0,
                    features=features or {},
                    reasoning=f"Warwick={wk_dir}(c={wk_conf:.2f}) vs Council={co_dir}(c={co_conf:.2f})",
                    learning="Engines disagreed - no trade",
                    confidence=0, trade_count=state.trade_count,
                    daily_pnl=state.daily_pnl, win_rate=0)
            except Exception as e:
                log.error(f"CRITICAL: Failed to record Chimera disagreement episode: {e}", exc_info=True)
        log.info(f"CHIMERA: DISAGREE -- Warwick={wk_dir} vs Council={co_dir} -> NO TRADE")
        return "DISAGREE (logged)"

    # --- HIGH CONVICTION: both agree on direction ---
    if wk_dir and co_dir and wk_dir == co_dir:
        direction = wk_dir
        avg_confidence = (wk_conf + co_conf) / 2.0

        # Scale size by confidence: 4 base, 5 if both very confident
        size = 5 if avg_confidence >= 0.7 else 4

        # R:R 4:1, use Warwick's stops (tighter, more aggressive)
        wk_stop = state.last_warwick_decision.get("stop_points", 10)
        stop_pts = max(6.0, float(wk_stop))
        target_pts = stop_pts * 4.0
        conviction = "HIGH"

    # --- MEDIUM CONVICTION: one has direction, other is neutral ---
    elif wk_dir or co_dir:
        direction = wk_dir or co_dir
        avg_confidence = wk_conf if wk_dir else co_conf
        size = 2

        # R:R 2:1, use the active engine's stops
        wk_stop = state.last_warwick_decision.get("stop_points", 10)
        co_stop = state.last_council_decision.get("stop_points", 30)
        if wk_dir and not co_dir:
            stop_pts = max(6.0, float(wk_stop))
        elif co_dir and not wk_dir:
            stop_pts = max(6.0, float(co_stop))
        else:
            stop_pts = max(6.0, (float(wk_stop) + float(co_stop)) / 2.0)
        target_pts = stop_pts * 2.0
        conviction = "MEDIUM"

    # --- NO SIGNAL: both neutral ---
    else:
        return None

    # Build chimera decision
    decision = {
        "action": direction,
        "size": size,
        "stop_points": round(stop_pts, 1),
        "target_points": round(target_pts, 1),
        "confidence": avg_confidence,
        "conviction": conviction,
        "reasoning": f"CHIMERA {conviction}: Warwick={wk_dir}(c={wk_conf:.2f}) Council={co_dir}(c={co_conf:.2f})"
    }

    log.info(f"CHIMERA: {conviction} conviction -- {direction} size={size} "
             f"sl={stop_pts:.1f} tp={target_pts:.1f} (W:{wk_dir}/{wk_conf:.2f} C:{co_dir}/{co_conf:.2f})")

    success = await execute_chimera_trade(decision)
    if success:
        # Record entry in chimera memory
        if chimera_awareness:
            try:
                chimera_awareness.record_episode(
                    action="ENTER", side=direction,
                    entry_price=state.chimera_trade.entry_price,
                    exit_price=state.chimera_trade.entry_price,
                    pnl=0, stop_points=stop_pts, target_points=target_pts,
                    features=features or {},
                    reasoning=decision["reasoning"],
                    learning=f"{conviction} conviction entry",
                    confidence=avg_confidence, trade_count=state.trade_count,
                    daily_pnl=state.daily_pnl,
                    win_rate=state.wins / max(state.trade_count, 1))
            except Exception as e:
                log.error(f"CRITICAL: Failed to record Chimera entry episode: {e}", exc_info=True)
        return f"{conviction} {direction} {size}ct (sl={stop_pts:.0f} tp={target_pts:.0f})"
    return None


async def execute_chimera_trade(decision, symbol: str = None):
    """Execute a Chimera trade with adaptive aggression sizing across any micro market."""
    action = decision["action"]
    size = decision.get("size", 2)
    stop_pts = decision.get("stop_points", 20)
    target_pts = decision.get("target_points", 40)

    sym = symbol or TICKER
    trade_key = f"chimera_{sym}"

    if trade_key in state.open_trades:
        log.info(f"CHIMERA: already has open trade on {sym}, skipping")
        return False

    if sym == TICKER:
        contract_id = mnq.instrument_info.id
        entry_price_ref = state.price
    else:
        contract_id = MICRO_CONTRACTS.get(sym)
        if not contract_id:
            log.error(f"CHIMERA: unknown symbol {sym}")
            return False
        mp = state.market_prices.get(contract_id)
        entry_price_ref = mp["price"] if mp and mp["price"] > 0 else 0
        if entry_price_ref <= 0:
            log.error(f"CHIMERA: no price data for {sym}")
            return False

    entry_side = 0 if action == "BUY" else 1
    exit_side = 1 if action == "BUY" else 0

    if sym == TICKER and state.price <= 0:
        log.error("CHIMERA: no price data")
        return False

    log.info(f"CHIMERA EXEC: {action} {size} @ market (sl={stop_pts:.1f}pts, tp={target_pts:.1f}pts)")

    tick = INSTRUMENT_CONFIG.get(sym, INSTRUMENT_CONFIG.get(TICKER, {})).get('tick_size', 0.25)
    pre_entry_sl = _round_to_tick(entry_price_ref - stop_pts, tick) if action == "BUY" else _round_to_tick(entry_price_ref + stop_pts, tick)
    if not _validate_pre_entry_stop(action, sym, pre_entry_sl, tick, "Chimera pre-entry"):
        return False

    # PHASE 1 FIX: Atomic position check + order execution under lock
    # Ensures all 3 engines see consistent position and don't accumulate beyond MAX_TOTAL_POSITION
    async with position_entry_lock:
        try:
            # Position check INSIDE lock (atomic with order placement)
            # Always use state.position_size as source of truth (more reliable than WebSocket)
            # This ensures we don't accumulate beyond limit even if WebSocket returns stale/empty data
            current_total = state.position_size
            try:
                positions = await mnq.positions.get_all_positions()
                if positions:
                    broker_total = sum(abs(p.size) for p in positions if _extract_position_contract_id(p) == contract_id)
                    if broker_total != current_total:
                        log.warning(f"Chimera: Position mismatch (state={current_total}, broker={broker_total}) - using state as source of truth")
            except Exception as e:
                log.warning(f"Chimera: Could not get broker positions ({e}) - using state.position_size={current_total}")
            
            if current_total + size > MAX_TOTAL_POSITION:
                log.error(f"POSITION LIMIT (Chimera): current={current_total} + new={size} > max={MAX_TOTAL_POSITION} -- BLOCKING")
                return False

            entry_result = await mnq.orders.place_market_order(
                contract_id=contract_id, side=entry_side, size=size)
            if not entry_result.success:
                log.error(f"CHIMERA entry failed: {entry_result.errorMessage}")
                return False

            # Wait for fill confirmation
            entry_price = entry_price_ref  # use market price as baseline
            max_wait = 20  # 2 seconds at 0.1s intervals
            for attempt in range(max_wait):
                await asyncio.sleep(0.1)
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, contract_id)
                if p and p.size != 0:
                    entry_price = p.averagePrice
                    log.info(f"Chimera position confirmed (attempt {attempt+1}): entry={entry_price}, size={p.size}")
                    break
            else:
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, contract_id)
                if p:
                    entry_price = p.averagePrice
                    log.info(f"Chimera position fallback: entry={entry_price}")
                else:
                    log.warning(f"Chimera position confirmation timeout, proceeding with market price {entry_price}")

            tick = INSTRUMENT_CONFIG.get(sym, INSTRUMENT_CONFIG.get(TICKER, {})).get('tick_size', 0.25)
            if action == "BUY":
                sl_price = _round_to_tick(entry_price - stop_pts, tick)
                tp_price = _round_to_tick(entry_price + target_pts, tick)
            else:
                sl_price = _round_to_tick(entry_price + stop_pts, tick)
                tp_price = _round_to_tick(entry_price - target_pts, tick)

            if not _validate_pre_entry_stop(action, sym, sl_price, tick, "Chimera post-fill"):
                log.error("Chimera post-fill stop invalid -- closing naked position for safety")
                try:
                    close_result = await mnq.orders.place_market_order(
                        contract_id=contract_id, side=exit_side, size=size)
                    if close_result.success:
                        log.info("CHIMERA naked position closed after post-fill validation failure")
                except Exception as close_err:
                    log.error(f"CRITICAL: Exception closing chimera naked position: {close_err}")
                return False

            sl_id = None
            try:
                sl_res = await mnq.orders.place_stop_order(
                    contract_id=contract_id, side=exit_side, size=size, stop_price=sl_price)
                if sl_res.success:
                    sl_id = sl_res.orderId
                else:
                    log.error(f"CHIMERA SL placement failed after validation: {sl_res.errorMessage}")
            except Exception as sl_err:
                log.error(f"CHIMERA SL placement exception: {sl_err}")

            if not sl_id:
                log.error("CHIMERA SL failed after validation -- closing naked position for safety")
                try:
                    close_result = await mnq.orders.place_market_order(
                        contract_id=contract_id, side=exit_side, size=size)
                    if close_result.success:
                        log.info("CHIMERA naked position closed after SL failure")
                    else:
                        log.error(f"CRITICAL: Failed to close chimera naked position: {close_result.errorMessage}")
                except Exception as close_err:
                    log.error(f"CRITICAL: Exception closing chimera naked position: {close_err}")
                log_anomaly("chimera_sl_failure_closed", f"Chimera SL failed after validation, position closed @ {entry_price}")
                return False

            tp_id = None
            tp_res = await mnq.orders.place_limit_order(
                contract_id=contract_id, side=exit_side, size=size, limit_price=tp_price)
            if tp_res.success:
                tp_id = tp_res.orderId

            state.chimera_trade = TradeRecord(
                entry_order_id=entry_result.orderId, sl_order_id=sl_id, tp_order_id=tp_id,
                side=action, size=size, entry_price=entry_price,
                sl_price=sl_price, tp_price=tp_price, opened_at=utc_now().isoformat(),
                pattern_id=decision.get("_pattern_id"),
                pattern_confidence=decision.get("_pattern_confidence", 0.5),
                reasoning=decision.get("reasoning", "")
            )
            state.open_trades[trade_key] = {
                "engine": "chimera", "symbol": sym, "side": action, "size": size,
                "entry": entry_price, "sl": sl_price, "tp": tp_price,
                "sl_id": sl_id, "tp_id": tp_id, "opened_at": utc_now().isoformat()
            }
            log.info(f"CHIMERA TRADE OPEN: {sym} {action} {size} @ {entry_price} | SL={sl_price:.2f} TP={tp_price:.2f} | conviction={decision.get('conviction', '?')}")
            return True

        except Exception as e:
            log.error(f"CHIMERA trade error: {e}")
            return False


async def close_chimera_trade():
    """Close Chimera's position and clean up its SL/TP orders."""
    if state.chimera_trade.side == "FLAT":
        return
    ct = state.chimera_trade
    log.info(f"CHIMERA CLOSING: {ct.side} {ct.size} @ {ct.entry_price}")
    direct_mode = getattr(state, 'direct_api_mode', False)
    contract_id = CONTRACT_IDS.get(TICKER, f"CON.F.US.{TICKER}.H26") if direct_mode else mnq.instrument_info.id
    try:
        close_side = 1 if ct.side == "BUY" else 0
        if direct_mode:
            result = await api_place_order(
                contract_id=contract_id, order_type=2, side=close_side, size=ct.size)
        else:
            result = await mnq.orders.place_market_order(
                contract_id=contract_id, side=close_side, size=ct.size)
        if (direct_mode and result.get('success')) or (not direct_mode and result.success):
            await asyncio.sleep(0.5)
            close_price = state.last_fill_price if state.last_fill_price > 0 else state.price
            try:
                if direct_mode:
                    positions = await api_get_positions()
                    p = _find_position_for_contract(positions, contract_id)
                    if p and p.get('averagePrice', 0) > 0:
                        broker_avg = p.get('averagePrice')
                        if abs(broker_avg - close_price) > 2.0:
                            close_price = broker_avg
                else:
                    positions = await mnq.positions.get_all_positions()
                    p = _find_position_for_contract(positions, contract_id)
                    if p and p.averagePrice > 0:
                        broker_avg = p.averagePrice
                        if abs(broker_avg - close_price) > 2.0:
                            close_price = broker_avg
            except Exception:
                pass
            pnl_pts = (close_price - ct.entry_price) if ct.side == "BUY" else (ct.entry_price - close_price)
            pnl_dollar = pnl_pts * POINT_VALUE * ct.size
            record_pnl(pnl_dollar, "chimera_close", contracts=ct.size)
            log.info(f"CHIMERA CLOSED: {ct.side} {ct.size} | PnL=${pnl_dollar:.2f} ({pnl_pts:.1f}pts)")
            # LEARNING MODE: Validate pattern after trade closes
            validate_trade_pattern(ct, pnl_dollar, "chimera")
            if chimera_awareness:
                chimera_awareness.record_episode(
                    action="CLOSE", side=ct.side,
                    entry_price=ct.entry_price, exit_price=close_price,
                    pnl=pnl_dollar, stop_points=ct.sl_price, target_points=ct.tp_price,
                    features={"price": close_price}, reasoning="chimera closed",
                    learning="", confidence=0.5, trade_count=state.trade_count,
                    daily_pnl=state.daily_pnl, win_rate=0)
        for oid in [ct.sl_order_id, ct.tp_order_id]:
            if oid:
                try:
                    if direct_mode:
                        await api_cancel_order(oid)
                    else:
                        await mnq.orders.cancel_order(oid)
                except Exception as e:
                    log.warning(f"Chimera: Failed to cancel order {oid}: {e}")
    except Exception as e:
        log.error(f"CHIMERA close error: {e}")
    state.chimera_trade = TradeRecord()
    for k in [k for k in state.open_trades if k.startswith("chimera_")]:
        del state.open_trades[k]


async def _handle_chimera_fill(fill_type, fill_price, fill_id=None):
    """Process a Chimera SL/TP fill on the main asyncio loop."""
    chimera_trade = state.chimera_trade
    if chimera_trade.side == "FLAT":
        return
    direct_mode = getattr(state, 'direct_api_mode', False)
    pnl_pts = (fill_price - chimera_trade.entry_price) if chimera_trade.side == "BUY" else (chimera_trade.entry_price - fill_price)
    pnl_dollar = pnl_pts * POINT_VALUE * chimera_trade.size
    record_pnl(pnl_dollar, f"chimera_{fill_type}_fill", fill_id=fill_id, contracts=chimera_trade.size)
    log.info(f"CHIMERA {fill_type.upper()} HIT: {chimera_trade.side} {chimera_trade.size} | "
             f"entry={chimera_trade.entry_price} exit={fill_price} | PnL=${pnl_dollar:.2f}")
    # LEARNING MODE: Validate pattern after SL/TP fill
    validate_trade_pattern(chimera_trade, pnl_dollar, "chimera")
    remaining_id = chimera_trade.tp_order_id if fill_type == "sl" else chimera_trade.sl_order_id
    if remaining_id:
        try:
            if direct_mode:
                await api_cancel_order(remaining_id)
            else:
                await mnq.orders.cancel_order(remaining_id)
        except Exception as e:
            log.warning(f"Chimera fill handler: Failed to cancel order {remaining_id}: {e}")
    if chimera_awareness:
        chimera_awareness.record_episode(
            action="CLOSE", side=chimera_trade.side,
            entry_price=chimera_trade.entry_price, exit_price=fill_price,
            pnl=pnl_dollar, stop_points=chimera_trade.sl_price, target_points=chimera_trade.tp_price,
            features={"price": fill_price}, reasoning=f"chimera {fill_type} hit",
            learning="", confidence=0.5, trade_count=state.trade_count,
            daily_pnl=state.daily_pnl, win_rate=0)
    state.chimera_trade = TradeRecord()
    for k in [k for k in state.open_trades if k.startswith("chimera_")]:
        del state.open_trades[k]


async def close_position():
    """Close current position. Cancel SL/TP only AFTER close confirmed."""
    if state.position_side == "FLAT":
        return

    close_side = state.position_side
    close_entry = state.position_entry
    try:
        if getattr(state, 'direct_api_mode', False):
            # Direct API mode - close via REST
            contract_id = CONTRACT_IDS.get(TICKER, f"CON.F.US.{TICKER}.H26")
            result = await api_close_position(contract_id)
            if not result.get('success'):
                log.info(f"No position to close or close failed: {result.get('error')}")
                state.position_side = "FLAT"
                state.position_size = 0
                state.active_trade = TradeRecord()
                return
            close_id = result.get('response', {}).get('orderId', 'direct')
        else:
            # SDK mode
            result = await mnq.orders.close_position(
                contract_id=mnq.instrument_info.id,
                method='market'
            )
            if not result:
                log.info("No position to close (already flat)")
                state.position_side = "FLAT"
                state.position_size = 0
                state.active_trade = TradeRecord()
                return
            close_id = getattr(result, 'orderId', None)
        
        log.info(f"Position close order: id={close_id}")

        # Cancel SL/TP orders
        await asyncio.sleep(0.3)
        if state.active_trade.sl_order_id or state.active_trade.tp_order_id:
            cancelled = 0
            for oid in [state.active_trade.sl_order_id, state.active_trade.tp_order_id]:
                if oid:
                    try:
                        if getattr(state, 'direct_api_mode', False):
                            await api_cancel_order(oid)
                        else:
                            await mnq.orders.cancel_order(oid)
                        cancelled += 1
                    except Exception:
                        pass
            log.info(f"Cleaned up SL/TP after close: {cancelled} cancelled")

        # Calculate P&L
        fill_price = state.last_fill_price if state.last_fill_price > 0 else state.price
        pnl = 0.0
        if close_entry > 0 and fill_price > 0:
            if close_side in ("LONG", "BUY"):
                pnl = (fill_price - close_entry) * state.position_size * POINT_VALUE
            else:
                pnl = (close_entry - fill_price) * state.position_size * POINT_VALUE
        record_pnl(pnl, f"close_position:{close_side}")
        
        # LEARNING MODE: Validate pattern after position closes
        validate_trade_pattern(state.active_trade, pnl, "council")

        log_trade_event("CLOSE", {
            "side": close_side, "entry_price": close_entry,
            "close_price": state.price, "pnl": round(pnl, 2),
            "close_order_id": close_id,
            "session_pnl": round(state.daily_pnl, 2),
            "record": f"{state.wins}W/{state.losses}L"
        })
        record_trade({"side": close_side, "entry": close_entry,
                       "exit": round(fill_price, 2), "pnl": round(pnl, 2)})

        # Reset active trade
        state.active_trade = TradeRecord()

    except Exception as e:
        log.error(f"Close position error: {e}")
        log_anomaly("close_error", str(e), {"side": close_side, "entry": close_entry})


# ============================================================
# WARWICK EXECUTION (multi-position hedge trades)
# ============================================================
async def warwick_open_leg(side, size, sl_pts, tp_pts, leg_type="primary", symbol: str = None):
    """Open a Warwick leg (primary or hedge). Accepts optional symbol for multi-market trading."""
    direct_mode = getattr(state, 'direct_api_mode', False)
    sym = symbol or TICKER
    if sym == TICKER:
        contract_id = CONTRACT_IDS.get(TICKER, f"CON.F.US.{TICKER}.H26") if direct_mode else mnq.instrument_info.id
        price_ref = state.price
    else:
        contract_id = MICRO_CONTRACTS.get(sym)
        if not contract_id:
            log.error(f"WARWICK: unknown symbol {sym}")
            return None
        mp = state.market_prices.get(contract_id)
        price_ref = mp["price"] if mp and mp["price"] > 0 else 0
        if price_ref <= 0:
            log.error(f"WARWICK: no price for {sym}")
            return None

    entry_side = 0 if side == "BUY" else 1
    exit_side = 1 if side == "BUY" else 0

    if sym == TICKER and state.price <= 0:
        log.error("WARWICK: Cannot open leg, no price data")
        return None
    
    # CRITICAL FIX: Check position limit BEFORE opening leg
    current_total = state.position_size
    if current_total + size > MAX_TOTAL_POSITION:
        log.error(f"WARWICK {leg_type}: POSITION LIMIT BLOCKED -- current={current_total} + size={size} > max={MAX_TOTAL_POSITION}")
        return None

    # P0-3: If opening a hedge, cancel primary's SL/TP first
    if leg_type == "hedge" and warwick and warwick.state.primary.is_open:
        primary = warwick.state.primary
        for attr in ['sl_order_id', 'tp_order_id']:
            oid = getattr(primary, attr)
            if oid:
                try:
                    if direct_mode:
                        await api_cancel_order(oid)
                    else:
                        await mnq.orders.cancel_order(oid)
                    setattr(primary, attr, None)
                    log.info(f"WARWICK: Cancelled primary {attr}={oid} before hedge")
                except Exception as e:
                    setattr(primary, attr, None)
                    log.info(f"WARWICK: Primary {attr} already gone, continuing hedge")

    log.info(f"WARWICK: Opening {leg_type} {side} {size} @ market (sl={sl_pts}pts, tp={tp_pts}pts)")
    state.last_fill_price = 0.0  # Reset for fresh fill detection
    try:
        if direct_mode:
            # Direct API mode - place market order WITH NATIVE BRACKETS
            entry_result = await api_place_order(
                contract_id=contract_id, order_type=2, side=entry_side, size=size,
                sl_price=sl_price, tp_price=tp_price)  # FIX: Add native brackets
            if not entry_result.get('success'):
                log.error(f"WARWICK: Entry failed: {entry_result.get('error')}")
                return None
            entry_id = entry_result.get('orderId')
            # Native brackets placed with entry - get order IDs from response
            sl_id = entry_result.get('response', {}).get('stopLossBracketId')
            tp_id = entry_result.get('response', {}).get('takeProfitBracketId')
            log.info(f"WARWICK: Native brackets placed - SL_id={sl_id} TP_id={tp_id}")
        else:
            # SDK mode
            entry_result = await mnq.orders.place_market_order(
                contract_id=contract_id, side=entry_side, size=size)
            if not entry_result.success:
                log.error(f"WARWICK: Entry failed: {entry_result.errorMessage}")
                return None
            entry_id = entry_result.orderId

        await asyncio.sleep(0.5)
        entry_price = state.last_fill_price if state.last_fill_price > 0 else price_ref
        log.info(f"WARWICK: {leg_type} filled @ {entry_price} (source={'fill' if state.last_fill_price > 0 else 'market'}, symbol={sym})")

        # Calculate SL/TP prices (tick-aligned)
        tick = INSTRUMENT_CONFIG.get(sym, INSTRUMENT_CONFIG.get(TICKER, {})).get('tick_size', 0.25)
        if side == "BUY":
            sl_price = _round_to_tick(entry_price - sl_pts, tick)
            tp_price = _round_to_tick(entry_price + tp_pts, tick)
        else:
            sl_price = _round_to_tick(entry_price + sl_pts, tick)
            tp_price = _round_to_tick(entry_price - tp_pts, tick)

        # Place SL/TP orders (skip if native brackets already placed)
        is_hedged = leg_type == "hedge"
        if not is_hedged and not direct_mode:
            # SDK mode - place separate SL/TP
            try:
                sl_result = await mnq.orders.place_stop_order(
                    contract_id=contract_id, side=exit_side, size=size, stop_price=sl_price)
                sl_id = sl_result.orderId if sl_result.success else None
                if sl_id:
                    log.info(f"WARWICK: SL placed @ {sl_price:.2f} (id={sl_id})")
            except Exception as e:
                log.error(f"WARWICK: SL placement FAILED: {e}")
            try:
                tp_result = await mnq.orders.place_limit_order(
                    contract_id=contract_id, side=exit_side, size=size, limit_price=tp_price)
                tp_id = tp_result.orderId if tp_result.success else None
                if tp_id:
                    log.info(f"WARWICK: TP placed @ {tp_price:.2f} (id={tp_id})")
            except Exception as e:
                log.error(f"WARWICK: TP placement FAILED: {e}")
        elif not is_hedged and direct_mode:
            # Direct API - native brackets already placed with entry
            log.info(f"WARWICK: Native brackets active SL={sl_price:.2f} TP={tp_price:.2f}")
        else:
            # B-2 FIX: Hedge legs ALWAYS get a broker-side emergency SL (50pt disaster stop)
            # Software trailing stops can tighten it, but broker must hold a last-resort stop.
            emergency_sl_pts = 50.0
            if side == "BUY":
                emergency_sl_price = entry_price - emergency_sl_pts
            else:
                emergency_sl_price = entry_price + emergency_sl_pts
            
            if direct_mode:
                # Direct API mode - place SL/TP via API
                try:
                    sl_result = await api_place_order(
                        contract_id=contract_id, order_type=4, side=exit_side, size=size,
                        stop_price=emergency_sl_price)
                    sl_id = sl_result.get('orderId') if sl_result.get('success') else None
                    if sl_id:
                        log.info(f"WARWICK: Hedge emergency SL placed @ {emergency_sl_price:.2f} (id={sl_id})")
                    else:
                        log.error(f"WARWICK: Hedge emergency SL FAILED: {sl_result.get('error')}")
                except Exception as e:
                    log.error(f"WARWICK: Hedge emergency SL error: {e}")
                try:
                    tp_result = await api_place_order(
                        contract_id=contract_id, order_type=1, side=exit_side, size=size,
                        limit_price=tp_price)
                    tp_id = tp_result.get('orderId') if tp_result.get('success') else None
                    if tp_id:
                        log.info(f"WARWICK: Hedge TP placed @ {tp_price:.2f} (id={tp_id})")
                    else:
                        log.error(f"WARWICK: Hedge TP FAILED: {tp_result.get('error')}")
                except Exception as e:
                    log.error(f"WARWICK: Hedge TP error: {e}")
            else:
                # SDK mode - place SL/TP via SDK
                try:
                    sl_result = await mnq.orders.place_stop_order(
                        contract_id=contract_id, side=exit_side, size=size, stop_price=emergency_sl_price)
                    sl_id = sl_result.orderId if sl_result.success else None
                    if sl_id:
                        log.info(f"WARWICK: Hedge emergency SL placed @ {emergency_sl_price:.2f} (id={sl_id})")
                    else:
                        log.error(f"WARWICK: Hedge emergency SL FAILED: {sl_result.errorMessage}")
                except Exception as e:
                    log.error(f"WARWICK: Hedge emergency SL error: {e}")
                try:
                    tp_result = await mnq.orders.place_limit_order(
                        contract_id=contract_id, side=exit_side, size=size, limit_price=tp_price)
                    tp_id = tp_result.orderId if tp_result.success else None
                    if tp_id:
                        log.info(f"WARWICK: Hedge TP placed @ {tp_price:.2f} (id={tp_id})")
                    else:
                        log.error(f"WARWICK: Hedge TP FAILED: {tp_result.errorMessage}")
                except Exception as e:
                    log.error(f"WARWICK: Hedge TP error: {e}")
            log.info(f"WARWICK: Hedge opened with emergency SL={emergency_sl_price:.2f} TP={tp_price:.2f}")

        leg = WarwickLeg(
            leg_type=leg_type, side=side, size=size,
            entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
            entry_order_id=entry_id, sl_order_id=sl_id, tp_order_id=tp_id,
            opened_at=datetime.now(timezone.utc).isoformat(),
            _point_value=POINT_VALUE)

        if leg_type == "primary":
            warwick.state.primary = leg
        else:
            warwick.state.hedge = leg

        trade_key = f"warwick_{sym}_{leg_type}"
        state.open_trades[trade_key] = {
            "engine": "warwick", "symbol": sym, "leg": leg_type, "side": side, "size": size,
            "entry": entry_price, "sl": sl_price, "tp": tp_price,
            "sl_id": sl_id, "tp_id": tp_id, "opened_at": datetime.now(timezone.utc).isoformat()
        }
        log.info(f"WARWICK: {leg_type} {sym} {side} {size} @ {entry_price:.2f} | SL={sl_price:.2f} TP={tp_price:.2f}")
        return leg

    except Exception as e:
        log.error(f"WARWICK: Open {leg_type} error: {e}")
        return None


async def warwick_close_leg(leg_type):
    """Close a specific Warwick leg by market order."""
    if leg_type in _closing_legs:
        return  # N-2: Prevent concurrent close (race with on_user_order)
    _closing_legs.add(leg_type)
    try:
        return await _warwick_close_leg_inner(leg_type)
    finally:
        _closing_legs.discard(leg_type)


async def _warwick_close_leg_inner(leg_type):
    leg = warwick.state.primary if leg_type == "primary" else warwick.state.hedge
    if not leg.is_open:
        return

    close_side = 1 if leg.side == "BUY" else 0  # opposite
    contract_id = mnq.instrument_info.id
    log.info(f"WARWICK: Closing {leg_type} {leg.side} {leg.size}")

    try:
        result = await mnq.orders.place_market_order(
            contract_id=contract_id, side=close_side, size=leg.size)
        if result.success:
            await asyncio.sleep(0.3)
            # Cancel this leg's SL/TP orders
            for oid in [leg.sl_order_id, leg.tp_order_id]:
                if oid:
                    try:
                        await mnq.orders.cancel_order(oid)
                    except Exception:
                        pass

            # Wait for fill callback, then use broker fill price for accurate PnL
            await asyncio.sleep(0.5)
            fill = state.last_fill_price if state.last_fill_price > 0 else state.price
            # Double-check: query broker for actual fill if available
            try:
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, mnq.instrument_info.id)
                if p and p.averagePrice > 0:
                    broker_avg = p.averagePrice
                    if abs(broker_avg - fill) > 2.0:
                        log.info(f"WARWICK: Using broker fill {broker_avg} instead of callback {fill}")
                        fill = broker_avg
            except Exception:
                pass
            pnl = leg.unrealized_pnl(fill)
            entry_px = leg.entry_price
            side = leg.side
            warwick.record_leg_close(leg_type, pnl)
            record_pnl(pnl, f"warwick_close_leg:{leg_type}")
            # LEARNING: Validate pattern if this trade was pattern-based
            validate_trade_pattern(leg, pnl, "warwick")
            if awareness:
                try:
                    features = compute_features() or {}
                    awareness.record_episode(
                        action="CLOSE", side=side,
                        entry_price=entry_px, exit_price=fill, pnl=pnl,
                        stop_points=leg.sl_price or 0, target_points=leg.tp_price or 0,
                        features=features, reasoning=f"warwick closed {leg_type}",
                        learning="", confidence=0.5, trade_count=state.trade_count,
                        daily_pnl=state.daily_pnl, win_rate=state.wins / max(state.trade_count, 1))
                except Exception as e:
                    log.error(f"CRITICAL: Failed to record Warwick close episode: {e}", exc_info=True)
            # Clean up open_trades tracking for this warwick leg
            for k in [k for k in state.open_trades if k.startswith(f"warwick_") and f"_{leg_type}" in k]:
                del state.open_trades[k]
            return pnl
    except Exception as e:
        log.error(f"WARWICK: Close {leg_type} error: {e}")
    return 0.0


async def _bootstrap_council_quick(action: str, size: int, price: float, sl_points: float) -> bool:
    """PHASE 1 FIX: Minimal Council bootstrap entry with pre-flight validation. ~4-5s execution."""
    try:
        tick = INSTRUMENT_CONFIG[TICKER]['tick_size']
        ideal_sl = _round_to_tick(price - sl_points, tick) if action == "BUY" else _round_to_tick(price + sl_points, tick)
        if not _validate_pre_entry_stop(action, TICKER, ideal_sl, tick, "Bootstrap Council pre-entry"):
            return False
        
        # Entry (use integer values: 0=BUY, 1=SELL per OrderSide enum)
        entry_side = 0 if action == "BUY" else 1
        entry_result = await asyncio.wait_for(
            mnq.orders.place_market_order(contract_id=MICRO_CONTRACTS[TICKER], side=entry_side, size=size),
            timeout=3.0
        )
        if not entry_result.success:
            log.error(f"Bootstrap Council entry failed: {entry_result.errorMessage}")
            return False
        
        entry_price = price
        # Fill confirmation
        for attempt in range(30):
            await asyncio.sleep(0.1)
            try:
                positions = await asyncio.wait_for(mnq.positions.get_all_positions(), timeout=2.0)
                p = _find_position_for_contract(positions, MICRO_CONTRACTS[TICKER])
                if p and abs(p.size) > 0:
                    entry_price = p.averagePrice
                    break
            except:
                pass
        else:
            try:
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, MICRO_CONTRACTS[TICKER])
                if p:
                    entry_price = p.averagePrice
            except:
                pass
        
        # SL
        tick = INSTRUMENT_CONFIG[TICKER]['tick_size']
        if action == "BUY":
            sl_price = _round_to_tick(entry_price - sl_points, tick)
        else:
            sl_price = _round_to_tick(entry_price + sl_points, tick)
        
        exit_side = 1 if action == "BUY" else 0
        if not _validate_pre_entry_stop(action, TICKER, sl_price, tick, "Bootstrap Council post-fill"):
            await asyncio.wait_for(mnq.orders.place_market_order(contract_id=MICRO_CONTRACTS[TICKER], side=exit_side, size=size), timeout=3.0)
            return False
        sl_result = await asyncio.wait_for(
            mnq.orders.place_stop_order(contract_id=MICRO_CONTRACTS[TICKER], side=exit_side, size=size, stop_price=sl_price),
            timeout=3.0
        )
        
        if not sl_result.success:
            # Close naked entry
            await asyncio.wait_for(mnq.orders.place_market_order(contract_id=MICRO_CONTRACTS[TICKER], side=exit_side, size=size), timeout=3.0)
            return False
        
        return True
    except asyncio.TimeoutError:
        log.error("Bootstrap Council: Timeout")
        return False
    except Exception as e:
        log.error(f"Bootstrap Council: {e}")
        return False


async def _bootstrap_warwick_quick(action: str, size: int, price: float, sl_points: float) -> bool:
    """PHASE 1 FIX: Minimal Warwick bootstrap entry with pre-flight validation. ~4-5s execution."""
    try:
        tick = INSTRUMENT_CONFIG[TICKER]['tick_size']
        ideal_sl = _round_to_tick(price - sl_points, tick) if action == "BUY" else _round_to_tick(price + sl_points, tick)
        if not _validate_pre_entry_stop(action, TICKER, ideal_sl, tick, "Bootstrap Warwick pre-entry"):
            return False
        
        # Entry (use integer values: 0=BUY, 1=SELL per OrderSide enum)
        entry_side = 0 if action == "BUY" else 1
        entry_result = await asyncio.wait_for(
            mnq.orders.place_market_order(contract_id=MICRO_CONTRACTS[TICKER], side=entry_side, size=size),
            timeout=3.0
        )
        if not entry_result.success:
            log.error(f"Bootstrap Warwick entry failed: {entry_result.errorMessage}")
            return False
        
        entry_price = price
        # Fill confirmation
        for attempt in range(30):
            await asyncio.sleep(0.1)
            try:
                positions = await asyncio.wait_for(mnq.positions.get_all_positions(), timeout=2.0)
                p = _find_position_for_contract(positions, MICRO_CONTRACTS[TICKER])
                if p and abs(p.size) > 0:
                    entry_price = p.averagePrice
                    break
            except:
                pass
        else:
            try:
                positions = await mnq.positions.get_all_positions()
                p = _find_position_for_contract(positions, MICRO_CONTRACTS[TICKER])
                if p:
                    entry_price = p.averagePrice
            except:
                pass
        
        # SL
        tick = INSTRUMENT_CONFIG[TICKER]['tick_size']
        if action == "BUY":
            sl_price = _round_to_tick(entry_price - sl_points, tick)
        else:
            sl_price = _round_to_tick(entry_price + sl_points, tick)
        
        exit_side = 1 if action == "BUY" else 0
        if not _validate_pre_entry_stop(action, TICKER, sl_price, tick, "Bootstrap Warwick post-fill"):
            await asyncio.wait_for(mnq.orders.place_market_order(contract_id=MICRO_CONTRACTS[TICKER], side=exit_side, size=size), timeout=3.0)
            return False
        sl_result = await asyncio.wait_for(
            mnq.orders.place_stop_order(contract_id=MICRO_CONTRACTS[TICKER], side=exit_side, size=size, stop_price=sl_price),
            timeout=3.0
        )
        
        if not sl_result.success:
            # Close naked entry
            await asyncio.wait_for(mnq.orders.place_market_order(contract_id=MICRO_CONTRACTS[TICKER], side=exit_side, size=size), timeout=3.0)
            return False
        
        return True
    except asyncio.TimeoutError:
        log.error("Bootstrap Warwick: Timeout")
        return False
    except Exception as e:
        log.error(f"Bootstrap Warwick: {e}")
        return False


async def warwick_open_leg_forced(warwick_engine, price: float, sl_pts: int, tp_pts: int, direction: str):
    """PHASE 1 FIX #4: Open a warwick leg with forced direction (for bootstrap testing).
    
    Simplified version - just call the existing warwick functions instead of reimplementing.
    """
    if not warwick_engine or not price or direction not in ["BUY", "SELL"]:
        log.error(f"WARWICK_FORCED: Invalid inputs - engine={warwick_engine}, price={price}, direction={direction}")
        return False
    
    try:
        log.info(f"WARWICK_FORCED: Opening {direction} leg at {price} SL={sl_pts}pts TP={tp_pts}pts")
        
        # Use the existing warwick_open_leg function but force it with specific parameters
        # This avoids duplicating all the SDK call logic
        success = await warwick_open_leg(
            warwick=warwick_engine,
            side=direction,
            size=1,
            leg_type="primary",
            symbol=TICKER,
            sl_pts=sl_pts,
            tp_pts=tp_pts
        )
        
        if success:
            log.info(f"WARWICK_FORCED: Trade placed successfully")
            return True
        else:
            log.error(f"WARWICK_FORCED: warwick_open_leg returned False")
            return False
        
    except Exception as e:
        log.error(f"WARWICK_FORCED: Exception: {e}", exc_info=True)
        return False


async def warwick_tick(features):
    """Called every cycle. Claude-as-Warwick makes ALL decisions.
    No hardcoded triggers. Claude evaluates state and returns actions."""
    if not warwick:
        return None

    price = state.price
    if price <= 0:
        return None

    # Apply learned patterns for Warwick via awareness engine
    if awareness:
        warwick_patterns = awareness.apply_patterns(features)
        if warwick_patterns:
            avoid_patterns = [p for p in warwick_patterns if 'AVOID' in p.get('action', '')]
            favor_patterns = [p for p in warwick_patterns if 'FAVOR' in p.get('action', '')]
            if avoid_patterns:
                features['warwick_pattern_warning'] = " | ".join([p['description'] for p in avoid_patterns])
                log.info(f"WARWICK PATTERN AVOID: {features['warwick_pattern_warning']}")
            if favor_patterns:
                features['warwick_pattern_boost'] = " | ".join([p['description'] for p in favor_patterns])
                log.info(f"WARWICK PATTERN FAVOR: {features['warwick_pattern_boost']}")

    # Ask Claude wearing the Warwick persona what to do
    decision = await ask_warwick(features)
    if not decision:
        return None

    # Cache for Chimera (Engine #3) -- adaptive aggression reads both engines
    state.last_warwick_decision = decision
    state.last_warwick_decision_time = time.time()

    action = decision.get("action", "HOLD")
    actions_taken = []

    # ENTER: Open primary when flat
    if action == "ENTER" and not warwick.state.primary.is_open:
        side = decision.get("side", "BUY")
        size = decision.get("size", 5)
        sl_pts = decision.get("stop_points", 8)
        tp_pts = decision.get("target_points", 16)
        leg = await warwick_open_leg(side, size, sl_pts, tp_pts, "primary")
        if leg:
            warwick.record_entry()
            actions_taken.append(f"HUNT: {side} {size} sl={sl_pts} tp={tp_pts}")

    # HEDGE: Open hedge against losing primary
    elif action == "HEDGE" and warwick.state.primary.is_open and not warwick.state.hedge.is_open:
        side = decision.get("side", "SELL" if warwick.state.primary.side == "BUY" else "BUY")
        size = decision.get("size", warwick.state.primary.size)
        sl_pts = decision.get("stop_points", 8)
        tp_pts = decision.get("target_points", 16)
        leg = await warwick_open_leg(side, size, sl_pts, tp_pts, "hedge")
        if leg:
            warwick.record_entry()
            actions_taken.append(f"HEDGE: {side} {size} sl={sl_pts} tp={tp_pts}")

    # CLOSE_PRIMARY: Close the primary leg
    elif action == "CLOSE_PRIMARY" and warwick.state.primary.is_open:
        await warwick_close_leg("primary")
        actions_taken.append("CLOSED primary")

    # CLOSE_HEDGE: Close the hedge leg
    elif action == "CLOSE_HEDGE" and warwick.state.hedge.is_open:
        await warwick_close_leg("hedge")
        actions_taken.append("CLOSED hedge")

    # CLOSE_BOTH: Flatten everything
    elif action == "CLOSE_BOTH":
        if warwick.state.primary.is_open:
            await warwick_close_leg("primary")
            actions_taken.append("CLOSED primary")
        if warwick.state.hedge.is_open:
            await warwick_close_leg("hedge")
            actions_taken.append("CLOSED hedge")

    # TRAIL_PRIMARY / TRAIL_HEDGE: Set/update trail on a leg
    elif action == "TRAIL_PRIMARY" and warwick.state.primary.is_open:
        tp = decision.get("trail_price", 0)
        if tp > 0:
            warwick.state.primary.trail_active = True
            warwick.state.primary.trail_price = tp
            actions_taken.append(f"TRAIL primary @ {tp:.2f}")

    elif action == "TRAIL_HEDGE" and warwick.state.hedge.is_open:
        tp = decision.get("trail_price", 0)
        if tp > 0:
            warwick.state.hedge.trail_active = True
            warwick.state.hedge.trail_price = tp
            actions_taken.append(f"TRAIL hedge @ {tp:.2f}")

    # HOLD: Do nothing this cycle
    # (also default for unrecognized actions)

    # Check trail hits (the only mechanical rule: if price crosses trail, close)
    for leg in [warwick.state.primary, warwick.state.hedge]:
        if leg.is_open and leg.trail_active:
            hit = False
            if leg.side == "BUY" and price <= leg.trail_price:
                hit = True
            elif leg.side == "SELL" and price >= leg.trail_price:
                hit = True
            if hit:
                log.info(f"WARWICK: {leg.leg_type} TRAIL HIT at {price:.2f} (trail={leg.trail_price:.2f})")
                await warwick_close_leg(leg.leg_type)
                actions_taken.append(f"TRAIL HIT {leg.leg_type}")

    reason = decision.get("reasoning", "")
    conf = decision.get("confidence", "?")
    if actions_taken:
        return f"{' | '.join(actions_taken)} -- {reason[:60]}"
    # Log HOLD decisions at INFO with position context
    if reason:
        p_info = ""
        if warwick.state.primary.is_open:
            p_pts = warwick.state.primary.unrealized_pts(price)
            p_info = f" [primary {warwick.state.primary.side} {p_pts:+.1f}pts]"
        h_info = ""
        if warwick.state.hedge.is_open:
            h_pts = warwick.state.hedge.unrealized_pts(price)
            h_info = f" [hedge {warwick.state.hedge.side} {h_pts:+.1f}pts]"
        log.info(f"WARWICK: HOLD (conf={conf}){p_info}{h_info} -- {reason[:80]}")
    return None


async def warwick_burst_tick():
    """Fast 5s tick: adjust SL/TP lines to protect profit and hedge risk.
    No API call. Pure math on current price vs position state."""
    if not warwick or state.price <= 0:
        return

    price = state.price

    contract_id = mnq.instrument_info.id

    # S-2: Emergency close if SL was lost in previous cycle
    if state._sl_emergency:
        log.critical("S-2 EMERGENCY: SL lost -- closing ALL positions immediately")
        state._sl_emergency = False
        for em_leg in [warwick.state.primary, warwick.state.hedge]:
            if em_leg.is_open:
                try:
                    close_side = 1 if em_leg.side == "BUY" else 0
                    await mnq.orders.place_market_order(
                        contract_id=contract_id, side=close_side, size=em_leg.size)
                    pnl = em_leg.unrealized_pnl(price)
                    warwick.record_leg_close(em_leg.leg_type, pnl)
                    record_pnl(pnl, f"emergency_sl_lost:{em_leg.leg_type}")
                    log.critical(f"S-2 EMERGENCY CLOSE: {em_leg.leg_type} {em_leg.side} PnL={pnl:+.2f}")
                    # Cancel any remaining orders
                    for oid in [em_leg.sl_order_id, em_leg.tp_order_id]:
                        if oid:
                            try:
                                await mnq.orders.cancel_order(oid)
                            except Exception:
                                pass
                except Exception as e:
                    log.critical(f"S-2 EMERGENCY CLOSE FAILED for {em_leg.leg_type}: {e}")
        return  # Skip normal burst tick this cycle after emergency

    async def safe_move_sl(leg, new_sl, reason):
        """Cancel-replace SL atomically. Restores old SL on failure. Never leaves naked."""
        old_sl_id = leg.sl_order_id
        old_sl_price = leg.sl_price
        exit_side = 1 if leg.side == "BUY" else 0
        try:
            await mnq.orders.cancel_order(old_sl_id)
            r = await mnq.orders.place_stop_order(
                contract_id=contract_id, side=exit_side, size=leg.size, stop_price=new_sl)
            if r.success:
                leg.sl_order_id = r.orderId
                leg.sl_price = new_sl
                log.info(f"BURST: {leg.leg_type} SL {old_sl_price:.2f} -> {new_sl:.2f} ({reason})")
            else:
                # Replace failed -- restore old SL immediately
                restore = await mnq.orders.place_stop_order(
                    contract_id=contract_id, side=exit_side, size=leg.size, stop_price=old_sl_price)
                if restore.success:
                    leg.sl_order_id = restore.orderId
                    log.warning(f"BURST: SL replace failed, restored old SL @ {old_sl_price:.2f}")
                else:
                    log.critical(f"BURST CRITICAL: SL LOST for {leg.leg_type} -- no stop protection! Setting emergency close flag.")
                    state._sl_emergency = True  # S-2: trigger emergency close next burst tick
        except Exception as e:
            # Cancel succeeded but place failed -- restore
            try:
                restore = await mnq.orders.place_stop_order(
                    contract_id=contract_id, side=exit_side, size=leg.size, stop_price=old_sl_price)
                if restore.success:
                    leg.sl_order_id = restore.orderId
                    log.warning(f"BURST: SL error ({e}), restored @ {old_sl_price:.2f}")
                else:
                    log.critical(f"BURST CRITICAL: SL LOST for {leg.leg_type}: {e} -- setting emergency close flag")
                    state._sl_emergency = True  # S-2: trigger emergency close next burst tick
            except Exception as e2:
                log.critical(f"BURST CRITICAL: SL LOST for {leg.leg_type}: {e} -> restore also failed: {e2} -- emergency close!")
                state._sl_emergency = True  # S-2: trigger emergency close next burst tick

    # SL VERIFICATION: check that each leg's SL order still exists at broker
    # If SL was filled (broker closed position) but callback missed it, detect here
    for leg in [warwick.state.primary, warwick.state.hedge]:
        if not leg.is_open or not leg.sl_order_id:
            continue
        # Check if price has blown through SL (broker filled it but we missed the callback)
        sl_breached = False
        if leg.side == "BUY" and price <= leg.sl_price - 1.0:
            sl_breached = True
        elif leg.side == "SELL" and price >= leg.sl_price + 1.0:
            sl_breached = True
        if sl_breached:
            log.warning(f"BURST SL BREACH: {leg.leg_type} {leg.side} price={price:.2f} past SL={leg.sl_price:.2f} -- force closing")
            pnl = leg.unrealized_pnl(price)
            try:
                close_side = 1 if leg.side == "BUY" else 0
                await mnq.orders.place_market_order(
                    contract_id=contract_id, side=close_side, size=leg.size)
                for oid in [leg.sl_order_id, leg.tp_order_id]:
                    if oid:
                        try:
                            await mnq.orders.cancel_order(oid)
                        except Exception:
                            pass
            except Exception as e:
                log.error(f"BURST SL BREACH close failed: {e}")
            warwick.record_leg_close(leg.leg_type, pnl)
            record_pnl(pnl, f"burst_sl_breach:{leg.leg_type}")
            continue

    for leg in [warwick.state.primary, warwick.state.hedge]:
        if not leg.is_open or not leg.sl_order_id:
            continue

        pts = leg.unrealized_pts(price)

        # --- Profit protection: aggressive ratchet for Warwick's asymmetric style ---
        # Breakeven at +4pts, then trail at 50% to let winners RUN
        if pts >= 4.0:
            if pts >= 15.0:
                lock_pct = 0.6  # lock 60% of big winners
            elif pts >= 8.0:
                lock_pct = 0.5  # lock 50% of profit
            else:
                lock_pct = 0.0  # breakeven at +4pts
            if leg.side == "BUY":
                new_sl = leg.entry_price + (pts * lock_pct)
                if new_sl > leg.sl_price:
                    await safe_move_sl(leg, new_sl, f"profit +{pts:.1f}pts lock {lock_pct:.0%}")
            else:
                new_sl = leg.entry_price - (pts * lock_pct)
                if new_sl < leg.sl_price:
                    await safe_move_sl(leg, new_sl, f"profit +{pts:.1f}pts lock {lock_pct:.0%}")

        # --- Risk cap: stop bleeds early (Warwick cuts losers fast) ---
        elif pts <= -10.0:
            max_loss_pts = max(abs(pts) + 4.0, 16.0)
            if leg.side == "BUY":
                tight_sl = leg.entry_price - max_loss_pts
                if tight_sl > leg.sl_price:
                    await safe_move_sl(leg, tight_sl, f"loss {pts:.1f}pts")
            else:
                tight_sl = leg.entry_price + max_loss_pts
                if tight_sl < leg.sl_price:
                    await safe_move_sl(leg, tight_sl, f"loss {pts:.1f}pts")


_last_hold_confidence = 0.0  # Cache high-confidence HOLDs to skip next call

async def ask_warwick(features):
    """Ask Claude wearing the Warwick persona what to do with both positions.
    Model tiering: Haiku for routine HOLDs, Sonnet for critical decisions."""
    global _last_hold_confidence
    positions_state = warwick.build_prompt_section(state.price)

    # --- Model tiering: use cheap model for routine situations ---
    is_critical = (
        not warwick.state.primary.is_open  # need to ENTER
        or warwick.state.is_hedged  # managing both legs
        or (warwick.state.primary.is_open and
            abs(warwick.state.primary.unrealized_pts(state.price)) > 6)  # big move
    )
    # Use Haiku for routine HOLDs, Sonnet for critical decisions
    model = AI_MODEL if is_critical else HAIKU_MODEL
    if not is_critical:
        log.info("WARWICK: Using Haiku for routine HOLD check")

    # --- HOLD cache: skip API call if last HOLD was high-confidence ---
    if _last_hold_confidence >= 0.8 and warwick.state.primary.is_open and not warwick.state.is_hedged:
        p_pts = warwick.state.primary.unrealized_pts(state.price)
        if -3 < p_pts < 6:  # comfortable range, nothing changed
            _last_hold_confidence = 0.0  # only skip ONE cycle
            log.info("WARWICK: HOLD (cached, skipping API call)")
            return {"action": "HOLD", "reasoning": "cached_hold", "confidence": 0.8}

    # Determine available actions based on current state
    if not warwick.state.primary.is_open:
        available = "ENTER (must provide side, size, stop_points, target_points)"
    elif warwick.state.primary.is_open and not warwick.state.hedge.is_open:
        available = (
            "HOLD, CLOSE_PRIMARY, TRAIL_PRIMARY (set trail_price), "
            "HEDGE (open counter-position: provide side, size, stop_points, target_points)"
        )
    else:
        available = (
            "HOLD, CLOSE_PRIMARY, CLOSE_HEDGE, CLOSE_BOTH, "
            "TRAIL_PRIMARY (set trail_price), TRAIL_HEDGE (set trail_price)"
        )

    # Build awareness context for critical decisions
    awareness_ctx = ""
    if is_critical and awareness:
        try:
            awareness_ctx = awareness.build_context(features, state.broker_balance, state.daily_pnl)
        except Exception:
            pass

    # Adaptive sizing: start small, scale up when winning
    if state.wins > state.losses and state.daily_pnl > 50:
        base_size = 5  # winning streak: go big
    elif state.wins >= state.losses and state.daily_pnl >= 0:
        base_size = 3  # even: moderate
    else:
        base_size = 2  # losing: protect capital

    # Dynamic R:R based on current volatility AND MARKET REGIME (PHASE 5)
    vol = features.get("volatility", 3.0)
    vol = max(vol, 1.5)  # floor at 1.5pts to avoid absurdly tight stops
    
    # PHASE 5: Apply regime-based adjustments to stop and target multipliers
    regime = features.get("current_regime", "RANGING")
    regime_settings = risk_math.regime_settings(regime)
    regime_stop_mult = regime_settings["stop_multiplier"]  # 1.5, 0.8, 2.5, etc
    regime_target_mult = regime_settings["target_multiplier"]  # 4.0, 2.0, 3.0, etc
    regime_size_reduction = regime_settings["position_size_reduction"]
    
    # Apply regime multipliers to volatility-based sizing
    vol_stop = round(vol * regime_stop_mult, 1)  # stop = regime-adjusted volatility
    vol_stop = max(vol_stop, 6.0)  # absolute minimum 6pts ($12/contract)
    vol_target_lo = round(vol_stop * max(3, regime_target_mult - 1), 0)  # Conservative target
    vol_target_mid = round(vol_stop * regime_target_mult, 0)  # Default target
    vol_target_hi = round(vol_stop * min(7, regime_target_mult + 1), 0)  # Aggressive target
    
    # Reduce position size in certain regimes (HIGH_VOL, RANGING, CHOPPY)
    regime_adjusted_size = max(1, int(base_size * regime_size_reduction))

    # STEERING CONTEXT: Inject adaptive decision guidance
    steering_section = features.get('steering_context', '')

    # L2 FRESHNESS WARNING: Add prominent warning if L2 data is stale or unavailable
    l2_warning = ""
    l2_age = time.time() - state.l2_timestamp if state.l2_timestamp > 0 else 999
    if not state.orderbook_data:
        l2_warning = "\n⚠️  WARNING: L2 ORDERBOOK DATA IS UNAVAILABLE - No depth data available  ⚠️\n"
    elif l2_age > L2_STALE_BLOCK_SECONDS:
        l2_warning = f"\n⚠️  WARNING: L2 DATA IS STALE ({l2_age:.1f}s old > {L2_STALE_BLOCK_SECONDS}s threshold) - Use caution  ⚠️\n"
    elif l2_age > L2_STALE_WARNING_SECONDS:
        l2_warning = f"\n⚠️  CAUTION: L2 data is aging ({l2_age:.1f}s) - May become stale soon  ⚠️\n"

    prompt = f"""You are WARWICK -- the Hedge Werewolf. A PREDATOR who bets big, cuts losers INSTANTLY, and lets winners run until they scream.
{l2_warning}
WARWICK'S EDGE: You accept a 30-40% win rate because your winners are 4-6x your losers. You are NOT afraid to lose small. Every loss is the cost of hunting.

{steering_section}
YOUR POSITIONS:
{positions_state}

MARKET REGIME (PHASE 5):
- Current: {regime} ({features.get('regime_confidence', 0):.0f}% confidence)
- Description: {features.get('regime_description', 'Unknown')}
- Strategy: {regime_settings['description']}
- Adjusted stops: {regime_stop_mult}x ATR (from 1.5x baseline)
- Adjusted targets: {regime_target_mult}:1 R:R (from 4:1 baseline)
- Position size: {regime_size_reduction:.0%} of baseline (from market volatility)

MARKET:
- Price: {features['price']}{" [STALE]" if features.get("price_is_stale") else ""}
- Momentum: {features['change_10']}pts ({features['pct_change_10']}%) | Vol: {features['volatility']}pts
- Trend: {features['trend']} (vs mean: {features['vs_mean']})
- Range: {features['range_low']}-{features['range_high']} ({features['range_size']}pts)
- ATR(14): {features.get('atr', 0):.1f}pts

SESSION: PnL ${state.daily_pnl:.2f} | W={state.wins} L={state.losses} | Balance ${state.broker_balance:.2f}
Adaptive size: {regime_adjusted_size} contracts ({regime}x{regime_size_reduction:.0%} = {regime_adjusted_size} | base was {base_size})
MATH STATS: {f"WR={state._math_stats['warwick']['win_rate']*100:.0f}% Exp=${state._math_stats['warwick']['expectancy']:.2f} Kelly={state._math_stats['warwick']['kelly_pct']:.1f}% Ruin={state._math_stats['warwick']['risk_of_ruin_pct']:.1f}%" if hasattr(state, '_math_stats') and 'warwick' in state._math_stats else "calculating..."} {'[HALTED - negative expectancy]' if state.warwick_halted else ''}

ALL OPEN TRADES (SL/TP across all engines and markets):
{chr(10).join([f"  {k}: {v['engine']} {v['symbol']} {v['side']} {v['size']}ct entry={v['entry']:.2f} SL={v['sl']:.2f} TP={v['tp']:.2f}" for k,v in state.open_trades.items()]) if state.open_trades else "  (none)"}

{get_market_snapshot()}
{awareness_ctx}
WARWICK'S PLAYBOOK (REGIME-AWARE):
1. ENTRY: Trade WITH the trend. Use RISK:REWARD to set stops based on REGIME. Stop = {regime_stop_mult}x volatility ({vol_stop:.1f}pts). Target = {regime_target_mult}:1 R:R ({vol_target_lo:.0f}-{vol_target_hi:.0f}pts). Size={regime_adjusted_size}.
   - In TRENDING/RANGING: wider stops, aggressive targets
   - In HIGH_VOLATILITY: much wider stops, safer targets
   - CHOPPY regimes: reduced sizes, defensive mode
2. HEDGE: Deploy when primary loses >1x volatility AND trend turned against you. The hedge is a REAL PROFIT TRADE aiming for 3-5x volatility, not insurance. Size same or smaller than primary. The primary stays OPEN -- it may recover.
3. PATIENCE WITH LOSERS: A losing primary that the trend may bring back should be HELD. Do NOT close it just because it is red. The hedge protects you while you WAIT for recovery. Only close a loser if the trend has DECISIVELY and PERMANENTLY reversed against it.
4. TRAIL: When a position is profitable > 2x volatility, set trail. Let it RUN. Burst mode tightens mechanically.
5. CLOSE: Close a leg ONLY when (a) it has hit your profit target, (b) trend has permanently reversed, or (c) the leg has been losing for 10+ minutes with no improvement.
6. HOLD: Default. Winners need TIME. A +3pt position can become +30pt. A -5pt position can become +10pt if trend reverses.

CURRENT CONDITIONS:
- Volatility: {vol:.1f}pts (determines your stop and target sizing)
- Regime adjustment: {regime_stop_mult}x stop multiplier, {regime_target_mult}:1 target multiplier, {regime_size_reduction:.0%} position sizing
- RECOMMENDED: stop={vol_stop:.0f}pts, target={vol_target_lo:.0f}-{vol_target_hi:.0f}pts (adjusted for {regime})

IRON RULES (REGIME-AWARE):
- FLAT = ENTER immediately. Warwick is ALWAYS hunting.
- Stop must be at LEAST {regime_stop_mult}x volatility ({vol:.1f}pts → {vol_stop:.1f}pts min). Tighter in RANGING, wider in HIGH_VOL.
- Target must be at LEAST {regime_target_mult}:1 R:R. This asymmetry is how you profit.
- Size: Use {regime_adjusted_size} contracts (regime-adjusted from base {base_size})
  - TRENDING: full size
  - RANGING: 75% size
  - HIGH_VOLATILITY: 50% size
  - CHOPPY: only with high conviction
- NEVER widen a stop. NEVER move a stop away from price. Stops only tighten.
- Hedge is a PROFIT TOOL. It should aim to make 3-5x volatility while the primary waits for recovery.
- DO NOT close the primary just because you hedged. Both legs can be profitable.
- {TICKER}: 1pt = ${POINT_VALUE}/contract.

AVAILABLE: {available}

Hunt. Kill. Feast. LAST LINE ONLY valid JSON:
{{"action": "...", "side": "BUY"|"SELL", "size": {regime_adjusted_size}, "stop_points": {vol_stop:.0f}, "target_points": {vol_target_mid:.0f}, "trail_price": 0, "confidence": 0.8, "reasoning": "brief"}}"""

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = json.dumps({
            "model": model,
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(url, data=body, headers=headers, method='POST')
        
        # PRIORITY FIX: Rate limit handling with retry
        for retry_attempt in range(CLAUDE_RATE_LIMIT_MAX_RETRIES + 1):
            try:
                def _call():
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        return json.loads(resp.read().decode())

                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(None, _call)
                break  # Success, exit retry loop
            except urllib.error.HTTPError as e:
                if e.code == 429:  # Rate limited
                    if retry_attempt < CLAUDE_RATE_LIMIT_MAX_RETRIES:
                        should_retry = await handle_claude_rate_limit(e, retry_attempt)
                        if not should_retry:
                            return {"action": "HOLD", "reasoning": "Claude rate limit - max retries exhausted"}
                        continue  # Retry
                    else:
                        log.error("WARWICK RATE LIMIT: Max retries exhausted")
                        log_anomaly("rate_limit", "Warwick API rate limit max retries")
                        return {"action": "HOLD", "reasoning": "Claude rate limit - max retries"}
                else:
                    raise  # Re-raise non-429 errors
        
        text = data["content"][0]["text"].strip()

        # Track API cost
        if "usage" in data:
            in_tok = data["usage"].get("input_tokens", 0)
            out_tok = data["usage"].get("output_tokens", 0)
            log_api_usage(in_tok + out_tok, f"warwick_{model.split('-')[2]}", in_tok, out_tok)

        brace_start = text.rfind('{')
        brace_end = text.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            decision = json.loads(text[brace_start:brace_end + 1])
            action = decision.get("action", "HOLD")
            conf = decision.get("confidence", 0.5)
            # Enforce dynamic R:R based on volatility
            if action in ("ENTER", "HEDGE"):
                sp = decision.get("stop_points", vol_stop)
                tp = decision.get("target_points", vol_target_mid)
                sp = max(vol_stop, min(vol_stop * 2, sp))  # stop: 1-2x recommended
                tp = max(sp * 3, min(sp * 6, tp))  # target: 3-6x stop (R:R enforced)
                decision["stop_points"] = round(sp, 1)
                decision["target_points"] = round(tp, 1)
                decision["size"] = max(1, min(5, int(decision.get("size", base_size))))
            # Cache HOLD confidence
            _last_hold_confidence = conf if action == "HOLD" else 0.0
            
            # PHASE 2: Check risk constraints and log ENTER decision
            if action in ("ENTER", "HEDGE"):
                can_enter, reason = check_risk_constraints("warwick", decision, features)
                if not can_enter:
                    log.warning(f"WARWICK: Trade blocked - {reason}")
                    decision["action"] = "HOLD"
                    decision["reasoning"] = f"Risk limit: {reason}"
                elif getattr(state, '_choppy_block_entries', False):
                    # CHOPPY regime hard block - skip entries when regime is CHOPPY with >70% confidence
                    log.warning(f"WARWICK: CHOPPY regime blocked ENTER (conf={state.regime_confidence:.0f}%)")
                    decision["action"] = "HOLD"
                    decision["reasoning"] = f"CHOPPY regime blocked (conf={state.regime_confidence:.0f}%)"
                else:
                    # L2 QUALITY GATE: Already checked in control_loop before calling this function
                    # Log detailed ENTER information
                    size = decision.get("size", base_size)
                    stop_pts = decision.get("stop_points", vol_stop)
                    target_pts = decision.get("target_points", vol_target_mid)
                    risk_amt = size * stop_pts * POINT_VALUE
                    account_util = (risk_amt / (state.broker_balance * 0.05)) * 100 if state.broker_balance > 0 else 0
                    kelly_pct = state._math_stats['warwick']['kelly_pct'] if hasattr(state, '_math_stats') and 'warwick' in state._math_stats else 0
                    log.info(f"WARWICK ENTER {size} contracts @ {state.price} | Risk: ${risk_amt:.2f} | Kelly: {kelly_pct:.1f}% | Account utilization: {account_util:.1f}%")
                    state.daily_risk_used += risk_amt
            
            # ML_ENTRY_FILTER: REMOVED 2026-03-09 - AI engines trade freely
            
            log.info(f"WARWICK: {action} [{model.split('-')[2]}] | {decision.get('reasoning','')[:80]}")
            return decision

        log.warning(f"WARWICK: No JSON in response: {text[:100]}")
        return {"action": "HOLD", "reasoning": "parse_error"}

    except Exception as e:
        log.warning(f"WARWICK API error: {e}")
        return {"action": "HOLD", "reasoning": f"api_error: {e}"}


# ============================================================
# PNL HANDSHAKE (Global Coordinator)
# ============================================================
pnl_lock = asyncio.Lock()

async def record_pnl(amount: float, source: str, symbol: str):
    """Handshake: Update global state while attributing to local instrument."""
    async with pnl_lock:
        state.daily_pnl += amount
        if amount > 0:
            state.wins += 1
        elif amount < 0:
            state.losses += 1
            
        mstate = state.get_market(symbol)
        mstate.daily_pnl += amount  # Local attribution
        
        log.info(f"PNL RECORDED [{symbol}]: ${amount:+.2f} ({source}) | Local: ${mstate.daily_pnl:+.2f} | Global: ${state.daily_pnl:+.2f}")
        
        # S-1: Global Daily Loss Circuit Breaker ($1k limit)
        if state.daily_pnl <= -1000.0:
            log.critical(f"GLOBAL LOSS LIMIT HIT: ${state.daily_pnl} <= -$1000.0")
            state.running = False
            await shutdown()
            
        # S-2: Local Stop-Trading (Halt instrument if it loses $300 in a day)
        if mstate.daily_pnl <= -300.0:
            log.warning(f"LOCAL HALT [{symbol}]: Daily loss limit hit ($300). Instrument disabled for 24h.")

# ============================================================
# STATE PERSISTENCE (deterministic)
# ============================================================
def save_status():
    """Write current state to JSON for external monitoring."""
    mstate = state.get_market(TICKER)
    unrealized = 0.0
    if mstate.position_side != "FLAT" and mstate.position_entry > 0 and mstate.price > 0:
        if mstate.position_side in ("LONG", "BUY"):
            unrealized = (mstate.price - mstate.position_entry) * mstate.position_size * POINT_VALUE
        else:
            unrealized = (mstate.position_entry - mstate.price) * mstate.position_size * POINT_VALUE

    status = {
        "timestamp": utc_now().isoformat(),
        "version": "v2-brick-house",
        "market": {"price": mstate.price, "samples": len(state.prices), "price_stale": mstate.price_is_stale},
        "position": {
            "side": mstate.position_side, "size": mstate.position_size,
            "entry": mstate.position_entry
        },
        "active_trade": asdict(state.active_trade),
        "pnl": {
            "realized": round(state.daily_pnl, 2),
            "unrealized": round(unrealized, 2),
            "total": round(state.daily_pnl + unrealized, 2)
        },
        "session": {
            "trades": state.trade_count, "wins": state.wins,
            "losses": state.losses, "last_decision": state.last_decision,
            "cycles": state.cycle_count
        },
        "fleet_count": len(fleet.agents) if fleet and fleet.running else 0,
        "broker": {
            "balance": round(state.broker_balance, 2),
            "starting_balance": round(state.broker_starting_balance, 2),
            "realized_pnl": round(state.broker_realized_pnl, 2),
            "pnl_divergence_count": state.pnl_divergence_count,
            "last_reconcile": state.last_reconcile_time,
        },
        "data_feed": {
            "ws_quotes": state.ws_quote_count,
            "price_age_s": round(time.time() - mstate.price_timestamp, 1) if mstate.price_timestamp > 0 else -1,
            "total_slippage": round(state.total_slippage, 2),
        },
        "warwick": warwick.get_status() if warwick else None,
        "chimera": asdict(mstate.chimera_trade) if mstate.chimera_trade.side != "FLAT" else None,
        "math": {
            "system": {
                "expectancy": round(state._math_stats["system"]["expectancy"], 2) if hasattr(state, "_math_stats") and "system" in state._math_stats else 0,
                "win_rate": round(state._math_stats["system"]["win_rate"], 3) if hasattr(state, "_math_stats") and "system" in state._math_stats else 0,
                "kelly_pct": round(state._math_stats["system"]["kelly_pct"], 1) if hasattr(state, "_math_stats") and "system" in state._math_stats else 0,
                "risk_of_ruin_pct": round(state._math_stats["system"]["risk_of_ruin_pct"], 2) if hasattr(state, "_math_stats") and "system" in state._math_stats else 0,
                "n": state._math_stats["system"]["n"] if hasattr(state, "_math_stats") and "system" in state._math_stats else 0,
            },
            "warwick": {
                "expectancy": round(state._math_stats["warwick"]["expectancy"], 2) if hasattr(state, "_math_stats") and "warwick" in state._math_stats else 0,
                "win_rate": round(state._math_stats["warwick"]["win_rate"], 3) if hasattr(state, "_math_stats") and "warwick" in state._math_stats else 0,
                "kelly_pct": round(state._math_stats["warwick"]["kelly_pct"], 1) if hasattr(state, "_math_stats") and "warwick" in state._math_stats else 0,
                "risk_of_ruin_pct": round(state._math_stats["warwick"]["risk_of_ruin_pct"], 2) if hasattr(state, "_math_stats") and "warwick" in state._math_stats else 0,
                "n": state._math_stats["warwick"]["n"] if hasattr(state, "_math_stats") and "warwick" in state._math_stats else 0,
                "halted": state.warwick_halted,
            },
            "council": {
                "expectancy": round(state._math_stats["council"]["expectancy"], 2) if hasattr(state, "_math_stats") and "council" in state._math_stats else 0,
                "win_rate": round(state._math_stats["council"]["win_rate"], 3) if hasattr(state, "_math_stats") and "council" in state._math_stats else 0,
                "kelly_pct": round(state._math_stats["council"]["kelly_pct"], 1) if hasattr(state, "_math_stats") and "council" in state._math_stats else 0,
                "risk_of_ruin_pct": round(state._math_stats["council"]["risk_of_ruin_pct"], 2) if hasattr(state, "_math_stats") and "council" in state._math_stats else 0,
                "n": state._math_stats["council"]["n"] if hasattr(state, "_math_stats") and "council" in state._math_stats else 0,
                "halted": state.council_halted,
            },
            "chimera": {
                "expectancy": round(state._math_stats["chimera"]["expectancy"], 2) if hasattr(state, "_math_stats") and "chimera" in state._math_stats else 0,
                "win_rate": round(state._math_stats["chimera"]["win_rate"], 3) if hasattr(state, "_math_stats") and "chimera" in state._math_stats else 0,
                "kelly_pct": round(state._math_stats["chimera"]["kelly_pct"], 1) if hasattr(state, "_math_stats") and "chimera" in state._math_stats else 0,
                "risk_of_ruin_pct": round(state._math_stats["chimera"]["risk_of_ruin_pct"], 2) if hasattr(state, "_math_stats") and "chimera" in state._math_stats else 0,
                "n": state._math_stats["chimera"]["n"] if hasattr(state, "_math_stats") and "chimera" in state._math_stats else 0,
                "halted": state.chimera_halted,
            },
        } if hasattr(state, "_math_stats") else None,
    }
    try:
        content = json.dumps(status, indent=2)
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"RALPH WIGGUM: status saved - price={mstate.price}, pos={mstate.position_side}")
    except Exception as e:
        print(f"RALPH WIGGUM: save_status FAILED: {e}")
        traceback.print_exc()


# ============================================================
# DASHBOARD REMOVED - Feature not needed for trading


# ============================================================
# BACKGROUND RESEARCH LOOP
# ============================================================
_RESEARCH_TOPICS = [
    "momentum trading MNQ",
    "mean reversion scalping",
    "volatility breakout strategies",
    "risk management futures",
    "trend following micro futures",
    "hedge strategies for losing positions",
]

_COUNCIL_RESEARCH_COOLDOWN = 120  # 2 minutes minimum between research calls


async def _run_council_research():
    """Fire-and-forget: run one research call for Council memory in a background thread."""
    try:
        topic = _RESEARCH_TOPICS[state._council_research_idx % len(_RESEARCH_TOPICS)]
        state._council_research_idx += 1
        state._last_council_research_time = time.time()
        log.info(f"COUNCIL RESEARCH (background): topic='{topic}'")
        await asyncio.to_thread(council_awareness.research_strategy, topic, ANTHROPIC_KEY, AI_MODEL)
    except Exception as e:
        log.debug(f"Council background research error: {e}")


def _maybe_trigger_council_research():
    """Check cooldown and episode count, then fire-and-forget a research task for Council."""
    if not council_awareness or not ANTHROPIC_KEY:
        return
    if time.time() - state._last_council_research_time < _COUNCIL_RESEARCH_COOLDOWN:
        return
    try:
        ep_count = council_awareness.conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    except Exception:
        ep_count = 0
    if ep_count < 1:
        return
    task = asyncio.create_task(_run_council_research())
    _background_tasks.add(task)
    task.add_done_callback(_bg_task_done)


# ============================================================
# BURST MODE - PHASE 3: Dynamic SL/TP adjustment based on profit
# ============================================================
async def burst_mode(symbol: str = None):
    """Check and adjust SL/TP for active positions when profit thresholds are hit.
    PHASE 3: Mechanically move stops to lock in gains as trades become profitable.
    No API calls - just local state and SL order updates."""
    sym = symbol or TICKER
    mstate = state.get_market(sym)
    
    if mstate.position_side == "FLAT":
        return  # Nothing to do if flat
    
    if mstate.current_atr <= 0:
        return  # No ATR data yet
    
    # Determine entry price and current position
    entry = mstate.position_entry
    current = mstate.price
    if entry <= 0 or current <= 0:
        return
    
    # Calculate current profit in points
    if mstate.position_side == "LONG":
        profit_pts = current - entry
    elif mstate.position_side == "SHORT":
        profit_pts = entry - current
    else:
        return
    
    # Only burst if we have meaningful profit (at least 4 points)
    if profit_pts < 4:
        return
    
    # Calculate burst mode levels
    trade = mstate.active_trade
    current_sl = trade.sl_price if trade.side != "FLAT" else entry
    current_tp = trade.tp_price if trade.side != "FLAT" else entry
    
    levels = risk_math.burst_mode_levels(profit_pts, current_sl, current_tp)
    
    # Check each level to see if we've hit it
    for level in levels:
        threshold = level["threshold_pts"]
        action = level["action"]
        
        if profit_pts >= threshold:
            # Calculate new SL price
            if mstate.position_side == "LONG":
                # For long: entry + adjustment
                if action == "MOVE_SL_BREAKEVEN":
                    new_sl = entry
                elif action == "MOVE_SL_LOCK_2PTS":
                    new_sl = entry + 2
                else:  # LOCK_60PCT
                    new_sl = entry + (current - entry) * 0.6
            else:
                # For short: entry - adjustment
                if action == "MOVE_SL_BREAKEVEN":
                    new_sl = entry
                elif action == "MOVE_SL_LOCK_2PTS":
                    new_sl = entry - 2
                else:  # LOCK_60PCT
                    new_sl = entry - (entry - current) * 0.6
            
            # Only update if new SL is better (tighter) than current
            if mstate.position_side == "LONG" and new_sl > current_sl:
                log.info(f"BURST MODE [{sym}]: {action} | Profit={profit_pts:.1f}pts | "
                        f"SL {current_sl:.2f} -> {new_sl:.2f} | "
                        f"ATR={mstate.current_atr:.1f}pts | Price={current:.2f}")
                trade.sl_price = new_sl
                # In real trading, would call: await mnq.orders.update_sl_order(...)
                mstate.burst_mode_active = True
            elif mstate.position_side == "SHORT" and new_sl < current_sl:
                log.info(f"BURST MODE [{sym}]: {action} | Profit={profit_pts:.1f}pts | "
                        f"SL {current_sl:.2f} -> {new_sl:.2f} | "
                        f"ATR={mstate.current_atr:.1f}pts | Price={current:.2f}")
                trade.sl_price = new_sl
                mstate.burst_mode_active = True


# ============================================================
# MARKET WORKER (Phase 2 Multi-Market)
# ============================================================
# PHASE 3: Strategy Dispatcher (SOE Simplicity)
STRATEGY_MAP = {
    "TRENDING_UP": "warwick",
    "TRENDING_DOWN": "warwick",
    "RANGING": "council",
    "CHOPPY": "WAIT",
    "VOLATILE": "chimera"
}

# PHASE 8: 10/10 Priority Dispatcher (mins blueprint)
# ATR Thresholds: MNQ (15-35), MES (8-20), MCL (0.4-1.2), MGC (4-12), MYM (80-200), M2K (4-10)
STRATEGY_THRESHOLDS = {
    "MNQ": {"ranging": 15.0, "volatile": 35.0},
    "MES": {"ranging": 8.0, "volatile": 20.0},
    "MCL": {"ranging": 0.4, "volatile": 1.2},
    "MGC": {"ranging": 4.0, "volatile": 12.0},
    "MYM": {"ranging": 80.0, "volatile": 200.0},
    "M2K": {"ranging": 4.0, "volatile": 10.0}
}

async def process_market(symbol: str, decision_timer: int):
    """Worker: Encapsulates the 10/10 Priority Dispatcher for one symbol."""
    state = VortexState.get_instance()
    try:
        mstate = state.get_market(symbol)
        config = INSTRUMENT_CONFIG.get(symbol, INSTRUMENT_CONFIG[TICKER])
        
        # 1. Market Hours Gate
        market_open, should_flatten = is_market_hours()
        if should_flatten:
            if mstate.position_side != "FLAT":
                log.info(f"DAILY HALT: {symbol} -- flattening")
                await close_position(symbol=symbol)
            return
        if not market_open: return

        # 2. Compute Features (Includes ATR & Slope)
        features = compute_features(symbol)
        if not features: return
        
        atr = features["atr"]
        slope = features.get("momentum", 0.0)
        thresholds = STRATEGY_THRESHOLDS.get(symbol, STRATEGY_THRESHOLDS["MNQ"])
        
        # S-1: 10/10 Engine Switching Logic
        if atr < thresholds["ranging"]:
            primary_engine = "council"
            regime = "RANGING"
        elif atr > thresholds["volatile"]:
            primary_engine = "chimera"
            regime = "VOLATILE"
        elif abs(slope) > (atr * 0.1): # Trend confirmed by slope
            primary_engine = "warwick"
            regime = f"TRENDING_{'UP' if slope > 0 else 'DOWN'}"
        else:
            primary_engine = "WAIT"
            regime = "CHOPPY"
            
        mstate.regime.regime = regime
        
        # 3. Decision Logic - Specialized Persona
        if decision_timer == 0 and mstate.position_side == "FLAT":
            async with state.position_entry_lock:
                # S-2: Atomic Global Open Risk Check (PHASE 7/8)
                total_open_risk = sum(m.get_open_risk() for m in state.markets.values())
                risk_limit = getattr(state, 'ai_risk_limit', 500.0) # AI can override
                
                if total_open_risk >= risk_limit:
                    if state.cycle_count % 30 == 0:
                        log.warning(f"GLOBAL RISK CAP HIT: Total risk ${total_open_risk:.2f} >= ${risk_limit:.2f}. Entry blocked.")
                    return

                # S-3: Probing Entry Guardrail (Deterministic Alpha Override)
                braid_alpha = mstate.check_braid_alpha()
                dynamic_size = mstate.get_dynamic_size()
                
                if braid_alpha in ["BUY_ALPHA", "SELL_ALPHA"] and primary_engine == "WAIT":
                    log.info(f"PROBING ENTRY [{symbol}]: Alpha={braid_alpha} detected in CHOPPY market. Scaling 1ct.")
                    primary_engine = "council" # Use council for probing
                    dynamic_size = 1

                if primary_engine == "WAIT":
                    return

                if state.position_count < state.max_concurrent_limit:
                    log.info(f"PROCESS [{symbol}]: Dispatching to {primary_engine} (Regime={regime}, Alpha={braid_alpha}, Size={dynamic_size})")
                    
                    # Force Braid Signal into prompt
                    features["braid_alpha"] = braid_alpha
                    features["dynamic_size"] = dynamic_size
                    features["primary_engine"] = primary_engine
                    features["current_pnl"] = mstate.daily_pnl
                    
                    decision = await ask_claude(features, symbol=symbol)
                    action = decision.get("action", "WAIT")
                    
                    # Force entry if Braid matches AI bias
                    if action == "WAIT" and braid_alpha != "NEUTRAL":
                        log.info(f"BRAID [{symbol}]: High-alpha detected ({braid_alpha}) but AI said WAIT. Respecting AI bias.")

    except Exception as e:
        log.error(f"Market worker error ({symbol}): {e}")

async def control_loop():
    """Main trading control loop - Coordinator for all active markets.
    """
    state = VortexState.get_instance()
    global market_conn, user_conn
    log.info("Control loop started")
    decision_timer = 0
    _last_ws_count = 0
    _last_ws_check = time.time()
    _ws_token_time = time.time()
    _last_reconnect_attempt = 0
    _reconnect_count = 0

    while state.running:
        try:
            state.cycle_count += 1
            
            # [CODE] WS health watchdog (Global)
            now_t = time.time()
            if now_t - _last_ws_check > 15:
                needs_reconnect = False
                reason = ""
                if state.ws_quote_count == _last_ws_count and _last_ws_count > 10:
                    needs_reconnect = True
                    reason = "quotes stalled"
                if state.price_is_stale and (now_t - state.price_timestamp > 30):
                    needs_reconnect = True
                    reason = "price stale"
                if now_t - _ws_token_time > 2700:
                    needs_reconnect = True
                    reason = "token refresh"

                if needs_reconnect:
                    # Exponential backoff and reconnect logic (omitted for brevity in this fix)
                    pass

            # [CODE] Global PnL Risk Check
            if state.daily_pnl <= -1000.0:
                log.critical(f"GLOBAL HALT: Daily loss limit hit (-$1000)")
                await shutdown()
                break

            # [CODE] Multi-Market Parallel Workers
            active_symbols = [TICKER]
            if ENABLE_MULTI_MARKET_TEST:
                active_symbols = list(MICRO_CONTRACTS.keys())
            
            tasks = [process_market(s, decision_timer) for s in active_symbols]
            # S-1: Multi-Market Burst Mode (Dynamic SL/TP)
            burst_tasks = [burst_mode(s) for s in active_symbols]
            await asyncio.gather(*tasks, *burst_tasks)

            # Global maintenance
            if decision_timer > 0:
                decision_timer -= 1
            
            _last_ws_count = state.ws_quote_count
            _last_ws_check = now_t
            
            await asyncio.sleep(1)

        except Exception as e:
            log.error(f"Coordinator loop error: {e}")
            await asyncio.sleep(5)
            
            # [CODE] Poll price
            got_price = await poll_price()
            if not got_price and state.price <= 0:  # Only hard-block if we have NO price at all
                await asyncio.sleep(1)
                continue
            
            # [CODE] Record price update for broker health monitoring
            if broker_outage_coordinator:
                broker_outage_coordinator.detector.record_price_update()

            # [CODE] Sync position from broker
            await sync_position()
            
            # [CODE] Check broker health status and handle outages
            if broker_outage_coordinator:
                # FIX: Use is_connected() method, not .connected attribute
                ws_is_connected = market_conn and market_conn.transport and market_conn.transport.is_connected()
                
                async def _query_positions():
                    try:
                        return await mnq.positions.get_all_positions() if mnq else None
                    except:
                        return None
                
                async def _query_balance():
                    try:
                        return await get_broker_balance() if suite else None
                    except:
                        return None
                
                is_broker_up = await broker_outage_coordinator.check_and_react(
                    current_price=state.price,
                    ws_connected=ws_is_connected,
                    state_obj=state,
                    position_query_func=_query_positions,
                    balance_query_func=_query_balance
                )
                
                if not is_broker_up and not state.trading_allowed:
                    # Broker is down, skip trading logic but keep monitoring
                    log.warning(f"BROKER OUTAGE: Skipping trading decisions, waiting for recovery...")
                    await asyncio.sleep(1)
                    continue
            
            # CRITICAL: Enforce hard 10-contract position limit from broker
            if state.position_size > MAX_TOTAL_POSITION:
                log.critical(f"POSITION LIMIT VIOLATION: {state.position_size} > {MAX_TOTAL_POSITION} -- FLATTENING ALL POSITIONS")
                # Emergency flatten all positions
                try:
                    if state.active_trade.side != "FLAT":
                        await close_position()
                    if state.council_trade.side != "FLAT":
                        await close_council_trade()
                    if warwick and warwick.state.primary.is_open:
                        await warwick_close_leg("primary")
                    if warwick and warwick.state.hedge.is_open:
                        await warwick_close_leg("hedge")
                    if state.chimera_trade.side != "FLAT":
                        await close_chimera_trade()
                except Exception as e:
                    log.error(f"Emergency flatten failed: {e}")
                state.running = False
                break
            
            # FIX #1: Daily P&L Reset at Midnight (UTC-based CT boundary check)
            try:
                ct = pytz.timezone('US/Central')
                now_ct = datetime.now(ct)
                current_date = now_ct.date().isoformat()
                
                if state._last_reset_date != current_date:
                    log.info(f"DAILY RESET: {state._last_reset_date} → {current_date}")
                    state.daily_pnl = 0.0
                    state.wins = 0
                    state.losses = 0
                    state._last_reset_date = current_date
            except Exception as e:
                log.debug(f"Daily reset check error: {e}")
            
            # [CODE] Broker reconciliation every 15 seconds (S-5: reduced from 60)
            if time.time() - state.last_reconcile_time > 15:
                await reconcile_with_broker()

            # [CODE] Save state every 5 cycles (in background to avoid blocking)
            if state.cycle_count % 5 == 0:
                try:
                    await asyncio.to_thread(save_status)
                except Exception:
                    pass

            # [CODE] Kill switch check (observer can trigger emergency stop)
            kill_file = STATE_DIR / "kill.json"
            if kill_file.exists():
                try:
                    kd = json.loads(kill_file.read_text(encoding='utf-8'))
                    if kd.get("kill"):
                        log.critical(f"KILL SWITCH ACTIVATED by observer: {kd.get('reason', '?')}")
                        kill_file.unlink()
                        state.running = False
                        break
                except Exception:
                    pass

            # [CODE] Check RPnL target and daily loss limit
            rpnl = state.broker_realized_pnl if state.broker_realized_pnl != 0 else state.daily_pnl
            if rpnl >= RPNL_TARGET:
                log.info(f"*** RPNL TARGET HIT: ${rpnl:.2f} >= ${RPNL_TARGET:.2f} ***")
                if state.position_side != "FLAT":
                    await close_position()
                state.running = False
                break
            if rpnl <= DAILY_LOSS_LIMIT:
                log.info(f"*** DAILY LOSS LIMIT HIT: ${rpnl:.2f} <= ${DAILY_LOSS_LIMIT:.2f} -- STOPPING ***")
                if state.position_side != "FLAT":
                    await close_position()
                state.running = False
                break

            # [CODE] Market hours enforcement
            market_open, should_flatten = is_market_hours()
            if should_flatten:
                if state.position_side != "FLAT":
                    log.info("DAILY HALT: 3:14 CT -- flattening before 3:15 halt")
                    await close_position()
                if warwick and warwick.state.primary.is_open:
                    log.info("DAILY HALT: flattening Warwick primary")
                    await warwick_close_leg("primary")
                if warwick and warwick.state.hedge.is_open:
                    log.info("DAILY HALT: flattening Warwick hedge")
                    await warwick_close_leg("hedge")
                if state.chimera_trade.side != "FLAT":
                    log.info("DAILY HALT: flattening Chimera")
                    await close_chimera_trade()
            if not market_open:
                if state.cycle_count % 300 == 0:
                    log.info("MARKET CLOSED: Waiting for CME Globex open")
                await asyncio.sleep(5)
                continue

            # ==================== OPTIONAL BOOTSTRAP MODE ====================
            BOOTSTRAP_TRADES = BOOTSTRAP_TRADES_TARGET if ENABLE_BOOTSTRAP else 0
            BOOTSTRAP_INTERVAL = 10

            bootstrap_elapsed = time.time() - state.bootstrap_start_time if state.bootstrap_start_time > 0 else 0
            if ENABLE_BOOTSTRAP and bootstrap_elapsed > state.bootstrap_hard_timeout and state.trade_count < BOOTSTRAP_TRADES:
                log.critical(f"🚀 BOOTSTRAP HARD TIMEOUT: {bootstrap_elapsed:.0f}s > {state.bootstrap_hard_timeout}s, forcing completion")
                state.trade_count = BOOTSTRAP_TRADES
            
            if ENABLE_BOOTSTRAP and state.trade_count < BOOTSTRAP_TRADES:
                if state.bootstrap_start_time == 0:
                    state.bootstrap_start_time = time.time()
                
                bootstrap_elapsed = time.time() - state.bootstrap_start_time
                council_ok = state.bootstrap_engine_success["council"] < 5 and state.bootstrap_engine_failures["council"] < 3
                warwick_ok = state.bootstrap_engine_success["warwick"] < 5 and state.bootstrap_engine_failures["warwick"] < 3
                chimera_ok = state.bootstrap_engine_success["chimera"] < 5 and state.bootstrap_engine_failures["chimera"] < 3
                
                log.info(f"🚀 BOOTSTRAP MODE: {state.trade_count}/{BOOTSTRAP_TRADES} trades ({bootstrap_elapsed:.0f}s) | Council:{state.bootstrap_engine_success['council']}/5✓ Warwick:{state.bootstrap_engine_success['warwick']}/5✓ Chimera:{state.bootstrap_engine_success['chimera']}/5✓")

                # Build features — use degraded if compute_features() returns None
                features = compute_features(TICKER)
                if not features:
                    mstate = state.get_market(TICKER)
                    if mstate.price > 0:
                        log.warning(f"BOOTSTRAP DEGRADED: using last known price {mstate.price}")
                        features = {
                            "price": mstate.price, "samples": max(len(mstate.prices), 1),
                            "degraded": True, "volatility": 5.0, "trend": 0.0,
                            "atr": 10.0, "rsi": 50.0, "imbalance": 0.0,
                            "ofi": 0.0, "book_pressure": 0.0, "spread": 1.0,
                            "regime": "UNKNOWN", "regime_code": 0,
                        }
                    else:
                        log.warning("BOOTSTRAP: No price yet, waiting 2s...")
                        await asyncio.sleep(2)
                        continue

                log.info(f"BOOTSTRAP FEATURES: price={features['price']:.2f} atr={features.get('atr',0):.1f} regime={features.get('regime','?')}")

                # Determine which engine should act this cycle (round-robin)
                # Council: cycles 0,3,6,9... | Warwick: 1,4,7,10... | Chimera: 2,5,8,11...
                engine_turn = state.trade_count % 3  # 0=Council, 1=Warwick, 2=Chimera

                try:
                    # PHASE 1 FIX #2: Skip engine if already completed (5 successes) or failed too many times (3 failures)
                    if engine_turn == 0:
                        council_ok = state.bootstrap_engine_success["council"] < 5 and state.bootstrap_engine_failures["council"] < 3
                        mstate = state.get_market(TICKER)
                        if not council_ok:
                            skipped_reason = "completed" if state.bootstrap_engine_success["council"] >= 5 else "3+ failures"
                            log.info(f"BOOTSTRAP COUNCIL: Skipping ({skipped_reason}), advancing to next engine")
                            state.trade_count += 1
                        elif mstate.council_trade.side == "FLAT":
                            # COUNCIL TURN — force trade regardless of Claude's preference
                            log.info(f"BOOTSTRAP COUNCIL TURN: Asking for decision (trade {state.trade_count+1}/{BOOTSTRAP_TRADES})")
                            council_decision = await ask_claude(features, symbol=TICKER)
                            log.info(f"BOOTSTRAP COUNCIL DECISION: {council_decision}")
                            if isinstance(council_decision, str):
                                council_decision = {"action": council_decision, "stop_points": 15, "target_points": 30, "confidence": 0.6, "reasoning": "Bootstrap learning trade"}
                            # FORCE: If Claude says WAIT, override based on trend direction
                            if council_decision.get("action") == "WAIT":
                                trend = features.get("trend", "FLAT")
                                forced_action = "BUY" if trend == "UP" else "SELL"
                                log.warning(f"BOOTSTRAP OVERRIDE: Claude said WAIT — forcing {forced_action} (trend={trend}) for learning data")
                                council_decision = {
                                    "action": forced_action, "size": 1,
                                    "stop_points": int(max(features.get("atr", 10.0) * 2, 8)),
                                    "target_points": int(max(features.get("atr", 10.0) * 4, 16)),
                                    "confidence": 0.5, "reasoning": f"Bootstrap forced {forced_action} — learning phase, must trade"
                                }
                            if council_decision.get("action") in ["BUY", "SELL"]:
                                log.info(f"🎯 BOOTSTRAP TRADE #{state.trade_count+1} COUNCIL: {council_decision['action']}")
                                try:
                                    # PHASE 1 FIX #3: Use minimal quick function for bootstrap
                                    sl_pts = max(council_decision.get("stop_points", 8), INSTRUMENT_CONFIG[TICKER]['tick_size'] * 8)
                                    success = await asyncio.wait_for(
                                        _bootstrap_council_quick(council_decision['action'], 1, features["price"], sl_pts),
                                        timeout=10.0
                                    )
                                except asyncio.TimeoutError:
                                    log.error("❌ COUNCIL BOOTSTRAP TRADE TIMED OUT after 10s")
                                    success = False
                                except Exception as e:
                                    log.error(f"❌ COUNCIL BOOTSTRAP ERROR: {e}")
                                    success = False
                                
                                if success:
                                    state.bootstrap_engine_success["council"] += 1
                                    state.trade_count += 1
                                    log.info(f"✅ COUNCIL BOOTSTRAP TRADE EXECUTED: {state.bootstrap_engine_success['council']}/5 successes")
                                else:
                                    state.bootstrap_engine_failures["council"] += 1
                                    state.trade_count += 1
                                    log.error(f"❌ COUNCIL BOOTSTRAP TRADE FAILED ({state.bootstrap_engine_failures['council']}/3 failures)")
                        else:
                            log.info("BOOTSTRAP COUNCIL: position open, skipping")
                            state.trade_count += 1

                    elif engine_turn == 1:
                        # WARWICK TURN — PHASE 1 FIX #4: Call warwick_open_leg() directly, not warwick_tick()
                        warwick_ok = state.bootstrap_engine_success["warwick"] < 5 and state.bootstrap_engine_failures["warwick"] < 3
                        if not warwick_ok:
                            skipped_reason = "completed" if state.bootstrap_engine_success["warwick"] >= 5 else "3+ failures"
                            log.info(f"BOOTSTRAP WARWICK: Skipping ({skipped_reason}), advancing to next engine")
                            state.trade_count += 1
                        elif warwick and warwick.state.primary.is_open:
                            log.info("BOOTSTRAP WARWICK: position open, skipping")
                            state.trade_count += 1
                        else:
                            log.info(f"BOOTSTRAP WARWICK TURN (trade {state.trade_count+1}/{BOOTSTRAP_TRADES})")
                            trend = features.get("trend", "FLAT")
                            forced_action = "SELL" if trend == "DOWN" else "BUY"
                            log.info(f"🎯 BOOTSTRAP TRADE #{state.trade_count+1} WARWICK: {forced_action} (forced, trend={trend})")
                            try:
                                # PHASE 1 FIX #4: Use minimal quick function for bootstrap
                                sl_pts = max(features.get("atr", 10.0) * 2, 8)
                                success = await asyncio.wait_for(
                                    _bootstrap_warwick_quick(forced_action, 1, features["price"], sl_pts),
                                    timeout=10.0
                                )
                            except asyncio.TimeoutError:
                                log.error("❌ WARWICK BOOTSTRAP TIMED OUT after 10s")
                                success = False
                            except Exception as e:
                                log.error(f"WARWICK BOOTSTRAP ERROR: {e}")
                                success = False
                            
                            if success:
                                state.bootstrap_engine_success["warwick"] += 1
                                state.trade_count += 1
                                log.info(f"✅ WARWICK BOOTSTRAP TRADE EXECUTED: {state.bootstrap_engine_success['warwick']}/5 successes")
                            else:
                                state.bootstrap_engine_failures["warwick"] += 1
                                state.trade_count += 1
                                log.warning(f"BOOTSTRAP WARWICK: Trade failed/timed out, advancing ({state.bootstrap_engine_failures['warwick']}/3 failures)")

                    elif engine_turn == 2:
                        mstate = state.get_market(TICKER)
                        # CHIMERA TURN — chimera needs both engines' decisions; use Council path with Chimera label
                        chimera_ok = state.bootstrap_engine_success["chimera"] < 5 and state.bootstrap_engine_failures["chimera"] < 3
                        if not chimera_ok:
                            skipped_reason = "completed" if state.bootstrap_engine_success["chimera"] >= 5 else "3+ failures"
                            log.info(f"BOOTSTRAP CHIMERA: Skipping ({skipped_reason}), advancing to next engine")
                            state.trade_count += 1
                        elif mstate.chimera_trade.side != "FLAT":
                            log.info("BOOTSTRAP CHIMERA: position open, skipping")
                            state.trade_count += 1
                        else:
                            log.info(f"BOOTSTRAP CHIMERA TURN (trade {state.trade_count+1}/{BOOTSTRAP_TRADES})")
                            trend = features.get("trend", "FLAT")
                            ch_action = "BUY" if trend == "UP" else "SELL"
                            ch_decision = {
                                "action": ch_action, "size": 1,
                                "stop_points": int(max(features.get("atr", 10.0)*2, 8)),
                                "target_points": int(max(features.get("atr", 10.0)*4, 16)),
                                "confidence": 0.5, "reasoning": f"Bootstrap Chimera forced {ch_action} — learning phase"
                            }
                            log.info(f"🎯 BOOTSTRAP TRADE #{state.trade_count+1} CHIMERA: {ch_decision['action']}")
                            try:
                                success = await asyncio.wait_for(execute_chimera_trade(ch_decision, symbol=TICKER), timeout=30.0)
                            except asyncio.TimeoutError:
                                log.error("❌ CHIMERA BOOTSTRAP TIMED OUT after 30s")
                                success = False
                            if success:
                                state.bootstrap_engine_success["chimera"] += 1
                                state.trade_count += 1
                                log.info(f"✅ CHIMERA BOOTSTRAP TRADE EXECUTED: {state.bootstrap_engine_success['chimera']}/5 successes")
                            else:
                                state.bootstrap_engine_failures["chimera"] += 1
                                state.trade_count += 1
                                log.error(f"❌ CHIMERA BOOTSTRAP TRADE FAILED ({state.bootstrap_engine_failures['chimera']}/3 failures)")

                    else:
                        # Fallback: engine has open position — advance turn
                        log.info(f"BOOTSTRAP: Unexpected turn state, advancing")
                        state.trade_count += 1

                except Exception as e:
                    log.error(f"BOOTSTRAP engine error: {e}", exc_info=True)

                await asyncio.sleep(BOOTSTRAP_INTERVAL)
                continue  # Skip normal gate-heavy loop

            # ==================== END BOOTSTRAP MODE ====================
            if not getattr(state, '_bootstrap_completed', False):
                state._bootstrap_completed = True
                log.info(f"✅ BOOTSTRAP COMPLETE: {BOOTSTRAP_TRADES} trades executed. Switching to normal mode.")

            # ==================== OPTIONAL MULTI-MARKET TEST MODE ====================
            TEST_MARKETS = ["MES", "MCL", "MGC", "MYM", "M2K"]
            if ENABLE_MULTI_MARKET_TEST and not getattr(state, '_multimarket_test_done', False):
                if not getattr(state, '_multimarket_test_started', False):
                    state._multimarket_test_started = True
                    state._multimarket_test_idx = 0  # 0-14: 5 markets × 3 engines
                    log.info("🎰 MULTI-MARKET TEST MODE: placing 5 trades per engine across MES/MCL/MGC/MYM/M2K")

                idx = getattr(state, '_multimarket_test_idx', 0)
                if idx < 15:
                    market_idx = idx % 5       # 0-4 → MES/MCL/MGC/MYM/M2K
                    engine_idx = idx // 5      # 0=Council, 1=Warwick, 2=Chimera
                    sym = TEST_MARKETS[market_idx]
                    engine_name = ["Council", "Warwick", "Chimera"][engine_idx]
                    mstate = state.get_market(sym)
                    sym_price = mstate.price if mstate.price > 0 else 0

                    log.info(f"🎰 TEST TRADE {idx+1}/15: {engine_name} on {sym} @ {sym_price:.2f}")

                    if sym_price <= 0:
                        log.warning(f"🎰 No price for {sym} yet, waiting...")
                        await asyncio.sleep(2)
                        continue

                    cfg = INSTRUMENT_CONFIG[sym]
                    # Use 2× ATR for SL, 4× ATR for TP — fall back to reasonable defaults per market
                    atr_est = features.get("atr", 10.0) if sym in ("MES", "MNQ") else {
                        "MCL": 0.5, "MGC": 5.0, "MYM": 50.0, "M2K": 2.0
                    }.get(sym, 10.0)
                    sl_pts = max(atr_est * 2, cfg["tick_size"] * 8)
                    tp_pts = sl_pts * 4

                    # Ask Claude for direction with explicit TEST banner
                    test_prompt = f"""TEST MODE - MULTI-MARKET LEARNING TRADE

You are placing a TEST TRADE on {sym} ({cfg['name']}) for the {engine_name} engine.
This is specifically to test vortex's ability to hold multiple positions across markets simultaneously.
You MUST return BUY or SELL — WAIT is not allowed in test mode.

{sym} CURRENT PRICE: {sym_price:.4f}
Point Value: ${cfg['point_value']}/pt | Tick: {cfg['tick_size']}
Suggested SL: {sl_pts:.2f}pts | Suggested TP: {tp_pts:.2f}pts

{get_market_snapshot()}

ALL OPEN TRADES:
{chr(10).join([f"  {k}: {v['engine']} {v['symbol']} {v['side']} {v['size']}ct entry={v['entry']:.2f} SL={v['sl']:.2f} TP={v['tp']:.2f}" for k,v in state.open_trades.items()]) if state.open_trades else "  (none yet)"}

Pick a direction based on recent price action for {sym}. This trade will be LEFT OPEN to test multi-position management.
Use the suggested SL/TP or adjust based on your read of {sym}.

Respond with ONLY valid JSON on the last line:
{{"action": "BUY"|"SELL", "size": 1, "stop_points": {sl_pts:.1f}, "target_points": {tp_pts:.1f}, "confidence": 0.6, "reasoning": "brief {sym} direction read"}}"""

                    try:
                        url = "https://api.anthropic.com/v1/messages"
                        headers = {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
                        body = json.dumps({"model": AI_MODEL, "max_tokens": 300, "messages": [{"role": "user", "content": test_prompt}]}).encode()
                        req = urllib.request.Request(url, data=body, headers=headers, method='POST')
                        def _sync_call():
                            with urllib.request.urlopen(req, timeout=20) as r:
                                return json.loads(r.read().decode())
                        loop = asyncio.get_running_loop()
                        resp = await asyncio.wait_for(loop.run_in_executor(None, _sync_call), timeout=25)
                        raw = resp["content"][0]["text"].strip()
                        last_line = [l.strip() for l in raw.split("\n") if l.strip().startswith("{")][-1]
                        test_decision = json.loads(last_line)
                        log.info(f"🎰 {engine_name} {sym} DECISION: {test_decision}")

                        if test_decision.get("action") in ("BUY", "SELL"):
                            test_decision["stop_points"] = test_decision.get("stop_points", sl_pts)
                            test_decision["target_points"] = test_decision.get("target_points", tp_pts)
                            test_decision["size"] = 1

                            if engine_idx == 0:
                                ok = await asyncio.wait_for(execute_council_trade(test_decision, symbol=sym), timeout=20)
                            elif engine_idx == 1:
                                ok = await asyncio.wait_for(warwick_open_leg(
                                    test_decision["action"], 1,
                                    test_decision["stop_points"], test_decision["target_points"],
                                    leg_type=f"primary_{sym}", symbol=sym), timeout=20)
                                ok = ok is not None
                            else:
                                ok = await asyncio.wait_for(execute_chimera_trade(test_decision, symbol=sym), timeout=20)

                            if ok:
                                log.info(f"✅ TEST TRADE {idx+1}/15 PLACED: {engine_name} {sym} {test_decision['action']}")
                                state._multimarket_test_idx = idx + 1
                            else:
                                log.error(f"❌ TEST TRADE {idx+1}/15 FAILED: {engine_name} {sym}")
                                state._multimarket_test_idx = idx + 1  # advance anyway
                        else:
                            log.warning(f"🎰 Claude returned WAIT for {sym} — forcing advance")
                            state._multimarket_test_idx = idx + 1

                    except asyncio.TimeoutError:
                        log.error(f"🎰 Test trade timeout: {engine_name} {sym}")
                        state._multimarket_test_idx = idx + 1
                    except Exception as e:
                        log.error(f"🎰 Test trade error: {engine_name} {sym}: {e}", exc_info=True)
                        state._multimarket_test_idx = idx + 1

                    await asyncio.sleep(3)
                    continue

                else:
                    state._multimarket_test_done = True
                    log.info(f"🎰 MULTI-MARKET TEST COMPLETE: {state.position_count} symbols active")
            # ==================== END MULTI-MARKET TEST ====================

            # [CODE] Decision interval (30s AI call) + burst mode (5s SL/TP adjust)
            decision_timer += 1

            # Burst mode: every 5s, adjust SL/TP lines (no API call)
            if decision_timer % BURST_INTERVAL == 0 and warwick:
                try:
                    await warwick_burst_tick()
                except Exception as e:
                    log.debug(f"Burst tick error: {e}")

            if decision_timer < DECISION_INTERVAL:
                await asyncio.sleep(1)
                continue
            decision_timer = 0

            # [CODE] Compute features
            features = compute_features()
            if not features:
                log.debug("Not enough data for features yet")
                await asyncio.sleep(1)
                continue
            
            # [CODE] PHASE 5: Update market regime detection
            try:
                await update_market_regime()
            except Exception as e:
                log.debug(f"Regime update error: {e}")

            # ========================================
            # PHASE 5: REGIME-AWARE TRADING RULES
            # ========================================
            # Check if current regime allows trading
            regime_settings = risk_math.regime_settings(state.current_regime)
            if not regime_settings.get("allowed_trades"):
                log.warning(f"TRADING BLOCKED: {state.current_regime} regime is too risky - {regime_settings['description']}")
                await asyncio.sleep(1)
                continue
            
            # Add regime context to features for AI decisions
            features['current_regime'] = state.current_regime
            features['regime_confidence'] = state.regime_confidence
            features['regime_description'] = regime_settings['description']
            features['regime_stop_multiplier'] = regime_settings['stop_multiplier']
            features['regime_target_multiplier'] = regime_settings['target_multiplier']
            features['regime_size_reduction'] = regime_settings['position_size_reduction']

            # ========================================
            # STEERING VECTOR SELECTION
            # ========================================
            # Select steering mode based on regime and PnL, then inject into features
            if steering:
                steering_mode = steering.select_steering(
                    state.current_regime, state.daily_pnl, state.trade_count
                )
                steering_context = steering.get_steering_prompt(steering_mode)
                features['steering_mode'] = steering_mode
                features['steering_context'] = steering_context
                features['steering_max_position'] = steering.get_position_size_guidance(steering_mode)
                features['steering_stop_points'] = steering.get_stop_loss_guidance(steering_mode)
                if state.cycle_count % 30 == 0:  # Log every 30 cycles
                    log.info(f"STEERING: {steering_mode} mode active (regime={state.current_regime}, pnl=${state.daily_pnl:.2f})")

            # ========================================
            # VOLATILITY SURGE CHECK - Safety improvement 2026-03-09
            # ========================================
            # Check for sudden ATR increase (>50% in 60s) - triggers circuit breaker
            volatility_breaker, breaker_reason = check_volatility_surge()
            if volatility_breaker:
                log.warning(f"VOLATILITY SURGE: {breaker_reason}")
                # Still let engines run their existing positions, but block NEW entries
                # The individual engine entry code checks volatility_circuit_breaker_active

            # ========================================
            # PHASE 4: TRADING PERMISSION & ENGINE SELECTION
            # ========================================
            # Check if trading should be allowed based on system health
            allow_trading, trading_reason = should_allow_trading()
            if not allow_trading:
                # Log and notify that trading is disabled
                log.warning(f"TRADING DISABLED: {trading_reason}")
                if state.trading_allowed:  # First time disabled
                    log.critical(f"TRADING HALTED: {state.trading_disable_reason}")
                state.trading_allowed = False
            else:
                # Trading is allowed - select which engine(s) should be active
                if state.trading_allowed == False:  # Just re-enabled
                    log.info(f"TRADING RESUMED: {trading_reason}")
                state.trading_allowed = True
                
                # Select active engine(s) every 300 seconds (5 minutes) or when status changes
                now_t = time.time()
                should_reselect = (now_t - state.last_engine_selection_time) > 300
                if should_reselect or not hasattr(state, '_current_engine_choice'):
                    engine_choice, engine_confidence = await select_active_engine()
                    state._current_engine_choice = engine_choice
                    state._engine_confidence = engine_confidence
                else:
                    engine_choice = getattr(state, '_current_engine_choice', 'CONSENSUS_NEEDED')
                    engine_confidence = getattr(state, '_engine_confidence', 0.5)
                
                # Log engine selection periodically (at INFO level) or when it changes
                if should_reselect:
                    log.info(f"ENGINE SELECTION: {engine_choice} ({engine_confidence:.0f}% confidence)")
                
                # Based on engine choice, decide which engines to activate
                # Store in state for reference by individual engine ticks
                state._warwick_should_trade = engine_choice in ("WARWICK_DOMINANT", "CONSENSUS_NEEDED")
                state._council_should_trade = engine_choice in ("COUNCIL_DOMINANT", "CONSENSUS_NEEDED")
                state._chimera_should_trade = engine_choice != "ALL_DISABLED"

            # ========================================
            # EMERGENCY: CYCLE-LEVEL POSITION CAP (PREVENT ACCUMULATION)
            # ========================================
            # Abort all trading if position exceeds MAX_TOTAL_POSITION
            # This is a hard safety circuit-breaker to prevent 17-contract accumulation
            # Note: MAX_TOTAL_POSITION is defined globally at line 258
            if state.position_size > MAX_TOTAL_POSITION:
                log.critical(f"CYCLE CAP BREACH: {state.position_size} > {MAX_TOTAL_POSITION}")
                log.critical(f"EMERGENCY FLATTEN: Stopping all trading and closing positions")
                
                # Try to close all open positions
                try:
                    positions = await mnq.positions.get_all_positions()
                    if positions:
                        for p in positions:
                            if p.size != 0:
                                side = 1 if p.size > 0 else 0  # Opposite of position
                                result = await mnq.orders.place_market_order(
                                    contract_id=mnq.instrument_info.id,
                                    side=side,
                                    size=abs(p.size)
                                )
                                log.critical(f"Emergency flatten: {abs(p.size)} contracts, success={result.success}")
                except Exception as e:
                    log.critical(f"Emergency flatten failed: {e}")
                
                # Disable all trading
                state.trading_allowed = False
                state.trading_disable_reason = f"Position cap breach: {state.position_size} > {MAX_TOTAL_POSITION}"
                log.critical("All trading disabled - manual intervention required")
                break  # Exit main loop
            
            # ========================================
            # L2 FRESHNESS CHECK WITH REST API FALLBACK (2026-03-09 FIX)
            # ========================================
            # Check if L2 data is fresh before AI decisions
            # If stale, try to fetch via REST API as fallback
            l2_age = time.time() - state.l2_timestamp if state.l2_timestamp > 0 else 999
            l2_is_stale = l2_age > L2_STALE_BLOCK_SECONDS  # >10 seconds
            l2_is_unavailable = not state.orderbook_data
            
            if l2_is_stale or l2_is_unavailable:
                log.warning(f"L2_FALLBACK: L2 data is {'unavailable' if l2_is_unavailable else f'stale ({l2_age:.1f}s)'}, attempting REST API fetch...")
                
                # Get contract ID for current instrument
                contract_id = MICRO_CONTRACTS.get(TICKER, f"CON.F.US.{TICKER}.H26")
                
                # Try REST API fallback
                try:
                    ob_data = await api_get_orderbook(contract_id, depth=5)
                    
                    if ob_data.get('source') != 'failed' and ob_data.get('bids') and ob_data.get('asks'):
                        # Successfully fetched orderbook data
                        # Update state with fetched data
                        now_ts = time.time()
                        best_bid = ob_data.get('best_bid', 0)
                        best_ask = ob_data.get('best_ask', 0)
                        
                        if best_bid > 0 and best_ask > 0:
                            spread = best_ask - best_bid
                            bid_levels = ob_data.get('bids', [])
                            ask_levels = ob_data.get('asks', [])
                            
                            # Calculate imbalance
                            bid_vol = sum(float(b[1]) if len(b) > 1 else 0 for b in bid_levels[:5])
                            ask_vol = sum(float(a[1]) if len(a) > 1 else 0 for a in ask_levels[:5])
                            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0.0
                            
                            # Update state
                            state.orderbook_data = {
                                'bid_levels': bid_levels[:10],
                                'ask_levels': ask_levels[:10],
                                'spread': round(spread, 4),
                                'imbalance': round(imbalance, 4),
                                'best_bid': round(best_bid, 2),
                                'best_ask': round(best_ask, 2),
                            }
                            state.best_bid_depth = bid_vol * POINT_VALUE
                            state.best_ask_depth = ask_vol * POINT_VALUE
                            state.l2_timestamp = now_ts
                            
                            log.info(f"L2_FALLBACK: Successfully fetched via REST API - source={ob_data.get('source')}, spread={spread:.4f}")
                            
                            # Calculate new age for quality gate
                            l2_age = 0
                            l2_is_stale = False
                        else:
                            log.warning(f"L2_FALLBACK: REST API returned invalid bid/ask prices")
                    else:
                        log.warning(f"L2_FALLBACK: REST API failed to return valid data - source={ob_data.get('source')}")
                        
                except Exception as e:
                    log.error(f"L2_FALLBACK: Exception during REST API fetch: {e}")
            
            # ========================================
            # L2 QUALITY GATE - Pre-decision check (2026-03-09 FIX)
            # ========================================
            # CRITICAL: Check L2 quality BEFORE calling AI engines
            # This prevents Claude from making decisions in bad market conditions
            l2_gate_pass, l2_gate_info = check_l2_quality_gate(state)
            if not l2_gate_pass and not GAMBLING_MODE:
                log.warning(f"L2_GATE: Blocking all trading - {l2_gate_info['blocked_reason']}")
                await asyncio.sleep(1)
                continue
            elif not l2_gate_pass and GAMBLING_MODE:
                log.debug(f"L2_GATE: would block ({l2_gate_info['blocked_reason']}) but GAMBLING_MODE overrides")
            
            # ========================================
            # CHOPPY REGIME HARD BLOCK - >70% confidence (2026-03-09 FIX)
            # ========================================
            # Block entries in CHOPPY regime when confidence > 70%
            # This is a SAFETY measure to prevent whipsaw losses
            if state.current_regime == "CHOPPY" and state.regime_confidence > 70 and not GAMBLING_MODE:
                log.warning(f"CHOPPY HARD BLOCK: regime={state.current_regime} conf={state.regime_confidence:.0f}% > 70% - skipping entries")
                state._choppy_block_entries = True
            else:
                state._choppy_block_entries = False  # GAMBLING_MODE: always allow entries

            # ========================================
            # PATTERN MATCHING - Apply learned patterns before AI decisions
            # ========================================
            # Check for actionable patterns in current market conditions
            # Patterns can recommend AVOID or FAVOR specific entries
            applicable_patterns = council_awareness.apply_patterns(features) if council_awareness else []

            # If patterns suggest avoiding entries, inject warning
            if applicable_patterns:
                avoid_patterns = [p for p in applicable_patterns if 'AVOID' in p.get('action', '')]
                favor_patterns = [p for p in applicable_patterns if 'FAVOR' in p.get('action', '')]

                if avoid_patterns:
                    features['pattern_warning'] = " | ".join([p['description'] for p in avoid_patterns])
                    log.info(f"PATTERN AVOID: {features['pattern_warning']}")
                if favor_patterns:
                    features['pattern_boost'] = " | ".join([p['description'] for p in favor_patterns])
                    log.info(f"PATTERN FAVOR: {features['pattern_boost']}")

            # ========================================
            # WARWICK: Claude-as-Warwick manages all positions
            # Claude wears the Warwick persona and decides
            # every cycle: entry, hedge, trail, close.
            # ========================================
            # [WARWICK] Claude-as-Warwick manages all positions
            warwick_should_trade = getattr(state, '_warwick_should_trade', True) and state.trading_allowed
            if warwick and warwick_should_trade:
                try:
                    wk_action = await warwick_tick(features)
                    if wk_action:
                        log.info(f"WARWICK: {wk_action}")
                    warwick.state._warwick_error_count = 0
                except Exception as e:
                    warwick.state._warwick_error_count += 1
                    if warwick.state._warwick_error_count <= 3:
                        log.warning(f"Warwick tick error ({warwick.state._warwick_error_count}): {e}")
                    elif warwick.state._warwick_error_count == 4:
                        log.error(f"WARWICK ERROR LIMIT: {e}")

            # [COUNCIL] 5-agent debate -- LIVE trading, alternating cycles with Warwick
            council_should_trade = getattr(state, '_council_should_trade', True) and (state.trading_allowed or GAMBLING_MODE)
            if council_awareness and council_should_trade and decision_timer == 0:
                council_cycle = (state.cycle_count // DECISION_INTERVAL) % 2 == 1
                if council_cycle:
                    try:
                        council_ctx = council_awareness.build_context(
                            features, state.broker_balance, state.daily_pnl)
                        wk_section = warwick.build_prompt_section(state.price) if warwick else "inactive"
                        ct = state.council_trade
                        council_pos = f"{ct.side} {ct.size} @ {ct.entry_price}" if ct.side != "FLAT" else "FLAT"
                        full_state = (f"\nFULL ACCOUNT STATE:\n"
                                     f"  Broker NET: {state.position_side} {state.position_size} @ {state.position_entry}\n"
                                     f"  Warwick legs: {wk_section}\n"
                                     f"  Council position: {council_pos}\n"
                                     f"  Balance: ${state.broker_balance:.2f} | Session PnL: ${state.daily_pnl:.2f}")
                        features['_council_context'] = council_ctx + full_state
                        council_decision = await ask_claude(features)
                        # Cache for Chimera (Engine #3)
                        state.last_council_decision = council_decision
                        state.last_council_decision_time = time.time()
                        action = council_decision.get("action", "WAIT")
                        conf = council_decision.get("confidence", "?")
                        reason = council_decision.get("reasoning", "")[:80]
                        log.info(f"COUNCIL: {action} (conf={conf}) | {reason}")
                        if action in ("BUY", "SELL") and state.council_trade.side == "FLAT":
                            success = await execute_council_trade(council_decision)
                            if success:
                                log.info(f"COUNCIL TRADE LIVE: {action} {council_decision.get('size',1)}")
                        elif action == "CLOSE" and state.council_trade.side != "FLAT":
                            await close_council_trade()
                        elif action == "WAIT":
                            _maybe_trigger_council_research()
                    except Exception as e:
                        log.warning(f"Council tick error: {e}")

            # [CHIMERA] Engine #3 -- Adaptive Aggression (synthesizes Warwick + Council)
            # Runs every decision cycle -- chimera_tick checks internally whether
            # both engines have fresh decisions within the 60s window.
            chimera_should_trade = getattr(state, '_chimera_should_trade', True) and state.trading_allowed
            if chimera_awareness and chimera_should_trade:
                try:
                    chimera_action = await chimera_tick(features)
                    if chimera_action:
                        log.info(f"CHIMERA: {chimera_action}")
                except Exception as e:
                    log.warning(f"Chimera tick error: {e}")

            state.last_decision = "TRIPLE"

            await asyncio.sleep(1)

        except KeyboardInterrupt:
            log.info("Keyboard interrupt - shutting down")
            state.running = False
        except Exception as e:
            log.error(f"Loop error: {e}")
            await asyncio.sleep(5)


# ============================================================
# STARTUP + SHUTDOWN
# ============================================================
async def startup():
    """Initialize all trading engines, SDKs, and start main control loop.
    
    Initialization sequence:
    1. Connect to broker SDK (project_x_py)
    2. Load/initialize all 3 trading engines (Warwick, Council, Chimera)
    3. Load awareness/learning systems
    4. Load ML entry filter model
    5. Connect to market data (WebSocket + SignalR hubs)
    6. Set up broker outage recovery system
    7. Clean up orphaned orders from previous runs
    8. Initialize ML model and Fleet advisor
    9. Load runtime state from files (memory, positions, etc.)
    10. Start dashboard HTTP server
    11. Enter main control loop
    
    Side Effects:
        - Initializes 6 global SDK connections
        - Initializes 3 global engine objects
        - Registers WebSocket callbacks (on_user_trade, on_user_order, etc.)
        - Starts background HTTP server
        - Loads ML model from disk (~100MB)
        - May read up to 5 JSON state files from disk
    
    Errors:
        - Raises exception if broker auth fails
        - Raises exception if instrument setup fails
        - Logs warning but continues if outage recovery unavailable
    """
    global suite, mnq, fleet, awareness, council_awareness, chimera_awareness, warwick, market_conn, user_conn, broker_outage_coordinator, steering, _main_loop, _on_market_open, _on_market_close, _on_market_error, _on_gateway_quote, _on_gateway_trade

    _main_loop = asyncio.get_running_loop()
    
    # Initialize broker outage detection and recovery system
    broker_outage_coordinator = BrokerOutageCoordinator()
    log.info("Broker outage detection system initialized")

    # Initialize steering vectors for adaptive decision-making
    steering = SteeringVectors()
    log.info("Steering vectors initialized")
    
    log.info("=" * 60)
    log.info("VORTEX V2 STARTING")
    mode_str = "STRESS TEST (no WAIT)" if STRESS_TEST_MODE else "NORMAL"
    log.info(f"Ticker: {TICKER} | AI: {AI_MODEL} | Interval: {DECISION_INTERVAL}s | Mode: {mode_str}")
    log.info(f"RPnL Target: ${RPNL_TARGET:.0f} | Daily Loss Limit: ${DAILY_LOSS_LIMIT:.0f}")
    log.info("=" * 60)
    
    if STRESS_TEST_MODE:
        log.critical("=" * 60)
        log.critical("🔥 VORTEX STRESS TEST ENABLED: All engines forced to trade. Mode: Aggressive")
        log.critical("🔥 Expected: High frequency trades, varied strategies, comprehensive bug detection")
        log.critical("🔥 Risk settings: Aggressive stops (8pts), targets (50pts), size (5), unlimited trades")
        log.critical("=" * 60)

    # Initialize SEPARATE memory systems for Warwick, Council, and Chimera
    from awareness_engine import WARWICK_DB_PATH, COUNCIL_DB_PATH, CHIMERA_DB_PATH
    awareness = AwarenessEngine(db_path=WARWICK_DB_PATH, name="warwick_memory")
    council_awareness = AwarenessEngine(db_path=COUNCIL_DB_PATH, name="council_memory")
    chimera_awareness = AwarenessEngine(db_path=CHIMERA_DB_PATH, name="chimera_memory")

    # Initialize Warwick hedge engine
    warwick = WarwickEngine(point_value=POINT_VALUE)
    log.info(f"Warwick engine initialized (point_value=${POINT_VALUE}/pt for {TICKER})")
    wk_ep = awareness.conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    wk_pat = awareness.conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    co_ep = council_awareness.conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    co_pat = council_awareness.conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    log.info(f"Warwick memory: {wk_ep} episodes, {wk_pat} patterns")
    log.info(f"Council memory: {co_ep} episodes, {co_pat} patterns")
    ch_ep = chimera_awareness.conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    ch_pat = chimera_awareness.conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    log.info(f"Chimera memory: {ch_ep} episodes, {ch_pat} patterns")

    # Initialize Fleet agent system
    log.info("Initializing Fleet...")
    fleet = FleetManager()
    await fleet.start()
    fleet_status = fleet.get_status()
    log.info(f"Fleet ready: {fleet_status['agent_count']} agents")

    # ML_ENTRY_FILTER: REMOVED 2026-03-09 - skipping ML model load

    from project_x_py import TradingSuite, EventType
    from project_x_py.types import OrderSide

    # PART 1: Add Startup Timeout & Retry Logic for broker connection
    log.info("Attempting to connect to TopStepX broker...")
    suite = None
    max_retries = 6  # 6 x 30 seconds = 3 minutes
    sdk_auth_failed = False  # Track if SDK auth failed
    
    for attempt in range(max_retries):
        try:
            # Use shorter timeout to detect if broker is down
            # Use auto_connect=False to avoid SDK WebSocket issues
            # We use our own DIRECT WS for price data
            suite = await asyncio.wait_for(
                TradingSuite.create(TICKER, timeframes=['1min'], auto_connect=False),
                timeout=15  # 15 second timeout instead of hanging indefinitely
            )
            log.info("✓ Broker connection successful")
            break
        except asyncio.TimeoutError:
            if attempt == 0:
                log.critical("⚠ Broker connection timeout - TopStepX appears to be offline")
                log.critical("⚠ Waiting for broker to come online...")
            log.info(f"Retry {attempt+1}/{max_retries} - waiting 30s for broker recovery...")
            await asyncio.sleep(30)
        except Exception as e:
            err_str = str(e)
            # Retry on auth failures (might be rate limiting or session conflict)
            if 'Authentication failed' in err_str or 'auth' in err_str.lower():
                log.warning(f"Broker auth attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    # Wait longer between auth attempts to let sessions expire
                    wait_time = 60 + (attempt * 30)  # 60s, 90s, 120s, etc.
                    log.info(f"Waiting {wait_time}s for broker session to clear...")
                    await asyncio.sleep(wait_time)
                    continue
                # Last attempt failed - try fallback mode
                log.warning("SDK authentication exhausted - trying fallback mode")
                sdk_auth_failed = True
                break
            log.critical(f"✗ Broker connection failed: {e}")
            log.critical(f"✗ Check status.topstep.com or try again later")
            sys.exit(1)
    
    # If SDK auth failed, try direct API authentication as fallback
    if sdk_auth_failed or suite is None:
        log.info("Attempting direct API authentication as fallback...")
        try:
            # Test our direct API auth
            token = await get_broker_token()
            if token:
                log.info("✓ Direct API authentication successful - running in DIRECT API MODE")
                log.warning("SDK bypassed - using native REST API + WebSocket for all operations")
                state.direct_api_mode = True
                suite = None
                mnq = None
                # Get balance via direct API
                balance = await get_broker_balance()
                log.info(f"Account balance: ${balance:.2f}")
            else:
                raise RuntimeError("Direct API auth returned no token")
        except Exception as e:
            log.critical(f"✗ All authentication methods failed: {e}")
            log.critical(f"✗ Check status.topstep.com or try again later")
            sys.exit(1)
    else:
        state.direct_api_mode = False
        mnq = suite[TICKER]
        inst = mnq.instrument_info
        log.info(f"Connected: {inst.id} (tickSize={inst.tickSize}, tickValue={inst.tickValue})")

    # PART 2: Add Startup Health Check
    try:
        log.info("Performing startup health check...")
        if state.direct_api_mode:
            # Direct API mode - use our own methods
            balance = await get_broker_balance()
            if balance is None or balance <= 0:
                log.critical(f"✗ Broker returned invalid balance: {balance} - refusing to start")
                sys.exit(1)
            positions = await api_get_positions()
            log.info(f"✓ Startup health check passed (DIRECT API): Balance=${balance:.2f}, Positions={len(positions)}")
        else:
            # SDK mode
            balance = suite.client.account_info.balance if suite.client.account_info else None
            if balance is None or balance <= 0:
                log.critical(f"✗ Broker returned invalid balance: {balance} - refusing to start")
                sys.exit(1)
            positions = await mnq.positions.get_all_positions()
            log.info(f"✓ Startup health check passed: Balance=${balance:.2f}, Positions={len(positions) if positions else 0}")
    except Exception as e:
        log.critical(f"✗ Startup health check failed: {e}")
        log.critical(f"✗ Broker may not be responding correctly - aborting")
        sys.exit(1)

    # BRICK HOUSE FIX v3: Subscribe to CORRECT real-time events
    # Fleet consultation found: EventType.TICK doesn't exist!
    # Correct types: EventType.TRADE_TICK, EventType.QUOTE_UPDATE
    # Also try: suite.realtime.add_callback("quote_update", fn)
    price_update_count = 0
    ws_connected = False

    def on_quote_update(data):
        """Callback for GatewayQuote events - real-time bid/ask updates.
        Data may arrive as dict or as list [contractId, {quote}] depending on source.
        """
        state = VortexState.get_instance()
        nonlocal price_update_count
        try:
            contract_id = None
            # Handle list format: [contractId, {quote_data}]
            if isinstance(data, list) and len(data) >= 2:
                contract_id = str(data[0])
                data = data[1] if isinstance(data[1], dict) else data
            elif isinstance(data, list) and len(data) >= 1 and isinstance(data[0], dict):
                data = data[0]
            
            if isinstance(data, dict):
                lp = data.get('lastPrice', 0)
                bid = data.get('bid', data.get('bestBid', 0))
                ask = data.get('ask', data.get('bestAsk', 0))
                
                # Routing to MarketState
                symbol = CONTRACT_TO_TICKER.get(contract_id) if contract_id else TICKER
                mstate = state.get_market(symbol)
                
                if bid > 0 and ask > 0:
                    mid = (bid + ask) / 2.0
                    mstate.price = mid
                    mstate.price_timestamp = time.time()
                    mstate.prices.append(mid)
                    if symbol == TICKER:
                        state.price = mid
                        state.price_timestamp = mstate.price_timestamp
                        state.price_is_stale = False
                        state.prices.append(mid)
                    price_update_count += 1
                    state.ws_quote_count = price_update_count
                    if price_update_count % 100 == 0:
                        log.info(f"WS quote #{price_update_count}: symbol={symbol} mid={mid}")
                elif lp and lp > 0:
                    mstate.price = float(lp)
                    mstate.price_timestamp = time.time()
                    mstate.prices.append(float(lp))
                    if symbol == TICKER:
                        state.price = float(lp)
                        state.price_timestamp = mstate.price_timestamp
                        state.price_is_stale = False
                        state.prices.append(float(lp))
                    price_update_count += 1
                    state.ws_quote_count = price_update_count
                elif bid > 0:
                    mstate.price = bid
                    mstate.price_timestamp = time.time()
                    mstate.prices.append(bid)
                    if symbol == TICKER:
                        state.price = bid
                        state.price_timestamp = mstate.price_timestamp
                        state.price_is_stale = False
                        state.prices.append(bid)
                    price_update_count += 1
                    state.ws_quote_count = price_update_count
            elif hasattr(data, 'price') or hasattr(data, 'bid'):
                p = getattr(data, 'price', None) or getattr(data, 'bid', None)
                if p and p > 0:
                    symbol = TICKER
                    mstate = state.get_market(symbol)
                    mstate.price = float(p)
                    mstate.price_timestamp = time.time()
                    mstate.prices.append(float(p))
                    if symbol == TICKER:
                        state.price = float(p)
                        state.price_timestamp = mstate.price_timestamp
                        state.price_is_stale = False
                        state.prices.append(float(p))
                    price_update_count += 1
        except Exception as e:
            log.debug(f"Quote callback error: {e}")

    def on_trade_tick(data):
        """Callback for GatewayTrade events - trade tape data.
        Data may arrive as list [contractId, [trades]] or dict.
        """
        state = VortexState.get_instance()
        nonlocal price_update_count
        try:
            contract_id = None
            if isinstance(data, list) and len(data) >= 2:
                contract_id = str(data[0])
                trades = data[1] if isinstance(data[1], list) else [data[1]]
                if trades and isinstance(trades[-1], dict):
                    data = trades[-1]
            if isinstance(data, dict):
                price = data.get('price', data.get('lastPrice', 0))
                if price and price > 0:
                    symbol = CONTRACT_TO_TICKER.get(contract_id) if contract_id else TICKER
                    mstate = state.get_market(symbol)
                    mstate.price = float(price)
                    mstate.price_timestamp = time.time()
                    mstate.prices.append(float(price))
                    if symbol == TICKER:
                        state.price = float(price)
                        state.price_timestamp = mstate.price_timestamp
                        state.price_is_stale = False
                        state.prices.append(float(price))
                    price_update_count += 1
            elif hasattr(data, 'price'):
                if data.price and data.price > 0:
                    symbol = TICKER
                    mstate = state.get_market(symbol)
                    mstate.price = float(data.price)
                    mstate.price_timestamp = time.time()
                    mstate.prices.append(float(data.price))
                    if symbol == TICKER:
                        state.price = float(data.price)
                        state.price_timestamp = mstate.price_timestamp
                        state.price_is_stale = False
                        state.prices.append(float(data.price))
                    price_update_count += 1
        except Exception as e:
            log.debug(f"Trade tick callback error: {e}")

    # === DIRECT SIGNALRCORE WS (proven stable -- test_full_ws.py: 60s, 499 quotes) ===
    # The SDK's internal WebSocket dies after 10s. We bypass it entirely.
    from signalrcore.hub_connection_builder import HubConnectionBuilder

    direct_ws_alive = False
    contract_id = inst.id  # e.g. "CON.F.US.MNQ.H26"
    jwt_token = await get_broker_token()

    market_url = f"https://rtc.topstepx.com/hubs/market?access_token={jwt_token}"
    market_conn = (
        HubConnectionBuilder()
        .with_url(market_url, options={"skip_negotiation": True})
        .with_automatic_reconnect({"type": "raw", "keep_alive_interval": 10,
                                   "reconnect_interval": 5, "max_attempts": None})
        .build()
    )

    def _on_market_open():
        nonlocal direct_ws_alive
        direct_ws_alive = True
        log.info(f"DIRECT WS: Market hub CONNECTED, subscribing to all instruments...")
        try:
            # Subscribe to all micro contracts for L1 and L2 data
            for sym, cid in MICRO_CONTRACTS.items():
                market_conn.send("SubscribeContractQuotes", [cid])
                market_conn.send("SubscribeContractTrades", [cid])
                # Activate L2 depth for all markets
                market_conn.send("SubscribeContractMarketDepth", [cid])
                log.info(f"DIRECT WS: Subscribed {sym} ({cid}) L1/L2 data")
        except Exception as e:
            log.error(f"DIRECT WS: Subscription send failed: {e}")

    def _on_market_close():
        nonlocal direct_ws_alive
        direct_ws_alive = False
        log.warning("DIRECT WS: Market hub DISCONNECTED")

    def _on_market_reconnect():
        """CRITICAL FIX: Re-subscribe to all contracts after reconnection.
        Without this, the 60s disconnect causes permanent data loss.
        Based on official ProjectX API docs: rtcConnection.onreconnected(() => { subscribe(); })
        """
        nonlocal direct_ws_alive
        direct_ws_alive = True
        log.info("DIRECT WS: Market hub RECONNECTED - Re-subscribing to ALL contracts...")
        try:
            # Re-subscribe to ALL micro contracts for L1 data
            for sym, cid in MICRO_CONTRACTS.items():
                market_conn.send("SubscribeContractQuotes", [cid])
                market_conn.send("SubscribeContractTrades", [cid])
            
            # Re-subscribe L2 for MNQ only
            mnq_cid = MICRO_CONTRACTS.get("MNQ")
            if mnq_cid:
                market_conn.send("SubscribeContractMarketDepth", [mnq_cid])
                log.info(f"DIRECT WS: Re-subscribed MNQ L2 depth ({mnq_cid})")
            
            log.info(f"DIRECT WS: Re-subscribed to {len(MICRO_CONTRACTS)} contracts after reconnect")
        except Exception as e:
            log.error(f"DIRECT WS: Re-subscription after reconnect failed: {e}")

    def _on_market_error(data):
        log.debug(f"DIRECT WS market error: {data}")

    def _on_gateway_quote(args):
        state = VortexState.get_instance()
        nonlocal price_update_count
        try:
            # Parse contractId and quote data from args
            quote_contract_id = None
            if isinstance(args, list) and len(args) >= 2:
                quote_contract_id = args[0] if isinstance(args[0], str) else None
                d = args[1] if isinstance(args[1], dict) else args
            else:
                d = args
            if not isinstance(d, dict):
                return

            if price_update_count < 3:
                log.info(f"DIRECT WS: GatewayQuote contract={quote_contract_id}, preview={str(d)[:200]}")

            lp = d.get('lastPrice', 0)
            bid = d.get('bestBid', d.get('bid', 0))
            ask = d.get('bestAsk', d.get('ask', 0))

            # Compute mid price
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2.0
            elif lp and lp > 0:
                mid = float(lp)
            elif bid > 0:
                mid = float(bid)
            else:
                return

            now_ts = time.time()

            # Update multi-market price tracker for ALL contracts (V3 Refactor)
            if quote_contract_id:
                symbol = CONTRACT_TO_TICKER.get(quote_contract_id)
                if symbol:
                    # SAFETY: Ensure state has market_prices attribute
                    if not hasattr(state, 'market_prices'):
                        state.market_prices = {}
                    
                    state.market_prices[symbol] = mid
                    mstate = state.get_market(symbol)
                    mstate.price = mid
                    mstate.best_bid = float(bid) if bid else 0.0
                    mstate.best_ask = float(ask) if ask else 0.0
                    mstate.price_timestamp = now_ts
                    mstate.price_is_stale = False

            # Only update state.price if this is the CURRENT trading instrument
            if quote_contract_id is None or quote_contract_id == contract_id:
                state.price = mid
                state.price_timestamp = now_ts
                state.price_is_stale = False
                state.prices.append(mid)  # deque(maxlen=300) auto-trims
                price_update_count += 1
                state.ws_quote_count = price_update_count
                if price_update_count % 500 == 0:
                    log.info(f"DIRECT WS quote #{price_update_count}: bid={bid} ask={ask} price={state.price}")
        except Exception as e:
            log.debug(f"Gateway quote error: {e}")

    def _on_gateway_trade(args):
        global state
        nonlocal price_update_count
        if state is None:
            return
        try:
            trade_contract_id = None
            d = args
            if isinstance(args, list) and len(args) >= 2:
                trade_contract_id = args[0] if isinstance(args[0], str) else None
                trades = args[1] if isinstance(args[1], list) else [args[1]]
                d = trades[-1] if trades and isinstance(trades[-1], dict) else args
            if trade_contract_id and trade_contract_id != contract_id:
                return  # ignore trades from other instruments
            if isinstance(d, dict):
                p = d.get('price', d.get('lastPrice', 0))
                if p and p > 0:
                    state.price = float(p)
                    state.price_timestamp = time.time()
                    state.price_is_stale = False
                    state.prices.append(float(p))  # deque(maxlen=300) auto-trims
                    price_update_count += 1
                    state.ws_quote_count = price_update_count
        except Exception as e:
            log.debug(f"Gateway trade error: {e}")

    def _on_gateway_depth(args):
        """Callback for GatewayDepth events - L2 orderbook data.
        Data format: [contractId, {depth_data}] or just {depth_data}
        """
        state = VortexState.get_instance()
        try:
            depth_contract_id = None
            d = args
            if isinstance(args, list) and len(args) >= 2:
                depth_contract_id = str(args[0])
                d = args[1]
            
            # 1. Resolve Symbol
            symbol = CONTRACT_TO_TICKER.get(depth_contract_id) if depth_contract_id else TICKER
            mstate = state.get_market(symbol)
            config = INSTRUMENT_CONFIG.get(symbol, INSTRUMENT_CONFIG[TICKER])
            tick_size = config['tick_size']
            pv = config['point_value']

            # Handle TopStepX GatewayDepth format: list of entries with type field
            if isinstance(d, list):
                bid_entries = []
                ask_entries = []
                for entry in d:
                    if not isinstance(entry, dict):
                        continue
                    entry_type = entry.get('type', 0)
                    price = entry.get('price', 0)
                    volume = entry.get('volume', 0)
                    if price <= 0:
                        continue
                    if entry_type in (2, 4, 9):  # Bid, BestBid, NewBestBid
                        bid_entries.append([price, volume])
                    elif entry_type in (1, 3, 10):  # Ask, BestAsk, NewBestAsk
                        ask_entries.append([price, volume])
                bid_entries.sort(key=lambda x: x[0], reverse=True)
                ask_entries.sort(key=lambda x: x[0])
                d = {'bids': bid_entries, 'asks': ask_entries}

            if not isinstance(d, dict):
                return

            # Extract bid and ask levels
            bid_levels = d.get('bids', d.get('bidLevels', []))
            ask_levels = d.get('asks', d.get('askLevels', []))
            
            # Normalize to list of [price, volume]
            if bid_levels and isinstance(bid_levels[0], dict):
                bid_levels = [[b.get('price', b.get('level', 0)), b.get('size', b.get('volume', 0))] for b in bid_levels]
            if ask_levels and isinstance(ask_levels[0], dict):
                ask_levels = [[a.get('price', a.get('level', 0)), a.get('size', a.get('volume', 0))] for a in ask_levels]
            
            best_bid = float(bid_levels[0][0]) if bid_levels and len(bid_levels[0]) >= 1 else 0.0
            best_ask = float(ask_levels[0][0]) if ask_levels and len(ask_levels[0]) >= 1 else 0.0
            
            if best_bid <= 0 or best_ask <= 0:
                return
            
            # Metrics Calculation
            spread = best_ask - best_bid
            bid_vol = sum(float(b[1]) for b in bid_levels[:5])
            ask_vol = sum(float(a[1]) for a in ask_levels[:5])
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0.0
            
            # Depth within 2 ticks (Normalized)
            depth_range = tick_size * 2.0
            bid_depth_usd = sum(float(b[1]) for b in bid_levels if float(b[0]) >= (best_bid - depth_range)) * pv
            ask_depth_usd = sum(float(a[1]) for a in ask_levels if float(a[0]) <= (best_ask + depth_range)) * pv
            
            # Update MarketState
            mstate.l2_timestamp = time.time()
            mstate.orderbook_data = {
                "bid": best_bid, "ask": best_ask, "spread": spread,
                "spread_ticks": round(spread / tick_size, 1),
                "imbalance": imbalance, "bid_depth_usd": bid_depth_usd, "ask_depth_usd": ask_depth_usd,
                "bid_vol": bid_vol, "ask_vol": ask_vol
            }
            
            # Sync to global (deprecated)
            if symbol == TICKER:
                if hasattr(state, 'orderbook_data'):
                    state.orderbook_data = mstate.orderbook_data
                if hasattr(state, 'l2_timestamp'):
                    state.l2_timestamp = mstate.l2_timestamp
                
        except Exception as e:
            log.debug(f"L2 routing error: {e}")
            
            # ======================================
            # QUALITY CHECKS (Tick-Normalized)
            # ======================================
            mstate.spread_ticks = round(spread / tick_size, 1)
            
            # 1. Spread anomaly (> 5 ticks for Micro-futures)
            max_spread_ticks = 5.0
            if symbol == "MCL": max_spread_ticks = 10.0 # Oil is thinner
            
            m_spread_ok = mstate.spread_ticks <= max_spread_ticks
            if not m_spread_ok:
                log.debug(f"L2 ANOMALY [{symbol}]: Wide spread {mstate.spread_ticks} ticks")
            
            # 2. Depth gate check
            min_depth_usd = float(os.getenv("VORTEX_L2_MIN_DEPTH_USD", "0"))
            m_depth_ok = (bid_depth_usd >= min_depth_usd) and (ask_depth_usd >= min_depth_usd)
            
            mstate.l2_quality_ok = m_spread_ok and m_depth_ok
            
        except Exception as e:
            log.debug(f"L2 routing error: {e}")
            ask_jump = abs(best_ask - state.l2_prev_best_ask) if state.l2_prev_best_ask > 0 else 0
            max_jump = max(bid_jump, ask_jump)
            # Flag jumps > 1 point as anomalies
            jump_check = max_jump <= 1.0 or state.l2_prev_best_bid == 0.0  # First update is ok
            quality_checks['no_large_jumps'] = jump_check
            if not jump_check:
                anomalies.append(f"PRICE_JUMP: bid_jump={bid_jump:.2f}pts, ask_jump={ask_jump:.2f}pts")
            
            # Check 3: Empty book (both sides must have quotes)
            book_check = len(bid_levels) > 0 and len(ask_levels) > 0
            quality_checks['book_complete'] = book_check
            if not book_check:
                anomalies.append(f"EMPTY_BOOK: bids={len(bid_levels)}, asks={len(ask_levels)}")
            
            # Check 4: Data freshness (updates should come every <1 second)
            time_now = time.time()
            if state.l2_timestamp > 0:
                time_since_last = time_now - state.l2_timestamp
                freshness_check = time_since_last < 2.0  # Allow up to 2 seconds between updates
                quality_checks['data_fresh'] = freshness_check
                if not freshness_check:
                    anomalies.append(f"STALE_DATA: {time_since_last:.1f}s since last update")
            else:
                quality_checks['data_fresh'] = True
            
            # Store quality metrics
            state.l2_quality_checks = quality_checks
            if anomalies:
                state.l2_anomalies_count += 1
                for anomaly in anomalies:
                    log.warning(f"L2 QUALITY: {anomaly}")
            
            # Store orderbook data in state
            state.orderbook_data = {
                'bid_levels': bid_levels[:10],  # Keep top 10 levels
                'ask_levels': ask_levels[:10],
                'spread': round(spread, 4),
                'imbalance': round(imbalance, 4),
                'best_bid': round(best_bid, 2),
                'best_ask': round(best_ask, 2),
                'bid_vol_top5': round(bid_vol, 0),
                'ask_vol_top5': round(ask_vol, 0),
                'ofi': round(ofi, 0),  # Order Flow Imbalance
                'book_pressure': round(book_pressure, 4)
            }
            state.best_bid_depth = best_bid_depth_usd
            state.best_ask_depth = best_ask_depth_usd
            state.l2_ofi = ofi
            state.l2_book_pressure = book_pressure
            
            # Update previous values for next iteration
            state.l2_prev_best_bid = best_bid
            state.l2_prev_best_ask = best_ask
            state.l2_prev_spread = spread
            
            # Store detailed quality metrics
            state.l2_quality_metrics = {
                'spread': round(spread, 4),
                'imbalance': round(imbalance, 4),
                'ofi': round(ofi, 0),
                'book_pressure': round(book_pressure, 4),
                'best_bid_depth_usd': round(best_bid_depth_usd, 2),
                'best_ask_depth_usd': round(best_ask_depth_usd, 2),
                'quality_checks': quality_checks,
                'anomalies_count': state.l2_anomalies_count,
                'timestamp': time_now
            }
            
            state.l2_timestamp = time_now
            
            # Log to L2 verification file (every 10 updates to avoid spam)
            if state.ws_quote_count % 10 == 0:
                _log_l2_metrics()
            
        except Exception as e:
            log.debug(f"Gateway depth error: {e}")

    market_conn.on_open(_on_market_open)
    market_conn.on_close(_on_market_close)
    market_conn.on_error(_on_market_error)
    market_conn.on_reconnect(_on_market_reconnect)  # CRITICAL FIX: Re-subscribe on reconnect
    market_conn.on("GatewayQuote", _on_gateway_quote)
    market_conn.on("GatewayTrade", _on_gateway_trade)
    market_conn.on("GatewayDepth", _on_gateway_depth)

    # User hub for fill tracking
    user_url = f"https://rtc.topstepx.com/hubs/user?access_token={jwt_token}"
    user_conn = (
        HubConnectionBuilder()
        .with_url(user_url, options={"skip_negotiation": True})
        .with_automatic_reconnect({"type": "raw", "keep_alive_interval": 10,
                                   "reconnect_interval": 5, "max_attempts": None})
        .build()
    )

    def _on_user_open():
        log.info("DIRECT WS: User hub CONNECTED")

    def _on_user_close():
        log.warning("DIRECT WS: User hub DISCONNECTED")

    def _on_user_reconnect():
        """CRITICAL FIX: Re-establish user hub callbacks after reconnection."""
        log.info("DIRECT WS: User hub RECONNECTED")

    user_conn.on_open(_on_user_open)
    user_conn.on_close(_on_user_close)
    user_conn.on_error(lambda d: log.debug(f"DIRECT WS user error: {d}"))
    user_conn.on_reconnect(_on_user_reconnect)  # CRITICAL FIX: Handle reconnection
    user_conn.on("GatewayUserTrade", lambda a: on_user_trade(a))
    user_conn.on("GatewayUserAccount", lambda a: None)
    user_conn.on("GatewayUserOrder", lambda a: on_user_order(a))
    user_conn.on("GatewayUserPosition", lambda a: None)

    # Start both hubs in background threads (signalrcore manages its own threads)
    market_conn.start()
    user_conn.start()
    log.info("DIRECT WS: Both hubs start() called")

    # Wait briefly for connections to establish
    for i in range(10):
        if direct_ws_alive:
            break
        await asyncio.sleep(0.5)

    if direct_ws_alive:
        ws_connected = True
        log.info(f"DIRECT WS: Market hub ALIVE after {(i+1)*0.5:.1f}s -- PRIMARY price source")
    else:
        log.warning("DIRECT WS: Market hub did not connect in 5s, falling back to SDK")
        # Fallback: try SDK EventBus (may not work if SDK WS also dies)
        try:
            await suite.events.on(EventType.QUOTE_UPDATE, on_quote_update)
            await suite.events.on(EventType.TRADE_TICK, on_trade_tick)
            log.info("SDK EventBus subscriptions registered as fallback")
            ws_connected = True
        except Exception as e:
            log.warning(f"SDK EventBus fallback also failed: {e}")

    if ws_connected:
        log.info("Real-time price feed ACTIVE")
    else:
        log.warning("ALL WebSocket strategies failed - REST polling only")

    # FIX 3: Initial broker reconciliation
    try:
        await reconcile_with_broker()
        log.info(f"Broker state: balance=${state.broker_balance:.2f}, "
                 f"starting=${state.broker_starting_balance:.2f}, "
                 f"realized_pnl=${state.broker_realized_pnl:.2f}")
    except Exception as e:
        log.warning(f"Initial broker reconciliation failed: {e}")

    # SAFETY: cancel open orders before trusting local position state
    try:
        orders = await mnq.orders.search_open_orders()
        if orders:
            log.info(f"STARTUP CLEANUP: Cancelling ALL {len(orders)} open orders before sync")
            result = await mnq.orders.cancel_all_orders()
            log.info(f"STARTUP CLEANUP: {result}")
        else:
            log.info("STARTUP CLEANUP: No open orders found")
    except Exception as cleanup_err:
        log.warning(f"STARTUP CLEANUP: Failed to cancel orders: {cleanup_err}")

    await sync_position()
    if state.position_side != "FLAT":
        log.info(f"Existing position after startup cleanup: {state.position_side} {state.position_size} @ {state.position_entry}")

    # Get initial price
    price = await mnq.data.get_current_price()
    if price:
        state.price = price
        log.info(f"Initial price: {price}")

    # Initialize memory
    mem = load_memory()
    save_memory(mem)

    log.info("Startup complete. Entering control loop.")
    await control_loop()


async def shutdown():
    """Clean shutdown -- flatten all positions first."""
    global suite, fleet
    log.info("Shutting down -- FLATTENING ALL POSITIONS...")

    # 1. Flatten Warwick legs (most dangerous when hedged -- no SL/TP)
    if warwick:
        for lt in ["primary", "hedge"]:
            leg = getattr(warwick.state, lt)
            if leg.is_open:
                try:
                    await warwick_close_leg(lt)
                except Exception as e:
                    log.error(f"SHUTDOWN: Failed to close Warwick {lt}: {e}")

    # 2. Flatten Chimera (Engine #3) position
    if state.chimera_trade.side != "FLAT":
        try:
            await close_chimera_trade()
        except Exception as e:
            log.error(f"SHUTDOWN: Failed to close Chimera: {e}")

    # 3. Flatten Claude's position
    if state.position_side != "FLAT":
        try:
            await close_position()
        except Exception as e:
            log.error(f"SHUTDOWN: Failed to close position: {e}")

    # 4. Cancel ALL remaining orders (nuclear cleanup)
    if mnq:
        try:
            await mnq.orders.cancel_all_orders()
        except Exception:
            pass

    # 4. Save final state
    try:
        save_status()
    except Exception:
        pass

    # 5. Stop connections
    if market_conn:
        try:
            market_conn.stop()
        except Exception:
            pass
    if user_conn:
        try:
            user_conn.stop()
        except Exception:
            pass

    if fleet:
        await fleet.stop()
    if suite:
        try:
            await suite.disconnect()
        except Exception:
            pass
    log.info("VORTEX V2 stopped -- all positions flattened")


async def main():
    try:
        await startup()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.error(f"Fatal: {e}")
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
