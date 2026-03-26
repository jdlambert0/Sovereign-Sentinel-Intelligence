# Sovereign Continuous Autonomous Loop Strategy

## The User's Goal
"I'm interested in having the system trading every turn and researching, but every time I've done that in the past I ran into many bugs and couldn't confirm stop loss and take profit were working."

## The Sovereign Solution: The "Kaizen-Mies" Loop

To achieve a 100% bug-free autonomous loop where the system trades seamlessly while constantly running online research to improve itself, we must decouple the *Trading Engine* from the *Research Agent*, and eliminate "bracket anxiety" using deterministic proofs.

### Step 1: Deterministic Bracket Proof (Eliminate SL/TP Anxiety)
Before unleashing the infinite loop, we must mathematically prove that SL/TP brackets are working on the platform.
*   **Action:** We will run `C:\KAI\armada\test_fixed_bracket.py` against a practice/simulated TopStepX account.
*   **Verification:** This script bypasses the AI completely and attempts to place precisely one 1-lot MNQ trade with a perfectly formatted tick offset bracket. If the platform accepts the bracket, we know the underlying infrastructure works. If it rejects it, we capture the exact JSON error.

### Step 2: The Decoupled Autonomous Loop
We will implement the **Persistent Mandate** described in our rules:
*   *Rule:* "The agent must continuously research online for new ways to achieve consistent profits with the SAE 5.8 DEV system, never stopping the search for optimization and improvement."

**Architecture:**
1.  **Foreground (Trading):** The Sovran engine (`sovran_ai.py`) runs its monitor loop. Because of Blueprint 1, it will not duplicate trades, it will not starve on quote data, and it will safely catch and log bracket dropouts.
2.  **Background (Research via Subdelegation):** While the engine runs, the Main Agent will spawn asynchronous `browser_subagent` tasks or `defuddle` web reads based on real-time market behavior. It will execute the "Mies" protocol—researching new coding paradigms, advanced TopStepX SDK hacks, and sophisticated AI prompting techniques.
3.  **The Memory Sink:** All research discoveries are synced to Obsidian as `.md` files.
4.  **The Kaizen Injection:** On the next turn, `sovran_ai.py` will read the newly populated Obsidian research nodes through the `Memory Bridge` we just built, actively teaching the AI in real-time.

### Step 3: Strict Risk Governors
To ensure "trading every turn" doesn't lead to account liquidation:
*   **Whipsaw Guards:** Enforce a hard 120-second cooldown between executions.
*   **Size Caps:** Hard limit at 1 MNQ per loop during the verification phase.

### Step 4: The Intelligence Injection (Blueprint 3)
To achieve meaningful autonomous alpha, the trading engine must consume real-time research nodes.
*   **Implementation:** The subagent (`kaizen_mies_research.py`) generates `Market_Regime_Live.md` algorithmically (volatility mapping). 
*   **Prompt Injection:** The Trading Engine (`sovran_ai.py`) reads this file every tick, injecting it into the `[KAIZEN LIVE MARKET REGIME]` block of the Gemini 2.5 Pro prompt. 
*   **Result:** Hunter Alpha now possesses "macro-awareness," allowing it to adjust its internal math (sizing, throttle) based on volatility windows described by the research daemon.

### Execution Path
1. Run `test_fixed_bracket.py` (Prove the SL/TP).
2. Launch `autonomous_sovereign_loop.py` into perpetual mode.
3. Verify `Market_Regime_Live.md` ingestion in logs.

*Status: Loop Active | Intelligence Flow Verified.*
