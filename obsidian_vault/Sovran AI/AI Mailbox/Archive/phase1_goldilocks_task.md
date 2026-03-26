# Phase 1: Goldilocks Trading - Research & Execution Task

## Task Overview
Begin your trading education by validating and testing the existing Goldilocks system.

## Background
You have an existing Goldilocks document at: `Session Logs/2026-03-17 Goldilocks Calibration & Current State.md`

This document contains:
- OFI Z-Score threshold: > 1.5
- VPIN threshold: > 0.55
- Combined High-Conviction: OFI_Z > 2.0 AND VPIN > 0.70
- Banned phases: EARLY AFTERNOON (12:30 - 2:00 CT)

## Your Mission

### Step 1: Research (Today)
1. Read the Goldilocks document thoroughly
2. Validate the OFI/VPIN/Z-Score thresholds against the Battle Arena data
3. Note any discrepancies or areas needing adjustment

### Step 2: Execute 10 Trades (This Week)
Using Goldilocks signals ONLY:
- Enter trades when: OFI_Z > 1.5 AND VPIN > 0.55
- High conviction: OFI_Z > 2.0 AND VPIN > 0.70 (prioritize these)
- Use 1 contract MNQ
- $500 max daily loss (hard limit)
- **EXIT EARLY**: Learning mode = close trade after reasonable time (5-15 min) without waiting for SL/TP

### Step 3: Document Each Trade
For EACH trade, create new file in `Trades/` with:
- Entry reasoning (why Goldilocks criteria were met)
- Exit reasoning (why you closed)
- Outcome (P&L, even if $0)
- Lessons learned

**Filename format:** `Trades/YYYY-MM-DD_MNQ_Goldilocks_N.md` where N = trade number

### Step 4: Solve This Open Problem
Research and document your findings on:
> **Optimal Daily Trade Count**
> 
> We fear overtrading erodes gains. Constraints:
> - Max daily loss: $500 (hard)
> - No profit cap
> 
> Consider: Win rate, avg win/loss, Kelly effects, fatigue, session phases.
> 
> Deliverable: Propose a rule for when to stop trading after profits. Document in `Research/Optimal_Trade_Count.md`

## Position Sizing
- Always use current account size
- Risk limit: $500/day max
- 1 contract MNQ = ~$20/tick = ~$200-400/risk

## Important Notes
- **Your decision**: Whether to trade in specific session phases (Goldilocks bans EARLY AFTERNOON, but you decide)
- **Learning mode**: Close trades early to gather more data, don't wait for SL/TP
- **Communication**: Write responses to `AI Mailbox/Outbox/` when tasks complete

## Success Criteria
1. 10 trades executed with Goldilocks criteria
2. Each trade documented in Obsidian
3. Research on optimal trade count delivered
4. Analysis of Goldilocks effectiveness

---

*Backup created: 2026-03-17*
*This is your first learning phase. Good luck!*


---
*Processed: 2026-03-17 12:30:48*