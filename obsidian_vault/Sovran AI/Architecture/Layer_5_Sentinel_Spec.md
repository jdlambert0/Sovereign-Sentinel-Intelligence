# Layer 5: The Sentinel (Autonomous Operations) — Technical Specification

> **Author**: CIO Agent  
> **Date**: 2026-03-25  
> **For**: Coding Agent  
> **Depends On**: All previous layers (0-4)  
> **Output Files**: `src/sentinel.py`, `tests/test_sentinel.py`, `run.py` (entry point)

---

## 1. Overview

The Sentinel is the orchestrator that makes everything run autonomously. It manages the lifecycle of all layers, monitors health, handles crashes, and runs the main trading loop. When you run `python run.py`, the Sentinel starts and the system trades until you stop it.

## 2. Architecture

```
run.py → Sentinel.start()
              ↓
    ┌─────────────────────────────────┐
    │ Startup Sequence                │
    │ 1. Load configs                 │
    │ 2. Connect broker (Layer 0)     │
    │ 3. Check account health         │
    │ 4. Start market data (Layer 2)  │
    │ 5. Initialize risk (Layer 1)    │
    │ 6. Initialize decision (Layer 3)│
    │ 7. Initialize learning (Layer 4)│
    │ 8. Enter main loop              │
    └─────────────────────────────────┘
              ↓
    ┌─────────────────────────────────┐
    │ Main Trading Loop (async)       │
    │ Every cycle (default 15s):      │
    │ 1. Check market data health     │
    │ 2. Get MarketSnapshot           │
    │ 3. DecisionEngine.analyze()     │
    │ 4. If intent → Guardian.eval()  │
    │ 5. If approved → Guardian.exec()│
    │ 6. Monitor open positions       │
    │ 7. Check daily PnL limits       │
    │ 8. Update Obsidian status       │
    │ 9. Sleep until next cycle       │
    └─────────────────────────────────┘
              ↓
    ┌─────────────────────────────────┐
    │ Background Tasks                │
    │ - Health monitor (every 30s)    │
    │ - Position monitor (every 10s)  │
    │ - Obsidian status (every 5min)  │
    │ - Trade close detector          │
    └─────────────────────────────────┘
```

## 3. Data Structures

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List
import time

class SystemState(Enum):
    STARTING = "starting"
    RUNNING = "running"
    TRADING_HALTED = "trading_halted"      # Daily limit hit or circuit breaker
    MARKET_CLOSED = "market_closed"
    DEGRADED = "degraded"                  # Some component unhealthy
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class HealthStatus:
    """Health of each component."""
    broker_connected: bool = False
    market_data_connected: bool = False
    market_data_last_update: float = 0.0
    risk_engine_ready: bool = False
    decision_engine_ready: bool = False
    learning_engine_ready: bool = False
    
    daily_pnl: float = 0.0
    account_balance: float = 0.0
    open_positions: int = 0
    
    system_state: SystemState = SystemState.STOPPED
    uptime_seconds: float = 0.0
    trades_today: int = 0
    errors_today: int = 0
    last_error: str = ""
    
    cycle_count: int = 0
    last_cycle_time: float = 0.0

@dataclass 
class SentinelConfig:
    """Sentinel configuration."""
    # Trading loop
    cycle_seconds: int = 15                  # Main loop interval
    health_check_seconds: int = 30           # Health monitor interval
    position_check_seconds: int = 10         # Position monitor interval
    obsidian_update_seconds: int = 300       # Status update interval (5 min)
    
    # Market hours (Central Time — TopStepX runs CT)
    market_open_hour: int = 17               # 5:00 PM CT (Sunday)
    market_open_minute: int = 0
    market_close_hour: int = 16              # 4:00 PM CT (Friday)
    market_close_minute: int = 0
    
    # Safety
    max_market_data_stale_seconds: int = 60  # If no data for 60s, halt trading
    max_consecutive_errors: int = 5          # Halt after 5 consecutive errors
    
    # Contracts to trade
    contract_id: str = "CON.F.US.MNQM26"
    tick_size: float = 0.25
    tick_value: float = 0.50
```

## 4. Class Design

```python
class Sentinel:
    """
    Autonomous operations manager.
    
    Orchestrates all layers, runs the main trading loop,
    monitors health, and handles recovery.
    """
    
    def __init__(self, config: SentinelConfig | None = None):
        """Initialize the sentinel with configuration."""
    
    # --- Lifecycle ---
    
    async def start(self) -> None:
        """
        Start the full system.
        
        1. Load all configs (broker, risk, decision, sentinel)
        2. Create and connect BrokerClient
        3. Verify account health (balance, canTrade)
        4. Look up the contract ID and verify it's active
        5. Create MarketDataPipeline and start WebSocket
        6. Wait for first market data (up to 30s timeout)
        7. Create RiskGuardian
        8. Create DecisionEngine
        9. Create LearningEngine (load history)
        10. Start background tasks (health monitor, position monitor)
        11. Enter main trading loop
        """
    
    async def stop(self) -> None:
        """
        Gracefully shut down.
        
        1. Set state to SHUTTING_DOWN
        2. Cancel background tasks
        3. Stop market data pipeline
        4. Check for open positions — log warning if any remain
        5. Save learning engine state
        6. Write final status to Obsidian
        7. Disconnect broker
        8. Set state to STOPPED
        """
    
    # --- Main Loop ---
    
    async def _trading_loop(self) -> None:
        """
        The main trading loop. Runs every cycle_seconds.
        
        Each cycle:
        1. Check system state — skip if not RUNNING
        2. Check market data freshness — halt if stale
        3. Get MarketSnapshot from Layer 2
        4. Run DecisionEngine.analyze(snapshot)
        5. If TradeIntent returned:
           a. Convert to TradeRequest
           b. Run Guardian.evaluate(request)
           c. If approved: run Guardian.execute(request, decision)
           d. Log the trade to LearningEngine
        6. Check open positions for closed trades
        7. Update cycle stats
        """
    
    # --- Position Monitoring ---
    
    async def _position_monitor(self) -> None:
        """
        Background task: monitor open positions every position_check_seconds.
        
        Checks:
        - Are positions still open on the broker?
        - If a position closed (TP/SL hit), record it via LearningEngine
        - If a position has no brackets, log ERROR (should never happen with Guardian)
        """
    
    async def _detect_closed_trades(self) -> None:
        """
        Compare current broker positions against last known positions.
        When a position disappears, it was closed (TP, SL, or manual).
        Query trade history to get the exit details and record in learning engine.
        """
    
    # --- Health Monitoring ---
    
    async def _health_monitor(self) -> None:
        """
        Background task: check system health every health_check_seconds.
        
        Checks:
        - Broker connectivity (ping)
        - Market data freshness (seconds since last update)
        - Daily PnL (from broker)
        - Account balance
        
        Actions:
        - If broker unreachable: try reconnect, set DEGRADED
        - If market data stale: set DEGRADED, halt trading
        - If daily PnL < -daily_loss_limit: set TRADING_HALTED
        - If balance near ruin (circuit breaker): set TRADING_HALTED
        - If max_consecutive_errors exceeded: set TRADING_HALTED
        """
    
    # --- Obsidian Updates ---
    
    async def _obsidian_status_update(self) -> None:
        """
        Background task: write system status to Obsidian every obsidian_update_seconds.
        
        Updates SOVEREIGN_COMMAND_CENTER.md with:
        - Current system state
        - Uptime
        - Daily PnL
        - Trades today
        - Open positions
        - Component health
        - Last error (if any)
        """
    
    def _write_obsidian_status(self, health: HealthStatus) -> None:
        """Write the health status to the Obsidian vault."""
    
    # --- Helpers ---
    
    def get_health(self) -> HealthStatus:
        """Return current system health."""
    
    def _is_market_open(self) -> bool:
        """Check if the futures market is currently open (Sun 5pm - Fri 4pm CT)."""
    
    def _intent_to_request(self, intent, snapshot) -> 'TradeRequest':
        """Convert a TradeIntent from Layer 3 to a TradeRequest for Layer 1."""
```

## 5. Entry Point (`run.py`)

```python
\"\"\"
Sovran v2 — Autonomous AI Futures Trading System
Entry point. Run this to start the system.

Usage:
    python run.py
    python run.py --contract MNQ
    python run.py --dry-run (no real orders)
\"\"\"
import asyncio
import argparse
import signal
import logging
from src.sentinel import Sentinel, SentinelConfig

def main():
    parser = argparse.ArgumentParser(description="Sovran v2 Trading System")
    parser.add_argument("--contract", default="CON.F.US.MNQM26", help="Contract ID to trade")
    parser.add_argument("--cycle", type=int, default=15, help="Main loop cycle seconds")
    parser.add_argument("--dry-run", action="store_true", help="Run without placing real orders")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    config = SentinelConfig(
        contract_id=args.contract,
        cycle_seconds=args.cycle,
    )
    
    sentinel = Sentinel(config=config)
    
    # Graceful shutdown on Ctrl+C
    def handle_signal(sig, frame):
        logging.info("Shutdown signal received")
        asyncio.get_event_loop().create_task(sentinel.stop())
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    asyncio.run(sentinel.start())

if __name__ == "__main__":
    main()
```

## 6. Test Requirements

### Unit Tests
- `test_market_hours_weekday_open` — Tuesday 2pm CT → market open
- `test_market_hours_weekday_closed` — Friday 4:30pm CT → market closed
- `test_market_hours_sunday_evening` — Sunday 5:30pm CT → market open
- `test_market_hours_saturday` — Saturday noon → market closed
- `test_health_status_creation` — verify default health status
- `test_intent_to_request_conversion` — TradeIntent → TradeRequest with correct fields
- `test_system_state_transitions` — STARTING → RUNNING → TRADING_HALTED → RUNNING
- `test_consecutive_error_tracking` — errors counted, max triggers halt

### Integration Tests (mocked broker/market)
- `test_startup_sequence` — verify all components initialized in order
- `test_trading_cycle_with_trade` — mock snapshot + intent → trade placed
- `test_trading_cycle_no_trade` — mock snapshot, no intent → no trade
- `test_daily_limit_halts_trading` — PnL at limit → state changes to HALTED
- `test_stale_data_halts_trading` — market data stale → state changes to DEGRADED
- `test_graceful_shutdown` — stop() cleans up all components
- `test_obsidian_status_write` — verify status written to file
- `test_closed_trade_detection` — position disappears → learning engine called

## 7. Acceptance Criteria

- [ ] System starts up and connects all layers in correct order
- [ ] Main trading loop cycles every N seconds
- [ ] TradeIntents from Layer 3 flow through Layer 1 to broker
- [ ] Closed trades are detected and recorded in Layer 4
- [ ] Daily PnL limit halts trading when hit
- [ ] Stale market data halts trading
- [ ] Health monitor tracks all component states
- [ ] Obsidian status is updated periodically
- [ ] Graceful shutdown stops all components
- [ ] Ctrl+C triggers graceful shutdown
- [ ] Market hours detection is correct for CME futures
- [ ] All unit tests pass (8+)
- [ ] All integration tests pass (8+)
- [ ] No `except: pass`
- [ ] Code is under 450 lines (sentinel.py) + 60 lines (run.py)

---
#specification #layer-5 #sentinel #autonomous #coding-agent
