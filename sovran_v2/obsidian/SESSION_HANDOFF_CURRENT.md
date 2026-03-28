---
title: SESSION HANDOFF — CURRENT STATE (Always Up To Date)
type: session-handoff
updated: 2026-03-27T23:45:00-05:00
next_priority: Monday 8am CT — run `py scripts/llm_as_brain.py` then say "hunt"
---

# SESSION HANDOFF — READ THIS FIRST

**Read this + CODEBASE_MAP.md to get fully up to speed.**

---

## SYSTEM STATUS: WEEKEND — MARKETS CLOSED

Last session closed at ~4pm CT Friday 2026-03-27. Next open: Monday 8:00 AM CT.

---

## CURRENT STATE (as of 2026-03-27 ~23:45 CT)

| Item | Status |
|------|--------|
| Account balance | $149,150.80 |
| Open positions | 0 (clean) |
| Live trades logged | 89 total (3 days) |
| Live PnL | +$337.43 (50% win rate, positive expectancy — winners 2.5x losers) |
| MCP Server | Registered in ~/.claude/settings.json as sovereign-sentinel |
| GitHub | https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence (branch: main) |
| Architecture | **LLM-as-brain (NEW)** — 2-step hunt: dry_run → LLM reasons → place_trade |

---

## WHAT WAS BUILT THIS SESSION (Claude Sonnet 4.6, 2026-03-27 evening)

### Architecture: Hunt V2 — LLM is the Brain

The 12-model voting system was replaced. Only Model 8 (OFI/VPIN) had a real signal.
8/12 were broken, correlated, or fabricating inputs. Now we have:

**5 clean Python signals → semantic English → LLM adversarial reasoning → deterministic contract sizing**

### New Functions in `mcp_server/run_server.py`

| Function | Purpose |
|----------|---------|
| `_compute_signals(snap)` | 5-signal engine: Order Flow, Price Structure (VWAP), Momentum, Volatility Regime, Session Context |
| `_build_hunt_context(...)` | Semantic English packet for LLM — doubled-text (role at top AND bottom) |
| `_calculate_position_size(...)` | TopStepX tier scaling: +$1500→3, +$2000→5 contracts |

### Updated Files

| File | Change |
|------|--------|
| `mcp_server/run_server.py` | Replaced `run_all_models()` with 5-signal system; dry_run now returns `semantic_context`; Step 5 uses `_calculate_position_size()` |
| `src/market_data.py` | Added `vwap: float = 0.0` field to MarketSnapshot |
| `live_session_v5.py` | Passes `tick.vwap` in `_build_snapshot()` |
| `skills/trade/SKILL.md` | Full rewrite: 2-step flow (dry_run → reason → place_trade), adversarial framing, TopStepX sizing rules |
| `obsidian/CODEBASE_MAP.md` | Updated signal architecture, 2-step flow diagram, VWAP data flow |
| `obsidian/kaizen_backlog.md` | RETHINK-1 through RETHINK-4 marked COMPLETED |

### What Kaizen Items Are Done

| # | Item | Status |
|---|------|--------|
| RETHINK-1 | Replace 12 broken models with 5 real signals | [OK] COMPLETED |
| RETHINK-2 | Adversarial bull/bear framing in SKILL.md | [OK] COMPLETED |
| RETHINK-3 | Conviction-based contract scaling (TopStepX tiers) | [OK] COMPLETED |
| RETHINK-4 | Semantic context packet (Python → English) with doubled-text | [OK] COMPLETED |
| RETHINK-5 | Fix prices_history → 20-bar rolling buffer | [TODO] NEXT |

---

## WHAT IS STILL OPEN (NEXT SESSION PRIORITY)

### RETHINK-5: 20-bar prices_history rolling buffer (HIGH PRIORITY — do before Monday)

**Problem:** `live_session_v5.py` currently writes `prices_history = [price]` — a single point.
The `_compute_signals()` momentum engine needs ≥5 prices to activate. Without this,
Signal 3 (Momentum) always returns "UNAVAILABLE" — one of 5 signals is dead.

**Fix needed in `live_session_v5.py`:**
- Add a `deque(maxlen=20)` rolling buffer
- Append close price every bar
- Write full list to IPC snapshot

**Impact:** Activates momentum signal. OFI + VWAP + momentum all aligning = highest-conviction trades.

### Then: Run Verification Tests

1. **VWAP in IPC**: Start live_session, check `ipc/request_*.json` → does `snapshot_data.vwap` exist?
2. **Dry run labels**: Call `hunt_and_trade(dry_run=True)` → does `semantic_context` look correct?
3. **Full adversarial flow**: Say "hunt" → does Claude output BEAR/BULL/SYNTHESIS/DECISION/THESIS?
4. **Daily cap**: Manually set daily pnl=2800 in trade_history.json, call hunt → should get NO_TRADE

---

## THE NEW HUNT FLOW (2-STEP)

```
Old: hunt_and_trade(dry_run=False) → Python math votes → trade placed

New: hunt_and_trade(dry_run=True) → semantic_context
       ↓ LLM reads: BEAR CASE / BULL CASE / SYNTHESIS / DECISION / CONVICTION
       ↓ LLM calls place_trade(conviction=HIGH→85 / MEDIUM→70 / LOW→55, contracts=2-5)
       → trade placed
```

**The calling LLM IS the brain.** hunt_and_trade is now data collection + context building only.

---

## HOW TO TRADE MONDAY

**Step 1** — Start the system (once per session):
```
py -3.12 scripts/llm_as_brain.py
```

**Step 2** — Then just say:
```
hunt
```

The SKILL.md skill fires automatically. It will:
1. Call `hunt_and_trade(dry_run=True)` to get `semantic_context`
2. Reason: BEAR CASE → BULL CASE → SYNTHESIS → DECISION → CONVICTION → THESIS
3. Call `place_trade(...)` with conviction level and correct contract count
4. Loop every 3–5 min until 3:55 PM CT

---

## ARCHITECTURE (CURRENT — CORRECT)

```
live_session_v5 runs → writes ipc/request_*.json (market snapshot + OFI/VPIN + VWAP)
LLM (Claude/Gemini) calls hunt_and_trade(dry_run=True) → gets semantic English context
LLM reasons adversarially → outputs conviction + thesis
LLM calls place_trade() → trade executed with 2-5 contracts
```

**Never kill live_session_v5. It is the OFI/VPIN/VWAP data source.**

---

## KEY FILES

1. `obsidian/SESSION_HANDOFF_CURRENT.md` ← this file
2. `obsidian/CODEBASE_MAP.md` ← find root causes fast
3. `mcp_server/run_server.py` ← main MCP server (3 new functions here)
4. `skills/trade/SKILL.md` ← the hunt skill (updated for 2-step flow)
5. `obsidian/kaizen_backlog.md` ← improvement queue
6. `obsidian/HUNT_RETHINK_27Mar2026.md` ← architecture decision doc

---

## GITHUB

- Repo: https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence
- Branch: genspace → main

---

*Updated: 2026-03-27 ~23:45 CT by Claude Sonnet 4.6*
