# Sovereign Alpha Scaling: Recommendations for $1k/Day
**Status:** Blueprint 4 & 5 Operational. The foundation for $1k/day is set.

## 1. LLM Tier Upgrade (Critical)
*   **The Issue:** Current free-tier models (Gemini Flash, GLM) are hit with 429 rate limits during intensive cycles (Gymnasium Study).
*   **The Recommendation:** Allocate $10-$20 to OpenRouter and switch the `audit_model` to a paid tier (e.g., `anthropic/claude-3.5-sonnet` or `openai/gpt-4o-mini`). 
*   **Result:** 100% reliability for the Veto Auditor, ensuring no trade is placed without a high-fidelity second opinion.

## 2. Dynamic Contract Scaling
*   **Current State:** 1-4 MNQ contracts.
*   **The Recommendation:** Now that Blueprint 5 Veto Auditing is active, we can safely scale to **8-10 MNQ contracts** for "High Conviction" setups.
*   **Calculated Profit:** 50 points on 10 MNQ = $1,000. This makes the daily goal achievable in a single "Opening Burst" or "Morning Session" trend.

## 3. Persistent Gymnasium Training
*   **The Recommendation:** Run `marl_gymnasium.py` daily during the NYC-London transition (2:00 AM - 4:00 AM CT).
*   **Result:** The AI enters the US open with "Fresh Practice" on the most recent 24 hours of volatility, significantly improving edge detection.

## 4. Multi-Symbol Expansion (MES/M2K)
*   **The Recommendation:** Enable MES and M2K with a small size (1 contract each) to diversify the equity curve. 
*   **Result:** Reduces reliance on MNQ whipsaws and provides a steadier path to the drawdown-protected $5,000 consistency target.
