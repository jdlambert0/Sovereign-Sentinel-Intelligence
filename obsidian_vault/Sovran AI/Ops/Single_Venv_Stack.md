# Single venv stack (Armada / Sovran)

## Problem
Duplicate processes: `C:\Users\...\Python312\python.exe` vs `C:\KAI\vortex\.venv312\Scripts\python.exe` both running `sovran_ai.py` / `sovran_watchdog.py` → portalocker storms, stderr spam, confusing logs.

## Tool
```text
cd C:\KAI\armada
C:\KAI\vortex\.venv312\Scripts\python.exe enforce_venv_armada.py
```
- Exit **0** if no offenders; **1** if non-venv armada sovran found.

Kill duplicates (use when flat / acceptable):
```text
C:\KAI\vortex\.venv312\Scripts\python.exe enforce_venv_armada.py --kill
```

## Prevention
- One launcher: `launch_armada.py` (headless) using venv Python only.
- Audit **Task Scheduler**, **Startup** folder, and **StartArmada.vbs** for a second path.
- Document the canonical interpreter in team notes: **always** `vortex\.venv312\Scripts\python.exe` for Sovran.

## For future LLMs
Run `enforce_venv_armada.py` before debugging “lock” or “duplicate” issues. Do not start a second stack without killing the first.
