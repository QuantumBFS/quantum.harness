---
name: using-itensors
description: Use when choosing or running ITensors.jl or ITensorMPS.jl for DMRG, TEBD, MPS calculations, tensor-network checks, or ITensors setup failures.
---

# ITensors

Use ITensors / ITensorMPS for the harness's canonical 1D and quasi-1D tensor-network workflows.

## Sources

- Stack contract: `skills/using-itensors/stack.toml`
- Method card: `.knowledge/methods/mps-based-algorithm.md`
- Install target: `make install itensors`
- Smoke test: `julia --project=julia-env -e 'using ITensors, ITensorMPS, KrylovKit, MPSKit'`

## Workflow

1. Consult `stack.toml` before setup and run `/setup-julia` first when Julia is not usable.
2. Pin lattice, boundary, conserved quantum numbers, bond dimension, sweeps, cutoff, initialization, and convergence observable.
3. Record energy, variance or residual proxy, discarded weight, and bond-dimension convergence.
4. Use cluster execution when bond dimension, cylinder width, or scans exceed the local threshold.

## Parameter setup

Use this section as the source for ITensors / MPS-specific reproduction knobs unless the paper or official code fixes a value. The method card supplies the starting values; this skill decides which knobs must be exposed.

- System/operator: site type (`S=1/2`, `Electron`, etc.), length/width, boundary, conserved quantum numbers, MPO convention, long-range terms, and whether PBC forces a larger bond dimension.
- Algorithm: DMRG for ground states; imaginary-time TEBD when the paper uses a preparation/evolution route; real-time TEBD only when the target is dynamics.
- Accuracy: `maxdim`/bond-dimension schedule, sweep count, cutoff, noise schedule if needed, TEBD time step and total time, and Krylov/Trotter settings.
- Initialization: paper-stated state, product state in the target sector, random MPS, warm start, and seed policy.
- Measurements: observable, normalization, correlation range, measurement cadence, and whether edge effects require a bulk window.
- Validation: energy convergence vs sweep and `chi`, variance/residual proxy, discarded weight, `tau` extrapolation for TEBD, and small-size ED check when feasible.

## Time estimate

Estimate from length `L`, local dimension `d`, bond dimension `chi`, number of sweeps or time steps, and whether symmetries are used.

- DMRG wall time scales roughly as `sweeps * L * chi^3` times the local MPO/site factor; memory scales roughly as `L * chi^2` tensors, with a factor for dtype and conserved-sector overhead.
- TEBD wall time scales as `time_steps * gates * chi^3`; memory follows the same MPS `L * chi^2` pattern.
- First-run Julia precompilation is setup time, not physics time; report it separately when estimating.
- For uncertain cases, a tiny probe may time a few low-`chi` sweeps or TEBD steps, then extrapolate to the paper `chi` and the largest local-PC-in-15-min setting.
