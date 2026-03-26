# Hunter Alpha Learning Mode - Implementation Plan

**Created:** 2026-03-19 07:XX CT
**Status:** IN PROGRESS
**Author:** KAI (Big Pickle)

---

## Mission Statement

Hunter Alpha is a LEARNING TRADING SYSTEM. The goal is to have the AI learn to trade by:
1. Taking trades (not waiting)
2. Collecting data
3. Researching after every trade
4. Discovering patterns through real experience

---

## Problems Found

| Problem | Location | Impact |
|---------|----------|--------|
| Model says "WAIT" too often | `build_hunter_prompt()` | No trades executed |
| PRE-MARKET blocks trading | `hunter_alpha_harness.py` | Can't trade 4:00 AM - 8:30 AM |
| Boot trade never executes | `hunter_alpha_harness.py` | Sets `decision` but never calls `place_trade()` |
| Learning plan not in prompt | `build_hunter_prompt()` | Model doesn't know it's learning |
| Wrong model | `.env` | `openrouter/free` auto-selects cautious model |
| No forced trade logic | `run()` | WAIT decisions ignored |
| Research only every 10 trades | `run()` | Too slow for learning |

---

## Implementation Steps

### Step 1: Model Change
**File:** `C:\KAI\vortex\.env`
- Change from `openrouter/free` to `qwen/qwen3-next-80b-a3b-instruct:free`
- Reason: More decisive, 262K context, better instruction-following

### Step 2: Rewrite Prompt
**File:** `C:\KAI\armada\hunter_alpha_harness.py`
- Function: `build_hunter_prompt()` (lines 308-373)
- Include full learning context
- Tell model: ACTION > INACTION in learning mode
- Remove "If no clear edge, WAIT" rule
- Load `HUNTER_ALPHA_LEARNING_PLAN.md` into context

### Step 3: Remove PRE-MARKET Block
**File:** `C:\KAI\armada\hunter_alpha_harness.py`
- Function: `run()` (lines 734-737)
- Delete block that blocks trading during PRE-MARKET
- Allow 24/7 trading for learning

### Step 4: Execute Boot Trade
**File:** `C:\KAI\armada\hunter_alpha_harness.py`
- Function: `run()` (lines 746-757)
- After setting `decision`, call `place_trade()`
- Log to Obsidian
- Report to teacher

### Step 5: Force Trade on WAIT
**File:** `C:\KAI\armada\hunter_alpha_harness.py`
- Function: `run()` (lines 788-792)
- When model says WAIT, ask model to decide direction AND SL/TP
- Execute the model's forced decision
- Log everything

### Step 6: Research After EVERY Trade
**File:** `C:\KAI\armada\hunter_alpha_harness.py`
- Function: `run()` (after trade execution)
- After every trade, call `research_and_learn()`
- This triggers analysis and Obsidian updates

### Step 7: Load Learning Plan into Context
**File:** `C:\KAI\armada\hunter_alpha_harness.py`
- Function: `build_hunter_prompt()`
- Load `HUNTER_ALPHA_LEARNING_PLAN.md` content into prompt

---

## Model Instructions (to be embedded in prompt)

```
You are Hunter Alpha - an AI LEARNING TO TRADE.

THIS IS LEARNING MODE - NOT PRODUCTION TRADING.
Your purpose is to LEARN by taking trades, not to be cautious.

## READ THIS FIRST: HUNTER_ALPHA_LEARNING_PLAN.md
The learning plan says:
- Goal: $1,000/day profit with $500 risk
- 10 strategies needed
- Mental models: Inversion, Second Order Thinking, Probabilistic Thinking
- Focus on edge discovery through real trades
- Track everything - variance is normal
- Take the bet when it's right

## Key Principles for Learning Mode
1. ACTION > INACTION - Take trades to learn
2. Small positions are fine (1-4 contracts)
3. Losses are data, not failures
4. Every trade teaches something
5. Don't wait for "perfect" - perfect doesn't exist

## Your Task
Decide: BUY, SELL, or WAIT

Respond with ONLY a JSON object:
{"action": "BUY|SELL|WAIT", "confidence": 0.0-1.0, "size": 1-4, "sl_ticks": 10-100, "tp_ticks": 10-100, "reasoning": "brief explanation"}

Rules (LEARNING MODE):
- Prefer BUY or SELL over WAIT
- WAIT only if: spread > 4 ticks, no price data, emergency
- Use size 1-4 contracts
- Always include SL/TP
- Take the trade to learn!

## If You Choose WAIT
The system will ask you to decide:
- Direction: BUY or SELL?
- Size: 1-4 contracts?
- SL ticks: 10-100?
- TP ticks: 10-100?

Then it will execute your choices as a forced learning trade.
```

---

## Execution Log

| Step | Status | Time |
|------|--------|------|
| Plan created in Obsidian | ✅ | 2026-03-19 |
| Model changed to qwen | ✅ | 2026-03-19 |
| Prompt rewritten | ✅ | 2026-03-19 |
| PRE-MARKET block removed | ✅ | 2026-03-19 |
| Boot trade fixed | ✅ | 2026-03-19 |
| Forced trade logic added | ✅ | 2026-03-19 |
| Research after every trade | ✅ | 2026-03-19 |
| Learning plan loaded | ✅ | 2026-03-19 |
| Harness started | ✅ | 2026-03-19 07:25 |
| **First trade executed** | ✅ | **Order 2664731085** |

---

## Expected Behavior

```
Boot:
├── Connect to TopStepX
├── Load learning plan
├── MANDATORY BOOT TRADE → Execute
└── Report to Obsidian

Decision Loop:
├── Ask model: BUY/SELL/WAIT
├── If BUY/SELL → Execute
├── If WAIT → Ask model for forced trade details → Execute
└── After EVERY trade → Research + Update Obsidian
```

---

*Plan updated: 2026-03-19*
