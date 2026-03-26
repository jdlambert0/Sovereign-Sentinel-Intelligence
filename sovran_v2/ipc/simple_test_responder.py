#!/usr/bin/env python3
"""
Simple IPC Test Responder

This script watches the ipc/ directory for request files and responds with
simple trading decisions for testing the file-based IPC system.

Usage:
    python ipc/simple_test_responder.py
"""
import json
import glob
import os
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

IPC_DIR = Path(__file__).parent
POLL_INTERVAL = 0.5  # seconds

def respond_to_request(request_path: Path):
    """Read request and write a simple response."""
    try:
        with open(request_path, 'r') as f:
            request = json.load(f)

        request_id = request.get('request_id')
        snapshot = request.get('snapshot_data', {})
        expected_response_path = request.get('expected_response_path')

        logger.info(f"Request {request_id}: {snapshot.get('contract_id')} @ {snapshot.get('last_price')}")

        # Simple logic: No trade by default (conservative test)
        response = {
            "signal": "no_trade",
            "conviction": 0,
            "thesis": "Test responder - no trade by default",
            "stop_distance_points": 0,
            "target_distance_points": 0,
            "frameworks_cited": ["test"],
            "time_horizon": "scalp"
        }

        # Write response
        response_path = IPC_DIR / os.path.basename(expected_response_path)
        with open(response_path, 'w') as f:
            json.dump(response, f, indent=2)

        logger.info(f"Response written: {response['signal']} (conviction {response['conviction']})")

        # Delete request file
        request_path.unlink()
        logger.info(f"Request file deleted: {request_path.name}")

    except Exception as e:
        logger.error(f"Error processing request: {e}")

def main():
    logger.info(f"IPC Test Responder started - watching {IPC_DIR}")
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            # Find all request files
            request_files = list(IPC_DIR.glob("request_*.json"))

            for request_path in request_files:
                respond_to_request(request_path)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\\nStopping IPC responder")

if __name__ == "__main__":
    main()
