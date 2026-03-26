# Bug Prevention Framework for AI-Assisted Development

**Date**: 2026-03-17  
**Purpose**: Prevent fix→bug loop in AI-assisted trading system development

---

## The Problem

AI models tend to:
1. Make assumptions about code state
2. Not check logs before debugging
3. Make multiple changes at once
4. Not verify fixes before declaring success
5. Lose context in long sessions

---

## Prevention Strategies

### 1. Log-First Principle
**Rule**: Always check existing logs before assuming what's broken

**Implementation**:
- Check `C:\KAI\armada\_logs\sovran_today.log` first
- Look for ERROR, CRITICAL, or recent activity
- Don't debug without log context

### 2. Test Before Fix
**Rule**: Verify behavior with test scripts before modifying production code

**Implementation**:
- Use `vortex/test_*.py` scripts to verify API behavior
- Run `python preflight.py` to validate code before sessions
- Never modify main code without understanding current behavior

### 3. One Change at a Time
**Rule**: Modify → Test → Verify before next change

**Implementation**:
- Make single logical change
- Verify it works
- Then move to next change
- Avoid "while I'm here" syndrome

### 4. Preflight Gate
**Rule**: Require validation before running sessions

**Implementation**:
- Run `python preflight.py` before any trading session
- All checks must pass
- Document any skipped checks

### 5. Session Log Management
**Rule**: Clear log at start of each run to avoid confusion

**Implementation**:
- Log cleared on Sovran startup
- Each session has distinct timestamp
- Easy to see what changed

### 6. Model Logs
**Rule**: Document model quirks for future AI sessions

**Implementation**:
- Create model-specific logs (Hunter_Alpha, Big_Pickle)
- Note response patterns, biases, common errors
- Update after each significant session

---

## Workflow for AI Sessions

### Before Making Changes
1. Check logs: `_logs/sovran_today.log`
2. Check current code state
3. Understand what should happen vs what's happening
4. Identify root cause

### During Changes
1. Make one change at a time
2. Verify change compiles
3. Test if possible
4. Document in Obsidian

### After Changes
1. Verify fix works
2. Run preflight
3. Update bug summary in Obsidian
4. Note in model log if new quirks discovered

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Solution |
|--------------|--------------|----------|
| "While I'm here" | Multiple changes = harder to debug | One change at a time |
| "Seems broken" | Assumptions without evidence | Check logs first |
| "Let me try X" | Shotgun debugging | Understand root cause |
| "It should work" | Not verified | Actually test it |
| "I'll remember" | Context lost in sessions | Write to Obsidian |

---

## Tool Recommendations

### For This System
- **Logs**: `C:\KAI\armada\_logs\sovran_today.log`
- **Test scripts**: `C:\KAI\vortex\test_*.py`
- **Preflight**: `C:\KAI\armada\preflight.py`
- **Obsidian**: `C:\KAI\obsidian_vault\Sovran AI\Bug Reports\`

### For Any AI System
1. Persistent log file
2. Test harness before production
3. Clear start/stop mechanism
4. Documentation in human-readable format

---

## Key Lessons from Sovran Development

1. **Complexity ≠ Capability**: Simple working systems beat complex theoretical ones
2. **Honest Failure**: When user reports problems, don't defend - fix
3. **Progressive Disclosure**: Load what you need, when you need it
4. **Community Beats Solo**: Open systems get better faster
5. **Never Defend Non-Working Systems**: Fix or replace

---

*This framework applies to any AI-assisted development project*
