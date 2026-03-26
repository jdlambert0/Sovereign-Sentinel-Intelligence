---
topic: Kelly_criterion_position_sizing_futures_trading
title: Kelly Criterion Position Sizing Futures Trading
date: 2026-03-17
timestamp: 2026-03-17T16:30:42.281748
type: research
tags: [research, learning, Kelly_criterion_position_sizing_futures_trading]
---

# Kelly Criterion Position Sizing Futures Trading

### **Research Summary: Kelly Criterion for Position Sizing in Futures Trading (MNQ Focus)**  

#### **1. Key Concepts & Definitions**  
- **Kelly Criterion**: A mathematical formula to determine optimal position size based on win probability and risk/reward ratio. Maximizes long-term growth while minimizing risk of ruin.  
- **Formula**:  
  \[
  f^* = \frac{bp - q}{b}
  \]  
  - \(f^*\) = fraction of capital to bet  
  - \(b\) = net odds received (reward/risk ratio)  
  - \(p\) = probability of winning  
  - \(q = 1 - p\) = probability of losing  

- **Futures-Specific Adjustments**:  
  - Account for leverage, margin requirements, and volatility (e.g., MNQ has a tick value of $2 per 0.25-point move).  
  - Use fractional Kelly (e.g., ½ or ¼) to reduce volatility in leveraged instruments.  

---  

#### **2. Calculation & Measurement**  
**Steps for MNQ Futures**:  
1. **Estimate Win Rate (p)**: Track historical trades (e.g., 60% win rate over 100 trades).  
2. **Determine Reward/Risk (b)**: Average winner = 8 ticks ($16), average loser = 4 ticks ($8) → \(b = 16/8 = 2\).  
3. **Apply Formula**:  
   \[
   f^* = \frac{(2 \times 0.6) - 0.4}{2} = 0.4 \quad \text{(40% of capital per trade)}
   \]  
4. **Adjust for Leverage**:  
   - For MNQ, use ¼ Kelly → 10% of capital per trade.  
   - Example: $50k account → $5k risked per trade. At $8 stop-loss, trade size = $5k / $8 = 625 contracts (adjust for broker margin).  

---  

#### **3. Trading Strategies**  
- **Trend Following**: Use Kelly to scale into high-probability trends (e.g., MNQ breaking 20-day high with 55% win rate and 1:3 R/R).  
- **Mean Reversion**: Reduce Kelly fraction (e.g., 1/8) for counter-trend trades (e.g., fading overbought RSI in MNQ).  
- **Volatility Scaling**: Increase position size during low-volatility regimes (VIX < 15) and reduce during high volatility (VIX > 25).  

---  

#### **4. Thresholds & Triggers**  
- **Entry**: Signal + Kelly > 5% of capital (e.g., MACD crossover + ½ Kelly sizing).  
- **Exit**:  
  - Stop-loss: Fixed $ or % (e.g., 1% of account).  
  - Take-profit: Reward/risk ≥ 2x (e.g., 8-tick profit for 4-tick stop in MNQ).  
- **Override Conditions**:  
  - Reduce sizing if win rate drops below 50% or drawdown exceeds 10%.  

---  

#### **5. Common Pitfalls**  
- **Overestimation of Win Rate**: Backtest rigorously; avoid survivorship bias.  
- **Ignoring Leverage**: Full Kelly can lead to >50% drawdowns in futures.  
- **Discretionary Overrides**: Stick to pre-calculated sizes; emotional deviations compound risk.  

---  

#### **6. MNQ-Specific Rules**  
- **Contract Size**: 1 MNQ = $2 per 0.25 point (1 tick = $0.50).  
- **Position Sizing Example**:  
  - Account: $20k  
  - ¼ Kelly risk: 2.5% ($500)  
  - Stop-loss: 10 ticks ($5) → Trade size = $500 / $5 = 100 contracts.  
- **Volatility Adjustment**: Reduce sizing by 50% if MNQ average true range (ATR) > 1.5x 20-day median.  

---  

### **Actionable Takeaways**  
1. Use ¼ to ½ Kelly for MNQ to balance growth and drawdowns.  
2. Size entries based on stop-loss distance (e.g., 10 ticks = $5 risk per contract).  
3. Recalculate win rates monthly; adjust sizing if win rate drops below 55%.  
4. Hard-cap risk at 2% per trade (even if Kelly suggests higher).  

**Save to Knowledge Base**: [MNQ_Kelly_2023Q4]

---

*Research completed: 2026-03-17T16:30:42.281748*
*This research will inform future trading decisions*
