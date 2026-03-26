# BUG-005: ZRS Static Analysis Audit (Baseline Integrity Errors)

**Status:** UNRESOLVED
**Date:** 2026-03-16
**Discovered By:** Zero-Runtime-Surprise (ZRS) Static Analysis Pipeline

## Context
Following the principle of "Shift-Left" debugging to achieve zero runtime surprises, the `sovran_ai.py` and `place_test_trade.py` engines were subjected to a strict `mypy` compilation gate as part of the new `preflight.py` schema.

The baseline audit discovered 7 static type violations and unannotated data structures that pose silent failure risks for the autonomous loop.

## The Bugs (Discovered without executing live)

1. **`place_test_trade.py:6` - IO Reconfigure Failure**
   - **Error:** `Item "TextIO" of "TextIO | Any" has no attribute "reconfigure"`
   - **Symptom:** Windows console UTF-8 reconfigurations can crash if the standard output stream is piped or overridden in a non-standard environment.

2. **`sovran_ai.py:383` - OFI Z-Score Return Leak**
   - **Error:** `Returning Any from function declared to return "float"`
   - **Symptom:** The `get_ofi_zscore` mathematical function lacks strict type flow; under certain empty-list conditions, it may return a value the engine cannot cast correctly.

3. **`sovran_ai.py:393` - OFI Delta Return Leak**
   - **Error:** `Returning Any from function declared to return "float"`
   - **Symptom:** The `get_ofi` baseline generator contains a type leak.

4. **`sovran_ai.py` - Unannotated Memory Buckets (x3)**
   - **Error:** `Need type annotation for "ofi_history"` (and `vpin_buckets_history`, `ofi_history_for_z`)
   - **Symptom:** Lists initialized as `[]` without strict boundaries (e.g., `list[float]`) allow the AI to push malformed types (like strings or dicts) into the mathematical engine during runtime, which would crash standard deviation calculations 10 minutes later.

5. **`sovran_ai.py` - Position Tracking Keys (`TopStepXPosition`)**
   - **Discovery:** `recover_active_position` expects `pos.get('instrumentId')`.
   - **Fact:** TopStepX WebSocket REST schema dictates `contractId` and `size`, NOT `instrumentId` and `netQuantity`. While not directly caught by standard `mypy` `get()` string literal interpretation, it was surfaced forcefully when mapping the new `api_types.py` ZRS boundary to the code.

## Next Steps
All bugs have been isolated before live deployment sequence execution.

**DO NOT FIX YET. AWAIT INSTRUCTIONS.** 
This document serves as the zero-day inventory. The fixes should be processed through the standard Agentic Engineering deterministic process.
