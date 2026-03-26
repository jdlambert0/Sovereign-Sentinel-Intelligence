# SOVEREIGN COMMAND CENTER

> [!IMPORTANT]
> This is the canonical reference for the Sovereign AI project. Read this file FIRST every session.
> Last updated: 2026-03-26 by CIO Agent (Accio Work — Sovran PM)

---

## CURRENT STATUS: V4 KAIZEN LIVE — 220/220 TESTS PASSING

**v1 is CONDEMNED.** See [[Architecture/CODE_AUTOPSY_25Mar2026|Code Autopsy]] for why.

**v2 Foundation is BUILT** at `C:\KAI\sovran_v2\`. All layers complete and tested.

**V4 (Kaizen Edition) is the ACTIVE TRADING ENGINE.**

> [!WARNING]
> V4 (`live_session_v4.py`) is a standalone monolith that does NOT use the `src/` modules.
> The 220 tests validate `src/` — they prove the foundation is sound but don't test the trading engine directly.
> This is a known trade-off. Refactoring to use `src/` is deferred until after combine pass.
> See [[Trader Diary/2026-03-26-V4-Kaizen-Validation]] for the full architecture audit.

### Test Suite

| Module | Tests | File |
|--------|-------|------|
| Broker | 17/17 | `tests/test_broker.py` |
| Risk | 26/26 | `tests/test_risk.py` |
| Market Data | 21/21 | `tests/test_market_data.py` |
| Decision Engine | 27/27 | `tests/test_decision.py` |
| Learning | 18/18 | `tests/test_learning.py` |
| Sentinel | 17/17 | `tests/test_sentinel.py` |
| Integration | 16/16 | `tests/test_integration.py` |
| Scanner | 33/33 | `tests/test_scanner.py` |
| Performance | 17/17 | `tests/test_performance.py` |
| Position Mgr | 28/28 | `tests/test_position_manager.py` |

**Total: 220 tests, 0 failures.**

### To Run
```bash
cd C:\KAI\sovran_v2
py -3.14 live_session_v4.py --cycles 720 --interval 5   # Live trading (1 hour)
py -3.14 -m pytest tests/ -v                             # Run all tests
```

---

## WHAT'S NEXT

V4 is in **live validation mode**. Priority order:

1. **Trade during US Core hours (10-14 CT)** with strict guardrails (-$200 session kill, 4 trade max)
2. **Let the Kaizen engine self-correct** — parameters adapt after every trade
3. **Monitor capture ratio** — should be >50% for sustainable profitability
4. **Review and commit after every session** — preserve context in Obsidian + GitHub
5. **Do NOT refactor** — V4 works, architectural purity waits until after the combine

See [[Trader Diary/2026-03-26-V4-Kaizen-Validation]] for the full operation plan.

---

## TRADING RESULTS

### V4 Kaizen (Current Engine)
| Date | Trades | Wins | PnL | Capture Ratio |
|------|--------|------|-----|---------------|
| 2026-03-26 | 1 | 1 | +$38.48 | 106.9% |

### V2/V3 (Predecessor — Retired)
| Date | Trades | Wins | PnL | Notes |
|------|--------|------|-----|-------|
| 2026-03-25/26 | 11 | 0 | -$220.80 | Trail never activated, all STOP_HIT |

**Lifetime: 12 trades, 1 win, net -$182.32**

---

## PHILOSOPHY

Read [[SOVEREIGN_DOCTRINE]] — the foundational philosophy document. It defines:
- What the system IS (autonomous hunter)
- The Five Laws
- The TopStepX Combine constraint ($9K profit / $4.5K drawdown)
- Why v1 failed
- The rebuild mandate

---

## KEY PATHS

| Path | Purpose |
|------|---------|
| `C:\KAI\obsidian_vault\Sovran AI\` | **Obsidian Vault** — the AI's brain and long-term memory |
| `C:\KAI\sovran_v2\` | **v2 Codebase** — active system |
| `C:\KAI\sovran_v2\live_session_v4.py` | **V4 Trading Engine** — THE file that trades |
| `C:\KAI\sovran_v2\state\trade_history.json` | All trade records |
| `C:\KAI\sovran_v2\state\kaizen_log.json` | Kaizen self-correction audit trail |
| `C:\KAI\armada\` | **v1 Codebase** — DEPRECATED, emergency_flatten.py still usable |
| `C:\KAI\vortex\` | **Research** — prototyping, historical analysis |

## AGENT REGISTRY

See [[Agents/AGENT_REGISTRY|Agent Registry]] for all active agents.

| Agent | Role | Context |
|-------|------|---------|
| CIO Agent | Architecture, PM, QA, Research | [[Agents/SOVRAN_CIO_AGENT]] |
| Coding Agent | Implementation Engineer | [[Agents/CODING_AGENT]] |

## ARCHITECTURE SPECS

| Spec | Layer | Location |
|------|-------|----------|
| Broker Truth | 0 | [[Architecture/Layer_0_Broker_Spec]] |
| Guardian/Risk | 1 | [[Architecture/Layer_1_Risk_Spec]] |
| Market Data | 2 | [[Architecture/Layer_2_MarketData_Spec]] |
| Decision Engine | 3 | [[Architecture/Layer_3_Decision_Spec]] |
| Learning Loop | 4 | [[Architecture/Layer_4_Learning_Spec]] |
| Sentinel/Ops | 5 | [[Architecture/Layer_5_Sentinel_Spec]] |

---

## ACCOUNT & TRADING

- **Broker**: TopStepX via ProjectX API
- **Account ID**: 20560125
- **Account**: 150k Combine evaluation
- **Balance**: $148,637.72 (as of 2026-03-26 morning)
- **Pass Condition**: +$9,000 before -$4,500 trailing drawdown
- **Remaining Drawdown Budget**: ~$3,138
- **Daily Soft Limit**: -$450
- **Instruments**: MNQ M26 (primary), MES, MYM, M2K, MGC, MCL (V4 scans all 6)
- **API Base**: `https://api.topstepx.com`
- **Credentials**: See `config/.env` in sovran_v2
- **Constraint**: Only ONE WebSocket connection per account

## V1 LESSONS (DO NOT REPEAT)

1. Stop losses must call the broker API — local-only updates are fake
2. Never use MagicMock or test doubles in production
3. Never hardcode PnL or balance values
4. Every order must be verified after placement
5. One WebSocket connection only
6. No `except: pass` — handle errors or raise them

## V4 LESSONS (LEARNED LIVE)

7. Trail activation must be aggressive — 0.5x SL, not 1.0x (profit capture)
8. Never trade with regime=unknown — hard block conviction to 0
9. Bar gate must match regime detection minimum (10 bars, not 3)
10. Flow vs bars conflict = hard block, not penalty
11. Overnight trading = noise — restrict to 8 AM - 4 PM CT
12. Never run multiple WebSocket connections — kill old sessions first
13. Partial TP at 0.6x SL locks guaranteed profit before reversal

## GITHUB

- **Repo**: https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence
- **Branch**: `main`
- **Local**: `C:\KAI` monorepo, branch `genspace` — push sovran_v2/ files selectively to `origin/main`
- **Sync Protocol**: After every session → `git add sovran_v2/... && git commit && git push origin genspace:main`

---
#sovereign #command-center #status #v4 #kaizen #live-trading
