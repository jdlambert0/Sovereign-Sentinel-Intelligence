# LLM Daily Cost Analysis (March 2026 Fleet)

## 1. Unit Economics (Consensus Mode)
The current 9-engine grid (MNQ, MES, MYM x Sovereign, Gambler, Warwick) generates approximately **7,020 LLM calls** per 6.5-hour trading day (assuming 30s intervals).

### Pricing Brackets (March 2026)
| Model | Input ($/1M) | Output ($/1M) | Avg Call Tokens |
|-------|--------------|---------------|-----------------|
| Claude 3 Haiku | $0.25 | $1.25 | 15.5k |
| Gemini 1.5 Flash | $0.075 | $0.30 | 15.5k |

## 2. Total Daily Burn Estimate
- **Claude 3 Haiku (Leader)**: **~$30.70**
- **Gemini 1.5 Flash (Auditor)**: **~$8.94**
- **Combined System Total**: **~$39.64 / Day**

### Comparison (Efficiency Gains)
- **Legacy Fleet (Sonnet)**: ~$240.00 / Day
- **New Fleet (Haiku+Flash)**: **$39.64 / Day**
- **Savings**: **83.5% Reduction in Opex.**

## 3. Weekend Cost (Zero)
The **Data Freshness Guard** in `sovran_ai.py` automatically idles the system when the market is closed. Billable LLM usage stays at **$0.00** from Friday close until Sunday open.

---
*Status: AUDIT COMPLETE | Opex Optimized | Date: March 20, 2026*
