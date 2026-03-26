# 📊 Goldilocks Calibration & Current System State (2026-03-17)

## 🎯 V3 GOLDILOCKS CALIBRATION
These numbers represent the "Goldilocks" state (neither too aggressive nor too cautious) derived from Battle Arena V1 and V2 data analysis.

### Core Entry Thresholds
- **OFI Z-Score**: `> 1.5` (Targeting institutional displacement. V1 winners avg: `1.56`)
- **VPIN**: `> 0.55` (Probability of informed trading. V1 winners avg: `0.645`)
- **Combined High-Conviction**: `OFI_Z > 2.0` AND `VPIN > 0.70` (Must-take signal)

### Filter & Safety Gates
- **Weak Signal Floor**: `|OFI_Z| < 1.0` (Blocked - avoid noise)
- **Confidence Gate**: `0.50` (LLM consensus threshold)
- **Banned Phases**: 
    - `EARLY AFTERNOON` (12:30 - 2:00 CT): Banned due to V3 data showing persistent losses (-$102 net).
    - `MIDDAY CHOP`: Banned by default.

### Institutional Provenance (Academic Grounding)
- **OFI**: Cont, Kukanov, Stoikov (2014) - *"The Price Impact of Order Book Events"*
- **VPIN**: Easley, López de Prado, O'Hara (2011) - *"The Microstructure of the Flash Crash"*
- **Kelly Sizing**: John L. Kelly (1956) - *"A New Interpretation of Information Rate"*

---

## 🏗️ CURRENT SYSTEM STATE (INTERNAL AUDIT)
*This section provides a high-fidelity hand-off for other AI agents to understand the current technical status of the Sovran AI fleet.*

### 1. Active Infrastructure
- **SDK**: `project-x-py` (v3.5.x context, patched for TopStepX).
- **Virtual Environment**: `C:\KAI\vortex\.venv312` (Python 3.12).
- **Launcher**: `launch_armada.py` (Background operation standard).
- **Watchdog**: `sovran_watchdog.py` (Ensures process persistence).

### 2. Resolved Vulnerabilities (March 16-17)
- [x] **SignalR Unicode Handshake**: Patched `signalrcore` to handle binary `b'\x03\xe8'` frames.
- [x] **Session Phase Mapping**: Implemented 8-phase MECE detection in `sovran_ai.py`.
- [x] **Singleton Execution**: Implemented file-based locks to prevent multiple TopStepX sessions on one key.
- [x] **Preflight Gate 39**: Enforced documentation-to-code consistency audit.

### 3. Open Critical Issues (Top Priority)
- **WebSocket Handshake Conflict**: The `JSONDecodeError` at char 4073 is caused by the Market Hub sending binary MessagePack while the client expects JSON.
    - **Status**: Identified. Solution requires forcing `MessagePackHubProtocol` in the SDK client.
- **Async Event Thread-Safety**: SignalR callbacks occur on a non-event-loop thread. Calling `asyncio.Event.set()` directly causes the `TadingSuite` to hang/timeout during `connect()`.
    - **Status**: Identified. Solution requires wrapping event calls in `loop.call_soon_threadsafe()`.
- **Unicode Logging Errors**: Console encoding issues when logging emojis.
    - **Status**: Minor but persistent. Requires log handler reconfiguration.

### 4. Immediate Roadmap
1. Apply the `connection_management.py` patch for MessagePack and thread-safety.
2. Verify order placement via `test_place_order_suite.py`.
3. Clear high-severity bugs identified in `COMPLETE_BUG_INVENTORY.md`.

---
*Status: CALIBRATED | Sovereign 11 Protocol active | Memory Ingested*
