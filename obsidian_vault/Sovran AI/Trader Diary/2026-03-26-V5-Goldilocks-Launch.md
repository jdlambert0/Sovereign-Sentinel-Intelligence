# 2026-03-26 — V5 Goldilocks Launch Day

## Status
- **Engine**: V5 Goldilocks Edition
- **Account Balance**: ~$148,647 (need $159,000 to pass combine)
- **Gap**: ~$10,353 remaining
- **Max Drawdown Budget**: ~$3,138 estimated

## What Changed from V4 → V5

### Fix 1: REST Bar Seeding
- **Problem**: B:0 S:0 warmup dead zone (7-10 min of no trades)
- **Fix**: `_seed_historical_bars()` fetches 30 1-min bars via `POST /api/History/retrieveBars` at startup
- Instantly seeds buy/sell volume, VWAP, price history, tick_count
- First scan cycle fires immediately with real data

### Fix 2: Goldilocks Signal Gates
- **OFI Z-Score gate**: |Z| > 1.5 required (institutional displacement filter)
- **VPIN gate**: VPIN > 0.55 required (informed flow filter)
- Both computed from `recent_trades[]` on each `MarketTick`

### User Decision: Banned Hours Disabled
- 12:30-14:00 CT ban is defined in code but DISABLED for this session
- Rationale: collect more Kaizen data across all time periods
- Can re-enable anytime by uncommenting the gate

## Session Plan
- Launch at 5:00 PM CT (after-hours session)
- Run with `--cycles 720 --interval 5` (1 hour)
- Monitor for: bar seeding confirmation, OFI/VPIN filter activity, trade execution

## Launch Command
```
cd C:\KAI\sovran_v2
python live_session_v5.py --cycles 720 --interval 5
```

## V4 Live Trade Results (context)
| # | Trade | PnL | Ticks | Capture | Exit |
|---|-------|-----|-------|---------|------|
| 1 | SHORT MCL | +$38.48 | 38t | 106.9% | TARGET_HIT |
| 2 | SHORT MES | +$9.22 | 7t | 46.1% | TRAIL_STOP |

Trail activation CONFIRMED. Partial TP CONFIRMED.

## Notes
- Contracts: MNQ M26, MES M26, MYM M26, M2K M26, MGC J26, MCL K26
- 1 contract only (process first, profitability second)
- Kaizen log auto-updates: `state/kaizen_log.json`
