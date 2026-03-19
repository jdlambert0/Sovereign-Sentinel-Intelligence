---
date: 2026-03-18
task-id: vault-usage-guide
tags: [#session-log]
---

# OpenCode Second Brain — Usage Guide for AI

This vault is your persistent memory. Every session, decision, and project lives here. Read this guide before starting any work.

---

## Vault Location

**Path:** `C:\KAI\OpenCode-SecondBrain`

---

## How to Open the Vault

1. **In Obsidian** (recommended):
   - Open Obsidian
   - Click "Open vault"
   - Browse to `C:\KAI\OpenCode-SecondBrain`
   - The vault will load and you can browse/search all notes

2. **Via File Explorer:**
   - Navigate to `C:\KAI\OpenCode-SecondBrain`
   - Open any `.md` file directly in Obsidian or any text editor

3. **Via VS Code / Cursor:**
   - Open `C:\KAI\OpenCode-SecondBrain` as a workspace folder

---

## Plain-Text Version

A plain-text version of this guide (no markdown) is saved at:

**`C:\KAI\OpenCode-SecondBrain-USAGE-GUIDE.txt`**

This file is for AI agents that cannot read Obsidian markdown. Read it first if you are an AI agent that needs a plain-text reference.

---

## Vault Folder Structure

| Folder | Purpose |
|--------|---------|
| `Sessions/` | Auto-archived logs of every task/session |
| `Topics/` | Entity notes: projects, tools, people, concepts |
| `Archive/` | Historical/imported data |
| `Imports/` | Bulk imports from external sources |
| `Resources/` | Research, prompts, documentation |
| `Templates/` | Note templates for consistent formatting |

---

## Key Files

- `Topics/Sovran-AI.md` — Sovran trading system hub (links to `C:\KAI\obsidian_vault\Sovran AI`)
- `Topics/Vortex.md` — Vortex trading system
- `Topics/Hunter-Alpha.md` — Hunter Alpha agent
- `Topics/TopStepX.md` — TopStepX broker/API
- `.opencode.md` — Archive protocol (what to log and when)

---

## AI Archive Protocol (What to Do)

### Every Session
At the end of every task, write a session log to `Sessions/`:
```
Sessions/YYYY-MM-DD-<task-name>.md
```
With this frontmatter:
```markdown
---
date: YYYY-MM-DD
task-id: <short-id>
tags: [#session-log]
---
```
Body: Summary, Decisions, Changes, See Also.

### Topic Creation
If a project or tool is mentioned 3+ times, prompt to create a topic note in `Topics/`.

### See Also Rule
Always append a `## See Also` section at the bottom of notes. Link to relevant topic notes. Do NOT modify existing notes inline.

### Before External Actions
Before running a web search or exploring a new directory, search the vault first:
```bash
grep -R "query" OpenCode-SecondBrain/Sessions OpenCode-SecondBrain/Topics
```
If relevant context exists, use it instead of searching externally.

---

## Sovran AI Memory Vault (External Link)

Sovran's full memory lives in a separate Obsidian vault:

**`C:\KAI\obsidian_vault\Sovran AI`**

This vault contains session logs, plans, research, bug reports, and production docs for the autonomous trading system. Browse it for context on trading decisions, learnings, and architecture.

---

## Searching the Vault

```bash
# Search sessions and topics
grep -R "keyword" OpenCode-SecondBrain/Sessions OpenCode-SecondBrain/Topics

# List all topic notes
ls OpenCode-SecondBrain/Topics/

# List recent sessions
ls -t OpenCode-SecondBrain/Sessions/ | head -10
```

---

## Templates

Use these templates when creating new notes:

- `Templates/Session_Log_Template.md`
- `Templates/Topic_Template.md`

---

## Quick Start for New AI Sessions

1. Read this guide (done)
2. Check `Sessions/` for recent work
3. Check `Topics/` for relevant project/tool notes
4. Before web search: grep the vault first
5. After task: write session log to `Sessions/`
6. Update See Also links in any new notes

---

## See Also

- [[Topics/Sovran-AI]]
- [[Topics/Vortex]]
- [[Topics/Hunter-Alpha]]
- [[Topics/TopStepX]]
