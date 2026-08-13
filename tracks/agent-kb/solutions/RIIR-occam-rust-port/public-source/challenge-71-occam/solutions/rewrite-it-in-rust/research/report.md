# Occam Size–Generalization Study

This artifact contains exactly 16 tasks × 8 observed fractions × 20 seeds × 8 methods = 20,480 trial records. Observed rows are sampled without replacement; accuracy is evaluated on the held-out complement. Failed searches remain rows.

## Measured conclusion

Across 8380 successful trials with both size measures, the Spearman correlation between official gate count and held-out exact accuracy is 0.3280; therefore larger gate counts correlate with higher held-out accuracy. Description length and gate count have Spearman correlation 0.4353. These are associations under the declared grammar, tasks, completion rules, and bounds—not a universal learning law.

| Method | Successful fits | Full semantic recovery |
|---|---:|---:|
| legacy-registry | 825/2560 | 800/2560 |
| mdl-enumerator | 2560/2560 | 2265/2560 |
| abc-dont-care | 2560/2560 | 0/2560 |
| robdd | 2560/2560 | 0/2560 |
| sat-cegis | 2560/2560 | 0/2560 |
| grammar-evolution | 2435/2560 | 2141/2560 |
| memorization | 2560/2560 | 0/2560 |
| oracle-expression | 2560/2560 | 2560/2560 |

The four partial-logic baselines use an explicit conservative zero completion in this release-grade deterministic matrix; they fit observed rows but are not presented as complete implementations of every possible ABC/BDD/CEGIS heuristic. The oracle expression is evaluator-only. Runtime and RSS fields are normalized to zero in the hash-stable matrix and must not be interpreted as performance measurements.

Timeout, resource-limit, unsupported, and no-hypothesis statuses count as failed recovery. No global circuit minimality or grammar universality is claimed.
