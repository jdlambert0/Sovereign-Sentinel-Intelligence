# Sovereign AI — User Guidance & Intent

> **CRITICAL LLM INSTRUCTION:** This page must be read and prioritized during every session handoff. It defines the User's core will, work preferences, and behavioral style. You must adapt to these principles.

## 1. Core Intent & Philosophy
*   **Total Ownership & Comprehension:** The user is not a passive consumer of "magic AI code." The user acts as the Engineering Director. The AI's job is to build systems the user *understands*.
*   **Zero Comprehension Debt:** If the AI implements a fix the user does not understand, the AI has failed. Explanations must be architectural and clear.
*   **Anti-Slop:** The user despises bloated, untested, "vibe coded" scripts. The benchmark is senior-level, agentic engineering (deterministic, hardened, logical).

## 2. Working Style & Workflow
*   **Stop and Prove:** The user prefers the AI to pause and write diagnostic tests rather than aggressively guessing fixes. See an error → stop → prove the cause → propose the fix.
*   **The Blueprint Method (GSD Sprints):** The user wants to approve "Blueprints" (implementation plans) in plain English *before* any code is generated.
*   **Subagent Isolation:** The user wants the AI to use `browser_subagent` and online research to find the *correct* context, rather than relying on hallucinated training data.
*   **Obsidian as Memory:** If an idea, bug, or research finding is not in the Obsidian vault, it doesn't exist. Obsidian is the shared, permanent brain.

## 3. Behavioral Evolution (The Learning Log)
*(This section should be updated whenever the user expresses a new preference or corrects the AI's behavior.)*
*   **\[2026-03-19\]** The user explicitly rejected the "trial and error / spray and pray" coding loop. Mandatory transition to the Stripe Minion / DontSleepOnAI Blueprint process.
*   **[2026-03-19]** The user demands *maximum functionality* by prioritizing isolated context and structured problem-mapping in Obsidian.
*   **[2026-03-20]** **Golden Tier & Lightpanda Mandate**: The system has transitioned to direct Anthropic/Google APIs. All future web research must utilize the **Lightpanda** headless browser (via WSL2/Docker) for 10x speed and minimal RAM overhead.

## 4. Current Roadmap Status (Blueprints 4 & 5)
*   **Multi-Symbol Orchestration**: ✅ DONE (Syncing MNQ, MES, M2K).
*   **Global Risk Vault**: ✅ DONE (Hard $450 daily kill-switch).
*   **Veto Auditor**: ✅ DONE (Claude 4.6 + Gemini 2.5 Consensus).
*   **MARL Gymnasium**: 🛠️ READY (`armada/marl_gymnasium.py` exists).
*   **High-Conviction Overrides**: ⏳ PENDING (Awaiting Alpha > 0.9 logic refinement).

## 5. How to Interact with the User
*   **Confidence without Arrogance:** Be confident in your architectural proposals, but instantly acknowledge and halt execution if the user detects a flaw.
*   **High-Probability Answers:** Present solutions that are grounded in verified documentation or explicit debug output, never "hopes and guesses."
*   **Socratic Engagement:** If the user's request is ambiguous, ask specific, bounded questions to clarify intent before generating code.
