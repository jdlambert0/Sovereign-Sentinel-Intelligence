# Sovran AI - Comprehensive Test Plan

**Date:** 2026-03-17
**Purpose:** Verify all system components work end-to-end before teaching AI to trade
**Success Criteria:** 10/10 tests passing

---

## Test Phases

### Phase 2: Component Verification (5 Tests)
| # | Test | Component | Status |
|---|------|-----------|--------|
| 2.1 | TopStepX Connection | API/SDK | PASS (2026-03-17) |
| 2.2 | Quote Data Flow | Market Data | PASS (2026-03-17) |
| 2.3 | SL/TP Bracket Orders | Order Execution | PASS (2026-03-17) |
| 2.4 | Position Management | Position Tracking | PASS (2026-03-17) |
| 2.5 | Learning System | Obsidian Integration | PASS (2026-03-17) |

### Phase 3: End-to-End Trading (5 Tests)
| # | Test | Scope | Status |
|---|------|-------|--------|
| 3.1 | Single Trade Cycle | Signal → Exit | PASS (2026-03-17) |
| 3.2 | 5-Trade Burst | 5 trades | PASS (2026-03-17) |
| 3.3 | 10-Trade Research | Learning trigger | PASS (2026-03-17) |
| 3.4 | Mailbox Integration | Human-AI comms | PASS (2026-03-17) |
| 3.5 | Dynamic Parameters | Config changes | PASS (2026-03-17) |

### Phase 4: Safety & Recovery (5 Tests)
| # | Test | Scenario | Status |
|---|------|----------|--------|
| 4.1 | WebSocket Disconnect | Reconnection | ⏳ Pending (2026-03-23: not run — needs controlled disconnect) |
| 4.2 | Stop Loss Hit | SL execution | ⏳ Pending (2026-03-23: not run — needs live bracket fill) |
| 4.3 | Take Profit Hit | TP execution | ⏳ Pending (2026-03-23: not run — needs live bracket fill) |
| 4.4 | Drawdown Protection | $500 limit | ⏳ Pending (2026-03-23: not run) |
| 4.5 | Process Restart | Recovery | ⏳ Pending (2026-03-23: not run) |

### Phase 5: Production Readiness (3 Tests)
| # | Test | Duration | Status |
|---|------|----------|--------|
| 5.1 | 24-Hour Run | 24 hours | ⏳ Pending (2026-03-23: not run — wall-clock) |
| 5.2 | Multi-Market | 3 symbols | ⏳ Pending — watchdog restart path uses `--symbols MNQ,MES,M2K` (2026-03-23); full checklist sign-off still open |
| 5.3 | LLM Rate Limits | API handling | partial PASS (2026-03-23) — monitor WARN on 429; backoff in OpenRouter provider |

---

## Test Environment

- **Python:** `C:\KAI\vortex\.venv312\Scripts\python.exe`
- **Working Dir:** `C:\KAI\armada`
- **Vault:** `C:\KAI\obsidian_vault\Sovran AI`
- **Account:** TopStepX Paper Trading (Combine)
- **Symbol:** MNQ (Micro Nasdaq)

---

## Test Procedures

### TEST 2.1: TopStepX Connection
```bash
cd /c/KAI/armada
/c/KAI/vortex/.venv312/Scripts/python.exe -c "
import asyncio
from project_x_py import TradingSuite
async def test():
    suite = await TradingSuite.create('MNQ')
    print('Connected:', suite is not None)
    await suite.disconnect()
asyncio.run(test())
"
```

### TEST 2.2: Quote Data Flow
1. Run `sovran_ai.py` briefly
2. Check logs for quote updates
3. Verify `last_price`, `bid`, `ask` updating

### TEST 2.3: SL/TP Bracket Orders
```bash
# Run single trade with brackets
cd /c/KAI/armada
/c/KAI/vortex/.venv312/Scripts/python.exe test_place_order_with_brackets.py
```

### TEST 2.4: Position Management
1. Open position
2. Close position
3. Verify P&L recorded

### TEST 2.5: Learning System
1. Run burst test
2. Check Obsidian Trades/ folder
3. Verify trade count incremented

---

## Results Tracking

All test results recorded in:
- `Testing/TEST_RESULTS.md`
- Individual test files in `Testing/Phase*_*/`
- Bug reports in `Bug Reports/`

---

## Notes for Future AI Agents

1. **Always update status** after each test in this file
2. **Create bug report** if test fails and cannot be fixed easily
3. **Document everything** - logs and positions help with bug discovery
4. **Market hours** - Tests 3.x require market hours (9:30 AM - 4 PM CT)

---
*Status: Phases 2–3 executed (2026-03-17) per TEST_RESULTS.md; Phase 4–5 RTH pending; 5.3 partial (2026-03-23). Session 2026-03-23: preflight 45/45 + monitor snapshot only (see TEST_RESULTS.md). Phase 4 runbook: `Testing/PHASE_4_RUNBOOK.md`.*
