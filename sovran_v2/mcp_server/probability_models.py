"""
Sovereign Probability Models — All 12 LIVE
==========================================
Every model runs on every trade decision. The AI (LLM) synthesizes all signals.
No shadow mode. No backtesting only. These are live inputs to every trade.

Each model returns:
  {
    "signal": "LONG" | "SHORT" | "NEUTRAL",
    "conviction": 0-100,
    "reasoning": str,
    "raw": dict  # model-specific raw values for LLM inspection
  }
"""
import math
import statistics
from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────
# 1. KELLY CRITERION (Full + Fractional)
# ─────────────────────────────────────────────────────────────

def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float,
                    fraction: float = 0.25) -> Dict[str, Any]:
    """
    Full Kelly: f* = (p*b - q) / b  where b = avg_win/avg_loss
    Fractional Kelly: use fraction=0.25 (quarter-Kelly) to reduce variance.
    Returns optimal position size as % of bankroll AND signal conviction.
    """
    if avg_loss == 0:
        return {"signal": "NEUTRAL", "conviction": 0, "reasoning": "No loss data", "raw": {}}

    b = avg_win / avg_loss  # win/loss ratio
    p = win_rate
    q = 1 - p
    full_kelly = (p * b - q) / b if b > 0 else 0
    frac_kelly = full_kelly * fraction

    # Positive Kelly = edge exists → trade direction depends on caller's signal
    # Negative Kelly = no edge → stay out
    if full_kelly > 0.10:
        conviction = min(100, int(full_kelly * 250))  # scale to 0-100
        signal = "LONG"  # direction neutral — caller supplies direction context
        reasoning = f"Strong edge: full_kelly={full_kelly:.3f}, fractional={frac_kelly:.3f} ({fraction*100:.0f}%). Bet {frac_kelly*100:.1f}% bankroll."
    elif full_kelly > 0:
        conviction = int(full_kelly * 150)
        signal = "NEUTRAL"
        reasoning = f"Marginal edge: full_kelly={full_kelly:.3f}. Proceed cautiously."
    else:
        conviction = 0
        signal = "NEUTRAL"
        reasoning = f"No edge (kelly={full_kelly:.3f}). Win rate {win_rate:.1%} too low vs ratio {b:.2f}."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {
            "full_kelly": round(full_kelly, 4),
            "fractional_kelly": round(frac_kelly, 4),
            "win_rate": win_rate,
            "win_loss_ratio": round(b, 3),
            "fraction_used": fraction
        }
    }


# ─────────────────────────────────────────────────────────────
# 2. POKER EV (Expected Value)
# ─────────────────────────────────────────────────────────────

def poker_ev(win_prob: float, pot_size: float, call_size: float,
             outs: int = 0, streets_remaining: int = 0) -> Dict[str, Any]:
    """
    Poker-style pot odds + implied odds EV calculation.
    pot_size = potential profit (TP in $)
    call_size = risk (SL in $)
    outs = # of favorable scenarios (like outs in poker, 0 if not applicable)
    """
    if call_size == 0:
        return {"signal": "NEUTRAL", "conviction": 0, "reasoning": "Zero risk", "raw": {}}

    # Pot odds needed to break even
    pot_odds = call_size / (pot_size + call_size)

    # If outs provided, calculate equity (rule of 2/4)
    if outs > 0 and streets_remaining > 0:
        equity = min(outs * (4 if streets_remaining >= 2 else 2) / 100, 0.99)
        win_prob = max(win_prob, equity)  # use higher of input or outs-based

    ev = (win_prob * pot_size) - ((1 - win_prob) * call_size)
    ev_ratio = ev / call_size  # EV per dollar risked

    if ev > 0 and win_prob > pot_odds:
        conviction = min(100, int(50 + ev_ratio * 30))
        signal = "LONG"
        reasoning = f"+EV trade: EV=${ev:.2f}, win_prob={win_prob:.1%} > pot_odds={pot_odds:.1%}. EV/risk ratio={ev_ratio:.2f}."
    elif ev > 0:
        conviction = 30
        signal = "NEUTRAL"
        reasoning = f"Marginal EV=${ev:.2f} but pot odds tight."
    else:
        conviction = 0
        signal = "NEUTRAL"
        reasoning = f"Negative EV=${ev:.2f}. Skip or wait."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"ev": round(ev, 2), "pot_odds": round(pot_odds, 3),
                "win_prob": win_prob, "ev_ratio": round(ev_ratio, 3)}
    }


# ─────────────────────────────────────────────────────────────
# 3. CASINO EDGE THEORY (House Edge / Player Advantage)
# ─────────────────────────────────────────────────────────────

def casino_edge(win_rate: float, rr_ratio: float,
                num_trades: int = 100) -> Dict[str, Any]:
    """
    Models trading like a casino: do we have a structural edge?
    Edge = win_rate * rr_ratio - (1 - win_rate)
    Law of large numbers: edge compounds over many trades.
    """
    edge = win_rate * rr_ratio - (1 - win_rate)
    edge_pct = edge * 100

    # Expected profit per trade normalized
    expected_per_trade = edge  # in units of avg_loss

    # Confidence that edge is real (binomial approximation)
    # N=num_trades, p=win_rate: std = sqrt(p*(1-p)/N)
    if num_trades > 0:
        std = math.sqrt(win_rate * (1 - win_rate) / num_trades)
        z_score = edge / std if std > 0 else 0
        statistical_confidence = min(0.99, 0.5 + 0.5 * math.erf(z_score / math.sqrt(2)))
    else:
        statistical_confidence = 0.5

    if edge > 0.05 and statistical_confidence > 0.7:
        conviction = min(100, int(50 + edge_pct * 5 + statistical_confidence * 20))
        signal = "LONG"
        reasoning = f"Strong house edge: {edge_pct:.1f}%, Z={z_score:.2f}, {statistical_confidence:.0%} confident over {num_trades} trades."
    elif edge > 0:
        conviction = int(30 + edge_pct * 3)
        signal = "NEUTRAL"
        reasoning = f"Thin edge {edge_pct:.1f}%: trade carefully, build sample."
    else:
        conviction = 0
        signal = "NEUTRAL"
        reasoning = f"Negative edge {edge_pct:.1f}%. System working against us."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"edge": round(edge, 4), "rr_ratio": rr_ratio, "win_rate": win_rate,
                "z_score": round(z_score if num_trades > 0 else 0, 2),
                "statistical_confidence": round(statistical_confidence, 3)}
    }


# ─────────────────────────────────────────────────────────────
# 4. MARKET MAKING (Bid-Ask Spread + Inventory)
# ─────────────────────────────────────────────────────────────

def market_making(bid: float, ask: float, mid: float, last_price: float,
                  inventory_contracts: int = 0,
                  fair_value: Optional[float] = None) -> Dict[str, Any]:
    """
    Market making model: buy below fair value, sell above.
    Spread captures edge. Inventory skew adjusts bias.
    """
    spread = ask - bid
    spread_pct = spread / mid if mid > 0 else 0

    if fair_value is None:
        fair_value = mid

    distance_from_fv = last_price - fair_value
    distance_pct = distance_from_fv / fair_value if fair_value > 0 else 0

    # Inventory adjustment: if long too much, bias SHORT to reduce
    inventory_skew = -inventory_contracts * 0.1  # per contract held

    if distance_pct < -0.001:  # Price below FV → buy
        base_conviction = min(80, int(abs(distance_pct) * 10000))
        direction = "LONG"
        reasoning = f"Price ${last_price:.2f} is {abs(distance_pct)*100:.2f}% BELOW fair value ${fair_value:.2f}. Buy the discount."
    elif distance_pct > 0.001:  # Price above FV → sell
        base_conviction = min(80, int(distance_pct * 10000))
        direction = "SHORT"
        reasoning = f"Price ${last_price:.2f} is {distance_pct*100:.2f}% ABOVE fair value ${fair_value:.2f}. Sell the premium."
    else:
        base_conviction = 20
        direction = "NEUTRAL"
        reasoning = f"Price at fair value. Spread={spread:.2f} ({spread_pct*100:.3f}%). Wait for dislocation."

    # Apply inventory skew
    adjusted_conviction = max(0, min(100, int(base_conviction + inventory_skew * 10)))

    return {
        "signal": direction,
        "conviction": adjusted_conviction,
        "reasoning": reasoning,
        "raw": {"spread": round(spread, 4), "spread_pct": round(spread_pct * 100, 3),
                "fair_value": fair_value, "distance_pct": round(distance_pct * 100, 3),
                "inventory_contracts": inventory_contracts}
    }


# ─────────────────────────────────────────────────────────────
# 5. STATISTICAL ARBITRAGE (Mean Reversion / Z-Score)
# ─────────────────────────────────────────────────────────────

def statistical_arbitrage(prices: List[float], lookback: int = 20) -> Dict[str, Any]:
    """
    Z-score mean reversion model.
    |Z| > 2: strong reversion signal
    |Z| > 1: weak signal
    Z direction: positive = overbought (SHORT), negative = oversold (LONG)
    """
    if len(prices) < max(3, lookback // 2):
        return {"signal": "NEUTRAL", "conviction": 0,
                "reasoning": "Insufficient price history for stat arb.", "raw": {}}

    window = prices[-lookback:] if len(prices) >= lookback else prices
    mean = statistics.mean(window)
    std = statistics.stdev(window) if len(window) > 1 else 1e-9

    current = prices[-1]
    z_score = (current - mean) / std if std > 0 else 0

    # Half-life estimate (Ornstein-Uhlenbeck proxy)
    # Simpler: how many bars to revert historically
    if abs(z_score) > 2.5:
        conviction = min(90, int(abs(z_score) * 25))
        signal = "SHORT" if z_score > 0 else "LONG"
        reasoning = f"Extreme Z={z_score:.2f}: {'overbought' if z_score > 0 else 'oversold'}. Mean=${mean:.2f}, STD={std:.4f}. Strong reversion expected."
    elif abs(z_score) > 1.5:
        conviction = int(abs(z_score) * 20)
        signal = "SHORT" if z_score > 0 else "LONG"
        reasoning = f"Z={z_score:.2f}: moderate {'overbought' if z_score > 0 else 'oversold'}. Mean reversion likely."
    elif abs(z_score) > 0.5:
        conviction = 20
        signal = "NEUTRAL"
        reasoning = f"Z={z_score:.2f}: mild deviation. Trending or low conviction."
    else:
        conviction = 10
        signal = "NEUTRAL"
        reasoning = f"Z={z_score:.2f}: at mean, no stat arb opportunity."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"z_score": round(z_score, 3), "mean": round(mean, 4),
                "std": round(std, 4), "current": current, "lookback": len(window)}
    }


# ─────────────────────────────────────────────────────────────
# 6. VOLATILITY MODEL (ATR + Regime + Position Sizing)
# ─────────────────────────────────────────────────────────────

def volatility_model(atr_ticks: float, avg_atr_ticks: float,
                     vix_equiv: Optional[float] = None,
                     session_phase: str = "us_core") -> Dict[str, Any]:
    """
    ATR-based volatility regime detection.
    High ATR relative to average → wider stops, smaller size, but better breakout signals.
    Low ATR → tight stops, mean reversion preferred.
    """
    if avg_atr_ticks == 0:
        avg_atr_ticks = atr_ticks

    vol_ratio = atr_ticks / avg_atr_ticks if avg_atr_ticks > 0 else 1.0

    # Phase multiplier
    phase_mult = {"us_open": 1.0, "us_core": 1.2, "us_close": 0.9}.get(session_phase, 1.0)

    # VIX context if available
    vix_note = ""
    if vix_equiv is not None:
        if vix_equiv > 25:
            vix_note = f" VIX={vix_equiv:.1f} (elevated — widen stops 20%)."
        elif vix_equiv < 15:
            vix_note = f" VIX={vix_equiv:.1f} (calm — tight stops valid)."

    if vol_ratio > 1.5:
        signal = "NEUTRAL"  # Too volatile for size; wait for direction
        conviction = 40
        reasoning = f"HIGH vol: ATR={atr_ticks:.1f} vs avg={avg_atr_ticks:.1f} ({vol_ratio:.2f}x). Widen stops. Reduce size. Wait for momentum break.{vix_note}"
    elif vol_ratio > 0.8:
        signal = "LONG"  # Normal vol — conditions good
        conviction = int(55 * phase_mult)
        reasoning = f"NORMAL vol: ATR={atr_ticks:.1f} ({vol_ratio:.2f}x avg). Good conditions. Phase multiplier={phase_mult}.{vix_note}"
    else:
        signal = "NEUTRAL"
        conviction = 35
        reasoning = f"LOW vol: ATR={atr_ticks:.1f} ({vol_ratio:.2f}x avg). Mean reversion preferred. Breakouts unlikely.{vix_note}"

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"vol_ratio": round(vol_ratio, 3), "atr_ticks": atr_ticks,
                "avg_atr_ticks": avg_atr_ticks, "phase_mult": phase_mult,
                "vix_equiv": vix_equiv}
    }


# ─────────────────────────────────────────────────────────────
# 7. MOMENTUM MODEL (Price Rate of Change + Trend Strength)
# ─────────────────────────────────────────────────────────────

def momentum_model(prices: List[float], fast_period: int = 5,
                   slow_period: int = 20,
                   volume_profile: Optional[List[float]] = None) -> Dict[str, Any]:
    """
    Dual-period momentum: fast MA vs slow MA + rate of change.
    Volume confirmation optional.
    """
    if len(prices) < slow_period:
        # Use what we have
        if len(prices) < 3:
            return {"signal": "NEUTRAL", "conviction": 0,
                    "reasoning": "Need more price history.", "raw": {}}
        slow_period = len(prices)
        fast_period = max(2, len(prices) // 4)

    fast_ma = statistics.mean(prices[-fast_period:])
    slow_ma = statistics.mean(prices[-slow_period:])

    current = prices[-1]
    roc = (current - prices[-slow_period]) / prices[-slow_period] * 100 if prices[-slow_period] != 0 else 0

    # MA crossover signal
    ma_diff_pct = (fast_ma - slow_ma) / slow_ma * 100 if slow_ma != 0 else 0

    # Volume confirmation
    vol_confirm = ""
    vol_mult = 1.0
    if volume_profile and len(volume_profile) >= fast_period:
        avg_vol = statistics.mean(volume_profile[:-fast_period]) if len(volume_profile) > fast_period else 1
        recent_vol = statistics.mean(volume_profile[-fast_period:])
        if avg_vol > 0:
            vol_ratio_v = recent_vol / avg_vol
            if vol_ratio_v > 1.5:
                vol_confirm = f" Volume {vol_ratio_v:.1f}x avg: confirms momentum."
                vol_mult = 1.2
            elif vol_ratio_v < 0.7:
                vol_confirm = f" Volume {vol_ratio_v:.1f}x avg: weak conviction."
                vol_mult = 0.8

    if ma_diff_pct > 0.05 and roc > 0:
        conviction = min(90, int(abs(ma_diff_pct) * 200 * vol_mult + abs(roc) * 3))
        signal = "LONG"
        reasoning = f"Bullish momentum: fast_MA({fast_period})>{slow_period}_MA by {ma_diff_pct:.3f}%, ROC={roc:.2f}%.{vol_confirm}"
    elif ma_diff_pct < -0.05 and roc < 0:
        conviction = min(90, int(abs(ma_diff_pct) * 200 * vol_mult + abs(roc) * 3))
        signal = "SHORT"
        reasoning = f"Bearish momentum: fast_MA below slow by {abs(ma_diff_pct):.3f}%, ROC={roc:.2f}%.{vol_confirm}"
    else:
        conviction = 20
        signal = "NEUTRAL"
        reasoning = f"No clear momentum: MA diff={ma_diff_pct:.3f}%, ROC={roc:.2f}%. Ranging.{vol_confirm}"

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"fast_ma": round(fast_ma, 4), "slow_ma": round(slow_ma, 4),
                "ma_diff_pct": round(ma_diff_pct, 4), "roc_pct": round(roc, 3),
                "current": current}
    }


# ─────────────────────────────────────────────────────────────
# 8. ORDER FLOW MODEL (OFI + VPIN)
# ─────────────────────────────────────────────────────────────

def order_flow_model(ofi_z: float, vpin: float,
                     cumulative_delta: Optional[float] = None,
                     ask_depth: Optional[float] = None,
                     bid_depth: Optional[float] = None) -> Dict[str, Any]:
    """
    Order Flow Imbalance (OFI) + Volume-synchronized PIN (VPIN).
    OFI > 0: buyers dominating → bullish
    VPIN > 0.7: informed trading / institutional activity
    Delta: cumulative buy-sell volume
    """
    signals = []

    # OFI signal
    if abs(ofi_z) > 1.5:
        ofi_direction = "LONG" if ofi_z > 0 else "SHORT"
        ofi_conviction = min(85, int(abs(ofi_z) * 25))
        signals.append(("OFI", ofi_direction, ofi_conviction,
                        f"OFI Z={ofi_z:.2f} ({'buy' if ofi_z > 0 else 'sell'} pressure)"))
    elif abs(ofi_z) > 0.5:
        signals.append(("OFI", "NEUTRAL", 20,
                        f"OFI Z={ofi_z:.2f}: mild flow imbalance"))

    # VPIN signal
    if vpin > 0.75:
        signals.append(("VPIN", "NEUTRAL", 60,
                        f"VPIN={vpin:.3f}: HIGH informed trading. Follow direction carefully."))
    elif vpin > 0.55:
        signals.append(("VPIN", "NEUTRAL", 35,
                        f"VPIN={vpin:.3f}: moderate toxic flow. Exercise caution."))

    # Cumulative delta
    if cumulative_delta is not None:
        if cumulative_delta > 500:
            signals.append(("Delta", "LONG", 50, f"Cum delta +{cumulative_delta:.0f}: buyers in control"))
        elif cumulative_delta < -500:
            signals.append(("Delta", "SHORT", 50, f"Cum delta {cumulative_delta:.0f}: sellers in control"))

    # Order book imbalance
    if ask_depth and bid_depth and ask_depth > 0:
        imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
        if imbalance > 0.3:
            signals.append(("BookImbalance", "LONG", 45, f"Book {imbalance:.1%} bid-heavy: support below"))
        elif imbalance < -0.3:
            signals.append(("BookImbalance", "SHORT", 45, f"Book {abs(imbalance):.1%} ask-heavy: resistance above"))

    if not signals:
        return {"signal": "NEUTRAL", "conviction": 20,
                "reasoning": "No significant order flow signal.", "raw": {"ofi_z": ofi_z, "vpin": vpin}}

    # Aggregate signals
    long_signals = [(s, c, r) for _, s, c, r in signals if s == "LONG"]
    short_signals = [(s, c, r) for _, s, c, r in signals if s == "SHORT"]

    if long_signals and len(long_signals) >= len(short_signals):
        avg_conviction = int(statistics.mean([c for _, c, _ in long_signals]))
        reasoning = " | ".join([r for _, _, r in long_signals])
        return {"signal": "LONG", "conviction": avg_conviction, "reasoning": reasoning,
                "raw": {"ofi_z": ofi_z, "vpin": vpin, "cumulative_delta": cumulative_delta}}
    elif short_signals:
        avg_conviction = int(statistics.mean([c for _, c, _ in short_signals]))
        reasoning = " | ".join([r for _, _, r in short_signals])
        return {"signal": "SHORT", "conviction": avg_conviction, "reasoning": reasoning,
                "raw": {"ofi_z": ofi_z, "vpin": vpin, "cumulative_delta": cumulative_delta}}
    else:
        return {"signal": "NEUTRAL", "conviction": 30,
                "reasoning": " | ".join([r for _, _, r in signals]),
                "raw": {"ofi_z": ofi_z, "vpin": vpin}}


# ─────────────────────────────────────────────────────────────
# 9. BAYESIAN INFERENCE (Beta-Binomial Update)
# ─────────────────────────────────────────────────────────────

def bayesian_inference(wins: int, losses: int,
                       contract: str = "",
                       regime: str = "",
                       prior_alpha: float = 10.0,
                       prior_beta: float = 10.0) -> Dict[str, Any]:
    """
    Beta-Binomial Bayesian update of win probability.
    Prior: Beta(alpha, beta) — default 50% with 20 pseudo-observations.
    Posterior: Beta(alpha + wins, beta + losses)
    Returns posterior mean, 90% CI, and signal.
    """
    posterior_alpha = prior_alpha + wins
    posterior_beta = prior_beta + losses

    # Posterior mean
    post_mean = posterior_alpha / (posterior_alpha + posterior_beta)

    # Mode (MAP estimate)
    n = posterior_alpha + posterior_beta
    post_mode = (posterior_alpha - 1) / (n - 2) if n > 2 else post_mean

    # Credible interval (approximation using normal approximation)
    post_var = (posterior_alpha * posterior_beta) / ((n ** 2) * (n + 1))
    post_std = math.sqrt(post_var)
    ci_90_low = max(0, post_mean - 1.645 * post_std)
    ci_90_high = min(1, post_mean + 1.645 * post_std)

    # Effective sample size
    ess = wins + losses

    context = f"{contract} {regime}".strip() or "overall"

    if post_mean > 0.60 and ess >= 5:
        conviction = min(90, int((post_mean - 0.5) * 300 + ess * 0.5))
        signal = "LONG"
        reasoning = f"Bayesian {context}: {post_mean:.1%} win rate ({wins}W/{losses}L). 90% CI: [{ci_90_low:.1%}, {ci_90_high:.1%}]. Strong edge."
    elif post_mean > 0.52:
        conviction = int((post_mean - 0.5) * 200)
        signal = "NEUTRAL"
        reasoning = f"Bayesian {context}: {post_mean:.1%} win rate — marginal edge. More data needed."
    elif post_mean < 0.40:
        conviction = int((0.5 - post_mean) * 200)
        signal = "SHORT"  # inverse strategy might work
        reasoning = f"Bayesian {context}: only {post_mean:.1%} win rate ({wins}W/{losses}L). Avoid or reverse."
    else:
        conviction = 15
        signal = "NEUTRAL"
        reasoning = f"Bayesian {context}: {post_mean:.1%} win rate — near-random. No edge detected."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"posterior_mean": round(post_mean, 4), "posterior_mode": round(post_mode, 4),
                "ci_90": [round(ci_90_low, 3), round(ci_90_high, 3)],
                "wins": wins, "losses": losses, "ess": ess}
    }


# ─────────────────────────────────────────────────────────────
# 10. MONTE CARLO (Path Simulation)
# ─────────────────────────────────────────────────────────────

def monte_carlo_quick(win_rate: float, avg_win: float, avg_loss: float,
                      balance: float, target: float, ruin_level: float,
                      n_trades: int = 20, n_paths: int = 1000) -> Dict[str, Any]:
    """
    Fast Monte Carlo: simulate N_PATHS of N_TRADES.
    Returns P(hit target), P(ruin), expected final balance.
    Uses Python random (fast) not numpy for portability.
    """
    import random
    random.seed(42)  # reproducible

    hits_target = 0
    hits_ruin = 0
    final_balances = []

    for _ in range(n_paths):
        bal = balance
        for _ in range(n_trades):
            if bal <= ruin_level:
                break
            if random.random() < win_rate:
                bal += avg_win
            else:
                bal -= avg_loss
            if bal >= target:
                break
        final_balances.append(bal)
        if bal >= target:
            hits_target += 1
        if bal <= ruin_level:
            hits_ruin += 1

    p_target = hits_target / n_paths
    p_ruin = hits_ruin / n_paths
    expected_final = statistics.mean(final_balances)
    median_final = statistics.median(final_balances)

    if p_target > 0.65 and p_ruin < 0.05:
        conviction = min(85, int(p_target * 100))
        signal = "LONG"
        reasoning = f"MC ({n_paths} paths): {p_target:.0%} hit target, {p_ruin:.1%} ruin risk. Strong trajectory."
    elif p_ruin > 0.15:
        conviction = 0
        signal = "NEUTRAL"
        reasoning = f"MC: {p_ruin:.1%} ruin risk — too high. Reduce size or wait."
    else:
        conviction = int(p_target * 60)
        signal = "NEUTRAL"
        reasoning = f"MC: {p_target:.0%} target, {p_ruin:.1%} ruin. Acceptable but not optimal."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"p_target": round(p_target, 3), "p_ruin": round(p_ruin, 4),
                "expected_final": round(expected_final, 2),
                "median_final": round(median_final, 2),
                "n_paths": n_paths, "n_trades": n_trades}
    }


# ─────────────────────────────────────────────────────────────
# 11. RISK OF RUIN (Gambler's Ruin / Ralph Vince)
# ─────────────────────────────────────────────────────────────

def risk_of_ruin(win_rate: float, rr_ratio: float,
                 balance: float, max_loss_per_trade: float,
                 ruin_threshold: float = 0.90) -> Dict[str, Any]:
    """
    Ralph Vince Risk of Ruin formula.
    RoR = ((1-edge)/(1+edge)) ^ (balance / max_loss_per_trade)
    where edge = win_rate * rr_ratio - (1 - win_rate)
    Stops trading if RoR > 5%.
    """
    if max_loss_per_trade == 0 or balance == 0:
        return {"signal": "NEUTRAL", "conviction": 0,
                "reasoning": "Cannot calculate RoR: zero loss or balance.", "raw": {}}

    edge = win_rate * rr_ratio - (1 - win_rate)
    n_units = balance / max_loss_per_trade  # number of "risk units" in bankroll

    if edge <= 0:
        ror = 1.0  # certain ruin with no edge
    else:
        lose_frac = (1 - edge) / (1 + edge)
        ror = lose_frac ** n_units if lose_frac > 0 else 0

    ror_pct = ror * 100

    if ror > 0.05:  # > 5% ruin risk
        signal = "NEUTRAL"
        conviction = 0
        reasoning = f"RoR={ror_pct:.2f}% EXCEEDS 5% threshold. DO NOT TRADE. Reduce size or rebuild edge first."
    elif ror > 0.01:
        signal = "NEUTRAL"
        conviction = int((0.05 - ror) / 0.05 * 50)
        reasoning = f"RoR={ror_pct:.2f}%: elevated but under limit. Trade conservatively."
    else:
        conviction = min(80, int((0.01 - ror) / 0.01 * 40 + 50))
        signal = "LONG"
        reasoning = f"RoR={ror_pct:.3f}%: excellent risk profile. {n_units:.0f} risk units, edge={edge:.3f}."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"ror_pct": round(ror_pct, 4), "edge": round(edge, 4),
                "n_units": round(n_units, 1), "rr_ratio": rr_ratio, "win_rate": win_rate}
    }


# ─────────────────────────────────────────────────────────────
# 12. INFORMATION THEORY (Shannon Entropy + Mutual Information)
# ─────────────────────────────────────────────────────────────

def information_theory(price_changes: List[float],
                       signal_sequence: Optional[List[str]] = None,
                       n_buckets: int = 10) -> Dict[str, Any]:
    """
    Shannon entropy of price change distribution.
    Low entropy = predictable market (tradeable)
    High entropy = random noise (stay out)

    Mutual information between signals and outcomes measures signal quality.
    """
    if len(price_changes) < 5:
        return {"signal": "NEUTRAL", "conviction": 0,
                "reasoning": "Need more data for information theory analysis.", "raw": {}}

    # Discretize price changes into buckets
    min_pc = min(price_changes)
    max_pc = max(price_changes)
    range_pc = max_pc - min_pc

    if range_pc == 0:
        return {"signal": "NEUTRAL", "conviction": 20,
                "reasoning": "Zero range — market flat, no entropy.", "raw": {"entropy": 0}}

    bucket_size = range_pc / n_buckets
    buckets = [0] * n_buckets
    for pc in price_changes:
        idx = min(int((pc - min_pc) / bucket_size), n_buckets - 1)
        buckets[idx] += 1

    # Shannon entropy
    n = len(price_changes)
    entropy = 0.0
    for count in buckets:
        if count > 0:
            p = count / n
            entropy -= p * math.log2(p)

    max_entropy = math.log2(n_buckets)  # uniform distribution
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 1.0

    # Directional bias
    up_changes = sum(1 for pc in price_changes if pc > 0)
    down_changes = sum(1 for pc in price_changes if pc < 0)
    direction_bias = (up_changes - down_changes) / n

    if normalized_entropy < 0.6:  # Low entropy = predictable
        conviction = int((1 - normalized_entropy) * 80)
        if direction_bias > 0.1:
            signal = "LONG"
            reasoning = f"LOW entropy ({normalized_entropy:.2f}): market is predictable. Upside bias={direction_bias:.1%}. Information edge exists."
        elif direction_bias < -0.1:
            signal = "SHORT"
            reasoning = f"LOW entropy ({normalized_entropy:.2f}): predictable. Downside bias={abs(direction_bias):.1%}."
        else:
            signal = "NEUTRAL"
            conviction = int(conviction * 0.5)
            reasoning = f"LOW entropy ({normalized_entropy:.2f}) but no directional bias. Mean reversion possible."
    elif normalized_entropy > 0.85:
        conviction = 10
        signal = "NEUTRAL"
        reasoning = f"HIGH entropy ({normalized_entropy:.2f}): near-random market. Information edge minimal."
    else:
        conviction = 30
        signal = "NEUTRAL"
        reasoning = f"MEDIUM entropy ({normalized_entropy:.2f}): some structure. Direction bias={direction_bias:.1%}."

    return {
        "signal": signal,
        "conviction": conviction,
        "reasoning": reasoning,
        "raw": {"entropy": round(entropy, 3), "normalized_entropy": round(normalized_entropy, 3),
                "direction_bias": round(direction_bias, 3), "max_entropy": round(max_entropy, 3),
                "n_samples": n}
    }


# ─────────────────────────────────────────────────────────────
# MASTER: Run All 12 Models and Aggregate
# ─────────────────────────────────────────────────────────────

def run_all_models(snapshot: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run all 12 probability models and return a structured report
    for the LLM to synthesize into a trading decision.

    snapshot: market snapshot from IPC request
    memory: ai_trading_memory.json data
    """
    contract = snapshot.get("contract_id", "")
    price = snapshot.get("price", 0)
    ofi_z = snapshot.get("ofi_z", 0)
    vpin = snapshot.get("vpin", 0.5)
    atr_ticks = snapshot.get("atr_ticks", 10)
    regime = snapshot.get("regime", "ranging")
    session_phase = snapshot.get("session_phase", "us_core")
    balance = snapshot.get("account_balance", 150000)
    prices_history = snapshot.get("prices_history", [price])

    # Get per-contract memory stats
    perf = memory.get("performance_by_contract", {}).get(contract, {})
    wins = perf.get("wins", 0)
    losses = perf.get("losses", 0)
    total_trades = wins + losses

    # Estimate avg win/loss from memory
    avg_win_est = 75.0   # $75 default per trade
    avg_loss_est = 50.0  # $50 default per trade
    if total_trades > 0 and perf.get("total_pnl", 0) != 0:
        pnl = perf.get("total_pnl", 0)
        if wins > 0:
            avg_win_est = max(10, pnl / wins) if pnl > 0 else 50
        if losses > 0:
            avg_loss_est = max(10, abs(pnl) / losses) if pnl < 0 else 50

    win_rate = wins / total_trades if total_trades > 5 else 0.50
    rr_ratio = avg_win_est / avg_loss_est if avg_loss_est > 0 else 1.5

    # Run all 12
    results = {}

    results["1_kelly"] = kelly_criterion(win_rate, avg_win_est, avg_loss_est)
    results["2_poker_ev"] = poker_ev(win_rate, avg_win_est, avg_loss_est)
    results["3_casino_edge"] = casino_edge(win_rate, rr_ratio, total_trades)
    results["4_market_making"] = market_making(
        bid=price - atr_ticks * 0.25,
        ask=price + atr_ticks * 0.25,
        mid=price, last_price=price
    )
    results["5_stat_arb"] = statistical_arbitrage(prices_history)
    results["6_volatility"] = volatility_model(atr_ticks, 12.0, session_phase=session_phase)
    results["7_momentum"] = momentum_model(prices_history)
    results["8_order_flow"] = order_flow_model(ofi_z, vpin)
    results["9_bayesian"] = bayesian_inference(wins, losses, contract, regime)
    results["10_monte_carlo"] = monte_carlo_quick(
        win_rate, avg_win_est, avg_loss_est,
        balance, balance * 1.07, balance * 0.98
    )
    results["11_risk_of_ruin"] = risk_of_ruin(
        win_rate, rr_ratio, balance, avg_loss_est
    )
    results["12_information_theory"] = information_theory(
        [prices_history[i] - prices_history[i-1] for i in range(1, len(prices_history))]
        if len(prices_history) > 1 else [0.0]
    )

    # Tally votes
    long_votes = sum(1 for r in results.values() if r["signal"] == "LONG")
    short_votes = sum(1 for r in results.values() if r["signal"] == "SHORT")
    avg_conviction = round(statistics.mean([r["conviction"] for r in results.values()]), 1)

    # Weighted conviction (higher-conviction models count more)
    weighted_long = sum(r["conviction"] for r in results.values() if r["signal"] == "LONG")
    weighted_short = sum(r["conviction"] for r in results.values() if r["signal"] == "SHORT")

    summary = {
        "long_votes": long_votes,
        "short_votes": short_votes,
        "neutral_votes": 12 - long_votes - short_votes,
        "avg_conviction": avg_conviction,
        "weighted_long_conviction": weighted_long,
        "weighted_short_conviction": weighted_short,
        "dominant_signal": "LONG" if weighted_long > weighted_short else (
            "SHORT" if weighted_short > weighted_long else "NEUTRAL"),
        "consensus_strength": abs(weighted_long - weighted_short) / max(weighted_long + weighted_short, 1)
    }

    return {
        "models": results,
        "summary": summary,
        "contract": contract,
        "regime": regime,
        "session_phase": session_phase
    }
