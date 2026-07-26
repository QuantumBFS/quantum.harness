---
name: method-qcs
description: Use when a quantum circuit simulation, VQE, TensorCircuit-NG, JAX backend, contraction path, statevector, MPS circuit, gradient, or circuit-performance reproduction needs method-level route and tool selection.
---

# Method QCS

Quantum circuit simulation is the differentiable-circuit and performance track. This card owns method selection (step 1: which representation), software routing (step 2), and method-level setup (step 3, method side). Package parameter *values* live in `/using-tensorcircuit-ng` and `/using-jax`.

## Sources

- **Methodology reference** (reproduction-grade algorithm, parameters, validation, gap analysis): `references/qcs-methodology.md`
- **Method-zoo card** (property table, cost classes): `.knowledge/methods/circuit-sim`
- Track README: `tracks/qcs/README.md`
- Interview notes: `docs/qcs/interview.html`
- Review notes: `docs/qcs/review.html`
- Challenge brief: `docs/qcs/backup.md`
- Tool skills: `/using-tensorcircuit-ng`, `/using-jax`

## Select method — step 1

### Suited for

- Classical simulation of quantum circuits: variational circuit optimization (VQE), expectation values, gradients, and general circuit contraction.
- Parameterized ansatz construction; Hamiltonian expectations from dense, sparse, Pauli-sum, or MPO-like representations; reverse-mode gradients through contractions; JIT-compiled value-and-gradient kernels.
- Runtime, compile-time, and peak-memory profiling of differentiable VQE steps; contraction-path, slicing, batching, scan, checkpointing, and precision studies.

### Route elsewhere when

- Hardware execution, cloud submission, readout mitigation, or QPU calibration — not a simulation task.
- No variational energy / differentiable objective and no performance target — a plain algorithm run may belong to another track's method.
- QAOA or generic quantum algorithms, unless treated as VQE-like variational energy minimization.

### Options & trade-offs — the representation is the method choice

Choose the state representation **first**; it determines memory and whether the result is exact or approximate.

| Representation | Memory model | Exact? | When |
|---|---|---|---|
| Tensor-network contraction | largest intermediate tensor on the contraction path — not qubit count | exact | large/deep circuits whose largest intermediate fits; the QCS track benchmark |
| Full statevector | `2^n` amplitudes × dtype (× batch/gradient copies) | exact | small `n`, full-state access, noise, sampling |
| MPS circuit | bond dimension `chi` | approximate | 1D low-entanglement circuits, with a `chi` convergence check |

## Select software — step 2

### The packages

- **TensorCircuit-NG** (default) — differentiable TN circuit simulator on a JAX backend: AD, JIT, batching, contraction-path control. The route for large/deep differentiable VQE, energy+gradient profiling, and the QCS track benchmark.
- **JAX** — the numerical backend underneath: device (CPU/GPU), precision, compile/warm-runtime behavior.
- If the paper requires Qiskit, PennyLane, Yao, cuQuantum, or quimb specifically, offer official code / web search or a new tool skill instead of silently forcing TensorCircuit-NG.

### Handoff

Invoke `/using-tensorcircuit-ng` after the route is chosen — it owns representation-specific parameters, contraction/path settings, observable format, gradients, validation, and the time estimate. Invoke `/using-jax` for backend setup.

## Method setup — step 3 (method side)

Conceptual knobs and what each controls; concrete values live in `/using-tensorcircuit-ng` (*Parameter setup* / *Knobs*). For a reproduction, the paper's stated settings win — confirm them, don't re-derive.

| Knob | Controls | How it affects results |
|---|---|---|
| representation | memory model and exactness | the step-1 choice; changing it changes what "exact" means |
| contraction optimizer / path | which contraction order is executed | part of the numerical method, not a runtime tweak: optimizer (greedy vs hyper-search e.g. cotengra), search budget (e.g. `max_repeats`), and objective (flops / write / size or a blend) set both the path quality and a search cost paid per circuit size |
| slicing | memory ↔ time trade | cuts large intermediates into serial chunks; enables circuits beyond device memory at extra contraction work |
| precision | accuracy vs speed/memory | `complex64` for performance scans; `complex128` when the observable or gradient demands it |
| gradient path | how the backward pass is computed | reverse-mode AD for simulation; parameter-shift only to mimic hardware |
| timing protocol | what each reported number means | keep compile time, path-search time, warm runtime, and optimizer-loop time separate in every proposal and report |

**Cost**: statevector memory is `2^n × dtype`; TN cost is the path's FLOPs plus the path-search and JIT-compile one-offs; MPS cost scales in `chi`. Anchors and the estimate procedure live in `/using-tensorcircuit-ng` *Time estimate*.

## Details

This card is generic methodology. Paper-specific benchmarks, hardware layouts, and figure protocols belong in `/reproduce-paper` protocols or run specs, not here. It is not a hardware-execution workflow.

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
- **Recompilation contamination**: shape or dtype changes retrigger JAX compilation mid-scan; a "runtime" curve with compile spikes in it is not a runtime curve.

## Verification — implementation stage

### Intermediate (mid-run)

- Warm step time stable after the first compiled call — spikes mean recompilation, not physics.
- Energy trajectory decreasing under the optimizer.

### Final verification + expert criticism

- **Small-system ED check**: compare VQE energy to ED for the same Hamiltonian and boundary condition.
- **Gradient check**: finite-difference a small parameter subset and compare with AD gradients.
- **Energy bound**: VQE energy should not fall below the exact ground-state energy for a Hermitian Hamiltonian.
- **Seed/depth stability**: run multiple seeds and a depth sweep before claiming ansatz convergence.
- **Contractor cross-check**: a simpler contractor must reproduce the same energy/gradient.

## Citations

- `.knowledge/literature/quantum-circuit-simulation/tensorcircuit-tensorcircuit-ng.md` - official TensorCircuit-NG repository and documentation entry.
- `.knowledge/literature/quantum-circuit-simulation/2602.14167_tensorcircuit-ng-a-universal-composable-and-scalable-platfor.md` - TensorCircuit-NG software reference.
- `.knowledge/literature/quantum-circuit-simulation/2205.10091_tensorcircuit-a-quantum-software-framework-for-the-nisq-era.md` - TensorCircuit software and differentiable-circuit reference.
- `.knowledge/literature/quantum-circuit-simulation/2002.01935_hyper-optimized-tensor-network-contraction.md` - cotengra contraction-path reference.
