# Sovereign Teacher Protocol

The Sovereign Teacher is a standalone automated script (`sovran_teacher.py`) that performs daily high-fidelity audits of all trades and interactions.

## Core Functions
- **Trade Audit**: Pulls the most recent 24 hours of trade logs from the `Trades/` directory.
- **Pattern Recognition**: Calculates win/loss streaks and identifies the most effective market micro-structures (e.g., "High VPIN Momentum").
- **Playbook Synthesis**: Writes/updates the `Analytics/Master_Playbook.md` with actionable instructions for the LLM.

## Implementation Details
- **Sync Method**: Analyzes `ofi` and `vpin` metadata stored in Obsidian trade files.
- **Output**: Generates a structured markdown file that is injected back into the LLM prompt via `learning.get_accrued_intelligence()`.

## Usage
Run manually via:
```powershell
python sovran_teacher.py
```
Or as part of the daily automated loop.
