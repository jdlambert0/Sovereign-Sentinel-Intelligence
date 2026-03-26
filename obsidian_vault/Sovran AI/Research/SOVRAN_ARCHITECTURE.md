Sovran AI Architecture (Phase 7 — Research)

Overview
- Sovran AI is a multi-symbol, single-process trading bot that uses an LLM-based decision loop (Claude/Gemini) to guide risk-enabled trading across multiple instruments. It combines a memory-backed learning loop, a trailing-drawdown risk framework, and an adaptive position/order management stack to operate with enterprise-grade reliability.

Core Components
- AIGamblerEngine: The centerpiece that receives Market context, computes risk/size, and orchestrates order execution. Integrates with TradingSuite for API access and, optionally, a real-time bridge for data/subscriptions.
- TrailingDrawdown: Tracks high-water marks and trailing floors to enforce risk constraints and preserve capital.
- GamblerState: Maintains bankroll, PnL history, and drawdown state; supports persistence to disk.
- Memory / Learning: Persists trades and events to Obsidian for auditing; triggers learning cycles after a fixed number of trades.
- Realtime Bridge / Node Sidecar: Optional real-time feed via a sidecar to supplement Python WebSocket connectivity; used as fallback when Python WS is flaky.
- Configuration: Tick sizes, symbol settings, risk thresholds, and per-symbol metadata to ensure deterministic risk budgeting.

Data Flow & Control Flow
- Market Data -> Engine: The Engine consumes market data (quotes, trades) and calculates decision signals using LLM-consensus architecture.
- Decision -> Position Sizing: The Engine computes risk-based position sizing (contracts) and target stop/target levels.
- Order Path:
  1. Attempt atomic bracket path via native API (place_native_atomic_bracket) if enabled and prerequisites satisfied (APIs available, token present, context available).
  2. If atomic bracket path fails, fallback to legacy method (entry order + SL/TP linkage) with OCO linking to entry.
- Memory: Each trade is recorded in memory; after a fixed number of trades a learning cycle can be invoked to generate insights.
- Observability: All actions logged; metrics captured (PnL, risk metrics, order stats) for auditing.

Key Algorithms & Mechanics
- Trailing Drawdown: 4-layer risk guardrails (HWM, floor, tail risk) to manage risk budgeting.
- Kelly Sizing: Used to adjust bet size based on win rate and risk-reward expectations.
- Tick-based pricing: All bracket parameters and price alignments are tick-based to maintain exchange compatibility.
- OCO Linkage: Atomic bracket path uses OCO linkage so SL/TP cancel each other on trigger.

Reality Check / Known Limitations
- WebSocket instability remains a live risk; REST-based bracket path is preferred for automation.
- UI parity differences can cause confusion; the API state is the ground truth for automation.
- Token management: ensure token refresh is robust and integrated in all code paths.

- Next Steps (Phase 7+)
- Document and implement a robust end-to-end test harness (Phase 6/7): test atomic bracket end-to-end in a controlled environment.
- Integrate the bracket path fully into the main trading loop (replace legacy SL/TP path when atomic brackets succeed).
- Expand observability and telemetry; ensure a clean rollback path if REST bracket path experiences issues in production.
- CI/Automation: Plan Windows-based CI to run the autonomous demo and collect logs; log artifacts to Obsidian.
