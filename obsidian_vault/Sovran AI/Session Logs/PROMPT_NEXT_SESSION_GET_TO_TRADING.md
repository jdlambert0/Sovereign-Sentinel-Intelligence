# Prompt: Next session — get Sovran trading

**Use this at the start of a new chat.** Paste everything below the line into the assistant.

---

You are continuing **Sovran AI (Armada)** on Windows. Goal this session: **move the system toward reliable live (or clearly scoped paper) trading** — not documentation for its own sake.

## Read first (vault)
1. `Session Logs/LLM_HANDOFF_LATEST.md` — mandates, file index, **Next steps**.
2. `Bugs/PROBLEM_TRACKER.md` — what’s open vs resolved.
3. `Architecture/Broker_API_Realized_PnL.md` — balance + session vs calendar RPNL.
4. `Testing/PHASE_4_RUNBOOK.md` — if touching safety/recovery.

## Read first (code)
- `C:\KAI\armada\sovran_ai.py` — `monitor_loop`, `retrieve_ai_decision`, gates, `calculate_size_and_execute`.
- `C:\KAI\armada\projectx_broker_api.py` — broker truth.
- `C:\KAI\armada\monitor_sovereign.py` — health snapshot.

## Operating constraints
- **Python:** `C:\KAI\vortex\.venv312\Scripts\python.exe` from `C:\KAI\armada`.
- **Preflight gate:** Run `python preflight.py` — must stay **45/45** after any code change.
- **Broker truth:** No fake balances; API is source of truth. Brackets: verify via **API / trade log**, not TopStepX chart UI.
- **Stacks:** Run `python enforce_venv_armada.py` before debugging “lock” issues; avoid duplicate system-Python + venv Sovran.
- **Stealth / focus:** Don’t spawn focus-stealing browsers unless the user asks.

## Session objective (pick and execute)
Choose the **highest-leverage** path toward *actually placing and managing trades*:

1. **Green path — system already healthy**  
   - Run `preflight.py`, `monitor_sovereign.py --once`, `enforce_venv_armada.py`.  
   - Confirm single Sovran stack, broker line OK, logs show quote/Gambler or explain WARNs.  
   - Identify what blocks orders: confidence gate, session phase, veto rate, risk vault, `WAIT` loop, API errors.  
   - Make **minimal code or config changes** to unblock *one* test trade path (small size), then re-run preflight.

2. **Red path — something is broken**  
   - Reproduce from logs (`watchdog_restart_stderr.log`, `sovran_run.log`).  
   - Fix root cause; preflight 45/45; document in Problem Tracker or session log.

3. **Safety path — user wants combine-safe testing**  
   - Follow `PHASE_4_RUNBOOK.md` for one row (e.g. restart recovery or SL/TP check) with **micro size**; update `Testing/TEST_RESULTS.md` with date + evidence.

## Deliverables before you say “done”
- [ ] `preflight.py` 45/45 (if you changed code).  
- [ ] Short note in vault: `Session Logs/YYYY-MM-DD_*.md` — what you ran, what blocks trading, what changed.  
- [ ] Update `LLM_HANDOFF_LATEST.md` **Next steps** if priorities shifted.  
- [ ] Honest statement: **did not verify live fills** unless you actually saw API confirmation.

## What you must not claim
- Guaranteed profit or “it will trade profitably.”  
- Chart UI as proof of brackets.  
- Completion without running preflight when code changed.

Start by summarizing what you read from the handoff, then state your chosen path (green/red/safety) and the **first three actions** you will take.

---

*File: `Sovran AI/Session Logs/PROMPT_NEXT_SESSION_GET_TO_TRADING.md` — link from [[LLM_HANDOFF_LATEST]] if useful.*
