# 2026-03-16 Preflight Unicode Fix

## Problem
Preflight validation was failing with UnicodeEncodeError: 'charmap' codec can't encode character '\u2705' in position X: character maps to <undefined>
This occurred when trying to print checkmark (✅) and cross (❌) characters to Windows console with cp1252 encoding.

## Root Cause
The `check()` and `warn()` functions in preflight.py were using Unicode characters (✅, ❌, ⚠️) that cannot be encoded by Windows console's default cp1252 codepage.

## Solution
Replaced Unicode characters with ASCII equivalents:
- ✅ → + (pass)
- ❌ → x (fail)  
- ⚠️ → ! (warning)

## Changes Made
Modified C:\KAI\armada\preflight.py:
1. Line 58: Changed `icon = "✅" if passed else "❌"` to `icon = "+" if passed else "x"`
2. Line 63: Changed `print(f"  ⚠️  {name}" + ...)` to `print(f"  ! {name}" + ...)`
3. Lines 365 & 370: Changed verdict output from Unicode to ASCII equivalents
4. Fixed indentation issue in VERDICT section (lines 360-376)

## Verification
After fix:
- Preflight now passes 39/39 gates
- System is cleared for Monday deployment
- Results saved to C:\KAI\armada\_logs\preflight_results.json

## Context
This fix maintains the deterministic nature of preflight while ensuring compatibility with Windows console encoding requirements. The change is purely cosmetic - all validation logic remains unchanged.

## Tags
#preflight #unicode-fix #windows-compatibility #zbi-protocol