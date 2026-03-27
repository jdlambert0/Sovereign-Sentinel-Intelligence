---
title: Sovran V2 Problem Tracker
updated: 2026-03-26T20:35:00
status: active
total_issues: 17
resolved: 13
active: 4
---

# Sovran V2 — Problem Tracker

## ACTIVE — Needs Monitoring

### P1 — Trade Volume Stuck at B:0 S:0 (PERSISTENT BUG)
- **Category:** data-feed
- **Severity:** high
- **Description:** V4/V5 showing "First trade" events in logs but buy/sell volumes remain at 0. Bar snapshots consistently show `B:0 S:0` even after multiple GatewayTrade events. Volume accumulation is broken.
- **Impact:** Cannot calculate VPIN, OFI, or flow-based signals without valid trade volumes
- **First Observed:** 2026-03-26 V4 session
- **Still Present:** 2026-03-26 V5 session (confirmed persistent)
- **Action:** Debug GatewayTrade event handling in bar accumulation logic. Verify trade classification (buy vs sell side) is working correctly.

### P2 — Partial TP Not Yet Validated Live
- **Category:** execution
- **Severity:** medium
- **Description:** V4 partial TP (0.6x SL) code is in place but hasn't triggered on a live multi-contract trade yet. The MCL win was a single-contract carryover.
- **Action:** Monitor next V4 session for partial TP activation.

### P2 — Contract Expiry Rollover Needed
- **Category:** infrastructure
- **Severity:** medium
- **Description:** MGC uses J26 (April expiry), MCL uses K26 (May). MNQ/MES/MYM/M2K use M26 (June). Need to update contract IDs in sovran_config.json before expiry.
- **Action:** Check expiry dates and roll contracts before they expire.

### P3 — No L2 Depth Data Available
- **Category:** infrastructure
- **Severity:** info
- **Status:** WONT_FIX (API limitation)
- **Description:** TopStepX API doesn't support SubscribeContractDepth.
- **Workaround:** Trade flow classification from GatewayTrade events.

## RESOLVED

### P0 — Trail Activation Too High — FIXED in V3/V4
- Trail activation lowered from 1.5x → 1.0x → 0.5x SL
- V4 adds KaizenEngine adaptive adjustment (can auto-tighten to 0.2x)

### P0 — Bar Gate vs Regime Mismatch — FIXED in V3
- Bar gate raised from 3 → 10 bars
- regime=unknown hard block (conviction=0)

### P0 — Counter-Trend Entry Detection — FIXED in V3
- Equity consensus uses flow AND bar trend
- V4 upgrades to hard flow/bars conflict block (conviction=0)

### P0 — Stop Loss Too Tight Overnight — FIXED in V3
- ATR-based SL with 15-tick floor + trailing stop

### P0 — Invalid Stop Price on Trail Modify — FIXED in V4
- Added price-side validation: SL must be below current price for LONG, above for SHORT
- Prevents API rejection when modifying stop orders

### P1 — No Profit Capture Mechanism — FIXED in V4
- Partial TP at 0.6x SL ticks → SL to breakeven
- Trail activation at 0.5x SL (Kaizen-adaptive)
- Phase 1 Kaizen: min 120s hold before trailing

### P1 — Trading During Thin Hours — FIXED in V4
- Hard block: no trades outside 8:00-16:00 CT
- Session phase multipliers weight US core session highest

### P1 — Bracket Tick Sign Convention — FIXED
### P1 — GatewayTrade Side Classification — FIXED
### P1 — API Authentication Key — FIXED
### P1 — WebSocket bestBid/bestAsk Field Names — FIXED
### P2 — PnL Timezone (UTC vs Central) — FIXED
### P2 — Windows UTF-8 Log Encoding — FIXED in V4

## Trading Statistics (as of V4 session end)

| Metric | Value |
|--------|-------|
| Total trades | ~14 |
| Wins | 1 |
| Losses | ~13 |
| Win rate | ~7% |
| Total PnL | ~-$65.93 |
| Best trade | MCL SHORT +$38.48 (38t, target hit) |
| Avg MFE (losers) | +12.8 ticks |
| Core insight | Exits were the constraint, not signals |
| Current balance | $148,637.72 |
| V4 status | Kaizen Edition deployed, first win recorded |
