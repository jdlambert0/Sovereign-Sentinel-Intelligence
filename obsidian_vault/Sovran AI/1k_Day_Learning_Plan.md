# $1,000/Day Profit Learning Plan

**Date**: 2026-03-19  
**Status**: **Stage 1: THE MECHANIC** (Restored Market Data Feed)
**Goal**: Achieve consistent $1,000/day profit with Sovran trading system

---

## System Context

| Parameter | Value |
|-----------|-------|
| Instrument | MNQ (Micro Nasdaq) |
| Bankroll | ~$4,500 |
| Trading System | Sovran AI (via `--force-direct` mode) |
| Market Data | Direct WS Bridge (`market_data_bridge.py`) |
| AI Ensemble | Hunter Alpha (Gemini 2.0 + Llama 3.3) |
| Current Mode | **STRICT_DIRECT_REST** (REST Fallback for real trades) |
| Prediction Engine | MiroFish Synthesis - Inject swarm intelligence data |
| Risk Framework | **Mathematical Gambling & Probability** (Kelly Criterion / House Edge) |

---

## The Gambling & Probability Framework
Trading is a game of high-frequency betting. The system must adopt a "House Edge" mindset.

### 1. The House Edge (Alpha)
- Identify the specific microstructure imbalance that gives us >51% probability.
- If the Edge is not visible, the "House" is not open. WAIT is the baseline.

### 2. Thinking in Bets (Probabilistic Thinking)
- Every trade is a single instance of a 10,000-trade sequence.
- Individual wins/losses are noise; only Calibration and Brier Scores matter.

### 3. Advanced Position Sizing (Kelly Criterion)
- **Aggressive Kelly**: `f* = (p*b - q) / b`
- Where `p` is win probability (AI Confidence), `b` is R:R ratio, `q` is loss probability.
- Never exceed 50% of the calculated Kelly (Fractional Kelly) to protect against entropy.

---

---

## Phase 1: Data Collection

Collect the following from every trade:

| Data Point | Purpose |
|------------|---------|
| Entry/exit timestamps | Time-of-day analysis |
| Liquidity conditions | Order book depth, spread width |
| Spread gate threshold | Optimize filter sensitivity |
| Realized PnL | Track actual performance |
| Confidence scores | Hunter Alpha precision |
| Drawdown events | Risk management |
| Volatility regimes | VIX levels, ATR |
| Order flow imbalance | Execution quality |

---

## Phase 2: Analysis

Key correlations to identify:

1. **Spread gate success rate** - Which thresholds work?
2. **Liquidity sweet spots** - Best times to trade
3. **Confidence bands** - 0.7+ = scale, 0.3- = abort
4. **Drawdown triggers** - News events, exposure flips
5. **Slippage patterns** - Order book depth correlation
6. **MiroFish Swarm Signals** - Parallel world simulation of trader sentiment

---

## Phase 3: Optimization

### Dynamic Filters
- Tighten spread gate during high confidence
- Volatility-adjusted sizing (scale up VIX 12-18, ATR < 0.3%)

### Liquidity Triggers
- Minimum 5-level order book depth
- Capture rate target: >70%

### Ensemble Override
- When Gemini/Llama disagree > 0.4 confidence delta

### Profit Taking Ladder
- 25% at 1:1 R/R
- 50% at 2:1 R/R
- 25% runner

---

## Position Sizing Strategy

**Volatility-Adaptive Kelly**:

| Condition | Risk | Contracts |
|-----------|------|-----------|
| Base | 0.5% ($22.50) | 4 |
| High confidence + High liquidity + VIX 12-18 | 1.5% ($67.50) | 12 |

**Math**: 1 MNQ = $0.50/pt = $5/tick

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Daily win rate | >58% |
| Profit factor | >1.8 per 20 trades |
| Max daily drawdown | <$300 (6.7%) |
| Daily target (first) | $250 |
| Liquidity capture | >70% |
| Hunter precision | >65% on 0.7+ trades |

---

## Timeline

**6-8 Week Ramp**:

| Weeks | Focus |
|-------|-------|
| 1-2 | Baseline data (100+ trades) |
| 3-4 | Pattern ID + small tests |
| 5-6 | Volatility/liquidity filters |
| 7-8 | Scaled trials + tuning |

---

## Circuit Breakers

| Level | Limit |
|-------|-------|
| Daily stop | -$300 (6.7%) |
| Weekly stop | -$900 (20%) |

---

## Execution Notes

1. Keep LEARNING_MODE = True until 3 consecutive days at $250+
2. Use first $1K profit for aggressive growth bankroll
4. **The Loop**: Trade -> Log (Obsidian) -> Research (MiroFish/Web) -> Learn
5. **Agent Tooling**: Deploy [Lightpanda](https://github.com/lightpanda-io/browser) headless browser for agent research (10x faster, ~50MB RAM vs 300MB+ Chrome). WSL2 install failed 2026-03-19; try Windows-native or Docker.

---

*Generated via AI analysis - to be validated through live trading*
