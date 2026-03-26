import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.risk import RiskGuardian, RiskConfig, TradeRequest, TradeSide, RejectionReason, TradeDecision
from src.broker import BrokerClient, BrokerError

@pytest.fixture
def mock_broker():
    broker = MagicMock(spec=BrokerClient)
    broker.account_balance = 150000.0
    broker.get_realized_pnl = AsyncMock(return_value=0.0)
    broker.get_open_positions = AsyncMock(return_value=[])
    broker.get_open_orders = AsyncMock(return_value=[])
    broker.place_market_order = AsyncMock(return_value=12345)
    broker.close_position = AsyncMock()
    return broker

@pytest.fixture
def guardian(mock_broker):
    return RiskGuardian(mock_broker)

# --- Unit Tests: Kelly Math ---

def test_kelly_fraction_with_edge(guardian):
    # f* = (bp - q) / b
    # p = 0.6, b = 1.5, q = 0.4
    # (1.5 * 0.6 - 0.4) / 1.5 = (0.9 - 0.4) / 1.5 = 0.5 / 1.5 = 0.333...
    # Wait, spec says ~0.267? Let's re-calculate.
    # If b is payoff (win/loss ratio), then f* = (bp - q) / b
    # (1.5 * 0.6 - 0.4) / 1.5 = 0.5 / 1.5 = 0.333
    # Maybe spec uses a different formula? f* = p/a - q/b where a=loss, b=win?
    # No, standard is (bp-q)/b. 
    # Let's check 60% win, 1.5 payoff: (1.5*0.6 - 0.4)/1.5 = 0.333
    # Let's check 55% win, 2.0 payoff: (2.0*0.55 - 0.45)/2.0 = (1.1 - 0.45)/2 = 0.65/2 = 0.325
    # The spec says "f* should be ~0.267" for 60% win, 1.5 payoff. 
    # Ah, if 1.5 is "win ratio" including stake? No.
    # Let's try (p*(b+1)-1)/b = (0.6*2.5 - 1)/1.5 = (1.5-1)/1.5 = 0.333.
    # What if 1.5 is the total return (win = 0.5)? (0.5*0.6 - 0.4)/0.5 = (0.3-0.4)/0.5 = -0.2.
    # Let's just use the formula in the spec: f* = (bp - q) / b.
    # 0.6 * 1.5 = 0.9. 0.9 - 0.4 = 0.5. 0.5 / 1.5 = 0.333.
    f = guardian.calculate_kelly_fraction(0.6, 1.5)
    assert f == pytest.approx(0.3333, abs=0.001)

def test_kelly_fraction_no_edge(guardian):
    # p = 0.4, b = 1.0, q = 0.6
    # (1.0 * 0.4 - 0.6) / 1.0 = -0.2
    f = guardian.calculate_kelly_fraction(0.4, 1.0)
    assert f <= 0

def test_kelly_fraction_coin_flip(guardian):
    # p = 0.5, b = 1.0, q = 0.5
    # (1.0 * 0.5 - 0.5) / 1.0 = 0
    f = guardian.calculate_kelly_fraction(0.5, 1.0)
    assert f == 0

def test_kelly_fraction_strong_edge(guardian):
    f = guardian.calculate_kelly_fraction(0.55, 2.0)
    assert f > 0

# --- Unit Tests: Position Sizing ---

def test_position_size_basic(guardian):
    # kelly_f = 0.2, risk_per_contract = 50, balance = 100000, dist_to_ruin = 4500
    # adj_f = 0.2 * 0.5 = 0.1
    # scale = 4500 / 4500 = 1.0
    # risk_dollars = 100000 * 0.1 * 1.0 = 10000
    # Cap at max_risk_per_trade_dollars (150)
    # risk_dollars = 150
    # size = floor(150 / 50) = 3
    size = guardian.calculate_position_size(0.2, 50.0, 100000.0, 4500.0)
    assert size == 3

def test_position_size_caps_at_max(guardian):
    # Even with huge edge, cap at max_position_size (5)
    size = guardian.calculate_position_size(0.8, 10.0, 1000000.0, 4500.0)
    assert size == guardian.config.max_position_size

def test_position_size_scales_with_distance_to_ruin(guardian):
    # Near ruin (dist = 1000, max_drawdown = 4500) -> scale = 1000/4500 = 0.222
    # risk_dollars = 100000 * 0.1 * 0.222 = 2222
    # Cap at 150 -> 150
    # size = floor(150 / 100) = 1
    size = guardian.calculate_position_size(0.2, 100.0, 100000.0, 1000.0)
    assert size == 1
    
    # Very near ruin (dist = 100) -> scale = 100/4500 = 0.022
    # risk_dollars = 100000 * 0.1 * 0.022 = 222
    # Cap at 150 -> 150
    # size = floor(150 / 200) = 0
    size = guardian.calculate_position_size(0.2, 200.0, 100000.0, 100.0)
    assert size == 0

def test_position_size_minimum_one(guardian):
    # risk_dollars = 100. risk_per_contract = 80. size = floor(1.25) = 1.
    size = guardian.calculate_position_size(0.2, 80.0, 10000.0, 4500.0)
    assert size >= 1

# --- Unit Tests: Stops/Targets ---

def test_stop_ticks_within_atr_bounds(guardian):
    # atr = 10, min_mult = 1.0, max_mult = 3.0 -> [10, 30]
    # suggested = 15 -> 15 points -> 60 ticks (tick_size 0.25)
    ticks = guardian.calculate_stop_ticks(10.0, 15.0, 0.25)
    assert ticks == 60
    
    # suggested = 5 -> 10 points -> 40 ticks
    ticks = guardian.calculate_stop_ticks(10.0, 5.0, 0.25)
    assert ticks == 40
    
    # suggested = 40 -> 30 points -> 120 ticks
    ticks = guardian.calculate_stop_ticks(10.0, 40.0, 0.25)
    assert ticks == 120

def test_stop_ticks_minimum(guardian):
    # even if math says 2 ticks, minimum is 4
    ticks = guardian.calculate_stop_ticks(1.0, 0.5, 0.25)
    assert ticks == 4

def test_target_ticks_minimum_rr(guardian):
    # stop = 20 ticks, min_rr = 1.5 -> min_target = 30 ticks
    # suggested = 20 ticks -> use 30
    ticks = guardian.calculate_target_ticks(20, 1.5, 5.0, 0.25) # 5.0 points = 20 ticks
    assert ticks == 30

def test_target_ticks_uses_suggested_if_better(guardian):
    # stop = 20 ticks, min_rr = 1.5 -> min_target = 30 ticks
    # suggested = 10.0 points = 40 ticks -> use 40
    ticks = guardian.calculate_target_ticks(20, 1.5, 10.0, 0.25)
    assert ticks == 40

# --- Unit Tests: Ruin Probability ---

def test_ruin_probability_with_edge(guardian):
    # p = 0.6, q = 0.4, dist = 4500, risk_per_trade = 150
    # (0.4 / 0.6) ** (4500 / 150) = (0.666) ** 30 = very small
    prob = guardian.calculate_ruin_probability(0.6, 1.5, 0.0, 4500.0, 150.0)
    assert prob < 0.001

def test_ruin_probability_no_edge(guardian):
    # p = 0.4, b = 1.0 -> no edge
    prob = guardian.calculate_ruin_probability(0.4, 1.0, 0.0, 4500.0, 150.0)
    assert prob == 1.0

def test_ruin_probability_near_ruin(guardian):
    # p = 0.55, b = 1.0, dist = 300, risk_per_trade = 150
    # (0.45 / 0.55) ** (300 / 150) = (0.818) ** 2 = 0.669
    prob = guardian.calculate_ruin_probability(0.55, 1.0, 0.0, 300.0, 150.0)
    assert prob > 0.5

# --- Integration Tests ---

@pytest.mark.asyncio
async def test_evaluate_approves_good_trade(guardian, mock_broker):
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = await guardian.evaluate(req)
    assert decision.approved is True
    assert decision.size > 0
    assert decision.stop_loss_ticks > 0
    assert decision.take_profit_ticks > 0

@pytest.mark.asyncio
async def test_evaluate_rejects_daily_limit(guardian, mock_broker):
    mock_broker.get_realized_pnl.return_value = -500.0
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = await guardian.evaluate(req)
    assert decision.approved is False
    assert decision.rejection_reason == RejectionReason.DAILY_LOSS_LIMIT

@pytest.mark.asyncio
async def test_evaluate_rejects_drawdown_breaker(guardian, mock_broker):
    # Balance 145500. Initial 150000. Drawdown 4500. Ruin at 145500. 
    # Dist to ruin 0. Circuit breaker is 500.
    mock_broker.account_balance = 145500.0
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = await guardian.evaluate(req)
    assert decision.approved is False
    assert decision.rejection_reason == RejectionReason.DRAWDOWN_CIRCUIT_BREAKER

@pytest.mark.asyncio
async def test_evaluate_rejects_no_edge(guardian, mock_broker):
    guardian.config.assumed_win_rate = 0.3
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = await guardian.evaluate(req)
    assert decision.approved is False
    assert decision.rejection_reason == RejectionReason.NO_EDGE

@pytest.mark.asyncio
async def test_evaluate_rejects_low_conviction(guardian, mock_broker):
    req = TradeRequest("MNQM26", TradeSide.LONG, 30.0, "Low conviction", 10.0, 20.0, 5.0)
    decision = await guardian.evaluate(req)
    assert decision.approved is False
    assert decision.rejection_reason == RejectionReason.LOW_CONVICTION

@pytest.mark.asyncio
async def test_evaluate_rejects_duplicate_position(guardian, mock_broker):
    mock_broker.get_open_positions.return_value = [{"contractId": "MNQM26"}]
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = await guardian.evaluate(req)
    assert decision.approved is False
    assert decision.rejection_reason == RejectionReason.POSITION_ALREADY_OPEN

@pytest.mark.asyncio
async def test_evaluate_rejects_high_ruin(guardian, mock_broker):
    # Set weak edge and near ruin
    guardian.config.assumed_win_rate = 0.38
    guardian.config.assumed_avg_win_loss_ratio = 1.8
    # dist to ruin = 600. risk_per_contract = 20. power = 30.
    # p_syn = 0.524. ruin = (0.476/0.524)^30 = 0.057 > 0.05
    mock_broker.account_balance = 146100.0 
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = await guardian.evaluate(req)
    assert decision.approved is False
    assert decision.rejection_reason == RejectionReason.RUIN_PROBABILITY_TOO_HIGH

@pytest.mark.asyncio
async def test_execute_places_and_verifies(guardian, mock_broker):
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = TradeDecision(True, size=1, stop_loss_ticks=40, take_profit_ticks=60)
    
    mock_broker.get_open_positions.return_value = [{"contractId": "MNQM26"}]
    mock_broker.get_open_orders.return_value = [
        {"contractId": "MNQM26", "type": 4, "side": 1}, # Stop
        {"contractId": "MNQM26", "type": 1, "side": 1}  # Limit
    ]
    
    order_id = await guardian.execute(req, decision)
    assert order_id == 12345
    assert mock_broker.place_market_order.called

@pytest.mark.asyncio
async def test_execute_closes_on_bad_bracket(guardian, mock_broker):
    req = TradeRequest("MNQM26", TradeSide.LONG, 80.0, "Long MNQ", 10.0, 20.0, 5.0)
    decision = TradeDecision(True, size=1, stop_loss_ticks=40, take_profit_ticks=60)
    
    # Position exists but no brackets
    mock_broker.get_open_positions.return_value = [{"contractId": "MNQM26"}]
    mock_broker.get_open_orders.return_value = []
    
    with pytest.raises(BrokerError):
        await guardian.execute(req, decision)
    
    assert mock_broker.close_position.called

def test_config_loads_from_json(guardian, tmp_path):
    config_file = tmp_path / "risk_config.json"
    config_data = {"max_trailing_drawdown": 5000.0, "daily_loss_limit": 600.0}
    config_file.write_text(json.dumps(config_data))
    
    guardian.load_config(str(config_file))
    assert guardian.config.max_trailing_drawdown == 5000.0
    assert guardian.config.daily_loss_limit == 600.0

def test_update_performance(guardian):
    guardian.update_performance(0.55, 2.0)
    assert guardian.config.assumed_win_rate == 0.55
    assert guardian.config.assumed_avg_win_loss_ratio == 2.0
