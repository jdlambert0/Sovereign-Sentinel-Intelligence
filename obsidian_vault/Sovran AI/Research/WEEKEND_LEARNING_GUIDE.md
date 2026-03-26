# MARL Gymnasium & Weekend Learning Guide

## 1. What is the MARL Gymnasium?
The **MARL (Multi-Agent Reinforcement Learning) Gymnasium** (`marl_gymnasium.py`) is an offline simulation environment. It allows the 9 engines to "replay" historical market ticks without risking real capital or paying live data fees.

## 2. Weekend Learning Workflow
Since the market is closed, you can run the "Study Mode" to refine the AI's internal weights:

### Step 1: Initialize the Study Session
Run the Gymnasium on Friday's data (saved in `_data_db`):
```powershell
C:\KAI\vortex\.venv312\Scripts\python.exe C:\KAI\armada\marl_gymnasium.py
```

### Step 2: Observation (The "Gym")
The script will:
1. Pick a historical tick from Friday.
2. Formulate a prompt based on that context (OFI, VPIN, Price).
3. Call the AI Council for a decision.
4. Compare the decision against what actually happened (Profit vs Loss).
5. Log the "Accuracy" score.

### Step 3: Optimization
The results are saved to `fleet_agents_digest.json`. On Monday morning, the live engines read this digest to know which "Pinned System" (Sovereign, Gambler, or Warwick) had the highest accuracy for that specific market condition.

## 3. Roadmap: Weekend Enhancements
| Feature | Status | Goal |
|---------|--------|------|
| **MARL Trainer 2.0** | Plan | Simulate 9 agents playing "against" each other for liquidity priority. |
| **Veto Audit 2.0** | Plan | Gemini checks Haiku decisions against 10 specific "Prop Firm Blowup" patterns. |
| **Obsidian Memory 5.0** | Plan | Agents create their own "Journal Entries" after each study session. |

---
*Status: READY | Action: Run marl_gymnasium.py | Date: March 20, 2026*
