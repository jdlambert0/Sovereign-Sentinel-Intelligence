# File-Based IPC — AI Brain Interface

This directory is the communication channel between Sovran's trading system and your external AI agent (Gemini CLI, Accio, Antigravity, Claude Code, etc.).

## How It Works

1. **Sovran writes a request**: `ipc/request_{timestamp}.json`
2. **Your AI reads it**, reasons about the market data, and writes: `ipc/response_{timestamp}.json`
3. **Sovran reads the response** and acts on it (or doesn't, if it says `no_trade`)

## Request Format

```json
{
  "request_id": 1711382400000,
  "timestamp": "2026-03-25T12:00:00Z",
  "prompt": "... full natural language analysis prompt ...",
  "expected_response_path": "ipc/response_1711382400000.json",
  "response_schema": { ... },
  "snapshot_data": {
    "contract_id": "CON.F.US.MNQM26",
    "last_price": 18000.50,
    "atr_points": 12.5,
    "vpin": 0.32,
    "ofi_zscore": 1.8,
    "regime": "trending_up",
    ...
  }
}
```

## Response Format

Your AI must write this JSON to the `expected_response_path`:

```json
{
  "signal": "long",
  "conviction": 82,
  "thesis": "Strong bullish momentum with OFI confirming buy pressure. ATR suggests 15pt stop is safe.",
  "stop_distance_points": 15.0,
  "target_distance_points": 30.0,
  "frameworks_cited": ["momentum", "order_flow"],
  "time_horizon": "scalp"
}
```

### Signal values: `"long"`, `"short"`, or `"no_trade"`

## Tips for Your AI Agent

- The `prompt` field contains everything the AI needs in natural language
- The `snapshot_data` field has the same data in structured form — use whichever is easier
- Conviction must be >= 70 for the system to act on it
- `stop_distance_points` and `target_distance_points` are in POINTS, not ticks
- When in doubt, say `"no_trade"` — capital preservation is paramount
- The system polls every 0.5s, max wait 120s before timeout

## Example Watcher Script

```python
import json, time, glob, os

IPC_DIR = "ipc"
while True:
    requests = glob.glob(os.path.join(IPC_DIR, "request_*.json"))
    for req_path in requests:
        with open(req_path) as f:
            req = json.load(f)
        
        # YOUR AI LOGIC HERE
        response = your_ai_analyze(req["prompt"])
        
        with open(req["expected_response_path"], "w") as f:
            json.dump(response, f)
    
    time.sleep(0.5)
```
