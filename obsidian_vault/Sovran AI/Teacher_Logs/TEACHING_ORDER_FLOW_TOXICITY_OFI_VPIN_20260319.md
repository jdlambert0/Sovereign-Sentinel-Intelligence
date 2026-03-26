# Teaching Note: Order Flow Toxicity (OFI vs. VPIN)

**Date:** 2026-03-19
**Topic:** Market Microstructure & Toxic Flow

## 1. Order Flow Imbalance (OFI) - The Lead Indicator
OFI measures the net aggression in the order book. 
- **High Positive OFI:** Aggressive buyers are sweeping the book. This is often "dumb money" chasing momentum or "informed money" entering early.
- **High Negative OFI:** Aggressive sellers are dominant.

## 2. VPIN (Volume-Synchronized Probability of Informed Trading)
VPIN measures **Toxicity**. It tells us if the flow is "Informed" (dangerous to trade against) or "Noise" (safe to provide liquidity to).

**MANDATE:**
1. **The Toxicity Trap:** When VPIN is > 0.70, the market is "Toxic". Spreads will widen, and price discovery will be violent. 
   - **ACTION:** Avoid entering new trades during extreme VPIN spikes, even if OFI is high. High OFI + High VPIN = A potential Flash Crash or violent reversal.
2. **The Liquidity Window:** When VPIN is low (< 0.40) and OFI is consistent, the market is "Liquid and Predictable".
   - **ACTION:** This is where our highest confidence scalps occur.

## AI Implementation
Cross-reference VPIN and OFI. If they disagree (e.g., negative OFI but rising price with high VPIN), identify this as "Divergence" in your reasoning.
