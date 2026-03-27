---
title: How the LLM Actually Trades — The Real Architecture
type: architecture-clarification
updated: 2026-03-27
critical: true
---

# THE HONEST TRUTH: HOW AN LLM ACTUALLY TRADES

## The Confusion

The system currently has `ai_decision_engine.py` running as a Python process.
It looks like "AI trading" but it is NOT an LLM — it's mathematical formulas.
No reasoning. No tokens spent. No intelligence.

For me (Claude, Gemini, GPT, any LLM) to ACTUALLY be the trader, I must be
**actively spending tokens in a turn** to reason about each decision.

---

## Three Ways to Use a Real LLM as the Trader

### MODE 1: Interactive Turn-by-Turn (what works RIGHT NOW)
```
Jesse: "hunt for trades"
Claude: [calls broker API via Bash/Python] → gets live snapshot
        [runs probability models] → reasons about signals
        [decides: LONG MNQ, conviction 78] → places order via API
        [monitors position every 30s] → reports status
        [trade closes] → logs outcome, updates memory
```
**Tokens spent:** ~2,000-5,000 per trade cycle
**How to start:** Just tell me "hunt for trades" or "go trade"
**Limitation:** Requires Claude Code to be open

### MODE 2: Headless Claude via Subprocess (autonomous, scheduled)
```python
# Called from cron every 5 minutes during market hours:
subprocess.run([
    "claude", "-p",
    "Hunt for the best trade across MNQ/MES/MYM/M2K/MGC/MCL. "
    "Check live prices, run probability models, place if conviction >= 65. "
    "Log thesis to obsidian. Report what you did.",
    "--allowedTools", "Bash,Read,Edit",
    "--output-format", "json"
])
```
**Tokens spent:** ~2,000-8,000 per invocation
**Cost:** ~$0.01-0.03/call with Sonnet
**How to setup:** `py scripts/setup_headless_loop.py`

### MODE 3: Anthropic API Inside Python Loop (cheapest at scale)
```python
# In live_session_v5.py, replace IPC file dance with:
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": snapshot_json}],
    system=TRADING_SYSTEM_PROMPT
)
decision = json.loads(response.content[0].text)
```
**Tokens spent:** ~500-1,500 per decision
**Cost:** ~$0.002-0.006/decision
**How to setup:** `py scripts/setup_api_loop.py`

---

## Current System Truth Table

| Component | Is it LLM? | What it actually is |
|-----------|-----------|---------------------|
| ai_decision_engine.py | NO | Python math (Kelly, Bayesian, Z-score) |
| ralph_ai_loop.py | NO | Python orchestrator |
| live_session_v5.py | NO | Python order execution |
| MCP server tools | YES (when LLM calls them) | Bridge for LLM to use in active turn |
| "hunt for trades" via Claude Code | YES | Claude reasoning + Bash execution |
| headless `claude -p "..."` | YES | Claude reasoning non-interactively |
| Anthropic API call | YES | Claude reasoning via HTTP |

---

## The Right Architecture (V4 Target)

```
Every 5 minutes during market hours:
  1. Python collects: price, OFI, VPIN, ATR, regime, balance, open positions
  2. Python runs: all 12 probability models → structured output
  3. LLM receives: snapshot + model outputs + obsidian context (recent trades, thesis)
  4. LLM reasons: which contract, which direction, why, what size
  5. LLM returns: {action, contract, sl_ticks, tp_ticks, reasoning, conviction}
  6. Python validates + executes via broker API
  7. Python monitors + closes position
  8. Python calls LLM again: "trade closed, outcome was X, what did you learn?"
  9. LLM writes lesson to obsidian
  10. Repeat
```

This is the system. MODE 1 (interactive) works today.
MODE 2 and MODE 3 are the next build.

---

## How to Trigger Me Right Now

Just say any of these in Claude Code:
- "hunt for trades"
- "go trade"
- "find me a trade"
- "check the market and trade"

I will:
1. Call broker API to get live snapshots
2. Run probability models in Python
3. Reason about the best setup
4. Place the trade via API
5. Monitor and report

**I use my active turns. Every step is visible. No black box.**

---

*Written: 2026-03-27 by Claude Sonnet 4.6 after being asked the right question*
*"How is it trading using you as an AI if you're not spending tokens in a turn?"*
