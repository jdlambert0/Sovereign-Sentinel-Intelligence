---
title: TrustGraph Integration Plan — Sovran V2
type: integration-plan
priority: P1
created: 2026-03-27
status: ready-to-deploy
---

# TrustGraph Integration for Sovran V2

## What Is TrustGraph?

[TrustGraph](https://github.com/trustgraph-ai/trustgraph) (1.7k stars) is an open-source *context development platform* — graph-native infrastructure for storing, enriching, and retrieving structured knowledge. Think Supabase but for knowledge graphs.

**Why it matters for us:** It replaces our flat-file Obsidian memory with a real graph database that any LLM can query via API. Trade history, market research, gambling theory, and system knowledge all become structured, searchable, and retrievable with semantic similarity + graph relationships.

### What TrustGraph Gives Us

| Feature | Current (Obsidian) | With TrustGraph |
|---------|-------------------|-----------------|
| Memory storage | Flat markdown files | Graph DB (Cassandra) + Vector DB (Qdrant) |
| Retrieval | Read full files | Semantic search (DocumentRAG), relationship traversal (GraphRAG) |
| LLM access | Must read entire files | API query for relevant context only |
| Cross-reference | Manual links | Automatic entity + relationship extraction |
| Scale | ~20 files | Millions of entities |
| Persistence | File system | Docker volumes |
| Visualization | None | 3D GraphViz built-in |
| Agent integration | Custom IPC | MCP protocol + REST + WebSocket + Python API |

---

## Architecture: How TrustGraph Fits Into Sovran V2

```
                    ┌─────────────────────────────────────┐
                    │         TrustGraph (Docker)          │
                    │                                      │
                    │  ┌──────────┐  ┌──────────┐         │
                    │  │Cassandra │  │  Qdrant  │         │
                    │  │(graph+KV)│  │(vectors) │         │
                    │  └──────────┘  └──────────┘         │
                    │  ┌──────────┐  ┌──────────┐         │
                    │  │  Garage  │  │  Pulsar  │         │
                    │  │ (files)  │  │(pub/sub) │         │
                    │  └──────────┘  └──────────┘         │
                    │                                      │
                    │  REST API :12345  │  Workbench :8888  │
                    └────────┬─────────┴───────────────────┘
                             │
               ┌─────────────┼─────────────┐
               │             │             │
    ┌──────────▼──┐  ┌───────▼──────┐  ┌──▼──────────────┐
    │ AI Decision │  │ ralph_ai_loop│  │ Any LLM (Claude,│
    │ Engine      │  │ .py          │  │ GPT, Gemini,    │
    │             │  │              │  │ local Ollama)   │
    │ Query before│  │ Ingest after │  │                 │
    │ every trade │  │ every trade  │  │ Query via MCP   │
    └─────────────┘  └──────────────┘  └─────────────────┘
```

### Data Flow

1. **Ingest Phase** (after each trade):
   - `ralph_ai_loop.py` calls TrustGraph REST API
   - Ingests: trade outcome, market conditions, strategy used, regime, P&L
   - TrustGraph extracts entities and relationships automatically
   - Builds knowledge graph: `MCL --[traded_in]--> Trending_Up --[won_with]--> Momentum`

2. **Query Phase** (before each trade):
   - `ai_decision_engine.py` queries TrustGraph before making decisions
   - "What strategy has the best win rate for MCL in trending regimes?"
   - "What time of day has the highest EV for energy contracts?"
   - Returns structured context, not raw text

3. **Research Ingest** (bulk load):
   - Load all research from `_research/` into TrustGraph
   - Ed Thorp strategies, probability models, gambling theory
   - All becomes queryable knowledge for any LLM

---

## Deployment Plan

### Prerequisites
- Docker Desktop for Windows (or Podman)
- ~4-8GB RAM available for containers
- Node.js (for npx config tool)

### Step 1: Generate Config

```bash
npx @trustgraph/config
```

Choose these options:
- **Deploy target:** Docker Compose
- **LLM:** Ollama (for local) OR Anthropic/OpenAI (with API key)
- **Graph store:** Cassandra (default)
- **Vector store:** Qdrant (default)
- **Enable:** Workbench, GraphRAG, DocumentRAG, Agent, MCP

This generates `deploy.zip` containing `docker-compose.yaml`.

### Step 2: Launch

```bash
cd C:\KAI\trustgraph
unzip deploy.zip
docker-compose up -d
```

Services will be available at:
- **Workbench:** http://localhost:8888
- **REST API:** http://localhost:12345
- **GraphViz:** http://localhost:8888 (built into workbench)

### Step 3: Load Existing Knowledge

Run the bulk loader to ingest all Obsidian knowledge + research:

```bash
python scripts/trustgraph_loader.py
```

This script (provided below) will:
1. Read all `obsidian/*.md` files
2. Read all `_research/*.md` files
3. Load them into TrustGraph via REST API
4. Let TrustGraph extract entities/relationships automatically

### Step 4: Wire Into Trading System

Add to `config/.env`:
```
TRUSTGRAPH_API_URL=http://localhost:12345
TRUSTGRAPH_API_KEY=your-chosen-key
```

---

## Integration Code

### trustgraph_client.py — Drop-in Client for Sovran V2

Create as `src/trustgraph_client.py`:

```python
"""
TrustGraph client for Sovran V2.

Provides structured knowledge retrieval for the AI Decision Engine.
Replaces flat-file Obsidian reads with graph-native semantic queries.
"""
import os
import json
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TRUSTGRAPH_URL = os.environ.get("TRUSTGRAPH_API_URL", "http://localhost:12345")
TRUSTGRAPH_KEY = os.environ.get("TRUSTGRAPH_API_KEY", "")


class TrustGraphClient:
    """Client for TrustGraph REST API."""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or TRUSTGRAPH_URL).rstrip("/")
        self.api_key = api_key or TRUSTGRAPH_KEY
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _post(self, endpoint: str, data: dict) -> Optional[dict]:
        try:
            resp = requests.post(
                f"{self.base_url}{endpoint}",
                json=data,
                headers=self.headers,
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"TrustGraph API error: {e}")
            return None

    # ── Knowledge Retrieval ──

    def query_graph_rag(self, question: str) -> Optional[str]:
        """
        Query using GraphRAG — traverses entity relationships.
        Best for: "What strategy works best for MCL in trending markets?"
        """
        result = self._post("/api/v1/graph-rag", {"query": question})
        if result:
            return result.get("response", "")
        return None

    def query_document_rag(self, question: str) -> Optional[str]:
        """
        Query using DocumentRAG — semantic similarity search.
        Best for: "What does Ed Thorp say about position sizing?"
        """
        result = self._post("/api/v1/document-rag", {"query": question})
        if result:
            return result.get("response", "")
        return None

    def vector_search(self, text: str, limit: int = 5) -> List[Dict]:
        """
        Raw vector similarity search.
        Returns most similar stored knowledge chunks.
        """
        result = self._post("/api/v1/vector-search", {
            "query": text,
            "limit": limit
        })
        if result:
            return result.get("results", [])
        return []

    # ── Knowledge Ingestion ──

    def ingest_trade(self, trade_data: Dict) -> bool:
        """
        Ingest a completed trade as structured knowledge.

        TrustGraph will automatically extract entities:
        - Contract (MCL, MNQ, etc.)
        - Strategy (momentum, mean_reversion)
        - Regime (trending, choppy)
        - Outcome (win/loss)
        - Time of day
        And create relationships between them.
        """
        text = self._trade_to_text(trade_data)
        return self.ingest_text(text, metadata={
            "type": "trade_outcome",
            "contract": trade_data.get("contract", ""),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def ingest_text(self, text: str, metadata: Dict = None) -> bool:
        """Ingest raw text into TrustGraph."""
        data = {"text": text}
        if metadata:
            data["metadata"] = metadata
        result = self._post("/api/v1/load/text", data)
        return result is not None

    def ingest_file(self, file_path: str) -> bool:
        """Ingest a file (markdown, PDF, etc.) into TrustGraph."""
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    f"{self.base_url}/api/v1/load/document",
                    files={"file": f},
                    headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                    timeout=60
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"TrustGraph file ingest error: {e}")
            return False

    # ── Trading-Specific Queries ──

    def get_strategy_for_conditions(self, contract: str, regime: str,
                                     time_of_day: str = "") -> Optional[Dict]:
        """
        Ask TrustGraph: what's the best strategy for these conditions?
        Returns structured recommendation from knowledge graph.
        """
        question = (
            f"Based on historical trade outcomes, what is the best trading strategy "
            f"for {contract} in a {regime} market regime"
            f"{f' during {time_of_day}' if time_of_day else ''}? "
            f"Include win rate, average P&L, and confidence level."
        )
        response = self.query_graph_rag(question)
        if response:
            return {"recommendation": response, "source": "graph_rag"}
        return None

    def get_risk_context(self, contract: str) -> Optional[str]:
        """
        Get risk-relevant context for a contract.
        Queries: historical drawdowns, Kelly sizing history, RoR trends.
        """
        return self.query_graph_rag(
            f"What are the risk characteristics and historical drawdowns for {contract}? "
            f"Include Kelly Criterion sizing recommendations and Risk of Ruin data."
        )

    def get_research_insight(self, topic: str) -> Optional[str]:
        """
        Query research knowledge base.
        E.g., "Ed Thorp on mean reversion", "Billy Walters on information edge"
        """
        return self.query_document_rag(
            f"What do the research materials say about {topic}? "
            f"Include specific strategies, formulas, and practical applications."
        )

    # ── Helpers ──

    @staticmethod
    def _trade_to_text(trade: Dict) -> str:
        """Convert trade data to natural language for ingestion."""
        contract = trade.get("contract", "UNKNOWN")
        strategy = trade.get("strategy", "unknown")
        signal = trade.get("signal", "unknown")
        pnl = trade.get("pnl", 0.0)
        outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"
        regime = trade.get("regime", "unknown")
        conviction = trade.get("conviction", 0)
        thesis = trade.get("thesis", "")
        hold_time = trade.get("hold_time", 0)
        mfe = trade.get("mfe", 0)
        mae = trade.get("mae", 0)

        return (
            f"Trade Outcome: {outcome} on {contract} using {strategy} strategy. "
            f"Signal was {signal} with {conviction}% conviction in {regime} regime. "
            f"P&L: ${pnl:+.2f}. Hold time: {hold_time:.0f}s. "
            f"MFE (max favorable): {mfe:.1f} ticks. MAE (max adverse): {mae:.1f} ticks. "
            f"Thesis: {thesis}"
        )
```

### Wiring Into AI Decision Engine

Add to `ai_decision_engine.py` in the `analyze_contract()` method, after calculating model probabilities:

```python
# ── TRUSTGRAPH CONTEXT (if available) ──
try:
    from src.trustgraph_client import TrustGraphClient
    tg = TrustGraphClient()
    tg_advice = tg.get_strategy_for_conditions(contract_id, regime)
    if tg_advice:
        thesis += f" [TG: {tg_advice['recommendation'][:100]}]"
        logger.info(f"  TrustGraph context: {tg_advice['recommendation'][:80]}")
except ImportError:
    pass  # TrustGraph not installed yet
except Exception as e:
    logger.debug(f"  TrustGraph query failed (non-critical): {e}")
```

### Wiring Into Ralph (Post-Trade Ingest)

Add to `ralph_ai_loop.py` after each iteration completes:

```python
# ── TRUSTGRAPH INGEST (if available) ──
try:
    from src.trustgraph_client import TrustGraphClient
    tg = TrustGraphClient()
    for trade in session_results.get("trades", []):
        tg.ingest_trade(trade)
        logger.info(f"[TG] Ingested trade: {trade.get('contract')} {trade.get('signal')}")
except ImportError:
    pass  # TrustGraph not installed yet
except Exception as e:
    logger.warning(f"[TG] Ingest failed (non-critical): {e}")
```

---

## Bulk Loader Script

Save as `scripts/trustgraph_loader.py`:

```python
"""
Bulk-load all Sovran V2 knowledge into TrustGraph.

Loads:
1. All Obsidian vault files (system knowledge)
2. All research files (gambling theory, probability models)
3. Trading rules and philosophy

Run once after TrustGraph deployment, then incrementally after that.
"""
import glob
import os
import sys
import time

# Add parent dir to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.trustgraph_client import TrustGraphClient

def main():
    tg = TrustGraphClient()
    loaded = 0
    failed = 0

    # 1. Obsidian vault
    print("=== Loading Obsidian Vault ===")
    for path in sorted(glob.glob("obsidian/*.md")):
        name = os.path.basename(path)
        print(f"  Loading {name}...", end=" ")
        if tg.ingest_file(path):
            print("OK")
            loaded += 1
        else:
            print("FAILED")
            failed += 1
        time.sleep(0.5)  # Rate limit

    # 2. Research files (if available)
    research_dirs = [
        "_research",
        "C:/KAI/_research",
    ]
    for research_dir in research_dirs:
        if os.path.isdir(research_dir):
            print(f"\n=== Loading Research from {research_dir} ===")
            for path in sorted(glob.glob(f"{research_dir}/**/*.md", recursive=True)):
                name = os.path.relpath(path, research_dir)
                print(f"  Loading {name}...", end=" ")
                if tg.ingest_file(path):
                    print("OK")
                    loaded += 1
                else:
                    print("FAILED")
                    failed += 1
                time.sleep(0.5)

    print(f"\n=== Done: {loaded} loaded, {failed} failed ===")

if __name__ == "__main__":
    main()
```

---

## What Knowledge Gets Stored

### Entity Types (auto-extracted by TrustGraph)
- **Contract**: MCL, MNQ, MES, MGC, MYM, M2K
- **Strategy**: momentum, mean_reversion, volatility_harvesting
- **Regime**: trending, choppy, ranging, volatile
- **TimeSlot**: US_Open, US_Core, Lunch, US_Close
- **Researcher**: Ed_Thorp, Billy_Walters, MIT_Team, Chris_Ferguson
- **Concept**: Kelly_Criterion, Risk_of_Ruin, Bayesian_Updating, Mean_Reversion
- **TradeOutcome**: individual trade records

### Relationship Types (auto-extracted)
- `Contract --[performs_best_in]--> Regime`
- `Strategy --[applied_to]--> Contract`
- `Strategy --[wins_in]--> Regime`
- `Researcher --[developed]--> Concept`
- `Concept --[implemented_in]--> SystemComponent`
- `TradeOutcome --[used]--> Strategy`
- `TradeOutcome --[occurred_in]--> Regime`

### Example Queries Once Populated
```
"What strategy has the highest win rate for MCL?"
→ TG traverses: MCL --[traded_with]--> {strategies} --[won]--> {outcomes}
→ Returns: "Momentum strategy has 65% win rate on MCL based on 23 trades"

"What does Ed Thorp recommend for position sizing when RoR is high?"
→ TG searches: Ed_Thorp --[developed]--> Kelly_Criterion --[recommends]--> ...
→ Returns: "Thorp recommends fractional Kelly at 25% when RoR approaches 1%..."

"What time of day is worst for equity index trading?"
→ TG traverses: MES/MNQ --[traded_at]--> {time_slots} --[resulted_in]--> {outcomes}
→ Returns: "Equity indices show 0% win rate during lunch chop (12:30-2pm CT)..."
```

---

## Deployment Checklist

- [ ] Install Docker Desktop on Windows
- [ ] Run `npx @trustgraph/config` to generate docker-compose
- [ ] `docker-compose up -d` to start TrustGraph
- [ ] Verify Workbench at http://localhost:8888
- [ ] Copy `src/trustgraph_client.py` into project
- [ ] Add `TRUSTGRAPH_API_URL` to `.env`
- [ ] Run `python scripts/trustgraph_loader.py` for initial knowledge load
- [ ] Verify knowledge in Workbench → Graph Visualizer
- [ ] Wire into `ai_decision_engine.py` (query before trades)
- [ ] Wire into `ralph_ai_loop.py` (ingest after trades)
- [ ] Monitor TrustGraph logs for errors

---

*This integration is designed to be non-blocking. If TrustGraph is down or not installed, the system falls back to existing flat-file memory. All TrustGraph calls are wrapped in try/except with graceful degradation.*
