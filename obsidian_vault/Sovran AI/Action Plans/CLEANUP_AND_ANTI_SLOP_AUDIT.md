# Plan: Cleanup & Anti-Slop Audit (Sovereign Alpha)

**Objective:** Prune technical debt, optimize performance, and ensure 100% "AI Slop" removal before the Monday market open.

---

## Track 1: Performance & Cost Optimization
- **WebSocket Latency:** Research `signalrcore` MessagePack efficiency vs current JSON overhead.
- **Prompt Token Pruning:** Analyze `llm_client.py` and `sovran_ai.py` prompts. Remove redundant context to lower costs per trade.
- **Async Execution:** Audit the `asyncio.gather` loops in `sovran_ai.py` to ensure no blocking calls are slowing down the 90s interval.

## Track 2: Anti-Slop Hunt
- **Redundancy Audit:** Identify and remove duplicate state checks (e.g., checking `mandate_active` in multiple nested layers).
- **Comment Cleanup:** Replace generic AI-generated comments with concise, technical documentation.
- **Logical Purity:** Ensure all "WAIT" reasons are distinct and non-overlapping.

## Track 3: Online Interaction Research
- **API Delta Check:** Perform a quick search for any recent TopStepX API changes or known "Sunday Night" maintenance patches.
- **SDK Stability:** Check for `project_x_py` updates or community-reported bugs regarding WebSocket drops.

---

## Schedule
1. **Research Phase** (Browser Subagent)
2. **Audit Phase** (Static Analysis)
3. **Execution Phase** (Pruning & Optimization)
4. **Final Sign-Off**

10/10 Sovereign.
