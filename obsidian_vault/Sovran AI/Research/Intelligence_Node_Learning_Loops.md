# RESEARCH: Asynchronous Memory & Learning Loops (Phase 49)

**Date:** 2026-03-22
**Status:** PROPOSED

## 1. The Repository Split (Armada vs Vortex)
The codebase architecture separates high-level machine learning functions from real-time execution limits.
- **Vortex**: The original ML Core. It houses `llm_client.py`, memory ingestion logics, state tracking, and vector generation.
- **Armada**: The Execution Wrapper. `sovran_ai.py` is the live execution daemon that bridges TopStepX websockets, and imports the `vortex` brain via `sys.path.append()`. 

## 2. Gambler 2.0: Specialized Learning Track
The user mandated an evolution from a single, unified learning loop into specialized cognitive tracks.
- **Current State:** `research_and_learn()` is monolithic.
- **The Evolution:** An asynchronous daemon, `gambler_learning_loop`, will be spun up. 
- **The Action:** It will isolate trade data where Gambler 2.0 executed based on mathematical heuristics. It will research the effectiveness of those scalping/momentum constraints and log all discoveries permanently to `C:\KAI\obsidian_vault\Sovran AI\Memory\Gambler_Reflex_Memory.md`. Gambler 2.0 will natively read this file before trading to continuously heighten its probability intuition.

## 3. The CRO Journal (Self-Correcting Behavioral Overlord)
The Gemini CRO cannot be static. It must learn the consequences of its own directives.
- **The Obsidian Journal:** The CRO will maintain `C:\KAI\obsidian_vault\Sovran AI\Memory\CRO_Journal.md`.
- **The Loop:** Every 15 minutes, the CRO evaluates the total 3x3 array behavior against the $450 Global Risk Vault. It issues a directive (e.g., "Halt Gambler, capital is at $150"). 
- **The Retrospection:** On the next cycle, it checks: "Did my last directive preserve capital, or did we miss a $1000 trend? Was I too conservative?" It writes this self-reflection into the Journal.
- By continuously reading its own Journal, the CRO organically learns exactly when it needs to hard-throttle the array, and when it needs to let the engines sprint loosely towards unbounded $1k profit targets.
