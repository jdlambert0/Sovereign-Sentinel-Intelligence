# Problem Tracker: Skills Architecture Optimization

## Problem 13: INSTRUCTION BLOAT → AI QUALITY DEGRADATION

### Status: ✅ RESOLVED (Phase 2 Complete)

### Description
The AI's trading quality degrades as the prompt length increases. The monolithic `build_prompt()` function was replaced with a **Phase-Aware Skills Architecture**.

### Evidence
1. **Antigravity Session (15:00-15:35 CT)**: AI stuck in `Observation → No Setup → Loop`. The prompt was ~800 tokens of instructions, leaving minimal room for genuine market analysis.
2. **Gemini CLI Session (16:00-20:30 CT)**: AI generated 30 identical empty research stubs every 40 seconds. It was "running" the instructions but not "thinking" about the market.
3. **Both AI instances failed identically** despite different LLM backends — confirming the problem is architectural, not model-specific.

### Root Cause
The system violates the **Skills Principle**: instructions should be loaded on-demand, not all-at-once.

### Video Source Analysis
Key insight from the skills tutorial:
> "There's a point where more instructions actually hurts the AI's output. Skills are loaded on demand — only showing the AI what it needs at that point in time."

### Phase 1 Mitigation (COMPLETE ✅)
The Intelligent Trader redesign reduced instruction noise by:
- Replacing static thresholds ("Goldilocks" rules) with the AI's own thesis-driven reasoning
- Adding temporal context (the AI sees TRENDS, so it doesn't need as many rules about how to interpret snapshots)
- Adding WATCH action (the AI doesn't need to force a decision, reducing wasted reasoning on non-setups)

### Phase 2 Solution (PENDING)
Break the monolithic prompt into 5 on-demand skills:

| Skill | When Loaded | Token Budget |
|---|---|---|
| OBSERVE | Scanning for setups (no position) | ~300 tokens |
| ENTRY | Confirmed thesis, ready to trade | ~250 tokens |
| MANAGE | Open position monitoring | ~200 tokens |
| EXIT | Closing a position | ~150 tokens |
| REFLECT | After trade closes | ~200 tokens |

**Base prompt (always loaded)**: ~150 tokens (identity + current price + previous thesis brief)
**Skill (on-demand)**: ~200-300 tokens depending on phase

**Total per cycle**: ~350-450 tokens (down from ~800+)
**Thinking space freed**: ~40-55% more capacity for actual reasoning

### Dependencies
- [[Architecture/SKILLS_ARCHITECTURE]] — Full specification
- [[Architecture/GEMINI_CLI_BRIDGE]] — How skills integrate with Gemini CLI

### Verification Criteria
- [ ] AI generates distinct, specific observations (not generic)
- [ ] WATCH cycles show thesis EVOLUTION (not repetition)
- [ ] Trade entries cite specific temporal evidence
- [ ] Post-trade reflections identify specific lessons (not templates)

### Citations
1. **Video**: "Skills for AI" — on-demand loading principle
2. **First Principles Analysis**: [[Architecture/FIRST_PRINCIPLES_AI_TRADER]]
3. **OpenAI CodeX / Claude Skills**: Description-based skill routing (1-2 sentence triggers)

---

## Problem 14: GITHUB INTEGRATION PRIORITIES

### Status: 🟡 EVALUATED

### Description
Which open-source repos should be integrated to enhance performance, reliability, and profitability?

### Evaluation

| Repo | Effort | Impact | Priority |
|---|---|---|---|
| `hikingthunder/thumber-trader` | Low (VPIN code is portable) | High (validates our VPIN calc) | 🔴 P1 |
| `TauricResearch/TradingAgents` | Medium (architecture reference) | High (structured firm deliberation) | 🟡 P2 |
| `AI4Finance-Foundation/FinRL` | High (RL framework) | High (adaptive sizing) | 🟢 P3 |
| `Open-Finance-Lab/AgenticTrading` | Medium (research integration) | Medium (alpha mining) | 🟢 P3 |

### Immediate Action Items
1. **P1**: Pull VPIN calculation from `thumber-trader` and compare against our implementation
2. **P2**: Study `TradingAgents` role-based architecture for Council redesign
3. **P3**: Evaluate FinRL for position sizing optimization

---

## Problem 15: GEMINI CLI CONTEXT CONTINUITY

### Status: 🟡 MITIGATED

### Description
When switching between Gemini CLI sessions, the AI loses all context (thesis, position state, market view). The Obsidian bridge resolves this but requires discipline.

### Solution
- `current_thesis.json` → AI's last thesis persists to disk
- `STATE_ANCHOR_LATEST.md` → Account state persists via CRP
- `DAILY_HANDOFF_GATEWAY.md` → Entry point for any new session
- `GEMINI_CLI_BRIDGE.md` → Step-by-step instructions

### Remaining Risk
If Gemini CLI doesn't read the handoff files, the AI starts cold. The `.gemini/GEMINI.md` file should include a directive to always read the gateway first.
