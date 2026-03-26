# Intelligence Node: TradingAgents Framework Architecture

## Gumption Logic: Why we researched this
We investigated the `TauricResearch/TradingAgents` repository to understand state-of-the-art multi-agent financial reasoning. As Sovran AI scales its 9-task MEMM Grid, observing how academic and open-source frameworks orchestrate structured debate (Bull vs. Bear) and risk modeling can provide architectural alpha for our next iterations.

## Mathematical & Architectural Invariants
1. **Delegation of Compute (Fast/Deep Thinking)**
   - The framework explicitly splits LLM cognitive load into `quick_think_llm` (e.g., gpt-4o-mini, haiku) for routing/summarization and `deep_think_llm` (e.g., gpt-4o, sonnet) for complex reasoning and final decisions.
   - *Invariant*: Routing cognitive load by task complexity preserves speed while allocating heavy compute only to the final probabilistic trade decision.

2. **Structured Adversarial Debate**
   - Employs dedicated `Bull Researcher` and `Bear Researcher` agents that construct explicit opposing arguments before the `Trader Agent` sees them.
   - *Invariant*: Forced polarization prevents early consensus collapse. The system requires agents to find reasons the trade will succeed *and* fail, mirroring our "Skepticism" parameter but elevating it to an independent agent level.

3. **Multi-Domain Information Silos**
   - Analysts are separated by domain: Fundamentals, Sentiment, News, Technical. Each has dedicated tools (e.g., `get_insider_transactions`, `get_stock_data`).
   - *Invariant*: Siloing data collection prevents LLM context contamination. An agent only reasons over the metrics it is specialized to interpret.

4. **Abstracted Memory States (State Graph)**
   - Utilizes `LangGraph` and a `FinancialSituationMemory` to pass distinct state blocks (`InvestDebateState`, `RiskDebateState`) between nodes.
   - *Invariant*: State must be strongly typed and historically persistent to allow agents to "reflect" on previous debate rounds.

## Trading Alpha: Application to Sovran
- **The "Veto Auditor" Evolution**: Currently, Sovran AI uses a single `VetoAuditor`. We can expand this into a "Risk Management Agent" that debates the "Sovereign Leader" directly, requiring the Leader to mathematically justify bypassing the veto.
- **Model Arbitration**: We currently use Haiku for the Council Leader. If we adopt the fast/deep pattern, we could use Haiku for continuous data scanning (fast), but trigger Sonnet/Pro (deep) only when Haiku identifies a strong anomaly (e.g., OFI Z-Score > 3.0 or VPIN > 0.8).
- **Tool Silos**: Future iterations of Sovran could spawn distinct subagents for News/Sentiment analysis prior to the main engine cycle, separating the microstructure execution loop from the macro-sentiment synthesis loop.

## The Inversion: How this concept could still fail us
- **Latency**: TradingAgents is research-focused and heavily sequential/graph-based. In live Futures (MNQ/MES), executing a multi-round debate through LangGraph would take 30-60+ seconds. Microstructure edges (like OFI sweeps) decay in milliseconds.
- **Resolution**: Sovran MUST retain its monolithic, single-prompt execution for the actual trade triggers to maintain sub-second speed. The "Multi-Agent Debate" pattern should only be used *asynchronously* (like the Curiosity Engine) to generate macro-bias variables that the fast-execution engine ingests, rather than debating the live trade itself.
