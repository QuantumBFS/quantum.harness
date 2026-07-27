# Attempt 001 Run Log

## Commands

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-001/run_candidate.py --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-001/submission.json
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-001 --instances dev --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-001/report.json
```

## Validator Result

Status: `accepted`

Score: `2.9263157894736844`

| Gap | Median full queries | Median Hessian queries | Median random queries | Speedup |
|---:|---:|---:|---:|---:|
| `0.03` | `278` | `95` | `213` | `2.9263157894736844` |
| `0.08` | `285` | `97` | `229` | `2.9381443298969074` |

## Interpretation

This run establishes that the current validator and result schema can carry the core comparison: rank-15 Hessian subspace, full raw baseline, random-subspace baseline, equal shots, five seeds, two nonzero gaps, and small-`k` failure.

It does not yet establish the physics claim. The next attempt should make the query counts come from an actual simulated quantum-control loop rather than the surrogate cost model.
