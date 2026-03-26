# Teaching Note: Gambling & Probability Frameworks (Kelly/RoR/Expectancy)

### 1. Kelly Criterion
- **Formula**: [(Win Rate * RR) - (Loss Rate)] / RR
- **Half-Kelly**: Use 50% of the suggested size for safety.
- **Goal**: Maximize logarithmic growth of the drawdown buffer.

### 2. Risk of Ruin
- **Goal**: Maintain RoR < 1%.
- **Action**: If Drawdown > $1,500 (approaching limit), reduce size to 1 MNQ regardless of confidence.

### 3. Expectancy
- **AI Task**: Calculate expectancy every 5 trades.
- **Adjustment**: If Expectancy is negative, switch to "Paper Trading only" for 10 turns to prove recovery.
