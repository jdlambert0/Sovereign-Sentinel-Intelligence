# Complete Bug Inventory — Sovran AI Kill List

**Date:** 2026-03-14 | **Total Bugs Found:** 15 | **All Fixed:** ✅ | **Preflight:** 37/37 PASS

## Status: ✅ ALL BUGS KILLED IN BATCH

---

## Phase 1: Code Audit Bugs (Fixed Earlier)

| # | Bug | Severity | Root Cause | Fix |
|---|-----|----------|------------|-----|
| 1 | JSON parser fails on multi-line LLM responses | 🔴 CRITICAL | Only matched single-line `{...}` | `rfind("{")` + line-by-line fallback |
| 2 | Daily PnL never resets | 🔴 CRITICAL | No date tracking between sessions | Date comparison + reset at midnight |
| 3 | Confidence gate at 0.30 instead of 0.50 | 🟡 HIGH | Code/prompt mismatch | Changed to `confidence < 0.50` |
| 4 | Ensemble voting case-sensitive | 🟡 HIGH | `"BUY"` vs `"Buy"` | Added `.upper()` to all filters |
| 5 | Infinite restart loop (no backoff) | 🟡 HIGH | `while True` + flat 15s delay | Exponential backoff, 50 max restarts |

## Phase 2: Online Research Bugs (Fixed Earlier)

| # | Bug | Severity | Root Cause | Fix |
|---|-----|----------|------------|-----|
| 6 | Silent WebSocket (heartbeat masks dead feed) | 🔴 CRITICAL | SignalR heartbeat ≠ data flow | Quote counter, 0 in 5min = reconnect |
| 7 | Stale data fed to AI after blocking LLM call | 🟡 HIGH | LLM takes 15-30s, data ages | Check data age < 30s before LLM call |
| 8 | TopStepX single-connection conflict | 🟡 HIGH | Only 1 API session per username | Startup warning logged |

## Phase 3: Comprehensive Sweep Bugs (Fixed Now — Batch)

| # | Bug | Severity | Root Cause | Fix |
|---|-----|----------|------------|-----|
| 9 | **State file corruption on crash** | 🔴 CRITICAL | `json.dump` directly to file → crash mid-write = corrupt | Atomic write: `.tmp` → `os.replace()` |
| 10 | **Ensemble WAIT falls through to decisions[0]** | 🔴 CRITICAL | No explicit return for WAIT majority → could execute a trade when all models said WAIT | Explicit `return WAIT` when no BUY/SELL consensus |
| 11 | **Orphaned position has stop=0.0, target=0.0** | 🔴 CRITICAL | On crash recovery, mock_position_check hits `current >= target(0.0)` → immediately closes at loss | Emergency stop=15pts, target=30pts from avg price |
| 12 | **Restart counter resets BEFORE run()** | 🟡 HIGH | `_restart_count = 0` at top of try → crash always resets counter → infinite restarts | Moved reset AFTER `asyncio.run(run())` returns |
| 13 | **OFI history never prunes stale entries** | 🟡 MED | Old timestamps accumulate beyond window size | Time-based prune: entries > 10 min removed |
| 14 | **Session range NaN on first boot** | 🟡 MED | `high=float("-inf")` checked against `float("inf")` (wrong comparison) | Fixed: checks `high == -inf` OR `low == inf` |
| 15 | **Unused `final_decision` variable** | 🟢 LOW | `final_decision = decisions[0]` assigned but never used | Removed dead code |

---

## Most Dangerous Bugs (Would Have Hit Monday)

> [!CAUTION]
> **Bug 10 (Ensemble WAIT fallthrough)** — If both models returned WAIT but fell through the vote logic, the system would execute `decisions[0]` which could be a BUY or SELL. This would bypass ALL safety gates because the decision already passed the gate checks.

> [!CAUTION]
> **Bug 11 (Orphaned position stop=0.0)** — If the bot crashed mid-trade and restarted, the recovered position had `target=0.0`. Since `current_price >= 0.0` is always true, `mock_position_check` would immediately close the position at a massive loss.

> [!CAUTION]
> **Bug 9 (State file corruption)** — A crash during `json.dump` would leave a partially-written JSON file. On restart, `GamblerState.load()` catches `JSONDecodeError` and returns defaults — resetting `daily_pnl`, `consecutive_losses`, and `trailing_drawdown` to zero. This could allow trading past the daily loss limit.

---

## Preflight Validation

```
PREFLIGHT: ✅ ALL CLEAR (37/37 passed, 0 warnings)
System is cleared for Monday deployment.
```
