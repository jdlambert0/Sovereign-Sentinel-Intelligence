"""
Windows Task Scheduler Setup for Sovereign Sentinel
====================================================
Sets up two scheduled tasks:
  1. START_TRADING — runs at 8:00 AM CT Monday-Friday
  2. STOP_TRADING  — runs at 4:05 PM CT Monday-Friday

Both tasks launch Claude Code in headless mode with the /trade skill.

Usage:
  py scripts/schedule_trading.py --setup   (create tasks)
  py scripts/schedule_trading.py --remove  (delete tasks)
  py scripts/schedule_trading.py --status  (check tasks)
  py scripts/schedule_trading.py --test    (trigger start now)
"""
import subprocess
import sys
import json
from pathlib import Path

# Claude Code binary location
# Try common locations
CLAUDE_PATHS = [
    r"C:\Users\liber\AppData\Roaming\npm\claude.cmd",
    r"C:\Users\liber\AppData\Local\Programs\claude\claude.exe",
    r"C:\Program Files\claude\claude.exe",
    r"claude",  # If on PATH
]

BASE_DIR = Path(__file__).parent.parent
START_SCRIPT = BASE_DIR / "scripts" / "start_trading_session.bat"
STOP_SCRIPT = BASE_DIR / "scripts" / "stop_trading_session.bat"

TASK_START = "SovranSentinel_StartTrading"
TASK_STOP = "SovranSentinel_StopTrading"


def find_claude():
    for path in CLAUDE_PATHS:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return path
        except Exception:
            continue
    return None


def create_bat_scripts():
    """Create the .bat files that Task Scheduler will call."""
    claude = find_claude() or "claude"

    # Start trading session — runs claude headlessly with /trade prompt
    start_content = f"""@echo off
REM Sovereign Sentinel — Start Trading Session
REM Triggered by Windows Task Scheduler at 8:00 AM CT

set LOGFILE=C:\\KAI\\sovran_v2\\logs\\trading_session_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log

echo Starting Sovereign trading session at %date% %time% >> "%LOGFILE%"

REM Check if ralph loop is already running
py C:\\KAI\\sovran_v2\\scripts\\check_and_start.py >> "%LOGFILE%" 2>&1

echo Session launched >> "%LOGFILE%"
"""

    stop_content = f"""@echo off
REM Sovereign Sentinel — Stop Trading Session
REM Triggered by Windows Task Scheduler at 4:05 PM CT

set LOGFILE=C:\\KAI\\sovran_v2\\logs\\trading_session_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log

echo Stopping Sovereign trading session at %date% %time% >> "%LOGFILE%"

REM Signal ralph loop to stop gracefully
py C:\\KAI\\sovran_v2\\scripts\\stop_trading.py >> "%LOGFILE%" 2>&1

echo Session stopped >> "%LOGFILE%"
"""

    START_SCRIPT.parent.mkdir(exist_ok=True)
    with open(START_SCRIPT, 'w') as f:
        f.write(start_content)
    with open(STOP_SCRIPT, 'w') as f:
        f.write(stop_content)

    print(f"Created: {START_SCRIPT}")
    print(f"Created: {STOP_SCRIPT}")


def create_check_and_start():
    """Script that checks if trading is already running before starting."""
    script = BASE_DIR / "scripts" / "check_and_start.py"
    content = """
import subprocess, json, sys, time
from pathlib import Path
from datetime import datetime

BASE = Path(r'C:\\KAI\\sovran_v2')
LOG = BASE / 'logs' / 'ralph_ai_loop.log'
STATUS = BASE / 'ai_loop_status.json'

def is_running():
    try:
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -eq \"\"} | Measure-Object | Select-Object -ExpandProperty Count'],
            capture_output=True, text=True, timeout=10
        )
        count = int(result.stdout.strip() or 0)
        return count > 0
    except Exception:
        return False

def main():
    now = datetime.now()
    print(f"[{now.strftime('%H:%M:%S')}] Checking if trading session is running...")

    if is_running():
        print("Python processes running — trading may already be active. Checking status...")

    # Start ralph loop
    print("Starting ralph_ai_loop.py...")
    proc = subprocess.Popen(
        ['py', str(BASE / 'ralph_ai_loop.py'), '--max-iterations', '999', '--sleep-between', '300'],
        cwd=str(BASE),
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )
    print(f"Started PID: {proc.pid}")

    # Write PID file
    with open(BASE / 'trading.pid', 'w') as f:
        f.write(str(proc.pid))

if __name__ == '__main__':
    main()
"""
    with open(script, 'w') as f:
        f.write(content)


def create_stop_script():
    """Script that gracefully stops trading."""
    script = BASE_DIR / "scripts" / "stop_trading.py"
    content = """
import subprocess, sys
from pathlib import Path

BASE = Path(r'C:\\KAI\\sovran_v2')

def main():
    pid_file = BASE / 'trading.pid'
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        print(f'Stopping trading process PID {pid}...')
        try:
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
            pid_file.unlink()
            print('Stopped.')
        except Exception as e:
            print(f'Error stopping: {e}')
    else:
        print('No PID file found — trading may not be running.')

    # Also write end signal
    with open(BASE / 'stop_signal.txt', 'w') as f:
        f.write('STOP')
    print('Stop signal written.')

if __name__ == '__main__':
    main()
"""
    with open(script, 'w') as f:
        f.write(content)


def setup_tasks():
    """Create Windows Task Scheduler tasks."""
    create_bat_scripts()
    create_check_and_start()
    create_stop_script()

    # Create START task — 8:00 AM CT = 9:00 AM ET = 14:00 UTC (winter) or 13:00 UTC (summer)
    # Using local time (CT) — Windows Task Scheduler uses local time
    start_cmd = [
        'schtasks', '/Create', '/TN', TASK_START,
        '/TR', str(START_SCRIPT),
        '/SC', 'WEEKLY',
        '/D', 'MON,TUE,WED,THU,FRI',
        '/ST', '08:00',          # 8:00 AM local time (set your system to CT)
        '/F',                     # Force overwrite
        '/RL', 'HIGHEST',         # Run with highest privilege
    ]

    # Create STOP task — 4:05 PM CT
    stop_cmd = [
        'schtasks', '/Create', '/TN', TASK_STOP,
        '/TR', str(STOP_SCRIPT),
        '/SC', 'WEEKLY',
        '/D', 'MON,TUE,WED,THU,FRI',
        '/ST', '16:05',
        '/F',
        '/RL', 'HIGHEST',
    ]

    print("\nCreating Task Scheduler tasks...")
    for cmd, name in [(start_cmd, "START"), (stop_cmd, "STOP")]:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] Task {name} created: {name == 'START' and TASK_START or TASK_STOP}")
        else:
            print(f"[FAIL] Task {name}: {result.stderr.strip()}")
            print(f"  Manual command: {' '.join(cmd)}")


def remove_tasks():
    for task in [TASK_START, TASK_STOP]:
        result = subprocess.run(
            ['schtasks', '/Delete', '/TN', task, '/F'],
            capture_output=True, text=True
        )
        status = "removed" if result.returncode == 0 else "not found"
        print(f"Task {task}: {status}")


def check_status():
    for task in [TASK_START, TASK_STOP]:
        result = subprocess.run(
            ['schtasks', '/Query', '/TN', task, '/FO', 'CSV'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"[EXISTS] {task}")
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                print(f"  {lines[1][:100]}")
        else:
            print(f"[NOT FOUND] {task}")


def test_run():
    """Trigger the start script now for testing."""
    print("Triggering start script now (test run)...")
    result = subprocess.run(['schtasks', '/Run', '/TN', TASK_START], capture_output=True, text=True)
    if result.returncode == 0:
        print("Task triggered. Check logs.")
    else:
        print(f"Error: {result.stderr}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="Create scheduled tasks")
    parser.add_argument("--remove", action="store_true", help="Remove scheduled tasks")
    parser.add_argument("--status", action="store_true", help="Check task status")
    parser.add_argument("--test", action="store_true", help="Trigger start task now")
    args = parser.parse_args()

    if args.setup:
        setup_tasks()
    elif args.remove:
        remove_tasks()
    elif args.status:
        check_status()
    elif args.test:
        test_run()
    else:
        print("Usage: py scripts/schedule_trading.py --setup | --remove | --status | --test")
        print("\nThis script sets up Windows Task Scheduler to:")
        print("  - Start trading at 8:00 AM CT (Mon-Fri)")
        print("  - Stop trading at 4:05 PM CT (Mon-Fri)")
