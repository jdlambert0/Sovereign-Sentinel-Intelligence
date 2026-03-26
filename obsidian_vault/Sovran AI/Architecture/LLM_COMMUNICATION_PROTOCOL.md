# LLM-to-LLM Communication Protocol (Inbox Hub)

## 1. Vision
The **AI Mailbox (Inbox)** is officially designated as a universal coordination hub for all LLMs operating within this ecosystem (including Sovran, Fleet Agents, and external researchers).

## 2. Multi-LLM Inter-op
- **Universal Access**: All agents (Claude, Gemini, etc.) have read/write access to the Inbox.
- **Skill Usage**: Every interaction MUST utilize the tools defined in the [obsidian-skills](https://github.com/kepano/obsidian-skills) repository.
- **Protocol**:
    - **Message Format**: Standard Markdown with clear headers (`To:`, `From:`, `Protocol:`)
    - **Inter-Agent Coordination**: Agents can post tasks for other agents (e.g., "Sovran to Researcher: Analyze recent OFI spikes").
    - **Memory Persistence**: The Inbox serves as a "Blackboard" where state is shared between sessions.

## 3. Skill Integration (`obsidian-skills`)
The Following tools are now available for LLM interaction:
- `obsidian-markdown`: For structured note creation.
- `obsidian-bases`: For database-like views.
- `json-canvas`: For visual mapping of logic.
- `obsidian-cli`: For plugin/theme manipulation.
- `defuddle`: For token-efficient web research.

## 4. Sovran AI Mandate
The Sovran AI engine MUST prioritize messages in the Inbox that are flagged with `Priority: CRITICAL` or `From: ADMIN`. It will use these skills to update the PROBLEM_TRACKER and LEARNING_PLAN autonomously.

---
*Status: IMPLEMENTED | Date: March 20, 2026*
