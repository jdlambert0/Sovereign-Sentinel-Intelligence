# BUG-004: Quote Stream Data Ingest Crash (Silenced Error)

**Status:** UNRESOLVED
**Date:** 2026-03-16
**Discovered By:** ZRS Subagent Boundary Audit

## Symptom
The live trading bot is actively dropping the live market price stream from its WebSocket connection. Because `msg.get()` fails silently by returning `None`, the engine has been using fallback prices (Bid/Ask averages) or stale data entirely.

## Location
`C:\KAI\armada\sovran_ai.py` - Line ~40, within `AIGamblerEngine.handle_quote()`.

## Hypothesis
Code currently attempts to extract the last traded price using:
```python
current_price = data.get('last')
```
However, the subagent research into the TopStepX `project_x_py` SDK schemas revealed that the actual incoming JSON structure for the `on_quote` market data payload uses the explicit key `last_price`.

The `last` key does not exist. The current implementation silently degrades.

## Context
During the initiation of the **Zero-Runtime-Surprise (ZRS) Pipeline** audit, a browser subagent gathered the definitive JSON schema shapes directly from TopStepX docs. 

TopStepX `on_quote` dictionary payload schema:
- `ticker`: string
- `bid`: float
- `ask`: float
- `last_price`: float
- `volume`: float
- `timestamp`: string

Our code is explicitly asking for keys that do not exist because we lacked a strict type boundary.

## Proposed ZRS Fix
Do not just fix the string. We must implement the ZRS pipeline:
1. Implement strict `TypedDict` boundaries in a new `api_types.py` file.
2. Cast `ev.data` to this `TopStepXQuote` type before accessing it in `sovran_ai.py`.
3. The IDE and mypy will instantly throw a fatal compile error if `get('last')` is ever attempted again, permanently stopping this class of bug.
