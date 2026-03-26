# Sovran Hunt: Night Hunter Strategy

## 🌑 The Objective
To execute a fully autonomous, high-frequency "Hunting" session during the overnight (Globex) session, maximizing profit potential until the system hits predefined usage limits (API rate limits or LLM token limits).

## 🛠️ The "Night Hunter" Loop
The following loop is designed for **Unattended Execution**:

1.  **State Persistence**: Before each trade, the Hunter writes its current "Mental State" to `_data_db/night_hunter_v1.json`.
2.  **Autonomous Entry**:
    - The `sovran_hunter.py` listener identifies a "Liquidity Cluster" (e.g., a 200-lot buy wall on MNQ).
    - It pushes a `BUY_MARKET` signal to `command_hub.py`.
3.  **Dynamic Risk Adjustment**:
    - Once filled, the `RiskManager` instantly attaches a **Trailing Stop** (15 ticks) and a **Scalp Target** (10 ticks).
4.  **Usage Monitoring**:
    - **API Rate Limits**: The system monitors `X-RateLimit-Remaining` headers. If < 10, it pauses for 60s.
    - **Token Management**: The Hunter summarizes its last 5 trades into a "Context Voucher" to keep the LLM's memory lean and prevent token exhaustion.

## 🏁 The Exit Strategy
The Night Hunter terminates ONLY when:
1.  **Stop-Loss Threshold**: Total realized PnL for the session hits -$500.
2.  **Usage Cap**: LLM usage hits 95% of the daily limit.
3.  **Market Close**: 4:00 PM EST (Friday) or daily maintenance windows.

## 📝 Execution Command
To start the Night Hunter:
```powershell
# Run the hub first
Start-Process python "C:\KAI\armada\command_hub.py"
# Launch the Hunter in Persistent Mode
C:\KAI\vortex\.venv312\Scripts\python.exe C:\KAI\armada\sovran_hunter.py --overnight --max-trades 50
```
