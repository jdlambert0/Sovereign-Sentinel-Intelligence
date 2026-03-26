# Sovereign Blueprint 4: Multi-Symbol Orchestration & Global Safety

This blueprint outlines the shift from a single-symbol "Mechanic" phase to a multi-symbol "Hunter" phase with hardened institutional risk controls, optimized for the TopStepX **single-connection** SignalR architecture.

## 1. Goal Description
The objective is to scale the Sovran system cross-market (MNQ, MES, M2K) to achieve the $1,000/day profit target via symbol diversification, while implementing a unified "Global Risk Vault" that kills all trading if the aggregate loss exceeds $450.

## 2. Technical Invariants (Research Findings)
- **SignalR Orchestration**: TopStepX enforces a single WebSocket connection per account. To scale across symbols, we must use a **Singleton Hub** pattern where one manager process handles the SignalR session and dispatches updates to symbol-specific "Brain" threads/tasks.
- **2026 EOD Trailing Drawdown**: Daily high minus $4,500. The system BETS based on the "Headroom" to this floor.
- **Global Kill-Switch**: A deterministic `$450` daily loss limit (mandate) that bypasses LLM reasoning and flattens all symbols instantly.

## 3. Proposed Changes

### Component: Multi-Symbol Manager (`sovran_ai.py`)
Status: REFACTORED (March 19)
- Already supports `--symbols MNQ,MES,M2K` in a single concurrent process.
- Logic: Each symbol runs an `AIGamblerEngine` in its own async task, sharing a single `TradingSuite` connection.

### Component: Global Safety Governor (`sovran_ai.py`)
- [NEW] Implement `GlobalRiskVault` class.
- [NEW] Total PnL monitor across all `AIGamblerEngine` instances.
- [NEW] `kill_all()` method to send `close_all_positions()` to TopStepX upon hitting -$450.

### Component: Manual Override (`flatten_all_positions.py`)
- [NEW] Standalone script to force-flatten all active positions and orders via REST (emergency use).

## 4. Verification Plan
- **Stress Test**: Run dummy symbols (sim/paper) alongside MNQ to verify SignalR message routing.
- **Kill-Switch Test**: Manually lower the risk cap to $5 and take a losing trade to verify all symbols flatten.
- **Logging**: Verify that `autonomous_sovran_engine.log` clearly separates symbol activity (e.g., `[MNQ] AI Decision...` vs `[MES] AI Decision...`).
