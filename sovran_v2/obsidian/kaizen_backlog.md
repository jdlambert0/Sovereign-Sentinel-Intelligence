---
title: Sovran V2 - Kaizen Improvement Backlog
updated: 2026-03-27T10:45:00Z
type: kaizen-backlog
priority_method: expected_impact_score
---

# Sovran V2 Kaizen Improvement Backlog

**Philosophy:** Fix the highest-leverage constraint first. Measure impact. Repeat.

## Priority Ranking Method

Expected Impact Score = (Probability of Fix Working x Estimated P&L Impact x Ease of Implementation) / 100

## P0 - CRITICAL (Do These First)

### 1. Deploy V5 Goldilocks Edition (OFI + VPIN Gates)
- **Status:** [OK] COMPLETED
- **Completed:** 2026-03-27 by Viktor AI
- **Result:** V5 Goldilocks Edition ready, will be used by trading loop

### 2. Roll MGC and MCL Contract Expirations
- **Status:** [OK] COMPLETED (2026-03-27 by Viktor AI)
- **Fix:** V5 was already on M26 (June) for all contracts. V4 updated: MGC J26->M26, MCL K26->M26.

### 3. Validate Partial TP Mechanism Under Live Conditions
- **Status:** [WAIT] Needs live trades
- **Blocker:** Zero recorded trade outcomes. Will validate after first 5-10 live V5 trades.

## P1 - HIGH IMPACT

### 4. Focus Trading on MCL/MGC (Energy/Metals) Over Equity Indices
- **Status:** [OK] COMPLETED (2026-03-27 by Viktor AI)
- **Implementation:** MCL/MGC conviction +10%, equity indices -20% in ai_decision_engine.py

### 5. Tighten Trail Activation to 0.3x SL for Scalping
- **Status:** [OK] COMPLETED (2026-03-27 by Viktor AI)
- **Implementation:** `TRAIL_ACTIVATION_MULT` changed from 0.5 to 0.3 in V5
- **File:** live_session_v5.py line 104

### 6. Implement "Overnight Lockout"
- **Status:** [OK] COMPLETED (2026-03-27 by Viktor AI)
- **Implementation:** Hard block in ai_decision_engine.py make_decision(), 8am-4pm CT only

## P0 - CRITICAL (NEW — Hunt Rethink Architecture 2026-03-27 evening)

### RETHINK-1. Replace 12 Broken/Correlated Models with 5 Real Signals + LLM Reasoning
- **Status:** [OK] COMPLETED (2026-03-27 evening by Claude Sonnet 4.6)
- **Result:** `_compute_signals()` in run_server.py replaces `run_all_models()`. 5 signals: Order Flow (OFI+VPIN), Price Structure (VWAP), Momentum, Volatility Regime, Session Context.

### RETHINK-2. Adversarial Bull/Bear Framing in LLM Prompt
- **Status:** [OK] COMPLETED (2026-03-27 evening by Claude Sonnet 4.6)
- **Result:** SKILL.md Step 3 requires LLM to output BEAR CASE / BULL CASE / SYNTHESIS / DECISION / CONVICTION / THESIS before placing any trade.

### RETHINK-3. Conviction-Based Contract Scaling (Use TopStepX Tiers)
- **Status:** [OK] COMPLETED (2026-03-27 evening by Claude Sonnet 4.6)
- **Result:** `_calculate_position_size()` in run_server.py: +$1,500→3 contracts, +$2,000→5 contracts. SKILL.md instructs LLM: HIGH→platform max, MEDIUM→half, LOW→1 probe.

### RETHINK-4. Semantic Context Packet (Python → English Before LLM Call)
- **Status:** [OK] COMPLETED (2026-03-27 evening by Claude Sonnet 4.6)
- **Result:** `_build_hunt_context()` translates all 5 signals to English labels. Uses doubled-text technique (role instruction at top AND bottom of context). Returned in `dry_run` response as `semantic_context`.

### RETHINK-5. Fix prices_history → 20-bar rolling buffer in live_session IPC
- **Status:** [OK] COMPLETED (2026-03-27 evening by Claude Sonnet 4.6)
- **Result:** Added `prices_history: List[float]` to `MarketSnapshot`; `_build_snapshot()` passes last 20 bar closes from `tick.bars`; `decision.py` writes it to IPC `snapshot_data`; MCP IPC enrichment copies it to each snap. Signal 3 (Momentum) now active.

## P1 - HIGH IMPACT (NEW — from AI trading research 2026-03-27)

### NEW-1. Opening Range Breakout (ORB) Model
- **Status:** [TODO] Not implemented
- **Source:** Backtested up to 400% on NQ/MNQ with strict rules (tradethatswing.com)
- **Rules:**
  - First 15 min after open (8:30–8:45 CT): record the high and low
  - BUY signal: 5-min candle closes above range high (+ VWAP confirmation)
  - SELL signal: 5-min candle closes below range low (+ VWAP confirmation)
  - Only valid before 11:00 AM CT (morning session only)
  - SL = opposite side of range, TP = 1.5x range width
- **Where to add:** `mcp_server/probability_models.py` as model #13
- **Data needed:** Track first 15-min high/low in `live_session_v5.py` or IPC snapshot
- **Impact Score:** 22 (high probability, proven backtest, low complexity)

### NEW-2. Macro Event Gate (News Veto)
- **Status:** [TODO] Not implemented
- **Source:** PickMyTrade news tone integration cuts false breakouts by 25%
- **Rules:**
  - Before each hunt: check economic calendar for events within ±30 min
  - VETO trade if: FOMC announcement, CPI/PPI release, NFP, Fed speaker
  - Use WebSearch or hard-coded calendar check
- **Where to add:** `_hunt_and_trade` pre-check (before Step 2)
- **Data needed:** Economic calendar API or pre-loaded event times
- **Impact Score:** 18 (25% false-breakout reduction = ~22 fewer losing trades on 89-trade sample)

### NEW-3. TopStep Consistency Rule Tracker
- **Status:** [OK] COMPLETED (2026-03-27 evening) — implemented in src/risk.py + run_server.py
- **Source:** Automated Trading Strategies Substack — prop firm plot twist
- **Rule:** TopStep requires no single day to exceed ~30% of total target profit
  - On a $150K account with $9K target: max single day ≈ $2,700
  - Violating this creates a new higher target
- **Where to add:** `src/risk.py` — daily consistency check
- **Implementation:** If daily PnL > 25% of weekly target → reduce size to 1 contract, set conviction floor to 80
- **Impact Score:** 25 (account disqualification risk = highest priority)

## P2 - MEDIUM IMPACT

### 7. Adaptive Conviction Threshold Based on Session Performance
- **Status:** [OK] COMPLETED (2026-03-27 by Viktor AI)
- **Implementation:**
  - Rolling 20-trade win rate drives conviction threshold
  - Win rate > 55%: lower threshold by up to 5 pts (lean into hot streak)
  - Win rate 45-55%: neutral (no adjustment)
  - Win rate < 40%: raise threshold by up to 10 pts (tighten when cold)
  - Wired into both the trade execution loop and scan logging
- **File:** live_session_v5.py `get_effective_conviction_threshold()`

### 8. Regime-Specific Partial TP Thresholds
- **Status:** [WAIT] Not yet implemented
- **Problem:** Partial TP fixed at 0.6x SL regardless of regime. Trending should give more room.
- **Plan:**
  - Trending: partial TP at 0.8x SL (let it run)
  - Ranging: partial TP at 0.5x SL (take it quick)
- **Impact Score:** 15

### 9. Losing Streak Cooldown (30 min After 3 Losses)
- **Status:** [OK] COMPLETED (2026-03-27 by Viktor AI)
- **Implementation:** 300s -> 1800s in both V4 and V5

## P3 - LOW IMPACT / RESEARCH

### 10. Monte Carlo Parameter Sweep
- **Status:** [OK] COMPLETED (2026-03-27 by Viktor AI)
- **Results (10,000 simulated paths):**
  - P(Hit $159K Target): *78.0%*
  - P(Ruin / Trailing DD): *0.0%*
  - P(Still Open after 60 days): *21.9%*
  - Mean time to target: *47.4 trading days*
  - MCL/MGC win rate: *56.7%* (equity indices: 41.2%)
  - All contracts profit factor: *3.3-3.4x*
- **Key Insight:** System has strong positive expectancy. Energy/metals emphasis validated by sim.
- **Files:** `scripts/monte_carlo_sweep.py`, `state/monte_carlo_results.json`, `state/monte_carlo_chart.png`

## Completed Summary

| # | Item | Status | Date |
|---|------|--------|------|
| 1 | V5 Goldilocks Deploy | [OK] | 2026-03-27 |
| 2 | Contract Rollover | [OK] | 2026-03-27 |
| 4 | MCL/MGC Focus | [OK] | 2026-03-27 |
| 5 | Trail Activation 0.3x | [OK] | 2026-03-27 |
| 6 | Overnight Lockout | [OK] | 2026-03-27 |
| 7 | Adaptive Conviction | [OK] | 2026-03-27 |
| 9 | Circuit Breaker 1800s | [OK] | 2026-03-27 |
| 10 | Monte Carlo Sweep | [OK] | 2026-03-27 |

## Still Open

| # | Item | Status | Blocker |
|---|------|--------|---------|
| 3 | Validate Partial TP | [WAIT] | Needs live trades |
| 8 | Regime-Specific TP | [WAIT] | Lower priority, needs live data first |

## Previous Completed (V4 Era)

- Partial TP at 0.6x SL (Phase 1)
- Trail activation lowered to 0.5x SL -> now 0.3x (Phase 1+Kaizen #5)
- Minimum hold time 120s (Phase 1)
- Regime=unknown hard block (Phase 1)
- Flow/bars conflict block (Phase 1)
- Regime-adaptive SL/TP profiles (Phase 2)
- Conviction-based sizing 1-2 contracts (Phase 2)
- Rolling 20-trade windows (Phase 3)
- KaizenEngine self-correction (Phase 4)
- Bayesian Belief Updating (Beta-Binomial conjugate)
- Round-Robin Always-Trade (no NO_TRADE returns)
- Full emoji cleanup (ASCII tags)
- TrustGraph integration client + loader + docs

## Last Updated

2026-03-27 12:00 CT by Accio Work Coder (V4 outcome tracking added, Bayesian memory backfilled)
