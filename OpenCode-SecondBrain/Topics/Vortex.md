---
date: 2026-03-18
topic-id: vortex
tags: [#topic-note]
---

# Vortex Trading System

Vortex is the autonomous AI trading system built around Claude Code. It is the broader system that Sovran runs within, designed to achieve consistent $1k daily profit through a continuous learning loop.

## Core Components

- **Hunter Alpha**: Primary trading agent that places bracket orders via TopStepX API
- **Claude Trader**: LLM-powered decision engine that reads L2 market data
- **Memory System**: Persistent learning via `vortex/memory/` and `vortex/state/`
- **Fleet Manager**: Orchestrates multiple trading engines (Warwick, Chimera)

## Key Files

- `C:\KAI\vortex\ARCHITECTURE.md`
- `C:\KAI\vortex\VERIFICATION_CONTRACT.md`
- `C:\KAI\vortex\REBOOT_PHASE1_LOG.md`
- `C:\KAI\vortex\vortex_simple.py`
- `C:\KAI\vortex\claude_trader.py`
- `C:\KAI\vortex\broker.py`

## Status

**Active development.** Hunter Alpha can place bracket orders. Full learning loop (Stage 4) is the target.

## See Also

- [[Sovran-AI]]
- [[Hunter-Alpha]]
- [[TopStepX]]
