---
date: 2026-03-18
topic-id: topstepx
tags: [#topic-note]
---

# TopStepX

TopStepX is the futures trading broker/platform used by Hunter Alpha for live trading. It provides a REST API for order placement and a WebSocket feed for market data.

## API Details

- **Base URL**: `https://api.topstepx.com/api`
- **Order Placement**: `POST /Order/place` (atomic bracket orders)
- **WebSocket**: Live market data feed

## Verified Working Bracket Order Payload

```python
payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 2,  # Market order
    "side": 0,  # 0=LONG, 1=SHORT
    "size": 1,
    "stopLossBracket": {"ticks": -200, "type": 4},   # NEGATIVE for LONG
    "takeProfitBracket": {"ticks": 100, "type": 1},  # POSITIVE for LONG
}
```

## Tick Convention (Verified)

| Direction | SL Ticks | TP Ticks |
|-----------|----------|----------|
| LONG (side=0) | NEGATIVE | POSITIVE |
| SHORT (side=1) | POSITIVE | NEGATIVE |

## Notes

- TP/SL distance limits may be enforced via Auto-OCO settings (~50% of requested distance applied)
- TopStepX is a simulation platform (not live capital)

## See Also

- [[Hunter-Alpha]]
- [[Sovran-AI]]
- [[Vortex]]
