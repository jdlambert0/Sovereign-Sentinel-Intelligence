"""
TrustGraph client for Sovran V2.

Provides structured knowledge retrieval for the AI Decision Engine.
Replaces flat-file Obsidian reads with graph-native semantic queries.

Usage:
    from src.trustgraph_client import TrustGraphClient
    tg = TrustGraphClient()
    advice = tg.get_strategy_for_conditions("MCL", "trending")
    tg.ingest_trade({"contract": "MCL", "pnl": 38.48, ...})

Requires:
    - TrustGraph running (docker-compose up -d)
    - TRUSTGRAPH_API_URL in .env (default: http://localhost:12345)
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
        self._available = None  # Cache availability check

    def is_available(self) -> bool:
        """Check if TrustGraph is running. Cached after first call."""
        if self._available is not None:
            return self._available
        try:
            resp = requests.get(f"{self.base_url}/api/v1/health", timeout=3)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def _post(self, endpoint: str, data: dict) -> Optional[dict]:
        if not self.is_available():
            return None
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

    # -- Knowledge Retrieval --

    def query_graph_rag(self, question: str) -> Optional[str]:
        """
        Query using GraphRAG -- traverses entity relationships.
        Best for: "What strategy works best for MCL in trending markets?"
        """
        result = self._post("/api/v1/graph-rag", {"query": question})
        if result:
            return result.get("response", "")
        return None

    def query_document_rag(self, question: str) -> Optional[str]:
        """
        Query using DocumentRAG -- semantic similarity search.
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

    # -- Knowledge Ingestion --

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
        if not self.is_available():
            return False
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

    # -- Trading-Specific Queries --

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

    # -- Helpers --

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
