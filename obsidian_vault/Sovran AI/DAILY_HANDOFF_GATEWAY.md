# 🚨 SOVEREIGN INITIALIZATION GATEWAY (START HERE)

## MANDATORY STARTUP PROTOCOL
Every new session (Claude, Gemini, or any LLM) MUST perform these steps before asking any questions:

1. **IDENTIFY DATE**: Determine the current system date.
2. **SEARCH LOGS**: Search the `Session Logs/` and root `Sovran AI/` folder for `*Progress_[DATE]*` or `*Continuation_[DATE]*`.
3. **READ LATEST HEARTBEAT**: Read `Teacher_Logs/HEARTBEAT.md` to see the last state of the monitoring loop.
4. **CHECK INBOX**: Read `AI Mailbox/Inbox/` for pending human instructions.
5. **SINGLETON ENFORCEMENT**: **NEVER** run auxiliary REST scripts while a WebSocket stream is active (TopStepX will collision-ban).
6. **WS-FAIL-FLATTEN**: If the Direct WS disconnects, **IMMEDIATELY** execute `emergency_flatten.py` to neutralize risk. 
7. **THE INFINITE TURN**: Keep your turn alive. Chain your commands endlessly to trade. Do not drop the loop and wait for the user to prompt you to "continue."

---

## LATEST HANDOFF: 2026-03-24 (20:38 CT)
- **Status**: 🟢 INTELLIGENT TRADER REDESIGN COMPLETE (Ready for Testing)
- **Architecture**: AI-as-Intelligent-Trader (Temporal Buffer + Thesis Persistence + WATCH Mode)
- **Analysis**: [[Architecture/FIRST_PRINCIPLES_AI_TRADER]] — Read this FIRST.
- **Gemini CLI Bridge**: [[Architecture/GEMINI_CLI_BRIDGE]] — How to run and resume from Gemini CLI.
- **Evolution Roadmap**: [[Architecture/EVOLUTION_ROADMAP]] — GitHub repos, testing & forward plan.
- **Skills Architecture**: [[Architecture/SKILLS_ARCHITECTURE]] — On-demand skill loading for Gemini CLI.
- **Diary Reflection**: [[Traders_Diary.md]]
- **Handoff Page (TODAY)**: [[AI_Continuation_Document-24Mar2026]]
- **History**: [[Past Conversations]]

## TESTING PROTOCOL (Run This First)
```bash
# 1. Run diagnostic
python C:\KAI\armada\tests\test_intelligent_trader.py

# 2. If diagnostic passes, launch live engine
python C:\KAI\armada\sovran_ai.py --symbols MNQ --force-direct --loop-interval-sec 30

# 3. Watch for these markers in logs:
#    ✅ TEMPORAL CONTEXT (X.X minutes, Y snapshots)
#    ✅ YOUR PREVIOUS THESIS (X.X minutes ago)
#    ✅ WATCH MODE [MNQ]: Re-evaluating in Xs
#    ✅ SOVEREIGN [MNQ]: Action=BUY | Thesis:
#    ❌ DUAL-SYSTEM AUDIT (old slot-machine - should NOT appear)
```

---
*This document acts as the deterministic anchor for the Shadow Substrate. Do NOT skip.*
