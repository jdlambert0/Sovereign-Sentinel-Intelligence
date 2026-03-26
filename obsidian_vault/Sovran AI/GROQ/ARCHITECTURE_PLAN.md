---
title: GROQ Trading System Architecture Plan
date: 2026-03-19
tags: [hunter-alpha, architecture, groq, plan]
status: approved
---

# GROQ Trading System Architecture Plan

**Date:** 2026-03-19
**Status:** Approved for Implementation
**Version:** 1.0

---

## Overview

This document describes the dual-agent architecture for Hunter Alpha trading system, separating KAI's context (for KAI AI) from Groq's context (for the trading model), with Obsidian as the central brain.

## Problem Being Solved

**Current Issue:** Groq model repeats same reasoning because:
- No persistent memory between decisions
- Context is reset every call
- Trades not influencing future decisions
- No teacher feedback loop

**Solution:** Obsidian-centric persistent brain where:
- All context lives in Obsidian
- Groq reads/writes to Obsidian
- KAI and Big Pickle review via OpenCode
- Teacher feedback loop established

---

## Architecture

### Dual-Context Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        OBSIDIAN VAULT                             │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ KAI_Continuation│  │GROQ_TRADING_CTX │  │   GROQ_INBOX    │  │
│  │  (for KAI AI)  │  │ (for Groq AI)  │  │ (KAI→Groq msgs) │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                        TRADES/                              │  │
│  │           Groq logs here after every trade                   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                     LEARNINGS/STRATEGIES/                   │  │
│  │     Full strategy docs, mental models, insights              │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ▲                    │
         │                    ▼
    ┌────┴────┐        ┌──────┴──────┐
    │   KAI   │◄──────►│    Groq     │
    │  (AI)   │        │  (Trader)   │
    └─────────┘        └─────────────┘
         ▲                    │
         │                    ▼
    ┌────┴────────────────────┴────┐
    │        Big Pickle           │
    │    (Human via OpenCode)     │
    └─────────────────────────────┘
```

---

## File Structure

```
C:\KAI\obsidian_vault\Sovran AI\
│
├── AI_Continuation_Document-[DATE]-[TIME].md     ← KAI's handoff
│
├── GROQ\
│   ├── GROQ_TRADING_CONTEXT.md                  ← Groq's persistent state
│   ├── GROQ_TRADING_CONTEXT_2026-03-19.md      ← Daily snapshot (auto)
│   ├── GROQ_INBOX\
│   │   ├── INBOX_001.md                         ← Teacher → Groq messages
│   │   └── INBOX_INDEX.md                       ← List of pending messages
│   ├── GROQ_RESUME_PROMPT.md                   ← Groq's resume prompt
│   └── TEACHER_WORKFLOW.md                      ← Teacher workflow docs
│
├── TRADES\
│   └── 2026-03-19\
│       ├── trade_001.md
│       └── _index.json
│
├── LEARNINGS\
│   ├── HUNTER_ALPHA_LEARNING_PLAN.md
│   ├── STRATEGIES\
│   │   └── strategy_001.md
│   └── INSIGHTS\
│       └── insight_001.md
│
└── SESSION_LOGS\
    └── session_2026-03-19.md
```

---

## Teacher Workflow

### Timing
- **After every trade**: KAI reviews reasoning, Big Pickle reviews via OpenCode

### INBOX Message Format

Messages use structured categories with callout boxes:

```markdown
> [!feedback] Observation
> Your reasoning mentions...

> [!correction] Correction
> You made an error here...

> [!question] Question for you
> Why did you choose...

> [!strategy] New direction
> Focus on...
```

### Dual Teacher Model

| Teacher | Role |
|---------|------|
| **KAI (AI)** | Automated review, structured feedback, research, answer questions |
| **Big Pickle (You)** | Deep analysis, corrections, new directions, approve/reject strategies |

---

## Implementation Steps

| Step | Action | Status |
|------|--------|--------|
| 1 | Create GROQ folder structure | ⏳ |
| 2 | Create GROQ_TRADING_CONTEXT.md | ⏳ |
| 3 | Create GROQ_INBOX/INBOX_INDEX.md | ⏳ |
| 4 | Create GROQ_RESUME_PROMPT.md | ⏳ |
| 5 | Create TEACHER_WORKFLOW.md | ⏳ |
| 6 | Modify hunter_alpha_harness.py for GROQ integration | ⏳ |
| 7 | Update AI_Continuation_Document | ⏳ |

---

## Context Management

### Groq Context (GROQ_TRADING_CONTEXT.md)
- **Persistent**: Accumulates forever, never resets
- **Size**: ~2000 tokens max (concise summary)
- **Contents**: Current state, questions, strategies, recent activity

### Trades
- **Stored in**: TRADES/YYYY-MM-DD/trade_XXX.md
- **Groq reads**: When needed via file queries
- **Not in prompt**: Keeps Groq context small

### Strategies
- **Summary**: GROQ_TRADING_CONTEXT.md
- **Details**: LEARNINGS/STRATEGIES/ (separate files)

---

## Verification Checklist

- [ ] GROQ folder created
- [ ] GROQ_TRADING_CONTEXT.md created
- [ ] GROQ_INBOX structure created
- [ ] GROQ_RESUME_PROMPT.md created
- [ ] TEACHER_WORKFLOW.md created
- [ ] hunter_alpha_harness.py modified
- [ ] Groq produces unique reasoning per trade
- [ ] Teacher feedback loop working

---

## Related Documents

- [[AI_Continuation_Document-19Mar2026-1415]]
- [[GROQ_TRADING_CONTEXT]]
- [[GROQ_RESUME_PROMPT]]
- [[TEACHER_WORKFLOW]]

---

*Plan documented: 2026-03-19 15:00 UTC*
*Status: Approved for implementation*
