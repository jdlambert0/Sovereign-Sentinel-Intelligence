# Sovereign Engine Realignment: Entry Point & LLM Handoff Details

**Date:** March 24, 2026 11:20 CT
**Engine Version:** V3.2 (Direct WS + Session Guard)

## 🏗 Entry Point Changes (`sovran_ai.py`)

The engine's boot sequence and execution loop have been re-engineered for "Direct WebSocket Only" operations.

### 1. Mandatory WS Gate (Gate 40)
The primary order execution method, `place_native_atomic_bracket`, now contains a deterministic check:
```python
if not (self.websocket_bridge and self.websocket_bridge.connected and 
        self.market_data_bridge and self.market_data_bridge.connected):
    logger.critical("WS GATE BLOCKED: Execution forbidden while telemetry is offline.")
    return False
```
This ensures that while REST is used for the *atomic placement* of the order, it is only allowed when high-fidelity WebSocket event loops are verified as healthy.

### 2. Multi-Process Session Guard
To resolve the TopStepX "Multiple sessions detected" conflict, the `run_engine_process` (which spawns isolated symbol workers) was modified:
- **SOVEREIGN Process**: Maintains the active User Hub SignalR connection.
- **GAMBLER Process**: Market data stream only; skips User Hub initialization.
- **Benefit**: Zero session collisions while maintaining dual-model market data fidelity.

### 3. REST Fallback Elimination
- **Hardset Core**: `config.strict_websocket = True` is now the immutable source of truth.
- **De-labeling**: Removed all logic-level labels and logs related to "REST fallback" to prevent confusion or accidental fallback activation.

---

## 🤖 LLM Handoff & Context Liberalization

The handoff between the Python engine and the LLM (Sovereign Thinker) has been updated to remove artificial trading bans.

### 1. Session Phase Context (`get_session_phase`)
The LLM no longer receives "(BANNED)" markers in its `TIME CONTEXT`.
- **PRE-MARKET (BANNED)** -> **PRE-MARKET**
- **MIDDAY CHOP (BANNED)** -> **MIDDAY LULL**
- **EARLY AFTERNOON (BANNED)** -> **EARLY AFTERNOON**

### 2. Veto Auditor Rule Revocation
The "Veto Auditor" (Gatekeeper LLM) has been updated. Rule #3, which previously mandated vetoes for trading in banned phases, has been replaced:
- **Old Rule**: `3. VETO if the primary ignores 'BANNED PHASES' (Midday Chop/Early Afternoon).`
- **New Rule**: `3. VETO if the primary ignores risk boundaries. (Updated: No session-based bans).`

### 3. Handoff Payload
The `build_prompt` method now passes clean, un-biased session phase strings, allowing the LLM to decide based on **microstructure (OFI/VPIN)** rather than a hardcoded clock.

---
**Status: Documentation Complete. 2-Hour Monitoring Turn Initiated.**
