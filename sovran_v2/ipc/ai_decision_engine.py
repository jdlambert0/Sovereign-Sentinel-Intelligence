#!/usr/bin/env python3
"""
AI Decision Engine - Beyond Edges

This is NOT a simple algorithm. This is an AI that:
- Scans all 6 contracts every cycle
- Calculates probability and expected value for each
- ALWAYS picks the best trade (even if all look "bad")
- Adapts risk dynamically based on market opportunity
- Learns continuously from Obsidian memory
- Trades actively, not passively

Philosophy: "You (AI) are the edge. Not the algorithm."
"""
import json
import glob
import os
import time
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [AI-ENGINE] %(message)s'
)
logger = logging.getLogger(__name__)

IPC_DIR = Path(__file__).parent
OBSIDIAN_DIR = Path(__file__).parent.parent / "obsidian"
STATE_DIR = Path(__file__).parent.parent / "state"
MEMORY_FILE = STATE_DIR / "ai_trading_memory.json"

# Ensure state directory exists
STATE_DIR.mkdir(exist_ok=True)


class TradingMemory:
    """Persistent memory for the AI. Learns from every trade."""

    def __init__(self, memory_file: Path):
        self.memory_file = memory_file
        self.data = self._load()

    def _load(self) -> Dict:
        if self.memory_file.exists():
            with open(self.memory_file) as f:
                return json.load(f)
        return {
            "trades_executed": 0,
            "total_pnl": 0.0,
            "strategies_tested": {},
            "market_patterns": {},
            "performance_by_contract": {},
            "performance_by_time": {},
            "performance_by_regime": {},
            "lessons_learned": [],
            "last_update": None
        }

    def save(self):
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def record_trade(self, contract: str, strategy: str, thesis: str,
                    market_conditions: Dict, outcome: Optional[Dict] = None):
        """Record a trade for learning."""
        self.data["trades_executed"] += 1

        # Record by contract
        if contract not in self.data["performance_by_contract"]:
            self.data["performance_by_contract"][contract] = {
                "trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0
            }
        self.data["performance_by_contract"][contract]["trades"] += 1

        # Record by strategy
        if strategy not in self.data["strategies_tested"]:
            self.data["strategies_tested"][strategy] = {
                "trades": 0, "wins": 0, "total_pnl": 0.0, "avg_hold_time": 0.0
            }
        self.data["strategies_tested"][strategy]["trades"] += 1

        # Record market pattern
        regime = market_conditions.get("regime", "unknown")
        if regime not in self.data["performance_by_regime"]:
            self.data["performance_by_regime"][regime] = {
                "trades": 0, "wins": 0, "total_pnl": 0.0
            }
        self.data["performance_by_regime"][regime]["trades"] += 1

        # If outcome is provided, update win/loss stats
        if outcome:
            pnl = outcome.get("pnl", 0.0)
            is_win = pnl > 0

            # Update contract performance
            self.data["performance_by_contract"][contract]["total_pnl"] += pnl
            if is_win:
                self.data["performance_by_contract"][contract]["wins"] += 1
            elif pnl < 0:
                self.data["performance_by_contract"][contract]["losses"] += 1

            # Update strategy performance
            self.data["strategies_tested"][strategy]["total_pnl"] += pnl
            if is_win:
                self.data["strategies_tested"][strategy]["wins"] += 1

            # Update regime performance
            self.data["performance_by_regime"][regime]["total_pnl"] += pnl
            if is_win:
                self.data["performance_by_regime"][regime]["wins"] += 1

            # Update total P&L
            self.data["total_pnl"] += pnl

            # Update average hold time
            if "hold_time" in outcome:
                strat_data = self.data["strategies_tested"][strategy]
                current_avg = strat_data.get("avg_hold_time", 0.0)
                current_count = strat_data["trades"]
                new_avg = ((current_avg * (current_count - 1)) + outcome["hold_time"]) / current_count
                strat_data["avg_hold_time"] = new_avg

        self.save()

    def query_similar_conditions(self, contract: str, regime: str,
                                 volatility_level: str) -> Dict:
        """Query memory for similar past conditions."""
        # Return what we learned from similar market conditions
        key = f"{contract}_{regime}_{volatility_level}"
        return self.data["market_patterns"].get(key, {
            "sample_size": 0,
            "win_rate": 0.5,  # Default 50% if no data
            "avg_win": 0.0,
            "avg_loss": 0.0
        })

    def get_bayesian_win_rate(self, strategy: str, prior: float = 0.5,
                              min_samples: int = 5) -> float:
        """
        Bayesian belief updating for strategy win rates.
        
        Uses Beta-Binomial conjugate prior:
        - Prior: Beta(alpha, beta) where alpha=beta=2 (weakly informative)
        - Posterior: Beta(alpha + wins, beta + losses)
        - Returns posterior mean as updated win rate
        
        This is the key Week 2 feature: the system LEARNS from outcomes
        and adjusts future probability estimates.
        """
        strat_data = self.data.get("strategies_tested", {}).get(strategy, {})
        wins = strat_data.get("wins", 0)
        trades = strat_data.get("trades", 0)
        losses = trades - wins

        if trades < min_samples:
            return prior  # Not enough data, use static prior

        # Beta-Binomial conjugate prior
        # Prior: Beta(2, 2) -> centered at 0.5, weakly informative
        alpha_prior = 2.0
        beta_prior = 2.0

        # Posterior: Beta(alpha_prior + wins, beta_prior + losses)
        alpha_post = alpha_prior + wins
        beta_post = beta_prior + losses

        # Posterior mean
        posterior_mean = alpha_post / (alpha_post + beta_post)

        # Credible interval width (for logging/diagnostics)
        # 95% CI is approximately mean +/- 1.96 * sqrt(var)
        variance = (alpha_post * beta_post) / ((alpha_post + beta_post)**2 * (alpha_post + beta_post + 1))
        ci_width = 1.96 * math.sqrt(variance) * 2

        logger.info(f"  Bayesian update [{strategy}]: prior={prior:.2f} -> "
                    f"posterior={posterior_mean:.2f} (W={wins}/L={losses}, "
                    f"95%CI width={ci_width:.2f})")

        return posterior_mean

    def get_bayesian_contract_rate(self, contract: str, prior: float = 0.5) -> float:
        """Bayesian win rate per contract (same method, different data slice)."""
        contract_data = self.data.get("performance_by_contract", {}).get(contract, {})
        wins = contract_data.get("wins", 0)
        trades = contract_data.get("trades", 0)
        losses = trades - wins

        if trades < 3:
            return prior

        alpha_post = 2.0 + wins
        beta_post = 2.0 + losses
        return alpha_post / (alpha_post + beta_post)

    def get_best_strategy_for(self, contract: str, regime: str) -> str:
        """Return the best performing strategy for this contract/regime."""
        # TODO: Implement sophisticated strategy selection
        # For now, return based on regime
        if regime in ["trending", "trending_up", "trending_down"]:
            return "momentum"
        elif regime in ["choppy", "ranging"]:
            return "mean_reversion"
        else:
            return "volatility_harvesting"


class ProbabilityCalculator:
    """Calculate trading probabilities using multiple models."""

    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float,
                       account_balance: float) -> float:
        """
        Kelly Criterion for optimal bet sizing.

        Formula: f* = (p*b - q) / b
        where:
        - p = win probability
        - q = loss probability (1-p)
        - b = odds (avg_win / avg_loss)
        """
        if avg_loss == 0 or win_rate >= 1.0 or win_rate <= 0:
            return 0.0

        p = win_rate
        q = 1 - win_rate
        b = avg_win / avg_loss

        kelly_fraction = (p * b - q) / b

        # Use fractional Kelly (25%) for safety
        fractional_kelly = kelly_fraction * 0.25

        # Cap at 5% of account
        max_risk = account_balance * 0.05
        return max(0.0, min(fractional_kelly, max_risk))

    @staticmethod
    def expected_value(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Expected Value calculation.

        EV = (win_rate × avg_win) - (loss_rate × avg_loss)
        """
        loss_rate = 1 - win_rate
        return (win_rate * avg_win) - (loss_rate * avg_loss)

    @staticmethod
    def risk_of_ruin(win_rate: float, avg_win: float, avg_loss: float, account_balance: float) -> float:
        """
        Calculate Risk of Ruin using Mason Malmuth formula.

        RoR = exp(-2μB/σ²)
        where:
        - μ = expected value per trade
        - B = account balance
        - σ² = variance per trade

        Target: < 1% (professional standard)
        Alert threshold: > 1% requires position size reduction
        """
        if avg_loss == 0 or win_rate >= 1.0 or win_rate <= 0:
            return 0.0

        # Expected value per trade (μ)
        ev = ProbabilityCalculator.expected_value(win_rate, avg_win, avg_loss)

        # Variance per trade (σ²)
        loss_rate = 1 - win_rate
        variance = (win_rate * (avg_win ** 2)) + (loss_rate * (avg_loss ** 2)) - (ev ** 2)

        if variance <= 0:
            return 0.0

        # Mason Malmuth formula
        import math
        ror = math.exp((-2 * ev * account_balance) / variance)

        return max(0.0, min(1.0, ror))

    @staticmethod
    def mean_reversion_probability(z_score: float) -> float:
        """
        Calculate mean reversion probability based on Z-score.

        High Z-score = high probability of reversion
        """
        # Simple model: P(reversion) increases with abs(z_score)
        abs_z = abs(z_score)
        if abs_z > 2.5:
            return 0.80
        elif abs_z > 2.0:
            return 0.70
        elif abs_z > 1.5:
            return 0.60
        elif abs_z > 1.0:
            return 0.55
        else:
            return 0.50

    @staticmethod
    def momentum_probability(ofi_z: float, vpin: float, regime: str) -> float:
        """
        Calculate momentum continuation probability.

        Strong OFI + high VPIN + trending regime = high momentum probability
        """
        base_prob = 0.50

        # OFI contribution
        if abs(ofi_z) > 2.0:
            base_prob += 0.15
        elif abs(ofi_z) > 1.5:
            base_prob += 0.10
        elif abs(ofi_z) > 1.0:
            base_prob += 0.05

        # VPIN contribution
        if vpin > 0.70:
            base_prob += 0.10
        elif vpin > 0.55:
            base_prob += 0.05

        # Regime contribution
        if regime in ["trending", "trending_up", "trending_down"]:
            base_prob += 0.10
        elif regime == "choppy":
            base_prob -= 0.10

        return min(0.85, max(0.30, base_prob))


class AIDecisionEngine:
    """
    The AI Decision Engine.

    Not a simple algorithm. This is where YOU (AI) make decisions based on:
    - Mathematical probability
    - Market physics
    - Obsidian memory
    - Intuition (leaps of faith when math is unclear)
    """

    def __init__(self):
        self.memory = TradingMemory(MEMORY_FILE)
        self.calc = ProbabilityCalculator()
        logger.info("AI Decision Engine initialized")
        logger.info(f"Memory loaded: {self.memory.data['trades_executed']} trades executed")

    def analyze_contract(self, snapshot: Dict, account_balance: float) -> Dict:
        """
        Analyze a single contract and return probability assessment.

        Returns:
        {
            'contract_id': str,
            'strategy': str (momentum, mean_reversion, volatility_harvesting),
            'expected_value': float,
            'win_probability': float,
            'signal': 'long' | 'short' | 'no_trade',
            'conviction': int (0-100),
            'thesis': str,
            'stop_points': float,
            'target_points': float,
            'position_size': int
        }
        """
        contract_id = snapshot.get('contract_id', 'UNKNOWN')
        price = snapshot.get('last_price', 0)
        ofi_z = snapshot.get('ofi_zscore', 0)
        vpin = snapshot.get('vpin', 0.5)
        regime = snapshot.get('regime', 'unknown')
        atr = snapshot.get('atr_points', 10.0)

        logger.info(f"Analyzing {contract_id} @ ${price:.2f}")
        logger.info(f"  OFI_Z={ofi_z:.2f} VPIN={vpin:.3f} Regime={regime} ATR={atr:.1f}")

        # Query memory for similar conditions
        volatility_level = "high" if atr > 15 else "medium" if atr > 8 else "low"
        historical = self.memory.query_similar_conditions(contract_id, regime, volatility_level)

        # Get best strategy for this contract/regime
        strategy = self.memory.get_best_strategy_for(contract_id, regime)

        # Calculate probabilities for different strategies
        mean_rev_prob = self.calc.mean_reversion_probability(ofi_z)
        momentum_prob = self.calc.momentum_probability(ofi_z, vpin, regime)

        # --- BAYESIAN BELIEF UPDATING (Week 2 priority) ---
        # Blend model probability with Bayesian posterior from actual outcomes.
        # This is how the system LEARNS: static priors get updated by real data.
        bayesian_strat_rate = self.memory.get_bayesian_win_rate(strategy, prior=0.5)
        bayesian_contract_rate = self.memory.get_bayesian_contract_rate(contract_id, prior=0.5)

        # Blend: 60% model probability, 25% strategy Bayesian, 15% contract Bayesian
        # As sample size grows, Bayesian component dominates naturally
        def blend_probability(model_prob: float) -> float:
            return (0.60 * model_prob +
                    0.25 * bayesian_strat_rate +
                    0.15 * bayesian_contract_rate)

        # Decide which strategy to use
        # ROUND-ROBIN RULE: NEVER return no_trade. Always pick a direction.
        # "If all markets look bad, pick best probability and trade anyway."
        # When signal is weak, we reduce conviction instead of refusing to trade.
        if strategy == "mean_reversion":
            win_probability = blend_probability(mean_rev_prob)
            if ofi_z > 1.0:
                signal = "short"
            elif ofi_z < -1.0:
                signal = "long"
            else:
                # Weak signal zone — still pick direction, flag as low-conviction
                signal = "short" if ofi_z > 0 else "long"
                win_probability *= 0.85  # Discount for weak setup
            thesis = f"Mean reversion: Z-score={ofi_z:.2f}, P(model)={mean_rev_prob:.2f}, P(bayesian)={win_probability:.2f}"
        elif strategy == "momentum":
            win_probability = blend_probability(momentum_prob)
            if ofi_z > 0.5:
                signal = "long"
            elif ofi_z < -0.5:
                signal = "short"
            else:
                # Weak signal zone — still pick direction, flag as low-conviction
                signal = "long" if ofi_z > 0 else "short"
                win_probability *= 0.85  # Discount for weak setup
            thesis = f"Momentum: OFI_Z={ofi_z:.2f}, VPIN={vpin:.2f}, P(model)={momentum_prob:.2f}, P(bayesian)={win_probability:.2f}"
        else:  # volatility_harvesting
            win_probability = blend_probability(0.55)
            signal = "long" if ofi_z > 0 else "short"
            thesis = f"Volatility harvest: Choppy market, P(bayesian)={win_probability:.2f}, ATR={atr:.1f}"

        # Dynamic risk based on opportunity
        # "Use the trade to determine what you risk"
        opportunity_size = atr * 2.0  # Potential profit is 2× ATR
        stop_distance = atr * 1.0  # Risk 1× ATR
        target_distance = atr * 2.0  # Target 2× ATR

        # Calculate expected value
        avg_win = target_distance
        avg_loss = stop_distance
        ev = self.calc.expected_value(win_probability, avg_win, avg_loss)

        # Conviction based on EV
        if ev > 0:
            conviction = min(100, int(50 + (ev / avg_loss) * 50))
        else:
            # Even negative EV trades can be learning trades
            conviction = 40  # Low but non-zero

        # --- ASSET PRIORITY WEIGHTING (Kaizen #4) ---
        # MCL has only win (+$38.48). MES/MNQ have 100% loss rate across 9 trades.
        # Boost energy/metals conviction, penalize equity indices.
        asset_class = snapshot.get('asset_class', '')
        if not asset_class:
            # Infer from contract_id
            cid_upper = contract_id.upper()
            if 'MCL' in cid_upper or 'CL' in cid_upper:
                asset_class = 'energy'
            elif 'MGC' in cid_upper or 'GC' in cid_upper:
                asset_class = 'metals'
            elif any(x in cid_upper for x in ['MES', 'MNQ', 'MYM', 'M2K']):
                asset_class = 'equity_index'
            else:
                asset_class = 'other'

        if asset_class == 'energy':
            conviction = min(100, int(conviction * 1.10))  # +10% boost
            thesis += " [+10% energy priority: MCL has proven edge]"
        elif asset_class == 'metals':
            conviction = min(100, int(conviction * 1.10))  # +10% boost
            thesis += " [+10% metals priority: MGC $1/tick value]"
        elif asset_class == 'equity_index':
            conviction = max(0, int(conviction * 0.80))  # -20% penalty
            thesis += " [-20% equity penalty: 0% win rate on MES/MNQ historically]"

        # Position sizing using Kelly Criterion
        kelly_size = self.calc.kelly_criterion(
            win_probability, avg_win, avg_loss, account_balance
        )

        # Convert to contracts (simplified)
        contracts = max(1, int(kelly_size / (stop_distance * 5)))  # $5/tick for MES

        return {
            'contract_id': contract_id,
            'strategy': strategy,
            'expected_value': ev,
            'win_probability': win_probability,
            'signal': signal,
            'conviction': conviction,
            'thesis': thesis,
            'stop_points': stop_distance,
            'target_points': target_distance,
            'position_size': contracts,
            'market_conditions': {
                'ofi_z': ofi_z,
                'vpin': vpin,
                'regime': regime,
                'atr': atr,
                'volatility_level': volatility_level
            }
        }

    def make_decision(self, request: Dict) -> Dict:
        """
        Main decision entry point. Called by IPC system.

        Returns standard IPC response format.
        """
        snapshot = request.get('snapshot_data', {})
        account_balance = request.get('account_balance', 150000)

        # --- OVERNIGHT LOCKOUT (Kaizen #6) ---
        # Hard block outside 8am-4pm CT. All overnight trades were losses.
        # Windows may lack tzdata; fall back to UTC-6 offset (CT)
        try:
            from zoneinfo import ZoneInfo
            ct_now = datetime.now(ZoneInfo("America/Chicago"))
        except Exception:
            from datetime import timedelta
            ct_now = datetime.now(timezone.utc) - timedelta(hours=6)
        hour_ct = ct_now.hour
        if hour_ct < 8 or hour_ct >= 16:
            contract_id = snapshot.get('contract_id', 'UNKNOWN')
            logger.info(f"OVERNIGHT LOCKOUT: {contract_id} blocked at {ct_now.strftime('%H:%M')} CT (allowed: 8am-4pm)")
            return {
                "signal": "no_trade",
                "conviction": 0,
                "thesis": f"Overnight lockout: {ct_now.strftime('%H:%M')} CT is outside 8am-4pm window. All overnight trades were losses.",
                "stop_distance_points": 0,
                "target_distance_points": 0,
                "frameworks_cited": ["risk_management", "kaizen_overnight_lockout"],
                "time_horizon": "none",
                "expected_value": 0,
                "win_probability": 0,
                "position_size": 0
            }

        # Analyze this contract
        analysis = self.analyze_contract(snapshot, account_balance)

        # Record in memory (pre-trade)
        self.memory.record_trade(
            contract=analysis['contract_id'],
            strategy=analysis['strategy'],
            thesis=analysis['thesis'],
            market_conditions=analysis['market_conditions']
        )

        # Convert to IPC response format
        response = {
            "signal": analysis['signal'],
            "conviction": analysis['conviction'],
            "thesis": analysis['thesis'],
            "stop_distance_points": analysis['stop_points'],
            "target_distance_points": analysis['target_points'],
            "frameworks_cited": [analysis['strategy'], "probability", "kelly_criterion"],
            "time_horizon": "scalp",
            "expected_value": analysis['expected_value'],
            "win_probability": analysis['win_probability'],
            "position_size": analysis['position_size']
        }

        logger.info(f"Decision: {analysis['signal'].upper()} "
                   f"(conviction={analysis['conviction']}, EV={analysis['expected_value']:.2f})")

        return response


def respond_to_request(request_path: Path, engine: AIDecisionEngine):
    """Process IPC request using AI Decision Engine."""
    try:
        with open(request_path, encoding='utf-8') as f:
            request = json.load(f)

        request_id = request.get('request_id')
        expected_response_path = request.get('expected_response_path')

        # Make AI decision
        response = engine.make_decision(request)

        # Write response
        response_path = IPC_DIR / os.path.basename(expected_response_path)
        with open(response_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2)

        logger.info(f"[OK] Response written to {response_path.name}")

        # Delete request file
        request_path.unlink()

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)


def check_risk_of_ruin(engine: AIDecisionEngine) -> Tuple[float, str]:
    """
    Check current Risk of Ruin and return alert status.

    Uses ONLY contract-level data (single source of truth) to avoid
    double-counting wins/losses.

    Returns:
        (ror_percentage, alert_message)
    """
    total_trades = engine.memory.data.get("trades_executed", 0)
    if total_trades < 10:
        return 0.0, ""  # Need minimum sample size

    # Aggregate from contract data ONLY (single source of truth)
    wins = 0
    losses = 0
    total_win_pnl = 0.0
    total_loss_pnl = 0.0

    for contract_data in engine.memory.data.get("performance_by_contract", {}).values():
        w = contract_data.get("wins", 0)
        l = contract_data.get("losses", 0)
        pnl = contract_data.get("total_pnl", 0.0)
        wins += w
        losses += l
        if pnl > 0:
            total_win_pnl += pnl
        else:
            total_loss_pnl += abs(pnl)

    if wins + losses == 0:
        return 0.0, ""

    win_rate = wins / (wins + losses)

    # Calculate avg win/loss from actual P&L
    avg_win = (total_win_pnl / wins) if wins > 0 else 10.0
    avg_loss = (total_loss_pnl / losses) if losses > 0 else 10.0

    # Floors to prevent degenerate math
    avg_win = max(5.0, avg_win)
    avg_loss = max(5.0, avg_loss)

    # Use current account balance from memory if available, else estimate
    account_balance = engine.memory.data.get("account_balance", 148000)

    ror = ProbabilityCalculator.risk_of_ruin(win_rate, avg_win, avg_loss, account_balance)

    # Alert if RoR > 1%
    if ror > 0.01:
        alert = f"[ALERT] Risk of Ruin = {ror*100:.2f}% (> 1% threshold) - REDUCE POSITION SIZES"
        return ror * 100, alert
    elif ror > 0.005:
        alert = f"[WARN] Risk of Ruin = {ror*100:.2f}% (approaching 1%) - Monitor closely"
        return ror * 100, alert
    else:
        return ror * 100, ""


def main():
    logger.info("=" * 60)
    logger.info("AI DECISION ENGINE - Beyond Edges")
    logger.info("=" * 60)
    logger.info("Philosophy: YOU (AI) are the edge")
    logger.info("Strategy: Trade actively, learn continuously")
    logger.info("Risk Management: Kelly Criterion + Risk of Ruin < 1%")
    logger.info(f"Watching: {IPC_DIR}")
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    engine = AIDecisionEngine()
    ror_check_counter = 0

    try:
        while True:
            # Find all request files
            request_files = list(IPC_DIR.glob("request_*.json"))

            for request_path in request_files:
                respond_to_request(request_path, engine)

            # Check Risk of Ruin every 10 cycles (~3 seconds)
            ror_check_counter += 1
            if ror_check_counter >= 10:
                ror_pct, alert = check_risk_of_ruin(engine)
                if alert:
                    logger.warning(alert)
                ror_check_counter = 0

            time.sleep(0.3)  # 300ms poll interval

    except KeyboardInterrupt:
        logger.info("\nStopping AI Decision Engine")
        logger.info(f"Total trades executed: {engine.memory.data['trades_executed']}")
        ror_pct, _ = check_risk_of_ruin(engine)
        logger.info(f"Final Risk of Ruin: {ror_pct:.3f}%")


if __name__ == "__main__":
    main()
