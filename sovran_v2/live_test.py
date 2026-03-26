"""
Live API Test & Autonomous Trading Session
-------------------------------------------
Phase 1: Connect, verify credentials, get account info
Phase 2: Get market data flowing (WebSocket)
Phase 3: Scan markets, find best setups
Phase 4: Execute trades with tight risk management
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.broker import BrokerClient, BrokerError, AuthenticationError, OutsideTradingHoursError
from src.market_data import MarketDataPipeline, MarketDataError, MarketSnapshot
from src.decision import DecisionEngine, PromptBuilder
from src.risk import RiskGuardian
from src.scanner import MarketScanner, MarketScore
from src.sentinel import CONTRACT_META, _lookup_contract_meta

# --- Configuration ---
USERNAME = "jessedavidlambert@gmail.com"
API_KEY = "/S16+QEnTHSMA2lPuGdEs3ISwrzmuuMqvouqzgT3T8g="
BASE_URL = "https://api.topstepx.com"

# Start with micro contracts only for safety
SCAN_CONTRACTS = [
    "CON.F.US.MNQ.M26",  # Micro Nasdaq
    "CON.F.US.MES.M26",  # Micro S&P
    "CON.F.US.MYM.M26",  # Micro Dow
    "CON.F.US.M2K.M26",  # Micro Russell
    "CON.F.US.MGC.J26",  # Micro Gold
    "CON.F.US.MCLE.K26", # Micro Crude
]

# Risk parameters — very conservative for live testing
MAX_POSITION_SIZE = 2        # Max 2 micro contracts
MAX_DAILY_LOSS = -500.0      # Stop trading if daily loss exceeds $500
MIN_CONVICTION = 72          # Higher conviction threshold for live
STOP_LOSS_TICKS = 20         # 20 ticks stop loss
TAKE_PROFIT_TICKS = 40       # 40 ticks take profit (2:1 R:R)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("live_test.log"),
    ]
)
logger = logging.getLogger("live_test")


class LiveSession:
    """Manages a live trading session."""

    def __init__(self):
        self.broker: BrokerClient = None
        self.pipelines: dict[str, MarketDataPipeline] = {}
        self.scanner = MarketScanner()
        self.results = {
            "auth": None,
            "account": None,
            "positions": None,
            "market_data": {},
            "scans": [],
            "trades_attempted": 0,
            "trades_executed": 0,
            "pnl": 0.0,
            "errors": [],
        }

    async def run(self):
        """Run the full live test session."""
        logger.info("=" * 60)
        logger.info("SOVRAN V2 — LIVE API TEST SESSION")
        logger.info("=" * 60)

        try:
            # Phase 1: Connect and verify
            await self._phase1_connect()

            # Phase 2: Get market data
            await self._phase2_market_data()

            # Phase 3: Scan and analyze
            await self._phase3_scan()

            # Phase 4: Trade (if conditions are good)
            await self._phase4_trade()

        except Exception as e:
            logger.error(f"Session error: {e}", exc_info=True)
            self.results["errors"].append(str(e))
        finally:
            await self._cleanup()

        return self.results

    async def _phase1_connect(self):
        """Phase 1: Authenticate and get account info."""
        logger.info("\n--- PHASE 1: CONNECT & VERIFY ---")

        # Test API ping
        self.broker = BrokerClient(
            username=USERNAME,
            api_key=API_KEY,
            base_url=BASE_URL,
        )

        ping_ok = await self.broker.ping()
        logger.info(f"API Ping: {'OK' if ping_ok else 'FAILED'}")

        # Authenticate
        logger.info("Authenticating...")
        await self.broker.connect()
        self.results["auth"] = "success"
        logger.info(f"✅ Authentication successful")

        # Account info
        account = self.broker._account
        self.results["account"] = {
            "id": account.get("id"),
            "name": account.get("name"),
            "balance": account.get("balance"),
            "can_trade": account.get("canTrade"),
        }
        logger.info(f"Account: {account.get('name')}")
        logger.info(f"Balance: ${account.get('balance', 0):,.2f}")
        logger.info(f"Can Trade: {account.get('canTrade')}")

        # Check existing positions
        positions = await self.broker.get_open_positions()
        self.results["positions"] = positions
        if positions:
            logger.info(f"⚠️  Open positions found: {len(positions)}")
            for p in positions:
                logger.info(f"  {p.get('contractId')}: {p.get('size')} @ {p.get('averagePrice')}")
        else:
            logger.info("No open positions (clean slate)")

        # Check today's PnL
        try:
            pnl = await self.broker.get_realized_pnl()
            logger.info(f"Session PnL: ${pnl:,.2f}")
            self.results["pnl"] = pnl
            if pnl < MAX_DAILY_LOSS:
                logger.warning(f"⚠️  Daily loss limit reached (${pnl:,.2f}), won't trade")
        except Exception as e:
            logger.warning(f"Couldn't get PnL: {e}")

        # Check open orders
        open_orders = await self.broker.get_open_orders()
        if open_orders:
            logger.info(f"Open orders: {len(open_orders)}")
            for o in open_orders:
                logger.info(f"  Order {o.get('id')}: {o.get('contractId')} {o.get('side')} {o.get('size')}")

    async def _phase2_market_data(self):
        """Phase 2: Start WebSocket market data for multiple contracts."""
        logger.info("\n--- PHASE 2: MARKET DATA ---")

        token = self.broker.token
        for contract_id in SCAN_CONTRACTS:
            try:
                pipeline = MarketDataPipeline(
                    jwt_token=token,
                    contract_id=contract_id,
                    buffer_minutes=15,
                    bar_seconds=15,
                )
                await pipeline.start()
                self.pipelines[contract_id] = pipeline
                logger.info(f"  Started pipeline for {contract_id}")
            except Exception as e:
                logger.error(f"  Failed to start {contract_id}: {e}")
                self.results["errors"].append(f"Pipeline {contract_id}: {e}")

        # Wait for data to flow
        logger.info("Waiting 20s for market data to flow...")
        await asyncio.sleep(20)

        # Check which pipelines have data
        for cid, pipe in self.pipelines.items():
            meta = _lookup_contract_meta(cid)
            symbol = meta.get("symbol", cid) if meta else cid
            connected = pipe.is_connected
            stale = pipe.seconds_since_last_update
            has_quote = pipe._latest_quote is not None

            status = "✅" if connected and has_quote else "❌"
            logger.info(f"  {status} {symbol}: connected={connected}, stale={stale:.1f}s, has_quote={has_quote}")

            self.results["market_data"][cid] = {
                "symbol": symbol,
                "connected": connected,
                "stale_seconds": round(stale, 1),
                "has_data": has_quote,
            }

            if has_quote:
                q = pipe._latest_quote
                logger.info(f"      Last={q.last_price}, Bid={q.best_bid}, Ask={q.best_ask}, Vol={q.volume}")

    async def _phase3_scan(self):
        """Phase 3: Scan markets and find best setups."""
        logger.info("\n--- PHASE 3: MARKET SCAN ---")

        snapshots = []
        for cid, pipe in self.pipelines.items():
            try:
                snap = pipe.get_snapshot()
                snapshots.append(snap)
                meta = _lookup_contract_meta(cid) or {}
                symbol = meta.get("symbol", cid)
                logger.info(f"  {symbol}: price={snap.last_price}, ATR={snap.atr_points:.2f}, "
                          f"VPIN={snap.vpin:.3f}, OFI_Z={snap.ofi_zscore:.2f}, "
                          f"regime={snap.regime.value}, L2_bids={snap.l2_bid_total_volume}, L2_asks={snap.l2_ask_total_volume}")
            except MarketDataError:
                logger.info(f"  {cid}: No data available")
            except Exception as e:
                logger.warning(f"  {cid}: Error getting snapshot: {e}")

        if len(snapshots) < 2:
            logger.warning("Not enough markets with data for scanning")
            return

        # Run scanner
        scores = self.scanner.scan(snapshots)
        logger.info(f"\nMarket Rankings ({len(scores)} scored):")
        for i, score in enumerate(scores):
            meta = _lookup_contract_meta(score.contract_id) or {}
            symbol = meta.get("symbol", score.contract_id)
            logger.info(f"  #{i+1} {symbol}: conviction={score.score:.0f}, "
                       f"direction={score.direction}, regime={score.regime}")

        self.results["scans"] = [
            {"contract_id": s.contract_id, "score": round(s.score, 1),
             "direction": s.direction, "regime": s.regime}
            for s in scores
        ]

        # Store best opportunity
        if scores and scores[0].score >= MIN_CONVICTION:
            self._best_opportunity = scores[0]
            logger.info(f"\n🎯 Best opportunity: {scores[0].contract_id} "
                       f"(conviction {scores[0].score:.0f}, {scores[0].direction})")
        else:
            self._best_opportunity = None
            if scores:
                logger.info(f"\nNo setups above {MIN_CONVICTION} conviction "
                          f"(best: {scores[0].score:.0f})")
            else:
                logger.info("No scores available")

    async def _phase4_trade(self):
        """Phase 4: Execute trades if conditions are met."""
        logger.info("\n--- PHASE 4: TRADE EXECUTION ---")

        # Safety checks
        if self.results["pnl"] < MAX_DAILY_LOSS:
            logger.info("⛔ Daily loss limit reached. No trades.")
            return

        if self.results["positions"]:
            logger.info("⚠️  Existing positions open. Monitoring only.")
            return

        best = getattr(self, "_best_opportunity", None)
        if not best:
            logger.info("No trading opportunities above conviction threshold.")
            # Try a lower threshold scan just for diagnostics
            return

        contract_id = best.contract_id
        meta = _lookup_contract_meta(contract_id) or {}
        symbol = meta.get("symbol", contract_id)
        tick_size = meta.get("tick_size", 0.25)
        tick_value = meta.get("tick_value", 0.50)

        side = "buy" if best.direction == "long" else "sell"
        size = 1  # Always start with 1 micro contract

        # Calculate risk
        risk_per_trade = STOP_LOSS_TICKS * tick_value * size
        reward_per_trade = TAKE_PROFIT_TICKS * tick_value * size

        logger.info(f"Trade Plan:")
        logger.info(f"  Contract: {symbol} ({contract_id})")
        logger.info(f"  Direction: {side.upper()}")
        logger.info(f"  Size: {size}")
        logger.info(f"  Stop Loss: {STOP_LOSS_TICKS} ticks (${risk_per_trade:.2f})")
        logger.info(f"  Take Profit: {TAKE_PROFIT_TICKS} ticks (${reward_per_trade:.2f})")
        logger.info(f"  Conviction: {best.score:.0f}")

        # Place the trade
        try:
            self.results["trades_attempted"] += 1
            order_id = await self.broker.place_market_order(
                contract_id=contract_id,
                side=side,
                size=size,
                stop_loss_ticks=STOP_LOSS_TICKS,
                take_profit_ticks=TAKE_PROFIT_TICKS,
                custom_tag=f"sovran_live_{int(time.time())}",
            )
            logger.info(f"✅ ORDER PLACED! ID: {order_id}")
            self.results["trades_executed"] += 1

            # Monitor for 60 seconds
            logger.info("Monitoring position for 60s...")
            for i in range(12):
                await asyncio.sleep(5)
                positions = await self.broker.get_open_positions()
                if not positions:
                    logger.info("Position closed (SL/TP hit)")
                    break
                for p in positions:
                    if p.get("contractId") == contract_id:
                        logger.info(f"  [{i*5}s] Size={p.get('size')}, AvgPrice={p.get('averagePrice')}")

            # Check final PnL
            final_pnl = await self.broker.get_realized_pnl()
            logger.info(f"Session PnL after trade: ${final_pnl:,.2f}")
            self.results["pnl"] = final_pnl

        except OutsideTradingHoursError:
            logger.warning("⚠️  Market is closed — outside trading hours")
            self.results["errors"].append("Outside trading hours")
        except BrokerError as e:
            logger.error(f"Trade failed: {e}")
            self.results["errors"].append(f"Trade error: {e}")

    async def _cleanup(self):
        """Clean up all connections."""
        logger.info("\n--- CLEANUP ---")
        for cid, pipe in self.pipelines.items():
            try:
                await pipe.stop()
            except:
                pass
        if self.broker:
            try:
                await self.broker.disconnect()
            except:
                pass
        logger.info("Session ended.")


async def main():
    session = LiveSession()
    results = await session.run()

    # Write results
    with open("live_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"\nResults saved to live_test_results.json")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SESSION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Auth: {results['auth']}")
    acct = results.get('account') or {}
    logger.info(f"Account: {acct.get('name', 'N/A')}")
    logger.info(f"Balance: ${acct.get('balance', 0):,.2f}")
    logger.info(f"Markets with data: {sum(1 for v in results['market_data'].values() if v.get('has_data'))}/{len(results['market_data'])}")
    logger.info(f"Trades attempted: {results['trades_attempted']}")
    logger.info(f"Trades executed: {results['trades_executed']}")
    logger.info(f"Session PnL: ${results['pnl']:,.2f}")
    if results['errors']:
        logger.info(f"Errors: {len(results['errors'])}")
        for e in results['errors']:
            logger.info(f"  - {e}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
