# 🌐 WebSocket Feed Solution & System State Handover (2026-03-17)

## 🛠️ THE WEBSOCKET SOLUTION: DUAL-MODE OPERATION
After extensive testing and research by multiple AI sessions, the definitive solution for the "Market Hub" instability has been identified.

### 1. Root Cause Summary
- **Binary Mismatch**: TopStepX sends binary MessagePack frames in data phase
- **Failed Remediation**: Injecting `MessagePackHubProtocol` at the SDK level causes a connection state loss (`ProjectXError: Realtime client not connected`)
- **Thread-Safety Race**: SignalR callbacks execute on non-event-loop threads, causing `asyncio.Event` synchronization to fail

### 2. The Solution: Dual-Mode Operation
For 100% operational uptime, the system operates in dual mode:
- **REST API (Primary)**: All trading operations work reliably via REST
- **WebSocket (When Available)**: Real-time quotes when WebSocket connects successfully

### CORRECTION (2026-03-18): "Fallback" Terminology Incorrect
Earlier documents incorrectly referred to REST as a "fallback." The correct model is:
- REST API is the **primary reliable method** for all operations
- WebSocket is **optional** for real-time data when available

---

## 🛰️ SYSTEM STATE HANDOVER (Internal AI Sync)
*Crucial context for other fleet agents working on the Sovereign system.*

### Current Baseline: HARDENED
- **Order Execution**: **STABLE**. Orders are now placed via **REST API** with `stopLossBracket` and `takeProfitBracket` parameters included in the initial payload. This creates correct OCO (One-Cancels-Other) behavior and proper SL/TP lines in the TopStepX UI.
- **Risk Management**: **ACTIVE**. `BUG-003` (Lock File) is mitigated. Trailing drawdown tracking and Kelly sizing are mathematically verified.
- **Memory/Learning**: **TRANSITIONING**. The system is moving from JSON flat files to **Obsidian-based context** for cross-session intelligence persistence.

### High-Priority Guidance for Other AI
1. **Never use `place_bracket_order()`**: This SDK method triggers the binary WebSocket code path which is currently unstable. Use the REST method with bracket parameters.
2. **Handle Feed Restarts**: If `engine.last_price` is stagnant, force a REST refresh rather than waiting for `handle_quote`.
3. **Log Unicode**: Be cautious of emojis in logs. Some environments trigger `UnicodeEncodeError` (charmap). Use `errors='ignore'` or a safe logger configuration.
4. **Agent Coordination**: Check `SESSION_LOGS` specifically for "SL/TP Integration" and "Goldilocks Calibration" notes before modifying `sovran_ai.py`.

---
*Status: SYSTEMS NOMINAL | Protocol Pivot Active | Handover Complete*
