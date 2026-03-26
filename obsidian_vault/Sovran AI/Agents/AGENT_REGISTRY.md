# Sovran Agent Registry

> All AI agents working on the Sovereign Sentinel system are registered here.
> Each agent has its own context page that it reads at session start.

---

## Active Agents

| Agent | Role | Context Page | Platform |
|-------|------|-------------|----------|
| **CIO Agent** | Architect, PM, QA, Research | `Agents/SOVRAN_CIO_AGENT.md` | Accio Work (Claude Opus) |
| **Coding Agent** | Implementation Engineer | `Agents/CODING_AGENT.md` | Accio Work (General Sub-Agent) |

## Future Agents (Planned)

| Agent | Role | When Needed |
|-------|------|-------------|
| **Research Agent** | Market analysis, pattern discovery, thesis generation | Layer 3 (Mind) |
| **Sentinel Agent** | Process monitoring, crash recovery, health checks | Layer 5 (Sentinel) |

## Agent Communication Protocol

1. CIO Agent writes **specifications** to `Architecture/Layer_*_Spec.md`
2. Coding Agent **reads** the spec and implements in `C:\KAI\sovran_v2\`
3. Coding Agent updates its **status** in `Agents/CODING_AGENT.md`
4. CIO Agent **reviews** the implementation against acceptance criteria
5. If accepted → CIO updates `Architecture/SOVRAN_V2_PRD.md` with checkmarks
6. If rejected → CIO writes specific issues, Coding Agent fixes

## The Golden Rule

**The Obsidian vault is the shared brain.** Every agent reads it at session start and writes to it before session end. No agent operates from memory alone — if it's not in the vault, it didn't happen.

---
#agents #registry #protocol
