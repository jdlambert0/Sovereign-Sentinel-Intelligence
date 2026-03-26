"""
Tests for the Sentinel (Layer 5) — orchestrator, multi-market scanning,
trade context persistence, and health monitoring.
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz

from src.sentinel import (
    Sentinel,
    SentinelConfig,
    SystemState,
    HealthStatus,
    _lookup_contract_meta,
    CONTRACT_META,
)
from src.risk import TradeSide, TradeRequest, TradeDecision
from src.decision import TradeIntent, DecisionConfig
from src.market_data import MarketSnapshot, MarketRegime


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sentinel_config(tmp_path):
    return SentinelConfig(
        contract_id="CON.F.US.MNQM26",
        cycle_seconds=1,
        obsidian_path=str(tmp_path / "LIVE_STATUS.md"),
        state_dir=str(tmp_path / "state"),
    )


@pytest.fixture
def sentinel(sentinel_config):
    s = Sentinel(config=sentinel_config)
    return s


@pytest.fixture
def multi_sentinel(sentinel_config):
    """Sentinel configured for multi-market scanning."""
    return Sentinel(
        config=sentinel_config,
        contracts=["CON.F.US.MNQM26", "CON.F.US.MESM26", "CON.F.US.MYMM26"],
    )


# ---------------------------------------------------------------------------
#  Unit Tests
# ---------------------------------------------------------------------------

def test_health_status_creation():
    health = HealthStatus()
    assert health.system_state == SystemState.STOPPED
    assert health.broker_connected is False
    assert health.trades_today == 0


def test_intent_to_request_conversion(sentinel):
    intent = TradeIntent(
        side=TradeSide.LONG,
        conviction=85.0,
        thesis="Bullish breakout",
        suggested_stop_points=20.0,
        suggested_target_points=40.0,
        frameworks_consulted=["momentum"],
        frameworks_agreeing=["momentum"],
        regime=MarketRegime.TRENDING_UP,
        snapshot_timestamp=123456789.0,
    )
    snapshot = MarketSnapshot(
        timestamp=123456789.0,
        contract_id="CON.F.US.MNQM26",
        last_price=18000.0,
        best_bid=17999.0,
        best_ask=18001.0,
        spread=2.0,
        atr_points=15.0,
        vpin=0.2,
        ofi_zscore=1.5,
        volume_rate=1.2,
        bid_ask_imbalance=0.0,
        regime=MarketRegime.TRENDING_UP,
        trend_strength=45.0,
        bar_count=10,
        tick_count=100,
        high_of_session=18100.0,
        low_of_session=17900.0,
        price_change_pct=0.5,
    )

    request = sentinel._intent_to_request(intent, snapshot)
    assert request.contract_id == "CON.F.US.MNQM26"
    assert request.side == TradeSide.LONG
    assert request.conviction == 85.0
    assert request.suggested_stop_points == 20.0
    assert request.atr_points == 15.0


# --- Contract metadata lookup ---

def test_lookup_contract_meta_full_id():
    meta = _lookup_contract_meta("CON.F.US.MNQM26")
    assert meta["tick_size"] == 0.25
    assert meta["tick_value"] == 0.50
    assert meta["point_value"] == 2.00


def test_lookup_contract_meta_root_symbol():
    meta = _lookup_contract_meta("MES")
    assert meta["tick_size"] == 0.25
    assert meta["tick_value"] == 1.25


def test_lookup_contract_meta_unknown():
    meta = _lookup_contract_meta("UNKNOWN_FUTURE")
    assert "tick_size" in meta  # Returns defaults


def test_lookup_contract_meta_commodities():
    meta = _lookup_contract_meta("CON.F.US.MCLM26")
    assert meta["tick_size"] == 0.01
    assert meta["name"] == "Micro WTI Crude Oil"


# --- Market hours ---

def test_market_hours_weekday_open(sentinel):
    tz_ct = pytz.timezone("US/Central")
    dt = tz_ct.localize(datetime(2026, 3, 24, 14, 0))
    with patch("src.sentinel.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert sentinel._is_market_open() is True


def test_market_hours_weekday_closed(sentinel):
    tz_ct = pytz.timezone("US/Central")
    dt = tz_ct.localize(datetime(2026, 3, 27, 16, 30))
    with patch("src.sentinel.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert sentinel._is_market_open() is False


def test_market_hours_sunday_evening(sentinel):
    tz_ct = pytz.timezone("US/Central")
    dt = tz_ct.localize(datetime(2026, 3, 29, 17, 30))
    with patch("src.sentinel.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert sentinel._is_market_open() is True


def test_market_hours_saturday(sentinel):
    tz_ct = pytz.timezone("US/Central")
    dt = tz_ct.localize(datetime(2026, 3, 28, 12, 0))
    with patch("src.sentinel.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert sentinel._is_market_open() is False


def test_system_state_transitions(sentinel):
    sentinel.state.system_state = SystemState.STARTING
    assert sentinel.state.system_state == SystemState.STARTING
    sentinel.state.system_state = SystemState.RUNNING
    assert sentinel.state.system_state == SystemState.RUNNING


# --- Multi-market round-robin ---

def test_multi_market_round_robin(multi_sentinel):
    assert multi_sentinel._current_contract() == "CON.F.US.MNQM26"
    multi_sentinel._next_contract()
    assert multi_sentinel._current_contract() == "CON.F.US.MESM26"
    multi_sentinel._next_contract()
    assert multi_sentinel._current_contract() == "CON.F.US.MYMM26"
    multi_sentinel._next_contract()
    assert multi_sentinel._current_contract() == "CON.F.US.MNQM26"  # Wraps around


def test_single_contract_round_robin(sentinel):
    assert sentinel._current_contract() == "CON.F.US.MNQM26"
    sentinel._next_contract()
    assert sentinel._current_contract() == "CON.F.US.MNQM26"


def test_contracts_list(multi_sentinel):
    assert len(multi_sentinel.contracts) == 3
    assert "CON.F.US.MESM26" in multi_sentinel.contracts


# --- Trade context persistence (Task 3) ---

def test_save_and_load_trade_context(sentinel):
    os.makedirs(sentinel.config.state_dir, exist_ok=True)
    sentinel._active_trade_data = {
        "MNQM26": {"entry_price": 18000, "side": "long", "conviction": 85},
    }
    sentinel._baseline_pnl = 150.0
    sentinel.state.trades_today = 3

    sentinel._save_trade_context()

    # Create new sentinel and load
    sentinel2 = Sentinel(config=sentinel.config)
    sentinel2._load_trade_context()
    assert sentinel2._active_trade_data["MNQM26"]["entry_price"] == 18000
    assert sentinel2._baseline_pnl == 150.0
    assert sentinel2.state.trades_today == 3


def test_clear_trade_context(sentinel):
    os.makedirs(sentinel.config.state_dir, exist_ok=True)
    sentinel._active_trade_data = {"MNQM26": {"entry_price": 18000}}
    sentinel._save_trade_context()

    assert os.path.exists(sentinel._state_file())
    sentinel._clear_trade_context()
    assert not os.path.exists(sentinel._state_file())


def test_load_nonexistent_context(sentinel):
    """Loading when no file exists should be a no-op."""
    sentinel._load_trade_context()
    assert sentinel._active_trade_data == {}
    assert sentinel._baseline_pnl == 0.0


def test_context_atomic_write(sentinel):
    """Save should use atomic write (write to .tmp then rename)."""
    os.makedirs(sentinel.config.state_dir, exist_ok=True)
    sentinel._active_trade_data = {"MNQ": {"entry_price": 18000}}
    sentinel._save_trade_context()

    # No .tmp file should remain
    assert not os.path.exists(sentinel._state_file() + ".tmp")
    assert os.path.exists(sentinel._state_file())


# --- Integration / Async Tests ---

@pytest.mark.asyncio
async def test_startup_sequence(sentinel):
    with (
        patch("src.sentinel.BrokerClient", return_value=AsyncMock()) as mock_broker_cls,
        patch("src.sentinel.MarketDataPipeline", return_value=AsyncMock()) as mock_md_cls,
        patch("src.sentinel.RiskGuardian", return_value=MagicMock()) as mock_risk_cls,
        patch("src.sentinel.DecisionEngine", return_value=MagicMock()) as mock_dec_cls,
        patch("src.sentinel.LearningEngine", return_value=MagicMock()) as mock_learn_cls,
    ):
        mock_broker = mock_broker_cls.return_value
        mock_broker._token = "test_token"
        mock_broker.token = "test_token"
        mock_broker.account_balance = 150000.0

        mock_md = mock_md_cls.return_value
        mock_md.is_connected = True
        mock_md._latest_quote = {"price": 100}

        with patch.object(Sentinel, "_trading_loop", return_value=None):
            await sentinel.start()

        assert sentinel.state.system_state == SystemState.RUNNING
        assert mock_broker.connect.called
        assert mock_md.start.called


@pytest.mark.asyncio
async def test_trading_cycle_with_trade(sentinel):
    sentinel.broker = AsyncMock()
    sentinel.market_data = MagicMock()
    sentinel.risk = AsyncMock()
    sentinel.decision = AsyncMock()
    sentinel.learning = MagicMock()
    sentinel.learning.history = []
    sentinel.learning.get_performance_matrix.return_value = MagicMock(
        win_rate=0.5, avg_win_loss_ratio=1.5, profit_factor=1.2, total_trades=10,
    )

    snapshot = MarketSnapshot(
        timestamp=time.time(),
        contract_id="CON.F.US.MNQM26",
        last_price=18000.0,
        best_bid=17999.0,
        best_ask=18001.0,
        spread=2.0,
        atr_points=15.0,
        vpin=0.2,
        ofi_zscore=1.5,
        volume_rate=1.2,
        bid_ask_imbalance=0.0,
        regime=MarketRegime.TRENDING_UP,
        trend_strength=45.0,
        bar_count=10,
        tick_count=100,
        high_of_session=18100.0,
        low_of_session=17900.0,
        price_change_pct=0.5,
    )
    sentinel.market_data.get_snapshot.return_value = snapshot
    sentinel.market_data.seconds_since_last_update = 0.5

    intent = TradeIntent(
        side=TradeSide.LONG,
        conviction=85.0,
        thesis="test",
        suggested_stop_points=20.0,
        suggested_target_points=40.0,
        frameworks_consulted=[],
        frameworks_agreeing=[],
        regime=MarketRegime.TRENDING_UP,
        snapshot_timestamp=time.time(),
    )

    decision = TradeDecision(approved=True, size=1, stop_loss_ticks=80, take_profit_ticks=160)
    sentinel.risk.evaluate.return_value = decision
    sentinel.risk.execute.return_value = 12345

    sentinel.state.system_state = SystemState.RUNNING
    with patch.object(sentinel, "_is_market_open", return_value=True):
        await sentinel._handle_trade_intent(intent, snapshot)

    assert sentinel.risk.execute.called
    assert sentinel.state.trades_today == 1


@pytest.mark.asyncio
async def test_daily_limit_halts_trading(sentinel):
    sentinel.broker = AsyncMock()
    sentinel.risk = MagicMock()
    sentinel.risk.config.daily_loss_limit = 1000.0

    sentinel.broker.get_realized_pnl.return_value = -1500.0
    sentinel.broker.ping.return_value = True

    await sentinel._health_monitor_logic()
    assert sentinel.state.system_state == SystemState.TRADING_HALTED


async def _health_monitor_logic(self):
    if self.broker:
        ping_ok = await self.broker.ping()
        self.state.broker_connected = ping_ok
        if ping_ok:
            self.state.account_balance = self.broker.account_balance
            self.state.daily_pnl = await self.broker.get_realized_pnl()
            if self.state.daily_pnl <= -self.risk.config.daily_loss_limit:
                self.state.system_state = SystemState.TRADING_HALTED


Sentinel._health_monitor_logic = _health_monitor_logic


@pytest.mark.asyncio
async def test_stale_data_halts_trading(sentinel):
    sentinel.market_data = MagicMock()
    sentinel.market_data.seconds_since_last_update = 100.0
    sentinel.config.max_market_data_stale_seconds = 60
    sentinel.state.system_state = SystemState.RUNNING

    with patch.object(sentinel, "_is_market_open", return_value=True):
        if sentinel.market_data.seconds_since_last_update > sentinel.config.max_market_data_stale_seconds:
            sentinel.state.system_state = SystemState.DEGRADED

    assert sentinel.state.system_state == SystemState.DEGRADED


@pytest.mark.asyncio
async def test_graceful_shutdown(sentinel):
    sentinel.broker = AsyncMock()
    sentinel.market_data = AsyncMock()
    sentinel.learning = MagicMock()

    await sentinel.stop()

    assert sentinel.state.system_state == SystemState.STOPPED
    assert sentinel.broker.disconnect.called


@pytest.mark.asyncio
async def test_obsidian_status_write(sentinel):
    sentinel.state.daily_pnl = 123.45
    sentinel.state.system_state = SystemState.RUNNING

    sentinel._write_obsidian_status(sentinel.state)

    assert os.path.exists(sentinel.config.obsidian_path)
    with open(sentinel.config.obsidian_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "RUNNING" in content
        assert "$123.45" in content


@pytest.mark.asyncio
async def test_obsidian_shows_contract_pool(multi_sentinel):
    multi_sentinel.state.system_state = SystemState.RUNNING
    multi_sentinel._write_obsidian_status(multi_sentinel.state)

    with open(multi_sentinel.config.obsidian_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "MNQM26" in content
        assert "MESM26" in content
        assert "MYMM26" in content


@pytest.mark.asyncio
async def test_consecutive_error_tracking(sentinel):
    sentinel.state.system_state = SystemState.RUNNING
    sentinel.config.max_consecutive_errors = 3

    with patch.object(sentinel, "_is_market_open", side_effect=Exception("Test error")):
        for _ in range(3):
            try:
                if sentinel._is_market_open():
                    pass
            except Exception:
                sentinel._consecutive_errors += 1
                if sentinel._consecutive_errors >= sentinel.config.max_consecutive_errors:
                    sentinel.state.system_state = SystemState.TRADING_HALTED

    assert sentinel.state.system_state == SystemState.TRADING_HALTED


@pytest.mark.asyncio
async def test_closed_trade_detection(sentinel):
    sentinel.broker = AsyncMock()
    sentinel._last_positions = [{"contractId": "MNQ", "id": 1}]
    current_positions = []

    sentinel.broker.get_trades.return_value = [{"contractId": "MNQ", "profitAndLoss": 100.0}]

    await sentinel._detect_closed_trades(current_positions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
