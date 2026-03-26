# Research: Dynamic VPIN Bucket Scaling for Multi-Session Liquidity

## Abstract
The current VPIN implementation uses a static `vpin_basket_size` derived from an assumed `avg_daily_volume` of 200,000 contracts divided by 50 buckets (4,000 contracts/bucket). While effective for RTH (Regular Trading Hours), this static sizing causes significant "Microstructure Blinding" during low-liquidity sessions (Evening/Asian), where a single bucket can take 30-60 minutes to fill.

## Findings
1.  **Liquidity Variance**: MNQ volume during Asian session (8 PM - 3 AM ET) is often < 5% of peak RTH volume.
2.  **Latency Penalty**: A 4,000-contract basket in a 5,000 contract/hour market creates a VPIN signal with 48 minutes of latency, making it useless for reactive scalping.
3.  **Goldilocks Target**: To maintain signal fidelity, a VPIN bucket should ideally represent **1-3 minutes** of market time regardless of session phase.

## Proposed Resolution: Dynamic Basket Scaling
Implement a session-aware `vpin_basket_size` multiplier:

| Session | Est. Vol/Hr | Static Bucket Time | Target Bucket Size |
| :--- | :--- | :--- | :--- |
| **RTH** | 200,000 | 1.2 min | 4,000 (1.0x) |
| **Evening** | 25,000 | 10.0 min | 500 (0.125x) |
| **Overnight** | 10,000 | 24.0 min | 200 (0.05x) |

## Implementation Plan
1.  Modify `AIGamblerEngine.handle_trade` to check the current `get_session_phase()`.
2.  Apply a `bucket_multiplier` to `self.vpin_basket_size`.
3.  Flush small partial baskets when transitioning sessions to prevent "stale liquidity" contamination.

---
*Authored by Antigravity - Sovereign Agentic Hub*
*Status: **LOGGED FOR PHASE 3 HARDENING***
