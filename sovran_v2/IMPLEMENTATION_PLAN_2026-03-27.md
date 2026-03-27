# Implementation Plan - March 27, 2026

**Created:** 2026-03-27 00:15 CT
**Goal:** Integrate research findings and launch autonomous trading
**Status:** In Progress

---

## Phase 1: Pre-Flight Checks (5 minutes)

### 1.1 Verify All Fixes Applied ✅
- [x] sl_ticks AttributeError fixed
- [x] AI memory JSON valid
- [x] Outcome tracking implemented
- [ ] Test validation

### 1.2 Create Learning Integration Plan
- [ ] Update Obsidian with research integration roadmap
- [ ] Prioritize quick wins from gambling research
- [ ] Document implementation steps

---

## Phase 2: Quick Wins Integration (20 minutes)

### 2.1 Add Kelly Criterion Position Sizing
**File:** `ipc/ai_decision_engine.py`
**Code:** From `_research/gambling_bookkeeping/GAMBLING_STRATEGIES_FOR_TRADING.md`
**Action:**
```python
def kelly_position_size(self, win_rate: float, avg_win: float, avg_loss: float,
                       balance: float, kelly_fraction: float = 0.25) -> float:
    """Calculate position size using Kelly Criterion."""
    if avg_win <= 0:
        return 0.0

    b = avg_win / avg_loss  # Win/loss ratio
    p = win_rate
    q = 1 - p

    # Kelly formula: f* = (bp - q) / b
    kelly_f = (b * p - q) / b

    # Apply fractional Kelly (safer)
    kelly_f *= kelly_fraction

    # Never exceed 5% of bankroll (Ferguson rule)
    kelly_f = min(kelly_f, 0.05)

    return max(0.0, kelly_f)
```

### 2.2 Add Risk of Ruin Monitoring
**File:** `ipc/ai_decision_engine.py`
**Action:** Add RoR calculation to memory system
**Alert:** If RoR > 1%, reduce position sizes

### 2.3 Enhanced Trade Recording
**File:** `ipc/record_trade_outcome.py`
**Action:** Add MFE/MAE tracking for diagnostics

---

## Phase 3: Launch Trading with Agent (10 minutes)

### 3.1 Create Trading Monitor Agent
**Purpose:** Launch Ralph AI Loop in background, monitor for bugs
**Duration:** 5 iterations (~25 minutes)
**Monitoring:**
- Check for crashes
- Verify outcome recording
- Watch for errors
- Monitor P&L

### 3.2 Agent Specifications
```python
Agent: "Trading Monitor"
Task:
- Launch ralph_ai_loop.py with 5 iterations
- Monitor logs for errors
- Report any crashes or bugs
- Track trading performance
- Validate fixes are working
```

---

## Phase 4: Update Obsidian (15 minutes)

### 4.1 Create Learning Integration Plan
**File:** `obsidian/LEARNING_INTEGRATION_PLAN.md`
**Content:**
- Research summary
- Implementation roadmap (4 weeks)
- Quick wins vs long-term
- Success metrics

### 4.2 Update Problem Tracker
- Mark completed items
- Add new tasks from research
- Prioritize based on impact

### 4.3 Update System State
- Current trading status
- Research integrated
- Next steps clear

---

## Phase 5: Validate Trading (Ongoing)

### 5.1 Check After Agent Completes
- [ ] No crashes (sl_ticks fixed)
- [ ] Outcomes recording (wins/losses updating)
- [ ] Trades executing
- [ ] P&L positive or learning

### 5.2 If Issues Found
- Diagnose from logs
- Quick fix
- Restart trading

---

## Success Criteria

**Must Have:**
- ✅ Ralph Loop runs 5 iterations without crash
- ✅ Outcome tracking working (wins/losses updating)
- ✅ No critical errors

**Nice to Have:**
- ✅ Kelly Criterion integrated
- ✅ RoR monitoring active
- ✅ Positive P&L
- ✅ Learning plan in Obsidian

---

## Execution Order

1. ✅ Validate fixes (2 min)
2. ⏳ Add Kelly Criterion (5 min)
3. ⏳ Add RoR monitoring (3 min)
4. ⏳ Enhance trade recording (5 min)
5. ⏳ Create Obsidian learning plan (10 min)
6. ⏳ Launch trading agent (starts 25-min background task)
7. ⏳ Update Obsidian while trading runs (10 min)
8. ⏳ Validate results when agent completes (5 min)

**Total Time:** ~45 minutes (25 min parallel with trading)

---

**Start Time:** 2026-03-27 00:15 CT
**Expected Completion:** 2026-03-27 01:00 CT
