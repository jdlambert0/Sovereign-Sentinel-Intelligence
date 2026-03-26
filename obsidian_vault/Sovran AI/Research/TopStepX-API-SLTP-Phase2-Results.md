Phase 2 Results: Atomic Bracket Integration

Date: 2026-03-18
Overview: Validated atomic SL/TP bracket placement via TopStepX native API in an end-to-end manner. SL is Stop Market (type 4) with negative ticks for LONG; TP is Limit (type 1) with positive ticks. OFF Position Brackets prerequisite observed; atomic bracket path works as a single API call.

Test flow summary:
- Acquire token via TradingSuite
- Call POST /api/Order/place with stopLossBracket and takeProfitBracket in a single payload
- Confirm response: success: true, orderId
- Verify open orders reflect both SL and TP
- Cleanup: Cancel existing orders to avoid interference

Key constraints observed:
- LONG entries require stopLossBracket.ticks negative (e.g., -400)
- Stop Market (type 4) used for SL
- Take Profit (type 1) used for TP
- Token must be valid for the duration of the test

Open Questions:
- How does UI reflect API-linked brackets vs account-level brackets?
- Is get_position_orders() valid for linked orders, or is it SDK-only visibility?

Next steps:
- Integrate place_native_atomic_bracket() into Sovran AI's trading loop
- Implement a fallback path: if REST API is unavailable, revert to a safe manual approach
- Run continuous end-to-end testing in a controlled environment

- Phase 2 Test Runs (Log Summary)
- Run 3: Atomic bracket path used in integrated phase; REST API bracket call reported success; 3rd orderId generated
- Run 1: Order placed with SL -400 ticks, TP 200 ticks; response: orderId 2660183597; success true
- Run 2: Order placed with SL -400 ticks, TP 200 ticks; response: orderId 2660192664; success true
- Observed REST path success; WebSocket logs show intermittent connectivity but REST path remained robust for API calls
