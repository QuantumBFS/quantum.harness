# Killer Queen: truncated Bose--Hubbard bulk-gap certificates

## Team

| | |
|---|---|
| **Team name** | Killer Queen |
| **Members** | 唐鼎文 (Tang Dingwen); 聂芃 (Nie Peng) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Can the thermodynamic state-polynomial hierarchy be extended to occupation-truncated bosons and produce independently checked bulk-gap upper statements and local Mott-diagnostic bounds on three infinite hyperbolic graphs? |
| **Catalog issue** | Addresses #92 — “Certified bulk spectral-gap bounds for truncated Bose-Hubbard models on hyperbolic lattices,” released by Xiangling Xu (Inria Saclay) and Jie Wang (AMSS-CAS). |
| **Track** | `tracks/polyopt/` — selected from the issue's `Method: Semidefinite programming / Noncommutative polynomial optimization` field. |

## Result

The Julia/JuMP hierarchy core and independent exact certificate checker are
implemented and tested. The current submission contains exact-projected
hard-core finite-level gap upper statements, accepted observable bounds, and
explicit `UNKNOWN` rows for every numerical or resource failure. It is a
partial Target 2 campaign, not a claim that the mandatory larger-cutoff and
nested-level grid is complete. Open the self-contained
[`submission/report.html`](submission/report.html) for the professor-facing
result and [`submission/FINAL_REPORT.md`](submission/FINAL_REPORT.md) for its
GitHub-readable counterpart.

## Technical guide

This directory is a reproducible research scaffold for
[quantum.harness issue #92](https://github.com/QuantumBFS/quantum.harness/issues/92).

Read in this order:

1. [`submission/report.html`](submission/report.html): the self-contained,
   professor-facing challenge report. Its curated tables, structured source,
   run summary, and data-provenance manifest live beside it in
   [`submission/`](submission/README.md).
2. [`submission/report.json`](submission/report.json) and
   [`submission/run.json`](submission/run.json): the committed structured
   report source and run/acceptance summary. The provenance manifest maps these
   curated artifacts to the intentionally uncommitted raw SCNet payloads.
3. [`PHYSICS_TALK.html`](PHYSICS_TALK.html): a professor-style
   many-body physics talk explaining exactly what finite ED, the atomic SDP,
   and the root-local thermodynamic outer test calculate—and what the results mean.
4. [`status.md`](status.md): authoritative checklist for the paper-defined
   `(L,d)` hierarchy, Target 2 model/grid, completed work, missing work, and
   implementation gates.
5. [`report.html`](report.html): detailed, self-contained technical visual report of the
   algorithm, implementation, experiments, audit trail, limitations, and roadmap.
6. [`agent.md`](agent.md): compact agent handoff and decision log containing
   scientific claim rules, durable corrections, blockers, and the next action.
7. [`ALGORITHM.md`](ALGORITHM.md): why the method is a thermodynamic bulk-gap
   **upper-bound** hierarchy rather than a ground-energy SDP.
8. [`SURVEY.md`](SURVEY.md): what current software can and cannot do.
9. [`REPORT.md`](REPORT.md): generated experiments, limitations, and next
   research steps (created after running the study).

The code contains four deliberately separated calculations:

- `julia/` is the paper-defined hierarchy core.  It implements the complete
  state-polynomial index sets in [`LEVEL_SPEC.md`](LEVEL_SPEC.md), exact
  finite-matrix algebra over `Q(sqrt(2),sqrt(3))`, charge blocks, `TS2`, JuMP
  assembly, Clarabel/Mosek solve paths, and independent dual checking.
  `solve_observable(...; exact_certificate=true)` requests a separately
  classified exact lower/upper certificate for a selected bound.

- `atomic_sdp.py` is a tiny, genuine state-polynomial SDP for the \(t=0\),
  single-site, \(U(1)\)-invariant problem. It includes the lifted nonlinear
  variance term and certifies the exact atomic benchmark.
- `rooted_sdp.py` is a custom root-local thermodynamic outer test: root-supported
  excitations, their complete nearest-neighbor Hamiltonian window, exact
  matrix-unit algebra, stationarity, local positivity, and a lifted gap block.
  It has a valid but weak \(U(1)\)-restricted thermodynamic implication, but it
  is not a paper-defined `(L,d)` level or the complete convergent hierarchy.
- `ed.py` computes open finite-patch spectra in fixed particle-number sectors.
  These results validate signs and observables but are **not** thermodynamic
  gap certificates.

## Reproduce the reported results

All commands below are run from this directory. The raw SCNet payloads are
git-ignored because they contain about a gigabyte of solver matrices and logs;
the lightweight report, curated tables, figures, and SHA-256 provenance are
committed under [`submission/`](submission/README.md). Consequently,
`make final-report` in a fresh clone must follow either a new HPC run or a copy
of the original `results/` checkpoint.

### 1. Check out and record the revision

To reproduce the pull-request version before it is merged:

```bash
git clone https://github.com/QuantumBFS/quantum.harness.git
cd quantum.harness
git fetch origin pull/267/head:issue92-reproduction
git switch issue92-reproduction
cd tracks/polyopt/solutions/killer-queen-92
git rev-parse HEAD
```

Record the last command's output with the run. Numerical inputs are fixed by
the generated JSON manifests; the mathematical level is specified in
[`LEVEL_SPEC.md`](LEVEL_SPEC.md).

### 2. Install the recorded environment

The submitted snapshot used Linux x86-64, Python 3.12.3, Julia 1.11.5,
JuMP 1.31.1, Clarabel 0.11.1, and 256-bit Arblib checks. Python package
versions are frozen in [`requirements-reproduction.txt`](requirements-reproduction.txt),
and Julia packages are frozen in `julia/Manifest.toml`.

```bash
python3.12 -m venv .raw/venv
.raw/venv/bin/python -m pip install --upgrade pip
.raw/venv/bin/python -m pip install -r requirements-reproduction.txt
JULIA_DEPOT_PATH=.raw/julia-depot: julia --project=julia \
  -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
make test
```

The expected regression result at this revision is 21 Python tests and 577
Julia assertions. Mosek is present as an optional interface but was not used
for the accepted results in the final report; those use Clarabel plus the
independent exact checker.

### 3. Reproduce Target 1 and the finite-ED diagnostics locally

```bash
make graphs
make study
JULIA_DEPOT_PATH=.raw/julia-depot: julia --project=julia \
  julia/scripts/check_atomic_certificate.jl
```

`make study` writes 120 atomic-SDP rows, 54 finite radius-one ED rows, and 12
graph summaries. The main outputs are:

- `results/atomic_gap_brackets.csv`: all three cutoffs give
  `[0.5, 0.5000009536743164]`;
- `results/finite_patch_ed.csv`: all Target-1 graph/cutoff rows give gap
  `0.5`, `rho0=1`, `F0=K0=0`, followed by the complete Target-2 ED diagnostic
  grid;
- `results/atomic/julia-hierarchy-certificate.json`: the full buffered Julia
  hierarchy gives `gamma=0.49` `FEASIBLE`, `gamma=0.51` exact-projected
  `EXCLUDED`, and an exact-projected density bound near one;
- `.figures/finite_patch_gap_vs_t.*` and
  `.figures/finite_patch_gap_vs_mu.*`: finite-patch diagnostic plots.

The Python atomic calculation is a one-site state-polynomial SDP. The Julia
atomic check is deliberately not a one-site shortcut: it sets `t=0` in the
same two-site buffered complete hierarchy and checker used for Target 2.

### 4. Generate the Target-2 inputs

```bash
make graphs
.raw/venv/bin/python scripts/build_campaign.py
.raw/venv/bin/python scripts/build_presentation_manifest.py
.raw/venv/bin/python scripts/build_deadline_manifest.py
```

These commands deterministically encode the graphs, parameters, symmetry,
cutoff, `(L,d)`, basis, precision profile, resources, and independent gamma
trials. In particular, `results/dry_level_manifest.json` has 38 unique level
assemblies, `results/presentation_manifest.json` has 12 observable cells, and
`results/deadline_geometry_grid_manifest.json` has 12 cells and 23 trials.
The full requested campaign is also preserved in
`results/campaign_manifest.json`; it has 90 primary gap endpoints and 270
observable cells (1,620 min/max objectives). No random sampling or random seed
is used.

### 5. Run the hierarchy on Slurm

The submitted hard-core calculation used SCNet partition `wzacnormal03`.
Ordinary cells requested 40 CPUs, 64 GiB, and at most 6 hours. Nested and
cutoff-two attempts used 104--128 CPUs and 192--237 GiB. Do not run more jobs
than a site allocation permits; our campaign was capped at 450 GiB total.
The exact depot-staging and interactive validation commands are in
[`hpc/README.md`](hpc/README.md).

For an ordinary fixed-gamma array, use:

```bash
mkdir -p results/slurm
sbatch --array=<indices> \
  --export=ALL,ISSUE92_GAP_MANIFEST=results/<manifest>,ISSUE92_GAP_RESULTS=results/<directory> \
  hpc/issue92_deadline_gap_scan.sbatch
```

The following array map regenerates every distinct fixed-gamma input used by
the scientific summary. Rows sharing an output directory have distinct cell
IDs and are safe to run sequentially.

| manifest | result directory | array |
|---|---|---|
| `deadline_gap_scan_manifest.json` | `deadline_gap_scans` | `0-3%4` |
| `deadline_gap_refinement_manifest.json` | `deadline_gap_refinement` | `0-1%2` |
| `deadline_gap_micro_manifest.json` | `deadline_gap_refinement` | `0%1` |
| `deadline_geometry_refinement_manifest.json` | `deadline_gap_refinement` | `0-1%2` |
| `deadline_geometry_parallel_manifest.json` | `deadline_geometry_parallel` | `0%1` |
| `deadline_geometry_micro_manifest.json` | `deadline_geometry_micro` | `0-1%2` |
| `deadline_geometry_grid_manifest.json` | `deadline_geometry_grid` | `0-11%4` |
| `deadline_remaining_target_gap_manifest.json` | `deadline_remaining_target_gaps` | `0-2%3` |
| `deadline_target_refinement_manifest.json` | `deadline_target_refinement` | `0-2%2` |
| `deadline_p5_fine_manifest.json` | `deadline_p5_fine` | `0%1` |
| `deadline_p3_micro_manifest.json` | `deadline_p3_micro` | `0%1` |

The observable inputs are regenerated with:

```bash
sbatch --array=0-11%4 hpc/issue92_presentation.sbatch

sbatch --array=0-8%4 \
  --export=ALL,ISSUE92_PRESENT_MANIFEST=results/deadline_remaining_target_observable_manifest.json,ISSUE92_PRESENT_RESULTS=results/deadline_remaining_target_observables \
  hpc/issue92_presentation.sbatch

sbatch --array=0%1 \
  --export=ALL,ISSUE92_PRESENT_MANIFEST=results/deadline_exact_observable_manifest.json,ISSUE92_PRESENT_RESULTS=results/deadline_exact_observables,ISSUE92_EXACT_OBSERVABLE_CERTIFICATE=1 \
  hpc/issue92_presentation.sbatch
```

The final command reproduces the representative exact P4 observable bounds.
Task 7 of the second command reproduces the accepted P5 two-sided density and
fluctuation intervals. Repeat the nested and cutoff-two resource gates with:

```bash
sbatch --array=0-1%1 \
  --export=ALL,ISSUE92_RESULTS_DIR=results/deadline_nested_mkl \
  hpc/issue92_deadline_nested.sbatch

sbatch --array=0%1 --cpus-per-task=128 --mem=237G \
  --export=ALL,ISSUE92_GAP_MANIFEST=results/deadline_cutoff2_gap_manifest.json,ISSUE92_GAP_RESULTS=results/deadline_cutoff2_gaps \
  hpc/issue92_deadline_gap_scan.sbatch
```

Those attempts are recorded as `UNKNOWN` after exhausting 192--237 GiB, not
as physical results. The dry-assembly tiers and reduced-thread/backend retry
commands are documented in [`hpc/README.md`](hpc/README.md).

Every cell is resumable and atomically writes one JSON file. That file records
the full level sizes, solver profile and status, residuals, primal/dual data,
exact certificate report, wall time, peak RSS, allocation, and Slurm IDs. A
floating solver status never becomes `EXCLUDED`: exact coefficient projection,
256-bit sign checks, exact/interval PSD verification, zero affine residual,
and positive normalized Farkas margin must all pass.

### 6. Fetch, aggregate, and compare

Copy the complete remote `results/` tree back to the same directory, then run:

```bash
ISSUE92_CLUSTER=scnet
ISSUE92_REMOTE=quantum.harness
rsync -az "$ISSUE92_CLUSTER:$ISSUE92_REMOTE/tracks/polyopt/solutions/killer-queen-92/results/" results/
make final-report
```

This rebuilds `results/deadline_analysis/`,
[`submission/FINAL_REPORT.md`](submission/FINAL_REPORT.md), and the
self-contained [`submission/report.html`](submission/report.html). The frozen
submission audit in [`submission/data_manifest.json`](submission/data_manifest.json)
records 212 attempted fixed-gamma rows, of which 166 were durable: 76
`FEASIBLE`, 51 verified `EXCLUDED`, and 85 `UNKNOWN`. It also records 10
certified gap upper statements, 26 accepted one-sided observable endpoints,
and two accepted intervals. Repeated floating-point runs may convert a fragile
trial to `UNKNOWN`; they must never be promoted by relaxing the checker.

The pinned upstream Ising comparison is optional and separate:

```bash
.raw/venv/bin/python scripts/reproduce_reference.py
```

It requires a Mosek license. Without one, the script writes a durable
`BLOCKED` record instead of substituting another solver and calling it an
upstream reproduction.
