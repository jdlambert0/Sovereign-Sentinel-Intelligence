# SL/TP Visibility & MEMM Grid Analysis

## 1. SL/TP Invisibility Investigation
**Root Cause Hypothesis:**
- **CSV Limitation:** `trades_export.csv` is a base-level export that does not capture bracket metadata. The absence of SL/TP in the CSV does NOT mean they weren't placed.
- **Platform Settings:** TopStepX hides API-generated brackets unless **"Position Brackets"** are enabled in the specific account's Risk Management portal.
- **Sign Convention:** Verified correct in `sovran_ai.py` (Negative ticks for Long SL).

**Remediation:**
- We will implement a **Bracket Validation Diagnostic** that logs the exact API success message for every SL/TP attachment.
- We recommend the user verify "Position Brackets" are toggled ON in the TopStepX web platform settings.

## 2. Multi-Engine Multi-Market (MEMM) Grid
**Current Bottleneck:**
- The system currently pins exactly ONE engine per symbol when >=3 symbols are used. 
- (e.g., MNQ = Sovereign, MES = Gambler, MYM = Warwick).

**Proposed MEMM Architecture:**
We will refactor the `run()` loop to a 3x3 Grid:
- **MNQ**: Sovereign, Gambler, Warwick (3 instances)
- **MES**: Sovereign, Gambler, Warwick (3 instances)
- **MYM**: Sovereign, Gambler, Warwick (3 instances)
- **Total**: 9 independent concurrent engine tasks.

**State Management:**
Each "Slot" (Symbol + System) will have a unique state file:
- `sovran_ai_state_MNQ_sovereign.json`
- `sovran_ai_state_MNQ_gambler.json`
- ...etc.

## 3. "Trade Every Turn" Guarantee
With 9 engines running, the "Every Turn" mandate will be enforced per-engine. Even if one system (e.g., Warwick) hits a cooling period, the other 2 on the same symbol can still fire.

---
*Status: RESEARCH COMPLETE | Plan: MEMM Grid | Date: March 20, 2026*
