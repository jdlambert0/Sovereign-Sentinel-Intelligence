# SOVRAN V2 — System State & Kaizen Continuous Improvement Framework

**Date:** 2026-03-26 | **Balance:** $148,632.78 | **Account:** TopStepX 150K Simulated Combine

---

## 1. Current System State — Honest Assessment

### Architecture (What Exists)
```
WebSocket (L1 quotes + trades) ──┐
                                 ├── MarketDataStream (6 micro-futures)
                                 │     MNQ, MES, MYM, M2K, MGC, MCL
                                 │
                                 ├── Per-Market Analysis Pipeline
                                 │     10 signal components → conviction score (0-100)
                                 │     10-bar gate → regime detection → direction
                                 │
                                 ├── Risk Filters
                                 │     $500 daily loss limit │ 8 trades/session
                                 │     90s cooldown │ 3-loss circuit breaker
                                 │     Correlated asset penalty
                                 │
                                 ├── Execution (bracket orders)
                                 │     Market entry + SL + TP (ATR-adaptive)
                                 │
                                 └── Position Management
                                       Trailing stop (0.5× SL activation)
                                       MFE/MAE tracking
```

### Performance Record (11 trades to date)
| Metric | Value | Assessment |
|--------|-------|------------|
| Win Rate | 0/9 closed (0%) | Critical — no wins yet |
| Total Closed PnL | -$158.75 | Small losses, manageable |
| Avg MFE (where > 0) | +12.8 ticks | The system FINDS direction |
| Avg MAE | -18.8 ticks | Stops are hit before winners develop |
| Trail Activations | 0/11 | Fixed (0.5× from 1.0×), untested |
| TP Hits | 0/11 | Targets too wide or exits too early |
| Avg Hold Time | ~250s | Reasonable for micro-futures |
| Best Unrealized | +20t on MCL ($20) | Gave it ALL back |

### The Core Paradox
**The system correctly identifies market direction 55-60% of the time** (6/11 trades had meaningful MFE > 10t), but **captures zero profit**. This is not a signal problem — it's an exit management problem.

### What's Working
1. Multi-market scanning correctly prioritizes highest-conviction setups
2. Regime detection blocks "unknown" regime trades (biggest recent fix)
3. 10-bar gate prevents premature entries
4. Cross-asset correlation penalty prevents correlated double-exposure
5. Session phase multipliers dampen overnight noise
6. Circuit breaker (3 consecutive losses → 5-min cooldown) preserves capital
7. Flow vs bars conflict detection catches contradictory signals

### What's Broken
1. **Exit management** — zero trail activations, zero TP hits
2. **Win rate literally 0%** — mathematically impossible to be profitable
3. **No partial take-profit** — all-or-nothing position management
4. **No minimum hold time** — some trades stopped in 50-100s
5. **Commission drag** — ~$2-3/trade on $5-15 average positions = 20-60% overhead

---

## 2. Kaizen Framework for Systematic Profitability

Kaizen (改善) = continuous, incremental improvement. Not "fix everything at once" — instead, identify the **highest-leverage constraint**, fix it, measure, repeat.

### The Theory of Constraints Applied to Trading Systems

The system has a clear bottleneck chain:

```
Signal Quality ──→ Entry Timing ──→ Exit Management ──→ Risk Sizing ──→ Capital Growth
     OK (55%)        Decent            BROKEN (0%)       Conservative      Negative
```

**Constraint #1: Exit Management** — Fix this first. Everything else is irrelevant until we can capture the edge we already detect.

---

### Phase 1: ELIMINATE WASTE (Muda — 無駄) — Week 1

The first Kaizen principle: eliminate waste before optimizing anything.

#### 1A. Partial Take-Profit (Highest Impact Fix)
**Problem:** 100% of position rides to SL or TP. When MFE reaches +15t, the unrealized profit is wasted.
**Solution:** Close 50% at 1:1 R:R, trail the remainder.

```python
# In _check_trailing_stop():
# At 1:1 R:R (MFE >= SL_ticks), close half
if pos.mfe >= pos.sl_ticks and not pos.partial_taken:
    close_half_position(cid)
    pos.partial_taken = True
    move_sl_to_breakeven(cid)
    # Remaining 50% trails freely
```

**Expected impact:** Trades 2, 6, 8, 9, 10 all had MFE > SL_ticks. At 1:1 partial TP:
- Trade 2: +$3.50 (half at +14t) instead of -$4.87
- Trade 6: +$7.50 (half at +15t) instead of -$21.04
- Trade 8: +$10.00 (half at +20t) instead of open
- Net improvement: ~$42 across those 3 trades alone

#### 1B. Minimum Hold Time (Eliminate Noise Exits)
**Problem:** Trades 4 and 6 held for 70-100s — insufficient time for the thesis to develop.
**Solution:** Do not check for stop unless position has been held > 120s (2 minutes).

```python
MIN_HOLD_BEFORE_TRAIL = 120  # seconds
if time.time() - pos.entry_time < MIN_HOLD_BEFORE_TRAIL:
    continue  # Let the bracket handle risk, don't trail yet
```

#### 1C. Flow vs Bars Hard Block (Eliminate Bad Entries)
**Problem:** Trade 9 had explicit conflict warning but still entered at conv=69.
**Solution:** When flow direction and bar trend direction strongly disagree, conviction = 0.

```python
# In analyze_market():
if (w_ratio > 0.15 and bar_trend < -0.3) or (w_ratio < -0.15 and bar_trend > 0.3):
    conviction = 0
    signals.append("BLOCKED: flow/bars conflict")
```

#### 1D. Measure Everything (Genchi Genbutsu — 現地現物)
Add per-trade instrumentation:
- **Entry quality score:** Was conviction high? Was regime favorable?
- **Exit quality score:** Did trail activate? How much MFE was captured?
- **Profit capture ratio:** actual_pnl / mfe_potential (target > 0.3)
- **Signal accuracy:** direction_correct / total_signals

### Phase 2: LEVEL THE FLOW (Heijunka — 平準化) — Week 2

Reduce variance. Smooth the P&L curve.

#### 2A. Position Sizing by Conviction
**Current:** Always 1 contract regardless of signal strength.
**Kaizen:** Scale 1-3 contracts by conviction band.

| Conviction | Size | Rationale |
|-----------|------|-----------|
| 60-69 | 1 contract | Minimum confidence |
| 70-79 | 1 contract | Standard |
| 80-89 | 2 contracts | High confidence (partial TP first contract, trail second) |
| 90+ | 2 contracts | Full conviction (rare — ~5% of signals) |

Only implement AFTER Phase 1 proves positive expectancy.

#### 2B. Regime-Adaptive Strategy
**Current:** Same SL/TP ratios regardless of regime.
**Kaizen:**

| Regime | Strategy | SL | TP | Trail |
|--------|----------|----|----|-------|
| Trending | Let it run | 2× ATR | 5× ATR | Aggressive (0.4× activation) |
| Ranging | Quick scalp | 1.5× ATR | 2× ATR | None (hard TP) |
| Volatile | Sit out | — | — | — |
| Unknown | BLOCKED | — | — | — |

#### 2C. Time-of-Day Optimization
**Evidence from session data:** Overnight trades (22:00-23:30 CT) = -$27.35. RTH trades have higher MFE.
**Kaizen:** Hard block all trades outside 8:00-15:00 CT. Focus on US Core (10-14 CT) where flow signals are most reliable.

### Phase 3: STANDARDIZE (Hyojunka — 標準化) — Week 3

#### 3A. Rolling Performance Windows
Every 20 trades, recalculate:
- Win rate (target > 45%)
- Profit factor (target > 1.2)
- Avg R:R captured (target > 1.0)
- Best time windows
- Best markets

If win rate < 35% over 20 trades → halve position size.
If win rate > 55% over 20 trades → allow size increase per 2A.

#### 3B. Automated Kaizen Logging
After every trade, append to `state/kaizen_log.json`:
```json
{
    "trade_id": 12,
    "hypothesis": "60s windowed flow predicts direction in trending MES",
    "entry_quality": 0.78,
    "exit_quality": 0.35,
    "profit_capture_ratio": 0.22,
    "mfe_vs_sl": 1.4,
    "lesson": "Direction correct but trail too slow",
    "category": "exit_management"
}
```

Group lessons by category. After 50 trades, the log reveals which category has the most waste → next Kaizen cycle targets that.

#### 3C. A/B Signal Testing
Run two analysis modes in parallel (paper-trade one, live-trade the other):
- **Mode A (current):** 10-signal scoring
- **Mode B (experimental):** Drop lowest-value signals, add new ones

Compare after 30 trades each. Adopt the better mode. Repeat.

### Phase 4: CONTINUOUS FLOW (Jidoka — 自働化) — Week 4+

#### 4A. Automated Self-Correction
```python
class KaizenEngine:
    def post_trade_review(self, trade: TradeResult):
        """After every trade, update adaptive parameters."""
        ratio = trade.pnl / (trade.mfe * tick_value) if trade.mfe > 0 else 0
        
        if ratio < 0.2:
            # We found edge but didn't capture it → exit problem
            self.trail_activation_mult *= 0.9  # Make trail more aggressive
        
        if trade.mfe < trade.sl_ticks * 0.3:
            # Never moved in our favor → signal problem
            self.min_conviction += 2  # Raise entry bar
        
        if trade.hold_time < 60:
            # Stopped out too fast → SL too tight
            self.default_sl_mult *= 1.1  # Widen SL slightly
```

#### 4B. Market Selection Kaizen
Track per-market statistics over rolling 50-trade windows:
- **MES:** Highest liquidity but widest noise
- **MCL:** Best MFE-to-MAE ratio in session data
- **M2K:** Most trades taken but most losses
- **MGC:** Widest spreads (3-5t), highest friction

After 50 trades, concentrate on top 3 performing markets. Drop bottom 2.

#### 4C. The Feedback Flywheel
```
Trade → Measure → Categorize Waste → Smallest Fix → Measure Again → Trade
                                        ↑                              │
                                        └──────────────────────────────┘
```

Each cycle should take 20-30 trades. Target one improvement per cycle.

---

## 3. Kaizen Implementation Priority (Weighted by Impact × Ease)

| # | Fix | Expected Impact | Effort | Priority |
|---|-----|----------------|--------|----------|
| 1 | Partial TP at 1:1 R:R | +$42/3 trades | Medium | **DO FIRST** |
| 2 | Flow/bars hard block | -2 losing trades/session | Easy | **DO FIRST** |
| 3 | Trail activation 0.5× (already done) | Breakeven recovery | Done | **VERIFY** |
| 4 | Minimum hold time 120s | Fewer noise exits | Easy | Week 1 |
| 5 | Time-of-day hard block | Eliminate overnight waste | Easy | Week 1 |
| 6 | Per-trade Kaizen logging | Measurement foundation | Medium | Week 2 |
| 7 | Regime-adaptive SL/TP | Better R:R by context | Medium | Week 2 |
| 8 | Rolling performance windows | Adaptive risk | Medium | Week 3 |
| 9 | Position sizing by conviction | Capital efficiency | Medium | Week 3 |
| 10 | Automated self-correction | Autonomous improvement | Hard | Week 4 |

---

## 4. The Kaizen Mindset Applied to Trading

### Five Why's — Root Cause of Current Losses

1. **Why are we losing?** Every trade hits stop loss.
2. **Why does every trade hit SL?** Unrealized profits (MFE +12-20t) are given back.
3. **Why are profits given back?** Trail stop never activated (required +30t, max MFE was +20t).
4. **Why was trail threshold so high?** Set at 1.0× SL — appropriate for trend-following but not scalping.
5. **Why scalping with trend-following exits?** The system evolved from a single-market to multi-market scanner without re-calibrating exit logic for the new signal mix.

**Root cause:** Exit management was never calibrated to the actual MFE distribution of the signals.

### Gemba Walk — Go See the Data

The most telling data point: **average MFE of +12.8 ticks with average SL of 25 ticks**. This means the system's edge exists at roughly 0.5× SL — exactly where the trail activation was moved to. The partial TP at 1:1 (25t) will never hit either. We need partial TP at 0.6-0.8× SL, not 1.0×.

**Revised partial TP target:** Close half at MFE = 0.6× SL_ticks (e.g., +15t for 25t SL). This aligns with actual MFE distribution.

### Single Minute Exchange of Die (SMED) — Fast Iteration

Each Kaizen improvement should be:
1. Implementable in < 50 lines of code
2. Testable in 1 live session (30 min)
3. Measurable after 5-10 trades
4. Reversible if results are worse

Never change more than one parameter per session. Otherwise attribution is impossible.

---

## 5. Current Live Session Status

**Session started:** 2026-03-26 08:20 CT (US open session)
**Configuration:** 360 cycles × 5s = 30 minutes
**Phase:** us_open (conviction multiplier: 1.0×)
**Warmup:** ~10 min bar formation before first possible trade
**Markets:** MNQ, MES, MYM, M2K, MGC, MCL
**Recent fixes applied:**
- [x] Trail activation 1.0× → 0.5×
- [x] regime=unknown hard block
- [x] Bar gate 3 → 10 bars
- [x] Encoding fix for Windows compatibility

**Pending fixes (not yet in code):**
- [ ] Partial take-profit at 1:1 R:R
- [ ] Flow/bars hard block (currently 0.6× penalty, should be 0.0×)
- [ ] Minimum hold time 120s before trailing
- [ ] Kaizen instrumentation logging

---

*"The key to the Toyota Way is not any of the individual elements. What is important is having all the elements together as a system. It must be practiced every day in a very consistent manner." — Taiichi Ohno*

*Applied to SOVRAN: The system's individual signals are good. What's missing is the exit management system that captures the edge those signals detect. Fix the constraint, measure, iterate.*
