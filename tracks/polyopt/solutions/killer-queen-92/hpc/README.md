# SCNet campaign launch

The active production profile is
`quantum.harness/skills/using-slurm/profiles/scnet.toml`: partition
`wzacnormal03`, 128 cores and 255,551 MB per node.  Its enforced
`DefMemPerCPU=1916M` means memory and CPU requests cannot be chosen
independently.  The conservative high-memory issue-92 template requests all
128 CPUs, 225 GB, and at most 24 hours.

SCNet's default `/usr/bin/python3` is 3.6.8.  All checked-in batch scripts
load `python/3.8.10` before invoking the standard-library-only orchestration
runners.  Mosek 11.2 also requires a newer C++ runtime than SCNet's base OS;
the production and relocation scripts load `compiler/gcc/12.2.0`.

For development, instantiate and run the regression suite on a compute node
with a short interactive allocation:

```bash
salloc -p wzacnormal03 --nodes=1 --ntasks=1 --cpus-per-task=16 \
  --mem=24G --time=00:30:00 \
  srun --ntasks=1 --cpus-per-task=16 \
    env ISSUE92_RUN_ATOMIC_CERTIFICATE=1 hpc/interactive_test.sh
```

SCNet compute nodes do not currently resolve the public Julia package
servers.  Before the first allocation (and whenever `Manifest.toml` changes),
stage the pinned local depot sources and artifacts from the laptop; compiled
caches are intentionally rebuilt on the compute node:

```bash
ssh scnet 'mkdir -p ~/quantum.harness/tracks/polyopt/solutions/issue92-bose-hubbard-hyperbolic/.raw/julia-depot'
rsync -az --exclude=compiled --exclude=logs \
  --exclude='packages/Mosek/*/deps/deps.jl' \
  --exclude='packages/Mosek/*/deps/mosekbindir' \
  --exclude='packages/Mosek/*/deps/inst_method' \
  .raw/julia-depot/ scnet:quantum.harness/tracks/polyopt/solutions/issue92-bose-hubbard-hyperbolic/.raw/julia-depot/
```

`interactive_test.sh` prepends that staged depot, sets Julia package offline
mode, and instantiates without updating registries.  It therefore fails
closed if a manifest dependency was not staged, instead of trying to compile
or download on the login node.  The development precompile imports the
hierarchy/Clarabel path only; Mosek is prepared separately after a license is
installed because its generated library path is host-specific.  Relocate and
precompile the staged Mosek binary on a compute node (never the login node):

```bash
salloc -p wzacnormal03 --nodes=1 --ntasks=1 --cpus-per-task=2 \
  --mem=3G --time=00:10:00 \
  srun --ntasks=1 --cpus-per-task=2 hpc/prepare_mosek.sh
```

This only prepares the runtime.  A valid `MOSEKLM_LICENSE_FILE` or license
file is still required before the pinned reference or any production solve.

If this remains pending with `AssocGrpCpuLimit`, cancel it and wait for the
shared account quota to clear; do not move compilation onto the login node.

Generate graphs, the immutable manifest, and the pinned depot on the laptop
before syncing:

```bash
cd tracks/polyopt/solutions/issue92-bose-hubbard-hyperbolic
PYTHONPATH=src .raw/venv/bin/python scripts/export_hierarchy_graphs.py --max-radius 3
.raw/venv/bin/python scripts/build_campaign.py
JULIA_DEPOT_PATH=.raw/julia-depot: julia --project=julia -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

`build_campaign.py` also writes `results/dry_level_manifest.json`.  It contains
38 unique level assemblies, deduplicated across all parameter points and
annotated with scheduler-tier index sets.  Submit the tiers with matching
resources (or initially submit only the hard-core primary indices `6-14`):

```bash
# Slurm opens output/error files before the batch script itself starts.
mkdir -p results/slurm results/dry_levels

# Safe 64 GB hard-core rows; index 12 is excluded after the empirical gate
sbatch --array=6-11,13-14%7 --cpus-per-task=40 --mem=64G hpc/issue92_dry.sbatch

# 192 GB tier, including the promoted {12,4} hard-core (2,2) row at index 12
sbatch --array=12,18-32%2 --cpus-per-task=104 --mem=192G hpc/issue92_dry.sbatch

# 225 GB tier, indices 33-37
sbatch --array=33-37%2 --cpus-per-task=128 --mem=225G hpc/issue92_dry.sbatch
```

Each dry row is atomically written under `results/dry_levels/` and records
the complete structural metadata, assembly wall time, actual child-process
peak RSS, allocation, and an explicit error reason on failure.  Running
`scripts/aggregate_campaign.py` overlays these records onto the 38-row level
table even before any solver cell is launched.

For TS2, chordal completion maintains each active vertex degree across fill
and elimination.  This preserves the original deterministic minimum-degree
tie-breaking and clique sequence while removing the former repeated cubic
degree scan.  Nineteen reference-equivalence tests cover the transformation;
a deterministic 220-vertex kernel benchmark improved from 0.188 seconds to
0.0091 seconds on the development machine.  This is an assembly optimization,
not a change to the formal TS2 support-closure level.

The pair-support phase is also parallel: each Julia thread evaluates a
read-only row against the fixed support seed and adjacency, after which rows
are merged in the original lexicographic order.  Dry runs enable phase
progress messages by default.  For the `{8,3}` cutoff-two gates, `(1,3)` has
10,921 moment monomials and 11,595,621 charge-compatible upper-triangle pairs
per closure pass; `(2,2)` has 5,421 and 3,109,596.  The full 577-assertion
suite passes with four Julia threads before the 104-thread SCNet retry.
Final clique matrices are likewise materialized in parallel into an indexed
output vector.  Each worker owns its matrix, inputs are read-only, and the
indexed merge preserves the exact clique order; entry-by-entry tests compare
the result with dense-reference sparsification.
Reproduce the deterministic chordal kernel comparison with:

```bash
JULIA_DEPOT_PATH=.raw/julia-depot: julia --project=julia \
  julia/scripts/benchmark_ts2_chordal.jl 220
```

The hard-core dry evidence separates assembly and solve resources.  Baseline
`(L,d)=(1,2)` production cells remain at 64 GB.  The tighter primary
`(2,2)` and `(1,3)` cells request 192 GB/104 CPUs.  Completed expression
assemblies used roughly 8--25 GB; the largest `{12,4}` `(2,2)` assembly was
cancelled from its original 64-GB allocation after its RSS had already grown
past 52 GB, then completed at 55.40 GB peak RSS in the 192-GB tier.  The
JuMP/Mosek workspace is
measured separately by the model-build gate below.
The dry manifest preserves both the allocation actually used for assembly and
the promoted production request.

For selected levels, a second dry mode constructs the complete unsolved
JuMP/Clarabel workspace.  This does not require a Mosek license and measures
the memory added after symbolic hierarchy assembly:

```bash
# Baseline hard-core model builds
ISSUE92_DRY_BUILD_MODEL=1 sbatch --export=ALL,ISSUE92_DRY_BUILD_MODEL=1 \
  --array=6-8%3 --cpus-per-task=40 --mem=64G hpc/issue92_dry.sbatch

# Tighter hard-core model builds use the promoted production tier
ISSUE92_DRY_BUILD_MODEL=1 sbatch --export=ALL,ISSUE92_DRY_BUILD_MODEL=1 \
  --array=9-14%2 --cpus-per-task=104 --mem=192G hpc/issue92_dry.sbatch
```

These records go to `results/dry_models/`; aggregation reports their build
status, wall time, peak RSS, solver, and JuMP variable count separately from
the expression-only dry rows.  They are resource evidence, not solves.

An optional end-to-end Clarabel pilot exercises the production cell driver
without writing into `results/hierarchy_cells`:

```bash
# Default array index 4 is Target-2 P2, {8,3}, nmax=1, complete (L,d)=(1,2).
sbatch hpc/issue92_clarabel_pilot.sbatch
```

Its checkpoints live under `results/clarabel_pilots/`.  They are numerical
diagnostics only; they do not replace the pinned Mosek reference or the Mosek
production campaign.

For a next-day presentation, the bounded low-precision pilot is generated and
submitted separately:

```bash
.raw/venv/bin/python scripts/build_presentation_manifest.py
sbatch hpc/issue92_presentation.sbatch
```

The deadline wrappers also accept explicit resumable manifest/result pairs,
so follow-up arrays do not overwrite the baseline campaign:

```bash
sbatch --export=ALL,ISSUE92_PRESENT_MANIFEST=results/<manifest>.json,ISSUE92_PRESENT_RESULTS=results/<output> \
  --array=<indices>%<concurrency> hpc/issue92_presentation.sbatch
sbatch --export=ALL,ISSUE92_GAP_MANIFEST=results/<manifest>.json,ISSUE92_GAP_RESULTS=results/<output> \
  --array=<indices>%<concurrency> hpc/issue92_deadline_gap_scan.sbatch
```

Command-line `--mem` and `--cpus-per-task` must meet each generated cell's
`requested_memory_gb` and `requested_cpus`; the runner fails before Julia if
the allocation is smaller. Dependencies across arrays must still enforce the
global 450-GiB issue-92 ceiling.

The gap wrapper normally maps all allocated CPUs to Julia, BLAS, MKL, and
OpenMP.  A memory-bound retry can retain the large scheduler allocation while
limiting per-thread factorization workspace with
`ISSUE92_JULIA_NUM_THREADS`, `ISSUE92_OPENBLAS_NUM_THREADS`,
`ISSUE92_MKL_NUM_THREADS`, `ISSUE92_OMP_NUM_THREADS`, and
`ISSUE92_CLARABEL_MAX_THREADS`.  The requested CPU/memory gate still checks
the Slurm allocation, not these internal thread caps, and the caps must be
recorded with the result.

It covers P2 on all three geometries and P4 on `{8,3}`, at all three requested
`gamma` values: 12 cells and 72 observable objectives.  Each Clarabel solve is
capped at 600 seconds and 60 iterations.  The scientific residual threshold
is not relaxed; the output directory is `results/presentation_pilots`, and
every result remains explicitly `LOW_PRECISION_CLARABEL_DIAGNOSTIC_ONLY`.
For `nmax=1`, newly starting cells solve only `rho0` and `K0`: the two `F0`
bounds are recorded with explicit provenance from the exact identity
`F0=1-rho0`, saving two redundant conic solves while preserving the source
primal/dual records.

For a selected representative observable cell, set
`ISSUE92_EXACT_OBSERVABLE_CERTIFICATE=1`.  The cell still solves all six
objectives with one cached hierarchy template, then independently projects
each dual onto the exact observable identity.  A singular floating optimum is
handled by an auxiliary interior-dual solve at a tiny conservative backoff;
the result is accepted only after exact affine and PSD checks.  The JSON keeps
the exact `Q(sqrt(2),sqrt(3))` multipliers and Gram matrices, the certified
lower/upper endpoint, and its normalized gap from the floating optimum.  This
option is intended for selected headline cells, not every observable cell:

With `ISSUE92_SOLVE_PROGRESS=1`, the log distinguishes exact-system assembly,
rational affine projection, rigorous PSD checking, and every auxiliary
interior-SDP attempt.  A long interval after ordinary dual diagnostics is
therefore visible as certificate work rather than being mistaken for a hung
optimizer.

Projected Gram matrices are first tested by a rigorous 256-bit Arb interval
LDL.  Strictly positive interval pivots certify the cone directly; a
zero-containing or otherwise inconclusive pivot first gets a cheap
floating-eigenvector search for a negative direction.  That path rejects a
block only when the proposed integer vector has a strictly negative quadratic
form in exact `Q(sqrt(2),sqrt(3))` arithmetic.  If no such witness exists, the
block falls back to a symmetrically pivoted exact-field LDL/Schur test, so
singular PSD certificates remain rigorous without repeatedly forming long
rational sums.  On the stored P3
hard-core certificate this reduced PSD wall time from about 200 seconds to
under one second without changing the exact affine or Farkas checks.
On the stored `{12,4}` P2 `gamma/U=0.520` certificate, all eight blocks
(largest `222x222`) replay in 3.125 seconds with rigorous interval LDL; the
already-running pre-optimization checker took 1,943 seconds on the same stored
matrices.  `julia/scripts/benchmark_projected_psd.jl` reproduces this PSD-only
timing audit and deliberately does not replace the full affine/margin checker.

```bash
ISSUE92_EXACT_OBSERVABLE_CERTIFICATE=1 ISSUE92_FORCE=1 sbatch \
  --export=ALL,ISSUE92_EXACT_OBSERVABLE_CERTIFICATE=1,ISSUE92_FORCE=1 \
  --array=<representative-index> hpc/issue92_cell.sbatch
```

`ISSUE92_FORCE=1` is needed when upgrading an already-complete floating cell;
without it, the resumable runner correctly skips completed work.

At `nmax=1`, a derived `F0=1-rho0` endpoint uses the source certificate's
conservative projected objective, not its floating optimum, and records both
numbers plus the source certificate report.

Split the manifest into Slurm arrays of at most 200 cells.  For a homogeneous
memory group, set array concurrency to
`min(8, floor(450/requested_memory_gb))`; this is `2` for 225-GB or 192-GB
cells and `7` for 64-GB cells.  Request at least 128, 104, or 40 CPUs for
those three memory tiers, respectively, to satisfy the partition's
memory-per-CPU rule.  The 450-GB cap is global across all simultaneous
issue-92 arrays, so do not independently launch two arrays at each tier's
maximum concurrency.  The checked-in sbatch file uses the conservative
128-CPU/225-GB setting.  Submit each chunk with its offset and
matching last array index, for example:

```bash
ISSUE92_ARRAY_OFFSET=0 sbatch --array=0-199%1 hpc/issue92_cell.sbatch
ISSUE92_ARRAY_OFFSET=200 sbatch --array=0-199%1 hpc/issue92_cell.sbatch
```

Do not submit the optional `nmax=3` cells until their `dry_assemble.jl`
summary is at most 225 GB and a representative hard solve finishes within six
hours.  Each bisection/objective solve atomically rewrites its own JSON result,
so resubmission skips only cells whose status is already `COMPLETE`.  At the
end of every wrapper attempt, the same JSON also records total wall time, peak
child RSS, allocated memory/CPUs, and Slurm job/array IDs; interrupted
`RUNNING` checkpoints remain resumable.
