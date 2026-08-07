# Attempt 002 Run Log

## Commands

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/run_candidate.py --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/submission.json
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-002 --instances dev --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/report.json
```

## Validator Result

Status: `accepted`

Score: `3.031578947368421`

| Gap | Median full queries | Median Hessian queries | Median random queries | Speedup |
|---:|---:|---:|---:|---:|
| `0.03` | `285` | `94` | `198` | `3.0319148936170213` |
| `0.08` | `288` | `95` | `200` | `3.031578947368421` |

## Interpretation

Attempt 002 upgrades the run loop from a direct rank surrogate to toy two-qubit quantum dynamics. It computes exact unitary propagation and finite-difference Hessian geometry locally, then emits validator rows from exact final infidelity checks.

The remaining gap to the challenge is the closed-loop search itself: the query counts are still produced by a deterministic conditioned-subspace trace model rather than by running Nelder-Mead/CMA-ES against the noisy scalar oracle. That is the target for attempt 003.
