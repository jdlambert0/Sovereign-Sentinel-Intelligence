# Obsidian Knowledge Graph Strategy
**Created:** 2026-03-23 | **Source:** InfraNodus MCP Transcript (`C:\KAI\infra.txt`)

## The Problem
Our AI trading system generates massive amounts of knowledge: trade logs, session notes, bug reports, research papers, architecture docs, and learning plans. But this knowledge is **flat** — it sits in Markdown files that are never connected. We have the same "statistical center" problem that InfraNodus describes: AI tools summarize what's obvious, but never find the **gaps** between our ideas.

## What InfraNodus Does (and How We Replicate It)

InfraNodus uses three approaches to generate insights from knowledge graphs:

| Approach | What It Does | Obsidian Equivalent |
|---|---|---|
| **Content Gaps** | Finds disconnected topic clusters and bridges them | Obsidian Graph View + manual [[wikilinks]] between unlinked notes |
| **Layer Slicing** | Removes dominant concepts to reveal hidden sub-clusters | Obsidian Graph View filters + Dataview queries to exclude common tags |
| **Peripheral Expansion** | Takes edge ideas and connects to outside context | Tag-based queries for low-frequency tags + AI research prompts |

## Implementation Plan

### Phase 1: Semantic Linking (Immediate — Manual)
Every Obsidian note should contain:
- **Tags:** `#bug`, `#trade`, `#research`, `#architecture`, `#session`, `#edge`, `#insight`
- **Wikilinks:** `[[Related Note Name]]` — link bugs to sessions, sessions to trades, trades to research
- **Properties (YAML frontmatter):**
  ```yaml
  ---
  type: bug | trade | research | architecture | session
  severity: P0 | P1 | P2
  status: open | resolved | investigating
  related: [[Other Note]]
  ---
  ```

### Phase 2: Automated Gap Detection (Script)
Create `C:\KAI\armada\knowledge_graph_gaps.py`:
1. **Parse all Obsidian .md files** — extract wikilinks, tags, and topics
2. **Build adjacency graph** — nodes = notes, edges = wikilinks
3. **Find disconnected clusters** — use networkx community detection
4. **Generate gap questions** — "How does [[Bug Report X]] relate to [[Research Y]]?"
5. **Feed gaps to LLM** — use Gemini to generate insights bridging the gaps
6. **Write insights back to Obsidian** — create new notes in `Insights/` folder

### Phase 3: Obsidian MCP Server (Future)
Build a custom MCP server that:
- Exposes `generate_research_ideas` tool (like InfraNodus does)
- Reads the Obsidian vault as context
- Runs gap detection algorithmically
- Returns structured insights that can be integrated into Claude conversations

## Obsidian Graph View Configuration
To use the built-in Graph View as a knowledge map:
1. Open Graph View (Ctrl+G)
2. Filter by folder: `Sovran AI/`
3. Group by tags: `#bug` (red), `#research` (blue), `#trade` (green)
4. Look for **isolated nodes** — these are knowledge that isn't connected
5. Look for **bridges** — notes that connect multiple clusters

## Gap Detection Algorithm (Pseudocode)
```python
# 1. Parse all notes
notes = parse_obsidian_vault("C:/KAI/obsidian_vault/Sovran AI/")

# 2. Build graph
G = nx.Graph()
for note in notes:
    G.add_node(note.title, tags=note.tags)
    for link in note.wikilinks:
        G.add_edge(note.title, link)

# 3. Find communities (clusters)
communities = nx.community.louvain_communities(G)

# 4. Find gaps (unconnected community pairs)
for c1, c2 in combinations(communities, 2):
    if not any(G.has_edge(n1, n2) for n1 in c1 for n2 in c2):
        print(f"GAP: {c1} <-> {c2}")
        # Generate bridging question via LLM
```

## Why This Matters for Trading
1. **Bug patterns** that we keep hitting may be connected to **architectural debt** we haven't linked
2. **Research insights** about market microstructure may solve **edge problems** we haven't considered
3. **Session learnings** from failed trades may reveal **systemic issues** that look like isolated bugs
4. By building the graph and finding gaps, we can **see what we're NOT seeing**

---
**Problem Tracker:** See `Bugs/PROBLEM_TRACKER.md` — "Knowledge Graph Integration (Planned)"
**InfraNodus Transcript:** See `Research/InfraNodus_Knowledge_Graph_Transcript.md`
