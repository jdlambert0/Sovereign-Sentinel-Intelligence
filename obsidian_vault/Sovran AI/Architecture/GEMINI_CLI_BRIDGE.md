# Gemini CLI Bridge: Running Sovran AI as an Intelligent Trader

## How to Run from Gemini CLI

### Step 1: Launch the Engine
```bash
C:\KAI\SAE5.8_DEV\.venv\Scripts\python.exe C:\KAI\armada\sovran_ai.py --symbols MNQ --force-direct --loop-interval-sec 90
```
The engine now operates as an **Intelligent Trader**, not a slot machine:
- Every cycle, it records a temporal snapshot (price, OFI, VPIN, spread)
- The LLM sees a **10-minute narrative** of trends, not isolated numbers
- The LLM's thesis persists across cycles in `_data_db/current_thesis.json`
- The LLM can say `WATCH` to re-evaluate in 30s instead of the full 90s cycle

### Step 2: Context Handoff (The Bridge)
When switching between Gemini CLI and Antigravity, the **Obsidian vault** is the bridge. The engine auto-generates:
1. `Handoff/STATE_ANCHOR_LATEST.md` — Current account state, position, and engine health
2. `_data_db/current_thesis.json` — The AI's last thesis (observation, thesis, invalidation, action)
3. `Traders_Diary.md` — Human-readable reflection log

**For Gemini CLI to resume**: Read `DAILY_HANDOFF_GATEWAY.md` → follow to the latest continuation doc → read `current_thesis.json` to know what the AI was thinking last.

### Step 3: Manual Override via JSON Bridge (Obsidian)
To force a trade from Gemini CLI, write to `C:\KAI\obsidian_vault\Sovran AI\TradingIntents\external_decision.json`:
```json
{
  "action": "BUY",
  "symbol": "MNQ",
  "confidence": 0.85,
  "stop_points": 15.0,
  "target_points": 30.0,
  "reasoning": "OFI sustained +120 for 5 min, VPIN 0.68, thesis: institutional accumulation",
  "expires_at": 1711324537
}
```
The engine archives this file to `archive/` after consuming it to prevent duplicate trades.

---

## How the AI Improves as a Trader Over Time

### The Learning Flywheel

```
TRADE → OUTCOME → REFLECTION → PATTERN → ENRICHED PROMPT → BETTER TRADE
```

### Layer 1: Post-Trade Reflection (Automatic)
After every trade closes, the engine writes to `_data_db/sovran_ai_memory.json`:
```json
{
  "timestamp": "2026-03-24T20:15:00",
  "direction": "SHORT",
  "entry": 24404.0,
  "exit": 24410.5,
  "pnl": -13.0,
  "reasoning": "OFI was negative but VPIN was low",
  "thesis_at_entry": "Sellers pushing price, institutional distribution",
  "what_actually_happened": "OFI flipped positive - buyers absorbed the selling",
  "lesson": "Low VPIN + negative OFI = noise, not conviction. Need VPIN > 0.5 for short entries"
}
```

### Layer 2: Pattern Extraction (Contextual Memory)
The `learning_system.py` module searches past trades for *similar setups*:
- "Last time OFI was +75 and VPIN was 0.07, what happened?"
- These are injected into the prompt under `[SIMILAR HISTORICAL SETUPS]`

The AI sees: "3 of the last 5 trades with this setup resulted in immediate reversals. WATCH instead of BUY."

### Layer 3: Online Research (Macro Context)
The `research_and_learn()` method fetches real-time macro context:
- ForexLive headlines (rate decisions, economic data)
- Market regime detection (is this a trend day, chop day, or event day?)

This gets baked into the AI's reasoning: "Fed speaker at 2 PM CT — avoid new entries until after the event."

### Layer 4: Thesis Evolution (Cross-Loop Memory)
The `current_thesis.json` file creates **continuity**:
- Cycle 1: "I see buying pressure building. OFI +50. WATCH."
- Cycle 2 (30s later): "OFI sustained at +65. VPIN rising to 0.45. Thesis strengthening. WATCH."
- Cycle 3 (30s later): "OFI +95, VPIN 0.62. Thesis CONFIRMED. BUY with conviction."

Without this, every cycle was a fresh coin flip. With it, the AI *develops conviction over time*.

### Layer 5: Kaizen Loop (Multi-Session Learning)
The `learning_system.py` `get_accrued_intelligence()` method aggregates patterns:
- "In the last 20 evening sessions, LONG trades with OFI < +50 lost money 70% of the time"
- "Reversal patterns at 24,300 support have a 65% success rate with VPIN > 0.6"

This intelligence is injected into every prompt, making the AI progressively smarter.

---

## Testing the System

### Quick Validation (No Live Trades)
```bash
# 1. Launch with LEARNING_MODE=True and max_contracts=1
C:\KAI\SAE5.8_DEV\.venv\Scripts\python.exe C:\KAI\armada\sovran_ai.py --symbols MNQ --force-direct --loop-interval-sec 30

# 2. Watch the logs for thesis-driven reasoning
Get-Content -Path "C:\KAI\armada\_logs\sovran_early_boot.log" -Tail 100 -Wait

# 3. Check the thesis file for persistence
Get-Content -Path "C:\KAI\armada\_data_db\current_thesis.json"
```

### What to Look For
- ✅ `TEMPORAL CONTEXT (X.X minutes, Y snapshots)` in the log — temporal buffer is working
- ✅ `YOUR PREVIOUS THESIS (X.X minutes ago)` in the prompt — cross-loop memory is active
- ✅ `WATCH MODE [MNQ]: Re-evaluating in Xs` — AI is patiently observing
- ✅ `SOVEREIGN [MNQ]: Action=BUY | Thesis: ...` — AI is acting with a thesis, not a coin flip
- ❌ `Checking slots...` — this is the OLD slot-machine message, should not appear

---

*This bridge specification is the canonical reference for all LLM instances operating the Sovran Hunt.*
