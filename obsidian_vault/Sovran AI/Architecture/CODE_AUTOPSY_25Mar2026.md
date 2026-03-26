# Code Autopsy — 2026-03-25
## Why The Current System Cannot Work

> This document is the honest forensic analysis of `sovran_ai.py` and `projectx_broker_api.py`.
> It explains why stop losses still don't work after weeks of fixing, and why the "christmas tree" approach must end.

---

## THE SMOKING GUNS

### 1. Stop Losses Are Fake (The #1 Bug)
**`move_stop_to_breakeven()` only updates local Python state — it never calls the broker API.**

```python
# Line 2390-2391 in sovran_ai.py
# In a real scenario, we would also update the bracket on the broker.
# But if the CLI is dead, we prioritize internal safety logic.
```

This means: when the AI thinks it moved your stop to breakeven, **your real stop on the broker is still at the original level.** The AI believes it protected you. It didn't.

### 2. Bracket Verification is Fake
`verify_bracket_integrity()` (Line 2308) checks if *any* stop or limit order exists in the account — not whether the *current trade* has its specific bracket. If you had a manual order from yesterday, it would pass verification even with zero protection on the live trade.

### 3. The Balance Resets Every Restart
Lines 3449-3467: The "ANTIGRAVITY MASTER SYNC OVERRIDE" hardcodes `tpnl = 106.25` and `actual_balance = 149788.27`. **Every time the bot starts, it overwrites your real PnL with stale values from a past session.** This is why PnL tracking drifts.

### 4. Emergency Procedures Use MagicMock
When the `TradingSuite` fails to initialize (Line 3543), the system falls back to `MagicMock` — a testing library that returns fake success for every method call. The system then enters "Extreme Degraded" mode where it *thinks* it's executing trades but is talking to a mock object.

### 5. Orphan Recovery Assigns Random Stops
`recover_active_position()` (Line 2393) finds positions left by dead sessions and assigns **hardcoded default stops** (15pts/30pts) instead of recovering the AI's intended values. Every restart potentially changes your risk exposure.

### 6. `fetch_price_from_suite` is Defined Twice
Lines 1182 and 1207 — exact duplicate function definitions. This is a symptom of copy-paste debugging.

---

## ARCHITECTURAL PROBLEMS

| Problem | Description |
|---------|-------------|
| **Split-brain state** | Local Python state and broker state diverge because modifications happen locally without API calls |
| **JSON file IPC** | Multi-process engines sync via JSON files read every 15s — stale data, file locking issues |
| **Monkey-patching** | Lines 270-390 patch `signalrcore` and `project_x_py` internals — breaks on any library update |
| **Global state in multiprocess** | `_trades_today` and `_system_status` are process-local globals treated as shared |
| **Error swallowing** | Critical paths wrapped in `except: pass` — failures are logged but execution continues as if successful |
| **Veto fail-closed** | A single malformed JSON character from the LLM triggers "Fail Closed" with no retry, blocking valid trades |

---

## FILE MANIFEST

| File | Purpose | Status |
|------|---------|--------|
| `sovran_ai.py` | Main engine — risk, orders, AI brain | ~3,600 lines, heavily patched, needs rebuild |
| `projectx_broker_api.py` | REST client — auth, accounts, PnL | Cleanest component, salvageable |
| `realtime_bridge.py` | WebSocket data via Node.js sidecar | Works but adds unnecessary complexity |
| `hunter_alpha_harness.py` | LLM persona for trading decisions | Depends on broken sovran_ai internals |
| `emergency_flatten.py` | Nuclear option — close everything | Simple, works, keep it |
| `autonomous_sovereign_loop.py` | Production runner | Wrapper, will be replaced |
| `canary_sentinel.py` | Health watchdog | Concept is good, implementation needs rework |
| `learning_system.py` | Obsidian logging + trade memory | Good concept, poor integration |
| `curiosity_engine.py` | Research node generator | Generates content but doesn't feed back into trading |
| `l2_watcher.py` | Level 2 order flow monitor | Good data source, needs cleaner API |

---

## VERDICT

The system is not patchable. The architecture was built by accretion — each bug fix added a new layer without addressing the structural cause. The result is a system where:
- **Safety mechanisms don't actually protect you** (local-only stop moves)
- **State tracking lies to you** (hardcoded balance overrides)
- **Failure modes are invisible** (MagicMock in production)

The correct path is a clean rebuild using `projectx_broker_api.py` as the foundation (it's the healthiest component) and building upward layer by layer, testing each layer before adding the next.

---
#architecture #audit #critical #rebuild
