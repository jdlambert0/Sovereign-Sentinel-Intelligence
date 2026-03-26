"""
Sovran v2 — Autonomous AI Futures Trading System
Entry point. Run this to start the system.

Usage:
    python run.py
    python run.py --contract CON.F.US.MNQM26
    python run.py --dry-run (no real orders)
    python run.py --contracts MNQ,MES,MYM  (multi-market)
"""
import asyncio
import argparse
import signal
import logging
import sys
from src.sentinel import Sentinel, SentinelConfig


def main():
    parser = argparse.ArgumentParser(description="Sovran v2 Trading System")
    parser.add_argument("--contract", default=None, help="Single contract ID to trade (legacy)")
    parser.add_argument("--contracts", default=None, help="Comma-separated list of contracts to hunt across")
    parser.add_argument("--cycle", type=int, default=15, help="Main loop cycle seconds")
    parser.add_argument("--dry-run", action="store_true", help="Run without placing real orders")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Build contract list
    if args.contracts:
        contracts = [c.strip() for c in args.contracts.split(",")]
    elif args.contract:
        contracts = [args.contract]
    else:
        contracts = ["CON.F.US.MNQM26"]  # Default

    config = SentinelConfig(
        contract_id=contracts[0],  # Primary contract (backward compat)
        cycle_seconds=args.cycle,
        dry_run=args.dry_run,
    )

    sentinel = Sentinel(config=config, contracts=contracts)

    # --- Cross-platform graceful shutdown ---
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _request_shutdown():
        logging.info("Shutdown signal received")
        loop.create_task(sentinel.stop())

    if sys.platform == "win32":
        # Windows: signal.signal with loop.call_soon_threadsafe
        signal.signal(signal.SIGINT, lambda s, f: loop.call_soon_threadsafe(_request_shutdown))
        signal.signal(signal.SIGTERM, lambda s, f: loop.call_soon_threadsafe(_request_shutdown))
    else:
        # Unix: loop.add_signal_handler (cleaner, async-safe)
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _request_shutdown)

    try:
        loop.run_until_complete(sentinel.start())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt caught, shutting down...")
        loop.run_until_complete(sentinel.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
