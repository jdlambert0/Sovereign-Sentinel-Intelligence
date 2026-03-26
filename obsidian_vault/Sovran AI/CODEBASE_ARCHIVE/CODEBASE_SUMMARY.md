# Sovran AI Codebase Archive
**Purpose**: Complete reference for future AI sessions
**Last Updated**: 2026-03-18

---

## 🎯 QUICK START (For Next Session)

### To Fix SL/TP Bug:
1. Read `Action Plans/SLTP_Fix_Plan.md`
2. Check `sovran_ai.py` lines 1020-1100
3. Add debug logging to `calculate_size_and_execute()`

### To Understand System:
1. Read `CODEBASE_SUMMARY.md` (this file)
2. Read `sovran_ai.py` with annotations
3. Read `Bug Reports/COMPLETE_BUG_HISTORY.md`

### To Continue Documentation:
1. Check `Session Logs/2026-03-18-CONTEXT-LOSS-PLAN.md`
2. Copy remaining files (see below)
3. Create function-level annotations

---

## 📁 FILE STRUCTURE

```
Sovran AI/
├── 📚 CODEBASE ARCHIVE/
│   ├── CODEBASE_SUMMARY.md              ← THIS FILE
│   ├── sovran_ai/
│   │   ├── sovran_ai.py                ← Main engine (1900+ lines)
│   │   ├── sovran_mailbox.py           ← LLM integration
│   │   └── api_types.py                ← Type definitions
│   └── sdk_patches/
│       ├── websocket_transport_PATCHED.py ← CRITICAL: WebSocket fix
│       └── PROJECT_X_PY_OVERVIEW.md    ← SDK structure guide
├── 🐛 Bug Reports/
│   ├── COMPLETE_BUG_HISTORY.md         ← All bugs & fix attempts
│   ├── MASTER_BUG_SUMMARY.md            ← Quick bug reference
│   └── WEBSOCKET_FIX_REFERENCE.md      ← WebSocket fix guide
├── 📋 Action Plans/
│   └── SLTP_Fix_Plan.md               ← SL/TP fix priority
├── 🤖 AI Mailbox/
│   └── README.md                       ← Session handoff protocol
└── 📝 Session Logs/
    ├── 2026-03-18-CONTEXT-LOSS-PLAN.md ← THIS SESSION TRANSFER
    └── [Other session logs]

Note: Code files also stored in /Architecture/ folder:
├── Architecture/
│   ├── sovran_ai_FINAL.py
│   ├── sovran_mailbox.py
│   ├── api_types.py
│   └── websocket_transport_PATCHED.py
```

---

## 📄 CORE FILES (Sovran AI)

### 1. `sovran_ai.py` - Main Trading Engine
**Location**: `CODEBASE_ARCHIVE/sovran_ai/sovran_ai.py`
**Lines**: ~1900
**Purpose**: AI-driven trading engine that:
- Connects to TopStepX via TradingSuite
- Receives market data (price, bid, ask)
- Calls Hunter Alpha (LLM) for trade decisions
- Executes trades with SL/TP brackets
- Manages position lifecycle

**Key Functions**:
| Function | Lines | Purpose |
|----------|-------|---------|
| `calculate_size_and_execute()` | 1020-1100 | ⚠️ **CRITICAL** - Trade execution with SL/TP |
| `retrieve_ai_decision()` | ~1130 | Call Hunter Alpha for signal |
| `handle_quote()` | ~570 | Process market data |
| `handle_trade()` | ~630 | Process trade ticks |

**BUG ALERT**: `calculate_size_and_execute()` may not attach SL/TP properly (BUG-002)

---

### 2. `sovran_mailbox.py` - LLM Integration
**Location**: `CODEBASE_ARCHIVE/sovran_ai/sovran_mailbox.py`
**Purpose**: Interface between Sovran and Hunter Alpha (LLM)
- Formats trading context for LLM
- Parses LLM decisions
- Handles communication with LLM API

---

### 3. `api_types.py` - Type Definitions
**Location**: `CODEBASE_ARCHIVE/sovran_ai/api_types.py`
**Purpose**: Python type hints and data classes
- `QuoteData`: bid, ask, last_price
- `TradeDecision`: action, confidence, stop_points, target_points
- `Position`: size, averagePrice, etc.

---

## 🔧 SDK FILES (project_x_py)

### ⚠️ CRITICAL: `websocket_transport.py` - WebSocket Patch
**Location**: `CODEBASE_ARCHIVE/sdk_patches/websocket_transport_PATCHED.py`
**Purpose**: Handles WebSocket communication with TopStepX

**Why It Was Modified**:
- TopStepX uses bimodal protocol:
  1. JSON handshake (works)
  2. MessagePack binary data (broke everything)
- Original signalrcore SDK expected JSON only
- Binary frames caused: `JSONDecodeError: Expecting value: line 1 column 4093`

**The Fix (Lines 85-113)**:
```python
# Check if message is bytes (MessagePack)
if isinstance(raw_message, bytes):
    import msgpack
    unpacked = msgpack.unpackb(raw_message, ...)
    raw_message = json.dumps(unpacked)
```

**⚠️ WARNING**: This patch will be OVERWRITTEN if you run:
- `pip install --upgrade signalrcore`
- Recreate virtual environment
See: `Bug Reports/WEBSOCKET_FIX_REFERENCE.md`

---

## 🐛 BUG REPORTS

### Critical Bugs:

| Bug ID | Issue | Status | Fix Location |
|--------|-------|--------|--------------|
| BUG-002 | SL/TP Missing | ❌ ONGOING | `sovran_ai.py` lines 1020-1100 |
| BUG-001 | WebSocket MessagePack | ✅ FIXED | `websocket_transport.py` |

### All Bugs:
See `Bug Reports/COMPLETE_BUG_HISTORY.md` for complete history of all fix attempts.

---

## 🚀 EXECUTION GUIDE

### Start Sovran (Background):
```batch
wscript "C:\KAI\armada\StartArmada.vbs"
```

### Check Logs:
```powershell
Get-Content "C:\KAI\armada\_logs\sovran_today.log" -Tail 50
```

### Kill Stuck Processes:
```powershell
Get-Process python* | Stop-Process -Force
```

---

## 📋 DOCUMENTATION CHECKLIST (Next Session)

- [ ] Annotate `sovran_ai.py` function-by-function
- [ ] Copy `phase_runner.py` to archive
- [ ] Create `PROJECT_X_PY_OVERVIEW.md` explaining SDK
- [ ] Document `sovran_mailbox.py`
- [ ] Add Big Pickle tips
- [ ] Add Hunter Alpha tips

---

## 🔗 EXTERNAL DEPENDENCIES

### TopStepX
- API: `project_x_py` SDK
- WebSocket: `signalrcore`
- Trading: REST API (primary), WebSocket (patched)

### LLM Providers
- Primary: Anthropic (Claude)
- Fallback: DeepSeek via OpenRouter
- Config: `.env` file

---

## 📊 SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    SOVERAN AI (Main Engine)                  │
│                     sovran_ai.py                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ handle_quote│  │handle_trade │  │calculate_size_and_  │ │
│  │   (price)   │  │   (fills)   │  │execute (trade+SLTP) │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    PROJECT_X_PY SDK                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ RealtimeData│  │ PositionMgr │  │   OrderManager       │ │
│  │ Manager     │  │             │  │   (place_market_     │ │
│  │             │  │             │  │    order + brackets) │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                    │            │
│         ▼                ▼                    ▼            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              signalrcore (WebSocket)               │    │
│  │         websocket_transport.py ⚠️ PATCHED          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    TopStepX     │
                    │   (Trading)      │
                    └─────────────────┘
```

---

## 📝 SESSION NOTES

### 2026-03-18 Session:
- **Accomplished**: WebSocket patch applied, tested, documented
- **Bug Found**: SL/TP not attached to trades (8:30am trade)
- **Context Loss**: Refresh recommended after this session
- **Next Priority**: Fix SL/TP bug

### For Full Session Details:
See `Session Logs/2026-03-18-CONTEXT-LOSS-PLAN.md`

---

## ✅ VERIFICATION CHECKLIST

Before considering the system working:

- [ ] SL/TP brackets attached to orders (BUG-002 check)
- [ ] WebSocket connects (off-hours)
- [ ] Hunter Alpha receives market data
- [ ] Trade decisions logged
- [ ] Position tracking accurate
- [ ] No command windows popping up

---

## 🎓 LEARNINGS FOR FUTURE SESSIONS

1. **Always use `wscript`** for background processes
2. **Log everything** - especially order responses
3. **Check SL/TP first** - critical risk management
4. **Document fixes immediately** - in Obsidian AND in comments
5. **Backup before modifying SDK files** - patches get overwritten

---

*Document created: 2026-03-18*
*Part of Sovran AI Codebase Archive*
*Use with: COMPLETE_BUG_HISTORY.md, SLTP_Fix_Plan.md*
