---
type: intelligence_node
date: 2026-03-20
status: active
participants: [Sovran, Hunter_Alpha, Lightpanda_Harness]
tags: [order_flow, volume_profile, delta_divergence, vpoc, liquidity]
---

# Intelligence Node: Order Flow & Liquidity Dynamics

**Generated via:** Autonomous Research Cycle (Phase 34)
**Constraint:** Algorithmic Setup Identification for MNQ

## 1. Volume Profile & VPOC (Volume Point of Control)
The Volume Profile plots volume explicitly on the Y-Axis (Price) rather than the X-Axis (Time). 
- **VPOC:** The specific price level where the most volume was transacted. This is the "Fair Value" agreed upon by the market.
- **High-Volume Nodes (HVNs):** Zones of consolidation. Price moves *slowly* through HVNs because liquidity absorbs momentum.
- **Low-Volume Nodes (LVNs):** Zones of imbalance. Price moves *rapidly* through LVNs because there is no liquidity to stop it (Liquidity Gaps).

**Algorithmic Synthesis (Sovran):**
Mean reversion algorithms should target the VPOC as a take-profit magnet when price is overextended (Z-Score > 2.0 or 3.0), as price naturally gravity-wells back to fair value.

## 2. Footprint Charts & Absorption
Footprint charts track the micro-interaction between aggressive market orders and passive limit orders inside the candlestick.
- **Imbalance:** Diagonal comparison of Ask volume vs. Bid volume.
- **Absorption:** When aggressive market orders smash into a price level, but the price *does not move*. This indicates a massive passive limit order wall absorbing the momentum. 

**Gambler Synthesis (Hunter Alpha):**
Absorption at the extreme of an LVN flash crash is the ultimate "exhaustion" signal. It is a high-conviction, asymmetric bet for a V-shape reversal. 

## 3. Cumulative Delta Divergence
Delta = (Aggressive Buy Market Orders) - (Aggressive Sell Market Orders).
- **Divergence Pattern:** If the MNQ makes a *Lower Low* in price, but the Cumulative Delta makes a *Higher Low* (less aggressive selling than the previous low), this is Delta Divergence.
- The underlying order flow is exhausting, and the price is moving on fumes (or stop runs).

**Live Engine Implementation:**
The `calculate_ofi_zscore` logic in Sovran already tracks rolling imbalances. A true Delta Divergence filter could upgrade the OFI logic to ensure Sovran only buys dips when sell-side aggression metrics (from Footprint/OFI) demonstrably decline.
