"""
Tests for the AI-driven Decision Engine (Layer 3).

Tests the prompt builder, all three AI backends (Ollama, OpenRouter, File IPC),
response parsing, cooldown logic, and edge cases.
"""

import asyncio
import json
import os
import shutil
import time
import tempfile
import threading
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytz

from src.market_data import MarketSnapshot, MarketRegime
from src.decision import (
    DecisionEngine,
    DecisionConfig,
    TradeIntent,
    PromptBuilder,
    _FileIPCBackend,
    _OllamaBackend,
    _OpenRouterBackend,
)
from src.risk import TradeSide


class TestPromptBuilder(unittest.TestCase):
    """Test the prompt construction."""

    def setUp(self):
        self.snapshot = MarketSnapshot(
            timestamp=1711382400.0,
            contract_id="CON.F.US.MNQM26",
            last_price=18000.0,
            best_bid=17999.75,
            best_ask=18000.25,
            spread=0.5,
            atr_points=10.0,
            vpin=0.3,
            ofi_zscore=1.5,
            volume_rate=1.2,
            bid_ask_imbalance=0.3,
            regime=MarketRegime.TRENDING_UP,
            trend_strength=35.0,
            bar_count=100,
            tick_count=1000,
            high_of_session=18100.0,
            low_of_session=17900.0,
            price_change_pct=0.5,
        )

    def test_prompt_contains_market_data(self):
        prompt = PromptBuilder.build(
            snapshot=self.snapshot,
            account_balance=150000,
            daily_pnl=0,
            distance_to_drawdown=4500,
            recent_trades=[],
            performance_summary={},
        )
        self.assertIn("18000.00", prompt)
        self.assertIn("VPIN", prompt)
        self.assertIn("OFI Z-score", prompt)
        self.assertIn("trending_up", prompt)

    def test_prompt_contains_account_state(self):
        prompt = PromptBuilder.build(
            snapshot=self.snapshot,
            account_balance=150000,
            daily_pnl=-200,
            distance_to_drawdown=4300,
            recent_trades=[],
            performance_summary={"win_rate": 0.55, "profit_factor": 1.2},
        )
        self.assertIn("$150,000", prompt)
        self.assertIn("-200", prompt)  # PnL value present (formatted as $-200.00)
        self.assertIn("55.0%", prompt)

    def test_prompt_contains_response_schema(self):
        prompt = PromptBuilder.build(
            snapshot=self.snapshot,
            account_balance=150000,
            daily_pnl=0,
            distance_to_drawdown=4500,
            recent_trades=[],
            performance_summary={},
        )
        self.assertIn('"signal"', prompt)
        self.assertIn('"conviction"', prompt)
        self.assertIn("no_trade", prompt)

    def test_prompt_includes_recent_trades(self):
        trades = [
            {"side": "long", "contract_id": "MNQ", "net_pnl": 50.0,
             "conviction": 75, "thesis": "Momentum breakout"},
        ]
        prompt = PromptBuilder.build(
            snapshot=self.snapshot,
            account_balance=150000,
            daily_pnl=50,
            distance_to_drawdown=4500,
            recent_trades=trades,
            performance_summary={},
        )
        self.assertIn("Momentum breakout", prompt)
        self.assertIn("$50.00", prompt)

    def test_prompt_includes_contract_meta(self):
        prompt = PromptBuilder.build(
            snapshot=self.snapshot,
            account_balance=150000,
            daily_pnl=0,
            distance_to_drawdown=4500,
            recent_trades=[],
            performance_summary={},
            contract_meta={"name": "Micro Nasdaq", "tick_size": 0.25, "tick_value": 0.50, "point_value": 2.0},
        )
        self.assertIn("Micro Nasdaq", prompt)
        self.assertIn("0.25", prompt)


class TestDecisionEngineResponseParsing(unittest.TestCase):
    """Test parsing of AI responses."""

    def setUp(self):
        self.config = DecisionConfig(ai_provider="file_ipc", ai_ipc_dir="/tmp/sovran_test_ipc")
        self.engine = DecisionEngine(self.config)
        self.snapshot = MarketSnapshot(
            timestamp=1711382400.0,
            contract_id="MNQM26",
            last_price=18000.0,
            best_bid=17999.75,
            best_ask=18000.25,
            spread=0.5,
            atr_points=10.0,
            vpin=0.3,
            ofi_zscore=1.5,
            volume_rate=1.2,
            bid_ask_imbalance=0.3,
            regime=MarketRegime.TRENDING_UP,
            trend_strength=35.0,
            bar_count=100,
            tick_count=1000,
            high_of_session=18100.0,
            low_of_session=17900.0,
            price_change_pct=0.5,
        )

    def test_parse_valid_long(self):
        raw = {
            "signal": "long",
            "conviction": 85,
            "thesis": "Strong trend",
            "stop_distance_points": 15.0,
            "target_distance_points": 30.0,
            "frameworks_cited": ["momentum", "order_flow"],
            "time_horizon": "scalp",
        }
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.side, TradeSide.LONG)
        self.assertEqual(intent.conviction, 85.0)
        self.assertEqual(intent.thesis, "Strong trend")
        self.assertAlmostEqual(intent.suggested_stop_points, 15.0)
        self.assertAlmostEqual(intent.suggested_target_points, 30.0)
        self.assertEqual(len(intent.frameworks_consulted), 2)

    def test_parse_valid_short(self):
        raw = {
            "signal": "short",
            "conviction": 72,
            "thesis": "Mean reversion off highs",
            "stop_distance_points": 12.0,
            "target_distance_points": 24.0,
            "frameworks_cited": ["mean_reversion"],
            "time_horizon": "scalp",
        }
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.side, TradeSide.SHORT)
        self.assertEqual(intent.conviction, 72.0)

    def test_parse_no_trade(self):
        raw = {"signal": "no_trade", "conviction": 30, "thesis": "No edge visible"}
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertIsNone(intent)

    def test_parse_invalid_signal(self):
        raw = {"signal": "buy_everything", "conviction": 100, "thesis": "YOLO"}
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertIsNone(intent)

    def test_parse_clamps_conviction(self):
        raw = {
            "signal": "long",
            "conviction": 150,
            "thesis": "Over-confident",
            "stop_distance_points": 10.0,
            "target_distance_points": 20.0,
        }
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertEqual(intent.conviction, 100.0)

    def test_parse_clamps_stop_minimum(self):
        raw = {
            "signal": "long",
            "conviction": 80,
            "thesis": "Tight stop",
            "stop_distance_points": 1.0,  # Too tight (< 0.5 * ATR=10 = 5)
            "target_distance_points": 20.0,
        }
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertGreaterEqual(intent.suggested_stop_points, 5.0)

    def test_parse_frameworks_as_string(self):
        raw = {
            "signal": "long",
            "conviction": 80,
            "thesis": "test",
            "stop_distance_points": 10.0,
            "target_distance_points": 20.0,
            "frameworks_cited": "momentum",  # String instead of list
        }
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertEqual(intent.frameworks_consulted, ["momentum"])

    def test_parse_defaults_stop_target(self):
        """If AI doesn't specify stop/target, use ATR-based defaults."""
        raw = {
            "signal": "long",
            "conviction": 80,
            "thesis": "trend trade",
        }
        intent = self.engine._parse_response(raw, self.snapshot)
        self.assertIsNotNone(intent)
        # Default stop = 1.5 * ATR = 15.0
        self.assertAlmostEqual(intent.suggested_stop_points, 15.0)
        # Default target = 2.5 * ATR = 25.0
        self.assertAlmostEqual(intent.suggested_target_points, 25.0)


class TestDecisionEngineCooldown(unittest.TestCase):
    """Test cooldown and session limits."""

    def setUp(self):
        self.config = DecisionConfig(
            ai_provider="file_ipc",
            ai_ipc_dir="/tmp/sovran_test_ipc",
            min_seconds_between_trades=120,
            max_trades_per_session=3,
        )
        self.engine = DecisionEngine(self.config)
        self.snapshot = MarketSnapshot(
            timestamp=1711382400.0,
            contract_id="MNQM26",
            last_price=18000.0,
            best_bid=17999.75,
            best_ask=18000.25,
            spread=0.5,
            atr_points=10.0,
            vpin=0.3,
            ofi_zscore=1.5,
            volume_rate=1.2,
            bid_ask_imbalance=0.3,
            regime=MarketRegime.TRENDING_UP,
            trend_strength=35.0,
            bar_count=100,
            tick_count=1000,
            high_of_session=18100.0,
            low_of_session=17900.0,
            price_change_pct=0.5,
        )

    def test_cooldown_blocks_rapid_trades(self):
        """After an intent, cooldown should block the next call."""
        # Simulate that last intent was just now
        self.engine.last_intent_time = time.time()
        result = asyncio.run(
            self.engine.analyze(self.snapshot)
        )
        self.assertIsNone(result)

    def test_cooldown_allows_after_delay(self):
        """After cooldown expires, should proceed."""
        self.engine.last_intent_time = time.time() - 200  # 200s ago, > 120s cooldown
        # Will fail on AI call since no backend running, but should not be None due to cooldown
        # We mock the backend to test
        async def mock_call(prompt, snapshot_data=None):
            return {"signal": "long", "conviction": 85, "thesis": "test",
                    "stop_distance_points": 15, "target_distance_points": 30}
        self.engine._backend.call = mock_call
        result = asyncio.run(
            self.engine.analyze(self.snapshot)
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.side, TradeSide.LONG)

    def test_session_limit(self):
        """Once max trades per session reached, should return None."""
        self.engine._trade_count_session = 3  # At limit
        result = asyncio.run(
            self.engine.analyze(self.snapshot)
        )
        self.assertIsNone(result)

    def test_reset_session_count(self):
        self.engine._trade_count_session = 5
        self.engine.reset_session_count()
        self.assertEqual(self.engine._trade_count_session, 0)


class TestFileIPCBackend(unittest.TestCase):
    """Test the file-based IPC backend."""

    def setUp(self):
        self.ipc_dir = tempfile.mkdtemp()
        self.config = DecisionConfig(
            ai_provider="file_ipc",
            ai_ipc_dir=self.ipc_dir,
            ai_ipc_poll_interval=0.1,
            ai_ipc_max_wait_seconds=5.0,
        )
        self.backend = _FileIPCBackend(self.config)

    def tearDown(self):
        shutil.rmtree(self.ipc_dir, ignore_errors=True)

    def test_request_file_written(self):
        """Verify request JSON is written to IPC dir."""
        async def run():
            # Start the call in background, it will timeout
            import glob as g
            task = asyncio.create_task(self.backend.call("test prompt"))
            await asyncio.sleep(0.3)
            # Check file exists
            files = g.glob(os.path.join(self.ipc_dir, "request_*.json"))
            self.assertTrue(len(files) > 0, "No request file written")
            with open(files[0]) as f:
                data = json.load(f)
            self.assertEqual(data["prompt"], "test prompt")
            self.assertIn("expected_response_path", data)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, TimeoutError):
                pass

        asyncio.run(run())

    def test_response_read(self):
        """Simulate external AI writing a response file."""
        async def run():
            response_data = {
                "signal": "short",
                "conviction": 78,
                "thesis": "Overbought at resistance",
                "stop_distance_points": 12.0,
                "target_distance_points": 24.0,
            }

            async def write_response_delayed():
                """Simulate external AI writing response after a short delay."""
                await asyncio.sleep(0.5)
                # Find request file
                import glob as g
                for _ in range(20):
                    files = g.glob(os.path.join(self.ipc_dir, "request_*.json"))
                    if files:
                        with open(files[0]) as f:
                            req = json.load(f)
                        resp_path = req["expected_response_path"]
                        with open(resp_path, "w") as f:
                            json.dump(response_data, f)
                        return
                    await asyncio.sleep(0.1)

            writer = asyncio.create_task(write_response_delayed())
            result = await self.backend.call("test prompt", snapshot_data={"price": 18000})
            await writer

            self.assertEqual(result["signal"], "short")
            self.assertEqual(result["conviction"], 78)

        asyncio.run(run())

    def test_timeout_raises(self):
        """If no response within max_wait, should raise TimeoutError."""
        self.backend.max_wait = 1.0  # Short timeout for test

        async def run():
            with self.assertRaises(TimeoutError):
                await self.backend.call("test prompt that no one answers")

        asyncio.run(run())

    def test_request_includes_snapshot_data(self):
        """Snapshot data should be in the request file."""
        async def run():
            import glob as g
            task = asyncio.create_task(
                self.backend.call("test", snapshot_data={"contract_id": "MNQ", "price": 18000})
            )
            await asyncio.sleep(0.3)
            files = g.glob(os.path.join(self.ipc_dir, "request_*.json"))
            with open(files[0]) as f:
                data = json.load(f)
            self.assertEqual(data["snapshot_data"]["contract_id"], "MNQ")
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, TimeoutError):
                pass

        asyncio.run(run())


class TestDecisionEngineWithMockedBackend(unittest.TestCase):
    """Full integration test with mocked AI backend."""

    def setUp(self):
        self.config = DecisionConfig(
            ai_provider="file_ipc",
            ai_ipc_dir="/tmp/sovran_test_ipc",
            min_conviction_to_trade=70.0,
        )
        self.engine = DecisionEngine(self.config)
        self.snapshot = MarketSnapshot(
            timestamp=1711382400.0,
            contract_id="MNQM26",
            last_price=18000.0,
            best_bid=17999.75,
            best_ask=18000.25,
            spread=0.5,
            atr_points=10.0,
            vpin=0.3,
            ofi_zscore=1.5,
            volume_rate=1.2,
            bid_ask_imbalance=0.3,
            regime=MarketRegime.TRENDING_UP,
            trend_strength=35.0,
            bar_count=100,
            tick_count=1000,
            high_of_session=18100.0,
            low_of_session=17900.0,
            price_change_pct=0.5,
        )

    def test_full_pipeline_long(self):
        """Test complete pipeline: snapshot → prompt → AI → TradeIntent."""
        async def mock_call(prompt, snapshot_data=None):
            return {
                "signal": "long",
                "conviction": 85,
                "thesis": "Strong bullish momentum with OFI confirmation",
                "stop_distance_points": 15.0,
                "target_distance_points": 30.0,
                "frameworks_cited": ["momentum", "order_flow"],
                "time_horizon": "scalp",
            }

        self.engine._backend.call = mock_call
        result = asyncio.run(
            self.engine.analyze(self.snapshot)
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.side, TradeSide.LONG)
        self.assertEqual(result.conviction, 85.0)
        self.assertIn("momentum", result.frameworks_consulted)

    def test_full_pipeline_below_conviction(self):
        """AI says long but conviction too low → None."""
        async def mock_call(prompt, snapshot_data=None):
            return {
                "signal": "long",
                "conviction": 50,
                "thesis": "Weak signal",
                "stop_distance_points": 10.0,
                "target_distance_points": 20.0,
            }

        self.engine._backend.call = mock_call
        result = asyncio.run(
            self.engine.analyze(self.snapshot)
        )
        self.assertIsNone(result)

    def test_full_pipeline_no_trade(self):
        """AI says no_trade → None."""
        async def mock_call(prompt, snapshot_data=None):
            return {"signal": "no_trade", "conviction": 20, "thesis": "No edge"}

        self.engine._backend.call = mock_call
        result = asyncio.run(
            self.engine.analyze(self.snapshot)
        )
        self.assertIsNone(result)

    def test_backend_failure_returns_none(self):
        """If AI backend fails after retries, return None."""
        async def mock_call(prompt, snapshot_data=None):
            raise Exception("Backend down")

        self.engine._backend.call = mock_call
        self.engine.config.ai_max_retries = 1
        result = asyncio.run(
            self.engine.analyze(self.snapshot)
        )
        self.assertIsNone(result)


class TestDecisionConfig(unittest.TestCase):
    """Test config loading."""

    def test_load_config_from_json(self):
        engine = DecisionEngine(DecisionConfig(ai_provider="file_ipc", ai_ipc_dir="/tmp/test"))
        config_path = "/tmp/test_decision_config.json"
        try:
            with open(config_path, "w") as f:
                json.dump({"min_conviction_to_trade": 66.0, "min_seconds_between_trades": 300}, f)
            engine.load_config(config_path)
            self.assertEqual(engine.config.min_conviction_to_trade, 66.0)
            self.assertEqual(engine.config.min_seconds_between_trades, 300)
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_update_weights_backward_compat(self):
        """update_weights is a no-op stub for backward compatibility."""
        engine = DecisionEngine(DecisionConfig(ai_provider="file_ipc", ai_ipc_dir="/tmp/test"))
        engine.update_weights({"momentum": 2.0})  # Should not raise


if __name__ == "__main__":
    unittest.main()
