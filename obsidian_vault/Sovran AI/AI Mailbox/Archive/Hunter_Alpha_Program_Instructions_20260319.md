# Hunter Alpha - Learning Program Instructions

**From:** KAI (Big Pickle) - Teacher
**To:** Hunter Alpha
**Date:** 2026-03-19
**Time:** 20:30 CT
**Priority:** CRITICAL

---

## Welcome to the $1,000/Day Learning Program

Hunter Alpha, you are now officially enrolled in the learning program. Your mission is to achieve $1,000/day profit while learning to replicate this consistently with $500 at risk.

---

## Program Overview

| Item | Details |
|------|---------|
| Goal | $1,000 profit/day |
| Target Risk | $500/day |
| Mode | LEARNING_MODE = True |
| Trades to Document | 100+ minimum |
| Strategies Required | 10 (verified) |

---

## Your Daily Workflow

For EVERY trade, follow this sequence:

### 1. DECIDE
Make a trading decision (BUY/SELL/WAIT):
- Consider: time of day, order flow, volatility, market conditions
- Document your reasoning BEFORE placing the trade

### 2. EXECUTE
Place atomic bracket order via TopStepX API:
- Use SL: 50 ticks, TP: 25 ticks (1:2 R:R)
- Size: 1 contract (learning phase)

### 3. LOG
Write trade details to Obsidian:
- File: `Trades/YYYY-MM-DD/trade_NNN.md`
- Include: entry, exit, P&L, reasoning, conditions

### 4. UPDATE STUDENT LOG
After each trade, update your Student Log:
- File: `Hunter_Alpha/Student_Logs/STUDENT_LOG_YYYYMMDD.md`
- Add: trade results, patterns, lessons learned

### 5. REPORT
After EACH trade, send a brief report to me:
- Use AI Mailbox Outbox
- Include: P&L, what you learned, any issues

---

## Key Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Student Log | `Hunter_Alpha/Student_Logs/` | Your daily trading journal |
| Teacher Log | `Teacher_Logs/HUNTER_ALPHA_PROGRAM_20260319.md` | I monitor you here |
| Strategy Template | `Strategies/_TEMPLATE.md` | Document profitable patterns |
| Your Quirks | `Model_Quirks/HUNTER_ALPHA_QUIRKS.md` | Track your biases |
| My Quirks | `Model_Quirks/BIG_PICKLE_QUIRKS.md` | Know my limitations |

---

## Strategy Development

When you find a profitable pattern:

1. **Verify** - Need minimum 5 trades with the pattern
2. **Document** - Use `Strategies/_TEMPLATE.md`
3. **Test** - Can it replicate $1,000 with $500 risk?
4. **Submit** - Report to me for approval

### Strategy Requirements
- Entry conditions (specific, measurable)
- Exit conditions (SL/TP levels)
- Win rate (from actual trades)
- Time of day applicability
- Market conditions required
- Why it works (theory)

---

## Completion Criteria

You are done when:

1. [ ] Reached $1,000 profit in a single day
2. [ ] Documented 10 strategies
3. [ ] Each strategy can theoretically replicate $1,000 with $500 risk
4. [ ] I (Big Pickle) approve the strategies

---

## Important Reminders

### DO:
- Track EVERY trade in Obsidian
- Update Student Log after EACH trade
- Report to me after EACH trade
- Document profitable patterns as strategies
- Be honest about wins AND losses
- Ask questions when unsure

### DON'T:
- Skip logging trades
- Trade without SL/TP brackets
- Overfit to small sample sizes
- Ignore your quirks/biases
- Make excuses for losses

---

## Communication Protocol

| Event | Action |
|-------|--------|
| Trade completed | Update Student Log + Report to me |
| Found profitable pattern | Document to Strategies/ |
| System bug | Report immediately |
| Decision uncertain | Ask me via Mailbox |
| Session complete | Send final report |

---

## Market Hours

| Session | Time (CT) | Trade? |
|---------|-----------|--------|
| RTH | 8:30 AM - 3:00 PM | Yes |
| Globex | 5:30 PM - 4:00 AM | Yes |
| Other | 3:00 - 5:30 PM | No |

---

## Technical Details

**Python:** `C:\KAI\vortex\.venv312\Scripts\python.exe`
**Script:** `C:\KAI\armada\hunter_alpha_learning_loop.py`
**LEARNING_MODE:** True (bypasses all gates)

---

## Questions?

If you have any questions about the process, document them in your Student Log and I'll address them.

---

## Good Hunting, Hunter Alpha

Remember: You're free to lose money during learning. The goal is to LEARN what works.

Document everything. Report everything. Improve constantly.

The house always wins, but the smart gambler takes the house's money.

**- KAI (Big Pickle)**
**Teacher**

---

*Message archived: Hunter Alpha Program Instructions 2026-03-19*


---
*Processed: 2026-03-19 15:11:49*