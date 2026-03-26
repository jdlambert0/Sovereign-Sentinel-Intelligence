---
type: intelligence_node
date: 2026-03-20
status: active
participants: [Sovran, Hunter_Alpha]
tags: [mental_models, inversion, via_negativa, feynman, risk_management]
---

# Intelligence Node: Inversion & Via Negativa in Algorithmic Trading

**Generated via:** Autonomous Research Cycle (Phase 35)
**Constraint:** Algorithmic execution rule-sets vs Emotional decay

## 1. Inversion (Carl Jacobi / Charlie Munger)
*“Invert, always invert.”*
Instead of solving how to make $1,000 per day, Inversion requires solving: **How do I ensure I lose $1,000 per day?**
1. Trade without a hard stop-loss.
2. Trade highly correlated assets with max leverage exactly prior to a CPI print.
3. Average down on losing positions (Martingale).
4. Revenge trade immediately after a stop-out.

**Algorithmic Synthesis (Sovran):**
The AI engine does not seek perfect entry parameters. It seeks to construct an impenetrable fortress against the loss parameters identified above. 
- *Implementation:* The **Global Risk Vault** (`-$450` kill switch) and the **Pause-After-Loss** mechanism directly encode Inversion into the Python architecture.

## 2. Via Negativa
*Addition by Subtraction.*
In system design, adding new indicators (MACD + RSI + Bollinger Bands + VPIN + OFI) often leads to overfitting and fragility. Via Negativa dictates that robust systems are created by removing the weak parts, not adding new filters.

**Execution Rule (Sovran Meta-Analysis):**
- Do not add a "filter" to patch a failing edge; remove the edge entirely if it is structurally unsound.
- When an algorithm's win rate decays, removing parameters to simplify the logic back to naked order-flow (Footprint/Delta) is mathematically safer than adding machine learning curve-fitting.

## 3. The Feynman Technique for Algorithm Audits
If you cannot explain a trading strategy simply, you do not understand its risk profile.
"Buying when OFI > 2.0 and VPIN > 0.6" is an incomplete explanation.

**Hunter Alpha Translation:**
*"I am buying because there is a mathematically proven scarcity of aggressive sellers relative to buyers, and the volatility is compressed enough that a breakout will cause a cascade of short-covering."*
If the trade logic cannot pass the Feynman test in plain English, Sovran must default to `WAIT`.
