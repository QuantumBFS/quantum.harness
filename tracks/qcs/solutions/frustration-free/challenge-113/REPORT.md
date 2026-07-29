# Challenge 113 measured study report

## Scope and interpretation

The experiment tests whether the leading model-Hessian subspace reduces
closed-loop query and shot cost under a controlled model gap. The often quoted
rank `d² − 1` is conditional: it is the regular, controllable pure-state
landscape expectation, not an unconditional numerical identity. Results are
therefore reported with rank-threshold sensitivity at `1e-6`, `1e-8`, and
`1e-10`, signed eigenvalue gaps, principal angles, and restricted noiseless
attainability.

The finite-shot device in this repository is an abstract Bernoulli estimator.
It is not randomized benchmarking and should not be interpreted as a hardware
noise model. The official Colab requires an authenticated Google session, so
the implementation is reconstructed from the challenge text and pinned author
notebook rather than claimed as an exact export of that Colab.

## Compute gate

The measured gate uses the representative two-qubit configuration with
Hilbert-space dimension `d=4`, 20 segments, 80 pulse parameters, model-Hessian
search dimension 4, model gap 0.05, exact observations, and budget 2,000. A
bounded representative calibration records compilation-inclusive first query,
warm throughput, exact-trajectory, restricted-optimization, geometry, peak RSS,
CPU count, JAX platform, and x64 status. A full representative pilot must then
pass strict artifact validation before the 9,500-trial array is eligible.

Cluster access was confirmed for the preferred CPU partition `xhacnormalb`
under the authorized account/QOS. Production concurrency and projected
core-hours/storage remain gated on the completed full pilot; no broad array is
submitted from an unmeasured estimate.

The canonical seed-zero statistical calibration, with immutable
`model_seed=5`, measured:

- first query, compilation-inclusive: 0.223 s;
- 19 warm queries: 0.0326 s (583 queries/s);
- open-loop setup: 7.94 s; landscape: 5.69 s;
- exact trajectory: 0.0326 s; geometry: 1.44 s;
- restricted optimization: 0.380 s (8 evaluations);
- peak RSS: 853,924 KiB; 32 logical CPUs visible;
- JAX CPU platform with x64 enabled.

The full seed-zero representative pilot completed 881 exact optimizer queries,
strictly validated, in 20.22 s wall with 860,776 KiB peak RSS. Its canonical
artifact store is 525,740 bytes. Direct scaling gives a provisional 53.4
trial-hours, 427 core-hours if eight cores per trial were eventually selected,
and 5.00 GB for 9,500 artifacts.

These figures are provisional single-trial estimates. Representative
resource-class and concurrency pilots are pending Task 10C; no production
resource class or concurrency is selected here.

The exact locked environment cannot currently run on either authorized cluster:
both expose glibc 2.17, while frozen `jaxlib==0.11.0` requires
`manylinux_2_27_x86_64`. The preferred revision archive was transferred and its
SHA256 verified, but frozen sync failed closed before any Slurm job was
submitted. No older JAX, source build, container, or CPU/GPU fallback was
silently substituted.

## Development smoke

The three-seed, budget-200 development sweep is written only to
`results/development-task10a`. All 84 canonical trials completed and strict
validation reported no errors. Wall time was 175.0 s, peak RSS was 926,300 KiB,
and the artifact store occupied 1,710,921 bytes.

Model preparation is now explicitly fixed at `model_seed=5` and cached by the
physics system configuration. Statistical `trial_seed=0` no longer controls
model optimization: the seed-zero full pilot passed strict validation. Truth
orientation remains controlled by `perturbation_seed`; search and measurement
randomness remain controlled by `trial_seed`.

## Production findings

The following claims remain intentionally unset until complete strict
production validation: whether model-Hessian beats random dimensionality
reduction, paired query and shot savings with 95% confidence intervals, the
model-gap crossover, and the empirical failure case. Figures and claims are
generated only from complete canonical artifacts; failed trials are retained.

## Reproduction identity

- Measured Task-10A source revision:
  `f1f5ed17c576f63d23420a304bfd712af1ddf419`.
- Frozen `uv.lock` SHA256:
  `1d16a82284cebf3ae050ee79bcba4f2c9166820cf5fcae6a277334e1614a35dc`.
- Compact evidence schemas, source bindings, and artifact hashes:
  `evidence/task10a/index.json`.

```bash
uv sync --frozen --group dev
uv run python -m pytest -q
JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu \
  uv run python scripts/calibrate_pilot.py --queries 20 \
  --output results/task10a-f1f5ed1/calibration.raw.json
uv run python run.py validate --output results/task10a-f1f5ed1/pilot
uv run python -m pytest tests/test_evidence.py -q
```
