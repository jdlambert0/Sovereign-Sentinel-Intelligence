# 10-Trade Autonomous Stress Test Plan

**Date**: 2026-03-18/19
**Time Started**: 20:06 CT
**Target**: 10 trades with atomic SL/TP brackets
**Mode**: LEARNING_MODE = True (bypasses all safety gates)

---

## Environment Verified

| Component | Status | Location |
|-----------|--------|----------|
| Python venv | ✅ | `C:\KAI\vortex\.venv312` |
| project_x_py | ✅ v3.5.9 | Installed in venv |
| API Key | ✅ | `9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=` |
| Account ID | ✅ | 18410777 |
| WebSocket | ⚠️ Errors (REST fallback) | Normal behavior |
| Market | ✅ | Globex OPEN |

---

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Symbol | MNQ |
| Direction | Alternating (LONG/SHORT) |
| Size | 1 contract |
| SL Distance | 50 ticks |
| TP Distance | 25 ticks |
| LEARNING_MODE | True |
| Throttle | Disabled |

---

## Trade Execution Plan

| Trade # | Direction | Expected Outcome | Verification |
|--------|-----------|------------------|--------------|
| 1 | LONG | Entry + SL + TP | Check TopStepX |
| 2 | SHORT | Entry + SL + TP | Check TopStepX |
| 3 | LONG | Entry + SL + TP | Check TopStepX |
| 4 | SHORT | Entry + SL + TP | Check TopStepX |
| 5 | LONG | Entry + SL + TP | Check TopStepX |
| 6 | SHORT | Entry + SL + TP | Check TopStepX |
| 7 | LONG | Entry + SL + TP | Check TopStepX |
| 8 | SHORT | Entry + SL + TP | Check TopStepX |
| 9 | LONG | Entry + SL + TP | Check TopStepX |
| 10 | SHORT | Entry + SL + TP | Check TopStepX |

---

## Verification Checklist

- [ ] Trade 1 placed with SL/TP
- [ ] Trade 2 placed with SL/TP
- [ ] Trade 3 placed with SL/TP
- [ ] Trade 4 placed with SL/TP
- [ ] Trade 5 placed with SL/TP
- [ ] Trade 6 placed with SL/TP
- [ ] Trade 7 placed with SL/TP
- [ ] Trade 8 placed with SL/TP
- [ ] Trade 9 placed with SL/TP
- [ ] Trade 10 placed with SL/TP
- [ ] All SL/TP visible on TopStepX
- [ ] Results logged to Obsidian

---

## Success Criteria

| Criteria | Target | Status |
|----------|--------|--------|
| All 10 trades placed | 10/10 | Pending |
| SL/TP attached | 10/10 | Pending |
| No errors | 0 | Pending |
| Order IDs captured | 10 | Pending |

---

*Test started: 2026-03-18 20:06 CT*
