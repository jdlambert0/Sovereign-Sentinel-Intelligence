Session Notes - 2026-03-18

Context
- Phase 6/7 work on atomic SL/TP brackets using TopStepX API; Sovran AI integration; Phase 7 archival and Phase 8 profitability planning.
- Tasks executed: code patches for atomic bracket path, test harness creation, Obsidian documentation, and Phase 7 bug logging. Added autonomous demo script hunter_alpha_trade_autonomous_demo.py for an end-to-end test.

What worked well
- Atomic bracket path implemented and tested in Phase 6 (native API call with SL/TP in one payload).
- Test harness added to validate end-to-end bracket placement; results captured in logs.
- Obsidian plan and architecture documentation created to map out the system and external docs.

What didn’t work (or blocked)
- Demo execution blocked by environment constraints (missing Python module project_x_py in the current interpreter).
- WebSocket real-time data is still flaky in the environment; REST-based atomic brackets are used for automation, but real-time streams remain fragile.
- Patch tooling occasionally fails due to mismatches with current code; requires careful patch targeting.

Current state
- Phase 7: architecture notes, phase 2 phase 2 results, and references are documented.
- Phase 8: profitability planning scaffold has been started; production-readiness plan is drafted.
- Autonomous demo script exists but could not run here due to environment constraints.

Immediate next steps
- Run the Hunter Alpha autonomous demo in a Windows environment with project_x_py installed, or via CI (GitHub Actions Windows runner).
- If demo succeeds: log results to the Bug Log and Interactive Session Log; patch Obsidian accordingly.
- If demo fails: log the error in Bug Log and create a fallback plan for manual test harness.
- Update Phase 7 architecture docs with the latest CI plan and connected to the CI workflow.
- Prepare Phase 8 profitability plan updates with concrete milestones.

Context Summary (this conversation)
- Requested to halt phases and perform an autonomous demo of Sovran's Hunter Alpha placement of a trade with wide SL/TP, log bugs, and stop.
- Implemented an autonomous demo script hunter_alpha_trade_autonomous_demo.py to place an atomic bracket using TopStepX API.
- Attempted to run the demo in this environment but encountered environment constraints (missing project_x_py or Windows venv compatibility).
- Added CI path: GitHub Actions workflow run-hunter-alpha-demo.yml to execute the demo on Windows runner; the script now logs to hunter_alpha_demo.log for artifact collection.
- Created a Bug Log entry and updated the Observability notes in Obsidian accordingly.
- Prepared obsidian references for Phase 7 rapid iteration and Phase 8 profitability planning.
- Attempt to execute hunter_alpha_trade_autonomous_demo.py in an environment with project_x_py installed and credentials loaded.
- If successful, log results to the Obsidian Bug Log and the Interactive Session Log.
- If not, capture exact error messages and log in Bug Log; prepare a fallback path for manual or semi-automatic test triggers.

Notes for future runs
- Ensure the testing environment uses the same Python interpreter and virtual environment for consistent module imports.
- Provide a CI-runner or a Windows host runner with the dependencies installed to automate the demo script execution.

## Update - 19:34 UTC - TRADE VERIFIED ON EXCHANGE!

### Verified Trade Status
- **Position Confirmed:** 1 open position on MNQ M26
- **Size:** 6 contracts LONG
- **Entry Price:** $24,785.58
- **Time:** 17:45:27 UTC

### Bracket Orders Confirmed (8 open orders)
| Order ID | Type | SL Price | TP Price | AutoBracket ID |
|----------|------|----------|----------|----------------|
| 2660260190 | SL | 24709.25 | - | 4ad5bfaf-... |
| 2660260191 | TP | - | 24859.25 | 4ad5bfaf-... |
| 2660719645 | SL | 24494.00 | - | b2870744-... |
| 2660719646 | TP | - | 24794.00 | b2870744-... |
| 2660743283 | SL | 24483.50 | - | 5107f8bb-... |
| 2660743284 | TP | - | 24783.50 | 5107f8bb-... |
| 2660788340 | SL | 24466.25 | - | feab24e3-... |
| 2660788341 | TP | - | 24766.25 | feab24e3-... |

### Critical Finding: Bug #11
The atomic bracket API call IS WORKING - SL/TP brackets are being attached to positions!
However, the latest TP (24766.25) is BELOW entry (24785.58) - this is WRONG.
For a LONG position, TP must be ABOVE entry price.

### Root Cause Hypothesis
The TP tick calculation is inverted or using wrong sign. Need to check:
1. TP ticks calculation in sovran_ai.py `place_native_atomic_bracket()` 
2. Whether TP ticks should be positive or negative for LONG positions

### Environment Note
- WebSocket errors still occurring (falling back to REST)
- .env file now loads correctly in check_positions.py
