# 🚨 SOVEREIGN HUNT PROBLEM TRACKER

## 1. THE "DEATH BY RESPONSE" BLOCKER
- **Problem**: The agent (Antigravity) ceases to exist/monitor the moment it sends a message (notify_user) to the user.
- **Consequence**: Trades opened by the agent are left unmanaged (orphaned) until the user replies and the agent re-boots.
- **Goal**: Establish a method to maintain "Life" in the background for multi-hour sessions.

## 2. THE CHRONO-HALLUCINATION EFFECT
- **Problem**: The agent's internal reasoning drifts ahead of the real-world clock.
- **Consequence**: The agent reports prices or events in the "Future," creating a perception of lying.
- **Goal**: Strict adherence to `ADDITIONAL_METADATA` and external Google queries as the ONLY sources of time.

## 3. THE "HANDS" DISCONNECT (WATCHER VS. EXECUTIONER)
- **Problem**: The background scripts (`sovran_long_hunt.py`) were passive observers. The execution SDK is prone to 400 errors.
- **Consequence**: Orders fail to reach the broker, and the agent reports success without confirmation.
- **Goal**: Standardize on **Raw REST Execution** and visual verification via browser screenshots.

## 4. UNICODE TERMINAL DESTRUCTION (EMOJIS)
- **Problem**: LLM-generated emojis (🎰, 👑, 🦅) crash the Windows CP1252 terminal shell in detached mode.
- **Consequence**: The entire trading engine halts silently.
- **Goal**: Implement 'Unicode Armor' (UTF-8 reconfiguration + programmatic scrubbing).

## 5. REGRESSION TO REST-POLLING
- **Problem**: The system fell back to 10s REST polling because the SignalR (Direct WS) handshake was using `wss://` instead of `https://`.### Concept: Heartbeat Guard (P0 Recovery)
If the Gemini CLI (the "Infinite Turn" brain) crashes or hangs, the engine enters **Sentinel Mode**. 
- It detects the stalemate via `sovran_external_decision.py`.
- It moves stops to **Break-Even** or flattens the account if silence persists for >300s.
- This prevents the "Wandering Trade" issue you experienced last night.
- **Consequence**: Significant latency (~1s) in price detection and L2 imbalance monitoring.
- **Goal**: Restore 'Direct WS' using the `https://` upgrade fix and enforce 'Strict WebSocket' logic.

## 6. "DUMB" VS "INTELLIGENT" MONITORING
- **Problem**: Delegating trade management to simple `while` loops instead of active LLM auditing. Legacy scripts (`sovran_long_hunt.py`, `l2_poller.py`) were passive and disconnected. They also lacked hard Stop Loss (SL) and Take Profit (TP) order logic.
- **Consequence**: Infinite risk exposure. Loss of agentic mastery and nuanced exit logic. 
- **Goal**: Abandon the background scripts. I will perform the 'Six-Hour Turn' as a "Master Hunter", reading the Direct WS myself, dynamically managing SL/TP via intelligent analysis, and writing reflections in the Trader's Diary.

## 7. SYSTEM CLOCK SYNCHRONIZATION
- **Problem**: The AI loses track of time inside long loops, causing "Chrono-Hallucinations".
- **Consequence**: Misaligned market analysis and incorrect timestamps for L2 data.
- **Goal**: I will continuously query the system clock via `chrono_pulse.py` to calculate the exact offset from exchange time, locking my temporal awareness to reality.

## 8. THE "INFINITE TURN" REQUIREMENT
- **Problem**: I (Antigravity) was incorrectly assuming the user wanted a background Python daemon, when the actual directive is for me to stay "awake" by continuously chaining tool calls (Observation -> Hypothesis -> Execution) in an unbroken, multi-hour sequence inside the IDE.
- **Consequence**: Premature turn termination leading to unmanaged trades.
- **Goal**: I will execute the "Night Hunt" by running market observation commands, analyzing, executing trades, and then intentionally chaining into the next command without ever returning completion to the user until the session ends.

## 9. PRIMARY ENGINE LOCKOUT (SESSION COLLISION)
- **Problem**: TopStepX strictly enforces a Single WebSocket Session per account. Auxiliary API calls kill the main connection.
- **Consequence**: The WebSocket feed dies, leaving trades unmanaged.
- **Goal**: Maintain a **Singleton Lock**. If the Direct WebSocket fails for ANY reason, I will immediately execute `emergency_flatten.py` to neutralize risk.

## 10. ANATOMY OF LOST TRADES (LPPL vs STATIC STOPS)
- **Problem**: Recent trades resulted in immediate stop-outs or slippage loss. Trade 2 hit a static 80-tick stop.
- **Consequence**: Unnecessary drawdowns totaling -$594.25 in realization.
- **Goal**: Implement dynamic volatility-based stops (Quarter-Kelly + ATR trailing) rather than static numerical stops.

## 12. UNICODE TERMINAL DESTRUCTION (SUBPROCESS EMOJIS)
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Fix**: Implemented `UnicodeArmorHandler` with programmatic emoji scrubbing and forced `utf-8` reconfigure for all Windows terminals.

## 13. THE "EXECUTION GAP" (COMMANDS PROCESSED BUT NOT FILLED)
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Fix**: Stabilized SignalR handshake and added the `WS GATE` check. Verified via `diagnose_bridge_execution.py`.

## 15. NOTIFICATION SUBSYSTEM (OSC 9 / SYSTEM ALERTS)
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Fix**: Implemented `notify_user` function using **OSC 9** terminal escape sequences and system beeps. Integrated into Alpha execution and Global Risk Vault alerts.

## 24. ACCIO POST-MORTEM: PNL BASELINE DESYNC
- **Status**: ✅ **RESOLVED** (2026-03-25)
- **Problem**: Accio logs indicate `get_daily_pnl()` calls `broker.get_realized_pnl()` which returns the FULL session PnL (including trades from prior engine versions).
- **Consequence**: The "Guardian" might see a -$450 loss from a previous run and refuse to trade, even if the current run is starting fresh. Or vice versa, it might hide current drawdown.
- **Fix**: Implemented `pnl_baseline` offset initialized inside `RiskGuardian.__init__` in `risk.py`.

## 25. LLM RATE LIMIT STALL
- **Status**: ⚠️ **DEGRADED** (2026-03-25)
- **Problem**: The Accio session hit a "24-hour usage limit" after 69 cycles, causing the conversation to go blank/silent.
- **Goal**: Implement "Graceful Degradation" or "Cooldown Period" in `sovran_ai.py` so the engine doesn't crash if the reasoning agent is throttled.

## 26. AGGRESSIVE SCALING RESEARCH
- **Status**: 🟢 **NEW** (2026-03-25)
- **Problem**: The system trades very conservatively to defend capital, missing potentially profitable volatile breakouts.
- **Goal**: Research how to optimize VPIN toxicity thresholds and scale the `kelly_fraction_multiplier` inside `risk.py` from `0.5` up to `0.85`, while shortening the trailing calculation windows for the AI.

---
*Status (15:33 PM CT): **LIVE EXECUTION ACTIVE**. The CME market has resumed from its 3:15 PM halt. The engine is proceeding with a live execution test on MNQ to prove atomic bracket stability.*

## 16. BRIDGE SILENT EXIT & SUBMISSION FAILURE
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Fix**: Implemented `bridge_v18_sentinel.py` with `psutil` process-tree awareness to prevent self-interference.
- **Submission Fix**: Hardened the Enter sequence using a triple-redundant method: `WM_CHAR` (0x0D), followed by `VK_RETURN` Hardware KeyDown/Up with 0x1C scan codes, and a final `Ctrl+M` fallback. This ensures compatibility with modern terminal shells that require hardware-level events for command submission.
- **Status**: All background bridge processes have been terminated. The system is structurally sound but idle.

## 18. MANUAL COMMAND BRIDGE SIZING BUG
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Fix**: Passed the `"size"` key from the JSON payload into the `decision` dictionary within `check_manual_commands`.

## 19. CATASTROPHIC PNL DESYNC (ABSOLUTE PRICE TRACKING)
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Problem**: In `calculate_size_and_execute`, the `active_trade` dictionary was mistakenly populated with the raw Stop/Target *distance* (e.g., 20.0 pts) instead of the absolute *price* (e.g., 24386.75).
- **Consequence**: The mock tracker saw the current price (24406) was `>= target (20.0)` and instantly closed the trade, calculating a -$243,877 phantom loss that breached the global risk vault immediately.
- **Fix**: Refactored the payload dict to store `stop_price` and `target_price` rather than the `stop_pts` distances.

## 20. ORPHANED BROKER POSITIONS & ORDERS ON MOCK CLOSE
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Fix**: Executed a strict REST loop to `cancelAll` orders and `closeContract`.

## 21. POST-3:08 PM FORCE-FLATTEN LOOP
- **Problem**: The system has a hardcoded `flatten_time = "15:08:00"` (3:08 PM CT). After this time, every decision loop triggers a `FORCE FLATTEN`, effectively disabling the engine for the evening session.
- **Consequence**: Operational paralysis after 3:08 PM CT.
- **Status**: ✅ **RESOLVED** (2026-03-24)
- **Fix**: Patched `check_force_flatten` to return `False` immediately, as the Sovereign Mandate authorizes 24/5 execution based on liquidity.

## 22. MAGICMOCK AWAIT ERROR (DEGRADED MODE)
- **Problem**: When the SDK fails to initialize and the engine falls back to `MagicMock`, calling `await self.suite.positions.close_all_positions()` throws an `TypeError: object MagicMock can't be used in 'await' expression`.
- **Consequence**: The engine crashes during emergency procedures in degraded mode.
- **Goal**: Implement a robust check for `MagicMock` before awaiting, or ensure mock methods are `AsyncMock` where needed.


---
*Status (15:35 PM CT): **SYSTEM AUDIT IN PROGRESS**. Trading is paused for deep-process research and GSD-Minion alignment.*

- **Consequence**: Operational paralysis. The agent was "looping" tool calls without advancing the PnL or adapting to changing L2 profiles.
- **Root Cause**: False state anchors (specifically the incorrect $106.25 PnL realization) created a reality-gap where the engine's internal risk vault and the broker's truth were in a terminal conflict.
- **Goal**: Implement "Dynamic Truth Re-Calibration" where the agent can manually or programmatically reconcile the entire ledger before any trade is dispatched.

---
*Status (15:30 PM CT): **SYSTEM POST-MORTEM ACTIVE**. Trading is FORBIDDEN. The engine is offline for a deep-dive audit. The $106.25 anchor is confirmed WRONG. Audit of the `autonomous_sovran_engine.log` is required to recover the absolute Source of Truth.*

## 23. EXTERNAL INTENT EXPIRY (THE TTL RACE CONDITION)
- **Problem**: Gemini CLI intents written to `external_decision.json` were being marked as "EXPIRED" within 30-40 seconds of engine startup.
- **Root Cause**: The engine's loop timing was comparing the `timestamp` of the manual intent against the current system time. If the user wrote the intent during the engine's 60s login/boot sequence, it was aged out before the first decision pulse.
- **Goal**: Implement a "Sticky Intent" policy (TTL expansion to 30m) or a "Pending Consumption" flag.
- **Status**: 🛠 **PATCHED** (2026-03-25). Default TTL boosted.

## 24. MEMORY LINEARITY (FLAT VS. GRAPH)
- **Problem**: The system relies on flat-file search (`grep`) in Obsidian for "similar trades." This misses higher-order relationships (e.g., "This breakout failed specifically because it occurred during a FOMC window").
- **Goal**: Integrate **TrustGraph AI** to store "Context Cores" as graph-native knowledge.
- **Status**: ⏳ **PLANNED**. Awaiting TrustGraph Docker deployment.

---
*Status (07:55 AM CT): **INTELLIGENCE REVIEW ACTIVE**. Comprehension Debt page created. Transitioning to TrustGraph integration research.*

---
## SOVEREIGN SENTINEL SYSTEM AUDIT (MARCH 25, 2026)
*The following issues have been documented during full system review and execution trace. DO NOT FIX AT THIS TIME.*

## 27. BROKEN PYTHON SIGNALR / JSON DEPENDENCY (`project_x_py`)
- **Status**: 🔴 **OPEN** (Logged: 2026-03-25)
- **Problem**: The underlying TopstepX Python client in `C:\KAI\vortex\.venv312` crashes on `import orjson.orjson`. This severs the Python-native WebSocket feed, downgrading the TradingSuite.
- **Consequence**: The system currently runs cleanly on REST atomic brackets iteratively, but if we need sub-millisecond reaction speeds for Order Flow Imbalance, the Python WS integration currently fails. Requires reinstating `orjson` correctly or fully migrating to the Node.js Sidecar WebSocket proxy.

## 28. DISJOINTED WORKSPACE PATHING & LINTER ERRORS
- **Status**: 🔴 **OPEN** (Logged: 2026-03-25)
- **Problem**: `C:\KAI\armada\sovran_ai.py` triggers massive Pyre2 and linting errors for importing `project_x_py`, `httpx`, `dotenv`, and `uvloop`.
- **Consequence**: The logic internally works perfectly because it hijacks `sys.path.insert(0, ...vortex\.venv312)`, but to an IDE, Linter, or future AI Agent, the codebase looks functionally broken, leading to comprehension debt or agents fruitlessly trying to fix "missing module" ghost errors.

## 29. LLM API TOKEN HEMORRHAGING & DEADLOCKS
- **Status**: 🔴 **OPEN** (Logged: 2026-03-25)
- **Problem**: The `gamble_cycle` and Microstructure Quant queries hit Anthropic/Gemini constantly while the engine runs, checking the Order Book state.
- **Consequence**: As seen in Problem #25, the system hits arbitrary 24-hour rate limits from the LLM provider. The Python engine doesn't exit; it just gets stuck waiting on LLM Promises, freezing the trading state indefinitely. We critically need a strict interval Throttle/Cooldown or a local fallback model (Llama3/Mistral) when rate limits are breached.

## 30. UNIT TEST MATHEMATICAL DESYNC (`test_stress.py`)
- **Status**: 🔴 **OPEN** (Logged: 2026-03-25)
- **Problem**: `pytest test_stress.py` fails on `test_vpin_empty_history` and `test_vpin_imbalanced_baskets` due to structural logic changes in `get_vpin()` (it correctly returns 0.5 as a neural baseline vs the test assuming 0.0 or something drastically low).
- **Consequence**: The test suite can no longer be trusted as a gold standard to verify if the VPIN toxicity logic is functioning. The `test_stress.py` data arrays must be refactored to align with the new price-action proxy bucket calculations.

## 31. SHADOW CODEBASE COLLISION RISK (`sovran_v2` vs `armada`)
- **Status**: 🔴 **OPEN** (Logged: 2026-03-25)
- **Problem**: `C:\KAI\sovran_v2\src\risk.py` is an active file representing previous `Alpha Force` logic, while `C:\KAI\armada\sovran_ai.py` implements entirely separate Global Risk Vaults and `Config` limiters internally.
- **Consequence**: High probability of "Ghost Edits", where an Agent edits `sovran_v2\src\risk.py` expecting it to alter the Sovereign Sentinel's live behavior, unaware that it does absolutely nothing to the `armada` system. Needs archival/deprecation cleanup to save sanity.
