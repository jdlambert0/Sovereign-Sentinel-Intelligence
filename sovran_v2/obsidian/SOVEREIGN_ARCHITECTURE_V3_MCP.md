---
title: Sovereign Sentinel — V3 Architecture: MCP-Native LLM Trading
type: architecture-plan
created: 2026-03-27T14:45:00-05:00
author: Claude Sonnet 4.6
status: APPROVED — implement next
priority: P0
---

# Sovereign Sentinel V3 Architecture: MCP-Native LLM Trading

## The Question Jesse Asked

> "Is IPC file-based the best way for an LLM like you to trade without API calls, so any AI can trade the system?"

**Short answer: IPC files were the right instinct, wrong implementation layer. MCP is the right answer.**

---

## Why the Current IPC System Is Good But Limited

The current architecture:
```
live_session_v5.py  →  ipc/request_{ts}.json  →  ai_decision_engine.py  →  ipc/response_{ts}.json
```

**What works:**
- LLM-agnostic by design (right idea)
- Any process can write/read the files
- Auditable (files persist)

**What's broken:**
- `ai_decision_engine.py` is Python logic *pretending* to be an LLM — it's rigid rules, not real intelligence
- For a real LLM (Claude Code, me) to trade via this system, I'd have to manually watch a folder and write files — clunky
- No obsidian context flows into the decision — the AI is blind to memory
- No standard — every LLM integration has to be custom-built
- 2984 stale response files accumulated in one day (file bloat problem)

---

## The Right Answer: Model Context Protocol (MCP)

**MCP is the industry standard** (Anthropic, OpenAI, Google, Microsoft all adopted it):
- 5,800+ MCP servers in production as of 2026
- 97M+ monthly SDK downloads
- Works with: Claude Code, Claude Desktop, GPT-4, Gemini, local LLMs (Ollama), any MCP client
- No API calls — MCP uses stdio transport (local process, zero network needed)

**The key insight for Jesse's vision:**
MCP turns the trading system into a set of **tools** that any LLM can call natively. Instead of:
> "Watch a file, write a file" (current)

It becomes:
> "I see the market. I query my memory. I reason. I execute." (MCP)

---

## V3 Architecture: Sovereign MCP Server

```
┌─────────────────────────────────────────────────────────┐
│    ANY LLM (Claude Code, Claude Desktop, GPT-4,         │
│    Gemini, Ollama local model, next LLM Jesse uses)     │
│                                                          │
│    LLM THINKS:                                          │
│    "OFI is -0.58 but obsidian shows last 3 MES          │
│     morning sessions reversed at this level.            │
│     Momentum + volume confirm. Taking LONG.             │
│     Thesis: mean reversion at VWAP, 8-tick stop."       │
└────────────────────────┬────────────────────────────────┘
                         │ MCP stdio transport
                         │ (no API call — LLM is already running)
                         │ (one line in Claude Code settings)
┌────────────────────────▼────────────────────────────────┐
│              SOVEREIGN MCP SERVER                        │
│              sovran_mcp_server.py                        │
│                                                          │
│  TOOLS (LLM calls these):                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │ get_market_snapshot()                            │   │
│  │   → live prices, OFI, VPIN, ATR, regime,         │   │
│  │     spread, volume for all 6 contracts           │   │
│  │                                                  │   │
│  │ run_probability_models(contract)                 │   │
│  │   → ALL 12 models: Kelly, poker EV, Bayesian,   │   │
│  │     momentum, mean reversion, order flow,        │   │
│  │     info theory, casino edge, vol, arb,          │   │
│  │     Monte Carlo, market making — raw signals     │   │
│  │                                                  │   │
│  │ query_memory(context_description)               │   │
│  │   → searches obsidian for similar past          │   │
│  │     conditions, returns relevant trade logs     │   │
│  │                                                  │   │
│  │ place_trade(contract, action, size,              │   │
│  │             sl_ticks, tp_ticks, thesis)          │   │
│  │   → executes on TopStepX, logs to obsidian      │   │
│  │                                                  │   │
│  │ get_account_status()                            │   │
│  │   → balance, open positions, daily PnL,         │   │
│  │     remaining risk budget                       │   │
│  │                                                  │   │
│  │ log_observation(market_note)                    │   │
│  │   → writes real-time market observation         │   │
│  │     to obsidian for future memory               │   │
│  │                                                  │   │
│  │ get_trading_rules()                             │   │
│  │   → returns current trading philosophy          │   │
│  │     from obsidian (Jesse's mandates)            │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  RESOURCES (LLM can read these at any time):            │
│  ┌──────────────────────────────────────────────────┐   │
│  │ obsidian://philosophy   → ai_trading_philosophy  │   │
│  │ obsidian://recent-trades → last 20 trade logs    │   │
│  │ obsidian://memory       → ai_trading_memory.json │   │
│  │ obsidian://rules        → trading_rules.md       │   │
│  └──────────────────────────────────────────────────┘   │
└───────────────┬────────────────────┬────────────────────┘
                │                    │
      ┌─────────▼────┐    ┌──────────▼──────────────────┐
      │ TopStepX API │    │ Obsidian + State Files       │
      │ (execution)  │    │ ai_trading_memory.json        │
      └──────────────┘    │ 12 probability models        │
                          │ trade_history.json           │
                          └─────────────────────────────┘
```

---

## How The LLM Actually Trades (Step by Step)

**Every trading cycle:**

1. LLM calls `get_account_status()` → knows balance, positions, risk budget
2. LLM calls `get_market_snapshot()` → sees all 6 contracts live
3. For top 1-2 candidates, calls `run_probability_models(contract)` → gets all 12 model signals
4. Calls `query_memory("MES trending down, VPIN 0.14, us_close phase")` → obsidian returns similar past trades and outcomes
5. LLM **reasons** using all of: market data + 12 model signals + past memory + philosophy
6. LLM decides: `place_trade("MES", "LONG", size=2, sl_ticks=8, tp_ticks=16, thesis="...")`
7. After outcome: `log_observation("MES LONG at 6420, OFI counter-signal, reversed as expected, +$120...")`

**The thesis logged to obsidian IS the memory that makes the next LLM smarter.**

---

## How Any LLM Connects (One Command)

### Claude Code (me, right now):
```bash
claude mcp add --transport stdio sovereign-trader -- python C:\KAI\sovran_v2\sovran_mcp_server.py
```

That's it. I then have `get_market_snapshot`, `place_trade`, `query_memory` etc. as native tools in my context.

### Claude Desktop:
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "sovereign-trader": {
      "command": "python",
      "args": ["C:\\KAI\\sovran_v2\\sovran_mcp_server.py"]
    }
  }
}
```

### Any other LLM (GPT-4, Gemini, local Ollama, etc.):
Same pattern — MCP is the universal standard. Any LLM with MCP support connects identically.

---

## What Happens to the Current System

| Component | V3 Role |
|-----------|---------|
| `live_session_v5.py` | Fallback mode: runs when no LLM is connected. Calls MCP server internally. |
| `ai_decision_engine.py` | Fallback engine: used when no LLM connected to MCP. |
| `ipc/request_*.json` | Eliminated: MCP tools replace file IPC |
| `ralph_ai_loop.py` | Becomes the fallback orchestrator when LLM offline |
| `sovran_mcp_server.py` | NEW: the bridge between any LLM and the trading system |
| `obsidian/` | Becomes a live, queryable memory system via MCP resources |

**Key principle:** The IPC file system doesn't need to be deleted. The MCP server wraps the same underlying logic. Files are the fallback; MCP is the primary path.

---

## The 12 Probability Models in V3

All 12 models run inside `run_probability_models(contract)`. The LLM receives their outputs as *inputs to its reasoning*, not as hard rules:

| Model | Signal Type | LLM Uses It For |
|-------|-------------|-----------------|
| Kelly Criterion | Optimal bet fraction | Position sizing |
| Fractional Kelly | Conservative sizing | Risk scaling |
| Poker EV Math | Expected value | Trade entry threshold |
| Casino Edge Theory | House advantage | Net edge validation |
| Market Making | Spread capture | Entry/exit timing |
| Statistical Arbitrage | Mean reversion z-score | Regime identification |
| Volatility Model | ATR bands, vol cycles | Stop/target sizing |
| Momentum Model | Trend strength, accel | Direction bias |
| Order Flow (OFI/VPIN) | Institutional flow | Conviction modifier |
| Bayesian Inference | Win rate by condition | Prior probability |
| Monte Carlo | Path simulation | Risk of ruin check |
| Information Theory | Signal entropy | Noise filter |

The LLM reads all 12, weighs them against obsidian memory and current context, and makes its own call. **No model is a gate. All models are evidence.**

---

## Why This Is Superior to Current Architecture

| Feature | Current IPC | V3 MCP |
|---------|-------------|--------|
| Real LLM intelligence | No (Python logic) | Yes (actual LLM reasoning) |
| Obsidian memory at decision time | No | Yes (query_memory tool) |
| Any LLM works | Technically yes, clunky | Yes, one command |
| No API calls needed | Yes | Yes |
| 12 models live | Partially | Fully, as LLM inputs |
| File bloat | 2984 files/day | Zero |
| LLM writes thesis to memory | No | Yes, after every trade |
| Standard protocol | No (custom) | Yes (MCP industry standard) |
| Works when LLM offline | Yes (Python engine) | Yes (fallback mode) |

---

## Implementation Plan

### Phase 1: Build Sovereign MCP Server (Next Session)
**File:** `sovran_v2/sovran_mcp_server.py`

Steps:
1. Install `fastmcp` or `mcp` Python package
2. Implement all 7 tools (get_market_snapshot, run_probability_models, query_memory, place_trade, get_account_status, log_observation, get_trading_rules)
3. Implement 4 resources (philosophy, recent-trades, memory, rules)
4. Test with: `claude mcp add --transport stdio sovereign-trader -- python sovran_mcp_server.py`

**Estimated complexity:** Medium (2-3 hours of LLM work)

### Phase 2: Register in Claude Code Settings
Add to `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "sovereign-trader": {
      "command": "python",
      "args": ["C:\\KAI\\sovran_v2\\sovran_mcp_server.py"],
      "transport": "stdio"
    }
  }
}
```

After this, every Claude Code session has trading tools available. I can trade directly.

### Phase 3: Implement All 12 Models as Python Functions
**File:** `sovran_v2/probability_models.py`

All 12 as clean Python functions returning standardized signal dicts. Called by `run_probability_models()` tool.

### Phase 4: Obsidian Memory Query
**File:** `sovran_v2/obsidian_memory.py`

Full-text search over obsidian markdown files, returning relevant past trade contexts when LLM queries memory.

### Phase 5: Fallback Mode
Update `live_session_v5.py` to call MCP server internally when running in fallback mode (no LLM connected). This way the Python engine ALSO benefits from the 12 models + obsidian context.

---

## The Big Picture: Jesse's Vision Realized

**Before (V2):** Python rules engine pretending to be an AI. Uses some math. Blind to its own history.

**After (V3):** Any LLM connects via one command. Sees live market data. Queries its own trade memory. Weighs 12 probability models with genuine reasoning. Executes trades. Logs thesis. Gets smarter with every trade.

**The LLM IS the trader. The MCP server is the nervous system. Obsidian is the brain.**

When Jesse switches LLMs — the new LLM connects to the same MCP server, reads the same obsidian memory, sees all the same tools. Zero re-briefing needed. The system IS the context.

---

---

## CRITICAL: Don't Build From Scratch — Use These Existing Resources

Research of the obsidian vault revealed these repos were already identified by prior LLMs:

### 1. `phsphd/TopstepX_MCP_Server_Python` — THE FOUNDATION
**This already exists. Clone it, don't build from scratch.**
- Python MCP server for TopstepX
- Already has: account management, contract search, positions, orders, market data
- Uses same credentials (TOPSTEPX_USERNAME, TOPSTEPX_API_KEY)
- Just needs: obsidian memory query, 12 probability models, thesis logging added on top
- [GitHub](https://github.com/phsphd/TopstepX_MCP_Server_Python)

### 2. `project-x-py` (PyPI) — BETTER SDK
- Official/professional Python SDK for ProjectX (TopstepX) gateway
- Replace manual API calls in `projectx_broker_api.py` with this
- `pip install project-x-py`
- [PyPI](https://pypi.org/project/project-x-py/)

### 3. `TauricResearch/TradingAgents` — REASONING PATTERNS
- Already cloned in `armada/research/TradingAgents/`
- Has "Trading-R1" reasoning loop: multi-agent analyst → researcher → risk → trader
- Borrow the structured reasoning pattern for the LLM decision prompt
- [GitHub](https://github.com/TauricResearch/TradingAgents)

### 4. `EthanAlgoX/LLM-TradeBot` — MULTI-LLM INTERFACE PATTERN
- Multi-agent: DataSync, Quant, Decision, Risk agents
- LLM factory: Claude, GPT, Gemini, DeepSeek, Qwen — same interface
- Adversarial decision frameworks (bull vs bear debate before trading)
- [GitHub](https://github.com/EthanAlgoX/LLM-TradeBot)

### 5. `obra/superpowers` — SKILLS FRAMEWORK
- Already referenced in obsidian (Session 2026-03-27 summary)
- Composable skills architecture for Claude Code agents
- Vector-indexed memory for past conversations (matches Jesse's obsidian vision)
- [GitHub](https://github.com/obra/superpowers)

### 6. `Arshad-13/genesis2025` — DEEP OFI SIGNALS
- DeepLOB CNN for OFI microstructure (upgrade from our basic OFI_Z)
- Real-time OFI metrics with institutional-grade signal quality
- [GitHub](https://github.com/Arshad-13/genesis2025)

### From EVOLUTION_ROADMAP.md (already in obsidian vault):
Prior LLMs designed this pattern — reuse it:
- `current_thesis.json` — AI writes its thesis BEFORE trading, persists across cycles
- Temporal Context Buffer (10-min rolling narrative of OFI/VPIN/price)
- WATCH action — LLM can say "I'm watching, re-evaluate in 30s" (patience before trades)
- 5-layer learning flywheel: thesis → trade → reflection → pattern → enrichment

---

## Revised Implementation Plan (Build On What Exists)

### Phase 1: Clone + Extend phsphd/TopstepX_MCP_Server_Python
```bash
git clone https://github.com/phsphd/TopstepX_MCP_Server_Python C:\KAI\sovran_v2\mcp_server
cd C:\KAI\sovran_v2\mcp_server
pip install -r requirements.txt
```
Then add these tools to their server:
- `run_probability_models(contract)` — all 12 models
- `query_obsidian(query)` — memory lookup
- `log_trade_thesis(thesis, conditions, action)` — obsidian write
- `get_temporal_context(contract)` — 10-min rolling narrative buffer

### Phase 2: Wire Credentials
```bash
# C:\KAI\sovran_v2\mcp_server\.env
TOPSTEPX_USERNAME=jessedavidlambert@gmail.com
TOPSTEPX_API_KEY=9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=
```

### Phase 3: Register in Claude Code
```bash
claude mcp add --transport stdio sovereign-trader -- python C:\KAI\sovran_v2\mcp_server\run_server.py
```

### Phase 4: Port 12 Models
Move from `ipc/ai_decision_engine.py` to `probability_models.py` as clean functions. Add 12th model (info theory) if not there.

### Phase 5: Thesis Persistence
Implement `current_thesis.json` pattern from EVOLUTION_ROADMAP. LLM writes its thesis before each trade. Next LLM session reads it and continues from where it left off.

---

## References

- [phsphd/TopstepX_MCP_Server_Python](https://github.com/phsphd/TopstepX_MCP_Server_Python) — **USE THIS AS BASE**
- [phsphd/TopstepX_MCP_Server_Node](https://github.com/phsphd/TopstepX_MCP_Server_Node) — Node.js version
- [mceesincus/tsxapi4py](https://github.com/mceesincus/tsxapi4py) — community Python SDK
- [project-x-py on PyPI](https://pypi.org/project/project-x-py/) — official SDK
- [EthanAlgoX/LLM-TradeBot](https://github.com/EthanAlgoX/LLM-TradeBot) — multi-LLM trading
- [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) — reasoning patterns (already cloned)
- [Arshad-13/genesis2025](https://github.com/Arshad-13/genesis2025) — DeepLOB OFI signals
- [obra/superpowers](https://github.com/obra/superpowers) — skills framework
- [Open-Finance-Lab/AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading) — MCP+A2A agentic trading
- [MCP for Trading (VARRD)](https://www.varrd.com/guides/mcp-trading.html)
- [Building Effective AI Agents (Anthropic)](https://www.anthropic.com/research/building-effective-agents)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25)

---

*Written by Claude Sonnet 4.6, 2026-03-27 ~15:00 CT*
*Updated with obsidian repo research*
*Next LLM: Start with Phase 1 — clone phsphd/TopstepX_MCP_Server_Python and extend it*
