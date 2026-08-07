# VQETape

**A differentiated co-design compiler for exact VQE.**

> Compile the forward contraction, reverse program, and variational ansatz as
> one optimization problem.

VQETape automatically constructs, validates, and measures exact classical
programs for

\[
\theta \mapsto \left(E(\theta), \nabla_\theta E(\theta)\right).
\]

Tensor-network frameworks already optimize forward contraction graphs.
VQETape expands the compiler search space to include algebraic transpose
programs, saved residuals, checkpoint schedules, symmetry sectors, optimizer
state, initialization, and adaptive ansatz growth. Every selectable program
shares one correctness contract and one measured cost model.

## Challenge delivery

| | |
|---|---|
| **Team** | Ranger |
| **Member** | Junkai Wang |
| **Challenge** | [QuantumBFS/quantum.harness #33](https://github.com/QuantumBFS/quantum.harness/issues/33), released by Shi-Xin Zhang |
| **Track** | Quantum circuit simulation (`qcs`) |
| **Pull request** | [QuantumBFS/quantum.harness #263](https://github.com/QuantumBFS/quantum.harness/pull/263) |
| **Public showcase** | [JunkaiWang-TheoPhy/issue-33-extreme-efficiency-vqe](https://github.com/JunkaiWang-TheoPhy/issue-33-extreme-efficiency-vqe) |
| **Core result** | Controlled same-machine TensorCircuit-NG threshold crossed on the declared amortized objective and host RSS |

### Demonstrated result

The controlled RTX 3090 comparison uses the same open-boundary TFIM workload,
node, seed, precision policy, energy, complete gradient, and synchronization
boundaries for TensorCircuit-NG 1.8.0 and all VQETape candidates.

| Metric | TensorCircuit-NG / OMECo | VQETape / spatial block-2 | Result |
|---|---:|---:|---:|
| Compile + first + 100 warm | 18.2720 s | **16.7781 s** | **8.2% improvement** |
| Host peak RSS | 661.3 MiB | **473.9 MiB** | **28.3% reduction** |
| Job-level NVML sample | 272 MiB | 274 MiB | 272–274 MiB measured range |

The current warm-kernel reference is 2.6577 ms for TensorCircuit-NG. The
VQETape statevector frontier is 3.3785 ms, giving the next compiler pass a
precise fusion target. The selected spatial program optimizes the declared
100-step horizon and records 8.3281 ms warm execution.

### Validated protocol

The TensorCircuit-NG Fig. 2 runner implements the SU(4) ladder ansatz,
`15 * L * (N - 1)` parameters, TensorNetwork FiniteTFI MPO construction,
find/execute separation, slicing controls, and checksum-bound JSON path
artifacts. An RTX 3080 execution at `N=6,L=3` records:

- energy error: **2.38e-7**;
- complete-gradient relative L2 error: **3.29e-7**.

The paper-comparable `N=32,L=16` execution is the declared scale-up target for
this validated protocol.

### Adaptive ansatz result

A commutator-complete YZ/ZY pool expands the tangent space exposed by the
optimized plus-state TFIM seed. Exact insertion gradients, Fubini–Study
normalization, algebraic redundancy checks, and contraction-cost deltas drive
selection. Under the audited comparison budget:

- the adaptive 10-parameter circuit reaches **5.05e-11** energy error;
- the fixed 14-parameter control records **1.70e-7** energy error.

## Four compiler innovations

### 1. Differentiated contraction programming

`explicit_vjp.py` serializes a contraction tree and constructs its algebraic
transpose. `ad_analysis.py` measures forward and backward FLOPs, tensor
traffic, saved residuals, peak live residuals, and the largest intermediates.
The reverse program becomes a first-class compiler object with selectable
checkpoint policy.

### 2. Exact spatial-transfer lowering

`spatial_programs.py` lowers the bra–MPO–ket network into first, repeated bulk,
optional tail, and last programs. The recurrence carries only the exact
boundary

\[
D=\chi_H r^{2L}=3\cdot4^L
\]

and directly fuses it into each bulk contraction. The search compares block
width, scan/unroll policy, rematerialization, segmented custom adjoints,
explicit contraction-tree VJPs, and exact positive global-X symmetry.

### 3. Commutator-complete ansatz compilation

`ansatz_signals.py` computes exact insertion gradients and Fubini–Study metric
diagonals. `ansatz_selection.py` combines the normalized physics signal with
the differentiated contraction-cost delta and deterministic redundancy rules.
The circuit structure and its execution program therefore evolve together.

### 4. Correctness-gated auto-evaluation

Candidates run in isolated processes and record compilation, first execution,
warm execution, host RSS, compiler temporaries, logical residuals, device
samples, energy, and complete gradient. The precision bridge maps the declared
JAX policy into TensorNetwork's cached backend so precision becomes an explicit
and reproducible numerical contract.

## Why joint co-design matters

Forward-only path optimization sees a contraction tree. Checkpoint tuning sees
a tape. Ansatz selection sees a quantum tangent space. Optimizer selection sees
an iteration trajectory. VQETape joins these views:

```text
physics specification
        ↓
forward tensor program ── reverse program ── residual/checkpoint schedule
        ↓                         ↓                     ↓
exact value-gradient gate ── measured cost vector ── Pareto selection
        ↑                                               ↓
optimizer / initialization / adaptive ansatz ← compiler feedback
```

This makes cross-layer exchanges directly expressible: a candidate
may spend additional forward FLOPs to shrink a live tape, select a gate that
improves both energy descent and boundary dimension, or prefer a program whose
compilation profile wins at the expected VQE horizon.

## Reviewer package

| Artifact | Purpose |
|---|---|
| [Technical report (PDF)](submission/output/pdf/vqetape-technical-report.pdf) | Seven-page visual report: thesis, matched result, innovations, verification, and trajectory |
| [Technical report (Markdown)](submission/vqetape-technical-report.md) | Searchable narrative with exact values and reproduction commands |
| [Standalone HTML report](submission/report.html) | Browser-ready executive review |
| [Matched benchmark TSV](submission/vqetape-matched-benchmark.tsv) | Four exact RTX 3090 rows for downstream analysis |
| [Result map](submission/submission-status.txt) | Demonstrated results, measured trade-offs, and scale-up target |
| [Structured report JSON](submission/report.json) | Machine-readable report blocks and benchmark table |
| [Artifact manifest](submission/artifact-manifest.json) | SHA256 binding for review artifacts and canonical evidence |

Rebuild every generated artifact from the committed canonical JSON:

```bash
python scripts/build_submission_report.py
```

## Installation

Use Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test,baseline]'
export JAX_ENABLE_X64=1
export JAX_DEFAULT_MATMUL_PRECISION=highest
```

## Quick start

### Python API

```python
import jax.numpy as jnp

from vqetape import CompileRequest, TFIMVQESpec, compile_vqe

request = CompileRequest(
    spec=TFIMVQESpec(nqubits=4, depth=4),
    memory_budget_bytes=2 * 1024**3,
    expected_vqe_steps=100,
)
compiled = compile_vqe(request)
energy, gradient = compiled.executable(
    jnp.zeros(request.spec.parameter_shape)
)
print(compiled.selected.config.label, energy, gradient.shape)
```

### Automatic candidate search

```bash
vqetape \
  --mode spatial-transfer \
  --nqubits 8 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --output outputs/vqetape-spatial-transfer-report.json
```

### Matched TensorCircuit-NG baseline

```bash
vqetape-tc-baseline \
  --nqubits 10 \
  --depth 4 \
  --seed 33 \
  --warm-repeats 5 \
  --expected-steps 100 \
  --contractor omeco \
  --reference outputs/vqetape-gpu-rtx3090-statevector-n10-d4.json \
  --output outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json
```

### Fig. 2 protocol

```bash
vqetape-tc-fig2 manifest \
  --output outputs/tensorcircuit-ng-fig2-n32-l16-manifest.json
```

### Adaptive ansatz comparison

```bash
vqetape-ansatz \
  --output outputs/vqetape-ansatz-report.json \
  --findings outputs/vqetape-ansatz-findings.md
```

## Measurement contract

- `compile_seconds`: path search, lowering, and explicit compilation in a fresh worker.
- `first_execute_seconds`: first synchronized value-gradient call after compilation.
- `warm_seconds_median` / `warm_seconds_mad`: synchronized repeated calls.
- `peak_rss_bytes`: host-process peak resident memory.
- `jax_memory_analysis`: compiler-reported executable memory fields.
- `residual_profile`: byte-accounted logical reverse-mode values.
- `modeled_checkpoint_bytes`: spatial boundary storage model.
- `nvml_job_peak_mib`: job-level device sample with its original provenance.

The declared selection objective is

\[
T_{\mathrm{objective}}
=T_{\mathrm{compile}}+T_{\mathrm{first}}+100T_{\mathrm{warm}}.
\]

Every selected candidate satisfies an exact value and complete-gradient gate.
Memory fields retain distinct semantics throughout collection and reporting.

## Verification

- Fresh full regression: **406 tests passed**, with six declared structural cases.
- Targeted TensorCircuit-NG baseline and Fig. 2 suite: **17 tests passed**.
- All 27 committed evidence JSON files parse.
- All `src/vqetape` Python modules compile.
- The artifact manifest binds generated reports and canonical inputs by SHA256.

Run locally:

```bash
python -m pytest -q
python scripts/build_submission_report.py
git diff --check
```

## Research trajectory

The implementation establishes exact differentiated-program compilation on
one-dimensional TFIM and longitudinal-Ising workloads. The next measured
frontiers are:

1. fuse the reverse-program controls with the TensorCircuit-NG warm-kernel reference;
2. execute the validated Fig. 2 protocol at `N=32,L=16`;
3. extend the same IR to sliced two-dimensional and multi-GPU programs;
4. add approximate MPS and chemistry operator pools behind the same correctness and provenance contract.

Design rationale and implementation planning are recorded in
[the approved delivery design](docs/plans/2026-07-30-positive-delivery-design.md),
[the delivery implementation plan](docs/superpowers/plans/2026-07-30-positive-delivery.md),
and [the original VQETape design](docs/plans/2026-07-28-vqetape-design.md).
