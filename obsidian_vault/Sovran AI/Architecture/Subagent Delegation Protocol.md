# Subagent Delegation Protocol

## Overview
When the main AI conversation encounters a **specific, bounded problem** (debugging, research, testing), it delegates to a **subagent** with fresh context. This preserves the main conversation's orchestration context while the subagent handles the detail work.

**Both** the main agent and subagent write findings to Obsidian, making the vault the shared communication layer.

## Architecture

```
┌─────────────────────────────────────┐
│       MAIN CONVERSATION             │
│  (Orchestration & Decision Making)  │
│  ▪ Reads Obsidian at session start  │
│  ▪ Delegates specific problems      │
│  ▪ Synthesizes subagent results     │
│  ▪ Writes session logs to Obsidian  │
└──────────┬──────────────────────────┘
           │ Delegates via browser_subagent tool
           ▼
┌──────────────────────────────────────┐
│       SUBAGENT (Fresh Context)       │
│  ▪ Gets specific task description    │
│  ▪ MANDATORY: Uses Lightpanda browser  │
│  ▪ Writes findings to Obsidian       │
│  ▪ Returns summary to main agent     │
└──────────┬───────────────────────────┘
           │ Reads/Writes
           ▼
┌──────────────────────────────────────┐
│    OBSIDIAN VAULT (Shared Memory)    │
│  C:\KAI\obsidian_vault\Sovran AI\   │
│  ▪ Session Logs/                     │
│  ▪ Architecture/                     │
│  ▪ Bugs/                            │
│  ▪ Action Plans/                     │
│  ▪ Research/  (NEW — subagent output)│
└──────────────────────────────────────┘
```

## When to Spawn a Subagent

| Situation | Spawn? | Rationale |
|-----------|--------|-----------|
| Online research (API docs, SDK behavior) | ✅ Yes | Browser access, fresh context |
| Debugging a specific function | ✅ Yes | Isolated analysis, won't pollute main |
| Reading long documentation pages | ✅ Yes | Don't waste main context on raw docs |
| Simple file edit | ❌ No | Main agent handles directly |
| High-level planning | ❌ No | Main agent's core job |
| Running a test/command | ❌ No | Main agent handles directly |

## How to Spawn (Using `browser_subagent` Tool)

### Task Description Template
The subagent gets ONLY the task description as its prompt. It must be self-contained:

```
TASK: [specific problem statement]

CONTEXT:
- Project: Sovran AI trading bot (C:\KAI\armada\sovran_ai.py)
- SDK: project_x_py (TopStepX futures trading)
- Vault: C:\KAI\obsidian_vault\Sovran AI\

RESEARCH:
1. [specific URL or search query]
2. [what to look for]
3. [what to extract]

OUTPUT:
Write findings to Obsidian vault at:
C:\KAI\obsidian_vault\Sovran AI\Research\[topic].md

Return a 3-line summary of what was found.
```

### Naming Convention
- `RecordingName`: Lowercase with underscores, max 3 words (e.g., `projectx_api_research`)
- `TaskName`: Human-readable title (e.g., `Researching ProjectX API Docs`)

## Subagent Output Protocol

### What the subagent writes to Obsidian
Each subagent creates a note in `Research/` with:
1. **Query:** What was researched
2. **Sources:** URLs visited
3. **Findings:** Key information extracted
4. **Implications:** How this affects our system
5. **Tags:** For retrieval

### What the main agent does after
1. Read the Obsidian note the subagent created
2. Synthesize findings into the current plan
3. Apply changes to code if needed
4. Update session log with subagent delegation record

## Current Limitations

> [!WARNING]
> The `browser_subagent` tool can only interact with web pages (clicking, typing, navigating).
>
> ### MANDATORY BROWSER: LIGHTPANDA
> As per the user mandate of March 2026, all subagents MUST use the **Lightpanda** browser for web research. 
> Lightpanda is 10x faster and has a minimal memory footprint, making it the canonical choice for machine-native web interaction.
> 
> When spawning a subagent, explicitly instruct it to use Lightpanda if possible.
>
> It CANNOT:
> - Edit local files directly
> - Run terminal commands
> - Access the Obsidian vault filesystem
>
> Therefore the subagent's job is RESEARCH ONLY.
> The main agent must manually create the Obsidian note from the subagent's returned findings.

## Integration with Bug Report Protocol (GEMINI.md §7)

When a bug is discovered:
1. Main agent writes bug report in `Bugs/` (per existing protocol)
2. If the bug requires **online research** (SDK docs, API behavior, known issues):
   - Spawn a subagent to research the specific question
   - Subagent returns findings
   - Main agent updates the bug report's "Evidence" section with research
3. Main agent then proceeds to Understanding → Fix phases

## Tags
#protocol #subagent #architecture #obsidian
