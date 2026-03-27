# Integration Guide: Adding Gambling & Bookkeeping Strategies to sovran_v2

**Step-by-step implementation guide**

Date: March 26, 2026

---

## Overview

This guide shows how to integrate professional gambling strategies and bookkeeping methods into the sovran_v2 AI trading system.

**What We're Adding:**
1. Kelly Criterion position sizing
2. Risk of Ruin monitoring
3. Bankroll management (Ferguson rules)
4. Expected Value filtering
5. Professional trade journaling
6. Performance attribution
7. GTO vs Exploitative strategy selection

---

## Architecture Overview

```
sovran_v2/
├── src/
│   ├── gambling_strategies.py      # NEW: Kelly, RoR, Bankroll mgmt
│   ├── trade_journal.py             # NEW: Professional journaling
│   ├── performance_metrics.py       # NEW: Sharpe, Sortino, attribution
│   ├── risk_monitor.py              # ENHANCED: Add RoR checks
│   ├── position_sizer.py            # ENHANCED: Add Kelly sizing
│   └── decision_engine.py           # ENHANCED: Add EV filtering
├── config/
│   └── gambling_config.yaml         # NEW: Gambling strategy config
└── tests/
    └── test_gambling_strategies.py  # NEW: Unit tests
```

---

## Phase 1: Core Gambling Strategies (Week 1)

### Step 1.1: Install gambling_strategies Module

**File: `sovran_v2/src/gambling_strategies.py`**

```python
"""
Core gambling strategies for trading.
Implements Kelly Criterion, RoR, Bankroll Management.
"""

from kelly_criterion import KellyCriterion
from risk_of_ruin import RiskOfRuinCalculator
from bankroll_management import BankrollManager
from expected_value import ExpectedValueAnalyzer

# [Full implementation from GAMBLING_STRATEGIES_FOR_TRADING.md]
```

**Integration Point:**
```python
# In sovran_v2/src/decision_engine.py

from gambling_strategies import (
    KellyCriterion,
    RiskOfRuinMonitor,
    BankrollManager,
    ExpectedValueAnalyzer
)

class DecisionEngine:
    def __init__(self, config):
        # ... existing code ...

        # Add gambling components
        self.kelly_sizer = KellyCriterion(
            bankroll=config.starting_capital,
            kelly_fraction=config.kelly_fraction  # Default 0.25
        )

        self.ror_monitor = RiskOfRuinMonitor(
            starting_bankroll=config.starting_capital,
            ruin_threshold=0.50  # 50% drawdown = ruin
        )

        self.bankroll_mgr = BankrollManager(
            starting_capital=config.starting_capital
        )

        self.ev_analyzer = ExpectedValueAnalyzer()

    def evaluate_trade_signal(self, signal):
        """Enhanced trade evaluation with gambling strategies."""

        # 1. Check Expected Value
        ev_analysis = self.ev_analyzer.analyze_trade_opportunity(
            entry=signal.entry_price,
            stop=signal.stop_loss,
            target=signal.take_profit,
            win_prob=signal.win_probability
        )

        if not ev_analysis['is_profitable']:
            return {
                'action': 'REJECT',
                'reason': 'Negative EV',
                'ev': ev_analysis['expected_value']
            }

        # 2. Check Bankroll Rules (Ferguson)
        should_stop, reason = self.bankroll_mgr.should_stop_trading_today()
        if should_stop:
            return {
                'action': 'REJECT',
                'reason': reason
            }

        # 3. Kelly Position Sizing
        kelly_size = self.kelly_sizer.calculate_position_size(
            win_prob=signal.win_probability,
            reward_risk=ev_analysis['reward_risk']
        )

        can_take, size_reason = self.bankroll_mgr.can_take_position(kelly_size)
        if not can_take:
            return {
                'action': 'REJECT',
                'reason': size_reason
            }

        # 4. Risk of Ruin Check
        current_metrics = self._get_current_metrics()
        is_safe, safety_reason = self.ror_monitor.is_safe_to_trade(
            current_metrics,
            max_ror=0.01  # 1% RoR threshold
        )

        if not is_safe:
            return {
                'action': 'REJECT',
                'reason': safety_reason
            }

        # 5. All checks passed - TAKE TRADE
        return {
            'action': 'TAKE',
            'position_size': kelly_size,
            'expected_value': ev_analysis['expected_value'],
            'edge': ev_analysis['edge'],
            'kelly_fraction': self.kelly_sizer.kelly_fraction,
            'ror_current': current_metrics.risk_of_ruin
        }
```

### Step 1.2: Configuration

**File: `sovran_v2/config/gambling_config.yaml`**

```yaml
# Gambling Strategies Configuration

kelly_criterion:
  enabled: true
  kelly_fraction: 0.25  # Quarter Kelly (conservative)
  min_edge_required: 0.05  # 5% edge minimum

risk_of_ruin:
  enabled: true
  max_ror_threshold: 0.01  # 1% max RoR (professional standard)
  ruin_drawdown: 0.50  # 50% DD = ruin
  monte_carlo_sims: 10000
  lookback_trades: 100  # Use last 100 trades for RoR calc

bankroll_management:
  enabled: true
  max_position_pct: 0.05  # 5% max per position (Ferguson)
  max_daily_risk_pct: 0.02  # 2% max daily risk
  session_stop_loss_pct: 0.10  # 10% session loss = stop trading
  move_up_threshold: 2.0  # Can increase size at 2x peak capital

expected_value:
  enabled: true
  min_ev_required: 0  # Must be positive
  min_edge_required: 0.05  # 5% edge above breakeven

gto_exploitative:
  mode: "adaptive"  # "gto", "exploitative", or "adaptive"
  confidence_threshold: 0.7  # Switch to exploitative at 70% confidence
  gto_allocation:
    trend_follow: 0.40
    mean_revert: 0.30
    breakout: 0.20
    other: 0.10
```

### Step 1.3: Testing

**File: `sovran_v2/tests/test_gambling_strategies.py`**

```python
import pytest
from src.gambling_strategies import *

def test_kelly_criterion():
    """Test Kelly position sizing."""
    kelly = KellyCriterion(bankroll=100000, kelly_fraction=0.25)

    # 55% WR, 1.5:1 R:R
    size = kelly.calculate_position_size(0.55, 1.5)

    assert size > 0
    assert size <= 100000 * 0.25  # Max quarter Kelly

def test_risk_of_ruin():
    """Test RoR calculation."""
    ror_calc = RiskOfRuinCalculator(starting_bankroll=25000)

    result = ror_calc.monte_carlo(
        win_rate=0.55,
        avg_win=150,
        avg_loss=100,
        position_size=500,
        num_trades=1000,
        num_sims=1000  # Reduced for speed
    )

    assert result.risk_of_ruin >= 0
    assert result.risk_of_ruin <= 1

def test_bankroll_management():
    """Test Ferguson bankroll rules."""
    mgr = BankrollManager(starting_capital=10000)

    # Check limits
    assert mgr.max_position_size() == 500  # 5% of 10k
    assert mgr.max_daily_risk() == 200  # 2% of 10k
    assert mgr.session_stop_loss() == 1000  # 10% of 10k

def test_expected_value():
    """Test EV calculation."""
    ev_calc = ExpectedValueAnalyzer()

    # Positive EV trade
    ev = ev_calc.calculate_ev(0.55, 150, 100)
    assert ev > 0  # Should be profitable

    # Negative EV trade
    ev = ev_calc.calculate_ev(0.45, 100, 150)
    assert ev < 0  # Should be unprofitable

if __name__ == "__main__":
    pytest.main([__file__])
```

---

## Phase 2: Trade Journaling (Week 2)

### Step 2.1: Install Trade Journal

**File: `sovran_v2/src/trade_journal.py`**

```python
"""
Professional trade journaling system.
Auto-logs all trades with complete data.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import json

# [Full implementation from TRADE_JOURNAL_TEMPLATE.md]
```

### Step 2.2: Hook into Trading Loop

```python
# In sovran_v2/src/main.py

from trade_journal import TradeJournal, TradeJournalEntry

class TradingSystem:
    def __init__(self, config):
        # ... existing code ...

        # Add journal
        self.journal = TradeJournal(
            journal_path="data/trade_journal.json"
        )

    def on_trade_entry(self, signal):
        """Called when entering trade."""

        # Create journal entry
        entry = TradeJournalEntry(
            trade_id=generate_unique_id(),
            entry_time=datetime.now(),
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=signal.entry_price,
            position_size=signal.position_size,
            stop_loss_planned=signal.stop_loss,
            take_profit_planned=signal.take_profit,
            strategy_name=signal.strategy,
            market_regime=self.detect_regime(),
            entry_reason=signal.reason,
            win_probability_estimated=signal.win_prob,
            reward_risk_planned=signal.reward_risk,
            commissions=self.calculate_commissions(signal),
            pre_trade_emotion=5,  # Default
            confidence_level=signal.confidence
        )

        self.journal.add_trade(entry)
        return entry.trade_id

    def on_trade_exit(self, trade_id, exit_price, exit_reason):
        """Called when exiting trade."""

        self.journal.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            exit_time=datetime.now(),
            exit_order_type="MARKET",
            what_worked=self.analyze_what_worked(trade_id),
            what_to_improve=self.analyze_improvements(trade_id),
            lessons_learned=self.extract_lessons(trade_id)
        )

    def generate_daily_report(self):
        """Generate end-of-day report."""

        summary = self.journal.get_performance_summary()
        strategy_breakdown = self.journal.get_strategy_breakdown()

        report = f"""
Daily Report - {datetime.now().strftime('%Y-%m-%d')}
{'='*60}

Performance:
  Total Trades: {summary['total_trades']}
  Win Rate: {summary['win_rate']*100:.1f}%
  Net P&L: ${summary['total_net_pnl']:,.2f}
  Profit Factor: {summary['profit_factor']:.2f}
  Expectancy: ${summary['expectancy']:.2f}

Strategy Breakdown:
{strategy_breakdown.to_string(index=False)}

Action Items:
{self.generate_action_items(summary, strategy_breakdown)}
"""

        # Save and print
        self.save_report(report)
        print(report)

        return report
```

### Step 2.3: Automated Reporting

**File: `sovran_v2/src/reporting.py`**

```python
"""
Automated reporting system.
Generates daily, weekly, monthly reports.
"""

class ReportGenerator:
    def __init__(self, journal):
        self.journal = journal

    def daily_report(self):
        """Generate daily report."""
        summary = self.journal.get_performance_summary()

        # Save to file
        filename = f"reports/daily_{datetime.now().strftime('%Y%m%d')}.md"
        with open(filename, 'w') as f:
            f.write(self.format_daily_report(summary))

    def weekly_report(self):
        """Generate weekly report."""
        # [Implementation]
        pass

    def monthly_report(self):
        """Generate monthly report."""
        # [Implementation]
        pass
```

---

## Phase 3: Performance Metrics (Week 3)

### Step 3.1: Install Performance Metrics

**File: `sovran_v2/src/performance_metrics.py`**

```python
"""
Professional performance metrics.
Sharpe, Sortino, Calmar, Attribution Analysis.
"""

import numpy as np
import pandas as pd

# [Full implementation from PROFESSIONAL_BOOKKEEPING_METHODS.md]
```

### Step 3.2: Add to Reporting

```python
# In sovran_v2/src/reporting.py

from performance_metrics import PerformanceMetrics, AttributionAnalysis

class ReportGenerator:
    def comprehensive_report(self):
        """Generate comprehensive performance report."""

        # Get returns
        returns = self.calculate_returns()
        trades_pnl = self.get_trades_pnl()

        # Calculate metrics
        metrics = PerformanceMetrics(returns)
        report = metrics.comprehensive_report(trades_pnl)

        # Attribution analysis
        attribution = AttributionAnalysis(self.journal.trades)
        strategy_attr = attribution.strategy_attribution()
        regime_attr = attribution.regime_attribution()

        # Format report
        output = f"""
COMPREHENSIVE PERFORMANCE REPORT
{'='*70}

Performance Metrics:
  Sharpe Ratio: {report['sharpe_ratio']:.2f}
  Sortino Ratio: {report['sortino_ratio']:.2f}
  Calmar Ratio: {report['calmar_ratio']:.2f}
  Max Drawdown: {report['maximum_drawdown']*100:.2f}%
  Profit Factor: {report['profit_factor']:.2f}
  Win Rate: {report['win_rate']*100:.1f}%

Strategy Attribution:
{strategy_attr.to_string(index=False)}

Regime Attribution:
{regime_attr.to_string(index=False)}

Action Items:
{self.generate_action_items(report, strategy_attr)}
"""

        return output
```

---

## Phase 4: Real-Time Monitoring (Week 4)

### Step 4.1: Dashboard

**File: `sovran_v2/src/dashboard.py`**

```python
"""
Real-time performance dashboard.
Shows Kelly sizing, RoR, current metrics.
"""

import streamlit as st
from gambling_strategies import *
from performance_metrics import *

def run_dashboard():
    st.title("sovran_v2 Performance Dashboard")

    # Load data
    journal = TradeJournal("data/trade_journal.json")
    summary = journal.get_performance_summary()

    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total P&L", f"${summary['total_net_pnl']:,.2f}")

    with col2:
        st.metric("Win Rate", f"{summary['win_rate']*100:.1f}%")

    with col3:
        st.metric("Profit Factor", f"{summary['profit_factor']:.2f}")

    with col4:
        st.metric("Expectancy", f"${summary['expectancy']:.2f}")

    # Risk of Ruin
    st.subheader("Risk of Ruin")
    ror_calc = RiskOfRuinCalculator(get_current_capital())
    result = ror_calc.calculate_from_trade_history(
        get_trade_pnls(),
        num_future_trades=500,
        num_sims=5000
    )

    st.metric("Current RoR", f"{result.risk_of_ruin*100:.2f}%",
              delta="Safe" if result.risk_of_ruin < 0.05 else "Risky")

    # Strategy breakdown
    st.subheader("Strategy Performance")
    strategy_df = journal.get_strategy_breakdown()
    st.dataframe(strategy_df)

    # Performance chart
    st.subheader("Equity Curve")
    equity_curve = calculate_equity_curve()
    st.line_chart(equity_curve)

if __name__ == "__main__":
    run_dashboard()
```

---

## Configuration Examples

### Conservative (Chris Ferguson Style)

```yaml
kelly_fraction: 0.125  # Eighth Kelly - very conservative
max_position_pct: 0.03  # 3% max
max_daily_risk_pct: 0.01  # 1% daily risk
session_stop_loss_pct: 0.05  # 5% session stop
max_ror_threshold: 0.005  # 0.5% RoR
```

### Moderate (Professional Standard)

```yaml
kelly_fraction: 0.25  # Quarter Kelly
max_position_pct: 0.05  # 5% max
max_daily_risk_pct: 0.02  # 2% daily risk
session_stop_loss_pct: 0.10  # 10% session stop
max_ror_threshold: 0.01  # 1% RoR
```

### Aggressive (High Growth)

```yaml
kelly_fraction: 0.50  # Half Kelly
max_position_pct: 0.10  # 10% max
max_daily_risk_pct: 0.05  # 5% daily risk
session_stop_loss_pct: 0.15  # 15% session stop
max_ror_threshold: 0.05  # 5% RoR
```

---

## Validation Checklist

Before deploying to live trading:

- [ ] Kelly sizing tested with historical data
- [ ] RoR calculation validated (compare to known formulas)
- [ ] Bankroll rules enforced in all conditions
- [ ] Trade journal auto-populates correctly
- [ ] Performance metrics match manual calculations
- [ ] Attribution analysis identifies top strategies
- [ ] Dashboard updates in real-time
- [ ] All unit tests passing
- [ ] Configuration file validated
- [ ] Emergency stop-loss mechanisms working

---

## Monitoring & Alerts

**Set up alerts for:**

1. **Risk of Ruin > 5%** → Email + SMS alert
2. **Daily loss > 10%** → Stop trading, notify user
3. **Consecutive losses > 5** → Warning alert
4. **Profit Factor < 1.0** → Review strategies
5. **Sharpe Ratio < 1.0** → Performance degradation warning

```python
# In sovran_v2/src/alerts.py

class AlertSystem:
    def check_alerts(self, metrics):
        """Check for alert conditions."""

        alerts = []

        if metrics.risk_of_ruin > 0.05:
            alerts.append({
                'level': 'CRITICAL',
                'message': f'RoR too high: {metrics.risk_of_ruin*100:.1f}%',
                'action': 'STOP_TRADING'
            })

        if metrics.daily_loss_pct > 0.10:
            alerts.append({
                'level': 'CRITICAL',
                'message': f'Daily loss limit hit: {metrics.daily_loss_pct*100:.1f}%',
                'action': 'STOP_TRADING'
            })

        # ... more checks ...

        return alerts
```

---

## Expected Results

After full implementation:

**Risk Management:**
- Position sizes automatically adjusted via Kelly
- Trading stops at daily/session limits
- RoR continuously monitored
- All trades filtered for positive EV

**Performance Tracking:**
- Every trade journaled automatically
- Daily reports generated
- Strategy attribution tracked
- Sharpe/Sortino/Calmar calculated real-time

**Continuous Improvement:**
- Identify best/worst strategies
- Learn from mistakes systematically
- Optimize capital allocation
- Adapt to changing market regimes

---

## Troubleshooting

**Issue: Kelly sizing too aggressive**
- Solution: Reduce kelly_fraction (use 0.125 or 0.10)

**Issue: RoR calculation slow**
- Solution: Reduce num_sims (use 5000 instead of 10000)

**Issue: Too many trades rejected**
- Solution: Lower min_edge_required (try 0.03 instead of 0.05)

**Issue: Journal file too large**
- Solution: Archive old trades monthly, keep only recent

---

## Next Steps

1. **Week 1-2:** Implement core gambling strategies
2. **Week 3:** Add trade journaling
3. **Week 4:** Implement performance metrics
4. **Week 5:** Build dashboard
5. **Week 6:** Paper trade testing
6. **Week 7+:** Live trading with monitoring

---

**End of INTEGRATION_GUIDE.md**
