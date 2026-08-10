# MinimalTFIM.jl

A compact, independent Julia implementation of discrete-imaginary-time
cluster Monte Carlo for the transverse-field Ising model. It supports
triangular and honeycomb lattices, local Metropolis sweeps, ordinary Wolff
clusters, and MPI-parallel independent Markov chains.

This directory is the Only-team submission for Harnessing Quantum Challenge
#148. The challenge asks whether the ratio of the triangular- and
honeycomb-lattice critical transverse fields is exactly √5.

## Result at a glance

The predeclared 243-point primary analysis gives

```text
h_c(triangular) = 4.768626879 ± 0.001019229
h_c(honeycomb)  = 2.132538417 ± 0.000562147
R               = 2.236157603 ± 0.000759908
95% interval    = [2.234599154, 2.237603704]
```

Here and below, quoted uncertainties for the final estimates are bootstrap
standard errors. The interval contains √5=2.236067978, so the calculation
neither establishes nor excludes exact equality.

Blöte and Deng, Phys. Rev. E 66, 066110 (2002), report
`h_c(triangular)=4.76811(9)` and `h_c(honeycomb)=2.13250(4)`. Their central
values give `R_PRE=2.235924971 ± 0.000059499` when the two published field
uncertainties are treated as independent. Our primary central value is closer
to √5. A separately labelled 273-point sensitivity analysis that includes
`Δτ=0.004` gives `R=2.236429014 ± 0.000461302`; its central value is farther
from √5, while its 95% interval still contains √5. This comparison is reported
to expose time-step sensitivity, not to select whichever estimate is closest.

Team: **Only-team** · Member: **Xingcan-Liu** · Challenge issue: **#148**

## Physics problem

The simulated Hamiltonian is

```math
H=J_1\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x ,
```

with Pauli matrices, periodic boundary conditions, `J1=-1`, `J2=0`, and
`h=hTrfd>0`. The sign is intentional: `J1<0` is ferromagnetic. Inputs,
metadata, tests, and outputs retain `J1=-1`; the program rejects `J1>=0` and
`J2!=0`.

The two spatial geometries are:

- triangular: one site per unit cell, coordination number 6, `N=L1*L2`;
- honeycomb: two sublattices per unit cell, coordination number 3,
  `N=2*L1*L2`.

The order-parameter moments are measured from the longitudinal magnetization.
The dimensionless crossing observable is the Binder moment ratio
`Q=<m²>²/<m⁴>`.

## Algorithm

### Discrete imaginary time

A Suzuki–Trotter decomposition maps the two-dimensional quantum model to an
anisotropic `(2+1)`-dimensional classical Ising model. The sampled variables
are `spins[site,tau] = ±1`, with periodic imaginary time. For time step `Δτ`,

```math
\log W =
K_{\rm space}\sum_{\langle i,j\rangle,\tau}s_{i,\tau}s_{j,\tau}
+K_\tau\sum_{i,\tau}s_{i,\tau}s_{i,\tau+1},
```

where

```math
K_{\rm space}=-\Delta\tau J_1,\qquad
K_\tau=-\frac{1}{2}\log[\tanh(h\Delta\tau)].
```

Both couplings are positive in the supported ferromagnetic regime. When
`IfSetDltau=true`, the code sets `LTrot=ceil(BetaT/FixedDltau)`, increases an
odd value to the next even integer, and finally uses `Dltau=BetaT/LTrot`.
Metadata records both requested and actual values.

### Updates and measurements

One update cycle performs `nLocal` full Metropolis sweeps followed by
`nWolff` ordinary Wolff-cluster flips:

- a local sweep visits every space-time spin and accepts from its exact
  change in `logW`;
- a Wolff cluster connects equal spins with
  `p_space=1-exp(-2*K_space)` and `p_tau=1-exp(-2*K_tau)`, then flips the
  complete cluster without an additional acceptance test.

Warmup is performed once. Each subsequent sweep updates first and measures
second. A measurement samples one imaginary-time slice from each of
`NmMeaConfg` non-overlapping segments, computes `m²` and `m⁴` on every chosen
slice, and then averages the moments across slices.

Every MPI rank owns a complete lattice and runs an independent Markov chain
with a deterministic rank-specific seed. Rank-level bin moments are reduced
only at bin boundaries. Rank 0 writes the shared output.

### Scaling analysis

Binder curves are fitted to correction-aware finite-size forms using the
three-dimensional Ising exponents `y_t=1.587` and `y_i=-0.815`. The report
shows Binder crossings, correction-adjusted data collapse, 64 predefined
fit variants, and the dependence on the minimum retained size. Critical
fields obtained at finite time step are extrapolated linearly in each cell's
actual `Δτ²`. Bootstrap resampling operates on saved bin averages and
propagates through the finite-size fits, continuum extrapolation, and ratio.

## Quick start

Requirements:

- Julia 1.10 or newer;
- an MPI implementation available to MPI.jl;
- Python 3.11 or newer for the challenge post-processing and HTML report.

Create the Python environment from a fresh checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install \
  numpy==2.5.1 scipy==1.18.0 matplotlib==3.11.1
```

From the repository root, instantiate the Julia environment once:

```bash
julia --project=tracks/qmc/solutions/Only-team \
  -e 'using Pkg; Pkg.instantiate()'
```

Run the complete Julia test suite:

```bash
julia --project=tracks/qmc/solutions/Only-team \
  -e 'using Pkg; Pkg.test()'
```

### Five-minute single-rank demo

The bundled smoke input is intentionally tiny. The following commands copy it
to a temporary TOML file and assign a fresh ignored output directory:

```bash
solution=tracks/qmc/solutions/Only-team
demo_config=$(mktemp --suffix=.toml)
demo_output="tracks/qmc/results/Only-team/demo-triangular-$(date +%Y%m%d-%H%M%S)"
sed "s#^output_dir = .*#output_dir = \"$demo_output\"#" \
  "$solution/configs/smoke-triangular.toml" > "$demo_config"

julia --project="$solution" \
  "$solution/scripts/run.jl" "$demo_config"

printf 'Demo output: %s\n' "$demo_output"
```

For clarity, the fully expanded runner is
`julia --project=tracks/qmc/solutions/Only-team
tracks/qmc/solutions/Only-team/scripts/run.jl
tracks/qmc/solutions/Only-team/configs/smoke-triangular.toml`; use a copy with
a new `output_dir` when that bundled destination already exists.

The default safety policy rejects an existing non-empty output directory.
Change `output_dir` rather than overwriting a prior run.

### MPI demo

Use the same code path with two independent chains:

```bash
solution=tracks/qmc/solutions/Only-team
mpi_config=$(mktemp --suffix=.toml)
mpi_output="tracks/qmc/results/Only-team/demo-honeycomb-mpi-$(date +%Y%m%d-%H%M%S)"
sed "s#^output_dir = .*#output_dir = \"$mpi_output\"#" \
  "$solution/configs/smoke-honeycomb.toml" > "$mpi_config"

mpiexec -n 2 julia --project="$solution" \
  "$solution/scripts/run.jl" "$mpi_config"
```

The production calculations used the identical executable with 32 ranks per
simulation point.

## Configuration

Inputs are TOML files. The supplied examples live in `configs/`.

| Field | Meaning |
|---|---|
| `lattice` | `triangular` or `honeycomb` |
| `NumL1`, `NumL2` | periodic spatial dimensions, each at least 3 |
| `J1`, `J2`, `hTrfd` | supported regime: `J1<0`, `J2=0`, `hTrfd>0` |
| `BetaT` | inverse quantum temperature |
| `IfSetDltau`, `FixedDltau`, `LTrot` | requested and fallback imaginary-time discretization |
| `nLocal`, `nWolff` | full local sweeps and Wolff clusters per update cycle |
| `nWarm` | update cycles discarded before measurement |
| `NmBin`, `NSwep` | number of bins and measured sweeps per bin |
| `NmMeaConfg` | number of imaginary-time segments sampled per measurement |
| `discard_initial_bins` | leading production bins removed before summary statistics |
| `trim_extrema` | independently remove one minimum and maximum from each bin sequence |
| `statistics_mode` | currently `bin_sem` |
| `seed` | deterministic base seed; each MPI rank receives a distinct derived seed |
| `initial_state` | `random` or `ordered` |
| `output_dir` | relative destination under the repository |

The production update cycle used `nLocal=1` and `nWolff=5`. Nothing in the
driver silently changes these values.

## Output files

Only rank 0 writes the common result directory:

- `results.csv`: parameters, total measurements, `m²`, Binder `Q`, and their
  bin standard errors;
- `bins.csv`: `m2_bin`, `m4_bin`, and `Q_bin` for every retained raw bin, so
  nonlinear estimators can be recomputed;
- `metadata.toml`: input and derived parameters, effective couplings, MPI
  seeds, acceptance and cluster diagnostics, software version, and wall time.

Challenge scan cells additionally contain a manifest with hashes and the exact
cell parameters. Generated data and figures remain under
`tracks/qmc/results/Only-team/`, which is intentionally ignored by Git.

## Reproduce the challenge analysis

The complete audited set contains 273 unique simulation points across eight
result directories. Those raw results are intentionally absent from a fresh
checkout because the challenge requires generated data to remain under the
gitignored `tracks/qmc/results/` tree. Reproduction therefore has two explicit
stages: regenerate and execute the tracked simulation specifications, then run
the deterministic analysis below. If the eight audited result directories
have already been supplied, skip directly to the analysis commands.

From the repository root, recreate all eight run specifications:

```bash
solution=tracks/qmc/solutions/Only-team
results=tracks/qmc/results/Only-team

.venv/bin/python scripts/parameter_scan.py plan \
  --axes "$solution/configs/challenge-extremes-min-axes.json" \
  --settings "$solution/configs/challenge-extremes-settings.json" \
  --run-id challenge-extremes-min-20260729 \
  --run-dir "$results/challenge-extremes-min-20260729"

.venv/bin/python scripts/parameter_scan.py plan \
  --axes "$solution/configs/challenge-extremes-max-axes.json" \
  --settings "$solution/configs/challenge-extremes-settings.json" \
  --run-id challenge-extremes-max-20260729 \
  --run-dir "$results/challenge-extremes-max-20260729"

.venv/bin/python "$solution/scripts/generate_challenge_scan_specs.py" \
  --repo-root "$PWD"

.venv/bin/python "$solution/scripts/generate_precision_recovery_specs.py" \
  --repo-root "$PWD" --include-small-step
```

Each cell uses the same Julia executable as the demos, with 32 independent MPI
chains. On the SCNet profile used for this submission, launch the first six
specifications with the tracked batch files:

```bash
sbatch "$solution/scripts/scnet-extremes-min.sbatch"
sbatch "$solution/scripts/scnet-extremes-max.sbatch"
sbatch "$solution/scripts/scnet-challenge-triangular.sbatch"
sbatch "$solution/scripts/scnet-challenge-honeycomb.sbatch"
sbatch "$solution/scripts/scnet-precision-recovery-triangular.sbatch"
sbatch "$solution/scripts/scnet-precision-recovery-honeycomb.sbatch"
```

The two 15-cell small-step specifications use the same audited cell runner.
The following arrays reproduce the scientific cells; adjust only the
partition, concurrency cap, memory, and wall-time directives for another
Slurm installation:

```bash
runner="$PWD/$solution/scripts/run_challenge_scan_cell.sh"
for lattice in triangular honeycomb
do
  spec="$results/challenge-dtau004-$lattice-20260729/run_spec.json"
  sbatch \
    --job-name="tfim-dt004-$lattice" \
    --partition=xhacnormalb --nodes=1 --ntasks=32 --cpus-per-task=1 \
    --mem=64G --time=20:00:00 --array=1-15%10 \
    --export="ALL,HARNESS_RUN_SPEC=$spec" \
    --output="dtau004-$lattice-%A_%a.log" \
    --wrap="$runner"
done
```

Do not begin the analysis until every cell has produced a manifest. The audit
command below rejects missing or duplicate cells, changed hashes, incomplete
bin sequences, repeated rank seeds, non-finite values, and inconsistent
per-bin Binder ratios.

Then run the complete deterministic analysis:

```bash
analysis=tracks/qmc/results/Only-team/challenge-analysis-final-20260730
run_args=(
  --run-dir tracks/qmc/results/Only-team/challenge-extremes-min-20260729
  --run-dir tracks/qmc/results/Only-team/challenge-extremes-max-20260729
  --run-dir tracks/qmc/results/Only-team/challenge-production-triangular-20260729
  --run-dir tracks/qmc/results/Only-team/challenge-production-honeycomb-20260729
  --run-dir tracks/qmc/results/Only-team/challenge-precision-recovery-triangular-20260729
  --run-dir tracks/qmc/results/Only-team/challenge-precision-recovery-honeycomb-20260729
  --run-dir tracks/qmc/results/Only-team/challenge-dtau004-triangular-20260729
  --run-dir tracks/qmc/results/Only-team/challenge-dtau004-honeycomb-20260729
)

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/audit_challenge_results.py \
  "${run_args[@]}" --output-dir "$analysis" --write-ratified-selection

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/assemble_challenge_dataset.py \
  "${run_args[@]}" --output-dir "$analysis"

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/fit_binder_scaling.py \
  --cells "$analysis/cells.csv" --bins "$analysis/bins.csv" \
  --output-dir "$analysis" --bootstrap 2000 --seed 20260729

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/fit_binder_scaling.py \
  --cells "$analysis/cells.csv" --bins "$analysis/bins.csv" \
  --output-dir "$analysis" --bootstrap 2000 --seed 20260729 \
  --only-sensitivities --selection "$analysis/accepted_cells.json"

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/extrapolate_dtau.py \
  --cells "$analysis/cells.csv" --bins "$analysis/bins.csv" \
  --output-dir "$analysis" --bootstrap 2000 --seed 20260731 \
  --step-mode primary \
  --finite-size-fits "$analysis/finite_size_fits.csv" \
  --finite-size-sensitivities "$analysis/finite_size_sensitivities.csv"

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/extrapolate_dtau.py \
  --cells "$analysis/cells.csv" --bins "$analysis/bins.csv" \
  --output-dir "$analysis/dtau004-sensitivity" \
  --bootstrap 2000 --seed 20260731 --step-mode small_step_sensitivity \
  --finite-size-fits "$analysis/finite_size_fits.csv" \
  --finite-size-sensitivities "$analysis/finite_size_sensitivities.csv"

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/plot_challenge_results.py \
  --cells "$analysis/cells.csv" \
  --finite-size-fits "$analysis/finite_size_fits.csv" \
  --dtau-fits "$analysis/dtau_fits.csv" \
  --final-results "$analysis/final_results.json" \
  --sensitivity-results "$analysis/dtau004-sensitivity/final_results.json" \
  --output-dir "$analysis/figures"

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/plot_challenge_results.py \
  --cells "$analysis/cells.csv" \
  --finite-size-fits "$analysis/finite_size_fits.csv" \
  --dtau-fits "$analysis/dtau004-sensitivity/dtau_fits.csv" \
  --final-results "$analysis/final_results.json" \
  --sensitivity-results "$analysis/dtau004-sensitivity/final_results.json" \
  --output-dir "$analysis/dtau004-sensitivity/figures"

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/build_challenge_run.py \
  "$analysis"
.venv/bin/python skills/report/render_report.py "$analysis"
```

The self-contained report is written to
`tracks/qmc/results/Only-team/challenge-analysis-final-20260730/report.html`.
All figures are embedded, so the HTML file can be reviewed offline.

## Verification and limitations

The implementation is checked at four levels:

1. lattice invariants, coupling/probability regression values, periodic
   imaginary time, local weight differences, cluster membership, measurement
   formulas, statistics, deterministic seeds, output safety, and MPI smoke
   tests;
2. triangular 3×3 and honeycomb 2×2 comparisons with exact diagonalization
   and exact finite-Trotter enumeration, including the Binder normalization;
3. an audit of all 273 simulation points, hashes, rank seeds, 32-bin
   sequences, finite values, and `Q_bin=m2_bin²/m4_bin`;
4. finite-size fit families, size-cut sensitivity, correction-adjusted data
   collapse, actual-`Δτ²` extrapolation, and bin-level bootstrap.

The main residual uncertainties are finite-size correction-family dependence,
one triangular finite-step crossing at the edge of its common field window,
and disagreement between two-stage and joint continuum fits above the desired
fifth-decimal scale. The program uses discrete rather than continuous
imaginary time, so a finite `Δτ` result is not itself the quantum limit.
Large triangular points also remain above the original per-point Binder-SEM
planning target; their measured uncertainties are retained in the weighted
fits and Bootstrap.

The current scope does not include energy, correlation length, dynamical
observables, frustrated interactions, antiferromagnetic couplings, geometric
cluster acceleration, spatial MPI decomposition, GPU execution, or automatic
finite-size model selection.

See also:

- `CURRENT_STATUS.md` — final numerical status and provenance;
- `PRECISION_RECOVERY_PLAN.md` — predeclared recovery and small-step
  sensitivity policies;
- `VALIDATION.md` — exact small-system checks;
- `configs/` — runnable examples.
