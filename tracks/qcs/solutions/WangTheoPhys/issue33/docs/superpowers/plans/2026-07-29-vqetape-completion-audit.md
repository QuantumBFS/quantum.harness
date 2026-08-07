# VQETape Holdout, Device, and Completion Audit Plan

**Goal:** Close the remaining generality and hardware-evidence gaps, then
prove every approved next-stage requirement is implemented, tested, and
documented.

**Architecture:** Add a small exact longitudinal-field Ising holdout whose
Hamiltonian and RY–RZZ–RX ansatz break the TFIM global-X charge. Use dense
statevector diagonalization only as a small-system oracle and measured
L-BFGS-B training as an end-to-solution check. Separately emit a structured
runtime capability report that distinguishes CPU RSS, compiler memory
analysis, and genuine GPU availability. Finish with a requirement-to-artifact
audit and one clean full regression run.

**Constraints:**

- The holdout must not use the TFIM BdG ground-energy formula.
- Its nonzero global-X commutator must be measured explicitly.
- Z2 symmetry compression must be marked inapplicable, never silently used.
- Holdout energy and gradients must agree with dense/finite-difference oracles.
- GPU results are only reported when JAX exposes a GPU device.
- CPU peak RSS is never labeled GPU memory.
- A missing optional GPU produces a structured skip reason, not a failure.
- Completion is declared only after the full suite passes and the worktree is
  clean.

---

## Task 1: Add a symmetry-breaking one-dimensional holdout

**Files:**
- Create: `src/vqetape/holdout.py`
- Create: `tests/test_holdout.py`

Define the longitudinal-field Ising Hamiltonian

\[
H=-J\sum_i Z_iZ_{i+1}-g\sum_iX_i-h\sum_iZ_i
\]

and a depth-controlled RY–RZZ–RX statevector ansatz. Implement exact
Hamiltonian action, dense ground energy for audited small systems, value and
gradient, global-X commutator norm, and an explicit symmetry-applicability
result.

Verify normalization, dense energy, central-difference gradients, nonzero
commutator when \(h\ne0\), and recovery of TFIM symmetry when \(h=0\).

Commit: `feat: add symmetry-breaking VQE holdout`

---

## Task 2: Measure holdout VQE convergence

**Files:**
- Create: `src/vqetape/holdout_report.py`
- Create: `tests/test_holdout_report.py`
- Create: `outputs/vqetape-holdout-report.json`
- Create: `outputs/vqetape-holdout-findings.md`

Run four-qubit complex128 L-BFGS-B in a fresh process. Include explicit
compile, synchronized optimization, exact dense ground energy, calls, time to
target, and final error. Record that Z2-native spatial compression is
inapplicable and why.

Commit: `docs: report symmetry-breaking VQE holdout`

---

## Task 3: Emit runtime and GPU capability evidence

**Files:**
- Create: `src/vqetape/runtime_capabilities.py`
- Create: `tests/test_runtime_capabilities.py`
- Create: `outputs/vqetape-runtime-capabilities.json`
- Create: `outputs/vqetape-runtime-capabilities.md`

Report Python, OS, JAX/jaxlib, backend, every device kind, x64 state, GPU count,
and whether genuine device-memory profiling is available. If no GPU exists,
emit `gpu_benchmark.status = "skipped"` with an exact reason. Keep compiler
memory analysis and process RSS explicitly separate.

Commit: `docs: report VQETape runtime capabilities`

---

## Task 4: Complete the project audit

**Files:**
- Create: `docs/vqetape-completion-audit.md`
- Modify: `README.md`

Map every approved design item to code, tests, raw reports, findings, and
decision outcome. Include negative results and defaults. Run:

```bash
python -m pytest -q
```

Record the final pass/skip count and elapsed time. Validate every committed
JSON report, compile all package modules, verify `git diff --check`, and
confirm a clean worktree.

Commit: `docs: complete VQETape implementation audit`
