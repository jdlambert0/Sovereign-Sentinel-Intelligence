"""
Integration Tests (Task 7)

End-to-end tests that verify the full pipeline works together:
  MarketSnapshot → AI Decision → Risk Evaluation → (mock) Execution → Learning

These tests use mocked broker/market data but exercise the real decision
engine, risk engine, and learning engine together.
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz

from src.broker import BrokerClient
from src.market_data import (
    MarketDataPipeline,
    MarketSnapshot,
    MarketRegime,
    TradeTick,
    Bar,
    RollingStats,
)
from src.decision import DecisionEngine, DecisionConfig, TradeIntent
from src.risk import RiskGuardian, TradeRequest, TradeSide, TradeDecision
from src.learning import LearningEngine, TradeRecord
from src.sentinel import Sentinel, SentinelConfig, SystemState, _lookup_contract_meta


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def make_snapshot(
    contract_id="CON.F.US.MNQM26",
    price=18000.0,
    regime=MarketRegime.TRENDING_UP,
    atr=12.0,
    vpin=0.3,
    ofi=1.5,
    imbalance=0.3,
) -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=time.time(),
        contract_id=contract_id,
        last_price=price,
        best_bid=price - 0.25,
        best_ask=price + 0.25,
        spread=0.50,
        atr_points=atr,
        vpin=vpin,
        ofi_zscore=ofi,
        volume_rate=1.2,
        bid_ask_imbalance=imbalance,
        regime=regime,
        trend_strength=40.0,
        bar_count=50,
        tick_count=500,
        high_of_session=price + 50,
        low_of_session=price - 50,
        price_change_pct=0.5,
    )


# ---------------------------------------------------------------------------
#  Integration: Decision → Risk pipeline
# ---------------------------------------------------------------------------

class TestDecisionToRisk:
    """Test that AI decisions flow correctly into risk evaluation."""

    @pytest.fixture
    def mock_broker(self):
        broker = MagicMock(spec=BrokerClient)
        broker.account_balance = 150000.0
        broker.get_realized_pnl = AsyncMock(return_value=0.0)
        broker.get_open_positions = AsyncMock(return_value=[])
        broker.get_open_orders = AsyncMock(return_value=[])
        broker.place_market_order = AsyncMock(return_value=12345)
        broker.close_position = AsyncMock()
        return broker

    @pytest.fixture
    def decision_engine(self):
        config = DecisionConfig(
            ai_provider="file_ipc",
            ai_ipc_dir="/tmp/integration_test_ipc",
            min_conviction_to_trade=70.0,
        )
        engine = DecisionEngine(config)
        # Mock the backend to return a controlled response
        async def mock_call(prompt, snapshot_data=None):
            return {
                "signal": "long",
                "conviction": 82,
                "thesis": "Integration test: strong momentum",
                "stop_distance_points": 15.0,
                "target_distance_points": 30.0,
                "frameworks_cited": ["momentum", "order_flow"],
                "time_horizon": "scalp",
            }
        engine._backend.call = mock_call
        return engine

    @pytest.mark.asyncio
    async def test_decision_produces_valid_trade_request(self, decision_engine):
        snapshot = make_snapshot()
        intent = await decision_engine.analyze(snapshot)
        assert intent is not None
        assert intent.side == TradeSide.LONG
        assert intent.conviction == 82.0

        # Convert to TradeRequest (as Sentinel would)
        meta = _lookup_contract_meta(snapshot.contract_id)
        request = TradeRequest(
            contract_id=snapshot.contract_id,
            side=intent.side,
            conviction=intent.conviction,
            thesis=intent.thesis,
            suggested_stop_points=intent.suggested_stop_points,
            suggested_target_points=intent.suggested_target_points,
            atr_points=snapshot.atr_points,
            tick_size=meta["tick_size"],
            tick_value=meta["tick_value"],
        )
        assert request.contract_id == "CON.F.US.MNQM26"
        assert request.side == TradeSide.LONG
        assert request.conviction == 82.0

    @pytest.mark.asyncio
    async def test_full_decision_to_risk_pipeline(self, decision_engine, mock_broker):
        snapshot = make_snapshot()
        intent = await decision_engine.analyze(snapshot)
        assert intent is not None

        # Risk evaluation
        guardian = RiskGuardian(mock_broker)
        meta = _lookup_contract_meta(snapshot.contract_id)
        request = TradeRequest(
            contract_id=snapshot.contract_id,
            side=intent.side,
            conviction=intent.conviction,
            thesis=intent.thesis,
            suggested_stop_points=intent.suggested_stop_points,
            suggested_target_points=intent.suggested_target_points,
            atr_points=snapshot.atr_points,
            tick_size=meta["tick_size"],
            tick_value=meta["tick_value"],
        )
        decision = await guardian.evaluate(request)
        assert decision.approved is True
        assert decision.size > 0
        assert decision.stop_loss_ticks > 0
        assert decision.take_profit_ticks > 0

    @pytest.mark.asyncio
    async def test_low_conviction_rejected_by_risk(self, mock_broker):
        """AI gives low conviction → Risk should reject."""
        config = DecisionConfig(
            ai_provider="file_ipc",
            ai_ipc_dir="/tmp/integration_test_ipc",
            min_conviction_to_trade=40.0,  # Lower threshold so intent gets through
        )
        engine = DecisionEngine(config)

        async def mock_call(prompt, snapshot_data=None):
            return {
                "signal": "long",
                "conviction": 45,
                "thesis": "Weak signal",
                "stop_distance_points": 10.0,
                "target_distance_points": 20.0,
            }

        engine._backend.call = mock_call
        snapshot = make_snapshot()
        intent = await engine.analyze(snapshot)
        assert intent is not None

        # Risk should reject low conviction
        guardian = RiskGuardian(mock_broker)
        meta = _lookup_contract_meta(snapshot.contract_id)
        request = TradeRequest(
            contract_id=snapshot.contract_id,
            side=intent.side,
            conviction=intent.conviction,
            thesis=intent.thesis,
            suggested_stop_points=intent.suggested_stop_points,
            suggested_target_points=intent.suggested_target_points,
            atr_points=snapshot.atr_points,
            tick_size=meta["tick_size"],
            tick_value=meta["tick_value"],
        )
        decision = await guardian.evaluate(request)
        assert decision.approved is False


# ---------------------------------------------------------------------------
#  Integration: Learning records from trade results
# ---------------------------------------------------------------------------

class TestLearningIntegration:

    @pytest.fixture
    def learning_engine(self, tmp_path):
        return LearningEngine(
            obsidian_path=str(tmp_path / "obsidian"),
            config_path=str(tmp_path / "config"),
        )

    def test_trade_lifecycle_recorded(self, learning_engine):
        """Record a complete trade lifecycle and verify metrics update."""
        record = TradeRecord(
            trade_id="INT-1",
            contract_id="CON.F.US.MNQM26",
            side="long",
            entry_time=time.time() - 300,
            exit_time=time.time(),
            entry_price=18000.0,
            exit_price=18015.0,
            size=1,
            pnl=30.0,
            fees=2.0,
            net_pnl=28.0,
            conviction=82.0,
            thesis="Integration test trade",
            frameworks_used=["momentum", "order_flow"],
            regime_at_entry="trending_up",
            atr_at_entry=12.0,
            vpin_at_entry=0.3,
            ofi_at_entry=1.5,
        )
        learning_engine.record_trade(record)
        matrix = learning_engine.get_performance_matrix()
        assert matrix.total_trades == 1
        assert matrix.wins == 1
        assert matrix.total_pnl == 28.0

    def test_multi_market_trades_tracked(self, learning_engine):
        """Trades across different contracts are all tracked."""
        for i, cid in enumerate(["MNQM26", "MESM26", "MYMM26"]):
            learning_engine.record_trade(
                TradeRecord(
                    trade_id=f"MM-{i}",
                    contract_id=cid,
                    side="long",
                    entry_time=time.time(),
                    exit_time=time.time() + 300,
                    entry_price=18000.0,
                    exit_price=18010.0,
                    size=1,
                    pnl=20.0,
                    fees=2.0,
                    net_pnl=18.0,
                    conviction=80.0,
                    thesis=f"Trade on {cid}",
                    frameworks_used=["momentum"],
                    regime_at_entry="trending_up",
                    atr_at_entry=12.0,
                    vpin_at_entry=0.3,
                    ofi_at_entry=1.5,
                )
            )

        matrix = learning_engine.get_performance_matrix()
        assert matrix.total_trades == 3
        assert matrix.total_pnl == 54.0


# ---------------------------------------------------------------------------
#  Integration: Market Data pipeline calculations
# ---------------------------------------------------------------------------

class TestMarketDataIntegration:
    """Test that market data calculations work end-to-end."""

    def test_bid_ask_imbalance_estimation(self):
        pipeline = MarketDataPipeline("token", "TEST")
        # Simulate 50 ticks: 35 buys, 15 sells → imbalance = (35-15)/50 = 0.4
        for i in range(50):
            side = 0 if i < 35 else 1
            pipeline._ticks.append(TradeTick(time.time(), 100.0, 10, side))

        imbalance = pipeline.estimate_bid_ask_imbalance()
        assert abs(imbalance - 0.4) < 0.01

    def test_bid_ask_imbalance_balanced(self):
        pipeline = MarketDataPipeline("token", "TEST")
        for i in range(50):
            side = 0 if i % 2 == 0 else 1
            pipeline._ticks.append(TradeTick(time.time(), 100.0, 10, side))

        imbalance = pipeline.estimate_bid_ask_imbalance()
        assert abs(imbalance) < 0.05

    def test_bid_ask_imbalance_insufficient_data(self):
        pipeline = MarketDataPipeline("token", "TEST")
        assert pipeline.estimate_bid_ask_imbalance() == 0.0

    def test_ofi_welford_rolling_stats(self):
        """Verify Welford rolling stats produce correct mean/std."""
        stats = RollingStats()
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for v in values:
            stats.update(v)

        assert abs(stats.mean - 30.0) < 0.01
        # std = sqrt(sum((x-30)^2) / 4) = sqrt(1000/4) = sqrt(250) ≈ 15.81
        import math
        assert abs(stats.std - math.sqrt(250)) < 0.01

    def test_ofi_rolling_updates_via_ticks(self):
        """Verify OFI rolling stats update as ticks arrive."""
        pipeline = MarketDataPipeline("token", "TEST")
        pipeline._ofi_window_size = 10  # Small window for testing

        # Feed 30 ticks (3 windows worth)
        for i in range(30):
            side = 0 if i % 2 == 0 else 1
            pipeline._update_ofi_rolling(TradeTick(time.time(), 100.0, 10, side))

        assert pipeline._ofi_rolling.n == 3  # 30 ticks / 10 window = 3 samples

    def test_snapshot_includes_bid_ask_imbalance(self):
        pipeline = MarketDataPipeline("token", "TEST")
        from src.market_data import Quote
        pipeline._latest_quote = Quote(time.time(), 100, 99.5, 100.5, 1000)
        for i in range(50):
            side = 0 if i < 40 else 1
            pipeline._ticks.append(TradeTick(time.time(), 100.0, 10, side))
            pipeline._bars.append(Bar(i, 100, 101, 99, 100, 10, 1))

        snapshot = pipeline.get_snapshot()
        # 40 buys, 10 sells out of last 50 → imbalance = (40-10)/50 = 0.6
        assert snapshot.bid_ask_imbalance > 0.5


# ---------------------------------------------------------------------------
#  Integration: Trade context persistence through crash
# ---------------------------------------------------------------------------

class TestCrashRecovery:
    """Test that trade context survives a simulated crash."""

    @pytest.fixture
    def state_dir(self, tmp_path):
        return str(tmp_path / "state")

    def test_context_survives_restart(self, state_dir):
        config = SentinelConfig(
            state_dir=state_dir,
            obsidian_path=os.path.join(state_dir, "status.md"),
        )
        # Simulate first run: sentinel has active trade
        s1 = Sentinel(config=config)
        s1._active_trade_data = {
            "MNQM26": {
                "entry_price": 18000,
                "side": "long",
                "conviction": 85,
                "thesis": "test",
                "frameworks": ["momentum"],
                "regime": "trending_up",
                "entry_time": time.time(),
                "size": 1,
                "atr": 12.0,
                "vpin": 0.3,
                "ofi": 1.5,
            }
        }
        s1._baseline_pnl = 50.0
        s1.state.trades_today = 2
        s1._save_trade_context()

        # Simulate crash → new sentinel starts
        s2 = Sentinel(config=config)
        s2._load_trade_context()

        assert "MNQM26" in s2._active_trade_data
        assert s2._active_trade_data["MNQM26"]["entry_price"] == 18000
        assert s2._baseline_pnl == 50.0
        assert s2.state.trades_today == 2


# ---------------------------------------------------------------------------
#  Integration: Multi-market contract metadata
# ---------------------------------------------------------------------------

class TestMultiMarketMetadata:
    """Verify contract metadata lookup works for all supported instruments."""

    def test_all_known_contracts_have_metadata(self):
        for root in ["MNQ", "MES", "MYM", "M2K", "NQ", "ES", "YM", "RTY",
                      "MCL", "MGC", "SIL", "MHG", "ZN", "ZB"]:
            meta = _lookup_contract_meta(root)
            assert "tick_size" in meta
            assert "tick_value" in meta
            assert meta["tick_size"] > 0
            assert meta["tick_value"] > 0

    def test_topstepx_format_contracts(self):
        """Full TopStepX contract IDs resolve correctly."""
        meta = _lookup_contract_meta("CON.F.US.MESM26")
        assert meta["name"] == "Micro E-mini S&P 500"
        assert meta["tick_size"] == 0.25
        assert meta["tick_value"] == 1.25

    def test_commodity_contracts(self):
        meta = _lookup_contract_meta("CON.F.US.MCLM26")
        assert meta["name"] == "Micro WTI Crude Oil"
        assert meta["tick_value"] == 1.00

    def test_treasury_contracts(self):
        meta = _lookup_contract_meta("ZN")
        assert "10-Year T-Note" in meta["name"]

    def test_treasury_contracts_full_id(self):
        meta = _lookup_contract_meta("CON.F.US.TYA.M26")
        assert "10yr Treasury" in meta["name"]
        assert meta["tick_size"] == 0.015625


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
