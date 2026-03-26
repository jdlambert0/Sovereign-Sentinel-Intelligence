# Sovran AI System Architecture

## Overview
An LLM-driven futures trading system that uses AI (via OpenRouter free models) to make every trading decision, with mathematical safety brakes (Kelly Criterion sizing, VPIN, Z-Score OFI).

## Core Files
- **`C:\KAI\armada\sovran_ai.py`** — The monolithic trading engine (Parallel 3x3 MEMM Grid)
- **`C:\KAI\armada\curiosity_engine.py`** — Autonomous AI Research & Intelligence Archiver
- **`C:\KAI\armada\market_data_bridge.py`** — Raw SignalR WebSocket Bridge (Bypass SDK)

## Data Flow
```
TopStepX WebSocket (SignalR)
    ↓ [DIRECT WS HANDSHAKE]
market_data_bridge.py (Bypass SDK)
    ↓ Normalized Dict (GatewayQuote, GatewayTrade)
handle_quote() → Updates: last_price, bid, ask, book_pressure
handle_trade() → Updates: OFI history, VPIN baskets, Z-Score
    ↓
monitor_loop() (every 30s)
    ↓ [Safety Gates]
    ├── last_price > 0?
    ├── Stale data < 90s?
    ├── Throttle cooldown expired?
    ├── Spread gate OK?
    ├── Session phase allowed?
    ├── Consecutive loss < max?
    ├── Trailing drawdown OK?
    ├── Micro-chop guard OK?
    └── Data freshness < 30s?
    ↓ [All gates pass]
retrieve_ai_decision() → OpenRouter LLM API
    ↓ JSON {action, confidence, reasoning}
calculate_size_and_execute() → Kelly Criterion → TopStepX Order
    ↓
sovran_memory.json ← Trade result + AI reasoning (feedback loop)
```

## Key Components

### Data Ingestion & Intelligence
| Component | Purpose |
|-----------|---------|
| `handle_quote` | L1 top-of-book: price, bid, ask, book pressure |
| `handle_trade` | Trade ticks: OFI, VPIN baskets, Z-Score |
| `get_session_phase` | CT timezone session classification |
| `curiosity_engine.py` | Generates 'Intelligence Nodes' from performance gaps |
| `Mind Palace` | Obsidian-based memory injected into trading prompts |

### Safety Gates
| Gate | Threshold | Purpose |
|------|-----------|---------|
| Price purgatory | `last_price > 0` | Won't trade without price data |
| Stale data | `< 90s` | Network hiccup protection |
| Spread gate | Configurable | Prevents wide-spread entries |
| Session phase | CT time-based | Bans midday chop, pre/post market |
| Consecutive loss | 3 max | Circuit breaker |
| Trailing drawdown | $500 danger zone | Account protection |
| Micro-chop | Range < 8, ATR < 5 | Dead market filter |
| Data freshness | `< 30s` | Pre-LLM staleness check |
| Throttle | 300s after loss | Revenge trade prevention |

### Multi-Symbol Architecture (3x3 MEMM Grid)
- **3 Symbols** (MNQ, MES, MYM) x **3 Engines** (Sovereign, Gambler, Warwick) = 18 Parallel Tasks.
- Single `TradingSuite` master connection + Symbol-specific `AIGamblerEngine` slots.
- **Global Risk Vault**: Monitors aggregate PnL across all 9 slots (Mandate: -$450.00 Limit).
- **Staggered Boot**: Tasks initialize with 5-15s delays to prevent API rate-limit bursts.
- Per-instance state: `sovran_ai_state_MNQ_SOVEREIGN.json`, etc.

## Dependencies
- `project_x_py` — TopStepX SDK (REST and authentication only)
- `market_data_bridge.py` — Direct SignalR/WebSocket bridge (Restored 2026-03-19)
- `signalrcore` — WebSocket transport (used for authentication handshake)
- `httpx` — HTTP for OpenRouter API
- OpenRouter free models for LLM inference

## Resolved Critical Issues (2026-03-19)
> [!NOTE]
> **SDK WebSocket Hang**: Resolved by implementing a pure-Python SignalR bridge (`market_data_bridge.py`). 
> The engine now uses the `--force-direct` flag to bypass SDK dependency for real-time data.

> [!CAUTION]
> The `event.data` from TopStepX is a raw **dict**, not a named object.
> `handle_quote` must use `.get()` not `getattr()`.
> This was the root cause of silent data starvation.

---

## Tags
#architecture #sovran-ai #topstepx
