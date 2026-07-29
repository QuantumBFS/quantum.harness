# Issue #86, Track B: first reproduction pass

This solution targets the validation floor of the consolidated challenge:

```text
H = -sum_{i<j} J_L(|i-j|) Z_i Z_j - Gamma sum_i X_i
J_L(r) = L^(-(1+sigma)) [
    zeta(1+sigma, r/L) + zeta(1+sigma, 1-r/L)
]
```

The convention is bare `J=1` with periodic image sums. The first long-range
anchors are `Gamma_c(7/4)=1.5609(3)` and `Gamma_c(2.0)=1.4208(2)`.

## What is implemented

- An independent sparse exact-diagonalization Hamiltonian for `L <= 16`.
- An exact all-pairs MPO for small-system checks.
- A finite-size, relative-error fit of the exact periodic Hurwitz-zeta
  coupling to a sum of exponentials.
- A stable `2P+2`-level MPO for the periodic image sum, with `P=8,12,16`.
- Finite two-site DMRG, optional orthogonality-penalty excited state, the gap,
  and the equal-time second-moment ratio `xi/L`.
- Per-cell atomic manifests, resumable packed-node execution, crossing
  analysis, gap fits, finite-size extrapolation, conservative error budgets,
  and plots.

MPSKit does not expose an accumulated discarded-weight scalar from `DMRG2`.
The output therefore retains the `discarded_weight` field as null and records
the ground/excited energy variance, variance divided by `E^2`, and the
Galerkin convergence residual.

## Setup and validation

```bash
make skills
make install julia
make install mpskit

PATH="$HOME/.juliaup/bin:$PATH" \
  julia --project=julia-env \
  tracks/mps/solutions/issue-86/test/runtests.jl
```

The tests verify Pauli normalization, Hurwitz-zeta symmetry, ED versus the
exact MPO spectrum, monotonic pole convergence, the periodic-image SOE MPO,
and DMRG/ED agreement for a six-site NN chain.

The analyzer enforces the small-system gates instead of silently proceeding:
`|E0(DMRG)-E0(ED)|/|E0(ED)| < 1e-8` and an absolute `xi/L` error below `1e-6`.
If the largest pole count misses either gate, `summary.json` records the
failure and the local/full scans must not be launched. `pole_drift.csv` and
the corresponding log-scale plots retain the failed pole sweep for diagnosis.

## Runs

The seven-job smoke run is intended for a laptop:

```bash
PATH="$HOME/.juliaup/bin:$PATH" \
  julia --project=julia-env \
  tracks/mps/solutions/issue-86/run.jl \
  tracks/mps/solutions/issue-86/configs/smoke.toml \
  tracks/mps/results/issue-86-local

PATH="$HOME/.juliaup/bin:$PATH" \
  julia --project=julia-env \
  tracks/mps/solutions/issue-86/analyze.jl \
  tracks/mps/results/issue-86-local
```

After the smoke gate passes, `configs/ed-gate.toml` checks both long-range
anchors at `L=16`, `chi=32,64`, and 16 poles against the sparse ED oracle.
Keep its output separate from the smoke data:

```bash
PATH="$HOME/.juliaup/bin:$PATH" \
  julia --project=julia-env \
  tracks/mps/solutions/issue-86/run.jl \
  tracks/mps/solutions/issue-86/configs/ed-gate.toml \
  tracks/mps/results/issue-86-ed-gate
```

`configs/local.toml` contains the first crossing grid. It is still limited to
`L <= 16` and should be described as pipeline validation or finite-size
preliminary data.

`configs/crossing-p16.toml` is the laptop-sized precision-first subset:
`L=8,16`, `chi=32`, and the now-gated 16-pole MPO. It provides one preliminary
crossing per long-range anchor before paying for the full pole/chi sweep.
`configs/crossing-p16-l16-32.toml` advances the same audit to the next size
pair without changing the numerical controls.

## SCNet production workflow

The production target is the shared CPU partition `xhacnormalb`: one
128-core node with two AMD EPYC 7742 processors, 512 GB DDR4, and 100 Gb IB.
The calculation is single-node; independent parameter points are packed into
the allocation. `run_full.sbatch` requests 128 cores and 480 GB and uses:

| class | default layout | points |
|---|---|---|
| A | 16 workers × 8 cores | `chi <= 64`, `L <= 64` |
| B | 8 workers × 16 cores | `chi = 128`, `L <= 64` |
| C | 4 workers × 32 cores | `L = 128`, `chi = 128` |
| D | 2 workers × 64 cores | optional `chi = 256` |

Each `srun` step receives an explicit share of `SLURM_MEM_PER_NODE`; without
that step-level request, SCNet treated every step as if it needed the full job
memory and serialized the first seven-cell smoke run. The launcher also caps
the requested worker count by `SLURM_CPUS_PER_TASK`, so a 16-core validation
allocation automatically uses two 8-core workers while a 128-core class-A
allocation uses all 16. A bounded GNU `xargs -P` pool is used because the
cluster provides Bash 4.2, which predates `wait -n`.

The committed stage configurations are:

| config | cells | purpose |
|---|---:|---|
| `calibration.toml` | 1 | compare thread layouts |
| `stage1.toml` | 75 | NN gates and the 1% long-range gate |
| `stage2-first-pass.toml` | 67 | incremental formal audit after Stage 1 |
| `stage2-baseline.toml` | 60 | `P=16`, `chi=64`, `L=8..64` crossings |
| `stage2-systematics.toml` | 32 | pole and bond-dimension drift |
| `stage2-contingency.toml` | 6 | optional `L=128`, `chi=128` |
| `stage2-chi256.toml` | 6 | optional last-resort bond dimension |

Before submission, verify the live account rather than trusting the saved
hardware description:

```bash
export HARNESS_CLUSTER_PROFILE=scnet
scripts/harness_slurm.sh precheck
scripts/harness_slurm.sh probe-partitions
ssh scnet 'whichpartition; sinfo -p xhacnormalb -o "%P %a %l %D %t %c %m"; sacctmgr -n -P show assoc where user=$USER format=Account,Partition,QOS,GrpTRES,MaxTRES'
```

The job creates the run spec on the remote checkout if it is absent. Test the
exact request first:

```bash
export HARNESS_CLUSTER_PROFILE=scnet
scripts/harness_slurm.sh submit --test-only \
  --script tracks/mps/solutions/issue-86/run_calibration.sbatch \
  --partition xhacnormalb --time 00:30:00 --cpus 4 \
  --extra "--mem=14G --output=tracks/mps/results/issue-86-calibration-4t/slurm-%x-%j.out"
scripts/harness_slurm.sh submit --test-only \
  --script tracks/mps/solutions/issue-86/run_calibration.sbatch \
  --partition xhacnormalb --time 00:30:00 --cpus 8 \
  --extra "--mem=24G --output=tracks/mps/results/issue-86-calibration-8t/slurm-%x-%j.out"

scripts/harness_slurm.sh submit --test-only \
  --script tracks/mps/solutions/issue-86/run_full.sbatch \
  --run-spec tracks/mps/results/issue-86-stage1/run_spec.json \
  --command stage1:A --partition xhacnormalb --time 06:00:00 --cpus 128
```

The calibration entrypoint maps the 4- or 8-CPU allocation to exactly one
worker using every allocated CPU, so the two timings measure the intended
thread layouts. The 4-thread request uses 14 GB because SCNet currently
enforces a per-CPU memory limit below 4 GB. On 2026-07-28 the 8-thread point
completed 2.69 times faster, corresponding to 1.34 times the full-node
throughput after accounting for the halved worker count; class A therefore
uses 16 workers × 8 cores. After the scheduler accepts each request, remove
`--test-only`. For production, submit class B against the same spec/output
directory with `--command stage1:B`. Repeat with `stage2-baseline:A`, then
`stage2-systematics:A` and
`stage2-systematics:B`. Classes C and D are conditional and are not submitted
until the formal analysis requests them.

After a completed Stage 1, prefer `stage2-first-pass.toml` over independently
submitting the baseline and systematics configs. It reuses the existing
`L=16,32,64`, `chi=64`, `P=16` rows and computes only the missing baseline
sizes, the pole/chi audit, the first adaptive midpoints, and one tightened
NN--ED diagnostic. Its 67 cells split into 54 class-A and 13 class-B cells.

Every cell writes
`results/.../cells/<cell-id>/manifest.json`. Re-running the same stage skips
successful cells and retries only missing or failed ones. Collect and analyze
multiple completed stages with:

```bash
julia --project=julia-env \
  tracks/mps/solutions/issue-86/analyze_formal.jl \
  tracks/mps/results/issue-86-formal \
  tracks/mps/results/issue-86-stage1 \
  tracks/mps/results/issue-86-stage2-baseline \
  tracks/mps/results/issue-86-stage2-systematics
```

The formal analyzer writes `formal_summary.json`, `crossings.csv`, finite-size
plots, and `adaptive_run_spec.json`. The latter contains midpoint cells until
each crossing bracket is at most `0.001`; it can be run through the same
packed-worker script. A formal claim is emitted only after the finite-size,
bond-dimension, and MPO components are all present and the combined interval
overlaps the published error bar.

## Quality-aware follow-up and scoped finalization

`generate_followup_spec.jl` combines unresolved adaptive points with unique
variance or residual failures. Strict retries preserve the physical
parameters and use `tolerance=1e-11`, `maxiter=80`, and `seed=86`. When an old
result and a strict retry describe the same physical point,
`analyze_formal.jl` selects a result that passes both quality gates before
comparing residuals.

After the merged analysis completes, `finalize_track_b.jl` compares it with
the preceding formal-analysis round and writes:

- `validation_summary.json`, containing each numerical gate and the scoped
  scientific status;
- `next-recommendations.json` plus run specs and a reason map for any
  remaining adaptive work, a `chi=128` retry, an `L=128` contingency, and a
  last-level `chi=256` check;
- `run.json` and `report.json`, the semantic and presentation sources for the
  offline challenge report.

Recommendation specs always carry `automatic_submission=false`. The
finalizer can certify the two published critical-point anchors as the Track B
validation floor. It also records that the complete Track B boundary still
requires long-range `z`, `gamma/nu`, and the `sigma=1.6` and `sigma=1.8`
rows.

## First local smoke result

The 2026-07-27 seven-job `L=6`, `chi=16` run is a pipeline validation, not a
critical-point reproduction. The NN point at `Gamma=1` passed the ED gates:
the relative ground-energy error was `8.58e-11`, the absolute `xi/L` error was
`1.78e-7`, and the DMRG gap differed from ED by `3.36e-10`.

The first positive Laplace-quadrature fitter missed the long-range ED gate by
several orders of magnitude. Replacing it with a relative least-squares fit
of the exact finite-periodic coupling fixed the root cause. The rerun gave:

| sigma | poles | max coupling error | E0 relative error | xi/L absolute error |
|---:|---:|---:|---:|---:|
| 1.75 | 16 | 4.67e-16 | 1.66e-11 | 8.71e-8 |
| 2.00 | 16 | 6.58e-16 | 2.09e-11 | 1.35e-7 |

The independent `L=16` ED gate also passed and shows controlled bond-dimension
convergence:

| sigma | chi | max coupling error | E0 relative error | xi/L absolute error | variance |
|---:|---:|---:|---:|---:|---:|
| 1.75 | 32 | 1.72e-13 | 5.87e-10 | 4.14e-8 | 3.27e-7 |
| 1.75 | 64 | 1.72e-13 | 3.49e-13 | 2.13e-11 | 1.98e-10 |
| 2.00 | 32 | 1.38e-13 | 4.55e-10 | 4.65e-8 | 2.05e-7 |
| 2.00 | 64 | 1.38e-13 | 2.54e-13 | 2.29e-11 | 1.32e-10 |

The first `L=8/16`, `chi=32`, 16-pole crossing grid then gave:

| sigma | Gamma crossing | reference | relative offset |
|---:|---:|---:|---:|
| 1.75 | 1.58572 | 1.5609 | +1.59% |
| 2.00 | 1.44112 | 1.4208 | +1.43% |

Every point retained the ED gate (`max E0 error = 6.81e-10`,
`max xi/L error = 7.24e-7`), so the remaining offset is finite-size drift.
It does not yet meet the 1% preliminary criterion. A follow-up `L=16/32`
run was stopped after 6/20 points when the first `L=32` point measured
73 seconds, making the scan exceed the ten-minute laptop budget. The partial
data are retained but are not fitted. No dynamic exponent or formal
literature-reproduction claim is made.

## Interpretation rule

A value is marked as formally reproduced only when the combined finite-size,
bond-dimension, and MPO-pole interval overlaps the published error bar.
Otherwise the output remains explicitly preliminary. No crossover-boundary
claim is made in this first pass.
