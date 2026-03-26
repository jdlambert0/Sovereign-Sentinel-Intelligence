# Sovereign AI: Strategic Recommendations & Model Roadmap

Based on your goal of achieving a systemic $1k/day profit with the lowest possible comprehension debt, and overcoming the current OpenRouter rate limits, here is the mandated path forward.

## 1. The OpenRouter "Stealth / Experimental" Solution

The primary issue with tying your engine to a single free model (like Groq's Llama or standard OpenRouter Llama 3) is rigid rate limits. Free models get swamped during market hours.

**Recommendation: The Cascade Strategy with "Stealth" Tiers**
OpenRouter frequently hosts unannounced "pre-release" versions of frontier models (often referred to as Alpha builds like *Pony Alpha*, *Sonic*, or experimental drops from Google/Mistral) that have massive context windows and minimal rate limits during their testing phase.

Instead of hardcoding one model, you should update `C:\KAI\.env` and the `sovran_ai.py` client to use a **Priority Cascade**:

*   **Priority 1 (The Heavyweight Stealth/Exp):** `google/gemini-2.5-pro-exp-03-25:free`
    *   *Why:* Google's newest experimental drops on OpenRouter boast immense reasoning and rarely hit 429 rate limits because they want developer stress-testing.
*   **Priority 2 (The Open-Source Elite):** `meta-llama/llama-3.3-70b-instruct:free`
    *   *Why:* GPT-4 level intelligence, but high traffic.
*   **Priority 3 (The Omniroot / Auto Fallback):** `openrouter/auto:free`
    *   *Why:* This explicitly tells OpenRouter to dynamically route to whatever free model is currently available and has low latency, ensuring the trading loop *never crashes* due to a provider timeout.

## 2. Next Immediate Action: The Data Starvation Bug

Before we trust *any* LLM to trade, we must fix the core ingestion issue noted in your `Project Overview.md`.
> *"The `handle_quote` function receives `event.data` as a dict, not an object. The original code used hasattr()/getattr() which silently fails on dicts."*

**The Minion-GSD Approach:**
Our next session should immediately target this bug using the new workflow:
1. Spawn a subagent to dump exactly what TopStepX sends in `event.data`.
2. Write a Blueprint to replace `getattr()` with `.get()`.
3. Verify via `test_quote_shape.py`.

## 3. The $1k/day Learning Loop (Memory Injection)

To achieve consistent scaling to $1k/day, the LLM needs intuition. Hardcoded rules break when volatility shifts.

**Recommendation:** We need to fully activate the **Memory Bridge**. 
Currently, trades are logged to Obsidian. We must ensure the `llm_client.py` prompt assembler actually *reads* the last 5 trades from `C:\KAI\armada\sovran_memory_<SYMBOL>.json` and injects them into the `<SYSTEM_PROMPT>` right before `calculate_size_and_execute` fires.

If the LLM sees: *"My last 3 longs failed because I ignored Order Flow Imbalance at resistance,"* its next decision will naturally size down or flip bias without us needing to write a Python rule for it.

## 4. Freezing the Core Edges

**Recommendation:** Do not invent Edge 4. 
The 3 Hardened Edges (PHG, OFI, MOM) are mathematically sufficient. Your focus should shift entirely from *Algorithm Design* to *Context Quality*. The better the data we feed the LLM (clean dicts, memory of past trades, 0 latency), the better it trades.
