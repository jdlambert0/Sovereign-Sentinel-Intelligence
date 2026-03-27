---
title: Probability-Based Trading Strategy
type: trading-strategy
created: 2026-03-27T02:50:00Z
status: research-phase
priority: P0
---

# Probability-Based Trading Strategy - Scalper/Gambler Approach

## Core Philosophy

**Shift from prediction to probability:** Instead of trying to predict market direction with OFI/VPIN/regime signals, we use pure probability and risk calculations to extract profit from market noise.

**Key Insight:** With micro-futures contracts ($5-$20 tick values), we can structure bets with asymmetric risk/reward ratios similar to professional gamblers or market makers.

---

## User Requirements (2026-03-27 02:50)

1. **Don't rely on trading logic** - Current OFI/VPIN gates are too restrictive in choppy markets
2. **Use gambling and probability calculations** - Research professional gambling approaches
3. **High reward because of contract size** - Leverage $5-$20/tick to create favorable odds
4. **Formulate profitable system without prediction** - Pure probability + risk management
5. **Record everything** - Full logging of all probability calculations and outcomes
6. **Integrate into Ralph trading loop** - Make this a continuous improvement cycle

---

## Questions for User

### 1. Risk Parameters
- **Max loss per trade:** What's acceptable? (Current system uses ATR-based stops ~15-30 ticks)
- **Max trades per session:** Should we increase from current 8 to allow more probability sampling?
- **Account risk per trade:** Current is ~0.5-1% of account. Keep this or go higher for gambler approach?

### 2. Probability Approach
Which probability model resonates with you?
- **A) Market Maker Approach:** Place limit orders at bid/ask, capture spread + small edge
- **B) Mean Reversion Scalping:** Fade extremes, bet on return to mean (Bollinger Bands, Z-score)
- **C) Volatility Harvesting:** Sell volatility (like writing options), collect premium from noise
- **D) Kelly Criterion:** Bet sizing based on edge and win rate (classic gambler math)
- **E) Grid Trading:** Place buy/sell ladders at intervals, profit from oscillations

### 3. Time Horizon
- **Scalper (seconds to minutes):** Quick in/out, many small bets
- **Day trader (minutes to hours):** Hold longer, fewer bets with higher conviction
- **Hybrid:** Mix of both depending on volatility regime

### 4. Contract Focus
Which contracts should we prioritize?
- **MES/MNQ** (equity indices): High volume, tighter spreads, $5/tick
- **MGC** (gold): Lower volume, $1/tick, higher volatility
- **MCL** (crude oil): Medium volume, $1/tick, proven winner for us
- **All 6 contracts:** Diversify probability bets across instruments

### 5. Edge Definition
What's our "edge" in probability terms?
- **Statistical arbitrage:** Find pricing inefficiencies (hard without Level 2 data)
- **Volatility edge:** Market overreacts, we fade the noise
- **Time decay edge:** Markets don't trend 70% of the time, profit from chop
- **Position size edge:** Kelly criterion optimal bet sizing
- **Speed edge:** IPC responder is fast (0.6s), can we react to micro-moves?

### 6. Win Rate Targets
Current system: 7% win rate (terrible for prediction, but what about probability?)
- **High win rate, small wins:** 60-70% win rate, R:R = 1:0.5 (grind profits)
- **Low win rate, big wins:** 30-40% win rate, R:R = 1:3 (lottery ticket approach)
- **Balanced:** 50% win rate, R:R = 1:1.5 (classic gambler's edge)

### 7. Integration with Current System
- **Replace IPC responder logic?** Keep OFI/VPIN for context but use probability for entries?
- **New mode/strategy?** Add "probability mode" as Option D alongside ollama/openrouter/file_ipc?
- **Hybrid approach?** Use probability for WHEN to trade, OFI/VPIN for DIRECTION?

---

## Research Topics to Explore

1. **Kelly Criterion** - Optimal bet sizing for known edge
2. **Expectancy Formula** - (Win% × AvgWin) - (Loss% × AvgLoss)
3. **Sharpe Ratio** - Risk-adjusted returns (target > 2.0)
4. **Monte Carlo Simulation** - Test probability distributions
5. **Professional Poker Math** - Pot odds, implied odds, expected value
6. **Market Making Strategies** - Bid-ask spread capture
7. **Mean Reversion Statistics** - Bollinger Bands, ATR bands, Z-scores
8. **Volatility Cone Analysis** - Identify high/low vol regimes
9. **Order Flow Imbalance** (we have this!) - Use it differently for probability
10. **Time-of-Day Patterns** - When is noise highest? (trade then)

---

## Initial Hypothesis

**The Volatility Harvesting Gambler:**

1. **Identify high-noise periods** (current: evenings show choppy regime)
2. **Place symmetric trades** with tight stops and wide targets
3. **Use Kelly Criterion** to size positions based on:
   - Historical win rate for this contract/time/volatility level
   - Average win/loss size
   - Current account balance
4. **Capture small edges repeatedly** - many small bets, law of large numbers
5. **Track every trade** in probability terms: edge, EV, actual outcome
6. **Adapt** - if edge disappears in certain conditions, stop trading

**Example Trade:**
- MES trading at $6,544
- ATR = 1.7 points = ~7 ticks
- Place LONG entry at market
- Stop: -10 ticks ($50 risk)
- Target: +15 ticks ($75 reward)
- R:R = 1:1.5
- If historical win rate = 45% in this regime:
  - Expectancy = (0.45 × $75) - (0.55 × $50) = $33.75 - $27.50 = **+$6.25 EV**
  - Kelly suggests bet size = (edge / odds) = might suggest 0.5-1 contract

---

## Next Steps (Pending User Answers)

1. Research selected probability approach
2. Backtest on historical data (we have tick data)
3. Implement in new `probability_responder.py`
4. Add to Ralph trading loop as "Probability Mode"
5. Paper trade 20 bets, measure actual vs expected results
6. Refine based on data
7. Go live with small position sizes

---

**Status:** Awaiting user input on questions 1-7 above.
