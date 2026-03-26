# Layer 3: The Mind (Decision Engine) — Technical Specification

> **Author**: CIO Agent  
> **Date**: 2026-03-25  
> **For**: Coding Agent  
> **Depends On**: Layer 1 (`src/risk.py`), Layer 2 (`src/market_data.py`)  
> **Output Files**: `src/decision.py`, `tests/test_decision.py`

---

## 1. Overview

The Mind analyzes market data from Layer 2 and produces trade intents that are evaluated by Layer 1 (Guardian). It is a **rule-based multi-framework decision engine** — not an LLM caller. This keeps it fast, deterministic, and testable.

The engine applies multiple analytical frameworks to the MarketSnapshot and produces a ConvictionScore. When conviction exceeds the threshold, it outputs a TradeRequest for the Guardian.

**Design philosophy**: The market speaks, the Mind listens. It does NOT impose predictions. It reads what the market IS doing and responds with the framework best suited to the current regime.

## 2. Architecture

```
MarketSnapshot (from Layer 2)
    ↓
FrameworkRouter (selects frameworks based on regime)
    ↓
┌─────────────────────────────────────────┐
│ Active Frameworks (run in parallel)     │
│  ├── MomentumFramework                  │
│  ├── MeanReversionFramework             │
│  ├── OrderFlowFramework                 │
│  └── VolatilityBreakoutFramework        │
└─────────────────────────────────────────┘
    ↓
ConvictionAggregator (weighted vote)
    ↓
TradeRequest (if conviction > threshold) → Layer 1
```

## 3. Data Structures

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

class Signal(Enum):
    STRONG_LONG = "strong_long"
    LONG = "long"
    NEUTRAL = "neutral"
    SHORT = "short"
    STRONG_SHORT = "strong_short"

@dataclass
class FrameworkVerdict:
    """Output from a single analytical framework."""
    framework_name: str       # e.g., "momentum", "mean_reversion"
    signal: Signal
    confidence: float         # 0-100 how confident this framework is
    reasoning: str            # Natural language explanation
    weight: float = 1.0      # Framework weight (adjusted by Layer 4)

@dataclass
class TradeIntent:
    """Final output of the Mind. Passed to Guardian for risk evaluation."""
    side: str                 # "long" or "short"
    conviction: float         # 0-100 aggregated conviction score
    thesis: str               # Full reasoning from all frameworks
    suggested_stop_points: float
    suggested_target_points: float
    frameworks_consulted: List[str]
    frameworks_agreeing: List[str]
    regime: str               # Current market regime
    snapshot_timestamp: float  # When this decision was made

@dataclass
class DecisionConfig:
    """Configuration for the decision engine. Loaded from JSON."""
    # Framework selection per regime
    trending_frameworks: list = field(default_factory=lambda: ["momentum", "order_flow"])
    choppy_frameworks: list = field(default_factory=lambda: ["mean_reversion", "order_flow"])
    breakout_frameworks: list = field(default_factory=lambda: ["volatility_breakout", "order_flow"])
    low_volume_frameworks: list = field(default_factory=lambda: [])  # Don't trade low volume
    unknown_frameworks: list = field(default_factory=lambda: ["order_flow"])  # Minimal in uncertain regimes
    
    # Framework weights (updated by Layer 4)
    framework_weights: dict = field(default_factory=lambda: {
        "momentum": 1.0,
        "mean_reversion": 1.0,
        "order_flow": 1.5,       # Order flow gets extra weight — it's closest to truth
        "volatility_breakout": 1.0
    })
    
    # Conviction thresholds
    min_conviction_to_trade: float = 55.0
    strong_conviction_threshold: float = 75.0
    
    # Cooldown
    min_seconds_between_trades: int = 120  # Don't overtrade — minimum 2 min between intents
    
    # Time-of-day modifiers (Eastern Time)
    # Open drive (9:30-10:30 ET): higher thresholds — fast moves, need more confirmation
    # Midday (11:00-14:00 ET): lower thresholds — choppier, mean reversion works
    # Power hour (15:00-16:00 ET): higher thresholds — unpredictable EOD flows
    time_of_day_conviction_modifier: dict = field(default_factory=lambda: {
        "open_drive": 10.0,    # Add 10 to min conviction during open
        "midday": -5.0,        # Subtract 5 during midday (easier to trade)
        "power_hour": 15.0,    # Add 15 during power hour (very cautious)
        "other": 0.0           # Regular hours outside the above
    })
```

## 4. Framework Implementations

Each framework is a class with an `analyze(snapshot: MarketSnapshot) -> FrameworkVerdict` method.

### 4.1 MomentumFramework
**When**: TRENDING_UP or TRENDING_DOWN regimes.
**Logic**:
- Check trend_strength (ADX proxy) > 25
- Check OFI Z-score aligns with trend direction (positive Z for uptrend, negative for downtrend)
- Check VPIN < 0.7 (not too toxic — avoid buying into informed selling)
- Check price is not overextended (price_change_pct < 2% from session open)

**Signal**:
- trend_strength > 35 AND OFI aligns AND VPIN < 0.6 → STRONG_LONG/SHORT
- trend_strength > 25 AND OFI aligns → LONG/SHORT
- Otherwise → NEUTRAL

**Stop**: 1.5x ATR opposite to entry
**Target**: 2.5x ATR in trend direction

### 4.2 MeanReversionFramework
**When**: CHOPPY regimes.
**Logic**:
- Check OFI Z-score > 2.0 or < -2.0 (overextended)
- Check price is far from session VWAP (use high/low of session midpoint as proxy)
- Check VPIN < 0.5 (low toxicity — informed traders aren't driving this move)
- Check spread is tight (< 2 ticks)

**Signal**:
- OFI Z > 2.5 AND VPIN < 0.4 → STRONG_SHORT (sell overextension)
- OFI Z < -2.5 AND VPIN < 0.4 → STRONG_LONG (buy underextension)
- OFI Z > 2.0 → SHORT
- OFI Z < -2.0 → LONG
- Otherwise → NEUTRAL

**Stop**: 1.0x ATR (tight — mean reversion should work quickly or not at all)
**Target**: 1.5x ATR (targeting midpoint/VPOC)

### 4.3 OrderFlowFramework
**When**: ALL regimes (universal — order flow always has information).
**Logic**:
- Check bid/ask imbalance magnitude
- Check OFI Z-score for directional pressure
- Check volume_rate (is volume elevated — more signal, or low — less signal)
- Check VPIN for informed flow detection

**Signal**:
- bid_ask_imbalance > 0.5 AND OFI Z > 1.5 AND volume_rate > 1.2 → LONG
- bid_ask_imbalance < -0.5 AND OFI Z < -1.5 AND volume_rate > 1.2 → SHORT
- VPIN > 0.8 → NEUTRAL (too much informed flow — step aside)
- Otherwise → NEUTRAL

**Stop**: 1.5x ATR
**Target**: 2.0x ATR

### 4.4 VolatilityBreakoutFramework
**When**: BREAKOUT regime.
**Logic**:
- Check ATR is expanding (current ATR > 1.5x average ATR in buffer)
- Check volume_rate > 1.5 (breakout needs volume confirmation)
- Check OFI Z-score for direction of the breakout
- Check price is near session high or low (breaking out of a range)

**Signal**:
- ATR expanding AND volume > 1.5x AND OFI Z > 1.0 AND price near session high → STRONG_LONG
- ATR expanding AND volume > 1.5x AND OFI Z < -1.0 AND price near session low → STRONG_SHORT
- Otherwise → NEUTRAL (false breakout risk)

**Stop**: 2.0x ATR (wider — breakouts are volatile)
**Target**: 3.0x ATR (bigger moves expected)

## 5. Class Design

```python
class DecisionEngine:
    """
    Multi-framework decision engine.
    
    Analyzes MarketSnapshot through multiple analytical lenses,
    aggregates their verdicts into a conviction score,
    and produces TradeIntents when conviction is high enough.
    """
    
    def __init__(self, config: DecisionConfig | None = None):
        """Initialize with optional config. Uses defaults if not provided."""
    
    def load_config(self, path: str) -> None:
        """Load decision config from JSON. Merges with defaults."""
    
    def update_weights(self, weights: dict) -> None:
        """Called by Layer 4 to update framework weights based on performance."""
    
    def analyze(self, snapshot: MarketSnapshot) -> TradeIntent | None:
        """
        The main entry point. Analyze a MarketSnapshot and return a TradeIntent
        if conviction is high enough, or None if no trade.
        
        Steps:
        1. Check cooldown (min_seconds_between_trades since last intent)
        2. Select frameworks based on current regime
        3. Run each selected framework's analyze() method
        4. Aggregate verdicts into a conviction score
        5. Apply time-of-day modifier
        6. If conviction >= threshold, build and return TradeIntent
        7. If conviction < threshold, return None
        """
    
    def _select_frameworks(self, regime: MarketRegime) -> list:
        """Select which frameworks to run based on market regime."""
    
    def _aggregate_verdicts(self, verdicts: list[FrameworkVerdict]) -> tuple[str, float, str]:
        """
        Aggregate framework verdicts into a single direction and conviction.
        
        Weighted voting:
        - Convert signals to numeric: STRONG_LONG=2, LONG=1, NEUTRAL=0, SHORT=-1, STRONG_SHORT=-2
        - Weighted sum = sum(numeric * confidence/100 * weight)
        - Direction = "long" if sum > 0 else "short"
        - Conviction = abs(weighted_sum) / max_possible_sum * 100, capped at 100
        
        Returns (direction, conviction, combined_thesis)
        """
    
    def _get_time_of_day_modifier(self) -> float:
        """Return conviction modifier based on current time (Eastern Time)."""
    
    def _aggregate_stops_targets(self, verdicts: list[FrameworkVerdict], 
                                   atr: float) -> tuple[float, float]:
        """Average the suggested stops/targets from agreeing frameworks."""


# Framework base class
class TradingFramework:
    """Base class for analytical frameworks."""
    name: str = "base"
    
    def analyze(self, snapshot: MarketSnapshot) -> FrameworkVerdict:
        """Analyze the snapshot and return a verdict."""
        raise NotImplementedError

class MomentumFramework(TradingFramework):
    name = "momentum"
    def analyze(self, snapshot: MarketSnapshot) -> FrameworkVerdict: ...

class MeanReversionFramework(TradingFramework):
    name = "mean_reversion"
    def analyze(self, snapshot: MarketSnapshot) -> FrameworkVerdict: ...

class OrderFlowFramework(TradingFramework):
    name = "order_flow"
    def analyze(self, snapshot: MarketSnapshot) -> FrameworkVerdict: ...

class VolatilityBreakoutFramework(TradingFramework):
    name = "volatility_breakout"
    def analyze(self, snapshot: MarketSnapshot) -> FrameworkVerdict: ...
```

## 6. Configuration File

Create `config/decision_config.json`:
```json
{
    "trending_frameworks": ["momentum", "order_flow"],
    "choppy_frameworks": ["mean_reversion", "order_flow"],
    "breakout_frameworks": ["volatility_breakout", "order_flow"],
    "low_volume_frameworks": [],
    "unknown_frameworks": ["order_flow"],
    "framework_weights": {
        "momentum": 1.0,
        "mean_reversion": 1.0,
        "order_flow": 1.5,
        "volatility_breakout": 1.0
    },
    "min_conviction_to_trade": 55.0,
    "strong_conviction_threshold": 75.0,
    "min_seconds_between_trades": 120,
    "time_of_day_conviction_modifier": {
        "open_drive": 10.0,
        "midday": -5.0,
        "power_hour": 15.0,
        "other": 0.0
    }
}
```

## 7. Test Requirements

### Unit Tests
- `test_momentum_strong_trend` — high trend_strength + aligned OFI + low VPIN → STRONG signal
- `test_momentum_weak_trend` — trend_strength < 25 → NEUTRAL
- `test_momentum_toxic_flow` — VPIN > 0.7 → NEUTRAL (step aside)
- `test_mean_reversion_overextended` — OFI Z > 2.5, low VPIN → STRONG counter-signal
- `test_mean_reversion_balanced` — OFI Z < 2.0 → NEUTRAL
- `test_order_flow_strong_imbalance` — high imbalance + volume → directional signal
- `test_order_flow_toxic` — VPIN > 0.8 → NEUTRAL
- `test_order_flow_low_volume` — volume_rate < 1.0 → NEUTRAL
- `test_breakout_confirmed` — ATR expanding + volume + OFI → STRONG signal
- `test_breakout_no_volume` — ATR expanding but no volume → NEUTRAL
- `test_regime_selects_correct_frameworks` — TRENDING_UP → momentum+order_flow
- `test_regime_low_volume_no_trade` — LOW_VOLUME → no frameworks → no trade
- `test_verdict_aggregation_unanimous_long` — all frameworks say LONG → high conviction
- `test_verdict_aggregation_mixed` — disagreeing frameworks → low conviction
- `test_verdict_aggregation_weighted` — order_flow (weight 1.5) dominates
- `test_cooldown_prevents_overtrade` — two analyze() calls within 120s → second returns None
- `test_time_of_day_open_drive` — conviction threshold raised by 10
- `test_time_of_day_midday` — conviction threshold lowered by 5
- `test_full_pipeline_trending_long` — complete snapshot with clear trend → TradeIntent returned
- `test_full_pipeline_no_trade` — ambiguous snapshot → None returned
- `test_config_loads_from_json` — verify JSON loading
- `test_update_weights` — verify weight changes take effect

## 8. Acceptance Criteria

- [ ] Each framework produces correct signals for its designed regime
- [ ] Framework router selects correct frameworks based on regime
- [ ] LOW_VOLUME regime produces no trade intents
- [ ] Conviction aggregation correctly weights framework verdicts
- [ ] Time-of-day modifier adjusts thresholds correctly
- [ ] Cooldown prevents overtrading (no two intents within min_seconds_between_trades)
- [ ] TradeIntent includes full thesis with reasoning from each framework
- [ ] Suggested stops and targets are ATR-based and reasonable
- [ ] Config loads from JSON and merges with defaults
- [ ] `update_weights()` modifies framework weights for Layer 4 integration
- [ ] All unit tests pass (22+)
- [ ] No `except: pass`
- [ ] Code is under 450 lines

---
#specification #layer-3 #decision #mind #coding-agent
