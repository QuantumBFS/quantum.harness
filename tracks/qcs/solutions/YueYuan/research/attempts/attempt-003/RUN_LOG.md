# Attempt 003 Run Log

## Commands

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/run_candidate.py --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/submission.json
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-003 --instances dev --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/report.json
```

## Validator Result

Status: `accepted`

Score: `3.235294117647059`

| Gap | Median full queries | Median Hessian queries | Median random queries | Speedup |
|---:|---:|---:|---:|---:|
| `0.03` | `75` | `2` | `37` | `37.5` |
| `0.08` | `110` | `34` | `41` | `3.235294117647059` |

## Interpretation

Attempt 003 closes the main gap left by attempt 002: query counts now come from a derivative-free simplex optimizer calling a finite-shot noisy scalar oracle. The optimizer is intentionally local and dependency-free, but it gives the run loop an actual closed-loop search trace rather than a deterministic query formula.

The next research improvement is trace visibility: write per-query trajectories into ignored results, then summarize query-to-target versus `k`, gap, and shot budget in committed tables/plots.
