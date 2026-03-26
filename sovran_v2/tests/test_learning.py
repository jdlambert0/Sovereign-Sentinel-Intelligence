import os
import json
import shutil
import pytest
import time
from datetime import datetime
from src.learning import LearningEngine, TradeRecord, PerformanceMatrix, LiveParameters

@pytest.fixture
def temp_paths(tmp_path):
    obsidian = tmp_path / "obsidian"
    config = tmp_path / "config"
    obsidian.mkdir()
    config.mkdir()
    return str(obsidian), str(config)

@pytest.fixture
def engine(temp_paths):
    obsidian, config = temp_paths
    return LearningEngine(obsidian_path=obsidian, config_path=config)

def create_trade(trade_id, net_pnl, conviction=60.0, frameworks=["momentum"], regime="trending_up"):
    return TradeRecord(
        trade_id=trade_id,
        contract_id="MNQJ6",
        side="long",
        entry_time=time.time(),
        exit_time=time.time() + 300,
        entry_price=18000.0,
        exit_price=18010.0 if net_pnl > 0 else 17990.0,
        size=1,
        pnl=net_pnl + 2.0,
        fees=2.0,
        net_pnl=net_pnl,
        conviction=conviction,
        thesis="Test trade",
        frameworks_used=frameworks,
        regime_at_entry=regime,
        atr_at_entry=15.0,
        vpin_at_entry=0.4,
        ofi_at_entry=1.2
    )

def test_record_trade_updates_matrix(engine):
    trade = create_trade("T1", 100.0)
    engine.record_trade(trade)
    matrix = engine.get_performance_matrix()
    assert matrix.total_trades == 1
    assert matrix.wins == 1
    assert matrix.win_rate == 1.0
    assert matrix.total_pnl == 100.0

def test_record_multiple_trades(engine):
    engine.record_trade(create_trade("T1", 100.0))
    engine.record_trade(create_trade("T2", 100.0))
    engine.record_trade(create_trade("T3", 100.0))
    engine.record_trade(create_trade("T4", -50.0))
    engine.record_trade(create_trade("T5", -50.0))
    
    matrix = engine.get_performance_matrix()
    assert matrix.total_trades == 5
    assert matrix.wins == 3
    assert matrix.losses == 2
    assert matrix.win_rate == 0.6
    assert matrix.avg_win == 100.0
    assert matrix.avg_loss == 50.0
    assert matrix.avg_win_loss_ratio == 2.0
    assert matrix.total_pnl == 200.0

def test_win_rate_calculation(engine):
    engine.record_trade(create_trade("T1", 10.0))
    engine.record_trade(create_trade("T2", -10.0))
    assert engine.get_performance_matrix().win_rate == 0.5

def test_avg_win_loss_ratio(engine):
    engine.record_trade(create_trade("T1", 100.0))
    engine.record_trade(create_trade("T2", -50.0))
    assert engine.get_performance_matrix().avg_win_loss_ratio == 2.0

def test_profit_factor(engine):
    engine.record_trade(create_trade("T1", 200.0))
    engine.record_trade(create_trade("T2", -50.0))
    engine.record_trade(create_trade("T3", -50.0))
    assert engine.get_performance_matrix().profit_factor == 2.0

def test_framework_stats(engine):
    engine.record_trade(create_trade("T1", 100.0, frameworks=["momentum", "order_flow"]))
    engine.record_trade(create_trade("T2", -50.0, frameworks=["momentum"]))
    
    stats = engine.get_performance_matrix().framework_stats
    assert stats["momentum"]["trades"] == 2
    assert stats["momentum"]["wins"] == 1
    assert stats["momentum"]["win_rate"] == 0.5
    assert stats["order_flow"]["trades"] == 1
    assert stats["order_flow"]["wins"] == 1

def test_regime_stats(engine):
    engine.record_trade(create_trade("T1", 100.0, regime="trending_up"))
    engine.record_trade(create_trade("T2", -50.0, regime="choppy"))
    
    stats = engine.get_performance_matrix().regime_stats
    assert stats["trending_up"]["trades"] == 1
    assert stats["choppy"]["trades"] == 1
    assert stats["trending_up"]["pnl"] == 100.0
    assert stats["choppy"]["pnl"] == -50.0

def test_conviction_bucket_stats(engine):
    engine.record_trade(create_trade("T1", 100.0, conviction=62.0))
    engine.record_trade(create_trade("T2", 100.0, conviction=68.0))
    engine.record_trade(create_trade("T3", -50.0, conviction=65.0))
    
    stats = engine.get_performance_matrix().conviction_stats
    assert stats["60-70"]["trades"] == 3
    assert stats["60-70"]["wins"] == 2

def test_kelly_calculation(engine):
    # win_rate 0.6, avg_win_loss 2.0
    # Kelly = (b*p - q) / b = (2*0.6 - 0.4) / 2 = (1.2 - 0.4) / 2 = 0.8 / 2 = 0.4
    engine.record_trade(create_trade("T1", 200.0))
    engine.record_trade(create_trade("T2", 200.0))
    engine.record_trade(create_trade("T3", 200.0))
    engine.record_trade(create_trade("T4", -100.0))
    engine.record_trade(create_trade("T5", -100.0))
    
    matrix = engine.get_performance_matrix()
    assert pytest.approx(matrix.kelly_optimal_fraction) == 0.4
    assert pytest.approx(matrix.recommended_kelly_fraction) == 0.2

def test_parameter_update_after_20_trades(engine):
    # Setup 19 trades with 100% win rate
    for i in range(19):
        engine.record_trade(create_trade(f"T{i}", 100.0))
    
    # Params should still be default
    params = engine.get_live_parameters()
    assert params.win_rate == 0.5
    
    # 20th trade
    engine.record_trade(create_trade("T19", 100.0))
    params = engine.get_live_parameters()
    assert params.win_rate == 1.0

def test_framework_weight_adjustment(engine):
    # Make overall win rate 0.5
    for i in range(10): engine.record_trade(create_trade(f"W{i}", 100.0, frameworks=["momentum"]))
    for i in range(10): engine.record_trade(create_trade(f"L{i}", -100.0, frameworks=["order_flow"]))
    
    # momentum win rate is 1.0, overall is 0.5. Scale = 2.0.
    # order_flow win rate is 0.0, overall is 0.5. Scale = 0.0.
    params = engine.get_live_parameters()
    assert params.framework_weights["momentum"] > 1.0
    assert params.framework_weights["order_flow"] < 1.5

def test_framework_weight_bounds(engine):
    # Force extreme performance
    for i in range(100):
        engine.record_trade(create_trade(f"W{i}", 1000.0, frameworks=["momentum"]))
        engine.record_trade(create_trade(f"L{i}", -10.0, frameworks=["mean_reversion"]))
    
    params = engine.get_live_parameters()
    assert params.framework_weights["momentum"] <= 3.0
    assert params.framework_weights["mean_reversion"] >= 0.3

def test_conviction_threshold_low_winrate(engine):
    for i in range(10):
        engine.record_trade(create_trade(f"L{i}", -100.0))
    
    params = engine.get_live_parameters()
    assert params.conviction_threshold_adjustment == 10.0

def test_conviction_threshold_high_winrate(engine):
    for i in range(10):
        engine.record_trade(create_trade(f"W{i}", 100.0))
    
    params = engine.get_live_parameters()
    assert params.conviction_threshold_adjustment == -5.0

def test_journal_entry_format(engine):
    trade = create_trade("T1", 100.0)
    engine.record_trade(trade)
    
    date_str = datetime.fromtimestamp(trade.entry_time).strftime("%Y-%m-%d")
    filename = f"{date_str}-trade-T1.md"
    filepath = os.path.join(engine.obsidian_path, "Trader Diary", filename)
    
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        content = f.read()
        assert "# Trade Journal: LONG MNQJ6" in content
        assert "$100.00" in content
        assert "Verdict: thesis_confirmed" in content

def test_live_parameters_export(engine):
    engine.record_trade(create_trade("T1", 100.0))
    path = os.path.join(engine.config_path, "live_parameters.json")
    assert os.path.exists(path)
    with open(path, "r") as f:
        data = json.load(f)
        assert "win_rate" in data

def test_load_and_save_history(engine, temp_paths):
    obsidian, config = temp_paths
    trade = create_trade("T1", 100.0)
    engine.record_trade(trade)
    
    # New engine loading from same config
    engine2 = LearningEngine(obsidian_path=obsidian, config_path=config)
    engine2.load_history()
    
    assert len(engine2.history) == 1
    assert engine2.history[0].trade_id == "T1"
    assert engine2.get_performance_matrix().total_trades == 1

def test_empty_history(engine):
    matrix = engine.get_performance_matrix()
    assert matrix.total_trades == 0
    assert matrix.win_rate == 0.0
    
    params = engine.get_live_parameters()
    assert params.win_rate == 0.5 # Default
