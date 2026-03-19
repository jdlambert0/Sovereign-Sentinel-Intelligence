---
date: 2026-03-18
topic-id: claude-code
tags: [#topic-note]
---

# Claude Code

Claude Code is Anthropic's CLI tool for running Claude in the terminal. It supports persistent context, file editing, bash execution, and multi-session memory via `CLAUDE.md`.

## Setup with OpenCode Second Brain

Add to `CLAUDE.md`:
```
Read C:\KAI\OpenCode-SecondBrain-USAGE-GUIDE.txt before starting any task.
Archive: Sessions/YYYY-MM-DD-<task>.md
Topics: Topics/<name>.md
Search before web: grep -R "query" C:\KAI\OpenCode-SecondBrain\Sessions C:\KAI\OpenCode-SecondBrain\Topics
```

## Key Commands

```bash
# Start a session
claude

# Single shot
claude --print "prompt"

# Search vault
grep -R "keyword" C:\KAI\OpenCode-SecondBrain\Sessions

# Log session
echo "..." > C:\KAI\OpenCode-SecondBrain\Sessions/$(date +%Y-%m-%d)-<task>.md
```

## See Also

- [[../OpenCode-SecondBrain/CROSS-AI-ADAPTATION]]
- [[Topics/Gemini-CLI]]
