---
name: method-qmc
description: Use when a quantum Monte Carlo, QMC, stochastic series expansion, SSE, finite-temperature, sign-problem, or statistical-bin reproduction needs method-level route and tool selection.
---

# Method QMC

QMC is the stochastic sampling track. Use it to decide whether the target is sign-problem-free SSE and whether stochastic error bars can reproduce the requested figure.

## Sources

- Track README: `tracks/qmc/README.md`
- Tool skills: `/using-sse`, `/using-cpmc-lab`

## Route

1. Check sign-problem control first: lattice, coupling signs, basis, and observable must be compatible with the selected QMC route.
2. Use SSE for sign-free spin/bosonic lattice targets, finite-temperature curves, beta convergence, and large-size statistical checks.
3. Recommend `/using-sse` for StochasticSeriesExpansion.jl / Carlo.jl setup, stochastic parameters, MPI choice, and timing.
4. Recommend `/using-cpmc-lab` when a constrained-path Monte Carlo / phaseless AFQMC route needs the official CPMC-Lab package as the software backend.
5. If the target is determinant QMC, impurity CTQMC, or has an uncontrolled sign problem outside a supported package route, do not force `/using-sse`; offer official code / web search or another track.

## Tool Handoff

Invoke `/using-sse` after an SSE route is chosen. `/using-sse` owns thermalization, sweeps, chains, bins, beta/temperature grid, autocorrelation checks, sign checks, MPI setup, and time estimate.

Invoke `/using-cpmc-lab` after a CPMC/AFQMC package route is chosen. `/using-cpmc-lab` owns the package mechanics: MATLAB setup, official package installation, batch invocation, `.mat` outputs, and package-level time probing. The scientific run parameters are caller-supplied (from the model and reproduction protocol), not set by this card.

## Details

Stochastic sampling of the finite-temperature partition function. The harness
default is stochastic series expansion (SSE) QMC for sign-problem-free spin and
bosonic lattice Hamiltonians. Constrained-path and phaseless auxiliary-field QMC
(AFQMC) is also supported, but only through the official CPMC-Lab package route
via `/using-cpmc-lab`; generic unconstrained determinant / auxiliary-field QMC is a
separate method family and is not covered by this card.

### Scope

Use this card for:

- Sign-problem-free quantum spin models in a fixed computational basis.
- Finite-temperature observables such as susceptibility, magnetization,
  structure factor, stiffness, energy, and Binder ratios.
- Ground-state estimates by taking beta large enough and checking beta
  convergence.
- Large-size checks where ED is impossible and DMRG geometry would bias a 2D
  result.
- Constrained-path / phaseless AFQMC ground states of fermionic lattice
  models, through the CPMC-Lab package route (`/using-cpmc-lab`).

Do not use this card for:

- Frustrated or fermionic models with an uncontrolled sign problem.
- Real-time dynamics.
- Generic unconstrained determinant QMC or continuous-time impurity QMC.

### Onboarding Reproduction Target

Default visual target: reproduce the StochasticSeriesExpansion.jl tutorial's
magnetic-susceptibility curve. The package tutorial cites the BaNi2V2O8
calculation and produces `MagChi` versus temperature, grouped by system size.
This is the cleanest install-to-figure route because it exercises the canonical
software, Carlo job output, postprocessing, and a visible finite-size trend.

For a Heisenberg-model benchmark target, run square-lattice S=1/2 Heisenberg
SSE and compare thermodynamic extrapolations against
`.knowledge/benchmark-numbers.md`. Treat that as a benchmark comparison,
not a paper reproduction, unless the primary paper has been ingested.

### Notation

- `beta = 1 / T`: inverse temperature.
- Sweep: one Monte Carlo update pass through the operator-string state.
- Thermalization: sweeps discarded before measurement.
- Bin size: number of sweeps averaged before one saved statistical bin.
- Autocorrelation time: effective sample correlation scale; sets meaningful
  error bars.
- Sign: average Monte Carlo sign. For this card, it should remain near one; a
  decaying sign means the chosen route is not controlled.

### Pitfalls

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

### Verification

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

### Citations

- `.knowledge/literature/quantum-monte-carlo/1101.3281_computational-studies-of-quantum-spin-systems.md`
  - Sandvik, *Computational Studies of Quantum Spin Systems* (2010).
- `.knowledge/literature/quantum-monte-carlo/10-1017-9781316417041.md`
  - Becca and Sorella, *Quantum Monte Carlo Approaches for Correlated Systems*
    (2017).
- `.knowledge/literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md`
  - Nguyen, Shi, Xu, and Zhang, *CPMC-Lab: A Matlab Package for Constrained-Path
    Monte Carlo Calculations* (2014).
