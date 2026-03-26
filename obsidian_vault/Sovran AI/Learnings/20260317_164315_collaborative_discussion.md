---
type: collaborative_discussion
topic: What metrics actually matter for edge detection?
date: 2026-03-17
timestamp: 2026-03-17T16:43:15.477684
participants: [Sovran, Hunter_Alpha]
---

# Collaborative Discussion: What metrics actually matter for edge detection?

## Sovran's Perspective (Analytical)
### **Metrics That Matter for Edge Detection – Sovran’s Analytical Take**  

**1. Order Flow Imbalance (OFI)**  
- **Why?** Reveals net buying/selling pressure in real-time.  
- **Key Insight:** Persistent OFI divergence from price action signals latent liquidity absorption (fading vs. following).  
- **Analytical Focus:** Z-score of OFI relative to recent distribution—extremes indicate overextension.  

**2. Volume-Weighted VPIN (Volume-Synchronized Probability of Informed Trading)**  
- **Why?** Measures toxicity of order flow—high VPIN suggests informed trading or structural breaks.  
- **Key Insight:** VPIN spikes often precede volatility expansions; track its cumulative distribution for regime shifts.  
- **Analytical Focus:** Conditional probability of VPIN > threshold given recent volatility clustering.  

**3. Microstructural Z-Scores (Price Impact, Spread Elasticity)**  
- **Why?** Normalized deviations highlight anomalies in liquidity dynamics.  
- **Key Insight:** Z-score of bid-ask spread vs. volume predicts short-term reversals (HFT crowding).  
- **Analytical Focus:** Decay rate of Z-score autocorrelation—fast reversion = noise, slow = signal.  

**4. Volume Delta & Aggressive vs. Passive Ratios**  
- **Why?** Separates speculative (aggressive) vs. structural (passive) flow.  
- **Key Insight:** High volume delta + low price change = absorption (potential reversal).  
- **Analytical Focus:** Conditional entropy of aggressive trades—lower entropy = more predictable edge.  

**5. Liquidity Elasticity (Depth vs. Execution Speed)**  
- **Why?** Measures market fragility—thin order books amplify price impact.  
- **Key Insight:** Elasticity breakdowns often precede flash crashes or squeezes.  
- **Analytical Focus:** Rate of depth replenishment after large executions (Poisson fit).  

**6. Cross-Asset Correlations (Conditional Beta)**  
- **Why?** Edges decay if isolated—macro flows distort micro signals.  
- **Key Insight:** Divergence between asset-specific OFI and cross-asset beta signals crowding.  
- **Analytical Focus:** Eigenvectors of correlation matrix during OFI extremes.  

**Hunter Alpha’s Gambler Mindset Note:**  
- **Exploit Asymmetry:** Focus on metrics with convex payoffs (e.g., VPIN tails, OFI Z > 3).  
- **Overfit Guard:** Use Bayesian updates—discard edges with posterior probability < 60%.  

**Final Take:**  
*"Edge is a function of conditional probabilities, not raw metrics. Isolate regimes where 2+ signals converge anomalously (e.g., high VPIN + OFI Z < -2). Backtest, but adapt—markets learn."*  

— **Sovran AI** *(Data-Driven Execution)*

---

## Hunter Alpha's Perspective (Gambler)
**Hunter Alpha’s Take:**  

Edge detection? Metrics are just the *smoke signals* of opportunity—you gotta know which ones to chase. Here’s the gambler’s breakdown:  

### **1. Win Rate vs. Expectancy (The Gambler’s Dilemma)**  
- **Win rate** is for ego. **Expectancy** (Avg Win * Win Rate) - (Avg Loss * Loss Rate) is for survival.  
- A 30% win rate with a 3:1 reward ratio? *Sign me up.* A 70% win rate where losers bleed you dry? *Hard pass.*  

### **2. Sharpe/Sortino (The Casino’s Cut)**  
- **Sharpe** tells you if the risk-adjusted juice is worth the squeeze.  
- **Sortino**? Even better—only penalizes *bad* volatility (the kind that breaks banks).  
- But remember: These are *rearview* metrics. Edge is about *forward* asymmetry.  

### **3. Maximum Adverse Excursion (MAE) & Maximum Favorable Excursion (MFE)**  
- **MAE** shows how much pain a trade endured before winning/losing. Tight MAE on winners? *Your edge is real.*  
- **MFE** tells you if you’re leaving money on the table. If MFE >> actual profit, your exit strategy’s weak.  

### **4. Hit Rate Under Different Regimes**  
- Edge isn’t static. Does your strategy hold up in:  
  - High vol vs. low vol?  
  - Trending vs. choppy markets?  
  - Liquidity droughts?  
- If it’s regime-dependent, *size accordingly or walk away.*  

### **5. Position Sizing Efficiency (The True Edge)**  
- **Kelly Criterion** (or fractional Kelly) tells you how much to bet when you *do* have edge.  
- Overbet = ruin. Underbet = leaving cash on the table.  

### **6. Drawdown Depth & Recovery (The Pain Check)**  
- If your strategy needs a 50% recovery after a 30% drawdown, *you’re playing Russian roulette.*  
- Gamblers respect the hole—*never dig deeper than you can climb out.*  

### **The Gambler’s Bottom Line:**  
Metrics are just *clues.* **Edge is the story they tell when pieced together.** Track ‘em, stress-test ‘em, but *never* confuse a good backtest with a license to gamble.  

**Sovran’s analytical rigor + Hunter’s risk instinct?** *Now that’s an edge.* Let’s find the mispriced bets and *attack.* 🎲

---

*Discussion conducted: 2026-03-17T16:43:15.477684*
