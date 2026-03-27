---
title: MCP Implementation Plan — Sovereign V3
type: implementation-plan
created: 2026-03-27T15:10:00-05:00
author: Claude Sonnet 4.6
status: IN PROGRESS — pick up from last checked step
priority: P0
---

# MCP Implementation Plan — Sovereign V3
## "Any LLM, One Command, Full Intelligence"

> **IF YOU ARE A NEW LLM PICKING THIS UP:** Find the last `[x]` checkbox, then continue from the next `[ ]`. All context is in this file. Read ARCHITECTURE doc first: `obsidian/SOVEREIGN_ARCHITECTURE_V3_MCP.md`

---

## Current State When Plan Was Written (2026-03-27 ~15:10 CT)

- Trading: ralph (PID 16264) + engine (PID 32392) + V5 session (PID 15488) running
- Live session V5 active, Bayesian memory healthy (50% WR, 32 trades)
- Account balance: ~$149,276
- IPC file system: working but being replaced by MCP
- GitHub: commit `468ad416` is latest

---

## What We're Building

A **Sovereign MCP Server** (`sovran_v2/mcp_server/`) that:
1. Wraps the TopstepX API (clone from phsphd's existing server)
2. Exposes all 12 probability models as tool inputs for the LLM
3. Queries obsidian memory at decision time
4. Logs the LLM's trade thesis back to obsidian after each decision
5. Persists the LLM's current thesis in `state/current_thesis.json` across sessions

Any LLM connects with one command. The IPC file system runs as fallback when no LLM is connected.

---

## Step-by-Step Checklist

### PHASE 0: Prep
- [x] Kill zombie autonomous_responder.py processes
- [x] Confirm clean process state: ralph + engine + V5 only
- [x] Architecture doc written: `obsidian/SOVEREIGN_ARCHITECTURE_V3_MCP.md`
- [x] This plan written: `obsidian/MCP_IMPLEMENTATION_PLAN.md`

### PHASE 1: Clone Base MCP Server
- [ ] **1.1** Clone phsphd's server into sovran_v2:
  ```bash
  cd C:\KAI\sovran_v2
  git clone https://github.com/phsphd/TopstepX_MCP_Server_Python mcp_server
  ```
- [ ] **1.2** Read the cloned server's README and list what tools it already has
- [ ] **1.3** Install dependencies:
  ```bash
  cd C:\KAI\sovran_v2\mcp_server
  pip install -r requirements.txt
  # also install: pip install mcp fastmcp
  ```
- [ ] **1.4** Create `.env` in mcp_server/:
  ```
  TOPSTEPX_USERNAME=jessedavidlambert@gmail.com
  TOPSTEPX_API_KEY=9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=
  TOPSTEPX_ENVIRONMENT=live
  OBSIDIAN_PATH=C:\KAI\sovran_v2\obsidian
  STATE_PATH=C:\KAI\sovran_v2\state
  ```
  **NEVER commit this file — it has credentials**
- [ ] **1.5** Test the base server starts:
  ```bash
  cd C:\KAI\sovran_v2\mcp_server
  python run_server.py
  # Should print: MCP server running on stdio
  ```

### PHASE 2: Build probability_models.py
**File:** `C:\KAI\sovran_v2\probability_models.py`

All 12 models as Python functions. Each returns a dict with `signal`, `conviction`, `reasoning`.

- [ ] **2.1** Create `probability_models.py` with these 12 functions:

```python
# Template for each model:
def model_kelly(price, atr, account_balance, recent_win_rate, recent_avg_win, recent_avg_loss):
    """Kelly Criterion — optimal bet fraction"""
    # kelly_f = (win_rate * avg_win - loss_rate * avg_loss) / avg_win
    # Returns: {"signal": "LONG"/"SHORT"/"NEUTRAL", "conviction": 0-100, "reasoning": str, "kelly_fraction": float}

def model_poker_ev(price, ofi_z, vpin, atr):
    """Poker EV Math — pot odds analog"""
    # EV = P(win) * avg_win - P(loss) * avg_loss
    # Returns: {"signal", "conviction", "reasoning", "ev": float}

def model_casino_edge(win_rate_history, avg_rr):
    """Casino Edge Theory — house edge analog"""
    # edge = win_rate * avg_rr - (1 - win_rate)
    # Returns: {"signal", "conviction", "reasoning", "edge": float}

def model_market_making(spread_ticks, atr_ticks, volume_ratio):
    """Market Making — spread capture opportunity"""
    # When spread > 2x normal and volume low = mean reversion signal
    # Returns: {"signal", "conviction", "reasoning"}

def model_statistical_arb(price, vwap, vwap_pct, atr_ticks):
    """Statistical Arbitrage — mean reversion z-score"""
    # z = (price - vwap) / (atr * 0.5)
    # Returns: {"signal", "conviction", "reasoning", "z_score": float}

def model_volatility(atr_ticks, atr_percentile, regime):
    """Volatility Model — ATR bands, vol cycles"""
    # High vol = wider stops, bigger targets
    # Low vol = tighter stops, smaller targets, higher size
    # Returns: {"signal", "conviction", "reasoning", "vol_regime": str, "size_multiplier": float}

def model_momentum(ofi_z, price_accel, volume_ratio, bars_trend):
    """Momentum Model — trend strength"""
    # Strong trend: |ofi_z| > 1.5 AND accel in same direction
    # Returns: {"signal", "conviction", "reasoning", "trend_strength": float}

def model_order_flow(ofi_z, vpin, buy_vol, sell_vol):
    """Order Flow — institutional flow (OFI/VPIN)"""
    # Primary signal already in system, but score it explicitly
    # Returns: {"signal", "conviction", "reasoning", "flow_imbalance": float}

def model_bayesian(contract, session_phase, regime, memory_file):
    """Bayesian Inference — historical win rate by condition"""
    # Load ai_trading_memory.json, find matching conditions, return posterior
    # Returns: {"signal", "conviction", "reasoning", "posterior_win_rate": float}

def model_monte_carlo(account_balance, win_rate, avg_win, avg_loss, n_paths=1000):
    """Monte Carlo — path simulation, risk of ruin check"""
    # Run 1000 paths, return P(ruin), P(target), expected_value
    # Returns: {"signal", "conviction", "reasoning", "p_ruin": float, "p_target": float}

def model_information_theory(ofi_z, vpin, price_accel, regime):
    """Information Theory — Shannon entropy, signal vs noise"""
    # Low entropy (predictable) = high conviction trade
    # High entropy (chaotic) = reduce conviction
    # Returns: {"signal", "conviction", "reasoning", "entropy": float, "signal_quality": float}

def model_risk_of_ruin(account_balance, proposed_risk_dollars, win_rate, avg_rr):
    """Risk of Ruin — never exceed 5% P(ruin)"""
    # Classic RoR formula
    # Returns: {"signal": "PROCEED"/"REDUCE"/"ABORT", "conviction", "reasoning", "ror": float}

def run_all_models(snapshot: dict, memory_file: str) -> dict:
    """Run all 12 models, return unified signal dict for LLM"""
    # snapshot: {contract, price, ofi_z, vpin, atr_ticks, regime, session_phase,
    #             account_balance, buy_vol, sell_vol, price_accel, vwap_pct, spread_ticks}
    # Returns all 12 model results + consensus summary
```

- [ ] **2.2** Implement each function with real math (not stubs)
- [ ] **2.3** Test: `python probability_models.py` should print sample output for MNQ

### PHASE 3: Build obsidian_memory.py
**File:** `C:\KAI\sovran_v2\obsidian_memory.py`

- [ ] **3.1** Create `obsidian_memory.py`:

```python
import os, re, json
from pathlib import Path
from datetime import datetime

OBSIDIAN_PATH = Path(r"C:\KAI\sovran_v2\obsidian")
STATE_PATH = Path(r"C:\KAI\sovran_v2\state")
THESIS_FILE = STATE_PATH / "current_thesis.json"

def query_memory(query: str, max_results: int = 5) -> str:
    """
    Search obsidian for relevant past trade context.
    Returns formatted string of matching snippets.
    query: natural language description of current conditions
    e.g. "MES trending down, us_close phase, VPIN low"
    """
    # Simple keyword search across all .md files
    # Returns up to max_results relevant passages
    ...

def log_trade_thesis(contract: str, action: str, thesis: str,
                     conditions: dict, models_summary: dict) -> str:
    """
    Write the LLM's trade reasoning to obsidian.
    Called BEFORE placing trade so reasoning is preserved.
    Returns path to created file.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OBSIDIAN_PATH / f"trade_thesis_{ts}_{contract}_{action}.md"
    ...

def log_trade_outcome(thesis_file: str, outcome: str,
                      pnl: float, lesson: str) -> None:
    """
    Update thesis file with actual outcome after trade closes.
    Called by live_session_v5.py via record_trade_outcome.py
    """
    ...

def get_current_thesis() -> dict:
    """Load persisted thesis from previous LLM session."""
    if THESIS_FILE.exists():
        return json.loads(THESIS_FILE.read_text())
    return {}

def save_current_thesis(thesis: dict) -> None:
    """Persist current LLM thesis across sessions."""
    THESIS_FILE.write_text(json.dumps(thesis, indent=2))

def get_recent_trades(n: int = 10) -> str:
    """Return last N trade theses as formatted string for LLM context."""
    ...

def get_philosophy() -> str:
    """Return Jesse's trading philosophy for LLM context."""
    phil_file = OBSIDIAN_PATH / "ai_trading_philosophy.md"
    if phil_file.exists():
        return phil_file.read_text(encoding='utf-8')[:3000]  # first 3000 chars
    return ""
```

- [ ] **3.2** Implement query_memory with keyword search
- [ ] **3.3** Implement log_trade_thesis with proper markdown formatting
- [ ] **3.4** Implement log_trade_outcome
- [ ] **3.5** Implement get_recent_trades
- [ ] **3.6** Test all functions

### PHASE 4: Extend MCP Server with Sovereign Tools
**File:** `C:\KAI\sovran_v2\mcp_server\sovereign_tools.py` (new file added to cloned server)

- [ ] **4.1** Study the cloned server's tool registration pattern
- [ ] **4.2** Create `sovereign_tools.py` that adds these tools:

```python
# Tools to add to the MCP server:

@mcp.tool()
def run_probability_models(contract: str) -> dict:
    """
    Run all 12 probability models on current market data for a contract.
    Returns unified signal dict. LLM uses this as evidence, not as a rule.
    """
    snapshot = get_live_snapshot(contract)  # from base server
    from probability_models import run_all_models
    return run_all_models(snapshot, STATE_PATH / "ai_trading_memory.json")

@mcp.tool()
def query_memory(query: str) -> str:
    """
    Search obsidian memory for past trades matching current conditions.
    query: describe current market conditions in plain English
    Returns: relevant past trade outcomes and lessons
    """
    from obsidian_memory import query_memory as _query
    return _query(query)

@mcp.tool()
def log_trade_thesis(contract: str, action: str, thesis: str,
                     sl_ticks: int, tp_ticks: int) -> str:
    """
    Log your trade reasoning to obsidian BEFORE executing.
    This is how the system remembers what you were thinking.
    Returns: path to created thesis file
    """
    from obsidian_memory import log_trade_thesis as _log, save_current_thesis
    save_current_thesis({"contract": contract, "action": action,
                          "thesis": thesis, "timestamp": datetime.now().isoformat()})
    return _log(contract, action, thesis, {}, {})

@mcp.tool()
def get_trading_context() -> dict:
    """
    Get full trading context: philosophy, recent trades, current thesis.
    Call this at the start of each trading cycle.
    Returns: {philosophy, recent_trades, current_thesis, account_status}
    """
    from obsidian_memory import get_philosophy, get_recent_trades, get_current_thesis
    return {
        "philosophy": get_philosophy(),
        "recent_trades": get_recent_trades(10),
        "current_thesis": get_current_thesis(),
    }
```

- [ ] **4.3** Register `sovereign_tools.py` in the MCP server's main entry point
- [ ] **4.4** Verify all tools appear when MCP server starts

### PHASE 5: Register in Claude Code

- [ ] **5.1** Add to `~/.claude/settings.json`:
  ```json
  {
    "permissions": {"defaultMode": "bypassPermissions"},
    "mcpServers": {
      "sovereign-trader": {
        "command": "python",
        "args": ["C:\\KAI\\sovran_v2\\mcp_server\\run_server.py"],
        "transport": "stdio",
        "env": {
          "TOPSTEPX_USERNAME": "jessedavidlambert@gmail.com",
          "TOPSTEPX_API_KEY": "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=",
          "TOPSTEPX_ENVIRONMENT": "live"
        }
      }
    }
  }
  ```
  Note: credentials in settings.json are stored locally only, never pushed to GitHub.

- [ ] **5.2** Restart Claude Code (or run `claude mcp add` command)
- [ ] **5.3** Verify: type `/mcp` in Claude Code — should see `sovereign-trader` listed

### PHASE 6: Test End-to-End

- [ ] **6.1** Call `get_trading_context()` — verify philosophy + recent trades load
- [ ] **6.2** Call `get_market_snapshot()` (from base server) — verify live prices
- [ ] **6.3** Call `run_probability_models("CON.F.US.MNQ.M26")` — verify all 12 models return
- [ ] **6.4** Call `query_memory("MNQ trending up with momentum")` — verify obsidian search works
- [ ] **6.5** Call `log_trade_thesis(...)` — verify file created in obsidian
- [ ] **6.6** Call `place_trade(...)` (from base server) — verify TopStepX execution

### PHASE 7: Clean Up IPC (Optional — after MCP proven stable)

- [ ] **7.1** Update `live_session_v5.py` to check if MCP server is running; if yes, skip IPC
- [ ] **7.2** Keep `ai_decision_engine.py` as fallback engine (when no LLM connected)
- [ ] **7.3** Update `ralph_ai_loop.py` to launch MCP server on startup

### PHASE 8: Commit & Sync

- [ ] **8.1** Commit all new files (mcp_server/, probability_models.py, obsidian_memory.py)
- [ ] **8.2** Update obsidian: SESSION_HANDOFF_CURRENT.md + LLM_HANDOFF_KIT.md
- [ ] **8.3** Push to GitHub: `cd C:\KAI && git push origin genspace:main --no-verify`

---

## Files Being Created

| File | Purpose | Status |
|------|---------|--------|
| `mcp_server/` | Cloned + extended MCP server | TODO |
| `probability_models.py` | All 12 models as Python functions | TODO |
| `obsidian_memory.py` | Obsidian query/write module | TODO |
| `mcp_server/sovereign_tools.py` | Adds Sovereign tools to MCP server | TODO |
| `state/current_thesis.json` | LLM thesis persistence | TODO |
| `~/.claude/settings.json` | MCP registration | TODO |

---

## Key Decisions Made

1. **Don't build MCP from scratch** — clone `phsphd/TopstepX_MCP_Server_Python`
2. **IPC files stay as fallback** — MCP is primary when LLM connected
3. **Credentials in settings.json env** — not in codebase, not on GitHub
4. **12 models are LLM inputs** — not rules, not gates, not vote counters. The LLM reads all 12 and reasons intelligently
5. **Thesis first, trade second** — LLM calls `log_trade_thesis()` BEFORE `place_trade()`
6. **Obsidian is the brain** — every decision reads memory, every outcome writes to it

---

## How The Next LLM Picks This Up

1. Read `obsidian/LLM_HANDOFF_KIT.md` (system overview)
2. Read this file (`obsidian/MCP_IMPLEMENTATION_PLAN.md`) — find last `[x]`
3. Continue from next `[ ]` step
4. Mark each step `[x]` as you complete it
5. Update "Current LLM Progress" section below
6. Commit after every phase

---

## Current LLM Progress Log

### Claude Sonnet 4.6 (2026-03-27 ~15:10 CT)
- Wrote architecture doc: `SOVEREIGN_ARCHITECTURE_V3_MCP.md`
- Wrote this plan: `MCP_IMPLEMENTATION_PLAN.md`
- Killed zombie process PID 25928
- Confirmed clean process state: ralph + engine + V5
- Starting Phase 1: clone base MCP server
- **STOPPED AT:** Beginning Phase 1.1

---

## Emergency Context (if you're lost)

- Jesse's goal: any LLM connects with one command and trades intelligently using all 12 models + obsidian memory
- Current trading: V5 session running (PID 15488), ralph orchestrating (PID 16264)
- Don't touch the trading session — it's running fine
- The MCP server is NEW work alongside the existing system
- Credentials: `C:\KAI\sovran_v2_secrets\credentials.env` (NEVER push to GitHub)
- GitHub push: `cd C:\KAI && git push origin genspace:main --no-verify`
