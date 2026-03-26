# Sovran v2 — Product Requirements Document
## "Built Right From The Foundation Up"

> **Status**: PROPOSED — Awaiting Director Approval  
> **Date**: 2026-03-25  
> **Author**: Sovran Agent (CIO)  
> **Reference**: [[SOVEREIGN_DOCTRINE]], [[CODE_AUTOPSY_25Mar2026]]

---

## 1. Problem Statement

The current Sovereign Sentinel system (v1) cannot fulfill its mission. After weeks of iterative bug fixing, the core architecture remains fundamentally broken:
- Stop losses don't actually execute on the broker
- The AI brain dies every message, orphaning trades
- PnL tracking lies due to hardcoded overrides
- MagicMock (a testing library) runs in production as a fallback
- No trade learnings feed back into future decisions

The Director has mandated a ground-up rebuild. Each layer must be battle-tested before the next is added.

## 2. Success Criteria

The system passes the TopStepX 150k Combine:
- **+$9,000 profit** before **-$4,500 trailing drawdown**
- Runs autonomously while the market is open (Sunday 5pm CT — Friday 4pm CT)
- No human intervention required during trading hours
- Every trade has a thesis, stops, and targets that *actually execute on the broker*
- The system demonstrably improves its performance over time

## 3. Architecture: The Five Layers

Each layer has explicit acceptance criteria. A layer is NOT complete until every criterion passes under real market conditions.

---

### Layer 0: THE BROKER TRUTH
**Purpose**: A clean, minimal, tested client for the TopStepX/ProjectX API.

**What it does**:
- Authenticates with API key (token caching with proper expiry)
- Places market orders with atomic bracket (SL + TP) in a single API call
- Modifies existing bracket orders (move stops, trail, etc.)  
- Cancels orders
- Queries current positions (from broker, not local state)
- Queries current PnL (from broker, not local state)
- Flattens all positions (emergency)

**What it does NOT do**:
- No trading logic
- No market data
- No AI reasoning
- No state management beyond auth tokens

**Acceptance Criteria**:
- [ ] Can authenticate and cache token correctly (test: auth → wait 5min → auth again uses cache → wait 2min → cache expires → re-auth)
- [ ] Can place a bracket order and confirm all 3 legs (parent + SL + TP) exist on broker
- [ ] Can modify a stop loss on the broker and confirm the new price via position query
- [ ] Can cancel all orders and confirm zero working orders
- [ ] Can query positions and get accurate contract, side, size, and entry price
- [ ] Can query PnL and match what TopStepX dashboard shows (within $1)
- [ ] Can flatten a position and confirm zero exposure
- [ ] All functions handle 401 (re-auth), 429 (backoff), 503 (retry), timeout (retry) correctly
- [ ] No `except: pass` anywhere — every error is either handled or raised
- [ ] 100% of public functions have docstrings explaining what they do, what they return, and what can go wrong

**Salvage from v1**: `projectx_broker_api.py` is the healthiest component. Clean it up, add proper tests, remove unused code.

---

### Layer 1: THE GUARDIAN (Risk Engine)
**Purpose**: Mathematical risk management that CANNOT be overridden by the AI brain.

**What it does**:
- Calculates position size using Kelly Criterion (half-Kelly by default)
- Sets stop loss distance using ATR-based calculation
- Sets take profit using risk:reward ratio (minimum 1.5:1)
- Enforces daily loss limit (-$450)
- Enforces trailing drawdown limit ($4,500 from high-water mark)
- Calculates distance-to-ruin and refuses trades when ruin probability > 5%
- Tracks open positions via **broker queries only** (no local state divergence)

**What it does NOT do**:
- No market analysis
- No trade decisions
- No AI integration

**Acceptance Criteria**:
- [ ] Given a win rate and avg win/loss, calculates correct Kelly fraction
- [ ] Given ATR, calculates stop distance that's neither too tight (noise) nor too wide (drawdown risk)
- [ ] Refuses to size a position that would risk more than the daily limit on a single trade
- [ ] Accurately tracks PnL by querying broker, not local state
- [ ] Can compute ruin probability for current bankroll + edge + sizing
- [ ] When daily loss limit is hit, returns "NO TRADE" for all requests until next session
- [ ] When trailing drawdown is within $500, returns "NO TRADE" (circuit breaker)
- [ ] All risk parameters are configurable via a single `risk_config.json` file
- [ ] Every risk calculation is logged to Obsidian `Trader Diary/` with full reasoning

---

### Layer 2: THE EYES (Market Data Pipeline)
**Purpose**: Clean, reliable, real-time market data that the AI can reason over.

**What it does**:
- Connects to ProjectX WebSocket (SignalR) for real-time quotes
- Maintains a rolling temporal buffer (configurable window, default 10 minutes)
- Computes derived signals: VPIN, OFI, ATR, volume profile, bid/ask imbalance
- Detects market regime: trending, mean-reverting, choppy, breakout
- Provides a clean `MarketSnapshot` object every N seconds with all signals

**What it does NOT do**:
- No trade decisions
- No order execution
- No AI reasoning

**Acceptance Criteria**:
- [ ] WebSocket connects, authenticates, and subscribes to contract within 10 seconds
- [ ] Handles disconnect with automatic reconnect (exponential backoff, max 5 retries)
- [ ] Temporal buffer correctly stores and ages out data points
- [ ] VPIN calculation matches reference implementation (test against known dataset)
- [ ] OFI Z-score correctly identifies order flow imbalance
- [ ] ATR calculation matches standard 14-period ATR within 0.1%
- [ ] Regime detection correctly classifies: trending (ADX>25), choppy (ADX<20), breakout (ATR expansion)
- [ ] `MarketSnapshot` contains all signals in a single, clean data structure
- [ ] Data pipeline runs independently — killing the AI brain does not stop data collection
- [ ] Only ONE WebSocket connection is ever opened (hard constraint from broker)

---

### Layer 3: THE MIND (Decision Engine)
**Purpose**: The AI brain that analyzes market data and produces trade decisions.

**What it does**:
- Reads `MarketSnapshot` from Layer 2
- Applies multi-dimensional analysis (quant, gambler, microstructure, behavioral)
- Produces a `TradeIntent` with:
  - Direction (long/short)
  - Conviction score (0-100)
  - Thesis (natural language, written to Obsidian)
  - Entry price (or "market")
  - Stop distance (suggested, but Layer 1 has final say on sizing)
  - Target distance
  - Framework used (which analytical lens produced this intent)
- Only produces intents when conviction > threshold (dynamically adjusted by Layer 4)

**What it does NOT do**:
- No direct broker access — passes intents to Layer 1 (Guardian) for execution
- No position management after entry (that's the Guardian's job)

**Acceptance Criteria**:
- [ ] Given a MarketSnapshot with clear trend + high OFI, produces a directional intent with conviction >70
- [ ] Given a choppy/noisy MarketSnapshot, produces "NO TRADE" or conviction <30
- [ ] Every intent has a written thesis that explains WHY, not just WHAT
- [ ] Conviction score is calibrated: trades with >70 conviction win more often than trades with <50
- [ ] Can switch between analytical frameworks based on regime (trending → momentum, choppy → mean-reversion)
- [ ] Respects "No Thesis, No Trade" — refuses to output bare directional calls
- [ ] LLM calls are resilient: timeout → retry with exponential backoff, API error → degrade gracefully (no MagicMock)
- [ ] Decision latency < 5 seconds (fast enough for futures scalping)

---

### Layer 4: THE MEMORY (Learning Loop)
**Purpose**: Close the feedback loop. Trade outcomes modify future behavior.

**What it does**:
- After every trade closes, writes a structured journal entry to `Trader Diary/`:
  - Entry thesis + conviction + framework
  - Market conditions at entry (regime, volatility, OFI, time of day)
  - Outcome (PnL, hold time, max adverse excursion, max favorable excursion)
  - Verdict: thesis confirmed or refuted
- Maintains a `Performance_Matrix.json`:
  - Win rate by framework, by regime, by time of day, by conviction level
  - Average win/loss by each dimension
  - Kelly-optimal sizing for each category
- Updates `Live_Parameters.json` that Layer 1 and Layer 3 read:
  - Conviction threshold (raised if recent accuracy is low)
  - Framework weights (emphasize frameworks that are working)
  - Position sizing (Kelly recalculated from recent performance)
- Updates Intelligence Nodes with empirical evidence

**What it does NOT do**:
- No real-time trading decisions
- No direct broker access

**Acceptance Criteria**:
- [ ] Every closed trade produces a complete journal entry within 60 seconds
- [ ] Performance matrix is accurate (spot-check against broker trade history)
- [ ] After 20+ trades, Kelly sizing recommendations are statistically meaningful
- [ ] Live_Parameters.json is read by Layer 1 and Layer 3 on every cycle
- [ ] Framework weights change over time (observable in `Intelligence/` nodes)
- [ ] Conviction threshold self-adjusts: lower during winning streaks (hunt more aggressively), higher during drawdowns (preserve capital)

---

### Layer 5: THE SENTINEL (Autonomous Operations)
**Purpose**: Keep everything running 24/5 without human intervention.

**What it does**:
- Manages the process lifecycle of all layers
- Heartbeat monitoring: if any layer stops responding, restart it
- Crash recovery: on restart, queries broker for actual state (no local assumptions)
- Session management: starts trading at market open, stops at close
- Health dashboard: writes system status to Obsidian `SOVEREIGN_COMMAND_CENTER.md`
- Alerts: if critical failure (can't reach broker, PnL approaching limit), writes urgent note to Obsidian

**What it does NOT do**:
- No trading logic (delegates to Layers 1-4)

**Acceptance Criteria**:
- [ ] Survives simulated crash of any single layer (kill process → auto-restart → correct state recovery)
- [ ] Survives simulated network outage (kill internet 5 min → reconnect → correct state, all positions checked)
- [ ] Survives simulated broker downtime (API returns 503 for 10 min → graceful degradation → resume)
- [ ] Runs for 48+ continuous hours without human intervention
- [ ] SOVEREIGN_COMMAND_CENTER.md is updated every 5 minutes with current state
- [ ] On startup, always queries broker for truth — never assumes local state is correct

---

## 4. Build Order & Dependencies

```
Layer 0 (Broker Truth)     ← START HERE. No other layer can be tested without this.
    ↓
Layer 1 (Guardian/Risk)    ← Depends on Layer 0 for execution and position queries.
    ↓
Layer 2 (Eyes/Data)        ← Independent of Layer 1, but needed for Layer 3.
    ↓
Layer 3 (Mind/AI)          ← Depends on Layer 1 (risk checks) + Layer 2 (market data).
    ↓
Layer 4 (Memory/Learning)  ← Depends on Layer 3 (trade outcomes) + Obsidian vault.
    ↓
Layer 5 (Sentinel/Ops)     ← Wraps all layers in process management.
```

## 5. Technology Decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Language | Python 3.12 | Existing expertise, good async support, rich ecosystem |
| Broker Client | httpx (async) | Already proven in v1, handles retries well |
| WebSocket | Direct SignalR (no sidecar) | Eliminate Node.js dependency, reduce complexity |
| State | Broker is truth, Obsidian is memory | No local state files, no JSON sync, no drift |
| AI/LLM | Multiple providers (Anthropic, Gemini, local) with fallback chain | No single point of failure for reasoning |
| Config | Single `sovran_config.json` + `Live_Parameters.json` | One place for static config, one for dynamic |
| Logging | Structured to Obsidian + stdout | Every decision is traceable |
| Process Mgmt | Python asyncio + supervisor pattern | Single process, multiple async tasks, no multiprocess IPC complexity |

## 6. What We Keep From v1

| Component | Verdict | Reasoning |
|-----------|---------|-----------|
| `projectx_broker_api.py` | **SALVAGE + CLEAN** | Healthiest component, good retry logic, needs cleanup |
| `emergency_flatten.py` | **KEEP AS-IS** | Simple, works, critical safety tool |
| Intelligence Nodes | **KEEP** | Valuable research, will feed into Layer 3 frameworks |
| Trader Diary format | **KEEP + STANDARDIZE** | Good concept, needs consistent schema |
| `sovran_ai.py` | **RETIRE** | 3,600 lines of christmas tree code — rebuild from scratch |
| `realtime_bridge.py` | **RETIRE** | Node.js sidecar adds unnecessary complexity |
| `hunter_alpha_harness.py` | **RETIRE** | Depends on broken sovran_ai internals |
| All monkey-patching | **ELIMINATE** | Use proper SignalR client or write our own |

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Rebuild takes too long, combine expires | MEDIUM | HIGH | Build Layer 0+1 first — can paper-trade safely within days |
| New architecture has its own bugs | HIGH | MEDIUM | Each layer is tested independently before integration |
| LLM API costs during development | MEDIUM | LOW | Use free/cheap models for testing, premium for live |
| ProjectX API changes | LOW | HIGH | Isolate all API calls in Layer 0, easy to update |
| WebSocket connection limit violated | MEDIUM | HIGH | Single-process architecture prevents multiple connections |

---

*"A house built on sand will fall. A house built on rock takes longer to build, but it stands forever."*

#architecture #prd #sovran-v2 #rebuild
