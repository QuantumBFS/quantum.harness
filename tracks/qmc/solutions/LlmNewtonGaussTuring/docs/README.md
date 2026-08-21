# TFIM √5 Conjecture (Challenge 148)

**Current objective**: compare C++17 cluster, merge--unmerge loop, and true
local worldline-segment line updates on the same TFIM SSE state,
Hamiltonian, diagonal update, and estimators. The original √5 critical-ratio
question is retained as scientific context, not as the current deliverable.

**Current result**: all three updates are available in C++17 without
third-party libraries. The first same-language performance pilot finds that
line has the lowest sweep cost, while cluster can retain higher ESS/s for slow
magnetic observables. Its 1,000-sweep chains are deliberately reported as a
pilot; they are not a precision estimate or a √5 test. See `REPORT.md` for
limits and data paths.

## Contents
- `REPORT.md` — C++ cluster/loop/line performance results and historical Julia context
- `docs/PLAN.md` — **current master plan**: C++ update-algorithm benchmark track
- `docs/三角晶格TFIM_loop算法note.md` — loop-algorithm note + ED benchmark (Chinese)
- `src/TIM_lattice_QMC.jl` — SSE **loop** (merge–unmerge) QMC for triangular/honeycomb TFIM (Julia)
- `src/TIM_lattice_line.jl` — SSE **line** update (worldline-segment flip), serial + color-parallel (Julia)
- `src/lattice_coloring.jl` — proper vertex coloring: honeycomb 2-color, triangular 3-color ((x+2y) mod 3, needs Lx,Ly ≡ 0 mod 3), greedy fallback
- `src/TIM_lattice_ED.jl` — exact diagonalization cross-checks
- `cpp/` — dependency-free C++17 cluster, loop, and segment-line SSE kernels
- `cpp/src/benchmark_updates.cpp` — matched-kernel autocorrelation and ESS/s benchmark
- `benchmarks/test_line_smoke.jl` — line-update smoke suite (coloring, J=0 analytic limit, worldline consistency, parallel run)
- `benchmarks/test_fss_observables.jl` — deterministic FSS estimator oracle (momentum shell, closure, Dirichlet moments, direct propagation)
- `benchmarks/bench_updates.jl` — ED validation, Sokal autocorrelation/ESS, scaling, and epsilon profiles
- `benchmarks/run_line_fss.jl`, `analyze_line_fss.py` — independent bounded production pilot and blocked analysis
- `benchmarks/plot_update_benchmarks.py` — figures from the processed benchmark CSVs
- `data/processed/` — provenance-preserving benchmark and bounded-pilot outputs

## Quick start
```bash
julia src/TIM_lattice_QMC.jl triangular 8 8 -1.0 4.76 0.0 16.0 10000 40000 12345 6.0
julia src/TIM_lattice_ED.jl honeycomb 3 2 -1.0 2.1325 0.0 20.0 20.0 1.0

# line update: same CLI plus [Gamma_start] [nthreads] [epsilon]; needs julia -t for nthreads > 1
julia -t 8 src/TIM_lattice_line.jl triangular 12 12 -1.0 4.768 0.0 24.0 5000 20000 1 0.0 8
julia -t 4 benchmarks/test_line_smoke.jl

# reproducible benchmark profiles and plots
julia -t 1 benchmarks/bench_updates.jl efficiency
julia -t 8 benchmarks/bench_updates.jl scaling
uv run --project ../../analysis python benchmarks/plot_update_benchmarks.py \
  data/processed/tfim-lineupdate-julia-20260730

# dedicated FSS estimator checks; pilot results and exact commands are in REPORT.md
julia --check-bounds=yes benchmarks/test_fss_observables.jl

# C++17 matched-kernel pilot (cluster, loop, and true segment line update)
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
./build/tfim_update_benchmark /tmp/tfim-loop-line.csv 1 100 1000
./build/tfim_ed_validation /tmp/tfim-ed-validation.csv
```

Sign convention: this repository simulates `H = J Σ σz σz − B Σ σz − Γ Σ σx`;
the challenge ferromagnet (J'=1, field h) is `J = −1, Γ = h` here. On the
non-bipartite triangular lattice this sign distinguishes the FM problem from
the frustrated AFM — see `docs/PLAN.md` §2 before running anything.

## Julia reference implementation

`src/TIM_lattice_line.jl` implements the thesis-lineage line update on top of
the same `Sim` state, diagonal update, and estimators as the loop code: each
site's worldline is cut into segments by its single-site operators; a segment
flip toggles one leg of every bond operator it crosses and converts the two
delimiting operators between constant and off-diagonal. Acceptance uses the
heat-bath rule R/(1+R) — plain Metropolis is non-ergodic here because empty
segments (R = 1) would flip deterministically; the J=0 smoke gate catches
this. Because a segment flip touches only site-local state and incident bond
legs, sites of one color class update concurrently (honeycomb: 2 colors,
triangular: 3), giving a parallel Monte Carlo update unavailable to cluster
algorithms. Architecture, validation ladder, and benchmark plan: `docs/PLAN.md`.
The measured benchmark and production recommendations are in `REPORT.md`;
the default bond shift is `epsilon=0.5` on triangular and `1.0` on honeycomb.

## C++17 update comparison

The C++ implementation contains cluster, merge--unmerge loop, and true
segment-flip line updates. They share compact operator storage, the
diagonal update, the lattice builder, and all estimators, so their serial
wall-time and autocorrelation measurements are algorithm comparisons rather
than Julia-versus-C++ comparisons. It supports triangular, honeycomb, and
square periodic lattices. The Hamiltonian convention remains
`H = J sum sigma_z sigma_z - B sum sigma_z - Gamma sum sigma_x`; use `J=-1`
for the ferromagnet.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure

./build/tfim_lineupdate triangular 8 8 -1.0 4.768 0.0 16.0 \
  10000 40000 12345 0.0 50 line
./build/tfim_update_benchmark /tmp/tfim-loop-line.csv 1 100 1000
./build/tfim_ed_validation /tmp/tfim-ed-validation.csv
```

The ten stdout columns are identical to the Julia CLI. The final optional
argument selects `cluster`, `loop` (default), or `line`:
`E,E_err,mx,mx_err,m2,m2_err,m4,m4_err,U,U_err`. Timing and update counters go
to stderr. A warmed-Julia comparison with source hashes and environment metadata
can be run with:

```bash
uv run --no-project python benchmarks/benchmark_lineupdate.py \
  --lattice triangular --sizes 4,8,12 --gamma 4.768 \
  --output /path/to/lineupdate_benchmark.csv [--run-spec /path/to/run_spec.json]
```

The long-chain finite-temperature ED check used for correctness is reproducible
with:

```bash
uv run --no-project python benchmarks/validate_lineupdate.py \
  --output /path/to/correctness.json
```

### Measured serial performance

On an AMD Ryzen 7 6800H, a Release build was compared with warmed Julia 1.12.6
at `L=4,8,12`, `beta=2L`, with 100 thermalization and 300 measurement sweeps.
Each table entry is the median of three independent seeds; constructor time is
included for both implementations and Julia JIT compilation is excluded.

| lattice | L | sites | C++ (s) | Julia (s) | speedup |
|---|---:|---:|---:|---:|---:|
| triangular | 4 | 16 | 0.0862 | 0.1020 | 1.18x |
| triangular | 8 | 64 | 0.7052 | 0.9413 | 1.33x |
| triangular | 12 | 144 | 2.6148 | 4.2135 | 1.61x |
| honeycomb | 4 | 32 | 0.0813 | 0.0935 | 1.15x |
| honeycomb | 8 | 128 | 0.6598 | 0.8575 | 1.30x |
| honeycomb | 12 | 288 | 2.4042 | 3.5719 | 1.49x |

Thus the C++ port reduced measured serial wall time by about 13--38% over the
tested range, with a monotonically increasing speedup versus `L` on both
lattices. This is a per-sweep wall-time comparison, not yet an autocorrelation
or effective-samples-per-second comparison. Full commands, hashes, validation
evidence, and limitations are recorded in
`../../data/processed/tfim-lineupdate-cpp/STAGE_REPORT.md`.
