"""Fix ZoneInfoNotFoundError: America/Chicago on Windows (no tzdata package)."""
import sys, py_compile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'C:\KAI\sovran_v2\ipc\ai_decision_engine.py', 'r', encoding='utf-8', errors='replace') as f:
    c = f.read()

OLD = (
    '        from zoneinfo import ZoneInfo\n'
    '        ct_now = datetime.now(ZoneInfo("America/Chicago"))'
)

NEW = (
    '        # Windows may lack tzdata; fall back to UTC-6 offset (CT)\n'
    '        try:\n'
    '            from zoneinfo import ZoneInfo\n'
    '            ct_now = datetime.now(ZoneInfo("America/Chicago"))\n'
    '        except Exception:\n'
    '            from datetime import timedelta\n'
    '            ct_now = datetime.now(timezone.utc) - timedelta(hours=6)'
)

if OLD in c:
    c2 = c.replace(OLD, NEW, 1)
    with open(r'C:\KAI\sovran_v2\ipc\ai_decision_engine.py', 'w', encoding='utf-8') as f:
        f.write(c2)
    py_compile.compile(r'C:\KAI\sovran_v2\ipc\ai_decision_engine.py', doraise=True)
    print('Patched timezone fix. Syntax OK.')
else:
    # Show what's around line 522 so we can find the right string
    lines = c.split('\n')
    for i in range(518, 530):
        print(f'{i+1}: {repr(lines[i])}')
    print('ERROR: OLD string not found')
