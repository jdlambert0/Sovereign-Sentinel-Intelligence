# Broker API — balance & realized PnL (for LLMs)

**Code:** `C:\KAI\armada\projectx_broker_api.py`  
**Swagger:** `https://api.topstepx.com/swagger/v1/swagger.json`

## Balance
- `POST /api/Account/search` with `{"onlyActiveAccounts": true}`
- `TradingAccountModel.balance` — use `select_trading_account()`; optional `PROJECT_X_ACCOUNT_ID` in `.env`

## Realized PnL (RPNL)
Half-turn fills: `POST /api/Trade/search` with `accountId`, `startTimestamp`, `endTimestamp`. Sum `HalfTradeModel.profitAndLoss` where `voided` is false.

### Why your dashboard RPNL ≠ Sovran (historical)
Two **windows** are computed:
| Field | Window | Typical use |
|--------|--------|-------------|
| `net_pnl_session` | Last **17:00 America/Chicago** → now | Often closer to TopStep **combine “day”** / futures-style boundary |
| `net_pnl_calendar_day` | Midnight Chicago → now | Calendar “today” |

**Primary `net_pnl`** follows `SOVRAN_REALIZED_PNL_MODE` in `.env`:
- `session` (**default**) — aligns state `daily_pnl` with session-style RPNL (e.g. user seeing **-218.82** vs older **-95** calendar-only sum)
- `calendar` — use if you explicitly want midnight–midnight

If the UI still differs by a few dollars: possible causes include **fees** in another field, **partial fills**, **void** corrections, or a **different official session cut** (holiday / 16:00 vs 17:00). Treat API + logs as engineering truth; reconcile with support if needed.

## Related session logs
- [[2026-03-23_Preload_State_Lock_Order]]
- [[2026-03-23_ProjectX_Broker_API_Fix]]
