# MARL Gymnasium Study Results (March 20, 2026)

## Overview
A comprehensive 3x3 session study was conducted across all major symbols and trading engines to evaluate AI decision-making consistency during market closure.

### Grid Matrix Results (3 Rounds per Slot)

| Symbol | Sovereign | Gambler | Warwick |
|--------|-----------|---------|---------|
| **MNQ** | 33.3%     | 33.3%   | 33.3%   |
| **MES** | 0.0%      | 0.0%    | 33.3%   |
| **MYM** | 0.0%      | 0.0%    | 33.3%   |

**Note:** The low accuracy scores are anticipated for a 3-round study with low-confidence overrides. The primary goal was **architectural verification** of the 9-engine grid.

## Technical Findings
1. **LLM Concurrency:** Identifying a semaphore bottleneck (limit 2) in `llm_client.py`. Fixed by increasing limit to 20.
2. **JSON Parsing:** Robust regex-based extraction successfully handled verbose LLM responses from Claude 3 Haiku.
3. **Execution Staggering:** Implementing a 2-second jitter between slot initiations prevented API rate-limiting.

## Liquid Intelligence (Scout Agent)
The Scout agent successfully executed a live scan of the CNBC Markets feed.
- **Source:** https://www.cnbc.com/markets/
- **Method:** Playwright (Native Windows)
- **Sentiment Score:** **-0.5 (Bearish)**
- **Audit Reasoning:** "Market headlines indicate concerns about rising interest rates and potential corrections."

## Future Learning Protocol
Weekend learning will now utilize the MARL Gymnasium with the Scout Agent's sentiment as a regime weight.
- **Command:** `C:\KAI\vortex\.venv312\Scripts\python.exe C:\KAI\armada\marl_gymnasium.py`
- **Output:** `C:\KAI\vortex\state\fleet_agents_digest.json`
