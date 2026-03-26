Sovran AI Consolidated Reference

Overview
- This document consolidates Sovran AI architecture, data flows, bracket integration (Phase 7+), and related external ProjectX API references to support safe production rollout and auditing.

Core Architecture (Summary)
- AIGamblerEngine: central decision/execution orchestrator; interfaces with TradingSuite for orders, positions, and data.
- TrailingDrawdown: risk guardrail system tracking high-water marks and trailing floors.
- GamblerState: persistent state including bankroll, PnL, and risk metrics; supports JSON persistence.
- Memory/Learning: stores trades in Obsidian-based memory journals; triggers learning cycles after a fixed trade count.
- RealtimeBridge: optional Node.js sidecar for real-time data streaming when Python WS is unstable.
- Config/Symbol Metadata: per-symbol tick sizes, point values, risk thresholds, and market metadata.

Bracket Integration (Atomic Path)
- Goal: atomic SL/TP bracket via TopStepX native API using a single Order/place payload.
- Payload structure: accountId, contractId, type=2, side, size, stopLossBracket{ticks, type}, takeProfitBracket{ticks, type}.
- Tick semantics: LONG requires stopLossBracket.ticks negative; Stop Market (type 4), TP with positive ticks and type 1 (Limit).
- Strategy: prefer REST atomic bracket path for automation; disable Position Brackets if API brackets are needed; consider Auto-OCO if appropriate.

External References (Docs)
- ProjectX: Order placement payload and bracket support (Order/place)
- ProjectX: Position management and ordering models
- TopStepX: Position Brackets vs Auto-OCO brackets; settings implications
- TopStepX: REST bracket usage in risk settings
- General: REST vs WebSocket real-time data tradeoffs

Testing & Validation (High-level)
- Test harness validates end-to-end: token acquisition, bracket payload, API response, and verify open orders reflect both SL/TP.
- Use a clean environment (cancel prior orders, close positions) before running tests.
- Maintain logs for auditability.

Next Steps
- Integrate atomic bracket flow into the main trading loop and wire test harness into CI.
- Add automated phase tests for edge cases (API errors, token expiry, network timeouts).
- Expand logging and metrics to support performance monitoring and profitability planning.
