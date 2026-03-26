# Bug Log — 2026-03-25 (First Live Attempt)

## Bugs Found and Fixed (Foundation-First)

### Bug 1: WebSocket subscriptions sent too early (Layer 2 - Foundation)
- **Symptom**: WebSocket connects, handshake succeeds, but no quotes/trades arrive
- **Root Cause**: Subscriptions sent immediately after handshake, before server processes it
- **Fix**: Delayed subscriptions by 0.5s in a separate thread (matching v1 working pattern)
- **Layer**: 2 (Market Data Pipeline)
- **File**: `src/market_data.py` lines 428-441

### Bug 2: PnL baseline not captured (Layer 5 - Integration)
- **Symptom**: System immediately halts trading because prior session's -$1,038 PnL exceeds -$450 limit
- **Root Cause**: `get_realized_pnl()` returns total session PnL including v1 trades, not just v2 trades
- **Fix**: Capture baseline PnL at startup, track delta only
- **Layer**: 5 (Sentinel)
- **File**: `src/sentinel.py` line 124

### Bug 3: AsyncMock format string crash (Layer 5 - Test)
- **Symptom**: `f"${value:,.2f}"` crashes when `value` is an AsyncMock in tests
- **Root Cause**: Format string tried to format a mock object
- **Fix**: Cast to `float()` before formatting
- **Layer**: 5 (Sentinel)
- **File**: `src/sentinel.py` line 127

### Bug 4: Partial quote updates have None fields (Layer 2 - Foundation)
- **Symptom**: Quote fields `lastPrice`, `bestBid`, `bestAsk`, `volume` are `None` in partial updates
- **Root Cause**: API sends incremental updates with only changed fields
- **Fix**: Merge with last known quote, preserving unchanged values
- **Layer**: 2 (Market Data Pipeline)
- **File**: `src/market_data.py` lines 493-508

### Bug 5: Contract ID format mismatch (Layer 0/5 - Config)
- **Symptom**: `CON.F.US.MNQM26` returns `result=1` (not found) from subscription
- **Root Cause**: Correct format is `CON.F.US.MNQ.M26` (with dot before month code)
- **Fix**: Updated default contract_id in SentinelConfig
- **Layer**: 5 (Config)
- **File**: `src/sentinel.py` line 57

### Bug 6: Broker token not publicly accessible (Layer 0)
- **Symptom**: Sentinel had to access `broker._token` (private attribute) to pass to MarketDataPipeline
- **Root Cause**: No public property for the auth token
- **Fix**: Added `token` property to BrokerClient
- **Layer**: 0 (Broker)
- **File**: `src/broker.py` line 87

## Resolution Status
All 6 bugs fixed. 120/120 tests passing. WebSocket diagnostic confirmed data flow.

---
#bugs #foundation-first #v2 #live-testing
