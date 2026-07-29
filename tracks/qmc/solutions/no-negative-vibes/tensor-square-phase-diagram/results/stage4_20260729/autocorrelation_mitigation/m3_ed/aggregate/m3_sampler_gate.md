# m=3 temporal-block sampler gate

- Decision: **STOP**.
- Reason: at least one pre-registered m=3 validation gate failed.
- Temporal-block energy vs ED: `|z|=4.285` (frozen limit `3.0`).
- Median worst autocorrelation: control `4.812`, block `3.799` (21.1% reduction).
- Numerical audits: control `True`, block `True`.
- Consequence: the mandatory m=3 gate blocks the Stage 4 m=8 A/B run. No scale, seed, or budget was changed.
