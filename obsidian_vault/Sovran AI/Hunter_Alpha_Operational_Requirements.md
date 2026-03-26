# Hunter Alpha - Operational Requirements

## IMPORTANT: Always Run from Prominent Place

**Jesse's directive**: Always run commands and processes from a prominent, visible location.

### What This Means

1. **Never run from hidden directories** - Always use visible paths
2. **Keep terminals visible** - Don't background critical processes without logging
3. **Log everything** - All processes should output to log files in `C:\KAI\armada\_logs\`
4. **Make output visible** - Use `wscript` for GUI apps, keep PowerShell windows visible

### Approved Working Directories

| Directory | Purpose |
|-----------|---------|
| `C:\KAI\armada\` | Main trading engine, sovran_ai.py |
| `C:\KAI\armada\topstep_sidecar\` | Node.js sidecar |
| `C:\KAI\armada\_logs\` | All log files |
| `C:\KAI\vortex\` | Vortex trading system |

### How to Run

```batch
# CORRECT - From prominent place with visible output (Direct WS Mode)
cd C:\KAI\armada
python sovran_ai.py --symbol MNQ --mode live --force-direct

# CORRECT - Background with logging
wscript "C:\KAI\armada\StartArmada.vbs"
```

### Logging Requirements

All processes MUST log to:
```
C:\KAI\armada\_logs\
  ├── sovran_today.log        # Main trading engine
  ├── sovran_live_action_v2.log # Current active verification log
  └── sidecar.log             # Node.js sidecar (if used)
```

### Process Management

1. **Check logs first** - Before debugging, check the relevant log file
2. **Make processes visible** - Don't hide processes that should be monitored
3. **Kill stuck processes** - If process hangs, kill and restart from prominent directory

---

## Hunter Alpha Trading Protocol

### Pre-Trade Checklist

- [x] Market hours: 8:30 AM - 3:00 PM CT (M-F)
- [x] Direct WS Bridge ready (market_data_bridge.py)
- [ ] Log file open and visible
- [ ] Account balance verified
- [x] Mock handling patched (for --force-direct safety)

### Trade Execution

1. Start from `C:\KAI\armada\` directory
2. Run: `python sovran_ai.py --symbol MNQ --mode live --force-direct`
3. Watch log: `Get-Content _logs\sovran_live_action_v2.log -Tail 20 -Wait`

### Wide Stop Test Trade

Test parameters for wide stop test:
- Stop Loss: 50 points (wide to avoid premature exit)
- Take Profit: 100 points
- Size: 1 contract
- Symbol: MNQ

### Bug Reporting

If bug occurs:
1. Capture full error from log
2. Note timestamp
3. Document what action triggered it
4. Report to Claude Code session

---
Last Updated: 2026-03-19
