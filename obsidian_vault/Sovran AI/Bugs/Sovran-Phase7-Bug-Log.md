# Sovran Phase 7 Bug Log

Date: 2026-03-18
Origin: Phase 7 research/logging (Phase 7 → Phase 8 planning)

Overview
+- This log captures bugs observed during Phase 6/7 integration and Phase 7 research activities. The goal is to document issues for future fixes without applying changes in this turn.

Bugs Logged (Non-fix, for later review)
+- Bug 1: LSP diagnostics show unresolved imports in sovran_ai.py (llm_client, signalrcore.* modules) in the editing environment. Impact: only an editor warning; runtime imports succeed, but static analysis reports errors.
+- Bug 2: AIGamblerEngine has several hypothetical attributes flagged as unknown by type checkers (ct_tz, oFi_history, vpin_.*). Impact: type-checking may fail in some tooling, runtime appears unaffected.
+- Bug 3: “Cannot access attribute …” warnings for vpin and OFI history attributes. Impact: static checks; runtime usage appears to be dynamic. Action: add proper type hints or adjust mocks in tests later.
+- Bug 4: WebSocket errors observed when connecting to TopStepX real-time feed; fallback to REST polling occurs. Impact: real-time data reliability concerns; operationally the system continues with REST depending on configuration.
+- Bug 5: UnicodeEncodeError in Windows CP1252 when logging emoji characters. Impact: log output may fail in non-UTF-8 environments. Action: standardize to UTF-8 logging in future fixes (not this turn).
+- Bug 6: Test harness reported ValueError: Required environment variable 'PROJECT_X_API_KEY' not found. Impact: test harness depends on env vars; resolved by loading from vortex/.env in test harness. Future: ensure harness loads env reliably.
+- Bug 7: Patch/apply_patch attempts sometimes fail due to mismatched lines in the code; patch tooling should be aligned with current file state. Impact: patching stability; this is tracked for future tooling alignment.
+- Bug 8: Phase 2 Run results show multiple REST calls; ensure bracket integration path remains atomic and stable across runs; potential drift with UI vs API state.
+- Bug 9: Autonomous demo run attempted; environment prevented execution due to missing project_x_py module in the Python environment used by this runner. Documented; awaiting a Windows host with dependencies to verify the autonomous demo end-to-end.
+- Bug 10: Autonomous demo succeeded in placing an order (Order ID: 2660743282) but the order did not appear in the open orders list when queried immediately after placement. Possible causes: order filled immediately (market order), or timing delay in open orders endpoint. Impact: requires verification of order lifecycle; may affect SL/TP linkage confirmation.
- Bug 11: TP price calculation was WRONG. Latest bracket had TP below entry price. Root cause: API tick sign confusion. **RESOLVED 2026-03-18**: Verified correct tick convention: LONG = negative SL, positive TP. Order 2661090950 confirmed working with correct prices visible on chart.

Notes
+- All bugs are logged for visibility; no fixes are performed in this turn per instruction.
+- Future work: unify logging, ensure encoding, add type hints, and stabilise real-time connectivity.

Actions (log-only)
+- Continue documenting observed bugs as new tests run and new failures surface.
+- Log any changes to Obsidian as separate notes and link to relevant patches or test outcomes.