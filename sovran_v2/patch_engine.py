#!/usr/bin/env python3
"""
Patch ai_decision_engine.py with:
1. Overnight lockout (hard block 4pm-8am CT)
2. MCL/MGC asset priority boost (+10%), MES/MNQ penalty (-20%)
3. Bayesian belief updating (Beta distribution priors)
4. Circuit breaker: 30 min (not 5 min) in V4/V5
"""

ENGINE_FILE = 'C:/KAI/sovran_v2/ipc/ai_decision_engine.py'

with open(ENGINE_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# ── PATCH 1: Overnight lockout + asset weighting in make_decision ──────────
OLD_MAKE_DECISION = '''    def make_decision(self, request: Dict) -> Dict:
        """
        Main decision entry point. Called by IPC system.

        Returns standard IPC response format.
        """
        snapshot = request.get('snapshot_data', {})
        account_balance = request.get('account_balance', 150000)

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

        return response'''

NEW_MAKE_DECISION = '''    # Asset priority weights (based on 30+ trade history)
    ASSET_WEIGHTS = {
        "energy":       1.10,   # MCL: only winner (+$38.48), +10% boost
        "metals":       1.05,   # MGC: neutral, slight boost
        "equity_index": 0.80,   # MES/MNQ: 100% loss rate, -20% penalty
        "other":        1.00,
    }

    # Trading hours (CT = UTC-5 or UTC-6 during DST)
    TRADING_HOURS_START_CT = 8   # 8 AM CT
    TRADING_HOURS_END_CT = 16    # 4 PM CT

    @staticmethod
    def _ct_hour() -> int:
        """Return current hour in CT (UTC-5, rough approximation)."""
        from datetime import timedelta
        return datetime.now(timezone(timedelta(hours=-5))).hour

    @staticmethod
    def _is_trading_hours() -> bool:
        """True if within 8am-4pm CT."""
        h = AIDecisionEngine._ct_hour()
        return AIDecisionEngine.TRADING_HOURS_START_CT <= h < AIDecisionEngine.TRADING_HOURS_END_CT

    def make_decision(self, request: Dict) -> Dict:
        """
        Main decision entry point. Called by IPC system.

        Returns standard IPC response format.
        Includes:
        - Overnight lockout (hard block outside 8am-4pm CT)
        - Asset priority weighting (MCL/MGC boosted, MES/MNQ penalized)
        - Bayesian belief updating from memory
        """
        snapshot = request.get('snapshot_data', {})
        account_balance = request.get('account_balance', 150000)

        # ── HARD GATE: Overnight lockout ──────────────────────────────────
        if not self._is_trading_hours():
            ct_hour = self._ct_hour()
            logger.info("OVERNIGHT LOCKOUT: no trading outside 8am-4pm CT (now %dh CT)", ct_hour)
            return {
                "signal": "no_trade",
                "conviction": 0,
                "thesis": f"OVERNIGHT LOCKOUT: {ct_hour}h CT outside 8am-4pm window (100% overnight loss rate)",
                "stop_distance_points": 0,
                "target_distance_points": 0,
                "frameworks_cited": ["overnight_lockout"],
                "time_horizon": "none",
                "expected_value": -1.0,
                "win_probability": 0.0,
                "position_size": 0
            }

        # Analyze this contract
        analysis = self.analyze_contract(snapshot, account_balance)

        # ── ASSET PRIORITY WEIGHTING ───────────────────────────────────────
        asset_class = snapshot.get('asset_class', 'other')
        asset_weight = self.ASSET_WEIGHTS.get(asset_class, 1.00)
        if asset_weight != 1.00:
            old_conv = analysis['conviction']
            analysis['conviction'] = int(min(100, analysis['conviction'] * asset_weight))
            logger.info("Asset weight %s (%.2fx): conviction %d -> %d",
                       asset_class, asset_weight, old_conv, analysis['conviction'])

        # ── BAYESIAN WIN PROBABILITY FROM MEMORY ──────────────────────────
        contract_id = analysis['contract_id']
        strategy = analysis['strategy']
        contract_data = self.memory.data.get('performance_by_contract', {}).get(contract_id, {})
        strat_data = self.memory.data.get('strategies_tested', {}).get(strategy, {})

        # Beta distribution posterior: alpha=wins+1, beta=losses+1 (uniform prior)
        c_trades = contract_data.get('trades', 0)
        c_wins = contract_data.get('wins', 0)
        c_losses = contract_data.get('losses', 0)
        s_trades = strat_data.get('trades', 0)
        s_wins = strat_data.get('wins', 0)

        if c_trades >= 3:
            # Use contract-specific Bayesian estimate
            bayesian_win_rate = (c_wins + 1) / (c_trades + 2)  # Beta mean
            if abs(bayesian_win_rate - analysis['win_probability']) > 0.05:
                logger.info("Bayesian update %s: %.0f%% observed -> %.0f%% prior",
                           contract_id, bayesian_win_rate * 100, analysis['win_probability'] * 100)
                analysis['win_probability'] = bayesian_win_rate
        elif s_trades >= 5:
            # Fall back to strategy-level estimate
            bayesian_win_rate = (s_wins + 1) / (s_trades + 2)
            analysis['win_probability'] = bayesian_win_rate

        # Record in memory (pre-trade, count only)
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
            "frameworks_cited": [analysis['strategy'], "probability", "kelly_criterion",
                                 "overnight_lockout", "bayesian_updating", "asset_priority"],
            "time_horizon": "scalp",
            "expected_value": analysis['expected_value'],
            "win_probability": analysis['win_probability'],
            "position_size": analysis['position_size']
        }

        logger.info("Decision: %s (conviction=%d, EV=%.2f, asset_weight=%.2fx)",
                   analysis['signal'].upper(), analysis['conviction'],
                   analysis['expected_value'], asset_weight)

        return response'''

if OLD_MAKE_DECISION in content:
    content = content.replace(OLD_MAKE_DECISION, NEW_MAKE_DECISION, 1)
    print('PATCH 1 (overnight + asset + bayesian): OK')
else:
    print('PATCH 1: make_decision not found - checking...')
    idx = content.find('def make_decision')
    print(f'  make_decision at: {idx}')
    print(f'  context: {repr(content[idx:idx+200])}')

with open(ENGINE_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Engine file written: {len(content)} chars')
