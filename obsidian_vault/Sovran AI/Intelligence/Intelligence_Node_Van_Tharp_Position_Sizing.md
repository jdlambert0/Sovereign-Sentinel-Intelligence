---
type: intelligence_node
date: 2026-03-20
status: active
participants: [Sovran, Hunter_Alpha, Lightpanda]
tags: [position_sizing, van_tharp, r_multiples, expectancy, algorithmic_sizing]
---

# Intelligence Node: Van Tharp Position Sizing & Expectancy Algorithms

**Generated via:** Autonomous Research Cycle (Phase 36)
**Constraint:** Algorithmic translation of Risk Variables vs Psychological variables

## 1. The Primacy of Position Sizing
According to Dr. Van K. Tharp, the *System/Setup* (e.g., waiting for OFI > 2.0) accounts for only ~10% of trading success. **Position Sizing accounts for 60% to 91% of all variability in performance.**
- *Core Principle:* It is impossible to achieve the $1,000/day objective without mathematical variance control. An algorithm with a 40% win rate can be wildly profitable with optimal sizing, and an algorithm with an 80% win rate can go bankrupt with poor sizing.

## 2. R-Multiples (Standardizing Variance)
An algorithm cannot view performance in dollar amounts ($50 vs $500), as dollars do not reflect the risk taken to acquire them. Tharp utilizes "R" (Initial Risk).
- **1R:** The distance between Entry and Hard Stop-Loss. If you enter MNQ at 20,000 and stop at 19,950, **1R = 50 points.**
- If the trade hits a Take-Profit at 20,150 (150 points), the trade yields **+3R**.
- If the trade hits the stop, the trade yields **-1R**.

**Sovran Engine Implementation:**
The `Hunter_Alpha` evaluation logic must track its history in `R-Multiples`, not PnL. The live engine must refuse any trade setup where the projected `TP` is less than `+1.5R`.

## 3. R-Expectancy (Solving for the Edge)
Expectancy is the average R-Multiple value per trade over a statistically significant sample size ($N > 30$).
> Formula: `Expectancy = Sum(All R-Multiples) / Total Number of Trades`

- If Sovran's historical trades are: `[-1R, +3R, -1R, -1R, +4R]`
- `Sum = +4R`. `Total Trades = 5.`
- `Expectancy = 4 / 5 = +0.8R per trade.`
- **Conclusion:** For every $100 put at risk, the system expects to extract $80 in profit.

## 4. Algorithmic Position Sizing Models
Van Tharp explicitly rejected "Martingale" (doubling down) and advocated for dynamic asset-independent sizing:

### A. Fixed Risk (Percent Equity) Model
- Risk exactly 1% (or X%) of Total Equity per trade.
- **Dynamic Calculation:** If Equity = $50,000, Max Risk = $500.
  - If Trade A requires a 50-point stop ($100 risk per contract on MNQ), Sovran sizes the position at **5 contracts** ($500 / $100).
  - If Trade B requires a 100-point stop ($200 risk per contract), Sovran sizes the position at **2.5 -> 2 contracts** ($500 / $200). 
  - *Result:* 1R ALWAYS equals exactly 1% of equity.

### B. Volatility Sizing (ATR-Based)
The market's baseline volatility determines the position size.
- If the 14-period Average True Range (ATR) is expanding rapidly over 30 points per 5-minute candle, the market is highly toxic.
- **Algorithmic Rule:** Sovran must divide its standard Risk Unit by a Volatility Multiplier. High Volatility = Less Contracts. Low Volatility (Compression) = More Contracts, because the breakout will be clean and one-directional.
