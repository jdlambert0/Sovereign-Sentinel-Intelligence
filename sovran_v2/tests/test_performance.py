"""Tests for Performance Attribution Engine and Problem Tracker."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.performance import PerformanceEngine, MarketPerformance, AdaptiveParameters
from src.problem_tracker import ProblemTracker, Problem


def _make_trade(
    contract_id="MNQ", side="long", pnl=50.0, conviction=80.0,
    entry_time=None, hold_seconds=300, exit_reason="bracket_closed",
    mfe=75.0, mae=-10.0, frameworks=None,
):
    return {
        "contract_id": contract_id,
        "side": side,
        "pnl": pnl,
        "conviction": conviction,
        "entry_time": entry_time or time.time() - hold_seconds,
        "exit_time": time.time(),
        "hold_seconds": hold_seconds,
        "exit_reason": exit_reason,
        "max_favorable_excursion": mfe,
        "max_adverse_excursion": mae,
        "frameworks": frameworks or ["momentum", "order_flow"],
        "thesis": "Test trade thesis",
    }


class TestPerformanceEngine:
    def test_analyze_insufficient_data(self, tmp_path):
        """Should return insufficient data message with too few trades."""
        engine = PerformanceEngine(state_dir=str(tmp_path))
        params = engine.analyze(min_trades=5)
        assert len(params.notes) > 0
        assert "Insufficient" in params.notes[0]

    def test_analyze_by_market(self, tmp_path):
        """Should compute per-market performance metrics."""
        # Write trade history
        trades = [
            _make_trade("MNQ", pnl=100),
            _make_trade("MNQ", pnl=-30),
            _make_trade("MNQ", pnl=50),
            _make_trade("MES", pnl=-20),
            _make_trade("MES", pnl=80),
        ]
        path = tmp_path / "trade_history.json"
        with open(path, "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        params = engine.analyze(min_trades=3)

        assert "MNQ" in engine.market_performances
        mp = engine.market_performances["MNQ"]
        assert mp.total_trades == 3
        assert mp.wins == 2
        assert mp.total_pnl == 120.0

    def test_win_rate_calculation(self, tmp_path):
        """Should compute correct win rate."""
        trades = [_make_trade(pnl=p) for p in [50, -10, 30, -5, 20]]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        engine.analyze(min_trades=3)
        mp = engine.market_performances["MNQ"]
        assert mp.win_rate == pytest.approx(0.6)

    def test_profit_factor(self, tmp_path):
        """Should compute correct profit factor."""
        trades = [_make_trade(pnl=p) for p in [100, -50, 80, -20]]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        engine.analyze(min_trades=3)
        mp = engine.market_performances["MNQ"]
        assert mp.profit_factor == pytest.approx(180.0 / 70.0, rel=0.01)

    def test_edge_score(self, tmp_path):
        """High-performing market should have high edge score."""
        trades = [_make_trade(pnl=p) for p in [50, 30, 60, 40, 70, -10, 55]]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        engine.analyze(min_trades=3)
        mp = engine.market_performances["MNQ"]
        assert mp.edge_score > 50

    def test_preferred_markets(self, tmp_path):
        """Markets with high edge should be in preferred list."""
        trades = [
            _make_trade("MNQ", pnl=50),
            _make_trade("MNQ", pnl=40),
            _make_trade("MNQ", pnl=60),
            _make_trade("MES", pnl=-20),
            _make_trade("MES", pnl=-30),
            _make_trade("MES", pnl=5),
            _make_trade("MES", pnl=-15),
            _make_trade("MES", pnl=-10),
        ]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        params = engine.analyze(min_trades=3)
        assert "MNQ" in params.preferred_markets

    def test_exit_analysis(self, tmp_path):
        """Should analyze performance by exit reason."""
        trades = [
            _make_trade(pnl=50, exit_reason="bracket_closed"),
            _make_trade(pnl=-30, exit_reason="vpin_toxic"),
            _make_trade(pnl=-20, exit_reason="vpin_toxic"),
            _make_trade(pnl=40, exit_reason="bracket_closed"),
            _make_trade(pnl=-10, exit_reason="ofi_flip"),
        ]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        engine.analyze(min_trades=3)
        assert "bracket_closed" in engine.exit_analyses
        assert engine.exit_analyses["bracket_closed"].avg_pnl > 0

    def test_risk_factor_hot_streak(self, tmp_path):
        """Hot streak should increase risk factor."""
        trades = [_make_trade(pnl=p) for p in
                  [50, 30, 60, 40, 70, 55, 45, 35, 65, 50,
                   80, 30, 60, 40, 55, 45, 35, 65, 50, 70]]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        params = engine.analyze(min_trades=3)
        assert params.risk_factor >= 1.0

    def test_saves_analysis(self, tmp_path):
        """Should save analysis results to JSON."""
        trades = [_make_trade(pnl=p) for p in [50, -10, 30, -5, 20]]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        engine.analyze(min_trades=3)

        assert (tmp_path / "performance_analysis.json").exists()
        with open(tmp_path / "performance_analysis.json") as f:
            data = json.load(f)
        assert "markets" in data
        assert "adaptive_parameters" in data

    def test_report_generation(self, tmp_path):
        """Should generate a readable text report."""
        trades = [_make_trade(pnl=p) for p in [50, -10, 30, -5, 20]]
        with open(tmp_path / "trade_history.json", "w") as f:
            json.dump(trades, f)

        engine = PerformanceEngine(state_dir=str(tmp_path))
        engine.analyze(min_trades=3)
        report = engine.get_report()
        assert "Performance Report" in report
        assert "MNQ" in report


class TestProblemTracker:
    def test_track_new_problem(self, tmp_path):
        """Should track a new problem."""
        tracker = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        p = tracker.track("data_quality", "warning", "Stale MNQ data", "No ticks for 30s")
        assert p.id.startswith("P")
        assert p.category == "data_quality"
        assert p.recurrence_count == 1

    def test_track_duplicate_increments(self, tmp_path):
        """Same problem should increment recurrence count."""
        tracker = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        p1 = tracker.track("data_quality", "warning", "Stale MNQ data", "desc")
        p2 = tracker.track("data_quality", "warning", "Stale MNQ data", "desc again")
        assert p2.recurrence_count == 2
        assert p1.id == p2.id

    def test_resolve_problem(self, tmp_path):
        """Should mark problem as resolved."""
        tracker = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        p = tracker.track("execution", "critical", "Order failed", "Timeout")
        tracker.resolve(p.id, "Fixed timeout handling")
        assert len(tracker.get_active_problems()) == 0

    def test_persistence(self, tmp_path):
        """Problems should survive restart."""
        tracker1 = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        tracker1.track("data_quality", "warning", "Test", "desc")

        tracker2 = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        assert len(tracker2.get_active_problems()) == 1

    def test_critical_filter(self, tmp_path):
        """Should filter critical problems."""
        tracker = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        tracker.track("data_quality", "warning", "Minor issue", "desc")
        tracker.track("execution", "critical", "Major issue", "desc")
        assert len(tracker.get_critical_problems()) == 1

    def test_obsidian_dashboard(self, tmp_path):
        """Should write Obsidian-compatible markdown."""
        tracker = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        tracker.track("data_quality", "warning", "Test Problem", "Description here")
        path = tracker.write_obsidian_dashboard()
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Problem Tracker" in content
        assert "Test Problem" in content
        assert "data_quality" in content

    def test_obsidian_daily_log(self, tmp_path):
        """Should write a daily log entry."""
        tracker = ProblemTracker(state_dir=str(tmp_path), obsidian_dir=str(tmp_path / "obs"))
        tracker.track("ai_quality", "info", "Low conviction", "AI returned 45 conviction")
        path = tracker.write_obsidian_daily_log(perf_summary="5 trades, 3 wins")
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Daily Log" in content
        assert "5 trades" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
