import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict

@dataclass
class TradeRecord:
    """Complete record of a closed trade."""
    trade_id: str
    contract_id: str
    side: str                        # "long" or "short"
    entry_time: float
    exit_time: float
    entry_price: float
    exit_price: float
    size: int
    pnl: float
    fees: float
    net_pnl: float
    conviction: float
    thesis: str
    frameworks_used: List[str]
    regime_at_entry: str
    atr_at_entry: float
    vpin_at_entry: float
    ofi_at_entry: float
    hold_time_seconds: float = 0.0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    hit_target: bool = False
    hit_stop: bool = False
    verdict: str = ""

@dataclass
class PerformanceMatrix:
    """Aggregated performance statistics."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_win_loss_ratio: float = 0.0
    total_pnl: float = 0.0
    profit_factor: float = 0.0
    framework_stats: Dict[str, dict] = field(default_factory=dict)
    regime_stats: Dict[str, dict] = field(default_factory=dict)
    conviction_stats: Dict[str, dict] = field(default_factory=dict)
    kelly_optimal_fraction: float = 0.0
    recommended_kelly_fraction: float = 0.0

@dataclass
class LiveParameters:
    """Parameters that are dynamically updated based on performance."""
    win_rate: float = 0.50
    avg_win_loss_ratio: float = 1.8
    kelly_fraction: float = 0.5
    framework_weights: Dict[str, float] = field(default_factory=lambda: {
        "momentum": 1.0, "mean_reversion": 1.0, "order_flow": 1.5, "volatility_breakout": 1.0
    })
    conviction_threshold_adjustment: float = 0.0
    last_updated: float = 0.0

class LearningEngine:
    """Closes the feedback loop between trade outcomes and future decisions."""
    
    def __init__(self, obsidian_path: str = r"C:\KAI\obsidian_vault\Sovran AI",
                 config_path: str = r"C:\KAI\sovran_v2\config"):
        self.obsidian_path = obsidian_path
        self.config_path = config_path
        self.history: List[TradeRecord] = []
        self.matrix = PerformanceMatrix()
        self.params = LiveParameters()
        self.logger = logging.getLogger("sovran.learning")
        
        # Ensure directories exist
        os.makedirs(os.path.join(self.obsidian_path, "Trader Diary"), exist_ok=True)
        os.makedirs(os.path.join(self.obsidian_path, "Performance"), exist_ok=True)
        os.makedirs(self.config_path, exist_ok=True)

    def record_trade(self, record: TradeRecord) -> None:
        """Record a completed trade and update all statistics."""
        record.hold_time_seconds = record.exit_time - record.entry_time
        record.verdict = "thesis_confirmed" if record.net_pnl > 0 else "thesis_refuted"
        
        self.history.append(record)
        self._update_matrix()
        self._update_parameters()
        self._write_journal_entry(record)
        self._write_performance_update()
        self._export_live_parameters()
        self._export_performance_matrix()
        self.save_history()

    def get_performance_matrix(self) -> PerformanceMatrix:
        return self.matrix

    def get_live_parameters(self) -> LiveParameters:
        return self.params

    def _update_matrix(self) -> None:
        if not self.history:
            return

        m = PerformanceMatrix()
        m.total_trades = len(self.history)
        win_pnls = [r.net_pnl for r in self.history if r.net_pnl > 0]
        loss_pnls = [r.net_pnl for r in self.history if r.net_pnl <= 0]
        
        m.wins = len(win_pnls)
        m.losses = len(loss_pnls)
        m.win_rate = m.wins / m.total_trades
        m.avg_win = sum(win_pnls) / m.wins if m.wins > 0 else 0.0
        m.avg_loss = abs(sum(loss_pnls) / m.losses) if m.losses > 0 else 0.0
        m.avg_win_loss_ratio = m.avg_win / m.avg_loss if m.avg_loss > 0 else 0.0
        m.total_pnl = sum(r.net_pnl for r in self.history)
        m.profit_factor = sum(win_pnls) / abs(sum(loss_pnls)) if loss_pnls and sum(loss_pnls) != 0 else float('inf')

        # Stats trackers
        framework_data = {}
        regime_data = {}
        conviction_data = {}

        for r in self.history:
            # Per-framework
            for f in r.frameworks_used:
                d = framework_data.setdefault(f, {"trades": 0, "wins": 0, "pnl": 0.0})
                d["trades"] += 1
                if r.net_pnl > 0: d["wins"] += 1
                d["pnl"] += r.net_pnl
            
            # Per-regime
            rd = regime_data.setdefault(r.regime_at_entry, {"trades": 0, "wins": 0, "pnl": 0.0})
            rd["trades"] += 1
            if r.net_pnl > 0: rd["wins"] += 1
            rd["pnl"] += r.net_pnl

            # Per-conviction (buckets of 10)
            bucket_start = int(r.conviction // 10 * 10)
            bucket = f"{bucket_start}-{bucket_start+10}"
            cd = conviction_data.setdefault(bucket, {"trades": 0, "wins": 0})
            cd["trades"] += 1
            if r.net_pnl > 0: cd["wins"] += 1

        # Finalize stats
        for f, d in framework_data.items():
            d["win_rate"] = d["wins"] / d["trades"]
        m.framework_stats = framework_data
        m.regime_stats = regime_data
        m.conviction_stats = conviction_data

        # Kelly
        p = m.win_rate
        b = m.avg_win_loss_ratio
        if b > 0:
            m.kelly_optimal_fraction = (b * p - (1 - p)) / b
        m.recommended_kelly_fraction = max(0, m.kelly_optimal_fraction * 0.5)
        self.matrix = m

    def _update_parameters(self) -> None:
        if self.matrix.total_trades >= 20:
            self.params.win_rate = self.matrix.win_rate
            self.params.avg_win_loss_ratio = self.matrix.avg_win_loss_ratio
            self.params.kelly_fraction = self.matrix.recommended_kelly_fraction

        # Framework weights
        for f in self.params.framework_weights:
            if f in self.matrix.framework_stats:
                f_stats = self.matrix.framework_stats[f]
                if self.matrix.win_rate > 0:
                    scale = f_stats["win_rate"] / self.matrix.win_rate
                    new_weight = self.params.framework_weights[f] * scale
                    self.params.framework_weights[f] = max(0.3, min(3.0, new_weight))

        # Conviction threshold adjustment
        if self.matrix.win_rate < 0.40 and self.matrix.total_trades >= 10:
            self.params.conviction_threshold_adjustment = 10.0
        elif self.matrix.win_rate > 0.65 and self.matrix.total_trades >= 10:
            self.params.conviction_threshold_adjustment = -5.0
        else:
            self.params.conviction_threshold_adjustment = 0.0
            
        self.params.last_updated = time.time()

    def _write_journal_entry(self, record: TradeRecord) -> None:
        date_str = datetime.fromtimestamp(record.entry_time).strftime("%Y-%m-%d")
        filename = f"{date_str}-trade-{record.trade_id}.md"
        filepath = os.path.join(self.obsidian_path, "Trader Diary", filename)
        
        lesson = "Keep doing what works." if record.net_pnl > 0 else "Review entry alignment with higher timeframe."
        if record.hit_stop: lesson = "Stop loss hit. Check if volatility was underestimated."
        
        content = f"""# Trade Journal: {record.side.upper()} {record.contract_id} — {record.verdict}

## Summary
- **Side**: {record.side}
- **Entry**: {record.entry_price} at {datetime.fromtimestamp(record.entry_time).isoformat()}
- **Exit**: {record.exit_price} at {datetime.fromtimestamp(record.exit_time).isoformat()}
- **PnL**: ${record.net_pnl:.2f}
- **Hold Time**: {record.hold_time_seconds:.1f}s

## Thesis
{record.thesis}

## Market Context
- Regime: {record.regime_at_entry}
- ATR: {record.atr_at_entry:.2f} | VPIN: {record.vpin_at_entry:.3f} | OFI Z: {record.ofi_at_entry:.2f}
- Frameworks: {", ".join(record.frameworks_used)}
- Conviction: {record.conviction:.1f}

## Outcome
- Max Favorable Excursion: ${record.max_favorable_excursion:.2f}
- Max Adverse Excursion: ${record.max_adverse_excursion:.2f}
- Hit Target: {record.hit_target} | Hit Stop: {record.hit_stop}
- Verdict: {record.verdict}

## Lesson
{lesson}
"""
        with open(filepath, "w") as f:
            f.write(content)

    def _write_performance_update(self) -> None:
        filepath = os.path.join(self.obsidian_path, "Performance", "performance_matrix.md")
        m = self.matrix
        content = f"""# Performance Matrix
Updated: {datetime.now().isoformat()}

## Key Stats
- **Total Trades**: {m.total_trades}
- **Win Rate**: {m.win_rate:.2%}
- **Avg Win/Loss**: {m.avg_win_loss_ratio:.2f}
- **Profit Factor**: {m.profit_factor:.2f}
- **Total PnL**: ${m.total_pnl:.2f}
- **Recommended Kelly**: {m.recommended_kelly_fraction:.2f}

## Framework Performance
"""
        for f, s in m.framework_stats.items():
            content += f"- **{f}**: {s['trades']} trades, {s['win_rate']:.2%} win rate, ${s['pnl']:.2f} PnL\n"
        
        with open(filepath, "w") as f:
            f.write(content)

    def _export_live_parameters(self) -> None:
        path = os.path.join(self.config_path, "live_parameters.json")
        with open(path, "w") as f:
            json.dump(asdict(self.params), f, indent=4)

    def _export_performance_matrix(self) -> None:
        path = os.path.join(self.config_path, "performance_matrix.json")
        with open(path, "w") as f:
            json.dump(asdict(self.matrix), f, indent=4)

    def load_history(self) -> None:
        path = os.path.join(self.config_path, "trade_history.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                self.history = [TradeRecord(**r) for r in data]
            self._update_matrix()
            self._update_parameters()

    def save_history(self) -> None:
        path = os.path.join(self.config_path, "trade_history.json")
        with open(path, "w") as f:
            json.dump([asdict(r) for r in self.history], f, indent=4)
