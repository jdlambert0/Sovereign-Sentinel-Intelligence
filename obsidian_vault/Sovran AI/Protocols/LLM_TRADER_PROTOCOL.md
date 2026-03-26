# LLM trader protocol (OpenRouter + Sovran)

**Stack:** `VORTEX_LLM_PROVIDER=openrouter` — verify with `python diag_openrouter_ping.py` from `C:\KAI\armada` (venv Python).

## Before any live action

1. Read latest [[LLM_HANDOFF_LATEST]] and [[Broker_API_Realized_PnL]].
2. Skim relevant notes under `Intelligence/` (sizing, order flow, Kelly, etc.).
3. **Broker truth (not chart UI):** run `python projectx_broker_api.py` from `C:\KAI\armada` and record `recent_fills_preview` + balance.

## Decision artifact

Append a block to `Journal/YYYY-MM-DD_Sovran.md` (create if needed):

- Action (BUY/SELL/WAIT), symbol, size, SL/TP in ticks, confidence, rationale, links to Intelligence notes used.

## Execution paths

| Path | When | How |
|------|------|-----|
| **A (recommended)** | Combine / automation | Run `sovran_ai` via venv + watchdog; LLM updates vault and reviews logs only. |
| **B (manual intent)** | Dev / explicit one-shot | Write `TradingIntents/pending_trade.json`, then `python pending_trade_intent.py --dry-run`, then `--i-understand-live` (MNQ, size 1 only). Appends result under `Journal/YYYY-MM-DD_pending_intent.md`. |
| **C (external stand-in)** | OpenRouter down, ensemble timeout, or empty council | Copy [[TradingIntents/external_decision.EXAMPLE]] to `TradingIntents/external_decision.json`, set `action` / `confidence` / `stop_points` / `target_points` / `expires_at`, set `.env`: `SOVRAN_EXTERNAL_DECISION_ENABLED=1`. Default: `SOVRAN_EXTERNAL_FALLBACK_ONLY=1` (file used **only** when ensemble fails). Pre-ensemble override: `SOVRAN_EXTERNAL_FALLBACK_ONLY=0`. Optional dangerous veto skip: `SOVRAN_EXTERNAL_BYPASS_VETO=1`. Consumed decisions append to `Journal/External_Decisions.md` and archive under `TradingIntents/archive/`. |

### API outage / OpenRouter down (Path C checklist)

1. Confirm `sovran_ai` is running (watchdog stderr shows activity).
2. Run `python projectx_broker_api.py` — broker must still work for **Path A** execution; Path C only replaces the **LLM** decision, not TopStep.
3. Write `external_decision.json` (valid `expires_at` or rely on default TTL from file mtime).
4. Look for log line `[EXTERNAL] Stand-in after` or `[EXTERNAL] Using pre-ensemble` in trading logs.
5. Confirm journal line in [[Journal/External_Decisions]].

## Mailbox (optional)

Human ↔ process messages: `AI Mailbox/Inbox` and `Outbox` (see `sovran_mailbox.py`).

## Honesty

- No guaranteed profit.
- Bracket verification: **API + trade log**, not TopStepX chart UI for API-placed orders.

## Related

- [[PROMPT_NEXT_SESSION_GET_TO_TRADING]]
- `C:\KAI\armada\.env.example`
