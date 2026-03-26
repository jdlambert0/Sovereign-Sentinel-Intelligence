"""
Performance Attribution Engine — Self-Evolution Analytics

Analyzes trade history to determine:
  - Which markets are most profitable
  - Which time windows have edge
  - Which frameworks/signals generate the best returns
  - Optimal position sizing per market
  - Regime-adaptive parameter recommendations

Feeds insights back into the system to evolve over time.
"""

import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import pytz


@dataclass
class MarketPerformance:
    """Performance metrics for a single market."""
    contract_id: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    win_rate: float = 0.0
    avg_hold_seconds: float = 0.0
    avg_mfe: float = 0.0  # Average max favorable excursion
    avg_mae: float = 0.0  # Average max adverse excursion
    best_trade: float = 0.0
    worst_trade: float = 0.0
    profit_factor: float = 0.0
    edge_score: float = 0.0  # Composite edge rating 0-100


@dataclass
class TimeWindow:
    """Performance metrics for a time-of-day window."""
    name: str
    start_hour: int  # CT hour
    end_hour: int
    total_trades: int = 0
    wins: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_pnl: float = 0.0


@dataclass
class ExitAnalysis:
    """Analysis of exit reasons."""
    reason: str
    count: int = 0
    avg_pnl: float = 0.0
    total_pnl: float = 0.0
    win_rate: float = 0.0


@dataclass
class AdaptiveParameters:
    """Recommended parameters based on performance analysis."""
    conviction_threshold: float = 70.0
    preferred_markets: List[str] = field(default_factory=list)
    avoided_markets: List[str] = field(default_factory=list)
    best_time_windows: List[str] = field(default_factory=list)
    position_size_adjustments: Dict[str, float] = field(default_factory=dict)
    regime_preferences: Dict[str, str] = field(default_factory=dict)
    framework_weights: Dict[str, float] = field(default_factory=dict)
    risk_factor: float = 1.0  # Scale risk up/down based on recent performance
    notes: List[str] = field(default_factory=list)


# Standard time windows (Central Time)
TIME_WINDOWS = [
    TimeWindow("Asia Session", 17, 2),      # 5pm - 2am CT (Sun-Thu)
    TimeWindow("Europe Open", 2, 8),          # 2am - 8am CT
    TimeWindow("US Pre-Market", 8, 9),        # 8am - 9:30am CT
    TimeWindow("US Morning", 9, 12),          # 9:30am - 12pm CT
    TimeWindow("US Afternoon", 12, 15),       # 12pm - 3pm CT
    TimeWindow("US Close", 15, 16),           # 3pm - 4pm CT
]


class PerformanceEngine:
    """
    Analyzes trade history and recommends system parameter adaptations.

    Uses the trade_history.json from PositionManager to build a
    comprehensive picture of what's working and what's not.
    """

    def __init__(self, state_dir: str = "state"):
        self.state_dir = state_dir
        self.logger = logging.getLogger("sovran.performance")
        self._trade_history: List[Dict] = []
        self._market_perf: Dict[str, MarketPerformance] = {}
        self._time_windows: List[TimeWindow] = []
        self._exit_analysis: Dict[str, ExitAnalysis] = {}
        self._last_analysis_time: float = 0.0

    def load_history(self) -> int:
        """Load trade history from state directory."""
        path = os.path.join(self.state_dir, "trade_history.json")
        if not os.path.exists(path):
            return 0
        try:
            with open(path) as f:
                self._trade_history = json.load(f)
            return len(self._trade_history)
        except Exception as e:
            self.logger.error(f"Failed to load trade history: {e}")
            return 0

    def analyze(self, min_trades: int = 5) -> AdaptiveParameters:
        """
        Run full performance analysis and generate adaptive parameters.

        Only generates recommendations if we have enough trades.
        """
        self.load_history()
        n = len(self._trade_history)

        if n < min_trades:
            self.logger.info(f"Only {n} trades — need {min_trades} for analysis")
            return AdaptiveParameters(notes=[f"Insufficient data: {n}/{min_trades} trades"])

        self._analyze_by_market()
        self._analyze_by_time()
        self._analyze_by_exit_reason()
        params = self._generate_adaptive_params()
        self._last_analysis_time = time.time()

        # Save analysis results
        self._save_analysis(params)

        return params

    def _analyze_by_market(self) -> None:
        """Analyze performance per market."""
        market_trades: Dict[str, List[Dict]] = defaultdict(list)
        for t in self._trade_history:
            cid = t.get("contract_id", "unknown")
            market_trades[cid].append(t)

        self._market_perf = {}
        for cid, trades in market_trades.items():
            mp = MarketPerformance(contract_id=cid)
            mp.total_trades = len(trades)
            pnls = [t.get("pnl", 0) for t in trades]
            mp.wins = sum(1 for p in pnls if p > 0)
            mp.losses = sum(1 for p in pnls if p <= 0)
            mp.total_pnl = sum(pnls)
            mp.avg_pnl = mp.total_pnl / mp.total_trades if mp.total_trades else 0
            mp.win_rate = mp.wins / mp.total_trades if mp.total_trades else 0
            mp.best_trade = max(pnls) if pnls else 0
            mp.worst_trade = min(pnls) if pnls else 0
            mp.avg_hold_seconds = (
                sum(t.get("hold_seconds", 0) for t in trades) / len(trades) if trades else 0
            )
            mp.avg_mfe = (
                sum(t.get("max_favorable_excursion", 0) for t in trades) / len(trades) if trades else 0
            )
            mp.avg_mae = (
                sum(t.get("max_adverse_excursion", 0) for t in trades) / len(trades) if trades else 0
            )

            # Profit factor
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = abs(sum(p for p in pnls if p < 0))
            mp.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

            # Edge score: composite rating 0-100
            wr_score = mp.win_rate * 50  # 50% weight on win rate
            pf_score = min(mp.profit_factor, 3.0) / 3.0 * 30  # 30% weight on profit factor
            consistency = (1.0 - min(abs(mp.worst_trade) / (abs(mp.best_trade) + 1), 1.0)) * 20
            mp.edge_score = wr_score + pf_score + consistency

            self._market_perf[cid] = mp

    def _analyze_by_time(self) -> None:
        """Analyze performance by time of day (Central Time)."""
        ct = pytz.timezone("US/Central")
        self._time_windows = []

        for tw_template in TIME_WINDOWS:
            tw = TimeWindow(
                name=tw_template.name,
                start_hour=tw_template.start_hour,
                end_hour=tw_template.end_hour,
            )
            for t in self._trade_history:
                entry_time = t.get("entry_time", 0)
                if entry_time <= 0:
                    continue
                dt = datetime.fromtimestamp(entry_time, tz=timezone.utc).astimezone(ct)
                hour = dt.hour
                # Handle overnight windows
                if tw.start_hour <= tw.end_hour:
                    in_window = tw.start_hour <= hour < tw.end_hour
                else:
                    in_window = hour >= tw.start_hour or hour < tw.end_hour

                if in_window:
                    tw.total_trades += 1
                    pnl = t.get("pnl", 0)
                    tw.total_pnl += pnl
                    if pnl > 0:
                        tw.wins += 1

            if tw.total_trades > 0:
                tw.win_rate = tw.wins / tw.total_trades
                tw.avg_pnl = tw.total_pnl / tw.total_trades
            self._time_windows.append(tw)

    def _analyze_by_exit_reason(self) -> None:
        """Analyze which exit reasons lead to best/worst outcomes."""
        reason_trades: Dict[str, List[float]] = defaultdict(list)
        for t in self._trade_history:
            reason = t.get("exit_reason", "unknown")
            pnl = t.get("pnl", 0)
            reason_trades[reason].append(pnl)

        self._exit_analysis = {}
        for reason, pnls in reason_trades.items():
            ea = ExitAnalysis(reason=reason)
            ea.count = len(pnls)
            ea.total_pnl = sum(pnls)
            ea.avg_pnl = ea.total_pnl / ea.count if ea.count else 0
            ea.win_rate = sum(1 for p in pnls if p > 0) / ea.count if ea.count else 0
            self._exit_analysis[reason] = ea

    def _generate_adaptive_params(self) -> AdaptiveParameters:
        """Generate recommended parameters from analysis."""
        params = AdaptiveParameters()

        # 1. Preferred/avoided markets
        for cid, mp in sorted(
            self._market_perf.items(), key=lambda x: x[1].edge_score, reverse=True
        ):
            if mp.total_trades >= 3 and mp.edge_score >= 60:
                params.preferred_markets.append(cid)
            elif mp.total_trades >= 5 and mp.edge_score < 30:
                params.avoided_markets.append(cid)
                params.notes.append(f"⚠️ {cid}: low edge ({mp.edge_score:.0f}), "
                                    f"win rate {mp.win_rate:.0%}")

        # 2. Best time windows
        for tw in sorted(self._time_windows, key=lambda x: x.avg_pnl, reverse=True):
            if tw.total_trades >= 3 and tw.avg_pnl > 0:
                params.best_time_windows.append(tw.name)

        # 3. Conviction threshold adaptation
        all_convictions = [t.get("conviction", 70) for t in self._trade_history]
        winning_convictions = [
            t.get("conviction", 70) for t in self._trade_history if t.get("pnl", 0) > 0
        ]
        if winning_convictions and all_convictions:
            avg_winning_conv = sum(winning_convictions) / len(winning_convictions)
            avg_all_conv = sum(all_convictions) / len(all_convictions)
            # If winning trades have higher conviction, raise threshold
            if avg_winning_conv > avg_all_conv + 5:
                params.conviction_threshold = min(85, avg_winning_conv - 5)
                params.notes.append(
                    f"📊 Winning trades avg conviction: {avg_winning_conv:.0f} "
                    f"vs all: {avg_all_conv:.0f} → threshold: {params.conviction_threshold:.0f}"
                )

        # 4. Position size adjustments by market
        for cid, mp in self._market_perf.items():
            if mp.total_trades >= 5:
                if mp.edge_score >= 70:
                    params.position_size_adjustments[cid] = 1.25  # Size up
                elif mp.edge_score <= 30:
                    params.position_size_adjustments[cid] = 0.5  # Size down

        # 5. Risk factor (scale all sizing)
        recent = self._trade_history[-20:]  # Last 20 trades
        if len(recent) >= 10:
            recent_wr = sum(1 for t in recent if t.get("pnl", 0) > 0) / len(recent)
            if recent_wr >= 0.6:
                params.risk_factor = 1.1  # Slightly more aggressive
                params.notes.append(f"🔥 Hot streak (WR={recent_wr:.0%}) → risk x1.1")
            elif recent_wr <= 0.35:
                params.risk_factor = 0.7  # Pull back
                params.notes.append(f"❄️ Cold streak (WR={recent_wr:.0%}) → risk x0.7")

        # 6. Exit reason insights
        for reason, ea in self._exit_analysis.items():
            if ea.count >= 3:
                if ea.avg_pnl < -20:
                    params.notes.append(
                        f"💡 Exit '{reason}' avg PnL: ${ea.avg_pnl:.2f} — "
                        f"consider adjusting this exit condition"
                    )

        # 7. Framework weights (from learning engine integration)
        fw_pnls: Dict[str, List[float]] = defaultdict(list)
        for t in self._trade_history:
            for fw in t.get("frameworks", []):
                fw_pnls[fw].append(t.get("pnl", 0))
        for fw, pnls in fw_pnls.items():
            if len(pnls) >= 3:
                avg = sum(pnls) / len(pnls)
                params.framework_weights[fw] = max(0.5, min(2.0, 1.0 + avg / 100.0))

        return params

    def _save_analysis(self, params: AdaptiveParameters) -> None:
        """Save analysis results for Obsidian tracking."""
        os.makedirs(self.state_dir, exist_ok=True)
        path = os.path.join(self.state_dir, "performance_analysis.json")

        result = {
            "timestamp": time.time(),
            "total_trades_analyzed": len(self._trade_history),
            "markets": {
                cid: {
                    "total_trades": mp.total_trades,
                    "win_rate": round(mp.win_rate, 3),
                    "total_pnl": round(mp.total_pnl, 2),
                    "avg_pnl": round(mp.avg_pnl, 2),
                    "profit_factor": round(mp.profit_factor, 2),
                    "edge_score": round(mp.edge_score, 1),
                    "avg_hold_seconds": round(mp.avg_hold_seconds, 0),
                }
                for cid, mp in self._market_perf.items()
            },
            "time_windows": {
                tw.name: {
                    "trades": tw.total_trades,
                    "win_rate": round(tw.win_rate, 3),
                    "avg_pnl": round(tw.avg_pnl, 2),
                }
                for tw in self._time_windows if tw.total_trades > 0
            },
            "exit_reasons": {
                reason: {
                    "count": ea.count,
                    "avg_pnl": round(ea.avg_pnl, 2),
                    "win_rate": round(ea.win_rate, 3),
                }
                for reason, ea in self._exit_analysis.items()
            },
            "adaptive_parameters": {
                "conviction_threshold": params.conviction_threshold,
                "preferred_markets": params.preferred_markets,
                "avoided_markets": params.avoided_markets,
                "best_time_windows": params.best_time_windows,
                "risk_factor": params.risk_factor,
                "position_size_adjustments": params.position_size_adjustments,
                "notes": params.notes,
            },
        }

        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(result, f, indent=2)
        os.replace(tmp, path)

    def get_market_performance(self, contract_id: str) -> Optional[MarketPerformance]:
        return self._market_perf.get(contract_id)

    @property
    def market_performances(self) -> Dict[str, MarketPerformance]:
        return self._market_perf

    @property
    def exit_analyses(self) -> Dict[str, ExitAnalysis]:
        return self._exit_analysis

    def get_report(self) -> str:
        """Generate a human-readable performance report."""
        lines = ["# Sovran Performance Report", ""]

        if not self._trade_history:
            return "No trades to analyze yet."

        total = len(self._trade_history)
        wins = sum(1 for t in self._trade_history if t.get("pnl", 0) > 0)
        total_pnl = sum(t.get("pnl", 0) for t in self._trade_history)
        lines.append(f"**Overall:** {total} trades | WR: {wins/total:.0%} | PnL: ${total_pnl:.2f}")
        lines.append("")

        # By market
        lines.append("## By Market")
        for cid, mp in sorted(self._market_perf.items(), key=lambda x: x[1].edge_score, reverse=True):
            lines.append(
                f"- **{cid}**: {mp.total_trades} trades | WR: {mp.win_rate:.0%} | "
                f"PnL: ${mp.total_pnl:.2f} | Edge: {mp.edge_score:.0f}/100"
            )
        lines.append("")

        # By time
        lines.append("## By Time of Day (CT)")
        for tw in self._time_windows:
            if tw.total_trades > 0:
                lines.append(
                    f"- **{tw.name}**: {tw.total_trades} trades | WR: {tw.win_rate:.0%} | "
                    f"Avg PnL: ${tw.avg_pnl:.2f}"
                )
        lines.append("")

        # By exit reason
        lines.append("## By Exit Reason")
        for reason, ea in sorted(self._exit_analysis.items(), key=lambda x: x[1].count, reverse=True):
            lines.append(
                f"- **{reason}**: {ea.count} times | WR: {ea.win_rate:.0%} | "
                f"Avg PnL: ${ea.avg_pnl:.2f}"
            )

        return "\n".join(lines)
