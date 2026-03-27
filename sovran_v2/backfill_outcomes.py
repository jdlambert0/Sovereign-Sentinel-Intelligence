"""
Backfill today's trade outcomes from live_session_v4.log into ai_trading_memory.json.
Parses [W] CLOSED / [L] CLOSED lines and calls record_trade_outcome.record_outcome().
"""
import sys
import re
import os
sys.path.insert(0, str(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from ipc.record_trade_outcome import record_outcome

LOG = r'C:\KAI\sovran_v2\live_session_v4.log'

# Pattern: [W] CLOSED: LONG MNQ | PnL: $+76.52 (153t) | TRAIL_STOP
# We need contract and PnL. Regime/strategy are unknown from log, default to 'unknown'/'momentum'
CLOSE_RE = re.compile(
    r'\[(?P<wl>[WL-])\] CLOSED: (?P<side>LONG|SHORT) (?P<sym>\w+) \| PnL: \$(?P<pnl>[+\-]?\d+\.?\d*)'
)
HOLD_RE = re.compile(r'Hold: (?P<hold>\d+\.?\d*)s')

# Map short symbols to full contract IDs (M26 = June 2026)
SYM_TO_CONTRACT = {
    'MNQ': 'CON.F.US.MNQ.M26',
    'MES': 'CON.F.US.MES.M26',
    'MYM': 'CON.F.US.MYM.M26',
    'M2K': 'CON.F.US.M2K.M26',
    'MGC': 'CON.F.US.MGC.M26',
    'MCL': 'CON.F.US.MCL.M26',
}

trades_backfilled = 0
wins = 0
losses = 0

with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

i = 0
while i < len(lines):
    line = lines[i]
    m = CLOSE_RE.search(line)
    if m:
        wl = m.group('wl')
        sym = m.group('sym')
        pnl = float(m.group('pnl'))

        # Look ahead for Hold time
        hold_time = 180.0  # default 3 min if not found
        for j in range(i+1, min(i+5, len(lines))):
            hm = HOLD_RE.search(lines[j])
            if hm:
                hold_time = float(hm.group('hold'))
                break

        contract = SYM_TO_CONTRACT.get(sym, f'CON.F.US.{sym}.M26')

        # Infer strategy: if trending => momentum, if ranging => mean_reversion
        # Default to momentum since most entries are trend-following
        strategy = 'momentum'
        regime = 'unknown'

        try:
            record_outcome(contract, strategy, regime, pnl, hold_time)
            trades_backfilled += 1
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
        except Exception as e:
            print(f'  WARN: failed to record {sym} ${pnl}: {e}')
    i += 1

print(f'\nBackfill complete: {trades_backfilled} trades recorded ({wins}W / {losses}L)')
print(f'Win rate: {wins/max(trades_backfilled,1)*100:.1f}%')
