# Quantum Monte Carlo

Stochastic sampling of the finite-temperature partition function. The harness
default is stochastic series expansion (SSE) QMC for sign-problem-free spin and
bosonic lattice Hamiltonians. Determinant / auxiliary-field QMC is a separate
method family and is not covered by this card.

## Setup

Canonical stack: `sse` (`tools/software/stacks/sse.toml`).

```
make install julia
make install sse
```

Activate the environment with `julia --project=julia-env`.

Remote route: use `/setup-julia`, then the `sse:cpu` profile for single-process
runs or `sse:cpu_mpi` inside a compute allocation for MPI runs. Cluster modules,
partitions, and `mpirun`/`srun` details belong in `tools/cluster/<profile>.md`,
not in this method card.

Official install and usage docs:

- StochasticSeriesExpansion.jl: https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/
- SSE tutorial: https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/tutorial.html
- Carlo.jl: https://lukas.weber.science/Carlo.jl/dev/

## Scope

Use this card for:

- Sign-problem-free quantum spin models in a fixed computational basis.
- Finite-temperature observables such as susceptibility, magnetization,
  structure factor, stiffness, energy, and Binder ratios.
- Ground-state estimates by taking beta large enough and checking beta
  convergence.
- Large-size checks where ED is impossible and DMRG geometry would bias a 2D
  result.

Do not use this card for:

- Frustrated or fermionic models with an uncontrolled sign problem.
- Real-time dynamics.
- Generic determinant QMC, AFQMC, or continuous-time impurity QMC.

## Onboarding Reproduction Target

Default visual target: reproduce the StochasticSeriesExpansion.jl tutorial's
magnetic-susceptibility curve. The package tutorial cites the BaNi2V2O8
calculation and produces `MagChi` versus temperature, grouped by system size.
This is the cleanest install-to-figure route because it exercises the canonical
software, Carlo job output, postprocessing, and a visible finite-size trend.

For a Heisenberg-model benchmark target, run square-lattice S=1/2 Heisenberg
SSE and compare thermodynamic extrapolations against
`.knowledge/benchmark-numbers.md`. Treat that as a benchmark comparison,
not a paper reproduction, unless the primary paper has been ingested.

## Notation

- `beta = 1 / T`: inverse temperature.
- Sweep: one Monte Carlo update pass through the operator-string state.
- Thermalization: sweeps discarded before measurement.
- Bin size: number of sweeps averaged before one saved statistical bin.
- Autocorrelation time: effective sample correlation scale; sets meaningful
  error bars.
- Sign: average Monte Carlo sign. For this card, it should remain near one; a
  decaying sign means the chosen route is not controlled.

## Code Shape (Julia / StochasticSeriesExpansion.jl + Carlo.jl)

Follow the package tutorial's job-script shape:

```julia
using Carlo
using Carlo.JobTools
using StochasticSeriesExpansion

tm = TaskMaker()
tm.sweeps = 80000
tm.thermalization = 10000
tm.binsize = 100

tm.model = MagnetModel
tm.S = 1
tm.J = 1
tm.measure = [:magnetization]

for L in [10, 20]
    tm.lattice = (unitcell = UnitCells.honeycomb, size = (L, L))
    for T in range(0.05, 4.0, 20)
        tm.T = T
        task(tm)
    end
end

job = JobInfo(
    splitext(@__FILE__)[1],
    StochasticSeriesExpansion.MC;
    run_time = "24:00:00",
    checkpoint_time = "30:00",
    tasks = make_tasks(tm),
)

start(job, ARGS)
```

Run locally with:

```
julia --project=julia-env scripts/<job>.jl run
```

Run under MPI only inside the selected remote allocation:

```
mpirun -n <ranks> julia --project=julia-env scripts/<job>.jl run
```

Read the resulting `<job>.results.json` with `Carlo.ResultTools.dataframe`.
Plot the primary observable versus the physical scan axis, with one curve per
system size or beta.

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| `sweeps` | Statistical precision after thermalization. | 1e4 for smoke; 8e4+ for tutorial-scale curves. |
| `thermalization` | Removes initial-state bias. | 10% to 20% of sweeps; increase near criticality. |
| `binsize` | Controls saved bin granularity. | Small compared with sweeps; larger than short autocorrelation scales. |
| `T` / `beta` | Physical temperature or ground-state projection. | Scan temperature for curves; for ground state increase beta until stable. |
| `L` | System size. | At least three sizes for scaling claims. |
| `measure` | Observable set. | `[:magnetization]` for susceptibility and Binder diagnostics. |
| MPI ranks | Independent task throughput. | Use only when Carlo task count is large enough to keep ranks busy. |

## Pitfalls

- **Sign problem**: if the average sign collapses, the result is not a
  controlled QMC estimate. Change basis/model route or use another method.
- **Under-thermalized runs**: early bins can bias means. Compare statistics with
  longer thermalization or dropped initial bins.
- **Autocorrelation near criticality**: naive standard errors can be too small.
  Increase bin size and sweeps; report binning/autocorrelation checks.
- **Beta not large enough**: ground-state claims require a beta sweep, not a
  single low-temperature run.
- **Finite-size confusion**: a visible curve is not a thermodynamic result.
  Separate finite-size trend plots from extrapolated values.
- **Restart semantics**: Carlo checkpoint data is persistent. Use the package
  restart/delete commands deliberately, and record whether a run continued or
  restarted.

## Verification

- **Install smoke**: run the `sse` stack smoke command from
  `tools/software/stacks/sse.toml`.
- **Sign check**: report the average sign when available; sign-free targets
  should not show a decaying sign.
- **Thermalization and binning**: compare means after dropping early bins and
  after changing `binsize`.
- **Beta convergence**: for ground-state observables, increase beta until the
  observable is stable within error bars.
- **Finite-size scaling**: use multiple `L`; never infer thermodynamic behavior
  from one size.
- **Small-system cross-check**: compare against ED for the same Hamiltonian,
  boundary condition, and temperature/sector when feasible.
- **Benchmark comparison**: for square-lattice Heisenberg quantities, compare
  to the tagged values in `.knowledge/benchmark-numbers.md`.

## Citations

- `.knowledge/literature/quantum-monte-carlo/1101.3281_computational-studies-of-quantum-spin-systems.md`
  - Sandvik, *Computational Studies of Quantum Spin Systems* (2010).
- `.knowledge/literature/quantum-monte-carlo/10-1017-9781316417041.md`
  - Becca and Sorella, *Quantum Monte Carlo Approaches for Correlated Systems*
    (2017).
- StochasticSeriesExpansion.jl documentation:
  https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/
- Carlo.jl documentation: https://lukas.weber.science/Carlo.jl/dev/
