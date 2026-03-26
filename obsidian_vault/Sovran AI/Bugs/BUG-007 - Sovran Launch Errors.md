# BUG-007: Sovran Launch Errors
**Date:** 2026-03-16
**Status:** DISCOVERED (Not Fixed)

## Symptom
During the live launch of `sovran_ai.py` on March 16, 2026, the diagnostic engine logged two distinct errors during its initialization and WebSocket connection phase.

## Evidence
The following raw errors were extracted from `C:\KAI\armada\sovran_launch_diagnostic.log`:

### Error 1: WebSocket Connection Failure
```json
{"timestamp":"2026-03-16T19:28:28.637211Z","level":"ERROR","logger":"project_x_py.realtime.connection_management","module":"connection_management","function":"connect","line":324,"message":"WebSocket error","taskName":"Task-1","operation":"setup_connections","user_hub":"https://rtc.topstepx.com/hubs/user","market_hub":"https://rtc.topstepx.com/hubs/market"}
```

### Error 2: Position Recovery Crash
```text
46: 2026-03-16 14:28:28,919 [ERROR] [sovran_ai] Failed to recover position: 'Position' object has no attribute 'get'
```

## Context
These logs occurred just before the AI Decision Loop started (`Starting AI Decision Loop (interval: 30s)`). 
- Error 1 originates from `project_x_py` library (`connection_management` module).
- Error 2 originates from `sovran_ai.py` during `Checking for orphaned positions on startup...`

## Next Steps (RESOLVED)
_Update: 2026-03-16_
**Status:** RESOLVED

**Fix Description:**
1. **Error 1 (WebSocket):** The TopStepX market hubs require binary MessagePack frames, but the Python `signalrcore` client defaults to JSON. We injected `MessagePackHubProtocol` into the `HubConnectionBuilder` within `vortex\.venv312\Lib\site-packages\project_x_py\realtime\connection_management.py` to correctly parse the data stream.
2. **Error 2 (Position Recovery Crash):** The `get_all_positions()` API returns a list of `TopStepXPosition` objects, not dictionaries. Calling `.get()` threw an `AttributeError`. The orphaned position recovery logic in `sovran_ai.py` was refactored to use standard `getattr(pos, 'attribute', ...)` safely. 

Both fixes were implemented and tested successfully against the `preflight.py` Zero-Runtime-Surprise gating.
