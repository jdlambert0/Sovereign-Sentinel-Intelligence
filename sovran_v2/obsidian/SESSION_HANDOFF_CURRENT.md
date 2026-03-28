---
title: SESSION HANDOFF — CURRENT STATE (Always Up To Date)
type: session-handoff
updated: 2026-03-28T09:15:00-05:00
next_priority: Monday 8am CT — start live_session, say "hunt"
---

# SESSION HANDOFF — READ THIS FIRST

**System is fully built, tested offline, and ready for live trading Monday.**

---

## SYSTEM STATUS: WEEKEND — READY FOR MONDAY

| Item | Status |
|------|--------|
| Account balance | $149,150.80 |
| Open positions | 0 (clean) |
| Architecture | LLM-as-brain (5 signals + adversarial reasoning) |
| MCP Server | Registered as `sovereign-sentinel` in ~/.claude/settings.json |
| GitHub | https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence (synced) |
| All offline tests | 13/13 PASSED |

---

## VERIFIED: 13/13 TESTS PASS

| Test | Result |
|------|--------|
| IPC reader: extracts snapshot_data, normalizes fields | PASS |
| 6-contract scan: all contracts scored, winner selected | PASS |
| Bearish scenario: OFI -2.4s -> SHORT direction | PASS |
| Daily cap: pnl=$2800 -> NO_TRADE (TopStep consistency rule) | PASS |
| Caution mode: pnl=$2100 raises threshold to 80 | PASS |
| Strong signal overrides caution (conv 96 >= 80) | PASS |
| News veto gate: FOMC/CPI within 30min blocked | PASS |
| Position sizing: all 4 TopStepX tiers correct | PASS |
| Semantic context: doubled-text, readable English | PASS |
| ORB bonus: power_hour breakout adds +8 conviction | PASS |
| Momentum: UNAVAILABLE when prices_history empty | PASS |
| MCP server starts without import/startup errors | PASS |
| All 4 modified files: syntax clean | PASS |

**One bug found and fixed during testing:**
- `_get_market_snapshot` was reading `contract_id` from IPC top level instead of
  `snapshot_data` nested dict. This caused empty `contract_snaps` -> NO_TRADE on every hunt.
  Fixed: now extracts `snapshot_data`, normalizes field names before returning.

---

## WHAT WAS BUILT THIS SESSION (2026-03-27 to 2026-03-28)

| Change | File | Status |
|--------|------|--------|
| Add `vwap` field to MarketSnapshot | `src/market_data.py` | DONE |
| Pass `tick.vwap` through `_build_snapshot()` | `live_session_v5.py` | DONE |
| Add `prices_history` to MarketSnapshot + IPC | `src/market_data.py`, `src/decision.py`, `live_session_v5.py` | DONE |
| Replace 12-model voting with `_compute_signals()` | `mcp_server/run_server.py` | DONE |
| Add `_build_hunt_context()` with doubled-text | `mcp_server/run_server.py` | DONE |
| Add `_calculate_position_size()` TopStepX tiers | `mcp_server/run_server.py` | DONE |
| NEW-2: `_check_news_veto()` (2026 calendar) | `mcp_server/run_server.py` | DONE |
| ORB bonus signal (power_hour +8 conviction) | `mcp_server/run_server.py` | DONE |
| Fix IPC reader (`_get_market_snapshot`) | `mcp_server/run_server.py` | DONE |
| Fix MEDIUM contract sizing (banker's rounding) | `mcp_server/run_server.py` | DONE |
| Fix Unicode: sigma + em-dash -> ASCII | `mcp_server/run_server.py` | DONE |
| 2-step skill flow (dry_run -> reason -> trade) | `skills/trade/SKILL.md` | DONE |
| Update CODEBASE_MAP.md | `obsidian/CODEBASE_MAP.md` | DONE |
| All kaizen RETHINK items 1-5 | Multiple files | DONE |

---

## HOW TO START MONDAY

**Step 1** — Start the data provider (once, at the beginning of the session):
```
py -3.12 scripts/llm_as_brain.py
```

**Step 2** — Say "hunt" in Claude Code CLI. That's it.

The skill fires automatically and does:
1. `hunt_and_trade(dry_run=True)` -> gets `semantic_context`
2. LLM reasons: BEAR CASE / BULL CASE / SYNTHESIS / DECISION / CONVICTION / THESIS
3. `place_trade(...)` with conviction-based contract sizing (2-5 contracts)

**One live test still needed:**
- After live_session starts, check `ipc/request_*.json` → confirm `vwap` and `prices_history` are populated (not 0.0 / empty)
- This verifies the full data pipeline end-to-end with real market data

---

## THE NEW HUNT FLOW (LLM IS THE BRAIN)

```
live_session_v5.py (always running)
  -> computes OFI/VPIN/VWAP/prices_history
  -> writes ipc/request_*.json every tick

Claude Code "hunt" command
  -> hunt_and_trade(dry_run=True)
     -> reads IPC, builds 5 signals, builds semantic English context
     -> returns semantic_context to LLM
  -> LLM reasons adversarially (BEAR/BULL/SYNTHESIS)
  -> LLM calls place_trade(conviction=HIGH, contracts=2-5)
  -> trade placed with correct size
```

---

## SIGNAL ARCHITECTURE (5 SIGNALS)

| # | Signal | Source | Weight |
|---|--------|--------|--------|
| 1 | Order Flow | OFI z-score + VPIN | PRIMARY ORACLE |
| 2 | Price Structure | VWAP deviation + session range | Alignment bonus +10 |
| 3 | Momentum | 20-bar rolling price history | Alignment bonus +5 |
| 4 | Volatility Regime | ATR vs avg ATR | Penalty -10 if high |
| 5 | Session Context | Time of day (CT) | Context only |
| 6 | ORB Bonus | Power hour + session H/L break | Bonus +8 |

**Decision gates (in order):**
1. News veto (FOMC/CPI/NFP within 30 min) -> NO_TRADE
2. Daily cap ($2,700) -> NO_TRADE
3. Outside hours (before 8am / after 4pm CT) -> NO_TRADE
4. Caution mode (pnl > $2,025) -> raise threshold to 80
5. Conviction below threshold -> NO_TRADE (LLM can still override with LOW probe)

---

## CONTRACT SIZING (TopStepX Tiers)

| Account gain | Platform max | HIGH | MEDIUM | LOW |
|-------------|-------------|------|--------|-----|
| < $1,500 | 2 contracts | 2 | 1 | 1 |
| +$1,500 | 3 contracts | 3 | 2 | 1 |
| +$2,000 | 5 contracts | 5 | 3 | 1 |
| Caution mode | capped at 1 | 1 | 1 | 1 |

Current account: $149,150 - $147,000 = +$2,150 -> **platform max = 5 contracts**

---

## OPEN ITEMS (Monday live trading will resolve)

| # | Item | Status | Blocker |
|---|------|--------|---------|
| Live IPC field check | Verify vwap+prices_history in real IPC files | PENDING | Needs live_session running |
| Partial TP validation | Validate 0.6x SL partial TP | PENDING | Needs live trades |
| Regime-specific TP | Trending=0.8x SL, Ranging=0.5x SL | LOW PRIORITY | Needs live data |
| ORB high/low tracking | Dedicated ORB buffer (not session H/L proxy) | FUTURE | Week 2 |

---

## KEY FILES (READ THESE TO UNDERSTAND THE SYSTEM)

1. `obsidian/CODEBASE_MAP.md` — find anything fast
2. `mcp_server/run_server.py` — all 4 new functions here
3. `skills/trade/SKILL.md` — the hunt skill (2-step flow)
4. `obsidian/kaizen_backlog.md` — what's done, what's open
5. `obsidian/HUNT_RETHINK_27Mar2026.md` — architecture decision record

---

*Updated: 2026-03-28 09:15 CT by Claude Sonnet 4.6 — 13/13 tests passing, ready for Monday*
