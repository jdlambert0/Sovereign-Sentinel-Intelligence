# Sovran AI - LLM Orchestration Process Map

This document details how LLMs are called, which models are used, and how data flows through the system.

## 1. Core Execution Flow

```mermaid
graph TD
    A[Start Loop - Every 30-45s] --> B{Position Open?}
    B -- Yes --> C[Monitor Exit/TP/SL]
    B -- No --> D[Data Ingestion]
    
    D --> E[Sovereign AI Council]
    D --> F[GSD-Gambler Engine]
    D --> G[Warwick Engine]
    
    subgraph "Sovereign AI Council"
    E1[Context Injection] --> E2[Prompt Construction]
## 2. Model Assignments & Purpose (REVISED: March 22)

| Component | Primary Model | Purpose | Provider |
|-----------|---------------|---------|----------|
| **AI Council Leader** | **`claude-sonnet-4-20250514`** | Strategic direction, high-conviction logic. | **Anthropic Direct** |
| **Council Consensus** | `gemini-2.5-flash` | High-fidelity audit layer & secondary perspective. | **Google Direct** |
| **Veto Auditor** | `gemini-2.5-flash` | Anti-slop / Anti-hallucination gate. | Google Direct |
| **Scout Agent** | `claude-sonnet-4-20250514` | Web research, sentiment analysis (Playwright). | Anthropic Direct |
| **Mailbox Hub** | `claude-4-haiku-20260307` | Fast, cost-effective inter-agent coordination. | Anthropic Direct |

> [!NOTE]
> **Direct-to-Lab Substrate**
> We have removed **OpenRouter** as a dependency to minimize "Truth Latency" and middleware costs. The system now communicates directly with Anthropic and Google API endpoints.

## 3. The Curiosity Loop & Mind Palace
The Curiosity Engine (`curiosity_engine.py`) runs as a background process to expand the system's "Gumption":
1. **Curiosity**: Analyzes performance and learning plans to generate a research topic (e.g., "The Kelly Criterion in Asymmetric Tails").
2. **Research**: Dispatches the **Scout Agent** to scan the web for data.
3. **Synthesis**: Ingests findings and creates an **Intelligence Node** in Obsidian.
4. **Accrual**: The next trading cycle in `sovran_ai.py` reads these nodes from the `Intelligence/` folder and injects them into the prompt.

## 4. Operational Invariants
*   **Loop Interval**: 90 seconds (Targeting <$20/day total cost).
*   **Safety**: SL/TP Atomic Brackets (Native platform OCO).
*   **Persistence**: All decisions and thoughts are logged to `Journal/` and `Session Logs/`.

---
*Created: March 20, 2026 | Audit Version: 1.0*
