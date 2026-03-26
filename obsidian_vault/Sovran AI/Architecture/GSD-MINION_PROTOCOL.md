# GSD-Minion Protocol: The Sovereignty Guard

## 1. The Core Mandate
The GSD-Minion is a dedicated sub-agent protocol designed to iron out system bugs, enforce "Broker Truth," and manage AI context to prevent performance degradation over time.

## 2. Operational Invariants

### A. Broker Truth Synchronization (BTS)
- **Mandate**: Never trust local state files (`sovran_ai_state.json`) as the final source of Truth.
- **Action**: On Every system startup and every 6-hour interval, the `GlobalRiskVault` MUST verify the account balance and daily PnL against the TopStepX API (or a manual `trades_export.csv` sync).
- **ZRS Compliance**: Any discrepancy > $1.00 triggers an auto-sync or manual halt until reconciled.

### B. High-Fidelity Research (Lightpanda)
- **Mandate**: All sub-agent research, documentation scraping, and web automation MUST use the **Lightpanda** browser.
- **Rationale**: 10x speed, zero-touch consistency, and machine-native reliability for autonomous agents.

### C. Context Refresh Protocol (CRP)
- **Mandate**: Prevent "vibe coding" and hallucinations caused by bloated conversation context.
- **Action**: When AI context reaches **50% of the maximum limit**, the agent MUST:
  1. Write a comprehensive `Session Log` to the Obsidian vault.
  2. Sync all architectural changes to `GSD-MINION.md`.
  3. Signal the user to start a **Fresh Context Session** using the handoff artifact as the seed.

## 3. The Gemini Brain Expansion

### A. Gambler Strategic Overlay
- The **Gambler Engine** uses Gemini Flash 2.0 to audit mathematical "Ideas" before execution.
- If Gemini conviction is < 0.8, the trade is discarded, regardless of mathematical GCS triggers.

### B. CRO Strategic Veto
- The **GlobalRiskVault** polls Gemini Flash 2.0 every 90 seconds.
- Gemini assesses "Market Regime" (Flash Crashes, News Spikes, Liquidity Gaps).
- Gemini holds the "Kill Switch" for all trading activity if regime stability is < 0.6.

## 4. Revision History
- **2026-03-22**: Initial Protocol instantiation (V1.0).
