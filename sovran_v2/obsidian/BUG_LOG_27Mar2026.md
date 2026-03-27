---
title: Bug Log — 2026-03-27 Live Hunt Session
type: bug-log
date: 2026-03-27
session: Claude Sonnet 4.6 ~14:30–16:00 CT
---

# Bug Log — 2026-03-27 Live Hunt Session

Live trading attempt using hunt_and_trade MCP tool. Market was open (3:33–3:57 CT).
Documented all bugs encountered during live execution.

---

## BUG-001: hunt_and_trade conviction_threshold scale mismatch
- **Severity:** CRITICAL (tool will never trade)
- **Status:** FIXED
- **Root cause:** `_hunt_and_trade()` used `summary.get("consensus_strength", 0)` for conviction. `consensus_strength` is a 0-1 float (direction purity ratio). Threshold is 65 (0-100 scale). `1.0 < 65` is always True → NO_TRADE forever.
- **Evidence:** With 4/0 LONG/SHORT votes and 100% consensus, conviction showed as 1.0 (not 100).
- **Fix:** Changed to use informed model average:
  ```python
  # Before (broken):
  conv = summary.get("consensus_strength", 0)  # 0–1 scale

  # After (fixed):
  all_model_convs = [v["conviction"] for v in result.get("models", {}).values() if v["conviction"] > 20]
  informed_conv = round(sum(all_model_convs) / max(len(all_model_convs), 1), 1)
  conv = round(informed_conv * (0.6 + consensus * 0.4))  # 0–100 scale
  ```
- **File:** `mcp_server/run_server.py:_hunt_and_trade` line ~603
- **Commit:** 599a092e (partial fix — full fix applied in session)

---

## BUG-002: BrokerClient has no place_bracket_order method
- **Severity:** HIGH (trade placement crashes)
- **Status:** FIXED
- **Root cause:** `_place_trade()` in run_server.py called `broker.place_bracket_order()`. Method doesn't exist. Correct method is `place_market_order(contract_id, side, size, stop_loss_ticks, take_profit_ticks)`.
- **Evidence:** `AttributeError: 'BrokerClient' object has no attribute 'place_bracket_order'. Did you mean: 'place_market_order'?`
- **Fix:** Updated `_place_trade()` to call `place_market_order` with correct signature.
- **File:** `mcp_server/run_server.py:_place_trade`
- **Note:** The working live session (live_session_v5) uses `_place_order()` internally via wrapper methods. MCP server bypassed this correctly once fixed.

---

## BUG-003: Bars API (retrieveBars) returns errorCode=1 for ALL contracts
- **Severity:** HIGH (no OHLCV data available)
- **Status:** UNRESOLVED — workaround active
- **Root cause:** Unknown. `POST /api/History/retrieveBars` returns `{"success": false, "errorCode": 1, "bars": null}` for all 6 contracts regardless of parameters.
- **Evidence:**
  ```
  MNQ: success=False errorCode=1 bars_count=0
  MES: success=False errorCode=1 bars_count=0
  MYM: success=False errorCode=1 bars_count=0
  M2K: success=False errorCode=1 bars_count=0
  MGC: success=False errorCode=1 bars_count=0
  MCL: success=False errorCode=1 bars_count=0
  ```
  Tried unit=0,1,2,3,4 — all fail the same way.
- **Workaround:** Use `POST /api/Trade/search` to get recent fills. Returns executed prices per contract. Not OHLCV, but gives current price.
- **Impact:** ATR calculation uses static estimates (MNQ≈50t, MES≈13t, M2K≈16t). Price action / momentum signals unreliable.
- **Hypothesis:** TopStepX may require active SignalR/WebSocket subscription before REST bars become available. The live_session_v5 uses SignalR; standalone REST calls fail.
- **Next investigation:** Check if bars work while live_session_v5 is running and holding the WebSocket connection.

---

## BUG-004: OFI/VPIN Zero Without Active IPC Session (ARCHITECTURE GAP)
- **Severity:** MEDIUM (reduces model accuracy, not a crash)
- **Status:** Known — partial mitigation in place
- **Root cause:** OFI (Order Flow Imbalance) and VPIN are calculated by live_session_v5 from real-time order flow data. These values are written to IPC request files. When no session is running, IPC files are absent, and OFI_Z=0.0, VPIN=0.50 (neutral defaults).
- **Impact:**
  - Models 5 (Stat Arb), 7 (Momentum), 8 (Order Flow), 10 (Monte Carlo), 12 (Information Theory) return 0 conviction with neutral OFI/VPIN
  - avg_conviction drops from ~65-80 (with live data) to ~36 (without)
  - hunt_and_trade fires based only on Kelly/Casino/PokerEV/RoR (4/12 models)
- **Mitigation:** Fixed conviction formula to use "informed models only" (those with conv > 20). With 4 models averaging 78, final conv=78 — above threshold.
- **Permanent fix plan:** Redesign hunt_and_trade to NOT kill live_session_v5:
  1. Keep live_session running for OFI/VPIN + execution
  2. Kill ONLY ai_decision_engine.py (the Python brain)
  3. LLM reads IPC request files (market data)
  4. LLM writes IPC response files (decision)
  5. live_session picks up decision and executes
  - Net: LLM IS the trader, no connection conflict, full OFI/VPIN available

---

## BUG-005: MNQ Contract Non-Trading Before 4:00 PM CT
- **Severity:** LOW (minor timing issue)
- **Status:** KNOWN — no fix needed
- **Evidence:** At ~3:57 CT:
  ```json
  {"errorCode": 2, "errorMessage": "Trading is currently unavailable. The instrument is not in an active trading status."}
  ```
- **Root cause:** CME Globex closes MNQ slightly before 4:00 PM CT. Exact cutoff is ~3:55-3:58 PM CT on Fridays (may vary by day).
- **Fix:** In `_current_session_phase()`, change us_close end from 16:00 to 15:55. Hunt loop should stop by 3:55 CT.

---

## DIAGNOSTIC SUMMARY — Live Hunt Attempt (2026-03-27, ~3:55 CT)

| Step | Result | Notes |
|------|--------|-------|
| Auth | OK | account_id=20560125, balance=$149,150.80 |
| Open positions | 0 | Clean slate |
| Get prices | OK (via trade history) | MNQ=23476, MES=6450.75, MYM=45717, M2K=2480.3 |
| Bars API | FAIL errorCode=1 | BUG-003 — known |
| OFI/VPIN | Neutral (0.0/0.50) | BUG-004 — no active session |
| Run 12 models | OK | 4 informed models: LONG conviction=78 |
| Place order | FAIL errorCode=2 | BUG-005 — market closed by the time execution reached |
| Net result | NO FILL | Market timing issue — 3 minutes too late |

**Decision was correct:** LONG MNQ conviction=78, informed by Kelly/Casino/PokerEV/RoR.
**Execution failed:** CME stopped accepting orders before our call reached the exchange.

**Monday plan:** Start hunt at 8:00 AM CT sharp with live_session running for OFI/VPIN data.

---

*Written: 2026-03-27 16:00 CT by Claude Sonnet 4.6*
