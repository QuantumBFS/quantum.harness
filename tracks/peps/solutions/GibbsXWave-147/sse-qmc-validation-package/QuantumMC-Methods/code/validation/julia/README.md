# Julia SSE validation

- Validation level: exact-small passed
- Julia: 1.11
- Primary runtime package: Carlo.jl 0.3.4
- Stage: `SSE_VALIDATION`

This is the source-backed and tested SSE reference implementation included in
the validation package.

## What is implemented

- open square-lattice Pauli TFIM model and bond list;
- independent-spin formulas and classical complete enumeration;
- dense exact diagonalization for \(N\leq10\) by default;
- exact finite open-chain Jordan–Wigner thermodynamics for arbitrary one-dimensional
  \(L\), plus the thermodynamic-limit analytic momentum integrals;
- fixed-length SSE diagonal insertion/removal;
- Sandvik TFIM all-cluster update;
- standard and analytically constant-deflated expansion-order energy and
  heat-capacity estimators;
- transverse-magnetization and bond-correlation count estimators;
- standalone binned-jackknife runner;
- per-sweep raw traces, Geyer initial-monotone autocorrelation estimates,
  effective sample size, nonlinear influence-series MCSE, and blocking curves;
- Carlo.jl adapter for tasks, RNG, binning, jackknife evaluables, MPI
  scheduling, and HDF5 checkpoints.

The physics kernel is implemented here rather than delegated to a high-level
SSE engine. Carlo is the low-level Monte Carlo infrastructure layer.

## Read the code in this order

1. [`src/models.jl`](src/models.jl): Hamiltonian and lattice indexing;
2. [`src/exact.jl`](src/exact.jl): independent reference calculations;
3. [`src/sse.jl`](src/sse.jl): configuration and the two update passes;
4. [`src/analysis.jl`](src/analysis.jl): estimators and jackknife;
5. [`src/carlo_adapter.jl`](src/carlo_adapter.jl): package integration;
6. [`test/runtests.jl`](test/runtests.jl): executable correctness claims.

Keep the model and algorithm notes open while reading:

- [`../../../notes/models/square-lattice-tfim.md`](../../../notes/models/square-lattice-tfim.md)
- [`../../../notes/algorithms/tfim-sse-quantum-cluster.md`](../../../notes/algorithms/tfim-sse-quantum-cluster.md)

## Reproduce the exact-small gate

From the repository root:

```bash
julia --project=code/validation/julia -e 'using Pkg; Pkg.test()'
julia --project=code/validation/julia \
  code/validation/julia/scripts/benchmark_exact_small.jl
julia --project=code/validation/julia \
  code/validation/julia/scripts/plot_exact_small_physics.jl
julia --project=code/validation/julia \
  code/validation/julia/scripts/benchmark_sampling_error.jl
julia --project=code/validation/julia \
  code/validation/julia/scripts/plot_sampling_error_scaling.jl
julia --threads=auto --project=code/validation/julia \
  code/validation/julia/scripts/benchmark_constant_deflated_precision.jl
julia --threads=20 --project=code/validation/julia \
  code/validation/julia/scripts/benchmark_1d_l128_exact.jl
julia --threads=20 --project=code/validation/julia \
  code/validation/julia/scripts/benchmark_xu_peps_metts.jl
julia --threads=20 --project=code/validation/julia \
  code/validation/julia/scripts/extend_xu_peps_metts_precision.jl
julia --project=code/validation/julia \
  code/validation/julia/scripts/plot_xu_peps_metts_benchmark.jl
```

The retained 2026-07-27 result used four seeds, 5,000 warmup sweeps and
100,000 measurement sweeps per seed and passed all 36 comparisons.

The retained 2026-07-28 sampling benchmark used 64 independent replicas at
four measurement lengths. Its error calibration passed, while the declared
heat-capacity precision gate failed; see the report rather than interpreting
the earlier `5 SE` correctness gate as a precision claim.

The separate constant-deflated protocol retained the same precision targets,
combined 64 independent replicas conservatively, and passed. Its final relative
MCSE was `0.2063%` for nominal heat capacity and `0.7374%` for the difficult
low-\(c\) point. This exact-small result does not open the \(4\times4\) or
\(10\times10\) production gate.

The benchmark size can be changed without editing the script:

```bash
QMC_BENCH_WARMUP=1000 \
QMC_BENCH_SWEEPS=20000 \
QMC_BENCH_BIN_SIZE=200 \
julia --project=code/validation/julia \
  code/validation/julia/scripts/benchmark_exact_small.jl
```

## Direct API

```julia
using QuantumMCMethods

model = SquareLatticeTFIM(2, 2; J=1.0, h=2.5)
exact = exact_thermal_observables(model, 0.7)
qmc = run_sse(
    model,
    0.7;
    warmup=10_000,
    sweeps=200_000,
    bin_size=1_000,
    seed=20260727,
)

println(exact.u)
println(qmc.energy)
```

For the one-dimensional exact references:

```julia
chain = SquareLatticeTFIM(128, 1; J=1.0, h=1.0)
finite = exact_open_chain_observables(chain, 2.0)
infinite = exact_infinite_chain_observables(1.0, 1.0, 2.0)
```

## Carlo job interface

The development job defaults to a \(4\times4\) lattice and a small
field/temperature grid:

```bash
julia --project=code/validation/julia \
  code/validation/julia/scripts/tfim_sse_job.jl --help
julia --project=code/validation/julia \
  code/validation/julia/scripts/tfim_sse_job.jl run
julia --project=code/validation/julia \
  code/validation/julia/scripts/tfim_sse_job.jl status
julia --project=code/validation/julia \
  code/validation/julia/scripts/tfim_sse_job.jl merge
```

Environment variables such as `QMC_LX`, `QMC_H_VALUES`,
`QMC_BETA_VALUES`, `QMC_SWEEPS`, `QMC_THERMALIZATION`, and
`QMC_BINSIZE` configure the job. Do not launch the \(10\times10\)
challenge grid until the next validation gate is reviewed.

## Not yet promoted

- thermodynamic integration for free energy;
- an automatic production stopping rule based on the new autocorrelation and
  blocking diagnostics;
- a reviewed \(4\times4\) reference strategy;
- the \(10\times10\) challenge run;
- a successful comparison with an independent second SSE implementation.
