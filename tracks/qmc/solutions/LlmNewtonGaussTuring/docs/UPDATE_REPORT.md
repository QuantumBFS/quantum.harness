# TFIM SSE Update-Algorithm Benchmark Track

Date: 2026-07-30

Current C++ run ID: `tfim-cpp-cluster-loop-line-benchmark-full-20260730`

## Current objective

The deliverable is no longer a high-precision test of the proposed √5
critical-field ratio. Local compute is insufficient for a credible
`1e-5`-scale finite-size extrapolation. The active result is instead a
dependency-free C++17 comparison of cluster, merge--unmerge loop, and true
local worldline-segment line updates on identical SSE configurations.

The Julia results below are retained as historical validation and design
context. The C++ comparison is the current implementation track.

## C++ matched-kernel pilot

All C++ kernels share the lattice builder, operator storage, diagonal update,
measurement routine, RNG family, and Sokal-window analysis. `cluster` joins
worldline segments with bond operators, `loop` is the merge--unmerge kernel,
and `line` rebuilds site-local operator lists and uses heat-bath segment flips.
No third-party library is used.

The first pilot used one chain per algorithm/lattice, 100 thermalization and
1,000 measurement sweeps. Its autocorrelation windows all closed, but a
single short chain is not sufficient to assign stable performance error bars.
The figures below are therefore directional pilot measurements only.

| lattice | observable | loop ESS/s | line ESS/s | line / loop |
|---|---|---:|---:|---:|
| triangular `L=12, beta=24` | `E` | 9.26 | 24.28 | 2.62x |
| triangular | `mx` | 3.38 | 5.46 | 1.62x |
| triangular | `m2` | 1.12 | 4.84 | 4.32x |
| triangular | `m4` | 1.60 | 4.95 | 3.11x |
| honeycomb `8x8, beta=16` | `E` | 105.36 | 285.01 | 2.71x |
| honeycomb | `mx` | 6.33 | 25.78 | 4.08x |
| honeycomb | `m2` | 3.89 | 10.03 | 2.58x |
| honeycomb | `m4` | 4.38 | 9.67 | 2.21x |

The corresponding line/loop sweep-time ratios are 0.37 on triangular
(`3.17` vs `8.63` ms) and 0.43 on honeycomb (`0.88` vs `2.07` ms). Raw
per-observable `tau_int`, windows, seeds, and wall-clock measurements are in
`data/processed/tfim-cpp-loop-line-benchmark-20260730/efficiency.csv`.

### Cluster comparison update

The earlier table compared only loop and line. A rejection-free worldline
cluster kernel is now implemented in the same C++ state and was ED-validated.
In its one-chain, 1,000-measurement-sweep pilot, line remained the cheapest
sweep but cluster reduced autocorrelation of slow magnetic observables enough
to change the ranking:

| lattice | observable | cluster ESS/s | line ESS/s | line / cluster |
|---|---|---:|---:|---:|
| triangular `L=12` | `E` | 27.31 | 25.96 | 0.95x |
| triangular | `mx` | 10.49 | 1.83 | 0.17x |
| triangular | `m2` | 1.81 | 1.45 | 0.80x |
| triangular | `m4` | 2.11 | 1.61 | 0.76x |
| honeycomb `8x8` | `E` | 262.25 | 272.96 | 1.04x |
| honeycomb | `mx` | 28.17 | 12.91 | 0.46x |
| honeycomb | `m2` | 12.03 | 5.76 | 0.48x |
| honeycomb | `m4` | 14.84 | 6.29 | 0.42x |

This is directional only: its chain is short relative to the slowest
autocorrelation times. The fair next result is a three-repeat,
20,000-measurement-sweep `cluster/loop/line` benchmark. Raw pilot data is in
`data/processed/tfim-cpp-cluster-loop-line-benchmark-20260730/efficiency.csv`.

### Three-repeat C++ result

The planned three-repeat run completed with 5,000 thermalization and 20,000
measurement sweeps per chain. All 72 observable chains had converged Sokal
windows. Across-chain means are mutually compatible at the available precision;
the short-pilot honeycomb mean split did not persist. The table reports mean
ESS/s across the three independent chains:

| lattice | observable | cluster | loop | line |
|---|---|---:|---:|---:|
| triangular `L=12` | `E` | 29.91 | 13.10 | **34.56** |
| triangular | `mx` | **5.84** | 1.80 | 4.83 |
| triangular | `m2` | **1.55** | 0.39 | 0.80 |
| triangular | `m4` | **1.80** | 0.47 | 0.92 |
| honeycomb `8x8` | `E` | 232.19 | 122.69 | **287.73** |
| honeycomb | `mx` | 19.48 | 9.04 | **21.98** |
| honeycomb | `m2` | **4.77** | 1.30 | 2.44 |
| honeycomb | `m4` | **5.48** | 1.47 | 3.16 |

Line has the smallest sweep cost (triangular `3.45` ms, honeycomb `0.89` ms),
and wins energy ESS/s by 15--24%. Cluster roughly halves the `m2/m4`
autocorrelation times, making it 1.7--1.9x faster for Binder/FSS observables.
The merge--unmerge loop is slower than both kernels in every measured cell.
Thus, cluster is the serial production reference for critical magnetic
observables, while line is the preferred low-cost/parallelization kernel and
the best energy sampler.

The full data is in
`data/processed/tfim-cpp-cluster-loop-line-benchmark-full-20260730/efficiency.csv`.

Before treating these gains as final, repeat independent chains and lengthen
them until the slowest `m2/m4` chains have many independent blocks. The C++
benchmark executable is `build/tfim_update_benchmark` and accepts output path,
repeat count, thermalization sweeps, and measurement sweeps.

### C++ finite-temperature ED cross-check

The C++ cluster, loop, and segment-line kernels were independently checked against a dependency-free
full-spectrum ED oracle using the same FM Hamiltonian, periodic clusters, and
observable normalization at `beta=2`. Triangular `3x2` (`2^6=64`) and
honeycomb `2x2` cells (`2^8=256`) were each sampled with 5,000 thermalization
and 20,000 measurement sweeps for all three updates. All 18 comparisons of `E/N`,
`mx`, and `m2` passed the predeclared four-sigma QMC gate; the largest z-score
was 1.45. This rules out an obvious small-cluster sign, segment-bit, or
normalization defect in the C++ line port. It does not by itself resolve the
approximately 2.6-sigma large-honeycomb repeat-mean split, which still calls
for longer independent chains before a final performance claim.

The raw comparison is in
`data/processed/tfim-cpp-cluster-loop-line-ed-validation-20260730/validation.csv`, generated by
`build/tfim_ed_validation`.

---

Historical Julia run ID: `tfim-lineupdate-julia-20260730`

Source: `01134d3cee3fa0625cb65f255c0ea04d1e1baaae`

## Result

At the literature critical fields, the serial line update produced more
effective samples per second than the merge--unmerge loop update for every
measured observable on both lattices. The gain was 3.58--5.53x on the
triangular lattice and 3.12--5.67x on the honeycomb lattice. The color kernel
also scaled to eight threads, but the full-sweep gain was limited to 1.66x and
1.20x by the serial diagonal update, list construction, and measurement.

This is the **win** branch of the planned three-way conclusion: the local line
update loses little or nothing in integrated autocorrelation at these two
points, is 3.3--4.0x cheaper per serial sweep, and exposes useful spatial
parallelism. It does not establish the requested `1e-5` critical-field ratio;
it establishes a faster update kernel and identifies the next serial
bottlenecks for a production campaign.

## Conventions and algorithms

The implementation uses

```text
H = J sum_<ij> sigma_i^z sigma_j^z - B sum_i sigma_i^z - Gamma sum_i sigma_i^x.
```

Challenge 148's ferromagnet therefore uses `J=-1`, `B=0`, with
`Gamma=4.76811` (triangular) or `2.13250` (honeycomb). This sign is essential
on the non-bipartite triangular lattice.

Both algorithms share the lattice builder, `Sim` state, diagonal update, and
estimators. The loop kernel is the group's merge--unmerge update; the line
kernel flips local worldline segments with heat-bath probability
`R/(1+R)`. The heat-bath rule is necessary: Metropolis would flip every
zero-bond segment deterministically when `R=1`, losing ergodicity in the
`J=0` limit. Proper vertex coloring makes same-color writes disjoint:
honeycomb uses two colors and triangular tori with dimensions divisible by
three use `c=(x+2y) mod 3`.

## Correctness gates

The smoke suite passed all 12 coloring, analytic-limit, worldline, and
parallel checks. A separate finite-temperature gate compared serial line,
serial loop, and four-thread line runs against full-spectrum ED at `beta=2`:

| lattice | cluster | Hilbert dimension | observables | largest ED z-score |
|---|---:|---:|---|---:|
| triangular | 3x3 | 512 | `E/N`, `mx`, `mz2` | 2.53 |
| honeycomb | 2x2 cells | 256 | `E/N`, `mx`, `mz2` | 3.18 |

All 18 comparisons passed the predeclared four-sigma gate, all Hamiltonians
had zero measured Hermiticity error, and all autocorrelation windows
converged. The serial and parallel line paths independently agreed with ED.

## Statistical efficiency

Single-thread runs used 5,000 thermalization sweeps and 20,000 saved sweeps.
The triangular point was `L=12, beta=24`; the honeycomb point was `8x8`
unit cells (`N=128`), `beta=16`. Integrated autocorrelation used the
self-consistent Sokal window with factor five and convention
`tau_int = 1/2 + sum rho(t)`. Effective throughput is
`1/(2 tau_int t_sweep)`.

| lattice | observable | loop tau | line tau | loop ESS/s | line ESS/s | gain |
|---|---|---:|---:|---:|---:|---:|
| triangular | `E` | 4.07 | 4.14 | 14.57 | 57.62 | 3.96x |
| triangular | `mx` | 35.91 | 26.15 | 1.65 | 9.13 | 5.53x |
| triangular | `m2` | 109.40 | 121.33 | 0.54 | 1.97 | 3.63x |
| triangular | `m4` | 80.55 | 90.47 | 0.74 | 2.64 | 3.58x |
| honeycomb | `E` | 1.84 | 1.97 | 139.63 | 434.96 | 3.12x |
| honeycomb | `mx` | 39.78 | 23.36 | 6.46 | 36.63 | 5.67x |
| honeycomb | `m2` | 202.94 | 146.17 | 1.27 | 5.85 | 4.63x |
| honeycomb | `m4` | 176.13 | 129.98 | 1.46 | 6.58 | 4.52x |

The line-vs-loop central values agree within their combined autocorrelation-
adjusted errors. The slowest observables have only O(100) effective samples,
so the exact ratios above are benchmark estimates, not asymptotic constants;
their uniform direction and large margins are the robust conclusion.

![Effective-sample benchmark](data/processed/tfim-lineupdate-julia-20260730/efficiency.png)

## Strong scaling

The fixed scaling problems were triangular `L=24, beta=48` and honeycomb
`12x12` cells, `beta=24`, with 1,000 thermalization and 500 timed sweeps.

| lattice | threads | color-kernel speedup | full-sweep speedup |
|---|---:|---:|---:|
| triangular | 2 | 1.92x | 1.30x |
| triangular | 4 | 3.00x | 1.49x |
| triangular | 8 | 4.90x | 1.66x |
| honeycomb | 2 | 1.26x | 1.04x |
| honeycomb | 4 | 1.91x | 1.16x |
| honeycomb | 8 | 2.51x | 1.20x |

The shorter honeycomb color phases amortize Julia task scheduling less well,
despite needing only two barriers. At eight threads, the triangular serial
fraction is dominated by diagonal update (6.20 ms), site-list construction
(4.02 ms), and measurement (1.37 ms), compared with 2.45 ms for the color
kernel. Parallelizing the first two passes is therefore the next performance
target.

![Strong scaling](data/processed/tfim-lineupdate-julia-20260730/scaling.png)

## Bond-shift scan

The shift `epsilon` trades segment acceptance against operator-string length.
The converged `m2` ESS/s scan selects `epsilon=0.5` for triangular (2.56 ESS/s)
and `epsilon=1.0` for honeycomb (5.99 ESS/s). Those lattice-specific values
are now the CLI defaults; explicit `epsilon` remains available for controlled
comparisons. The common `epsilon=0.5` used above is retained to keep the
line-vs-loop benchmark matched.

![Bond-shift scan](data/processed/tfim-lineupdate-julia-20260730/epsilon.png)

## Bounded production pilot

The independent run `tfim-lineupdate-julia-fss-pilot-ctau1-20260730` exercised
the complete line-update FSS path at the paper-matched aspect ratio
`c_tau = beta*h/L = 1`. Each lattice used `L=12,24,48`, three fields, and four
independent chains per cell (two random and two ordered starts), with 1,000
thermalization sweeps and 200 bins of 10 sweeps. This produced 7,200 checked
bins per lattice. The observables match the existing Challenge 148 pipeline:
the Dirichlet spacing average of the full-imaginary-time Binder ratio
`Q_spacetime` and the equal-time six-momentum-shell correlation length
`xi/L`.

The pilot is **inconclusive**, not a new critical-field measurement:

| lattice | min independent blocks/chain | max random/ordered drift | central roots |
|---|---:|---:|---|
| triangular | 2 (gate: 8) | 3.71 sigma (gate: 5) | only `xi/L`, L=12/24: 4.7662(142) |
| honeycomb | 2 (gate: 8) | 5.90 sigma (gate: 5) | none |

Every `Q_spacetime` size pair and both `L=24/48` `xi/L` pairs lack a unique
central root in the three-field window. Even the displayed triangular root is
not accepted because its sampling gate fails; it is a diagnostic only. No new
`h_c` values and no triangular/honeycomb ratio are therefore formed. This is
the honest bounded-pilot outcome: the implementation is production-capable,
but this sampling budget is not sufficient for critical finite-size scaling.

![Bounded triangular pilot](data/processed/tfim-lineupdate-julia-fss-pilot-ctau1-20260730/triangular_crossings.png)

![Bounded honeycomb pilot](data/processed/tfim-lineupdate-julia-fss-pilot-ctau1-20260730/honeycomb_crossings.png)

## Reproduction

From this directory:

```bash
julia -t 4 benchmarks/test_line_smoke.jl
julia -t 4 benchmarks/bench_updates.jl validate data/processed/tfim-lineupdate-julia-20260730
julia -t 1 benchmarks/bench_updates.jl efficiency data/processed/tfim-lineupdate-julia-20260730
julia -t 8 benchmarks/bench_updates.jl scaling data/processed/tfim-lineupdate-julia-20260730
julia -t 1 benchmarks/bench_updates.jl epsilon data/processed/tfim-lineupdate-julia-20260730
TFIM_EPSILON_LATTICE=honeycomb TFIM_EPSILON_SWEEPS=30000 \
  julia -t 1 benchmarks/bench_updates.jl epsilon data/processed/tfim-lineupdate-julia-20260730
uv run --project ../../analysis python benchmarks/plot_update_benchmarks.py \
  data/processed/tfim-lineupdate-julia-20260730

# Dedicated FSS estimator oracle and bounded production pilot
julia --check-bounds=yes benchmarks/test_fss_observables.jl
TFIM_FSS_RUN_ID=tfim-lineupdate-julia-fss-pilot-ctau1-20260730 \
TFIM_FSS_SIZES=12,24,48 TFIM_FSS_FIELDS=4.74,4.76811,4.80 \
TFIM_FSS_C_TAU=1 TFIM_FSS_THERM=1000 TFIM_FSS_BINS=200 \
TFIM_FSS_SWEEPS_PER_BIN=10 TFIM_FSS_REPLICAS=2 TFIM_FSS_LINE_THREADS=8 \
  julia -t 8 benchmarks/run_line_fss.jl triangular \
  data/processed/tfim-lineupdate-julia-fss-pilot-ctau1-20260730
uv run --project ../../analysis python benchmarks/analyze_line_fss.py \
  data/processed/tfim-lineupdate-julia-fss-pilot-ctau1-20260730/triangular_bins.csv \
  --bootstrap 2000 --seed 20260730
```

The data directory contains the raw per-sweep efficiency series, summary
CSVs, commands, Julia/thread/host metadata, fixed seeds, source commit, and
`SHA256SUMS`. Measurements were made with Julia 1.12.6 on an AMD Ryzen 7
6800H. No 16-thread result or accepted new critical-field fit was produced.
The bounded production grid was run separately as documented above and failed
its declared sampling/crossing gates.

The merge--unmerge loop update remains a separate second innovation axis:
unlike cluster updates, it supports nonzero longitudinal field `B`. This
benchmark used `B=0`, so that capability was not exercised here.
