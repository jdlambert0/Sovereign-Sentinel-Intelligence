# Sovran AI: Development Journey Trace (March 20, 2026)

## 0. The Vision
A fully autonomous AI trader that doesn't just execute predefined strategies but develops its own "gumption" through independent research into math, probability, and gambling theory.

## 1. Chronology of Evolution
### Phase 28: Grounding & Stabilization
- **Status**: The system was returning stale data due to a WebSocket hang in the SDK.
- **Action**: Restored the `market_data_bridge.py` for direct SignalR connection.
- **Outcome**: 100% data freshness achieved.

### Phase 29: Cost & Orchestration
- **Problem**: High frequency (30s) and expensive models (Sonnet/Gemini 1.5 Pro) exceeded $100/day.
- **Action**:
    - Increased `loop_interval_sec` to 90 seconds.
    - Promoted **Claude 3 Haiku** to Council Leader.
    - Switched consensus and audit to **Gemini 1.5 Flash**.
- **Outcome**: Projected daily cost dropped to ~$18.80.

### Phase 30: The Second Loop (Mind Palace)
- **Problem**: The system was purely reactive to market data with no "long-term memory" or evolving intelligence.
- **Action**:
    - Built `curiosity_engine.py` (The Gumption Loop).
    - Integrated `scout_agent.py` for web sentiment research.
    - Created the `Intelligence/` and `Journal/` directories in Obsidian.
    - Injected "Accrued Intelligence" into the `sovran_ai.py` prompt.
- **Outcome**: The system now reads its own research before trading.

## 2. Global State Audit

### What works (Functional)
- **Data Bridge**: Direct SignalR handshake is stable.
- **Council Consensus**: Agreement/Disagree logic in `complete_ensemble` is active.
- **Veto Auditor**: Final safety gate logic is implemented.
- **Mind Palace**: Research nodes are being created and ingested.
- **SL/TP Brackets**: Native TopStepX OCO brackets are being sent.

### What is Partial/Experimental
- **Scout Stability**: Playwright can sometimes timeout on heavy news sites (CNBC). Fallback to model-only synthesis is implemented.
- **Multi-Symbol Concurrency**: The system starts symbols in parallel, but high load (10 symbols) can still stress the 1500ms latency gate.

### What remains (TO-DO)
- **Asymmetric Kelly Tuning**: The curiosity engine just researched this; it needs to be "hardened" into the `calculate_size_and_execute` logic if the user desires.
- **Visual Verification of SL/TP**: While logs show they are sent, the user reports intermittent invisibility on the chart. Needs platform-side verification.
- **Gap analysis**: The "one trade per turn" mandate is literal in the prompt but the engine still respects thresholds. This "disconnect" is documented in the Map.

## 3. Map of the Code (Armada)
- `sovran_ai.py`: The Main Brain (Monolith).
- `curiosity_engine.py`: The Researcher (Background).
- `scout_agent.py`: The Web Explorer.
- `market_data_bridge.py`: The Data Gateway.
- `llm_client.py`: The Communication Layer.

---
*Signed: Antigravity | March 20, 2026*
