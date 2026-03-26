Sovran-X Bracket Plan - Phase 2 (Atomic Brackets)

Objective
- Implement an atomic SL/TP bracket path using TopStepX native API (Order/place with stopLossBracket and takeProfitBracket).
- Validate end-to-end via a test harness; ensure no unplanned fixes are introduced.

Prerequisites
- TopStepX Position Brackets must be OFF when using API brackets (per API constraints).
- Stop Loss: SL must be Stop Market (type 4) with negative ticks for LONG entries.
- Take Profit: TP should be Limit (type 1) with positive ticks.

Planned Implementation
- Add place_native_atomic_bracket(side, size, stop_loss_ticks, take_profit_ticks) to sovran_ai.py.
- Add test_native_bracket_integration.py to perform an end-to-end bracket placement and validation.
- Integrate the atomic bracket route into the main trading path, replacing the old sequential SL/TP logic.
- Add robust error handling and logging for traceability.

Testing Plan
- Phase 2 Test Harness: test_native_bracket_integration.py
- Sequence:
  1. Authenticate (TradingSuite)
  2. Place atomic bracket with LONG using SL -400 and TP 200
  3. Validate API response and open orders
  4. Clean up by canceling existing orders

Acceptance Criteria
- Atomic bracket call succeeds (API returns success)
- Open orders show both SL and TP with proper IDs
- POTENTIAL UI visibility differences documented
- No new unplanned fixes; only bracket integration and tests

Risks & Mitigations
- WebSocket instability: rely on REST API for atomic bracket path
- Token management: ensure token present and refreshed when needed
- UI discrepancies: treat API results as source of truth for automation

Next Steps
- Phase 3: Integrate code changes into the main Sovran trading loop and run Phase 3 tests
- Phase 4: Run Phase 4 tests and finalize integration
- Phase 5: Full Sovran + ProjectX documentation synthesis in Obsidian
- Phase 3: Integrate code changes into the main Sovran trading loop and run Phase 3 tests
- Update Obsidian with results and new Phase 2 findings
