# 12 Trading Probability Models - Part 3 (Models 8-12)

**Final Section: Order Flow, Risk Management, Simulation, Bayesian, Information Theory**

---

## 8. Order Flow Analysis

### Core Mathematical Formulas

#### Order Flow Imbalance (OFI)
```
OFI = Buy_Volume - Sell_Volume

Normalized_OFI = OFI / Total_Volume

Delta = Cumulative OFI over period

Positive Delta → Aggressive buying (bullish)
Negative Delta → Aggressive selling (bearish)
```

#### Volume-Weighted Average Price (VWAP)
```
VWAP = Σ(Price_i × Volume_i) / Σ(Volume_i)

Price > VWAP → Buyers in control
Price < VWAP → Sellers in control

VWAP bands:
Upper = VWAP + (k × σ_price)
Lower = VWAP - (k × σ_price)
```

#### Volume Profile / Market Profile
```
For each price level:
Volume_at_Price_Level = Σ(Volume traded at that price)

Point of Control (POC) = Price level with highest volume
Value Area = Price range containing 70% of volume

POC acts as magnet (mean reversion target)
```

#### Volume-Synchronized Probability of Informed Trading (VPIN)
```
VPIN = |Buy_Volume - Sell_Volume| / Total_Volume

Over n buckets:
VPIN = (1/n) × Σ|Buy_Volume_i - Sell_Volume_i| / Total_Volume_i

High VPIN (>0.8) → High probability of informed trading → Adverse selection risk
Low VPIN (<0.3) → Low informed trading → Safe to provide liquidity
```

#### Amihud Illiquidity Measure
```
Illiquidity = |Return| / Dollar_Volume

High illiquidity → Price sensitive to order flow
Low illiquidity → Liquid, less market impact
```

#### Auction Market Theory - Zones
```
Acceptance: Price revisits level with increasing volume
Rejection: Price touches level, immediately reverses with high volume
Initiative: Directional move with sustained volume

Auction imbalance = P_distribution above value area / below value area
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd
from collections import defaultdict

class OrderFlowAnalysis:
    def __init__(self, vwap_std_bands=2.0):
        """
        Initialize order flow analysis

        Args:
            vwap_std_bands: Number of standard deviations for VWAP bands
        """
        self.vwap_std_bands = vwap_std_bands
        self.volume_profile = defaultdict(float)

    def calculate_ofi(self, buy_volume, sell_volume):
        """
        Calculate Order Flow Imbalance

        Args:
            buy_volume: Aggressive buy volume (market buy orders)
            sell_volume: Aggressive sell volume (market sell orders)
        """
        ofi = buy_volume - sell_volume
        total_volume = buy_volume + sell_volume

        if total_volume > 0:
            normalized_ofi = ofi / total_volume
        else:
            normalized_ofi = 0

        return {
            'ofi': ofi,
            'normalized_ofi': normalized_ofi,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'total_volume': total_volume
        }

    def classify_trades(self, prices, volumes, best_bid, best_ask):
        """
        Classify trades as buyer or seller initiated

        Uses tick rule: trade at ask = buy, trade at bid = sell
        """
        buy_volume = 0
        sell_volume = 0

        for price, volume in zip(prices, volumes):
            # Tick rule
            mid_price = (best_bid + best_ask) / 2

            if price >= mid_price:
                # Trade closer to ask → buyer initiated
                buy_volume += volume
            else:
                # Trade closer to bid → seller initiated
                sell_volume += volume

        return self.calculate_ofi(buy_volume, sell_volume)

    def calculate_vwap(self, prices, volumes):
        """
        Calculate Volume-Weighted Average Price

        Args:
            prices: Transaction prices
            volumes: Transaction volumes
        """
        # VWAP
        vwap = np.sum(prices * volumes) / np.sum(volumes)

        # Price variance for bands
        variance = np.sum(volumes * (prices - vwap)**2) / np.sum(volumes)
        std_dev = np.sqrt(variance)

        # VWAP bands
        upper_band = vwap + (self.vwap_std_bands * std_dev)
        lower_band = vwap - (self.vwap_std_bands * std_dev)

        return {
            'vwap': vwap,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'std_dev': std_dev
        }

    def build_volume_profile(self, prices, volumes, num_bins=50):
        """
        Build Volume Profile (Volume at Price)

        Args:
            prices: Price levels
            volumes: Volumes traded
            num_bins: Number of price bins
        """
        # Price bins
        min_price = np.min(prices)
        max_price = np.max(prices)

        bins = np.linspace(min_price, max_price, num_bins)
        bin_width = bins[1] - bins[0]

        # Accumulate volume at each price level
        volume_at_price = defaultdict(float)

        for price, volume in zip(prices, volumes):
            # Find bin
            bin_index = int((price - min_price) / bin_width)
            bin_index = min(bin_index, num_bins - 1)

            bin_price = bins[bin_index]
            volume_at_price[bin_price] += volume

        # Find Point of Control (POC)
        poc_price = max(volume_at_price, key=volume_at_price.get)
        poc_volume = volume_at_price[poc_price]

        # Find Value Area (70% of volume)
        total_volume = sum(volume_at_price.values())
        target_volume = total_volume * 0.70

        # Sort by volume
        sorted_prices = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)

        value_area_volume = 0
        value_area_prices = []

        for price, vol in sorted_prices:
            if value_area_volume < target_volume:
                value_area_prices.append(price)
                value_area_volume += vol

        value_area_high = max(value_area_prices)
        value_area_low = min(value_area_prices)

        return {
            'volume_profile': dict(volume_at_price),
            'poc_price': poc_price,
            'poc_volume': poc_volume,
            'value_area_high': value_area_high,
            'value_area_low': value_area_low,
            'value_area_volume_pct': (value_area_volume / total_volume)
        }

    def calculate_vpin(self, buy_volumes, sell_volumes, num_buckets=50):
        """
        Calculate VPIN (Volume-Synchronized Probability of Informed Trading)

        Args:
            buy_volumes: Array of buy volumes
            sell_volumes: Array of sell volumes
            num_buckets: Number of volume buckets to analyze
        """
        if len(buy_volumes) < num_buckets:
            return {'vpin': 0, 'warning': 'Insufficient data'}

        # Recent buckets
        recent_buy = buy_volumes[-num_buckets:]
        recent_sell = sell_volumes[-num_buckets:]

        # VPIN calculation
        ofi_abs = np.abs(recent_buy - recent_sell)
        total_vol = recent_buy + recent_sell

        if np.sum(total_vol) > 0:
            vpin = np.sum(ofi_abs) / np.sum(total_vol)
        else:
            vpin = 0

        # Interpretation
        if vpin > 0.8:
            toxicity = 'high'
            recommendation = 'widen_spreads_or_avoid'
        elif vpin > 0.5:
            toxicity = 'moderate'
            recommendation = 'cautious'
        else:
            toxicity = 'low'
            recommendation = 'normal_market_making'

        return {
            'vpin': vpin,
            'toxicity': toxicity,
            'recommendation': recommendation
        }

    def calculate_amihud_illiquidity(self, returns, dollar_volumes):
        """
        Calculate Amihud illiquidity measure

        Higher value = less liquid (price impact per dollar traded)
        """
        if len(dollar_volumes) == 0:
            return 0

        # Illiquidity = avg(|return| / dollar_volume)
        illiquidity_measures = np.abs(returns) / (dollar_volumes + 1e-10)

        avg_illiquidity = np.mean(illiquidity_measures)

        return {
            'illiquidity': avg_illiquidity,
            'interpretation': 'high' if avg_illiquidity > 1e-6 else 'normal'
        }

    def auction_analysis(self, prices, volumes):
        """
        Analyze auction behavior (acceptance, rejection, initiative)

        Args:
            prices: Price array
            volumes: Volume array
        """
        if len(prices) < 3:
            return {'status': 'insufficient_data'}

        # Calculate volume profile
        profile = self.build_volume_profile(prices, volumes)

        poc = profile['poc_price']
        va_high = profile['value_area_high']
        va_low = profile['value_area_low']

        current_price = prices[-1]

        # Determine position relative to value area
        if current_price > va_high:
            position = 'above_value'
            bias = 'bullish'
        elif current_price < va_low:
            position = 'below_value'
            bias = 'bearish'
        else:
            position = 'within_value'
            bias = 'neutral'

        # Check for acceptance/rejection
        # If price returns to POC repeatedly → acceptance
        # If price touches POC and reverses sharply → rejection

        distance_to_poc = abs(current_price - poc)
        distance_to_poc_pct = distance_to_poc / current_price

        if distance_to_poc_pct < 0.002:  # Within 0.2% of POC
            auction_state = 'near_poc_equilibrium'
        elif position == 'within_value':
            auction_state = 'acceptance'
        else:
            auction_state = 'initiative_away_from_value'

        return {
            'position': position,
            'bias': bias,
            'auction_state': auction_state,
            'distance_to_poc_pct': distance_to_poc_pct,
            'poc': poc,
            'value_area_high': va_high,
            'value_area_low': va_low
        }

# Usage Example
ofa = OrderFlowAnalysis()

# Generate sample data
np.random.seed(42)
n = 1000

# Simulated order flow
base_price = 4500
prices = base_price + np.random.randn(n) * 5
volumes = np.random.randint(10, 1000, n)

# Simulate buy/sell classification
best_bid = base_price - 0.25
best_ask = base_price + 0.25

# Classify trades
ofi_data = ofa.classify_trades(prices, volumes, best_bid, best_ask)
print(f"Order Flow Imbalance: {ofi_data['ofi']:.0f}")
print(f"Normalized OFI: {ofi_data['normalized_ofi']:.2f}")

# VWAP
vwap_data = ofa.calculate_vwap(prices, volumes)
print(f"\nVWAP: {vwap_data['vwap']:.2f}")
print(f"Upper Band: {vwap_data['upper_band']:.2f}")
print(f"Lower Band: {vwap_data['lower_band']:.2f}")

# Volume Profile
profile = ofa.build_volume_profile(prices, volumes)
print(f"\nPoint of Control (POC): {profile['poc_price']:.2f}")
print(f"Value Area High: {profile['value_area_high']:.2f}")
print(f"Value Area Low: {profile['value_area_low']:.2f}")

# VPIN
buy_vols = np.random.randint(50, 500, 100)
sell_vols = np.random.randint(50, 500, 100)
vpin_data = ofa.calculate_vpin(buy_vols, sell_vols)
print(f"\nVPIN: {vpin_data['vpin']:.2f}")
print(f"Toxicity: {vpin_data['toxicity']}")
print(f"Recommendation: {vpin_data['recommendation']}")

# Auction Analysis
auction = ofa.auction_analysis(prices, volumes)
print(f"\nAuction Position: {auction['position']}")
print(f"Bias: {auction['bias']}")
print(f"Auction State: {auction['auction_state']}")
print(f"Distance to POC: {auction['distance_to_poc_pct']:.2%}")
```

### When to Use

**Optimal Conditions:**
- Intraday trading (order flow most relevant)
- Liquid markets with visible order book
- Mean reversion strategies (VWAP, POC reversion)
- Market making (VPIN for toxicity detection)
- Scalping (delta divergence signals)

**Avoid When:**
- Low liquidity (order flow unreliable)
- Position trading (daily+ timeframes)
- Opaque markets (limited volume data)

### Strengths and Weaknesses

**Strengths:**
- Real-time, forward-looking (not lagging)
- Reveals institutional activity
- POC/VWAP act as magnets (mean reversion targets)
- VPIN detects toxic flow before adverse moves
- Works in all market conditions

**Weaknesses:**
- Requires tick-by-tick data (expensive)
- Complex to implement correctly
- Can be noisy on short timeframes
- Requires understanding of market microstructure
- Dark pools obscure true order flow

### Real-World Examples

**Jump Trading (HFT Order Flow):**
- Analyzes every tick for order flow imbalance
- VPIN-based adverse selection avoidance
- Provides liquidity when VPIN < 0.4
- Pulls quotes when VPIN > 0.7
- Microsecond-level execution

**Jigsaw Trading (Retail Order Flow):**
- Volume Profile + Order Flow Delta tools
- POC as support/resistance
- Delta divergence signals (price up, delta down = bearish)
- Real-time footprint charts
- Used by retail day traders successfully

**Professional Trader Example:**
```
ES Futures Scalping with Order Flow

Setup:
- 5-minute VWAP
- Volume Profile (POC)
- Real-time Delta

Current State (9:45 AM ET):
- ES Price: 4505.00
- VWAP: 4500.00
- POC: 4498.00
- Cumulative Delta: +15,000 contracts (bullish)

Signal 1: Price pullback to VWAP
- Price drops to 4500.25 (near VWAP)
- Delta remains positive (buyers still active)
- Entry: Buy 4500.50
- Stop: 4498.00 (below POC)
- Target: 4507.00 (previous high)
- Risk: 2.50 points ($125)
- Reward: 6.50 points ($325)
- R:R = 1:2.6

Result:
- Price bounces from VWAP
- Reaches 4507.00 in 15 minutes
- Exit at target
- Profit: $325/contract

Signal 2: Negative Delta Divergence
- Price: 4510.00 (new high)
- Delta: Turns negative (-5,000 contracts)
- Interpretation: Weak high, sellers stepping in
- Entry: Sell 4509.75
- Stop: 4512.00
- Target: 4502.00 (VWAP)
- Risk: 2.25 points
- Reward: 7.75 points

Result:
- Price rejects high
- Falls back to VWAP
- Exit at 4502.25
- Profit: $373/contract
```

### Integration with AI Decision-Making

```python
class AIOrderFlow:
    def __init__(self, base_strategy):
        self.ofa = base_strategy
        self.ml_model = None

    def predict_order_flow_continuation(self, features):
        """
        ML predicts if current order flow imbalance will continue

        Features:
        - Current cumulative delta
        - VPIN
        - Distance from VWAP
        - Volume profile shape
        - Time of day
        """
        prediction = self.ml_model.predict_proba(features)

        p_continuation = prediction[0][1]

        return {
            'p_continuation': p_continuation,
            'confidence': max(prediction[0])
        }

    def smart_poc_targeting(self, current_price, poc, delta):
        """
        Determine if POC will act as support or resistance

        Positive delta → POC likely support
        Negative delta → POC likely resistance
        """
        distance_to_poc = current_price - poc

        if delta > 0 and distance_to_poc > 0:
            # Price above POC, positive delta
            role = 'poc_is_support'
            action = 'buy_pullback_to_poc'

        elif delta < 0 and distance_to_poc < 0:
            # Price below POC, negative delta
            role = 'poc_is_resistance'
            action = 'sell_rally_to_poc'

        else:
            role = 'uncertain'
            action = 'wait'

        return {
            'role': role,
            'action': action,
            'delta': delta,
            'distance_to_poc': distance_to_poc
        }

    def vpin_regime_detection(self, vpin_history, window=20):
        """
        Detect regime changes using VPIN

        Low VPIN → High VPIN = Regime change imminent
        """
        recent_vpin = vpin_history[-window:]
        avg_vpin = np.mean(recent_vpin)
        current_vpin = vpin_history[-1]

        if current_vpin > avg_vpin * 1.5:
            regime = 'increasing_toxicity'
            action = 'reduce_exposure'
        elif current_vpin < avg_vpin * 0.5:
            regime = 'normal_flow'
            action = 'normal_trading'
        else:
            regime = 'stable'
            action = 'maintain'

        return {
            'regime': regime,
            'action': action,
            'current_vpin': current_vpin,
            'avg_vpin': avg_vpin
        }
```

---

## 9. Bookkeeper Risk Management

### Core Mathematical Formulas

#### Position Sizing (Fixed Fractional)
```
Position_Size = (Account_Value × Risk_Pct) / Stop_Loss_Distance

Example:
Account: $100,000
Risk: 2%
Stop: 10 points

Position = ($100,000 × 0.02) / 10 = $2,000 / 10 = 200 point-equivalent
```

#### Portfolio Heat (Total Risk)
```
Portfolio_Heat = Σ(Position_i × Risk_per_Position_i)

Max recommended: 6-10% for professional traders
Conservative: 2-4%
```

#### Correlation-Adjusted Risk
```
Portfolio_Variance = Σ(w_i² × σ_i²) + Σ Σ(w_i × w_j × ρ_{ij} × σ_i × σ_j)

Where:
- w_i = weight of position i
- σ_i = volatility of position i
- ρ_{ij} = correlation between positions i and j

Portfolio_Risk = √(Portfolio_Variance)
```

#### Value at Risk (VaR)
```
VaR_α = μ - (Z_α × σ)

Where:
- μ = expected return
- Z_α = Z-score for confidence level α
- σ = portfolio standard deviation

95% VaR: Z = 1.65
99% VaR: Z = 2.33
```

#### Expected Shortfall (CVaR)
```
CVaR_α = E[Loss | Loss > VaR_α]

Average loss in worst α% of cases
More conservative than VaR (accounts for tail risk)
```

#### Maximum Drawdown Capacity
```
Max_Drawdown_Capacity = (Current_Equity - Minimum_Equity) / Peak_Equity

Risk_of_Ruin when:
Current_Drawdown / Max_Drawdown_Capacity > 0.7
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd
from scipy import stats

class BookkeeperRiskManagement:
    def __init__(self, max_portfolio_heat=0.06, max_position_risk=0.02):
        """
        Initialize risk management system

        Args:
            max_portfolio_heat: Maximum total portfolio risk (0.06 = 6%)
            max_position_risk: Maximum risk per position (0.02 = 2%)
        """
        self.max_portfolio_heat = max_portfolio_heat
        self.max_position_risk = max_position_risk

        self.positions = []

    def calculate_position_size(self, account_value, stop_loss_distance,
                                risk_pct=None):
        """
        Calculate position size using fixed fractional method

        Args:
            account_value: Current account value
            stop_loss_distance: Distance to stop loss in currency units
            risk_pct: Risk percentage (uses max if None)
        """
        if risk_pct is None:
            risk_pct = self.max_position_risk

        # Risk amount
        risk_amount = account_value * risk_pct

        # Position size
        if stop_loss_distance > 0:
            position_size = risk_amount / stop_loss_distance
        else:
            position_size = 0

        return {
            'position_size': position_size,
            'risk_amount': risk_amount,
            'risk_pct': risk_pct
        }

    def calculate_portfolio_heat(self, positions):
        """
        Calculate total portfolio risk exposure

        Args:
            positions: List of dicts with 'size', 'entry', 'stop'
        """
        total_risk = 0

        for pos in positions:
            # Risk per position = size × |entry - stop|
            position_risk = pos['size'] * abs(pos['entry'] - pos['stop'])
            total_risk += position_risk

        return {
            'total_risk': total_risk,
            'num_positions': len(positions),
            'avg_risk_per_position': total_risk / len(positions) if positions else 0
        }

    def check_new_position_allowed(self, account_value, new_position_risk,
                                   current_positions):
        """
        Check if new position can be added without exceeding risk limits

        Returns: True/False and reason
        """
        # Current portfolio heat
        current_heat = self.calculate_portfolio_heat(current_positions)['total_risk']
        current_heat_pct = current_heat / account_value

        # After adding new position
        new_heat_pct = (current_heat + new_position_risk) / account_value

        # Check limits
        if new_heat_pct > self.max_portfolio_heat:
            return {
                'allowed': False,
                'reason': 'exceeds_portfolio_heat',
                'current_heat': current_heat_pct,
                'new_heat': new_heat_pct,
                'max_heat': self.max_portfolio_heat
            }

        elif new_position_risk / account_value > self.max_position_risk:
            return {
                'allowed': False,
                'reason': 'exceeds_single_position_risk',
                'position_risk_pct': new_position_risk / account_value,
                'max_position_risk': self.max_position_risk
            }

        else:
            return {
                'allowed': True,
                'new_heat': new_heat_pct,
                'remaining_capacity': self.max_portfolio_heat - new_heat_pct
            }

    def correlation_adjusted_risk(self, positions, correlation_matrix):
        """
        Calculate portfolio risk accounting for correlation

        Args:
            positions: List of position sizes
            correlation_matrix: Correlation matrix between assets
        """
        n = len(positions)

        if n == 0:
            return {'portfolio_std': 0}

        # Position weights
        weights = np.array([p['size'] for p in positions])
        weights = weights / np.sum(weights)

        # Volatilities
        vols = np.array([p.get('volatility', 0.01) for p in positions])

        # Portfolio variance
        portfolio_var = 0

        for i in range(n):
            for j in range(n):
                portfolio_var += (weights[i] * weights[j] *
                                 correlation_matrix[i, j] *
                                 vols[i] * vols[j])

        portfolio_std = np.sqrt(portfolio_var)

        # Diversification benefit
        undiversified_std = np.sum(weights * vols)
        diversification_benefit = undiversified_std - portfolio_std

        return {
            'portfolio_std': portfolio_std,
            'undiversified_std': undiversified_std,
            'diversification_benefit': diversification_benefit,
            'benefit_pct': (diversification_benefit / undiversified_std) if undiversified_std > 0 else 0
        }

    def calculate_var(self, portfolio_value, returns, confidence=0.95):
        """
        Calculate Value at Risk (VaR)

        Args:
            portfolio_value: Current portfolio value
            returns: Historical returns array
            confidence: Confidence level (0.95 = 95%)
        """
        # Mean and std
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Z-score for confidence level
        z_score = stats.norm.ppf(1 - confidence)

        # VaR
        var_pct = mean_return + (z_score * std_return)
        var_dollar = portfolio_value * abs(var_pct)

        return {
            'var_pct': var_pct,
            'var_dollar': var_dollar,
            'confidence': confidence,
            'interpretation': f'{confidence:.0%} confident loss will not exceed ${var_dollar:,.0f}'
        }

    def calculate_cvar(self, portfolio_value, returns, confidence=0.95):
        """
        Calculate Conditional Value at Risk (Expected Shortfall)

        Average loss in worst (1-confidence)% of cases
        """
        # Sort returns
        sorted_returns = np.sort(returns)

        # Threshold index
        threshold_idx = int(len(sorted_returns) * (1 - confidence))

        # CVaR = average of returns below threshold
        worst_returns = sorted_returns[:threshold_idx]

        if len(worst_returns) > 0:
            cvar_pct = np.mean(worst_returns)
            cvar_dollar = portfolio_value * abs(cvar_pct)
        else:
            cvar_pct = 0
            cvar_dollar = 0

        return {
            'cvar_pct': cvar_pct,
            'cvar_dollar': cvar_dollar,
            'confidence': confidence,
            'interpretation': f'Average loss in worst {(1-confidence):.0%} of cases: ${cvar_dollar:,.0f}'
        }

    def maximum_drawdown_analysis(self, equity_curve):
        """
        Analyze maximum drawdown and current drawdown

        Args:
            equity_curve: Array of account values over time
        """
        # Running maximum
        running_max = np.maximum.accumulate(equity_curve)

        # Drawdown at each point
        drawdown = (equity_curve - running_max) / running_max

        # Maximum drawdown
        max_drawdown = np.min(drawdown)

        # Current drawdown
        current_drawdown = drawdown[-1]

        # Duration in drawdown
        in_drawdown = current_drawdown < 0

        if in_drawdown:
            # Find start of current drawdown
            dd_start = np.where(drawdown == 0)[0]
            if len(dd_start) > 0:
                dd_start_idx = dd_start[-1]
                dd_duration = len(equity_curve) - dd_start_idx
            else:
                dd_duration = len(equity_curve)
        else:
            dd_duration = 0

        # Risk assessment
        if abs(current_drawdown / max_drawdown) > 0.7:
            risk_level = 'high'
            action = 'reduce_exposure_significantly'
        elif abs(current_drawdown / max_drawdown) > 0.5:
            risk_level = 'elevated'
            action = 'reduce_exposure_moderately'
        else:
            risk_level = 'normal'
            action = 'maintain'

        return {
            'max_drawdown': max_drawdown,
            'current_drawdown': current_drawdown,
            'dd_duration': dd_duration,
            'in_drawdown': in_drawdown,
            'risk_level': risk_level,
            'action': action
        }

# Usage Example
risk_mgr = BookkeeperRiskManagement(max_portfolio_heat=0.06, max_position_risk=0.02)

# Position sizing
account_value = 100000
stop_distance = 50  # $50 stop loss

position = risk_mgr.calculate_position_size(
    account_value=account_value,
    stop_loss_distance=stop_distance
)
print(f"Position Size: {position['position_size']:.2f} units")
print(f"Risk Amount: ${position['risk_amount']:.2f}")

# Portfolio heat
current_positions = [
    {'size': 10, 'entry': 4500, 'stop': 4480},  # Risk: 10 × 20 = $200
    {'size': 5, 'entry': 100, 'stop': 98},      # Risk: 5 × 2 = $10
    {'size': 20, 'entry': 50, 'stop': 49}       # Risk: 20 × 1 = $20
]

heat = risk_mgr.calculate_portfolio_heat(current_positions)
print(f"\nPortfolio Heat: ${heat['total_risk']:.2f}")
print(f"Heat %: {(heat['total_risk'] / account_value):.2%}")

# Check new position
new_position_risk = 1000
check = risk_mgr.check_new_position_allowed(
    account_value=account_value,
    new_position_risk=new_position_risk,
    current_positions=current_positions
)
print(f"\nNew position allowed: {check['allowed']}")
if check['allowed']:
    print(f"New heat: {check['new_heat']:.2%}")
else:
    print(f"Reason: {check['reason']}")

# Correlation-adjusted risk
positions_with_vol = [
    {'size': 10, 'volatility': 0.02},
    {'size': 5, 'volatility': 0.03},
    {'size': 8, 'volatility': 0.025}
]

# Correlation matrix (example: moderately correlated)
corr_matrix = np.array([
    [1.0, 0.5, 0.6],
    [0.5, 1.0, 0.4],
    [0.6, 0.4, 1.0]
])

corr_risk = risk_mgr.correlation_adjusted_risk(positions_with_vol, corr_matrix)
print(f"\nPortfolio Std (corr-adjusted): {corr_risk['portfolio_std']:.2%}")
print(f"Diversification benefit: {corr_risk['benefit_pct']:.2%}")

# VaR
returns = np.random.randn(252) * 0.01  # Simulated daily returns
var = risk_mgr.calculate_var(account_value, returns, confidence=0.95)
print(f"\n95% VaR: ${var['var_dollar']:,.0f}")

# CVaR
cvar = risk_mgr.calculate_cvar(account_value, returns, confidence=0.95)
print(f"95% CVaR: ${cvar['cvar_dollar']:,.0f}")

# Drawdown analysis
equity_curve = account_value * (1 + np.cumsum(returns))
dd = risk_mgr.maximum_drawdown_analysis(equity_curve)
print(f"\nMax Drawdown: {dd['max_drawdown']:.2%}")
print(f"Current Drawdown: {dd['current_drawdown']:.2%}")
print(f"Risk Level: {dd['risk_level']}")
print(f"Action: {dd['action']}")
```

### When to Use

**Optimal Conditions:**
- All trading (fundamental risk management)
- Multiple uncorrelated strategies
- Leveraged trading
- Volatile markets
- Professional trading operations

**Avoid When:**
- Never (always use risk management!)

### Strengths and Weaknesses

**Strengths:**
- Prevents catastrophic losses
- Ensures long-term survival
- Quantifies risk precisely
- Accounts for correlation
- Systematic, unemotional

**Weaknesses:**
- Cannot prevent all losses
- Correlation can spike in crises
- VaR underestimates tail risk
- Requires discipline to follow

### Real-World Examples

**Long-Term Capital Management (LTCM) Failure:**
- Brilliant quants (Nobel laureates)
- Ignored correlation risk
- Assumed normal distributions (wrong)
- Leverage: 25:1
- 1998: Correlations went to 1.0
- Lost $4.6B in 4 months
- Lesson: Risk management > Alpha

**Renaissance Medallion (Success):**
- Strict risk limits
- Max drawdown capacity: 20%
- Diversification: 1000s of small bets
- Correlation monitoring
- Result: 66% annual returns for 30 years

### Integration with AI:**

```python
class AIRiskManagement:
    def __init__(self, base_risk_mgr):
        self.risk_mgr = base_risk_mgr
        self.ml_model = None

    def dynamic_position_sizing(self, market_regime, strategy_confidence):
        """
        Adjust position sizing based on regime and ML confidence
        """
        base_risk = self.risk_mgr.max_position_risk

        if market_regime == 'high_vol' or strategy_confidence < 0.6:
            adjusted_risk = base_risk * 0.5  # Half size
        elif market_regime == 'trending' and strategy_confidence > 0.8:
            adjusted_risk = base_risk * 1.5  # Increase size
        else:
            adjusted_risk = base_risk

        return adjusted_risk

    def predict_correlation_spike(self, features):
        """
        ML predicts when correlations will spike (crisis detector)
        """
        prob_crisis = self.ml_model.predict_proba(features)[0][1]

        if prob_crisis > 0.7:
            action = 'reduce_all_positions'
        elif prob_crisis > 0.4:
            action = 'increase_cash_buffer'
        else:
            action = 'normal'

        return {'prob_crisis': prob_crisis, 'action': action}
```

---

## 10. Monte Carlo Simulation

### Core Mathematical Formulas

#### Basic Monte Carlo
```
For N simulations:
  For each timestep t:
    Return_t = μ + σ × Z_t
    Price_t = Price_{t-1} × exp(Return_t)

Where Z_t ~ N(0,1) (random normal)

Statistics:
- Mean final price = avg(Price_T across simulations)
- Confidence intervals = percentiles of final prices
```

#### Geometric Brownian Motion (GBM)
```
dS_t = μ × S_t × dt + σ × S_t × dW_t

Discrete form:
S_{t+1} = S_t × exp((μ - σ²/2)Δt + σ√Δt × Z)

Where:
- μ = drift (expected return)
- σ = volatility
- Z ~ N(0,1)
```

#### Monte Carlo VaR
```
For N simulations of portfolio:
  Calculate final P&L for each path

VaR_α = Percentile(P&L, α)

Example: 95% VaR = 5th percentile of P&L distribution
```

#### Drawdown Distribution
```
For each simulation path:
  Calculate maximum drawdown

Drawdown_distribution = histogram of max DDs across paths

99th percentile DD = worst expected DD with 99% confidence
```

#### Win Rate / Profit Factor Validation
```
For strategy with historical:
- Win rate W
- Avg win R_w
- Avg loss R_l

Simulate N trades:
  For each trade:
    If random() < W:
      P&L += R_w
    Else:
      P&L += -R_l

Check if historical results within 95% CI of simulations
```

#### Expected Shortfall from MC
```
CVaR = Mean(losses worse than VaR threshold)

From MC paths:
CVaR = avg(P&L for paths where P&L < VaR_α)
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

class MonteCarloSimulation:
    def __init__(self, num_simulations=10000, num_periods=252):
        """
        Initialize Monte Carlo simulator

        Args:
            num_simulations: Number of simulation paths
            num_periods: Number of time periods (e.g., trading days)
        """
        self.num_simulations = num_simulations
        self.num_periods = num_periods

    def simulate_gbm(self, initial_price, mu, sigma):
        """
        Simulate Geometric Brownian Motion

        Args:
            initial_price: Starting price
            mu: Expected return (annualized)
            sigma: Volatility (annualized)
        """
        dt = 1 / 252  # Daily timestep

        # Random normal draws
        Z = np.random.standard_normal((self.num_periods, self.num_simulations))

        # Price paths
        returns = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z

        # Cumulative returns
        log_returns = np.cumsum(returns, axis=0)

        # Price paths
        price_paths = initial_price * np.exp(log_returns)

        # Add initial price
        price_paths = np.vstack([np.full(self.num_simulations, initial_price), price_paths])

        return price_paths

    def calculate_statistics(self, price_paths):
        """
        Calculate statistics from simulation paths
        """
        final_prices = price_paths[-1, :]

        # Statistics
        mean_final = np.mean(final_prices)
        std_final = np.std(final_prices)
        median_final = np.median(final_prices)

        # Confidence intervals
        ci_95_low = np.percentile(final_prices, 2.5)
        ci_95_high = np.percentile(final_prices, 97.5)

        ci_99_low = np.percentile(final_prices, 0.5)
        ci_99_high = np.percentile(final_prices, 99.5)

        return {
            'mean': mean_final,
            'std': std_final,
            'median': median_final,
            'ci_95': (ci_95_low, ci_95_high),
            'ci_99': (ci_99_low, ci_99_high)
        }

    def calculate_var_cvar(self, price_paths, initial_price, confidence=0.95):
        """
        Calculate VaR and CVaR from Monte Carlo simulation
        """
        final_prices = price_paths[-1, :]

        # P&L
        pnl = final_prices - initial_price

        # VaR (percentile)
        var_percentile = (1 - confidence) * 100
        var = np.percentile(pnl, var_percentile)

        # CVaR (expected shortfall)
        losses_beyond_var = pnl[pnl <= var]
        cvar = np.mean(losses_beyond_var) if len(losses_beyond_var) > 0 else var

        return {
            'var': var,
            'cvar': cvar,
            'confidence': confidence,
            'var_pct': (var / initial_price),
            'cvar_pct': (cvar / initial_price)
        }

    def calculate_drawdown_distribution(self, price_paths):
        """
        Calculate maximum drawdown for each simulation path
        """
        max_drawdowns = []

        for i in range(price_paths.shape[1]):
            path = price_paths[:, i]

            # Running maximum
            running_max = np.maximum.accumulate(path)

            # Drawdown
            drawdown = (path - running_max) / running_max

            # Maximum drawdown for this path
            max_dd = np.min(drawdown)
            max_drawdowns.append(max_dd)

        max_drawdowns = np.array(max_drawdowns)

        # Statistics
        mean_dd = np.mean(max_drawdowns)
        median_dd = np.median(max_drawdowns)
        percentile_95 = np.percentile(max_drawdowns, 95)
        percentile_99 = np.percentile(max_drawdowns, 99)

        return {
            'mean_max_dd': mean_dd,
            'median_max_dd': median_dd,
            'dd_95': percentile_95,
            'dd_99': percentile_99,
            'all_drawdowns': max_drawdowns
        }

    def validate_strategy_performance(self, win_rate, avg_win, avg_loss,
                                     num_trades, historical_pnl):
        """
        Validate if historical strategy performance is within expected range

        Args:
            win_rate: Historical win rate
            avg_win: Average winning trade
            avg_loss: Average losing trade
            num_trades: Number of trades in backtest
            historical_pnl: Actual historical P&L
        """
        simulated_pnls = []

        for _ in range(self.num_simulations):
            pnl = 0

            for _ in range(num_trades):
                # Random outcome
                if np.random.random() < win_rate:
                    # Win
                    pnl += avg_win
                else:
                    # Loss
                    pnl -= avg_loss

            simulated_pnls.append(pnl)

        simulated_pnls = np.array(simulated_pnls)

        # Statistics
        mean_pnl = np.mean(simulated_pnls)
        std_pnl = np.std(simulated_pnls)

        # Confidence intervals
        ci_95_low = np.percentile(simulated_pnls, 2.5)
        ci_95_high = np.percentile(simulated_pnls, 97.5)

        # Check if historical within CI
        within_ci = ci_95_low <= historical_pnl <= ci_95_high

        # Z-score
        z_score = (historical_pnl - mean_pnl) / std_pnl if std_pnl > 0 else 0

        # P-value (two-tailed)
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

        return {
            'mean_expected_pnl': mean_pnl,
            'std_pnl': std_pnl,
            'ci_95': (ci_95_low, ci_95_high),
            'historical_pnl': historical_pnl,
            'within_ci': within_ci,
            'z_score': z_score,
            'p_value': p_value,
            'interpretation': 'realistic' if within_ci else 'suspicious (luck or curve-fit)'
        }

    def simulate_portfolio_paths(self, positions, correlation_matrix):
        """
        Simulate portfolio with multiple correlated positions

        Args:
            positions: List of {'initial': price, 'mu': return, 'sigma': vol, 'weight': allocation}
            correlation_matrix: Correlation between assets
        """
        n_assets = len(positions)

        # Cholesky decomposition for correlated random numbers
        L = np.linalg.cholesky(correlation_matrix)

        # Uncorrelated random numbers
        Z = np.random.standard_normal((self.num_periods, n_assets, self.num_simulations))

        # Correlated random numbers
        Z_corr = np.einsum('ij,tkj->tki', L, Z)

        # Simulate each asset
        portfolio_values = np.zeros((self.num_periods + 1, self.num_simulations))
        portfolio_values[0, :] = sum([p['initial'] * p['weight'] for p in positions])

        for t in range(self.num_periods):
            portfolio_change = 0

            for i, pos in enumerate(positions):
                # Asset return
                ret = (pos['mu'] - 0.5 * pos['sigma']**2) / 252 + \
                      pos['sigma'] / np.sqrt(252) * Z_corr[t, i, :]

                # Value change
                portfolio_change += pos['initial'] * pos['weight'] * (np.exp(ret) - 1)

            portfolio_values[t + 1, :] = portfolio_values[t, :] + portfolio_change

        return portfolio_values

# Usage Example
mc = MonteCarloSimulation(num_simulations=10000, num_periods=252)

# Simulate price paths (GBM)
initial_price = 4500
mu = 0.10  # 10% annual return
sigma = 0.20  # 20% annual volatility

price_paths = mc.simulate_gbm(initial_price, mu, sigma)

# Calculate statistics
stats_result = mc.calculate_statistics(price_paths)
print(f"Expected final price: ${stats_result['mean']:.2f}")
print(f"Std dev: ${stats_result['std']:.2f}")
print(f"95% CI: ${stats_result['ci_95'][0]:.2f} - ${stats_result['ci_95'][1]:.2f}")

# VaR and CVaR
var_cvar = mc.calculate_var_cvar(price_paths, initial_price, confidence=0.95)
print(f"\n95% VaR: ${var_cvar['var']:.2f} ({var_cvar['var_pct']:.2%})")
print(f"95% CVaR: ${var_cvar['cvar']:.2f} ({var_cvar['cvar_pct']:.2%})")

# Drawdown distribution
dd_dist = mc.calculate_drawdown_distribution(price_paths)
print(f"\nMean max drawdown: {dd_dist['mean_max_dd']:.2%}")
print(f"95th percentile DD: {dd_dist['dd_95']:.2%}")
print(f"99th percentile DD: {dd_dist['dd_99']:.2%}")

# Strategy validation
validation = mc.validate_strategy_performance(
    win_rate=0.55,
    avg_win=150,
    avg_loss=100,
    num_trades=100,
    historical_pnl=2750  # Actual backtest result
)
print(f"\nStrategy Validation:")
print(f"Expected P&L: ${validation['mean_expected_pnl']:.2f} ± ${validation['std_pnl']:.2f}")
print(f"95% CI: ${validation['ci_95'][0]:.2f} - ${validation['ci_95'][1]:.2f}")
print(f"Historical P&L: ${validation['historical_pnl']:.2f}")
print(f"Within CI: {validation['within_ci']}")
print(f"Interpretation: {validation['interpretation']}")
```

### When to Use

**Optimal Conditions:**
- Strategy validation
- Risk assessment (VaR, drawdown)
- Portfolio optimization
- Stress testing
- Confidence intervals for forecasts

**Avoid When:**
- Real-time trading decisions (too slow)
- Non-parametric distributions (use bootstrapping instead)

### Strengths and Weaknesses

**Strengths:**
- Quantifies uncertainty
- Identifies tail risks
- Validates backtest results
- Accounts for randomness
- Easy to understand visually

**Weaknesses:**
- Assumes known distribution (usually GBM)
- Computationally intensive
- GIGO (assumes parameters are correct)
- May underestimate black swans
- Doesn't predict the unpredictable

### Real-World Examples

**JPMorgan - London Whale (2012):**
- VaR model showed low risk
- Monte Carlo didn't capture correlation changes
- Lost $6.2B
- Lesson: Models are only as good as assumptions

**Professional Use:**
```
Futures Trading Strategy MC Validation

Historical backtest:
- 200 trades
- Win rate: 58%
- Avg win: $175
- Avg loss: $100
- Total P&L: $8,300

Monte Carlo (10,000 simulations):
- Expected P&L: $7,800 ± $1,456
- 95% CI: $5,000 - $10,600
- Historical $8,300 within CI ✓
- P-value: 0.73 (not suspicious)
- Max DD (99%): -18.5%
- Interpretation: Results are statistically realistic

Action: Deploy strategy with confidence
```

### Integration with AI:

```python
class AIMonteCarlo:
    def __init__(self, base_mc):
        self.mc = base_mc
        self.ml_model = None

    def ml_enhanced_parameters(self, current_features):
        """
        Use ML to predict μ and σ for MC simulation

        Better than using historical parameters
        """
        predicted_mu = self.ml_model.predict_mu(current_features)
        predicted_sigma = self.ml_model.predict_sigma(current_features)

        return {'mu': predicted_mu, 'sigma': predicted_sigma}

    def regime_conditional_mc(self, regime_probabilities):
        """
        Run MC simulations for each regime, weight by probability
        """
        results = []

        for regime, prob in regime_probabilities.items():
            params = self.get_regime_parameters(regime)
            paths = self.mc.simulate_gbm(**params)
            results.append({'regime': regime, 'prob': prob, 'paths': paths})

        # Weight results by regime probability
        weighted_var = sum([r['prob'] * self.calculate_var(r['paths']) for r in results])

        return weighted_var
```

---

## 11. Bayesian Inference

### Core Mathematical Formulas

#### Bayes' Theorem
```
P(H|E) = P(E|H) × P(H) / P(E)

Where:
- P(H|E) = Posterior (belief after evidence)
- P(E|H) = Likelihood (probability of evidence given hypothesis)
- P(H) = Prior (initial belief)
- P(E) = Marginal likelihood (normalizing constant)

Trading application:
P(Trend|Signal) = P(Signal|Trend) × P(Trend) / P(Signal)
```

#### Bayesian Update
```
Posterior = Likelihood × Prior / Evidence

After each observation:
P(θ|data) ∝ P(data|θ) × P(θ)

Sequential updating:
Prior_new = Posterior_old
```

#### Beta-Binomial Conjugate Prior (Win Rate Estimation)
```
Prior: Win_Rate ~ Beta(α, β)

After observing w wins and l losses:
Posterior: Win_Rate ~ Beta(α + w, β + l)

Expected win rate = (α + w) / (α + β + w + l)

Start with uniform: Beta(1, 1)
Informative: Beta(10, 10) → 50% win rate prior with 20 trades worth of confidence
```

#### Normal-Normal Conjugate (Return Estimation)
```
Prior: μ ~ N(μ_0, σ_0²)
Data: X ~ N(μ, σ²)

Posterior:
μ ~ N(μ_post, σ_post²)

Where:
μ_post = (σ²μ_0 + nσ_0²X̄) / (σ² + nσ_0²)
σ_post² = (σ² × σ_0²) / (σ² + nσ_0²)

n = number of observations
X̄ = sample mean
```

#### Credible Intervals
```
95% Credible Interval = range containing 95% of posterior probability

Different from confidence interval!
Interpretation: "95% probability true value is in this range"
```

#### Bayesian A/B Testing
```
Strategy A: Win_Rate_A ~ Beta(α_A, β_A)
Strategy B: Win_Rate_B ~ Beta(α_B, β_B)

P(A > B) = ∫∫ P(W_A > W_B) × P(W_A) × P(W_B) dW_A dW_B

Can sample from posteriors to estimate P(A > B)
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import beta as beta_function

class BayesianInference:
    def __init__(self):
        """Initialize Bayesian inference system"""
        self.prior_alpha = 1  # Beta prior for win rate
        self.prior_beta = 1

    def update_win_rate_belief(self, wins, losses, prior_alpha=None, prior_beta=None):
        """
        Update belief about win rate using Beta-Binomial conjugate

        Args:
            wins: Number of winning trades observed
            losses: Number of losing trades observed
            prior_alpha, prior_beta: Prior parameters (defaults to uniform)
        """
        if prior_alpha is None:
            prior_alpha = self.prior_alpha
        if prior_beta is None:
            prior_beta = self.prior_beta

        # Posterior parameters
        posterior_alpha = prior_alpha + wins
        posterior_beta = prior_beta + losses

        # Expected win rate
        expected_win_rate = posterior_alpha / (posterior_alpha + posterior_beta)

        # 95% credible interval
        ci_low = stats.beta.ppf(0.025, posterior_alpha, posterior_beta)
        ci_high = stats.beta.ppf(0.975, posterior_alpha, posterior_beta)

        # Variance
        variance = (posterior_alpha * posterior_beta) / \
                   ((posterior_alpha + posterior_beta)**2 * (posterior_alpha + posterior_beta + 1))

        return {
            'expected_win_rate': expected_win_rate,
            'credible_interval_95': (ci_low, ci_high),
            'variance': variance,
            'posterior_alpha': posterior_alpha,
            'posterior_beta': posterior_beta
        }

    def bayesian_ab_test(self, wins_a, losses_a, wins_b, losses_b):
        """
        Compare two strategies using Bayesian A/B test

        Args:
            wins_a, losses_a: Results for strategy A
            wins_b, losses_b: Results for strategy B
        """
        # Update beliefs for both strategies
        belief_a = self.update_win_rate_belief(wins_a, losses_a)
        belief_b = self.update_win_rate_belief(wins_b, losses_b)

        # Sample from posteriors
        num_samples = 100000
        samples_a = np.random.beta(belief_a['posterior_alpha'], belief_a['posterior_beta'], num_samples)
        samples_b = np.random.beta(belief_b['posterior_alpha'], belief_b['posterior_beta'], num_samples)

        # Probability that A > B
        prob_a_better = np.mean(samples_a > samples_b)

        # Expected lift
        expected_lift = np.mean(samples_a - samples_b)

        # Credible interval for lift
        lift_samples = samples_a - samples_b
        lift_ci_low = np.percentile(lift_samples, 2.5)
        lift_ci_high = np.percentile(lift_samples, 97.5)

        return {
            'prob_a_better': prob_a_better,
            'prob_b_better': 1 - prob_a_better,
            'expected_lift': expected_lift,
            'lift_credible_interval': (lift_ci_low, lift_ci_high),
            'belief_a': belief_a,
            'belief_b': belief_b
        }

    def update_return_belief(self, observations, prior_mean=0, prior_std=0.01, data_std=0.01):
        """
        Update belief about expected return using Normal-Normal conjugate

        Args:
            observations: Array of observed returns
            prior_mean: Prior belief about mean return
            prior_std: Uncertainty in prior
            data_std: Known standard deviation of returns
        """
        n = len(observations)
        sample_mean = np.mean(observations)

        # Posterior parameters
        posterior_variance = 1 / (1/prior_std**2 + n/data_std**2)
        posterior_std = np.sqrt(posterior_variance)

        posterior_mean = posterior_variance * (prior_mean/prior_std**2 + n*sample_mean/data_std**2)

        # 95% credible interval
        ci_low = posterior_mean - 1.96 * posterior_std
        ci_high = posterior_mean + 1.96 * posterior_std

        return {
            'posterior_mean': posterior_mean,
            'posterior_std': posterior_std,
            'credible_interval_95': (ci_low, ci_high),
            'num_observations': n
        }

    def calculate_bayes_factor(self, wins, losses, null_win_rate=0.5):
        """
        Calculate Bayes Factor for hypothesis testing

        H0: Win rate = null_win_rate (e.g., 0.5 = no edge)
        H1: Win rate ≠ null_win_rate

        BF > 3: Moderate evidence for H1
        BF > 10: Strong evidence for H1
        BF > 100: Decisive evidence for H1
        """
        # Under H0 (null hypothesis)
        likelihood_h0 = stats.binom.pmf(wins, wins + losses, null_win_rate)

        # Under H1 (alternative with uniform prior)
        # Marginal likelihood = integral of likelihood × prior
        # For Beta(1,1) prior and binomial likelihood, this is known
        marginal_likelihood_h1 = 1 / (wins + losses + 1)

        # Bayes Factor
        bf = marginal_likelihood_h1 / likelihood_h0

        # Interpretation
        if bf > 100:
            interpretation = 'decisive_evidence_for_edge'
        elif bf > 10:
            interpretation = 'strong_evidence_for_edge'
        elif bf > 3:
            interpretation = 'moderate_evidence_for_edge'
        elif bf > 1:
            interpretation = 'weak_evidence_for_edge'
        elif bf > 0.33:
            interpretation = 'inconclusive'
        else:
            interpretation = 'evidence_against_edge'

        return {
            'bayes_factor': bf,
            'interpretation': interpretation,
            'log_bf': np.log10(bf)
        }

    def sequential_probability_ratio(self, wins, losses, target_win_rate, null_win_rate=0.5,
                                    alpha=0.05, beta=0.05):
        """
        Sequential Probability Ratio Test (SPRT)

        Decide if strategy has edge without waiting for fixed sample size

        Args:
            wins, losses: Current results
            target_win_rate: Alternative hypothesis win rate
            null_win_rate: Null hypothesis win rate
            alpha: Type I error rate
            beta: Type II error rate
        """
        n = wins + losses

        if n == 0:
            return {'decision': 'continue', 'log_lr': 0}

        # Log likelihood ratio
        log_lr = wins * np.log(target_win_rate / null_win_rate) + \
                 losses * np.log((1 - target_win_rate) / (1 - null_win_rate))

        # Decision boundaries
        upper_bound = np.log((1 - beta) / alpha)
        lower_bound = np.log(beta / (1 - alpha))

        # Decision
        if log_lr >= upper_bound:
            decision = 'accept_alternative'  # Strategy has edge
        elif log_lr <= lower_bound:
            decision = 'accept_null'  # No edge
        else:
            decision = 'continue'  # Need more data

        return {
            'decision': decision,
            'log_lr': log_lr,
            'upper_bound': upper_bound,
            'lower_bound': lower_bound,
            'trades_so_far': n
        }

# Usage Example
bayes = BayesianInference()

# Scenario 1: Update win rate belief
wins = 55
losses = 45

belief = bayes.update_win_rate_belief(wins, losses)
print(f"Expected win rate: {belief['expected_win_rate']:.2%}")
print(f"95% Credible Interval: {belief['credible_interval_95'][0]:.2%} - {belief['credible_interval_95'][1]:.2%}")

# Scenario 2: A/B test two strategies
strategy_a = {'wins': 58, 'losses': 42}  # 58% win rate
strategy_b = {'wins': 52, 'losses': 48}  # 52% win rate

ab_test = bayes.bayesian_ab_test(
    strategy_a['wins'], strategy_a['losses'],
    strategy_b['wins'], strategy_b['losses']
)

print(f"\nA/B Test Results:")
print(f"P(A better than B): {ab_test['prob_a_better']:.2%}")
print(f"Expected lift: {ab_test['expected_lift']:.2%}")
print(f"Lift CI: {ab_test['lift_credible_interval'][0]:.2%} - {ab_test['lift_credible_interval'][1]:.2%}")

# Scenario 3: Update return belief
daily_returns = np.random.randn(60) * 0.01 + 0.0005  # Slightly positive returns

return_belief = bayes.update_return_belief(
    daily_returns,
    prior_mean=0.0,
    prior_std=0.01,
    data_std=0.01
)

print(f"\nReturn Belief:")
print(f"Expected daily return: {return_belief['posterior_mean']:.4%}")
print(f"95% CI: {return_belief['credible_interval_95'][0]:.4%} - {return_belief['credible_interval_95'][1]:.4%}")

# Scenario 4: Bayes Factor (test for edge)
bf = bayes.calculate_bayes_factor(wins=55, losses=45, null_win_rate=0.5)
print(f"\nBayes Factor: {bf['bayes_factor']:.2f}")
print(f"Interpretation: {bf['interpretation']}")

# Scenario 5: Sequential testing
sprt = bayes.sequential_probability_ratio(
    wins=30,
    losses=20,
    target_win_rate=0.6,
    null_win_rate=0.5
)

print(f"\nSequential Test:")
print(f"Decision: {sprt['decision']}")
print(f"Log LR: {sprt['log_lr']:.2f}")
print(f"Trades so far: {sprt['trades_so_far']}")
```

### When to Use

**Optimal Conditions:**
- Updating beliefs with new data
- A/B testing strategies
- Small sample sizes (Bayesian works better than frequentist)
- Sequential testing (don't wait for fixed N)
- Incorporating prior knowledge

**Avoid When:**
- Need exact p-values (regulatory)
- No prior knowledge (use non-informative priors)
- Computational constraints (MCMC can be slow)

### Strengths and Weaknesses

**Strengths:**
- Updates beliefs continuously
- Incorporates prior knowledge
- Provides probability of hypothesis (intuitive)
- Works with small samples
- No p-hacking problem

**Weaknesses:**
- Requires prior specification (subjective)
- Can be computationally intensive
- Less familiar to many traders
- "Wrong" prior can bias results

### Real-World Examples

**Quantitative Hedge Funds:**
- Bayesian portfolio optimization
- Update strategy parameters as market evolves
- A/B test algo variations
- Stop underperforming strategies faster (SPRT)

**Professional Example:**
```
New Trading Strategy Evaluation

Traditional approach:
- Wait for 300 trades
- Calculate p-value
- If p < 0.05, deploy strategy
- Takes 6+ months

Bayesian SPRT approach:
- Start with prior: Win_Rate ~ Beta(5, 5) (50% with moderate confidence)
- After 20 trades: 13 wins, 7 losses
- Update: Win_Rate ~ Beta(18, 12)
- Expected: 60% win rate
- 95% CI: [41%, 77%]
- SPRT decision: Continue (need more data)

- After 50 trades: 32 wins, 18 losses
- Update: Win_Rate ~ Beta(37, 23)
- Expected: 61.7% win rate
- 95% CI: [51%, 72%]
- SPRT decision: Accept alternative (has edge!)
- Deploy strategy after 50 trades instead of 300

Result: Faster deployment, more profits captured
```

### Integration with AI:

```python
class AIBayesian:
    def __init__(self, base_bayes):
        self.bayes = base_bayes
        self.ml_model = None

    def ml_informed_prior(self, strategy_features):
        """
        Use ML to set informed prior based on strategy characteristics

        Similar strategies → use their performance as prior
        """
        similar_strategies = self.find_similar_strategies(strategy_features)

        # Aggregate historical performance
        avg_win_rate = np.mean([s['win_rate'] for s in similar_strategies])

        # Convert to Beta parameters
        # If avg = 0.55 with 100 trades worth of confidence
        prior_alpha = avg_win_rate * 100
        prior_beta = (1 - avg_win_rate) * 100

        return {'prior_alpha': prior_alpha, 'prior_beta': prior_beta}

    def regime_conditional_bayes(self, current_regime):
        """
        Different priors for different market regimes
        """
        regime_priors = {
            'bull': {'prior_alpha': 6, 'prior_beta': 4},  # 60% prior
            'bear': {'prior_alpha': 4, 'prior_beta': 6},  # 40% prior
            'sideways': {'prior_alpha': 5, 'prior_beta': 5}  # 50% prior
        }

        return regime_priors.get(current_regime, {'prior_alpha': 1, 'prior_beta': 1})
```

---

## 12. Information Theory

### Core Mathematical Formulas

#### Entropy (Uncertainty)
```
H(X) = -Σ P(x_i) × log_2(P(x_i))

Where:
- H(X) = entropy in bits
- P(x_i) = probability of outcome i

High entropy → High uncertainty
Low entropy → Low uncertainty (predictable)

Market application:
- Trending market: Low entropy (predictable direction)
- Choppy market: High entropy (unpredictable)
```

#### Mutual Information (Signal Quality)
```
I(X;Y) = H(X) + H(Y) - H(X,Y)

Or:
I(X;Y) = Σ Σ P(x,y) × log_2(P(x,y) / (P(x) × P(y)))

Measures how much knowing Y reduces uncertainty about X

Trading: How much does indicator reduce uncertainty about future price?

I(Indicator; Future_Return) → Higher = better signal
```

#### Transfer Entropy (Causality)
```
TE_{X→Y} = H(Y_t | Y_{t-1}) - H(Y_t | Y_{t-1}, X_{t-1})

Measures information flow from X to Y

Detect leading indicators:
TE_{VIX→SPX} > 0 → VIX leads SPX
```

#### Shannon's Information Content
```
Information_content = -log_2(P(event))

Rare event → High information content
Common event → Low information content

Trading: Unusual volume spike = high information content
```

#### Signal-to-Noise Ratio (SNR)
```
SNR = Power_signal / Power_noise

Or in dB:
SNR_dB = 10 × log_10(Signal²/ Noise²)

Trading application:
Signal = predictable component (edge)
Noise = random component (market noise)

High SNR → Reliable signal
Low SNR → Noisy, unreliable
```

#### Channel Capacity (Maximum Information Rate)
```
C = B × log_2(1 + SNR)

Where:
- C = channel capacity (bits/second)
- B = bandwidth (sampling rate)

Trading: Maximum rate at which you can extract information from market
```

### Practical Implementation Steps

```python
import numpy as np
import pandas as pd
from scipy.stats import entropy as scipy_entropy

class InformationTheory:
    def __init__(self):
        """Initialize information theory calculator"""
        pass

    def calculate_entropy(self, probabilities):
        """
        Calculate Shannon entropy

        Args:
            probabilities: Array of probabilities (must sum to 1)
        """
        # Remove zeros to avoid log(0)
        probs = np.array(probabilities)
        probs = probs[probs > 0]

        # Entropy in bits
        entropy = -np.sum(probs * np.log2(probs))

        # Normalized entropy (0-1)
        max_entropy = np.log2(len(probs))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

        return {
            'entropy': entropy,
            'normalized_entropy': normalized_entropy,
            'max_entropy': max_entropy
        }

    def calculate_mutual_information(self, x, y, bins=10):
        """
        Calculate mutual information between two variables

        Args:
            x, y: Time series data
            bins: Number of bins for discretization
        """
        # Discretize continuous data
        x_binned = pd.cut(x, bins=bins, labels=False)
        y_binned = pd.cut(y, bins=bins, labels=False)

        # Joint probability distribution
        joint_hist = np.histogram2d(x_binned, y_binned, bins=bins)[0]
        joint_prob = joint_hist / np.sum(joint_hist)

        # Marginal probabilities
        x_prob = np.sum(joint_prob, axis=1)
        y_prob = np.sum(joint_prob, axis=0)

        # Mutual information
        mi = 0
        for i in range(bins):
            for j in range(bins):
                if joint_prob[i, j] > 0:
                    mi += joint_prob[i, j] * np.log2(
                        joint_prob[i, j] / (x_prob[i] * y_prob[j] + 1e-10)
                    )

        # Normalized MI (0-1)
        h_x = self.calculate_entropy(x_prob)['entropy']
        h_y = self.calculate_entropy(y_prob)['entropy']
        normalized_mi = mi / min(h_x, h_y) if min(h_x, h_y) > 0 else 0

        return {
            'mutual_information': mi,
            'normalized_mi': normalized_mi,
            'entropy_x': h_x,
            'entropy_y': h_y
        }

    def calculate_transfer_entropy(self, source, target, lag=1):
        """
        Calculate transfer entropy (information flow from source to target)

        Args:
            source: Source time series
            target: Target time series
            lag: Time lag
        """
        # Simple approximation using conditional entropy
        # TE = H(target_t | target_{t-lag}) - H(target_t | target_{t-lag}, source_{t-lag})

        n = len(target)

        # Target current and lagged
        target_curr = target[lag:]
        target_lag = target[:-lag]
        source_lag = source[:-lag]

        # Discretize
        bins = 10
        target_curr_bin = pd.cut(target_curr, bins=bins, labels=False)
        target_lag_bin = pd.cut(target_lag, bins=bins, labels=False)
        source_lag_bin = pd.cut(source_lag, bins=bins, labels=False)

        # Calculate entropies
        # H(target_t | target_{t-lag})
        joint_tt = np.histogram2d(target_curr_bin, target_lag_bin, bins=bins)[0]
        joint_tt_prob = joint_tt / np.sum(joint_tt)

        h_target_cond = 0
        for i in range(bins):
            p_target_lag = np.sum(joint_tt_prob[:, i])
            if p_target_lag > 0:
                for j in range(bins):
                    if joint_tt_prob[j, i] > 0:
                        h_target_cond -= joint_tt_prob[j, i] * np.log2(
                            joint_tt_prob[j, i] / p_target_lag
                        )

        # H(target_t | target_{t-lag}, source_{t-lag})
        # Simplified approximation using 2D approach
        joint_tts = np.zeros((bins, bins))
        for i in range(len(target_curr_bin)):
            if not (np.isnan(target_curr_bin[i]) or np.isnan(target_lag_bin[i])):
                idx = int(target_lag_bin[i]) + int(source_lag_bin[i]) * bins // 2
                if idx < bins:
                    joint_tts[int(target_curr_bin[i]), idx] += 1

        joint_tts_prob = joint_tts / np.sum(joint_tts)

        h_target_cond_source = 0
        for i in range(bins):
            p_cond = np.sum(joint_tts_prob[:, i])
            if p_cond > 0:
                for j in range(bins):
                    if joint_tts_prob[j, i] > 0:
                        h_target_cond_source -= joint_tts_prob[j, i] * np.log2(
                            joint_tts_prob[j, i] / p_cond
                        )

        # Transfer entropy
        te = h_target_cond - h_target_cond_source

        return {
            'transfer_entropy': te,
            'interpretation': 'positive means source influences target' if te > 0 else 'no significant influence'
        }

    def calculate_information_content(self, probability):
        """
        Calculate information content of an event

        Args:
            probability: Probability of event occurring
        """
        if probability <= 0 or probability > 1:
            return {'information_content': float('inf')}

        # Information content in bits
        ic = -np.log2(probability)

        # Interpretation
        if ic > 10:
            interpretation = 'extremely_rare_event'
        elif ic > 5:
            interpretation = 'rare_event'
        elif ic > 2:
            interpretation = 'uncommon_event'
        else:
            interpretation = 'common_event'

        return {
            'information_content': ic,
            'interpretation': interpretation,
            'probability': probability
        }

    def calculate_snr(self, signal, noise):
        """
        Calculate Signal-to-Noise Ratio

        Args:
            signal: Signal component (e.g., trend, edge)
            noise: Noise component (e.g., random fluctuations)
        """
        # Power
        signal_power = np.mean(signal ** 2)
        noise_power = np.mean(noise ** 2)

        if noise_power == 0:
            snr = float('inf')
            snr_db = float('inf')
        else:
            # SNR
            snr = signal_power / noise_power

            # SNR in dB
            snr_db = 10 * np.log10(snr)

        # Interpretation
        if snr_db > 20:
            quality = 'excellent'
        elif snr_db > 10:
            quality = 'good'
        elif snr_db > 3:
            quality = 'fair'
        else:
            quality = 'poor'

        return {
            'snr': snr,
            'snr_db': snr_db,
            'signal_power': signal_power,
            'noise_power': noise_power,
            'quality': quality
        }

    def market_entropy_regime(self, returns, window=20):
        """
        Calculate rolling entropy to detect market regimes

        High entropy → Unpredictable, choppy
        Low entropy → Predictable, trending
        """
        entropies = []

        for i in range(window, len(returns)):
            window_returns = returns[i-window:i]

            # Discretize into up/down/flat
            bins = [-np.inf, -0.001, 0.001, np.inf]
            discretized = np.digitize(window_returns, bins)

            # Probability distribution
            unique, counts = np.unique(discretized, return_counts=True)
            probs = counts / len(discretized)

            # Entropy
            ent = self.calculate_entropy(probs)['normalized_entropy']
            entropies.append(ent)

        entropies = np.array(entropies)

        # Current regime
        current_entropy = entropies[-1] if len(entropies) > 0 else 0.5

        if current_entropy > 0.9:
            regime = 'high_entropy_choppy'
        elif current_entropy < 0.6:
            regime = 'low_entropy_trending'
        else:
            regime = 'moderate_entropy'

        return {
            'current_entropy': current_entropy,
            'regime': regime,
            'entropy_series': entropies
        }

# Usage Example
info_theory = InformationTheory()

# Entropy
probs = [0.5, 0.3, 0.2]  # Three possible outcomes
entropy_result = info_theory.calculate_entropy(probs)
print(f"Entropy: {entropy_result['entropy']:.2f} bits")
print(f"Normalized: {entropy_result['normalized_entropy']:.2%}")

# Mutual Information
np.random.seed(42)
indicator = np.random.randn(1000)
returns = 0.5 * indicator + np.random.randn(1000) * 0.5  # Indicator partially predicts returns

mi = info_theory.calculate_mutual_information(indicator, returns)
print(f"\nMutual Information: {mi['mutual_information']:.3f} bits")
print(f"Normalized MI: {mi['normalized_mi']:.2%}")

# Transfer Entropy
vix = np.random.randn(500)
spy = np.roll(vix, 1) * -0.3 + np.random.randn(500) * 0.7  # VIX leads SPY inversely

te = info_theory.calculate_transfer_entropy(vix, spy, lag=1)
print(f"\nTransfer Entropy (VIX → SPY): {te['transfer_entropy']:.3f}")
print(f"Interpretation: {te['interpretation']}")

# Information Content
rare_event_prob = 0.01  # 1% probability
ic = info_theory.calculate_information_content(rare_event_prob)
print(f"\nInformation Content: {ic['information_content']:.2f} bits")
print(f"Interpretation: {ic['interpretation']}")

# SNR
trend = np.linspace(0, 10, 100)  # Clean trend
noise_component = np.random.randn(100) * 2
signal_with_noise = trend + noise_component

snr = info_theory.calculate_snr(trend, noise_component)
print(f"\nSNR: {snr['snr']:.2f}")
print(f"SNR (dB): {snr['snr_db']:.2f} dB")
print(f"Quality: {snr['quality']}")

# Market Regime Detection
market_returns = np.random.randn(500) * 0.01
entropy_regime = info_theory.market_entropy_regime(market_returns)
print(f"\nCurrent Entropy: {entropy_regime['current_entropy']:.2f}")
print(f"Market Regime: {entropy_regime['regime']}")
```

### When to Use

**Optimal Conditions:**
- Indicator evaluation (mutual information)
- Regime detection (entropy)
- Lead-lag relationships (transfer entropy)
- Signal quality assessment (SNR)
- Detecting rare events (information content)

**Avoid When:**
- Need simple, interpretable metrics
- Small sample sizes (entropy estimates unreliable)
- Real-time ultra-low-latency (computationally intensive)

### Strengths and Weaknesses

**Strengths:**
- Quantifies predictability objectively
- Model-free (no assumptions about distributions)
- Detects non-linear relationships
- Universal framework

**Weaknesses:**
- Requires discretization (information loss)
- Sample size dependent
- Computationally intensive
- Less intuitive than traditional metrics

### Real-World Examples

**Renaissance Technologies:**
- Uses information theory extensively
- Evaluate signal quality via mutual information
- Entropy-based regime detection
- Filter noise from signal

**Professional Application:**
```
Indicator Evaluation

Indicator A (RSI):
- MI with next-day return: 0.12 bits
- Interpretation: Low predictive power

Indicator B (Order flow imbalance):
- MI with next-5-min return: 0.45 bits
- Interpretation: Moderate predictive power

Indicator C (Volume profile POC distance):
- MI with next-hour return: 0.68 bits
- Interpretation: High predictive power

Decision: Weight indicators by MI in ensemble
- RSI: 15% weight
- OFI: 35% weight
- POC distance: 50% weight

Result: Ensemble SNR = 8.2 dB (good quality)
```

### Integration with AI:

```python
class AIInformationTheory:
    def __init__(self, base_it):
        self.it = base_it
        self.ml_model = None

    def feature_selection_by_mi(self, features, target):
        """
        Select features with highest mutual information with target
        """
        mi_scores = []

        for feature in features:
            mi = self.it.calculate_mutual_information(feature, target)
            mi_scores.append(mi['mutual_information'])

        # Select top features
        top_indices = np.argsort(mi_scores)[-10:]  # Top 10 features

        return {
            'selected_features': top_indices,
            'mi_scores': mi_scores
        }

    def adaptive_signal_filtering(self, signal, noise_estimate):
        """
        Adjust signal usage based on SNR
        """
        snr = self.it.calculate_snr(signal, noise_estimate)

        if snr['snr_db'] > 15:
            confidence = 1.0  # Use signal fully
        elif snr['snr_db'] > 5:
            confidence = 0.5  # Use with caution
        else:
            confidence = 0.1  # Mostly ignore

        return confidence
```

---

## Summary Table: When to Use Each Model

| Model | Best For | Avoid When | Key Metric |
|-------|----------|------------|------------|
| **Kelly Criterion** | Position sizing, maximizing growth | Small sample (<100 trades), uncertain edge | Optimal f* |
| **Poker Math** | EV calculation, bankroll mgmt | Continuous distributions | Expected Value |
| **Casino Theory** | High-frequency, large sample | Low frequency trading | House Edge % |
| **Market Making** | Liquidity provision, spread capture | Trending markets, low tech | Spread / Inventory |
| **Stat Arb** | Pairs trading, mean reversion | Trending, breaking cointegration | Z-score, Half-life |
| **Volatility** | Breakouts, position sizing | Strong trends (BB fails) | ATR, Bandwidth |
| **Momentum** | Trend following | Range-bound markets | ADX, RSI |
| **Order Flow** | Intraday, scalping | Position trading, opaque markets | Delta, VPIN |
| **Risk Mgmt** | Always (foundational) | Never | Portfolio Heat, VaR |
| **Monte Carlo** | Validation, risk assessment | Real-time decisions | Confidence Intervals |
| **Bayesian** | Updating beliefs, A/B testing | Need exact p-values | Posterior Probability |
| **Information Theory** | Indicator evaluation, regime detection | Small samples | Mutual Info, Entropy |

---

## Integration Checklist for AI Trading System

✅ **Position Sizing**: Kelly + Risk Management
✅ **Entry Logic**: Momentum + Volatility + Order Flow
✅ **Risk Control**: Bookkeeper + Monte Carlo VaR
✅ **Strategy Validation**: Monte Carlo + Bayesian A/B
✅ **Regime Detection**: Information Theory Entropy
✅ **Indicator Selection**: Mutual Information ranking
✅ **Edge Verification**: Poker Math EV + Bayes Factor
✅ **Portfolio Construction**: Correlation-adjusted risk
✅ **Performance Monitoring**: Sequential Bayesian updates

---

*End of 12 Trading Probability Models Comprehensive Guide*

