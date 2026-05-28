---
name: using-sse
description: Use when choosing or running StochasticSeriesExpansion.jl or Carlo.jl for sign-free QMC/SSE workflows, MPI setup, or SSE setup failures.
---

# SSE

Use StochasticSeriesExpansion.jl with Carlo.jl for sign-problem-free stochastic-series-expansion QMC workflows.

## Sources

- Stack contract: `skills/using-sse/stack.toml`
- Method card: `skills/method-qmc/SKILL.md`
- Install target: `make install sse`
- Smoke test: `julia --project=julia-env -e 'using Carlo, StochasticSeriesExpansion'`
- Docs: StochasticSeriesExpansion.jl <https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/>; tutorial <https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/tutorial.html>; Carlo.jl <https://lukas.weber.science/Carlo.jl/dev/>

## Workflow

1. Confirm the model is sign-problem-free for the chosen lattice, coupling signs, and basis.
2. Consult `stack.toml` for CPU vs MPI smoke tests and compose with `/using-slurm` for scheduled runs.
3. Pin thermalization, samples, chains, bins, update type, estimator, seed policy, and target uncertainty.
4. Report autocorrelation/binning diagnostics with the measured observable.

## Parameter setup

Use this section as the source for SSE/QMC-specific reproduction knobs unless the paper or official code fixes a value. This skill holds the SSE/Carlo job shape and exposes the stochastic controls and sign-problem gate.

- Validity: sign-problem-free basis, lattice, coupling signs, temperature/inverse temperature `beta`, and boundary condition. Stop or reroute if the sign is uncontrolled.
- Markov chain: update type, thermalization sweeps, measurement sweeps, sweep definition, chains/replicas, seed policy, and checkpoint cadence.
- Estimator: measured observable, normalization, improved estimator if used, bin size, autocorrelation handling, and target uncertainty.
- Runtime profile: serial CPU vs MPI, process count, allocation, and whether the run is a parameter scan.
- Validation: acceptance/update diagnostics, binning stability, autocorrelation time, independent chains, and comparison to exact or known-limit values when feasible.

## Knobs

Concrete starting points for the stochastic controls in Parameter setup.

| Knob | Effect | Starting point |
|---|---|---|
| `sweeps` | Statistical precision after thermalization. | 1e4 for smoke; 8e4+ for tutorial-scale curves. |
| `thermalization` | Removes initial-state bias. | 10% to 20% of sweeps; increase near criticality. |
| `binsize` | Controls saved bin granularity. | Small compared with sweeps; larger than short autocorrelation scales. |
| `T` / `beta` | Physical temperature or ground-state projection. | Scan temperature for curves; for ground state increase beta until stable. |
| `L` | System size. | At least three sizes for scaling claims. |
| `measure` | Observable set. | `[:magnetization]` for susceptibility and Binder diagnostics. |
| MPI ranks | Independent task throughput. | Use only when Carlo task count is large enough to keep ranks busy. |

## Code shape

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

Run under MPI only inside the selected remote allocation (the `sse:cpu_mpi` profile; use `sse:cpu` for single-process). Cluster modules, partitions, and `mpirun`/`srun` details live in `skills/using-slurm/profiles/<profile>.md`.

```
mpirun -n <ranks> julia --project=julia-env scripts/<job>.jl run
```

Read the resulting `<job>.results.json` with `Carlo.ResultTools.dataframe`. Plot the primary observable versus the physical scan axis, with one curve per system size or beta.

## Time estimate

Estimate from `thermalization_sweeps + measurement_sweeps`, cost per sweep, number of chains, and autocorrelation time.

- Per-sweep cost scales with lattice size, operator-string length, and update type; low temperature usually increases the operator string and autocorrelation.
- Effective independent samples are fewer than raw samples when autocorrelation is large; include the binning/autocorrelation penalty in the estimate.
- MPI reduces wall time only when chains or parameter points parallelize cleanly; use `stack.toml` for the MPI smoke test and `/using-slurm` for scheduled runs.
- For uncertain cases, time a short non-production chain to estimate sweep rate and autocorrelation proxy, then show paper-size and local-PC-in-15-min estimates before asking scale.
