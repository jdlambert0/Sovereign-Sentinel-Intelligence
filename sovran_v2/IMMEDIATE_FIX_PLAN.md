# Immediate Fix Plan - Sovran V2 AI Trading System

**Created:** 2026-03-26 22:45 CT
**Status:** In Progress
**Research Agents:** Running in background (will enhance when complete)

---

## ✅ COMPLETED

### 1. Fix AttributeError: sl_ticks Missing
**Problem:** TradeResult missing sl_ticks attribute causing crashes
**Solution:** Added sl_ticks and tp_ticks to TradeResult dataclass
**File:** `live_session_v5.py` lines 223-243, 1849-1862
**Status:** ✅ FIXED
**Test:** Next trade close should not crash

### 2. Fix Corrupted AI Trading Memory JSON
**Problem:** Extra `}` in ai_trading_memory.json causing JSONDecodeError
**Solution:** Removed extra closing brace, validated JSON
**File:** `state/ai_trading_memory.json`
**Status:** ✅ FIXED
**Test:** Ralph Loop can now load memory without crashing

---

## 🔄 IN PROGRESS

### 3. Add Trade Outcome Tracking to AI Memory
**Problem:** Trades execute but wins/losses stay at 0 in memory
**Current:** Memory records trade initiation only
**Needed:** Post-trade callback to update with actual results

**Implementation:**
```python
# In ai_decision_engine.py - add method:
def record_outcome(self, trade_id: str, outcome: Dict):
    """Update memory with trade outcome"""
    memory = self.load_memory()

    # Update strategy stats
    strategy = outcome["strategy"]
    memory["strategies_tested"][strategy]["wins"] += 1 if outcome["pnl"] > 0 else 0
    memory["strategies_tested"][strategy]["total_pnl"] += outcome["pnl"]

    # Update contract stats
    contract = outcome["contract"]
    memory["performance_by_contract"][contract]["wins"] += 1 if outcome["pnl"] > 0 else 0
    memory["performance_by_contract"][contract]["losses"] += 1 if outcome["pnl"] < 0 else 0
    memory["performance_by_contract"][contract]["total_pnl"] += outcome["pnl"]

    # Update total P&L
    memory["total_pnl"] += outcome["pnl"]

    self.save_memory(memory)
```

**Integration Point:** `live_session_v5.py` line 1870 after trade closes
**Status:** 🔄 IMPLEMENTING NEXT

---

## ⏳ PENDING (After Research Completes)

### 4. Implement Round-Robin Always-Trade Logic
**Problem:** AI returns NO_TRADE when no high-confidence setups
**Philosophy:** "Pick best probability and trade anyway, never sit idle"
**Implementation:** Will use research findings on market maker patterns
**Status:** ⏳ WAITING for research agent

### 5. Add Bayesian Belief Updating
**Problem:** AI uses static probabilities (momentum P=0.60 always)
**Needed:** Learn from actual outcomes, adjust future probabilities
**Implementation:** Will use research findings on gambler "updating the count"
**Status:** ⏳ WAITING for research agent

### 6. Integrate 12 Probability Models Research
**Completed Research:** Kelly, Poker Math, Casino Theory, Market Making, etc.
**Location:** `C:\KAI\_research\12_Trading_Probability_Models_*.md`
**Next Steps:** Select 3-5 models, implement shadow mode testing
**Status:** ⏳ WAITING for review

---

## 🧪 TESTING PLAN

### After Each Fix:
1. Validate code doesn't crash
2. Run 1 trading iteration
3. Check logs for errors
4. Verify expected behavior

### Full Integration Test:
1. Launch Ralph AI Loop with all fixes
2. Run 5 iterations (~25 minutes)
3. Verify:
   - No crashes (sl_ticks fixed)
   - No JSON errors (memory fixed)
   - Outcomes recorded (if implemented)
   - Trades executing
4. Check GitHub auto-commits working
5. Check Obsidian updates working

---

## 📝 OBSIDIAN UPDATE CHECKLIST

After implementation:
- [ ] Update `problem_tracker.md` with fixes applied
- [ ] Update `system_state.md` with current status
- [ ] Create session log for today's fixes
- [ ] Document all code changes

---

## 🔄 GITHUB SYNC CHECKLIST

After implementation:
- [ ] Commit fixed `live_session_v5.py`
- [ ] Commit fixed `ai_trading_memory.json`
- [ ] Commit new AI outcome tracking code
- [ ] Commit updated Obsidian docs
- [ ] Push to main branch
- [ ] Verify CI/CD (if applicable)

---

## 🎯 SUCCESS CRITERIA

**Minimum (This Session):**
- ✅ No more AttributeError crashes
- ✅ No more JSON parse errors
- ⏳ Ralph Loop completes 5 iterations without crashing

**Ideal (This Session):**
- ⏳ Trade outcomes being recorded in memory
- ⏳ Win rate tracking working
- ⏳ All fixes committed to GitHub
- ⏳ Obsidian fully updated

**Future (Next Session):**
- Round-robin logic implemented
- Bayesian updating active
- 12 models integrated
- System learning from every trade

---

**Next Action:** Implement trade outcome tracking (#3)
