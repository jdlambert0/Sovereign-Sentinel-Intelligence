# 🌐 TRUSTGRAPH ONTOLOGY: Trading Context Core

## 🎯 OBJECTIVE
To define the structured knowledge graph for Sovereign Hunt, allowing the AI to "navigate" its past successes and failures using TrustGraph's native relationship mapping.

---

## 1. ENTITY DEFINITIONS (THE NODES)
| Entity | Description | Required Fields |
|---|---|---|
| **MarketRegime** | The high-level state. | `regime_type` (Trend/Chop), `volatility_bracket` |
| **Microstructure** | The order-flow snapshot. | `ofi_score`, `vpin_score`, `imbalance_ratio` |
| **TradingThesis** | The AI’s prediction. | `direction`, `target`, `stop`, `conviction` |
| **InvalidationGate** | The failure condition. | `price_trigger`, `narrative_fail` (e.g., "OFI flips") |
| **TradeOutcome** | The PnL result. | `pnl`, `mafe` (Max Advers_Excursion), `mfae` |

---

## 2. RELATIONSHIP DEFINITIONS (THE EDGES)
- **THESIS** -> `based_on` -> **MICROSTRUCTURE**
- **MICROSTRUCTURE** -> `occurs_in` -> **MARKET_REGIME**
- **THESIS** -> `guarded_by` -> **INVALIDATION_GATE**
- **TRADE_OUTCOME** -> `validates` -> **THESIS**

---

## 3. SEMANTIC CONTEXT CORE (The "Why")
Instead of just searching for "MNQ Buy", the AI will query the graph:
> *"Find me all **TradingTheses** that were `validated` by a positive **TradeOutcome** when the **MarketRegime** was 'Trend-Bullish' and **OFI** was > +50."*

---

## 4. INTEGRATION ROADMAP
1. **Phase A (Portable Cores)**: Export all Obsidian `Trades/` and `Learnings/` as JSON-backed nodes.
2. **Phase B (Schema Mapping)**: Align the Python bridge with this Ontology so every trade stores its "Relational ID."
3. **Phase C (TrustGraph Workbench)**: Use the 3D visualizer to see the "Cluster of Profitability."

---
#trustgraph #ontology #knowledge-graph #trading-intelligence #context-core
