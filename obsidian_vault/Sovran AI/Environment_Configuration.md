# Environment Configuration - CRITICAL REFERENCE

**Last Updated**: 2026-03-18
**Status**: ✅ COMPLETE - All environment components located

---

## Python Virtual Environment

| Property | Value |
|----------|-------|
| **Path** | `C:\KAI\vortex\.venv312` |
| **Python Version** | 3.12 |
| **project_x_py Version** | 3.5.9 |
| **Location** | `C:\KAI\vortex\.venv312\Lib\site-packages\project_x_py` |

### Python Executable
```
C:\KAI\vortex\.venv312\Scripts\python.exe
```

### How to Run Scripts
```batch
cd C:\KAI\vortex
.venv312\Scripts\python.exe <script.py>
```

Or from armada:
```batch
cd C:\KAI\armada
C:\KAI\vortex\.venv312\Scripts\python.exe <script.py>
```

### Backup Venv (Pre-reboot)
```
C:\KAI\vortex_backup_20260313_pre_reboot\.venv312
```

---

## API Credentials

### TopStepX / ProjectX API Keys

Both keys are verified and valid:

| Key ID | Value | Location |
|--------|-------|----------|
| **Key A** | `9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=` | `C:\KAI\vortex\.env`, `C:\KAI\armada\.env` |
| **Key B** | `/S16+QEnTHSMA2lPuGdEs3ISwrzmuuMqvouqzgT3T8g=` | User-provided |

### Username
```
jessedavidlambert@gmail.com
```

### .env Files Locations

| Path | Last Modified | Contents |
|------|---------------|----------|
| `C:\KAI\vortex\.env` | 2026-03-17 14:00 | API Key A + OpenRouter config |
| `C:\KAI\armada\.env` | 2026-03-16 20:12 | API Key A |
| `C:\KAI\LOE\.env` | 2026-03-03 16:57 | API Key A |
| `C:\KAI\acttrade\.env` | 2026-03-03 16:45 | API Key A |

### Recommended .env for Armada
```env
PROJECT_X_API_KEY=/S16+QEnTHSMA2lPuGdEs3ISwrzmuuMqvouqzgT3T8g=
PROJECT_X_USERNAME=jessedavidlambert@gmail.com
```

Or use Key A:
```env
PROJECT_X_API_KEY=9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE=
PROJECT_X_USERNAME=jessedavidlambert@gmail.com
```

---

## Module Import Paths

### Primary (Venv)
```python
from project_x_py import TradingSuite
```

### Alternative (Local Source)
```python
import sys
sys.path.append(r"C:\KAI\SYSTEM")
from projectx import projectx_client
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `C:\KAI\armada\sovran_ai.py` | Main trading engine |
| `C:\KAI\vortex\.venv312\Lib\site-packages\signalrcore\transport\websockets\websocket_transport.py` | WebSocket patch location |
| `C:\KAI\armada\check_positions.py` | Broker verification |
| `C:\KAI\armada\hunter_alpha_trade_autonomous_demo.py` | Demo trade script |

---

## WebSocket MessagePack Patch

**File**: `C:\KAI\vortex\.venv312\Lib\site-packages\signalrcore\transport\websockets\websocket_transport.py`

**Reference**: `Bug Reports\WEBSOCKET_FIX_REFERENCE.md`

---

*Documented: 2026-03-18*
