"""Tests for the PositionManager (active trade monitoring)."""
import asyncio
import json
import os
import time
import pytest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock, patch
from src.position_manager import (
    PositionManager, PositionManagerConfig, PositionState, ExitReason
)
from src.market_data import MarketSnapshot, MarketRegime, DepthLevel


def _mock_snapshot(
    price=20000.0, vpin=0.3, ofi=1.0, imbalance=0.2,
    regime=MarketRegime.TRENDING_UP, atr=25.0,
    bid=19999.75, ask=20000.25,
):
    return MarketSnapshot(
        timestamp=time.time(),
        contract_id="CON.F.US.MNQ.M26",
        last_price=price,
        best_bid=bid,
        best_ask=ask,
        spread=ask - bid,
        atr_points=atr,
        vpin=vpin,
        ofi_zscore=ofi,
        volume_rate=1.0,
        bid_ask_imbalance=imbalance,
        regime=regime,
        trend_strength=30.0,
        bar_count=50,
        tick_count=500,
        high_of_session=20050.0,
        low_of_session=19950.0,
        price_change_pct=0.1,
    )


class TestPositionState:
    def test_initial_state(self):
        state = PositionState(
            contract_id="MNQ",
            side="long",
            entry_price=20000.0,
            entry_time=time.time(),
            size=1,
            target_price=20050.0,
            stop_price=19950.0,
            thesis="Test trade",
            conviction=80.0,
        )
        assert not state.is_closed
        assert state.max_favorable_excursion == 0.0
        assert state.max_adverse_excursion == 0.0
        assert not state.trail_stop_active

    def test_unrealized_pnl_tracking(self):
        state = PositionState(
            contract_id="MNQ",
            side="long",
            entry_price=20000.0,
            entry_time=time.time(),
            size=1,
            target_price=20050.0,
            stop_price=19950.0,
            thesis="Test",
            conviction=80.0,
        )
        state.unrealized_pnl = 25.0
        state.max_favorable_excursion = 25.0
        assert state.max_favorable_excursion == 25.0


class TestRuleBasedExits:
    def setup_method(self):
        self.broker = AsyncMock()
        self.config = PositionManagerConfig(
            check_interval_seconds=0.1,
            vpin_exit_threshold=0.7,
            ofi_flip_threshold=-1.5,
            time_exit_no_progress_seconds=600.0,
            max_hold_seconds=3600.0,
        )
        self.pm = PositionManager(broker=self.broker, config=self.config)

    def test_vpin_toxic_exit(self):
        """Should trigger exit when VPIN > threshold."""
        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time(), size=1, target_price=20050.0,
            stop_price=19950.0, thesis="test", conviction=80.0,
        )
        snap = _mock_snapshot(vpin=0.85)  # Toxic
        result = self.pm._evaluate_rules(state, snap)
        assert result == ExitReason.VPIN_TOXIC

    def test_vpin_safe_no_exit(self):
        """Should not trigger when VPIN is safe."""
        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time(), size=1, target_price=20050.0,
            stop_price=19950.0, thesis="test", conviction=80.0,
        )
        snap = _mock_snapshot(vpin=0.3)
        result = self.pm._evaluate_rules(state, snap)
        assert result is None

    def test_ofi_flip_long(self):
        """Long position should exit when OFI Z-score goes strongly negative."""
        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time(), size=1, target_price=20050.0,
            stop_price=19950.0, thesis="test", conviction=80.0,
        )
        snap = _mock_snapshot(ofi=-2.0)  # Strong sell pressure
        result = self.pm._evaluate_rules(state, snap)
        assert result == ExitReason.OFI_FLIP

    def test_ofi_flip_short(self):
        """Short position should exit when OFI Z-score goes strongly positive."""
        state = PositionState(
            contract_id="MNQ", side="short", entry_price=20000.0,
            entry_time=time.time(), size=1, target_price=19950.0,
            stop_price=20050.0, thesis="test", conviction=80.0,
        )
        snap = _mock_snapshot(ofi=2.0)  # Strong buy pressure
        result = self.pm._evaluate_rules(state, snap)
        assert result == ExitReason.OFI_FLIP

    def test_max_hold_time_exit(self):
        """Should exit after max hold time."""
        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time() - 4000,  # Held for over an hour
            size=1, target_price=20050.0, stop_price=19950.0,
            thesis="test", conviction=80.0,
        )
        snap = _mock_snapshot()
        result = self.pm._evaluate_rules(state, snap)
        assert result == ExitReason.TIME_EXPIRED


class TestTrailingStop:
    def setup_method(self):
        self.broker = AsyncMock()
        self.config = PositionManagerConfig(
            trail_trigger_pct=0.50,
            trail_offset_pct=0.25,
        )
        self.pm = PositionManager(broker=self.broker, config=self.config)

    def test_trail_activates_at_50pct(self):
        """Trail stop activates at 50% of target distance."""
        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time(), size=1,
            target_price=20100.0,  # 100 points target
            stop_price=19900.0, thesis="test", conviction=80.0,
        )
        # Price at 50% of target (20050)
        snap = _mock_snapshot(price=20055.0)
        self.pm._update_trailing_stop(state, snap, tick_size=0.25, tick_value=0.50)
        assert state.trail_stop_active
        # Trail stop should be at entry + 25% of target = 20000 + 25 = 20025
        assert state.trail_stop_price == pytest.approx(20025.0, abs=1.0)

    def test_trail_not_active_below_trigger(self):
        """Trail stop should not activate below trigger percent."""
        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time(), size=1,
            target_price=20100.0, stop_price=19900.0,
            thesis="test", conviction=80.0,
        )
        snap = _mock_snapshot(price=20030.0)  # Only 30% of target
        self.pm._update_trailing_stop(state, snap, tick_size=0.25, tick_value=0.50)
        assert not state.trail_stop_active

    def test_trail_ratchets_up(self):
        """Trail stop should ratchet higher as price rises."""
        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time(), size=1,
            target_price=20100.0, stop_price=19900.0,
            thesis="test", conviction=80.0,
        )
        # Activate at 60%
        snap1 = _mock_snapshot(price=20060.0)
        self.pm._update_trailing_stop(state, snap1, tick_size=0.25, tick_value=0.50)
        trail_1 = state.trail_stop_price

        # Price moves higher — trail should ratchet
        snap2 = _mock_snapshot(price=20080.0)
        self.pm._update_trailing_stop(state, snap2, tick_size=0.25, tick_value=0.50)
        assert state.trail_stop_price >= trail_1

    def test_trail_short_position(self):
        """Trail stop for short works in reverse."""
        state = PositionState(
            contract_id="MNQ", side="short", entry_price=20000.0,
            entry_time=time.time(), size=1,
            target_price=19900.0,  # 100 points down
            stop_price=20100.0, thesis="test", conviction=80.0,
        )
        snap = _mock_snapshot(price=19940.0)  # 60% of target
        self.pm._update_trailing_stop(state, snap, tick_size=0.25, tick_value=0.50)
        assert state.trail_stop_active
        # Trail stop should be at entry - 25% of target_distance = 20000 - 25 = 19975
        assert state.trail_stop_price == pytest.approx(19975.0, abs=1.0)


class TestTradeHistory:
    def test_save_trade_outcome(self, tmp_path):
        broker = AsyncMock()
        config = PositionManagerConfig(state_dir=str(tmp_path))
        pm = PositionManager(broker=broker, config=config)

        state = PositionState(
            contract_id="MNQ", side="long", entry_price=20000.0,
            entry_time=time.time() - 300, size=1,
            target_price=20050.0, stop_price=19950.0,
            thesis="Test trade", conviction=85.0,
            exit_price=20030.0, exit_time=time.time(),
            exit_reason="bracket_closed", pnl=60.0,
            max_favorable_excursion=75.0, max_adverse_excursion=-10.0,
            is_closed=True,
        )
        pm._save_trade_outcome(state)

        path = tmp_path / "trade_history.json"
        assert path.exists()
        with open(path) as f:
            history = json.load(f)
        assert len(history) == 1
        assert history[0]["contract_id"] == "MNQ"
        assert history[0]["pnl"] == 60.0
        assert history[0]["exit_reason"] == "bracket_closed"

    def test_history_appends(self, tmp_path):
        broker = AsyncMock()
        config = PositionManagerConfig(state_dir=str(tmp_path))
        pm = PositionManager(broker=broker, config=config)

        for i in range(3):
            state = PositionState(
                contract_id=f"MKT{i}", side="long", entry_price=100+i,
                entry_time=time.time(), size=1,
                target_price=110+i, stop_price=90+i,
                thesis=f"Trade {i}", conviction=80.0,
                exit_price=105+i, exit_time=time.time(),
                exit_reason="target_hit", pnl=10.0,
                is_closed=True,
            )
            pm._save_trade_outcome(state)

        path = tmp_path / "trade_history.json"
        with open(path) as f:
            history = json.load(f)
        assert len(history) == 3


class TestL2DepthIntegration:
    """Test L2 depth book in MarketDataPipeline."""

    def test_depth_book_update(self):
        from src.market_data import MarketDataPipeline
        pipeline = MarketDataPipeline(jwt_token="test", contract_id="TEST")

        # Simulate depth updates
        levels = [
            {"price": 20000.0, "volume": 10, "type": 1, "timestamp": "2026-03-26T00:00:00Z"},
            {"price": 19999.75, "volume": 15, "type": 1, "timestamp": "2026-03-26T00:00:00Z"},
            {"price": 20000.25, "volume": 8, "type": 2, "timestamp": "2026-03-26T00:00:00Z"},
            {"price": 20000.50, "volume": 12, "type": 2, "timestamp": "2026-03-26T00:00:00Z"},
        ]
        pipeline._process_depth(levels)

        assert len(pipeline._l2_bids) == 2
        assert len(pipeline._l2_asks) == 2
        assert pipeline._l2_bids[20000.0] == 10
        assert pipeline._l2_asks[20000.25] == 8

    def test_depth_book_reset(self):
        from src.market_data import MarketDataPipeline
        pipeline = MarketDataPipeline(jwt_token="test", contract_id="TEST")

        # Add some levels
        pipeline._process_depth([
            {"price": 20000.0, "volume": 10, "type": 1},
            {"price": 20000.25, "volume": 8, "type": 2},
        ])
        assert len(pipeline._l2_bids) == 1

        # Reset
        pipeline._process_depth([{"type": 6}])
        assert len(pipeline._l2_bids) == 0
        assert len(pipeline._l2_asks) == 0

    def test_depth_level_removal(self):
        from src.market_data import MarketDataPipeline
        pipeline = MarketDataPipeline(jwt_token="test", contract_id="TEST")

        # Add a level
        pipeline._process_depth([{"price": 20000.0, "volume": 10, "type": 1}])
        assert 20000.0 in pipeline._l2_bids

        # Remove it (volume=0)
        pipeline._process_depth([{"price": 20000.0, "volume": 0, "type": 1}])
        assert 20000.0 not in pipeline._l2_bids

    def test_l2_imbalance_from_depth(self):
        from src.market_data import MarketDataPipeline
        pipeline = MarketDataPipeline(jwt_token="test", contract_id="TEST")

        # Heavy bid side
        pipeline._process_depth([
            {"price": 20000.0, "volume": 100, "type": 1},
            {"price": 19999.75, "volume": 50, "type": 1},
            {"price": 20000.25, "volume": 10, "type": 2},
        ])

        imbalance = pipeline._compute_bid_ask_imbalance()
        assert imbalance > 0.5  # Strongly bid-side

    def test_snapshot_includes_l2(self):
        from src.market_data import MarketDataPipeline, Quote
        pipeline = MarketDataPipeline(jwt_token="test", contract_id="TEST")

        # Need a quote for snapshot
        pipeline._latest_quote = Quote(
            timestamp=time.time(), last_price=20000.0,
            best_bid=19999.75, best_ask=20000.25, volume=1000,
        )
        pipeline._process_depth([
            {"price": 20000.0, "volume": 10, "type": 1},
            {"price": 20000.25, "volume": 8, "type": 2},
        ])

        snap = pipeline.get_snapshot()
        assert snap.l2_bid_total_volume == 10
        assert snap.l2_ask_total_volume == 8
        assert len(snap.l2_bid_levels) >= 1


class TestExpandedContractMeta:
    """Test that the expanded CONTRACT_META covers all asset classes."""

    def test_all_asset_classes_present(self):
        from src.sentinel import CONTRACT_META
        classes = set(m.get("asset_class", "") for m in CONTRACT_META.values())
        assert "equity_index" in classes
        assert "metals" in classes
        assert "energy" in classes
        assert "currency" in classes
        assert "treasury" in classes
        assert "agriculture" in classes
        assert "crypto" in classes

    def test_at_least_50_instruments(self):
        from src.sentinel import CONTRACT_META
        assert len(CONTRACT_META) >= 50

    def test_micro_contracts(self):
        from src.sentinel import CONTRACT_META
        micros = [k for k, v in CONTRACT_META.items() if "Micro" in v["name"]]
        assert len(micros) >= 8  # At least MNQ/MES/MYM/M2K/MCL/MGC/SIL/MHG

    def test_agriculture_contracts(self):
        from src.sentinel import CONTRACT_META, _lookup_contract_meta
        meta = _lookup_contract_meta("CON.F.US.ZCE.K26")
        assert "Corn" in meta["name"]

    def test_crypto_contracts(self):
        from src.sentinel import CONTRACT_META, _lookup_contract_meta
        meta = _lookup_contract_meta("CON.F.US.MBT.H26")
        assert "Bitcoin" in meta["name"]

    def test_currency_contracts(self):
        from src.sentinel import CONTRACT_META, _lookup_contract_meta
        meta = _lookup_contract_meta("CON.F.US.EU6.M26")
        assert "Euro" in meta["name"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
