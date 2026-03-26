# Teaching Note: Anti-Martingale for Prop Firm Survival

**Date:** 2026-03-19
**Topic:** Risk Management vs. Drawdown

## The "Anti-Martingale" Principle
In prop firm trading (like TopStepX), the #1 goal is **survival**. Most traders blow up because they double down on losers (Martingale).

**MANDATE:**
1. **Never double down on a loss.**
2. **Reduce size when the bankroll is shrinking.** (Kill the "revenge trade" urge).
3. **Scale up ONLY on winning streaks.** When the "House Money" (profits) is high, we can afford slightly larger bets (Kelly Scaling).

## Why This Matters
TopStepX uses a **Trailing Drawdown**. If you lose big once, your floor stays high. You lose room to breathe. Anti-Martingale preserves that room.

## AI Implementation
When evaluating "Confidence", factor in the current `daily_pnl`. If it is negative, the confidence threshold for the next trade must be HIGHER.
