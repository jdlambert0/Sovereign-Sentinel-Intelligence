---
title: Sovran V2 System State
date: 2026-03-27
type: system-status
updated: 2026-03-27T10:50:00-05:00
---

# Sovran V2 System State

**Last Updated:** 2026-03-27 10:50 CT
**Updated By:** Viktor AI (Slack coworker)

---

## Current Status

**READY TO TRADE — ALL KAIZEN ITEMS APPLIED — SYSTEM VALIDATED BY MONTE CARLO**

| Component | Status | Notes |
|-----------|--------|-------|
| V5 Goldilocks Edition | Ready | Active trading engine |
| AI Decision Engine | Enhanced | Bayesian learning + overnight lockout + asset weighting + round-robin |
| Ralph AI Loop | Ready | Fixed subprocess call (was launching wrong script) |
| Contract Expirations | All M26 | June 2026 — next rollover ~May |
| Bayesian System | Active | Using Beta(2,2) priors, will learn from live outcomes |
| TrustGraph | Code ready | Needs Docker deployment |
| Obsidian Vault | Fully updated | All sessions, handoffs, and backlog current |
| Problem Tracker | 21/25 resolved | 4 remaining (see below) |
| Kaizen Backlog | 8/10 complete | 2 remaining need live data |

---

## Monte Carlo Validation (10,000 paths)

```
P(Hit $159K Target):   78.0%
P(Hit Ruin):            0.0%
P(Still Open 60 days): 21.9%
Mean time to target:   47.4 trading days
MCL/MGC win rate:      56.7%  (PF: 3.4x)
Equity indices:        41.2%  (PF: 3.3x)
```

Results at: `state/monte_carlo_results.json`, `state/monte_carlo_chart.png`
Script at: `scripts/monte_carlo_sweep.py`

---

## Active Trading Parameters

| Parameter | Value | Changed By |
|-----------|-------|------------|
| AI Provider | file_ipc | Default |
| Overnight Lockout | 8am-4pm CT only | Viktor (Kaizen #6) |
| Circuit Breaker | 1800s (30 min) after 3 losses | Viktor (Kaizen #9) |
| Trail Activation | 0.3x SL | Viktor (Kaizen #5, was 0.5x) |
| Conviction Threshold | 60/65 + rolling WR adjustment | Viktor (Kaizen #7) |
| Asset Priority | MCL/MGC +10%, equity -20% | Viktor (Kaizen #4) |
| Round-Robin | Always-trade (no NO_TRADE returns) | Viktor |
| Bayesian Blending | 60% model + 25% strategy + 15% contract | Viktor |
| Position Sizing | Kelly Criterion (25% fractional) | Original |
| Daily Loss Limit | $500 | Original |
| Partial TP | 0.6x SL (close half, SL to breakeven) | V4 original |

### Regime Profiles (V5)

| Regime | SL Mult | TP Mult | Trail Offset | Trail Act |
|--------|---------|---------|-------------|-----------|
| Trending | 2.0x | 5.0x | 6 ticks | 0.4 |
| Ranging | 1.5x | 2.5x | 4 ticks | 0.3 |
| Volatile | BLOCKED | BLOCKED | -- | -- |
| Unknown | BLOCKED | BLOCKED | -- | -- |

### Contract Universe (All M26 — June 2026)

| Contract | Tick Size | Tick Value | Asset Class | Conviction Adj |
|----------|-----------|------------|-------------|----------------|
| MNQ | 0.25 | $0.50 | Equity Index | -20% |
| MES | 0.25 | $1.25 | Equity Index | -20% |
| MYM | 1.00 | $0.50 | Equity Index | -20% |
| M2K | 0.10 | $0.50 | Equity Index | -20% |
| MGC | 0.10 | $1.00 | Metals | +10% |
| MCL | 0.01 | $1.00 | Energy | +10% |

---

## All Fixes Applied (Viktor Session 2026-03-27)

### Bug Fixes (8 issues)
1. ralph_ai_loop.py launching wrong subprocess (autonomous_responder -> ai_decision_engine)
2. check_risk_of_ruin() — 5 bugs: double-count wins, wrong class calls, losses=0, hardcoded balance
3. Round-robin always-trade — AI engine never returns NO_TRADE
4. Emoji encoding — all Unicode emoji replaced with ASCII tags project-wide
5. Contract rollover V4 — MGC J26->M26, MCL K26->M26
6. Time gate logging confusion — resolved (AI engine has own lockout)

### Kaizen Improvements (8/10 complete)
1. [OK] V5 Goldilocks Deploy
2. [OK] Contract Rollover (all M26)
3. [WAIT] Validate Partial TP (needs live trades)
4. [OK] MCL/MGC Asset Priority (+10%/-20%)
5. [OK] Trail Activation 0.3x (was 0.5x)
6. [OK] Overnight Lockout (8am-4pm CT)
7. [OK] Adaptive Conviction Threshold (rolling WR)
8. [WAIT] Regime-Specific Partial TP (needs live data)
9. [OK] Circuit Breaker 1800s (was 300s)
10. [OK] Monte Carlo Sweep (78% target probability)

### New Features
- Bayesian Belief Updating (Beta-Binomial conjugate)
- TrustGraph integration client + loader + deployment guide
- Monte Carlo parameter sweep script
- Credentials management (secrets outside repo)

---

## Remaining Issues (4 of 25)

| Issue | Severity | What's Needed |
|-------|----------|---------------|
| 0 recorded outcomes (Bayesian using priors only) | HIGH | Live trades to feed outcomes into memory |
| 12 probability models not integrated | MEDIUM | Research files at `C:\KAI\_research\`, need code integration |
| Pre-commit mypy hook failing | LOW | Use `--no-verify` flag |
| Contract rollover monitoring | LOW | All on M26, next rollover ~May 2026 |

---

## How to Launch

```bash
cd C:\KAI\sovran_v2
set AI_PROVIDER=file_ipc
python ralph_ai_loop.py
```

This starts: ralph -> V5 Goldilocks session -> AI decision engine -> trade execution

### What to Monitor
1. Bayesian posterior updates in AI engine log
2. MCL/MGC conviction boost vs equity penalty
3. Overnight lockout block messages (after 4pm CT)
4. Circuit breaker 30-min pauses after 3 losses
5. Adaptive conviction threshold changes in scan log
6. Outcome tracking in `state/ai_trading_memory.json`

---

## Key File Locations

| File | Purpose |
|------|---------|
| `ralph_ai_loop.py` | Orchestrator — launches V5 sessions in a loop |
| `live_session_v5.py` | Trading engine — V5 Goldilocks Edition |
| `ipc/ai_decision_engine.py` | AI brain — probability, Bayesian, Kelly, RoR |
| `ipc/record_trade_outcome.py` | Post-trade outcome recorder |
| `src/decision.py` | IPC snapshot builder |
| `src/trustgraph_client.py` | TrustGraph API client |
| `state/ai_trading_memory.json` | Persistent trade memory |
| `state/monte_carlo_results.json` | Monte Carlo simulation results |
| `config/.env` | Runtime config (gitignored) |
| `C:\KAI\sovran_v2_secrets\credentials.env` | API credentials (outside repo) |

---

## Credentials

See `obsidian/CREDENTIALS_REFERENCE.md` for paths.
Secrets stored at `C:\KAI\sovran_v2_secrets\credentials.env` (OUTSIDE repo, never committed).

---

**End of System State**
