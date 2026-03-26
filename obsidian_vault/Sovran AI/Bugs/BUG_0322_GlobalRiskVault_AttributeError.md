# BUG 0322: GlobalRiskVault Cross-Market Flatten AttributeError
**Status**: RESOLVED
**Date**: 2026-03-22
**Severity**: CRITICAL (Systemic Liability)

## 1. Symptom / Discovery
The user expressed intuitive suspicion regarding the-$500 loss limit propagating correctly across a 3x3 multi-engine MEMM grid. A deep mathematical trace of the execution topology revealed a catastrophic failure point:
If the `GlobalRiskVault` (`C:\KAI\armada\sovran_ai.py`) breached the aggregate limit, it attempted to trigger `self.emergency_flatten()`. The `GlobalRiskVault` class does not possess this method. If a critical draw-down occurred concurrently across engines, the vault would throw an `AttributeError` and crash the safety listener, leaving all concurrent trades completely naked on the market without an active limit governor.

## 2. Hypothesis
The initial architecture logic conflated `GlobalRiskVault` with a singular `AIGamblerEngine` orchestrator object, rather than treating it as an independent daemon array listener. 

## 3. Fix Deployed (The Recursive Array Flatten)
Surgically replaced the invalid `self.emergency_flatten()` block with an inter-engine iteration matrix. When the -$500 aggregated threshold algorithm breaches:
1. `self.is_halted = True` locks the heartbeat flag.
2. A recursive `for eng in self.engines:` loop iterates through all active nodes in the grid.
3. If an engine has directional exposure (`eng.current_pos != 0`), the vault invokes `await eng.suite.client.flatten_all_positions()`.
4. It calls `await eng.finalize_trade(0.0)` to force the offline state synchronization required for memory ingestion.

This topology is completely sandboxed via multiple `try/except` guardrails to guarantee that a network failure flattening Engine 1 will not prevent the algorithm from advancing to flatten Engine 2. The entire 3x3 grid is now mathematically robust against catastrophic cross-leakage.
