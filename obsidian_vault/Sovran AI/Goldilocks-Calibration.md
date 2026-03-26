# Goldilocks Calibration — Sovran V2

These thresholds represent the system's "ideal execution" state — the
conditions under which Sovran should trade. Named Goldilocks because
conditions must be "just right": not too hot (volatile/unknown regime),
not too cold (no institutional flow), but exactly right.

Implemented in `live_session_v5.py` (Goldilocks Edition).

## Signal Thresholds

| Signal | Threshold | Meaning |
|--------|-----------|---------|
| OFI Z-Score | > 1.5 | Institutional order flow displacement above 1.5 standard deviations |
| VPIN | > 0.55 | Probability of Informed Trading above 55% |
| High-Conviction Combo | OFI_Z > 2.0 AND VPIN > 0.70 | Both institutional signals firing together |
| LLM Consensus Gate | >= 0.50 | AI must agree with signal direction (50% threshold) |

## Banned Trading Phases

| Phase | Time (CT) | Reason |
|-------|-----------|--------|
| Early Afternoon | 12:30 - 14:00 CT | Lunch chop, low institutional participation |

## V5 Startup Fix: REST Bar Seeding

**Problem:** WebSocket `GatewayTrade` events take 7-10 minutes to accumulate
enough buy/sell volume for the `MIN_FLOW_TRADES = 50` gate. Until then,
every market scores B:0 S:0 and no trades fire.

**Solution:** `_seed_historical_bars()` calls `POST /api/History/retrieveBars`
at startup to fetch the last 30 1-min bars per contract. Instantly populates
buy/sell volume (60/40 split by bar direction), VWAP, price history, and
tick_count — so the first scan cycle has real data.

## Implementation Status

- [x] OFI Z-Score gate in `live_session_v5.py` (gate at `analyze_market`)
- [x] VPIN gate in `live_session_v5.py` (gate at `analyze_market`)
- [x] Banned phase 12:30-14:00 CT hard block in `live_session_v5.py`
- [x] REST bar seeding at startup (`_seed_historical_bars`)
- [ ] LLM consensus gate (currently bypassed — pure signal scoring mode)
- [ ] High-conviction combo (OFI_Z > 2.0 AND VPIN > 0.70) bonus scoring

## Rationale

OFI Z-Score > 1.5 identifies when institutional players are displacing
price — our edge comes from following informed order flow. VPIN > 0.55
confirms that the probability of trading against informed participants
is high enough to justify risk. The 12:30-14:00 CT ban eliminates the
most statistically lossy period for micro-futures flow strategies.

## Related

- [[KAIZEN_TRADING_FRAMEWORK]] — Overall Kaizen philosophy
- [[2026-03-26-V4-Kaizen-Validation]] — V4 live trade results (proof Kaizen works)
- GitHub: `sovran_v2/live_session_v5.py`

## Calibration History

| Date | Version | Change | Reason |
|------|---------|--------|--------|
| 2026-03-26 | V5 | Initial Goldilocks calibration | Eliminate B:0 S:0 warmup + filter uninformed flow |
