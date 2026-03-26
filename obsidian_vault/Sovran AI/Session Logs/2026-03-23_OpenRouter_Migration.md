# Session log — OpenRouter-only migration (2026-03-23)

## Code

- `C:\KAI\armada\diag_openrouter_ping.py` — one-shot OpenRouter `chat/completions` check (`VORTEX_LLM_MODEL` + `VORTEX_LLM_API_KEY` or `OPENROUTER_API_KEY`).
- `sovran_ai.py` — defaults: `SOVRAN_CONSENSUS_MODELS` or primary+audit OpenRouter slugs; startup prefers **sk-or-** → `openrouter`; Gambler / veto / audit use `audit_model` (no hardcoded Gemini).
- `monitor_sovereign.py` — if `VORTEX_LLM_PROVIDER=openrouter` or **sk-or-** key, health check uses OpenRouter only (no Gemini probe).
- `pending_trade_intent.py` — Path B: JSON → single MNQ bracket (size 1, `--i-understand-live`).
- `armada/.env.example` — template for OpenRouter + TopStepX.

## Verification

- Run `python diag_openrouter_ping.py` after setting `.env` (must show `sk-or-...` key).
- Run `python preflight.py` after code changes (expect ALL CLEAR).

## Note

If no OpenRouter key is present locally, `diag_openrouter_ping` exits non-zero until `VORTEX_LLM_API_KEY` or `OPENROUTER_API_KEY` is set.
