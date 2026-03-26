# Sovereign System Hardening Plan (GSD-Minion Phase 2)

## 🎯 Objective
Achieve 100% operational reliability for the Sovereign Hunt by eliminating terminal crashes, session collisions, and ledger drift.

## 🛠️ Execution Roadmap

### 1. Structural Hardening (Immediate)
- [x] **Unicode Armor Implementation**: Patch `sovran_ai.py` to programmatically scrub emojis and force UTF-8 logging in all subprocesses.
- [x] **Singleton OS Lock**: Implement a mandatory file-based lock (`.sovereign.lock`) to prevent concurrent API sessions.
- [x] **Ledger Reconciliation**: Force the Master Anchor to Broker Truth: Balance **$148,912.57** | Session PnL **-$747.25**.
- [x] **Cooldown Removal**: Delete the artificial 17:00-17:30 CT market cooldown to allow continuous 24/5 execution.

### 2. Validation & Diagnostics
- [x] **Sovereign Test Suite**: Create `tests/test_sovereign_reliability.py` to verify the Singleton lock and Unicode scrubbing.
- [x] **Bridge Diagnostic Program**: Create `diagnose_bridge_execution.py` to trace manual commands from JSON to REST Fill.
- [x] **Mock Execution Environment**: Implement `mock_sovran_engine.py` to simulate 1,000+ trades and stress-test the PnL stabilizer.

### 3. GSD-Minion Continuous Improvement
- [x] **Automated Context Refresh**: Implement the CRP (Context Refresh Protocol) to clear AI hallucinations.
- [x] **Lightpanda Scraper**: Migrate all external research to the Lightpanda headless browser.
- [x] **Notification Subsystem**: Implement OSC 9 terminal notifications and system beeps.
- [ ] **Live Server Validation**: Deploy the hardened engine to the TopStepX live environment with 1-contract "canary" lots.

---
*Plan formulated by Antigravity - Sovereign Agentic Hub.*
*Status: **READY FOR EXECUTION***
