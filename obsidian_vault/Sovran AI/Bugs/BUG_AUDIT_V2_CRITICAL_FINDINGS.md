# BUG AUDIT V2 — Critical Findings (March 22, 2026)

**Audit Scope:** `C:\KAI\armada\sovran_ai.py` (2,462 lines)  
**Audit Type:** Deep Static Analysis + Log Correlation  
**Date:** 2026-03-22  
**Status:** 🔴 **6 BUGS FOUND — 3 CRITICAL (CRASH), 2 HIGH, 1 MEDIUM**

---

## 🔴 BUG-V2-001: Missing Vote-Counting Variables (CRASH)
**Severity:** CRITICAL  
**Location:** `sovran_ai.py`, Line 1332  
**Symptom:** `NameError: name 'buy_votes' is not defined`  

**Evidence:** Lines 1330-1332:
```python
if not decisions:
    action_result = "WAIT"
elif buy_votes > sell_votes and buy_votes >= wait_votes:
```

The variables `buy_votes`, `sell_votes`, and `wait_votes` are **never defined**. The code that should count votes from the `decisions` list is **completely missing** between lines 1330 and 1332.

**Impact:** The entire LLM Ensemble Consensus system crashes on EVERY trading cycle where the LLM returns a valid decision. The system **cannot** trade via the Sovereign Alpha engine.

**Fix:** Insert vote-counting logic before line 1332:
```python
buy_votes = sum(1 for d in decisions if d.get("action","").upper() == "BUY")
sell_votes = sum(1 for d in decisions if d.get("action","").upper() == "SELL")
wait_votes = sum(1 for d in decisions if d.get("action","").upper() == "WAIT")
```

---

## 🔴 BUG-V2-002: `emergency_flatten()` Method Not Defined (CRASH)
**Severity:** CRITICAL  
**Location:** `sovran_ai.py`, Line 1440 (called), **nowhere defined**  
**Symptom:** `AttributeError: 'AIGamblerEngine' object has no attribute 'emergency_flatten'`

**Evidence:** Line 1440:
```python
await self.emergency_flatten()
```
This is called when the AI detects an opposite signal while holding a position. The method body does not exist anywhere in the class.

**Impact:** If the AI ever decides to reverse direction while holding a position, the system crashes. No graceful exit from opposing trades.

**Fix:** Define the method using the existing `get_manual_token()` + REST flatten API.

---

## 🔴 BUG-V2-003: `current_stack_count` Undefined in `gamble_cycle` (CRASH)
**Severity:** CRITICAL  
**Location:** `sovran_ai.py`, Line 939 (inside `gamble_cycle`)  
**Symptom:** `NameError: name 'current_stack_count' is not defined`

**Evidence:** Line 939:
```python
"stack_count": current_stack_count + 1,
```
This variable is defined inside `calculate_size_and_execute` (line 1424) but not inside `gamble_cycle`. If the gambler successfully places a trade, it crashes while recording the active trade.

**Impact:** Every successful Gambler trade crashes the engine during state recording.

**Fix:** Add `current_stack_count = self.active_trade.get("stack_count", 0) if self.active_trade else 0` at the top of `gamble_cycle`.

---

## 🟡 BUG-V2-004: `GAMBLE_MANDATE` Overrides Risk Vault
**Severity:** HIGH  
**Location:** `sovran_ai.py`, Line 2199-2200  
**Symptom:** Global loss limit ($450) is **completely bypassed** when `GAMBLE_MANDATE = True`

**Evidence:**
```python
if total_pnl <= self.daily_limit:
    if GAMBLE_MANDATE:
        logger.warning(f"[RISK] GLOBAL LOSS LIMIT REACHED ... but GAMBLE_MANDATE is active. CONTINUING.")
```

**Impact:** With `GAMBLE_MANDATE = True` (currently line 98), the system will **never** flatten positions on hitting the daily loss limit. This makes the $450 global risk cap a dead letter. The system can lose the entire $4,500 bankroll in a single day.

**Fix:** Remove the `GAMBLE_MANDATE` override from `GlobalRiskVault`. Risk limits must be inviolable.

---

## 🟡 BUG-V2-005: `handle_trade` Scope Bug — `delta` Outside `try/except`
**Severity:** HIGH  
**Location:** `sovran_ai.py`, Lines 816–824  
**Symptom:** `NameError: name 'delta' is not defined` if the trade tick parsing fails

**Evidence:** Lines 815-824:
```python
                delta = vol if side == 0 else -vol  # inside try
                # ...
        except Exception as e:
            logger.error(f"Error processing trade: {e}")

        now = time.time()
        self.ofi_history.append((now, delta))  # outside try — delta may not exist
```

If any error occurs inside the try block before `delta` is assigned, the code after the `except` block still tries to use `delta`, causing a second crash.

**Impact:** A malformed trade tick causes a double-fault crash.

**Fix:** Move OFI history appending inside the try block, or initialize `delta = 0` before the try.

---

## 🟠 BUG-V2-006: Hardcoded Credentials
**Severity:** MEDIUM (Security)  
**Location:** `sovran_ai.py`, Lines 2314-2315  
**Symptom:** API credentials hardcoded in source

**Evidence:**
```python
os.environ["PROJECT_X_USERNAME"] = "jessedavidlambert@gmail.com"
os.environ["PROJECT_X_API_KEY"] = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="
```

**Impact:** Credentials exposed in any shared code or logs.

**Fix:** Remove hardcoded values. Rely solely on `.env` file.

---

## Summary Table

| ID | Severity | Bug | Status |
|---|---|---|---|
| V2-001 | 🔴 CRITICAL | Missing vote-counting in ensemble consensus | OPEN |
| V2-002 | 🔴 CRITICAL | `emergency_flatten()` not defined | OPEN |
| V2-003 | 🔴 CRITICAL | `current_stack_count` undefined in gamble_cycle | OPEN |
| V2-004 | 🟡 HIGH | GAMBLE_MANDATE bypasses risk vault | OPEN |
| V2-005 | 🟡 HIGH | `delta` scope escape in handle_trade | OPEN |
| V2-006 | 🟠 MEDIUM | Hardcoded API credentials | OPEN |
