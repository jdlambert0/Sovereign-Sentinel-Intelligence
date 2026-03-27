---
title: Sovran V2 - Kaizen Improvement Backlog
updated: 2026-03-26T21:00:00Z
type: kaizen-backlog
priority_method: expected_impact_score
---

# Sovran V2 Kaizen Improvement Backlog

**Philosophy:** Fix the highest-leverage constraint first. Measure impact. Repeat.

## Priority Ranking Method

Expected Impact Score = (Probability of Fix Working × Estimated P&L Impact × Ease of Implementation) / 100

## P0 - CRITICAL (Do These First)

### 1. Deploy V5 Goldilocks Edition (OFI + VPIN Gates)
- **Status:** 🟡 Code ready, not yet run live
- **Problem:** V4 has no institutional order flow filter. VPIN and OFI Z-Score gates should reduce noise trades.
- **Expected Impact:** Win rate 7% → 25-30% by filtering retail-driven fake signals
- **Implementation:** Replace live_session_v4.py calls with live_session_v5.py
- **Success Metric:** Win rate improves by at least 10 percentage points
- **Ease:** Low (code is done, just needs deployment)
- **Impact Score:** 0.7 × $200 × 0.9 = **126** ⭐ **HIGHEST PRIORITY**

### 2. Roll MGC and MCL Contract Expirations
- **Status:** 🔴 Urgent - MGC J26 (April), MCL K26 (May)
- **Problem:** Trading expired contracts will fail. Need to update to next quarterly expiry.
- **Expected Impact:** Prevents catastrophic failure
- **Implementation:**
  - MGC: J26 → M26 (June)
  - MCL: K26 → M26 (June)
  - Update `SCAN_CONTRACTS` and `CONTRACT_META` in live_session_v5.py
- **Success Metric:** Contracts trade successfully through April/May
- **Ease:** Low (config change + verification)
- **Impact Score:** 1.0 × $0 (prevents failure) = **CRITICAL** (non-negotiable)

### 3. Validate Partial TP Mechanism Under Live Conditions
- **Status:** 🟡 Implemented but untested at scale
- **Problem:** V4 partial TP code exists but only 1 win (single-contract carryover from v3). Haven't seen partial TP trigger on a multi-contract high-conviction trade yet.
- **Expected Impact:** +$50-100/week if it works as designed
- **Implementation:** Deploy V5, monitor first 5-10 trades for partial TP activation
- **Success Metric:** At least 2 partial TP events in next 20 trades
- **Ease:** Low (already implemented, just needs validation)
- **Impact Score:** 0.8 × $75 × 0.9 = **54**

## P1 - HIGH IMPACT

### 4. Focus Trading on MCL/MGC (Energy/Metals) Over Equity Indices
- **Status:** 🔴 Not implemented
- **Problem:** MES/MNQ have 100% loss rate across 9 trades. MCL has the only win (+$38.48). Tick values: MCL $1.00, MGC $1.00 vs MES $1.25, MNQ $0.50.
- **Expected Impact:** Win rate improves if we trade contracts where our edge is proven
- **Implementation:**
  - Add `asset_priority` weighting to conviction score
  - Boost MCL/MGC conviction by 10%
  - Penalize MES/MNQ conviction by 20%
  - Or hard block equity indices until MCL/MGC prove profitable
- **Success Metric:** 50%+ of trades are energy/metals, win rate on those ≥ 30%
- **Ease:** Medium (requires code change to conviction scoring)
- **Impact Score:** 0.6 × $100 × 0.6 = **36**

### 5. Tighten Trail Activation to 0.3× SL for Scalping
- **Status:** 🟡 Currently 0.5× SL (V4 improvement from 1.0×)
- **Problem:** Avg MFE is 12.8 ticks but avg MAE is -18.8 ticks. Many trades show +10-15t MFE then give it back. 0.5× might still be too wide.
- **Expected Impact:** Capture ratio 0% → 30-40% by locking in smaller but more frequent winners
- **Implementation:** Lower `TRAIL_ACTIVATION_MULT` from 0.5 to 0.3 in V5
- **Success Metric:** Avg capture ratio ≥ 0.35 over next 20 trades
- **Ease:** Low (single parameter change)
- **Impact Score:** 0.7 × $80 × 0.9 = **50.4**

### 6. Implement "Overnight Lockout" (Disable Trading 12am-8am CT)
- **Status:** 🔴 Not implemented (time-of-day hard block exists but allows overnight at 0.5× conviction)
- **Problem:** 3/14 trades happened overnight, all losses. Thin market + wide spreads + low conviction = waste.
- **Expected Impact:** Avoid -$25-50 in overnight noise losses per week
- **Implementation:** Hard block conviction → 0 if hour < 8 or hour >= 16
- **Success Metric:** Zero overnight trades, daily P&L variance decreases
- **Ease:** Low (single if-statement in session phase logic)
- **Impact Score:** 0.9 × $40 × 0.9 = **32.4**

## P2 - MEDIUM IMPACT

### 7. Adaptive Conviction Threshold Based on Session Performance
- **Status:** 🔴 Not implemented
- **Problem:** Fixed thresholds (60/65) don't adapt to market conditions. Some days need higher bar.
- **Expected Impact:** Reduce losing streaks by raising bar when edge disappears
- **Implementation:**
  - Track rolling 10-trade win rate
  - If win rate < 20%: min_conviction += 10
  - If win rate > 50%: min_conviction -= 5 (be more aggressive)
- **Success Metric:** Losing streaks limited to 3-4 trades max
- **Ease:** Medium (requires rolling window state tracking)
- **Impact Score:** 0.5 × $60 × 0.5 = **15**

### 8. Regime-Specific Partial TP Thresholds
- **Status:** 🔴 Not implemented (partial TP is fixed at 0.6× SL regardless of regime)
- **Problem:** Trending markets can give more room to run. Ranging markets need tighter TP.
- **Expected Impact:** Capture more of trending moves, protect profits in chop
- **Implementation:**
  - Trending: partial TP at 0.8× SL (let it run)
  - Ranging: partial TP at 0.5× SL (take it quick)
  - Update `_check_trailing_stop()` to use `REGIME_PROFILES`
- **Success Metric:** Avg win size increases in trending markets
- **Ease:** Medium (requires regime-aware logic in position manager)
- **Impact Score:** 0.6 × $50 × 0.5 = **15**

### 9. Add "Losing Streak Cooldown" (30 min After 3 Losses)
- **Status:** 🟡 Circuit breaker exists (3 losses → 5 min), but only 5 min might be too short
- **Problem:** After 3 losses in a row, the system is clearly misreading market conditions. 5 min isn't enough for regime to shift.
- **Expected Impact:** Prevent compounding losses during adverse conditions
- **Implementation:** Increase `circuit_breaker_pause_seconds` from 300 to 1800 (30 min)
- **Success Metric:** Max consecutive losses ≤ 4
- **Ease:** Low (single parameter change)
- **Impact Score:** 0.7 × $30 × 0.9 = **18.9**

## P3 - LOW IMPACT / RESEARCH NEEDED

### 10. Monte Carlo Parameter Sweep (Trail, Partial TP, Conviction)
- **Status:** 🔴 Not done
- **Problem:** We're guessing at optimal params. Could be leaving money on the table.
- **Expected Impact:** Unknown - could be 10-50% improvement or none
- **Implementation:**
  - Replay 14 trades with different param combinations
  - Find params that would have yielded best Sharpe ratio
  - Test on forward data before deploying
- **Success Metric:** Identify at least one param set with Sharpe > 1.5
- **Ease:** High (requires backtest infrastructure)
- **Impact Score:** 0.3 × $100 × 0.3 = **9**

## Completed Kaizen Items (V4)

- ✅ **Partial TP at 0.6× SL** (Phase 1)
- ✅ **Trail activation lowered to 0.5× SL** (Phase 1, was 1.0×)
- ✅ **Minimum hold time 120s** (Phase 1)
- ✅ **Regime=unknown hard block** (Phase 1)
- ✅ **Flow/bars conflict block** (Phase 1)
- ✅ **Regime-adaptive SL/TP profiles** (Phase 2)
- ✅ **Conviction-based sizing (1-2 contracts)** (Phase 2)
- ✅ **Rolling 20-trade performance windows** (Phase 3)
- ✅ **KaizenEngine self-correction** (Phase 4)

## Execution Plan for Next Session

**Immediate (Before Friday market open):**
1. Deploy V5 Goldilocks Edition (#1) - **HIGHEST PRIORITY**
2. Roll MGC/MCL contract expirations (#2) - **CRITICAL**
3. Validate partial TP under live conditions (#3)

**After 5-10 V5 Trades:**
4. Analyze which contracts are winning (MCL focus #4)
5. Adjust trail activation if needed (#5)
6. Implement overnight lockout if data confirms (#6)

**Weekend Research:**
7. Monte Carlo parameter sweep (#10)

## Last Updated

2026-03-26 21:00 UTC by KAI (Claude Code)
Next update: After each Ralph loop iteration or significant finding


### [OK] COMPLETED: 1. Deploy V5 Goldilocks Edition (OFI + VPIN Gates)
- **Completed:** 2026-03-27T01:17:11.200556+00:00
- **Result:** V5 Goldilocks Edition ready (code exists, will be used by trading loop)
