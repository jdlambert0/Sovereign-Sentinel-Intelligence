"""
Kill stale processes and restart V5 + ai_decision_engine cleanly.
- Kills: autonomous_responder (zombie), live_session_v5 (old in-memory limit)
- Restarts: ai_decision_engine, live_session_v5
"""
import subprocess, sys, time, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

KILL_PIDS = [21480, 33428]  # autonomous_responder, live_session_v5
for pid in KILL_PIDS:
    r = subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True)
    print(f'Kill PID {pid}: {r.stdout.strip() or r.stderr.strip()}')

time.sleep(3)

# Restart ai_decision_engine (in case it also needs reload)
engine_log = open(r'C:\KAI\sovran_v2\ai_engine.log', 'a')
p1 = subprocess.Popen(
    [sys.executable, r'C:\KAI\sovran_v2\ipc\ai_decision_engine.py'],
    cwd=r'C:\KAI\sovran_v2',
    stdout=engine_log, stderr=engine_log,
    creationflags=0x00000008
)
print(f'ai_decision_engine restarted: PID {p1.pid}')
time.sleep(2)

# Restart V5
v5_log = open(r'C:\KAI\sovran_v2\live_session_v5.log', 'a')
p2 = subprocess.Popen(
    [sys.executable, r'C:\KAI\sovran_v2\live_session_v5.py', '--cycles', '360', '--interval', '10'],
    cwd=r'C:\KAI\sovran_v2',
    stdout=v5_log, stderr=v5_log,
    creationflags=0x00000008
)
print(f'live_session_v5 restarted: PID {p2.pid}')
print('Done. System restarted cleanly.')
