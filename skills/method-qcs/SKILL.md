---
name: method-qcs
description: Use when a quantum circuit simulation, VQE, TensorCircuit-NG, JAX backend, contraction path, statevector, MPS circuit, gradient, or circuit-performance reproduction needs method-level route and tool selection.
---

# Method QCS

Quantum circuit simulation is the differentiable-circuit and performance track. Use it to choose representation and software stack before tuning backend settings.

## Sources

- Track README: `tracks/qcs/README.md`
- Interview notes: `docs/qcs/interview.html`
- Review notes: `docs/qcs/review.html`
- Challenge brief: `docs/qcs/backup.md`
- Tool skills: `/using-tensorcircuit-ng`, `/using-jax`

## Route

1. Choose representation first: tensor-network contraction, full statevector, or MPS circuit. This determines memory and whether the result is exact or approximate.
2. Recommend `/using-tensorcircuit-ng` for large/deep differentiable VQE, energy+gradient profiling, contraction tuning, batching, scan/checkpointing, and the QCS track benchmark.
3. Invoke `/using-jax` for backend, CPU/GPU, precision, device, and compile/warm-runtime setup.
4. If the paper requires Qiskit, PennyLane, Yao, cuQuantum, or quimb specifically, offer official code / web search or a new tool skill instead of silently forcing TensorCircuit-NG.
5. Keep compile time, path-search time, warm runtime, and optimizer-loop time separate in any proposal or report.

## Tool Handoff

Invoke `/using-tensorcircuit-ng` after the route is chosen. `/using-tensorcircuit-ng` owns representation-specific parameters, contraction/path settings, observable format, gradients, validation, and time estimate. Invoke `/using-jax` for backend setup.

## Details

Classical simulation of quantum circuits, including variational circuit optimization (VQE) and general circuit contraction. In this harness, the default route uses TensorCircuit-NG on a JAX backend with automatic differentiation, JIT compilation, and tensor-network contraction controls. It is not a hardware-execution workflow.

This card is generic methodology. Paper-specific benchmarks, hardware layouts, and figure protocols belong in `/reproduce-paper` protocols or run specs, not here.

### Scope

Use this card for:

- Parameterized circuit ansatz construction.
- Hamiltonian expectation values from dense, sparse, Pauli-sum, or MPO-like representations.
- Reverse-mode gradients through circuit contractions.
- JIT-compiled value-and-gradient kernels.
- Runtime, compile-time, and peak-memory profiling of differentiable VQE steps.
- Contraction-path, slicing, batching, scan, checkpointing, and precision studies.

Do not use this card for:

- Hardware execution, cloud submission, readout mitigation, or QPU calibration.
- QAOA or generic quantum algorithms unless they are treated as VQE-like variational energy minimization.
- TensorCircuit-NG paper-specific benchmark reproduction.
- General quantum-circuit simulation without a variational energy / differentiable objective.

### Notation

- `theta`: variational parameters.
- Ansatz: parameterized circuit preparing `|psi(theta)>`.
- `H`: Hamiltonian represented as Pauli terms, sparse matrix, dense matrix, or tensor-network operator.
- Forward pass: compute `E(theta)`.
- Backward pass: compute `grad_theta E(theta)` by reverse-mode AD.
- JIT compile time: first traced/compiled execution cost.
- Steady runtime: execution time after compilation/cache warmup.
- Peak memory: maximum device or host memory during forward/backward execution.
- Contractor: tensor-network contraction path and execution strategy.

### Pitfalls

- **Dense Hamiltonian blowup**: prefer sparse, Pauli-sum, or MPO-like representations when a dense matrix would dominate memory. The representation choice is part of the method, not only a runtime tweak.

### Verification

- **Small-system ED check**: compare VQE energy to ED for the same Hamiltonian and boundary condition.
- **Gradient check**: finite-difference a small parameter subset and compare with AD gradients.
- **Energy bound**: VQE energy should not fall below the exact ground-state energy for a Hermitian Hamiltonian.
- **Seed/depth stability**: run multiple seeds and a depth sweep before claiming ansatz convergence.

### Citations

- `.knowledge/literature/quantum-circuit-simulation/tensorcircuit-tensorcircuit-ng.md` - official TensorCircuit-NG repository and documentation entry.
- `.knowledge/literature/quantum-circuit-simulation/2602.14167_tensorcircuit-ng-a-universal-composable-and-scalable-platfor.md` - TensorCircuit-NG software reference.
- `.knowledge/literature/quantum-circuit-simulation/2205.10091_tensorcircuit-a-quantum-software-framework-for-the-nisq-era.md` - TensorCircuit software and differentiable-circuit reference.
- `.knowledge/literature/quantum-circuit-simulation/2002.01935_hyper-optimized-tensor-network-contraction.md` - cotengra contraction-path reference.
