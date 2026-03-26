import asyncio
import json
import logging
import math
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from src.broker import BrokerClient, BrokerError

class TradeSide(Enum):
    LONG = "long"
    SHORT = "short"

class RejectionReason(Enum):
    DAILY_LOSS_LIMIT = "daily_loss_limit_reached"
    DRAWDOWN_CIRCUIT_BREAKER = "drawdown_circuit_breaker"
    NO_EDGE = "kelly_fraction_zero_or_negative"
    RUIN_PROBABILITY_TOO_HIGH = "ruin_probability_exceeds_threshold"
    POSITION_ALREADY_OPEN = "position_already_open"
    MARKET_CLOSED = "outside_trading_hours"
    RISK_PER_TRADE_EXCEEDED = "risk_per_trade_exceeds_limit"
    LOW_CONVICTION = "low_conviction_score"

@dataclass
class TradeRequest:
    contract_id: str
    side: TradeSide
    conviction: float
    thesis: str
    suggested_stop_points: float
    suggested_target_points: float
    atr_points: float
    tick_size: float = 0.25
    tick_value: float = 0.50

@dataclass
class TradeDecision:
    approved: bool
    rejection_reason: Optional[RejectionReason] = None
    size: int = 0
    stop_loss_ticks: int = 0
    take_profit_ticks: int = 0
    risk_dollars: float = 0.0
    reward_dollars: float = 0.0
    risk_reward_ratio: float = 0.0
    kelly_fraction: float = 0.0
    ruin_probability: float = 0.0
    reasoning: str = ""

@dataclass
class RiskConfig:
    max_trailing_drawdown: float = 4500.0
    daily_loss_limit: float = 450.0
    drawdown_circuit_breaker: float = 500.0
    kelly_fraction_multiplier: float = 0.5
    max_risk_per_trade_dollars: float = 150.0
    min_risk_reward_ratio: float = 1.5
    max_position_size: int = 5
    min_stop_atr_multiplier: float = 1.0
    max_stop_atr_multiplier: float = 3.0
    default_stop_atr_multiplier: float = 1.5
    assumed_win_rate: float = 0.50
    assumed_avg_win_loss_ratio: float = 1.8
    max_ruin_probability: float = 0.05
    min_conviction_to_trade: float = 55.0
    initial_balance: float = 150000.0

class RiskGuardian:
    def __init__(self, broker: BrokerClient, config: RiskConfig | None = None):
        self.broker = broker
        self.config = config or RiskConfig()
        self.logger = logging.getLogger("sovran.risk")
        self.pnl_baseline: float = 0.0  # Set by Sentinel to offset prior session losses

    def load_config(self, path: str) -> None:
        with open(path, 'r') as f:
            data = json.load(f)
            for k, v in data.items():
                if hasattr(self.config, k):
                    setattr(self.config, k, v)

    def update_performance(self, win_rate: float, avg_win_loss_ratio: float) -> None:
        self.config.assumed_win_rate = win_rate
        self.config.assumed_avg_win_loss_ratio = avg_win_loss_ratio

    def calculate_kelly_fraction(self, win_rate: float, avg_win_loss_ratio: float) -> float:
        b = avg_win_loss_ratio
        p = win_rate
        q = 1 - p
        if b == 0: return 0.0
        return (b * p - q) / b

    def calculate_position_size(self, kelly_f: float, risk_per_contract: float, 
                                 account_balance: float, distance_to_ruin: float) -> int:
        if kelly_f <= 0: return 0
        adj_f = kelly_f * self.config.kelly_fraction_multiplier
        scale = max(0.0, min(1.0, distance_to_ruin / self.config.max_trailing_drawdown))
        risk_dollars = account_balance * adj_f * scale
        risk_dollars = min(risk_dollars, self.config.max_risk_per_trade_dollars)
        size = math.floor(risk_dollars / risk_per_contract) if risk_per_contract > 0 else 0
        return max(1, min(size, self.config.max_position_size)) if size >= 1 else 0

    def calculate_stop_ticks(self, atr_points: float, suggested_stop: float, 
                              tick_size: float) -> int:
        min_stop = self.config.min_stop_atr_multiplier * atr_points
        max_stop = self.config.max_stop_atr_multiplier * atr_points
        clamped = max(min_stop, min(max_stop, suggested_stop))
        ticks = int(round(clamped / tick_size))
        return max(4, ticks)

    def calculate_target_ticks(self, stop_ticks: int, min_rr: float,
                                suggested_target: float, tick_size: float) -> int:
        min_target_ticks = int(math.ceil(stop_ticks * min_rr))
        suggested_ticks = int(round(suggested_target / tick_size))
        return max(min_target_ticks, suggested_ticks)

    def calculate_ruin_probability(self, win_rate: float, avg_win_loss_ratio: float,
                                    risk_fraction: float, distance_to_ruin: float,
                                    risk_per_trade: float) -> float:
        p = win_rate
        b = avg_win_loss_ratio
        q = 1 - p
        
        if (b * p - q) <= 0: return 1.0
        if risk_per_trade <= 0: return 0.0
        
        # p_syn: probability of a 'unit' move being up
        # This accounts for payoff b != 1 while keeping the (q/p)^n form
        p_syn = (p * b) / (p * b + q)
        p_syn = max(0.5001, min(0.9999, p_syn))
        
        return ((1 - p_syn) / p_syn) ** (distance_to_ruin / risk_per_trade)

    async def get_daily_pnl(self) -> float:
        raw_pnl = await self.broker.get_realized_pnl(session_mode="session")
        return raw_pnl - self.pnl_baseline

    async def get_distance_to_ruin(self) -> float:
        balance = self.broker.account_balance
        # Conservative: high_water_mark = max(initial_balance, current_balance)
        hwm = max(self.config.initial_balance, balance) 
        return max(0.0, balance - (hwm - self.config.max_trailing_drawdown))

    async def evaluate(self, request: TradeRequest) -> TradeDecision:
        pnl = await self.get_daily_pnl()
        if pnl <= -self.config.daily_loss_limit:
            return TradeDecision(False, RejectionReason.DAILY_LOSS_LIMIT, reasoning=f"Daily loss ${pnl:.2f} exceeds limit")
        
        dist_to_ruin = await self.get_distance_to_ruin()
        if dist_to_ruin <= self.config.drawdown_circuit_breaker:
            return TradeDecision(False, RejectionReason.DRAWDOWN_CIRCUIT_BREAKER, reasoning=f"Distance to ruin ${dist_to_ruin:.2f} below breaker")

        positions = await self.broker.get_open_positions()
        if any(p["contractId"] == request.contract_id for p in positions):
            return TradeDecision(False, RejectionReason.POSITION_ALREADY_OPEN, reasoning="Position already open")

        if request.conviction < self.config.min_conviction_to_trade:
            return TradeDecision(False, RejectionReason.LOW_CONVICTION, reasoning=f"Conviction {request.conviction} < {self.config.min_conviction_to_trade}")

        kelly_f = self.calculate_kelly_fraction(self.config.assumed_win_rate, self.config.assumed_avg_win_loss_ratio)
        if kelly_f <= 0:
            return TradeDecision(False, RejectionReason.NO_EDGE, reasoning="No mathematical edge detected (Kelly <= 0)")

        stop_ticks = self.calculate_stop_ticks(request.atr_points, request.suggested_stop_points or (request.atr_points * self.config.default_stop_atr_multiplier), request.tick_size)
        target_ticks = self.calculate_target_ticks(stop_ticks, self.config.min_risk_reward_ratio, request.suggested_target_points, request.tick_size)
        
        risk_per_contract = stop_ticks * request.tick_value
        size = self.calculate_position_size(kelly_f, risk_per_contract, self.broker.account_balance, dist_to_ruin)
        if size == 0:
            return TradeDecision(False, RejectionReason.RISK_PER_TRADE_EXCEEDED, reasoning="Calculated size is 0")

        risk_dollars = size * risk_per_contract
        reward_dollars = size * target_ticks * request.tick_value
        rr = reward_dollars / risk_dollars if risk_dollars > 0 else 0
        
        ruin_prob = self.calculate_ruin_probability(self.config.assumed_win_rate, self.config.assumed_avg_win_loss_ratio, 0.0, dist_to_ruin, risk_per_contract)
        if ruin_prob > self.config.max_ruin_probability:
             return TradeDecision(False, RejectionReason.RUIN_PROBABILITY_TOO_HIGH, reasoning=f"Ruin probability {ruin_prob:.2%} > limit")

        return TradeDecision(
            approved=True, size=size, stop_loss_ticks=stop_ticks, take_profit_ticks=target_ticks,
            risk_dollars=risk_dollars, reward_dollars=reward_dollars, risk_reward_ratio=rr,
            kelly_fraction=kelly_f, ruin_probability=ruin_prob, reasoning="Risk parameters satisfied"
        )

    async def execute(self, request: TradeRequest, decision: TradeDecision) -> int:
        if not decision.approved:
            raise ValueError("Cannot execute unapproved trade")
        
        side_str = "buy" if request.side == TradeSide.LONG else "sell"
        order_id = await self.broker.place_market_order(
            contract_id=request.contract_id, side=side_str, size=decision.size,
            stop_loss_ticks=decision.stop_loss_ticks, take_profit_ticks=decision.take_profit_ticks
        )
        
        await asyncio.sleep(1.0)
        verified = await self.verify_bracket(request.contract_id, side_str, decision.stop_loss_ticks, decision.take_profit_ticks)
        if not verified:
            self.logger.error(f"Bracket verification failed for {request.contract_id}. Closing position.")
            await self.broker.close_position(request.contract_id)
            raise BrokerError(f"Bracket verification failed for {request.contract_id}")
            
        return order_id

    async def verify_bracket(self, contract_id: str, expected_side: str, 
                              expected_stop_ticks: int, expected_tp_ticks: int) -> bool:
        positions = await self.broker.get_open_positions()
        pos = next((p for p in positions if p["contractId"] == contract_id), None)
        if not pos: return False
        
        orders = await self.broker.get_open_orders()
        relevant_orders = [o for o in orders if o["contractId"] == contract_id]
        
        has_stop = any(o["type"] == 4 and o["side"] != (0 if expected_side == "buy" else 1) for o in relevant_orders)
        has_limit = any(o["type"] == 1 and o["side"] != (0 if expected_side == "buy" else 1) for o in relevant_orders)
        
        return has_stop and has_limit

    def get_risk_summary(self) -> dict:
        return {
            "config": asdict(self.config),
            "account_balance": getattr(self.broker, "account_balance", 0.0),
            "last_check": datetime.now().isoformat()
        }
