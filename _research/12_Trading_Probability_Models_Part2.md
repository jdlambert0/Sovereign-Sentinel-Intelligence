# 12 Trading Probability Models - Part 2 (Models 5-12)

**Continuation of Comprehensive Implementation Guide**

---

## 5. Statistical Arbitrage

### Core Mathematical Formulas

#### Pairs Trading - Cointegration
```
Spread = Stock_A - β × Stock_B

Where β is calculated from linear regression:
β = Cov(A, B) / Var(B)

Z-Score of spread:
Z = (Spread - μ_spread) / σ_spread

Entry signal: |Z| > 2.0
Exit signal: Z crosses 0
```

#### Augmented Dickey-Fuller Test (Stationarity)
```
ΔY_t = α + βt + γY_{t-1} + Σ(δ_i × ΔY_{t-i}) + ε_t

H0: γ = 0 (unit root, non-stationary)
H1: γ < 0 (stationary, mean-reverting)

p-value < 0.05 → Reject H0 → Series is stationary
```

#### Half-Life of Mean Reversion
```
ΔY_t = λ(μ - Y_{t-1}) + ε_t

Half-life = -ln(2) / ln(1 + λ)

Typical ranges:
- HFT stat arb: 1-60 minutes
- Daily stat arb: 5-20 days
- Too long (>30 days): Not reliable
```

#### Optimal Entry/Exit Thresholds
```
Optimal_Entry = μ + k_entry × σ
Optimal_Exit = μ + k_exit × σ

Where k is optimized for:
max E[PnL] = (Entry_Threshold - μ) × P(Reversion) - Transaction_Costs

Typical k_entry: 2.0-2.5
Typical k_exit: 0.0-0.5
```

#### Hedge Ratio (Beta)
```
Static Beta:
β = Cov(A, B) / Var(B)

Dynamic Beta (Kalman Filter):
β_t = β_{t-1} + K_t × (A_t - β_{t-1} × B_t)

Where K_t is Kalman gain
```

#### Position Sizing for Pairs
```
Position_A = Capital × f / (2 × σ_spread)
Position_B = -β × Position_A

Where:
- f = Kelly fraction or fixed risk %
- σ_spread = standard deviation of spread
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint
from scipy import stats

class StatisticalArbitrage:
    def __init__(self, entry_z=2.0, exit_z=0.5, lookback=60):
        """
        Initialize statistical arbitrage strategy

        Args:
            entry_z: Z-score threshold for entry
            exit_z: Z-score threshold for exit
            lookback: Lookback period for statistics
        """
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.lookback = lookback
        self.position = 0  # 1 = long spread, -1 = short spread, 0 = flat

    def test_cointegration(self, series_a, series_b):
        """
        Test if two series are cointegrated using Engle-Granger

        Returns p-value and beta coefficient
        """
        # Calculate beta (hedge ratio)
        beta = np.cov(series_a, series_b)[0, 1] / np.var(series_b)

        # Calculate spread
        spread = series_a - beta * series_b

        # ADF test on spread
        adf_result = adfuller(spread)

        return {
            'beta': beta,
            'adf_statistic': adf_result[0],
            'p_value': adf_result[1],
            'is_cointegrated': adf_result[1] < 0.05,
            'critical_values': adf_result[4]
        }

    def calculate_half_life(self, spread):
        """
        Calculate mean reversion half-life

        Returns time for spread to revert halfway to mean
        """
        spread_lag = np.roll(spread, 1)
        spread_lag[0] = spread[0]

        spread_ret = spread - spread_lag
        spread_lag = spread_lag[1:]
        spread_ret = spread_ret[1:]

        # Regression: ΔY = λY_{-1}
        regression = np.polyfit(spread_lag, spread_ret, 1)
        lambda_param = regression[0]

        # Half-life
        if lambda_param < 0:
            half_life = -np.log(2) / lambda_param
        else:
            half_life = float('inf')

        return {
            'half_life': half_life,
            'lambda': lambda_param,
            'mean_reverting': lambda_param < 0
        }

    def calculate_spread_zscore(self, series_a, series_b, beta=None):
        """
        Calculate current Z-score of spread

        Args:
            series_a: Price series A
            series_b: Price series B
            beta: Hedge ratio (if None, calculate from data)
        """
        if beta is None:
            beta = np.cov(series_a, series_b)[0, 1] / np.var(series_b)

        # Spread
        spread = series_a - beta * series_b

        # Z-score using rolling window
        if len(spread) > self.lookback:
            recent_spread = spread[-self.lookback:]
        else:
            recent_spread = spread

        mean_spread = np.mean(recent_spread)
        std_spread = np.std(recent_spread)

        if std_spread == 0:
            zscore = 0
        else:
            zscore = (spread[-1] - mean_spread) / std_spread

        return {
            'zscore': zscore,
            'spread': spread[-1],
            'mean': mean_spread,
            'std': std_spread,
            'beta': beta
        }

    def generate_signal(self, zscore):
        """
        Generate trading signal based on Z-score

        Returns: 1 (long spread), -1 (short spread), 0 (no position)
        """
        current_pos = self.position

        # Entry signals
        if zscore < -self.entry_z and current_pos != 1:
            # Spread is oversold → Long spread (buy A, sell B)
            signal = 1
            self.position = 1

        elif zscore > self.entry_z and current_pos != -1:
            # Spread is overbought → Short spread (sell A, buy B)
            signal = -1
            self.position = -1

        # Exit signals
        elif abs(zscore) < self.exit_z and current_pos != 0:
            # Mean reversion complete → Close position
            signal = 0
            self.position = 0

        else:
            # Hold current position
            signal = current_pos

        return signal

    def calculate_position_size(self, capital, std_spread, risk_pct=0.02):
        """
        Calculate position size for pairs trade

        Args:
            capital: Trading capital
            std_spread: Standard deviation of spread
            risk_pct: Risk per trade (Kelly fraction)
        """
        # Risk amount
        risk_amount = capital * risk_pct

        # Position size based on spread volatility
        # Risk 1σ move in spread
        if std_spread > 0:
            position_size = risk_amount / (self.entry_z * std_spread)
        else:
            position_size = 0

        return position_size

    def backtest_pair(self, prices_a, prices_b, capital=100000):
        """
        Backtest pairs trading strategy

        Returns equity curve and trade statistics
        """
        # Test cointegration
        coint_test = self.test_cointegration(prices_a, prices_b)

        if not coint_test['is_cointegrated']:
            return {'error': 'Pair is not cointegrated'}

        beta = coint_test['beta']
        spread = prices_a - beta * prices_b

        # Calculate half-life
        half_life_result = self.calculate_half_life(spread)

        # Storage
        signals = []
        equity = [capital]
        positions = []

        for i in range(self.lookback, len(prices_a)):
            # Calculate z-score
            zscore_data = self.calculate_spread_zscore(
                prices_a[:i+1],
                prices_b[:i+1],
                beta=beta
            )

            # Generate signal
            signal = self.generate_signal(zscore_data['zscore'])
            signals.append(signal)

            # Calculate P&L
            if i > self.lookback:
                prev_spread = spread[i-1]
                curr_spread = spread[i]
                spread_change = curr_spread - prev_spread

                # P&L = position × spread_change
                pnl = signals[-2] * spread_change if len(signals) > 1 else 0

                equity.append(equity[-1] + pnl)
            else:
                equity.append(capital)

        # Calculate statistics
        returns = np.diff(equity) / equity[:-1]

        results = {
            'beta': beta,
            'half_life': half_life_result['half_life'],
            'is_cointegrated': coint_test['is_cointegrated'],
            'final_equity': equity[-1],
            'total_return': (equity[-1] - capital) / capital,
            'sharpe_ratio': np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0,
            'max_drawdown': self._calculate_max_drawdown(equity),
            'num_trades': len([s for i, s in enumerate(signals) if i > 0 and s != signals[i-1]])
        }

        return results

    def _calculate_max_drawdown(self, equity_curve):
        """Calculate maximum drawdown from equity curve"""
        peak = equity_curve[0]
        max_dd = 0

        for value in equity_curve:
            if value > peak:
                peak = value

            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd

# Usage Example
stat_arb = StatisticalArbitrage(entry_z=2.0, exit_z=0.5, lookback=60)

# Generate synthetic cointegrated pair for demonstration
np.random.seed(42)
n = 500
series_b = np.cumsum(np.random.randn(n)) + 100
series_a = 1.5 * series_b + np.random.randn(n) * 2 + 50

# Test cointegration
coint = stat_arb.test_cointegration(series_a, series_b)
print(f"Cointegrated: {coint['is_cointegrated']}")
print(f"Beta (hedge ratio): {coint['beta']:.4f}")
print(f"P-value: {coint['p_value']:.4f}")

# Calculate half-life
spread = series_a - coint['beta'] * series_b
half_life = stat_arb.calculate_half_life(spread)
print(f"Half-life: {half_life['half_life']:.1f} periods")

# Current signal
zscore = stat_arb.calculate_spread_zscore(series_a, series_b)
print(f"Current Z-score: {zscore['zscore']:.2f}")

signal = stat_arb.generate_signal(zscore['zscore'])
print(f"Signal: {signal}")

# Backtest
results = stat_arb.backtest_pair(series_a, series_b)
print(f"\nBacktest Results:")
print(f"Total Return: {results['total_return']:.2%}")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['max_drawdown']:.2%}")
print(f"Number of Trades: {results['num_trades']}")
```

### When to Use

**Optimal Conditions:**
- Two or more assets are cointegrated (p-value < 0.05)
- Half-life < 30 periods (faster mean reversion)
- Low transaction costs (frequent trading)
- Sufficient liquidity in both instruments
- Stable beta relationship (test over multiple regimes)
- Mean-reverting markets

**Avoid When:**
- Cointegration breaks down (regime change)
- Half-life > 30 periods (too slow to revert)
- High transaction costs eat into edge
- Assets become perfectly correlated (no spread)
- Structural changes (mergers, splits, policy changes)
- Trending markets (spreads can widen indefinitely)

### Strengths and Weaknesses

**Strengths:**
- Market-neutral (hedged against broad market moves)
- Statistical edge from mean reversion
- Quantifiable risk (spread volatility)
- Works in all market conditions (if cointegration holds)
- Diversification benefits (many pairs possible)

**Weaknesses:**
- Cointegration can break down suddenly
- Requires two positions (double transaction costs)
- Model risk (past cointegration ≠ future cointegration)
- Spread can widen beyond pain threshold
- Requires margin for short positions
- Tail risk (extreme spread widening)

### Real-World Examples

**D.E. Shaw & Co (Stat Arb Pioneer):**
- Founded 1988 by computer scientist David Shaw
- Early pioneer of pairs trading
- Equity pairs, fixed income relative value
- AUM: $60B+
- Returns: 20%+ annualized (1990s-2000s), lower now due to competition

**Renaissance Technologies - Medallion Fund:**
- Extensive statistical arbitrage across asset classes
- Thousands of small bets, short holding periods
- Mean reversion + momentum + other alphas
- Returns: 66% annual (before fees) 1988-2018
- Key: Rebalance constantly, adapt to regime changes

**Two Sigma (Modern Stat Arb):**
- Founded by former D.E. Shaw quants
- Machine learning + traditional stat arb
- Equity pairs, futures spreads, cross-asset
- AUM: $60B+
- Focus: Data-driven mean reversion strategies

**Practical Futures Example:**
```
CL (Crude Oil) vs BZ (Brent)
- Historical spread: $2-5 per barrel
- Cointegration test: p-value = 0.001 ✓
- Beta: 0.95 (close to 1:1 hedge)
- Half-life: 8 days

Current state:
- CL: $75.00
- BZ: $82.00
- Spread: $7.00 (unusually wide)
- Mean spread: $3.50
- Std spread: $1.20
- Z-score: (7.00 - 3.50) / 1.20 = 2.92

Signal: Short spread (sell BZ, buy CL)

Position sizing ($100k capital, 2% risk):
- Risk: $2,000
- Spread std: $1.20
- Entry at Z=2.92 → expect 2.92σ reversion
- Position: $2,000 / (2.92 × $1.20) = 570 barrels

Execution:
- Buy 6 CL contracts @ $75.00 (600 barrels)
- Sell 6 BZ contracts @ $82.00 (600 barrels)
- Spread per barrel: $7.00

Target exit:
- Z-score = 0.5
- Spread target: $3.50 + (0.5 × $1.20) = $4.10

Expected profit:
- Spread compression: $7.00 → $4.10 = $2.90/barrel
- Total: 600 × $2.90 = $1,740

Risk:
- Spread widens to $10.00 (Z=5.4)
- Loss: 600 × $3.00 = $1,800
- Stop loss at Z=4.0: spread = $9.30, loss = $1,380
```

### Integration with AI Decision-Making

```python
class AIStatisticalArbitrage:
    def __init__(self, base_strategy):
        self.stat_arb = base_strategy
        self.ml_model = None

    def predict_spread_direction(self, features):
        """
        ML model predicts spread mean reversion likelihood

        Features:
        - Current Z-score
        - Half-life
        - Recent volatility
        - Market regime
        - Order flow imbalance
        """
        # ML predicts P(mean reversion) vs P(continued divergence)
        prediction = self.ml_model.predict_proba(features)

        p_revert = prediction[0][1]

        # Adjust entry threshold based on confidence
        if p_revert > 0.8:
            adjusted_entry_z = self.stat_arb.entry_z * 0.8  # More aggressive
        elif p_revert > 0.6:
            adjusted_entry_z = self.stat_arb.entry_z  # Normal
        else:
            adjusted_entry_z = self.stat_arb.entry_z * 1.5  # More conservative

        return {
            'p_revert': p_revert,
            'adjusted_entry_z': adjusted_entry_z,
            'confidence': max(prediction[0])
        }

    def dynamic_beta_estimation(self, prices_a, prices_b, method='kalman'):
        """
        Use Kalman filter for time-varying beta

        Better than static OLS beta for non-stationary relationships
        """
        from pykalman import KalmanFilter

        # Observation matrix [price_b, 1]
        obs_mat = np.vstack([prices_b, np.ones(len(prices_b))]).T

        # Kalman filter for dynamic beta
        kf = KalmanFilter(
            n_dim_obs=1,
            n_dim_state=2,
            initial_state_mean=np.array([1.0, 0.0]),
            transition_matrices=np.eye(2),
            observation_matrices=obs_mat
        )

        # Filter prices_a to get dynamic beta
        state_means, _ = kf.filter(prices_a)

        betas = state_means[:, 0]

        return {
            'current_beta': betas[-1],
            'beta_time_series': betas,
            'beta_std': np.std(betas[-20:])  # Recent beta volatility
        }

    def regime_aware_trading(self, market_regime, current_zscore):
        """
        Adjust strategy based on market regime

        Mean-revert regime: Normal parameters
        Trending regime: Widen thresholds or pause
        High volatility: Reduce position size
        """
        if market_regime == 'trending':
            # Spreads less likely to revert in trends
            entry_z = self.stat_arb.entry_z * 1.5
            position_multiplier = 0.5

        elif market_regime == 'high_volatility':
            # More risk, reduce size
            entry_z = self.stat_arb.entry_z
            position_multiplier = 0.5

        elif market_regime == 'mean_reverting':
            # Optimal conditions
            entry_z = self.stat_arb.entry_z
            position_multiplier = 1.0

        else:
            # Default
            entry_z = self.stat_arb.entry_z
            position_multiplier = 0.75

        return {
            'entry_z': entry_z,
            'position_multiplier': position_multiplier,
            'regime': market_regime
        }

    def correlation_breakdown_detection(self, prices_a, prices_b, window=60):
        """
        Detect when cointegration is breaking down

        Exit all positions if correlation drops significantly
        """
        recent_corr = np.corrcoef(prices_a[-window:], prices_b[-window:])[0, 1]
        historical_corr = np.corrcoef(prices_a, prices_b)[0, 1]

        corr_drop = historical_corr - recent_corr

        if corr_drop > 0.2:
            action = 'exit_all_positions'
            reason = 'correlation_breakdown'
        elif corr_drop > 0.1:
            action = 'reduce_positions'
            reason = 'correlation_weakening'
        else:
            action = 'normal'
            reason = 'correlation_stable'

        return {
            'recent_corr': recent_corr,
            'historical_corr': historical_corr,
            'corr_drop': corr_drop,
            'action': action,
            'reason': reason
        }
```

---

## 6. Volatility Trading

### Core Mathematical Formulas

#### Average True Range (ATR)
```
True_Range = max(High - Low, |High - Close_prev|, |Low - Close_prev|)

ATR = EMA(True_Range, period)

ATR Bands:
Upper = Price + (k × ATR)
Lower = Price - (k × ATR)

Typical k = 2-3
```

#### Bollinger Bands
```
Middle_Band = SMA(Close, period)
Upper_Band = Middle_Band + (k × σ)
Lower_Band = Middle_Band - (k × σ)

Where:
- σ = Standard deviation of closes
- k = 2 (95% of data within bands)

%B Indicator:
%B = (Close - Lower_Band) / (Upper_Band - Lower_Band)

Bandwidth:
BW = (Upper_Band - Lower_Band) / Middle_Band
```

#### Historical Volatility
```
Returns = ln(Price_t / Price_{t-1})

Historical_Vol = σ(Returns) × √(Periods_per_Year)

For daily data: √252
For hourly data: √(252 × 6.5)
For 5-min data: √(252 × 78)
```

#### Parkinson Volatility (High-Low)
```
Parkinson_Vol = √(Σ[ln(High/Low)]² / (4 × ln(2) × n))

More efficient than close-to-close volatility
Uses intraday range information
```

#### GARCH(1,1) Model
```
σ²_t = ω + α × ε²_{t-1} + β × σ²_{t-1}

Where:
- ω = long-run variance constant
- α = weight on recent shock (ARCH term)
- β = weight on previous variance (GARCH term)
- Typical: α + β ≈ 0.99 (high persistence)
```

#### Volatility Cones
```
For each horizon (1d, 5d, 20d, 60d):
- Min historical volatility
- 25th percentile
- Median
- 75th percentile
- Max historical volatility

Compare current volatility to historical quantiles
```

#### Keltner Channels
```
Middle = EMA(Close, period)
Upper = Middle + (k × ATR)
Lower = Middle - (k × ATR)

Similar to Bollinger but uses ATR instead of std dev
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd
from scipy import stats
from arch import arch_model  # For GARCH

class VolatilityTrading:
    def __init__(self, atr_period=14, bb_period=20, bb_std=2.0):
        """
        Initialize volatility trading system

        Args:
            atr_period: ATR calculation period
            bb_period: Bollinger Bands period
            bb_std: Bollinger Bands standard deviations
        """
        self.atr_period = atr_period
        self.bb_period = bb_period
        self.bb_std = bb_std

    def calculate_atr(self, high, low, close):
        """
        Calculate Average True Range

        Args:
            high, low, close: Price arrays
        """
        # True Range components
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))

        # Max of three
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        # ATR as EMA of TR
        atr = pd.Series(tr).ewm(span=self.atr_period, adjust=False).mean().values

        return atr

    def calculate_bollinger_bands(self, close):
        """
        Calculate Bollinger Bands

        Returns: middle, upper, lower, %B, bandwidth
        """
        # Middle band (SMA)
        middle = pd.Series(close).rolling(window=self.bb_period).mean().values

        # Standard deviation
        std = pd.Series(close).rolling(window=self.bb_period).std().values

        # Upper and lower bands
        upper = middle + (self.bb_std * std)
        lower = middle - (self.bb_std * std)

        # %B indicator
        percent_b = (close - lower) / (upper - lower)

        # Bandwidth
        bandwidth = (upper - lower) / middle

        return {
            'middle': middle,
            'upper': upper,
            'lower': lower,
            'percent_b': percent_b,
            'bandwidth': bandwidth,
            'std': std
        }

    def calculate_historical_volatility(self, close, window=20, annualize_factor=252):
        """
        Calculate historical volatility

        Args:
            close: Close prices
            window: Lookback window
            annualize_factor: 252 for daily, 252*6.5 for hourly, etc.
        """
        # Log returns
        returns = np.log(close / np.roll(close, 1))
        returns[0] = 0  # Remove NaN

        # Rolling standard deviation
        vol = pd.Series(returns).rolling(window=window).std().values

        # Annualize
        annualized_vol = vol * np.sqrt(annualize_factor)

        return annualized_vol

    def calculate_parkinson_volatility(self, high, low, window=20, annualize_factor=252):
        """
        Parkinson volatility estimator (more efficient)

        Uses high-low range instead of close-to-close
        """
        # Log of high/low ratio
        log_hl = np.log(high / low)

        # Squared log ratios
        log_hl_squared = log_hl ** 2

        # Rolling sum
        sum_squared = pd.Series(log_hl_squared).rolling(window=window).sum().values

        # Parkinson estimator
        parkinson = np.sqrt(sum_squared / (4 * window * np.log(2)))

        # Annualize
        annualized = parkinson * np.sqrt(annualize_factor)

        return annualized

    def fit_garch_model(self, returns, p=1, q=1):
        """
        Fit GARCH(p,q) model to returns

        Returns forecasted volatility
        """
        # Fit GARCH model
        model = arch_model(returns, vol='Garch', p=p, q=q)
        fitted = model.fit(disp='off')

        # Forecast next period volatility
        forecast = fitted.forecast(horizon=1)
        forecasted_vol = np.sqrt(forecast.variance.values[-1, :][0])

        return {
            'model': fitted,
            'forecasted_vol': forecasted_vol,
            'omega': fitted.params['omega'],
            'alpha': fitted.params['alpha[1]'],
            'beta': fitted.params['beta[1]'],
            'persistence': fitted.params['alpha[1]'] + fitted.params['beta[1]']
        }

    def calculate_volatility_cone(self, close, horizons=[5, 10, 20, 60]):
        """
        Calculate volatility cone (distribution of realized vols)

        Args:
            close: Price series
            horizons: List of time horizons to analyze
        """
        returns = np.log(close / np.roll(close, 1))
        returns[0] = 0

        cone_data = {}

        for horizon in horizons:
            # Rolling volatility for this horizon
            rolling_vol = []

            for i in range(horizon, len(returns)):
                window_returns = returns[i-horizon:i]
                vol = np.std(window_returns) * np.sqrt(252)
                rolling_vol.append(vol)

            rolling_vol = np.array(rolling_vol)

            # Percentiles
            cone_data[f'{horizon}d'] = {
                'min': np.min(rolling_vol),
                'p25': np.percentile(rolling_vol, 25),
                'median': np.percentile(rolling_vol, 50),
                'p75': np.percentile(rolling_vol, 75),
                'max': np.max(rolling_vol),
                'current': rolling_vol[-1] if len(rolling_vol) > 0 else None
            }

        return cone_data

    def bollinger_squeeze_signal(self, bandwidth, lookback=120):
        """
        Detect Bollinger Band squeeze (low volatility)

        Squeeze = bandwidth at multi-period low
        Typically precedes high volatility breakout
        """
        recent_bandwidth = bandwidth[-lookback:]

        # Current bandwidth percentile
        current_bw = bandwidth[-1]
        percentile = stats.percentileofscore(recent_bandwidth, current_bw)

        # Squeeze if in bottom 5%
        if percentile < 5:
            signal = 'squeeze_active'
        elif percentile < 20:
            signal = 'squeeze_building'
        elif percentile > 80:
            signal = 'high_volatility'
        else:
            signal = 'normal'

        return {
            'signal': signal,
            'bandwidth': current_bw,
            'percentile': percentile
        }

    def atr_breakout_signal(self, close, atr, multiplier=2.0):
        """
        Generate breakout signals using ATR bands

        Buy: Close > (Previous Close + multiplier × ATR)
        Sell: Close < (Previous Close - multiplier × ATR)
        """
        prev_close = np.roll(close, 1)

        upper_threshold = prev_close + (multiplier * atr)
        lower_threshold = prev_close - (multiplier * atr)

        signals = np.zeros(len(close))

        # Breakout signals
        signals[close > upper_threshold] = 1   # Buy signal
        signals[close < lower_threshold] = -1  # Sell signal

        return signals

# Usage Example
vol_trader = VolatilityTrading(atr_period=14, bb_period=20, bb_std=2.0)

# Generate sample price data
np.random.seed(42)
n = 500
close = 100 + np.cumsum(np.random.randn(n) * 0.5)
high = close + np.abs(np.random.randn(n) * 0.3)
low = close - np.abs(np.random.randn(n) * 0.3)

# ATR
atr = vol_trader.calculate_atr(high, low, close)
print(f"Current ATR: {atr[-1]:.2f}")

# Bollinger Bands
bb = vol_trader.calculate_bollinger_bands(close)
print(f"Bollinger %B: {bb['percent_b'][-1]:.2f}")
print(f"Bandwidth: {bb['bandwidth'][-1]:.4f}")

# Historical Volatility
hist_vol = vol_trader.calculate_historical_volatility(close, window=20)
print(f"20-day Historical Vol: {hist_vol[-1]:.2%}")

# Parkinson Volatility
park_vol = vol_trader.calculate_parkinson_volatility(high, low, window=20)
print(f"20-day Parkinson Vol: {park_vol[-1]:.2%}")

# Returns for GARCH
returns = np.log(close / np.roll(close, 1))[1:] * 100  # Percentage returns

# GARCH model
garch = vol_trader.fit_garch_model(returns)
print(f"\nGARCH(1,1) Parameters:")
print(f"Omega: {garch['omega']:.6f}")
print(f"Alpha: {garch['alpha']:.4f}")
print(f"Beta: {garch['beta']:.4f}")
print(f"Persistence: {garch['persistence']:.4f}")
print(f"Forecasted Vol: {garch['forecasted_vol']:.2%}")

# Volatility Cone
cone = vol_trader.calculate_volatility_cone(close)
print(f"\nVolatility Cone:")
for horizon, stats in cone.items():
    print(f"{horizon}: Current={stats['current']:.2%}, Median={stats['median']:.2%}, P75={stats['p75']:.2%}")

# Squeeze Detection
squeeze = vol_trader.bollinger_squeeze_signal(bb['bandwidth'])
print(f"\nBollinger Squeeze: {squeeze['signal']}")
print(f"Bandwidth Percentile: {squeeze['percentile']:.1f}%")

# ATR Breakout Signals
signals = vol_trader.atr_breakout_signal(close, atr, multiplier=2.0)
print(f"Current ATR Breakout Signal: {signals[-1]}")
```

### When to Use

**Optimal Conditions:**
- Volatility mean-reversion strategies (vol cycles high/low)
- Breakout trading (low vol → high vol transition)
- Position sizing based on current volatility
- Stop-loss placement (ATR-based stops)
- Range-bound markets (Bollinger mean reversion)

**Avoid When:**
- Strong trending markets (Bollinger Bands not effective)
- News events (vol models break down)
- Low liquidity (wide spreads invalidate technical signals)

### Strengths and Weaknesses

**Strengths:**
- Adapts to changing market conditions
- ATR-based stops reduce whipsaws
- Bollinger squeeze predicts breakouts
- GARCH captures volatility clustering
- Works across all timeframes

**Weaknesses:**
- Lagging indicators (historical vol)
- False breakouts common
- Requires parameter optimization
- Vol can stay high/low longer than expected
- Model risk (GARCH assumptions may not hold)

### Real-World Examples

**AQR Capital Management (Vol Targeting):**
- Risk parity strategies use vol targeting
- Target constant volatility (e.g., 10% annual)
- Scale positions inversely to volatility
- When vol doubles, halve position size
- Smoother equity curves, better risk-adjusted returns

**LJM Partners (Short Vol Disaster):**
- Sold VIX options assuming mean reversion
- Feb 2018: VIX spike from 14 → 50 in one day
- Lost -82% in single day
- Lesson: Volatility can gap beyond any stop loss

**Successful Vol Trading Example:**
```
ES Futures Volatility Strategy

Setup:
- 20-day Bollinger Bands (2 std dev)
- 14-day ATR for position sizing
- GARCH for vol forecasting

Current State:
- Price: 4500
- BB Upper: 4520
- BB Middle: 4500
- BB Lower: 4480
- Bandwidth: 0.009 (bottom 3% historically) → SQUEEZE
- ATR: 25 points
- GARCH forecast: Vol increasing next 5 days

Signal: Squeeze breakout imminent
- Wait for close > 4520 (upper band breakout)
- Or close < 4480 (lower band breakdown)

Breakout occurs: Close at 4525
- Entry: 4525 (long)
- Stop: 4525 - (2 × 25 ATR) = 4475
- Risk: 50 points = $2,500/contract

Position size ($100k, 2% risk):
- Risk amount: $2,000
- Contracts: $2,000 / $2,500 = 0.8 → 1 contract

Target:
- Volatility expansion typically lasts 5-10 days
- Target: Previous high volatility band = 4600
- Reward: 75 points = $3,750
- Risk/Reward: 1:1.5

Result:
- Day 5: Price reaches 4595
- Exit at 4595
- Profit: 70 points = $3,500
- Bandwidth expanded from 0.009 → 0.025 (normal)
```

### Integration with AI Decision-Making

```python
class AIVolatilityTrading:
    def __init__(self, base_strategy):
        self.vol_trader = base_strategy
        self.ml_model = None

    def predict_volatility_regime(self, features):
        """
        ML predicts upcoming volatility regime

        Features:
        - Current bandwidth
        - GARCH forecast
        - VIX term structure
        - Market breadth
        - Time of day/week
        """
        # ML predicts: low_vol, normal_vol, high_vol, volatility_spike
        prediction = self.ml_model.predict(features)

        regime_map = {
            0: 'low_vol',
            1: 'normal_vol',
            2: 'high_vol',
            3: 'volatility_spike'
        }

        regime = regime_map[prediction[0]]

        return {
            'regime': regime,
            'confidence': self.ml_model.predict_proba(features).max()
        }

    def adaptive_position_sizing(self, current_vol, target_vol=0.10):
        """
        Vol-targeting position sizing

        Maintain constant portfolio volatility
        """
        # Scale positions inversely to volatility
        if current_vol > 0:
            size_multiplier = target_vol / current_vol
        else:
            size_multiplier = 1.0

        # Cap at reasonable limits
        size_multiplier = np.clip(size_multiplier, 0.25, 4.0)

        return {
            'size_multiplier': size_multiplier,
            'current_vol': current_vol,
            'target_vol': target_vol
        }

    def breakout_probability(self, bandwidth_percentile, days_in_squeeze):
        """
        Estimate probability of volatility breakout

        Longer squeeze → higher probability of breakout
        """
        # Simple heuristic
        if bandwidth_percentile < 5 and days_in_squeeze > 10:
            prob = 0.8
        elif bandwidth_percentile < 10 and days_in_squeeze > 5:
            prob = 0.6
        elif bandwidth_percentile < 20:
            prob = 0.4
        else:
            prob = 0.2

        return {
            'breakout_probability': prob,
            'days_in_squeeze': days_in_squeeze,
            'bandwidth_percentile': bandwidth_percentile
        }
```

---

## 7. Momentum Models

### Core Mathematical Formulas

#### Rate of Change (ROC)
```
ROC = ((Price_current - Price_n_periods_ago) / Price_n_periods_ago) × 100

Momentum = Price_current - Price_n_periods_ago
```

#### Relative Strength Index (RSI)
```
RS = Average_Gain / Average_Loss

RSI = 100 - (100 / (1 + RS))

Where:
- Average_Gain = EMA(Gains, period)
- Average_Loss = EMA(Losses, period)
- Typical period: 14

Overbought: RSI > 70
Oversold: RSI < 30
```

#### Moving Average Convergence Divergence (MACD)
```
MACD_Line = EMA(Close, 12) - EMA(Close, 26)
Signal_Line = EMA(MACD_Line, 9)
MACD_Histogram = MACD_Line - Signal_Line

Bullish: MACD crosses above Signal
Bearish: MACD crosses below Signal
```

#### ADX (Trend Strength)
```
+DM = High_current - High_previous (if positive, else 0)
-DM = Low_previous - Low_current (if positive, else 0)

+DI = 100 × EMA(+DM, period) / ATR
-DI = 100 × EMA(-DM, period) / ATR

DX = 100 × |+DI - -DI| / (+DI + -DI)
ADX = EMA(DX, period)

ADX > 25: Trending
ADX < 20: Ranging
```

#### Trend Strength Score
```
Score = Σ(weights_i × indicator_i)

Example:
Score = 0.3×(Price > SMA200) + 0.3×(ADX > 25) + 0.2×(RSI > 50) + 0.2×(MACD > 0)

Score > 0.6: Strong uptrend
Score < 0.4: Strong downtrend
```

#### Volume-Weighted Momentum
```
Volume_Momentum = Σ(Price_change × Volume) / Σ(Volume)

Higher weight to price moves with high volume
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd

class MomentumModels:
    def __init__(self, rsi_period=14, macd_fast=12, macd_slow=26, macd_signal=9):
        """
        Initialize momentum indicators

        Args:
            rsi_period: RSI lookback period
            macd_fast: MACD fast EMA period
            macd_slow: MACD slow EMA period
            macd_signal: MACD signal line period
        """
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    def calculate_rsi(self, close):
        """
        Calculate Relative Strength Index

        Args:
            close: Close prices
        """
        # Price changes
        delta = np.diff(close)

        # Gains and losses
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        # Add leading zero
        gains = np.concatenate([[0], gains])
        losses = np.concatenate([[0], losses])

        # Exponential moving average
        avg_gain = pd.Series(gains).ewm(span=self.rsi_period, adjust=False).mean().values
        avg_loss = pd.Series(losses).ewm(span=self.rsi_period, adjust=False).mean().values

        # RS and RSI
        rs = avg_gain / (avg_loss + 1e-10)  # Avoid division by zero
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(self, close):
        """
        Calculate MACD indicator

        Returns: MACD line, signal line, histogram
        """
        # EMAs
        ema_fast = pd.Series(close).ewm(span=self.macd_fast, adjust=False).mean().values
        ema_slow = pd.Series(close).ewm(span=self.macd_slow, adjust=False).mean().values

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line
        signal_line = pd.Series(macd_line).ewm(span=self.macd_signal, adjust=False).mean().values

        # Histogram
        histogram = macd_line - signal_line

        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram
        }

    def calculate_adx(self, high, low, close, period=14):
        """
        Calculate Average Directional Index (trend strength)

        Args:
            high, low, close: Price arrays
            period: Lookback period
        """
        # Directional movement
        plus_dm = high - np.roll(high, 1)
        minus_dm = np.roll(low, 1) - low

        # Set to zero if not dominant
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)

        # ATR for normalization
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        atr = pd.Series(tr).ewm(span=period, adjust=False).mean().values

        # Directional indicators
        plus_di = 100 * pd.Series(plus_dm).ewm(span=period, adjust=False).mean().values / (atr + 1e-10)
        minus_di = 100 * pd.Series(minus_dm).ewm(span=period, adjust=False).mean().values / (atr + 1e-10)

        # DX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)

        # ADX (smoothed DX)
        adx = pd.Series(dx).ewm(span=period, adjust=False).mean().values

        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di
        }

    def calculate_roc(self, close, period=10):
        """
        Calculate Rate of Change

        Args:
            close: Close prices
            period: Lookback period
        """
        roc = ((close - np.roll(close, period)) / np.roll(close, period)) * 100

        return roc

    def calculate_trend_strength_score(self, close, high, low, sma_period=200):
        """
        Composite trend strength score (0-1)

        Combines multiple indicators
        """
        # SMA
        sma = pd.Series(close).rolling(window=sma_period).mean().values

        # RSI
        rsi = self.calculate_rsi(close)

        # MACD
        macd = self.calculate_macd(close)

        # ADX
        adx = self.calculate_adx(high, low, close)

        # Individual scores (0 or 1)
        score_sma = (close > sma).astype(float)
        score_adx = (adx['adx'] > 25).astype(float)
        score_rsi = (rsi > 50).astype(float)
        score_macd = (macd['macd_line'] > 0).astype(float)

        # Weighted composite
        weights = [0.3, 0.3, 0.2, 0.2]
        composite_score = (
            weights[0] * score_sma +
            weights[1] * score_adx +
            weights[2] * score_rsi +
            weights[3] * score_macd
        )

        return {
            'composite_score': composite_score,
            'sma_score': score_sma,
            'adx_score': score_adx,
            'rsi_score': score_rsi,
            'macd_score': score_macd
        }

    def calculate_volume_weighted_momentum(self, close, volume, period=20):
        """
        Volume-weighted momentum

        Gives more weight to price moves with high volume
        """
        # Price changes
        price_change = np.diff(close)
        price_change = np.concatenate([[0], price_change])

        # Volume-weighted sum
        vw_momentum = pd.Series(price_change * volume).rolling(window=period).sum().values / \
                       pd.Series(volume).rolling(window=period).sum().values

        return vw_momentum

    def generate_momentum_signal(self, close, high, low, volume=None):
        """
        Generate comprehensive momentum signal

        Returns: -1 (bearish), 0 (neutral), 1 (bullish)
        """
        # Calculate indicators
        rsi = self.calculate_rsi(close)
        macd = self.calculate_macd(close)
        adx = self.calculate_adx(high, low, close)
        trend_score = self.calculate_trend_strength_score(close, high, low)

        # Current values
        current_rsi = rsi[-1]
        current_macd_hist = macd['histogram'][-1]
        current_adx = adx['adx'][-1]
        current_trend = trend_score['composite_score'][-1]

        # Bullish conditions
        bullish_count = 0
        if current_rsi > 50 and current_rsi < 70:
            bullish_count += 1
        if current_macd_hist > 0:
            bullish_count += 1
        if current_adx > 25 and adx['plus_di'][-1] > adx['minus_di'][-1]:
            bullish_count += 1
        if current_trend > 0.6:
            bullish_count += 1

        # Bearish conditions
        bearish_count = 0
        if current_rsi < 50 and current_rsi > 30:
            bearish_count += 1
        if current_macd_hist < 0:
            bearish_count += 1
        if current_adx > 25 and adx['minus_di'][-1] > adx['plus_di'][-1]:
            bearish_count += 1
        if current_trend < 0.4:
            bearish_count += 1

        # Signal
        if bullish_count >= 3:
            signal = 1
        elif bearish_count >= 3:
            signal = -1
        else:
            signal = 0

        return {
            'signal': signal,
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'rsi': current_rsi,
            'macd_hist': current_macd_hist,
            'adx': current_adx,
            'trend_score': current_trend
        }

# Usage Example
momentum = MomentumModels()

# Generate sample data
np.random.seed(42)
n = 500
trend = np.linspace(0, 50, n)
noise = np.random.randn(n) * 2
close = 100 + trend + noise
high = close + np.abs(np.random.randn(n))
low = close - np.abs(np.random.randn(n))
volume = np.random.randint(1000, 10000, n)

# RSI
rsi = momentum.calculate_rsi(close)
print(f"Current RSI: {rsi[-1]:.2f}")

# MACD
macd = momentum.calculate_macd(close)
print(f"MACD Line: {macd['macd_line'][-1]:.2f}")
print(f"Signal Line: {macd['signal_line'][-1]:.2f}")
print(f"Histogram: {macd['histogram'][-1]:.2f}")

# ADX
adx = momentum.calculate_adx(high, low, close)
print(f"ADX: {adx['adx'][-1]:.2f}")
print(f"+DI: {adx['plus_di'][-1]:.2f}")
print(f"-DI: {adx['minus_di'][-1]:.2f}")

# ROC
roc = momentum.calculate_roc(close, period=10)
print(f"10-period ROC: {roc[-1]:.2f}%")

# Trend Strength Score
trend_strength = momentum.calculate_trend_strength_score(close, high, low)
print(f"Trend Strength Score: {trend_strength['composite_score'][-1]:.2f}")

# Volume-Weighted Momentum
vw_momentum = momentum.calculate_volume_weighted_momentum(close, volume)
print(f"Volume-Weighted Momentum: {vw_momentum[-1]:.4f}")

# Generate Signal
signal = momentum.generate_momentum_signal(close, high, low, volume)
print(f"\nMomentum Signal: {signal['signal']}")
print(f"Bullish Indicators: {signal['bullish_count']}/4")
print(f"Bearish Indicators: {signal['bearish_count']}/4")
```

### When to Use

**Optimal Conditions:**
- Trending markets (ADX > 25)
- After consolidation periods
- Strong directional volume
- Multiple timeframe confirmation
- Clear support/resistance breaks

**Avoid When:**
- Choppy, range-bound markets
- Low ADX (<20)
- During major news events (whipsaws)
- Divergence between price and indicators

### Strengths and Weaknesses

**Strengths:**
- Captures trend direction and strength
- Multiple confirmation reduces false signals
- Works across timeframes
- Easy to backtest and optimize
- Objective, rule-based

**Weaknesses:**
- Lagging indicators (trend already started)
- Whipsaws in ranging markets
- Requires parameter optimization
- Can miss early trend entry
- Overbought/oversold can persist

### Real-World Examples

**Turtle Traders (Momentum Breakout):**
- 20-day and 55-day breakout system
- Entry: New 20-day high/low
- Exit: 10-day adverse move
- ATR-based position sizing
- Captured massive trends (1983-1988)
- Average annual return: 80%+

**Integration with AI:**
```python
class AIMomentum:
    def __init__(self, base_strategy):
        self.momentum = base_strategy
        self.ml_model = None

    def predict_trend_continuation(self, features):
        """ML predicts if momentum will continue"""
        prob_continue = self.ml_model.predict_proba(features)[0][1]

        return prob_continue

    def adaptive_rsi_thresholds(self, market_regime):
        """Adjust RSI thresholds based on regime"""
        if market_regime == 'bull':
            # In bull markets, RSI 40-50 is oversold
            return {'overbought': 80, 'oversold': 40}
        elif market_regime == 'bear':
            # In bear markets, RSI 50-60 is overbought
            return {'overbought': 60, 'oversold': 20}
        else:
            return {'overbought': 70, 'oversold': 30}
```

---

*[Models 8-12 continue in next response due to length constraints...]*

