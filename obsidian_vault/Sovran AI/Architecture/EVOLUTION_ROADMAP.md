# Evolution Roadmap: Sovran AI - Intelligent Trader

## How This System Matches Your Vision

### Your Vision
> "The AI IS the trader. Not an algorithm with an LLM bolted on. The AI observes, thinks, decides, and executes — intelligently, using the process we outlined."

### What's Now Implemented

| Your Vision | How It's Implemented |
|---|---|
| AI observes the market | Temporal Context Buffer: 10-min rolling narrative of OFI/VPIN/price trends |
| AI forms a thesis | Structured prompt requires `observation` → `thesis` → `invalidation` |
| AI waits for confirmation | WATCH action: re-evaluate in 30s without forcing a trade |
| AI remembers what it was thinking | `current_thesis.json` persists across cycles and across sessions |
| AI learns from its trades | Memory file + similar setup search + Kaizen intelligence |
| AI runs from Gemini CLI | Obsidian bridge: all context flows through the vault |
| AI improves over time | 5-layer learning flywheel (thesis → trade → reflection → pattern → enrichment) |

### The Key Shift
**Before**: Timer(90s) → snapshot → JSON → vote → execute. The AI was a *random number generator with market context*.
**After**: Observe → hypothesize → wait → confirm → act → reflect. The AI is a *trader with patience and memory*.

---

## How to Test It Fully

### Level 1: Structural Verification (No Risk)
```bash
# Launch engine in learning mode with 1 contract
C:\KAI\SAE5.8_DEV\.venv\Scripts\python.exe C:\KAI\armada\sovran_ai.py --symbols MNQ --force-direct --loop-interval-sec 30
```

**Check for these markers in the logs**:
1. `TEMPORAL CONTEXT (X.X minutes, Y snapshots)` — Buffer populating ✅
2. `YOUR PREVIOUS THESIS (X.X minutes ago)` — Memory working ✅
3. `WATCH MODE [MNQ]: Re-evaluating in Xs` — Patience working ✅
4. `SOVEREIGN [MNQ]: Action=BUY | Thesis:` — Thesis-driven decisions ✅

### Level 2: Thesis Quality Audit (Manual)
After 30+ minutes of running, read `_data_db/current_thesis.json`:
- Does the `observation` describe what's *actually* happening? Or is it generic?
- Does the `thesis` make a specific, falsifiable prediction?
- Does the `invalidation` identify a real risk?
- Are WATCH decisions evolving over successive cycles (building conviction)?

### Level 3: Live Stress Test (1 Contract)
Run in LEARNING_MODE with 1 contract for a full session (8:30 AM - 3:00 PM CT).
Track:
- Number of WATCH cycles before a BUY/SELL (should be 3-10, not 0)
- Whether invalidation conditions are actually checked after entry
- Whether the AI's reasoning quality degrades over time (context bloat)
- Trade outcomes vs. thesis quality

### Level 4: Comparative Backtest
Run simultaneously with the old prompt (via a flag) and the new Intelligent Trader prompt on the same market data. Compare:
- WAIT rate (old should be higher — it was too conservative)
- Trade quality (new should have higher avg win)
- False signal rate (new should trade less often but more profitably)

---

## How to Evolve It Forward

### Immediate (This Week)
1. **ATR-Based Dynamic Stops**: Replace static `stop_points` with ATR-driven levels from the temporal buffer
2. **Thesis Invalidation Engine**: Automated monitoring — if AI said "invalidation: OFI flips negative" and it does, auto-close
3. **Post-Trade Enrichment**: After each trade, the AI writes a genuine "what I learned" entry to the memory file

### Medium Term (Next 2 Weeks)
4. **Multi-Timeframe Context**: Add a 1-hour and 4-hour buffer alongside the 10-minute buffer
5. **Regime Detection**: Use the temporal buffer to classify "trending" vs "chopping" vs "event-driven"
6. **Gemini CLI Auto-Handoff**: When the bridge detects a new Gemini CLI session, it auto-generates a thesis summary

### Long Term (Month+)
7. **RL Fine-Tuning**: Use trade outcomes to fine-tune the LLM's thesis quality via FinRL
8. **Multi-Symbol Intelligence**: Share pattern learning across MNQ/MES/MYM
9. **Swarm Consensus**: Multiple LLM instances form theses independently, then debate

---

## GitHub Repos to Enhance This System

### 🏆 Tier 1: Direct Integration Candidates

| Repo | What It Does | How It Helps Sovran |
|---|---|---|
| **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** | Multi-agent LLM trading firm (analyst, researcher, trader, risk manager roles) | Model the "Sovereign Council" as a structured firm simulation instead of simple vote averaging |
| **[Open-Finance-Lab/AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading)** | Agentic alpha mining with adaptive research loops and LLM-driven factor generation | Enhance the thesis generation with dynamic factor discovery (OFI-variants, cross-asset signals) |
| **[hikingthunder/thumber-trader](https://github.com/hikingthunder/thumber-trader)** | VPIN order flow toxicity detection + ATR-adaptive grids + Kelly sizing | Directly upgrade your VPIN calculation and add ATR-based stop management |
| **[AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL)** | Financial RL framework with live brokerage integration | Add RL-based position sizing and reward optimization on top of the LLM thesis layer |

### 🔧 Tier 2: Component Libraries

| Repo | What It Does | How It Helps |
|---|---|---|
| **[web3spreads/quant-flow](https://github.com/web3spreads/quant-flow)** | Multi-LLM decision engine with Grid Flow Strategy | Reference architecture for multi-model consensus (better than current vote-counting) |
| **[EthanAlgoX/LLM-TradeBot](https://github.com/EthanAlgoX/LLM-TradeBot)** | Market regime detection + dynamic score calibration | Steal the regime detection logic to improve session-phase intelligence |
| **[SGTYang/VPIN](https://github.com/SGTYang/VPIN)** | Clean VPIN implementation | Validate/upgrade your VPIN bucket calculations |
| **[LLMQuant](https://github.com/LLMQuant)** | Community hub for LLM+quant | Data connectors and strategy simulation tools |

### 📚 Tier 3: Research & Architecture References

| Repo | What It Does | How It Helps |
|---|---|---|
| **[FinRL-Contest-2025](https://github.com/AI4Finance-Foundation/FinRL_Contest_2025)** | FinRL + DeepSeek for stock trading | Shows how to combine RL with LLM reasoning for trading |
| **[theopenstreet/VPIN_HFT](https://github.com/theopenstreet/VPIN_HFT)** | VPIN for high-frequency trading | Academic VPIN implementation with Bulk Volume Classification |

---

## The Gemini CLI Bridge (How It Works)

The bridge mechanism is already documented in [[Architecture/GEMINI_CLI_BRIDGE]], but here's the mental model:

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────┐
│  Gemini CLI  │────▶│  Obsidian Vault       │◀────│  Antigravity │
│  (Session A) │     │  ┌─────────────────┐  │     │  (Session B) │
│              │     │  │ current_thesis   │  │     │              │
│  Reads:      │     │  │ STATE_ANCHOR     │  │     │  Writes:     │
│  - thesis    │     │  │ Traders_Diary    │  │     │  - thesis    │
│  - state     │     │  │ manual_commands  │  │     │  - state     │
│  - diary     │     │  └─────────────────┘  │     │  - diary     │
│              │     │                        │     │              │
│  Writes:     │     │  Bridge Files:         │     │  Reads:      │
│  - commands  │     │  - manual_commands.json│     │  - commands  │
│  - research  │     │  - current_thesis.json │     │  - research  │
└─────────────┘     └──────────────────────┘     └─────────────┘
```

**Any LLM** (Gemini CLI, Antigravity, Claude) can pick up where the last one left off by reading:
1. `DAILY_HANDOFF_GATEWAY.md` → Current system state
2. `current_thesis.json` → What the AI was thinking
3. `STATE_ANCHOR_LATEST.md` → Account positions & balance

---

*Document updated: 2026-03-24 20:33 CT. Sovereign Agentic Hub.*
