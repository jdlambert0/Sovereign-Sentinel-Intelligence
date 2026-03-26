---
type: intelligence_node
date: 2026-03-20
status: active
participants: [Sovran, Hunter_Alpha, Lightpanda_Harness]
tags: [market_microstructure, time_of_day_alpha, open_drive, power_hour, liquidity_gaps]
---

# Intelligence Node: MNQ Microstructure & Time-Of-Day Alpha

**Generated via:** Autonomous Research Cycle (Phase 34)
**Constraint:** Execution Strategy timing & Volatility mapping

## 1. Time-Of-Day Alpha Regimes
Volatility and order toxicity vary dramatically based on the clock.
- **The Open Drive (9:30 AM - 10:30 AM ET):** The period of peak institutional positioning, highest volume, and highest directional momentum. True alpha exists here, but mean reversion strategies are highly vulnerable to getting trapped in one-way institutional flow.
- **Mid-Day Chop (11:00 AM - 2:00 PM ET):** Volumes drop, algorithms ping-pong between HVNs. Mean reversion thrives here.
- **Power Hour (3:00 PM - 4:00 PM ET):** EOD rebalancing, 0DTE options hedging, and forced closures. Notorious for "chop and run" price action.

**Execution Rule (Sovran):** 
Different VPIN & OFI thresholds should apply dynamically depending on the time of day. 
- *Open Drive:* Requires massive OFI divergence to fade a trend.
- *Mid-Day:* Requires smaller OFI divergence to fade a trend due to lower institutional conviction.

## 2. Liquidity Gaps vs. Fair Value Gaps (FVG)
Because MNQ is 1/10th the size of NQ, retail liquidity creates different micro-spreads.
- **FVG:** A 3-candle imbalance where the market reprices so quickly that order books are skipped.
- Nature abhors a vacuum. These liquidity gaps become magnets for price later in the session.

**Gambler Synthesis (Hunter Alpha):**
"If the market runs up leaving an FVG at 10 AM, and begins bleeding at 2 PM, my bet is targeting the absolute center of that FVG to fill the gap." 

## 3. Order Impact & Slippage Economics
During Extended Trading Hours (ETH) or pre-market, the MNQ order book is notoriously thin.
- A 10-lot market order at 3 AM might induce 2-3 ticks of slippage due to wide spreads.
- In RTH (Regular Trading Hours), a 10-lot fills instantly with zero slippage.
- *Risk Metric:* The live engine must factor in $+/- 0.50$ per contract in slippage during non-RTH trading when calculating expected EV of a setup.
