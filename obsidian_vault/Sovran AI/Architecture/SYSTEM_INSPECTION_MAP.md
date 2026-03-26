# Sovereign System Inspection Map (GSD-Audit Protocol)

This document defines the 100% Coverage Inspection plan requested by the User on March 20. It breaks the system into "Audit Cells" with specific verification steps.

## Audit Cell 1: Connectivity & Data Ingestion
- **Target**: `market_data_bridge.py`, `websocket_bridge.py`, `sovran_ai.py:handle_quote`
- **Verification**:
    - [ ] **SignalR Schema**: Ensure `bestBid`/`bestAsk` correctly map to `self.bid`/`self.ask`.
    - [ ] **Timeout Robustness**: Verify REST fallback triggers if heartbeat stops for > 60s.
    - [ ] **MessagePack Handling**: Ensure non-JSON frames don't crash the parser.

## Audit Cell 2: Execution & Side Convention (CRITICAL)
- **Target**: `sovran_ai.py:calculate_size_and_execute`, `place_native_atomic_bracket`
- **Verification**:
    - [ ] **Side Logic**: Confirm `BUY = 1`, `SELL = 0` across all REST and WS calls.
    - [ ] **Bracket Polarities**: Ensure SL is physically below Entry for Longs (Negative sign if REST API tick-based).
    - [ ] **Legacy Side Check**: Audit all `direction == "LONG"` vs `"BUY"` string comparisons for case sensitivity.

## Audit Cell 3: Risk & Position Recovery
- **Target**: `GlobalRiskVault`, `recover_active_position`, `intelligent_trade_management`
- **Verification**:
    - [ ] **Orphan Brackets**: Does the system place missing SL/TP orders if it finds a naked position on startup? (Found BUG: Currently only monitors internally).
    - [ ] **Kill-Switch**: Verify `flatten_all_positions.py` cancels PENDING orders, not just active positions.
    - [ ] **Drift Sync**: Confirm periodic balance reconciliation doesn't double-count PnL.

## Audit Cell 4: Intelligence & Consensus
- **Target**: `llm_client.py`, `retrieve_ai_decision`, `VetoAuditor`
- **Verification**:
    - [ ] **Model Failover**: Verify if `anthropic` fails, it successfully hits `google_gemini` without looping.
    - [ ] **Wait vs mandate**: Ensure `GAMBLE_MANDATE` uses reduced sizing (0.2x) as intended.
    - [ ] **Refusal Handling**: Ensure models aren't "hallucinating" trade results in their reasoning.

## Audit Cell 5: Learning & Persistence
- **Target**: `learning_system.py`, `finalize_trade`, `obsidian_vault/`
- **Verification**:
    - [ ] **Log Fidelity**: Confirm SL/TP prices are actually recorded in the Obsidian trade log.
    - [ ] **Atomic Memory**: Ensure JSON state file doesn't corrupt on power-loss (Use temp file + rename move).
    - [ ] **Research Loop**: Verify `research_and_learn` actually triggers after N trades.

---
*Next Audit Sweep: 2026-03-20 12:00 CT.*
