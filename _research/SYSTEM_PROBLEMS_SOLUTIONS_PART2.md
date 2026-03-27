# Sovran V2 Problems 5-8: Solutions (Part 2)

## Problem 5: No Outcome Tracking for Bayesian Updates

### Root Cause Analysis

**Missing:** Post-trade Bayesian probability adjustment
**Current:** Static probability models (conviction scoring uses fixed weights)
**Needed:** Update beliefs based on actual win/loss outcomes

---

### Solution: Bayesian Belief Engine

```python
# src/bayesian_beliefs.py
from dataclasses import dataclass
from typing import Dict
import json

@dataclass
class BeliefState:
    signal_name: str
    alpha: float = 1.0  # Successes
    beta: float = 1.0   # Failures

    @property
    def mean_probability(self) -> float:
        return self.alpha / (self.alpha + self.beta)

class BayesianBeliefEngine:
    def __init__(self, config_path: str = "config/beliefs.json"):
        self.beliefs: Dict[str, BeliefState] = {
            'ofi_strong': BeliefState('ofi_strong', alpha=2, beta=2),
            'vpin_toxic': BeliefState('vpin_toxic', alpha=2, beta=2),
        }

    def update_belief(self, signal_name: str, outcome: bool):
        belief = self.beliefs[signal_name]
        if outcome:
            belief.alpha += 1
        else:
            belief.beta += 1
```

---

## Problem 6: Pre-commit Hook Failures

### Solution: Use Local Mypy

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: mypy
        language: system
        types: [python]
        args: [--ignore-missing-imports]
```

---

## Problem 7: Win Rate Extremely Low (7%)

### Diagnosis Using MFE/MAE

**7% win rate = fundamental problem, not bad luck**

**Typical benchmarks:**
- Mean Reversion: 60-70% WR
- Momentum: 40-50% WR
- Your system: 7% WR ← **BROKEN**

**Use MFE/MAE to diagnose:**

```python
def diagnose_low_win_rate(trades):
    losses = [t for t in trades if t.pnl <= 0]
    avg_mfe_on_losses = sum(t.mfe for t in losses) / len(losses)

    if avg_mfe_on_losses < 3.0:
        return "BAD ENTRIES - increase conviction threshold"
    elif avg_mfe_on_losses > 15.0:
        return "BAD EXITS - add trailing stops"
    else:
        return "NO EDGE - review strategy fundamentals"
```

---

## Problem 8: 12 Probability Models Not Integrated

### Solution: Model Registry with Shadow Mode

```python
# src/model_registry.py
class ModelRegistry:
    def register_model(self, model_id: str, predict_fn, status='shadow'):
        self.models[model_id] = {'fn': predict_fn, 'status': status}

    def predict_ensemble(self, snapshot):
        predictions = {}
        for mid, model in self.models.items():
            predictions[mid] = model['fn'](snapshot)

        # Weighted average
        ensemble_prob = sum(p['probability'] for p in predictions.values()) / len(predictions)
        return ensemble_prob
```

---

## Implementation Priority

### Immediate (Today)
1. Add `getattr()` defensive checks
2. Fix pre-commit
3. Instantiate LearningEngine

### This Week
4. Add MFE/MAE diagnostics
5. Implement Bayesian updates
6. Fix time gate confusion

### Next Sprint
7. Round-robin forced trades
8. Model registry framework

---

**Sources:**

- [Bayesian Kelly Self-Learning Algorithm](https://medium.com/@jlevi.nyc/bayesian-kelly-a-self-learning-algorithm-for-power-trading-2e4d7bf8dad6)
- [MAE/MFE Trading Metrics](https://trademetria.com/blog/understanding-mae-and-mfe-metrics-a-guide-for-traders/)
- [Ensemble Trading Models](https://www.tandfonline.com/doi/full/10.1080/08839514.2021.2001178)
- [Shadow Deployment vs A/B Testing](https://www.linkedin.com/pulse/shadow-deployment-vs-ab-testing-quest-smarter-bhargavi-meda-cexmc)
- [Ed Thorp Kelly Criterion](https://web.williams.edu/Mathematics/sjmiller/public_html/341/handouts/Thorpe_KellyCriterion2007.pdf)
