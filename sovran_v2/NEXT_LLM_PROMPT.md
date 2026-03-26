# Sovran V2 — Next LLM Handoff Prompt

**Use this as the system/context prompt for the next AI session working on Sovran V2.**

---

## Context

You are continuing development on **Sovran V2**, an autonomous micro-futures trading system that runs on the TopStepX simulated combine platform. The codebase is at `C:\KAI\sovran_v2` and is tracked in the GitHub repo `https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence` on the `main` branch.

## Account State (as of 2026-03-26 ~09:00 CT)

- **Account:** TopStepX 150KTC-V2-423406-25666664 (ID: 20560125)
- **Balance:** $148,637.72
- **canTrade:** True
- **Open positions:** 0
- **Starting balance was:** $148,703.64

## System Architecture

The trading system is a 5-layer pipeline:

1. **MarketDataStream** (`src/market_data.py`) — WebSocket to `wss://rtc.topstepx.com/hubs/market`. Subscribes to L1 quotes and trade flow for 6 micro-futures: MNQ, MES, MYM, M2K, MGC, MCL. Builds 1-minute bars in memory.
2. **Scanner** (`live_session_v4.py`) — Runs `analyze_market()` per contract every cycle. 10-signal scoring pipeline: flow ratio, windowed flow, bar trend, momentum, ATR volatility, VWAP, acceleration, regime detection, equity consensus, session phase multiplier. Outputs conviction score (0-100).
3. **Risk** (`src/risk.py`) — Kelly sizing, ruin probability, daily loss limits ($500/day), max 8 trades/session, 90s cooldown, 3-loss circuit breaker.
4. **Broker** (`src/broker.py`) — TopStepX REST API at `https://api.topstepx.com`. Bracket orders (market entry + SL + TP). Auth via API key.
5. **KaizenEngine** (`live_session_v4.py`) — Post-trade self-correction. Adjusts trail activation, conviction threshold, and SL multiplier based on trade outcomes. Logs to `state/kaizen_log.json`.

## Current Version: V4 (Kaizen Edition)

The latest live script is `live_session_v4.py`. It integrates 4 Kaizen phases:

### Phase 1 — Eliminate Waste
- **Partial take-profit** at MFE ≥ 0.6× SL_ticks → SL moves to breakeven
- **Hard flow/bars conflict block** → conviction=0 when flow and bar trend strongly disagree
- **Minimum hold time** 120s before trailing stop logic runs
- **Trading hours hard block** — no entries outside 8:00-16:00 CT

### Phase 2 — Level the Flow
- **Regime-adaptive SL/TP profiles** — trending: 2×/5× ATR, ranging: 1.5×/2.5× ATR, volatile/unknown: BLOCKED
- **Conviction-based sizing** — score ≥ 80 with no open positions → 2 contracts

### Phase 3 — Standardize
- **Rolling 20-trade performance windows** — win rate, profit factor, capture ratio
- **Per-trade Kaizen log** at `state/kaizen_log.json` — every trade records conviction, regime, MFE, MAE, capture ratio, and parameter adjustments
- **Profit capture ratio** = actual_pnl / (mfe × tick_value)

### Phase 4 — Continuous Flow
- **KaizenEngine self-correction** — after each trade:
  - Low capture ratio → tighten trail activation (×0.92)
  - Low MFE → raise conviction threshold (+1)
  - Fast stop-out → widen SL (×1.05)
  - Winning trade → slowly relax all params toward defaults
- **Per-market performance ranking** — tracks wins/losses/PnL per contract

## Trade History Summary (14 trades total)

| Metric | Value |
|--------|-------|
| Total trades | ~14 (across v1-v4 sessions) |
| Win rate | ~7% (1 win: MCL SHORT +$38.48) |
| Total PnL | ~-$65.93 |
| Best trade | MCL SHORT +$38.48 (38t, target hit, 106.9% capture) |
| Avg MFE (losers) | +12.8 ticks |
| Core problem | Exits, not entries. System finds direction but gives back profits |

### V4 First Win Details
- **MCL SHORT** entered at $94.93, target hit at $94.55
- PnL: +$38.48, 38 ticks, hold 149s
- MFE: +36t, MAE: 0t, Capture: 106.9%
- This was a carryover position from v3, managed by v4's bracket

## Key Config

- **Contracts:** `CON.F.US.MNQ.M26`, `CON.F.US.MES.M26`, `CON.F.US.MYM.M26`, `CON.F.US.M2K.M26`, `CON.F.US.MGC.J26`, `CON.F.US.MCLE.K26`
- **Auth:** API key in `config/.env` — `userName=jessedavidlambert@gmail.com`
- **Risk:** $500 daily loss limit, $4500 max trailing drawdown, max 2 concurrent positions
- **Conviction threshold:** 60 (first trade), 65 (after loss) + Kaizen adjustment
- **Trail activation:** 0.5× SL_ticks (Kaizen-adaptive, can tighten to 0.2×)

## Known Issues / Next Steps

1. **Partial TP not fully tested** — the 0.6× SL partial TP fires and moves SL to breakeven, but hasn't been validated with a live 2-contract trade yet
2. **B:0 S:0 display bug** — `_log_scan` shows B:0 S:0 when `analyze_market()` returns early at gate checks. Cosmetic only — trade flow IS accumulating on tick objects
3. **`Invalid stop price` on trail** — v3 had this bug. V4 added price-side validation (SL below price for LONG, above for SHORT). Needs monitoring.
4. **Contract expiry** — MGC uses J26 (April), MCL uses K26 (May). MNQ/MES/MYM/M2K use M26 (June). Check for rollovers.
5. **Commission optimization** — ~$2-3 round-trip overhead. Need 2:1 R:R minimum after costs.
6. **No L2 depth data** — TopStepX API doesn't support `SubscribeContractDepth`. WONT_FIX.

## File Layout

```
C:\KAI\sovran_v2/
├── live_session_v4.py          ← LATEST — run this
├── live_session_v3.py          ← previous version (kept for rollback)
├── KAIZEN_TRADING_FRAMEWORK.md ← full Kaizen philosophy + implementation plan
├── SESSION_NOTES.md            ← detailed trade-by-trade history
├── config/
│   ├── sovran_config.json      ← contracts, account ID
│   ├── risk_config.json        ← drawdown limits, Kelly params
│   ├── decision_config.json    ← AI provider config (file_ipc)
│   ├── sentinel_config.json    ← cycle timing, market hours
│   └── .env                    ← API credentials (gitignored)
├── src/
│   ├── broker.py               ← TopStepX REST client
│   ├── market_data.py          ← WebSocket streaming + bar builder
│   ├── decision.py             ← AI decision engine (currently bypassed)
│   ├── risk.py                 ← Kelly sizing, ruin probability
│   ├── sentinel.py             ← Main orchestrator (v1 architecture)
│   ├── performance.py          ← Performance attribution engine
│   ├── position_manager.py     ← Position monitoring/exit control
│   ├── scanner.py              ← Market scanning utilities
│   └── problem_tracker.py      ← Automated problem detection
├── state/
│   ├── kaizen_log.json         ← Per-trade Kaizen instrumentation
│   └── trade_history.json      ← Full trade history
├── obsidian/
│   ├── daily_log_YYYY-MM-DD.md ← Daily session logs
│   └── problem_tracker.md      ← Issue tracker
└── tests/                      ← Unit + integration tests
```

## How to Run

```powershell
cd C:\KAI\sovran_v2
python live_session_v4.py --cycles 720 --interval 5   # 1 hour session
```

## Git Workflow

The repo root is `C:\KAI` but the current working branch is `genspace` with uncommitted changes in other dirs. To push sovran_v2 changes to GitHub:

```powershell
git -C "C:\KAI" worktree add "C:\KAI\_main_wt" main
# copy changed files into worktree's sovran_v2/
git -C "C:\KAI\_main_wt" add sovran_v2/
git -C "C:\KAI\_main_wt" commit -m "your message"
$token = (gh auth token).Trim()
git -C "C:\KAI\_main_wt" -c "url.https://jdlambert0:$token@github.com/.insteadOf=https://github.com/" push origin main --no-verify
git -C "C:\KAI" worktree remove "C:\KAI\_main_wt" --force
```

## Priority for Next Session

1. **Run V4 during US RTH** (8:00-16:00 CT) and monitor for at least 30 minutes
2. **Validate partial TP** — watch for a trade where MFE ≥ 0.6× SL and confirm SL moves to breakeven
3. **Review Kaizen log** — after 5+ trades, check `state/kaizen_log.json` for parameter drift patterns
4. **If win rate > 40% over 10 trades** → enable conviction-based sizing (already in code, activate at score ≥ 80)
5. **If win rate < 25% over 10 trades** → Kaizen engine will auto-raise conviction threshold; verify it's working
6. **Push results to GitHub** after each session
