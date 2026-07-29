# VQETape End-to-Solution Training Implementation Plan

**Goal:** Compare exact VQE execution programs, classical optimizers, and
initialization/recycling policies by synchronized wall-clock time and value-
gradient calls required to reach a target energy error.

**Architecture:** A training specification selects an already-supported
statevector or spatial program and one optimizer. A compiler helper explicitly
lowers/compiles the value-and-gradient kernel and records that time. A pure
training loop records every synchronized evaluation, convergence error,
gradient norm, optimizer overhead, call count, and total time. The exact
open-boundary TFIM ground energy comes from a \(2n\times2n\) BdG oracle.
Parameter recycling is a separately serialized initialization transform.

**Constraints:**

- The target is \(E(\theta)-E_0\leq\epsilon\), never raw iteration count.
- Compile, first execution, all value-gradient calls, and optimizer overhead
  remain separately reported and all contribute to end-to-solution time.
- Every optimizer starts from exactly the serialized initialization assigned
  to that comparison.
- The unused final RZZ padding parameter remains zero and is never updated.
- NaN/Inf energy, gradient, metric, or optimizer state invalidates a run.
- Optional SciPy absence yields a structured skip for L-BFGS-B.
- Natural gradient reports damping and metric conditioning.

---

## Task 1: Add the exact TFIM ground-energy oracle

**Files:**
- Create: `src/vqetape/ground_state.py`
- Create: `tests/test_ground_state.py`

Construct the open-chain BdG matrices:

\[
A_{jj}=2g,\quad A_{j,j+1}=A_{j+1,j}=-J,
\]

\[
B_{j,j+1}=-J,\quad B_{j+1,j}=J,
\]

\[
\mathcal H_{\mathrm{BdG}}=
\begin{pmatrix}A&B\\-B&-A\end{pmatrix}.
\]

If \(\epsilon_\nu>0\) are the positive eigenvalues, return
\(-\frac12\sum_\nu\epsilon_\nu\). Compare with dense diagonalization for
two through seven qubits and multiple \(J,g\).

Commit: `feat: add exact TFIM ground-energy oracle`

---

## Task 2: Define training requests, traces, and results

**Files:**
- Create: `src/vqetape/training_spec.py`
- Create: `tests/test_training_spec.py`

Define validated immutable records:

```python
OptimizerName = Literal["adam", "lbfgs", "natural-gradient"]
InitializationName = Literal["zeros", "random", "recycled"]

@dataclass(frozen=True)
class VQETrainingRequest:
    spec: TFIMVQESpec
    program: ProgramConfig | SpatialProgramConfig
    optimizer: OptimizerName
    initialization: InitializationName
    target_energy_error: float
    max_steps: int
    seed: int = 0
    learning_rate: float = 0.05
    damping: float = 1e-3
    recycled_parameters: tuple[...] | None = None

@dataclass(frozen=True)
class VQEStep:
    evaluation: int
    optimizer_step: int
    energy: float
    energy_error: float
    gradient_norm: float
    elapsed_seconds: float

@dataclass(frozen=True)
class VQETrainingResult:
    ...
```

Round-trip every record through JSON-compatible dictionaries. Reject invalid
targets, steps, learning rates, damping, or recycled provenance.

Commit: `feat: define VQE training contracts`

---

## Task 3: Implement deterministic initialization and recycling

**Files:**
- Create: `src/vqetape/initialization.py`
- Create: `tests/test_initialization.py`

Implement zeros/random initialization and a translation-aware recycling map:

- copy overlapping layers and physical sites;
- fill new sites from the mean active RZZ/RX angle in the source layer;
- fill new layers from the last source layer;
- always force `theta[:, 0, -1] = 0`;
- serialize source/target shapes and transform policy.

Test chain growth, depth growth, shrinkage, deterministic random seeds, and
exact zero padding.

Commit: `feat: initialize and recycle VQE parameters`

---

## Task 4: Implement Adam, L-BFGS-B, and natural gradient

**Files:**
- Create: `src/vqetape/optimizers.py`
- Create: `tests/test_optimizers.py`

Implement:

- Adam with bias correction and configurable learning rate;
- SciPy L-BFGS-B using one combined value-and-gradient callback;
- damped natural gradient using the exact pure-state QGT from the
  statevector Jacobian on audited small systems.

Expose callbacks so the training runner records every expensive evaluation.
For natural gradient solve:

\[
(F+\lambda I)\Delta\theta=-\eta\nabla E
\]

and report `numpy.linalg.cond(F + damping*I)`. Freeze the RZZ padding mask in
all updates.

Compare each optimizer on convex quadratic fixtures; compare the QGT with a
finite-difference metric for a two-qubit circuit.

Commit: `feat: add classical VQE optimizer kernels`

---

## Task 5: Execute and time complete VQE training

**Files:**
- Create: `src/vqetape/training.py`
- Create: `tests/test_training.py`

Build the chosen program, lower and compile it explicitly, then run the
optimizer with synchronized outputs. Track:

- compile seconds;
- first-execution seconds;
- optimization seconds;
- time to first target, including compile;
- value-gradient call count;
- optimizer steps;
- peak RSS;
- final parameters and complete trace;
- failure/skip reason.

Use the BdG ground energy unless a validated override is supplied. Stop at
the first target crossing. Tests use small TFIM workloads and deterministic
quadratic injected kernels to audit timing/call/stop semantics.

Commit: `feat: measure VQE time to target`

---

## Task 6: Add a training CLI and comparison report

**Files:**
- Create: `src/vqetape/training_cli.py`
- Modify: `pyproject.toml`
- Create: `tests/test_training_cli.py`
- Create:
  - `outputs/vqetape-training-report.json`
  - `outputs/vqetape-training-findings.md`
- Modify: `README.md`

Add the `vqetape-train` command. Run an audited small TFIM matrix comparing:

- Adam, L-BFGS-B, and natural gradient;
- zero and seeded-random starts;
- a recycled start from a smaller/shallower converged workload;
- at least two exact execution programs chosen from dense spatial and the
  measured spatial/symmetry frontier.

Report convergence curves, calls, compile, optimization, time-to-target,
final error, and failures. Do not rank nonconverged runs by final time alone.
Validate JSON, run the full suite, and document the best supported policy.

Commit: `docs: report VQE time-to-solution results`
