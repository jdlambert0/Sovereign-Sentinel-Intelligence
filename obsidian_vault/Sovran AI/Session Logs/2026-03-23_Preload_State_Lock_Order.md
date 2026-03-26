# Continuation: pre-lock state persist + trailing reset

**Date:** 2026-03-23

## Problem
Watchdog spawns overlapping `sovran_ai.py` instances. Only the lock **winner** reached the old “persist sovereign JSON” step, so losers exited at `FATAL: locked` with **no** disk update — `bankroll_remaining` stayed at `$50,000`.

## Fix
`C:\KAI\armada\sovran_ai.py`
- After successful `sync_broker_truth_api()`, write **all** `sovran_ai_state_{SYMBOL}_SOVEREIGN.json` files **before** `portalocker` (every spawn aligns JSON with API).
- Set `trailing_high_water_mark` / `trailing_drawdown_floor` from API PnL + `TrailingDrawdown.max_drawdown` (fixes stale 50k HWM after placeholder reset).

## Verification
- `preflight.py` → 45/45
- `monitor_sovereign.py --once` → `[6] broker` **OK** (API vs state within $20); realized matches Chicago-day sum
- Duplicate **system Python** vs **venv** stacks can still spawn; prefer one launcher (`launch_armada.py` + venv only) and disable Task Scheduler duplicates if present.
