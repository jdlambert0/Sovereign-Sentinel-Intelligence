# BUG-003: TradingSuite instrument_id Execution Crash

**Status:** UNRESOLVED
**Date:** 2026-03-16

## Symptom
The `sovran_ai.py` live trading bot contains a critical latent execution error that will crash the system the moment an LLM generates a valid `BUY` or `SELL` command. It has remained undiscovered because the AI has correctly filtered all trades with `WAIT` so far.

## Location
`C:\KAI\armada\sovran_ai.py` - Line 666, within `AIGamblerEngine.execute_decision()`.

## Hypothesis
The specific line attempting to place a bracket order uses:
```python
contract_id=self.suite.instrument_id,
```
However, testing confirmed that the encapsulated `context` object passed to `AIGamblerEngine` (which acts as `self.suite`) does **not** possess an `instrument_id` attribute. Instead, the TopStepX API SDK encapsulates this identifier within an `instrument_info` object (`self.suite.instrument_info.id`). 

When the LLM eventually resolves to enter the market, the API client would crash with an `AttributeError`, leaving the engine ungracefully halted.

## Context
During the user-requested manual trade verification, I constructed a replica order execution script (`place_test_trade.py`) using the exact logic the `sovran_ai` engine uses to submit bracket orders to the TopStepX platform.

During testing, attempting to extract the instrument ID using the live system's syntax raised an `AttributeError`. Dumping the directory attributes revealed the correct `instrument_info` nesting. 

## Proposed Fix
In `sovran_ai.py`, update `AIGamblerEngine.execute_decision` to extract the correct `instrument_id`.

```python
# Before
await self.suite.orders.place_bracket_order(
    contract_id=self.suite.instrument_id, ... 
)

# After
instrument_id = getattr(self.suite.instrument_info, "id", None)
await self.suite.orders.place_bracket_order(
    contract_id=instrument_id, ...
)
```

**Note:** The system must also correctly parse the `instrumentId` when executing the manual cleanup loops on Position/Orders (Line 697).
