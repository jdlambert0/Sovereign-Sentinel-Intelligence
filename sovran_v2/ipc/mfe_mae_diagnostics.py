#!/usr/bin/env python3
"""
MFE/MAE Diagnostic Framework

Analyzes Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE)
to identify whether win rate issues are due to:
1. Entry problems (signals are wrong)
2. Exit problems (signals are good but exits too early/late)
3. Stop loss problems (stops too tight)

Based on _research/SYSTEM_PROBLEMS_SOLUTIONS.md Problem 7
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class MFEMAEDiagnostic:
    """Diagnostic result from MFE/MAE analysis."""
    total_trades: int
    wins: int
    losses: int
    win_rate: float

    # MFE analysis
    avg_mfe_winners: float
    avg_mfe_losers: float
    avg_mae_winners: float
    avg_mae_losers: float

    # Diagnostics
    entry_quality_score: float  # 0-100, higher = better entries
    exit_quality_score: float   # 0-100, higher = better exits
    stop_placement_score: float # 0-100, higher = better stop placement

    # Recommendations
    primary_issue: str  # "entry", "exit", or "stop_placement"
    recommendations: List[str]


def load_trade_data() -> List[Dict]:
    """Load MFE/MAE data from memory."""
    memory_file = Path(__file__).parent.parent / "state" / "ai_trading_memory.json"

    if not memory_file.exists():
        return []

    with open(memory_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get("mfe_mae_data", [])


def analyze_mfe_mae() -> MFEMAEDiagnostic:
    """
    Run MFE/MAE diagnostic analysis.

    Key Insights:
    - High MFE on losers + Low win rate = EXIT PROBLEM (taking profit too late)
    - Low MFE on all trades = ENTRY PROBLEM (wrong signals)
    - High MAE on all trades = STOP PLACEMENT PROBLEM (stops too tight)
    """
    trades = load_trade_data()

    if not trades:
        return MFEMAEDiagnostic(
            total_trades=0, wins=0, losses=0, win_rate=0.0,
            avg_mfe_winners=0.0, avg_mfe_losers=0.0,
            avg_mae_winners=0.0, avg_mae_losers=0.0,
            entry_quality_score=0.0, exit_quality_score=0.0, stop_placement_score=0.0,
            primary_issue="insufficient_data",
            recommendations=["Need at least 10 trades for meaningful analysis"]
        )

    # Separate winners and losers
    winners = [t for t in trades if t["is_win"]]
    losers = [t for t in trades if not t["is_win"]]

    win_count = len(winners)
    loss_count = len(losers)
    win_rate = win_count / len(trades) if trades else 0.0

    # Calculate averages
    avg_mfe_winners = sum(t["mfe"] for t in winners) / win_count if winners else 0.0
    avg_mfe_losers = sum(t["mfe"] for t in losers) / loss_count if losers else 0.0
    avg_mae_winners = sum(abs(t["mae"]) for t in winners) / win_count if winners else 0.0
    avg_mae_losers = sum(abs(t["mae"]) for t in losers) / loss_count if losers else 0.0

    # Diagnostic scores (0-100)

    # ENTRY QUALITY: If MFE is good on losers, entries are fine
    # Score based on avg MFE of losers (in ticks, assuming ~$5/tick)
    mfe_losers_ticks = avg_mfe_losers / 5.0 if avg_mfe_losers > 0 else 0
    entry_quality = min(100, mfe_losers_ticks * 5)  # 20 ticks = perfect score

    # EXIT QUALITY: If MFE high but still lost, exits are bad
    # Inverse relationship: high MFE on losers = bad exits
    if avg_mfe_losers > 10:  # $10+ favorable but still lost
        exit_quality = max(0, 100 - (avg_mfe_losers / 1.0))  # Worse with higher MFE
    else:
        exit_quality = 70  # Neutral

    # STOP PLACEMENT: If MAE too high before stop, stops are too tight
    # Score based on MAE of losers
    mae_losers_ticks = avg_mae_losers / 5.0 if avg_mae_losers > 0 else 0
    if mae_losers_ticks < 5:  # Stops very tight
        stop_placement = 30
    elif mae_losers_ticks < 10:  # Reasonable
        stop_placement = 70
    else:  # Wide stops
        stop_placement = 90

    # Determine primary issue
    scores = {
        "entry": entry_quality,
        "exit": exit_quality,
        "stop_placement": stop_placement
    }
    primary_issue = min(scores, key=scores.get)

    # Generate recommendations
    recommendations = []

    if primary_issue == "entry":
        recommendations.append("ENTRY PROBLEM: Signals not predicting profitable moves")
        recommendations.append("- Review OFI/VPIN thresholds - may need tightening")
        recommendations.append("- Add regime filter - only trade in favorable regimes")
        recommendations.append("- Increase conviction threshold from 60 to 70+")
        recommendations.append(f"- Current avg MFE on losers: ${avg_mfe_losers:.2f} (< $20 is concerning)")

    if primary_issue == "exit":
        recommendations.append("EXIT PROBLEM: Good entries but poor profit capture")
        recommendations.append(f"- Avg MFE on losers: ${avg_mfe_losers:.2f} - these should be winners!")
        recommendations.append("- Tighten partial TP threshold (currently 0.6x SL)")
        recommendations.append("- Activate trailing stop earlier (currently 0.5x SL)")
        recommendations.append("- Consider time-based exits if MFE not captured within 5min")

    if primary_issue == "stop_placement":
        recommendations.append("STOP PLACEMENT PROBLEM: Stops too tight for volatility")
        recommendations.append(f"- Avg MAE on losers: ${avg_mae_losers:.2f} before stop")
        recommendations.append("- Increase ATR multiplier for SL calculation")
        recommendations.append("- Add wider buffer for overnight/thin hour trades")
        recommendations.append("- Consider volatility-adjusted stop placement")

    # Add strategy-specific insights
    strat_performance = {}
    for trade in trades:
        strat = trade["strategy"]
        if strat not in strat_performance:
            strat_performance[strat] = {"wins": 0, "total": 0}
        strat_performance[strat]["total"] += 1
        if trade["is_win"]:
            strat_performance[strat]["wins"] += 1

    for strat, perf in strat_performance.items():
        strat_win_rate = perf["wins"] / perf["total"] if perf["total"] > 0 else 0
        if strat_win_rate < 0.35:
            recommendations.append(f"- {strat.upper()} strategy underperforming ({strat_win_rate:.1%} win rate)")

    return MFEMAEDiagnostic(
        total_trades=len(trades),
        wins=win_count,
        losses=loss_count,
        win_rate=win_rate,
        avg_mfe_winners=avg_mfe_winners,
        avg_mfe_losers=avg_mfe_losers,
        avg_mae_winners=avg_mae_winners,
        avg_mae_losers=avg_mae_losers,
        entry_quality_score=entry_quality,
        exit_quality_score=exit_quality,
        stop_placement_score=stop_placement,
        primary_issue=primary_issue,
        recommendations=recommendations
    )


def print_diagnostic_report():
    """Print formatted diagnostic report."""
    diag = analyze_mfe_mae()

    print("\n" + "="*70)
    print("MFE/MAE DIAGNOSTIC REPORT")
    print("="*70)

    print(f"\nTRADE STATISTICS:")
    print(f"  Total Trades: {diag.total_trades}")
    print(f"  Wins: {diag.wins} | Losses: {diag.losses}")
    print(f"  Win Rate: {diag.win_rate:.1%}")

    print(f"\nMFE/MAE ANALYSIS:")
    print(f"  Winners - Avg MFE: ${diag.avg_mfe_winners:+.2f} | Avg MAE: ${diag.avg_mae_winners:.2f}")
    print(f"  Losers  - Avg MFE: ${diag.avg_mfe_losers:+.2f} | Avg MAE: ${diag.avg_mae_losers:.2f}")

    print(f"\nDIAGNOSTIC SCORES (0-100):")
    print(f"  Entry Quality:      {diag.entry_quality_score:.0f}/100")
    print(f"  Exit Quality:       {diag.exit_quality_score:.0f}/100")
    print(f"  Stop Placement:     {diag.stop_placement_score:.0f}/100")

    print(f"\nPRIMARY ISSUE: {diag.primary_issue.upper()}")

    print(f"\nRECOMMENDATIONS:")
    for rec in diag.recommendations:
        print(f"  {rec}")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print_diagnostic_report()
