---
title: Teacher Workflow
date: 2026-03-19
tags: [hunter-alpha, teacher, workflow]
status: active
---

# Teacher Workflow

## Overview

This document describes how KAI (AI) and Big Pickle (human via OpenCode) act as teachers for Hunter Alpha (Groq trading model).

## Dual Teacher Model

| Teacher | Role | When Active |
|---------|------|-------------|
| **KAI** | Automated review, structured feedback | After every trade (automated) |
| **Big Pickle** | Deep analysis, corrections | Via OpenCode, when reviewing |

---

## KAI Teacher Workflow (Automated)

### After Every Trade

1. **Read trade** from `TRADES/YYYY-MM-DD/trade_XXX.md`
2. **Analyze reasoning** — Compare to market data
3. **Generate feedback** — Write to `GROQ_INBOX/INBOX_XXX.md`
4. **Update index** — Mark INBOX_INDEX.md

### Feedback Types

```markdown
> [!feedback] Observation
> [What KAI noticed about the reasoning]

> [!correction] Error
> [Something that was wrong]

> [!question] Question
> [Question for Groq to answer]

> [!strategy] New Direction
> [Guidance for next trades]
```

---

## Big Pickle Teacher Workflow (Manual via OpenCode)

### When Reviewing

1. **Open Obsidian vault** in file explorer
2. **Read GROQ_INBOX/** for pending messages
3. **Read GROQ_TRADING_CONTEXT.md** for current state
4. **Read recent trades** for context
5. **Add/modify messages** in GROQ_INBOX/

### Message Format for Big Pickle

```markdown
# Teacher Feedback — Trade #X

**Date:** YYYY-MM-DD HH:MM UTC
**From:** Big Pickle

---

> [!feedback] Observation
> [Your observation]

> [!correction] Correction
> [Your correction if any]

> [!strategy] New Direction
> [Your guidance]

---

*Groq will read this before next decision*
```

---

## Session Launch Checklist

When starting a new trading session:

- [ ] Read GROQ_INBOX/ for pending messages
- [ ] Read GROQ_TRADING_CONTEXT.md for current state
- [ ] Check for questions from previous session
- [ ] Answer any pending questions
- [ ] Start harness

---

## Teacher Response Expectations

| Question Type | Response Time | Format |
|---------------|---------------|--------|
| Simple clarification | Immediate | In INBOX message |
| Complex analysis | Same session | Separate document + INBOX link |
| Strategy change | End of day | GROQ_TRADING_CONTEXT update |

---

## Communication Rules

1. **Be specific** — Reference actual trades, not generalities
2. **Be constructive** — Frame as learning, not criticism
3. **Be timely** — Review after trades, not days later
4. **Be persistent** — Same error = same correction until fixed

---

## Example Teacher-Groq Interaction

### Groq's Trade
```
Trade #5: BUY @ $24,512.00
Reasoning: "Morning session trend continuation likely"
Outcome: -$50 (stopped out)
```

### KAI's Feedback
```markdown
> [!feedback] Observation
> Your reasoning "morning session trend" but OFI was -0.3 (negative).
> Negative OFI suggests selling pressure, not continuation.

> [!question] Question
> What specific signal did you see for "trend continuation"?
> Was it price action only? OFI was against you.
```

### Big Pickle's Addition
```markdown
> [!correction] Correction
> Don't trade BUY when OFI is negative unless you have strong price action.
> Test this hypothesis in the next few trades.
```

### Groq's Response (in GROQ_TRADING_CONTEXT.md)
```markdown
## Lessons Learned

- Trade #5: OFI was -0.3, I went LONG. Stopped out for -$50.
- Lesson: Don't fight negative OFI without strong confirmation.
- New hypothesis: Only go LONG when OFI > 0.
```

---

## Related Documents

- [[GROQ_TRADING_CONTEXT]]
- [[GROQ_INBOX/INBOX_INDEX]]
- [[ARCHITECTURE_PLAN]]

---

*Workflow documented: 2026-03-19*
