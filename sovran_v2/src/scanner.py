"""
Market Scanner — Multi-Market Intelligence Engine

Scans all subscribed markets simultaneously, scores them by conviction,
and recommends which market to trade next.

Features:
  - Cross-asset correlation tracking
  - Regime-based market ranking
  - Opportunity scoring (volatility × trend × flow)
  - Per-market position sizing recommendations
  - Asset-class diversification (won't stack correlated bets)
"""

import asyncio
import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.market_data import MarketDataPipeline, MarketSnapshot, MarketRegime


@dataclass
class MarketScore:
    """Conviction score for a single market at a single point in time."""
    contract_id: str
    symbol: str
    asset_class: str
    score: float                  # 0-100 composite score
    direction: str                # "long", "short", or "neutral"
    regime: MarketRegime
    components: Dict[str, float] = field(default_factory=dict)  # breakdown
    timestamp: float = 0.0
    snapshot: Optional[MarketSnapshot] = None

    @property
    def is_tradeable(self) -> bool:
        return self.score >= 50.0 and self.direction != "neutral"


@dataclass
class AssetClassState:
    """Aggregated state for an asset class (equities, metals, etc.)."""
    name: str
    avg_price_change_pct: float = 0.0  # Average across members
    dominant_regime: MarketRegime = MarketRegime.UNKNOWN
    avg_vpin: float = 0.0
    avg_ofi: float = 0.0
    member_count: int = 0
    bullish_count: int = 0
    bearish_count: int = 0

    @property
    def sentiment(self) -> str:
        if self.member_count == 0:
            return "unknown"
        bull_pct = self.bullish_count / self.member_count
        if bull_pct >= 0.6:
            return "bullish"
        elif bull_pct <= 0.4:
            return "bearish"
        return "mixed"


class MarketScanner:
    """
    Scans multiple markets and ranks them by opportunity.

    Scoring factors:
      1. Trend Clarity (30%): ADX/trend_strength — strong trends = higher score
      2. Flow Signal (25%): OFI Z-score magnitude — strong order flow = conviction
      3. Volatility Sweet Spot (20%): ATR in optimal range (not too low, not too high)
      4. Flow Cleanliness (15%): 1 - VPIN — clean flow = safer trade
      5. Cross-Asset Confirmation (10%): asset class alignment bonus

    Per-market scanning is O(1) — just reads the latest snapshot.
    """

    SCORING_WEIGHTS = {
        "trend_clarity": 0.30,
        "flow_signal": 0.25,
        "volatility": 0.20,
        "flow_clean": 0.15,
        "cross_asset": 0.10,
    }

    def __init__(self):
        self.logger = logging.getLogger("sovran.scanner")
        self._score_history: Dict[str, deque] = {}  # contract -> last 20 scores
        self._asset_class_states: Dict[str, AssetClassState] = {}
        self._last_scan_time: float = 0.0

    def scan(
        self,
        snapshots: Dict[str, MarketSnapshot],
        contract_meta: Dict[str, Dict],
        active_positions: Optional[Dict[str, any]] = None,
    ) -> List[MarketScore]:
        """
        Score all markets and return sorted list (highest conviction first).

        Args:
            snapshots: contract_id -> MarketSnapshot (current data for each market)
            contract_meta: contract_id -> metadata dict (tick_size, tick_value, asset_class)
            active_positions: contract_id -> position data (to avoid stacking)

        Returns:
            List of MarketScore, sorted by score descending.
        """
        active_positions = active_positions or {}
        self._last_scan_time = time.time()

        # 1. Build asset class aggregates for cross-market analysis
        self._update_asset_class_states(snapshots, contract_meta)

        # 2. Score each market
        scores: List[MarketScore] = []
        for contract_id, snap in snapshots.items():
            meta = contract_meta.get(contract_id, {})
            asset_class = meta.get("asset_class", "unknown")
            symbol = meta.get("name", contract_id)

            # Skip if we already have a position in this market
            if contract_id in active_positions:
                continue

            # Skip if data is too stale or missing
            if snap.last_price <= 0 or snap.bar_count < 5:
                continue

            score = self._score_market(snap, meta, asset_class)
            scores.append(score)

            # Track history for trend analysis
            if contract_id not in self._score_history:
                self._score_history[contract_id] = deque(maxlen=20)
            self._score_history[contract_id].append(score.score)

        # 3. Apply cross-asset correlation penalties
        scores = self._apply_correlation_penalties(scores, active_positions)

        # 4. Sort by score, descending
        scores.sort(key=lambda s: s.score, reverse=True)

        # Log top 3
        if scores:
            top3 = scores[:3]
            self.logger.info(
                f"SCAN: Top markets — " +
                ", ".join(f"{s.contract_id}({s.direction[0].upper()}):{s.score:.0f}" for s in top3)
            )

        return scores

    def _score_market(
        self, snap: MarketSnapshot, meta: Dict, asset_class: str
    ) -> MarketScore:
        """Compute the composite conviction score for one market."""
        components = {}

        # 1. Trend Clarity (0-100)
        # ADX > 25 = trending, > 40 = strong trend, > 60 = very strong
        trend_raw = min(snap.trend_strength / 60.0, 1.0) * 100
        components["trend_clarity"] = trend_raw

        # 2. Flow Signal (0-100)
        # OFI Z-score: |Z| > 2 = strong signal, > 3 = very strong
        ofi_magnitude = abs(snap.ofi_zscore)
        flow_raw = min(ofi_magnitude / 3.0, 1.0) * 100
        components["flow_signal"] = flow_raw

        # 3. Volatility Sweet Spot (0-100)
        # Too low = no opportunity, too high = dangerous
        # Optimal: ATR is 0.1-0.5% of price
        if snap.last_price > 0:
            atr_pct = snap.atr_points / snap.last_price * 100
            if 0.05 <= atr_pct <= 0.8:
                vol_raw = 100.0 - abs(atr_pct - 0.3) * 200  # Peak at 0.3%
            else:
                vol_raw = max(0, 50 - abs(atr_pct - 0.3) * 100)
        else:
            vol_raw = 0
        components["volatility"] = max(0, min(100, vol_raw))

        # 4. Flow Cleanliness (0-100)
        # VPIN < 0.3 = clean, > 0.7 = toxic
        clean_raw = max(0, (1.0 - snap.vpin) * 100)
        components["flow_clean"] = clean_raw

        # 5. Cross-Asset Confirmation (0-100)
        class_state = self._asset_class_states.get(asset_class)
        if class_state:
            # Bonus if the whole asset class agrees on direction
            if snap.ofi_zscore > 1.0 and class_state.sentiment == "bullish":
                cross_raw = 80.0
            elif snap.ofi_zscore < -1.0 and class_state.sentiment == "bearish":
                cross_raw = 80.0
            elif class_state.sentiment == "mixed":
                cross_raw = 40.0  # No bonus, no penalty
            else:
                cross_raw = 20.0  # Diverging from class
        else:
            cross_raw = 50.0  # Neutral
        components["cross_asset"] = cross_raw

        # Composite score
        composite = sum(
            components[k] * self.SCORING_WEIGHTS[k]
            for k in self.SCORING_WEIGHTS
        )

        # Determine direction from OFI + regime
        if snap.ofi_zscore > 1.0 and snap.regime in (MarketRegime.TRENDING_UP, MarketRegime.UNKNOWN):
            direction = "long"
        elif snap.ofi_zscore < -1.0 and snap.regime in (MarketRegime.TRENDING_DOWN, MarketRegime.UNKNOWN):
            direction = "short"
        elif snap.regime == MarketRegime.TRENDING_UP and snap.trend_strength > 25:
            direction = "long"
        elif snap.regime == MarketRegime.TRENDING_DOWN and snap.trend_strength > 25:
            direction = "short"
        else:
            direction = "neutral"
            composite *= 0.5  # Penalty for no direction

        return MarketScore(
            contract_id=snap.contract_id,
            symbol=meta.get("name", snap.contract_id),
            asset_class=asset_class,
            score=round(composite, 1),
            direction=direction,
            regime=snap.regime,
            components=components,
            timestamp=time.time(),
            snapshot=snap,
        )

    def _update_asset_class_states(
        self, snapshots: Dict[str, MarketSnapshot], contract_meta: Dict[str, Dict]
    ) -> None:
        """Aggregate market data by asset class for cross-market analysis."""
        class_data: Dict[str, List[MarketSnapshot]] = {}

        for contract_id, snap in snapshots.items():
            meta = contract_meta.get(contract_id, {})
            ac = meta.get("asset_class", "unknown")
            if ac not in class_data:
                class_data[ac] = []
            class_data[ac].append(snap)

        self._asset_class_states = {}
        for ac, snaps in class_data.items():
            n = len(snaps)
            avg_change = sum(s.price_change_pct for s in snaps) / n if n else 0
            avg_vpin = sum(s.vpin for s in snaps) / n if n else 0
            avg_ofi = sum(s.ofi_zscore for s in snaps) / n if n else 0
            bullish = sum(1 for s in snaps if s.ofi_zscore > 0.5)
            bearish = sum(1 for s in snaps if s.ofi_zscore < -0.5)

            # Dominant regime: majority vote
            regime_counts: Dict[MarketRegime, int] = {}
            for s in snaps:
                regime_counts[s.regime] = regime_counts.get(s.regime, 0) + 1
            dominant_regime = max(regime_counts, key=regime_counts.get) if regime_counts else MarketRegime.UNKNOWN

            self._asset_class_states[ac] = AssetClassState(
                name=ac,
                avg_price_change_pct=avg_change,
                dominant_regime=dominant_regime,
                avg_vpin=avg_vpin,
                avg_ofi=avg_ofi,
                member_count=n,
                bullish_count=bullish,
                bearish_count=bearish,
            )

    def _apply_correlation_penalties(
        self, scores: List[MarketScore], active_positions: Dict
    ) -> List[MarketScore]:
        """Reduce score for markets in same asset class as active positions.

        This prevents stacking correlated bets (e.g., long MNQ + long MES).
        """
        # Identify asset classes of active positions
        active_classes = set()
        for contract_id in active_positions:
            # Infer asset class from score history or from the score list
            for s in scores:
                if s.contract_id == contract_id:
                    active_classes.add(s.asset_class)
                    break

        if not active_classes:
            return scores

        # Penalize markets in same class as active positions
        for score in scores:
            if score.asset_class in active_classes:
                score.score *= 0.5  # 50% penalty for same asset class
                score.components["correlation_penalty"] = -50.0

        return scores

    def get_cross_market_summary(self) -> Dict[str, Dict]:
        """Get a summary of cross-market conditions for AI prompts."""
        summary = {}
        for ac, state in self._asset_class_states.items():
            summary[ac] = {
                "sentiment": state.sentiment,
                "avg_change_pct": round(state.avg_price_change_pct, 4),
                "avg_vpin": round(state.avg_vpin, 3),
                "avg_ofi": round(state.avg_ofi, 2),
                "dominant_regime": state.dominant_regime.value,
                "members": state.member_count,
            }
        return summary

    def recommend_position_size(
        self,
        contract_meta: Dict,
        account_balance: float,
        max_risk_pct: float = 0.02,
        atr_points: float = 0.0,
    ) -> int:
        """Recommend position size based on market-specific tick value and account size.

        Conservative approach:
          - Risk at most max_risk_pct of account per trade
          - Stop is 1.5x ATR
          - Position size = risk_dollars / (stop_distance_dollars)
        """
        tick_size = contract_meta.get("tick_size", 0.25)
        tick_value = contract_meta.get("tick_value", 0.50)

        if atr_points <= 0 or tick_size <= 0:
            return 1

        # Risk budget
        risk_dollars = account_balance * max_risk_pct

        # Stop distance = 1.5 ATR in dollars
        stop_ticks = (atr_points * 1.5) / tick_size
        stop_dollars = stop_ticks * tick_value

        if stop_dollars <= 0:
            return 1

        # Position size
        size = int(risk_dollars / stop_dollars)
        return max(1, min(size, 10))  # Cap at 10 for safety

    @property
    def asset_class_states(self) -> Dict[str, AssetClassState]:
        return self._asset_class_states

    @property
    def last_scan_time(self) -> float:
        return self._last_scan_time
