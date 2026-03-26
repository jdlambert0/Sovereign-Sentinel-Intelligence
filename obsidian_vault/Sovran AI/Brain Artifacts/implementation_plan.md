# Sovran AI Gambler (V3 - The True AI-at-the-Helm)

We are immediately scrapping the algorithmic V2 (LOE) because it violated the core mandate: "ignore anything algorithm... create an ai-based gambling system."

We are returning to first principles: an LLM makes every single trading decision based on market intuition, and a mathematical sizing engine executes it safely.

## Proposed Changes

### [NEW] `sovran_ai.py`
This will be the single operational file for Monday. It merges the real-time ProjectX feed with the `vortex/gambler_prompt.py` LLM pattern.

**1. Data Ingestion (The Environment):**
- Maintains the custom MessagePack fix (`soe_transport.py` logic) so the SignalR connection doesn't crash on Monday.
- Subscribes to ProjectX L2 and trade ticks.
- Calculates real-time OFI, Book Pressure, and ATR over a 1-minute rolling window.

**2. AI Decision Engine (The Brain):**
- Every 15 seconds (configurable), if flat, the script pauses.
- It builds a prompt containing:
  - Real-time Price, Spread, OFI, Book Pressure.
  - The last 5 trades and their PNL (The Memory Bridge).
  - The explicit instruction: "You are the AI Gambler. Make a bet."
- It calls the Gemini/Claude API asynchronously.
- The AI returns JSON: `{"action": "BUY"|"SELL"|"WAIT", "confidence": 0.0 to 1.0, "reasoning": "..."}`

**3. The Sovereign Kelly Sizer (The Brakes):**
- If AI says BUY/SELL, the script takes the AI's `confidence` score (e.g., 0.82).
- It applies the Kelly Criterion formula: `Size = Bankroll * (Expected Value)`.
- Bankroll is strictly pinned to the TopStep $4,500 trailing drawdown.
- Risk scales dynamically but is hard-capped at 4 MNQ contracts maximum.

**4. Execution & Learning (The Loop):**
- Executes bracket orders via `ProjectX TradingSuite`.
- Upon trade closure, it writes the result, the PNL, and the AI's original reasoning into a local `sovran_memory.json` file.
- The *next* prompt reads this file. This creates the continuous in-context learning loop mandated by `AGENTS.md`.

### Phase 3: Final Hardening (P0 Security)
Summary: Enhancing reliability for unattended Monday execution.

#### [MODIFY] [sovran_ai.py](file:///C:/KAI/sovran_ai.py)
- **Position Recovery:** Add `recover_active_position()` to check for open trades on startup.
- **Force Flatten:** Implement auto-close logic at 15:08 CT (14:08 CT for futures) or as configured.
- **WebSocket Resilience:** Add heartbeats or explicit timeout monitoring for the data stream.
- **Timezone Alignment:** Ensure all logs and logic use CT to match TopStepX reality.

### [DELETE] `sovran_loe.py`
- We will delete the algorithmic file to remove the temptation to rely on hard-coded standard deviations.

### [NEW] `evaluate_ai_stress.py`
- A script to run the "15/15 Stress Test" offline. It will feed historic/mock data into the `sovran_ai.py` decision loop to prove the LLM does not hallucinate, outputs valid JSON 15 times in a row, and maintains the learning loop context.

### Phase 4: Multiverse Battle Arena (Advanced Simulation) [DONE]
Summary: Stress testing the AI against 6 market "Villains" to ensure profitability across all conditions.

- [x] **Villain 1: The Whipsaw Kraken** (High volatility, no direction).
- [x] **Villain 2: The Institutional Dragon** (One-way trend, high volume).
- [x] **Villain 3: The Bear Golem** (Fast liquidation spikes).
- [x] **Villain 4: The News Serpent** (Giant slippage and spread widening).
- [x] **Villain 5: The Liquidity Vampire** (Thin order book, slow updates).
- [x] **Villain 6: The Midnight Ghost** (Low volume, high precision).

### Phase 5: High-Quality Integrity Hardening [DONE]
- [x] **Rolling OFI:** Refactor `handle_trade` to use a rolling window (last 200 trades) for more responsive directionality.
- [x] **Drawdown-Aware Kelly:** Sizing will now factor in the *distance to the trailing drawdown limit*, not just the total bankroll.
- [x] **Braided Memory:** Trade post-mortems will be "hallucination-checked" against actual tick data before being saved to memory.

### Phase 6: Rate optimization & Resilience [DONE]
- [x] **Smart Pacing:** Increase `loop_interval_sec` to 30s as default.
- [x] **Provider Rotation:** OpenRouter retry logic handles 429 errors autonomously.

### Phase 10: Fleet Orchestration (The Armada)
Scaling to 4 micro-instruments concurrently.

#### [MODIFY] [sovran_ai.py](file:///C:/KAI/sovran_ai.py)
- Parameterize `state_file`, `memory_file`, and `log_file` via CLI.
- Derive instrument-specific paths automatically (e.g., `sovran_state_MES.json`).

#### [NEW] [sovran_fleet.py](file:///C:/KAI/sovran_fleet.py)
- **Fleet Manager**: Spawns and monitors 4 sub-processes (MNQ, MES, MYM, M2K).
- **Auto-Restart**: Automatically recovers any crashed micro-engine.

### Phase 11: Sovereign Dashboard (Project Wisdom)
Real-time visibility into the entire fleet.

#### [NEW] [sovran_monitor.py](file:///C:/KAI/sovran_monitor.py)
- **Consolidated Dashboard**: Aggregate PnL, VPIN, and Sentry status across all 4 micros in a single terminal view.
- **Alerting**: Log color-coding for "Critical Disagreements" or "Throttled" states.

### Phase 12: Zero-Slop Audit & Logic Purification
Ensuring 100% code quality and "Institutional Purity".

#### [MODIFY] [sovran_ai.py](file:///C:/KAI/sovran_ai.py)
- **Purge Redundancy**: Remove any leftover LOE-era variables or unused imports.
- **Error Hardening**: Add explicit `try-except` blocks around JSON extrapolation from Ensemble responses.

#### [NEW] [sovran_final_audit_v6_5.py](file:///C:/KAI/sovran_final_audit_v6_5.py)
- **High-Fidelity Monte Carlo**: Run 100,000 simulations of the 4-micro fleet with random model delays and execution slippage to find the absolute "Floor" of profitability.

### Phase 13: Sovereign SimTest & Logic Breakdown
Proving 100% bug-free operation and 100% code comprehension.

#### [NEW] [sovran_armada_simtest.py](file:///C:/KAI/sovran_armada_simtest.py)
- **Synthetic Exchange**: Inject 10,000 randomized quote/trade events into 4 concurrent instances of `sovran_ai.py` in `paper` mode.
- **Stability Audit**: Monitor for memory leaks, JSON parsing errors, or SignalR thread lockups.

#### [MODIFY] [vortex/llm_client.py](file:///C:/KAI/vortex/llm_client.py)
- **Local Rate-Limiter**: Implement a simple token bucket to throttle concurrent LLM requests, protecting OpenRouter credits and preventing 429 cascades.

#### [NEW] [SOVRAN_DEEP_LOGIC.md](file:///C:/KAI/brain/f480b9d1-3222-454b-b7e8-8f2c522dfbec/SOVRAN_DEEP_LOGIC.md)
- **Code Walkthrough**: A high-level architectural document explaining every "neuron" of the system (VPIN, Kelly, Ensemble, Sentry).

### Phase 14: Sovereign Loop & SLOP-DELETION Protocol
Establishing the "Skepticism Layer" and Autonomous Watchdog.

#### [NEW] [sovran_watchdog.py](file:///C:/KAI/sovran_watchdog.py)
- **Health Sentry**: Monitor the fleet processes. If any process stops heartbeat or CPU spikes > 70%, kill and restart.
- **Log Auditor**: Continuously scan `_logs/` for "SLOP" (e.g., model hallucinations, JSON failures, persistent 429s).

#### [MODIFY] [sovran_ai.py](file:///C:/KAI/sovran_ai.py)
- **Skepticism Injection**: AI prompt now requires a "Confidence Challenger" - the model must explain why its own signal might be wrong.
- **Broker Truth Verification**: The `check_broker_positions` logic must be the primary source of truth, not local state.

#### [MODIFY] [start_armada.bat](file:///C:/KAI/start_armada.bat)
- Launch the Watchdog service alongside the fleet.

## Verification Plan
1. **Watchdog Stress**: Force kill an engine process. Verify Watchdog recovers it within 10s.
2. **Skepticism Audit**: Review AI logs for the "Challenger" reasoning.
3. **Sovereign Final Sign-off (V8.0)**.

### Phase 8: Institutional Hardening (Sovereign Firewall)
Integration of HFT-grade risk metrics and prop firm consistency logic.

#### [MODIFY] [sovran_ai.py](file:///C:/KAI/sovran_ai.py)
- **Implement VPIN (Volume-Synchronized Probability of Informed Trading)**: Measure order flow toxicity using volume baskets.
- **Implement Z-Score OFI**: Normalize Order Flow Imbalance to identify extreme deviations.
- **Micro-Chop Guard**: Hard-code filters for `range < 8.0` and `ATR < 5.0`.

#### [NEW] [sovran_sentry.py](file:///C:/KAI/sovran_sentry.py)
- **Neural Risk Sentry**: A dedicated "Guardian" thread/process to monitor the engine.
- **Order Throttling**: Enforce a 5-minute cooldown after any loss.
- **Consistency Rule Tracker**: Track daily PnL against the TopStep 50% rule to prevent "Best Day Bias".

### Phase 9: Consensus Ensemble (Sovereign Council)
Increase conviction using multi-model voting.

#### [MODIFY] [vortex/providers/openrouter.py](file:///C:/KAI/vortex/providers/openrouter.py)
- Support for parallel model calls (e.g., Gemini 2.0 Flash + Claude 3 Haiku).

## Verification Plan
1. **Stress Test:** Run `evaluate_ai_stress.py` with 30s intervals.
2. **Multiverse Expansion:** Run `sovran_battle_multiverse.py` with 10 villains and 100% success.
3. **Kelly Audit:** Verify multi-instrument risk allocation.
4. **Honesty Audit:** Run `sovran_battle_audit.py` (V4.5) to verify net profitability under friction.
5. **Sentry Audit:** Run `test_sentry.py` to verify the "Firewall" correctly throttles trade frequency.
### Phase 16: Consolidation & Stealth Ignition
Summary: Fixing the "window spam" crash and consolidating the system for institutional reliability.

#### [NEW] [armada](file:///C:/KAI/armada/)
- Consolidate all core scripts into a single workspace.

#### [MODIFY] [sovran_fleet.py](file:///C:/KAI/sovran_fleet.py)
- **Background Execution**: Change `subprocess.Popen` flags to use `CREATE_NO_WINDOW`.
- **Safe Restart**: Prevent recursive process spawns on error.

#### [MODIFY] [sovran_ai.py](file:///C:/KAI/sovran_ai.py)
- **SDK Path Fix**: Ensure `project_x_py` is always in `sys.path`.

## Verification Plan
1. **Background Check**: Launch `start_armada.bat` and verify 0 windows appear in taskbar.
2. **Reliability Audit**: Confirm logs show successful connection despite being invisible.
