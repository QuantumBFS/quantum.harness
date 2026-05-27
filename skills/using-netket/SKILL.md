---
name: using-netket
description: Use when choosing or running NetKet for VMC, neural quantum states, sampler or optimizer choices, JAX CPU/GPU setup, or NetKet setup failures.
---

# NetKet

Use NetKet for VMC / neural-quantum-state workflows where the task needs a variational ansatz, sampler, optimizer, and statistical validation.

## Sources

- Stack contract: `skills/using-netket/stack.toml`
- Method card: `.knowledge/methods/variational-monte-carlo-neural-quantum-states.md`
- CPU install target: `make install netket`
- GPU install target: `make install netket-gpu`

## Workflow

1. Consult the stack contract and choose CPU, single-node GPU, or multi-node GPU before installing.
2. Smoke-test JAX devices and NetKet import in the same environment where the run will execute.
3. Pin ansatz, sampler, optimizer, learning rate, samples, steps, seeds, and validation observable before compute.
4. Treat energy variance, independent seeds, and exact/small-size comparison as required validation when feasible.

## Parameter setup

Use this section as the source for NetKet-specific reproduction knobs unless the paper or official code fixes a value. The method card supplies the default VMC/NQS knobs; this skill decides the NetKet runtime and validation setup.

- Hilbert and graph: lattice, boundary, local states, constraints, symmetries, and operator convention.
- Ansatz: RBM/CNN/Transformer or paper architecture, hidden ratio/width/depth/features, parameter count, dtype/precision, initialization, and seed policy.
- Sampler: sampler type, chains, samples per iteration, burn-in, sweep size/decorrelation, and acceptance/autocorrelation diagnostics.
- Optimizer: SGD/Adam/SR or paper optimizer, learning-rate schedule, diagonal shift, iteration count, and stopping rule.
- Runtime profile: CPU, single-node GPU, or multi-node GPU; use `/using-jax` and the NetKet stack profile for device setup.
- Validation: energy variance, energy upper-bound sanity check, multiple seeds, small-size ED comparison when feasible, error bars/binning, and observable stability.

## Time estimate

Estimate from `iterations * samples_per_iteration * model_eval_cost`, plus JAX compilation and sampler overhead.

- CPU vs GPU changes the rate; use `stack.toml` to choose the profile, then smoke-test `jax.devices()` in the same environment.
- JAX compilation is a one-time setup/runtime overhead and should be reported separately from steady-state VMC iteration time.
- Memory is dominated by model parameters, sampler state, per-device batch size, and optimizer/SR state; SR can dominate memory for large parameter counts.
- For paper-size estimates, time a few warmup iterations after compilation or use an existing measured rate; then estimate the largest local-PC-in-15-min run without recommending a scale.

## Common Setup Notes

- GPU smoke tests belong inside a compute allocation, not on a login node.
- Multi-node GPU needs MPI/JAX distributed setup; compose with `/using-slurm`.
- Do not silently fall back from GPU to CPU; report the setup failure and ask.
