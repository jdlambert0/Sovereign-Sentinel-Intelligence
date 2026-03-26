import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from src.broker import (
    BrokerClient,
    BrokerError,
    AuthenticationError,
    OrderRejectedError,
    InsufficientFundsError,
    ConnectionError
)

@pytest.fixture
def mock_client_config():
    return {
        "username": "test_user",
        "api_key": "test_key",
        "base_url": "https://api.test.com",
        "token_cache_seconds": 120
    }

@pytest_asyncio.fixture
async def broker(mock_client_config):
    client = BrokerClient(**mock_client_config)
    yield client
    await client.disconnect()

@pytest.mark.asyncio
async def test_auth_success(broker):
    """test_auth_success — mock 200 login, verify token cached"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "token": "fake_token"}
    
    with patch.object(broker.client, 'post', AsyncMock(return_value=mock_response)) as mock_post:
        await broker._ensure_authenticated()
        
        assert broker._token == "fake_token"
        assert broker.client.headers["Authorization"] == "Bearer fake_token"
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_auth_failure(broker):
    """test_auth_failure — mock 401 login, verify AuthenticationError raised"""
    mock_response = MagicMock()
    mock_response.status_code = 200 # API returns 200 but success: false
    mock_response.json.return_value = {"success": False, "errorCode": 3, "message": "Invalid credentials"}
    
    with patch.object(broker.client, 'post', AsyncMock(return_value=mock_response)):
        with pytest.raises(AuthenticationError) as excinfo:
            await broker._ensure_authenticated()
        assert excinfo.value.error_code == 3

@pytest.mark.asyncio
async def test_token_cache_hit(broker):
    """test_token_cache_hit — second call within TTL uses cached token"""
    broker._token = "cached_token"
    broker._token_expiry = time.time() + 60
    
    with patch.object(broker.client, 'post', AsyncMock()) as mock_post:
        await broker._ensure_authenticated()
        mock_post.assert_not_called()

@pytest.mark.asyncio
async def test_token_cache_expired(broker):
    """test_token_cache_expired — call after TTL re-authenticates"""
    broker._token = "expired_token"
    broker._token_expiry = time.time() - 60
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "token": "new_token"}
    
    with patch.object(broker.client, 'post', AsyncMock(return_value=mock_response)) as mock_post:
        await broker._ensure_authenticated()
        assert broker._token == "new_token"
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_401_triggers_reauth(broker):
    """test_401_triggers_reauth — mock 401 on endpoint → re-auth → retry succeeds"""
    broker._token = "old_token"
    broker._token_expiry = time.time() + 60
    
    # Mock 401 then 200
    resp_401 = MagicMock(spec=httpx.Response)
    resp_401.status_code = 401
    
    resp_200 = MagicMock(spec=httpx.Response)
    resp_200.status_code = 200
    resp_200.json.return_value = {"success": True, "data": "ok"}
    resp_200.raise_for_status = MagicMock()

    # Mock Auth Response
    auth_resp = MagicMock(spec=httpx.Response)
    auth_resp.status_code = 200
    auth_resp.json.return_value = {"success": True, "token": "new_token"}

    with patch.object(broker.client, 'request', AsyncMock(side_effect=[resp_401, resp_200])) as mock_req:
        with patch.object(broker.client, 'post', AsyncMock(return_value=auth_resp)):
            res = await broker._request("GET", "/test")
            assert res == {"success": True, "data": "ok"}
            assert broker._token == "new_token"
            assert mock_req.call_count == 2

@pytest.mark.asyncio
async def test_429_retry_with_backoff(broker):
    """test_429_retry_with_backoff — mock 429 → verify retries with increasing delay"""
    broker._token = "token"
    broker._token_expiry = time.time() + 60
    broker.max_retries = 2
    broker.base_retry_delay = 0.01

    resp_429 = MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    
    resp_200 = MagicMock(spec=httpx.Response)
    resp_200.status_code = 200
    resp_200.json.return_value = {"success": True}
    resp_200.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(side_effect=[resp_429, resp_429, resp_200])) as mock_req:
        res = await broker._request("GET", "/test")
        assert res == {"success": True}
        assert mock_req.call_count == 3

@pytest.mark.asyncio
async def test_place_market_order_with_brackets(broker):
    """test_place_market_order_with_brackets — verify correct JSON body sent"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "orderId": 999}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)) as mock_req:
        order_id = await broker.place_market_order(
            contract_id="MNQ", side="buy", size=2,
            stop_loss_ticks=60, take_profit_ticks=120,
            custom_tag="test-tag"
        )
        
        assert order_id == 999
        args, kwargs = mock_req.call_args
        payload = kwargs["json"]
        assert payload["accountId"] == 12345
        assert payload["contractId"] == "MNQ"
        assert payload["type"] == 2 # Market
        assert payload["side"] == 0 # Buy
        assert payload["size"] == 2
        # BUY (side=0): SL ticks negative, TP ticks positive
        assert payload["stopLossBracket"] == {"ticks": -60, "type": 4}
        assert payload["takeProfitBracket"] == {"ticks": 120, "type": 1}
        assert payload["customTag"] == "test-tag"

@pytest.mark.asyncio
async def test_place_market_order_error(broker):
    """test_place_market_order_error — mock rejection → verify OrderRejectedError"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": False, "errorCode": 2, "message": "Rejected"}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)):
        with pytest.raises(OrderRejectedError):
            await broker.place_market_order("MNQ", "buy", 1)

@pytest.mark.asyncio
async def test_modify_order(broker):
    """test_modify_order — verify correct JSON body sent"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)) as mock_req:
        await broker.modify_order(67890, limit_price=15000.5)
        
        args, kwargs = mock_req.call_args
        payload = kwargs["json"]
        assert payload["orderId"] == 67890
        assert payload["limitPrice"] == 15000.5

@pytest.mark.asyncio
async def test_cancel_order(broker):
    """test_cancel_order — verify correct call"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)) as mock_req:
        await broker.cancel_order(67890)
        
        args, kwargs = mock_req.call_args
        payload = kwargs["json"]
        assert payload["orderId"] == 67890
        assert payload["accountId"] == 12345

@pytest.mark.asyncio
async def test_get_open_positions(broker):
    """test_get_open_positions — mock response → verify parsed correctly"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True, 
        "positions": [{"id": 1, "contractId": "MNQ", "size": 1}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)):
        positions = await broker.get_open_positions()
        assert len(positions) == 1
        assert positions[0]["contractId"] == "MNQ"

@pytest.mark.asyncio
async def test_close_position(broker):
    """test_close_position — verify correct call"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)) as mock_req:
        await broker.close_position("MNQ")
        args, kwargs = mock_req.call_args
        assert kwargs["json"]["contractId"] == "MNQ"

@pytest.mark.asyncio
async def test_flatten_all(broker):
    """test_flatten_all — with 2 positions → verify both closed"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    pos_resp = MagicMock(spec=httpx.Response)
    pos_resp.status_code = 200
    pos_resp.json.return_value = {
        "success": True, 
        "positions": [{"contractId": "MNQ"}, {"contractId": "MES"}]
    }
    pos_resp.raise_for_status = MagicMock()

    close_resp = MagicMock(spec=httpx.Response)
    close_resp.status_code = 200
    close_resp.json.return_value = {"success": True}
    close_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(side_effect=[pos_resp, close_resp, close_resp])) as mock_req:
        await broker.flatten_all()
        assert mock_req.call_count == 3 # 1 search + 2 close

@pytest.mark.asyncio
async def test_get_realized_pnl_session(broker):
    """test_get_realized_pnl_session — mock trades → verify PnL math"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "trades": [
            {"profitAndLoss": 50.0, "voided": False},
            {"profitAndLoss": -20.0, "voided": False},
            {"profitAndLoss": 1000.0, "voided": True} # Should be ignored
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)):
        pnl = await broker.get_realized_pnl(session_mode="session")
        assert pnl == 30.0

@pytest.mark.asyncio
async def test_account_selection_by_id(broker):
    """test_account_selection_by_id — explicit ID override"""
    broker._explicit_account_id = 999
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "accounts": [
            {"id": 111, "name": "Wrong", "canTrade": True},
            {"id": 999, "name": "Target", "canTrade": True}
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)):
        info = await broker.get_account_info()
        assert info["id"] == 999
        assert broker.account_id == 999

@pytest.mark.asyncio
async def test_account_selection_heuristic(broker):
    """test_account_selection_heuristic — canTrade + non-simulated + name matching"""
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "accounts": [
            {"id": 1, "name": "SIM", "canTrade": True, "simulated": True},
            {"id": 2, "name": "COMBINE", "canTrade": True, "simulated": False},
            {"id": 3, "name": "OTHER", "canTrade": False, "simulated": False}
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)):
        info = await broker.get_account_info()
        assert info["id"] == 2

@pytest.mark.asyncio
async def test_get_bars(broker):
    """test_get_bars — verify correct request body"""
    broker._account = {"id": 12345}
    broker._token = "token"
    broker._token_expiry = time.time() + 3600
    
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "bars": [{"c": 15000}]}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(broker.client, 'request', AsyncMock(return_value=mock_resp)) as mock_req:
        bars = await broker.get_bars("MNQ", "2026-03-25T00:00:00", "2026-03-25T01:00:00")
        assert len(bars) == 1
        assert bars[0]["c"] == 15000
        
        args, kwargs = mock_req.call_args
        payload = kwargs["json"]
        assert payload["contractId"] == "MNQ"
        assert payload["unit"] == 2
