# SYSTEMIC AUDIT: Swarm Architecture Vulnerabilities & Mitigations (Phase 50)

**Date:** 2026-03-22
**Status:** VALIDATION

A critical audit of the proposed Phase 48 (Omni-Observer CRO) and Phase 49 (Asynchronous Learning Loops) integration reveals several architectural vulnerabilities that must be mitigated before live execution, along with a revised API cost projection.

## 1. Vulnerability Matrix & Mitigations

### A. The "Blocked Event Loop" Vulnerability (P0)
- **The Risk:** `sovran_ai.py` is an `asyncio` loop running the TopStepX SignalR websocket. Creating multiple background tasks (`gambler_learning`, `omni_observer_cro`) that execute blocking CPU code or blocking network requests will freeze the real-time websocket, causing the engine to miss price ticks and violate drawdown limits.
- **The Mitigation:** All LLM calls via `llm_client.py` MUST correctly utilize `run_in_executor` to offload to a thread pool. Furthermore, we must introduce `await asyncio.sleep(0.5)` yields inside the background loops to yield control back to the websocket tick processor.

### B. Obsidian File I/O Contention (P1)
- **The Risk:** The CRO writes to `Inbox/CRO_Directive.md` asynchronously. At the exact same millisecond, Sovereign Alpha and Gambler 2.0 might attempt to `open()` the file to read the contents for their next prompt. This will trigger a Windows File Lock error (`PermissionError: [Errno 13]`), crashing the engine.
- **The Mitigation:** Implement a thread-safe `async_file_reader` and `async_file_writer` utility utilizing `asyncio.Lock()`. If the file is locked, the engines will cleanly fallback to an empty string `""` rather than crashing, treating it as "no new instructions from CRO."

### C. CPU Starvation Mandate (P0)
- **The Risk:** User Global Rule states `Total CPU usage must never exceed 70%`. Running 4 concurrent model evaluations (Sovereign Main, Gambler Main, Gambler Reflex, CRO Evaluator) could spike local CPU usage due to intensive string serialization and JSON block parsing.
- **The Mitigation:** We will significantly stagger the learning loops. The CRO will only run once every 5 minutes. The Gambler Learning Loop will only trigger after 10 closed trades (not every tick).

## 2. LLM Cost Projections (API Burn Rate)

The shift from 1 LLM (Sovereign) to 3 active LLMs (Sovereign, Gambler, CRO) alters the cost landscape.

### Model Cost Assumptions:
- **Claude 3 Haiku (Gambler/Sovereign):** 
  - Input: $0.25 / 1M Tokens (Extremely cheap)
  - Output: $1.25 / 1M Tokens
- **Gemini 2.5 Flash (CRO):**
  - Virtually free / negligible under normal limits.

### Burn Rate Estimate (Per 6.5 Hour Trading Day):
1. **Sovereign Alpha & Gambler Main Execution:** 
   - 4 calls per minute x 60 mins x 6.5 hours = ~1,560 queries/day.
   - At ~2,000 contextual tokens per prompt: ~3.1M input tokens/day ($0.77).
   - At ~100 output tokens: ~150k output tokens/day ($0.18).
   - **Daily Execution Cost:** ~$0.95 
2. **Gambler Research Loop:**
   - Evaluates batches per 10 trades. Assume 30 trades/day = 3 batches.
   - Larger context (10,000 tokens): ~30k input tokens, ~1k output tokens.
   - **Daily Reflex Cost:** ~$0.01
3. **Gemini CRO Evaluator:**
   - Runs every 5 minutes = 78 calls/day.
   - **Daily CRO Cost:** ~$0.00 (Covered by API free tier/Gemini integration).

**TOTAL PROJECTED DAILY API COST: < $1.00 USD.**
This cost is mathematically trivial compared to the target $1k/day profit mandate.

## 3. Verification Testing Blueprint (Post-Rewrite)
Before connecting the rewritten `sovran_ai.py` to TopStepX, we will execute an offline mock validation suite (`test_swarm_architecture.py`).

**The 3-Step Verification Pipeline:**
1. **Lock Contention Test:** Force 10 simulated engines to read `CRO_Directive.md` while the CRO continuously overwrites it. Verify zero crashes.
2. **Context Injection Test:** Assert that Gambler 2.0 correctly retrieves the most recent text from `Gambler_Reflex_Memory.md` and appends it to the LLM prompt payload.
3. **Execution Routing Bypass:** Ensure that `llm_client.py` receives the model `haiku` and routes bypassing `OpenRouter` to prevent 429 errors.
