# Implementation Plan: MEMM Grid (Multi-Engine Multi-Market)

## Overview
The **MEMM Grid** expands the Sovran AI fleet from 3 "pinned" slots to a 9-slot parallel execution matrix (3 Symbols x 3 Engines).

## Core Refactor (in `sovran_ai.py`)

### 1. The 3x3 Loop
Instead of pinning one system per symbol, we will spawn all 3 engines for each symbol:
```python
symbol_list = ["MNQ", "MES", "MYM"]
system_list = ["sovereign", "gambler", "warwick"]

for symbol in symbol_list:
    for system in system_list:
        # Create unique instance 
        instance_id = f"{symbol}_{system}"
        state_file = f"sovran_ai_state_{instance_id}.json"
        
        # Initialize and run
        tasks.append(...) 
```

### 2. State & Memory Isolation
Each (Symbol, System) pair gets its own persistent state to prevent "Confidence" or "OFI" cross-contamination.

### 3. Verification of "Every Turn" Mandate
- **Sovereign**: LLM-driven decision every turn.
- **Gambler**: Probabilistic trade every turn (if GCS > threshold).
- **Warwick**: Trend-following trade every turn (if Velocity > threshold).

## SL/TP Visibility Fix
- **Diagnostic Logging**: Each `place_order` call will now emit a `[BRACKET_SUCCESS]` log with the EXACT ticks used and the API's confirmation ID.
- **TopStepX Sync**: We will programmatically check if the API returns a `positionId` that carries the `stopLoss` and `takeProfit` legs.

## Verification
- **Stress Test**: 9 concurrent engines running in the background.
- **Visual Audit**: User should see 3 trades per symbol (total 9) on the TopStepX dashboard.

---
*Status: PLAN REFINED | Implement in Phase 26 | Date: March 20, 2026*
