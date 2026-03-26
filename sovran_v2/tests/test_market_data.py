import json
import time
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch
from src.market_data import (
    MarketDataPipeline, Quote, TradeTick, Bar, MarketRegime, MarketSnapshot, MarketDataError
)

# --- Unit Tests ---

def test_quote_creation():
    q = Quote(timestamp=1000.0, last_price=15000.0, best_bid=14999.0, best_ask=15001.0, volume=100)
    assert q.spread == 2.0
    assert q.last_price == 15000.0

def test_bar_aggregation():
    pipeline = MarketDataPipeline("token", "TEST", bar_seconds=10)
    # Use fixed timestamps that won't age out if we mock time
    with patch("time.time", return_value=2000.0):
        # Buckets: 1000-1010, 1010-1020
        ts0 = datetime.fromtimestamp(1000.0, tz=timezone.utc).isoformat()
        ts1 = datetime.fromtimestamp(1005.0, tz=timezone.utc).isoformat()
        ts2 = datetime.fromtimestamp(1011.0, tz=timezone.utc).isoformat()
    
        # Feed trades
        pipeline._process_trade([
            {"price": 100.0, "volume": 10, "side": 0, "timestamp": ts0},
            {"price": 105.0, "volume": 5, "side": 1, "timestamp": ts1},
        ])
        # Still in current_bar
        assert len(pipeline._bars) == 0
        assert pipeline._current_bar.open == 100.0
        assert pipeline._current_bar.volume == 15
        
        # Next bar
        pipeline._process_trade([
            {"price": 102.0, "volume": 20, "side": 0, "timestamp": ts2}
        ])
        assert len(pipeline._bars) == 1
        assert pipeline._bars[0].close == 105.0
        assert pipeline._current_bar.open == 102.0

def test_bar_buy_sell_volume():
    pipeline = MarketDataPipeline("token", "TEST", bar_seconds=60)
    pipeline._process_trade([
        {"price": 100.0, "volume": 10, "side": 0}, # Buy
        {"price": 100.0, "volume": 5, "side": 1},  # Sell
    ])
    assert pipeline._current_bar.buy_volume == 10
    assert pipeline._current_bar.sell_volume == 5

def test_buffer_aging():
    pipeline = MarketDataPipeline("token", "TEST", buffer_minutes=1)
    now = time.time()
    # Old data
    with pipeline.lock:
        pipeline._bars.append(Bar(timestamp=now - 120, open=100, high=100, low=100, close=100, volume=10, tick_count=1))
        pipeline._ticks.append(TradeTick(timestamp=now - 120, price=100, volume=10, side=0))
        # New data
        pipeline._bars.append(Bar(timestamp=now - 30, open=100, high=100, low=100, close=100, volume=10, tick_count=1))
        pipeline._ticks.append(TradeTick(timestamp=now - 30, price=100, volume=10, side=0))
    
    pipeline._age_buffer()
    assert len(pipeline._bars) == 1
    assert len(pipeline._ticks) == 1
    assert pipeline._bars[0].timestamp > now - 60

def test_atr_calculation():
    pipeline = MarketDataPipeline("token", "TEST")
    # 15 bars (need 14 + 1 for prev_close)
    # TR = max(H-L, |H-PC|, |L-PC|)
    # Let's make it constant: H=110, L=100, PC=105 -> TR=10
    for i in range(16):
        pipeline._bars.append(Bar(timestamp=i*10, open=105, high=110, low=100, close=105, volume=10, tick_count=1))
    
    atr = pipeline.calculate_atr(period=14)
    assert atr == 10.0

def test_atr_insufficient_data():
    pipeline = MarketDataPipeline("token", "TEST")
    pipeline._bars.append(Bar(timestamp=10, open=100, high=110, low=90, close=100, volume=10, tick_count=1))
    assert pipeline.calculate_atr(period=14) == 0.0

def test_vpin_calculation():
    pipeline = MarketDataPipeline("token", "TEST")
    # Bucket size 50
    # Bucket 1: 30 buy, 20 sell -> imb = |30-20|/50 = 0.2
    # Bucket 2: 50 buy, 0 sell -> imb = |50-0|/50 = 1.0
    # VPIN = (0.2 + 1.0) / 2 = 0.6
    pipeline._ticks = [
        TradeTick(0, 100, 30, 0),
        TradeTick(0, 100, 20, 1),
        TradeTick(0, 100, 50, 0)
    ]
    vpin = pipeline.calculate_vpin(bucket_size=50)
    assert vpin == 0.6

def test_vpin_all_buys():
    pipeline = MarketDataPipeline("token", "TEST")
    pipeline._ticks = [TradeTick(0, 100, 100, 0)]
    assert pipeline.calculate_vpin(bucket_size=50) == 1.0

def test_vpin_balanced():
    pipeline = MarketDataPipeline("token", "TEST")
    pipeline._ticks = [
        TradeTick(0, 100, 25, 0),
        TradeTick(0, 100, 25, 1)
    ]
    assert pipeline.calculate_vpin(bucket_size=50) == 0.0

def test_ofi_zscore_calculation():
    pipeline = MarketDataPipeline("token", "TEST")
    # Need at least 5 samples of OFI (window=10)
    # 50 ticks, window 10 -> samples at 0, 5, 10, 15, 20, 25, 30, 35, 40 (step = window/2)
    for i in range(50):
        pipeline._ticks.append(TradeTick(0, 100, 10, 0 if i % 2 == 0 else 1)) # OFI per tick = 10, -10, ...
    
    # Last 10 ticks: 0, -10, 10, -10... -> sum = 0
    # Mean will be near 0, Std will be some value.
    z = pipeline.calculate_ofi_zscore(window=10)
    assert isinstance(z, float)

def test_regime_trending_up():
    pipeline = MarketDataPipeline("token", "TEST")
    # Trend up: high/low increasing
    for i in range(20):
        pipeline._bars.append(Bar(
            timestamp=i*15,
            open=100 + i,
            high=105 + i,
            low=95 + i,
            close=100 + i,
            volume=100,
            tick_count=10
        ))
    regime, strength = pipeline.detect_regime()
    assert regime == MarketRegime.TRENDING_UP
    assert strength > 25

def test_regime_choppy():
    pipeline = MarketDataPipeline("token", "TEST")
    # Flat range
    for i in range(20):
        pipeline._bars.append(Bar(
            timestamp=i*15,
            open=100,
            high=105,
            low=95,
            close=100,
            volume=100,
            tick_count=10
        ))
    regime, strength = pipeline.detect_regime()
    assert regime == MarketRegime.CHOPPY
    assert strength < 20

def test_regime_unknown_insufficient_data():
    pipeline = MarketDataPipeline("token", "TEST")
    regime, strength = pipeline.detect_regime()
    assert regime == MarketRegime.UNKNOWN

def test_snapshot_creation():
    pipeline = MarketDataPipeline("token", "CON.ID")
    pipeline._latest_quote = Quote(time.time(), 100, 99.5, 100.5, 1000)
    # Add some data so calculations don't return 0 if possible
    for i in range(20):
        pipeline._bars.append(Bar(i, 100, 101, 99, 100, 10, 1))
        pipeline._ticks.append(TradeTick(i, 100, 10, 0))
    
    snapshot = pipeline.get_snapshot()
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.contract_id == "CON.ID"
    assert snapshot.last_price == 100
    assert snapshot.bar_count == 20

# --- Protocol Tests ---

def test_handshake_sent_on_open():
    pipeline = MarketDataPipeline("token", "TEST")
    mock_ws = MagicMock()
    pipeline._on_open(mock_ws)
    # Handshake is sent immediately (subscriptions are delayed in a thread)
    assert mock_ws.send.call_count == 1
    args = mock_ws.send.call_args_list[0][0][0]
    assert "protocol" in args
    assert args.endswith('\x1e')

def test_subscription_sent_after_handshake():
    import time as _time
    pipeline = MarketDataPipeline("token", "TEST")
    mock_ws = MagicMock()
    pipeline._on_open(mock_ws)
    # Subscriptions are sent after a 0.5s delay in a thread
    _time.sleep(1.0)  # Wait for the delayed thread to fire
    assert mock_ws.send.call_count == 4  # handshake + 3 subs (quotes + trades + depth)
    args2 = mock_ws.send.call_args_list[1][0][0]
    args3 = mock_ws.send.call_args_list[2][0][0]
    args4 = mock_ws.send.call_args_list[3][0][0]
    assert "SubscribeContractQuotes" in args2
    assert "SubscribeContractTrades" in args3
    assert "SubscribeContractDepth" in args4

def test_parse_gateway_quote():
    pipeline = MarketDataPipeline("token", "TEST")
    ts = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()
    msg = json.dumps({
        "type": 1,
        "target": "GatewayQuote",
        "arguments": ["TEST", {
            "contractId": "TEST",
            "lastPrice": 18000.5,
            "bestBid": 18000.0,
            "bestAsk": 18001.0,
            "volume": 50000,
            "timestamp": ts
        }]
    }) + '\x1e'
    pipeline._on_message(None, msg)
    assert pipeline._latest_quote.last_price == 18000.5
    assert pipeline._latest_quote.volume == 50000

def test_parse_gateway_trade():
    pipeline = MarketDataPipeline("token", "TEST")
    # Use recent timestamp
    ts = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()
    msg = json.dumps({
        "type": 1,
        "target": "GatewayTrade",
        "arguments": ["TEST", [{
            "price": 18000.25,
            "volume": 2,
            "side": 0,
            "timestamp": ts
        }]]
    }) + '\x1e'
    pipeline._on_message(None, msg)
    assert len(pipeline._ticks) == 1
    assert pipeline._ticks[0].price == 18000.25
    assert pipeline._ticks[0].volume == 2

def test_parse_multiple_frames():
    pipeline = MarketDataPipeline("token", "TEST")
    msg1 = json.dumps({"type": 6})
    msg2 = json.dumps({"type": 1, "target": "GatewayQuote", "arguments": ["TEST", {"lastPrice": 100}]})
    full_msg = msg1 + '\x1e' + msg2 + '\x1e'
    
    mock_ws = MagicMock()
    pipeline._on_message(mock_ws, full_msg)
    
    # Should have replied to ping
    mock_ws.send.assert_called_with('{"type":6}\x1e')
    # Should have updated quote
    assert pipeline._latest_quote.last_price == 100

def test_parse_gateway_quote_total_volume():
    """Test that totalVolume field is accepted (actual API format)."""
    pipeline = MarketDataPipeline("token", "TEST")
    ts = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()
    msg = json.dumps({
        "type": 1,
        "target": "GatewayQuote",
        "arguments": ["TEST", {
            "lastPrice": 20000.5,
            "bestBid": 20000.0,
            "bestAsk": 20001.0,
            "totalVolume": 75000,
            "change": -15.5,
            "changePercent": -0.08,
            "timestamp": ts,
        }]
    }) + '\x1e'
    pipeline._on_message(None, msg)
    assert pipeline._latest_quote.last_price == 20000.5
    assert pipeline._latest_quote.volume == 75000
    assert pipeline._latest_quote.change == -15.5
    assert pipeline._latest_quote.change_pct == -0.08


def test_parse_gateway_depth():
    """Test GatewayDepth L2 order book parsing."""
    pipeline = MarketDataPipeline("token", "TEST")
    msg = json.dumps({
        "type": 1,
        "target": "GatewayDepth",
        "arguments": ["TEST", [
            {"price": 20000.0, "volume": 15, "type": 1, "timestamp": "2026-03-26T00:00:00Z"},
            {"price": 19999.75, "volume": 8, "type": 1, "timestamp": "2026-03-26T00:00:00Z"},
            {"price": 20000.25, "volume": 12, "type": 2, "timestamp": "2026-03-26T00:00:00Z"},
            {"price": 20000.50, "volume": 5, "type": 2, "timestamp": "2026-03-26T00:00:00Z"},
        ]]
    }) + '\x1e'
    pipeline._on_message(None, msg)
    assert len(pipeline._l2_bids) == 2
    assert len(pipeline._l2_asks) == 2
    assert pipeline._l2_bids[20000.0] == 15
    assert pipeline._l2_asks[20000.25] == 12


def test_parse_gateway_depth_reset():
    """Test GatewayDepth type=6 (reset) clears book."""
    pipeline = MarketDataPipeline("token", "TEST")
    # Add levels
    pipeline._process_depth([
        {"price": 20000.0, "volume": 10, "type": 1},
        {"price": 20000.25, "volume": 5, "type": 2},
    ])
    assert len(pipeline._l2_bids) == 1
    # Reset message
    msg = json.dumps({
        "type": 1,
        "target": "GatewayDepth",
        "arguments": ["TEST", [{"type": 6}]]
    }) + '\x1e'
    pipeline._on_message(None, msg)
    assert len(pipeline._l2_bids) == 0
    assert len(pipeline._l2_asks) == 0


def test_ping_response():
    pipeline = MarketDataPipeline("token", "TEST")
    mock_ws = MagicMock()
    pipeline._on_message(mock_ws, '{"type":6}\x1e')
    mock_ws.send.assert_called_with('{"type":6}\x1e')

@patch("src.market_data.websocket.WebSocketApp")
@patch("time.sleep", return_value=None)
def test_reconnect_on_close(mock_sleep, mock_ws_app):
    pipeline = MarketDataPipeline("token", "TEST", max_reconnect_attempts=2)
    # Force a failure in run_forever or similar
    mock_ws_instance = mock_ws_app.return_value
    mock_ws_instance.run_forever.side_effect = [Exception("fail"), None]
    
    import threading
    # We'll call _run_websocket_loop directly for test
    pipeline._run_websocket_loop()
    
    assert pipeline._reconnect_count == 2
    assert mock_ws_app.call_count == 2
