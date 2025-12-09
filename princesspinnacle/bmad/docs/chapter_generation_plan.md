# Integrated Plan: Phased, Context-Aware Chapter Workflow with Iterative Human Oversight

This document outlines the strategic plan for efficiently generating and editing all "Princess Pinnacle" chapters using "Write Agent" and "Edit Agent" workflows. The plan is designed to rigorously avoid API rate limits, maintain the highest narrative quality, and integrate crucial human oversight.

## Overall Strategy: Act-by-Act Iteration with Comprehensive Human Validation

The generation and editing process will proceed Act-by-Act. Each Act will undergo a complete Write Agent and Edit Agent pass, followed by a mandatory human review and validation, before moving to the next Act. This iterative approach ensures quality, allows for continuous learning, and prevents the propagation of errors.

## Phase 1: Act Generation Loop (Iterative Write & Edit per Act)

**Objective:** Produce a high-quality, fully edited draft for an entire Act (e.g., Act 1). This phase is repeated for Act 1, then Act 2, then Act 3.

### 1. Pre-Flight Checklist (Human Task)

*   **Action:** A human reviewer will perform a rapid qualitative review of the relevant `chapters-actX.md` (fully refined) and `character_evolution_tracker.md` for the current Act.
*   **Goal:** Catch any high-level thematic or character inconsistencies *before* automated generation begins. This serves as a final human gate on the source material.
*   **Output:** Human approval to proceed with automated generation for the Act.

### 2. Write Agent (Chapter-by-Chapter, Sequential within Act)

This process automates the initial prose generation for each chapter within the current Act.

*   **Execution Order:** Chapters will be processed sequentially (Chapter 1, then Chapter 2, etc.) within the current Act.
*   **BMAD Sync Check (Chapter-level):**
    *   **Action:** Before generating Chapter N, the `Write Agent` will automatically validate its specific chapter outline (from `chapters-actX.md`) against core `GEMINI.md` directives (e.g., correct character names, MaidKnight aesthetic, Evolution Rhythm structure).
    *   **Behavior on Discrepancy:** If critical discrepancies are found, the agent will **halt generation for that specific chapter**, log the error, and notify the human reviewer for intervention. It *may* proceed with other chapters if not interdependent.
*   **Dynamic Context Priming:** For each Chapter N, the `Write Agent` will be comprehensively primed with:
    *   **Chapter N's Outline:** The full, detailed outline from `chapters-actX.md`.
    *   **Act-Level Thematic Context:** The **full summary of the *entire current Act*** (`chapters-actX.md`) for high-level thematic priming.
    *   **Narrative Continuity Context:** The **full prose text of the *immediately preceding chapter* (N-1)** for direct stylistic and narrative continuity.
    *   **Broader Contextual Awareness:** **Detailed summaries (or full text, if token limits allow) of Chapters N-2 to N-5** for broader contextual awareness, character development, and theme progression.
    *   **Core BMAD References:** Relevant sections of `character_evolution_tracker.md`, `world-codex.md`, `genre-wisdom.md`.
*   **Dynamic Rate Limit Governor:**
    *   **Mechanism:** A configurable, self-adjusting delay will be implemented between chapter generations. This governor will actively monitor API usage (tokens/minute, requests/minute) and dynamically adjust `sleep()` times (e.g., using exponential backoff) to prevent hitting API rate limits.
    *   **Goal:** Ensure uninterrupted generation flow while respecting external API constraints.
*   **Checkpointing & Error Handling:**
    *   **Output:** Generated prose will be saved as `C:\KAI\princesspinnacle\bmad\chapters\actX/chapter_YYY_Title_DRAFT.md`.
    *   **Manifest:** An `actX_write_status.json` manifest will be updated after each successful chapter generation, tracking its status (pending, in_progress, completed, failed). This manifest allows the process to resume precisely from the last successful point after any interruption or failure.
    *   **Logging:** All generation failures, warnings, or unexpected behaviors will be logged to a chapter-specific `_write_log.md` file.

### 3. Edit Agent (Chapter-by-Chapter, Sequential within Act, Multi-Pass)

Once all chapters in an Act are in `_DRAFT.md` form, this process refines the prose.

*   **Execution Order:** Chapters will be processed sequentially within the current Act.
*   **Dynamic Context Priming:** For each Chapter N, the `Edit Agent` will be primed with:
    *   Full `_DRAFT.md` text of Chapter N.
    *   Full summary of the *entire Act*.
    *   **Cross-Chapter Coherence:** The **full prose text of the *immediately preceding (N-1) and succeeding (N+1) chapters*** (if available from `bmad/chapters/actX/`) for seamless transitions and cross-chapter consistency validation.
    *   Relevant sections of `character_evolution_tracker.md` (for Voice Pass), `GEMINI.md` (for Anti-Patterns), and `genre-wisdom.md` (for Aesthetic).
*   **Dynamic Rate Limit Governor:** A *separate*, dynamically tuned governor will be implemented for `Edit Agent` API calls, recognizing that editing tasks might have different token usage patterns.
*   **Iterative Quality Passes (Specialized & Sequential):** The `Edit Agent` will execute multiple, distinct passes to address different aspects of quality:
    1.  **Anti-Pattern Compliance Pass:** Aggressive removal of "was/were," generic adjectives, abstract concepts as actions, weak dialogue tags, etc. (multiple passes if necessary).
    2.  **Voice & Tags Pass:** Strict validation against `character_evolution_tracker.md` for all dialogue and internal monologue, ensuring consistent and authentic character voice.
    3.  **Pacing & Flow Pass:** Adjust sentence length variation, paragraph structure, and narrative rhythm to enhance overall pacing and impact.
    4.  **Aesthetic & Imagery Pass:** Refine "Gilded Entropy" descriptions and "Glitch Visuals," ensuring rich sensory detail and thematic consistency.
    5.  **Thematic Resonance Pass:** Verify that the chapter subtly reinforces Act-level themes, motifs, and character arcs.
*   **Output & Logging:**
    *   **Output:** Save refined prose as `C:\KAI\princesspinnacle\bmad\chapters\actX/chapter_YYY_Title.md` (overwriting the `_DRAFT.md` version).
    *   **Logging:** Log all detected issues, corrections made, and any remaining flagged items to a `_edit_log.md` file specific to the chapter. Chapters failing critical quality thresholds are explicitly flagged for **mandatory human review**.
    *   **Automated Rollback/Versioning:** Implement an automatic system to create a dated backup or version of a chapter *before* an `Edit Agent` pass, allowing for rollback if an edit introduces regressions.

### 4. Human Review & Iteration (Act-Level Validation - CRITICAL)

This is the most crucial step, providing qualitative assessment and guidance.

*   **Action:** After *all* chapters in an Act are processed by the `Edit Agent`, a human reviewer meticulously reviews the generated prose for the entire Act, along with its associated `_write_log.md` and `_edit_log.md` files.
*   **Qualitative Assessment:** The review will focus on holistic narrative flow, character emotional arcs, thematic consistency, adherence to the "Gilded Entropy" aesthetic and "Clinical Nightmare Rhythm," and overall "Princess Pinnacle" feel. This is where the subjective, creative feedback is integrated.
*   **Feedback Loop & BMAD Refinement:** Identified issues (e.g., character voice drift across several chapters, thematic misinterpretations in a sequence of events, inconsistencies in "Soul Strain" depiction) directly lead to:
    *   **Refinements in `GEMINI.md` or other BMAD documents:** Updating directives based on learned patterns.
    *   **Targeted Re-generation/Re-editing:** Specific problematic chapters or sections can be sent back through the Write/Edit Agent loop with updated instructions.
    *   **Direct Instructions to Agents:** Providing explicit guidance for future Acts, ensuring continuous learning and improvement of the AI agents' creative output.
*   **Output:** Human approval to commit the Act's chapters and proceed to the next Act.

## Phase 2: Act Progression

*   Once an Act is fully human-validated and signed off, the entire workflow (Phase 1) is repeated for the next Act (Act 2, then Act 3).

This integrated plan ensures that the mass generation and editing of chapters is both efficient and high-quality, leveraging AI capabilities while maintaining crucial human creative oversight and iterative refinement, all within API rate limit constraints.
