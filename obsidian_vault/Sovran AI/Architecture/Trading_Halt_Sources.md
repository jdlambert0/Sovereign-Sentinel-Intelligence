# Trading halt sources (grep / debug)

Use **API + logs** as truth. Search `_logs/watchdog_restart_stderr.log` and `sovran_run.log` (if fresh).

## Strings and code

| Source | Location | Trigger / meaning |
|--------|----------|---------------------|
| Trailing drawdown floor | `sovran_ai.py` — log line `TRAILING DRAWDOWN FLOOR HIT` … `ALL TRADING HALTED` | Account protection when trail floor breached |
| Daily profit cap | `calculate_size_and_execute` | `Daily Profit Cap (...) reached` — execution halted for consistency |
| Global Risk Vault | `GlobalRiskVault` in `sovran_ai.py` | `GLOBAL LOSS LIMIT REACHED` — aggregate `daily_pnl` vs vault limit; `is_halted` |
| Strategic veto (audit LLM) | `GlobalRiskVault.monitor_loop` | `STRATEGIC VETO` + HALT in audit response |
| Consecutive loss breaker | commented / optional path near `monitor_loop` | Session halt if enabled |
| Max restarts | outer process loop | `MAX RESTARTS ... REACHED` — manual intervention |

## Grep examples (PowerShell)

```text
rg "HALTED|halted|VETO|drawdown" C:\KAI\armada\_logs\watchdog_restart_stderr.log
rg "HALTED" C:\KAI\armada\_logs\sovran_run.log
```

## Related

- [[Bugs/PROBLEM_TRACKER]] (P4)
- [[Broker_API_Realized_PnL]]
