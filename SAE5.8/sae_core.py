# sae_core.py
# The Functional Core: Pure Logic, No Side Effects.
from decimal import Decimal, getcontext
from dataclasses import dataclass, replace
from typing import Optional, Any, List, Tuple, Dict, Deque, Callable
from collections import deque
import datetime
import time
import pytz
import asyncio
import functools
import random
import os
import json
import numpy as np
from numpy.typing import NDArray
from sae_config import config

# GD: Increased precision to 50. Micro contracts like MGC 
# ($0.10 ticks) and potentially FX micros ($0.00005 ticks) require extreme precision 
# when calculating moving averages and standard deviations to avoid rounding errors.
getcontext().prec = 50

def exponential_backoff(max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 30.0):
    """
    Decorator for institutional-grade exponential backoff with jitter.
    Useful for REST API calls and database reconnections.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    
                    delay = min(base_delay * (2 ** (retries - 1)), max_delay)
                    jitter = delay * 0.2 * random.random()
                    total_delay = delay + jitter
                    
                    # Log the retry (Institutional Observability)
                    print(f" [RETRY] {func.__name__} failed: {e}. Retrying in {total_delay:.2f}s (Attempt {retries}/{max_retries})")
                    await asyncio.sleep(total_delay)
            return None
        return wrapper
    return decorator

@dataclass(frozen=True)
class PriceState:
    """Tracks running statistics for a ticker price feed."""
    ticker: str
    count: int
    last_price: Decimal
    sum_price: Decimal
    sum_sq_price: Decimal
    prev_sma: Decimal

    @property
    def std_dev(self) -> Decimal:
        """Calculate population standard deviation."""
        if self.count < 2: return Decimal("0.0")
        variance = (self.sum_sq_price / Decimal(self.count)) - ((self.sum_price / Decimal(self.count)) ** 2)
        return abs(variance).sqrt() if variance != 0 else Decimal("0.0")

@dataclass(frozen=True)
class MacroState:
    """Captures high-level market environment and sentiment."""
    inflation_rate: Decimal
    interest_rate: Decimal
    sentiment: str
    liquidity_crisis: bool
    retail_sentiment: Decimal = Decimal("0.5")
    strategic_posture: str = "STABLE"
    verdict: str = "NEUTRAL"

    @property
    def real_rate(self) -> Decimal:
        """Calculate the real interest rate (Nominal - Inflation)."""
        return self.interest_rate - self.inflation_rate

from sae_fast_math import update_kalman_fast, calculate_vpin_fast

# --- VPIN Toxicity Filter (SAE 5.8 Step 2) ---
class VPIN:
    """
    Volume-Synchronized Probability of Informed Trading.
    Measures toxic flow (information asymmetry) to filter unprofitable trading periods.
    Accelerated with Numba JIT (Phase 6).
    """
    def __init__(self, bucket_size: int = 5000, n_buckets: int = 50) -> None:
        self.bucket_size: int = bucket_size
        self.n_buckets: int = n_buckets
        self.current_bucket_buy_vol: int = 0
        self.current_bucket_sell_vol: int = 0
        self.current_bucket_vol: int = 0
        self.imbalances = np.zeros(n_buckets, dtype=np.float64)
        self.vpin_value: float = 0.0
        self._count = 0

    def update(self, trade: Any) -> float:
        """Update VPIN with new trade. Returns current VPIN value."""
        remaining_size: int = trade.size
        side: str = trade.aggressor_side

        while remaining_size > 0:
            space_in_bucket: int = self.bucket_size - self.current_bucket_vol
            fill_amount: int = min(remaining_size, space_in_bucket)

            if side == "Buy":
                self.current_bucket_buy_vol += fill_amount
            elif side == "Sell":
                self.current_bucket_sell_vol += fill_amount

            self.current_bucket_vol += fill_amount
            remaining_size -= fill_amount

            # Bucket full - calculate imbalance and reset
            if self.current_bucket_vol >= self.bucket_size:
                imb: int = abs(self.current_bucket_buy_vol - self.current_bucket_sell_vol)
                
                # Manual window management for Numba compatibility
                self.imbalances = np.roll(self.imbalances, -1)
                self.imbalances[-1] = float(imb)
                self._count = min(self._count + 1, self.n_buckets)

                # Use Fast Math
                if self._count > 0:
                    self.vpin_value = calculate_vpin_fast(self.imbalances[-self._count:], self.n_buckets, self.bucket_size)

                # Reset bucket
                self.current_bucket_buy_vol = 0
                self.current_bucket_sell_vol = 0
                self.current_bucket_vol = 0

        return self.vpin_value

    def is_toxic(self, threshold: float = 0.70) -> bool:
        """Check if current market conditions are toxic (high information asymmetry)."""
        return self.vpin_value > threshold

from sae_fast_math import update_kalman_fast

class SaeKalmanFilter:
    """
    Institutional Noise Reduction (Accelerated).
    Uses Numba-JIT hot loops to find the 'True' price velocity.
    """
    def __init__(self, **kwargs):
        # Support flexible initialization for brain fleet compatibility
        self.q = kwargs.get('q', kwargs.get('process_variance', 1e-5))
        self.r = kwargs.get('r', kwargs.get('measurement_variance', 0.01))
        self.x = 0.0
        self.p = 1.0
        self.is_initialized = False

    def update(self, measurement: float) -> Tuple[float, float]:
        if not self.is_initialized:
            self.x = measurement
            self.is_initialized = True
            return self.x, 0.0
            
        old_x = self.x
        self.x, self.p = update_kalman_fast(self.x, self.p, measurement, self.q, self.r)
        
        # Calculate velocity (first derivative)
        velocity = self.x - old_x
        return self.x, velocity

# --- Order Lifecycle FSM ---
ORDER_STATES = ("PENDING_NEW", "WORKING", "FILLED", "PARTIALLY_FILLED", "REJECTED", "RISK_REJECTED", "CANCELED")

class DynamicLockoutManager:
    """
    Institutional Risk Guard: Exponential Lockout.
    Increases cooldown duration after consecutive losses.
    """
    def __init__(self, base_seconds: int = 300, multiplier: float = 1.5):
        self.base = base_seconds
        self.multiplier = multiplier
        self.loss_count = 0
        self.last_loss_ts = 0.0

    def record_result(self, pnl: float, ts: float):
        if pnl < 0:
            self.loss_count += 1
            self.last_loss_ts = ts
        else:
            self.loss_count = 0

    def is_locked(self, current_ts: float) -> bool:
        if self.loss_count == 0: return False
        duration = self.base * (self.multiplier ** (self.loss_count - 1))
        # Cap at 30 minutes
        duration = min(duration, 1800)
        return (current_ts - self.last_loss_ts) < duration
class DynamicLockoutManager:
    """
    Institutional Risk Guard: Exponential Lockout.
    Increases cooldown duration after consecutive losses.
    """
    def __init__(self, base_seconds: int = 300, multiplier: float = 1.5):
        self.base = base_seconds
        self.multiplier = multiplier
        self.loss_count = 0
        self.last_loss_ts = 0.0

    def record_result(self, pnl: float, ts: float):
        if pnl < 0:
            self.loss_count += 1
            self.last_loss_ts = ts
        else:
            self.loss_count = 0

    def is_locked(self, current_ts: float) -> bool:
        if self.loss_count == 0: return False
        duration = self.base * (self.multiplier ** (self.loss_count - 1))
        # Cap at 30 minutes
        duration = min(duration, 1800)
        return (current_ts - self.last_loss_ts) < duration

def evolve_order(current_status: str, event: str) -> str:
    """
    Finite State Machine for order lifecycle transitions.
    
    Args:
        current_status: Current state of the order
        event: Event triggering the transition
        
    Returns:
        The next status string
    """
    transitions = {
        ("PENDING_NEW", "SENT"): "WORKING",
        ("WORKING", "FILL"): "FILLED",
        ("WORKING", "PARTIAL_FILL"): "PARTIALLY_FILLED",
        ("PARTIALLY_FILLED", "FILL"): "FILLED",
        ("WORKING", "REJECT"): "REJECTED",
        ("PENDING_NEW", "RISK_BLOCK"): "RISK_REJECTED",
        ("WORKING", "CANCEL"): "CANCELED",
        ("PENDING_NEW", "REJECT"): "REJECTED"
    }
    return transitions.get((current_status, event), current_status)

def update_price_state(state: PriceState, new_price: Decimal) -> PriceState:
    """
    Update PriceState with a new price point using Welford-style accumulation.
    
    Args:
        state: Current PriceState
        new_price: New price to incorporate
        
    Returns:
        Updated PriceState object
    """
    return replace(state,
        count=state.count + 1,
        last_price=new_price,
        sum_price=state.sum_price + new_price,
        sum_sq_price=state.sum_sq_price + (new_price ** 2),
        prev_sma=(state.sum_price / Decimal(state.count)) if state.count > 0 else Decimal("0.0")
    )

def validate_risk(signal: Dict[str, Any], open_positions: List[Dict[str, Any]], daily_pnl: Decimal, risk_config: Dict[str, Any], macro: Optional[MacroState] = None) -> bool:
    """
    Validate if a signal meets portfolio-level risk requirements.
    
    Args:
        signal: Proposed trade signal
        open_positions: List of currently open positions
        daily_pnl: Realized + Unrealized PnL for the current session
        risk_config: Dictionary containing risk limits
        macro: Current MacroState (optional)
        
    Returns:
        True if signal is valid, False otherwise
    """
    if not signal: return False

    # 1. Hard Daily Limit Check
    limit = Decimal(str(risk_config.get('daily_loss_limit', risk_config.get('limit', -1000))))
    if daily_pnl <= limit:
        return False

    # 2. Daily Profit Target
    if daily_pnl >= Decimal(str(risk_config.get('daily_profit_target', risk_config.get('target', 2000)))):
        return False

    # 3. Max Contracts
    if len(open_positions) >= risk_config.get('max_contracts', 15):
        return False

    # 4. Correlation/Exposure Check
    longs = sum(1 for p in open_positions if p['direction'] == "Long")
    shorts = sum(1 for p in open_positions if p['direction'] == "Short")
    # TopstepX: max 15 contracts per direction
    if signal['direction'] == "Long" and longs >= risk_config.get('max_longs', 15): return False
    if signal['direction'] == "Short" and shorts >= risk_config.get('max_shorts', 15): return False

    # 5. TopstepX Compliance: Ticker Universe
    approved_tickers = ['MNQ', 'MES', 'M2K', 'MYM', 'MGC', 'MCL']
    if signal['ticker'] not in approved_tickers:
        return False

    # 6. TopstepX Compliance: Position Size (no pyramiding)
    if signal['size'] != 1:
        return False

    # 7. TopstepX Compliance: Stacking Rule (Max 3 contracts in same direction per ticker)
    ticker_direction_count = sum(1 for p in open_positions if p['ticker'] == signal['ticker'] and p['direction'] == signal['direction'])
    if ticker_direction_count >= 3:
        return False

    return True

def allocate_contracts(brain_name: str, brain_allocations: Dict[str, int], open_positions: List[Dict[str, Any]]) -> int:
    """
    Determine available contract capacity for a specific brain.
    
    Args:
        brain_name: Name of the brain requesting allocation
        brain_allocations: Mapping of brain names to maximum allowed contracts
        open_positions: Current list of open positions
        
    Returns:
        Number of available contracts
    """
    max_contracts = brain_allocations.get(brain_name, 0)
    if max_contracts == 0: return 0
    # Sum the actual number of contracts (size) for all trades from this brain
    current_contract_count = sum(pos.get('size', 1) for pos in open_positions if pos.get('brain') == brain_name)
    return max(0, max_contracts - current_contract_count)

# --- Institutional Filters (SAE 5.8 Phase 4) ---
class ADXFilter:
    def __init__(self, length: int = 14):
        self.length = length
        self.history = deque(maxlen=200)
        self.prev_px = None
        self.tr_smooth = 0.0
        self.pdm_smooth = 0.0
        self.mdm_smooth = 0.0
        self.prev_adx = 0.0
        self.tick_count = 0

    def update(self, price: float) -> Tuple[float, float, float]:
        """Returns (ADX, Plus_DI, Minus_DI)"""
        if self.prev_px is None:
            self.prev_px = price
            return 0.0, 0.0, 0.0
            
        tr = abs(price - self.prev_px)
        up_move = price - self.prev_px
        down_move = self.prev_px - price
        
        p_dm = up_move if up_move > 0 and up_move > down_move else 0.0
        m_dm = down_move if down_move > 0 and down_move > up_move else 0.0
        self.prev_px = price
        self.tick_count += 1

        if self.tick_count <= self.length:
            self.tr_smooth += tr
            self.pdm_smooth += p_dm
            self.mdm_smooth += m_dm
            return 0.0, 0.0, 0.0

        # Wilder's Smoothing
        self.tr_smooth = self.tr_smooth - (self.tr_smooth / self.length) + tr
        self.pdm_smooth = self.pdm_smooth - (self.pdm_smooth / self.length) + p_dm
        self.mdm_smooth = self.mdm_smooth - (self.mdm_smooth / self.length) + m_dm
        
        if self.tr_smooth == 0: return 0.0, 0.0, 0.0
        
        p_di = (self.pdm_smooth / self.tr_smooth) * 100
        m_di = (self.mdm_smooth / self.tr_smooth) * 100
        
        dx = (abs(p_di - m_di) / (p_di + m_di) * 100) if (p_di + m_di) > 0 else 0
        
        if self.prev_adx == 0:
            self.prev_adx = dx
        else:
            self.prev_adx = (self.prev_adx * (self.length - 1) + dx) / self.length
            
        return self.prev_adx, p_di, m_di

class MFDFilter:
    """
    Elite Alpha: Money Flow Divergence (MFD).
    Logic: Compares Price momentum to Money Flow (Volume * Directional Price Change).
    Signals Reversals when Price and Money Flow decouple.
    """
    def __init__(self, window: int = 14):
        self.window = window
        self.price_history = deque(maxlen=window)
        self.mf_history = deque(maxlen=window) # Money Flow history
        self.last_price = None

    def update(self, price: float, volume: float) -> float:
        """
        Calculates MFD Score.
        Returns: 
          1.0: Bullish Divergence (Price Down, MF Up)
          -1.0: Bearish Divergence (Price Up, MF Down)
          0.0: Neutral
        """
        if self.last_price is None:
            self.last_price = price
            return 0.0
            
        typical_price = price # In futures, we use last_price as typical
        raw_mf = typical_price * volume
        
        if price > self.last_price:
            direction = 1
        elif price < self.last_price:
            direction = -1
        else:
            direction = 0
            
        directional_mf = raw_mf * direction
        self.mf_history.append(directional_mf)
        self.price_history.append(price)
        self.last_price = price
        
        if len(self.mf_history) < self.window:
            return 0.0
            
        # Cumulative Money Flow over window
        pos_mf = sum(x for x in self.mf_history if x > 0)
        neg_mf = abs(sum(x for x in self.mf_history if x < 0))
        
        mfr = pos_mf / neg_mf if neg_mf > 0 else 100.0
        mfi = 100 - (100 / (1 + mfr))
        
        # Divergence Logic
        # 1. Price is trending down (Last vs First in window)
        price_trend = self.price_history[-1] - self.price_history[0]
        # 2. MFI is trending up (Simplified)
        # We look for decoupling in signs
        
        # Bullish: Price Lower, but Money Flow accumulating (Positive MFI trend)
        if price_trend < 0 and mfi > 60: # Threshold for 'Strong MF'
            return 1.0
        # Bearish: Price Higher, but Money Flow exhausting (Negative MFI trend)
        if price_trend > 0 and mfi < 40: # Threshold for 'Weak MF'
            return -1.0
            
        return 0.0

class KalmanFilter:
    """
    Institutional noise reduction and velocity (momentum) estimator.
    Infers the hidden 'true' price and its current velocity from noisy ticks.
    """
    def __init__(self, process_noise: float = 1e-5, measurement_noise: float = 1e-3) -> None:
        self.q: float = process_noise
        self.r: float = measurement_noise
        self.x: float = 0.0 # State: [Price]
        self.v: float = 0.0 # State: [Velocity]
        self.p: NDArray[np.float64] = np.eye(2) # Error covariance
        self.f: NDArray[np.float64] = np.array([[1, 1], [0, 1]]) # State transition matrix
        self.h: NDArray[np.float64] = np.array([[1, 0]]) # Measurement function

    def update(self, observed_price: float) -> Tuple[float, float]:
        """Update filter with new price observation. Returns (smoothed_price, velocity)."""
        if self.x == 0.0:
            self.x = observed_price
            return self.x, 0.0

        # 1. Predict
        x_prior = self.f @ np.array([[self.x], [self.v]])
        p_prior = self.f @ self.p @ self.f.T + np.eye(2) * self.q

        # 2. Correct (Update)
        z = np.array([[observed_price]])
        y = z - self.h @ x_prior
        s = self.h @ p_prior @ self.h.T + self.r
        # Optimization: s is 1x1, use scalar division instead of np.linalg.inv
        k = (p_prior @ self.h.T) / s[0, 0]

        x_post = x_prior + k @ y
        self.p = (np.eye(2) - k @ self.h) @ p_prior
        
        self.x = float(x_post[0, 0])
        self.v = float(x_post[1, 0])
        
        return self.x, self.v

class CVDAbsorptionDetector:
    """
    Elite Alpha: Cumulative Volume Delta (CVD) Absorption.
    Identifies when aggressive buyers/sellers are being absorbed by passive walls.
    """
    def __init__(self, window: int = 50):
        self.window = window
        self.price_history: deque = deque(maxlen=window)
        self.cvd_history: deque = deque(maxlen=window)
        self.last_corr = 0.0
        self.tick_counter = 0

    def update(self, price: Decimal, cvd: Decimal) -> float:
        """
        Check for absorption.
        Returns: 1.0 (Bullish Absorption), -1.0 (Bearish), 0.0 (Neutral)
        """
        px = float(price)
        val_cvd = float(cvd)
        self.price_history.append(px)
        self.cvd_history.append(val_cvd)
        self.tick_counter += 1

        if len(self.price_history) < self.window:
            return 0.0

        # Optimization: Calculate correlation only every 10 ticks to save CPU
        if self.tick_counter % 10 == 0:
            corr_matrix = np.corrcoef(list(self.price_history), list(self.cvd_history))
            self.last_corr = corr_matrix[0, 1]
        
        corr = self.last_corr
        if np.isnan(corr): return 0.0
        
        delta_cvd = val_cvd - self.cvd_history[0]
        delta_px = px - self.price_history[0]
        
        # Bullish: CVD increasing (buying), but price stalled/falling + negative correlation
        if delta_cvd > 0 and delta_px <= 0 and corr < -0.5:
            return 1.0
        # Bearish: CVD decreasing (selling), but price stalled/rising + negative correlation
        if delta_cvd < 0 and delta_px >= 0 and corr < -0.5:
            return -1.0
            
        return 0.0

    def get_latest(self) -> float:
        """Returns the last calculated absorption score without updating history."""
        if len(self.price_history) < self.window:
            return 0.0
            
        corr_matrix = np.corrcoef(list(self.price_history), list(self.cvd_history))
        corr = corr_matrix[0, 1]
        
        if np.isnan(corr): return 0.0
        
        delta_cvd = float(self.cvd_history[-1]) - float(self.cvd_history[0])
        delta_px = float(self.price_history[-1]) - float(self.price_history[0])
        
        if delta_cvd > 0 and delta_px <= 0 and corr < -0.5:
            return 1.0
        if delta_cvd < 0 and delta_px >= 0 and corr < -0.5:
            return -1.0
            
        return 0.0

class MetaLabeler:
    """
    Institutional Secondary Model: Meta-Labeling (De Prado).
    Vets 'Primary' signals by comparing current market state to a database of wins/losses.
    """
    def __init__(self, feature_count: int = 4, memory_size: int = 500, storage_path: str = "metalabeler_db.json"):
        self.win_database: deque = deque(maxlen=memory_size)
        self.loss_database: deque = deque(maxlen=memory_size)
        self.feature_count: int = feature_count
        self.storage_path = os.path.join(os.path.dirname(__file__), storage_path)

    def save_to_disk(self):
        """Persists the memory to disk."""
        data = {
            "wins": [v.tolist() for v in self.win_database],
            "losses": [v.tolist() for v in self.loss_database]
        }
        try:
            with open(self.storage_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f" [META_ERROR] Failed to save database: {e}")

    def load_from_disk(self):
        """Loads memory from disk if it exists."""
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                self.win_database = deque([np.array(v) for v in data.get("wins", [])], maxlen=self.win_database.maxlen)
                self.loss_database = deque([np.array(v) for v in data.get("losses", [])], maxlen=self.loss_database.maxlen)
                # print(f" [META] Loaded {len(self.win_database)} wins, {len(self.loss_database)} losses.")
        except Exception as e:
            print(f" [META_ERROR] Failed to load database: {e}")

    def record_outcome(self, feature_vector: List[float], success: bool) -> None:
        """Adds a trade outcome to the database."""
        if len(feature_vector) != self.feature_count:
            return
        
        if success:
            self.win_database.append(np.array(feature_vector))
        else:
            self.loss_database.append(np.array(feature_vector))

    def predict_success_probability(self, feature_vector: List[float]) -> float:
        """Predicts probability of success [0, 1] for a given state."""
        if len(self.win_database) < 5 or len(self.loss_database) < 5:
            return 0.5
            
        current_state = np.array(feature_vector)
        
        def calculate_avg_dist(state, database):
            dists = [np.linalg.norm(state - hist) for hist in database]
            return np.mean(sorted(dists)[:5])

        dist_win = calculate_avg_dist(current_state, self.win_database)
        dist_loss = calculate_avg_dist(current_state, self.loss_database)
        
        total_dist = dist_win + dist_loss
        if total_dist == 0: return 0.5
        
        return float(dist_loss / total_dist)

class ToxicityAdjustedStop:
    """
    Institutional Risk Guard.
    Logic: Tightens stops as Order Flow Toxicity (VPIN) increases.
    """
    def __init__(self, base_stop_ticks: int = 40, extreme_vpin: float = 0.7):
        self.base_stop: int = base_stop_ticks
        self.extreme_vpin: float = extreme_vpin

    def calculate_adjusted_stop(self, current_price: Decimal, side: int, vpin: float, tick_size: Decimal) -> Decimal:
        """Returns a new VPIN-adjusted Stop Price."""
        tightening_factor = 1.0 - (min(vpin, self.extreme_vpin) / self.extreme_vpin) * 0.5
        adj_ticks = self.base_stop * tightening_factor
        
        buffer = Decimal(str(adj_ticks)) * tick_size
        if side == 1:
            return current_price - buffer
        else:
            return current_price + buffer

class DynamicRiskManager:
    """
    Dynamically adjusts trade parameters (size, stop, target) based on market conditions.
    Inputs: MarketProfile.regime, ATR, brain conviction, daily PnL.
    """
    def __init__(self, ticker_info: Dict, risk_config: Dict, dynamic_risk_cfg: Dict):
        self.ticker_info = ticker_info
        self.risk_config = risk_config
        self.dynamic_risk_cfg = dynamic_risk_cfg
        
        self.base_contract_size = dynamic_risk_cfg.get('base_contract_size', 1)
        self.stop_loss_multiplier = dynamic_risk_cfg.get('stop_loss_multiplier', 1.0)
        self.profit_target_multiplier = dynamic_risk_cfg.get('profit_target_multiplier', 3.0)
        self.volatility_stop_factor = dynamic_risk_cfg.get('volatility_stop_factor', 2.0)
        self.min_atr = dynamic_risk_cfg.get('min_atr', Decimal("0.5")) # Minimum ATR to consider
        self.conviction_size_scale = dynamic_risk_cfg.get('conviction_size_scale', 2.0)
        
        self.tick_size = Decimal(str(ticker_info.get('tick_size', 0.25)))
        self.tick_value = Decimal(str(ticker_info.get('tick_value', 0.5)))

    def adjust_trade_params(self, base_signal: Dict, profile: Any, current_pnl: Decimal) -> Dict:
        adjusted_signal = base_signal.copy()

        # 1. Dynamic Position Sizing (Kelly Criterion & Regime) 
        # Formula: f* = p - (1 - p) / R
        # p = Win Probability (from conviction), R = Reward/Risk Ratio
        p = float(base_signal.get('conviction', 0.5))

        # Calculate R:R Ratio
        stop_ticks = base_signal.get('stop_ticks', 10)
        target_ticks = base_signal.get('target_ticks', 30)      
        R = float(target_ticks) / float(stop_ticks) if stop_ticks > 0 else 3.0

        # Kelly Fraction (f*)
        if R <= 0: R = 0.1 # Safety floor
        kelly_f = p - ((1.0 - p) / R)
        kelly_f = max(0.0, min(kelly_f, 0.2)) # Conservative cap: never bet > 20% of account

        # Scale size based on Kelly Fraction vs Base Size       
        regime = getattr(profile, 'regime', 'NEUTRAL')
        hmm_state = getattr(profile, 'hmm_state', 0) # 0:Range, 1:Trend, 2:Chaos
        
        size_factor = 1 + (kelly_f * 5.0)

        # --- INSTITUTIONAL UPGRADE: TOXICITY & SENTIMENT SIZING ---
        # 1. Toxicity Penalty (VPIN)
        vpin = getattr(profile, 'vpin_score', 0.0)
        if vpin > 0.7:
            # Linear penalty: if vpin=0.9 (Toxic), reduce size by ~20%
            toxicity_penalty = 1.0 - ((vpin - 0.7) / 0.3)
            size_factor *= max(0.5, toxicity_penalty)

        # 2. Sentiment Boost (Cross-Asset)
        sentiment = getattr(profile, 'sentiment_conviction', 1.0)
        size_factor *= sentiment
        
        # 3. HMM Regime Scaling (Phase 3)
        if hmm_state == 1: # TREND
            size_factor *= 1.2 # Boost size in confirmed trends
        elif hmm_state == 0: # RANGE
            size_factor *= 0.6 # Reduce size in mean-reversion
        elif hmm_state == 2: # CHAOS
            size_factor *= 0.0 # VETO
            adjusted_signal['size'] = 0
            adjusted_signal['direction'] = "VETO"
            adjusted_signal['reason'] = "HMM Chaos Veto"
            return adjusted_signal
        # ---------------------------------------------------------

        adjusted_size = max(1, round(self.base_contract_size * size_factor))

        # Enforce max contracts (Hard cap at 3 for stability)   
        max_total_contracts = min(self.risk_config.get('max_contracts', 15), 3)
        adjusted_signal['size'] = min(adjusted_size, max_total_contracts)

        # 2. Adaptive Stop-Loss & Take-Profit (based on ATR and regime)
        current_atr = getattr(profile, 'atr', self.min_atr)
        if current_atr == Decimal("0"): current_atr = self.min_atr
        
        # Ensure Decimal for calculation
        current_atr = Decimal(str(current_atr))
        
        # Stop loss based on volatility
        stop_ticks_float = float(current_atr / self.tick_size) * self.volatility_stop_factor
        
        # Ensure minimum stop ticks
        stop_ticks = max(base_signal.get('stop_ticks', 10), round(stop_ticks_float))
        
        # MOD: HMM-Adaptive Targeting (SAE 5.8 Fix)
        target_multiplier = self.profit_target_multiplier
        if hmm_state == 0: # RANGE
            target_multiplier = 1.2 # Tighter target for mean reversion
        elif hmm_state == 1: # TREND
            target_multiplier = 6.0 # Expansion target for trending moves
            
        target_ticks = max(base_signal.get('target_ticks', stop_ticks * 2), round(stop_ticks * target_multiplier))
        
        adjusted_signal['stop_ticks'] = stop_ticks
        adjusted_signal['target_ticks'] = target_ticks
        
        return adjusted_signal

class MarketRegimeFilter:
    def __init__(self, enabled: bool = True, default_preferred_regimes: List[str] = ["TREND", "NEUTRAL"]):
        self.enabled = enabled
        self.default_preferred_regimes = [r.upper() for r in default_preferred_regimes]

    def is_trading_allowed(self, current_regime: str, brain_preferred_regimes: Optional[List[str]] = None) -> bool:
        if not self.enabled:
            return True # Filter is disabled

        preferred = [r.upper() for r in brain_preferred_regimes] if brain_preferred_regimes else self.default_preferred_regimes
        return current_regime.upper() in preferred

class OFIAccelerator:
    def __init__(self, window: int = 50):
        self.window = window
        self.ofi_history: Deque[float] = deque(maxlen=window)
        self.velocity_history: Deque[float] = deque(maxlen=window)
        self.last_ofi: Optional[float] = None
        self.last_velocity: Optional[float] = None

    def update(self, ofi_value: float) -> Tuple[float, float]:
        self.ofi_history.append(ofi_value)
        velocity = 0.0
        if self.last_ofi is not None:
            velocity = ofi_value - self.last_ofi
        self.last_ofi = ofi_value
        self.velocity_history.append(velocity)
        acceleration = 0.0
        if self.last_velocity is not None:
            acceleration = velocity - self.last_velocity
        self.last_velocity = velocity
        return velocity, acceleration

class DataQualityMonitor:
    """
    Institutional Data Guard: Monitors consistency and completeness of incoming tick data.
    Prevents trading on unreliable or gappy data.
    """
    def __init__(self, enabled: bool = True, max_time_gap_seconds: int = 10, min_l2_levels: int = 3):
        self.enabled = enabled
        self.max_time_gap_seconds = max_time_gap_seconds
        self.min_l2_levels = min_l2_levels
        self.last_timestamp: Optional[float] = None
        self.last_l2_state: Optional[Any] = None

    def is_data_reliable(self, l2_state: Any, trade: Any) -> bool:
        """
        Checks if the current tick data is reliable enough for trading.
        
        Args:
            l2_state: Current L2State object.
            trade: Current TradeEvent object.
            
        Returns:
            True if data is reliable, False otherwise.
        """
        if not self.enabled:
            return True # Monitor is disabled
        
        if trade is None or l2_state is None:
            return False # Missing critical data
            
        # 1. Check for time gaps (missing ticks)
        if self.last_timestamp is not None:
            time_diff = trade.timestamp - self.last_timestamp
            if time_diff > self.max_time_gap_seconds:
                # print(f" [DATA_WARN] Large time gap detected: {time_diff:.2f}s. Max allowed: {self.max_time_gap_seconds}s.")
                self.last_timestamp = trade.timestamp # Reset last timestamp to current to avoid repeated warnings for same gap
                return False
                
        # 2. Check L2 book completeness
        if not hasattr(l2_state, 'bids') or not hasattr(l2_state, 'asks'):
            # print(" [DATA_WARN] L2State missing bids/asks attributes.")
            return False
        if len(l2_state.bids) < self.min_l2_levels or len(l2_state.asks) < self.min_l2_levels:
            # print(f" [DATA_WARN] Insufficient L2 levels: Bids={len(l2_state.bids)}, Asks={len(l2_state.asks)}. Min required: {self.min_l2_levels}.")
            return False

        # 3. Check for obvious data corruption (e.g., zero price/size)
        if trade.price <= 0 or trade.size <= 0:
            # print(f" [DATA_WARN] Trade event with zero price or size: Price={trade.price}, Size={trade.size}.")
            return False
            
        # All checks passed
        self.last_timestamp = trade.timestamp
        self.last_l2_state = l2_state
        return True

class VolatilityDetector:
    """
    Institutional Volatility Guard: Detects periods of extreme market volatility.
    Suggests halting trading during extreme conditions to avoid outsized losses or bad fills.
    """
    def __init__(self, enabled: bool = True, atr_multiplier_threshold: float = 3.0, atr_length: int = 20):
        self.enabled = enabled
        self.atr_multiplier_threshold = atr_multiplier_threshold
        self.atr_length = atr_length
        self.atr_history: deque[Decimal] = deque(maxlen=atr_length)

    def is_extreme_volatility(self, profile: Any) -> bool:
        """
        Checks if the market is currently experiencing extreme volatility.
        
        Args:
            profile: Current MarketProfile object (must have 'atr' attribute).
            
        Returns:
            True if volatility is extreme, False otherwise.
        """
        if not self.enabled:
            return False # Detector is disabled
            
        current_atr = getattr(profile, 'atr', Decimal("0"))
        if current_atr == Decimal("0"):
            return False # Cannot determine volatility without ATR
            
        self.atr_history.append(current_atr)
        
        if len(self.atr_history) < self.atr_length:
            return False # Not enough history to determine "extreme"
            
        avg_atr = sum(self.atr_history) / len(self.atr_history)
        
        # Check if current ATR is significantly higher than average ATR
        if current_atr > (avg_atr * Decimal(str(self.atr_multiplier_threshold))):
            # print(f" [VOL_WARN] Extreme volatility detected: Current ATR {current_atr:.2f} > Avg ATR {avg_atr:.2f} * {self.atr_multiplier_threshold}.")
            return True
            
        return False

def calc_pnl_micros(
    entry_price: Decimal,
    exit_price: Decimal,
    direction: str,
    tick_size: Decimal,
    tick_value: Decimal,
    quantity: int
) -> Decimal:
    """
    Calculate PnL for micro futures contracts.
    """
    # Validate direction parameter
    if direction not in ["Long", "Short"]:
        raise ValueError(f"Invalid direction: {direction}. Must be 'Long' or 'Short'")

    # Ensure all numeric parameters are Decimal for precision
    entry = Decimal(str(entry_price))
    exit_p = Decimal(str(exit_price))
    tick_sz = Decimal(str(tick_size))
    tick_val = Decimal(str(tick_value))
    qty = int(quantity)

    # Calculate price difference based on position direction
    if direction == "Long":
        # Long position: profit when price goes up
        price_diff = exit_p - entry
    else:  # Short
        # Short position: profit when price goes down
        price_diff = entry - exit_p

    # Convert price difference to number of ticks
    ticks = price_diff / tick_sz

    # Calculate gross PnL (before commissions)
    gross_pnl = ticks * tick_val * Decimal(str(qty))

    return gross_pnl

def get_market_time_ct(timestamp: float) -> datetime.datetime:
    """
    Converts a Unix timestamp to Chicago (Central) time.
    Boundary Check: Forces timestamp into realistic CME range (2020-2030).
    """
    # Force boundary safety (prevent OSError [Errno 22])
    if timestamp < 1577836800: # Before 2020
        timestamp = time.time()
    elif timestamp > 1893456000: # After 2030
        timestamp = time.time()
        
    tz = pytz.timezone('America/Chicago')
    return datetime.datetime.fromtimestamp(timestamp, tz)

def get_trading_day(timestamp: float) -> str:
    # CME Rule: Trading day resets at 5:00 PM CT (17:00).
    # Force boundary safety
    if timestamp < 1577836800 or timestamp > 1893456000:
        timestamp = time.time()
        
    dt = datetime.datetime.fromtimestamp(timestamp, pytz.timezone('America/Chicago'))
    
    # If time is 5 PM CT or later, it's the NEXT trading day
    if dt.time() >= datetime.time(17, 0):
        dt += datetime.timedelta(days=1)
        
    # CME Trading Days only exist on M-F. 
    # Friday 5 PM (interpreted as Saturday) and Saturday trades roll to Monday.
    if dt.weekday() == 5: # Saturday -> Monday
        dt += datetime.timedelta(days=2)
    elif dt.weekday() == 6: # Sunday -> Monday
        dt += datetime.timedelta(days=1)
        
    return dt.strftime("%Y-%m-%d")

# --- Elite Filters & Risk (SAE 5.8 Phase 2) ---
from scipy.signal import savgol_coeffs

class SavitzkyGolayFilter:
    """
    Institutional Noise Reduction: Savitzky-Golay Filter.
    Smooths data by fitting local polynomial regressions.
    """
    def __init__(self, window=11, polyorder=2):
        if window % 2 == 0: window += 1
        self.window = window
        self.polyorder = polyorder
        self.history: Deque[float] = deque(maxlen=window)
        # Pre-calculate coefficients for the middle point
        self.coeffs = savgol_coeffs(window, polyorder, pos=window-1)

    def update(self, val: float) -> float:
        self.history.append(val)
        if len(self.history) < self.window: return val
        data = np.array(self.history)
        return float(np.dot(self.coeffs, data))

class HMMRegimeDetector:
    """
    Institutional Regime Detection (Loaded Model).
    Uses pre-trained GaussianHMM from 'hmm_model.pkl' to classify market states.
    States: 0: Range, 1: Trend, 2: Chaos.
    """
    def __init__(self, window=50, model_path="hmm_model.pkl"):
        self.window = window
        self.returns_history: Deque[float] = deque(maxlen=window)
        self.current_state = 0
        self.state_buffer = [] # FIX: Added missing buffer
        self.prev_price = None
        self.model = None
        
        # Load Pre-Trained Model
        try:
            full_path = os.path.join(os.path.dirname(__file__), model_path)
            if os.path.exists(full_path):
                import pickle
                with open(full_path, "rb") as f:
                    self.model = pickle.load(f)
                print(f" [HMM] Loaded institutional model from {model_path}")
            else:
                print(f" [HMM] Model not found at {full_path}. Using fallback heuristic.")
        except Exception as e:
            print(f" [HMM] Failed to load model: {e}")

    def update(self, price: Decimal, vpin: float = 0.5, ofi_z: float = 0.0) -> int:
        # --- INSTITUTIONAL INTEGRITY GUARD ---
        assert price > 0, f"BUG: Negative/Zero Price detected: {price}"
        assert 0 <= vpin <= 1.0, f"BUG: VPIN out of bounds: {vpin}"
        # -------------------------------------
        
        px = float(price)
        if self.prev_price is None:
            self.prev_price = px
            return 0
            
        # Log Return
        ret = np.log(px / self.prev_price) if self.prev_price > 0 else 0.0
        self.returns_history.append(ret)
        self.prev_price = px
        
        if len(self.returns_history) < 10: return self.current_state
            
        # Fallback Heuristic (Hardened for L2 Microstructure)
        vol_s = np.std(list(self.returns_history)[-10:])
        raw_state = 0
        
        # 1. Chaos Detection: Extreme Volatility or High Toxicity
        if vol_s > 0.0005 or vpin > 0.8: 
            raw_state = 2 
        # 2. Trend Detection: Significant OFI Conviction + Sustained Velocity
        elif abs(ofi_z) > 1.5:
            raw_state = 1
        # 3. Range Detection
        else:
            raw_state = 0
            
        # Institutional State Smoothing (Schmitt Trigger / Diagonal Bias)
        # Phase 22: Added state persistence threshold
        if raw_state != self.current_state:
            self.state_buffer.append(raw_state)
            # Require 15 consecutive ticks (up from 5) to switch regime
            if len(self.state_buffer) >= 15 and all(s == raw_state for s in self.state_buffer):
                print(f" [HMM] Regime Shift: {self.current_state} -> {raw_state}")
                self.current_state = raw_state
                self.state_buffer.clear()
        else:
            self.state_buffer.clear()
            
        return self.current_state

class HierarchicalRiskSizer:
    """
    Institutional Position Sizing: Hierarchical Risk Parity (HRP-Lite).
    Ensures high-volatility signals receive smaller allocations.
    """
    def __init__(self, n_strategies=3, window=100):
        self.n = n_strategies
        self.window = window
        self.pnl_history: List[Deque[float]] = [deque(maxlen=window) for _ in range(n_strategies)]

    def record_outcome(self, strategy_idx: int, pnl: float):
        if strategy_idx < self.n:
            self.pnl_history[strategy_idx].append(pnl)

    def calculate_allocations(self) -> NDArray[np.float64]:
        variances = []
        for history in self.pnl_history:
            if len(history) < 10: variances.append(1.0)
            else: variances.append(np.var(history) + 1e-9)
        inv_vars = 1.0 / np.array(variances)
        return inv_vars / np.sum(inv_vars)

    def get_final_size(self, strategy_idx: int, base_size: int) -> int:
        weights = self.calculate_allocations()
        weight = weights[strategy_idx]
        scale = weight * self.n
        return max(1, min(int(base_size * scale), 15))

class IcebergDetector:

    """

    Elite Alpha: Iceberg Detector (Wasserstein-Inspired).

    Identifies hidden institutional walls by measuring the "distance" between 

    expected price movement and actual volume absorption.

    """

    def __init__(self, window: int = 50, threshold_sigma: float = 2.5):

        self.window = window

        self.threshold_sigma = threshold_sigma

        self.volume_history: deque = deque(maxlen=window)

        self.price_history: deque = deque(maxlen=window)

        self.last_score = 0.0



    def update(self, price: Decimal, size: int, side: str) -> float:

        """

        Detects potential iceberg orders using absorption metrics.

        Returns: 1.0 (Bullish), -1.0 (Bearish), 0.0 (Neutral)

        """

        px = float(price)

        self.volume_history.append(float(size))

        self.price_history.append(px)



        if len(self.volume_history) < self.window:

            return 0.0



        avg_vol = np.mean(self.volume_history)

        std_vol = np.std(self.volume_history)



        # 1. Identify abnormally large volume (Potential Iceberg)
        is_vol_spike = float(size) > (avg_vol + self.threshold_sigma * std_vol)

        # 2. Check if price stalled despite the spike (Absorption)
        price_range = max(self.price_history) - min(self.price_history)
        is_stalled = price_range < 0.5 # Tight range (e.g., 2 ticks on MNQ)
        
        if is_vol_spike and is_stalled:
            # If volume was 'Buy' but price didn't go up -> Bearish Iceberg (selling wall)
            if side == "Buy":
                return -1.0
            # If volume was 'Sell' but price didn't go down -> Bullish Iceberg (buying floor)
            elif side == "Sell":
                return 1.0
                
        return 0.0

class DynamicLockoutManager:
    """
    Phase 18: Adaptive Cooldown & Lockout Escalation.
    Manages exponential backoff for signal generation based on recent trade outcomes.
    """
    def __init__(self, base_cooldown: int = 300):
        self.base_cooldown = base_cooldown
        self.consecutive_losses = 0
        self.lockout_until = 0.0

    def record_outcome(self, pnl: float):
        if pnl > 0:
            self.consecutive_losses = 0
            self.lockout_until = 0.0 # Reset
        elif pnl < 0:
            self.consecutive_losses += 1
            # Exponential backoff: 300, 450, 675, 900 (Cap)
            multiplier = 1.5 ** (self.consecutive_losses - 1)
            duration = min(self.base_cooldown * multiplier, 900)
            self.lockout_until = time.time() + duration
            print(f" [LOCKOUT] Loss #{self.consecutive_losses}. Cooling down for {duration:.0f}s")

    def is_locked(self, *args, **kwargs) -> bool:
        """Phase 18: Returns True if the engine is currently in a loss-recovery cooldown."""
        return time.time() < self.lockout_until

class ConsensusEngine:
    """
    Institutional Consensus Engine: Aggregates signals from the brain fleet.
    Reduces idiosyncratic noise by requiring multiple strategies to agree on direction.
    """
    def __init__(self, config: Dict = None, **kwargs):
        # Support both dictionary config (Engine) and direct kwargs (Leader)
        cfg = config or kwargs
        self.enabled = cfg.get('enabled', True)
        self.min_agreement = cfg.get('min_agreement_count', cfg.get('min_agreement', 2))
        self.min_conviction = float(cfg.get('min_conviction', 0.6))
        self.mode = cfg.get('decision_mode', 'MAJORITY_VOTE')
        self.signal_window_seconds = float(cfg.get('signal_window_seconds', cfg.get('window_seconds', 2.0)))
        self.signal_memory: Dict[str, Tuple[float, Dict]] = {} # brain_name -> (timestamp, signal)
        
        self.solo_brains = cfg.get('solo_brains', [])
        self.solo_conviction = float(cfg.get('solo_conviction', 0.95))
        self.required_brains = cfg.get('required_brains', [])
        
        # Phase 18: Dynamic Lockout Integration
        self.lockout = DynamicLockoutManager()

    def aggregate_signals(self, signals: List[Dict], current_time: float) -> Optional[Dict]:
        """
        Processes a list of signals and returns a single consensus signal or None.
        Uses a sliding time window to allow for non-simultaneous brain firing.
        """
        if not self.enabled:
            return None

        # 1. Update memory with new signals that meet minimum conviction
        for sig in signals:
            self.add_signal(current_time, sig.get('brain', 'Unknown'), sig['direction'], sig.get('conviction', 0.5))
            
        return self.get_consensus(current_time)

    def add_signal(self, timestamp: float, brain_name: str, direction: Any, conviction: float, price: Optional[Decimal] = None):
        """Adds a signal to the sliding window memory with price tracking."""
        if conviction >= self.min_conviction:
            # Reconstruct signal dict for internal consistency
            sig = {
                'brain': brain_name,
                'direction': direction,
                'conviction': conviction,
                'price': price
            }
            self.signal_memory[brain_name] = (timestamp, sig)

    def get_consensus(self, current_time: float) -> Optional[Dict]:
        """Evaluates the current signal memory for a consensus decision."""
        # 0. Check Dynamic Lockout (Phase 18)
        if self.lockout.is_locked():
            return None

        # 2. Cleanup expired signals
        self.signal_memory = {
            name: (ts, sig) for name, (ts, sig) in self.signal_memory.items()
            if current_time - ts <= self.signal_window_seconds
        }

        if not self.signal_memory:
            return None

        # 3. Check for VETO (Highest Priority)
        for name, (ts, sig) in self.signal_memory.items():
            if sig.get('direction') == "VETO":
                return None

        # 4. Count directions with Strategic Weighting
        valid_signals = [sig for ts, sig in self.signal_memory.values()]
        
        # Spatial Alignment Check: Ensure signals are in the same price cluster
        prices = [float(s['price']) for s in valid_signals if s.get('price') is not None]
        if len(prices) >= 2:
            price_drift = max(prices) - min(prices)
            if price_drift > 2.0: # Institutional Limit: 8 ticks (2.0 pts)
                # print(f" [CONSENSUS] VETO: Price drift too high ({price_drift:.2f})")
                return None

        weights = {"Whale": 1.5, "CVD_Divergence": 1.5, "Flux": 1.5, "ECR": 1.2}
        long_weight = 0.0
        short_weight = 0.0
        longs = []
        shorts = []

        for s in valid_signals:
            brain_name = s.get('brain', 'Unknown')
            weight = weights.get(brain_name, 1.0)
            if s.get('direction') in ["Long", "BUY", 1]:
                long_weight += (1.0 * weight)
                longs.append(brain_name)
            elif s.get('direction') in ["Short", "SELL", -1]:
                short_weight += (1.0 * weight)
                shorts.append(brain_name)

        # Consensus Result
        is_consensus = False
        cons_dir = None
        contributing = []

        if long_weight >= float(self.min_agreement) and long_weight > short_weight:
            is_consensus = True
            cons_dir = "Long"
            contributing = longs
        elif short_weight >= float(self.min_agreement) and short_weight > long_weight:
            is_consensus = True
            cons_dir = "Short"
            contributing = shorts

        if is_consensus:
            # Pick first contributing brain for SL/TP snapshot
            first_brain = contributing[0] if contributing else "ENSEMBLE"
            return {
                "direction": cons_dir,
                "contributing_brains": contributing,
                "agreement_count": len(contributing),
                "brain": "ENSEMBLE",
                "size": 1, # Consensus defaults to 1 unless scaled by Risk Manager
                "stop_ticks": 40, # Default institutional stop
                "target_ticks": 120, # Default institutional target (3:1)
                "reason": f"Consensus ({cons_dir}) from {', '.join(contributing)}"
            }
        return None

        return None

class ComplianceSentry:

    def __init__(self, risk_config: Dict):

        self.risk_config = risk_config

        self.daily_loss_limit = Decimal(str(risk_config.get('daily_loss_limit', -3000)))     



        # TopstepX: Flat by 3:10 PM CT (15:10)

        # Institutional Buffer: No new trades after 15:00, Hard flatten at 15:08

        self.entry_halt_time = datetime.time(15, 0, 0)

        self.hard_flatten_time = datetime.time(15, 8, 0)

        

        self.dead_zone_start = datetime.time(15, 10, 0)

        self.dead_zone_end = datetime.time(17, 0, 0)



    def is_trading_allowed(self, timestamp: float, current_pnl: Decimal) -> Tuple[bool, str]:

        # 1. Risk Check

        if current_pnl <= self.daily_loss_limit:

            return False, "Daily loss limit hit"



        # 2. Time Check (Central Time)

        dt = datetime.datetime.fromtimestamp(timestamp, pytz.timezone('America/Chicago'))    

        current_time = dt.time()



        # Check Dead Zone (15:10 - 17:00)

        if self.dead_zone_start <= current_time <= self.dead_zone_end:

            return False, "Market dead zone (Market Close/Maintenance)"



        # Check Entry Halt (15:00 - 15:10) - Stop new trades before the hard close

        if self.entry_halt_time <= current_time <= self.dead_zone_start:

            return False, "Entry halted (Approaching Market Close)"



        # Check Weekend (Friday 4 PM - Sunday 5 PM)

        if dt.weekday() == 4 and current_time > datetime.time(16, 0):

            return False, "Weekend close (Friday)"

        if dt.weekday() == 5:

            return False, "Weekend (Saturday)"



        return True, "OK"



    def should_flatten(self, timestamp: float, current_pnl: Decimal) -> bool:

        dt = datetime.datetime.fromtimestamp(timestamp, pytz.timezone('America/Chicago'))

        current_time = dt.time()

        

        # 1. Hard Flatten Time (15:08 CT)

        if self.hard_flatten_time <= current_time <= self.dead_zone_start:

            return True

            

        # 2. Risk or Dead Zone

        is_allowed, _ = self.is_trading_allowed(timestamp, current_pnl)

        if not is_allowed:

            # We only flatten for Risk or Maintenance, not the 'Entry Halt' zone

            if current_pnl <= self.daily_loss_limit or self.dead_zone_start <= current_time:

                return True



        return False

class ConsensusMonitor:
    """
    Phase 25: Consensus Monitoring & Multi-Agent Voting Tracker.
    Tracks agreement rate, decision frequency, and voting patterns across the brain fleet.
    """
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.decision_history: Deque[Dict[str, Any]] = deque(maxlen=window_size)
        self.agreement_count = 0
        self.total_rounds = 0
        self.brain_vote_counts = {}
        self.direction_votes = {}  # 'Long' -> count, 'Short' -> count

    def record_decision(self, brain_name: str, direction: str, conviction: float, timestamp: float = None):
        """Records a brain's decision for consensus analysis."""
        if timestamp is None:
            timestamp = time.time()
        
        decision = {
            'brain': brain_name,
            'direction': direction,
            'conviction': conviction,
            'timestamp': timestamp
        }
        self.decision_history.append(decision)
        
        # Track per-brain voting
        if brain_name not in self.brain_vote_counts:
            self.brain_vote_counts[brain_name] = 0
        self.brain_vote_counts[brain_name] += 1
        
        # Track direction voting
        if direction not in self.direction_votes:
            self.direction_votes[direction] = 0
        self.direction_votes[direction] += 1

    def calculate_agreement_rate(self, window: int = None) -> float:
        """
        Calculates agreement rate: % of decisions that match consensus direction.
        Returns: 0.0 to 1.0
        """
        if window is None:
            window = self.window_size
        
        if len(self.decision_history) < 2:
            return 0.0
        
        # Get consensus direction (mode)
        recent_decisions = list(self.decision_history)[-window:]
        directions = [d['direction'] for d in recent_decisions if d['direction'] != 'HOLD']
        
        if not directions:
            return 0.0
        
        # Find consensus direction
        consensus_dir = max(set(directions), key=directions.count)
        
        # Count agreements
        agreements = sum(1 for d in recent_decisions if d['direction'] == consensus_dir)
        
        return agreements / len(recent_decisions)

    def get_voting_stats(self) -> Dict[str, Any]:
        """Returns voting statistics summary."""
        return {
            'total_decisions': len(self.decision_history),
            'brain_vote_counts': dict(self.brain_vote_counts),
            'direction_votes': dict(self.direction_votes),
            'agreement_rate': self.calculate_agreement_rate(),
            'consensus_direction': max(self.direction_votes.items(), key=lambda x: x[1])[0] if self.direction_votes else 'NEUTRAL'
        }

    def get_brain_effectiveness(self) -> Dict[str, float]:
        """
        Returns per-brain effectiveness (how often they voted with consensus).
        """
        if not self.decision_history:
            return {}
        
        brain_effectiveness = {}
        consensus_dir = max(self.direction_votes.items(), key=lambda x: x[1])[0] if self.direction_votes else 'NEUTRAL'
        
        for brain_name in self.brain_vote_counts.keys():
            brain_decisions = [d for d in self.decision_history if d['brain'] == brain_name]
            if not brain_decisions:
                continue
            
            agreements = sum(1 for d in brain_decisions if d['direction'] == consensus_dir)
            effectiveness = agreements / len(brain_decisions)
            brain_effectiveness[brain_name] = effectiveness
        
        return brain_effectiveness
