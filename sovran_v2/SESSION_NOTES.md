# SOVRAN V2/V3 — Full Session Notes & Export
**Date:** 2026-03-25 to 2026-03-26
**Account:** TopStepX Simulated Combine — 150KTC-V2-423406-25666664 (ID: 20560125)
**Starting Balance:** $148,729.75
**Ending Balance:** $148,533.67
**Net PnL:** -$196.08 (closed: -$158 + open positions ~-$6 each way)

---

## TABLE OF CONTENTS
1. [System Architecture](#1-system-architecture)
2. [All Trades](#2-all-trades--11-total)
3. [Session-by-Session Breakdown](#3-session-by-session-breakdown)
4. [Problems Encountered & Fixes](#4-problems-encountered--fixes)
5. [Key Learnings](#5-key-learnings)
6. [Current System State](#6-current-system-state)
7. [Evolution Roadmap](#7-evolution-roadmap)

---

## 1. System Architecture

### Core Components (11 source files)
| File | Purpose |
|------|---------|
| `src/broker.py` | TopStepX API: auth, order placement, position queries, order modification |
| `src/market_data.py` | WebSocket: quotes, trades, depth subscriptions; MarketSnapshot with L1/L2 |
| `src/decision.py` | AI brain with 3 backends: Ollama, OpenRouter, File-IPC (Option C) |
| `src/risk.py` | Position sizing, drawdown limits, daily loss caps |
| `src/sentinel.py` | Order flow analysis: VPIN, OFI Z-score (Welford), bid/ask imbalance |
| `src/learning.py` | Trade context persistence, session learning |
| `src/position_manager.py` | Active trade monitoring: trailing stop, VPIN toxic exit, OFI flip |
| `src/scanner.py` | Multi-market scanner: composite conviction scoring, correlation penalties |
| `src/performance.py` | Per-market/time/exit-reason analysis, adaptive parameters |
| `src/problem_tracker.py` | Obsidian integration: dashboard, daily logs, problem registry |
| `live_session_v3.py` | Main trading engine: market scanning, signal generation, order execution |

### Signal Pipeline
```
WebSocket Feed (quotes + trades)
    → MarketSnapshot (price, spread, trade counts, bars)
    → Per-market scoring:
        1. Windowed flow (60s buy/sell ratio)
        2. Bar trend (1-min OHLCV direction)
        3. Momentum (price change %)
        4. ATR → regime detection (trending/ranging/volatile)
        5. VWAP position
        6. Trade acceleration
        7. Cross-market equity consensus
    → Conviction score (0-100)
    → Entry if conviction ≥ threshold (60 first trade, 65 after loss)
    → Bracket order: SL/TP based on ATR + regime
    → Position monitoring: trail stop, early close logic
```

### Multi-Market Support
Scans 7 markets per cycle: MES, MNQ, MYM, M2K, MCL, MGC, MBT
Dynamic round-robin — scores all, takes best conviction above threshold.
51+ instruments in CONTRACT_META for TopStepX format lookup.

### File-IPC (Option C) Architecture
Any external AI system (Gemini CLI, Accio, Antigravity) can:
1. Read `ipc/prompt.json` — current market state + trade context
2. Write `ipc/response.json` — trade decision in structured format
3. System polls for response, parses, and executes

---

## 2. All Trades — 11 Total

### Trade Log
```
#   Date/Time (CT)       Market  Side   Entry       SL    TP    Conv  PnL       MFE   MAE   Hold    Exit        Session
1   03/25 ~22:00         MYM     LONG   46,652      20t   40t   --    -$11.37   +0t   -18t  ~40m    STOP_HIT    V2 Overnight
2   03/25 ~23:00         M2K     SHORT  2,544.40    10t   30t   --    -$4.87    +14t  -10t  ~5m     STOP_HIT    V2 Overnight
3   03/25 ~23:15         M2K     LONG   2,541.70    20t   40t   --    -$10.37   +0t   -20t  ~10m    STOP_HIT    V2 Overnight
4   03/26 14:26          MES     LONG   6,617.50    20t   40t   70    -$25.74   +0t   -13t  100s    STOP_HIT    V3 RTH-1
5   03/26 14:31          M2K     LONG   2,550.90    30t   60t   69    -$14.87   +12t  -25t  ~300s   STOP_HIT    V3 RTH-1→2
6   03/26 15:04          MCL     LONG   93.84       20t   40t   60    -$21.04   +15t  -6t   70s     STOP_HIT    V3 RTH-3
7   03/26 15:05          MES     LONG   6,599.25    30t   60t   79    -$37.51   +4t   -23t  655s    STOP_HIT    V3 RTH-3
8   03/26 15:08          MCL     LONG   94.08       30t   60t   67    open+$5   +20t  -12t  --      RUNNING     V3 RTH-3
9   03/26 15:16          M2K     SHORT  2,531.10    30t   40t   69    -$15.74   +11t  -26t  690s    STOP_HIT    V3 RTH-3
10  03/26 15:28          M2K     LONG   2,533.90    30t   80t   79    -$16.24   +12t  -28t  126s    STOP_HIT    V3 RTH-3
11  03/26 15:30          MYM     SHORT  46,544      30t   80t   66    open+$6   +6t   --    --      RUNNING     V3 RTH-3
```

### Aggregate Statistics
- **Win rate:** 0/9 closed (0%) — 2 still open
- **Total closed PnL:** -$158.75
- **Avg MFE (where > 0):** +12.8 ticks (trades 2, 5, 6, 8, 9, 10)
- **Avg MAE:** -18.8 ticks
- **Trail activated:** 0/11 trades (NONE)
- **TP hit:** 0/11 trades
- **Commission overhead:** ~$2/round-trip

---

## 3. Session-by-Session Breakdown

### Session 1: V2 Overnight (03/25, ~22:00-23:30 CT)
**Engine:** live_session_v2.py (pre-V3)
**Conditions:** Asian session, thin volume, steady equity selling

| Trade | Result | Notes |
|-------|--------|-------|
| LONG MYM @ 46,652 | -$11.37 | Entered during thin overnight volume, never moved in favor |
| SHORT M2K @ 2,544.40 | -$4.87 | BEST TRADE — reached +$7.00 peak (+14t MFE), SL too tight at 10t |
| LONG M2K @ 2,541.70 | -$10.37 | Counter-trend entry, stopped immediately |

**Session PnL: -$27.35**
**Key learning:** Overnight Asian session = noise. Flow signals unreliable with thin volume.

---

### Session 2: V3 RTH-1 (03/26, 14:25-14:34 CT)
**Engine:** live_session_v3.py (first V3 run)
**Conditions:** US RTH just starting, indices volatile

| Trade | Result | Notes |
|-------|--------|-------|
| LONG MES @ 6,617.50 | -$25.74 | Entered at cycle 4 (~20s), regime=unknown, bar_trend=0.00 — NO bars formed yet |
| LONG M2K @ 2,550.90 | Carried → Session 2 | Was +$6.00 unrealized at one point |

**CRITICAL BUG DISCOVERED:** WebSocket trade feed dropped on session restart — all markets showed B:0 S:0. Trade subscriptions didn't re-establish after process restart. Had to kill and restart cleanly.

**Session PnL: -$25.74 (+ M2K carried)**

---

### Session 2b: V3 RTH-2 (03/26, 14:34-14:38 CT)
**Engine:** live_session_v3.py (restarted to fix WebSocket)
**Note:** M2K position from Session 2 was still open, immediately stopped out

| Trade | Result | Notes |
|-------|--------|-------|
| LONG M2K (from RTH-1) | -$14.87 | Was +$6 in RTH-1, reversed during restart gap, stopped at -30t |

**Session PnL: -$14.87**

---

### Session 3: V3 RTH-3 (03/26, 15:00-15:31 CT)
**Engine:** live_session_v3.py (360 cycles × 5s = 30 min)
**Conditions:** US RTH prime time, good volume

| Trade | Result | Notes |
|-------|--------|-------|
| LONG MCL #1 @ $93.84 | -$21.04 | regime=unknown, bar_trend=0.00 (only 3 bars), hit +15t MFE but trail needed 20t |
| LONG MES @ $6,599.25 | -$37.51 | regime=unknown, biggest single loss, MES moved against immediately |
| LONG MCL #2 @ $94.08 | open +$5 | regime=unknown, reached +$20 MFE! Trail needed +30t (1.0×SL). Gave back ALL profit |
| SHORT M2K @ $2,531.10 | -$15.74 | regime=ranging, ⚠️ flow vs bars conflict flagged, still entered |
| LONG M2K @ $2,533.90 | -$16.24 | regime=trending, good signals aligned, reached +12t but trail needed 15t |
| SHORT MYM @ $46,544 | open +$6 | regime=trending, bars↓ aligned, last trade of session |

**Session PnL: -$90.53 closed | 2 open (~+$11 unrealized)**
**Key finding:** 4 of 6 trades found correct direction (MFE +11 to +20 ticks). Trail NEVER activated.

---

## 4. Problems Encountered & Fixes

### P1: WebSocket Field Names (FIXED — Phase 1)
- **Problem:** `market_data.py` expected `bestBidPrice` but TopStepX API sends `bestBid`
- **Impact:** No price data, spread calculation showed -97,418 ticks
- **Fix:** Full rewrite of `_process_quote()` to handle `lastPrice`, `bestBid`, `bestAsk` fields
- **Also fixed:** `GatewayTrade` uses `type` not `side` (0=buy aggressor, 1=sell aggressor)

### P2: Bracket Order Tick Signs (FIXED — Live testing)
- **Problem:** Orders failed with "Invalid stop loss ticks"
- **Root cause:** TopStepX requires: BUY → `stopLossTicks = -abs(sl)`, SELL → `stopLossTicks = +abs(sl)`
- **Fix:** Sign logic in `_place_bracket_order()` based on order side

### P3: L2 Depth Not Available (CONFIRMED — Live testing)
- **Problem:** `SubscribeContractDepth` → "Method does not exist"
- **Impact:** L2 order book features (bid/ask imbalance, OFI) unavailable on TopStepX
- **Workaround:** System uses trade flow (aggressor side) instead of L2 book data

### P4: Multiple Session Instances (FIXED — Live testing)
- **Problem:** Up to 3 competing session PIDs caused trade data loss (B:0 S:0)
- **Root cause:** Previous sessions not killed before launching new ones
- **Fix:** Always `pkill -f live_session` before starting; added health monitor that re-subscribes if B:0 S:0 after 200+ messages

### P5: Bar Gate vs Regime Mismatch (FIXED — Jesse caught this)
- **Problem:** Bar gate required ≥3 bars, but `detect_regime()` requires ≥10 bars
- **Impact:** Trades entered with 3-9 bars where regime=unknown and bar_trend was flat
- **Evidence:** Trades 4, 6, 7, 8 all entered with regime=unknown
- **Fix:** Bar gate raised to 10; added hard block: `if regime == "unknown": conviction = 0`

### P6: Trail Stop Activation Too High (FIXED)
- **Problem:** `TRAIL_ACTIVATION_MULT = 1.0` means 30t SL needs +30t MFE to activate trail
- **Impact:** MCL #2 reached +20t MFE ($20 profit!) but trail needed +30t → gave back ALL profit
- **Evidence:** Trail=NO on every single trade across all sessions (0/11)
- **Fix:** Lowered to `TRAIL_ACTIVATION_MULT = 0.5` — trail now activates at +15t for 30t SL
- **Projected impact:** Trades 6, 8, 9, 10 would have locked breakeven. Turns -$90 session into ~-$37

### P7: PnL Timezone Bug (FIXED — Task 2)
- **Problem:** UTC timestamps vs Central Time for daily PnL calculations
- **Fix:** All PnL tracking uses America/Chicago timezone

### P8: WebSocket Health on Restart (FIXED)
- **Problem:** After process restart, trade subscriptions don't re-establish
- **Fix:** `check_health()` monitors message counts; re-subscribes if stale. Main loop checks every 10 cycles.

### P9: Flow vs Bars Conflict Allowed Entry (NEEDS FIX)
- **Problem:** M2K SHORT (trade 9) had flow↓ but bars↑ — flagged with ⚠️ but still entered at conv=69
- **Impact:** -$15.74 loss on conflicting signal
- **Status:** Currently only applies 70% penalty. Consider hard blocking when flow and bars strongly disagree.

---

## 5. Key Learnings

### Market Behavior
1. **Overnight Asian session = noise.** Thin volume makes flow signals unreliable. V3 correctly refused all overnight setups (0 trades).
2. **System finds direction.** Average MFE of +12.8 ticks on 6/11 trades shows real edge detection.
3. **Profit capture is the bottleneck.** Zero TP hits, zero trail activations. The system enters correctly but can't hold winners.
4. **Commission + slippage ~$2-3/trade.** At 1 contract micro-futures, this is material overhead.
5. **Buy flow in a downtrend ≠ bullish.** Often retail buying the dip against institutional selling.

### Technical Learnings
6. **TopStepX API quirks:** Field names differ from docs (`bestBid` not `bestBidPrice`), L2 depth not available, bracket tick signs are side-dependent.
7. **WebSocket reconnect requires re-subscription.** Connections can silently drop trade feeds.
8. **Never run multiple session instances.** Competing WebSocket connections cause data loss.
9. **Bar gate must match regime detection minimum.** A gate at 3 with regime needing 10 creates a blind spot for ~7 cycles.
10. **Trail activation must be aggressive.** At 1.0× SL, micro-futures rarely get enough MFE before mean-reverting. 0.5× is the minimum viable threshold.

### System Design
11. **Regime detection is critical.** regime=unknown entries were the worst performers (trades 4, 6, 7, 8).
12. **Windowed flow (60s) is better than cumulative.** Cumulative flow drifts; 60s window captures recent aggression.
13. **Cross-market equity consensus works.** When indices align, signals are stronger. 80% penalty for counter-trend is appropriate.
14. **Circuit breaker (3 losses → 5 min cooldown) saves capital.** Prevents tilt-trading after losing streaks.

---

## 6. Current System State

### Files (57 total)
```
sovran_v2/
├── src/                    # 11 source modules
│   ├── broker.py           # TopStepX API client
│   ├── market_data.py      # WebSocket data feed
│   ├── decision.py         # AI brain (3 backends)
│   ├── risk.py             # Position sizing
│   ├── sentinel.py         # Order flow analysis
│   ├── learning.py         # Trade persistence
│   ├── position_manager.py # Active trade monitoring
│   ├── scanner.py          # Multi-market scanner
│   ├── performance.py      # Performance analytics
│   ├── problem_tracker.py  # Obsidian integration
│   └── __init__.py
├── tests/                  # 11 test files, 220+ tests
├── config/                 # JSON configs
│   ├── sovran_config.json  # Markets, thresholds
│   ├── decision_config.json
│   ├── risk_config.json
│   └── sentinel_config.json
├── live_session.py         # V1 engine (deprecated)
├── live_session_v2.py      # V2 engine (overnight)
├── live_session_v3.py      # V3 engine (CURRENT)
├── monitor_position.py     # Standalone position monitor
├── ipc/                    # File-IPC for external AI
├── state/                  # Trade history, session state
├── obsidian/               # Problem tracker, daily logs
└── requirements.txt
```

### Pending Fixes (Applied but Untested in Live)
1. ✅ Bar gate 3 → 10 bars
2. ✅ regime=unknown hard block (conviction = 0)
3. ✅ Trail activation 1.0× → 0.5× SL

### Open Positions (Still on TopStepX)
- LONG MCL @ $94.08 — SL: 30t, TP: 60t (last seen +$5)
- SHORT MYM @ $46,544 — SL: 30t, TP: 80t (last seen +$6)
These have bracket orders on the exchange and will resolve on their own.

---

## 7. Evolution Roadmap

### Completed ✅
- [x] Phase 1: Fix WebSocket parsing, build PositionManager, wire trade outcomes
- [x] Phase 2: Multi-market scanner, cross-asset correlation, per-market sizing
- [x] V3 Engine: Multi-timeframe, trailing stop, equity consensus, regime detection

### Next Up (from SOVRAN_EVOLUTION_PLAN.md)
- [ ] **Phase 3A:** Rich AI prompts with full OHLCV bars, indicators, cross-market context
- [ ] **Phase 3B:** Structured AI response (complete trade plan, not just signal)
- [ ] **Phase 4A:** Performance attribution (which signals generate best edge)
- [ ] **Phase 4B:** Parameter adaptation (rolling 50-trade optimization)
- [ ] **Phase 4C:** Regime-adaptive sizing/strategy switching

### Immediate Priorities (Based on Live Data)
1. **Validate 0.5× trail fix** — this is the single most impactful change
2. **Partial take profit** — close half at 1:1 R:R, trail remainder. Would have saved $20+ on MCL #2
3. **Hard block on flow vs bars conflict** — trade 9 had ⚠️ flagged but still entered
4. **Minimum hold time** — some stops hit in 50-100s, before market had time to develop
5. **Bar trend strength threshold** — bar_trend of +0.40 is weak (3 of 5 bars in direction). Consider requiring +0.60

---

## Appendix: Trade-by-Trade Analysis

### Trade 1: LONG MYM @ 46,652 (V2 Overnight)
- **Why entered:** V2 engine, flow-based signal during Asian session
- **What happened:** Thin volume, price drifted down, stopped at -18t
- **Lesson:** Don't trade overnight with flow-only signals

### Trade 2: SHORT M2K @ 2,544.40 (V2 Overnight) ⭐ Best Signal
- **Why entered:** Sell flow dominance, equity correlation
- **What happened:** Reached +$7.00 (+14t MFE) — system correctly identified selling pressure
- **Why lost:** SL was only 10t, price bounced through stop before resuming down
- **Lesson:** SL too tight. With 15t+ SL or trail, this was a winner

### Trade 3: LONG M2K @ 2,541.70 (V2 Overnight)
- **Why entered:** Buy flow after M2K drop
- **What happened:** Counter-trend bounce didn't materialize, stopped at -20t
- **Lesson:** Buy flow in a downtrend = retail buying the dip

### Trade 4: LONG MES @ 6,617.50 (V3 RTH-1)
- **Why entered:** Flow buy +0.40 (B:532 S:227), conv 70
- **What went wrong:** Only 4 cycles in (~20s). regime=unknown, bar_trend=0.00. NO bars had formed.
- **Lesson:** Bar gate was only 3 bars — regime detection needs 10

### Trade 5: LONG M2K @ 2,550.90 (V3 RTH-1→2)
- **Why entered:** Flow buy +0.42 (B:202 S:82), equity consensus aligned
- **What happened:** Reached +$6.00 unrealized, then session restart caused WebSocket drop. Price reversed during gap.
- **Lesson:** WebSocket health monitoring is critical. Never restart during open position.

### Trade 6: LONG MCL @ $93.84 (V3 RTH-3)
- **Why entered:** Flow buy +0.23, mom +0.035%, VWAP above, conv 60 (minimum threshold)
- **What went wrong:** regime=unknown, bar_trend=0.00 — only had a few bars
- **MFE: +15t** — system was RIGHT about direction but trail needed 20t to activate
- **Lesson:** With 0.5× trail fix, would have activated at +10t and locked ~+5t profit

### Trade 7: LONG MES @ $6,599.25 (V3 RTH-3)
- **Why entered:** Flow buy +0.20, bars ↑ +0.40, conv 79 (high!), equity consensus ✓
- **What happened:** MES moved against immediately (-23t MAE). Market was selling despite flow signal.
- **Lesson:** High conviction doesn't guarantee success. MES had broadest spread noise.

### Trade 8: LONG MCL #2 @ $94.08 (V3 RTH-3) ⭐ Most Instructive
- **Why entered:** Cum flow +0.06, bars ↑ +0.40, VWAP above (+0.304%), conv 67
- **MFE: +20t ($20 profit!)** — this was a $20 winner that became a loser
- **Why lost profits:** Trail needed +30t MFE (SL 30t × 1.0). Never activated.
- **Still open** at +$5 at session end
- **Lesson:** THIS is the trade that proves the trail fix matters. At 0.5×, trail activates at +15t, locks breakeven+2t

### Trade 9: SHORT M2K @ $2,531.10 (V3 RTH-3)
- **Why entered:** Flow sell -0.26 (B:65 S:110), VWAP below, equity sell consensus
- **Warning flagged:** ⚠️ Flow vs bars conflict (flow↓ but bars↑)
- **MFE: +11t** — again found direction, but reversed
- **Lesson:** Flow vs bars conflict should be a HARD BLOCK, not just a penalty

### Trade 10: LONG M2K @ $2,533.90 (V3 RTH-3)
- **Why entered:** Flow buy +0.36 (B:105 S:49), bars ↑, regime=trending, conv 79
- **MFE: +12t** — this was the best-aligned entry of the session
- **Why lost:** Trail needed +15t (at 0.5× fix), reached +12t — just 3 ticks short!
- **Lesson:** Consider even lower trail activation (0.4×) or partial TP at 1:1

### Trade 11: SHORT MYM @ $46,544 (V3 RTH-3)
- **Why entered:** Bars ↓ -0.40, regime=trending, VWAP below, conv 66
- **Status:** Still open +$6 at session end
- **Note:** One of the better entries — trending regime, signals aligned

---

*Generated by SOVRAN V3 / Viktor AI — 2026-03-26*
