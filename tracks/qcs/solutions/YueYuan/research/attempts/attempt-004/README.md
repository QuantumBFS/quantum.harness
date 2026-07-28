# Attempt 004: Full Checklist Hessian-Guided Calibration

This package implements the full challenge #113 checklist for the YueYuan PR.

## Local Setup

```bash
python3 -m pip install -r tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt
```

## Local Verification

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py --out tracks/qcs/results/YueYuan/attempt-004/smoke --fast
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py --results tracks/qcs/results/YueYuan/attempt-004/smoke
```

## Outputs

Generated JSONL, summaries, figures, and HPC logs are written under
`tracks/qcs/results/YueYuan/attempt-004/` and are intentionally ignored by git.
