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

The local 80-parameter, 20-query calibration measured:

- first query, compilation-inclusive: 0.212 s;
- 19 warm queries: 0.0362 s (525 queries/s);
- open-loop setup: 7.65 s; landscape: 5.83 s;
- exact trajectory: 0.0382 s; geometry: 1.62 s;
- restricted optimization: 0.347 s (7 evaluations);
- peak RSS: 848,664 KiB; 32 logical CPUs visible;
- JAX CPU platform with x64 enabled.

Linear use of only these measured 80-parameter components gives a preliminary
23.3 s/trial estimate, about 61.5 trial-hours or 492 core-hours at eight cores
per trial. Development artifacts averaged 19.6 KiB/trial; scaling the
query-aligned records by the tenfold production budget suggests roughly 1.9 GB
for 9,500 trials. These are calibration estimates; the full local pilot below
supplies the authoritative runtime, RSS, and artifact size for this gate.

The full local representative pilot then completed 929 exact optimizer queries,
strictly validated, in 19.12 s wall with 860,224 KiB peak RSS. Its canonical
trial artifact is 551,237 bytes. Direct scaling gives 50.5 trial-hours,
approximately 404 core-hours at eight cores/trial, and 5.24 GB for 9,500 trial
artifacts. The selected production class is therefore 8 CPU cores, 24 GiB, a
12-hour element limit, and concurrency 32.

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

The measured gate also exposed a production risk: the two-qubit open-loop
optimizer does not reach its mandatory `1e-8` acceptance threshold for seed 0,
while the established acceptance fixture and representative pilot use seed 5.
The 9,500-trial array contains seed 0. Broad submission is therefore withheld
until the pilot completes and this seed-coverage issue is resolved or explicitly
accepted as a fail-closed production outcome.

## Production findings

The following claims remain intentionally unset until complete strict
production validation: whether model-Hessian beats random dimensionality
reduction, paired query and shot savings with 95% confidence intervals, the
model-gap crossover, and the empirical failure case. Figures and claims are
generated only from complete canonical artifacts; failed trials are retained.

## Reproduction identity

- Pre-Task-10 source revision:
  `7f36ecc89d97b42f3a68461cbb191aa6d276da39`.
- Frozen `uv.lock` SHA256:
  `1d16a82284cebf3ae050ee79bcba4f2c9166820cf5fcae6a277334e1614a35dc`.
- Final Task-10 revision and deployment archive SHA256 are recorded after the
  required clean commit and immutable deployment.

```bash
uv sync --frozen --group dev
uv run python -m pytest -q
JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu \
  uv run python scripts/calibrate_pilot.py --queries 32 \
  --output results/calibration.json
bash scripts/run_development.sh
uv run python run.py validate --output results/development
```
