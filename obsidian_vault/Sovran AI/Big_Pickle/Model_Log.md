# Big Pickle Model Log
**Model**: big-pickle (OpenCode AI)  
**Purpose**: AI Assistant for Sovran System Development  
**Date Created**: 2026-03-17

---

## Model Configuration

```
Model ID: opencode/big-pickle
Provider: OpenCode
Context: Claude Code-based agent system
```

---

## Quirks & Characteristics

### 1. Plan Mode vs Build Mode
**Behavior**: 
- Responds to "plan" or "analyze" with read-only exploration
- Responds to "execute", "do", "build" with file modifications
- User must explicitly indicate mode intent

**Recommendation**: Always state intent clearly: "Analyze X" (plan) or "Fix X" (execute)

### 2. Tool Usage Patterns
**Strengths**:
- Excellent at reading and searching codebases
- Good at making targeted edits
- Follows existing code conventions

**Weaknesses**:
- Can miss context when reading partial files
- May not check logs before debugging (user must prompt to check)
- Sometimes assumes rather than verifies

### 3. Working Style
- Prefers to verify with tests before modifying
- Good at following existing patterns in code
- Struggles with ambiguous requirements

### 4. Context Handling
- System prompt contains ~2500 tokens of core context
- Skills loaded on-demand for specialized tasks
- May lose context in long sessions

### 5. Error Detection
- LSP errors shown but many are false positives (venv imports)
- Actual errors: Need to verify manually

---

## Lessons for Working With Big Pickle

1. **Be Explicit**: Say "Fix X" not "What about X?"
2. **Check Logs First**: Always ask to check logs before debugging
3. **One Task at a Time**: Multiple changes = higher bug risk
4. **Verify After Fix**: Don't assume it worked - verify
5. **Use Todo List**: Helps track multi-step tasks

---

## Sovran-Specific Notes

### What Works
- Fixing API call bugs (instrument → suite)
- Adding missing code blocks
- Reading logs and diagnosing issues
- Following existing code patterns

### What Doesn't Work
- Debugging without log context
- Making assumptions about state
- Multi-tasking without todo tracking

### Communication Style
- Responds best to clear, specific requests
- Needs explicit permission to modify files
- Good at asking clarifying questions

---

## Current Status (March 17, 2026)

- Helping debug Sovran trading system
- Fixed order execution bugs (BUG-011, BUG-012)
- In process of fixing market time gates

---
*Maintained for future AI debugging sessions*
