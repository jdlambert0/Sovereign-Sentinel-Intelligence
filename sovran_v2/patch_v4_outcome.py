"""Patch live_session_v4.py to add outcome tracking after trade close."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'C:\KAI\sovran_v2\live_session_v4.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

if 'Record outcome to AI trading memory' in content:
    print('V4 already has outcome tracking - skipping.')
    sys.exit(0)

# The block to find (after kaizen rolling stats, before _save_trade_history)
OLD = (
    '        # Phase 3: Log rolling stats\n'
    '        stats = self.kaizen.get_rolling_stats(self.trades)\n'
    '        if stats["count"] >= 3:\n'
    '            logger.info(f"   ROLLING({stats[\\"count\\"]}):'
    ' WR={stats[\\"win_rate\\"]:.'
    '0%} PF={stats[\\"profit_factor\\"]:.'
    '2f} Capture={stats[\\"avg_capture_ratio\\"]:.'
    '1%}")\n'
    '\n'
    '        # Save to trade history\n'
    '        self._save_trade_history(result)'
)

NEW = (
    '        # Phase 3: Log rolling stats\n'
    '        stats = self.kaizen.get_rolling_stats(self.trades)\n'
    '        if stats["count"] >= 3:\n'
    '            logger.info(f"   ROLLING({stats[\\"count\\"]}):'
    ' WR={stats[\\"win_rate\\"]:.'
    '0%} PF={stats[\\"profit_factor\\"]:.'
    '2f} Capture={stats[\\"avg_capture_ratio\\"]:.'
    '1%}")\n'
    '\n'
    '        # Record outcome to AI trading memory (Bayesian learning)\n'
    '        try:\n'
    '            _strategy = "momentum" if "P(continuation)" in pos.thesis else "mean_reversion"\n'
    '            _regime = pos.regime_at_entry if pos.regime_at_entry else "unknown"\n'
    '            import subprocess as _sp\n'
    '            _sp.run([\n'
    '                sys.executable,\n'
    '                str(Path(__file__).parent / "ipc" / "record_trade_outcome.py"),\n'
    '                pos.contract_id,\n'
    '                _strategy,\n'
    '                _regime,\n'
    '                str(trade_pnl),\n'
    '                str(hold_time),\n'
    '                str(getattr(pos, "mfe", 0.0)),\n'
    '                str(getattr(pos, "mae", 0.0)),\n'
    '            ], check=False, timeout=10)\n'
    '        except Exception as _e:\n'
    '            logger.warning(f"Failed to record AI outcome: {_e}")\n'
    '\n'
    '        # Save to trade history\n'
    '        self._save_trade_history(result)'
)

if OLD not in content:
    # Try a simpler find — just locate the _save_trade_history line after _rolling stats
    # Find "# Save to trade history\n        self._save_trade_history(result)" and insert before it
    SIMPLE_OLD = (
        '        # Save to trade history\n'
        '        self._save_trade_history(result)\n'
        '\n'
        '        if cid in self.active_positions:'
    )
    SIMPLE_NEW = (
        '        # Record outcome to AI trading memory (Bayesian learning)\n'
        '        try:\n'
        '            _strategy = "momentum" if "P(continuation)" in pos.thesis else "mean_reversion"\n'
        '            _regime = pos.regime_at_entry if pos.regime_at_entry else "unknown"\n'
        '            import subprocess as _sp\n'
        '            _sp.run([\n'
        '                sys.executable,\n'
        '                str(Path(__file__).parent / "ipc" / "record_trade_outcome.py"),\n'
        '                pos.contract_id,\n'
        '                _strategy,\n'
        '                _regime,\n'
        '                str(trade_pnl),\n'
        '                str(hold_time),\n'
        '                str(getattr(pos, "mfe", 0.0)),\n'
        '                str(getattr(pos, "mae", 0.0)),\n'
        '            ], check=False, timeout=10)\n'
        '        except Exception as _e:\n'
        '            logger.warning(f"Failed to record AI outcome: {_e}")\n'
        '\n'
        '        # Save to trade history\n'
        '        self._save_trade_history(result)\n'
        '\n'
        '        if cid in self.active_positions:'
    )
    if SIMPLE_OLD in content:
        content = content.replace(SIMPLE_OLD, SIMPLE_NEW, 1)
        print('Patched V4 with simple insertion.')
    else:
        print('ERROR: Could not find insertion point in V4.')
        sys.exit(1)
else:
    content = content.replace(OLD, NEW, 1)
    print('Patched V4 with full block replacement.')

with open(r'C:\KAI\sovran_v2\live_session_v4.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Written. Verifying syntax...')
import py_compile
py_compile.compile(r'C:\KAI\sovran_v2\live_session_v4.py', doraise=True)
print('V4 syntax OK.')
