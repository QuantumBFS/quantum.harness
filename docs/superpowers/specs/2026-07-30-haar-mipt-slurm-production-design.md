# Haar-MIPT Slurm Production Design

## Objective

Run a literature-aligned generic Haar monitored-circuit ensemble on the remote
Slurm cluster at `172.16.42.240`, using at most 100 concurrent single-CPU array
tasks.  Measure the measurement-record free-energy density for
`L = 6, 8, 10, 12, 14, 16` with 25,000 independent trajectories for each of
the two initial-state families at each width, then extract the effective
central charge with both the paper's double-fit procedure and a finite-size
stability fit.

Credentials must be entered interactively.  Passwords, tokens, or SSH private
keys must never be copied into the repository, Slurm scripts, result files, or
logs.

## Fixed Physics Parameters

- Circuit: periodic one-dimensional brick-wall circuit of independent Haar
  `U(4)` two-qubit gates.
- Measurement probability: `p = 0.170` per site after every even or odd gate
  layer.
- Measurement sampling: conditional Born sampling.
- Initial-state families: `global_haar` and `product`, analyzed separately and
  combined with equal one-half weights.
- Widths: `6, 8, 10, 12, 14, 16`.
- Equilibration: `4L` time steps.
- Recorded evolution: `24L` time steps.
- Target count: 25,000 trajectories per `(L, initial_family)`, for 300,000
  trajectories in total.
- Anisotropy used in the central-charge conversion: `alpha = 0.81`, with its
  uncertainty reported separately.

One time step is one parity layer of two-qubit gates followed by one
measurement layer, matching arXiv:2107.03393.

## Cluster Constraints

- Scheduler: Slurm, default `batch` partition.
- Resource ceiling chosen by the user: 100 concurrently running CPU tasks.
- Slurm account QOS observed during discovery: up to 480 CPUs and 480 running
  jobs, so the user ceiling is the binding limit.
- Every array element requests one CPU and disables internal BLAS/OpenMP
  threading.
- Every array element has a six-hour wall-time limit.
- The array concurrency limit is `%100`.
- No work runs on the login node beyond environment setup, file transfer,
  manifest validation, and scheduler commands.

## Execution Architecture

### Remote environment

Create a project directory under the user's remote home and a Python virtual
environment containing the minimal pinned runtime dependencies required by
the existing exact-state-vector scripts.  Transfer a clean source snapshot
from the current Git commit plus the new production files.  Do not transfer
ignored local results, credentials, or unrelated dirty worktree content.

### Calibration stage

Before production, submit a small Slurm array covering every `(L, family)`.
It measures per-trajectory runtime on compute nodes and validates:

- NumPy imports and runs with one BLAS/OpenMP thread;
- every output record passes the existing schema validator;
- each seed maps uniquely to exactly one `(L, family, sample_index)`;
- measured runtime supports a conservative chunk duration below 90 minutes;
- projected production runtime remains below six hours per array element.

Production submission stops if calibration fails any validation or projects a
chunk beyond the time limit.

### Production stage

Generate a deterministic manifest of disjoint sample-index ranges.  Each array
element consumes one manifest row and sequentially computes all trajectories
in that range.  Chunk sizes are width- and family-dependent, derived from the
calibration rates, and target 30--90 minutes per array element.

The scheduler submits all manifest rows as one or more arrays with a `%100`
concurrency cap.  Each array element writes first to a temporary file in its
own output directory, validates the completed batch, and atomically renames it
to its final name.  Rerunning the submission skips batches whose final files
already exist and pass validation.

### Storage format

Do not create one filesystem file per trajectory.  Store one compressed batch
artifact per manifest row, containing:

- the manifest identity and configuration hash;
- `L`, initial-state family, sample-index interval, and deterministic seeds;
- per-trajectory total record cost and the time series required for the
  slope estimator;
- runtime and measurement-count diagnostics;
- validation status.

A separate small checkpoint records completed, missing, invalid, and failed
batches.  All analysis reads batch artifacts through a single loader so that
local checkpoint data and remote production data share the same logical
record schema.

## Analysis

For each trajectory, estimate the bulk entropy density from a linear fit of
`F(t)/L` against recorded time `t`, including an intercept.  Average the two
initial-state families separately and then combine them with equal weights.
Bootstrap complete trajectories within each family independently.

The primary result follows the paper:

1. fit `f_tilde(L) = a + m_0(L_min)/L^2` for successive cutoffs;
2. use cutoffs `L_min = 6, 8, 10, 12` when enough widths remain;
3. extrapolate `m_0(L_min)` linearly in `1/L_min^2`;
4. convert with `c_eff = -6 m_0(infinity)/(pi alpha)`.

The report also includes these stability checks:

- repeat the primary analysis excluding `L = 6`;
- fit all widths directly to `a + b/L^2 + d/L^4`;
- compare full-window and late-window time slopes;
- show family-to-family differences and their convergence;
- report statistical, anisotropy, fit-window, and critical-point uncertainties
  separately rather than combining them into one unsupported error bar.

## Failure Handling and Monitoring

- A failed array element must not corrupt or overwrite completed batches.
- Nonzero exits, invalid records, NaNs, duplicate sample indices, seed
  collisions, and configuration mismatches are recorded explicitly.
- A resume command reconstructs only missing or invalid manifest rows.
- Monitoring uses `squeue` and `sacct`; no password or environment dump is
  written into diagnostic output.
- Production is scientifically complete only when every requested manifest
  row is valid, not merely when Slurm reports all jobs finished.

## Runtime and Sample Estimate

Local corrected single-thread timings imply approximately 145 CPU-hours for
the 300,000-trajectory target after removing `L = 18`.  With 100 concurrent
single-CPU tasks this is an ideal 1.45 hours.  Allowing for remote CPU
differences, environment startup, storage, scheduler imbalance, and batch
validation, the expected wall time is two to three hours.

If calibration predicts more than five hours for the complete production
array, retain the 25,000 target but split it into separately resumable waves;
do not silently reduce the scientific sample count.  Increasing to 50,000 per
family and width is outside this design and requires a separate user decision
after reviewing the 25,000-sample convergence.

## Acceptance Criteria

- The remote calibration passes for all twelve `(L, family)` combinations.
- No Slurm submission requests more than 100 concurrent CPUs or more than six
  hours per array element.
- Exactly 25,000 unique valid trajectories exist for every `(L, family)`.
- All requested sample indices and seeds are unique and reproducible.
- The production dataset can be resumed without recomputing valid batches.
- Primary and stability central-charge fits are generated from the slope-based
  free-energy estimator.
- Final reporting includes job IDs, actual CPU and wall time, sample counts,
  validation results, fitted values, and uncertainty decomposition.
- No credential appears in Git history, source files, Slurm logs, or results.
