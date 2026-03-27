"""
Fix session trade limits:
- src/decision.py: raise max_trades_per_session 20 -> 50
- live_session_v4.py: raise MAX_TRADES_SESSION 8 -> 20
- live_session_v5.py: raise MAX_TRADES_SESSION 8 -> 20
Also resets the ai_decision_engine session counter by touching the reset trigger.
"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

changes = []

# 1. src/decision.py — raise max_trades_per_session
with open(r'C:\KAI\sovran_v2\src\decision.py', 'r', encoding='utf-8', errors='replace') as f:
    c = f.read()
new_c = c.replace(
    'max_trades_per_session: int = 20',
    'max_trades_per_session: int = 50'
)
if new_c != c:
    with open(r'C:\KAI\sovran_v2\src\decision.py', 'w', encoding='utf-8') as f:
        f.write(new_c)
    changes.append('src/decision.py: max_trades_per_session 20 -> 50')
else:
    changes.append('src/decision.py: already patched or not found')

# 2. live_session_v4.py
for fname in [r'C:\KAI\sovran_v2\live_session_v4.py', r'C:\KAI\sovran_v2\live_session_v5.py']:
    with open(fname, 'r', encoding='utf-8', errors='replace') as f:
        c = f.read()
    new_c = re.sub(r'MAX_TRADES_SESSION\s*=\s*8', 'MAX_TRADES_SESSION = 20', c)
    new_c = re.sub(r'MAX_TRADES_SESSION\s*=\s*6', 'MAX_TRADES_SESSION = 20', new_c)
    if new_c != c:
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(new_c)
        short = fname.split('\\')[-1]
        changes.append(f'{short}: MAX_TRADES_SESSION -> 20')
    else:
        short = fname.split('\\')[-1]
        changes.append(f'{short}: already at limit or not found')

print('Changes made:')
for ch in changes:
    print(f'  [OK] {ch}')

# 3. Verify syntax
import py_compile
for f in [r'C:\KAI\sovran_v2\src\decision.py',
          r'C:\KAI\sovran_v2\live_session_v4.py',
          r'C:\KAI\sovran_v2\live_session_v5.py']:
    try:
        py_compile.compile(f, doraise=True)
        print(f'  [OK] syntax: {f.split(chr(92))[-1]}')
    except py_compile.PyCompileError as e:
        print(f'  [FAIL] syntax: {e}')

# 4. Reset the session counter in the running engine by writing a reset signal file
import json, os
reset_path = r'C:\KAI\sovran_v2\ipc\reset_session.json'
with open(reset_path, 'w') as f:
    json.dump({'reset_trade_count': True, 'timestamp': __import__('time').time()}, f)
print(f'  [OK] Reset signal written to {reset_path}')
print('\nNOTE: Restart ai_decision_engine.py (PID 23004) to pick up new limit + reset counter.')
print('      OR: Kill PID 23004 and re-run: python ipc/ai_decision_engine.py')
