# BUG 0322: WEEKEND API LEAK (RESEARCH LOOP)
**Status**: RESOLVED
**Date**: 2026-03-22
**Severity**: CRITICAL (Financial Burn Risk)

## 1. Symptom / Discovery
The user requested verification that the AI engine would not consume API credits if launched over the weekend while waiting for the 5:00 PM Sunday open. Auditing `monitor_loop` in `C:\KAI\armada\sovran_ai.py` revealed that while trade evaluations correctly block on stale weekend data, the newly implemented `research_and_learn` loop (added March 19) executes unconditionally *before* the Data Freshness gate. 

Because `research_and_learn` utilizes LLM evaluation over the session context, leaving the engine open on Saturday would actively drain OpenRouter/Anthropic credits every 30 seconds for 48 hours without executing any productive logic.

## 2. Hypothesis
The `get_session_phase` correctly returns `"WEEKEND (Market Closed)"`, but the engine merely passed that string into the LLM context prompt instead of actively using it to halt loop operations.

## 3. Fix Deployed (The Physical Firewall)
We explicitly trapped the weekend tag immediately after `get_session_phase()` returns, inserting a hard `continue` directive to bypass the entire remainder of the evaluation loop until the clock strikes 5:00 PM CST on Sunday.

```python
# sovran_ai.py (Line ~2014)
current_phase = self.get_session_phase()
if "WEEKEND" in current_phase:
    logger.info("MARKET CLOSED (Weekend). Coasting to preserve API credits...")
    continue
```
This guarantees absolute zero LLM logic executions when markets are closed, satisfying the architectural requirements of the user. Tests pass. ZBI satisfied.
