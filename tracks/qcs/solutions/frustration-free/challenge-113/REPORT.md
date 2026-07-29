# Challenge 113 measured production-gate report

## Current status

Production remains blocked and has not been submitted. The canonical 9,500
paired trials all construct, including model-Hessian dimensions `k=24` for
`d=2` and `k=20,30,80` for `d=4`. Dense landscapes retain a complete
curvature-ordered orthonormal basis while effective Hessian ranks remain 3 and
15 at the `1e-8` relative threshold. Matrix-free results expose only the
columns actually computed.

Model preparation uses canonical `model_seed=5`; `perturbation_seed` controls
truth orientation and `trial_seed` controls search and measurement randomness.
The seed-zero statistical pilot therefore shares the accepted canonical model
without coupling statistical seeds to model acceptance.

## Current measured gate

Revision `dd16192953c130d738716238525760de73343e09` was rerun locally with the
actual JAX CPU x64 runtime. The representative `d=4`, `p=80`, gap 0.05,
model-Hessian `k=4`, exact-observation, budget-2,000 calibration measured:

- compilation-inclusive first query: 0.217 s;
- 19 warm queries: 0.0338 s (562 queries/s);
- open-loop setup: 7.75 s; dense landscape: 5.81 s;
- exact trajectory: 0.0340 s; geometry: 1.67 s;
- restricted optimization: 0.430 s (8 evaluations);
- peak RSS: 862,252 KiB; 32 logical CPUs; JAX CPU x64.

The full representative pilot completed 881 exact queries and strict validation
reported `valid=true`. Wall time was 21.91 s and peak RSS was 864,260 KiB.
The compact evidence records the measured artifact size and an arithmetic,
provisional 9,500-trial projection. No resource class or concurrency has been
selected; those require Task 10C resource pilots.

Historical preliminary measurements are superseded by this rerun and are kept
only in Git history.

## Remaining Task 10C blocker

Both authorized clusters expose glibc 2.17, while frozen `jaxlib==0.11.0`
requires `manylinux_2_27_x86_64`. Frozen sync therefore fails closed before
Slurm submission. No older JAX, source build, container, or platform fallback
has been substituted. The final candidate archive is local-only until an exact
runtime-compatible cluster environment is approved.

## Interpretation and production claims

The rank `d²−1` is the regular controllable pure-state expectation, not an
unconditional identity. Production comparisons, confidence intervals,
model-gap crossover, and failure-case claims remain unset until the complete
canonical artifacts pass strict validation. The finite-shot device is an
abstract Bernoulli estimator, not a hardware noise model.

## Reproduction identity

- measured source revision: `dd16192953c130d738716238525760de73343e09`;
- frozen `uv.lock` SHA256:
  `1d16a82284cebf3ae050ee79bcba4f2c9166820cf5fcae6a277334e1614a35dc`;
- canonical evidence index: `evidence/task10a/index.json`.

```bash
uv sync --frozen --group dev
JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu uv run python -m pytest -q
JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu uv run python \
  scripts/build_task10a_evidence.py \
  --run-root results/task10a-dd16192 \
  --time results/task10a-dd16192-pilot.time \
  --validation results/task10a-dd16192-validation.json \
  --output evidence/task10a \
  --revision dd16192953c130d738716238525760de73343e09 \
  --report REPORT.md
uv run python -m pytest tests/test_evidence.py -q
```
