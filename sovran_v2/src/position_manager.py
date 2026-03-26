"""
Position Manager — Active Trade Monitoring and Exit Control

After a trade is placed, the PositionManager takes over:
  1. Subscribes to live market data for the traded contract
  2. Runs a 5-second evaluation loop while the position is open
  3. Evaluates exit conditions (rule-based + AI-driven)
  4. Can close early via broker.close_position() or modify stops
  5. Reports outcomes to the LearningEngine

Exit conditions:
  - Trail stop to breakeven at +50% of target
  - Close if VPIN > 0.7 (toxic flow)
  - Close if OFI Z-score flips from entry direction
  - Close if unrealized PnL < -max_adverse_excursion
  - AI-driven hold/trail/close every ai_eval_interval seconds
  - Time-based exit if position held > max_hold_seconds with no progress
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

from src.broker import BrokerClient, BrokerError
from src.market_data import MarketDataPipeline, MarketSnapshot
from src.decision import DecisionEngine
from src.risk import TradeSide


class ExitReason(Enum):
    TARGET_HIT = "target_hit"
    STOP_HIT = "stop_hit"
    TRAIL_STOP = "trail_stop"
    VPIN_TOXIC = "vpin_toxic"
    OFI_FLIP = "ofi_flip"
    AI_DECISION = "ai_decision"
    TIME_EXPIRED = "time_expired"
    MANUAL_CLOSE = "manual_close"
    BRACKET_CLOSED = "bracket_closed"
    ERROR = "error"


@dataclass
class PositionState:
    """Tracks the lifecycle of a monitored position."""
    contract_id: str
    side: str                     # "long" or "short"
    entry_price: float
    entry_time: float
    size: int
    target_price: float
    stop_price: float
    thesis: str
    conviction: float
    frameworks: List[str] = field(default_factory=list)

    # Tracking (updated by the monitor loop)
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    max_favorable_excursion: float = 0.0   # Best unrealized PnL seen
    max_adverse_excursion: float = 0.0     # Worst unrealized PnL seen
    trail_stop_active: bool = False
    trail_stop_price: float = 0.0

    # Contextual state at entry
    entry_vpin: float = 0.0
    entry_ofi_zscore: float = 0.0
    entry_regime: str = "unknown"
    entry_atr: float = 0.0

    # Exit state
    exit_price: float = 0.0
    exit_time: float = 0.0
    exit_reason: str = ""
    pnl: float = 0.0
    is_closed: bool = False


@dataclass
class PositionManagerConfig:
    """Configuration for the position manager."""
    check_interval_seconds: float = 5.0     # How often to evaluate
    ai_eval_interval_seconds: float = 30.0  # How often to ask AI for hold/trail/close
    max_hold_seconds: float = 3600.0        # 1 hour max hold
    vpin_exit_threshold: float = 0.7        # Close if VPIN > this
    trail_trigger_pct: float = 0.50         # Trail stop at 50% of target
    trail_offset_pct: float = 0.25          # Trail stop offset (25% of target distance)
    time_exit_no_progress_seconds: float = 600.0  # Exit if no progress after 10 min
    ofi_flip_threshold: float = -1.5        # OFI Z-score flip threshold
    state_dir: str = "state"


class PositionManager:
    """
    Active position monitoring and exit management.

    The PositionManager is given control after a trade is placed.
    It runs a continuous evaluation loop until the position is closed,
    then returns the outcome for learning.

    Can operate in two modes:
      1. Rule-based: checks VPIN, OFI, trailing stop, time
      2. AI-assisted: periodically asks the AI brain for hold/trail/close

    Both modes run concurrently — rules provide safety net, AI provides alpha.
    """

    def __init__(
        self,
        broker: BrokerClient,
        decision_engine: Optional[DecisionEngine] = None,
        config: Optional[PositionManagerConfig] = None,
    ):
        self.broker = broker
        self.decision_engine = decision_engine
        self.config = config or PositionManagerConfig()
        self.logger = logging.getLogger("sovran.position_manager")

        self._active_positions: Dict[str, PositionState] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}

    async def monitor_position(
        self,
        contract_id: str,
        side: str,
        entry_price: float,
        size: int,
        target_price: float,
        stop_price: float,
        thesis: str,
        conviction: float,
        frameworks: List[str],
        pipeline: MarketDataPipeline,
        snapshot: Optional[MarketSnapshot] = None,
        tick_value: float = 0.50,
        tick_size: float = 0.25,
    ) -> PositionState:
        """
        Monitor a position until it closes.

        This is the main entry point. Call after placing a trade.
        Returns the final PositionState with exit details.
        """
        state = PositionState(
            contract_id=contract_id,
            side=side,
            entry_price=entry_price,
            entry_time=time.time(),
            size=size,
            target_price=target_price,
            stop_price=stop_price,
            thesis=thesis,
            conviction=conviction,
            frameworks=frameworks,
            current_price=entry_price,
            entry_vpin=snapshot.vpin if snapshot else 0.0,
            entry_ofi_zscore=snapshot.ofi_zscore if snapshot else 0.0,
            entry_regime=snapshot.regime.value if snapshot else "unknown",
            entry_atr=snapshot.atr_points if snapshot else 0.0,
        )

        self._active_positions[contract_id] = state
        self.logger.info(
            f"MONITOR START [{contract_id}] {side.upper()} x{size} @ {entry_price:.2f} "
            f"SL={stop_price:.2f} TP={target_price:.2f}"
        )

        last_ai_eval = 0.0
        check_count = 0

        try:
            while not state.is_closed:
                await asyncio.sleep(self.config.check_interval_seconds)
                check_count += 1

                # 1. Check if broker still has the position (SL/TP bracket may have closed it)
                broker_positions = await self.broker.get_open_positions()
                pos_open = any(p["contractId"] == contract_id for p in broker_positions)

                if not pos_open:
                    # Position was closed by bracket or externally
                    state.is_closed = True
                    state.exit_time = time.time()
                    state.exit_reason = ExitReason.BRACKET_CLOSED.value
                    state.exit_price = state.current_price
                    self.logger.info(
                        f"POSITION CLOSED by bracket [{contract_id}] — "
                        f"likely SL/TP hit"
                    )
                    break

                # 2. Get current market data
                try:
                    snap = pipeline.get_snapshot()
                    state.current_price = snap.last_price
                except Exception as e:
                    self.logger.warning(f"Snapshot error during monitoring: {e}")
                    continue

                # 3. Calculate unrealized PnL
                if side == "long":
                    price_diff = snap.last_price - entry_price
                else:
                    price_diff = entry_price - snap.last_price
                ticks_diff = price_diff / tick_size
                state.unrealized_pnl = ticks_diff * tick_value * size

                # Track excursions
                if state.unrealized_pnl > state.max_favorable_excursion:
                    state.max_favorable_excursion = state.unrealized_pnl
                if state.unrealized_pnl < state.max_adverse_excursion:
                    state.max_adverse_excursion = state.unrealized_pnl

                # 4. Rule-based exit conditions
                exit_reason = self._evaluate_rules(state, snap)
                if exit_reason:
                    self.logger.info(
                        f"RULE EXIT [{contract_id}]: {exit_reason.value} "
                        f"PnL=${state.unrealized_pnl:.2f}"
                    )
                    await self._close_position(state, exit_reason, snap)
                    break

                # 5. Trailing stop management
                self._update_trailing_stop(state, snap, tick_size, tick_value)

                # 6. AI-driven evaluation (periodically)
                now = time.time()
                if (self.decision_engine and
                    now - last_ai_eval >= self.config.ai_eval_interval_seconds):
                    last_ai_eval = now
                    ai_action = await self._ai_evaluate(state, snap)
                    if ai_action == "close":
                        self.logger.info(
                            f"AI EXIT [{contract_id}]: AI recommends closing. "
                            f"PnL=${state.unrealized_pnl:.2f}"
                        )
                        await self._close_position(state, ExitReason.AI_DECISION, snap)
                        break

                # Log periodic status
                if check_count % 12 == 0:  # ~every minute
                    hold_time = now - state.entry_time
                    self.logger.info(
                        f"POSITION [{contract_id}] {side.upper()} "
                        f"held={hold_time:.0f}s PnL=${state.unrealized_pnl:.2f} "
                        f"MFE=${state.max_favorable_excursion:.2f} "
                        f"MAE=${state.max_adverse_excursion:.2f} "
                        f"VPIN={snap.vpin:.3f} OFI={snap.ofi_zscore:.2f} "
                        f"trail={'ON' if state.trail_stop_active else 'OFF'}"
                    )

        except asyncio.CancelledError:
            self.logger.warning(f"Monitor cancelled for {contract_id}")
            state.exit_reason = ExitReason.MANUAL_CLOSE.value
        except Exception as e:
            self.logger.error(f"Monitor error for {contract_id}: {e}", exc_info=True)
            state.exit_reason = ExitReason.ERROR.value
        finally:
            state.is_closed = True
            state.exit_time = state.exit_time or time.time()
            self._active_positions.pop(contract_id, None)

            # Compute final PnL from broker trades
            state.pnl = await self._compute_trade_pnl(contract_id, state.entry_time)
            self._save_trade_outcome(state)

        return state

    def _evaluate_rules(self, state: PositionState, snap: MarketSnapshot) -> Optional[ExitReason]:
        """Evaluate rule-based exit conditions. Returns ExitReason or None."""
        now = time.time()
        hold_seconds = now - state.entry_time

        # VPIN toxic flow — exit immediately
        if snap.vpin > self.config.vpin_exit_threshold:
            self.logger.info(f"VPIN toxic: {snap.vpin:.3f} > {self.config.vpin_exit_threshold}")
            return ExitReason.VPIN_TOXIC

        # OFI Z-score flip — thesis invalidated
        if state.side == "long" and snap.ofi_zscore < self.config.ofi_flip_threshold:
            self.logger.info(f"OFI flip (long): Z={snap.ofi_zscore:.2f} < {self.config.ofi_flip_threshold}")
            return ExitReason.OFI_FLIP
        if state.side == "short" and snap.ofi_zscore > -self.config.ofi_flip_threshold:
            self.logger.info(f"OFI flip (short): Z={snap.ofi_zscore:.2f} > {-self.config.ofi_flip_threshold}")
            return ExitReason.OFI_FLIP

        # Time-based exit: held too long with no progress
        if hold_seconds > self.config.time_exit_no_progress_seconds:
            # "No progress" = unrealized PnL is within 25% of zero (basically flat)
            target_distance_dollars = abs(state.unrealized_pnl)
            if state.max_favorable_excursion < 5.0:  # Never moved in our favor
                self.logger.info(f"Time exit: held {hold_seconds:.0f}s with no progress")
                return ExitReason.TIME_EXPIRED

        # Hard max hold time
        if hold_seconds > self.config.max_hold_seconds:
            return ExitReason.TIME_EXPIRED

        # Trailing stop hit (if active)
        if state.trail_stop_active:
            if state.side == "long" and snap.last_price <= state.trail_stop_price:
                return ExitReason.TRAIL_STOP
            if state.side == "short" and snap.last_price >= state.trail_stop_price:
                return ExitReason.TRAIL_STOP

        return None

    def _update_trailing_stop(
        self, state: PositionState, snap: MarketSnapshot,
        tick_size: float, tick_value: float
    ) -> None:
        """Manage trailing stop logic.

        Activates at +50% of target distance. Once active, trails at entry +25% of target.
        """
        if state.side == "long":
            target_distance = state.target_price - state.entry_price
            progress = snap.last_price - state.entry_price
        else:
            target_distance = state.entry_price - state.target_price
            progress = state.entry_price - snap.last_price

        if target_distance <= 0:
            return

        progress_pct = progress / target_distance

        if progress_pct >= self.config.trail_trigger_pct and not state.trail_stop_active:
            # Activate trailing stop at breakeven + offset
            offset = target_distance * self.config.trail_offset_pct
            if state.side == "long":
                state.trail_stop_price = state.entry_price + offset
            else:
                state.trail_stop_price = state.entry_price - offset
            state.trail_stop_active = True
            self.logger.info(
                f"TRAIL STOP activated [{state.contract_id}]: "
                f"price={snap.last_price:.2f} trail_stop={state.trail_stop_price:.2f} "
                f"(progress={progress_pct:.0%})"
            )

        elif state.trail_stop_active:
            # Ratchet the trail — never move it backward
            offset = target_distance * self.config.trail_offset_pct
            if state.side == "long":
                new_trail = snap.last_price - offset
                if new_trail > state.trail_stop_price:
                    state.trail_stop_price = new_trail
            else:
                new_trail = snap.last_price + offset
                if new_trail < state.trail_stop_price:
                    state.trail_stop_price = new_trail

    async def _ai_evaluate(self, state: PositionState, snap: MarketSnapshot) -> str:
        """Ask the AI whether to hold, trail, or close.

        Uses the file IPC system (or whatever backend is configured).
        Returns: "hold", "trail", or "close"
        """
        if not self.decision_engine:
            return "hold"

        hold_seconds = time.time() - state.entry_time
        prompt = f"""You are managing an OPEN position. Evaluate whether to HOLD, TRAIL STOP, or CLOSE.

## OPEN POSITION
- Contract: {state.contract_id}
- Side: {state.side.upper()}
- Entry Price: {state.entry_price:.2f}
- Current Price: {snap.last_price:.2f}
- Unrealized PnL: ${state.unrealized_pnl:.2f}
- Max Favorable Excursion: ${state.max_favorable_excursion:.2f}
- Max Adverse Excursion: ${state.max_adverse_excursion:.2f}
- Hold Time: {hold_seconds:.0f} seconds
- Original Thesis: {state.thesis}
- Target Price: {state.target_price:.2f}
- Stop Price: {state.stop_price:.2f}
- Trail Stop Active: {state.trail_stop_active} ({state.trail_stop_price:.2f})

## CURRENT MARKET CONDITIONS
- Best Bid / Ask: {snap.best_bid:.2f} / {snap.best_ask:.2f}
- ATR: {snap.atr_points:.4f}
- VPIN: {snap.vpin:.4f} (>0.7 toxic)
- OFI Z-score: {snap.ofi_zscore:.4f}
- Bid/Ask Imbalance: {snap.bid_ask_imbalance:.4f}
- Regime: {snap.regime.value}
- Trend Strength: {snap.trend_strength:.1f}

## CONDITIONS AT ENTRY
- VPIN at entry: {state.entry_vpin:.4f}
- OFI Z at entry: {state.entry_ofi_zscore:.4f}
- Regime at entry: {state.entry_regime}

## YOUR TASK
Respond with JSON only:
{{"action": "hold" | "trail" | "close", "reasoning": "<1-2 sentences>"}}
"""
        try:
            if hasattr(self.decision_engine, '_backend'):
                raw = await self.decision_engine._backend.call(prompt)
                action = str(raw.get("action", "hold")).lower().strip()
                reasoning = raw.get("reasoning", "")
                self.logger.info(f"AI position eval [{state.contract_id}]: {action} — {reasoning}")
                if action in ("close", "trail", "hold"):
                    return action
        except Exception as e:
            self.logger.warning(f"AI position eval failed: {e}")

        return "hold"

    async def _close_position(
        self, state: PositionState, reason: ExitReason, snap: MarketSnapshot
    ) -> None:
        """Close the position via the broker."""
        try:
            await self.broker.close_position(state.contract_id)
            state.is_closed = True
            state.exit_price = snap.last_price
            state.exit_time = time.time()
            state.exit_reason = reason.value
            self.logger.info(
                f"CLOSED [{state.contract_id}] reason={reason.value} "
                f"exit_price={snap.last_price:.2f} PnL=${state.unrealized_pnl:.2f}"
            )
        except BrokerError as e:
            self.logger.error(f"Failed to close {state.contract_id}: {e}")
            # Position may have already been closed by bracket
            state.exit_reason = ExitReason.ERROR.value

    async def _compute_trade_pnl(self, contract_id: str, since: float) -> float:
        """Compute realized PnL for a contract from broker trades."""
        try:
            start_iso = datetime.fromtimestamp(since, tz=timezone.utc).isoformat()
            trades = await self.broker.get_trades(start_iso)
            relevant = [t for t in trades if t.get("contractId") == contract_id and not t.get("voided")]
            return sum(float(t.get("profitAndLoss") or 0.0) for t in relevant)
        except Exception as e:
            self.logger.error(f"PnL computation error: {e}")
            return 0.0

    def _save_trade_outcome(self, state: PositionState) -> None:
        """Persist trade outcome to state/trade_history.json for learning feedback."""
        os.makedirs(self.config.state_dir, exist_ok=True)
        path = os.path.join(self.config.state_dir, "trade_history.json")

        outcome = {
            "contract_id": state.contract_id,
            "side": state.side,
            "entry_price": state.entry_price,
            "exit_price": state.exit_price,
            "entry_time": state.entry_time,
            "exit_time": state.exit_time,
            "size": state.size,
            "pnl": state.pnl,
            "unrealized_pnl_at_close": state.unrealized_pnl,
            "max_favorable_excursion": state.max_favorable_excursion,
            "max_adverse_excursion": state.max_adverse_excursion,
            "exit_reason": state.exit_reason,
            "thesis": state.thesis,
            "conviction": state.conviction,
            "frameworks": state.frameworks,
            "hold_seconds": state.exit_time - state.entry_time,
            "entry_vpin": state.entry_vpin,
            "entry_ofi_zscore": state.entry_ofi_zscore,
            "entry_regime": state.entry_regime,
            "entry_atr": state.entry_atr,
            "trail_stop_was_active": state.trail_stop_active,
        }

        # Append to history
        history = []
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    history = json.load(f)
            except Exception:
                history = []

        history.append(outcome)

        # Keep last 200 trades
        if len(history) > 200:
            history = history[-200:]

        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(history, f, indent=2)
        os.replace(tmp, path)

    @property
    def active_positions(self) -> Dict[str, PositionState]:
        return self._active_positions

    def has_position(self, contract_id: str) -> bool:
        return contract_id in self._active_positions
