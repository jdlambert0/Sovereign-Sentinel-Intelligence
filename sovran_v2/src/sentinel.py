"""
Layer 5 — The Sentinel (Autonomous Operations Manager)

Orchestrates all layers, runs the main trading loop,
monitors health, handles recovery, and manages multi-market scanning.

Multi-Market Mode:
  The Sentinel cycles through configured contracts in a round-robin fashion.
  For each contract it subscribes to market data, takes a snapshot, asks the
  AI brain for a decision, then moves on to the next contract. Only one
  contract is actively analyzed per cycle (dynamic switching, not parallel).
"""

import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, time as dt_time, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

import pytz
from dotenv import load_dotenv

from src.broker import BrokerClient, BrokerError
from src.risk import RiskGuardian, TradeRequest, TradeSide, RiskConfig, TradeDecision
from src.market_data import MarketDataPipeline, MarketSnapshot, MarketRegime
from src.decision import DecisionEngine, DecisionConfig, TradeIntent
from src.learning import LearningEngine, TradeRecord
from src.position_manager import PositionManager, PositionManagerConfig, PositionState, ExitReason
from src.scanner import MarketScanner, MarketScore
from src.performance import PerformanceEngine
from src.problem_tracker import ProblemTracker


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

# Known contract metadata for automatic tick size/value lookup
# All 51 tradeable instruments from the ProjectX/TopStepX universe
CONTRACT_META = {
    # ── Micro Equity Index Futures ──
    "MNQ": {"name": "Micro E-mini Nasdaq-100",    "tick_size": 0.25,     "tick_value": 0.50,    "point_value": 2.00,    "asset_class": "equity_index"},
    "MES": {"name": "Micro E-mini S&P 500",       "tick_size": 0.25,     "tick_value": 1.25,    "point_value": 5.00,    "asset_class": "equity_index"},
    "MYM": {"name": "Micro E-mini Dow",           "tick_size": 1.00,     "tick_value": 0.50,    "point_value": 0.50,    "asset_class": "equity_index"},
    "M2K": {"name": "Micro E-mini Russell 2000",  "tick_size": 0.10,     "tick_value": 0.50,    "point_value": 5.00,    "asset_class": "equity_index"},
    # ── E-mini Equity Index Futures ──
    "NQ":  {"name": "E-mini Nasdaq-100",           "tick_size": 0.25,     "tick_value": 5.00,    "point_value": 20.00,   "asset_class": "equity_index"},
    "ES":  {"name": "E-mini S&P 500",              "tick_size": 0.25,     "tick_value": 12.50,   "point_value": 50.00,   "asset_class": "equity_index"},
    "YM":  {"name": "E-mini Dow ($5)",             "tick_size": 1.00,     "tick_value": 5.00,    "point_value": 5.00,    "asset_class": "equity_index"},
    "RTY": {"name": "E-mini Russell 2000",         "tick_size": 0.10,     "tick_value": 5.00,    "point_value": 50.00,   "asset_class": "equity_index"},
    "NKD": {"name": "Nikkei 225",                  "tick_size": 5.00,     "tick_value": 25.00,   "point_value": 5.00,    "asset_class": "equity_index"},
    "ENQ": {"name": "E-mini Nasdaq-100 (alt)",     "tick_size": 0.25,     "tick_value": 5.00,    "point_value": 20.00,   "asset_class": "equity_index"},
    "EP":  {"name": "E-Mini S&P 500 (alt)",        "tick_size": 0.25,     "tick_value": 12.50,   "point_value": 50.00,   "asset_class": "equity_index"},
    # ── Metals ──
    "GCE": {"name": "Gold (Globex)",               "tick_size": 0.10,     "tick_value": 10.00,   "point_value": 100.00,  "asset_class": "metals"},
    "MGC": {"name": "Micro Gold",                  "tick_size": 0.10,     "tick_value": 1.00,    "point_value": 10.00,   "asset_class": "metals"},
    "SIE": {"name": "Silver (Globex)",             "tick_size": 0.005,    "tick_value": 25.00,   "point_value": 5000.00, "asset_class": "metals"},
    "SIL": {"name": "Micro Silver",               "tick_size": 0.005,    "tick_value": 5.00,    "point_value": 1000.00, "asset_class": "metals"},
    "CPE": {"name": "Copper (Globex)",             "tick_size": 0.0005,   "tick_value": 12.50,   "point_value": 25000.00,"asset_class": "metals"},
    "MHG": {"name": "Micro Copper",               "tick_size": 0.0005,   "tick_value": 1.25,    "point_value": 2500.00, "asset_class": "metals"},
    "PLE": {"name": "Platinum (Globex)",           "tick_size": 0.10,     "tick_value": 5.00,    "point_value": 50.00,   "asset_class": "metals"},
    # ── Energy ──
    "CLE": {"name": "Crude Light (Globex)",        "tick_size": 0.01,     "tick_value": 10.00,   "point_value": 1000.00, "asset_class": "energy"},
    "MCL": {"name": "Micro WTI Crude Oil",         "tick_size": 0.01,     "tick_value": 1.00,    "point_value": 100.00,  "asset_class": "energy"},
    "NGE": {"name": "Natural Gas (Globex)",        "tick_size": 0.001,    "tick_value": 10.00,   "point_value": 10000.00,"asset_class": "energy"},
    "MNG": {"name": "Micro Henry Hub Nat Gas",     "tick_size": 0.001,    "tick_value": 1.00,    "point_value": 1000.00, "asset_class": "energy"},
    "NQG": {"name": "E-Mini Natural Gas",          "tick_size": 0.005,    "tick_value": 12.50,   "point_value": 2500.00, "asset_class": "energy"},
    "NQM": {"name": "E-Mini Crude Oil",            "tick_size": 0.025,    "tick_value": 12.50,   "point_value": 500.00,  "asset_class": "energy"},
    "HOE": {"name": "NY Harbor ULSD",              "tick_size": 0.0001,   "tick_value": 4.20,    "point_value": 42000.00,"asset_class": "energy"},
    "RBE": {"name": "RBOB Gasoline",               "tick_size": 0.0001,   "tick_value": 4.20,    "point_value": 42000.00,"asset_class": "energy"},
    # ── Currencies ──
    "EU6": {"name": "Euro FX",                     "tick_size": 0.00005,  "tick_value": 6.25,    "point_value": 125000.00,"asset_class": "currency"},
    "BP6": {"name": "British Pound",               "tick_size": 0.0001,   "tick_value": 6.25,    "point_value": 62500.00,"asset_class": "currency"},
    "JY6": {"name": "Japanese Yen",                "tick_size": 0.0000005,"tick_value": 6.25,    "point_value": 12500000.00,"asset_class": "currency"},
    "CA6": {"name": "Canadian Dollar",             "tick_size": 0.00005,  "tick_value": 5.00,    "point_value": 100000.00,"asset_class": "currency"},
    "DA6": {"name": "Australian Dollar",           "tick_size": 0.00005,  "tick_value": 5.00,    "point_value": 100000.00,"asset_class": "currency"},
    "SF6": {"name": "Swiss Franc",                 "tick_size": 0.00005,  "tick_value": 6.25,    "point_value": 125000.00,"asset_class": "currency"},
    "NE6": {"name": "New Zealand Dollar",          "tick_size": 0.00005,  "tick_value": 5.00,    "point_value": 100000.00,"asset_class": "currency"},
    "MX6": {"name": "Mexican Peso",               "tick_size": 0.00001,  "tick_value": 5.00,    "point_value": 500000.00,"asset_class": "currency"},
    "M6E": {"name": "E-Micro EUR/USD",             "tick_size": 0.0001,   "tick_value": 1.25,    "point_value": 12500.00,"asset_class": "currency"},
    "M6B": {"name": "E-Micro GBP/USD",             "tick_size": 0.0001,   "tick_value": 0.625,   "point_value": 6250.00, "asset_class": "currency"},
    "M6A": {"name": "E-Micro AUD/USD",             "tick_size": 0.0001,   "tick_value": 1.00,    "point_value": 10000.00,"asset_class": "currency"},
    "EEU": {"name": "E-mini Euro FX",              "tick_size": 0.0001,   "tick_value": 6.25,    "point_value": 62500.00,"asset_class": "currency"},
    # ── Treasuries ──
    "USA": {"name": "30yr US Treasury Bonds",      "tick_size": 0.03125,  "tick_value": 31.25,   "point_value": 1000.00, "asset_class": "treasury"},
    "ULA": {"name": "Ultra T-Bond",                "tick_size": 0.03125,  "tick_value": 31.25,   "point_value": 1000.00, "asset_class": "treasury"},
    "TYA": {"name": "10yr Treasury Notes",         "tick_size": 0.015625, "tick_value": 15.625,  "point_value": 1000.00, "asset_class": "treasury"},
    "TNA": {"name": "Ultra 10yr Treasury Note",    "tick_size": 0.015625, "tick_value": 15.625,  "point_value": 1000.00, "asset_class": "treasury"},
    "FVA": {"name": "5 Year Treasury Notes",       "tick_size": 0.0078125,"tick_value": 7.8125,  "point_value": 1000.00, "asset_class": "treasury"},
    "TUA": {"name": "2 Year Treasury Note",        "tick_size": 0.00390625,"tick_value":7.8125,  "point_value": 1000.00, "asset_class": "treasury"},
    "ZN":  {"name": "10-Year T-Note (alias)",      "tick_size": 0.015625, "tick_value": 15.625,  "point_value": 1000.00, "asset_class": "treasury"},
    "ZB":  {"name": "30-Year T-Bond (alias)",      "tick_size": 0.03125,  "tick_value": 31.25,   "point_value": 1000.00, "asset_class": "treasury"},
    # ── Agriculture ──
    "ZCE": {"name": "Corn",                        "tick_size": 0.25,     "tick_value": 12.50,   "point_value": 50.00,   "asset_class": "agriculture"},
    "ZSE": {"name": "Soybeans",                    "tick_size": 0.25,     "tick_value": 12.50,   "point_value": 50.00,   "asset_class": "agriculture"},
    "ZWA": {"name": "Wheat",                       "tick_size": 0.25,     "tick_value": 12.50,   "point_value": 50.00,   "asset_class": "agriculture"},
    "ZLE": {"name": "Soybean Oil",                 "tick_size": 0.01,     "tick_value": 6.00,    "point_value": 600.00,  "asset_class": "agriculture"},
    "ZME": {"name": "Soybean Meal",                "tick_size": 0.10,     "tick_value": 10.00,   "point_value": 100.00,  "asset_class": "agriculture"},
    "HE":  {"name": "Lean Hogs",                   "tick_size": 0.025,    "tick_value": 10.00,   "point_value": 400.00,  "asset_class": "agriculture"},
    "GLE": {"name": "Live Cattle",                 "tick_size": 0.025,    "tick_value": 10.00,   "point_value": 400.00,  "asset_class": "agriculture"},
    # ── Crypto ──
    "MBT": {"name": "Micro Bitcoin",               "tick_size": 5.00,     "tick_value": 0.50,    "point_value": 0.10,    "asset_class": "crypto"},
    "GMET":{"name": "Micro Ether",                 "tick_size": 0.50,     "tick_value": 0.05,    "point_value": 0.10,    "asset_class": "crypto"},
}


def _lookup_contract_meta(contract_id: str) -> Dict[str, Any]:
    """Look up contract metadata from a contract ID string.
    
    Handles full TopStepX format like 'CON.F.US.MNQM26' by extracting the
    root symbol, or plain symbols like 'MNQ'.
    """
    # Extract root symbol from TopStepX format
    parts = contract_id.split(".")
    if len(parts) >= 4:
        raw = parts[3]  # e.g., "MNQM26"
    else:
        raw = contract_id
    
    # Strip month/year suffix to get root
    for root in sorted(CONTRACT_META.keys(), key=len, reverse=True):
        if raw.upper().startswith(root.upper()):
            return CONTRACT_META[root]
    
    # Default to MNQ-like specs
    return {"name": contract_id, "tick_size": 0.25, "tick_value": 0.50, "point_value": 2.00}


# ---------------------------------------------------------------------------
#  State / Config
# ---------------------------------------------------------------------------

class SystemState(Enum):
    STARTING = "starting"
    RUNNING = "running"
    TRADING_HALTED = "trading_halted"
    MARKET_CLOSED = "market_closed"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class HealthStatus:
    """Health of each component."""
    broker_connected: bool = False
    market_data_connected: bool = False
    market_data_last_update: float = 0.0
    risk_engine_ready: bool = False
    decision_engine_ready: bool = False
    learning_engine_ready: bool = False

    daily_pnl: float = 0.0
    account_balance: float = 0.0
    open_positions: int = 0

    system_state: SystemState = SystemState.STOPPED
    uptime_seconds: float = 0.0
    trades_today: int = 0
    errors_today: int = 0
    last_error: str = ""

    cycle_count: int = 0
    last_cycle_time: float = 0.0
    current_contract: str = ""


@dataclass
class SentinelConfig:
    """Sentinel configuration."""
    cycle_seconds: int = 15
    health_check_seconds: int = 30
    position_check_seconds: int = 10
    obsidian_update_seconds: int = 300

    market_open_hour: int = 17
    market_open_minute: int = 0
    market_close_hour: int = 16
    market_close_minute: int = 0

    max_market_data_stale_seconds: int = 60
    max_consecutive_errors: int = 5

    # Primary contract (backward compat) — also first in round-robin
    contract_id: str = "CON.F.US.MNQ.M26"
    tick_size: float = 0.25
    tick_value: float = 0.50

    obsidian_path: str = r"C:\KAI\obsidian_vault\Sovran AI\LIVE_STATUS.md"
    learning_db_path: str = r"C:\KAI\obsidian_vault\Sovran AI\LEARNING_DB.json"
    learning_config_path: str = r"C:\KAI\sovran_v2\config\learning_config.json"

    # Trade context persistence
    state_dir: str = "state"

    # Obsidian problem tracker / daily log output
    obsidian_dir: str = "obsidian"

    # Dry run mode
    dry_run: bool = False


# ---------------------------------------------------------------------------
#  Sentinel
# ---------------------------------------------------------------------------

class Sentinel:
    """
    Autonomous operations manager.
    Orchestrates all layers, runs the main trading loop,
    monitors health, and handles recovery.
    
    Multi-market: cycles through `contracts` list in round-robin,
    subscribing/analyzing one at a time (dynamic switching).
    """

    def __init__(
        self,
        config: Optional[SentinelConfig] = None,
        contracts: Optional[List[str]] = None,
    ):
        self.config = config or SentinelConfig()
        self.logger = logging.getLogger("sovran.sentinel")
        self.state = HealthStatus()
        self.start_time = 0.0

        # Multi-market: list of contract IDs to scan
        self.contracts: List[str] = contracts or [self.config.contract_id]
        self._contract_index = 0  # Round-robin pointer

        # Components
        self.broker: Optional[BrokerClient] = None
        self.market_data: Optional[MarketDataPipeline] = None
        self.risk: Optional[RiskGuardian] = None
        self.decision: Optional[DecisionEngine] = None
        self.learning: Optional[LearningEngine] = None
        self.position_manager: Optional[PositionManager] = None
        self.scanner: Optional[MarketScanner] = None
        self.performance: Optional[PerformanceEngine] = None
        self.problems: Optional[ProblemTracker] = None

        self._tasks: List[asyncio.Task] = []
        self._consecutive_errors = 0
        self._last_positions: List[Dict[str, Any]] = []
        self._active_trade_data: Dict[str, Any] = {}
        self._baseline_pnl: float = 0.0

        # Per-contract market data pipelines (lazy-created)
        self._pipelines: Dict[str, MarketDataPipeline] = {}

    # ------------------------------------------------------------------
    #  Trade context persistence (Task 3)
    # ------------------------------------------------------------------

    def _state_file(self) -> str:
        return os.path.join(self.config.state_dir, "active_trades.json")

    def _save_trade_context(self) -> None:
        """Persist active trade context to disk for crash recovery."""
        os.makedirs(self.config.state_dir, exist_ok=True)
        path = self._state_file()
        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "baseline_pnl": self._baseline_pnl,
            "trades_today": self.state.trades_today,
            "active_trades": self._active_trade_data,
        }
        # Atomic write: write to tmp then rename
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)

    def _load_trade_context(self) -> None:
        """Restore active trade context from disk after a crash/restart."""
        path = self._state_file()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._active_trade_data = data.get("active_trades", {})
            self._baseline_pnl = data.get("baseline_pnl", 0.0)
            self.state.trades_today = data.get("trades_today", 0)
            self.logger.info(
                f"Restored trade context: {len(self._active_trade_data)} active trades, "
                f"baseline_pnl={self._baseline_pnl}, trades_today={self.state.trades_today}"
            )
        except Exception as e:
            self.logger.warning(f"Failed to load trade context: {e}")

    def _clear_trade_context(self) -> None:
        """Clear persisted trade context (clean shutdown)."""
        path = self._state_file()
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the full system."""
        self.logger.info("Starting Sentinel...")
        self.state.system_state = SystemState.STARTING
        self.start_time = time.time()

        try:
            load_dotenv(r"C:\KAI\sovran_v2\config\.env")
            # Also try local .env
            load_dotenv("config/.env")

            # Restore crash context BEFORE connecting
            self._load_trade_context()

            # 1. Connect Broker
            self.broker = BrokerClient(
                username=os.getenv("PROJECT_X_USERNAME"),
                api_key=os.getenv("PROJECT_X_API_KEY"),
                account_id=(
                    int(os.getenv("PROJECT_X_ACCOUNT_ID"))
                    if os.getenv("PROJECT_X_ACCOUNT_ID")
                    else None
                ),
            )
            await self.broker.connect()
            self.state.broker_connected = True
            self.state.account_balance = self.broker.account_balance

            # Record baseline PnL so we only track OUR trades
            baseline = await self.broker.get_realized_pnl()
            if self._baseline_pnl == 0.0:
                self._baseline_pnl = float(baseline)
            self.logger.info(f"Baseline PnL: {self._baseline_pnl}")

            # 2. Market Data — start pipeline for the first contract
            first_contract = self.contracts[0]
            self.market_data = self._get_or_create_pipeline(first_contract)
            await self.market_data.start()

            # Wait for first data
            self.logger.info("Waiting for market data...")
            for _ in range(30):
                if self.market_data.is_connected and self.market_data._latest_quote:
                    break
                await asyncio.sleep(1)
            else:
                self.logger.warning("Market data timed out")

            self.state.market_data_connected = self.market_data.is_connected

            # 3. Risk Engine
            self.risk = RiskGuardian(self.broker)
            risk_cfg_path = r"C:\KAI\sovran_v2\config\risk_config.json"
            if os.path.exists(risk_cfg_path):
                self.risk.load_config(risk_cfg_path)
            elif os.path.exists("config/risk_config.json"):
                self.risk.load_config("config/risk_config.json")
            self.state.risk_engine_ready = True

            # 4. Decision Engine (AI-driven)
            self.decision = DecisionEngine()
            dec_cfg_path = r"C:\KAI\sovran_v2\config\decision_config.json"
            if os.path.exists(dec_cfg_path):
                self.decision.load_config(dec_cfg_path)
            elif os.path.exists("config/decision_config.json"):
                self.decision.load_config("config/decision_config.json")
            self.decision.load_config_from_env()
            self.state.decision_engine_ready = True

            # 5. Learning Engine
            self.learning = LearningEngine(
                obsidian_path=r"C:\KAI\obsidian_vault\Sovran AI",
                config_path=r"C:\KAI\sovran_v2\config",
            )
            if os.path.exists("config"):
                self.learning = LearningEngine(
                    obsidian_path="obsidian",
                    config_path="config",
                )
            self.learning.load_history()
            self.state.learning_engine_ready = True

            # 6. Position Manager (active trade monitoring)
            pm_config = PositionManagerConfig(state_dir=self.config.state_dir)
            self.position_manager = PositionManager(
                broker=self.broker,
                decision_engine=self.decision,
                config=pm_config,
            )
            self.logger.info("Position Manager initialized")

            # 7. Market Scanner (multi-market intelligence)
            self.scanner = MarketScanner()
            self.logger.info("Market Scanner initialized")

            # 8. Performance Attribution Engine
            self.performance = PerformanceEngine(state_dir=self.config.state_dir)
            self.logger.info("Performance Engine initialized")

            # 9. Problem Tracker (Obsidian)
            self.problems = ProblemTracker(
                state_dir=self.config.state_dir,
                obsidian_dir=self.config.obsidian_dir,
            )
            self.logger.info("Problem Tracker initialized")

            # Background tasks
            self._tasks.append(asyncio.create_task(self._health_monitor()))
            self._tasks.append(asyncio.create_task(self._position_monitor()))
            self._tasks.append(asyncio.create_task(self._obsidian_status_update()))

            self.state.system_state = SystemState.RUNNING
            self.logger.info(
                f"Sentinel operational — scanning {len(self.contracts)} contract(s): "
                + ", ".join(self.contracts)
            )

            await self._trading_loop()

        except Exception as e:
            self.logger.error(f"Startup failed: {e}", exc_info=True)
            self.state.system_state = SystemState.ERROR
            self.state.last_error = str(e)
            await self.stop()

    async def stop(self) -> None:
        """Gracefully shut down."""
        self.logger.info("Shutting down Sentinel...")
        self.state.system_state = SystemState.SHUTTING_DOWN

        for task in self._tasks:
            task.cancel()

        # Stop all market data pipelines
        for pipeline in self._pipelines.values():
            try:
                await pipeline.stop()
            except Exception:
                pass

        if self.broker:
            positions = await self.broker.get_open_positions()
            if positions:
                self.logger.warning(f"Shutting down with {len(positions)} open positions!")
                # Persist trade context so we can recover
                self._save_trade_context()
            else:
                # Clean shutdown, no open positions
                self._clear_trade_context()
            await self.broker.disconnect()

        if self.learning:
            self.learning.save_history()

        self._write_obsidian_status(self.state)
        self.state.system_state = SystemState.STOPPED
        self.logger.info("Sentinel stopped")

    # ------------------------------------------------------------------
    #  Multi-market pipeline management
    # ------------------------------------------------------------------

    def _get_or_create_pipeline(self, contract_id: str) -> MarketDataPipeline:
        """Get an existing pipeline or create one for a contract."""
        if contract_id not in self._pipelines:
            token = self.broker.token if self.broker else ""
            self._pipelines[contract_id] = MarketDataPipeline(
                jwt_token=token,
                contract_id=contract_id,
            )
        return self._pipelines[contract_id]

    def _next_contract(self) -> str:
        """Round-robin to the next contract."""
        self._contract_index = (self._contract_index + 1) % len(self.contracts)
        return self.contracts[self._contract_index]

    def _current_contract(self) -> str:
        return self.contracts[self._contract_index]

    # ------------------------------------------------------------------
    #  Trading loop
    # ------------------------------------------------------------------

    async def _trading_loop(self) -> None:
        """Main trading loop with multi-market round-robin scanning."""
        while self.state.system_state not in [SystemState.SHUTTING_DOWN, SystemState.STOPPED]:
            cycle_start = time.time()
            try:
                if not self._is_market_open():
                    self.state.system_state = SystemState.MARKET_CLOSED
                elif self.state.system_state == SystemState.MARKET_CLOSED:
                    self.state.system_state = SystemState.RUNNING

                if self.state.system_state == SystemState.RUNNING:
                    # Get current contract in the round-robin
                    contract_id = self._current_contract()
                    self.state.current_contract = contract_id

                    # Ensure pipeline exists and is connected
                    pipeline = self._get_or_create_pipeline(contract_id)
                    if not pipeline.is_connected:
                        try:
                            await pipeline.start()
                            # Brief wait for data
                            await asyncio.sleep(2)
                        except Exception as e:
                            self.logger.warning(f"Failed to start pipeline for {contract_id}: {e}")

                    # Update the primary market_data reference
                    self.market_data = pipeline

                    stale = pipeline.seconds_since_last_update
                    if stale > self.config.max_market_data_stale_seconds:
                        self.logger.warning(
                            f"Market data stale for {contract_id} ({stale:.0f}s)"
                        )
                        if self.problems:
                            self.problems.track(
                                "data_quality", "warning",
                                f"Stale data: {contract_id}",
                                f"No updates for {stale:.0f}s (limit {self.config.max_market_data_stale_seconds}s)",
                                {"contract_id": contract_id, "stale_seconds": stale},
                            )
                        # Don't halt — just skip this contract and try the next
                    else:
                        try:
                            snapshot = pipeline.get_snapshot()
                        except Exception as snap_err:
                            self.logger.info(f"Snapshot not ready for {contract_id}: {snap_err}")
                            snapshot = None

                        if snapshot:
                            self.state.market_data_last_update = snapshot.timestamp
                            meta = _lookup_contract_meta(contract_id)

                            # ── Multi-Market Scanner ──
                            # Collect snapshots from all active pipelines
                            all_snapshots = {}
                            all_meta = {}
                            for cid, pipe in self._pipelines.items():
                                try:
                                    s = pipe.get_snapshot()
                                    if s and s.last_price > 0:
                                        all_snapshots[cid] = s
                                        all_meta[cid] = _lookup_contract_meta(cid)
                                except Exception:
                                    pass

                            # Run scanner if we have multiple markets
                            scanner_scores = []
                            cross_market_summary = {}
                            if self.scanner and len(all_snapshots) > 1:
                                active_pos = (
                                    self.position_manager.active_positions
                                    if self.position_manager else {}
                                )
                                scanner_scores = self.scanner.scan(
                                    all_snapshots, all_meta, active_pos
                                )
                                cross_market_summary = self.scanner.get_cross_market_summary()

                                # If scanner found a better market, switch to it
                                if scanner_scores and scanner_scores[0].is_tradeable:
                                    best = scanner_scores[0]
                                    if best.contract_id != contract_id and best.score > 65:
                                        self.logger.info(
                                            f"SCANNER: Switching from {contract_id} to "
                                            f"{best.contract_id} (score={best.score:.0f} "
                                            f"{best.direction})"
                                        )
                                        contract_id = best.contract_id
                                        snapshot = best.snapshot
                                        meta = all_meta.get(contract_id, meta)
                                        pipeline = self._get_or_create_pipeline(contract_id)
                                        self.market_data = pipeline

                            self.logger.info(
                                f"[{contract_id}] price={snapshot.last_price:.2f} "
                                f"ATR={snapshot.atr_points:.2f} VPIN={snapshot.vpin:.3f} "
                                f"OFI={snapshot.ofi_zscore:.2f} "
                                f"regime={snapshot.regime.value} "
                                f"bars={snapshot.bar_count} ticks={snapshot.tick_count}"
                            )

                            # Get performance context for the AI
                            perf = {}
                            recent_trades = []
                            if self.learning:
                                matrix = self.learning.get_performance_matrix()
                                perf = {
                                    "win_rate": matrix.win_rate,
                                    "avg_win_loss_ratio": matrix.avg_win_loss_ratio,
                                    "profit_factor": matrix.profit_factor,
                                    "total_trades": matrix.total_trades,
                                }
                                recent_trades = [
                                    {
                                        "trade_id": t.trade_id,
                                        "contract_id": t.contract_id,
                                        "side": t.side,
                                        "net_pnl": t.net_pnl,
                                        "conviction": t.conviction,
                                        "thesis": t.thesis,
                                    }
                                    for t in self.learning.history[-10:]
                                ]

                            # Also include trade history from PositionManager
                            # (richer data: exit reason, MFE/MAE, hold time)
                            recent_trades = self._load_recent_trade_history(recent_trades)

                            # AI Decision (async)
                            intent = await self.decision.analyze(
                                snapshot=snapshot,
                                account_balance=self.state.account_balance
                                    or (self.broker.account_balance if self.broker else 150000),
                                daily_pnl=self.state.daily_pnl,
                                distance_to_drawdown=max(
                                    0,
                                    (self.state.account_balance or 150000)
                                    - (150000 - self.risk.config.max_trailing_drawdown)
                                    if self.risk
                                    else 4500,
                                ),
                                recent_trades=recent_trades,
                                performance_summary=perf,
                                contract_meta=meta,
                                cross_market_summary=cross_market_summary,
                            )
                            if intent:
                                self.logger.info(
                                    f"TRADE INTENT [{contract_id}]: {intent.side.value} "
                                    f"conviction={intent.conviction:.1f}"
                                )
                                await self._handle_trade_intent(intent, snapshot, meta)
                            else:
                                self.logger.debug(f"No trade intent for {contract_id}")

                    # Advance round-robin
                    self._next_contract()

                self._consecutive_errors = 0
            except Exception as e:
                self._consecutive_errors += 1
                self.state.errors_today += 1
                self.state.last_error = str(e)
                self.logger.error(f"Error in trading loop: {e}", exc_info=True)
                if self._consecutive_errors >= self.config.max_consecutive_errors:
                    self.state.system_state = SystemState.TRADING_HALTED
                    self.logger.error("Max consecutive errors reached, trading halted")

            self.state.cycle_count += 1
            self.state.last_cycle_time = time.time()
            self.state.uptime_seconds = time.time() - self.start_time

            sleep_time = max(0, self.config.cycle_seconds - (time.time() - cycle_start))
            await asyncio.sleep(sleep_time)

    async def _handle_trade_intent(
        self,
        intent: TradeIntent,
        snapshot: MarketSnapshot,
        contract_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Process a TradeIntent from the AI Decision Engine.

        After execution, hands off to the PositionManager for active monitoring.
        The PM runs its own evaluation loop (rule-based + AI-driven) until
        the position is closed, then feeds the outcome back to learning.
        """
        meta = contract_meta or _lookup_contract_meta(snapshot.contract_id)
        request = self._intent_to_request(intent, snapshot, meta)
        decision = await self.risk.evaluate(request)

        if decision.approved:
            self.logger.info(
                f"TRADE APPROVED [{snapshot.contract_id}]: {intent.side.value} "
                f"x{decision.size} @ {snapshot.last_price:.2f} | "
                f"SL={decision.stop_loss_ticks}t TP={decision.take_profit_ticks}t | "
                f"risk=${decision.risk_dollars:.2f} rr={decision.risk_reward_ratio:.1f}"
            )
            if self.config.dry_run:
                self.logger.info("DRY RUN — skipping execution")
                return

            try:
                order_id = await self.risk.execute(request, decision)
                self.state.trades_today += 1
                self.logger.info(f"Trade executed, order ID: {order_id}")

                # Store active trade context + persist
                self._active_trade_data[snapshot.contract_id] = {
                    "entry_price": snapshot.last_price,
                    "entry_time": snapshot.timestamp,
                    "side": intent.side.value,
                    "size": decision.size,
                    "conviction": intent.conviction,
                    "thesis": intent.thesis,
                    "frameworks": intent.frameworks_consulted,
                    "regime": intent.regime.value,
                    "atr": snapshot.atr_points,
                    "vpin": snapshot.vpin,
                    "ofi": snapshot.ofi_zscore,
                }
                self._save_trade_context()

                # Hand off to PositionManager for active monitoring
                if self.position_manager:
                    tick_size = meta.get("tick_size", self.config.tick_size)
                    tick_value = meta.get("tick_value", self.config.tick_value)
                    # Compute target/stop prices from ticks
                    if intent.side == TradeSide.LONG:
                        target_price = snapshot.last_price + (decision.take_profit_ticks * tick_size)
                        stop_price = snapshot.last_price - (decision.stop_loss_ticks * tick_size)
                    else:
                        target_price = snapshot.last_price - (decision.take_profit_ticks * tick_size)
                        stop_price = snapshot.last_price + (decision.stop_loss_ticks * tick_size)

                    pipeline = self._get_or_create_pipeline(snapshot.contract_id)

                    # Launch as background task so the trading loop continues
                    monitor_task = asyncio.create_task(
                        self._monitor_and_learn(
                            contract_id=snapshot.contract_id,
                            side=intent.side.value,
                            entry_price=snapshot.last_price,
                            size=decision.size,
                            target_price=target_price,
                            stop_price=stop_price,
                            thesis=intent.thesis,
                            conviction=intent.conviction,
                            frameworks=intent.frameworks_consulted,
                            pipeline=pipeline,
                            snapshot=snapshot,
                            tick_value=tick_value,
                            tick_size=tick_size,
                        )
                    )
                    self._tasks.append(monitor_task)

            except Exception as e:
                self.logger.error(f"Execution failed: {e}")
        else:
            self.logger.info(
                f"Trade rejected [{snapshot.contract_id}]: "
                f"{decision.rejection_reason.value if decision.rejection_reason else 'Unknown'}"
                f" - {decision.reasoning}"
            )

    async def _monitor_and_learn(
        self,
        contract_id: str,
        side: str,
        entry_price: float,
        size: int,
        target_price: float,
        stop_price: float,
        thesis: str,
        conviction: float,
        frameworks: List[str],
        pipeline: MarketDataPipeline,
        snapshot: MarketSnapshot,
        tick_value: float,
        tick_size: float,
    ) -> None:
        """Monitor a position via PositionManager and record outcome for learning."""
        try:
            result: PositionState = await self.position_manager.monitor_position(
                contract_id=contract_id,
                side=side,
                entry_price=entry_price,
                size=size,
                target_price=target_price,
                stop_price=stop_price,
                thesis=thesis,
                conviction=conviction,
                frameworks=frameworks,
                pipeline=pipeline,
                snapshot=snapshot,
                tick_value=tick_value,
                tick_size=tick_size,
            )

            # Record closed trade for learning
            if self.learning and result.is_closed:
                record = TradeRecord(
                    trade_id=str(int(result.entry_time * 1000)),
                    contract_id=contract_id,
                    side=side,
                    entry_time=result.entry_time,
                    exit_time=result.exit_time,
                    entry_price=result.entry_price,
                    exit_price=result.exit_price,
                    size=size,
                    pnl=result.pnl,
                    fees=0.0,
                    net_pnl=result.pnl,
                    conviction=conviction,
                    thesis=thesis,
                    frameworks_used=frameworks,
                    regime_at_entry=result.entry_regime,
                    atr_at_entry=result.entry_atr,
                    vpin_at_entry=result.entry_vpin,
                    ofi_at_entry=result.entry_ofi_zscore,
                    hold_time_seconds=result.exit_time - result.entry_time,
                    max_favorable_excursion=result.max_favorable_excursion,
                    max_adverse_excursion=result.max_adverse_excursion,
                    verdict=result.exit_reason,
                )
                self.learning.record_trade(record)
                self.logger.info(
                    f"TRADE RECORDED [{contract_id}]: PnL=${result.pnl:.2f} "
                    f"exit={result.exit_reason} hold={result.exit_time - result.entry_time:.0f}s"
                )

            # Clean up active trade data
            self._active_trade_data.pop(contract_id, None)
            self._save_trade_context()

        except Exception as e:
            self.logger.error(f"Monitor/learn error for {contract_id}: {e}", exc_info=True)

    # ------------------------------------------------------------------
    #  Monitors
    # ------------------------------------------------------------------

    async def _position_monitor(self) -> None:
        """Monitor open positions."""
        while True:
            try:
                if self.broker and self.state.broker_connected:
                    positions = await self.broker.get_open_positions()
                    self.state.open_positions = len(positions)
                    await self._detect_closed_trades(positions)
                    self._last_positions = positions
            except Exception as e:
                self.logger.error(f"Position monitor error: {e}")
            await asyncio.sleep(self.config.position_check_seconds)

    async def _detect_closed_trades(self, current_positions: List[Dict[str, Any]]) -> None:
        """Detect and record closed trades."""
        last_ids = {p["contractId"] for p in self._last_positions}
        curr_ids = {p["contractId"] for p in current_positions}
        closed_ids = last_ids - curr_ids

        for cid in closed_ids:
            self.logger.info(f"Detected closed position for {cid}")
            now = datetime.now(timezone.utc)
            start_search = (now - timedelta(hours=1)).isoformat()
            trades = await self.broker.get_trades(start_search)
            relevant = [t for t in trades if t["contractId"] == cid and not t.get("voided")]

            if relevant and cid in self._active_trade_data:
                entry_data = self._active_trade_data.pop(cid)
                pnl = sum(float(t.get("profitAndLoss") or 0.0) for t in relevant)

                record = TradeRecord(
                    trade_id=str(relevant[0].get("tradeId", int(time.time()))),
                    contract_id=cid,
                    side=entry_data["side"],
                    entry_time=entry_data["entry_time"],
                    exit_time=time.time(),
                    entry_price=entry_data["entry_price"],
                    exit_price=float(relevant[-1].get("price", 0.0)),
                    size=entry_data["size"],
                    pnl=pnl,
                    fees=0.0,
                    net_pnl=pnl,
                    conviction=entry_data["conviction"],
                    thesis=entry_data["thesis"],
                    frameworks_used=entry_data["frameworks"],
                    regime_at_entry=entry_data["regime"],
                    atr_at_entry=entry_data["atr"],
                    vpin_at_entry=entry_data["vpin"],
                    ofi_at_entry=entry_data["ofi"],
                )
                self.learning.record_trade(record)
                self.logger.info(f"Recorded trade: {cid} PnL={pnl}")
                self._save_trade_context()
            elif cid in self._active_trade_data:
                self._active_trade_data.pop(cid)
                self._save_trade_context()

    async def _health_monitor(self) -> None:
        """Check system health."""
        while True:
            try:
                if self.broker:
                    ping_ok = await self.broker.ping()
                    self.state.broker_connected = ping_ok
                    if ping_ok:
                        self.state.account_balance = self.broker.account_balance
                        raw_pnl = await self.broker.get_realized_pnl()
                        self.state.daily_pnl = raw_pnl - self._baseline_pnl

                        if self.risk and self.state.daily_pnl <= -self.risk.config.daily_loss_limit:
                            self.state.system_state = SystemState.TRADING_HALTED
                            self.logger.warning("Daily loss limit reached, halting trading")
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
            await asyncio.sleep(self.config.health_check_seconds)

    async def _obsidian_status_update(self) -> None:
        """Update Obsidian status file."""
        while True:
            try:
                self._write_obsidian_status(self.state)
            except Exception as e:
                self.logger.error(f"Obsidian update error: {e}")
            await asyncio.sleep(self.config.obsidian_update_seconds)

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _write_obsidian_status(self, health: HealthStatus) -> None:
        """Write health status to Obsidian."""
        contracts_list = ", ".join(self.contracts)
        content = f"""# 🏛️ SOVEREIGN COMMAND CENTER
## System Status: {health.system_state.value.upper()}

| Metric | Value |
|--------|-------|
| **Uptime** | {int(health.uptime_seconds // 3600)}h {int((health.uptime_seconds % 3600) // 60)}m |
| **Daily PnL** | ${health.daily_pnl:,.2f} |
| **Balance** | ${health.account_balance:,.2f} |
| **Open Positions** | {health.open_positions} |
| **Trades Today** | {health.trades_today} |
| **Cycle Count** | {health.cycle_count} |
| **Scanning** | {health.current_contract} |
| **Contract Pool** | {contracts_list} |
| **Last Error** | {health.last_error or "None"} |

### Component Health
- **Broker**: {"✅" if health.broker_connected else "❌"}
- **Market Data**: {"✅" if health.market_data_connected else "❌"} (Last: {datetime.fromtimestamp(health.market_data_last_update).strftime('%H:%M:%S') if health.market_data_last_update > 0 else "Never"})
- **Risk Engine**: {"✅" if health.risk_engine_ready else "❌"}
- **Decision Engine (AI)**: {"✅" if health.decision_engine_ready else "❌"}
- **Learning Engine**: {"✅" if health.learning_engine_ready else "❌"}

*Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        try:
            os.makedirs(os.path.dirname(self.config.obsidian_path), exist_ok=True)
        except (OSError, ValueError):
            pass
        with open(self.config.obsidian_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _is_market_open(self) -> bool:
        """Check if futures market is open (Sun 5pm - Fri 4pm CT)."""
        tz_ct = pytz.timezone("US/Central")
        now_ct = datetime.now(tz_ct)
        weekday = now_ct.weekday()
        hour = now_ct.hour

        if weekday == 4 and hour >= 16:
            return False
        if weekday == 5:
            return False
        if weekday == 6 and hour < 17:
            return False
        return True

    def _intent_to_request(
        self,
        intent: TradeIntent,
        snapshot: MarketSnapshot,
        contract_meta: Optional[Dict[str, Any]] = None,
    ) -> TradeRequest:
        """Convert TradeIntent to TradeRequest."""
        meta = contract_meta or _lookup_contract_meta(snapshot.contract_id)
        return TradeRequest(
            contract_id=snapshot.contract_id,
            side=intent.side,
            conviction=intent.conviction,
            thesis=intent.thesis,
            suggested_stop_points=intent.suggested_stop_points,
            suggested_target_points=intent.suggested_target_points,
            atr_points=snapshot.atr_points,
            tick_size=meta.get("tick_size", self.config.tick_size),
            tick_value=meta.get("tick_value", self.config.tick_value),
        )

    def _load_recent_trade_history(
        self, existing: List[Dict[str, Any]], max_trades: int = 10
    ) -> List[Dict[str, Any]]:
        """Load recent trade outcomes from state/trade_history.json.

        Merges with learning engine records, preferring richer PM data.
        Returns the most recent `max_trades` entries.
        """
        history_path = os.path.join(self.config.state_dir, "trade_history.json")
        if not os.path.exists(history_path):
            return existing[-max_trades:]

        try:
            with open(history_path, "r") as f:
                pm_history = json.load(f)
        except Exception:
            return existing[-max_trades:]

        # Convert PM records to the format the prompt expects
        pm_trades = []
        for t in pm_history[-max_trades:]:
            pm_trades.append({
                "trade_id": f"pm_{int(t.get('entry_time', 0))}",
                "contract_id": t.get("contract_id", "?"),
                "side": t.get("side", "?"),
                "net_pnl": t.get("pnl", 0),
                "conviction": t.get("conviction", 0),
                "thesis": t.get("thesis", ""),
                "exit_reason": t.get("exit_reason", ""),
                "hold_seconds": t.get("hold_seconds", 0),
                "max_favorable_excursion": t.get("max_favorable_excursion", 0),
                "max_adverse_excursion": t.get("max_adverse_excursion", 0),
            })

        # Merge: PM trades take priority (have more context)
        if pm_trades:
            return pm_trades[-max_trades:]
        return existing[-max_trades:]

    def get_health(self) -> HealthStatus:
        return self.state
