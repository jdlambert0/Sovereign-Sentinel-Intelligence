# Trading intents (Path B)

Place `pending_trade.json` here for `C:\KAI\armada\pending_trade_intent.py`.

See [[Protocols/LLM_TRADER_PROTOCOL]].

**Do not commit secrets.** Example shape:

```json
{
  "symbol": "MNQ",
  "side": "LONG",
  "size": 1,
  "sl_ticks": 40,
  "tp_ticks": 20,
  "contract_id": "CON.F.US.MNQ.M26"
}
```
