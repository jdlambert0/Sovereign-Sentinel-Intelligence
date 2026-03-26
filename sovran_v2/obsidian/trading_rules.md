---
title: Sovran V2 - Trading Rules & Decision Framework
updated: 2026-03-26T21:00:00Z
type: trading-rules
---

# Sovran V2 Trading Rules & Decision Framework

## Core Philosophy

**Kaizen-Driven Profitability:** Continuous, measurable improvement through root cause analysis and parameter adaptation. Success is not perfection in one trade - it's consistent edge capture across many trades.

**Risk-First Mindset:** Capital preservation > opportunity maximization. The account must survive to improve.

## Entry Rules

### Signal Requirements (10-Component Conviction Score)

1. **Flow Bias (60s window):** Buy/sell aggressor ratio
2. **Cumulative Flow:** Directional accumulation over session
3. **Bar Trend:** 1-min bar slope over 10 bars minimum
4. **Momentum:** Percentage price change
5. **ATR:** Volatility regime classification
6. **VWAP Position:** Price above/below volume-weighted average
7. **Trade Acceleration:** Rate of change in trade count
8. **Equity Consensus:** Cross-contract correlation check
9. **Regime Strength:** Trending vs ranging vs volatile
10. **Session Phase:** Time-of-day multiplier (0.5× to 1.2×)

### Conviction Thresholds

- **First trade:** ≥ 60
- **After loss:** ≥ 65
- **High conviction (2x size):** ≥ 80

### Hard Gates (Instant Rejection)

- **Regime = unknown or volatile:** conviction → 0 (BLOCK)
- **Bars formed < 10:** conviction → 0 (BLOCK)
- **Flow/bars conflict:** If flow and bar trend strongly disagree → conviction → 0
- **Spread > 4 ticks:** Too wide for micro futures
- **Outside trading hours (8am-4pm CT):** conviction → 0
- **V5 OFI Z-Score < 1.5:** Institutional flow too weak (BLOCK)
- **V5 VPIN < 0.55:** Probability of informed trading too low (BLOCK)

### Time-of-Day Session Phases

| Phase | Hours (CT) | Multiplier | Notes |
|-------|-----------|------------|-------|
| Overnight | 12am-7am | 0.5× | Thin market, high noise |
| Premarket | 7am-8am | 0.7× | Warming up |
| US Open | 8am-10am | 1.0× | High volume, volatile |
| **US Core** | 10am-2pm | **1.2×** | **BEST for flow trading** |
| US Close | 2pm-4pm | 0.9× | End-of-day moves |
| Evening | 4pm-12am | 0.5× | Thin again |

**Banned Phase (V5, currently disabled):** 12:30pm-2:00pm CT - lunch chop

## Exit Rules (Kaizen Phase 1 - Eliminate Waste)

### Partial Take-Profit
- **Trigger:** MFE ≥ 0.6× SL_ticks
- **Action:** Close 50% of position, move SL to breakeven + 2 ticks
- **Remaining 50%:** Trails freely toward TP

### Trailing Stop
- **Activation:** MFE ≥ 0.5× SL_ticks (Phase 1 improvement from 1.0×)
- **Offset:** 8 ticks for base regime, adaptive by regime profile
- **Breakeven lock:** After partial TP, SL moves to entry + 2 ticks

### Minimum Hold Time
- **120 seconds** before any trailing or partial TP logic activates
- Prevents noise exits on scalp entries

### Regime-Adaptive Profiles (Phase 2 - Level the Flow)

| Regime | SL Multiplier | TP Multiplier | Trail Offset | Trail Activation |
|--------|---------------|---------------|--------------|------------------|
| Trending | 2.0× ATR | 5.0× ATR | 6 ticks | 0.4× SL |
| Ranging | 1.5× ATR | 2.5× ATR | 4 ticks | 0.3× SL |
| Volatile | BLOCKED | BLOCKED | N/A | N/A |
| Unknown | BLOCKED | BLOCKED | N/A | N/A |

## Position Sizing (Phase 2 - Level the Flow)

- **Base size:** 1 contract
- **High conviction boost:** 2 contracts if:
  - Conviction ≥ 80
  - No other open positions
  - Rolling win rate > 35% (last 20 trades)

## Risk Limits

### Per-Trade
- **Max position size:** 2 contracts (conviction-based)
- **Max SL distance:** 3.0× ATR (adaptive)
- **Min R:R ratio:** 1:1 (partial TP ensures this)

### Per-Session
- **Max daily loss:** $500 (hard stop)
- **Max trades:** 8
- **Circuit breaker:** 3 consecutive losses → 5-min pause
- **Trade cooldown:** 90 seconds between entries

### Per-Account
- **Trailing drawdown:** $4,500 from high-water mark
- **Max concurrent positions:** 2
- **Correlation penalty:** If 2+ equity indices open, reduce conviction

## Kaizen Self-Correction (Phase 4 - Continuous Flow)

After each trade close, the KaizenEngine adjusts parameters:

### If capture ratio < 0.3 (gave back profits):
- Trail activation multiplier ×= 0.92 (tighter)

### If MFE < 0.3× SL (bad signal):
- Min conviction threshold += 1 (higher bar)

### If stopped out in < 60s (noise):
- SL multiplier ×= 1.05 (wider stops)

### If winning trade:
- Slowly relax params toward defaults (×= 1.01 toward 1.0)

## Market Selection Priority

Based on 14-trade history:

1. **MCL (Crude Oil):** 1 win, $1.00/tick, clean trends → **HIGH PRIORITY**
2. **MGC (Gold):** $1.00/tick, good range → **MEDIUM PRIORITY**
3. **MES/MNQ (Equity Indices):** $1.25-0.50/tick, all losses → **LOW PRIORITY**
4. **M2K (Russell 2000):** $0.50/tick, mixed → **MEDIUM PRIORITY**
5. **MYM (Dow):** $0.50/tick, limited data → **MEDIUM PRIORITY**

## Decision Framework (For External LLMs via IPC)

When responding to IPC request files:

1. **Read market snapshot** (VPIN, OFI, regime, flow, bars)
2. **Check hard gates** - if any fail, return `"no_trade"`
3. **Evaluate thesis** - does the setup align with known edges?
4. **Estimate R:R** - stop distance vs target distance in POINTS
5. **Assign conviction** - 0-100, must be ≥ 70 to trade
6. **Write response** - JSON with signal, conviction, thesis, SL/TP

**Conservative bias:** When in doubt, `"no_trade"` is ALWAYS valid. Preserving capital is more important than catching every move.

## Key Lessons from 14 Trades

1. **Exit management > signal quality** - System found direction (55-60% MFE > 0) but captured nothing
2. **Trail at 1.0× SL was too wide** - Fixed in V4 to 0.5×
3. **100% position to SL/TP = waste** - Fixed with partial TP in V4
4. **Regime=unknown is blind** - Now hard blocked
5. **Flow ≠ trend direction** - Buy flow in downtrend = retail dip-buying, not accumulation
6. **Crude oil (MCL) showed best edge** - Highest tick value, cleanest trends
7. **< 10 bars = noise** - Regime detector needs 10 min of data

## Verification Metrics (What "Profitable" Means)

- **Win rate ≥ 40%** - At least 2 wins per 5 trades
- **Profit factor ≥ 1.5** - Winners 50% larger than losers
- **Avg capture ratio ≥ 0.5** - Hold at least 50% of MFE
- **Trail activation rate ≥ 50%** - Half of trades reach 0.5× SL MFE
- **Drawdown < $4,500** - Account survives combine rules

## Last Updated

2026-03-26 21:00 UTC by KAI (Claude Code)
Reflects V4 Kaizen Edition rules + V5 OFI/VPIN gates
