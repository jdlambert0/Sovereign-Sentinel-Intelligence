# Layer 1: The Guardian (Risk Engine) — Technical Specification

> **Author**: CIO Agent  
> **Date**: 2026-03-25  
> **For**: Coding Agent  
> **Depends On**: Layer 0 (`src/broker.py`) — verified and working  
> **Output Files**: `src/risk.py`, `tests/test_risk.py`

---

## 1. Overview

The Guardian is the mathematical gatekeeper. It sits between the AI brain (Layer 3) and the broker (Layer 0). Every trade request passes through it. It enforces:
- Kelly-optimal position sizing
- ATR-based stop/target distances
- Daily loss limits
- Trailing drawdown protection
- Ruin probability checks

**The Guardian CANNOT be overridden.** If it says "NO TRADE," the system does not trade.

## 2. Architecture

```
Layer 3 (Mind) → TradeRequest → Guardian.evaluate() → TradeDecision
                                      ↓ if approved
                                  BrokerClient.place_market_order()
                                      ↓ confirm
                                  Guardian.verify_bracket()
```

The Guardian does NOT import or depend on Layer 3. It receives a `TradeRequest` dataclass and returns a `TradeDecision`. It uses `BrokerClient` from Layer 0 for execution and verification.

## 3. Data Structures

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

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

@dataclass
class TradeRequest:
    """What the AI brain wants to do."""
    contract_id: str           # e.g., "CON.F.US.MNQM26"
    side: TradeSide            # LONG or SHORT
    conviction: float          # 0-100 score from Layer 3
    thesis: str                # Natural language reason for trade
    suggested_stop_points: float    # AI's suggested stop distance in points
    suggested_target_points: float  # AI's suggested target distance in points
    atr_points: float          # Current ATR in points (from Layer 2)
    tick_size: float = 0.25    # Instrument tick size
    tick_value: float = 0.50   # Dollar value per tick (MNQ default)

@dataclass
class TradeDecision:
    """What the Guardian decided."""
    approved: bool
    rejection_reason: Optional[RejectionReason] = None
    # Filled if approved:
    size: int = 0                    # Number of contracts
    stop_loss_ticks: int = 0         # SL distance in ticks
    take_profit_ticks: int = 0       # TP distance in ticks
    risk_dollars: float = 0.0        # Dollar risk on this trade
    reward_dollars: float = 0.0      # Dollar reward target
    risk_reward_ratio: float = 0.0   # Reward / Risk
    kelly_fraction: float = 0.0      # Calculated Kelly fraction
    ruin_probability: float = 0.0    # Current ruin probability
    reasoning: str = ""              # Human-readable explanation

@dataclass
class RiskConfig:
    """All risk parameters. Loaded from config/risk_config.json."""
    # Account constraints (TopStepX 150k Combine)
    max_trailing_drawdown: float = 4500.0     # Lose this from high-water mark = fail
    daily_loss_limit: float = 450.0            # Self-imposed daily soft limit
    drawdown_circuit_breaker: float = 500.0    # Stop trading when within this $ of ruin
    
    # Position sizing
    kelly_fraction_multiplier: float = 0.5     # Half-Kelly (reduces vol 50%, growth only -25%)
    max_risk_per_trade_dollars: float = 150.0  # Absolute max risk on any single trade
    min_risk_reward_ratio: float = 1.5         # Minimum reward:risk ratio
    max_position_size: int = 5                 # Max contracts at once
    
    # Stop/Target
    min_stop_atr_multiplier: float = 1.0       # Minimum stop = 1x ATR
    max_stop_atr_multiplier: float = 3.0       # Maximum stop = 3x ATR
    default_stop_atr_multiplier: float = 1.5   # Default if AI doesn't suggest
    
    # Edge assumptions (updated by Layer 4 learning loop)
    assumed_win_rate: float = 0.50              # Starting assumption: 50% win rate
    assumed_avg_win_loss_ratio: float = 1.8     # Starting assumption: win 1.8x per loss
    
    # Ruin
    max_ruin_probability: float = 0.05          # Refuse trade if ruin prob > 5%
    
    # Conviction
    min_conviction_to_trade: float = 55.0       # Minimum conviction score to approve
```

## 4. Class Design

```python
class RiskGuardian:
    """
    The mathematical gatekeeper. Every trade request must pass through this.
    
    Responsibilities:
    - Calculate Kelly-optimal position size
    - Enforce stop/target distances using ATR
    - Check daily loss limit
    - Check trailing drawdown proximity
    - Compute ruin probability
    - Execute approved trades via broker and verify brackets
    
    The Guardian CANNOT be overridden. If it says NO, the trade does not happen.
    """
    
    def __init__(self, broker: BrokerClient, config: RiskConfig | None = None):
        """
        broker: Layer 0 BrokerClient (must be connected)
        config: Risk parameters. Uses defaults if not provided.
        """

    def load_config(self, path: str) -> None:
        """Load risk config from JSON file. Merges with defaults."""

    def update_performance(self, win_rate: float, avg_win_loss_ratio: float) -> None:
        """Called by Layer 4 to update edge assumptions with real data."""

    # --- Core Risk Math ---

    def calculate_kelly_fraction(self, win_rate: float, avg_win_loss_ratio: float) -> float:
        """
        Calculate Kelly fraction: f* = (bp - q) / b
        where b = avg_win_loss_ratio, p = win_rate, q = 1 - p
        Returns the raw Kelly fraction (can be negative = no edge).
        """

    def calculate_position_size(self, kelly_f: float, risk_per_contract: float, 
                                 account_balance: float, distance_to_ruin: float) -> int:
        """
        Determine number of contracts.
        
        Steps:
        1. Apply Half-Kelly modifier: adj_f = kelly_f * kelly_fraction_multiplier
        2. Apply dynamic scaling: scale = distance_to_ruin / max_trailing_drawdown
        3. Calculate dollar risk: risk_dollars = account_balance * adj_f * scale
        4. Cap at max_risk_per_trade_dollars
        5. Contracts = floor(risk_dollars / risk_per_contract)
        6. Cap at max_position_size
        7. Minimum 1 if approved, 0 if no edge
        """

    def calculate_stop_ticks(self, atr_points: float, suggested_stop: float, 
                              tick_size: float) -> int:
        """
        Determine stop distance in ticks.
        
        - Clamp suggested_stop between min_stop_atr_multiplier * ATR and max_stop_atr_multiplier * ATR
        - Convert to ticks: ticks = int(clamped_points / tick_size)
        - Minimum 4 ticks (1 point on MNQ) for sanity
        """

    def calculate_target_ticks(self, stop_ticks: int, min_rr: float,
                                suggested_target: float, tick_size: float) -> int:
        """
        Determine target distance in ticks.
        
        - Minimum target = stop_ticks * min_risk_reward_ratio
        - If suggested_target (in ticks) > minimum, use it
        - Otherwise use minimum
        """

    def calculate_ruin_probability(self, win_rate: float, avg_win_loss_ratio: float,
                                    risk_fraction: float, distance_to_ruin: float,
                                    risk_per_trade: float) -> float:
        """
        Estimate probability of ruin.
        
        Simplified gambler's ruin formula:
        If edge exists (p > q adjusted for payoff):
            ruin = ((1-p)/p) ^ (distance_to_ruin / risk_per_trade)
        If no edge: ruin = 1.0
        
        This is a conservative estimate.
        """

    # --- Trade Evaluation ---

    async def evaluate(self, request: TradeRequest) -> TradeDecision:
        """
        The main entry point. Evaluate a trade request and return a decision.
        
        Steps:
        1. Query broker for current PnL → check daily loss limit
        2. Query broker for account balance → check drawdown circuit breaker
        3. Query broker for open positions → check no duplicate position
        4. Calculate Kelly fraction from current edge assumptions
        5. If Kelly <= 0: reject (no edge)
        6. Calculate stop/target distances
        7. Check risk:reward ratio
        8. Calculate position size
        9. Calculate ruin probability
        10. If ruin > max: reject
        11. If conviction < min: reject
        12. APPROVE with full parameters
        """

    async def execute(self, request: TradeRequest, decision: TradeDecision) -> int:
        """
        Execute an approved trade via the broker.
        
        Steps:
        1. Verify decision.approved is True (raise if not)
        2. Call broker.place_market_order with brackets
        3. Wait 1 second
        4. Call verify_bracket to confirm all legs exist
        5. Return the order ID
        
        If bracket verification fails, immediately close the position.
        """

    async def verify_bracket(self, contract_id: str, expected_side: str, 
                              expected_stop_ticks: int, expected_tp_ticks: int) -> bool:
        """
        Verify a trade has proper protection on the broker.
        
        Steps:
        1. Get open positions → confirm position exists for this contract
        2. Get open orders → find stop and limit orders for this contract
        3. Verify stop order exists with correct side and approximate price
        4. Verify limit order exists with correct side and approximate price
        5. Return True only if ALL checks pass
        """

    async def get_daily_pnl(self) -> float:
        """Get today's realized PnL from the broker."""

    async def get_distance_to_ruin(self) -> float:
        """
        Calculate how far we are from the trailing drawdown limit.
        distance = current_balance - (high_water_mark - max_trailing_drawdown)
        
        For now, use account_balance from broker since we can't query high-water mark directly.
        Conservative: assume high_water_mark = initial_balance (150000).
        """

    def get_risk_summary(self) -> dict:
        """Return current risk state for logging/Obsidian."""
```

## 5. Configuration File

Create `config/risk_config.json`:
```json
{
    "max_trailing_drawdown": 4500.0,
    "daily_loss_limit": 450.0,
    "drawdown_circuit_breaker": 500.0,
    "kelly_fraction_multiplier": 0.5,
    "max_risk_per_trade_dollars": 150.0,
    "min_risk_reward_ratio": 1.5,
    "max_position_size": 5,
    "min_stop_atr_multiplier": 1.0,
    "max_stop_atr_multiplier": 3.0,
    "default_stop_atr_multiplier": 1.5,
    "assumed_win_rate": 0.50,
    "assumed_avg_win_loss_ratio": 1.8,
    "max_ruin_probability": 0.05,
    "min_conviction_to_trade": 55.0,
    "initial_balance": 150000.0
}
```

## 6. Test Requirements

### Unit Tests (no broker needed, pure math)
- `test_kelly_fraction_with_edge` — 60% win rate, 1.5 payoff → f* should be ~0.267
- `test_kelly_fraction_no_edge` — 40% win rate, 1.0 payoff → f* should be ≤ 0
- `test_kelly_fraction_coin_flip` — 50% win rate, 1.0 payoff → f* = 0 (no edge)
- `test_kelly_fraction_strong_edge` — 55% win rate, 2.0 payoff → positive f*
- `test_position_size_basic` — verify contracts calculation with known inputs
- `test_position_size_caps_at_max` — even with huge edge, cap at max_position_size
- `test_position_size_scales_with_distance_to_ruin` — closer to ruin → smaller size
- `test_position_size_minimum_one` — if edge exists, minimum 1 contract
- `test_stop_ticks_within_atr_bounds` — verify clamping logic
- `test_stop_ticks_minimum` — never less than 4 ticks
- `test_target_ticks_minimum_rr` — target enforces min risk:reward
- `test_target_ticks_uses_suggested_if_better` — uses AI suggestion when it exceeds minimum
- `test_ruin_probability_with_edge` — low ruin when edge is strong
- `test_ruin_probability_no_edge` — ruin = 1.0 when no edge
- `test_ruin_probability_near_ruin` — high ruin when close to drawdown limit

### Integration Tests (with mocked broker)
- `test_evaluate_approves_good_trade` — clear edge, healthy account, good conviction → APPROVED
- `test_evaluate_rejects_daily_limit` — PnL already at -$400 → REJECTED (daily_loss_limit)
- `test_evaluate_rejects_drawdown_breaker` — balance near ruin → REJECTED (circuit_breaker)
- `test_evaluate_rejects_no_edge` — Kelly ≤ 0 → REJECTED (no_edge)
- `test_evaluate_rejects_low_conviction` — conviction 30 → REJECTED (min_conviction)
- `test_evaluate_rejects_duplicate_position` — already have position → REJECTED
- `test_evaluate_rejects_high_ruin` — ruin prob > 5% → REJECTED
- `test_execute_places_and_verifies` — mock place + verify → success
- `test_execute_closes_on_bad_bracket` — mock place + verify fails → position closed
- `test_config_loads_from_json` — verify config file parsing
- `test_update_performance` — verify edge assumptions change after update

## 7. Critical Rules

1. **The Guardian NEVER places an order without brackets.** Every `execute()` call includes stop_loss_ticks and take_profit_ticks.
2. **Every placed order is verified.** After placing, we query the broker to confirm all 3 legs (parent + SL + TP) exist. If verification fails, the position is immediately closed.
3. **PnL comes from the broker, not local state.** `get_daily_pnl()` calls `broker.get_realized_pnl()`.
4. **Distance to ruin is conservative.** We assume high_water_mark = initial_balance until we have tracking.
5. **Config is hot-reloadable.** `load_config()` can be called anytime to pick up new parameters from Layer 4.
6. **All math is tested with known values.** Every formula has a unit test with hand-calculated expected results.

## 8. Acceptance Criteria

- [ ] Kelly fraction calculation matches hand-computed values for 5 different edge scenarios
- [ ] Position size respects all caps (max_risk, max_position, distance_to_ruin scaling)
- [ ] Stop/target distances are ATR-normalized and clamped correctly
- [ ] Daily loss limit blocks trades when PnL approaches -$450
- [ ] Drawdown circuit breaker activates within $500 of ruin
- [ ] Ruin probability correctly identifies high-risk scenarios
- [ ] `execute()` places bracket order AND verifies it on broker
- [ ] `execute()` closes position if bracket verification fails
- [ ] Config loads from JSON and merges with defaults
- [ ] `update_performance()` modifies edge assumptions
- [ ] All unit tests pass (15+)
- [ ] All mock-broker integration tests pass (11+)
- [ ] No `except: pass` anywhere
- [ ] Every public method has a docstring
- [ ] Code is under 400 lines

---

**When done**: Update `Agents/CODING_AGENT.md` status, then CIO will review.

#specification #layer-1 #risk #guardian #coding-agent
