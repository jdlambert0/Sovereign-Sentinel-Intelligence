# Sovereign Blueprint 5: MARL Gymnasium & Veto Audits
**Goal:** Transition from $500 daily risk to $1k daily profit using enhanced AI tuition and a "Double-Check" safety layer.

## 1. MARL Gymnasium (Multi-Agent RL Training)
*   **The Problem:** The current system only learns during live market hours. This is too slow for 100% alpha extraction.
*   **The Solution:** Create `marl_gymnasium.py`. 
    *   **Input:** Historical tick data or 1-minute bars from `C:\KAI\armada\_data_db\`.
    *   **Loop:** Feed state to `AIGamblerEngine` in "Study Mode".
    *   **Output:** Append findings to `fleet_agents_digest.json` WITHOUT placing real trades.
    *   **Kaizen Integration:** Research Loop now runs on historical data during market close.

## 2. Veto Audit Layer (Double-Check)
*   **The Problem:** LLM "hallucinations" of edges can lead to oversized losses on bad setups.
*   **The Solution:** `VetoAuditor` class in `sovran_ai.py`.
    *   **Primary Decision**: (e.g., Gemini 2.0 Flash)
    *   **Audit Decision**: (e.g., GPT-4o-mini or Claude 3.5 Sonnet)
    *   **Logic:** Auditor reviews the *Internal Reasoning* of the Primary.
    *   **Outcome:** If Auditor sees "Slop" or "Panic", it issues a `VETO` and the `AIGamblerEngine` reverts to `WAIT`.

## 3. High-Conviction Overrides (Alpha > 0.9)
*   **The Problem:** The hard $500 risk limit blocks the $1k profit goal.
*   **The Solution:** `HighConvictionHandler`.
    *   AI triggers a `CONVICTION` flag in its JSON response.
    *   If `VetoAuditor` confirms 100% alignment + Edge Strength > 0.9.
    *   System temporarily increases risk for THAT TRADE ONLY (e.g., 8 MNQ contracts instead of 4).

## 4. Implementation Steps
1.  **Draft `marl_gymnasium.py`** to read historical log fragments.
2.  **Add `VetoAuditor`** to `sovran_ai.py` utilizing a secondary OpenRouter model.
3.  **Update `AIGamblerEngine`** to require "Double Signature" for >$500 risk trades.
4.  **Verification**: Run "Gymnasium Sprint" and confirm memory updates.
