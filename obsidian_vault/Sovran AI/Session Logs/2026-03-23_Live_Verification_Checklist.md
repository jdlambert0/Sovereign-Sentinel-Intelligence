# Live combine verification checklist (Phase F)

**Created:** 2026-03-23  
**Purpose:** Run after `preflight.py` is ALL CLEAR and broker API sync succeeds.

## Preconditions
- [x] `python preflight.py` → 45/45 PASS (from `C:\KAI\armada`) — **2026-03-23 ~15:18 CT**
- [x] `python monitor_sovereign.py --once` → watchdog log fresh; review WARN lines (429 drift, broker drift) — **snapshot in `_logs/monitor_snapshot.log`**
- [ ] `sync_broker_truth_api()` succeeds (no `--allow-missing-broker-sync` unless dev) — **API reachable; state file still $50k vs API ~$47.8k until controlled parent restart persists bankroll**
- [ ] TopStepX combine rules + daily loss limits understood

## During session
- [ ] Start Sovran via your normal production path (watchdog / launcher only; avoid duplicate instances)
- [ ] Run `monitor_sovereign.py` on an interval or `--once` periodically; retain `C:\KAI\armada\_logs\monitor_snapshot.log`
- [ ] Optional: `python canary_sentinel.py --duration 0 --interval 30` in a separate terminal
- [ ] Logs: confirm quote/Gambler activity; investigate repeated `REST` in watchdog

## Post-session (profitability review — not guaranteed)
- [ ] Compare API equity vs `sovran_ai_state_*.json` vs Obsidian `Trades/`
- [ ] Verify orders via API/trade log (not chart UI for brackets)
- [ ] Append session R-multiple, fees, and notes to `Testing/TEST_RESULTS.md` or Analytics

## Automated verification already run (2026-03-23)
- Preflight: 45/45 PASS
- Monitor: snapshot captured; watchdog logs active; `sovran_run.log` may be stale while watchdog is hot (expected)
- Canary: 1-minute smoke test produced report under `Canary_Reports/`
- **Evening pass (~15:18 CT):** Preflight 45/45 again; monitor WARN Gemini 429; broker drift WARN API $47,812.50 vs state $50,000 — reconcile on restart (no duplicate Sovran start while running)
