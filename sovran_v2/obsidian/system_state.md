---
title: Sovran V2 - System State
updated: 2026-03-26T21:00:00Z
type: system-state
---

# Sovran V2 Trading System - Current State

## Account Status

- **Balance:** $148,637.72
- **Starting Balance:** $150,000.00
- **Current P&L:** -$1,362.28 (-0.91%)
- **Account ID:** 20560125 (TopStepX 150K Simulated Combine)
- **Trailing Drawdown:** $4,500 from high-water mark
- **Daily Loss Limit:** $500

## Trading Performance

- **Total Trades:** 14
- **Wins:** 1 (7.1%)
- **Losses:** 13 (92.9%)
- **Win Rate:** 7.1%
- **Profit Factor:** N/A (insufficient wins)
- **Best Trade:** MCL SHORT +$38.48 (38 ticks, 106.9% capture ratio)
- **Avg MFE (losing trades):** +12.8 ticks
- **Avg MAE:** -18.8 ticks

## System Versions

- **Production Version:** V4 Kaizen Edition (last run)
- **Latest Version:** V5 Goldilocks Edition (ready to deploy)
- **Core Engine:** live_session_v5.py (1,950 lines)
- **Decision Backend:** file_ipc (LLM-agnostic)

### V4 Kaizen Edition Features
- Phase 1: Partial TP at 0.6× SL, hard flow/bars block, 120s min hold, 8-16 CT trading hours
- Phase 2: Regime-adaptive SL/TP, conviction-based sizing (1-2 contracts)
- Phase 3: Rolling 20-trade windows, Kaizen log, profit capture ratio
- Phase 4: KaizenEngine self-correction, adaptive params

### V5 Goldilocks Edition Features
- All V4 features PLUS:
- REST bar seeding (eliminates B:0 S:0 warmup dead zone)
- OFI Z-Score gate (institutional flow > 1.5 std devs)
- VPIN gate (informed trading probability > 0.55)
- Banned phase 12:30-14:00 CT (CURRENTLY DISABLED)

## Active Positions

**None** - all positions closed as of last session

## Contract Configuration

Scanning 6 micro-futures:
1. **MNQ** (Micro Nasdaq-100) - M26 expiry (June)
2. **MES** (Micro S&P 500) - M26 expiry (June)
3. **MYM** (Micro Dow) - M26 expiry (June)
4. **M2K** (Micro Russell 2000) - M26 expiry (June)
5. **MGC** (Micro Gold) - J26 expiry (April) ⚠️ **Needs rollover soon**
6. **MCL** (Micro Crude Oil) - K26 expiry (May) ⚠️ **Needs rollover soon**

## Risk Parameters

- **Max Position Size:** 1 contract (base)
- **Max Conviction Boost:** 2 contracts (if score ≥ 80)
- **Max Concurrent Positions:** 2
- **Max Daily Loss:** $500
- **Max Trades/Session:** 8
- **Trade Cooldown:** 90 seconds
- **Circuit Breaker:** 3 consecutive losses → 5-min pause

## Architecture Status

- **IPC Directory:** ✅ Created (C:\KAI\sovran_v2\ipc\)
- **Obsidian Vault:** ✅ Active (multi-LLM memory)
- **GitHub Sync:** ⚠️ Local changes on `genspace` branch
- **Test Suite:** ✅ 220/220 passing
- **Decision Engine:** file_ipc configured, backend tested

## Known Issues

1. **Win rate critically low (7%)** - exit management was the constraint, V4/V5 addresses this
2. **Contract expiry rollover needed** - MGC J26 (April), MCL K26 (May)
3. **Partial TP not yet validated live** - only 1 win so far (single-contract carryover)
4. **GitHub sync delayed** - local changes not pushed to main

## Next Session Priorities

1. Deploy V5 Goldilocks Edition
2. Validate partial TP mechanism under live conditions
3. Test OFI/VPIN gates with real market data
4. Achieve win rate > 25% (at least 1 win per 4 trades)
5. Net positive P&L for Friday session

## Last Updated

2026-03-26 21:00 UTC by KAI (Claude Code)
Next update: After first V5 session or significant system change


## Meta-Loop Update - 2026-03-27T01:17:11.200556+00:00

- **kaizen_fix_applied:** V5 Goldilocks Edition ready (code exists, will be used by trading loop)
- **tests_passed:** True
- **iteration:** 1

## System Update - 2026-03-26T20:47:00Z

- **IPC System:** ✅ WORKING - V5 successfully using file_ipc for trading decisions
- **Test Trade:** MES LONG conviction=69 (below 70 threshold, correctly blocked)
- **IPC Response Time:** 0.6s
- **Decision Logic:** OFI_Z=1.12, VPIN=0.52 → LONG signal
- **Fixed:** config/.env AI_PROVIDER changed from "openrouter" to "file_ipc"
- **Status:** System ready for autonomous trading with IPC-based decisions
