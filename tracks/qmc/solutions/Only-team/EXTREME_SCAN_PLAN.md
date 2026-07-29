# Challenge extreme-size scan implementation plan

> **Execution:** inline in the current session. No Git commit, push, or PR.

**Goal:** Submit the seven-field scans at the smallest and largest approved
sizes for both supported lattices, and finish every cell well before the
30-hour challenge deadline.

**Architecture:** Two independent Slurm arrays share one cell runner.  Each
array has 14 cells: seven triangular fields followed by seven honeycomb
fields.  The runner derives `BetaT=L/h`, writes an immutable per-cell TOML
configuration, invokes 32-rank Julia QMC, validates the three native output
files, and writes a per-cell JSON manifest.

**Tech stack:** Julia 1.12.6, MPI.jl, Bash, Python 3 standard library, Slurm,
SCNet `xhacnormalb`.

## Global constraints

- Hamiltonian: `H = J1 Σ_<i,j> σᶻ_i σᶻ_j − h Σ_i σˣ_i`.
- `J1=-1`, `J2=0`, periodic spatial and imaginary-time boundaries.
- Triangular sizes: minimum `L=8`, maximum `L=48`.
- Honeycomb sizes: minimum `L=10`, maximum `L=32`.
- Triangular fields: `4.76511:0.001:4.77111`.
- Honeycomb fields: `2.12950:0.001:2.13550`.
- Main requested `FixedDltau=0.013`; actual `Dltau=BetaT/LTrot`.
- `nLocal=1`, `nWolff=5`, `nWarm=10000`, `NmBin=32`, `NSwep=2000`.
- `NmMeaConfg=10`, 32 deterministic MPI chains per cell.
- Minimum-size array limit: one hour. Maximum-size array limit: six hours.
- Each array has concurrency limit eight.
- Ship only `tracks/qmc/solutions/Only-team/` and the two ignored run
  directories.  Do not ship `.knowledge/`.
- Do not commit, push, or create a PR.

---

### Task 1: Freeze the approved scan design

**Files:**

- Modify: `tracks/qmc/solutions/Only-team/CHALLENGE_RUN_DESIGN.md`
- Create: `tracks/qmc/solutions/Only-team/configs/challenge-extremes-min-axes.json`
- Create: `tracks/qmc/solutions/Only-team/configs/challenge-extremes-max-axes.json`
- Create: `tracks/qmc/solutions/Only-team/configs/challenge-extremes-settings.json`

- [ ] Record the approved minimum and maximum sizes, seven field values,
  `FixedDltau=0.013`, and the unchanged update/statistics budget.
- [ ] Generate one seven-field run specification for the minimum-size array
  and one for the maximum-size array.
- [ ] Verify that each run specification contains exactly 14 unique cells.

### Task 2: Add the array cell runner with a regression test

**Files:**

- Create: `tracks/qmc/solutions/Only-team/scripts/run_extreme_scan_cell.sh`
- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`

**Interface:**

- Consumes `HARNESS_RUN_SPEC`, `SLURM_ARRAY_TASK_ID`, and `SIZE_ROLE`.
- Produces
  `tracks/qmc/results/Only-team/challenge-extremes-<role>-20260729/cells/<cell_id>/config.toml`,
  native QMC output under `qmc/`, and `manifest.json`.

- [ ] Add a failing static/integration test that requires all approved
  sizes, fields, sampling settings, output checks, and progress flushing.
- [ ] Run the focused test and verify it fails because the runner is absent.
- [ ] Implement the minimal runner.
- [ ] Run the focused test and the complete Julia test suite.

### Task 3: Add and guard the two Slurm arrays

**Files:**

- Create: `tracks/qmc/solutions/Only-team/scripts/scnet-extremes-min.sbatch`
- Create: `tracks/qmc/solutions/Only-team/scripts/scnet-extremes-max.sbatch`

- [ ] Request one node, 32 tasks, one CPU per task, 64 GB, array `1-14%8`.
- [ ] Set one-hour and six-hour limits respectively.
- [ ] Run `bash -n` and `scripts/cluster_guardrail.py inspect` on both files.
- [ ] Verify no credential, absolute Windows path, overwrite, or destructive
  command appears.

### Task 4: Stage, test, and submit

- [ ] Create the isolated remote root
  `/work/home/acyv3xww1l/qmc-tfim-challenge-extremes-20260729-a`.
- [ ] Rsync only the approved `Only-team` subtree and both run specs.
- [ ] Compare local and remote SHA-256 hashes for code, runner, scripts, and
  run specifications.
- [ ] Run exact `sbatch --test-only` checks on `xhacnormalb`.
- [ ] Submit the minimum-size and maximum-size arrays and capture both job IDs.

### Task 5: Settle-time monitoring

- [ ] Confirm both arrays transition from pending to running or report the
  exact pending reason.
- [ ] Tail one minimum-size and one maximum-size log until Julia warmup
  progress appears.
- [ ] Verify output cells begin writing to distinct directories.
- [ ] Continue monitoring the minimum-size array to first completed cells and
  report the maximum-size array's measured progress against the six-hour cap.
