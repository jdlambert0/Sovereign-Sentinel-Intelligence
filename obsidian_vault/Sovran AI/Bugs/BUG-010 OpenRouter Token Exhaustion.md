# Bug Report: BUG-010 OpenRouter Token Exhaustion

## Symptom
The AI Decision Loop fails with an `Insufficient Credits` error from OpenRouter, specifically stating: 
"You requested up to 8192 tokens, but can only afford 6897."

## Location
- `C:\KAI\vortex\llm_client.py` (Default `max_tokens` set to 8192)
- `C:\KAI\armada\sovran_ai.py` (Large prompt context from Obsidian)

## Hypothesis
The default `max_tokens` (output limit) is set to 8192, which OpenRouter checks against the available balance at the start of the request. Since the balance is lower than the cost of 8192 tokens + input tokens, the request is rejected immediately.

## Evidence
Log output in `sovran_live_action_v2.log`:
```
2026-03-19 16:04:40,374 [INFO] [sovran_ai] AI Decision: WAIT. Reason: No valid model responsesThis request requires more credits, or fewer max_tokens. You requested up to 8192 tokens, but can only afford 6897.
```

## Context
The system recently added dynamic learning plans and recent trade history to the prompt, increasing input token count. Combined with the high 8192 output cap, the total "potential cost" exceeds the account balance.

## Proposed Fix
1. Set `VORTEX_MAX_TOKENS=1024` in the environment. Trading decisions rarely need more than 100-200 tokens of output (JSON only).
2. Prune the `recent_trades` history to the last 5 instead of 10 if necessary.

## Status
**RESOLVED** (via environment override).
