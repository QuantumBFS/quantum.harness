---
name: using-sse
description: Use when choosing or running StochasticSeriesExpansion.jl or Carlo.jl for sign-free QMC/SSE workflows, MPI setup, or SSE setup failures.
---

# SSE

Use StochasticSeriesExpansion.jl with Carlo.jl for sign-problem-free stochastic-series-expansion QMC workflows.

## Sources

- Stack contract: `skills/using-sse/stack.toml`
- Method card: `.knowledge/methods/quantum-monte-carlo.md`
- Install target: `make install sse`
- Smoke test: `julia --project=julia-env -e 'using Carlo, StochasticSeriesExpansion'`

## Workflow

1. Confirm the model is sign-problem-free for the chosen lattice, coupling signs, and basis.
2. Consult `stack.toml` for CPU vs MPI smoke tests and compose with `/using-slurm` for scheduled runs.
3. Pin thermalization, samples, chains, bins, update type, estimator, seed policy, and target uncertainty.
4. Report autocorrelation/binning diagnostics with the measured observable.

## Parameter setup

Use this section as the source for SSE/QMC-specific reproduction knobs unless the paper or official code fixes a value. The method card supplies the SSE/Carlo job shape; this skill exposes the stochastic controls and sign-problem gate.

- Validity: sign-problem-free basis, lattice, coupling signs, temperature/inverse temperature `beta`, and boundary condition. Stop or reroute if the sign is uncontrolled.
- Markov chain: update type, thermalization sweeps, measurement sweeps, sweep definition, chains/replicas, seed policy, and checkpoint cadence.
- Estimator: measured observable, normalization, improved estimator if used, bin size, autocorrelation handling, and target uncertainty.
- Runtime profile: serial CPU vs MPI, process count, allocation, and whether the run is a parameter scan.
- Validation: acceptance/update diagnostics, binning stability, autocorrelation time, independent chains, and comparison to exact or known-limit values when feasible.

## Time estimate

Estimate from `thermalization_sweeps + measurement_sweeps`, cost per sweep, number of chains, and autocorrelation time.

- Per-sweep cost scales with lattice size, operator-string length, and update type; low temperature usually increases the operator string and autocorrelation.
- Effective independent samples are fewer than raw samples when autocorrelation is large; include the binning/autocorrelation penalty in the estimate.
- MPI reduces wall time only when chains or parameter points parallelize cleanly; use `stack.toml` for the MPI smoke test and `/using-slurm` for scheduled runs.
- For uncertain cases, time a short non-production chain to estimate sweep rate and autocorrelation proxy, then show paper-size and local-PC-in-15-min estimates before asking scale.
