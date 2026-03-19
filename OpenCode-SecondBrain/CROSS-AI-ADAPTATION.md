---
date: 2026-03-18
topic-id: cross-ai-adaptation
tags: [#topic-note]
---

# Cross-AI Second Brain Adaptation Guide

This vault was built for OpenCode but works with any AI CLI tool. This guide covers Claude Code CLI and Gemini CLI adapters, plus a general template for any AI system.

---

## Vault Location

**Path:** `C:\KAI\OpenCode-SecondBrain`

**Plain-text version:** `C:\KAI\OpenCode-SecondBrain-CROSS-AI-ADAPTATION.txt`

---

## Part 1: Claude Code CLI Adaptation

### Setup

1. **Install Claude Code CLI:**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **Open the vault in Claude Code:**
   ```bash
   cd C:\KAI\OpenCode-SecondBrain
   ```

3. **Add to `CLAUDE.md`** (Claude Code's system prompt file):

   ```markdown
   Read C:\KAI\OpenCode-SecondBrain-USAGE-GUIDE.txt before starting any task.
   
   Archive protocol:
   - After every session: write to C:\KAI\OpenCode-SecondBrain\Sessions\YYYY-MM-DD-<task-name>.md
   - Topic creation: if a project/tool is mentioned 3+ times, create a note in Topics/
   
   Before external tools, search the vault:
   grep -R "keyword" C:\KAI\OpenCode-SecondBrain\Sessions
   grep -R "keyword" C:\KAI\OpenCode-SecondBrain\Topics
   ```

### Session Log Command

Run after every task:
```bash
claude --print "Summarize what we did in this session in 3 sentences."
```

**File:** `Sessions/YYYY-MM-DD-<task-name>.md`

**Format:**
```markdown
---
date: YYYY-MM-DD
task-id: <short-id>
tags: [#session-log]
---

Summary: [session summary]

Decisions: [key decisions]

Changes: [files changed, code written]

## See Also
- [[Topics/<relevant-topic>]]
```

### Search Command
```bash
grep -R "keyword" C:\KAI\OpenCode-SecondBrain\Sessions C:\KAI\OpenCode-SecondBrain\Topics
```

---

## Part 2: Gemini CLI Adaptation

### Setup

1. **Install Gemini CLI:**
   ```bash
   gemini install
   # or via your package manager
   ```

2. **Set vault path:**
   ```bash
   export GEMINI_VAULT="C:\KAI\OpenCode-SecondBrain"
   ```

3. **Add to `GEMINI.md` or `.gemini/config`:**

   ```markdown
   Read C:\KAI\OpenCode-SecondBrain-USAGE-GUIDE.txt before starting.
   
   Archive protocol:
   - After each task: archive to Sessions/YYYY-MM-DD-<task-name>.md
   - Before external tools: grep the vault for context
   - Topic notes: create in Topics/ when relevant
   ```

### Session Log Command
```bash
gemini ask "Write a 3-sentence summary of this session."
```

**File:** `Sessions/YYYY-MM-DD-<task-name>.md`

**Format:**
```markdown
---
date: YYYY-MM-DD
task-id: <short-id>
tags: [#session-log]
---

Summary: [summary]

Decisions: [decisions]

Changes: [changes]

## See Also
- [[Topics/<relevant-topic>]]
```

### Search Command
```bash
grep -R "keyword" C:\KAI\OpenCode-SecondBrain\Sessions C:\KAI\OpenCode-SecondBrain\Topics
```

---

## Part 3: General AI CLI Adaptation (Any System)

### Minimum Setup (3 Steps)

1. **Read the guide at session start:**
   `C:\KAI\OpenCode-SecondBrain-USAGE-GUIDE.txt`

2. **Before external tools:** grep the vault for context

3. **After task:** write session log to `Sessions/YYYY-MM-DD-<task-name>.md`

### System Prompt Addition

Add to your AI's config:

```
Before starting: Read C:\KAI\OpenCode-SecondBrain-USAGE-GUIDE.txt

Archive protocol:
- Sessions go to: C:\KAI\OpenCode-SecondBrain\Sessions\
- Topics go to: C:\KAI\OpenCode-SecondBrain\Topics\
- Search before web: grep -R "query" C:\KAI\OpenCode-SecondBrain\Sessions C:\KAI\OpenCode-SecondBrain\Topics
```

### Bash Helper Functions

Add to `.bashrc` or `.zshrc`:

```bash
vault_search() {
  grep -R "$1" "C:\KAI\OpenCode-SecondBrain\Sessions" "C:\KAI\OpenCode-SecondBrain\Topics"
}

vault_log() {
  echo "---
date: $(date +%Y-%m-%d)
task-id: $1
tags: [#session-log]
---
\$2

## See Also
- [[Topics/Sovran-AI]]
" > "C:\KAI\OpenCode-SecondBrain\Sessions\$(date +%Y-%m-%d)-$1.md"
}
```

Usage:
```bash
vault_search "vortex"
vault_log "my-task" "Summary of what we did"
```

---

## Part 4: Cross-AI Sessions (Multiple AIs Working Together)

When multiple AIs (e.g., Claude Code + Gemini CLI) work on the same project:

### Rules

1. All AIs read the same vault at `C:\KAI\OpenCode-SecondBrain`
2. Each AI logs its own sessions to `Sessions/<AI>-YYYY-MM-DD-<task>.md`
   - Example: `Sessions/claude-2026-03-18-trading-fix.md`
   - Example: `Sessions/gemini-2026-03-18-research.md`
3. Topic notes are shared and cross-linked
4. See Also sections reference other AIs' work
5. Update the AI-USAGE-GUIDE.md in the vault to list all active AI agents

### Cross-Reference Template

```markdown
## See Also
- [[Sessions/claude-2026-03-18-trading-fix]]
- [[Sessions/gemini-2026-03-18-research]]
- [[Topics/Vortex]]
```

---

## Obsidian Plugin Notes

The vault includes a basic Auto Note Mover plugin scaffold at:
`C:\KAI\OpenCode-SecondBrain\.obsidian\plugins\auto-note-mover\`

This plugin moves notes based on tags:
- `#session-log` → `Sessions/`
- `#topic-note` → `Topics/`
- `#research` → `Resources/`

Enable it in Obsidian via Community Plugins (the `manifest.json` is included).

---

## Key Files

| File | Purpose |
|------|---------|
| `AI-USAGE-GUIDE.md` | General AI usage guide |
| `OpenCode-SecondBrain-CROSS-AI-ADAPTATION.txt` | Plain-text cross-AI adapter |
| `.opencode.md` | Archive protocol |
| `Templates/` | Note templates |
| `Sessions/` | All session logs |
| `Topics/` | All topic notes |

---

## See Also

- [[AI-USAGE-GUIDE]]
- [[Topics/Sovran-AI]]
- [[Topics/Vortex]]
- [[Topics/Claude-Code]]
- [[Topics/Gemini-CLI]]
