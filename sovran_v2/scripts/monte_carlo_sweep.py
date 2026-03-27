#!/usr/bin/env python3
"""
Sovran V2 — Monte Carlo Parameter Sweep

Simulates 10,000 trading paths using the system's actual parameters to validate:
- Probability of hitting $159K target (TopStepX 150K Combine)
- Probability of hitting trailing drawdown (ruin)
- Expected time to target
- Risk/reward profile per contract/regime

Uses Sovran V2's real configuration:
- 6 contracts: MNQ, MES, MYM, M2K, MGC, MCL
- 3 regimes: trending, ranging, volatile (blocked)
- Bayesian win rate priors (Beta(2,2) = 50% baseline)
- Kelly-derived position sizing
- Circuit breaker, cooldowns, conviction thresholds

Usage:
    python scripts/monte_carlo_sweep.py

Output:
    state/monte_carlo_results.json
    state/monte_carlo_chart.png
"""
import json
import math
import os
import random
import statistics
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

# ─── System Parameters (mirrored from live_session_v5.py) ─────────────

STARTING_BALANCE = 148_608.0
PROFIT_TARGET = 159_000.0          # TopStepX 150K Combine target
TRAILING_DRAWDOWN = 4_500.0        # Trailing max drawdown
MAX_TRADES_PER_DAY = 25            # Practical limit (~8h / 20min avg)
TRADING_DAYS = 60                  # Simulate up to 60 trading days
N_SIMULATIONS = 10_000

# Contract universe
CONTRACTS = {
    "MNQ": {"tick_size": 0.25, "tick_value": 0.50, "asset": "equity_index"},
    "MES": {"tick_size": 0.25, "tick_value": 1.25, "asset": "equity_index"},
    "MYM": {"tick_size": 1.00, "tick_value": 0.50, "asset": "equity_index"},
    "M2K": {"tick_size": 0.10, "tick_value": 0.50, "asset": "equity_index"},
    "MGC": {"tick_size": 0.10, "tick_value": 1.00, "asset": "metals"},
    "MCL": {"tick_size": 0.01, "tick_value": 1.00, "asset": "energy"},
}

# Regime profiles (from V5 config)
REGIMES = {
    "trending": {"sl_mult": 2.0, "tp_mult": 5.0, "trail_act": 0.4, "frequency": 0.35},
    "ranging":  {"sl_mult": 1.5, "tp_mult": 2.5, "trail_act": 0.3, "frequency": 0.50},
    "choppy":   {"sl_mult": 1.2, "tp_mult": 1.8, "trail_act": 0.3, "frequency": 0.15},
}

# AI engine conviction/probability
BASE_WIN_RATE = 0.50               # Beta(2,2) prior = 50% baseline
CONVICTION_THRESHOLD = 60          # MIN_CONVICTION_FIRST
WEAK_SIGNAL_DISCOUNT = 0.85        # Round-robin discount

# Asset class adjustment (from ai_decision_engine.py)
ASSET_CONVICTION_ADJ = {
    "energy": 1.10,      # +10% for MCL
    "metals": 1.10,      # +10% for MGC
    "equity_index": 0.80, # -20% for equity
}

# Average ticks for SL/TP per regime (based on ATR and system config)
BASE_SL_TICKS = 20  # Average stop-loss in ticks
BASE_TP_TICKS = 40  # Scales by regime profile


@dataclass
class TradeOutcome:
    contract: str
    regime: str
    signal: str
    pnl: float
    win: bool
    sl_ticks: int
    tp_ticks: int


@dataclass
class SimPath:
    trades: List[TradeOutcome] = field(default_factory=list)
    balance_history: List[float] = field(default_factory=list)
    final_balance: float = 0.0
    peak_balance: float = 0.0
    max_drawdown: float = 0.0
    hit_target: bool = False
    hit_ruin: bool = False
    days_to_target: int = 0
    total_trades: int = 0


def simulate_trade(contract: str, regime_name: str, regime: Dict,
                   win_rate: float, size: int = 1) -> TradeOutcome:
    """Simulate a single trade with realistic parameters."""
    meta = CONTRACTS[contract]
    tv = meta["tick_value"]

    # SL/TP in ticks based on regime
    sl_ticks = max(15, int(BASE_SL_TICKS * regime["sl_mult"]))
    tp_ticks = max(sl_ticks, int(BASE_TP_TICKS * regime["tp_mult"]))

    # Asset class conviction adjustment
    adj = ASSET_CONVICTION_ADJ.get(meta["asset"], 1.0)
    effective_wr = min(0.85, win_rate * adj)

    # Simulate outcome
    if random.random() < effective_wr:
        # WIN — but we don't always capture full TP
        # Model trailing stop behavior: capture between 40% and 100% of TP
        capture_ratio = random.triangular(0.3, 1.0, 0.65)
        pnl_ticks = tp_ticks * capture_ratio
        pnl = pnl_ticks * tv * size
        return TradeOutcome(contract, regime_name, "WIN", pnl, True, sl_ticks, tp_ticks)
    else:
        # LOSS — usually full SL, sometimes partial (trail moved SL)
        loss_ratio = random.triangular(0.5, 1.0, 0.9)
        pnl_ticks = -sl_ticks * loss_ratio
        pnl = pnl_ticks * tv * size
        return TradeOutcome(contract, regime_name, "LOSS", pnl, False, sl_ticks, tp_ticks)


def simulate_path(sim_id: int) -> SimPath:
    """Simulate one complete trading path."""
    path = SimPath()
    balance = STARTING_BALANCE
    peak = balance
    consecutive_losses = 0
    total_wins = 0
    total_losses = 0
    path.balance_history.append(balance)

    for day in range(1, TRADING_DAYS + 1):
        trades_today = 0
        daily_start = balance

        # Simulate a trading day
        while trades_today < MAX_TRADES_PER_DAY:
            # Pick regime
            r = random.random()
            if r < REGIMES["trending"]["frequency"]:
                regime_name, regime = "trending", REGIMES["trending"]
            elif r < REGIMES["trending"]["frequency"] + REGIMES["ranging"]["frequency"]:
                regime_name, regime = "ranging", REGIMES["ranging"]
            else:
                regime_name, regime = "choppy", REGIMES["choppy"]

            # Pick contract (round-robin among all 6)
            contract = random.choice(list(CONTRACTS.keys()))

            # Calculate effective win rate
            # Bayesian updating: as we accumulate data, the win rate converges
            total = total_wins + total_losses
            if total >= 5:
                bayesian_wr = (total_wins + 2) / (total + 4)  # Beta(2,2) posterior
            else:
                bayesian_wr = BASE_WIN_RATE

            # Blended probability: 60% model + 25% strategy Bayes + 15% contract
            model_wr = BASE_WIN_RATE + (regime_name == "trending") * 0.08 + (regime_name == "ranging") * 0.02
            blended_wr = 0.60 * model_wr + 0.25 * bayesian_wr + 0.15 * BASE_WIN_RATE

            # Weak signal discount (30% of trades are weak signal)
            if random.random() < 0.30:
                blended_wr *= WEAK_SIGNAL_DISCOUNT

            # Conviction check: skip if below threshold (but round-robin means very few skips)
            conviction = blended_wr * 100
            if conviction < CONVICTION_THRESHOLD * 0.8:
                trades_today += 1
                continue

            # Position size: 1 contract, 2 if high conviction
            size = 2 if conviction >= 80 else 1

            # Execute trade
            trade = simulate_trade(contract, regime_name, regime, blended_wr, size)
            path.trades.append(trade)
            trades_today += 1

            # Update balance
            balance += trade.pnl
            path.balance_history.append(balance)

            # Track peak and drawdown
            if balance > peak:
                peak = balance
            drawdown = peak - balance

            # Update stats
            if trade.win:
                total_wins += 1
                consecutive_losses = 0
            else:
                total_losses += 1
                consecutive_losses += 1

            # Circuit breaker: 3 consecutive losses, stop for the day
            if consecutive_losses >= 3:
                consecutive_losses = 0
                break

            # Check target
            if balance >= PROFIT_TARGET:
                path.hit_target = True
                path.days_to_target = day
                path.final_balance = balance
                path.peak_balance = peak
                path.max_drawdown = peak - min(path.balance_history)
                path.total_trades = len(path.trades)
                return path

            # Check ruin (trailing drawdown)
            if drawdown >= TRAILING_DRAWDOWN:
                path.hit_ruin = True
                path.final_balance = balance
                path.peak_balance = peak
                path.max_drawdown = drawdown
                path.total_trades = len(path.trades)
                return path

    # End of simulation period
    path.final_balance = balance
    path.peak_balance = peak
    path.max_drawdown = peak - min(path.balance_history)
    path.total_trades = len(path.trades)
    return path


def run_sweep() -> Dict:
    """Run full Monte Carlo sweep."""
    random.seed(42)  # Reproducible

    paths: List[SimPath] = []
    for i in range(N_SIMULATIONS):
        paths.append(simulate_path(i))
        if (i + 1) % 1000 == 0:
            print(f"  Simulated {i+1}/{N_SIMULATIONS} paths...")

    # ─── Aggregate Results ───
    target_hits = sum(1 for p in paths if p.hit_target)
    ruin_hits = sum(1 for p in paths if p.hit_ruin)
    neither = N_SIMULATIONS - target_hits - ruin_hits

    finals = [p.final_balance for p in paths]
    drawdowns = [p.max_drawdown for p in paths]
    trade_counts = [p.total_trades for p in paths]

    target_days = [p.days_to_target for p in paths if p.hit_target]

    # Per-contract stats
    contract_stats = {}
    for name in CONTRACTS:
        contract_trades = []
        for p in paths:
            for t in p.trades:
                if t.contract == name:
                    contract_trades.append(t)
        if contract_trades:
            wins = sum(1 for t in contract_trades if t.win)
            total = len(contract_trades)
            avg_win = statistics.mean([t.pnl for t in contract_trades if t.win]) if wins else 0
            avg_loss = statistics.mean([t.pnl for t in contract_trades if not t.win]) if (total - wins) else 0
            contract_stats[name] = {
                "total_trades": total,
                "win_rate": wins / total if total else 0,
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            }

    # Per-regime stats
    regime_stats = {}
    for regime_name in REGIMES:
        regime_trades = []
        for p in paths:
            for t in p.trades:
                if t.regime == regime_name:
                    regime_trades.append(t)
        if regime_trades:
            wins = sum(1 for t in regime_trades if t.win)
            total = len(regime_trades)
            regime_stats[regime_name] = {
                "total_trades": total,
                "win_rate": wins / total if total else 0,
                "avg_pnl": round(statistics.mean([t.pnl for t in regime_trades]), 2),
            }

    results = {
        "simulation_params": {
            "starting_balance": STARTING_BALANCE,
            "profit_target": PROFIT_TARGET,
            "trailing_drawdown": TRAILING_DRAWDOWN,
            "n_simulations": N_SIMULATIONS,
            "max_trading_days": TRADING_DAYS,
            "base_win_rate": BASE_WIN_RATE,
        },
        "outcomes": {
            "probability_hit_target": round(target_hits / N_SIMULATIONS * 100, 1),
            "probability_hit_ruin": round(ruin_hits / N_SIMULATIONS * 100, 1),
            "probability_neither": round(neither / N_SIMULATIONS * 100, 1),
            "target_hits": target_hits,
            "ruin_hits": ruin_hits,
            "neither": neither,
        },
        "balance_stats": {
            "mean_final": round(statistics.mean(finals), 2),
            "median_final": round(statistics.median(finals), 2),
            "std_dev": round(statistics.stdev(finals), 2),
            "min_final": round(min(finals), 2),
            "max_final": round(max(finals), 2),
            "p5": round(sorted(finals)[int(N_SIMULATIONS * 0.05)], 2),
            "p25": round(sorted(finals)[int(N_SIMULATIONS * 0.25)], 2),
            "p75": round(sorted(finals)[int(N_SIMULATIONS * 0.75)], 2),
            "p95": round(sorted(finals)[int(N_SIMULATIONS * 0.95)], 2),
        },
        "drawdown_stats": {
            "mean_max_drawdown": round(statistics.mean(drawdowns), 2),
            "median_max_drawdown": round(statistics.median(drawdowns), 2),
            "p95_max_drawdown": round(sorted(drawdowns)[int(N_SIMULATIONS * 0.95)], 2),
        },
        "time_to_target": {
            "mean_days": round(statistics.mean(target_days), 1) if target_days else None,
            "median_days": round(statistics.median(target_days), 1) if target_days else None,
            "p75_days": round(sorted(target_days)[int(len(target_days) * 0.75)], 1) if target_days else None,
        },
        "trade_stats": {
            "mean_trades_per_path": round(statistics.mean(trade_counts), 0),
            "avg_trades_per_day": round(statistics.mean(trade_counts) / TRADING_DAYS, 1),
        },
        "contract_performance": contract_stats,
        "regime_performance": regime_stats,
    }

    return results, paths


def generate_chart(paths: List[SimPath], results: Dict, output_path: str):
    """Generate Monte Carlo visualization."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker
    except ImportError:
        print("  [WARN] matplotlib not available, skipping chart")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Sovran V2 — Monte Carlo Simulation (10,000 paths)", fontsize=14, fontweight="bold")

    # 1. Balance paths (sample 200)
    ax1 = axes[0, 0]
    sample_indices = random.sample(range(len(paths)), min(200, len(paths)))
    for i in sample_indices:
        p = paths[i]
        color = "#2ecc71" if p.hit_target else "#e74c3c" if p.hit_ruin else "#95a5a6"
        alpha = 0.15 if not p.hit_target and not p.hit_ruin else 0.25
        ax1.plot(p.balance_history, color=color, alpha=alpha, linewidth=0.5)
    ax1.axhline(y=PROFIT_TARGET, color="#27ae60", linestyle="--", linewidth=1.5, label=f"Target ${PROFIT_TARGET:,.0f}")
    ax1.axhline(y=STARTING_BALANCE - TRAILING_DRAWDOWN, color="#c0392b", linestyle="--", linewidth=1.5, label=f"Ruin ${STARTING_BALANCE - TRAILING_DRAWDOWN:,.0f}")
    ax1.axhline(y=STARTING_BALANCE, color="#3498db", linestyle=":", linewidth=1, alpha=0.5)
    ax1.set_title("Balance Paths (200 sample)")
    ax1.set_xlabel("Trade #")
    ax1.set_ylabel("Balance ($)")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # 2. Final balance distribution
    ax2 = axes[0, 1]
    finals = [p.final_balance for p in paths]
    ax2.hist(finals, bins=80, color="#3498db", alpha=0.7, edgecolor="white", linewidth=0.3)
    ax2.axvline(x=PROFIT_TARGET, color="#27ae60", linestyle="--", linewidth=1.5)
    ax2.axvline(x=statistics.mean(finals), color="#e67e22", linestyle="-", linewidth=1.5, label=f"Mean ${statistics.mean(finals):,.0f}")
    ax2.set_title("Final Balance Distribution")
    ax2.set_xlabel("Final Balance ($)")
    ax2.set_ylabel("Count")
    ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 3. Outcome pie chart
    ax3 = axes[1, 0]
    outcomes = results["outcomes"]
    labels = [
        f"Hit Target\n{outcomes['probability_hit_target']}%",
        f"Hit Ruin\n{outcomes['probability_hit_ruin']}%",
        f"Still Open\n{outcomes['probability_neither']}%",
    ]
    sizes = [outcomes["target_hits"], outcomes["ruin_hits"], outcomes["neither"]]
    colors = ["#2ecc71", "#e74c3c", "#95a5a6"]
    ax3.pie(sizes, labels=labels, colors=colors, autopct="", startangle=90, textprops={"fontsize": 10})
    ax3.set_title("Outcome Probabilities")

    # 4. Per-contract performance
    ax4 = axes[1, 1]
    cp = results["contract_performance"]
    names = list(cp.keys())
    win_rates = [cp[n]["win_rate"] * 100 for n in names]
    profit_factors = [cp[n]["profit_factor"] for n in names]
    x = range(len(names))
    bars = ax4.bar(x, win_rates, color=["#3498db" if wr >= 50 else "#e74c3c" for wr in win_rates], alpha=0.8)
    ax4.set_xticks(x)
    ax4.set_xticklabels(names)
    ax4.set_ylabel("Win Rate (%)")
    ax4.set_title("Win Rate by Contract")
    ax4.axhline(y=50, color="gray", linestyle="--", alpha=0.5)
    ax4.grid(True, alpha=0.3, axis="y")
    for bar, pf in zip(bars, profit_factors):
        ax4.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"PF:{pf:.1f}", ha="center", fontsize=8, color="#555")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"  Chart saved: {output_path}")
    plt.close()


def print_results(results: Dict):
    """Print formatted results."""
    print("\n" + "=" * 65)
    print("  SOVRAN V2 — MONTE CARLO PARAMETER SWEEP")
    print("=" * 65)

    p = results["simulation_params"]
    print(f"\n  Start Balance:     ${p['starting_balance']:>12,.2f}")
    print(f"  Profit Target:     ${p['profit_target']:>12,.2f}  (+${p['profit_target'] - p['starting_balance']:,.2f})")
    print(f"  Trailing DD:       ${p['trailing_drawdown']:>12,.2f}")
    print(f"  Simulations:       {p['n_simulations']:>12,}")
    print(f"  Base Win Rate:     {p['base_win_rate']*100:>11.0f}%")

    o = results["outcomes"]
    print(f"\n  --- OUTCOMES ---")
    print(f"  P(Hit Target):     {o['probability_hit_target']:>11.1f}%  ({o['target_hits']:,} paths)")
    print(f"  P(Hit Ruin):       {o['probability_hit_ruin']:>11.1f}%  ({o['ruin_hits']:,} paths)")
    print(f"  P(Still Open):     {o['probability_neither']:>11.1f}%  ({o['neither']:,} paths)")

    b = results["balance_stats"]
    print(f"\n  --- BALANCE DISTRIBUTION ---")
    print(f"  Mean Final:        ${b['mean_final']:>12,.2f}")
    print(f"  Median Final:      ${b['median_final']:>12,.2f}")
    print(f"  Std Dev:           ${b['std_dev']:>12,.2f}")
    print(f"  5th Percentile:    ${b['p5']:>12,.2f}")
    print(f"  95th Percentile:   ${b['p95']:>12,.2f}")

    d = results["drawdown_stats"]
    print(f"\n  --- DRAWDOWN ---")
    print(f"  Mean Max DD:       ${d['mean_max_drawdown']:>12,.2f}")
    print(f"  Median Max DD:     ${d['median_max_drawdown']:>12,.2f}")
    print(f"  95th Pctl DD:      ${d['p95_max_drawdown']:>12,.2f}")

    t = results["time_to_target"]
    if t["mean_days"]:
        print(f"\n  --- TIME TO TARGET ---")
        print(f"  Mean Days:         {t['mean_days']:>12.1f}")
        print(f"  Median Days:       {t['median_days']:>12.1f}")
        print(f"  75th Pctl Days:    {t['p75_days']:>12.1f}")

    print(f"\n  --- CONTRACT PERFORMANCE ---")
    print(f"  {'Contract':<8} {'Trades':>8} {'Win%':>6} {'Avg Win':>9} {'Avg Loss':>9} {'PF':>5}")
    print(f"  {'-'*8} {'-'*8} {'-'*6} {'-'*9} {'-'*9} {'-'*5}")
    for name, stats in sorted(results["contract_performance"].items()):
        print(f"  {name:<8} {stats['total_trades']:>8,} {stats['win_rate']*100:>5.1f}% ${stats['avg_win']:>8.2f} ${stats['avg_loss']:>8.2f} {stats['profit_factor']:>4.1f}x")

    print(f"\n  --- REGIME PERFORMANCE ---")
    for name, stats in results["regime_performance"].items():
        print(f"  {name:<10} {stats['total_trades']:>8,} trades  WR={stats['win_rate']*100:.1f}%  Avg PnL=${stats['avg_pnl']:+.2f}")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    os.makedirs("state", exist_ok=True)

    print("Running Monte Carlo simulation...")
    results, paths = run_sweep()
    print_results(results)

    # Save results
    with open("state/monte_carlo_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: state/monte_carlo_results.json")

    # Generate chart
    generate_chart(paths, results, "state/monte_carlo_chart.png")
