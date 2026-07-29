# frustration-free — Finite-temperature Anderson impurity solver

## Team

| | |
|---|---|
| **Team name** | frustration-free |
| **Members** | 蒋玮琪 (`jiangweiqi001`), 陈硕 (`ChS-YHWH`), 马追景 (`desitterf`) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Build and independently validate a deterministically purified tensor-network solver for the continuous-bath spinful Anderson impurity model, then determine the coldest inverse temperature reachable with a controlled observable error budget. |
| **Catalog issue** | `Addresses #81` — “[challenge]: How cold can a purified tensor-network Anderson impurity solver go?”, released by Weiyi Guo, University of Amsterdam. |
| **Track** | `tracks/mps/solutions/frustration-free/` — selected from the issue’s `Method: MPS Based Algorithm` field. |

## Initial scope

The four-day acceptance target is:

1. fit and serialize the semicircular hybridization;
2. validate finite-bath \(n_d\), double occupancy, and \(G(\tau)\) against an independent exact-diagonalization oracle to \(10^{-6}\);
3. run a purified finite-temperature MPS baseline at \(\beta=16\) or \(32\);
4. report bath, chain-length, bond-truncation, and time-step/residual errors together with runtime, peak memory, and per-bond dimensions.

The implicit logarithmic integrator and residual-driven bond expansion are research extensions. The bosonic bath, DMFT self-consistency, real-time dynamics, analytic continuation, and METTS implementation remain out of scope.

## Current Julia capability

The locked Julia project now constructs normalized identity-pair purifications
for explicit finite spinful baths, builds the physical Anderson Hamiltonian as
an MPO on interleaved physical/ancilla `Electron` sites, and evolves
`exp(-βK/2)` with two-site TDVP. Its bounded per-step history records the beta
endpoint, normalization-log increment, maximum link dimension, maximum
two-site SVD truncation error, and the convergence/error estimate and work
counters from every KrylovKit local `exponentiate` call. Requested increments
are automatically subdivided using a conservative Hamiltonian-norm bound; the
requested and effective settings are both recorded. These local metrics are
not a global TDVP or time-step error estimate; convergence still requires
comparing runs at smaller time step and larger cutoff/maxdim settings. Safe
subdivision is capped by `MAX_EVOLUTION_STEPS = 100_000`.

`julia/finite_bath_observables.jl` adds the full-grand-canonical
`finite_bath_observables` API for impurity occupancy, double occupancy, and
spin-resolved `G_up(τ)`/`G_dn(τ)`. It preserves the caller's τ-grid order and
returns bounded per-point branch, bond-dimension, truncation, Krylov, settings,
and convention provenance diagnostics. The Green function uses only
nonpositive-imaginary-time purified branches with accumulated log norms.

Run its focused and smoke tests from the repository root:

```bash
julia --project=tracks/mps/solutions/frustration-free/julia tracks/mps/solutions/frustration-free/julia/test/runtests.jl
```

## Small-bath MPS-versus-ED acceptance gate

From a fresh checkout, run the deterministic two-bath acceptance fixture with
the pinned Python/NumPy runtime and explicit Julia project. `JULIA` may point
to a Julia executable; otherwise the runner resolves `julia` from `PATH`.

```bash
uv sync --project tracks/mps/solutions/frustration-free --frozen
JULIA="$(command -v julia)" uv run \
  --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/acceptance.py \
  --julia-project "$PWD/tracks/mps/solutions/frustration-free/julia" \
  --output-directory "$PWD/tracks/mps/solutions/frustration-free/results/acceptance"
```

The fixture has `U=0.8`, `D=1`, two nonzero bath couplings, bath energies
`epsilon=+/-0.5`, `beta=0.5`, `tau=[0,0.125,0.25,0.375,0.5]`, TDVP
inverse-temperature step `0.02`, cutoff `1e-14`, maximum bond dimension `128`,
and explicit global-Krylov expansion dimension `32`. The exact serialized
`bath.json` is embedded in the MPS request and is also passed to the Python ED
oracle. The command exits zero only when every scalar in `n_d`, double
occupancy, `G_up(tau)`, and `G_down(tau)` has absolute error `<=1e-6`.
The `1e-6` value is binding: programmatic callers and `--threshold` may choose
a stricter nonnegative value but cannot relax it above `1e-6`. The acceptance
artifact records both `effective_threshold` and `binding_max_threshold`.
Both the zero-coupling and shifted-bath-energy ED ablations must also change
at least one genuine-interior spin Green-function value by more than the named
`1e-5` safety margin.

`krylov_expansion_dim` is an explicit, hash-bound solver setting. The scalable
library default is `0` (TDVP only); no chain length silently enables expansion.
The value `32` is selected only by this small acceptance fixture and is retained
in solver settings, diagnostics, and provenance.

The controlled `beta=0.5` study observed non-monotonic timestep behavior:
`dt=0.01` gave global error `2.621836803884392e-6`, while `dt=0.02` gave
`4.631353420214701e-8`. Other controlled comparisons were cutoff `1e-12`
(`2.970672798419116e-5`) versus `1e-14` (`4.631353420214701e-8`), maxdim
`128` versus `256` (both `4.631353420214701e-8`), and expansion dimension
`24` (`1.9892100094898169e-7`) versus `32` (`4.631353420214701e-8`).
These values and the non-monotonicity warning are preserved in
`acceptance.json`. They validate only this small `beta=0.5` fixture:
production claims at `beta=16` or `beta=32` require a dedicated convergence
investigation.

The immutable gate root is:

```text
tracks/mps/solutions/frustration-free/results/acceptance/acceptance.json
```

This results directory is generated and gitignored. Each invocation builds all
scientific files plus a hash-bound completion manifest in a unique staging
directory, validates every file and provenance binding, publishes an
immutable `runs/acceptance-<hash>/` directory, then atomically advances
`current.json`. Startup archives SIGKILL-abandoned stages without deleting
them. Existing runs are fully revalidated before reuse; a failed or corrupt
run cannot alter the current pointer or displace fresh staging.

Intermediate `bath.json`, `ed-oracle.json`, `mps-input.json`, and
`mps-result.json` files in the same directory retain schema, hash, solver
settings, diagnostics, and source/package provenance.

## Beta 16/32 staged convergence

`convergence.py` plans and runs the scalable TDVP-only study. Every generated
cell explicitly sets `krylov_expansion_dim=0`; Krylov-32 remains confined to
the beta=0.5 acceptance gate above. The default production plan has 14
deduplicated cells: for each beta in `{16,32}`, a bath trend at
`(N_b,dt,maxdim)={(12,0.05,512),(24,0.05,512),(48,0.05,512)}`, a timestep
sweep `(12,{0.2,0.1,0.05},512)`, and a maxdim sweep
`(12,0.05,{128,256,512})`. The shared `(12,0.05,512)` anchor occurs once.
Green functions are sampled at tau/beta `{0,1/4,1/2,3/4,1}`.

Cells are input-hash and bath-hash bound to the selected Julia project and its
Manifest plus `convergence.py`, `convergence.schema.json`, `bath.py`,
`acceptance.py`, and all finite-bath Julia sources. A per-cell advisory lock covers validation, execution, and
atomic publication. A valid completed cell is skipped on resume; stale,
partial, mismatched, or concurrently attempted output cannot be treated as
complete. Resumable state lives outside immutable results at
`RUN/checkpoints/<cell-id>/` under the same lock. Only hash-valid checkpoint
trees bound to a planned cell are resumed. Invalid checkpoint trees are
archived and fail closed. After the completed cell directory is validated and
atomically published, only the active `current.json` pointer is retired;
immutable generations remain under `generations/`, the retired pointer remains
under `retired/`, and `retirement.json` binds that audit state to the completed
cell artifact. A completed cell and active checkpoint pointer are never
accepted simultaneously. Draft 2020-12 validation covers plans, resource
estimates, checkpoint cursors and retirement records, completed cells, and
analyses using `convergence.schema.json`.

Create a tiny local pilot run bundle and run it with an explicit runtime Julia
project:

```bash
uv run --python 3.12.13 --with numpy==2.5.1 --with jsonschema python \
  tracks/mps/solutions/frustration-free/convergence.py plan \
  --stage pilot --betas 0.2 --bath-sizes 1 --time-steps 0.1 \
  --cutoffs 1e-12 --maxdims 32 --tau-fractions 0,0.5,1 \
  --output-root tracks/mps/solutions/frustration-free/results/convergence-pilot
# Resolve RUN from convergence-pilot/current.json before execution.
uv run --python 3.12.13 --with numpy==2.5.1 --with jsonschema python \
  tracks/mps/solutions/frustration-free/convergence.py run \
  --plan "$RUN/plan.json" --run-directory "$RUN" \
  --julia-project "$PWD/tracks/mps/solutions/frustration-free/julia"
```

Generate the production plan without running computation:

```bash
uv run --python 3.12.13 --with numpy==2.5.1 --with jsonschema python \
  tracks/mps/solutions/frustration-free/convergence.py plan \
  --stage production \
  --output-root tracks/mps/solutions/frustration-free/results/convergence-beta16-32
```

`--output-root` stages and fsyncs `plan.json`, deterministic plan-bound
`resources.json`, and `completion.json`, atomically publishes the immutable
`run-<hash>` directory, then advances `current.json`. Legacy `--output` is only
a standalone export; production `run` and `run-cell` reject it.

Production execution requires the plan-bound `resources.json` and an explicit
acknowledgment of its `resource_sha256`. Run one permitted zero-based cluster
cell or analyze the available calibration cells:

```bash
# Resolve RUN from convergence-beta16-32/current.json first.
RESOURCE_ACK="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["resource_sha256"])' \
  "$RUN/resources.json")"
uv run --python 3.12.13 --with numpy==2.5.1 --with jsonschema python \
  tracks/mps/solutions/frustration-free/convergence.py run-cell \
  --plan "$RUN/plan.json" --resources "$RUN/resources.json" \
  --acknowledge-resources "$RESOURCE_ACK" --execution-target cluster \
  --run-directory "$RUN" \
  --julia-project "$PWD/tracks/mps/solutions/frustration-free/julia" \
  --cell-index 0
uv run --python 3.12.13 --with numpy==2.5.1 --with jsonschema python \
  tracks/mps/solutions/frustration-free/convergence.py analyze \
  --plan "$RUN/plan.json" --run-directory "$RUN" \
  --allow-incomplete
```

For a cluster, select resources from the active cluster profile and submit the
profile-neutral wrapper as a zero-based array. It contains no partition,
account, hostname, credentials, memory, or wall-time policy:

```bash
sbatch --signal=B:USR1@300 --array=0,3-7,10-13 \
  --export=ALL,HARNESS_SOLUTION_DIR="$PWD/tracks/mps/solutions/frustration-free",HARNESS_RUN_SPEC="$RUN/plan.json",HARNESS_RESOURCES="$RUN/resources.json",HARNESS_RESOURCE_ACK="$RESOURCE_ACK",HARNESS_RUN_DIR="$RUN",JULIA_PROJECT="$PWD/tracks/mps/solutions/frustration-free/julia" \
  tracks/mps/solutions/frustration-free/convergence_slurm_array.sh
sbatch --signal=B:USR1@300 --array=1,8 \
  --export=ALL,HARNESS_SOLUTION_DIR="$PWD/tracks/mps/solutions/frustration-free",HARNESS_RUN_SPEC="$RUN/plan.json",HARNESS_RESOURCES="$RUN/resources.json",HARNESS_RESOURCE_ACK="$RESOURCE_ACK",HARNESS_RUN_DIR="$RUN",JULIA_PROJECT="$PWD/tracks/mps/solutions/frustration-free/julia" \
  tracks/mps/solutions/frustration-free/convergence_slurm_array.sh
```

`HARNESS_SOLUTION_DIR` is explicit because Slurm may execute a copied wrapper
from its spool directory rather than from the submitted script's directory.

Use the profile's partition, memory, CPU, and wall-time flags after a pilot
calibrates the conservative estimator. Re-submitting the same array is safe:
valid cells skip, while failed or partial cells rerun independently. The two
excluded `N_b=48` indices (2 and 9) cannot execute on any target. The runner
requires a plan-bound, schema-validated solver capability whose evidence is
also present in its compiled allowlist; no such capability exists yet.
Accidentally submitting the full array therefore fails those cells before
starting Julia. A star-to-chain mapping or equivalent compressed-MPO
optimization must first be implemented and validated. The direct star MPO has
98 interleaved sites and an MPO width that
grows with bath size, so the current path is not considered feasible at
`N_b=48`. Operational failures are classified separately as bath-discretization, timestep,
maxdim/truncation, runtime/memory, input-validation, or solver-runtime errors.
The wrapper forwards Slurm `SIGUSR1` and `SIGTERM` to Python, which forwards
them to Julia's process group. Julia publishes and reload-validates a
checkpoint before returning exit 75; Python accepts 75 only when it
independently observes a newly hash-valid checkpoint. The wrapper preserves
that status for scheduler requeue policy. Exit 75 without a fresh validated
checkpoint is a hard failure. RSS limits and scientific/diagnostic failures
remain nonretryable.

After the 4/8/16-thread calibration jobs finish, create one strict
`calibrationTelemetry` document with exactly one sample for each thread class.
Each sample references an absolute checkpoint root, distinct start and end
generation names plus all metadata/state/completion SHA256 values, and a
regular non-symlink canonical `slurmAccountingExport` JSON file plus its
SHA256. Boolean “validated” claims are not accepted.

Calibration independently validates the complete checkpoint root and every
generation file, requires the end generation to be current, verifies the
start history is an exact prefix of the end history, and derives beta/step
deltas from the two cumulative cursors. The Slurm export binds the same plan,
cell, input, start/end generations, job ID, elapsed time, allocation, MaxRSS,
checkpoint read/write time, actual Julia/BLAS threads, source hashes,
Project/Manifest hashes, and Julia/ITensors/ITensorMPS/HDF5 versions. Those
runtime values must exactly equal checkpoint and plan provenance. Duplicate
job IDs or checkpoint segments, missing thread classes, symlinks, hash
mismatches, unknown JSON fields, mixed cell/input benchmark identities, and
mixed runtime identities fail closed. All three allocations therefore measure
the same planned workload.

Publish the calibration without changing `resources.json`, `completion.json`,
or either completion/current pointer:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py calibrate \
  --plan "$RUN/plan.json" --run-directory "$RUN" \
  --telemetry "$RUN/slurm-calibration-telemetry.json"
```

This creates canonical, hash-bound `calibration.json` and
`resources-calibrated.json`. Existing identical files are revalidated and
reused; different or partial files fail closed. `calibration.json` reports
completed-beta/second and steps/second, time-per-step groups by observed
maximum link dimension, checkpoint overhead and size, MaxRSS, actual thread
counts, and a three-class observed envelope. The chosen allocation is the
smallest CPU then memory allocation whose throughput is at least 90% of the
best observed throughput.

For each sample, the normalized coefficient is
`elapsed / (delta_steps * sites * MPO_width * observed_link_dimension^3)`.
For each planned cell, `work_units = steps * branch_equivalents * sites *
MPO_width`. The central prediction uses the median normalized coefficient.
Because three sparse samples do not support a Gaussian confidence interval,
the conservative recommendation is distribution-free within the observed
envelope:

```text
ceil(work_units * target_link_dimension^3
     * max_observed_normalized_coefficient * 1.25
     + max_observed_checkpoint_read_write_overhead)
```

The artifact records the min/median/max coefficient, envelope width, fixed
1.25 sparse-sample safety factor, and formula. Every validation and production
acknowledgment reloads the raw checkpoint/accounting files and exactly rebuilds
all rates, link groups, allocation selection, uncertainty, and per-cell wall
recommendations before accepting either calibrated artifact.

Production use of the calibrated allocation is explicit:

```bash
CALIBRATED_ACK="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["resource_sha256"])' \
  "$RUN/resources-calibrated.json")"
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py run-cell \
  --plan "$RUN/plan.json" --run-directory "$RUN" \
  --resources "$RUN/resources-calibrated.json" \
  --acknowledge-resources "$CALIBRATED_ACK" \
  --execution-target cluster \
  --julia-project "$PWD/tracks/mps/solutions/frustration-free/julia" \
  --cell-index 0
```

The exact `resource_sha256` is the required production acknowledgment; the
original estimate's hash cannot acknowledge calibrated resources.

**Neither beta=16 nor beta=32 is accepted from one setting.** Results remain
unaccepted until controlled bath-size, timestep, and maxdim comparisons all
meet their named tolerances. The bath claim additionally requires the complete
12/24/48 trend, strictly decreasing nearest bath energy, and finest
`|epsilon_bath|/T <= 1.1`. Every thermal and Green branch must have nonempty
diagnostics, converged local Krylov updates, Krylov error at or below the named
limit, truncation at or below the named limit, and no maxdim saturation.
Missing/empty diagnostics and non-monotonic behavior on any controlled axis
unconditionally block a convergence claim.

Long Julia evolutions emit flushed progress from the shared TDVP step loop,
bounded to approximately 20 reports per nonempty thermal or Green evolution.
Each report includes the step and beta endpoint, maximum link dimension,
truncation error, and local Krylov convergence/error summary. Default library
calls remain quiet.

## Reproducible references

Download the version-pinned papers and reference repositories into the
gitignored results tree:

```bash
python tracks/mps/solutions/frustration-free/references/download_references.py
```

Verify an existing download without network access:

```bash
python tracks/mps/solutions/frustration-free/references/download_references.py \
  --verify-only
```

`references/references.json` records immutable arXiv versions, file sizes,
SHA256 digests, and exact Git commits. These references are inputs for method
design and independent validation; they are not vendored into the submission.

## Locked runtime and generated-artifact policy

`.python-version`, `pyproject.toml`, and `uv.lock` lock Python 3.12.13 and every direct/transitive
dependency used by the code and tests (`numpy`, `scipy`, `h5py`,
`jsonschema`, and `pytest`). Reproduce without re-solving:

```bash
uv sync --project tracks/mps/solutions/frustration-free --frozen
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest tracks/mps/solutions/frustration-free/tests
```

Plans carry generator, schema, solution-software, model, source, Julia project,
and Manifest identities. New automation should use `convergence.py plan
--output-root ROOT`, which atomically creates a complete
`ROOT/run-<plan-hash>/` plan/resources/completion bundle; it never overwrites a
run. Before submitting, resuming, or analyzing
existing content, run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python tracks/mps/solutions/frustration-free/convergence.py \
  validate-existing --plan RUN/plan.json --resources RUN/resources.json \
  --run-directory RUN
```

Stale plans/resources fail schema and version validation. Invalid immutable
cells and abandoned stage/backup trees are moved to explicit
`.superseded-*`/`.abandoned-*` audit directories; they are never submitted or
silently deleted.

## Profiling and optimization gates

Every MPS result records request-validation, context/evolution, and result
assembly timings; actual MPO/MPS link dimensions; Julia and BLAS thread counts
and versions; and peak RSS where the platform exposes it. Local child
processes that reach the declared 600-second boundary first receive a
cooperative checkpoint request, then are process-group killed after a bounded
grace period if they do not stop. A 16-GiB RSS breach remains an immediate,
nonretryable process-group kill.
Cluster results record the actual Julia/BLAS settings seen by the runner.

The reusable `FiniteBathContext` API constructs one identity-purification
template, physical MPO, site layout, and Hamiltonian bound for branch/checkpoint
work. It does **not** enable spin QNs: `spin_qn_enabled=false` remains a runtime
assertion because the current `Electron` purification has not passed a
QN-sector equivalence gate.

Before any `N_b=48` execution, both of these are mandatory:

1. implement and dense-ED validate a QN-conserving purification, including
   thermal and both Green branches; benchmark memory/time and observable error;
2. implement and validate star-to-chain (or equivalently compressed-MPO)
   mapping, including hybridization reconstruction and small-bath MPS-versus-ED
   equivalence.

Neither optimization is claimed implemented. The direct-star `N_b=48` cells
remain fail-closed on local and cluster targets.

## Platform boundary

Atomic directory publication, advisory locks, directory `fsync`, `/proc` RSS,
and the Slurm wrapper require Linux/POSIX semantics. Python numerical kernels
and artifact validation are portable, but production publication and cluster
execution are unsupported on native Windows; use Linux, WSL2, or a POSIX
cluster filesystem with atomic same-filesystem rename.

## CT-HYB status

`triqs/smoke_test.py` is only an import/constructor smoke test and prints
`SMOKE TEST ONLY — NO SCIENTIFIC COMPARISON`. The fail-closed
`cthyb-production.schema.json` and example require hybridization identity,
seeds, warmup/measurement cycles, autocorrelation acceptance, tau grid, and
MPI/thread settings. The scaffold has `production_ready=false` and cannot be
mistaken for a Monte Carlo result; no CT-HYB production run was launched.
