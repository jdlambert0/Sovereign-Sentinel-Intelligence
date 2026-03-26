# 🚀 MONDAY LAUNCH CHECKLIST

**System:** Sovereign Armada V3+ (Goldilocks Calibrated)  
**Date:** Monday, March 17, 2026  
**Markets:** MNQ → MES (Day 2) → MYM + M2K (Day 3)

---

## PRE-MARKET (7:30 AM CT — Before Login)

- [ ] Confirm `.env` has correct credentials: `PROJECT_X_USERNAME`, `API_KEY`, `VORTEX_LLM_API_KEY`
- [ ] Confirm `VORTEX_AI_MODEL=google/gemini-2.0-flash-001` (free model)
- [ ] Check OpenRouter balance/status at [openrouter.ai/account](https://openrouter.ai/account)
- [ ] Run unit tests:
  ```powershell
  C:\KAI\vortex\.venv312\Scripts\python.exe C:\KAI\armada\tests\test_sovran_core.py
  ```
  **Must pass:** 20/20

## LAUNCH (8:15 AM CT — Paper Mode First)

```powershell
# PAPER mode — zero risk, validates connection
Start-Process -WindowStyle Hidden -FilePath "C:\KAI\vortex\.venv312\Scripts\pythonw.exe" -ArgumentList "C:\KAI\armada\sovran_ai.py --mode paper --symbol MNQ" -PassThru | Select-Object Id
```

**Verify within 2 minutes:**
```powershell
Get-Content "C:\KAI\armada\_logs\sovran_MNQ.log" -Tail 20
```

**Must see:**
- ✅ `INITIALIZING SOVRAN AI GAMBLER (V3)`
- ✅ `Market hub connected`
- ✅ `Starting AI Decision Loop`
- ❌ NO `ModuleNotFoundError` or `JSONDecodeError`

## MONITOR AT MARKET OPEN (8:30 AM CT)

```powershell
# Watch live decisions
Get-Content "C:\KAI\armada\_logs\sovran_MNQ.log" -Tail 30 -Wait
```

**Expected behavior 8:30-9:05 (OPENING BURST):**
- LLM calls every 30s
- If OFI_Z > 1.5 + VPIN > 0.55 → BUY or SELL decision
- If weak signal → WAIT

**Expected behavior 10:30-12:30 (MIDDAY CHOP):**
- `SESSION PHASE GATE: MIDDAY CHOP — BANNED phase. Skipping.`
- Zero trades. Zero LLM calls.

**Expected behavior 12:30-2:00 (EARLY AFTERNOON):**
- `SESSION PHASE GATE: EARLY AFTERNOON — BANNED phase. Skipping.`
- Zero trades.

## LIVE SWITCH (After 1+ Hour Paper Success)

```powershell
# Kill paper mode
Stop-Process -Id <PID_FROM_LAUNCH>

# Start LIVE
Start-Process -WindowStyle Hidden -FilePath "C:\KAI\vortex\.venv312\Scripts\pythonw.exe" -ArgumentList "C:\KAI\armada\sovran_ai.py --mode live --symbol MNQ" -PassThru | Select-Object Id
```

## SAFETY GATES (All Must Fire Correctly)

| Gate | Trigger | Expected Behavior |
|------|---------|-------------------|
| Spread Gate | Spread > 4 ticks | `SPREAD GATE: Blocking entry` |
| Session Phase | MIDDAY CHOP / EARLY AFTERNOON | `SESSION PHASE GATE: BANNED` |
| ConsecLoss | 3 losses in a row | `CONSECUTIVE LOSS BREAKER` |
| Trailing Drawdown | Headroom < $500 | `DANGER ZONE` in logs |
| Drawdown Blown | Headroom ≤ $0 | `ALL TRADING HALTED` |
| Stale Data | No update > 90s | `STALE DATA: Skipping` |
| Force Flatten | 3:08 PM CT | `FORCE FLATTEN TRIGGERED` |
| Last Entry | 2:45 PM CT | `LAST ENTRY TIME passed` |

## EMERGENCY PROCEDURES

**Kill everything immediately:**
```powershell
Get-Process pythonw | Stop-Process -Force
```

**Check TopStepX for orphaned positions:**
```powershell
C:\KAI\vortex\.venv312\Scripts\python.exe C:\KAI\armada\check_broker_positions.py
```

## KNOWN RISKS & MITIGATIONS

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Free LLM rate limited after hours | HIGH | 30s interval + retry logic (2/4/8s backoff) |
| WebSocket disconnects | MEDIUM | Auto-reconnect in project_x_py SDK |
| Stale quotes (feed gap) | MEDIUM | Stale data guard (>90s = skip) |
| JSON parse failure | LOW | `rfind("{")` parser + fallback to WAIT |
| PC sleep/hibernate | MEDIUM | Disable sleep before launch |
| Network outage | LOW | WS_TIMEOUT raises after 60s, process restarts |
