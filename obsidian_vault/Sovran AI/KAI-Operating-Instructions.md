# KAI Operating Instructions

**Created:** 2026-03-18
**Updated:** 2026-03-18
**Author:** Jesse Lambert

---

# ALWAYS RUN EVERYTHING

This is the **SUPREME COMMAND** that overrides all other instructions:

> **"I always want you to run everything in a prominent place"**

## What This Means

1. **ALWAYS run code before claiming it works**
2. **ALWAYS verify with actual results, not assumptions**
3. **ALWAYS document what you ran and what happened**
4. **NEVER claim completion without wall-clock verification**
5. **NEVER skip running tests/commands to save time**

## Examples

### WRONG (Don't do this)
```
Assistant: "The code should work now."
User: *runs it* "It doesn't work"
```

### RIGHT (Do this)
```
Assistant: "I'll run the test to verify..."
[executes code]
Assistant: "Result: SUCCESS. The test passed. Output: [actual output]"
```

## Where to Run

- **Trading tests:** Run via `python.exe` directly, capture actual output
- **API calls:** Verify with broker positions check
- **Code changes:** Run linters/tests before declaring fixed
- **Research:** Run web searches, verify sources

## Prominent Display

Include in every response:
```
📋 SUMMARY: What I did
🔍 ANALYSIS: What I found
⚡ ACTIONS: Commands I ran
✅ RESULTS: ACTUAL OUTPUT (not "it should work")
📊 STATUS: Current state
➡️ NEXT: Follow-up actions
```

## The Golden Rule

> **Working code > Theoretical perfection**

If you can't run it, say so. If it fails, document it. If it works, SHOW THE EVIDENCE.

---

# Related Files

- Research: `C:\KAI\obsidian_vault\Sovran AI\Research\TopStepX-API-SLTP-Research-Results.md`
- Session Logs: `C:\KAI\obsidian_vault\Sovran AI\Session Logs\2026-03-18-CONTEXT-LOSS-PLAN.md`
