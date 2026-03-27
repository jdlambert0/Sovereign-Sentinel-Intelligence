#!/usr/bin/env python3
"""
Autonomous IPC Responder - Makes Trading Decisions

This responder analyzes market data and makes trading decisions based on:
- OFI Z-Score (order flow imbalance)
- VPIN (probability of informed trading)
- Regime (trending/ranging/volatile)
- ATR (volatility)

It responds to IPC requests from sovran_v2 trading system.
"""
import json
import glob
import os
import time
import logging
from pathlib import Path
from typing import Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [IPC-RESPONDER] %(message)s'
)
logger = logging.getLogger(__name__)

IPC_DIR = Path(__file__).parent
POLL_INTERVAL = 0.3  # seconds

def make_trading_decision(request: Dict) -> Dict:
    """
    Analyze market data and return trading decision.

    Strategy:
    - LONG if OFI_Z > 1.5 AND VPIN > 0.55 AND regime=trending
    - SHORT if OFI_Z < -1.5 AND VPIN > 0.55 AND regime=trending
    - NO_TRADE otherwise
    """
    snapshot = request.get('snapshot_data', {})

    # Extract key metrics
    ofi_z = snapshot.get('ofi_zscore', 0)
    vpin = snapshot.get('vpin', 0)
    regime = snapshot.get('regime', 'unknown')
    atr = snapshot.get('atr_points', 10.0)
    contract_id = snapshot.get('contract_id', 'UNKNOWN')
    last_price = snapshot.get('last_price', 0)

    # Log the analysis
    logger.info(f"Analyzing {contract_id} @ ${last_price:.2f}")
    logger.info(f"  OFI_Z={ofi_z:.2f} VPIN={vpin:.3f} Regime={regime} ATR={atr:.1f}")

    # Decision logic
    signal = "no_trade"
    conviction = 0
    thesis = "Waiting for clear setup"

    # Strong institutional buying + trending
    if ofi_z > 1.5 and vpin > 0.55 and regime in ['trending', 'trending_up']:
        signal = "long"
        conviction = min(100, int(50 + (ofi_z * 10) + (vpin * 50)))
        thesis = f"Strong institutional buying: OFI_Z={ofi_z:.2f}, VPIN={vpin:.2f}, trending regime"

    # Strong institutional selling + trending
    elif ofi_z < -1.5 and vpin > 0.55 and regime in ['trending', 'trending_down']:
        signal = "short"
        conviction = min(100, int(50 + (abs(ofi_z) * 10) + (vpin * 50)))
        thesis = f"Strong institutional selling: OFI_Z={ofi_z:.2f}, VPIN={vpin:.2f}, trending regime"

    # Moderate signals
    elif ofi_z > 1.0 and vpin > 0.50:
        signal = "long"
        conviction = min(80, int(40 + (ofi_z * 8) + (vpin * 40)))
        thesis = f"Moderate buying pressure: OFI_Z={ofi_z:.2f}, VPIN={vpin:.2f}"

    elif ofi_z < -1.0 and vpin > 0.50:
        signal = "short"
        conviction = min(80, int(40 + (abs(ofi_z) * 8) + (vpin * 40)))
        thesis = f"Moderate selling pressure: OFI_Z={ofi_z:.2f}, VPIN={vpin:.2f}"

    # No clear signal
    else:
        thesis = f"No clear edge: OFI_Z={ofi_z:.2f}, VPIN={vpin:.2f}, Regime={regime}"

    # Calculate stops and targets based on ATR
    stop_distance = max(atr * 1.5, 10.0)  # 1.5x ATR, min 10 points
    target_distance = stop_distance * 2.0  # 2:1 R:R

    response = {
        "signal": signal,
        "conviction": conviction,
        "thesis": thesis,
        "stop_distance_points": stop_distance,
        "target_distance_points": target_distance,
        "frameworks_cited": ["order_flow", "microstructure", "regime"],
        "time_horizon": "scalp"
    }

    logger.info(f"  Decision: {signal.upper()} (conviction={conviction})")
    if signal != "no_trade":
        logger.info(f"  SL={stop_distance:.1f}pts TP={target_distance:.1f}pts")
        logger.info(f"  Thesis: {thesis}")

    return response


def respond_to_request(request_path: Path):
    """Read request and write response."""
    try:
        with open(request_path, encoding='utf-8') as f:
            request = json.load(f)

        request_id = request.get('request_id')
        expected_response_path = request.get('expected_response_path')

        # Make trading decision
        response = make_trading_decision(request)

        # Write response
        response_path = IPC_DIR / os.path.basename(expected_response_path)
        with open(response_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2)

        logger.info(f"[OK] Response written to {response_path.name}")

        # Delete request file
        request_path.unlink()

    except Exception as e:
        logger.error(f"Error processing request: {e}")


def main():
    logger.info(f"Autonomous IPC Responder started - watching {IPC_DIR}")
    logger.info("Strategy: Trade on OFI + VPIN signals in trending regimes")
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    try:
        while True:
            # Find all request files
            request_files = list(IPC_DIR.glob("request_*.json"))

            for request_path in request_files:
                respond_to_request(request_path)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\nStopping IPC responder")


if __name__ == "__main__":
    main()
