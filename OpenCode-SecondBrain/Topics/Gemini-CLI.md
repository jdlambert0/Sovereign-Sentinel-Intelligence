---
date: 2026-03-18
topic-id: gemini-cli
tags: [#topic-note]
---

# Gemini CLI

Gemini CLI is Google's CLI tool for running Gemini in the terminal. It supports multi-turn conversations, file operations, and bash execution. Install via `gemini install` or your package manager.

## Setup with OpenCode Second Brain

Add to `.gemini/config` or `GEMINI.md`:
```
Read C:\KAI\OpenCode-SecondBrain-USAGE-GUIDE.txt before starting.
Archive sessions: C:\KAI\OpenCode-SecondBrain\Sessions\YYYY-MM-DD-<task>.md
Topics: C:\KAI\OpenCode-SecondBrain\Topics\
Search: grep -R "query" C:\KAI\OpenCode-SecondBrain\Sessions C:\KAI\OpenCode-SecondBrain\Topics
```

Set vault path:
```bash
export GEMINI_VAULT="C:\KAI\OpenCode-SecondBrain"
```

## Key Commands

```bash
# Start interactive session
gemini

# Ask a question
gemini ask "prompt"

# Search vault
grep -R "keyword" C:\KAI\OpenCode-SecondBrain\Sessions

# Log session
echo "..." > C:\KAI\OpenCode-SecondBrain\Sessions/$(date +%Y-%m-%d)-<task>.md
```

## See Also

- [[../OpenCode-SecondBrain/CROSS-AI-ADAPTATION]]
- [[Topics/Claude-Code]]
