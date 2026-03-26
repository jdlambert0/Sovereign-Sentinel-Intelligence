# Hunter Alpha Stress Test Plan
## 10-Turn Autonomous Trading Test

**Date:** 2026-03-18  
**Status:** IN PROGRESS  
**Purpose:** Stress test Sovran to unveil bugs and performance issues

---

## Overview

**Who:** Hunter Alpha (AI Trader)  
**Memory:** Obsidian Vault  
**Duration:** 10 turns (~15 seconds each)  
**Goal:** Validate trading system + learning loop

---

## Per-Turn Protocol

```
┌─────────────────────────────────────────────────────────────┐
│ TURN START                                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. VERIFY REALTIME DATA (BUG TEST)                         │
│    - Check: last_price, bid, ask, timestamp                 │
│    - Log: data freshness (stale > 30s = BUG)               │
│    - Test: WebSocket connection status                      │
├─────────────────────────────────────────────────────────────┤
│ 2. HUNTER ALPHA ANALYSIS                                    │
│    - Analyze market conditions                               │
│    - Generate signal (BUY/SELL/WAIT)                        │
│    - Record: reasoning, hypothesis being tested            │
├─────────────────────────────────────────────────────────────┤
│ 3. IF TRADE SIGNAL → EXECUTE TRADE                          │
│    ├── Place atomic bracket order (WORKING ✅)                │
│    ├── Log: entry, SL, TP, size, order_id                   │
│    ├── Verify brackets attached                              │
│    ├── Test: order placement latency                         │
│    └── Test: position tracking accuracy                      │
├─────────────────────────────────────────────────────────────┤
│ 4. RESEARCH LEARNING PLAN                                   │
│    - Hunter Alpha follows curiosity                          │
│    - Search relevant patterns from Learnings/                │
│    - Document: what was researched, why relevant            │
├─────────────────────────────────────────────────────────────┤
│ 5. LOG TO OBSIDIAN (MEMORY)                                 │
│    ├── Turn log: reasoning + research + outcome              │
│    ├── Trade log: entry/exit with full reasoning            │
│    ├── Performance metrics: latency, errors                 │
│    └── Update indices for AI searchability                   │
├─────────────────────────────────────────────────────────────┤
│ 6. PERFORMANCE METRICS                                      │
│    - WebSocket: reconnect count, error count                │
│    - Order latency: time to fill                            │
│    - Memory: usage trend                                    │
│    - Bugs: any anomalies logged                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Memory Structure

### File Locations

| Type | Location | Purpose |
|------|----------|---------|
| **Turn Logs** | `Trades/2026-03-18/turn_XXX.md` | Each turn's full analysis |
| **Trade Logs** | `Trades/YYYY-MM-DD/*.md` | Individual trade documentation |
| **Hunter Thoughts** | `Hunter_Alpha/thoughts/YYYY-MM-DD.md` | Reasoning separate from trades |
| **Learnings** | `Learnings/by_pattern/*.md` | Searchable insights |
| **Indices** | `*.json` | AI-searchable cross-references |

### Naming Convention

```
turn_001_market_bullish_vpin_high.md
turn_002_trade_LONG_entry_50pts.md
```

---

## Data Captured Per Turn

### 1. Market State
```markdown
| Metric | Value | Timestamp |
|--------|-------|-----------|
| Last Price | $24,XXX.XX | HH:MM:SS |
| Bid | $24,XXX.XX | HH:MM:SS |
| Ask | $24,XXX.XX | HH:MM:SS |
| Spread | X ticks | HH:MM:SS |
| VPIN | 0.XX | - |
| Z-Score | X.XX | - |
```

### 2. Hunter Alpha Decision
```markdown
**Signal:** BUY/SELL/WAIT
**Confidence:** 0.XX
**Hypothesis:** What I'm testing with this trade
**Reasoning:** Why I think this will work
```

### 3. Trade Execution (if signal)
```markdown
| Field | Value |
|-------|-------|
| Order ID | XXXXXX |
| Entry | $24,XXX.XX |
| SL | $24,XXX.XX |
| TP | $24,XXX.XX |
| Size | X contracts |
| Fill Time | XXms |
| Brackets Attached | YES/NO |
```

### 4. Research Notes
```markdown
**Pattern Searched:** [e.g., VPIN reversal patterns]
**Learnings Found:** [relevant insights from Obsidian]
**Curiosity Trail:** Why I looked this up
```

### 5. Bug/Performance Report
```markdown
**WebSocket Errors:** X
**Order Latency:** XXms avg
**Position Sync:** MATCH/MISMATCH
**Memory Usage:** XX MB
**Anomalies:** [any issues found]
```

---

## Bug/Performance Tests

### 1. WebSocket Stability
| Check | Expected | Bug Indicator |
|-------|----------|---------------|
| Connection count | 1 | >1 = reconnect loop |
| Error rate | <5% | >5% = unstable |
| Data gap | <1s | >1s = stale data |

### 2. Order Placement Latency
| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Order → Fill | <500ms | 500-1000ms | >1000ms |
| SL/TP attached | <1s | 1-3s | >3s |
| Position sync | <2s | 2-5s | >5s |

### 3. Position Tracking Accuracy
| Check | Expected | Bug Indicator |
|-------|----------|---------------|
| Entry price match | Exact | Off by >1 tick |
| SL/TP visible | YES | NO or wrong price |
| Position size | Matches order | Mismatch |

### 4. Memory Usage
| Check | Target | Warning | Critical |
|-------|--------|---------|----------|
| RAM usage | <200MB | 200-500MB | >500MB |
| Growth rate | 0 | Any growth | >10MB/turn |

---

## Research Query Strategy

Hunter Alpha follows curiosity based on:

### Pattern Recognition
- "VPIN spiked recently - what did I learn about VPIN reversals?"
- "Z-score is extreme - what patterns exist for Z-score trades?"
- "Spread is wide - any learnings about spread conditions?"

### Time-of-Day
- "It's power hour - what do learnings say about this period?"
- "NY open set up - any edge at open?"

### Trade Outcome
- "Last trade was winner - what worked?"
- "Last trade was loser - what failed?"

### Hypothetical Curiosity
- "What if I tried X?"
- "Has this pattern ever worked?"
- "What does the data say about Y?"

---

## 10-Turn Test Schedule

| Turn | Focus | What We Learn |
|------|-------|---------------|
| 1 | **Setup** | System boots, connects, first decision |
| 2 | **Simple Trade** | BUY signal, place order, verify brackets |
| 3 | **Research Loop** | Hunter follows curiosity, logs learnings |
| 4 | **Sell Signal** | SHORT trade, verify direction handling |
| 5 | **Wait Signal** | No trade, verify decision not to trade |
| 6 | **Fast Market** | High volatility, test latency |
| 7 | **Recovery** | After loss, verify system continues |
| 8 | **Pattern Trade** | Hunter uses learning from Turn 3 |
| 9 | **Stress** | Rapid decisions, multiple signals |
| 10 | **Wrap Up** | Final metrics, bugs found, recommendations |

---

## Success Criteria

### Must Pass (Bug Detection)
- [ ] WebSocket connects without error loop
- [ ] Order places with SL/TP attached
- [ ] Position tracks correctly
- [ ] Memory writes without failure
- [ ] No crashes or hangs

### Performance Targets
- [ ] Order latency <1s average
- [ ] Data refresh <2s
- [ ] Memory stable (no leak)
- [ ] 10/10 turns completed

### Learning Validation
- [ ] Hunter Alpha reasons through trades
- [ ] Research queries return relevant learnings
- [ ] Full reasoning logged to Obsidian
- [ ] Trade outcomes recorded

---

## Files Created

### During Test
- `Trades/2026-03-18/turn_001.md` → `turn_010.md`
- `Hunter_Alpha/thoughts/2026-03-18.md`
- `Trades/2026-03-18/_index.json`

### After Test
- `Trades/2026-03-18/STRESS_TEST_REPORT.md`
- `Bug_Reports/stress_test_bugs.md`

---

## References

- `SOVRAN_AUTONOMOUS_TRADING_SUCCESS.md` - Bracket order verification
- `LEARNING_MODE_and_Launch_Guide.md` - LEARNING_MODE flag
- `1k_Day_Learning_Plan.md` - Learning priorities
- `Learnings/20260317_164125_unified_learning_plan.md` - Unified learning plan

---

*Last Updated: 2026-03-18*
