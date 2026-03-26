# Hunter Alpha Model Log
**Model**: Gemini 2.0 Flash + Llama 3.3 70B (Ensemble)  
**Purpose**: Sovran AI Trading Decisions  
**Date Created**: 2026-03-17

---

## Model Configuration

```
consensus_models: [
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct"
]
```

---

## Quirks & Observations

### 1. JSON Extraction Issues
**Issue**: Models sometimes output markdown-wrapped JSON or add trailing text.
**Fix Applied**: Robust JSON extraction in `sovran_ai.py` lines 771-785:
```python
# Handles ```json blocks and trailing text
clean_res = clean_res.split("```json")[-1].split("```")[0].strip()
# Finds last complete JSON object
j_start = clean_res.rfind("{")
j_end = clean_res.rfind("}") + 1
```

### 2. Response Format Inconsistency
**Issue**: Models sometimes omit required fields (`action`, `confidence`).
**Behavior**: System defaults to WAIT when fields missing.

### 3. Confidence Scoring
- Gemini tends to be more conservative (lower confidence)
- Llama tends to be more aggressive (higher confidence)
- Ensemble voting: Requires consensus (BUY + SELL = WAIT)

### 4. Timing Sensitivity
**Critical**: These models have ~30 second response time. Market conditions can change during inference.
**Recommendation**: Always check spread/liquidity AFTER getting AI decision but BEFORE executing.

### 5. Prompt Sensitivity
The prompt heavily influences decisions. Key context needed:
- Session phase (morning vs afternoon vs evening)
- Recent PnL and drawdown status
- Spread conditions
- VPIN/order flow signals

### 6. Biases Observed
- Both models倾向 to WAIT in low-volatility conditions
- Both models are skeptical of "MIDDAY CHOP" phase
- Neither model has strong edge in mean-reversion scenarios

---

## Lessons for Future Models

1. **Always validate JSON output** - Don't assume model follows instructions
2. **Check gates AFTER AI decision** - Spread, confidence, drawdown
3. **Ensemble helps** - Single model can get stuck; consensus prevents dumb trades
4. **Prompt is critical** - The system prompt determines 80% of behavior
5. **Log everything** - You need historical data to debug model behavior

---

## Current Status (March 17, 2026)

- Models configured and responding
- Ensemble voting working
- Need more live trade data to assess true performance

---
*Maintained for future AI models debugging Sovran*
