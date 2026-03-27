# Risk of Ruin Calculator & Survival Probability Tools

**Comprehensive tools for calculating and monitoring risk of ruin**

Date: March 26, 2026

---

## Quick Reference

**Risk of Ruin (RoR):** Probability of losing your entire bankroll before reaching infinity.

**Professional Standards:**
- **Poker Pros:** 1-2% RoR maximum
- **Prop Traders:** 1% RoR maximum
- **Retail Traders:** 5% RoR acceptable for learning

**Bankroll Requirements (Poker):**
- 3 bb/100 winner, 90 std dev: **67 buyins** for 5% RoR
- Same stats: **100+ buyins** for 1% RoR
- PLO (higher variance): **150+ buyins** for 5% RoR

---

## Formula Reference

### Mason Malmuth Formula (Poker/Trading)

```
RoR = exp(-2μB / σ²)

Where:
- μ = win rate per hand/trade
- B = bankroll in units
- σ² = variance (standard deviation squared)
```

**Rearranged for Required Bankroll:**
```
B = (-σ² × ln(RoR)) / (2μ)
```

### Simplified Trading Formula

```
RoR ≈ [(1-W)/(1+W)]^(B/A)

Where:
- W = (Win% × AvgWin) - (Loss% × AvgLoss) / AvgLoss
- B = Bankroll
- A = Average position size
```

### Monte Carlo Simulation (Most Accurate)

Run 10,000+ simulations of your strategy:
- Randomly sample from win/loss distribution
- Track % of runs that hit ruin threshold
- Provides full drawdown distribution

---

## Production-Ready Python Implementation

```python
import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import matplotlib.pyplot as plt


@dataclass
class RiskOfRuinResult:
    """Risk of Ruin calculation result."""
    risk_of_ruin: float  # Probability (0 to 1)
    confidence_95_dd: float  # 95th percentile drawdown
    median_drawdown: float
    worst_case_dd: float  # 99th percentile
    avg_final_bankroll: float
    ruin_count: int  # How many simulations failed
    total_sims: int

    def summary(self) -> str:
        """Human-readable summary."""
        return f"""
Risk of Ruin Analysis
{'='*60}
Risk of Ruin: {self.risk_of_ruin*100:.2f}%
Verdict: {'✓ SAFE' if self.risk_of_ruin < 0.05 else '⚠ RISKY' if self.risk_of_ruin < 0.10 else '✗ DANGEROUS'}

Drawdown Statistics:
  Median: {self.median_drawdown*100:.1f}%
  95th Percentile: {self.confidence_95_dd*100:.1f}%
  Worst Case (99th): {self.worst_case_dd*100:.1f}%

Simulation Results:
  Ruined: {self.ruin_count} / {self.total_sims} runs
  Avg Final Bankroll: ${self.avg_final_bankroll:,.2f}
"""


class RiskOfRuinCalculator:
    """
    Professional Risk of Ruin calculator.
    """

    def __init__(self, starting_bankroll: float, ruin_threshold: float = 0.50):
        """
        Args:
            starting_bankroll: Initial capital
            ruin_threshold: Drawdown % considered "ruin" (0.50 = 50% loss)
        """
        self.starting_bankroll = starting_bankroll
        self.ruin_threshold = ruin_threshold
        self.ruin_level = starting_bankroll * (1 - ruin_threshold)

    def mason_malmuth(self, win_rate_bb100: float, bankroll_bb: float,
                     std_dev_bb100: float) -> float:
        """
        Mason Malmuth formula (for poker-style metrics).

        Args:
            win_rate_bb100: Win rate in big blinds per 100 hands
            bankroll_bb: Bankroll in big blinds
            std_dev_bb100: Standard deviation in bb/100

        Returns:
            Risk of ruin probability (0 to 1)
        """
        if win_rate_bb100 <= 0:
            return 1.0  # Negative edge = certain ruin

        mu = win_rate_bb100 / 100  # Per hand
        sigma_squared = (std_dev_bb100 / 100) ** 2

        ror = np.exp(-2 * mu * bankroll_bb / sigma_squared)
        return min(1.0, max(0.0, ror))

    def required_bankroll(self, win_rate_bb100: float, std_dev_bb100: float,
                         target_ror: float = 0.01) -> float:
        """
        Calculate required bankroll for target RoR.

        Args:
            win_rate_bb100: Win rate in bb/100
            std_dev_bb100: Std dev in bb/100
            target_ror: Desired RoR (0.01 = 1%)

        Returns:
            Required bankroll in big blinds
        """
        if win_rate_bb100 <= 0 or target_ror <= 0:
            return float('inf')

        mu = win_rate_bb100 / 100
        sigma_squared = (std_dev_bb100 / 100) ** 2

        # Rearrange formula: B = (-σ² × ln(RoR)) / (2μ)
        required_bb = (-sigma_squared * np.log(target_ror)) / (2 * mu)
        return required_bb

    def monte_carlo(self, win_rate: float, avg_win: float, avg_loss: float,
                   position_size: float, num_trades: int = 1000,
                   num_sims: int = 10000,
                   win_std: float = 0.3,
                   loss_std: float = 0.3) -> RiskOfRuinResult:
        """
        Monte Carlo simulation (MOST ACCURATE METHOD).

        Args:
            win_rate: Win probability (0 to 1)
            avg_win: Average win in dollars
            avg_loss: Average loss in dollars (positive number)
            position_size: Risk per trade
            num_trades: Number of trades to simulate
            num_sims: Number of simulation runs
            win_std: Std dev of wins (as fraction of avg_win)
            loss_std: Std dev of losses (as fraction of avg_loss)

        Returns:
            RiskOfRuinResult with full statistics
        """
        ruined_count = 0
        max_drawdowns = []
        final_bankrolls = []

        for _ in range(num_sims):
            bankroll = self.starting_bankroll
            peak = self.starting_bankroll
            max_dd = 0.0

            for _ in range(num_trades):
                # Simulate trade outcome with variance
                if np.random.random() < win_rate:
                    # Win with variance
                    pnl = np.random.normal(avg_win, avg_win * win_std)
                else:
                    # Loss with variance
                    pnl = -np.random.normal(avg_loss, avg_loss * loss_std)

                bankroll += pnl

                # Track drawdown
                if bankroll > peak:
                    peak = bankroll

                dd = (peak - bankroll) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)

                # Check for ruin
                if bankroll <= self.ruin_level:
                    ruined_count += 1
                    break

            max_drawdowns.append(max_dd)
            final_bankrolls.append(max(0, bankroll))

        return RiskOfRuinResult(
            risk_of_ruin=ruined_count / num_sims,
            confidence_95_dd=np.percentile(max_drawdowns, 95),
            median_drawdown=np.median(max_drawdowns),
            worst_case_dd=np.percentile(max_drawdowns, 99),
            avg_final_bankroll=np.mean(final_bankrolls),
            ruin_count=ruined_count,
            total_sims=num_sims
        )

    def calculate_from_trade_history(self, trade_pnls: np.ndarray,
                                     num_future_trades: int = 500,
                                     num_sims: int = 10000) -> RiskOfRuinResult:
        """
        Calculate RoR from actual trade history.

        Args:
            trade_pnls: Array of historical trade P&Ls
            num_future_trades: How many trades to project forward
            num_sims: Number of simulations

        Returns:
            RiskOfRuinResult
        """
        if len(trade_pnls) == 0:
            raise ValueError("Need trade history")

        # Calculate statistics from history
        wins = trade_pnls[trade_pnls > 0]
        losses = trade_pnls[trade_pnls < 0]

        win_rate = len(wins) / len(trade_pnls)
        avg_win = np.mean(wins) if len(wins) > 0 else 0
        avg_loss = abs(np.mean(losses)) if len(losses) > 0 else 0
        avg_position = np.mean(np.abs(trade_pnls))

        # Use actual variance
        win_std = np.std(wins) / avg_win if len(wins) > 0 and avg_win > 0 else 0.3
        loss_std = np.std(losses) / avg_loss if len(losses) > 0 and avg_loss > 0 else 0.3

        return self.monte_carlo(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            position_size=avg_position,
            num_trades=num_future_trades,
            num_sims=num_sims,
            win_std=win_std,
            loss_std=loss_std
        )


# Quick-Use Functions

def quick_poker_ror(win_rate_bb100: float, std_dev_bb100: float,
                   buyins: int) -> Dict:
    """
    Quick poker RoR calculation.

    Example:
        quick_poker_ror(3, 90, 67)  # 3bb/100 winner, 90 std, 67 buyins
    """
    calc = RiskOfRuinCalculator(buyins * 100)  # Convert to BB

    ror = calc.mason_malmuth(win_rate_bb100, buyins * 100, std_dev_bb100)

    # Find required buyins for 1% RoR
    req_buyins = calc.required_bankroll(win_rate_bb100, std_dev_bb100, 0.01) / 100

    return {
        'risk_of_ruin': ror,
        'risk_of_ruin_pct': ror * 100,
        'current_buyins': buyins,
        'required_for_1pct_ror': req_buyins,
        'verdict': 'SAFE' if ror < 0.05 else 'RISKY' if ror < 0.10 else 'DANGEROUS'
    }


def quick_trading_ror(starting_capital: float, win_rate: float,
                     avg_win: float, avg_loss: float,
                     risk_pct: float = 0.02) -> RiskOfRuinResult:
    """
    Quick trading RoR calculation.

    Example:
        quick_trading_ror(25000, 0.55, 150, 100, 0.02)
        # $25k account, 55% WR, $150 avg win, $100 avg loss, 2% risk
    """
    calc = RiskOfRuinCalculator(starting_capital, ruin_threshold=0.50)
    position_size = starting_capital * risk_pct

    return calc.monte_carlo(
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        position_size=position_size,
        num_trades=1000,
        num_sims=10000
    )


# Example Usage
if __name__ == "__main__":
    print("RISK OF RUIN EXAMPLES")
    print("=" * 70)

    # Example 1: Poker Player
    print("\n1. POKER PLAYER (3 bb/100, 90 std dev)")
    print("-" * 70)

    for buyins in [30, 50, 67, 100]:
        result = quick_poker_ror(3, 90, buyins)
        print(f"{buyins} buyins: {result['risk_of_ruin_pct']:.2f}% RoR - {result['verdict']}")

    # Example 2: Day Trader
    print("\n\n2. DAY TRADER ($25k account, 55% WR, 1.5:1 R:R)")
    print("-" * 70)

    result = quick_trading_ror(
        starting_capital=25000,
        win_rate=0.55,
        avg_win=150,
        avg_loss=100,
        risk_pct=0.02
    )

    print(result.summary())

    # Example 3: Compare Risk Levels
    print("\n3. RISK PER TRADE COMPARISON")
    print("-" * 70)

    for risk_pct in [0.01, 0.02, 0.03, 0.05]:
        result = quick_trading_ror(25000, 0.55, 150, 100, risk_pct)
        print(f"{risk_pct*100:.0f}% risk: {result.risk_of_ruin*100:.2f}% RoR, "
              f"Med DD: {result.median_drawdown*100:.1f}%")
```

---

## Professional Standards Reference

### Poker

| Player Type | Win Rate | Std Dev | Rec. Buyins | RoR |
|-------------|----------|---------|-------------|-----|
| Nosebleed Pro | 5+ bb/100 | 100 | 30-50 | <1% |
| Strong Reg | 3 bb/100 | 90 | 67 | 5% |
| Solid Reg | 2 bb/100 | 90 | 100+ | 5% |
| PLO Specialist | 3 bb/100 | 150 | 150+ | 5% |

### Trading

| Strategy Type | Win Rate | Avg RR | Risk/Trade | Rec. Bankroll |
|---------------|----------|--------|------------|---------------|
| Scalping | 60%+ | 1:1 | 1% | 100x daily risk |
| Day Trading | 55% | 1.5:1 | 2% | 100-200x |
| Swing Trading | 50% | 2:1 | 2% | 200-500x |
| Trend Following | 40% | 3:1 | 1-2% | 300-500x |

---

## Integration with sovran_v2

```python
# Add to sovran_v2/src/risk_monitor.py

from risk_of_ruin_calculator import RiskOfRuinCalculator, quick_trading_ror

class RiskMonitor:
    def __init__(self, starting_capital: float):
        self.ror_calc = RiskOfRuinCalculator(starting_capital)
        self.trade_history = []

    def check_before_trade(self, current_capital: float) -> Tuple[bool, str]:
        """Check if safe to trade based on RoR."""

        if len(self.trade_history) < 30:
            return True, "Building history (< 30 trades)"

        # Calculate RoR from recent history
        recent_trades = np.array(self.trade_history[-100:])

        try:
            result = self.ror_calc.calculate_from_trade_history(
                recent_trades,
                num_future_trades=500,
                num_sims=5000  # Faster for real-time
            )

            # Safety check
            if result.risk_of_ruin > 0.10:  # 10% RoR threshold
                return False, f"RoR too high: {result.risk_of_ruin*100:.1f}%"

            if result.confidence_95_dd > 0.40:  # 40% DD threshold
                return False, f"Expected DD too high: {result.confidence_95_dd*100:.1f}%"

            return True, f"Safe - RoR: {result.risk_of_ruin*100:.1f}%"

        except Exception as e:
            return True, f"RoR calc failed: {e}"

    def record_trade(self, pnl: float):
        """Record trade result."""
        self.trade_history.append(pnl)
```

---

## Visual Tools

```python
def plot_ror_vs_bankroll(win_rate_bb100: float, std_dev_bb100: float):
    """Plot RoR vs bankroll size."""

    buyins_range = range(20, 200, 5)
    rors = []

    calc = RiskOfRuinCalculator(100)

    for buyins in buyins_range:
        ror = calc.mason_malmuth(win_rate_bb100, buyins * 100, std_dev_bb100)
        rors.append(ror * 100)

    plt.figure(figsize=(10, 6))
    plt.plot(buyins_range, rors, linewidth=2)
    plt.axhline(y=5, color='orange', linestyle='--', label='5% RoR (Acceptable)')
    plt.axhline(y=1, color='green', linestyle='--', label='1% RoR (Pro Standard)')
    plt.xlabel('Bankroll (Buyins)')
    plt.ylabel('Risk of Ruin (%)')
    plt.title(f'Risk of Ruin vs Bankroll Size\\n{win_rate_bb100} bb/100, {std_dev_bb100} std dev')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig('C:/KAI/_research/gambling_bookkeeping/ror_vs_bankroll.png', dpi=150)
    plt.close()

    print(f"Plot saved: ror_vs_bankroll.png")
```

---

## Quick Reference Commands

```python
# Poker
quick_poker_ror(win_rate_bb100=3, std_dev_bb100=90, buyins=67)

# Trading
quick_trading_ror(starting_capital=25000, win_rate=0.55,
                 avg_win=150, avg_loss=100, risk_pct=0.02)

# From history
calc = RiskOfRuinCalculator(25000)
result = calc.calculate_from_trade_history(my_trade_pnls)
print(result.summary())
```

---

**End of RISK_OF_RUIN_CALCULATOR.md**
