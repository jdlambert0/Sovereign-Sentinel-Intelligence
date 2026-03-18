---
date: 2026-03-18
topic-id: hunter-alpha
tags: [#topic-note]
---

# Hunter Alpha

Hunter Alpha is the primary trading agent in the Vortex/Sovran system. It uses Claude Code to analyze L2 market data and place bracket orders via the TopStepX API.

## Verified Capabilities

- Places market orders with SL/TP brackets via TopStepX atomic bracket API
- **Working tick convention** (verified 2026-03-18):
  - LONG (side=0): SL ticks NEGATIVE, TP ticks POSITIVE
  - SHORT (side=1): SL ticks POSITIVE, TP ticks NEGATIVE
- **Confirmed trade**: Order ID 2661090950, entry $24,629.25, SL $24,579.25, TP $24,654.25

## Key Files

- `C:\KAI\armada\sovran_ai.py` - Main trading engine
- `C:\KAI\armada\test_fixed_bracket.py` - Bracket test script
- `C:\KAI\armada\sovran_hunter_alpha_session.py` - Session runner
- `C:\KAI\obsidian_vault\Sovran AI\Hunter_Alpha/` - Hunter Alpha docs
- `C:\KAI\obsidian_vault\Sovran AI\Hunter_Alpha_Operational_Requirements.md`

## Architecture

Hunter Alpha dispatches trades based on Claude's L2 analysis. The decision loop:
1. Read L2 market data (bid/ask, volume)
2. Claude analyzes and decides direction/sizing
3. Hunter Alpha places bracket order via TopStepX
4. SL/TP managed by broker

## See Also

- [[Sovran-AI]]
- [[Vortex]]
- [[TopStepX]]
