#!/usr/bin/env python3
"""Patch ralph_ai_loop.py: replace run_ai_trading_session with correct implementation."""

new_func = '''def _is_engine_running() -> bool:
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'cmdline']):
            cmdline = proc.info.get('cmdline') or []
            if any('ai_decision_engine' in str(c) for c in cmdline):
                return True
    except Exception:
        pass
    return False


def _is_session_running() -> bool:
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'cmdline']):
            cmdline = proc.info.get('cmdline') or []
            if any('live_session_v' in str(c) for c in cmdline):
                return True
    except Exception:
        pass
    return False


def run_ai_trading_session(cycles: int = 360, interval: int = 10) -> Tuple[bool, Dict]:
    """
    Run an AI trading session using V5 Goldilocks + ai_decision_engine.py.

    Architecture:
    - ai_decision_engine.py: Full Kelly+Bayesian AI brain (file IPC)
    - live_session_v5.py: V5 Goldilocks with OFI+VPIN gates
    - Smart: if session already running, monitor it instead of re-launching
    """
    logger.info("[LAUNCH] AI trading session starting (%d cycles x %ds)", cycles, interval)
    ai_engine_process = None

    # Ensure AI Decision Engine is running
    if _is_engine_running():
        logger.info("[OK] ai_decision_engine already running - reusing existing instance")
    else:
        logger.info("[LAUNCH] Starting ai_decision_engine.py...")
        ai_engine_log = open("ai_engine.log", "a", encoding="utf-8")
        ai_engine_process = subprocess.Popen(
            [sys.executable, "ipc/ai_decision_engine.py"],
            stdout=ai_engine_log,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT)
        )
        time.sleep(2)
        logger.info("[OK] AI engine started (PID %d)", ai_engine_process.pid)

    # If a trading session is already running, just monitor it
    success = False
    if _is_session_running():
        logger.info("[OK] Trading session already running - monitoring for %ds", min(cycles * interval, 600))
        time.sleep(min(cycles * interval, 600))
        success = True
    else:
        # Launch V5 Goldilocks
        logger.info("[LAUNCH] Starting live_session_v5.py...")
        try:
            v5_log = open("live_session_v5_loop.log", "a", encoding="utf-8")
            v5_proc = subprocess.Popen(
                [sys.executable, "live_session_v5.py",
                 "--cycles", str(cycles), "--interval", str(interval)],
                stdout=v5_log,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT)
            )
            logger.info("[OK] V5 Goldilocks started (PID %d)", v5_proc.pid)
            try:
                v5_proc.wait(timeout=cycles * interval + 300)
                success = v5_proc.returncode == 0
                if success:
                    logger.info("[OK] V5 session completed successfully")
                else:
                    logger.error("[ERROR] V5 exited with code %d", v5_proc.returncode)
            except subprocess.TimeoutExpired:
                logger.warning("[WARN] V5 session timed out - terminating")
                v5_proc.terminate()
                success = False
        except Exception as e:
            logger.error("[ERROR] Failed to launch V5: %s", e)

    # Load memory results
    memory_file = PROJECT_ROOT / "state" / "ai_trading_memory.json"
    results = {"trades_executed": 0, "strategies_tested": 0, "total_pnl": 0.0}
    if memory_file.exists():
        try:
            with open(memory_file, encoding="utf-8") as f:
                mem = json.load(f)
            results = {
                "trades_executed": mem.get("trades_executed", 0),
                "strategies_tested": len(mem.get("strategies_tested", {})),
                "total_pnl": mem.get("total_pnl", 0.0)
            }
        except Exception as e:
            logger.error("[ERROR] Load memory failed: %s", e)

    return True, results


'''

with open('C:/KAI/sovran_v2/ralph_ai_loop.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('def run_ai_trading_session')
end_idx = content.find('def update_obsidian')

if start_idx < 0 or end_idx < 0:
    print(f"ERROR: markers not found start={start_idx} end={end_idx}")
    exit(1)

new_content = content[:start_idx] + new_func + content[end_idx:]

with open('C:/KAI/sovran_v2/ralph_ai_loop.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"SUCCESS: run_ai_trading_session replaced ({start_idx}-{end_idx} -> {len(new_func)} chars)")
