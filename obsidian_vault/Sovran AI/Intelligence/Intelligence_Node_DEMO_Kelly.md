# [Intelligence Node] Kelly Criterion for Asymmetric Tails in MNQ
## Gumption Logic: Why we researched this
Recent trades in the fleet digest show that Sovereign Alpha is aggressive in trend following but lacks a mathematical anchor for 'sizing down' or 'sizing up' based on the specific probabilistic tail risk of Nasdaq futures (MNQ).

## Mathematical Invariants (The Logic)
The **Kelly Criterion** states that `f* = (bp - q) / b`, where:
- `f*` is the fraction of total bankroll to wager.
- `b` is the decimal odds (Profit/Loss ratio).
- `p` is the probability of winning.
- `q` is the probability of losing (1-p).

In MNQ, the 'odds' are often asymmetric. If our Target:Stop is 2.5:1, `b=2.5`. If our confidence from Council is 60%, `p=0.6`.
`f* = (2.5 * 0.6 - 0.4) / 2.5 = 0.44`.
However, applying full Kelly to systemic trading leads to ruin if the 'b' (odds) are miscalculated. We recommend **Fractional Kelly (Half-Kelly)** of 0.22, or a conservative 0.1 for Prop Firm accounts (TopStepX).

## Trading Alpha: How to use this in the next loop
When the council returns a confidence `p`, we compare it to a dynamic `b` based on current volatility-aware Target/Stop lines. If the `f*` (Kelly Fraction) is < 0.05, we should return WAIT regardless of signal strength, as the 'Expected Value' (EV) does not compensate for the tail risk.

## The Inversion: How this concept could still fail us
Kelly assumes we know the 'Win Rate' (p). In markets, `p` is ephemeral. This concept fails if we overestimate our edge or if the market regime shifts from trending to choppiness (mean-reversion), making our `b` (fixed target/stop) a liability.
