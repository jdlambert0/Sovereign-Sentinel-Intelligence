---
title: SESSION HANDOFF — CURRENT STATE (Always Up To Date)
type: session-handoff
updated: 2026-03-27T17:00:00-05:00
next_priority: MCP server is BUILT and REGISTERED — next LLM just needs to open /mcp in Claude Code and start trading
---

# SESSION HANDOFF — READ THIS FIRST

**Canonical handoff. Read this + LLM_HANDOFF_KIT.md to get fully up to speed.**

---

## SYSTEM STATUS: MCP SERVER BUILT — READY TO TRADE

The Sovereign Sentinel MCP Server is **complete and registered** in Claude Code settings.
Any LLM can now connect with zero setup and trade intelligently.

---

## WHAT THIS LLM SESSION DID (Claude Sonnet 4.6, 2026-03-27 ~14:30-17:00 CT)

1. Built `mcp_server/probability_models.py` — all 12 probability models LIVE
2. Built `mcp_server/obsidian_memory.py` — full obsidian read/write layer
3. Built `mcp_server/run_server.py` — Sovereign MCP Server with 9 tools
4. Registered MCP server in `~/.claude/settings.json` (with credentials in env)
5. Ran integration tests — all tools passing
6. Updated obsidian handoff

---

## MCP SERVER — HOW TO USE IT

### Connect from Claude Code
```
/mcp
```
Look for "sovereign-sentinel" server. All tools will appear.

### Tools Available
| Tool | Purpose |
|------|---------|
| `get_market_snapshot` | Get live market state (reads IPC files or simulates) |
| `run_probability_models` | Run all 12 models on a contract |
| `query_memory` | Read obsidian (philosophy/trades/thesis/rules/performance) |
| `place_trade` | Execute a trade via TopStepX API |
| `get_account_status` | Balance, positions, PnL |
| `log_trade_thesis` | Record reasoning BEFORE trade |
| `log_trade_outcome` | Record result AFTER trade |
| `save_thesis` | Persist market thesis across sessions |
| `write_observation` | Log market observation to obsidian |

### Server Location
```
C:\KAI\sovran_v2\mcp_server\
  run_server.py        <- entry point
  probability_models.py  <- all 12 models
  obsidian_memory.py   <- obsidian read/write
  __init__.py
```

### Manual Start (if needed)
```bash
py -3.12 C:\KAI\sovran_v2\mcp_server\run_server.py
```

---

## HOW TO TRADE AS THE AI

1. **Start session**: `query_memory("thesis")` — see what previous LLM believed
2. **Assess market**: `get_market_snapshot("all")` — see all 6 contracts
3. **Run models**: `run_probability_models(contract_id, snapshot)` — get 12-model consensus
4. **Log thesis**: `log_trade_thesis(...)` — record reasoning BEFORE trading
5. **Trade**: `place_trade(action, contract_id, sl_ticks, tp_ticks, reasoning, conviction)`
6. **Monitor & log**: `log_trade_outcome(...)` when trade closes
7. **Update thesis**: `save_thesis(...)` at end of session for next LLM

---

## TRADING STATE

| Item | Status |
|------|--------|
| Account balance | ~$149,276 |
| Bayesian memory | 3400+ trades (full backfill) |
| Best performers | MES 71% WR, MNQ 67% WR |
| Avoid | M2K (27% WR) |
| Boost | MGC, MCL (+10% conviction) |
| IPC files | Still work — V5 session still uses them |

---

## CURRENT TRADING PROCESSES

Check if V5 is running:
```bash
py -c "import subprocess; r=subprocess.run(['powershell','Get-Process python'],capture_output=True,text=True); print(r.stdout)"
```

Start V5 session if not running:
```bash
py C:\KAI\sovran_v2\ralph_ai_loop.py --max-iterations 20
```

---

## GITHUB STATE

- **Repo:** https://github.com/jdlambert0/Sovereign-Sentinel-Intelligence
- **Branch:** genspace → main
- **Push:** `cd C:\KAI && git push origin genspace:main --no-verify`

---

## NEXT PRIORITIES

1. **IMMEDIATE**: Connect MCP in Claude Code via `/mcp` — confirm tools appear
2. **TRADE**: Use MCP tools to actively trade — you are the AI trader
3. **Validate partial TP**: check `state/trade_history.json` for `partial_taken: true`
4. **Regime-specific TP**: after 20+ trades — tune per regime

---

*Updated: 2026-03-27 ~17:00 CT by Claude Sonnet 4.6*
*Previous: Claude Sonnet 4.6 at 14:20 CT*
