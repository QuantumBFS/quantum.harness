# Quantum Circuit Simulation

Classical simulation of quantum circuits, including variational circuit optimization (VQE) and general circuit contraction. In this harness, the default route uses TensorCircuit-NG on a JAX backend with automatic differentiation, JIT compilation, and tensor-network contraction controls. It is not a hardware-execution workflow.

This card is generic methodology. Paper-specific benchmarks, hardware layouts, and figure protocols belong in `/reproduce-paper` protocols or run specs, not here.

## Setup

Canonical stack: `tensorcircuit-ng` with a JAX backend (`tools/software/stacks/tensorcircuit-ng.toml`).

TensorCircuit-NG requires JAX first.

```
make install jax EXTRA=cpu
make install tensorcircuit-ng
```

On GPU servers, replace `cpu` with the CUDA extra declared by the active cluster profile. Prefer `cuda13` when the cluster supports it.

Activate the environment with `source .venv/bin/activate`.

## Scope

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

## Notation

- `theta`: variational parameters.
- Ansatz: parameterized circuit preparing `|psi(theta)>`.
- `H`: Hamiltonian represented as Pauli terms, sparse matrix, dense matrix, or tensor-network operator.
- Forward pass: compute `E(theta)`.
- Backward pass: compute `grad_theta E(theta)` by reverse-mode AD.
- JIT compile time: first traced/compiled execution cost.
- Steady runtime: execution time after compilation/cache warmup.
- Peak memory: maximum device or host memory during forward/backward execution.
- Contractor: tensor-network contraction path and execution strategy.

## Code Shape (Python / TensorCircuit-NG + JAX)

```python
import jax
import tensorcircuit as tc

tc.set_backend("jax")
tc.set_contractor("greedy")  # switch to cotengra-backed contractors when needed


def ansatz(params, n, depth):
    c = tc.Circuit(n)
    for layer in range(depth):
        for i in range(n):
            c.rx(i, theta=params[layer, i, 0])
            c.rz(i, theta=params[layer, i, 1])
        for i in range(n - 1):
            c.cnot(i, i + 1)
    return c


def energy(params, hamiltonian, n, depth):
    c = ansatz(params, n, depth)
    return tc.backend.real(tc.templates.measurements.operator_expectation(c, hamiltonian))


value_and_grad = tc.backend.jit(tc.backend.value_and_grad(energy))
e, grad = value_and_grad(params, hamiltonian, n, depth)
```

For deep repeated layers, express the layer update with JAX control flow (`jax.lax.scan`) when possible. For large contractions, move path search and slicing into explicit contractor settings and record the contractor identity in the run manifest.

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| dtype | Accuracy and memory/runtime. | `complex64` for performance scans; `complex128` for precision checks. |
| ansatz depth | Expressiveness and compilation graph size. | Sweep depth; avoid interpreting one depth as converged. |
| contractor | Controls contraction order and memory. | `greedy` for smoke; cotengra-backed search for larger circuits. |
| path-search budget | Better paths vs planning overhead. | Separate path-search time from steady execution time. |
| slicing target | Trades memory for additional contraction work. | Use when peak memory blocks execution. |
| `jit` boundary | Controls compilation granularity. | JIT the full value-and-gradient step for benchmarkable steady runtime. |
| `scan` | Reduces graph growth for repeated layers. | Use for deep homogeneous layer stacks. |
| checkpointing | Reduces backward memory at extra compute cost. | Use when gradients OOM before forward pass does. |
| batching / `vmap` | Parallelizes seeds, terms, or parameter points. | Use only when batch axes are physically independent. |

## Pitfalls

- **Measuring compile as runtime**: report first-run compile time separately from steady runtime.
- **Silent CPU fallback**: on GPU runs, inspect `jax.devices()` inside the compute allocation.
- **Changing contractor mid-scan**: path/search settings are part of the numerical method and must be recorded.
- **Dense Hamiltonian blowup**: prefer sparse, Pauli-sum, or MPO-like forms when dense matrices dominate memory.
- **Gradient cache confusion**: shape or dtype changes can trigger recompilation; record parameter shape and dtype.
- **Optimizer hides objective cost**: profile the VQE step (`value_and_grad`) separately from the outer optimizer loop.

## Verification

- **Install smoke**: JAX devices print correctly, then `tc.set_backend("jax")` succeeds.
- **Small-system ED check**: compare VQE energy to ED for the same Hamiltonian and boundary condition.
- **Gradient check**: finite-difference a small parameter subset and compare with AD gradients.
- **Energy bound**: VQE energy should not fall below the exact ground-state energy for a Hermitian Hamiltonian.
- **Seed/depth stability**: run multiple seeds and a depth sweep before claiming ansatz convergence.
- **Performance hygiene**: report compile time, warm runtime, and peak memory as separate quantities.
- **Contractor consistency**: rerun a small case with a simple contractor and compare the energy/gradient.

## Upstream agent resources

TensorCircuit-NG ships its own agent skills (task playbooks) and memory notes (backend / AD / contraction usage lore) in-repo. Not vendored here — consult upstream when working in this method:

- Skills: https://github.com/tensorcircuit/tensorcircuit-ng/tree/master/.agents/skills
- Memory: https://github.com/tensorcircuit/tensorcircuit-ng/tree/master/.agents/memory

## Citations

- `.knowledge/literature/quantum-circuit-simulation/tensorcircuit-tensorcircuit-ng.md` - official TensorCircuit-NG repository and documentation entry.
- `.knowledge/literature/quantum-circuit-simulation/2602.14167_tensorcircuit-ng-a-universal-composable-and-scalable-platfor.md` - TensorCircuit-NG software reference.
- `.knowledge/literature/quantum-circuit-simulation/2205.10091_tensorcircuit-a-quantum-software-framework-for-the-nisq-era.md` - TensorCircuit software and differentiable-circuit reference.
- `.knowledge/literature/quantum-circuit-simulation/2002.01935_hyper-optimized-tensor-network-contraction.md` - cotengra contraction-path reference.
