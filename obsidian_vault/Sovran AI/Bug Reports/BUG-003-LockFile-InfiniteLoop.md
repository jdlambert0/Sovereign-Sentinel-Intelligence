# Bug Report: Lock File Infinite Restart Loop

**Date:** 2026-03-17
**Severity:** CRITICAL
**Status:** FIXED

## Description
When Sovran starts, it creates a lock file with its PID. If the process exits/crashes after creating the lock but before removing it, subsequent starts detect the stale lock file and see the old PID as "alive" (or there's a race condition), causing immediate abort with "FATAL: Another instance is already running".

This creates an infinite loop where:
1. Process starts, writes PID to lock
2. Process crashes or exits
3. New process sees lock, checks PID (returns True even if process is dead in some cases)
4. New process aborts immediately
5. External watchdog/restart mechanism tries again
6. Loop continues forever

## Root Cause
The lock file logic at `sovran_ai.py:1665-1684` checks if the PID exists using `psutil.pid_exists()`. However:
- On Windows, PIDs can be reused quickly
- The previous process may still appear "alive" in some edge cases
- No timestamp in lock file to detect staleness

## Fix Applied
Added timestamp to lock file and check for stale locks (>5 minutes old):

```python
lock_file = r"C:\KAI\armada\sovran_ai.lock"
try:
    if os.path.exists(lock_file):
        with open(lock_file, "r") as f:
            content = f.read().strip()
            # Format: "PID timestamp" or just "PID"
            parts = content.split()
            old_pid = int(parts[0])
            lock_time = float(parts[1]) if len(parts) > 1 else 0
        
        import psutil
        is_stale = False
        
        # Check if stale (>5 minutes old)
        if lock_time > 0 and (time.time() - lock_time) > 300:
            is_stale = True
            
        if psutil.pid_exists(old_pid) and not is_stale:
            logger.error(f"FATAL: Another instance running (PID {old_pid}). Aborting.")
            return
            
        # Stale lock - remove it
        if is_stale:
            os.remove(lock_file)
            
    # Write new lock with timestamp
    with open(lock_file, "w") as f:
        f.write(f"{os.getpid()} {time.time()}")
```

## Files Modified
- `sovran_ai.py` - Lock file handling (lines 1665-1684)

## Testing
After fix, Sovran starts cleanly without infinite restart loop.

---
*Bug reported by: KAI*
