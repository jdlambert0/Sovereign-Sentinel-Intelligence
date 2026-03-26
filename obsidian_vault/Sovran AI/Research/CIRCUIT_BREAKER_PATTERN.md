# Circuit Breaker Pattern - Sovran AI Trading System

**Date**: 2026-03-19  
**Purpose**: Document the 4 circuit breakers protecting Hunter Alpha from losses

---

## Overview

The circuit breaker pattern prevents catastrophic losses by stopping trading when certain danger thresholds are met. Sovran implements **4 independent circuit breakers** that can trigger a trading halt.

---

## Circuit Breaker 1: Runtime Circuit Breaker

**Purpose**: Prevent runaway processes that consume resources or trade indefinitely

### Configuration
```python
VORTEX_MAX_RUNTIME_SECONDS = 0  # 0 = unlimited, set to X to stop after X seconds
```

### Behavior
- Process runs until market close or manual stop
- Originally set to 120 seconds (TOO AGGRESSIVE - caused exit code 120)
- **FIXED**: Set to 0 (unlimited runtime)

### Why Exit Code 120 is NOT a Crash
- Exit code 120 = Windows SIGTERM signal (graceful shutdown)
- Process received termination signal, not crashed
- Caused by `VORTEX_MAX_RUNTIME_SECONDS=120` forcing shutdown after 2 minutes
- **Solution**: Set to 0 for unlimited runtime

---

## Circuit Breaker 2: L2 Staleness Circuit Breaker

**Purpose**: Prevent entries when market data is stale/unreliable

### Configuration
```python
MAX_CUMULATIVE_STALENESS_SECONDS = 60  # Stop if feed is stale for 60+ cumulative seconds
```

### Behavior
- Tracks cumulative time market data feed is disconnected/stale
- If L2 data missing for 60+ seconds total, block new entries
- Allows existing positions to close normally
- Resets counter when fresh data arrives

### Why It Matters
- Stale data = wrong prices = bad entries
- Prevents trading on outdated information
- Protects against data feed failures

---

## Circuit Breaker 3: Volatility Circuit Breaker

**Purpose**: Prevent entries during extreme volatility (news events, flash crashes)

### Configuration
```python
VOLATILITY_LOCK_SECONDS = 120  # No entries for 2 minutes after ATR surge
```

### Behavior
- Monitors ATR (Average True Range) for sudden spikes
- If volatility surges beyond threshold, lock out entries for 120 seconds
- Allows volatile period to stabilize before continuing
- Protects against adverse fills during chaotic moves

### Why It Matters
- High volatility = wider spreads = worse fills
- News events can cause violent moves against positions
- 2-minute cooldown allows market to find equilibrium

---

## Circuit Breaker 4: PNL Circuit Breaker

**Purpose**: Daily loss limit to prevent exceeding risk tolerance

### Configuration
```python
DAILY_LOSS_LIMIT = -500  # Stop trading if daily P&L drops below -$500
```

### Behavior
- Tracks realized + unrealized P&L for the trading day
- If total P&L falls below -$500, halt all trading
- Positions may remain open to close naturally
- Resets at start of new trading day

### Why It Matters
- $500/day loss limit protects capital
- Prevents revenge trading after losses
- Enforces discipline even when AI "feels confident"

---

## Summary Table

| Circuit Breaker | Trigger | Action |
|-----------------|---------|--------|
| Runtime | X seconds elapsed | Stop process (set to 0) |
| L2 Staleness | 60+ seconds stale | Block new entries |
| Volatility | ATR spike detected | Lock 120 seconds |
| PNL | Daily loss < -$500 | Halt all trading |

---

## How They Work Together

```
                    ┌─────────────────────────────┐
                    │   Market Open / New Entry   │
                    │         Requested           │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  Circuit Breaker Check      │
                    └─────────────┬───────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Runtime OK?     │    │ L2 Data Fresh?  │    │ Volatility OK?  │
│ (Runtime = 0)   │    │ (<60s stale)    │    │ (No ATR spike)  │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────┬───────────┴──────────────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  LLM Decision       │
         │  (Groq/HunterAlpha) │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  PNL Check          │
         │  (Daily > -$500)    │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Execute Trade      │
         │  (Atomic Bracket)   │
         └─────────────────────┘
```

---

## Monitoring

All circuit breaker states are logged and can be checked via:

```python
# Check circuit breaker status
from sovran_ai import get_circuit_breaker_status
status = get_circuit_breaker_status()
print(status)
# {'runtime': 'ok', 'l2_staleness': 5, 'volatility': 'ok', 'pnl': -125.50}
```

---

## References

- Original implementation: `C:\KAI\armada\sovran_ai.py`
- Configuration: `C:\KAI\vortex\.env`
