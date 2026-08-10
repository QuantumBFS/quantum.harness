# Challenge 113 measured production-gate report

## Current status

Production remains blocked and has not been submitted. The canonical 9,500
paired trials all construct, including model-Hessian dimensions `k=24` for
`d=2` and `k=20,30,80` for `d=4`. Dense landscapes retain a complete
curvature-ordered orthonormal basis while effective Hessian ranks remain 3 and
15 at the `1e-8` relative threshold. Matrix-free results expose only the
columns actually computed. For the bounded `k=p` comparison, model-Hessian
dispatches to exactly the full baseline's identity coordinates, bounds, and
mapping while retaining its model-Hessian label and complete source-basis hash.

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

## Task 10C runtime gate

The host glibc 2.17 incompatibility is resolved by the compute-verified LASG02
Apptainer image `uv-0.9.9-python3.12-bookworm-slim.sif` at SHA256
`2405a769d520e6d0f680c0f1dff0d9f92083724f1ffd85ea0c26b5e36defa323`.
The image provides Python 3.12.12, uv 0.9.9, and glibc 2.36; the unchanged
frozen lock installs JAX/JAXLIB 0.11.0 on CPU with x64 enabled. A LASG02
compute smoke has passed, but no representative pilot for the current source
candidate has run.

Runtime preparation now verifies source/archive/evidence/report/SIF/project/lock
hashes and the exact external deployment-metadata byte hash before requiring
`CHALLENGE113_ACK_NETWORKED_PREPARE=1` for one command only: frozen uv sync in
a clean, no-home container with normal cluster networking. No qcontrol code is
executed in that network-enabled container, and no wheelhouse/offline
preparation is claimed.

The post-sync smoke returns to network-none isolation, validates exact package
versions, finite propagation, and a deterministic objective, then writes a
marker recording the networked preparation mode, isolated execution policy,
runtime versions, lock/hash bindings, metadata digest, and successful smoke.
Slurm jobs use
`apptainer exec --no-home --cleanenv --net --network none`, never sync
packages, and fail closed before entering the container on a metadata mismatch
or on an absent/stale marker. Deployment metadata remains external to the
source tree. An unprivileged no-physics probe verified this network-isolation
mode with LASG02 Apptainer 1.3.4 on 2026-07-30.

The remaining Task 10C gate is operational measurement: stage the final source,
run one representative pilot on LASG02, validate its artifact, measure the
resource class, and approve concurrency/cost before any production array.

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
