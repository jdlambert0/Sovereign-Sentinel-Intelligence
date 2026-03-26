# Design: GSD-Gambler Engine (Probabilistic Profit Extraction)

## Philosophy
The GSD-Gambler is a "wait-time utility" engine. When the primary Alpha Engine detects no high-conviction setups (`WAIT`), the Gambler uses Superforecasting principles to extract micro-value from market noise.

## Core Mechanics: Philip Tetlock's Superforecasting
1. **Probabilistic Calibration**: Instead of BUY/SELL, the engine outputs a % probability of a price move within $N$ ticks.
2. **Bayesian Revision**: Updates its "belief" every tick based on Order Flow Imbalance (OFI).
3. **Base Rate Filtering**: Ignores signals if the current market regime (e.g., Opening Bell) has a low historical base rate for scalps.

## Weighting Model (The "Idea Generator")
The engine computes a `GamblerConfidenceScore (GCS)` from 0.0 to 1.0:
- **OFI Z-Score (40%)**: `abs(min(z / 4.0, 1.0))` — Scales up to Z=4.
- **VPIN (30%)**: `min(vpin * 2.0, 1.0)` — Scales informed trading probability.
- **Tick Velocity (20%)**: `min(pts_per_tick / 0.5, 1.0)`.
- **Regime Bias (10%)**: `0.1` if in high-liquidity session (Opening/Closing), `0.0` otherwise.

`GCS = (Z_Score * 0.4) + (VPIN * 0.3) + (Velocity * 0.2) + (Regime * 0.1)`

## Execution Gate
- **Gamble Trigger**: `GCS > 0.65`.
- **Direction**: `SIGN(OFI_Z)`.
- **Targets**: 5 ticks profit / 8 ticks stop.

## Execution Rules
- **Entry**: Prob(Success) > 60%.
- **Sizing**: 0.25x Standard Sizing (Fractional).
- **Exit**: 4-6 tick profit targets or 8-tick hard stops.
- **Mode**: Only active when Alpha Engine is `WAIT`.

## GSD-Minion Integration
- **Step 1**: Implement `ProbabilisticIdeaGenerator` class.
- **Step 2**: Integrate into `Council` voting as a "Sub-Engine" signal.
- **Step 3**: Add `MANDATE_GAMBLE` flag to skip standard safety gates for low-size extraction.
