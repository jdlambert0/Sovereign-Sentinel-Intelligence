# Teaching Note: Kelly Criterion vs. Volatility-Adjusted Sizing

**Date:** 2026-03-19
**Topic:** Advanced Position Sizing for Prop Firms

## 1. Kelly Criterion (The Strategy Edge)
The Kelly Criterion tells us how much to bet based on our historical Win Rate and Risk/Reward ratio.
- **Formula:** % of Bankroll = WinRate - (LossRate / RR)
- **Aggression Management:** We use **Quarter-Kelly (0.25)**. If Kelly says bet 10%, we bet 2.5%. This protects against "Black Swan" events and fat-tail risks.

## 2. Volatility-Adjusted Sizing (The Market Gate)
Kelly assumes static market conditions. Volatility-Adjusted sizing (using ATR or Price Volatility) reduces size during "Crazy" markets and increases it during "Smooth" markets.

**MANDATE:**
1. **Hierarchical Sizing:**
   - First, calculate the Kelly size based on your confidence and historical stats.
   - Second, reduce that size if the current market ATR is > 2.0x the daily average.
2. **Standard Unit:** On TopStepX 150k, 1 MNQ contract is our base unit. Never exceed 4 MNQ unless confidence is > 0.9 and daily profit is already > $300.

## AI Implementation
Before outputting `size` in your JSON, ask: "Is the current market moving too fast for this many contracts?" If yes, scale down by 50%.
