# Skills Architecture: On-Demand Loading for Gemini CLI

## The Problem (From Video Insight)

> "The longer your instructions get, the quality of AI output peaks then DEGRADES. The AI fills its head with instructions, leaving no room to actually THINK."

This is **exactly** what happened with Sovran Hunt:
- The `build_prompt()` function was 60+ lines of static instructions
- Every cycle loaded ALL rules, ALL thresholds, ALL context — whether relevant or not
- The LLM's "thinking space" was consumed by instructions it didn't need for that specific decision

## The Fix: Skills = On-Demand Specialist Loading

**Instructions** = The Manager (always loaded, high-level purpose and rules)
**Skills** = The Specialists (loaded only when needed)

### Current System (Instructions-Heavy)
```
Every 90s: Load ALL of this →
  - Sovereign identity (who you are)
  - Temporal context (10-min buffer) ← NEW, GOOD
  - Current snapshot (price, OFI, VPIN)
  - Previous thesis ← NEW, GOOD
  - Performance history
  - Recent trades
  - Similar setups
  - Account state
  - Thinking process scaffold
  - Action definitions
  - Response format spec
```

### Redesigned System (Skills-Based)
```
ALWAYS LOADED (Manager Instructions):
  - Identity: "You are Sovran AI, an intelligent futures trader"
  - Current snapshot: price, OFI, VPIN, spread
  - Previous thesis (1 paragraph)
  - Available skills: [OBSERVE, ENTRY, MANAGE, EXIT, REFLECT]

ON-DEMAND SKILLS (Loaded when triggered):
  OBSERVE_SKILL: Temporal buffer + trend analysis prompting
  ENTRY_SKILL: Thesis validation, R:R calculation, entry reasoning
  MANAGE_SKILL: Open position management, stop adjustment, thesis monitoring
  EXIT_SKILL: Exit reasoning, PnL finalization, invalidation checks
  REFLECT_SKILL: Post-trade analysis, pattern extraction, diary entry
```

## How This Maps to Gemini CLI

### Gemini CLI Skill Structure
```
C:\KAI\armada\.gemini\skills\
├── observe\
│   └── SKILL.md          "When to use: AI is scanning for setups"
├── entry\
│   └── SKILL.md          "When to use: AI has a confirmed thesis and wants to trade"
├── manage\
│   └── SKILL.md          "When to use: AI has an open position"
├── exit\
│   └── SKILL.md          "When to use: AI wants to close a position"
└── reflect\
    └── SKILL.md          "When to use: After a trade closes"
```

Each SKILL.md has:
1. **Description** (1-2 sentences — this is what the AI always sees)
2. **Detailed Instructions** (only loaded when the skill is activated)
3. **Examples** (what good looks like)

### Implementation in `sovran_ai.py`

Instead of one monolithic prompt, `build_prompt()` becomes:

```python
async def build_prompt(self, memory, phase="observe"):
    base = f"""You are Sovran AI. Price: {self.last_price}. 
    OFI: {self.get_ofi():.1f}. Previous thesis: {self._format_thesis_brief()}.
    Available phases: OBSERVE, ENTRY, MANAGE, EXIT."""
    
    if phase == "observe":
        base += self._load_skill("observe")  # Temporal buffer + trend analysis
    elif phase == "entry":
        base += self._load_skill("entry")    # R:R + thesis validation
    elif phase == "manage":
        base += self._load_skill("manage")   # Stop management + monitoring
    # etc.
    
    return base
```

## Benefits
1. **The AI has more room to think** — base prompt is ~200 tokens instead of ~800
2. **Each skill is deeply specialized** — the OBSERVE skill doesn't need to know about exit rules
3. **Skills can evolve independently** — update the ENTRY skill without touching OBSERVE
4. **Gemini CLI can invoke skills directly** — `$observe` or `$enter` in the chat

## The Sweet Spot
- **5-10 skills max** (per the video advice)
- **Descriptions must be DISTINCT** (avoid confusion between OBSERVE vs MANAGE)
- **Audit regularly** — if the AI calls the wrong skill, the descriptions overlap

---

## Adaptation From Claude to Gemini CLI

| Claude Concept | Gemini CLI Equivalent |
|---|---|
| Project System Instructions | `.gemini/GEMINI.md` (global) or project `GEMINI.md` |
| Skills folder | `.gemini/skills/` directory |
| Skill.md file | `SKILL.md` with YAML frontmatter (name, description) |
| Skill Creator | Manual creation or AI reverse-interview |
| Always-on instructions | `GEMINI.md` system prompt |
| On-demand skills | Skills loaded via description matching |

---

*This architecture is ready for implementation. The current prompt redesign is Phase 1 (monolithic but thesis-driven). Phase 2 is breaking it into the 5 skills above.*
