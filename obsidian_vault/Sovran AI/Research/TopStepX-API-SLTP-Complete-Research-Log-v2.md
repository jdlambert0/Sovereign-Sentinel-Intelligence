TopStepX SL/TP Research - Phase 2 Update

- Date: 2026-03-18
- Outcome: Atomic bracket path via native API validated end-to-end.
- API: /api/Order/place with stopLossBracket and takeProfitBracket in a single payload.
- SL: type 4 (Stop Market); ticks negative for LONG; e.g., -400
- TP: type 1 (Limit); ticks positive for LONG; e.g., 200
- Prereqs: Position Brackets OFF in TopStepX when using API bracket path
- Observations: 401/401-like errors resolved by correct token usage; WebSocket instability still observed for live data
- Next actions: Integrate into Sovran AI, create end-to-end test harness, and log results in Obsidian
