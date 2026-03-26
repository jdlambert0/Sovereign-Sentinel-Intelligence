# Layer 4: The Memory (Learning Loop) — Technical Specification

> **Author**: CIO Agent  
> **Date**: 2026-03-25  
> **For**: Coding Agent  
> **Depends On**: Layer 0 (broker), Layer 1 (risk), Layer 3 (decision)  
> **Output Files**: `src/learning.py`, `tests/test_learning.py`

---

## 1. Overview

The Memory closes the feedback loop. After every trade closes, it records the full context (thesis, market conditions, outcome), updates a performance matrix, and adjusts parameters that Layer 1 (Guardian) and Layer 3 (Mind) read on their next cycle. This is what makes the system self-evolving.

It also writes structured journal entries to the Obsidian vault for permanent memory.

## 2. Data Structures

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import time

@dataclass
class TradeRecord:
    """Complete record of a closed trade."""
    trade_id: str                    # Unique ID (timestamp-based)
    contract_id: str
    side: str                        # "long" or "short"
    entry_time: float                # Unix timestamp
    exit_time: float                 # Unix timestamp
    entry_price: float
    exit_price: float
    size: int                        # Number of contracts
    pnl: float                       # Realized P&L in dollars
    fees: float                      # Trading fees
    net_pnl: float                   # pnl - fees
    
    # Context at entry
    conviction: float                # Conviction score at entry
    thesis: str                      # Why we entered
    frameworks_used: List[str]       # Which frameworks generated the signal
    regime_at_entry: str             # Market regime at entry
    atr_at_entry: float              # ATR at entry
    vpin_at_entry: float             # VPIN at entry
    ofi_at_entry: float              # OFI Z-score at entry
    
    # Outcome analysis
    hold_time_seconds: float = 0.0   # How long the trade was held
    max_favorable_excursion: float = 0.0   # Best unrealized PnL during trade
    max_adverse_excursion: float = 0.0     # Worst unrealized PnL during trade
    hit_target: bool = False          # Did TP get hit?
    hit_stop: bool = False            # Did SL get hit?
    verdict: str = ""                 # "thesis_confirmed" or "thesis_refuted"

@dataclass
class PerformanceMatrix:
    """Aggregated performance statistics. Updated after every trade."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_win_loss_ratio: float = 0.0
    total_pnl: float = 0.0
    profit_factor: float = 0.0       # gross_wins / gross_losses
    
    # Per-framework stats
    framework_stats: Dict[str, dict] = field(default_factory=dict)
    # e.g., {"momentum": {"trades": 10, "wins": 6, "win_rate": 0.6, "avg_rr": 1.5}}
    
    # Per-regime stats
    regime_stats: Dict[str, dict] = field(default_factory=dict)
    
    # Per-conviction-bucket stats
    conviction_stats: Dict[str, dict] = field(default_factory=dict)
    # e.g., {"55-65": {"trades": 5, "wins": 2}, "65-75": {"trades": 8, "wins": 6}}
    
    # Kelly calculation
    kelly_optimal_fraction: float = 0.0
    recommended_kelly_fraction: float = 0.0  # Half-Kelly applied

@dataclass
class LiveParameters:
    """Parameters that are dynamically updated based on performance.
    Read by Layer 1 (risk config) and Layer 3 (decision config) on each cycle."""
    win_rate: float = 0.50
    avg_win_loss_ratio: float = 1.8
    kelly_fraction: float = 0.5
    
    # Framework weights (adjusted by performance)
    framework_weights: Dict[str, float] = field(default_factory=lambda: {
        "momentum": 1.0,
        "mean_reversion": 1.0,
        "order_flow": 1.5,
        "volatility_breakout": 1.0
    })
    
    # Conviction threshold adjustment
    conviction_threshold_adjustment: float = 0.0  # Added to base threshold
    
    last_updated: float = 0.0
```

## 3. Class Design

```python
class LearningEngine:
    """
    Closes the feedback loop between trade outcomes and future decisions.
    
    After each trade:
    1. Records the full trade context
    2. Updates the performance matrix
    3. Recalculates optimal parameters
    4. Writes to Obsidian vault for permanent memory
    5. Exports LiveParameters for other layers to read
    """
    
    def __init__(self, obsidian_path: str = r"C:\KAI\obsidian_vault\Sovran AI",
                 config_path: str = r"C:\KAI\sovran_v2\config"):
        """
        obsidian_path: Path to the Sovran AI vault for journal entries
        config_path: Path to config/ directory for live_parameters.json
        """
    
    # --- Core Methods ---
    
    def record_trade(self, record: TradeRecord) -> None:
        """
        Record a completed trade and update all statistics.
        
        Steps:
        1. Add record to trade history
        2. Update performance matrix
        3. Recalculate live parameters
        4. Write journal entry to Obsidian
        5. Export live_parameters.json
        """
    
    def get_performance_matrix(self) -> PerformanceMatrix:
        """Return current performance statistics."""
    
    def get_live_parameters(self) -> LiveParameters:
        """Return current dynamic parameters for other layers."""
    
    # --- Statistics ---
    
    def _update_matrix(self) -> None:
        """
        Recalculate the performance matrix from trade history.
        
        Computes:
        - Overall win rate, avg win/loss, profit factor
        - Per-framework win rates and avg returns
        - Per-regime win rates
        - Per-conviction-bucket win rates
        - Kelly optimal fraction
        """
    
    def _update_parameters(self) -> None:
        """
        Recalculate live parameters based on performance matrix.
        
        Rules:
        - win_rate and avg_win_loss_ratio from matrix (only after 20+ trades for stability)
        - Framework weights: scale by (framework_win_rate / overall_win_rate)
          - Winning frameworks get higher weight, losing ones get lower
          - Minimum weight 0.3, maximum 3.0 (no framework completely silenced or dominant)
        - Conviction threshold adjustment:
          - If recent win_rate < 40%: raise threshold by +10 (be more selective)
          - If recent win_rate > 65%: lower threshold by -5 (hunt more aggressively)
          - Otherwise: no adjustment
        - Kelly fraction: use half-Kelly of calculated optimal
        """
    
    # --- Obsidian Integration ---
    
    def _write_journal_entry(self, record: TradeRecord) -> None:
        """
        Write a structured trade journal entry to Obsidian.
        
        File: Trader Diary/YYYY-MM-DD-trade-{trade_id}.md
        
        Format:
        ```markdown
        # Trade Journal: {side} {contract} — {verdict}
        
        ## Summary
        - **Side**: {side}
        - **Entry**: {entry_price} at {entry_time}
        - **Exit**: {exit_price} at {exit_time}
        - **PnL**: ${net_pnl}
        - **Hold Time**: {hold_time}
        
        ## Thesis
        {thesis}
        
        ## Market Context
        - Regime: {regime}
        - ATR: {atr} | VPIN: {vpin} | OFI Z: {ofi}
        - Frameworks: {frameworks_used}
        - Conviction: {conviction}
        
        ## Outcome
        - Max Favorable Excursion: ${mfe}
        - Max Adverse Excursion: ${mae}
        - Hit Target: {hit_target} | Hit Stop: {hit_stop}
        - Verdict: {verdict}
        
        ## Lesson
        {auto-generated lesson based on outcome}
        ```
        """
    
    def _write_performance_update(self) -> None:
        """
        Update Obsidian with current performance summary.
        Writes to: Performance/performance_matrix.md
        """
    
    # --- Persistence ---
    
    def _export_live_parameters(self) -> None:
        """Write live_parameters.json to config directory."""
    
    def _export_performance_matrix(self) -> None:
        """Write performance_matrix.json to config directory."""
    
    def load_history(self) -> None:
        """Load existing trade history and performance matrix from JSON files on startup."""
    
    def save_history(self) -> None:
        """Save trade history to JSON for persistence across restarts."""
```

## 4. Files Written

| File | Purpose |
|------|---------|
| `config/live_parameters.json` | Dynamic parameters read by Layer 1 + Layer 3 |
| `config/performance_matrix.json` | Full performance stats |
| `config/trade_history.json` | All trade records for persistence |
| `Obsidian: Trader Diary/YYYY-MM-DD-trade-{id}.md` | Per-trade journal entries |

## 5. Test Requirements

### Unit Tests
- `test_record_trade_updates_matrix` — record a winning trade → matrix shows 1 win
- `test_record_multiple_trades` — 3 wins, 2 losses → correct win rate, avg win/loss
- `test_win_rate_calculation` — verify exact math
- `test_avg_win_loss_ratio` — verify exact math
- `test_profit_factor` — gross_wins / gross_losses
- `test_framework_stats` — trades with different frameworks → correct per-framework stats
- `test_regime_stats` — trades in different regimes → correct per-regime stats
- `test_conviction_bucket_stats` — conviction 60 goes in "55-65" bucket
- `test_kelly_calculation` — from known win rate + ratio → correct Kelly
- `test_parameter_update_after_20_trades` — params only change after 20 trades
- `test_framework_weight_adjustment` — winning framework gets higher weight
- `test_framework_weight_bounds` — weights clamped to [0.3, 3.0]
- `test_conviction_threshold_low_winrate` — win rate < 40% → threshold +10
- `test_conviction_threshold_high_winrate` — win rate > 65% → threshold -5
- `test_journal_entry_format` — verify markdown output structure
- `test_live_parameters_export` — verify JSON file output
- `test_load_and_save_history` — save → load → verify identical
- `test_empty_history` — no trades → reasonable defaults

## 6. Acceptance Criteria

- [ ] `record_trade()` updates all statistics correctly
- [ ] Performance matrix matches hand-computed values for 5+ trades
- [ ] Per-framework, per-regime, per-conviction stats are accurate
- [ ] Kelly fraction calculated correctly from performance data
- [ ] Framework weights adjust based on relative performance
- [ ] Conviction threshold raises when losing, lowers when winning
- [ ] Parameters only shift after 20+ trades (stability)
- [ ] Journal entries written to Obsidian in correct format
- [ ] `live_parameters.json` exported correctly
- [ ] Trade history persists across save/load cycles
- [ ] All unit tests pass (18+)
- [ ] No `except: pass`
- [ ] Code is under 400 lines

---
#specification #layer-4 #learning #memory #coding-agent
