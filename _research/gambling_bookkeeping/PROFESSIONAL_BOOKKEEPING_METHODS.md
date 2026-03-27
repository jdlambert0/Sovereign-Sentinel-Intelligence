# Professional Bookkeeping Methods for Trading

**Comprehensive guide to bookkeeper-level precision for AI trading systems**

Date: March 26, 2026
Focus: Trade Journals, Performance Metrics, Attribution Analysis, Tax Optimization, Audit Trails

---

## Table of Contents

1. [Trade Journal Best Practices](#trade-journal-best-practices)
2. [Performance Metrics & Ratios](#performance-metrics--ratios)
3. [Attribution Analysis](#attribution-analysis)
4. [Double-Entry Bookkeeping for Trading](#double-entry-bookkeeping-for-trading)
5. [Tax Optimization Strategies](#tax-optimization-strategies)
6. [Audit Trails & Compliance](#audit-trails--compliance)
7. [Professional Bookmaker Practices](#professional-bookmaker-practices)
8. [Implementation for sovran_v2](#implementation-for-sovran_v2)

---

## Trade Journal Best Practices

### What to Record (The Complete List)

**Every trade must include:**

1. **Timestamp Data**
   - Entry date/time (to the second)
   - Exit date/time
   - Time in trade (duration)
   - Market session (pre-market, RTH, after-hours)

2. **Trade Mechanics**
   - Symbol/Instrument
   - Direction (LONG/SHORT)
   - Entry price
   - Exit price
   - Position size (shares/contracts)
   - Stop loss price (planned and actual)
   - Take profit target (planned and actual)

3. **Financial Data**
   - Gross P&L
   - Commissions & fees
   - Slippage
   - Net P&L
   - R-multiple (P&L / Risk)
   - ROI % on risk capital

4. **Pre-Trade Analysis**
   - Setup/Strategy name (e.g., "Trend Follow", "Mean Revert")
   - Market regime (trending, ranging, volatile, quiet)
   - Why entered (specific setup criteria)
   - Expected probability of success
   - Risk/Reward ratio planned

5. **Execution Quality**
   - Entry execution quality (slippage)
   - Exit execution quality
   - Partial fills (if any)
   - Order type (market, limit, stop)

6. **Emotional State**
   - Pre-trade emotional state (1-10 scale)
   - Post-trade emotional state
   - Tilt level (if any)
   - Confidence level

7. **Post-Trade Analysis**
   - What worked well
   - What could improve
   - Mistakes made
   - Lessons learned
   - Would you take this trade again? (Y/N)

8. **Context Data**
   - Market conditions (VIX, sector performance)
   - News events impacting trade
   - Correlation to other positions
   - Overnight risk (held overnight? Y/N)

### Python Implementation: Professional Trade Journal

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json


class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class MarketRegime(Enum):
    STRONG_TREND = "strong_trend"
    WEAK_TREND = "weak_trend"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    UNKNOWN = "unknown"


@dataclass
class TradeJournalEntry:
    """
    Complete trade journal entry with all data.
    Based on professional trading journal best practices.
    """
    # Unique identifier
    trade_id: str

    # Timestamps
    entry_time: datetime
    exit_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Trade mechanics
    symbol: str = ""
    direction: TradeDirection = TradeDirection.LONG
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    position_size: float = 0.0
    stop_loss_planned: float = 0.0
    stop_loss_actual: Optional[float] = None
    take_profit_planned: float = 0.0
    take_profit_actual: Optional[float] = None

    # Financial
    gross_pnl: Optional[float] = None
    commissions: float = 0.0
    slippage: float = 0.0
    net_pnl: Optional[float] = None
    r_multiple: Optional[float] = None  # P&L / Risk
    roi_pct: Optional[float] = None

    # Pre-trade analysis
    strategy_name: str = ""
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    entry_reason: str = ""
    win_probability_estimated: float = 0.5
    reward_risk_planned: float = 0.0

    # Execution quality
    entry_slippage_pct: float = 0.0
    exit_slippage_pct: float = 0.0
    partial_fills: int = 0
    entry_order_type: str = "MARKET"
    exit_order_type: str = "MARKET"

    # Emotional state (1-10 scale)
    pre_trade_emotion: int = 5
    post_trade_emotion: int = 5
    tilt_level: int = 0  # 0 = no tilt, 10 = full tilt
    confidence_level: int = 5

    # Post-trade analysis
    what_worked: str = ""
    what_to_improve: str = ""
    mistakes_made: str = ""
    lessons_learned: str = ""
    would_take_again: bool = True

    # Context
    market_vix: Optional[float] = None
    news_events: str = ""
    held_overnight: bool = False
    correlated_positions: str = ""

    # Status
    status: TradeStatus = TradeStatus.OPEN

    def calculate_metrics(self):
        """Calculate derived metrics after trade closes."""
        if self.exit_time and self.entry_time:
            self.duration_seconds = (self.exit_time - self.entry_time).total_seconds()

        if self.exit_price and self.entry_price:
            # Gross P&L
            if self.direction == TradeDirection.LONG:
                price_diff = self.exit_price - self.entry_price
            else:
                price_diff = self.entry_price - self.exit_price

            self.gross_pnl = price_diff * self.position_size

            # Net P&L
            self.net_pnl = self.gross_pnl - self.commissions - self.slippage

            # R-multiple
            risk = abs(self.entry_price - self.stop_loss_planned) * self.position_size
            if risk > 0:
                self.r_multiple = self.net_pnl / risk
            else:
                self.r_multiple = 0.0

            # ROI %
            if risk > 0:
                self.roi_pct = (self.net_pnl / risk) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert enums to strings
        data['direction'] = self.direction.value
        data['market_regime'] = self.market_regime.value
        data['status'] = self.status.value
        # Convert datetime to ISO string
        data['entry_time'] = self.entry_time.isoformat()
        if self.exit_time:
            data['exit_time'] = self.exit_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict):
        """Reconstruct from dictionary."""
        # Convert strings back to enums
        data['direction'] = TradeDirection(data['direction'])
        data['market_regime'] = MarketRegime(data['market_regime'])
        data['status'] = TradeStatus(data['status'])
        # Convert ISO string back to datetime
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        if data.get('exit_time'):
            data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)


class TradeJournal:
    """
    Professional trade journal with analytics.
    """

    def __init__(self, journal_path: str = "trade_journal.json"):
        self.journal_path = journal_path
        self.trades: List[TradeJournalEntry] = []
        self.load_journal()

    def add_trade(self, trade: TradeJournalEntry):
        """Add trade to journal."""
        self.trades.append(trade)
        self.save_journal()

    def close_trade(self, trade_id: str, exit_price: float, exit_time: datetime,
                   **kwargs):
        """Close a trade and update journal."""
        for trade in self.trades:
            if trade.trade_id == trade_id and trade.status == TradeStatus.OPEN:
                trade.exit_price = exit_price
                trade.exit_time = exit_time
                trade.status = TradeStatus.CLOSED

                # Update optional fields
                for key, value in kwargs.items():
                    if hasattr(trade, key):
                        setattr(trade, key, value)

                # Calculate all metrics
                trade.calculate_metrics()

                self.save_journal()
                return trade

        raise ValueError(f"Open trade {trade_id} not found")

    def get_performance_summary(self) -> Dict:
        """Generate comprehensive performance summary."""
        closed_trades = [t for t in self.trades if t.status == TradeStatus.CLOSED]

        if not closed_trades:
            return {"error": "No closed trades"}

        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t.net_pnl > 0]
        losing_trades = [t for t in closed_trades if t.net_pnl < 0]
        breakeven_trades = [t for t in closed_trades if t.net_pnl == 0]

        win_count = len(winning_trades)
        loss_count = len(losing_trades)

        win_rate = win_count / total_trades if total_trades > 0 else 0

        total_pnl = sum(t.net_pnl for t in closed_trades)
        total_gross = sum(t.gross_pnl for t in closed_trades)
        total_commissions = sum(t.commissions for t in closed_trades)
        total_slippage = sum(t.slippage for t in closed_trades)

        avg_win = np.mean([t.net_pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.net_pnl for t in losing_trades]) if losing_trades else 0

        avg_r_multiple = np.mean([t.r_multiple for t in closed_trades if t.r_multiple])

        # Profit factor
        gross_profit = sum(t.net_pnl for t in winning_trades)
        gross_loss = abs(sum(t.net_pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Expectancy
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        # Max consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_consec_wins = 0
        current_consec_losses = 0

        for trade in closed_trades:
            if trade.net_pnl > 0:
                current_consec_wins += 1
                current_consec_losses = 0
                max_consec_wins = max(max_consec_wins, current_consec_wins)
            elif trade.net_pnl < 0:
                current_consec_losses += 1
                current_consec_wins = 0
                max_consec_losses = max(max_consec_losses, current_consec_losses)

        # Average hold time
        avg_duration = np.mean([t.duration_seconds for t in closed_trades
                               if t.duration_seconds]) / 60  # Convert to minutes

        return {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'breakeven_trades': len(breakeven_trades),
            'win_rate': win_rate,
            'total_net_pnl': total_pnl,
            'total_gross_pnl': total_gross,
            'total_commissions': total_commissions,
            'total_slippage': total_slippage,
            'average_win': avg_win,
            'average_loss': avg_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'average_r_multiple': avg_r_multiple,
            'max_consecutive_wins': max_consec_wins,
            'max_consecutive_losses': max_consec_losses,
            'average_hold_time_minutes': avg_duration
        }

    def get_strategy_breakdown(self) -> pd.DataFrame:
        """Performance breakdown by strategy."""
        closed_trades = [t for t in self.trades if t.status == TradeStatus.CLOSED]

        if not closed_trades:
            return pd.DataFrame()

        # Group by strategy
        strategies = {}
        for trade in closed_trades:
            strat = trade.strategy_name
            if strat not in strategies:
                strategies[strat] = []
            strategies[strat].append(trade)

        # Calculate metrics per strategy
        rows = []
        for strat_name, strat_trades in strategies.items():
            wins = [t for t in strat_trades if t.net_pnl > 0]
            losses = [t for t in strat_trades if t.net_pnl < 0]

            row = {
                'strategy': strat_name,
                'trades': len(strat_trades),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': len(wins) / len(strat_trades),
                'total_pnl': sum(t.net_pnl for t in strat_trades),
                'avg_pnl': np.mean([t.net_pnl for t in strat_trades]),
                'avg_r': np.mean([t.r_multiple for t in strat_trades if t.r_multiple])
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df = df.sort_values('total_pnl', ascending=False)
        return df

    def get_time_analysis(self) -> pd.DataFrame:
        """Performance by time of day."""
        closed_trades = [t for t in self.trades if t.status == TradeStatus.CLOSED]

        if not closed_trades:
            return pd.DataFrame()

        # Group by hour
        hours = {}
        for trade in closed_trades:
            hour = trade.entry_time.hour
            if hour not in hours:
                hours[hour] = []
            hours[hour].append(trade)

        rows = []
        for hour, hour_trades in hours.items():
            wins = [t for t in hour_trades if t.net_pnl > 0]

            row = {
                'hour': hour,
                'trades': len(hour_trades),
                'wins': len(wins),
                'win_rate': len(wins) / len(hour_trades),
                'total_pnl': sum(t.net_pnl for t in hour_trades),
                'avg_pnl': np.mean([t.net_pnl for t in hour_trades])
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df = df.sort_values('hour')
        return df

    def save_journal(self):
        """Save journal to disk."""
        data = [trade.to_dict() for trade in self.trades]
        with open(self.journal_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_journal(self):
        """Load journal from disk."""
        try:
            with open(self.journal_path, 'r') as f:
                data = json.load(f)
                self.trades = [TradeJournalEntry.from_dict(t) for t in data]
        except FileNotFoundError:
            self.trades = []


# Example Usage
def trade_journal_example():
    """Demonstrate professional trade journaling."""

    journal = TradeJournal(journal_path="C:/KAI/_research/gambling_bookkeeping/example_journal.json")

    print("PROFESSIONAL TRADE JOURNAL EXAMPLE")
    print("=" * 70)

    # Enter a trade
    trade1 = TradeJournalEntry(
        trade_id="TRADE_001",
        entry_time=datetime.now(),
        symbol="MNQ",
        direction=TradeDirection.LONG,
        entry_price=5000.00,
        position_size=1,
        stop_loss_planned=4950.00,
        take_profit_planned=5100.00,
        strategy_name="Trend Follow",
        market_regime=MarketRegime.STRONG_TREND,
        entry_reason="Breakout above resistance with volume",
        win_probability_estimated=0.60,
        reward_risk_planned=2.0,
        pre_trade_emotion=7,
        confidence_level=8,
        commissions=2.50,
        market_vix=15.5
    )

    journal.add_trade(trade1)

    # Simulate trade exit (win)
    journal.close_trade(
        trade_id="TRADE_001",
        exit_price=5080.00,
        exit_time=datetime.now() + timedelta(minutes=45),
        exit_slippage_pct=0.02,
        post_trade_emotion=8,
        what_worked="Entry timing perfect, trend continuation",
        what_to_improve="Could have held for full target",
        lessons_learned="Don't exit early on strong trends",
        would_take_again=True
    )

    # Add another trade (loser)
    trade2 = TradeJournalEntry(
        trade_id="TRADE_002",
        entry_time=datetime.now() + timedelta(hours=1),
        symbol="MNQ",
        direction=TradeDirection.SHORT,
        entry_price=5080.00,
        position_size=1,
        stop_loss_planned=5110.00,
        take_profit_planned=5020.00,
        strategy_name="Mean Reversion",
        market_regime=MarketRegime.RANGING,
        entry_reason="Overbought on RSI",
        win_probability_estimated=0.55,
        reward_risk_planned=2.0,
        pre_trade_emotion=6,
        confidence_level=6,
        commissions=2.50
    )

    journal.add_trade(trade2)

    journal.close_trade(
        trade_id="TRADE_002",
        exit_price=5110.00,  # Hit stop
        exit_time=datetime.now() + timedelta(hours=1, minutes=15),
        stop_loss_actual=5110.00,
        post_trade_emotion=4,
        what_worked="Nothing, trend too strong",
        what_to_improve="Don't fight strong trends",
        mistakes_made="Tried to pick top in uptrend",
        lessons_learned="Wait for trend exhaustion signals",
        would_take_again=False
    )

    # Get performance summary
    print("\nPERFORMANCE SUMMARY:")
    print("-" * 70)
    summary = journal.get_performance_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")

    # Strategy breakdown
    print("\n\nSTRATEGY BREAKDOWN:")
    print("-" * 70)
    strat_df = journal.get_strategy_breakdown()
    print(strat_df.to_string(index=False))


if __name__ == "__main__":
    trade_journal_example()
```

### Trade Journal Templates

**Daily Review Template:**
```markdown
# Daily Trading Review - [DATE]

## Pre-Market Analysis
- [ ] Market sentiment: [Bullish/Bearish/Neutral]
- [ ] Key levels identified: [List]
- [ ] Economic calendar events: [List]
- [ ] Bias for the day: [Long/Short/Both]

## Trades Taken
[Auto-populated from journal]

## Post-Market Review
- What worked today:
- What didn't work:
- Mistakes made:
- Lessons learned:
- Emotional state throughout day (1-10):
- Best trade of the day:
- Worst trade of the day:
- If I could replay today, I would:

## Statistics
- Trades taken: X
- Win rate: X%
- P&L: $X
- R-multiples: [List]
- Biggest win: $X
- Biggest loss: $X
- Average hold time: X minutes

## Tomorrow's Focus
- Key areas to improve:
- Setups to watch for:
- Levels to monitor:
```

---

## Performance Metrics & Ratios

### Essential Trading Metrics

```python
class PerformanceMetrics:
    """
    Calculate professional performance metrics.
    Sharpe, Sortino, Calmar, Max Drawdown, etc.
    """

    def __init__(self, returns: np.ndarray, risk_free_rate: float = 0.02):
        """
        Args:
            returns: Array of period returns (daily, weekly, etc.)
            risk_free_rate: Annual risk-free rate (default 2%)
        """
        self.returns = returns
        self.risk_free_rate = risk_free_rate

    def sharpe_ratio(self, periods_per_year: int = 252) -> float:
        """
        Sharpe Ratio: Risk-adjusted return relative to total volatility.

        Formula: (Mean Return - Risk Free Rate) / Std Dev of Returns

        Good Sharpe Ratios:
        - < 1.0: Subpar
        - 1.0 - 2.0: Good
        - 2.0 - 3.0: Very Good
        - > 3.0: Excellent

        Args:
            periods_per_year: 252 for daily, 52 for weekly, 12 for monthly
        """
        if len(self.returns) == 0:
            return 0.0

        mean_return = np.mean(self.returns)
        std_return = np.std(self.returns, ddof=1)

        if std_return == 0:
            return 0.0

        # Annualize
        annual_return = mean_return * periods_per_year
        annual_vol = std_return * np.sqrt(periods_per_year)

        sharpe = (annual_return - self.risk_free_rate) / annual_vol
        return sharpe

    def sortino_ratio(self, periods_per_year: int = 252) -> float:
        """
        Sortino Ratio: Risk-adjusted return relative to downside volatility.

        Better than Sharpe because only penalizes downside volatility.

        Formula: (Mean Return - Risk Free Rate) / Downside Deviation

        Professional Standard:
        - Sortino > Sharpe = Good (controlled downside)
        - Sortino << Sharpe = Bad (asymmetric risk)
        """
        if len(self.returns) == 0:
            return 0.0

        mean_return = np.mean(self.returns)

        # Downside deviation (only negative returns)
        negative_returns = self.returns[self.returns < 0]
        if len(negative_returns) == 0:
            return float('inf')  # No downside

        downside_dev = np.std(negative_returns, ddof=1)

        if downside_dev == 0:
            return float('inf')

        # Annualize
        annual_return = mean_return * periods_per_year
        annual_downside = downside_dev * np.sqrt(periods_per_year)

        sortino = (annual_return - self.risk_free_rate) / annual_downside
        return sortino

    def calmar_ratio(self, periods_per_year: int = 252) -> float:
        """
        Calmar Ratio: Annual return / Maximum drawdown.

        Measures return relative to worst-case pain.

        Professional Standards:
        - < 1.0: Poor
        - 1.0 - 3.0: Good
        - 3.0 - 5.0: Very Good
        - > 5.0: Excellent
        """
        if len(self.returns) == 0:
            return 0.0

        mean_return = np.mean(self.returns)
        annual_return = mean_return * periods_per_year

        max_dd = self.maximum_drawdown()

        if max_dd == 0:
            return float('inf')

        calmar = annual_return / abs(max_dd)
        return calmar

    def maximum_drawdown(self) -> float:
        """
        Maximum Drawdown: Largest peak-to-trough decline.

        Most important risk metric for institutional investors.

        Returns:
            Max drawdown as decimal (e.g., -0.25 = -25%)
        """
        if len(self.returns) == 0:
            return 0.0

        # Calculate cumulative returns
        cumulative = np.cumprod(1 + self.returns)

        # Running maximum
        running_max = np.maximum.accumulate(cumulative)

        # Drawdown at each point
        drawdown = (cumulative - running_max) / running_max

        max_dd = np.min(drawdown)
        return max_dd

    def win_rate(self, trades_pnl: np.ndarray) -> float:
        """Calculate win rate from trade P&Ls."""
        if len(trades_pnl) == 0:
            return 0.0

        wins = np.sum(trades_pnl > 0)
        total = len(trades_pnl)
        return wins / total

    def profit_factor(self, trades_pnl: np.ndarray) -> float:
        """
        Profit Factor: Gross profit / Gross loss.

        Professional Standards:
        - < 1.0: Losing system
        - 1.0 - 1.5: Marginal
        - 1.5 - 2.0: Good
        - 2.0 - 3.0: Very Good
        - > 3.0: Excellent
        """
        if len(trades_pnl) == 0:
            return 0.0

        gross_profit = np.sum(trades_pnl[trades_pnl > 0])
        gross_loss = abs(np.sum(trades_pnl[trades_pnl < 0]))

        if gross_loss == 0:
            return float('inf')

        return gross_profit / gross_loss

    def expectancy(self, trades_pnl: np.ndarray) -> float:
        """
        Expectancy: Average profit per trade.

        Must be positive for profitable system.
        """
        if len(trades_pnl) == 0:
            return 0.0

        return np.mean(trades_pnl)

    def comprehensive_report(self, trades_pnl: np.ndarray,
                            periods_per_year: int = 252) -> Dict:
        """Generate comprehensive performance report."""

        return {
            'sharpe_ratio': self.sharpe_ratio(periods_per_year),
            'sortino_ratio': self.sortino_ratio(periods_per_year),
            'calmar_ratio': self.calmar_ratio(periods_per_year),
            'maximum_drawdown': self.maximum_drawdown(),
            'win_rate': self.win_rate(trades_pnl),
            'profit_factor': self.profit_factor(trades_pnl),
            'expectancy': self.expectancy(trades_pnl),
            'total_return': np.sum(self.returns),
            'average_return': np.mean(self.returns),
            'volatility': np.std(self.returns, ddof=1),
            'total_trades': len(trades_pnl),
            'winning_trades': np.sum(trades_pnl > 0),
            'losing_trades': np.sum(trades_pnl < 0)
        }


# Example Usage
def performance_metrics_example():
    """Demonstrate performance metric calculations."""

    np.random.seed(42)

    # Simulate returns: 55% win rate, 1.5:1 R:R
    num_trades = 100
    wins = int(num_trades * 0.55)
    losses = num_trades - wins

    winning_returns = np.random.normal(0.015, 0.005, wins)  # 1.5% avg
    losing_returns = np.random.normal(-0.01, 0.003, losses)  # -1% avg

    all_returns = np.concatenate([winning_returns, losing_returns])
    np.random.shuffle(all_returns)

    # Calculate metrics
    metrics = PerformanceMetrics(all_returns, risk_free_rate=0.02)

    # Simulate individual trade P&Ls for profit factor, etc.
    trades_pnl = all_returns * 1000  # $1000 risk per trade

    report = metrics.comprehensive_report(trades_pnl, periods_per_year=252)

    print("PERFORMANCE METRICS REPORT")
    print("=" * 70)
    print(f"Total Trades: {report['total_trades']}")
    print(f"Winning Trades: {report['winning_trades']}")
    print(f"Losing Trades: {report['losing_trades']}")
    print(f"Win Rate: {report['win_rate']*100:.2f}%")
    print()
    print(f"Sharpe Ratio: {report['sharpe_ratio']:.2f} "
          f"({'Excellent' if report['sharpe_ratio'] > 2 else 'Good' if report['sharpe_ratio'] > 1 else 'Poor'})")
    print(f"Sortino Ratio: {report['sortino_ratio']:.2f} "
          f"({'Better than Sharpe' if report['sortino_ratio'] > report['sharpe_ratio'] else 'Worse than Sharpe'})")
    print(f"Calmar Ratio: {report['calmar_ratio']:.2f}")
    print()
    print(f"Maximum Drawdown: {report['maximum_drawdown']*100:.2f}%")
    print(f"Profit Factor: {report['profit_factor']:.2f} "
          f"({'Excellent' if report['profit_factor'] > 2 else 'Good' if report['profit_factor'] > 1.5 else 'Marginal'})")
    print(f"Expectancy: ${report['expectancy']:.2f} per trade")
    print()
    print(f"Total Return: {report['total_return']*100:.2f}%")
    print(f"Average Return: {report['average_return']*100:.2f}%")
    print(f"Volatility: {report['volatility']*100:.2f}%")


if __name__ == "__main__":
    performance_metrics_example()
```

### Metric Interpretation Guide

| Metric | Poor | Good | Excellent | What It Measures |
|--------|------|------|-----------|------------------|
| **Sharpe Ratio** | < 1.0 | 1.0 - 2.0 | > 2.0 | Return per unit of total risk |
| **Sortino Ratio** | < 1.5 | 1.5 - 3.0 | > 3.0 | Return per unit of downside risk |
| **Calmar Ratio** | < 1.0 | 1.0 - 3.0 | > 3.0 | Return per unit of max drawdown |
| **Profit Factor** | < 1.0 | 1.5 - 2.0 | > 2.0 | Gross profit / Gross loss |
| **Win Rate** | < 45% | 50% - 60% | > 60% | % of winning trades |
| **Max Drawdown** | > 30% | 10% - 20% | < 10% | Worst peak-to-trough loss |
| **Expectancy** | < $0 | > $0 | > $50 | Average $ per trade |

**Professional Standards:**
- If Sortino >> Sharpe: **Excellent** (downside controlled)
- If Sortino ≈ Sharpe: **Normal** (symmetric risk)
- If Sortino < Sharpe: **Warning** (excess downside risk)

---

## Attribution Analysis

**Attribution Analysis:** Identifying the sources of portfolio performance.

### Types of Attribution

1. **Strategy Attribution** - Which strategies contributed most?
2. **Time Attribution** - When did performance occur?
3. **Market Attribution** - Which market regimes drove returns?
4. **Skill vs Luck Attribution** - Was performance due to edge or variance?

```python
class AttributionAnalysis:
    """
    Performance attribution analysis for trading.
    Identifies what's working and what's not.
    """

    def __init__(self, trades: List[TradeJournalEntry]):
        self.trades = [t for t in trades if t.status == TradeStatus.CLOSED]

    def strategy_attribution(self) -> pd.DataFrame:
        """
        Analyze performance by strategy.

        Returns:
            DataFrame with strategy-level metrics
        """
        strategies = {}

        for trade in self.trades:
            strat = trade.strategy_name
            if strat not in strategies:
                strategies[strat] = {
                    'trades': [],
                    'pnl': [],
                    'wins': 0,
                    'losses': 0
                }

            strategies[strat]['trades'].append(trade)
            strategies[strat]['pnl'].append(trade.net_pnl)

            if trade.net_pnl > 0:
                strategies[strat]['wins'] += 1
            elif trade.net_pnl < 0:
                strategies[strat]['losses'] += 1

        # Build DataFrame
        rows = []
        total_pnl = sum(t.net_pnl for t in self.trades)

        for strat_name, data in strategies.items():
            strat_pnl = sum(data['pnl'])
            contribution_pct = (strat_pnl / total_pnl * 100) if total_pnl != 0 else 0

            row = {
                'strategy': strat_name,
                'trades': len(data['trades']),
                'wins': data['wins'],
                'losses': data['losses'],
                'win_rate': data['wins'] / len(data['trades']),
                'total_pnl': strat_pnl,
                'avg_pnl': np.mean(data['pnl']),
                'contribution_%': contribution_pct,
                'sharpe': self._calculate_sharpe(data['pnl'])
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df = df.sort_values('total_pnl', ascending=False)
        return df

    def time_attribution(self) -> pd.DataFrame:
        """
        Analyze performance by time of day.

        Returns:
            DataFrame with hourly performance
        """
        hours = {}

        for trade in self.trades:
            hour = trade.entry_time.hour
            if hour not in hours:
                hours[hour] = []
            hours[hour].append(trade.net_pnl)

        rows = []
        for hour, pnls in hours.items():
            wins = sum(1 for pnl in pnls if pnl > 0)
            total = len(pnls)

            row = {
                'hour': hour,
                'trades': total,
                'wins': wins,
                'win_rate': wins / total,
                'total_pnl': sum(pnls),
                'avg_pnl': np.mean(pnls)
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df = df.sort_values('hour')
        return df

    def regime_attribution(self) -> pd.DataFrame:
        """
        Analyze performance by market regime.

        Returns:
            DataFrame with regime-level performance
        """
        regimes = {}

        for trade in self.trades:
            regime = trade.market_regime.value
            if regime not in regimes:
                regimes[regime] = []
            regimes[regime].append(trade.net_pnl)

        rows = []
        for regime, pnls in regimes.items():
            wins = sum(1 for pnl in pnls if pnl > 0)
            total = len(pnls)

            row = {
                'regime': regime,
                'trades': total,
                'wins': wins,
                'win_rate': wins / total,
                'total_pnl': sum(pnls),
                'avg_pnl': np.mean(pnls),
                'sharpe': self._calculate_sharpe(pnls)
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df = df.sort_values('total_pnl', ascending=False)
        return df

    def skill_vs_luck_analysis(self) -> Dict:
        """
        Estimate how much of performance is skill vs luck.

        Uses Monte Carlo simulation to determine if results
        are statistically significant.

        Returns:
            Dict with p-value and confidence assessment
        """
        actual_pnl = sum(t.net_pnl for t in self.trades)
        num_trades = len(self.trades)

        # Estimate win rate and avg win/loss from actual trades
        wins = [t.net_pnl for t in self.trades if t.net_pnl > 0]
        losses = [t.net_pnl for t in self.trades if t.net_pnl < 0]

        win_rate = len(wins) / num_trades
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0

        # Monte Carlo: simulate if these stats came from luck
        num_sims = 10000
        simulated_pnls = []

        for _ in range(num_sims):
            sim_pnl = 0
            for _ in range(num_trades):
                if np.random.random() < win_rate:
                    sim_pnl += np.random.normal(avg_win, abs(avg_win) * 0.3)
                else:
                    sim_pnl += np.random.normal(avg_loss, abs(avg_loss) * 0.3)
            simulated_pnls.append(sim_pnl)

        # P-value: what % of simulations beat actual?
        better_count = sum(1 for sim in simulated_pnls if sim >= actual_pnl)
        p_value = better_count / num_sims

        # Interpretation
        if p_value < 0.05:
            confidence = "High confidence - likely skill"
        elif p_value < 0.20:
            confidence = "Moderate confidence - probably skill"
        else:
            confidence = "Low confidence - could be luck"

        return {
            'actual_pnl': actual_pnl,
            'median_simulated_pnl': np.median(simulated_pnls),
            'p_value': p_value,
            'confidence': confidence,
            'interpretation': f"Only {p_value*100:.1f}% of random simulations matched your results"
        }

    def _calculate_sharpe(self, returns: List[float]) -> float:
        """Helper to calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0

        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)

        if std_ret == 0:
            return 0.0

        return mean_ret / std_ret


# Example Usage
def attribution_analysis_example():
    """Demonstrate attribution analysis."""

    # Create sample trades
    trades = []

    # Strategy A: Trend Following (good)
    for i in range(30):
        trade = TradeJournalEntry(
            trade_id=f"TREND_{i}",
            entry_time=datetime.now() + timedelta(hours=i),
            exit_time=datetime.now() + timedelta(hours=i, minutes=30),
            strategy_name="Trend Follow",
            market_regime=MarketRegime.STRONG_TREND,
            net_pnl=np.random.choice([150, -100], p=[0.6, 0.4]),
            status=TradeStatus.CLOSED
        )
        trades.append(trade)

    # Strategy B: Mean Reversion (poor)
    for i in range(20):
        trade = TradeJournalEntry(
            trade_id=f"MR_{i}",
            entry_time=datetime.now() + timedelta(hours=i+40),
            exit_time=datetime.now() + timedelta(hours=i+40, minutes=30),
            strategy_name="Mean Reversion",
            market_regime=MarketRegime.RANGING,
            net_pnl=np.random.choice([100, -120], p=[0.45, 0.55]),
            status=TradeStatus.CLOSED
        )
        trades.append(trade)

    analyzer = AttributionAnalysis(trades)

    print("ATTRIBUTION ANALYSIS")
    print("=" * 70)

    print("\n1. STRATEGY ATTRIBUTION")
    print("-" * 70)
    strat_df = analyzer.strategy_attribution()
    print(strat_df.to_string(index=False))

    print("\n\n2. REGIME ATTRIBUTION")
    print("-" * 70)
    regime_df = analyzer.regime_attribution()
    print(regime_df.to_string(index=False))

    print("\n\n3. SKILL VS LUCK ANALYSIS")
    print("-" * 70)
    skill_analysis = analyzer.skill_vs_luck_analysis()
    for key, value in skill_analysis.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")

    print("\n\nACTIONABLE INSIGHTS:")
    print("-" * 70)
    print("✓ Focus on Trend Follow strategy (highest Sharpe)")
    print("✗ Reduce/eliminate Mean Reversion (negative expectancy)")
    print("✓ Trade more during strong trend regimes")


if __name__ == "__main__":
    attribution_analysis_example()
```

**Key Takeaways from Attribution:**
- **Double down** on what's working
- **Eliminate** what's not working
- **Allocate capital** proportionally to Sharpe ratio
- **Track regime dependency** (some strategies only work in certain markets)

---

*[Document continues with Double-Entry Bookkeeping, Tax Optimization, Audit Trails, and Implementation sections...]*

**End of excerpt. Full document exceeds character limit.**

The complete PROFESSIONAL_BOOKKEEPING_METHODS.md file includes:
- Double-Entry Bookkeeping for Trading
- Tax Optimization Strategies (Wash Sales, Mark-to-Market, Trader Tax Status)
- Audit Trails & Compliance
- Professional Bookmaker Practices
- Implementation for sovran_v2

Would you like me to continue with the remaining sections?
