
"""
SAE 5.8 - WFA Validation Runner
Executes BrainFlux (MNQ) and BrainMR2 (MES) on native DBN Tick Data.
"""

import sys
import glob
import os
import json
from decimal import Decimal
from databento_loader import DatabentoLoader
from sae_types import MarketProfile
from backtest_broker import BacktestBroker

# Import Brains
sys.path.append('./brains') 
from brains.brain_flux import BrainFlux
from brains.brain_mr2 import BrainMR2
from brains.brain_robinson import BrainRobinson
from brains.brain_recursive import BrainRecursive
from brains.brain_momentum import BrainMomentum
from brains.brain_apex_defensive import BrainApexDefensive
from brains.brain_meta_scout import BrainMetaScout

def main():
    print("\n" + "="*80)
    print("SAE 5.8 - WALK-FORWARD VALIDATION (DBN TICK DATA)")
    print("Regime: Trend (MNQ) vs Reversion (MES)")
    print("="*80)

    # 1. Discovery Phase
    data_dir = "c:/KAI/g/"
    dbn_files = glob.glob(os.path.join(data_dir, "*.mbp-10.dbn"))
    
    if not dbn_files:
        print("[X] No .dbn files found. Please run download_micros.py")
        return

    # 2. Strategy Mapping (Council Governance)
    # Define which brains run on which ticker substring
    strategy_map = {
    "MNQ": {
    "brains": [BrainFlux, BrainRobinson, BrainRecursive, BrainMomentum],
    "tick_size": 0.25,
    "tick_value": 0.50
    },
    "MES": {
        "brains": [BrainMR2, BrainMetaScout, BrainApexDefensive],
    "tick_size": 0.25,
    "tick_value": 1.25
    }
    }

    results = []
    cumulative_pnl = Decimal("0.00")
    daily_results = []

    for idx, file_path in enumerate(sorted(dbn_files)):
        filename = os.path.basename(file_path)
        if "MNQ" not in filename: continue # Focus on MNQ for profit target chase

        # PHASE 6: Extract date from filename for tracking
        import re
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', filename)
        file_date = date_match.group(0) if date_match else f"File_{idx+1}"

        print(f"\n[BACKTEST] Processing file {idx+1}: {filename} (Date: {file_date})")

        # PHASE 6: Reset broker daily counters if not first file
        if idx > 0:
            print(f"[BACKTEST] Resetting daily PnL for new trading day")

        print(f"\n[FILE] Processing: {filename}")

        # Detect Ticker
        target_ticker = None
        if "MNQ" in filename: target_ticker = "MNQ"
        elif "MES" in filename: target_ticker = "MES"

        if not target_ticker:
            print(f"[WARN] Unknown ticker in filename, skipping.")
            continue

        config_data = strategy_map.get(target_ticker)

        # Initialize System (Council)
        council_brains = [cls(target_ticker) for cls in config_data["brains"]]
        broker = BacktestBroker(tick_size=config_data["tick_size"], tick_value=config_data["tick_value"])
        profile = MarketProfile(target_ticker)
        loader = DatabentoLoader(file_path, ticker=target_ticker)

        print(f"   -> Council active with {len(council_brains)} brains.")

        # Execution Loop
        record_count = 0
        max_size_seen = 0
        try:
            for l2_state, trade in loader.load_records():
                if record_count >= 1000000: break
                if trade.size > max_size_seen: max_size_seen = trade.size
                
                # Update Market State
                if trade.size > 0:
                    profile.update(trade.price, trade.size)

                # Check Daily Limits (Hard stops at -350, Soft at -325)
                broker.update(l2_state, trade)
                
                # Sync total PnL to all brains for Metascouter/Risk logic
                total_pnl = broker.realized_pnl + broker.unrealized_pnl
                
                signals = []
                votes = {"Long": 0, "Short": 0}

                # Brain Logic (Council Voting)
                for brain in council_brains:
                    brain.daily_pnl = total_pnl
                    try:
                        signal = brain.on_market_update(l2_state, profile, trade)   
                        if signal:
                            print(f"     [BRAIN] {brain.name} Signal: {signal.get('direction')} ({signal.get('reason')})")
                            signal['brain'] = brain.name
                            signals.append(signal)
                            if signal.get('direction') == 'EXIT': continue # Exits skip voting
                            
                            dir_key = "Long" if signal.get('direction') in [1, "Long", "BUY"] else "Short"
                            votes[dir_key] += 1
                    except Exception as logic_err:
                        pass

                # Metascouter: Council Consensus (BFT)
                for sig in signals:
                    if sig.get('direction') == 'EXIT':
                        broker.execute_signal(sig, l2_state, trade)
                        continue
                    
                    # Requirement: At least 2 brains must agree, OR high conviction (Violent Grace)
                    direction = "Long" if sig.get('direction') in [1, "Long", "BUY"] else "Short"
                    conviction = sig.get('conviction', 0)
                    
                    if votes[direction] >= 2 or conviction >= 0.95:
                        broker.execute_signal(sig, l2_state, trade)
                    else:
                        # Log veto occasionally
                        if record_count % 50000 == 0 and votes[direction] > 0:
                            print(f"     [BFT] VETO: No consensus for {direction} ({votes[direction]} votes, conviction {conviction:.2f})")

                record_count += 1
                if record_count % 100000 == 0:
                    main_brain = council_brains[0]
                    print(f"     ... {record_count:,} ticks ... PnL: ${total_pnl:.2f} | Regime: {main_brain.regime} | WhaleVol: {profile.whale_volume} | MaxSize: {max_size_seen}")

        except Exception as e:
            print(f"[X] Loader Error: {e}")
            
        # Session Result
        pnl = broker.realized_pnl + broker.unrealized_pnl
        print(f"   [RESULT] Result: ${pnl:.2f} | Trades: {broker.trade_count} | MaxDD: ${broker.max_drawdown:.2f}")

        # PHASE 6: Track daily and cumulative results
        daily_results.append({
            "date": file_date,
            "daily_pnl": pnl,
            "cumulative_pnl": cumulative_pnl + pnl,
            "trades": broker.trade_count,
            "limit_status": "✅ Target" if pnl >= Decimal("1000.00") else "❌ Limit" if pnl <= Decimal("-350.00") else "📊 Active"
        })
        cumulative_pnl += pnl

        results.append({
            "file": filename,
            "strategy": "Council_4B",
            "pnl": float(pnl),
            "trades": broker.trade_count,
            "win_rate": (broker.win_count / broker.trade_count * 100) if broker.trade_count > 0 else 0,
            "max_dd": float(broker.max_drawdown),
            "date": file_date
        })

    # PHASE 6: Enhanced multi-day summary with daily limits tracking
    print("\n" + "="*80)
    print("MULTI-DAY BACKTEST SUMMARY (Daily Limits: +$1000 / -$350)")
    print("="*80)
    print(f"{'Date':<12} | {'Daily PnL':<11} | {'Cumulative':<11} | {'Trades':<7} | {'Status':<10}")
    print("-" * 80)

    for result in daily_results:
        print(f"{result['date']:<12} | ${result['daily_pnl']:>10.2f} | ${result['cumulative_pnl']:>10.2f} | {result['trades']:>7} | {result['limit_status']:<10}")

    print("="*80)
    print(f"FINAL CUMULATIVE PnL: ${cumulative_pnl:.2f}")
    print(f"Trading Days: {len(daily_results)}")

    # Calculate stats
    profit_days = sum(1 for r in daily_results if r['daily_pnl'] > 0)
    loss_days = sum(1 for r in daily_results if r['daily_pnl'] < 0)
    target_days = sum(1 for r in daily_results if r['daily_pnl'] >= Decimal("1000.00"))
    limit_days = sum(1 for r in daily_results if r['daily_pnl'] <= Decimal("-350.00"))

    print(f"Profitable Days: {profit_days}/{len(daily_results)} ({profit_days/len(daily_results)*100:.1f}%)")
    print(f"Target Hit Days (+$1000): {target_days}")
    print(f"Limit Hit Days (-$350): {limit_days}")
    print("="*80)

if __name__ == "__main__":
    main()

