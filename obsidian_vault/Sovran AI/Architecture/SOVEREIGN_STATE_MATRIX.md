# Sovereign State Matrix (SSM) - V1.0

> **Canonical Context Anchor for Multi-Session AI Coherence**

## 🏁 CURRENT OPERATIONAL STATE (as of 2026-03-22)

| Parameter | Value | Source | Reliability |
| :--- | :--- | :--- | :--- |
| **Daily PnL** | -$118.88 | `trades_export.csv` | 10/10 (Broker Truth) |
| **Account Balance** | $149,881.12 | `topstepx-portal` | 10/10 |
| **Trailing Floor** | $145,500.00 | `sovran_ai_state.json` | 9/10 |
| **System Status** | SHADOW DEBUGGING | `heartbeat.txt` | 10/10 |
| **Active Baseline** | VLD-LOE-HYBRID-01 | `GEMINI.md` | 10/10 |

---

## 🏗️ ARCHITECTURAL DEBT & FIXES

### 1. The "Ghost PnL" Deletion (2026-03-22 FIX)
- **Symptom**: System reported $145k PnL locally while broker was at -$118. Prevents trading due to "hitting profit targets" or false drawdown floors.
- **Root Cause**: Python state objects not clearing on a per-session basis and lacks global reset logic.
- **Fix (PROVEN)**: 
    - `GlobalRiskVault` now resets `total_pnl = 0.0` at the start of its 30s monitor loop.
    - `GamblerState` uses **Atomic Writes** (.tmp + os.replace) for disk persistence.
    - **Verification**: `preflight.py` GATE 4 passed.

### 2. Gemini Strategic Brain Expansion
- **Engine**: Gemini Flash 2.0 (Tier 1 Rate Limits: 2k RPM).
- **Functionality**: 
    - **Gambler**: Strategic overlay (directional conviction > 0.8 required).
    - **CRO**: 90-second market regime veto (stability > 0.6 required).

---

## 🧠 RECENT AI LEARNINGS (Evidence Tracker)

| Date | Process | Learning Type | Impact |
| :--- | :--- | :--- | :--- |
| 2026-03-20 | GSD-Gambler | MIDDAY CHOP Analysis | Injected Kaizen Intel into decision cycle |
| 2026-03-18 | Hunter Alpha | GCS Microstructure | Refined directional bias filters |
| 2026-03-22 | Audit Subagent | BTS (Broker Truth Sync) | Mandated `trades_export.csv` as PnL source |

---

## 🧭 SOVEREIGN ROADMAP (Stage 4: "The $1k Momentum")

1. **[ ] Live Gemini Validation**: Monitor "STRATEGIC VETO" in logs for 4 hours.
2. **[ ] Auto-Log Rotation**: Prevent `gsd_gambler_final.log` from bloating > 100MB.
3. **[ ] Profit Momentum**: 5 of 7 days at $1000 target.

---

## ⚠️ CRITICAL INVARIANTS (FOR NEW AI CONTEXTS)
- **Rule 1**: NEVER trust internal `daily_pnl` if `trades_export.csv` is available.
- **Rule 2**: If LLM times out, **SKIP CYCLE** (Do not force trade).
- **Rule 3**: Preflight must be 37/37 before ANY live deployment.
