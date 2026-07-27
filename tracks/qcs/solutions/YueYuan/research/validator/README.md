# Validator

This directory contains the approved validation gate for the YueYuan issue #113 autoresearch loop.

The validator checks whether a candidate demonstrates Hessian-guided sim-to-real calibration on the public development split before any result is treated as evidence. It accepts only if:

- `hessian_subspace_nelder_mead` reaches exact true infidelity `<= 1e-3`;
- its median query count is at least `2x` lower than `full_raw_nelder_mead` on `two_qubit_cz_minimal`;
- `random_subspace_nelder_mead` is reported as a dimensionality control;
- the agreed `k` sweep, model-truth gap sweep, five seeds, and equal shot budget are present;
- the candidate includes a too-small-`k` failure or plateau;
- source and metadata checks do not indicate leakage, private holdout access, network access, or unfair stopping.

Run a structural precheck:

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py <candidate-dir> --precheck --instances dev --out report.json
```

Run a scored development validation:

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py <candidate-dir> --instances dev --out report.json
```

Run the validator controls:

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py --write-manifest
```

Sealed holdout instances live under `../benchmark/private/`, which is gitignored. The manifest records the holdout query budget and usage.
