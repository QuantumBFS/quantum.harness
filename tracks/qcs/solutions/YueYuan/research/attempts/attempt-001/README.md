# Attempt 001: Rank-15 Surrogate Run

## Status

Accepted by the public development validator on 2026-07-27.

This is the first run-loop artifact, not the final physical quantum-dynamics simulator. It is a local surrogate designed to exercise the challenge geometry and the validator contract before moving to a Schrödinger-equation implementation.

## Hypothesis

If the model Hessian has 15 visible directions inside a 48-dimensional raw two-qubit pulse vector, a closed-loop search restricted to the rank-15 Hessian subspace should need fewer black-box queries than a full raw search, while too-small subspaces should plateau.

## Model

- Raw pulse dimension: 48.
- Visible model curvature rank: 15, matching `d^2 - 1` for a two-qubit gate.
- Public gaps: `0.03` and `0.08`.
- Seeds: `0, 1, 2, 3, 4`.
- Methods: `full_raw_nelder_mead`, `random_subspace_nelder_mead`, and `hessian_subspace_nelder_mead`.
- `k` sweep: `0`, `3`, `8`, `15`, `24`, `48`.

The emitted rows use the validator schema and keep method metadata identical across comparisons.

## Run

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-001/run_candidate.py --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-001/submission.json
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-001 --instances dev --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-001/report.json
```

`submission.json` and `report.json` are generated outputs and are ignored by git.

## Next

Attempt 002 should replace the surrogate query model with an actual tiny-system propagator, model loss, Hessian extraction, and derivative-free closed-loop trace.
