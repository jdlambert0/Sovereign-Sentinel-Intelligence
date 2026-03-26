# Layer 0: Broker Truth — Technical Specification

> **Author**: CIO Agent  
> **Date**: 2026-03-25  
> **For**: Coding Agent  
> **Codebase**: `C:\KAI\sovran_v2\`  
> **Output Files**: `src/broker.py`, `tests/test_broker.py`

---

## 1. Overview

Build a clean, async Python client for the TopStepX/ProjectX REST API. This is Layer 0 — the foundation everything else depends on. It must be **perfect**. No shortcuts, no TODOs, no "we'll fix it later."

The client handles: authentication, account discovery, order placement (with brackets), order modification, order cancellation, position queries, PnL queries, contract lookups, historical bars, and position closing.

## 2. API Reference

**Base URL**: `https://api.topstepx.com`  
**Auth**: POST `/api/Auth/loginKey` with `{ userName, apiKey }` → returns `{ token }` (Bearer)

### 2.1 Authentication

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/Auth/loginKey` | POST | `{ userName: str, apiKey: str }` | `{ success: bool, errorCode: int, token: str }` |
| `/api/Auth/validate` | POST | (none, uses Bearer) | `{ success: bool, errorCode: int, newToken?: str }` |
| `/api/Auth/logout` | POST | (none, uses Bearer) | `{ success: bool, errorCode: int }` |

**Error codes for login**: 0=Success, 1=UserNotFound, 2=PasswordVerificationFailed, 3=InvalidCredentials, 4=AppNotFound, 5=AppVerificationFailed, 6=InvalidDevice, 7=AgreementsNotSigned, 8=UnknownError, 9=ApiSubscriptionNotFound, 10=ApiKeyAuthenticationDisabled

**Token management**:
- Cache the bearer token with a configurable TTL (default 120 seconds)
- On any 401 response from any endpoint, invalidate cache and re-authenticate
- On 429, use exponential backoff with jitter (base 1s, max 6 retries)
- On 503, same backoff behavior

### 2.2 Accounts

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/Account/search` | POST | `{ onlyActiveAccounts: bool }` | `{ success, accounts: [TradingAccountModel] }` |

**TradingAccountModel**: `{ id: int, name: str, balance: decimal, canTrade: bool, isVisible: bool, simulated: bool }`

**Account selection logic**: When multiple accounts exist, select the one that:
1. Has `canTrade = true`
2. Preferably `simulated = false`
3. Name contains "COMBINE" or "TOPSTEP"
4. Can be overridden by explicit account ID

### 2.3 Contracts

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/Contract/search` | POST | `{ searchText?: str, live: bool }` | `{ success, contracts: [ContractModel] }` |
| `/api/Contract/searchById` | POST | `{ contractId: str }` | `{ success, contract: ContractModel }` |
| `/api/Contract/available` | POST | `{ live: bool }` | `{ success, contracts: [ContractModel] }` |

**ContractModel**: `{ id: str, name: str, description: str, tickSize: decimal, tickValue: decimal, activeContract: bool, symbolId: str }`

**Key instruments**:
- MNQ = Micro E-mini Nasdaq, tickSize=0.25, tickValue=$0.50
- NQ = E-mini Nasdaq, tickSize=0.25, tickValue=$5.00
- MES = Micro E-mini S&P 500, tickSize=0.25, tickValue=$1.25
- ES = E-mini S&P 500, tickSize=0.25, tickValue=$12.50

### 2.4 Orders

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/Order/place` | POST | `PlaceOrderRequest` | `{ success, errorCode, orderId: int64 }` |
| `/api/Order/modify` | POST | `ModifyOrderRequest` | `{ success, errorCode }` |
| `/api/Order/cancel` | POST | `{ accountId: int, orderId: int64 }` | `{ success, errorCode }` |
| `/api/Order/search` | POST | `{ accountId: int, startTimestamp: datetime, endTimestamp?: datetime }` | `{ success, orders: [OrderModel] }` |
| `/api/Order/searchOpen` | POST | `{ accountId: int }` | `{ success, orders: [OrderModel] }` |

**PlaceOrderRequest**:
```json
{
  "accountId": 12345,
  "contractId": "CON.F.US.MNQ.M26",
  "type": 2,           // 1=Limit, 2=Market, 3=StopLimit, 4=Stop, 5=TrailingStop, 6=JoinBid, 7=JoinAsk
  "side": 0,           // 0=Bid(Buy), 1=Ask(Sell)
  "size": 1,
  "limitPrice": null,   // Required for Limit/StopLimit
  "stopPrice": null,    // Required for Stop/StopLimit
  "trailPrice": null,   // Required for TrailingStop
  "customTag": "sovran-v2-001",
  "stopLossBracket": { "ticks": 60, "type": 4 },    // Optional: SL as Stop order, 60 ticks = 15 pts MNQ
  "takeProfitBracket": { "ticks": 120, "type": 1 }   // Optional: TP as Limit order, 120 ticks = 30 pts MNQ
}
```

**CRITICAL**: The `stopLossBracket` and `takeProfitBracket` fields use **ticks**, not points. For MNQ with tickSize=0.25, 1 point = 4 ticks. So 15 points = 60 ticks. ALWAYS compute: `ticks = int(points / tickSize)`.

**PlaceOrder error codes**: 0=Success, 1=AccountNotFound, 2=OrderRejected, 3=InsufficientFunds, 4=AccountViolation, 5=OutsideTradingHours, 6=OrderPending, 7=UnknownError, 8=ContractNotFound, 9=ContractNotActive, 10=AccountRejected

**ModifyOrderRequest**:
```json
{
  "accountId": 12345,
  "orderId": 67890,
  "size": null,         // Optional: new size
  "limitPrice": null,   // Optional: new limit price
  "stopPrice": null,    // Optional: new stop price
  "trailPrice": null    // Optional: new trail price
}
```

**OrderModel**: `{ id: int64, accountId: int, contractId: str, symbolId: str, creationTimestamp: datetime, updateTimestamp?: datetime, status: int, type: int, side: int, size: int, limitPrice?: decimal, stopPrice?: decimal, fillVolume: int, filledPrice?: decimal, customTag?: str }`

**OrderStatus**: 0=None, 1=Open, 2=Filled, 3=Cancelled, 4=Expired, 5=Rejected, 6=Pending, 7=PendingCancellation, 8=Suspended
**OrderType**: 0=Unknown, 1=Limit, 2=Market, 3=StopLimit, 4=Stop, 5=TrailingStop, 6=JoinBid, 7=JoinAsk
**OrderSide**: 0=Bid(Buy), 1=Ask(Sell)

### 2.5 Positions

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/Position/searchOpen` | POST | `{ accountId: int }` | `{ success, positions: [PositionModel] }` |
| `/api/Position/closeContract` | POST | `{ accountId: int, contractId: str }` | `{ success, errorCode }` |
| `/api/Position/partialCloseContract` | POST | `{ accountId: int, contractId: str, size: int }` | `{ success, errorCode }` |

**PositionModel**: `{ id: int, accountId: int, contractId: str, contractDisplayName?: str, creationTimestamp: datetime, type: int, size: int, averagePrice: decimal }`

**PositionType**: 0=Undefined, 1=Long, 2=Short

### 2.6 Trades (Half-turns)

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/Trade/search` | POST | `{ accountId: int, startTimestamp?: datetime, endTimestamp?: datetime }` | `{ success, trades: [HalfTradeModel] }` |

**HalfTradeModel**: `{ id: int64, accountId: int, contractId: str, creationTimestamp: datetime, price: decimal, profitAndLoss?: decimal, fees: decimal, side: int, size: int, voided: bool, orderId: int64 }`

PnL is calculated by summing `profitAndLoss` for non-voided trades within a time window. The CME "trading day" starts at 17:00 CT (previous day) and ends at 16:00 CT.

### 2.7 Historical Bars

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/History/retrieveBars` | POST | `RetrieveBarRequest` | `{ success, bars: [AggregateBarModel] }` |

**RetrieveBarRequest**: `{ contractId: str, live: bool, startTime: datetime, endTime: datetime, unit: int, unitNumber: int, limit: int, includePartialBar: bool }`

**AggregateBarUnit**: 0=Unspecified, 1=Second, 2=Minute, 3=Hour, 4=Day, 5=Week, 6=Month
**AggregateBarModel**: `{ t: datetime, o: decimal, h: decimal, l: decimal, c: decimal, v: int64 }`

### 2.8 Status

| Endpoint | Method | Response |
|----------|--------|----------|
| `/api/Status/ping` | GET | `"pong"` (string) |

---

## 3. Class Design

```python
class BrokerClient:
    """
    Async client for the TopStepX/ProjectX REST API.
    
    This is the single source of truth for all broker communication.
    Every method either succeeds and returns data, or raises a specific exception.
    No silent failures. No local state that shadows broker state.
    """
    
    def __init__(self, username: str, api_key: str, 
                 base_url: str = "https://api.topstepx.com",
                 account_id: int | None = None,
                 token_cache_seconds: float = 120.0,
                 max_retries: int = 6,
                 base_retry_delay: float = 1.0):
        ...
    
    # --- Lifecycle ---
    async def connect(self) -> None:
        """Authenticate and discover the trading account. Must be called before any other method."""
    
    async def disconnect(self) -> None:
        """Logout and clean up."""
    
    @property
    def account_id(self) -> int:
        """The selected trading account ID. Raises if not connected."""
    
    @property
    def account_balance(self) -> float:
        """Last known account balance from connect/refresh."""
    
    # --- Orders ---
    async def place_market_order(self, contract_id: str, side: str, size: int,
                                  stop_loss_ticks: int | None = None,
                                  take_profit_ticks: int | None = None,
                                  custom_tag: str | None = None) -> int:
        """Place a market order with optional bracket. Returns orderId.
        
        side: 'buy' or 'sell' (translated to 0/1 internally)
        stop_loss_ticks: SL distance in ticks (placed as Stop order)
        take_profit_ticks: TP distance in ticks (placed as Limit order)
        
        Raises BrokerError on failure with specific error code.
        """
    
    async def place_limit_order(self, contract_id: str, side: str, size: int,
                                 limit_price: float,
                                 stop_loss_ticks: int | None = None,
                                 take_profit_ticks: int | None = None,
                                 custom_tag: str | None = None) -> int:
        """Place a limit order with optional bracket. Returns orderId."""
    
    async def place_stop_order(self, contract_id: str, side: str, size: int,
                                stop_price: float,
                                custom_tag: str | None = None) -> int:
        """Place a stop order. Returns orderId."""

    async def modify_order(self, order_id: int, *,
                           size: int | None = None,
                           limit_price: float | None = None,
                           stop_price: float | None = None,
                           trail_price: float | None = None) -> None:
        """Modify an existing open order. Raises BrokerError on failure."""
    
    async def cancel_order(self, order_id: int) -> None:
        """Cancel an order. Raises BrokerError on failure."""
    
    async def get_open_orders(self) -> list[dict]:
        """Get all open/working orders for the account."""
    
    async def search_orders(self, start_time: str, end_time: str | None = None) -> list[dict]:
        """Search historical orders in a time range."""
    
    # --- Positions ---
    async def get_open_positions(self) -> list[dict]:
        """Get all open positions from the broker (truth source)."""
    
    async def close_position(self, contract_id: str) -> None:
        """Fully close a position for a contract. Raises BrokerError on failure."""
    
    async def partial_close_position(self, contract_id: str, size: int) -> None:
        """Partially close a position. Raises BrokerError on failure."""
    
    async def flatten_all(self) -> None:
        """Emergency: close ALL positions on ALL contracts. Never fails silently."""
    
    # --- Account & PnL ---
    async def get_account_info(self) -> dict:
        """Refresh and return account info (balance, name, canTrade, etc.)."""
    
    async def get_realized_pnl(self, session_mode: str = "session") -> float:
        """Get realized PnL for the current trading session.
        
        session_mode: 'session' (17:00 CT to now) or 'calendar' (midnight CT to now)
        """
    
    async def get_trades(self, start_time: str, end_time: str | None = None) -> list[dict]:
        """Get half-turn trades in a time range."""
    
    # --- Contracts ---
    async def search_contracts(self, search_text: str = "", live: bool = True) -> list[dict]:
        """Search for contracts by name."""
    
    async def get_contract_by_id(self, contract_id: str) -> dict:
        """Get a specific contract by ID."""
    
    async def get_available_contracts(self, live: bool = True) -> list[dict]:
        """List all available contracts."""
    
    # --- Historical Data ---
    async def get_bars(self, contract_id: str, start_time: str, end_time: str,
                       unit: int = 2, unit_number: int = 1, limit: int = 500,
                       include_partial: bool = True) -> list[dict]:
        """Get historical OHLCV bars.
        
        unit: 1=Second, 2=Minute, 3=Hour, 4=Day, 5=Week, 6=Month
        unit_number: bar size (e.g., unit=2 + unit_number=5 = 5-minute bars)
        """
    
    # --- Health ---
    async def ping(self) -> bool:
        """Check if the API is responsive."""
```

## 4. Error Handling

Define a custom exception hierarchy:

```python
class BrokerError(Exception):
    """Base exception for broker operations."""
    def __init__(self, message: str, error_code: int | None = None, endpoint: str = ""):
        self.error_code = error_code
        self.endpoint = endpoint
        super().__init__(message)

class AuthenticationError(BrokerError):
    """Failed to authenticate with the broker."""

class OrderRejectedError(BrokerError):
    """Order was rejected by the broker."""

class InsufficientFundsError(BrokerError):
    """Insufficient funds or margin for the order."""

class AccountViolationError(BrokerError):
    """Account rule violation (e.g., max position size, trading hours)."""

class OutsideTradingHoursError(BrokerError):
    """Market is closed."""

class ConnectionError(BrokerError):
    """Network or connection failure."""
```

**Rules**:
- Every API call that returns `success: false` MUST raise the appropriate exception
- Every network error (timeout, DNS, connection refused) MUST raise `ConnectionError`
- No `except: pass` anywhere — if you catch an exception, handle it specifically or re-raise
- Retry logic: 429 and 503 → exponential backoff with jitter (base 1s, max 6 retries). All other errors → raise immediately.

## 5. Configuration

Create `config/sovran_config.json`:
```json
{
  "broker": {
    "base_url": "https://api.topstepx.com",
    "token_cache_seconds": 120,
    "max_retries": 6,
    "base_retry_delay_seconds": 1.0,
    "http_timeout_seconds": 20
  }
}
```

Create `config/.env`:
```
PROJECT_X_USERNAME=jessedavidlambert@gmail.com
PROJECT_X_API_KEY=/S16+QEnTHSMA2lPuGdEs3ISwrzmuuMqvouqzgT3T8g=
PROJECT_X_ACCOUNT_ID=
```

## 6. Test Requirements

Create `tests/test_broker.py` with:

### Unit Tests (no network, mock httpx responses)
- `test_auth_success` — mock 200 login, verify token cached
- `test_auth_failure` — mock 401 login, verify AuthenticationError raised
- `test_token_cache_hit` — second call within TTL uses cached token
- `test_token_cache_expired` — call after TTL re-authenticates
- `test_401_triggers_reauth` — mock 401 on endpoint → re-auth → retry succeeds
- `test_429_retry_with_backoff` — mock 429 → verify retries with increasing delay
- `test_503_retry_with_backoff` — mock 503 → verify retries
- `test_place_market_order_with_brackets` — verify correct JSON body sent (especially tick calculations)
- `test_place_market_order_error` — mock rejection → verify OrderRejectedError
- `test_modify_order` — verify correct JSON body sent
- `test_cancel_order` — verify correct call
- `test_get_open_positions` — mock response → verify parsed correctly
- `test_close_position` — verify correct call
- `test_flatten_all` — with 2 positions → verify both closed
- `test_get_realized_pnl_session` — mock trades → verify PnL math (sum non-voided)
- `test_get_realized_pnl_calendar` — different time window
- `test_account_selection_by_id` — explicit ID override
- `test_account_selection_heuristic` — canTrade + non-simulated + name matching
- `test_get_bars` — verify correct request body and response parsing

### Integration-Ready Tests (marked with `@pytest.mark.integration`, skipped by default)
- `test_live_ping` — call Status/ping
- `test_live_auth` — authenticate with real credentials
- `test_live_account_discovery` — find the trading account
- `test_live_positions` — query current positions
- `test_live_pnl` — query current PnL and compare mental sanity check

## 7. Dependencies

```
# requirements.txt
httpx>=0.27.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

## 8. Acceptance Criteria (Must ALL Pass)

- [ ] `BrokerClient` authenticates and discovers the account
- [ ] Token caching works (no unnecessary re-auth)
- [ ] 401 → re-auth → retry works transparently
- [ ] 429/503 → exponential backoff works
- [ ] `place_market_order` with brackets sends correct JSON (tick calculation verified)
- [ ] `modify_order` sends correct JSON to the right endpoint
- [ ] `cancel_order` works
- [ ] `get_open_positions` returns parsed PositionModel data
- [ ] `get_open_orders` returns parsed OrderModel data
- [ ] `get_realized_pnl` correctly sums non-voided half-turn trades
- [ ] `close_position` and `flatten_all` work
- [ ] `get_bars` returns parsed OHLCV data
- [ ] Every error condition raises a specific, named exception (never silent)
- [ ] No `except: pass` in the entire file
- [ ] No global mutable state (token cache is instance-level)
- [ ] Every public method has a docstring
- [ ] All unit tests pass
- [ ] Code is under 500 lines (keep it focused)

---

**When done**: Update `Agents/CODING_AGENT.md` with what you built, then the CIO will review.

#specification #layer-0 #broker #coding-agent
