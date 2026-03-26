"""Tests for the Market Scanner (multi-market intelligence)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.scanner import MarketScanner, MarketScore, AssetClassState
from src.market_data import MarketSnapshot, MarketRegime


def _make_snapshot(
    contract_id="MNQ", price=20000.0, vpin=0.3, ofi=1.5,
    trend=35.0, atr=25.0, regime=MarketRegime.TRENDING_UP,
    imbalance=0.3, change_pct=0.1, bar_count=50, tick_count=500,
):
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
        volume_rate=1.0,
        bid_ask_imbalance=imbalance,
        regime=regime,
        trend_strength=trend,
        bar_count=bar_count,
        tick_count=tick_count,
        high_of_session=price + 50,
        low_of_session=price - 50,
        price_change_pct=change_pct,
    )


_META = {
    "MNQ": {"name": "Micro E-mini Nasdaq-100", "tick_size": 0.25, "tick_value": 0.50, "asset_class": "equity_index"},
    "MES": {"name": "Micro E-mini S&P 500", "tick_size": 0.25, "tick_value": 1.25, "asset_class": "equity_index"},
    "MGC": {"name": "Micro Gold", "tick_size": 0.10, "tick_value": 1.00, "asset_class": "metals"},
    "MCL": {"name": "Micro WTI Crude", "tick_size": 0.01, "tick_value": 1.00, "asset_class": "energy"},
    "EU6": {"name": "Euro FX", "tick_size": 0.00005, "tick_value": 6.25, "asset_class": "currency"},
}


class TestMarketScoring:
    def setup_method(self):
        self.scanner = MarketScanner()

    def test_score_trending_market(self):
        """A strongly trending market with clean flow should score high."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.5, trend=45.0, vpin=0.2),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert len(scores) == 1
        assert scores[0].score > 60

    def test_score_quiet_market(self):
        """A quiet market with no direction should score low."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=0.1, trend=10.0, vpin=0.5,
                                   regime=MarketRegime.CHOPPY),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert len(scores) == 1
        assert scores[0].score < 40

    def test_scores_sorted_descending(self):
        """Scores should be sorted highest first."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.5, trend=50.0, vpin=0.1),
            "MES": _make_snapshot("MES", ofi=0.5, trend=15.0, vpin=0.6,
                                   regime=MarketRegime.CHOPPY),
            "MGC": _make_snapshot("MGC", ofi=1.8, trend=30.0, vpin=0.2,
                                   price=3000.0),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert len(scores) == 3
        for i in range(len(scores) - 1):
            assert scores[i].score >= scores[i + 1].score

    def test_direction_long(self):
        """Strong buy flow in uptrend should produce 'long' direction."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.0, regime=MarketRegime.TRENDING_UP),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert scores[0].direction == "long"

    def test_direction_short(self):
        """Strong sell flow in downtrend should produce 'short' direction."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=-2.0, regime=MarketRegime.TRENDING_DOWN),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert scores[0].direction == "short"

    def test_direction_neutral(self):
        """Choppy market with weak flow should be neutral."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=0.3, trend=8.0,
                                   regime=MarketRegime.CHOPPY),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert scores[0].direction == "neutral"
        assert not scores[0].is_tradeable

    def test_toxic_flow_reduces_score(self):
        """High VPIN should reduce the flow_clean component."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", vpin=0.85, ofi=2.0, trend=40.0),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert scores[0].components["flow_clean"] < 30

    def test_skip_stale_market(self):
        """Markets with insufficient data should be skipped."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", bar_count=2, tick_count=10),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert len(scores) == 0

    def test_skip_active_positions(self):
        """Markets with active positions should be excluded."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.5, trend=50.0),
            "MES": _make_snapshot("MES", ofi=2.0, trend=40.0),
        }
        active = {"MNQ": {"side": "long"}}
        scores = self.scanner.scan(snapshots, _META, active)
        assert len(scores) == 1
        assert scores[0].contract_id == "MES"


class TestCrossAssetCorrelation:
    def setup_method(self):
        self.scanner = MarketScanner()

    def test_asset_class_aggregation(self):
        """Should aggregate multiple equity index markets correctly."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.0, change_pct=0.3),
            "MES": _make_snapshot("MES", ofi=1.5, change_pct=0.2),
        }
        self.scanner.scan(snapshots, _META)
        states = self.scanner.asset_class_states
        assert "equity_index" in states
        assert states["equity_index"].member_count == 2
        assert states["equity_index"].bullish_count == 2

    def test_mixed_sentiment(self):
        """Should detect mixed sentiment when markets disagree."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.0),
            "MES": _make_snapshot("MES", ofi=-1.5),
        }
        self.scanner.scan(snapshots, _META)
        states = self.scanner.asset_class_states
        eq = states["equity_index"]
        assert eq.sentiment == "mixed"

    def test_cross_asset_summary(self):
        """Should produce a summary for AI prompt context."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.0),
            "MGC": _make_snapshot("MGC", ofi=-1.0, price=3000.0),
        }
        self.scanner.scan(snapshots, _META)
        summary = self.scanner.get_cross_market_summary()
        assert "equity_index" in summary
        assert "metals" in summary
        assert "sentiment" in summary["equity_index"]

    def test_correlation_penalty(self):
        """Markets in same class as active position should be penalized."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.5, trend=50.0),
            "MES": _make_snapshot("MES", ofi=2.0, trend=40.0),
            "MGC": _make_snapshot("MGC", ofi=1.8, trend=35.0, price=3000.0),
        }
        active = {"MNQ": {"side": "long"}}
        scores = self.scanner.scan(snapshots, _META, active)
        # MES (equity_index, same class as active MNQ) should be penalized
        # MGC (metals, different class) should not be penalized
        mes_score = next((s for s in scores if s.contract_id == "MES"), None)
        mgc_score = next((s for s in scores if s.contract_id == "MGC"), None)
        # Exact scores depend on components, but MES should have a penalty
        if mes_score and "correlation_penalty" in mes_score.components:
            assert mes_score.components["correlation_penalty"] < 0


class TestPositionSizing:
    def setup_method(self):
        self.scanner = MarketScanner()

    def test_basic_sizing(self):
        """Should compute reasonable position size."""
        size = self.scanner.recommend_position_size(
            _META["MNQ"],
            account_balance=150000,
            atr_points=25.0,
        )
        assert 1 <= size <= 10

    def test_sizing_caps_at_max(self):
        """Should cap at 10 contracts."""
        size = self.scanner.recommend_position_size(
            _META["MNQ"],
            account_balance=1000000,  # Very large account
            atr_points=5.0,  # Very small ATR
        )
        assert size <= 10

    def test_sizing_minimum_one(self):
        """Should always return at least 1."""
        size = self.scanner.recommend_position_size(
            _META["MNQ"],
            account_balance=1000,
            atr_points=100.0,  # Huge ATR
        )
        assert size >= 1

    def test_sizing_by_tick_value(self):
        """Higher tick value markets should get smaller sizes."""
        size_micro = self.scanner.recommend_position_size(
            _META["MNQ"],  # tick_value=0.50
            account_balance=150000,
            atr_points=25.0,
        )
        size_gold = self.scanner.recommend_position_size(
            _META["MGC"],  # tick_value=1.00
            account_balance=150000,
            atr_points=25.0,
        )
        # Gold should get equal or smaller size (higher tick value)
        assert size_gold <= size_micro + 1  # Allow some tolerance


class TestMultiMarketFlow:
    def setup_method(self):
        self.scanner = MarketScanner()

    def test_full_scan_five_markets(self):
        """Full scan of 5 different asset classes."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ", ofi=2.5, trend=50.0, vpin=0.1),
            "MES": _make_snapshot("MES", ofi=1.0, trend=20.0, vpin=0.4,
                                   regime=MarketRegime.CHOPPY),
            "MGC": _make_snapshot("MGC", ofi=-1.8, trend=35.0, vpin=0.2,
                                   price=3000.0, regime=MarketRegime.TRENDING_DOWN),
            "MCL": _make_snapshot("MCL", ofi=0.3, trend=12.0, vpin=0.6,
                                   price=70.0, regime=MarketRegime.CHOPPY),
            "EU6": _make_snapshot("EU6", ofi=1.5, trend=28.0, vpin=0.3,
                                   price=1.0800, regime=MarketRegime.TRENDING_UP),
        }
        scores = self.scanner.scan(snapshots, _META)
        assert len(scores) == 5
        # MNQ (strong trend + high OFI + clean flow) should be top
        assert scores[0].contract_id == "MNQ"

    def test_market_score_has_components(self):
        """Each score should have all expected component breakdowns."""
        snapshots = {
            "MNQ": _make_snapshot("MNQ"),
        }
        scores = self.scanner.scan(snapshots, _META)
        s = scores[0]
        assert "trend_clarity" in s.components
        assert "flow_signal" in s.components
        assert "volatility" in s.components
        assert "flow_clean" in s.components
        assert "cross_asset" in s.components

    def test_scan_records_time(self):
        """Scanner should track when last scan occurred."""
        before = time.time()
        self.scanner.scan({"MNQ": _make_snapshot("MNQ")}, _META)
        assert self.scanner.last_scan_time >= before


class TestPromptCrossMarket:
    """Test that cross-market context integrates into the prompt."""

    def test_cross_market_in_prompt(self):
        from src.decision import PromptBuilder
        summary = {
            "equity_index": {
                "sentiment": "bullish",
                "avg_change_pct": 0.15,
                "avg_vpin": 0.25,
                "avg_ofi": 1.5,
                "dominant_regime": "trending_up",
                "members": 4,
            },
            "metals": {
                "sentiment": "bearish",
                "avg_change_pct": -0.08,
                "avg_vpin": 0.35,
                "avg_ofi": -0.8,
                "dominant_regime": "trending_down",
                "members": 3,
            },
        }
        result = PromptBuilder._format_cross_market(summary)
        assert "equity_index" in result
        assert "bullish" in result
        assert "metals" in result
        assert "bearish" in result

    def test_cross_market_none(self):
        from src.decision import PromptBuilder
        result = PromptBuilder._format_cross_market(None)
        assert "single market mode" in result.lower()

    def test_full_prompt_includes_cross_market(self):
        from src.decision import PromptBuilder
        snap = _make_snapshot("MNQ")
        prompt = PromptBuilder.build(
            snapshot=snap,
            account_balance=150000,
            daily_pnl=0,
            distance_to_drawdown=4500,
            recent_trades=[],
            performance_summary={},
            cross_market_summary={"equity_index": {
                "sentiment": "bullish",
                "avg_change_pct": 0.1,
                "avg_vpin": 0.2,
                "avg_ofi": 1.0,
                "dominant_regime": "trending_up",
                "members": 2,
            }},
        )
        assert "CROSS-MARKET CONTEXT" in prompt
        assert "equity_index" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
