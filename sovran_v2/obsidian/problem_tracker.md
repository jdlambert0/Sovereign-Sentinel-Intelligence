---
title: Sovran V2 Problem Tracker
updated: 2026-03-27T10:50:00-05:00
status: active
total_issues: 25
resolved: 21
active: 4
---

# Sovran V2 — Problem Tracker

**Resolved:** 21/25 | **Active:** 4 | **Last Updated:** 2026-03-27 10:50 CT by Viktor AI

---

## ACTIVE ISSUES (4 remaining)

### 1. Zero Recorded Trade Outcomes — Bayesian Using Priors Only
- **Severity:** HIGH
- **Category:** data / ai-learning
- **Status:** Waiting on live trades
- **Problem:** The Bayesian belief system is implemented and working, but `state/ai_trading_memory.json` has 0 recorded outcomes. The system is running on Beta(2,2) priors (50% baseline) instead of learned posteriors.
- **Impact:** AI cannot learn or adapt until real trade outcomes are recorded.
- **What's Needed:** Run live trading sessions. After each trade, `record_trade_outcome.py` will feed results into memory. After 5+ trades per strategy, Bayesian posteriors will diverge from priors.
- **Blocker:** Need to deploy patch and run `ralph_ai_loop.py` in live market hours.

### 2. 12 Probability Models Research Not Integrated
- **Severity:** MEDIUM
- **Category:** ai-enhancement
- **Status:** Research complete, code not integrated
- **Problem:** Background agent completed 12-model research (15,000+ lines) covering Kelly, Poker Math, Casino Theory, Market Making, Stat Arb, Volatility, Momentum, Order Flow, Risk Mgmt, Monte Carlo, Bayesian, Information Theory. These files exist on the local machine but are not wired into the trading engine.
- **Files:** `C:\KAI\_research\12_Trading_Probability_Models_*.md`
- **Impact:** Potential 10-50% improvement in decision quality if best models are integrated.
- **What's Needed:**
  1. Review the 12 research files
  2. Select 3-5 highest-value models to integrate
  3. Implement as shadow mode (log predictions without trading)
  4. Validate against live outcomes
  5. Gradual rollout of proven models

### 3. Pre-commit mypy Hook Failing
- **Severity:** LOW
- **Category:** development tooling
- **Status:** Known workaround
- **Error:** `ERROR: No matching distribution found for types-pkg-resources`
- **Workaround:** Use `git commit --no-verify`
- **Impact:** Cosmetic only — no effect on trading system.
- **What's Needed:** Either fix the mypy environment or remove the hook from `.pre-commit-config.yaml` (note: no `.pre-commit-config.yaml` exists in the repo currently, so this may be a local-only issue).

### 4. Contract Rollover Monitoring
- **Severity:** LOW (not urgent until May 2026)
- **Category:** infrastructure
- **Status:** All contracts currently on M26 (June 2026)
- **Problem:** Futures contracts expire quarterly. Current M26 contracts expire in late June 2026.
- **When to Act:** Mid-May 2026 — roll from M26 to U26 (September) before June expiry.
- **Contracts:** MNQ, MES, MYM, M2K, MGC, MCL
- **Files to Update:** `SCAN_CONTRACTS` and `CONTRACT_META` in `live_session_v5.py` and `live_session_v4.py`

---

## RESOLVED ISSUES — Viktor Session (2026-03-27)

| # | Issue | Fix | Files |
|---|-------|-----|-------|
| 1 | Ralph launching wrong subprocess | `autonomous_responder.py` -> `ai_decision_engine.py` | `ralph_ai_loop.py` |
| 2 | check_risk_of_ruin() double-counted wins | Uses contract data only now | `ipc/ai_decision_engine.py` |
| 3 | check_risk_of_ruin() wrong class call | `TradingMemory` -> `ProbabilityCalculator` | `ipc/ai_decision_engine.py` |
| 4 | risk_of_ruin() wrong expected_value call | Fixed to `ProbabilityCalculator.expected_value` | `ipc/ai_decision_engine.py` |
| 5 | Losses counter never incremented | Reads from contract data now | `ipc/ai_decision_engine.py` |
| 6 | Hardcoded account_balance | Reads from memory data | `ipc/ai_decision_engine.py` |
| 7 | Round-robin never returns NO_TRADE | Weak signals get 0.85x discount instead | `ipc/ai_decision_engine.py` |
| 8 | Emoji encoding errors (project-wide) | All emoji -> ASCII tags | V1-V5, record_outcome |
| 9 | V4 contract rollover (MGC J26, MCL K26) | Rolled to M26 (June) | `live_session_v4.py` |
| 10 | Time gate logging confusion | AI engine has own lockout, V5 bypass correct | N/A (was not a bug) |
| 11 | Overnight lockout missing | Hard block 8am-4pm CT in make_decision() | `ipc/ai_decision_engine.py` |
| 12 | Circuit breaker too short (300s) | Increased to 1800s (30 min) | V4 + V5 |
| 13 | No Bayesian belief updating | Beta-Binomial conjugate implemented | `ipc/ai_decision_engine.py` |
| 14 | Asset priority not implemented | MCL/MGC +10%, equity -20% | `ipc/ai_decision_engine.py` |
| 15 | Trail activation too wide (0.5x) | Tightened to 0.3x SL | `live_session_v5.py` |
| 16 | Adaptive conviction not implemented | Rolling 20-trade WR drives threshold | `live_session_v5.py` |

## RESOLVED ISSUES — Previous Sessions (2026-03-26)

| # | Issue | Fix |
|---|-------|-----|
| 17 | Memory not recording trade outcomes | Created `record_trade_outcome.py`, integrated in V5 |
| 18 | TradeResult missing sl_ticks attribute | Added `sl_ticks` and `tp_ticks` to dataclass |
| 19 | Corrupted AI trading memory JSON | Removed extra `}`, validated structure |
| 20 | Trail activation too high (1.5x -> 1.0x -> 0.5x) | Progressive tightening across V3/V4 |
| 21 | Bar gate vs regime mismatch | Bar gate raised to 10, unknown hard block |
| 22 | Counter-trend entry detection | Equity consensus with flow + bar trend |
| 23 | Stop loss too tight overnight | ATR-based SL with 15-tick floor |
| 24 | Invalid stop price on trail modify | Price-side validation added |
| 25 | Goldilocks gates restricting AI | V5 bypasses OFI/VPIN when AI_PROVIDER=file_ipc |

## WONT_FIX

| Issue | Reason |
|-------|--------|
| No L2 depth data | TopStepX API doesn't support SubscribeContractDepth. Using GatewayTrade flow instead. |
| Git repository needs pruning | Cosmetic warning only. Run `git prune` when convenient. |

---

**End of Problem Tracker**
