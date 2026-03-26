# Sovran Learning Plan with Superforecasting

**Date**: 2026-03-18  
**Updated**: 2026-03-19 - Added TradingAgents framework  
**Status**: API Subscription Required for Real-Time Data

---

## 🚨 CRITICAL BUG FOUND - LEARNING_MODE WAS BROKEN

**The Problem**: Even with `LEARNING_MODE = True`, the system had TWO gates that still blocked ALL trading:

1. **Spread Gate** - If spread > 4 ticks, NO TRADE
2. **Micro-Chop Guard** - If session range < 50 pts, NO TRADE

**Why Hunter Alpha Never Traded**: Market conditions weren't meeting these thresholds, so the system just sat idle despite being in "learning mode."

**The Fix**: Updated `sovran_ai.py` so LEARNING_MODE now bypasses BOTH spread and micro-chop gates.

---

## Superforecasting Framework

### What is Superforecasting?

Superforecasting is the methodology developed by Philip Tetlock (Good Judgment Project) that produced "superforecasters" - people who could predict world events with remarkable accuracy.

**Key Principles**:

1. **Probabilistic Thinking**: Everything is a probability, not a certainty
2. **Calibration**: Be honest about confidence levels
3. **Fermi Estimates**: Break complex questions into components
4. **Tracking Accuracy**: Measure and learn from predictions
5. **Updating**: Revise beliefs when new evidence arrives

### Applying Superforecasting to Trading

**Instead of**: "The market will go up"
**Say**: "There's a 73% probability the market will be higher in 30 minutes, with a confidence interval of ±15%"

### Superforecasting Steps for Each Trade

```
1. PRIOR PROBABILITY: Start with base rate (what usually happens)
2. NEW INFORMATION: Update based on:
   - Order flow imbalance (VPIN)
   - Spread conditions
   - Recent price action
   - Volume patterns
3. CALCULATE POSTERIOR: New probability after updates
4. SET THRESHOLD: Only trade if probability > X% (e.g., 65%)
5. RECORD AND UPDATE: Track accuracy, adjust threshold
```

### Superforecasting Questions for Sovran

Before each trade, answer:

| Question | Answer Format |
|----------|---------------|
| What's the base rate win rate? | __% |
| How does current VPIN affect this? | +/ - __% |
| How does current spread affect this? | +/ - __% |
| What's the conditional probability? | __% |
| Is this above threshold (65%)? | YES/NO |
| What's my confidence? | __% |

---

## III. Gambling & Probability Frameworks

### 1. Kelly Criterion for MNQ Position Sizing
*   **Formula:** $f = \frac{W \times R - (1 - W)}{R}$
    *   $W$: Win Rate (decimal)
    *   $R$: Reward-to-Risk Ratio ($AvgWin / AvgLoss$)
    *   $f$: Optimal fraction of DRAWDOWN to risk per trade.
*   **Implementation**: Apply **Half-Kelly ($0.5f$)** to account for MNQ volatility.
*   **Drawdown Basis**: Calculate risk based on the $2,000 prop firm drawdown, NOT the $50k account balance.

### 2. Risk of Ruin (RoR)
*   **Formula**: $RoR \approx (\frac{1 - Edge}{1 + Edge})^U$ ($U$ = Units of risk before blowout).
*   **Constraint**: In a prop firm, $U$ is small (10-20 units).
*   **AI Protocol**: Prioritize survival (increasing $U$) by reducing risk-per-trade during drawdown phases.

### 3. Trading Expectancy Optimization
*   **Expectancy**: $E = (Win\% \times AvgWin) - (Loss\% \times AvgLoss)$.
*   **Threshold Tuning**: If rolling 10-trade expectancy < 0.5 points, AI MUST tighten Order Flow filters (e.g., raise OFI requirement to 5:1).
*   **Circuit Breaker**: Suspend trading if current session expectancy is negative after 3 consecutive trades.

---

## Phase 1: Data Collection (NOW - FIXED)

**GOAL**: Collect 100+ trades to build statistical baseline

### What to Log Per Trade

| Field | Description |
|-------|-------------|
| timestamp | Exact time of decision |
| market_price | Price at decision time |
| spread_ticks | Current spread |
| vpin | Volume-synchronized Probability of Informed Trading |
| confidence | Hunter Alpha's stated confidence |
| prediction | BUY/SELL/WAIT |
| actual_outcome | Price change after N minutes |
| pnl | Actual profit/loss |
| conditions | Micro-chop/wide-spread/etc |

### Superforecasting Metrics to Track

| Metric | Description |
|--------|-------------|
| Brier Score | Measure of probabilistic prediction accuracy |
| Calibration | Did 70% confidence events happen 70% of the time? |
| Resolution | How much did predictions distinguish outcomes? |

---

## Phase 2: Pattern Recognition (Week 2)

**GOAL**: Find conditions that predict wins vs losses

### Superforecasting Analysis

```
For each condition (spread, VPIN, time, etc):
  1. Calculate win rate WITH this condition
  2. Calculate win rate WITHOUT this condition
  3. Calculate conditional probability: P(win | condition)
  4. If P(win | condition) > 55%, flag as EDGE condition
```

### Pattern Categories

| Pattern | Win Rate | When to Trade |
|--------|----------|---------------|
| Tight spread + Low VPIN | 60%+ | Ideal conditions |
| Wide spread + High VPIN | 40% | Avoid |
| Morning session | 55% | Good |
| Afternoon session | 45% | Poor |

---

## Phase 3: Self-Optimization (Week 3+)

**GOAL**: Let system adjust parameters based on results

### Self-Optimizing Parameters

1. **Entry Threshold**: Adjust based on win rate
2. **Stop Loss**: Optimize based on volatility
3. **Take Profit**: Adjust based on R:R analysis
4. **Confidence Cutoff**: Raise/lower based on accuracy

### The Self-Learning Loop

```
Every 20 trades:
  1. Calculate Brier score
  2. If score < 0.25 (good):
     - Increase position size slightly
     - Lower entry threshold
  3. If score > 0.40 (poor):
     - Decrease position size
     - Raise entry threshold
  4. Store updated parameters in memory
```

---

## The $1K/Day Math (Superforecasting View)

| Component | Calculation |
|-----------|------------|
| Base win rate | ~50% |
| Superforecasting improvement | +5-10% |
| Target win rate | 55-60% |
| Average R:R | 2:1 |
| Expected value per trade | +$50-100 |
| Trades needed for $1K | 10-20/day |

**Superforecasting doesn't predict direction. It quantifies uncertainty.**

---

## Next Steps (Immediate)

### Step 1: Verify LEARNING_MODE Now Works
- Run Sovran with LEARNING_MODE = True
- Verify it bypasses spread and micro-chop gates
- Check logs for "LEARNING MODE: Bypassing" messages

### Step 2: Force First Trade
- Use mandate mode to force one trade
- Verify order reaches broker
- Check TopStepX for confirmation

### Step 3: Collect Baseline Data
- Let system trade freely for 2-3 hours
- Collect 20-50 trades minimum
- Analyze for patterns

### Step 4: Implement Superforecasting Metrics
- Add Brier score calculation
- Add calibration tracking
- Update AI prompt to include Superforecasting questions

### Step 5: Analyze and Optimize
- Calculate win rate by condition
- Identify edge conditions
- Adjust thresholds

---

## Files Modified

| File | Change |
|------|--------|
| `sovran_ai.py` | LEARNING_MODE now bypasses spread + micro-chop gates |

---

## Verification Checklist

- [x] Identified LEARNING_MODE bug
- [x] Fixed spread gate bypass
- [x] Fixed micro-chop gate bypass
- [ ] Verified syntax
- [ ] Test run with logs
- [ ] Force first trade
- [ ] Collect 20+ trades
- [ ] Calculate Brier scores
- [ ] Identify edge conditions

---

*Superforecasting turns opinions into calibrated probabilities.*

---

## NEW: TradingAgents Multi-Agent Framework

**Source**: https://github.com/TauricResearch/TradingAgents  
**Stars**: 33.2k | **Forks**: 6.4k | **License**: Apache-2.0  
**Tech**: Python, LangGraph, Multi-LLM (OpenAI/GPT, Google/Gemini, Anthropic/Claude, xAI/Grok, OpenRouter, Ollama)

### Architecture Overview

TradingAgents mirrors a **real trading firm** with specialized agents:

```
┌─────────────────────────────────────────────────────────────┐
│                    ANALYST TEAM                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │Funda-    │ │Sentiment │ │  News    │ │Technical │      │
│  │mentals   │ │Analyst   │ │Analyst   │ │Analyst   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   RESEARCHER TEAM                             │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │   Bullish Researcher │◄──►│  Bearish Researcher │        │
│  └─────────────────────┘    └─────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      TRADER AGENT                            │
│  Composes reports, determines timing & magnitude             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              RISK MANAGEMENT + PORTFOLIO MANAGER             │
│  Evaluates risk, approves/rejects trades                     │
└─────────────────────────────────────────────────────────────┘
```

### Agent Roles

| Agent | Purpose | Sovran Integration |
|-------|---------|-------------------|
| **Fundamentals Analyst** | Evaluates company financials | Could analyze market structure/regime |
| **Sentiment Analyst** | Social media + public sentiment | Order flow sentiment (VPIN) |
| **News Analyst** | Global news + macro indicators | Economic calendar events |
| **Technical Analyst** | MACD, RSI, patterns | Already in Sovran ✅ |
| **Bullish/Bearish Researchers** | Debate analysis | Self-play for strategy validation |
| **Risk Management** | Portfolio risk assessment | Circuit breakers already ✅ |
| **Portfolio Manager** | Final trade approval | Could add confirmation layer |

### Key Features

1. **Multi-LLM Support**: OpenAI, GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x
2. **LangGraph Orchestration**: Modular, scalable agent coordination
3. **Debate Rounds**: Bullish vs bearish researchers for balanced analysis
4. **Deep Think / Quick Think**: Different LLMs for complex vs simple tasks
5. **CLI Interface**: Easy experimentation with ticker/date/LLM selection
6. **Python Package**: Can import `TradingAgentsGraph()` directly

### How Sovran Can Learn from TradingAgents

| TradingAgents Feature | Sovran Implementation |
|---------------------|---------------------|
| Multiple specialized analysts | Currently: single LLM (Groq/Hunter Alpha) |
| Bullish/Bearish debate | Could add: "challenge my thesis" prompt |
| Risk management team | Already: circuit breakers ✅ |
| Technical analyst agent | Already: technical indicators ✅ |
| Sentiment analysis | Could add: VPIN sentiment scoring |
| News/macro analysis | Could add: economic calendar integration |
| Multi-LLM ensemble | Currently: single model |

### Potential Integration Ideas

1. **Hybrid Architecture**: Use TradingAgents for analysis, Sovran for execution
2. **Debate Prompt**: Add bullish/bearish argument generation to Sovran prompts
3. **Multi-Model Ensemble**: Use TradingAgents' multi-LLM approach for decision confidence
4. **Risk Assessment Layer**: Add formal risk scoring before trade execution
5. **Learning from Debates**: Capture bull/bear arguments for pattern recognition

### Next Steps for Integration

- [ ] Clone and explore TradingAgents codebase
- [ ] Run CLI with sample ticker (NVDA)
- [ ] Study agent coordination in `tradingagents/graph/`
- [ ] Consider: Can Sovran use TradingAgents' analyst agents?
- [ ] Consider: Add bull/bear debate prompt to Hunter Alpha

### Code Example (TradingAgents)

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openrouter"  # Use OpenRouter like Sovran
config["deep_think_llm"] = "anthropic/claude-sonnet-4"
config["quick_think_llm"] = "openrouter/hunters/Hunter-Alpha-Xiaomi-MiMo-V2-Pro"
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

### References

- Paper: https://arxiv.org/abs/2412.20138
- Discord: https://discord.com/invite/hk9PGKShPK
- Tauric Research: https://tauric.ai/

---

## NEW: Lightpanda Headless Browser for Agent Research

**Source**: https://github.com/lightpanda-io/browser  
**Purpose**: 10x faster, minimal-RAM headless browser designed for machine-to-machine web automation  
**Status**: ⏳ Planned — WSL2 install attempted but failed; exploring Windows-native path  
**Date Added**: 2026-03-19

### Why Lightpanda?

| Feature | Lightpanda | Puppeteer/Chrome |
|---------|-----------|-----------------|
| Speed | **10x faster** | Baseline |
| RAM | **~50MB** | ~300-500MB |
| Designed for | **Agents/M2M** | Human browsing |
| JS Engine | Zig-based | V8 |
| Headless-first | ✅ Yes | Bolted-on |

### Integration Plan

1. **Phase 1**: Install Lightpanda on Windows host (Puppeteer-compatible client)
2. **Phase 2**: Wire into agent subagent research tasks (replace Chrome-based browser)
3. **Phase 3**: Use for real-time web scraping (news, economic calendar, sentiment)
4. **Phase 4**: Power the Scout agent (Sovereign Fleet) with live web data

### Installation Notes

- WSL2 install failed (2026-03-19) — dependency issues
- **Recommended path**: Install native Windows binary or use Docker container
- Lightpanda exposes a **CDP (Chrome DevTools Protocol)** endpoint → Puppeteer can connect directly
- `npx puppeteer connect --browserURL=http://localhost:9222` should work once running

### Next Steps

- [ ] Research Windows-native install or Docker approach
- [ ] Test CDP connection from Puppeteer/Playwright
- [ ] Benchmark vs Chrome headless on agent research tasks
- [ ] Integrate into GEMINI.md as mandated research browser
- [ ] Deploy for Scout agent real-time data ingestion
