import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

# --- Exceptions ---

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

# --- Client ---

class BrokerClient:
    """
    Async client for the TopStepX/ProjectX REST API.
    
    This is the single source of truth for all broker communication.
    Every method either succeeds and returns data, or raises a specific exception.
    No silent failures. No local state that shadows broker state.
    """

    def __init__(
        self, 
        username: str, 
        api_key: str, 
        base_url: str = "https://api.topstepx.com",
        account_id: int | None = None,
        token_cache_seconds: float = 120.0,
        max_retries: int = 6,
        base_retry_delay: float = 1.0,
        timeout: float = 20.0
    ):
        self.username = username
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._explicit_account_id = account_id
        self.token_cache_seconds = token_cache_seconds
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.timeout = timeout

        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._account: Optional[Dict[str, Any]] = None
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"}
        )
        self.logger = logging.getLogger("sovran.broker")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    # --- Lifecycle ---

    async def connect(self) -> None:
        """Authenticate and discover the trading account. Must be called before any other method."""
        await self._ensure_authenticated()
        await self.get_account_info()

    async def disconnect(self) -> None:
        """Logout and clean up."""
        if self._token:
            try:
                await self._request("POST", "/api/Auth/logout", auth_required=True)
            except Exception:
                pass
        self._token = None
        self._token_expiry = 0.0
        await self.client.aclose()

    @property
    def token(self) -> str:
        """Current auth token. Raises if not authenticated."""
        if not self._token:
            raise BrokerError("Not authenticated")
        return self._token

    @property
    def account_id(self) -> int:
        """The selected trading account ID. Raises if not connected."""
        if not self._account:
            raise BrokerError("Not connected to an account")
        return self._account["id"]

    @property
    def account_balance(self) -> float:
        """Last known account balance from connect/refresh."""
        if not self._account:
            raise BrokerError("Not connected to an account")
        return float(self._account.get("balance", 0.0))

    # --- Internal Request Handling ---

    async def _ensure_authenticated(self, force: bool = False) -> None:
        """Ensure we have a valid token."""
        now = time.time()
        if not force and self._token and now < self._token_expiry:
            return

        self.logger.info("Authenticating with broker...")
        payload = {"userName": self.username, "apiKey": self.api_key}
        
        # Note: We don't use _request here because it calls _ensure_authenticated
        response = await self.client.post("/api/Auth/loginKey", json=payload)
        data = response.json()

        if not data.get("success"):
            error_code = data.get("errorCode", 8)
            raise AuthenticationError(f"Login failed: {data.get('message', 'Unknown error')}", error_code=error_code)

        self._token = data["token"]
        self._token_expiry = time.time() + self.token_cache_seconds
        self.client.headers["Authorization"] = f"Bearer {self._token}"

    async def _request(self, method: str, endpoint: str, json_data: Any = None, auth_required: bool = True, retry_count: int = 0) -> Dict[str, Any]:
        """Generic request handler with retries and re-auth logic."""
        if auth_required:
            await self._ensure_authenticated()

        try:
            response = await self.client.request(method, endpoint, json=json_data)
            
            if response.status_code == 401 and auth_required:
                self.logger.warning("Received 401, re-authenticating...")
                await self._ensure_authenticated(force=True)
                return await self._request(method, endpoint, json_data, auth_required, retry_count)

            if response.status_code in (429, 503):
                if retry_count < self.max_retries:
                    delay = self.base_retry_delay * (2 ** retry_count)
                    import random
                    delay += random.uniform(0, 0.1 * delay)
                    self.logger.warning(f"Received {response.status_code}, retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                    return await self._request(method, endpoint, json_data, auth_required, retry_count + 1)
                else:
                    raise ConnectionError(f"Max retries reached for {response.status_code}", error_code=response.status_code, endpoint=endpoint)

            response.raise_for_status()
            
            # Special case for ping which returns raw string
            if endpoint == "/api/Status/ping":
                return response.text

            return response.json()

        except httpx.HTTPError as e:
            raise ConnectionError(f"HTTP error: {str(e)}", endpoint=endpoint) from e

    # --- Orders ---

    async def place_market_order(self, contract_id: str, side: str, size: int,
                                  stop_loss_ticks: int | None = None,
                                  take_profit_ticks: int | None = None,
                                  custom_tag: str | None = None) -> int:
        """Place a market order with optional bracket. Returns orderId."""
        return await self._place_order(
            contract_id=contract_id,
            order_type=2, # Market
            side=0 if side.lower() == "buy" else 1,
            size=size,
            stop_loss_ticks=stop_loss_ticks,
            take_profit_ticks=take_profit_ticks,
            custom_tag=custom_tag
        )

    async def place_limit_order(self, contract_id: str, side: str, size: int,
                                 limit_price: float,
                                 stop_loss_ticks: int | None = None,
                                 take_profit_ticks: int | None = None,
                                 custom_tag: str | None = None) -> int:
        """Place a limit order with optional bracket. Returns orderId."""
        return await self._place_order(
            contract_id=contract_id,
            order_type=1, # Limit
            side=0 if side.lower() == "buy" else 1,
            size=size,
            limit_price=limit_price,
            stop_loss_ticks=stop_loss_ticks,
            take_profit_ticks=take_profit_ticks,
            custom_tag=custom_tag
        )

    async def place_stop_order(self, contract_id: str, side: str, size: int,
                                stop_price: float,
                                custom_tag: str | None = None) -> int:
        """Place a stop order. Returns orderId."""
        return await self._place_order(
            contract_id=contract_id,
            order_type=4, # Stop
            side=0 if side.lower() == "buy" else 1,
            size=size,
            stop_price=stop_price,
            custom_tag=custom_tag
        )

    async def _place_order(self, contract_id: str, order_type: int, side: int, size: int,
                            limit_price: float | None = None,
                            stop_price: float | None = None,
                            stop_loss_ticks: int | None = None,
                            take_profit_ticks: int | None = None,
                            custom_tag: str | None = None) -> int:
        payload = {
            "accountId": self.account_id,
            "contractId": contract_id,
            "type": order_type,
            "side": side,
            "size": size,
            "limitPrice": limit_price,
            "stopPrice": stop_price,
            "customTag": custom_tag
        }
        if stop_loss_ticks is not None:
            # TopStepX bracket convention:
            #   BUY (long):  SL ticks must be NEGATIVE (below entry)
            #   SELL (short): SL ticks must be POSITIVE (above entry)
            if side == 0:  # Bid/Buy
                sl_signed = -abs(stop_loss_ticks)
            else:  # Ask/Sell
                sl_signed = abs(stop_loss_ticks)
            payload["stopLossBracket"] = {"ticks": sl_signed, "type": 4}  # Stop
        if take_profit_ticks is not None:
            # TP is the opposite of SL:
            #   BUY (long):  TP ticks must be POSITIVE (above entry)
            #   SELL (short): TP ticks must be NEGATIVE (below entry)
            if side == 0:  # Bid/Buy
                tp_signed = abs(take_profit_ticks)
            else:  # Ask/Sell
                tp_signed = -abs(take_profit_ticks)
            payload["takeProfitBracket"] = {"ticks": tp_signed, "type": 1}  # Limit

        data = await self._request("POST", "/api/Order/place", json_data=payload)
        if not data.get("success"):
            error_code = data.get("errorCode", 7)
            msg = f"Order placement failed: {data.get('message', 'Unknown error')}"
            if error_code == 2: raise OrderRejectedError(msg, error_code, "/api/Order/place")
            if error_code == 3: raise InsufficientFundsError(msg, error_code, "/api/Order/place")
            if error_code == 4: raise AccountViolationError(msg, error_code, "/api/Order/place")
            if error_code == 5: raise OutsideTradingHoursError(msg, error_code, "/api/Order/place")
            raise BrokerError(msg, error_code, "/api/Order/place")
        
        return data["orderId"]

    async def modify_order(self, order_id: int, *,
                            size: int | None = None,
                            limit_price: float | None = None,
                            stop_price: float | None = None,
                            trail_price: float | None = None) -> None:
        """Modify an existing open order. Raises BrokerError on failure."""
        payload = {
            "accountId": self.account_id,
            "orderId": order_id,
            "size": size,
            "limitPrice": limit_price,
            "stopPrice": stop_price,
            "trailPrice": trail_price
        }
        data = await self._request("POST", "/api/Order/modify", json_data=payload)
        if not data.get("success"):
            raise BrokerError(f"Order modification failed: {data.get('message')}", data.get("errorCode"), "/api/Order/modify")

    async def cancel_order(self, order_id: int) -> None:
        """Cancel an order. Raises BrokerError on failure."""
        payload = {"accountId": self.account_id, "orderId": order_id}
        data = await self._request("POST", "/api/Order/cancel", json_data=payload)
        if not data.get("success"):
            raise BrokerError(f"Order cancellation failed: {data.get('message')}", data.get("errorCode"), "/api/Order/cancel")

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open/working orders for the account."""
        payload = {"accountId": self.account_id}
        data = await self._request("POST", "/api/Order/searchOpen", json_data=payload)
        return data.get("orders", [])

    async def search_orders(self, start_time: str, end_time: str | None = None) -> List[Dict[str, Any]]:
        """Search historical orders in a time range."""
        payload = {"accountId": self.account_id, "startTimestamp": start_time}
        if end_time:
            payload["endTimestamp"] = end_time
        data = await self._request("POST", "/api/Order/search", json_data=payload)
        return data.get("orders", [])

    # --- Positions ---

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions from the broker (truth source)."""
        payload = {"accountId": self.account_id}
        data = await self._request("POST", "/api/Position/searchOpen", json_data=payload)
        return data.get("positions", [])

    async def close_position(self, contract_id: str) -> None:
        """Fully close a position for a contract. Raises BrokerError on failure."""
        payload = {"accountId": self.account_id, "contractId": contract_id}
        data = await self._request("POST", "/api/Position/closeContract", json_data=payload)
        if not data.get("success"):
            raise BrokerError(f"Close position failed: {data.get('message')}", data.get("errorCode"), "/api/Position/closeContract")

    async def partial_close_position(self, contract_id: str, size: int) -> None:
        """Partially close a position. Raises BrokerError on failure."""
        payload = {"accountId": self.account_id, "contractId": contract_id, "size": size}
        data = await self._request("POST", "/api/Position/partialCloseContract", json_data=payload)
        if not data.get("success"):
            raise BrokerError(f"Partial close failed: {data.get('message')}", data.get("errorCode"), "/api/Position/partialCloseContract")

    async def flatten_all(self) -> None:
        """Emergency: close ALL positions on ALL contracts. Never fails silently."""
        positions = await self.get_open_positions()
        for pos in positions:
            await self.close_position(pos["contractId"])

    # --- Account & PnL ---

    async def get_account_info(self) -> Dict[str, Any]:
        """Refresh and return account info (balance, name, canTrade, etc.)."""
        payload = {"onlyActiveAccounts": True}
        data = await self._request("POST", "/api/Account/search", json_data=payload)
        accounts = data.get("accounts", [])
        
        if not accounts:
            raise BrokerError("No active accounts found")

        # Selection logic
        selected = None
        if self._explicit_account_id:
            selected = next((a for a in accounts if a["id"] == self._explicit_account_id), None)
            if not selected:
                raise BrokerError(f"Account ID {self._explicit_account_id} not found")
        else:
            # Heuristic
            candidates = [a for a in accounts if a.get("canTrade")]
            if not candidates:
                raise BrokerError("No tradeable accounts found")
            
            # Prefer non-simulated
            real_accounts = [a for a in candidates if not a.get("simulated")]
            target_list = real_accounts if real_accounts else candidates
            
            # Prefer name matching
            matches = [a for a in target_list if any(kw in a["name"].upper() for kw in ["COMBINE", "TOPSTEP"])]
            selected = matches[0] if matches else target_list[0]

        self._account = selected
        return selected

    async def get_realized_pnl(self, session_mode: str = "session") -> float:
        """Get realized PnL for the current trading session.
        
        session_mode: 'session' (17:00 CT to now) or 'calendar' (midnight CT to now)
        
        CME Globex session boundary is 17:00 US/Central (5:00 PM CT).
        If it's before 17:00 CT, the session started at 17:00 CT *yesterday*.
        If it's after 17:00 CT, the session started at 17:00 CT *today*.
        """
        import pytz
        tz_ct = pytz.timezone("US/Central")
        now_ct = datetime.now(tz_ct)
        
        if session_mode == "session":
            # CME session boundary: 17:00 CT
            session_boundary = now_ct.replace(hour=17, minute=0, second=0, microsecond=0)
            if now_ct.hour < 17:
                # Before 5pm CT — session started yesterday at 5pm CT
                session_boundary -= timedelta(days=1)
            start_time = session_boundary.isoformat()
        else:
            # Calendar mode: midnight CT
            start_time = now_ct.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            
        trades = await self.get_trades(start_time)
        realized = sum(float(t.get("profitAndLoss") or 0.0) for t in trades if not t.get("voided"))
        return realized

    async def get_trades(self, start_time: str, end_time: str | None = None) -> List[Dict[str, Any]]:
        """Get half-turn trades in a time range."""
        payload = {"accountId": self.account_id, "startTimestamp": start_time}
        if end_time:
            payload["endTimestamp"] = end_time
        data = await self._request("POST", "/api/Trade/search", json_data=payload)
        return data.get("trades", [])

    # --- Contracts ---

    async def search_contracts(self, search_text: str = "", live: bool = True) -> List[Dict[str, Any]]:
        """Search for contracts by name."""
        payload = {"searchText": search_text, "live": live}
        data = await self._request("POST", "/api/Contract/search", json_data=payload)
        return data.get("contracts", [])

    async def get_contract_by_id(self, contract_id: str) -> Dict[str, Any]:
        """Get a specific contract by ID."""
        payload = {"contractId": contract_id}
        data = await self._request("POST", "/api/Contract/searchById", json_data=payload)
        return data.get("contract", {})

    async def get_available_contracts(self, live: bool = True) -> List[Dict[str, Any]]:
        """List all available contracts."""
        payload = {"live": live}
        data = await self._request("POST", "/api/Contract/available", json_data=payload)
        return data.get("contracts", [])

    # --- Historical Data ---

    async def get_bars(self, contract_id: str, start_time: str, end_time: str,
                        unit: int = 2, unit_number: int = 1, limit: int = 500,
                        include_partial: bool = True) -> List[Dict[str, Any]]:
        """Get historical OHLCV bars.
        
        unit: 1=Second, 2=Minute, 3=Hour, 4=Day, 5=Week, 6=Month
        unit_number: bar size (e.g., unit=2 + unit_number=5 = 5-minute bars)
        """
        payload = {
            "contractId": contract_id,
            "live": True,
            "startTime": start_time,
            "endTime": end_time,
            "unit": unit,
            "unitNumber": unit_number,
            "limit": limit,
            "includePartialBar": include_partial
        }
        data = await self._request("POST", "/api/History/retrieveBars", json_data=payload)
        return data.get("bars", [])

    # --- Health ---

    async def ping(self) -> bool:
        """Check if the API is responsive."""
        try:
            res = await self._request("GET", "/api/Status/ping", auth_required=False)
            return "pong" in res.lower()
        except Exception:
            return False
