# Bug Report: Unicode Terminal Hang (March 20, 2026)

## Symptom
The Sovereign AI system "hung" overnight after a restart attempt. The `autonomous_sovereign_loop.py` and `sovereign_watchdog.py` background processes were inactive, and logs stopped updating abruptly.

## Location
- `C:\KAI\armada\sovereign_watchdog.py`
- PowerShell background job redirection (`*>`)

## Root Cause
**Unicode Encoding Failure (Charmap Codec Error).**
The `sovereign_watchdog.py` used status emojis (🟢, 🔴, 🟡, ✅, ⚠️). When these were printed to `stdout` and redirected to a file via PowerShell's `*>` operator in a background job, the Windows terminal environment (defaulting to a restricted charmap) triggered a fatal `UnicodeEncodeError`. This error trapped the PowerShell job, causing a "silent hang" where the process was neither running nor officially dead in a way that triggered the wrapper's restart logic.

## Evidence
`watchdog_stdout.log`:
```
[WATCHDOG ERROR] 'charmap' codec can't encode characters in position 0-2: character maps to <undefined>
```

## Fix
1. **ASCII-fication**: Removed all non-ASCII characters from `sovereign_watchdog.py`. Emojis replaced with `[OK]`, `[WARN]`, `[CRIT]`.
2. **Standardization**: Ensured `sovran_ai.py` remains 100% ASCII in its console output path.
3. **Redirection Robustness**: Updated `sovereign_watchdog.py` to explicitly reconfigure `sys.stdout` to UTF-8 on Windows as a secondary defense.

## Status
**RESOLVED.** System restarted and verified healthy with ASCII logs.
