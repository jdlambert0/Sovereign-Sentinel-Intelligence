# Sovereign Agent Workflow: The "Minion-GSD" Protocol

Based on the architectural successes of Stripe's Minion system and the workflow optimization strategies from DontSleepOnAI.com (GSD - Get Sh*t Done Sprints), this document defines the mandatory process for all future Sovran system development.

The goal is zero "spray and pray" coding, zero context loss, and zero unmanageable "comprehension debt" for the user.

## Core Principles

1.  **Obsidian as The Permanent Brain:** The LLM context window is volatile. Obsidian is permanent. Every problem, discovery, and plan must be anchored in an Obsidian markdown file before execution.
2.  **Context Isolation (Subagent Spawning):** Never polluting the main reasoning context with deep stack traces or web searches. Bounded tasks are delegated to subagents with fresh context.
3.  **Hybrid Architecture (The Blueprint):** Combining AI creativity with deterministic, hard-coded gates (`preflight.py`).
4.  **No Trial-and-Error Loops:** If an implementation fails, the AI must STOP, record the exact error in Obsidian, and return to the Understanding Phase.

---

## The 5-Phase Workflow

### Phase 1: Discovery & Memory Anchor
**Trigger:** You (the User) report a bug, request a feature, or paste an error.
1.  **Stop & Record:** The AI does *not* write code. It immediately creates or updates a note in `C:\KAI\obsidian_vault\Sovran AI\Bugs\` or `Features\`.
2.  **Symptom Mapping:** The exact request is codified.
3.  **Result:** The problem is permanently captured. The AI knows what to solve, and you know the AI understands the problem.

### Phase 2: Context Isolation & Subdelegation
**Trigger:** The problem requires research, deep log analysis, or API documentation review.
1.  **Spawn Subagents:** The main AI spawns a *Subagent* (e.g., `browser_subagent` or a code-reading agent) with a strictly bounded, single-objective prompt.
2.  **Eliminate Context Loss:** By isolating the research, the main AI's context window remains pure and focused strictly on architecture.
3.  **Synthesize Findings:** The subagent's findings are formatted and saved as a `Research/` note in Obsidian.

### Phase 3: The Blueprint (Managing Comprehension Debt)
**Trigger:** Research is complete and a fix is theoretically possible.
1.  **Draft the Blueprint:** The AI writes a step-by-step implementation plan in Obsidian.
2.  **Deterministic Interleaving:** The plan must explicitly state which files will change and which deterministic tests (like `preflight.py` or unit tests) will validate the change.
3.  **Human Gate:** You review the Blueprint. Because the steps are explicit and separated from the code mechanics, your "comprehension debt" is zero. You lead the AI by approving or modifying the steps.

### Phase 4: Execution (GSD Sprint)
**Trigger:** You approve the Blueprint.
1.  **Execute:** The AI writes the code exactly as specified in the Blueprint.
2.  **Anti-Tilt Mechanism:** If the code throws a new, unexpected error during execution, the AI is **prohibited** from guessing a fix. It must halt the GSD Sprint, record the new error in Phase 1, and request your authorization to spawn a new subagent or draft a new Blueprint.

### Phase 5: Deterministic Verification
**Trigger:** Execution is complete.
1.  **The Hard Gate:** The AI automatically runs the designated testing suites (e.g., `C:\KAI\armada\preflight.py`).
2.  **Final Polish:** If the tests pass, the AI updates the original Obsidian note to `[RESOLVED]` and archives the Blueprint.

---

## Why This Works
*   **For the AI:** It behaves like a Stripe Minion—it receives a bounded ticket (Blueprint), executes in an isolated context, and relies on deterministic linters rather than vibes.
*   **For You:** You act as the Engineering Manager. You review the Blueprints and the Obsidian logs. You never have to read the raw Python to know if the system is stable; the deterministic gates and the high-level Obsidian narratives guarantee it.
