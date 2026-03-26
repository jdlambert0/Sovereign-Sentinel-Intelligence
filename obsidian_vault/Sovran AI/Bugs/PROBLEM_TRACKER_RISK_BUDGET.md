# PROBLEM TRACKER: Risk Budget Starvation (The Piggy Bank Problem)
**Status**: IDENTIFIED (Awaiting Structural Fix)
**Date**: 2026-03-22
**Severity**: HIGH (Asymmetric Capital Bleed)

## 1. Description of the Vulnerability
The user correctly identified a catastrophic vulnerability in the 3x3 MEMM (Multi-Engine Multi-Market) execution array. The `GlobalRiskVault` assigns a singular, universal limit of -$450.0 to all 9 concurrent engine processes. 

Because the engines have radically different execution architectures (Gambler is hyper-aggressive and fast; Sovereign Alpha is highly selective and slow), all engines are physically siphoning from the exact same "Piggy Bank." 

If Gambler_MNQ enters a rapid drawdown chop and loses -$450 in the first 30 minutes of the market open, it drags the `aggregate_pnl` to the floor limit. The `GlobalRiskVault` identifies the breach, triggers `is_halted = True`, and flattens the ENTIRE grid. 

## 2. The Consequence (Capital Starvation)
The highly sophisticated "Sensible" engines (Sovereign Alpha) and the hedging engines (Warwick) are abruptly deactivated for the entire day **without ever taking a single trade**. Their unique mathematical edges and recovery logic are completely choked out by the undisciplined bleed of a single aggressive node.

## 3. Mathematical Proof
A custom offline integration test (`C:\KAI\armada\test_risk_budget_leakage.py`) simulated this exact topology. The results proved that an engine operating at 6x speed consumed $450 of risk capital in under 5 simulated seconds, halting the Vault. The slow, sensible engine recorded exactly `0` trades.

## 4. Proposed Architectural Solutions (For Future Phase)
Do not implement these changes until the user approves the roadmap.

**Option A: Fractional Ring-Fenced Budgets (The Sieve)**
The vault allocates individual -$50 daily limits to each of the 9 engines (`9 * 50 = 450`). If Gambler_MNQ hits -$50, Gambler is halted, but Sovereign and Warwick remain online with their unharmed allocations.

**Option B: The Dynamic Allocation Matrix**
Engines pool from the -$450, but feature hard-locks. Gambler defaults to a max -$150 pull. Sovereign (higher win rate) is permitted a -$300 pull. No single engine can bleed the whole $450 alone.

**Option C: The Conviction Throttle**
If an engine sustains 3 consecutive losses, its loop is forcefully deactivated for 60 minutes, intentionally shifting capital velocity to the adjacent engines that haven't hit the chop bucket yet.

## 5. Next Actions
Awaiting user confirmation to select an architectural pathway (A, B, or C) from the tracker before executing structural changes to `GlobalRiskVault` and `AIGamblerEngine`.
