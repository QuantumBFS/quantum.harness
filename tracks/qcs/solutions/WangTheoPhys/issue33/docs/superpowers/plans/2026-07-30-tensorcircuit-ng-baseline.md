# TensorCircuit-NG Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and execute an audited TensorCircuit-NG value-and-gradient baseline for the exact VQETape RTX 3090 workload, while separately documenting the larger SU(4) Fig. 2 protocol.

**Architecture:** A standalone optional baseline module imports TensorCircuit-NG lazily, constructs the same open-chain TFIM and `|+>`/RZZ/RX ansatz as VQETape, generates parameters with the same NumPy seed protocol, and measures JAX lower+compile, first execution, warm execution, correctness, and memory metadata. A thin CLI writes one atomic JSON report. The GPU job runs in a fresh process and an external NVML sampler records job-level device memory.

**Tech Stack:** Python 3.12, TensorCircuit-NG, JAX, NumPy, pytest, Slurm, NVIDIA NVML.

## Global Constraints

- Matched workload: open-boundary `H = -sum ZZ - sum X`, `n=10`, depth `4`, `|+>^n`, RZZ then RX, `complex64`, NumPy `default_rng(33)` normal scale `0.1`.
- The unused last RZZ parameter remains in the `(depth, 2, nqubits)` array and must have zero gradient.
- Use `JAX_DEFAULT_MATMUL_PRECISION=highest` unless the caller explicitly overrides it.
- Report lower+compile, first execution, warm median/MAD, host RSS, JAX memory analysis, and NVML peak separately.
- Do not describe the matched RZZ/RX baseline as the paper's Fig. 2 SU(4) benchmark.
- All committed paths remain below `tracks/qcs/solutions/WangTheoPhys/issue33/`.

---

### Task 1: Protocol and parameter parity

**Files:**
- Create: `src/vqetape/tensorcircuit_baseline.py`
- Test: `tests/test_tensorcircuit_baseline.py`

**Interfaces:**
- Consumes: `TFIMVQESpec` and the seed protocol in `vqetape.worker._parameters`.
- Produces: `matched_parameters(spec: TFIMVQESpec, seed: int) -> numpy.ndarray` and `build_protocol(spec, seed) -> dict`.

- [ ] **Step 1: Write failing parity tests**

```python
def test_matched_parameters_equal_vqetape_worker():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    assert np.array_equal(matched_parameters(spec, 33), _parameters(spec, 33))

def test_protocol_records_exact_matched_workload():
    protocol = build_protocol(TFIMVQESpec(nqubits=10, depth=4), 33)
    assert protocol["hamiltonian"] == "-sum_i Z_i Z_{i+1} - sum_i X_i"
    assert protocol["ansatz"] == "plus_then_rzz_rx"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest -q tests/test_tensorcircuit_baseline.py`

- [ ] **Step 3: Implement the parameter and protocol helpers**

Use `numpy.random.default_rng(seed).normal(0.0, 0.1, spec.parameter_shape)` and cast to float32/float64 from `spec.dtype`.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m pytest -q tests/test_tensorcircuit_baseline.py`

### Task 2: TensorCircuit-NG value-and-gradient runner

**Files:**
- Modify: `src/vqetape/tensorcircuit_baseline.py`
- Modify: `tests/test_tensorcircuit_baseline.py`

**Interfaces:**
- Consumes: `matched_parameters`, `TFIMVQESpec`, contractor name, warm repeat count, optional VQETape reference JSON.
- Produces: `run_baseline(...) -> dict` with protocol, versions, timings, energy, gradient, correctness, and memory analysis.

- [ ] **Step 1: Add a dependency-free failure test**

Monkeypatch the lazy TensorCircuit import and assert the error names the `baseline` optional extra.

- [ ] **Step 2: Implement the official TensorCircuit construction**

Build `PauliStringSum2COO`, start `tc.Circuit(n)` with Hadamards, apply `c.rzz(i, i+1, theta=params[layer,0,i])`, then `c.rx(i, theta=params[layer,1,i])`, and evaluate `operator_expectation`. JIT `value_and_grad`, call `lower(...).compile()`, synchronize every timed call, and compute median/MAD.

- [ ] **Step 3: Add correctness checks**

Compare the result to the committed VQETape statevector energy and gradient. Require energy absolute error at most `1e-5` and gradient relative L2 error at most `1e-5` for complex64.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_tensorcircuit_baseline.py`

### Task 3: CLI and optional dependency

**Files:**
- Create: `src/vqetape/tensorcircuit_baseline_cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_tensorcircuit_baseline.py`

**Interfaces:**
- Produces console script `vqetape-tc-baseline` and optional dependency group `baseline`.

- [ ] **Step 1: Add parser tests**

Assert defaults `n=10`, depth `4`, seed `33`, warm repeats `5`, contractor `omeco`, and an explicit output path.

- [ ] **Step 2: Implement the CLI**

Write the report through a sibling `.tmp` file and `os.replace`; print a flushed one-line timing/correctness summary.

- [ ] **Step 3: Register dependencies and entry point**

Add `baseline = ["tensorcircuit-ng", "omeco", "cotengra"]` and `vqetape-tc-baseline = "vqetape.tensorcircuit_baseline_cli:main"`.

- [ ] **Step 4: Run focused and full tests**

Run: `python -m pytest -q tests/test_tensorcircuit_baseline.py`

### Task 4: RTX 3090 execution

**Files:**
- Create: `scripts/tensorcircuit-ng-rtx3090.sbatch`

**Interfaces:**
- Consumes: the installed issue33 package and the committed statevector reference JSON.
- Produces: `outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json`, NVML samples, environment manifest, and SHA256 sums.

- [ ] **Step 1: Precheck SSH, worktree, partition, and remote environment**

Use the existing `login03`/`hpccube-xh5` alias, inspect `xhhgnormal01`, and verify JAX/TensorCircuit versions inside a compute allocation.

- [ ] **Step 2: Preview and feasibility-check the exact job**

Request one RTX 3090, 8 CPU cores, 16 GiB RAM, and 30 minutes. Inspect the scheduler response before leaving the job queued.

- [ ] **Step 3: Submit and monitor**

Confirm `PENDING -> RUNNING`, tail the startup log until `jax.devices()` reports `cuda:0`, then monitor to a terminal Slurm state.

- [ ] **Step 4: Fetch and audit artifacts**

Verify JSON parsing, SHA256, Slurm `ExitCode=0:0`, finite timings, correctness pass, and NVML samples.

### Task 5: Reviewer-facing evidence

**Files:**
- Create: `outputs/tensorcircuit-ng-baseline-findings.md`
- Modify: `README.md`
- Modify: `docs/vqetape-completion-audit.md`

**Interfaces:**
- Produces: a matched A/B table and a separate Fig. 2 protocol gap statement.

- [ ] **Step 1: Write the matched comparison**

Compare TensorCircuit-NG and VQETape at identical `n=10`, depth `4`, seed `33`, dtype, precision, Hamiltonian, ansatz, and hardware.

- [ ] **Step 2: State the Fig. 2 boundary**

Record that the paper uses SU(4) ladder gates, `15 L (N-1)` parameters, `N=32`, `L=16`, cotengra `max_repeats=640`, `FLOPS + 640*WRITE`, and slicing; do not collapse it into the matched RZZ/RX result.

- [ ] **Step 3: Update the PR summary and verify links**

Lead with current GPU evidence and `395 passed, 6 skipped`, link the baseline findings, and remove the stale CPU-only/GPU-skipped claim.
