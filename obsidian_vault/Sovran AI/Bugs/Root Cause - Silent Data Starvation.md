# Root Cause: Silent Data Starvation

## Bug Classification
**Severity:** P0 (System completely non-functional)  
**Type:** Type mismatch / Silent failure  
**Status:** Partially fixed as of 2026-03-16. Needs verification.

---

## The Problem
The Sovran AI trading bot connects to TopStepX, subscribes to market data, and enters its 30-second decision loop. But it **never reaches the AI decision call**. Logs show:
```
Starting AI Decision Loop (interval: 30s)
Starting AI Decision Loop (interval: 30s)
Starting AI Decision Loop (interval: 30s)
```
...repeating forever, with no "Passing context to AI Gambler" message.

## Root Cause Chain

### Level 1: `last_price` stays at 0
The monitor loop has this gate:
```python
if self.last_price <= 0:
    continue  # Silently skip everything
```
Since `last_price` is initialized to `0.0` and never gets set, the loop short-circuits every 30 seconds forever.

### Level 2: `handle_quote` silently fails
The quote handler was written as:
```python
async def handle_quote(self, event):
    data = event.data
    if hasattr(data, 'last_price') and data.last_price:
        self.last_price = data.last_price
```
**But `data` is a `dict`, not an object.** `hasattr(dict_instance, 'last_price')` returns `False` because dicts don't have attributes for their keys. The correct pattern is `data.get('last_price')`.

### Level 3: No error, no crash
The `project_x_py` SDK's `EventBus` catches and logs exceptions from event handlers:
```
Error in event handler handle_quote for quote_update: 'Event' object has no attribute 'get'
```
But this error is logged by the SDK, not by `sovran_ai.py` — so it appears as an SDK warning, not as a trading engine crash. The engine continues running, data never flows in, and the loop silently waits forever.

### Level 4: Why the diagnostic was confusing
When we added `logger.info(f"FIRST QUOTE STRUCTURE: dir={dir(data)}")`, it returned:
```
['__class__', '__class_getitem__', '__contains__', 'copy', 'fromkeys', 'get', 'items', 'keys', ...]
```
This proves `data` is a plain Python `dict`. The presence of `'get'` in `dir()` was the smoking gun.

---

## The Fix
Replace all `hasattr`/`getattr` patterns with `isinstance(data, dict)` checks:

```python
async def handle_quote(self, event):
    data = event.data
    if isinstance(data, dict):
        last_px = data.get('last_price', data.get('price', 0.0))
        self.bid = float(data.get('bid_price', data.get('bid', self.bid)))
        self.ask = float(data.get('ask_price', data.get('ask', self.ask)))
    else:
        # Fallback for object-style data
        last_px = getattr(data, 'last_price', 0.0)
```

## Verification Needed
> [!IMPORTANT]
> The exact **key names** in the dict have not been verified.
> We need to dump raw `event.data` to confirm whether it's:
> - `'last_price'` vs `'price'` vs `'lastPrice'`
> - `'bid_price'` vs `'bid'` vs `'bidPrice'`
> 
> **Action:** Write `test_quote_shape.py` to capture 5 raw events.

---

## Why The Bug Loop Happened
Each fix attempt introduced a new problem because:
1. The text-replace tool sometimes matched wrong sections, creating duplicates
2. No git history meant no safe rollback point
3. Fixes were applied and tested on the live system during market hours
4. No isolated unit test existed for the `handle_quote` data path

## Lessons Learned
1. **Always write a diagnostic script FIRST** — Don't guess the data shape, prove it
2. **Commit before touching production code** — Even a simple `git init && git add . && git commit`
3. **One atomic change per cycle** — Edit one function, run, verify, repeat
4. **The SDK's error log IS your error** — Don't ignore `[project_x_py.event_bus] Error in event handler`

---

## Related Notes
- [[System Architecture]]
- [[2026-03-16 Live Launch Session]]

## Tags
#bug #p0 #root-cause #topstepx #data-starvation
