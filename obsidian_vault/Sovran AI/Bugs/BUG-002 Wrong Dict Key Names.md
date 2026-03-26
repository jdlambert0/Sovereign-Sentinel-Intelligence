# BUG-002: Wrong Dict Key Names in handle_quote/handle_trade

## Status: ✅ RESOLVED
**Date:** 2026-03-16  
**Severity:** P0 (System completely non-functional)  
**Resolution Date:** 2026-03-16 09:06 CT

---

## Symptom
Bot connects, receives market data, but `last_price` stays at 0.0 forever. Monitor loop silently skips all AI logic.

## Location
- `C:\KAI\armada\sovran_ai.py`, lines 308-340
- Functions: `handle_quote()`, `handle_trade()`

## Evidence (PROVEN via test_quote_shape.py)
The diagnostic dump at `C:\KAI\armada\_logs\quote_shape_dump.txt` proves:

```
type(event)       = <class 'project_x_py.event_bus.Event'>
type(event.data)  = <class 'dict'>
Keys: ['bid', 'ask', 'last', 'volume', 'symbol', 'timestamp']

  [bid]       = 24735.25  (float)
  [ask]       = 24736.0   (float)
  [last]      = 24735.75  (float)  ← CAN BE None!
  [volume]    = 466121    (int)
  [symbol]    = 'F.US.MNQ' (str)
  [timestamp] = datetime   (datetime with CDT tzinfo)
```

## Root Cause
The code used wrong key names: `last_price`, `bid_price`, `ask_price`, `bid_size`, `ask_size`. The actual keys are `last`, `bid`, `ask`. There is no `bid_size` or `ask_size`.

Additionally, `last` can be `None` when no recent trade has occurred, which requires a None guard before comparison.

## Fix Applied
```python
async def handle_quote(self, event):
    data = event.data  # Always a dict
    last = data.get('last')
    if last is not None and last > 0:
        self.last_price = float(last)
    bid = data.get('bid', 0)
    ask = data.get('ask', 0)
    if bid and bid > 0: self.bid = float(bid)
    if ask and ask > 0: self.ask = float(ask)
    if self.last_price <= 0 and self.bid > 0 and self.ask > 0:
        self.last_price = round((self.bid + self.ask) / 2.0, 2)
    self.book_pressure = 0.5  # No size data in feed
```

## Verification
```
09:05:38 [INFO] Starting AI Decision Loop (interval: 30s)
09:06:08 [INFO] 🧠 Passing context to AI Gambler...
09:06:24 [INFO] Council Voting: BUY=0, SELL=0, WAIT=2 over 2 models
```
WAIT is correct for Sunday thin market — full pipeline works end-to-end.

---

## Tags
#bug #p0 #resolved #handle-quote #data-shape
