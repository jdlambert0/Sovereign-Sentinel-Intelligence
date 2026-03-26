# Sovereign Canary Architecture (Speculative Spec)

## The Core Problem
Autonomous trading agents suffer from "silent failures". A crashed process is easy to detect (`watchdog.py`), but **logic stalls, rate limit loops, data starvation, and hallucinated consensus** are infinitely harder to catch. If the WebSocket drops but the SDK doesn't throw an error, Sovereign will silently stop trading.

## The "Canary in a Coal Mine" System
A Sentinel Agent (the Canary) must sit completely outside the execution loop, observing the environment and the trader without participating in the execution. 

### 1. The Heartbeat Matrix (What the Canary Watches)
The Canary does not track `system_uptime`. It tracks **Data Velocity** and **Semantic Entropy**.
- **Velocity Heartbeat:** Are we receiving at least 1,500 L1/L2 quotes per minute on MNQ during RTH? If this drops below 100, the data bridge is silently disconnected.
- **Cognitive Heartbeat:** Is the Gambler outputting an `[AI DECISION]` every N minutes? If the log shows `WAIT` 50 times in a row with identical reasoning, the LLM is caught in an entropy loop.
- **Latency Heartbeat:** How long does the `complete_ensemble` call take? If OpenRouter degrades from 800ms to 4500ms, the Canary knows slippage will destroy the edge before the engine does.

### 2. Implementation: The Three Sensors
To build this, we would deploy three decoupled sensors:
1. **The Tailer (Log Pulse):** A Rust or Python `asyncio` script that tails `watchdog_restart_stderr.log` and `sovran_run.log` in real-time, matching regex strings for `Gambler Idea`, `[ERROR]`, and WebSocket disconnects.
2. **The Dummy Order (API Pulse):** The Canary attempts to place a mock bracket order on a Micro contract far outside the spread (e.g., $100 away) every 15 minutes, then immediately cancels it. This proves the *execution* layer is online, not just the data layer.
3. **The Balance Tracker (Truth Pulse):** Scrapes the TopStepX REST API for the current bankroll every 5 minutes and compares it against `sovran_ai_state`. If they diverge by more than $20, the system is out of sync.

### 3. The Alerting Mechanism (The Tripwire)
When the Canary dies (or triggers an alert), it must bypass the standard logs.
- **Discord Webhook / Twilio SMS:** Immediate physical alert.
- **The Execution Killswitch:** The Canary has the authority to run `emergency_flatten()` strictly over the REST API and forcefully kill `sovran_ai.py` at the PID level, changing a master `.env` flag `TRADING_HALTED=TRUE`.

## Immediate Action
V0 prototype: `canary_sentinel.py` tails logs, watches CPU, tracks Gambler beats, and writes reports to `C:\KAI\obsidian_vault\Sovran AI\Canary_Reports`.

## Operations (V1 — long-running)

**Location:** `C:\KAI\armada\canary_sentinel.py`

**CLI:**
- Default: 60-minute run, polls every 30s, tails `watchdog_restart_stderr.log` and `sovran_run.log`.
- `python canary_sentinel.py --duration 0` — run until **Ctrl+C** (decoupled monitor).
- `python canary_sentinel.py --duration 120 --interval 30` — two hours, 30s poll.
- `python canary_sentinel.py --log C:\KAI\armada\_logs\sovran_fresh_stderr.log` — add extra log paths (repeat `--log`).

**Background on Windows (no console):**
- Task Scheduler: action = `C:\KAI\vortex\.venv312\Scripts\python.exe` with arguments `C:\KAI\armada\canary_sentinel.py --duration 0 --interval 30`, start in `C:\KAI\armada`, run whether user is logged on or not (optional).
- Or run in a separate terminal tab during RTH; keep `monitor_sovereign.py` as the primary health snapshot.

**Note:** Dummy-order and Discord tripwires remain future work; this V1 is log + CPU only.
