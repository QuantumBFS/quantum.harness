---
name: using-tensorcircuit-ng
description: Use when choosing or running TensorCircuit-NG for quantum-circuit simulation, differentiable circuits, VQE, JAX backend setup, or TensorCircuit-NG setup failures.
---

# TensorCircuit-NG

Use TensorCircuit-NG for JAX-backed circuit simulation, differentiable circuit workflows, and quantum-circuit-simulation track reproductions.

## Sources

- Stack contract: `skills/using-tensorcircuit-ng/stack.toml`
- JAX prerequisite: `skills/using-jax/stack.toml`
- Method card: `.knowledge/methods/quantum-circuit-simulation.md`
- QCS interview notes: `docs/qcs/interview.html`
- QCS review notes: `docs/qcs/review.html`
- QCS challenge brief: `docs/qcs/backup.md`
- Install target: `make install tensorcircuit-ng`

## Workflow

1. Install and smoke-test JAX first; TensorCircuit-NG depends on the selected JAX backend.
2. Choose CPU or GPU based on the actual run size and cluster availability, then smoke-test in that environment.
3. Pin backend, dtype/precision, circuit depth, batch size, random seeds, and observable before compute.
4. For differentiable runs, record optimizer, gradient path, and JIT/compilation expectations.

## Parameter setup

Use this section as the source for TensorCircuit-NG-specific reproduction knobs unless the paper or official code fixes a value. QCS setup starts with representation and stack, then tunes settings inside that choice.

- Representation: tensor-network contraction, full statevector, or MPS. Pick contraction for large/deep differentiable VQE when the largest intermediate tensor fits; statevector for small/full-state/noise/sampling; MPS for 1D low-entanglement circuits after `chi` convergence.
- Backend/runtime: usually JAX for compiled speed, automatic differentiation, and batching; NumPy is debugging only. Use `/using-jax` for device, dtype, and compile setup.
- Precision: default complex64 for performance scans; complex128 when the observable, gradient, or baseline accuracy demands it.
- Circuit/task: qubit count, geometry, gate set, depth/layers, parameter shape, initialization, seed policy, and whether the target is expectation, gradient/VQE, sampling, or training.
- Observable form: Pauli-term loop, batched Pauli structure, sparse matrix, dense matrix only for small cases, or MPO-like form for short-range Hamiltonians.
- Differentiation/compilation: reverse-mode AD for simulation; parameter-shift only to mimic hardware. JIT the value-and-gradient step for benchmark timing; use `scan` for deep repeated layers and checkpointing when backward memory is tight.
- Contraction/memory: greedy for smoke/moderate circuits; cotengra when contraction cost matters. Record path-search budget, objective (`flops`, `write`, `size`, or blend), largest intermediate, slicing target, and whether distributed contraction is data-parallel or model-parallel.
- Optimizer/runtime loop: Adam/SGD for large noisy objectives, L-BFGS for smooth tensor-network objectives, SciPy optimizers for small special cases, gradient-free only when gradients are unavailable.
- Validation: small-system exact check, Pauli/sparse/MPO agreement, energy not below exact ground state, AD vs finite-difference spot check, MPS `chi` convergence when used, and matched baseline for speed claims.

## Time estimate

Estimate from representation, qubit count, depth/gate count, observable form, batch size, gradient path, contraction path, and device.

- Statevector: memory is `2^n` complex amplitudes times dtype, multiplied by batches/gradients. `docs/qcs/review.html` gives an 80 GB GPU anchor of about 33 complex64 qubits.
- Tensor-network contraction: memory is the largest intermediate tensor from contraction info, not qubit count alone; wall is contraction FLOPs plus path search and compile time.
- MPS: memory/time depend on bond dimension `chi`; the run is approximate unless `chi` convergence is shown.
- Timing must separate one-off path search, JAX compile, warm value-and-gradient runtime, and optimizer-loop overhead. The QCS benchmark anchor is 32 qubits x 16 layers with one warm energy+gradient evaluation on a single H200 GPU; `docs/qcs/backup.md` gives a CPU baseline target of 24 qubits x 12 layers.
- First estimate paper-size qubits/depth and the largest local-PC-in-15-min circuit. If memory is infeasible, use slicing, GPU/cluster, MPS approximation, or reduced scope as explicit options.

## Common Setup Notes

- Long first-run latency can be JAX compilation, not stalled physics.
- GPU availability must be checked with `jax.devices()` inside the runtime allocation.
- Do not substitute another circuit package without recording it as a protocol deviation.
