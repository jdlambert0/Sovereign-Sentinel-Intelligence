---
type: intelligence_node
date: 2026-03-20
status: active
participants: [Sovran, Hunter_Alpha, Lightpanda_Harness]
tags: [sentiment, vix_term_structure, cot_reports, contango, backwardation]
---

# Intelligence Node: Sentiment Extremes & Correlator Modeling

**Generated via:** Autonomous Research Cycle (Phase 34)
**Constraint:** Macro Context for Micro Execution

## 1. VIX Term Structure: Overriding the Intraday Noise
The VIX (Volatility Index) curve maps the expected future volatility across 30, 60, 90 days.
- **Contango (Normal State):** 80%+ of the time. Short-term VIX is cheaper than Long-term VIX. The market expects volatility to slowly expand or remain stable. A steep contango signals immense complacency.
- **Backwardation (Panic State):** Short-term VIX spikes higher than Long-term VIX. The market demands immediate insurance. This represents absolute panic.

**Synthesis (Hunter Alpha):**
Historically, VIX backwardation indicates peak fear. Buying equities (Long MNQ) during deep backwardation when retail is capitulating often acts as a generational wealth generator. It is the ultimate contrarian signal.

## 2. COT (Commitment of Traders) Extremes
The CFTC releases the COT report weekly, detailing where Hedgers (Commercial) and Speculators (Non-Commercial/Hedge Funds) are positioned.
- **The Setup:** Hedge funds are trend-followers. When speculators reach historic, multi-year net-long or net-short extremes, they are typically "offside" and trapped.
- **The Execution:** If Speculators are at historic net-shorts, and the market begins to grind up, the resulting "Short Squeeze" provides immense upside alpha. 

**Execution Rule (Sovran Meta-Analysis):**
While the live engine trades on millisecond tick data, it must ingest *Context Providers*. If the weekly Context reads "VIX Backwardation + Extreme Net Short COT", the engine's long-side scaling parameters should be explicitly looser than its short-side parameters.

## 3. Component Divergence (The NDX Trifecta)
The MNQ tracks the Nasdaq-100, which is heavily weighted by a few mega-caps (AAPL, MSFT, NVDA).
- If the MNQ is breaking to a new high, but NVDA and AAPL are simultaneously breaking to new intraday *lows*, the index is being propped up by low-weight garbage.
- **Algorithmic Signal:** This represents a major internal divergence. The rally is toxic. Sovran must aggressively short the inevitable index reconciliation.
