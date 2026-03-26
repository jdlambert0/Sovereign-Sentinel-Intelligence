---
topic: adaptive_position_sizing_Kelly
title: Adaptive Position Sizing Kelly
date: 2026-03-17
timestamp: 2026-03-17T16:45:27.504866
type: research
tags: [research, learning, adaptive_position_sizing_Kelly]
---

# Adaptive Position Sizing Kelly

### **Research Summary: Adaptive Position Sizing (Kelly Criterion)**  
**Focus:** MNQ (Micro Nasdaq) Futures  

---

### **1. Key Concepts & Definitions**  
- **Kelly Criterion**: A formula to determine optimal position size based on win probability and risk/reward ratio. Maximizes long-term growth while minimizing risk of ruin.  
- **Adaptive Position Sizing**: Dynamically adjusts position size based on changing market conditions (volatility, win rate).  
- **Key Variables**:  
  - **Win Rate (W)**: % of trades that are profitable.  
  - **Loss Rate (L)**: 1 - W.  
  - **Reward-to-Risk (R)**: Avg. profit per trade / avg. loss per trade.  

---

### **2. Calculation**  
**Kelly Formula**:  
\[ f^* = \frac{W \cdot R - L}{R} \]  
Where:  
- \( f^* \) = Fraction of capital to risk per trade.  
- \( W \) = Historical win rate (e.g., 60% → 0.6).  
- \( R \) = Avg. profit / avg. loss (e.g., 2:1 → 2).  

**Example**:  
- Win rate = 55% (0.55), R = 1.5 → \( f^* = \frac{(0.55 \times 1.5) - 0.45}{1.5} = 0.216 \) (21.6% of capital).  

**Adaptive Adjustments for MNQ**:  
- Scale down \( f^* \) by 50-80% ("Half-Kelly") to reduce volatility.  
- Adjust for volatility: Reduce position size if ATR (Avg. True Range) > 1.5x 20-day average.  

---

### **3. Trading Strategies**  
**A. Trend-Following (MNQ)**  
- **Entry**: Price > 20EMA + RSI(14) > 50.  
- **Position Size**: Full-Kelly if win rate > 55%, else Half-Kelly.  
- **Exit**: Trailing stop at 2x ATR(14).  

**B. Mean Reversion (MNQ)**  
- **Entry**: Price < lower Bollinger Band (20,2) + RSI(14) < 30.  
- **Position Size**: 0.5x Kelly (higher uncertainty).  
- **Exit**: Take profit at middle Bollinger Band.  

---

### **4. Thresholds & Rules**  
- **Aggressive**: Full-Kelly if win rate > 60% and R > 2.  
- **Conservative**: Half-Kelly if win rate < 50% or R < 1.  
- **Volatility Cutoff**: Avoid new positions if MNQ ATR > 100 points (adjust for contract size).  

---

### **5. Common Pitfalls**  
- **Overestimation of Win Rate**: Use at least 100 trades for statistical significance.  
- **Ignoring Volatility**: MNQ’s high volatility can lead to oversized positions—use ATR-based caps.  
- **No Position Capping**: Never risk > 5% of capital per trade, even if Kelly suggests more.  

---

### **6. MNQ-Specific Application**  
- **Contract Size**: 1 MNQ = $2 per point.  
- **Position Sizing Example**:  
  - Account: $20,000  
  - Kelly %: 20% → $4,000 risk per trade.  
  - Stop Loss: 50 points ($100) → 40 contracts ($4,000 / $100).  
  - **Adaptive Adjustment**: Reduce to 20 contracts if ATR > 80 points.  

**Actionable Rule**:  
- Use Half-Kelly for MNQ due to volatility.  
- Enter longs only if VIX < 25 (lower volatility regime).  

---  
**Final Note**: Backtest adaptive Kelly sizing on MNQ with 2020-2023 data to validate win rates and R ratios before live deployment.

---

*Research completed: 2026-03-17T16:45:27.504866*
*This research will inform future trading decisions*
