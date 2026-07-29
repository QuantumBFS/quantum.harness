# Challenge 81 CT-HYB Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox syntax for tracking.

**Goal:** Produce an independently reproducible, statistically gated,
continuous-bath CT-HYB reference at \(\beta=16\), retain its raw HDF5 evidence,
and compare it with the MPS result without conflating Monte Carlo and
finite-bath errors.

**Architecture:** A canonical JSON input defines the physics, meshes, seeds,
Monte Carlo controls, gates, and source/runtime identities. Four separate
single-rank runners publish immutable chain bundles. A reducer validates all
raw evidence, computes independent-chain standard errors, and atomically
publishes a hash-bound aggregate. A separate comparator joins that aggregate
to the existing MPS convergence/error-budget artifacts.

**Tech stack:** Python 3.12, TRIQS 4.0.0, TRIQS/cthyb 4.0.0, OpenMPI 5,
MPI-enabled HDF5, JSON Schema draft 2020-12, pytest, POSIX advisory locks and
atomic rename, Slurm arrays.

## Global constraints

* Physics is exactly `D=1.0`, `U=0.8`, `Gamma=0.1`,
  `epsilon_d=-0.4`, `mu=0.0`, `beta=16.0`.
* Reported tau is exactly `[0.0, 4.0, 8.0, 12.0, 16.0]`.
* Production uses exactly four independent single-rank chains with seeds
  `[810001, 810002, 810003, 810004]`.
* Production controls are exactly 50,000 warmup cycles, 1,000,000 measurement
  cycles, and cycle length 50.
* The accepted environment is created from `conda-linux-64.lock`; re-solving
  `environment.yml` is not production reproduction.
* Canonical JSON is UTF-8, sorted-key, compact, finite, duplicate-key-free,
  and newline-terminated. Payload hashes exclude the top-level `sha256`.
* Raw HDF5 files are retained and byte-hashed, but are not described as
  canonical across HDF5 versions.
* Interrupted chains restart from the beginning. No task may claim partial
  Markov-chain checkpoint support.
* `finite_bath_ed.py` remains the small finite-bath oracle. CT-HYB remains the
  continuous-bath stochastic comparator.
* CT-HYB standard error is never used as a replacement for MPS
  bath-discretization, chain, bond, or time-step/residual error.
* Every production validator rejects unknown keys, nonfinite numbers,
  symlinks, stale source hashes, and hash mismatches.
* No production result is committed to git.

## Planned file map

Create:

* `triqs/cthyb-production-input.schema.json` — exact schema-2 input.
* `triqs/cthyb-chain.schema.json` — chain summary and completion contracts.
* `triqs/cthyb-summary.schema.json` — aggregate and comparator contracts.
* `triqs/artifacts.py` — strict JSON, canonical hashes, file hashes, fsync,
  locking, atomic publication, and runtime identity.
* `triqs/make_input.py` — canonical production input generator/verifier.
* `triqs/hybridization.py` — analytic semicircular \(\Delta(i\omega_n)\) and
  TRIQS installation helpers.
* `triqs/run_chain.py` — one-chain solver and raw HDF5 publisher.
* `triqs/reduce.py` — four-chain validation, statistics, gates, publication.
* `triqs/validate_existing.py` — independent full-tree validator.
* `triqs/compare_mps.py` — MPS–CTHYB comparator and separated error budget.
* `triqs/cthyb_slurm_array.sh` — profile-neutral one-chain Slurm entry point.
* `triqs/tests/` — focused unit, corruption, recovery, and integration tests.

Modify:

* `triqs/README.md` — exact production and offline commands.
* `triqs/cthyb-production.schema.json` — retain schema 1 as an explicitly
  deprecated non-production scaffold; do not weaken its false constants.
* `tracks/mps/solutions/frustration-free/README.md` — replace “smoke only”
  status only after an accepted production bundle exists.
* `convergence.schema.json` and `convergence.py` — add a separately named
  MPS error-budget artifact if the current convergence analysis cannot provide
  all four required deterministic components.

## Task 1: Canonical production input contract

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/cthyb-production-input.schema.json`
* Create: `tracks/mps/solutions/frustration-free/triqs/artifacts.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/make_input.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_input.py`
* Modify: `tracks/mps/solutions/frustration-free/triqs/cthyb-production.schema.json`

**Interfaces:**

* `canonical_json(value: object) -> bytes`
* `sha256_bytes(value: bytes) -> str`
* `strict_json_load(path: Path) -> object`
* `verify_input(artifact: object) -> dict[str, object]`
* `make_production_input(solution_dir: Path) -> dict[str, object]`
* `write_production_input(path: Path, solution_dir: Path) -> dict[str, object]`

- [ ] **Step 1: Write failing canonicalization and schema tests**

Test two clean generations for byte equality, exact physics and gates, sorted
compact encoding, final newline, payload SHA256, four unique seeds, exact tau
mesh indices, and source/lock/model hashes. Add rejection cases for duplicate
keys, NaN/infinity, booleans used as integers, unknown keys, schema 1,
placeholder zero digests, changed model values, changed seed order, and a
source file changed after input generation.

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_input.py -q
```

Expected: FAIL because the schema and modules do not exist.

- [ ] **Step 2: Implement strict artifact primitives**

Use `json.loads(..., object_pairs_hook=...)` to reject duplicate keys,
`parse_constant` to reject nonstandard constants, `json.dumps` with
`sort_keys=True`, `separators=(",", ":")`, and `allow_nan=False`, SHA256 from
`hashlib`, and an atomic same-directory temporary-file/fsync/replace writer.
Reject symlink destinations and non-regular existing files.

- [ ] **Step 3: Implement the exact schema-2 generator and verifier**

Load `model.json`; do not accept physics flags from the CLI. Compute
`model_json_sha256`, `conda_lock_sha256`, `runner_source_sha256`, and
`schema_sha256`. Because `run_chain.py` does not exist until Task 3, bind the
initial input to a checked-in `runner-contract-v1` digest fixture in the tests,
then replace that fixture with the actual runner digest in Task 3 before any
production input is generated.

The only CLI option is `--output`. Reject pre-existing different content;
revalidate and reuse byte-identical content.

- [ ] **Step 4: Preserve schema 1 as non-production**

Add a `$comment` and README-facing description that
`cthyb-production.schema.json` is scaffold schema 1 and always requires
`production_ready=false` and `scientific_comparison=false`. Do not make schema
1 accept production.

- [ ] **Step 5: Run tests and commit**

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_input.py -q
git diff --check
git add tracks/mps/solutions/frustration-free/triqs
git commit -m "feat(cthyb): define canonical production input"
```

Expected: tests PASS and only Task 1 files are staged.

## Task 2: Analytic continuous-bath hybridization

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/hybridization.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_hybridization.py`

**Interfaces:**

* `delta_iw(omega: numpy.ndarray, *, gamma: float, bandwidth: float) -> numpy.ndarray`
* `install_g0(solver: Solver, input_payload: dict[str, object]) -> None`
* `reported_tau_indices(beta: float, n_tau: int, tau: Sequence[float]) -> list[int]`

- [ ] **Step 1: Write failing analytic tests**

Cover positive and negative fermionic frequencies, conjugation symmetry,
purely imaginary output, causality, high-frequency coefficient
\(\Delta(i\omega)\sim\Gamma D/(2i\omega)\), and agreement within `2e-13`
absolute error with a 512-node Gauss-Legendre integration for representative
frequencies. Check the exact tau indices `[0,1000,2000,3000,4000]` and reject a
non-node reported tau.

Add a noninteracting test that inspects installed
`G0_iw` and proves the inverse is
`iOmega_n + mu - epsilon_d - Delta`, not a double-counted impurity level.

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_hybridization.py -q
```

Expected: FAIL because `hybridization.py` does not exist.

- [ ] **Step 2: Implement the branch-safe Matsubara formula**

For nonzero real `omega`, compute
`1j * gamma / bandwidth * (omega - sign(omega) *
sqrt(omega**2 + bandwidth**2))`. Require finite float64 input and reject zero
because fermionic Matsubara meshes contain no zero mode.

- [ ] **Step 3: Implement solver installation**

Construct TRIQS block Green functions without numerical bath
discretization. Verify both spin blocks receive identical values and record a
float64 complex-array digest used by raw-HDF5 validation.

- [ ] **Step 4: Run tests and commit**

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_hybridization.py -q
git diff --check
git add tracks/mps/solutions/frustration-free/triqs
git commit -m "feat(cthyb): add analytic semicircular bath"
```

## Task 3: One-chain solver and raw HDF5 evidence

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/cthyb-chain.schema.json`
* Create: `tracks/mps/solutions/frustration-free/triqs/run_chain.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_chain_runner.py`
* Modify: `tracks/mps/solutions/frustration-free/triqs/make_input.py`
* Modify: `tracks/mps/solutions/frustration-free/triqs/tests/test_input.py`

**Interfaces:**

* `run_chain(input_path: Path, chain_index: int, output_root: Path) -> Path`
* `extract_chain_observables(solver: Solver, payload: dict[str, object]) -> dict[str, object]`
* `validate_chain_bundle(path: Path, input_artifact: dict[str, object], chain_index: int) -> dict[str, object]`

- [ ] **Step 1: Write failing tests with a fake solver**

The fake solver must expose the same attributes used in production. Test exact
solve parameters, one-rank enforcement, seed/index binding, density-matrix
`trace_rho_op` calls, exact tau-node extraction, raw archive contents,
`raw.h5` byte digest, source/runtime provenance, and reload-based
re-extraction.

Reject wrong seed, MPI size greater than one, `use_norm_as_weight=False`,
missing density matrix, non-normal solve status, unconverged autocorrelation,
nonfinite sign, modified raw HDF5, missing archive member, symlinked file, and
chain summary not reproducible from raw data.

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_chain_runner.py -q
```

Expected: FAIL because the chain runner does not exist.

- [ ] **Step 2: Implement the production solve call**

Construct a new solver per process, call `install_g0`, use
`h_int=U*n("up",0)*n("down",0)`, and pass all controls from the verified
input. Do not add `epsilon_d*n` to `h_int`. Assert `mpi.size == 1`,
`OMP_NUM_THREADS == 1`, and supported BLAS thread variables are one.

- [ ] **Step 3: Retain complete raw evidence**

Write `raw.h5` through `HDFArchive` with the input bytes and all objects listed
in `PRODUCTION_DESIGN.md` section 4. Capture stdout/stderr outside HDF5.
Compute occupancy and double occupancy from the measured density matrix, not
from a particle-hole hard-coded value.

- [ ] **Step 4: Implement per-chain atomic publication**

Use `work/<input-sha>/chain-NNN/.attempt-<uuid>`, a per-chain advisory lock,
`completion.json`, full reload validation, directory fsync, and atomic rename.
On startup archive abandoned attempts. A valid completed chain skips; a stale
or corrupt completed chain fails closed and is not overwritten.

- [ ] **Step 5: Bind the actual runner source**

Replace Task 1's contract fixture with `sha256(run_chain.py bytes)`. Add a test
that modifying the runner after input generation makes the runner reject the
input. Input generation must happen after source is final.

- [ ] **Step 6: Run focused tests and a tiny real pilot**

The pilot uses a test-only schema with 50 warmup and 200 measurement cycles;
production verification must reject that schema.

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_chain_runner.py \
  tracks/mps/solutions/frustration-free/triqs/tests/test_input.py -q
./micromamba run --prefix "$CTHYB_ENV" python \
  tracks/mps/solutions/frustration-free/triqs/run_chain.py \
  --test-pilot --chain-index 0 --output-root /tmp/ch81-cthyb-chain-pilot
```

Expected: tests PASS; pilot produces a reload-valid but explicitly
non-production chain.

- [ ] **Step 7: Commit**

```bash
git diff --check
git add tracks/mps/solutions/frustration-free/triqs
git commit -m "feat(cthyb): retain validated raw chain evidence"
```

## Task 4: Calibration gates

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/calibrate.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_calibration.py`
* Modify: `tracks/mps/solutions/frustration-free/triqs/cthyb-summary.schema.json`

**Interfaces:**

* `analyze_warmup(cells: Sequence[ChainBundle]) -> dict[str, object]`
* `select_cycle_length(cells: Sequence[ChainBundle]) -> dict[str, object]`
* `analyze_mc_scaling(cells: Sequence[ChainBundle]) -> dict[str, object]`
* `validate_calibration(artifact: object, production_input: object) -> None`

- [ ] **Step 1: Write failing synthetic-statistics tests**

Construct deterministic fixtures for warmup shifts, pooled errors,
autocorrelation convergence, exact cycle-length selection, and
`SE_500k/SE_250k` median bounds. Test boundary inclusion at `5e-4`, `5.0`,
`0.55`, and `0.90`. Reject calibration seeds reused by production, missing
cells, duplicate cells, mixed input identities, and an attempted silent
change from cycle length 50.

- [ ] **Step 2: Implement canonical calibration plans and analysis**

Generate all warmup/cycle-length/scaling cells with a separate deterministic
seed namespace. Hash-bind each plan and result. Calibration may pass or fail;
it cannot edit the production input.

- [ ] **Step 3: Run tests and commit**

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_calibration.py -q
git diff --check
git add tracks/mps/solutions/frustration-free/triqs
git commit -m "feat(cthyb): gate production calibration"
```

## Task 5: Four-chain reducer and atomic aggregate

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/cthyb-summary.schema.json`
* Create: `tracks/mps/solutions/frustration-free/triqs/reduce.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/validate_existing.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_reduce.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_recovery.py`

**Interfaces:**

* `effective_samples(n_cycles: int, tau_int: float) -> int`
* `independent_chain_statistics(values: Sequence[float]) -> dict[str, object]`
* `build_summary(input_artifact: object, chains: Sequence[object], calibration: object) -> dict[str, object]`
* `publish_run(output_root: Path, summary: object, chains: Sequence[Path]) -> Path`
* `validate_published_run(path: Path) -> dict[str, object]`

- [ ] **Step 1: Write failing statistics tests**

For four known values, assert exact mean, sample standard error,
three-degree-of-freedom interval with `3.182446305284263`, and preservation of
all chain means. Check pointwise Green-function arrays and spin average.

Test effective samples at autocorrelation 0.5, 1, 5, and above 5. Reject three
chains, five chains, duplicate seed/index, unconverged autocorrelation,
effective samples below 100,000, total below 400,000, sign below 0.99,
spin asymmetry above 0.005, half-filling error above 0.005, endpoint failure,
or any omitted chain.

- [ ] **Step 2: Implement summary and gates**

Every gate records threshold, measured value, and pass status. The summary can
serialize a rejected analysis for audit, but only `status="accepted"` is
publishable as `current.json`.

- [ ] **Step 3: Write failing publication/recovery tests**

Inject failures before and after each file fsync, run-directory rename, and
current-pointer replace. Kill a chain attempt and prove only that chain reruns.
Run two reducers concurrently and prove they either reuse identical content or
one blocks. Corrupt every referenced file in turn and prove fresh validation
fails. Ensure abandoned staging is archived, never accepted or silently
deleted.

- [ ] **Step 4: Implement immutable publication**

Publish `runs/cthyb-<summary-sha-prefix>/`, write a complete file-hash manifest,
then atomically advance `current.json`. Use same-filesystem rename and directory
fsync. Reject symlinks, special files, extra files, run-ID collision, and
existing different bytes.

- [ ] **Step 5: Run tests and commit**

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_reduce.py \
  tracks/mps/solutions/frustration-free/triqs/tests/test_recovery.py -q
git diff --check
git add tracks/mps/solutions/frustration-free/triqs
git commit -m "feat(cthyb): publish gated four-chain summary"
```

## Task 6: MPS–CTHYB comparator and error-budget contract

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/compare_mps.py`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_compare_mps.py`
* Modify if required: `tracks/mps/solutions/frustration-free/convergence.schema.json`
* Modify if required: `tracks/mps/solutions/frustration-free/convergence.py`
* Modify if required: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`

**Interfaces:**

* `load_mps_error_budget(path: Path) -> dict[str, object]`
* `compare(mps_result: object, mps_budget: object, cthyb_summary: object) -> dict[str, object]`
* `validate_comparison(artifact: object) -> None`

- [ ] **Step 1: Audit the current convergence output against required axes**

Record whether it provides pointwise bounds for `bath`, `chain`, `bond`, and
`time_residual`. If it reports only pairwise convergence deltas, add a new
artifact type rather than changing the meaning of an existing field.

- [ ] **Step 2: Write failing comparator tests**

Use fixtures with known MPS values, four deterministic error components, and
CT-HYB standard errors. Assert pointwise

```text
abs(MPS - CTHYB)
<= bath + chain + bond + time_residual + 3.182446305284263 * cthyb_se
```

for `n_d`, double occupancy, `G_up`, and `G_down`. Require exact model, beta,
tau, and convention identity.

Reject missing axes, null axes, negative bounds, renamed MC errors, mismatched
tau, use of finite-bath ED as the continuous reference, and any calculation
that assigns observed discrepancy to bath or MC error.

- [ ] **Step 3: Add the smallest missing MPS budget contract**

If needed, extend the schema with a new hash-bound
`artifact_type="mps_error_budget"` that references completed cells and
convergence analysis by digest and preserves the four components separately.
Do not infer an unavailable production bound.

- [ ] **Step 4: Implement and test the comparator**

The output reports observed differences, CT-HYB SE/Student interval, each MPS
component, envelope, and pass status separately. A missing MPS component is a
named blocker, not zero.

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_compare_mps.py \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py -q
git diff --check
git add tracks/mps/solutions/frustration-free
git commit -m "feat(cthyb): integrate separated MPS error budget"
```

## Task 7: Offline cluster wrapper

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/cthyb_slurm_array.sh`
* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_slurm_wrapper.py`
* Modify: `tracks/mps/solutions/frustration-free/triqs/README.md`

**Interfaces:**

Environment:

* `CTHYB_ENV` — absolute locked environment path.
* `CTHYB_INPUT` — absolute canonical input path.
* `CTHYB_ROOT` — absolute result root.
* `SLURM_ARRAY_TASK_ID` — required integer 0 through 3.

- [ ] **Step 1: Write failing wrapper tests**

Run with a fake `micromamba` and fake Python chain runner. Assert exact
`--offline`, prefix, input, chain index, output root, one-rank and one-thread
environment. Reject absent variables, relative paths, array indices outside
0–3, `SLURM_NTASKS != 1`, `SLURM_CPUS_PER_TASK != 1`, or thread settings other
than one. Verify signal exit cannot create completion.

- [ ] **Step 2: Implement the wrapper**

Use `set -euo pipefail`, `umask 077`, no network commands, explicit flushed
logs, and `exec` so scheduler signals reach Python. Do not use `mpirun -np 4`.

- [ ] **Step 3: Document and execute exact offline smoke commands**

Follow `PRODUCTION_DESIGN.md` section 9 exactly. On a no-network compute node,
create the lock-file environment with `--offline`, run `smoke_test.py`, and run
one test pilot. Record command output and package versions in a noncommitted
validation log.

- [ ] **Step 4: Run tests and commit**

```bash
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_slurm_wrapper.py -q
git diff --check
git add tracks/mps/solutions/frustration-free/triqs
git commit -m "feat(cthyb): add offline four-chain Slurm runner"
```

## Task 8: End-to-end corruption and reproducibility gate

**Files:**

* Create: `tracks/mps/solutions/frustration-free/triqs/tests/test_end_to_end.py`
* Modify: `tracks/mps/solutions/frustration-free/triqs/README.md`
* Modify after real acceptance only:
  `tracks/mps/solutions/frustration-free/README.md`

- [ ] **Step 1: Build a reduced-cycle end-to-end test profile**

Use four fake or tiny real solver bundles, but mark the profile
`artifact_type="cthyb_test_input"` so no production validator can accept it.
Exercise input generation, four chain publications, reduction, current
pointer, fresh validation, and comparator.

- [ ] **Step 2: Add an exhaustive corruption matrix**

Mutate input bytes, every chain summary, each HDF5 file, completion hashes,
source hashes, lock hash, seed, tau order, model convention, aggregate
standard error, comparison component, and current pointer. Each mutation must
fail before a scientific value is returned.

- [ ] **Step 3: Verify deterministic metadata**

Run the test profile twice from clean roots. Canonical input bytes and all
deterministic derived metadata must match. Raw Monte Carlo/HDF5 byte equality
is not required and must not be asserted.

- [ ] **Step 4: Run complete pre-production verification**

```bash
git diff --check
./micromamba run --prefix "$CTHYB_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests -q
SKIP_CHALLENGE81_ACCEPTANCE=1 \
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest tracks/mps/solutions/frustration-free/tests -q
```

Expected: all tests PASS; no result directories are staged.

- [ ] **Step 5: Commit**

```bash
git status --short
git add tracks/mps/solutions/frustration-free/triqs \
  tracks/mps/solutions/frustration-free/README.md
git commit -m "test(cthyb): verify production artifact lifecycle"
```

Do not update the top-level CT-HYB status to “production accepted” in this
task. That statement requires Task 9 evidence.

## Task 9: Calibration, production, reduction, and comparison

**Files generated under gitignored results only:**

* `tracks/mps/results/frustration-free/cthyb-beta16-calibration/`
* `tracks/mps/results/frustration-free/cthyb-beta16-production/`

- [ ] **Step 1: Create and validate calibration plans**

Generate the exact warmup, cycle-length, and MC-scaling cells from Task 4.
Submit as independent one-rank arrays. Re-run full validation before analysis.

- [ ] **Step 2: Apply the calibration stopping gate**

Proceed only if:

* 25,000-to-50,000 warmup shifts satisfy the pooled-SE/`5e-4` bound;
* cycle length 50 has converged autocorrelation no larger than 5 for all four
  chains;
* all nonzero standard errors shrink from 250,000 to 500,000 cycles;
* the median shrinkage ratio lies in `[0.55,0.90]`.

If any condition fails, publish a calibration failure report and stop. Change
the design/input in a reviewed commit; do not override the gate.

- [ ] **Step 3: Generate the final canonical input**

Generate `cthyb-input.json` only from the final committed source. Record the
git commit, input payload digest, schema digest, runner digest, model digest,
and conda-lock digest.

- [ ] **Step 4: Submit exactly four production chains**

Use the exact `sbatch --array=0-3` command in `PRODUCTION_DESIGN.md`. Requeueing
restarts only incomplete chains from their original seeds. Do not merge
partial HDF5 or change cycles after submission.

- [ ] **Step 5: Reduce and apply production stopping gates**

Stop without an accepted result unless all ten stopping criteria in
`PRODUCTION_DESIGN.md` section 11 hold. A failed result remains auditable and
does not advance `current.json`.

- [ ] **Step 6: Compare with MPS**

Use an accepted MPS completed cell and complete four-axis MPS error budget on
the same model and tau grid. Publish compatibility or explicit named
blockers. Do not infer missing deterministic errors from the CT-HYB
difference.

- [ ] **Step 7: Update status only from accepted evidence**

After fresh validation succeeds, update both READMEs with the immutable run
ID, summary digest, input digest, exact environment digest, chain/gate
statistics, and comparator status. Commit documentation only; leave generated
results gitignored unless repository policy is explicitly changed.

## Final verification checklist

- [ ] Schema 1 still cannot claim production.
- [ ] Canonical input is byte-stable and source/hash bound.
- [ ] The bath is analytic and continuous; no finite bath artifact is consumed.
- [ ] Four separate chain processes and four unique seeds are present.
- [ ] Raw HDF5 regenerates every chain value.
- [ ] Autocorrelation convergence, maximum time, effective samples, sign,
  symmetry, and endpoints all pass.
- [ ] Standard errors come from four independent chain means.
- [ ] Student intervals disclose three degrees of freedom.
- [ ] Partial-chain resume is not claimed.
- [ ] Atomic publication and current-pointer recovery pass injected failures.
- [ ] Comparator keeps MC, bath, chain, bond, and time/residual errors separate.
- [ ] Offline lock-file bootstrap and Slurm execution are reproduced.
- [ ] No generated production result is committed.

The first implementation task is Task 1: land the exact schema-2 canonical
input and strict artifact primitives before any solver code is written.
