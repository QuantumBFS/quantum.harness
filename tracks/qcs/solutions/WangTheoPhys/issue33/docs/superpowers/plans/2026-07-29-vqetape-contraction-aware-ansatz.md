# VQETape Contraction-Aware Ansatz Growth Implementation Plan

**Goal:** Compare a fixed RZZ–RX circuit, gradient-only adaptive growth, and
contraction-aware adaptive growth under identical VQE energy targets, operator
pools, screening budgets, optimization budgets, and fresh-process timing.

**Architecture:** Represent an ansatz as a serialized ordered sequence of
local `RX(i)` and nearest-neighbor `RZZ(i,i+1)`, `YZ(i,i+1)`, and
`ZY(i,i+1)` Pauli rotations. The `YZ`/`ZY` operators are the first Lie-
commutator closure of the original \(X\) and \(ZZ\) generators. They commute
with global X and retain operator-Schmidt rank two, but prevent a fully
optimized depth-one seed from terminating in the zero-gradient tangent space
of the original pool. Begin both
adaptive methods from the same trained depth-one RZZ–RX seed circuit. At each
round, compute every pool operator's exact insertion gradient and diagonal
pure-state quantum metric at zero insertion angle. The gradient-only selector
maximizes metric-normalized signal. The contraction-aware selector divides
that signal by exact spatial-boundary growth plus compiler, warm-runtime, and
memory proxies. Append the selected gate at zero, recompile the changed
structure, warm-start all prior parameters, and reoptimize. Compare both
adaptive methods with a depth-two fixed circuit having the same maximum active
parameter count.

**Correctness and fairness constraints:**

- Every gate is an exact unitary; no tensor truncation or approximate energy is
  introduced.
- Pool operators commute with the TFIM global-X symmetry.
- The insertion gradient is checked against central finite differences.
- The diagonal metric is checked against the state Jacobian definition.
- Both adaptive selectors screen the complete same pool at every round.
- Both receive the same maximum seven growth rounds and per-round L-BFGS-B
  budget.
- Recompilation, screening, optimization, and first-target time are all
  included.
- The fixed circuit has fourteen active gates, equal to the depth-one seed plus
  seven adaptive additions for four qubits.
- Structural executable reuse requires an exact key over ordered gates,
  workload, dtype, JAX version, and device signature.
- Stationary, nonfinite, or metric-degenerate candidates are recorded and
  handled deterministically.

---

## Task 1: Define ordered ansatz structures

**Files:**
- Create: `src/vqetape/ansatz.py`
- Create: `tests/test_ansatz.py`

Define immutable `AnsatzOperator` and `AnsatzStructure` records with JSON
round trips, validation, labels, parameter counts, a depth-one/depth-two fixed
RZZ–RX constructor, and the complete local symmetry-compatible first-
commutator pool.

Implement exact statevector application for an ordered parameter vector and
verify it agrees with the existing layered kernel for fixed structures.

Commit: `feat: define exact adaptive VQE ansatz structures`

---

## Task 2: Derive exact candidate signals

**Files:**
- Create: `src/vqetape/ansatz_signals.py`
- Create: `tests/test_ansatz_signals.py`

For appended \(U_A(\alpha)=e^{-i\alpha P_A/2}\), compute

\[
g_A
=-\operatorname{Im}\langle P_A\psi|H|\psi\rangle
\]

and

\[
F_{AA}
=\frac14\left(1-\langle P_A\rangle^2\right).
\]

Return the raw gradient, metric, and regularized normalized signal
\(|g_A|^2/(F_{AA}+\varepsilon)\). Check gradients against JAX autodiff and
central differences for every pool operator.

Commit: `feat: evaluate exact adaptive ansatz signals`

---

## Task 3: Add contraction-cost deltas and structural cache keys

**Files:**
- Create: `src/vqetape/ansatz_cost.py`
- Create: `tests/test_ansatz_cost.py`

For a structure, count entanglers crossing every spatial cut and model the
exact bra–MPO–ket boundary as

\[
D=3\cdot4^{\max_e c_e}.
\]

For every candidate report:

- \(\Delta\log D\);
- weighted compiler-node delta;
- weighted execution delta;
- relative boundary-memory delta.

Implement the approved score

\[
S(A)=
\frac{|g_A|^2/(F_{AA}+\varepsilon)}
{1+\lambda_D\Delta\log D_A+\lambda_C\Delta C_A+
\lambda_W\Delta W_A+\lambda_M\Delta M_A}.
\]

Create a stable cache key including the full ordered structure, workload,
dtype, JAX version, and device signature.

Commit: `feat: score ansatz growth by contraction cost`

---

## Task 4: Select gates under equal pool budgets

**Files:**
- Create: `src/vqetape/ansatz_selection.py`
- Create: `tests/test_ansatz_selection.py`

Define gradient-only and contraction-aware policies. Both evaluate the full
pool and use the same metric regularizer. Resolve score ties by the serialized
operator label. Serialize every candidate's signal, cost deltas, final score,
rank, and selected status.

Use synthetic signal fixtures to prove that:

- policies agree when all costs are equal;
- contraction awareness can reject an otherwise highest-gradient gate when it
  increases the maximum spatial cut;
- repeated operators remain legal because circuit order changes their action.

Commit: `feat: select contraction-aware adaptive gates`

---

## Task 5: Execute dynamic VQE growth

**Files:**
- Create: `src/vqetape/ansatz_training.py`
- Create: `tests/test_ansatz_training.py`

Compile and optimize each structure in a fresh process. The adaptive runner:

1. optimizes the shared depth-one seed from the same seeded initialization;
2. screens the full pool;
3. appends one selected gate at zero;
4. recompiles using the structural cache;
5. warm-starts old parameters and optimizes the new structure;
6. stops on the first target crossing or after seven additions.

Measure cumulative compile, screening, execution/optimization, number of
value-gradient calls, number of compiled structures, peak RSS, final error,
and time to target. Add the fixed depth-two control with the same maximum
fourteen parameters.

Commit: `feat: train dynamically grown VQE ansatzes`

---

## Task 6: Add the fresh-process comparison report

**Files:**
- Create: `src/vqetape/ansatz_worker.py`
- Create: `src/vqetape/ansatz_report.py`
- Create: `tests/test_ansatz_report.py`
- Create: `outputs/vqetape-ansatz-report.json`
- Create: `outputs/vqetape-ansatz-findings.md`
- Modify: `README.md`

Run fixed, gradient-only, and contraction-aware policies on the same four-
qubit TFIM target. Preserve nonconverged results, selection traces, structural
costs, and all timing components. State whether contraction awareness improves
energy, memory proxy, compile cost, or time to target; do not claim a win if it
only changes gate order.

Validate JSON, run focused tests, then run the full regression suite.

Commit: `docs: report contraction-aware VQE ansatz results`
