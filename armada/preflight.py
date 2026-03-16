"""
PREFLIGHT VALIDATION GATE (Stripe Blueprint Engine Principle)
=============================================================
This is a DETERMINISTIC script. No LLM, no AI, no vibes.
It runs hard checks that either PASS or FAIL.

Usage:
    python preflight.py              # Full preflight
    python preflight.py --quick      # Compile + imports only

Every code change MUST pass preflight before being considered "done."
This is the #1 thing that stops endless bug-chasing with AI.
"""

import sys
import os
import json
import importlib
import py_compile
import subprocess
import traceback
from pathlib import Path

# ── CONFIG ──
ARMADA_DIR = Path(r"C:\KAI\armada")
VORTEX_DIR = Path(r"C:\KAI\vortex")
PYTHON = Path(r"C:\KAI\vortex\.venv312\Scripts\python.exe")

CRITICAL_FILES = [
    ARMADA_DIR / "sovran_ai.py",
    VORTEX_DIR / "llm_client.py",
    VORTEX_DIR / "providers" / "openrouter.py",
]

REQUIRED_ENV_KEYS = [
    "VORTEX_LLM_PROVIDER",
    "VORTEX_LLM_API_KEY",
]


# ── RESULTS TRACKING ──
class ValidationResults:
    def __init__(self):
        self.passed_count = 0
        self.failed_count = 0
        self.warn_count = 0
        self.details = []


results = ValidationResults()


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    if passed:
        results.passed_count += 1
    else:
        results.failed_count += 1
    results.details.append({"name": name, "status": status, "detail": detail})
    icon = "+" if passed else "-"
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))


def warn(name, detail=""):
    results.warn_count += 1
    results.details.append({"name": name, "status": "WARN", "detail": detail})
    print(f"  ! {name}" + (f" — {detail}" if detail else ""))


# ── GATE 1: COMPILATION ──
def gate_compile():
    print("\n[GATE 1] COMPILATION")
    for f in CRITICAL_FILES:
        try:
            py_compile.compile(str(f), doraise=True)
            check(f"Compile {f.name}", True)
        except py_compile.PyCompileError as e:
            check(f"Compile {f.name}", False, str(e))


# ── GATE 2: IMPORT CHAIN ──
def gate_imports():
    print("\n[GATE 2] IMPORT CHAIN")
    # Check that sovran_ai.py can resolve its critical imports
    sys.path.insert(0, str(VORTEX_DIR))
    sys.path.insert(0, str(ARMADA_DIR))

    critical_imports = [
        ("llm_client", "complete_ensemble"),
        ("providers.openrouter", "complete"),
    ]
    for mod_name, func_name in critical_imports:
        try:
            mod = importlib.import_module(mod_name)
            func = getattr(mod, func_name, None)
            check(
                f"Import {mod_name}.{func_name}",
                func is not None,
                "Function not found" if func is None else "",
            )
        except Exception as e:
            check(f"Import {mod_name}.{func_name}", False, str(e)[:80])


# ── GATE 3: UNIT TESTS ──
def gate_tests():
    print("\n[GATE 3] UNIT TESTS")
    test_file = ARMADA_DIR / "tests" / "test_sovran_core.py"
    if not test_file.exists():
        check("Test file exists", False, str(test_file))
        return

    try:
        result = subprocess.run(
            [str(PYTHON), str(test_file)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ARMADA_DIR),
        )
        output = result.stdout + result.stderr
        passed = "ALL TESTS PASSED" in output or result.returncode == 0

        # Extract pass/fail counts
        import re

        match = re.search(r"(\d+) PASSED, (\d+) FAILED", output)
        if match:
            p, f = int(match.group(1)), int(match.group(2))
            check(
                f"Unit Tests ({p} passed, {f} failed)",
                f == 0,
                f"{f} tests failed" if f > 0 else "",
            )
        else:
            check(
                "Unit Tests",
                passed,
                "Could not parse results" if passed else output[-200:],
            )
    except subprocess.TimeoutExpired:
        check("Unit Tests", False, "TIMEOUT after 30s")
    except Exception as e:
        check("Unit Tests", False, str(e)[:80])


# ── GATE 4: STRUCTURAL INTEGRITY ──
def gate_structure():
    print("\n[GATE 4] STRUCTURAL INTEGRITY")

    sovran = (ARMADA_DIR / "sovran_ai.py").read_text(encoding="utf-8")

    # Check critical functions exist
    critical_functions = [
        "async def retrieve_ai_decision",
        "async def calculate_size_and_execute",
        "async def monitor_loop",
        "async def run()",
        "def build_prompt",
        "def get_session_phase",
        "class Config",
        "class GamblerState",
        "class AIGamblerEngine",
        "class TrailingDrawdown",
    ]
    for func in critical_functions:
        check(f"Contains '{func}'", func in sovran)

    # Check safety gates exist in monitor_loop
    safety_gates = [
        ("Spread Gate", "max_spread_ticks"),
        ("Session Phase Gate", "SESSION PHASE GATE"),
        ("Stale Data Guard", "STALE DATA"),
        ("Consecutive Loss Breaker", "CONSECUTIVE LOSS BREAKER"),
        ("Trailing Drawdown", "trailing_dd"),
        ("Force Flatten", "force_flatten"),
        ("Micro-Chop Guard", "check_micro_chop"),
        ("Data Freshness", "DATA FRESHNESS"),
        ("Silent WS Detection", "SILENT WEBSOCKET"),
        ("Daily PnL Reset", "NEW TRADING DAY"),
        ("Confidence Gate (0.50)", "confidence < 0.50"),
    ]
    for name, marker in safety_gates:
        check(f"Safety Gate: {name}", marker in sovran)


# ── GATE 5: ENVIRONMENT ──
def gate_environment():
    print("\n[GATE 5] ENVIRONMENT")

    # Check .env file exists and has required keys
    env_file = VORTEX_DIR / ".env"
    check(".env file exists", env_file.exists())

    if env_file.exists():
        env_content = env_file.read_text()
        for key in REQUIRED_ENV_KEYS:
            check(f".env has {key}", key in env_content)

    # Check data directory
    data_dir = ARMADA_DIR / "_data_db"
    check("_data_db directory exists", data_dir.exists())

    logs_dir = ARMADA_DIR / "_logs"
    check("_logs directory exists", logs_dir.exists())

    # Check Python executable
    check("Python 3.12 exists", PYTHON.exists())


# ── GATE 6: CONSISTENCY CHECKS ──
def gate_consistency():
    print("\n[GATE 6] CONSISTENCY CHECKS")

    sovran = (ARMADA_DIR / "sovran_ai.py").read_text(encoding="utf-8")

    # Check no hardcoded MNQ in trade execution
    if 'f"Executing Live Bracket Order -> {direction} {contracts} MNQ"' in sovran:
        check(
            "No hardcoded symbol in trade log",
            False,
            "Still says 'MNQ' instead of {self.config.symbol}",
        )
    else:
        check("No hardcoded symbol in trade log", True)

    # Check confidence gate matches prompt
    if "confidence < 0.3" in sovran:
        check(
            "Confidence gate matches prompt (should be 0.50)",
            False,
            "Gate is 0.3, prompt says 0.50",
        )
    else:
        check("Confidence gate matches prompt", True)

    # Check ensemble voting uses .upper()
    if "d['action']==\"BUY\"" in sovran:
        check("Ensemble voting is case-safe", False, "Missing .upper() in vote filter")
    else:
        check("Ensemble voting is case-safe", True)

    # Check restart loop has backoff
    if "while True:" in sovran and "time.sleep(15)" in sovran:
        check("Restart loop has backoff", False, "Still infinite with flat 15s delay")
    else:
        check("Restart loop has backoff", True)


# ── GATE 7: STATIC ANALYSIS (MYPY) ──
def gate_typing():
    print("\n[GATE 7] STATIC ANALYSIS (MYPY)")
    try:
        result = subprocess.run(
            [
                str(PYTHON),
                "-m",
                "mypy",
                str(ARMADA_DIR / "sovran_ai.py"),
                "--ignore-missing-imports",
                "--follow-imports=skip",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ARMADA_DIR),
        )
        passed = result.returncode == 0
        if passed:
            check("Type Check / Mypy", True)
        else:
            errors = result.stdout.strip().splitlines()
            # Grab just the first 5 errors to surface quickly
            err_limit = min(len(errors), 5)
            err_summary = "\n  ".join(errors[:err_limit])
            if len(errors) > 5:
                err_summary += f"\n  ...and {len(errors) - 5} more."
            check("Type Check / Mypy", False, err_summary)
    except subprocess.TimeoutExpired:
        check("Type Check / Mypy", False, "TIMEOUT after 30s")
    except Exception as e:
        check("Type Check / Mypy", False, str(e))


# ── GATE 8: OBSIDIAN CONTEXT GATE ──
def gate_obsidian_context():
    print("\n[GATE 8] OBSIDIAN CONTEXT GATE")
    import datetime

    today = datetime.date.today()

    # Check for code changes today
    code_changed = False
    for f in ARMADA_DIR.rglob("*.py"):
        if f.is_file():
            mtime = datetime.date.fromtimestamp(f.stat().st_mtime)
            if mtime == today and f.name != "preflight.py":
                code_changed = True
                break

    if not code_changed:
        check(
            "Code Change Detection",
            True,
            "No code changes detected today. Skipping documentation check.",
        )
        return

    # If code changed, check for documentation today
    obsidian_dirs = [
        Path(r"C:\KAI\obsidian_vault\Sovran AI\Bugs"),
        Path(r"C:\KAI\obsidian_vault\Sovran AI\Session Logs"),
    ]

    doc_found = False
    for d in obsidian_dirs:
        if d.exists():
            for f in d.glob("*.md"):
                mtime = datetime.date.fromtimestamp(f.stat().st_mtime)
                if mtime == today:
                    doc_found = True
                    break
        if doc_found:
            break

    if doc_found:
        check(
            "Obsidian Documentation Check",
            True,
            "Contemporary documentation found in vault.",
        )
    else:
        check(
            "Obsidian Documentation Check",
            False,
            "CODE CHANGED BUT NO OBSIDIAN LOGS FOUND. Breach of ZBI Protocol.",
        )


# ── MAIN ──
def main():
    quick = "--quick" in sys.argv

    print("=" * 60)
    print("SOVRAN AI — PREFLIGHT VALIDATION GATE")
    print("Stripe Blueprint Principle: Deterministic checks, no AI")
    print("=" * 60)

    gate_compile()
    gate_imports()

    if not quick:
        gate_tests()
        gate_structure()
        gate_environment()
        gate_consistency()
        gate_typing()
        gate_obsidian_context()

        # ── VERDICT ──
        print("\n" + "=" * 60)
        total_checks = results.passed_count + results.failed_count
        if results.failed_count == 0:
            print(
                f"PREFLIGHT: + ALL CLEAR ({results.passed_count}/{total_checks} passed, {results.warn_count} warnings)"
            )
            print("System is cleared for Monday deployment.")
        else:
            print(
                f"PREFLIGHT: x BLOCKED ({results.failed_count} failures, {results.passed_count} passed)"
            )
            print("DO NOT DEPLOY. Fix failures first.")
            for d in results.details:
                if d.get("status") == "FAIL":
                    print(f"  x {d.get('name')}: {d.get('detail')}")
        print("=" * 60)

    # Save results
    results_file = ARMADA_DIR / "_logs" / "preflight_results.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(results_file, "w") as f:
        # Create a serializable dict from the class
        json_results = {
            "pass": results.passed_count,
            "fail": results.failed_count,
            "warn": results.warn_count,
            "details": results.details,
        }
        json.dump(json_results, f, indent=2)
    print(f"\nResults saved: {results_file}")

    return 0 if results.failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
