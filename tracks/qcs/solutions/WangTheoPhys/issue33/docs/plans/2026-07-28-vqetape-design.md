# VQETape Design

**Date:** 2026-07-28

## 1. Purpose

VQETape is a research compiler for exact classical simulation of the core
Variational Quantum Eigensolver (VQE) kernel:

\[
\theta \mapsto \left(E(\theta), \nabla_\theta E(\theta)\right),\qquad
E(\theta)=\langle\psi(\theta)|H|\psi(\theta)\rangle.
\]

It jointly selects a tensor-contraction program and a reverse-mode residual
schedule under a device-memory budget. The first prototype is intended to
test one falsifiable hypothesis:

> Jointly changing the forward contraction program and its reverse-mode tape
> schedule can produce compile-time, steady-state-time, and peak-memory Pareto
> points that cannot be obtained by contraction-path optimization or generic
> rematerialization alone.

VQETape is a compiler layer, not a replacement for TensorCircuit-NG, JAX,
cotengra, OMEinsum, or cuTensorNet.

## 2. First Prototype Scope

### 2.1 Supported

- Exact expectation value and full reverse-mode gradient.
- One-dimensional nearest-neighbor circuits.
- Repeated VQE layers with independently parameterized gates.
- Initial product state \(|0\rangle^{\otimes n}\) or
  \(|+\rangle^{\otimes n}\).
- `RX`, `RZ`, and `RZZ` parameterized gates.
- Open-boundary 1D TFIM Hamiltonian.
- JAX execution on CPU or GPU.
- `complex64` and `complex128`.
- Two forward programs:
  - an unrolled state-vector reference;
  - a rolled `jax.lax.scan` state-vector program.
- Three reverse schedules:
  - JAX default reverse mode;
  - whole-body `jax.checkpoint`;
  - segmented custom VJP with sparse boundary checkpoints.
- Cold compile time, warm value-and-gradient time, static memory analysis,
  process peak RSS, numerical error, and Pareto reporting.

The state-vector prototype intentionally does not yet change the asymptotic
representation. It establishes the IR, schedule, measurement, and correctness
infrastructure with a tractable oracle before direct bra-H-ket tensor programs
are added.

### 2.2 Explicitly Not Supported in the First Prototype

- Arbitrary Python program capture.
- Arbitrary TensorCircuit-NG source rewriting.
- Noisy channels, sampling, or shot-based gradients.
- Dynamic circuits or mid-circuit measurement.
- Approximate MPS truncation.
- Multi-GPU or distributed execution.
- Mixed-precision search.
- Classical-optimizer or ansatz co-design.
- Reinforcement-learning search.

## 3. User Contract

The public compile request is:

```python
request = CompileRequest(
    spec=TFIMVQESpec(
        nqubits=12,
        depth=4,
        coupling=1.0,
        field=1.0,
        initial_state="plus",
        dtype="complex64",
    ),
    memory_budget_bytes=8 * 1024**3,
    expected_vqe_steps=500,
)

result = compile_vqe(request)
energy, gradient = result.executable(theta)
```

`compile_vqe` returns:

- the selected executable;
- every valid measured candidate;
- the nondominated Pareto frontier;
- the selected program and schedule configuration;
- a benchmark and correctness report.

The selected candidate minimizes

\[
T_{\mathrm{compile}} + K T_{\mathrm{warm}}
\]

among candidates satisfying the memory budget and correctness tolerances,
where \(K\) is `expected_vqe_steps`.

## 4. Architecture

```text
TFIMVQESpec
    |
    v
VQE semantic frontend
    |
    v
VQEProgramIR
    |
    +--> unrolled program
    +--> scan program
    |
    v
Adjoint schedule generator
    |
    +--> default
    +--> remat
    +--> segmented custom VJP
    |
    v
Static analysis and correctness filter
    |
    v
Fresh-process benchmark runner
    |
    v
Pareto frontier and K-aware selection
```

The later tensor-network phase extends `VQEProgramIR` with direct
bra-Hamiltonian-ket contractions, MPO lowering, cotengra paths, slicing, and
block contraction bodies without changing the compile or report interfaces.

## 5. Core Data Model

### 5.1 `TFIMVQESpec`

An immutable dataclass containing:

- `nqubits: int`
- `depth: int`
- `coupling: float`
- `field: float`
- `initial_state: Literal["zero", "plus"]`
- `dtype: Literal["complex64", "complex128"]`

Validation requires `nqubits >= 2`, `depth >= 1`, finite couplings, and a
supported dtype and initial state.

The parameter array shape is:

```text
(depth, 2, nqubits)
```

The first parameter row in each layer stores `RZZ` angles. Its last element is
padding and is deliberately unused. The second row stores `RX` angles.

### 5.2 `ProgramConfig`

An immutable dataclass containing:

- `representation: Literal["statevector"]`
- `control_flow: Literal["unrolled", "scan"]`
- `adjoint: Literal["default", "remat", "segmented"]`
- `unroll: int`
- `segment_length: int | None`

Invalid combinations are rejected. In particular, `segmented` requires
`control_flow="scan"` and a positive `segment_length`.

### 5.3 `StaticEstimate`

Contains:

- `parameter_count`
- `state_bytes`
- `saved_boundary_upper_bound_bytes`
- `estimated_forward_gate_applications`
- `estimated_recompute_gate_applications`

The segmented saved-boundary upper bound is:

\[
M_{\mathrm{boundary}} \leq
\left(\lceil m/s\rceil+s+2\right)2^n b_{\mathrm{complex}},
\]

where \(m\) is circuit depth and \(s\) is the segment length. This is an
analytical upper bound, not a replacement for measured memory.

### 5.4 `CandidateResult`

Contains:

- `config`
- `compile_seconds`
- `first_execute_seconds`
- `warm_seconds_median`
- `warm_seconds_mad`
- `peak_rss_bytes`
- optional JAX executable memory-analysis fields
- `energy_abs_error`
- `gradient_relative_l2_error`
- `valid`
- `failure`

## 6. Numerical Kernel

### 6.1 Circuit

The initial state is either \(|0\rangle^{\otimes n}\) or
\(|+\rangle^{\otimes n}\). Each layer applies:

\[
\prod_{i=0}^{n-2}R_{ZZ}(\gamma_{\ell i})
\quad\text{then}\quad
\prod_{i=0}^{n-1}R_X(\beta_{\ell i}).
\]

The gate convention is:

\[
R_X(\beta)=e^{-i\beta X/2},\qquad
R_{ZZ}(\gamma)=e^{-i\gamma Z\otimes Z/2}.
\]

Gate application reshapes the state to rank \(n\), moves target axes to the
front, performs a small dense matrix multiplication, and restores the original
axis order. This is an oracle-friendly implementation, not the final
tensor-network kernel.

### 6.2 Hamiltonian

The open-boundary TFIM Hamiltonian is:

\[
H=-J\sum_{i=0}^{n-2}Z_iZ_{i+1}-g\sum_{i=0}^{n-1}X_i.
\]

Energy is evaluated directly from the state without materializing the dense
\(2^n\times2^n\) Hamiltonian.

### 6.3 Correctness Reference

For every candidate:

- the reference is the unrolled program with JAX default reverse mode;
- energy must satisfy absolute error at most `1e-5` for `complex64` and
  `1e-10` for `complex128`;
- gradient relative L2 error must be at most `1e-4` for `complex64` and
  `1e-9` for `complex128`;
- all outputs must be finite.

Small-system tests additionally compare selected gradient coordinates against
central finite differences.

## 7. Program Generation

### 7.1 Unrolled

Python loops over layers and gates are executed while tracing the JIT function,
which produces a statically unrolled JAX program.

### 7.2 Scan

`jax.lax.scan` rolls the layer loop into one control-flow operation. Gate loops
inside a layer remain static because qubit count is a compile-time constant.
The `unroll` field controls how many layer iterations are unrolled inside the
scan body.

### 7.3 Rematerialized Scan

The scan body is wrapped in `jax.checkpoint`, instructing reverse mode to
recompute body intermediates rather than retaining all of them.

### 7.4 Segmented Custom VJP

The segmented program partitions the depth into fixed-size segments. The
forward rule stores only segment-boundary states. During the backward rule,
segments are visited in reverse:

1. restore the left boundary state;
2. recompute states inside the segment;
3. apply the VJP of that segment to its output cotangent;
4. release segment-local states before processing the previous segment.

The final partial segment is padded with zero-angle gates and masked so that
all JAX loop shapes remain static.

The custom VJP returns gradients in the original padded parameter layout, with
the unused final `RZZ` parameter in each layer receiving exactly zero.

## 8. Candidate Search

The first prototype enumerates a deliberately small candidate set:

```text
unrolled/default
scan/default       for unroll in {1, 2, 4}
scan/remat         for unroll in {1, 2, 4}
scan/segmented     for unroll in {1, 2, 4}
                   for segment_length in divisors and near-sqrt(depth)
```

Invalid unroll factors larger than depth are removed. Segment candidates always
include `1`, `depth`, `floor(sqrt(depth))`, and `ceil(sqrt(depth))`, clipped to
the valid range.

Search uses three filters:

1. static feasibility under the memory budget;
2. numerical correctness;
3. measured Pareto dominance.

Candidate \(a\) dominates \(b\) when it is no worse in compile time, warm time,
and peak RSS, and strictly better in at least one metric.

The selected candidate minimizes:

\[
T_{\mathrm{compile}} + K T_{\mathrm{warm}}
\]

over valid Pareto candidates within the memory budget.

## 9. Measurement Contract

- Each measured candidate runs in a fresh subprocess.
- JAX asynchronous results are synchronized with `block_until_ready`.
- Compilation time includes lowering and compilation but excludes Python
  environment startup.
- First execution is reported separately.
- Warm time reports median and median absolute deviation.
- Process peak RSS is collected with `resource.getrusage`.
- On GPU, JAX executable memory analysis is recorded when available.
- JAX preallocation behavior and relevant environment variables are included
  in the report.
- A deterministic PRNG seed generates parameters.

The first prototype does not claim that process RSS equals GPU peak memory.
GPU allocator or profiler integration is a later milestone.

## 10. Research Decision Gates

The prototype supports the research direction only if all of the following are
observed:

1. At least one non-default schedule reduces a measured or compiler-reported
   memory metric.
2. At least one joint program/schedule candidate is nondominated relative to
   both path/control-flow-only and rematerialization-only baselines.
3. Correctness tolerances hold for energy and full gradients.
4. Benefits are reproduced at two or more combinations of qubit count and
   depth.

If reverse residuals account for less than 30% of the measured memory delta
between energy-only and value-and-gradient, the next phase prioritizes direct
bra-H-ket contraction and slicing rather than a more sophisticated checkpoint
solver.

## 11. Later Tensor-Network Extension

After the oracle prototype passes its decision gates:

1. lower the VQE objective directly to a bra-Hamiltonian-ket network;
2. support Pauli-sum and MPO Hamiltonian programs;
3. call cotengra/OMEinsum for multiple contraction trees;
4. partition trees into loopable blocks;
5. derive contraction VJPs and residual liveness;
6. jointly search tree, block, unroll, slicing, and tape schedule;
7. add cuTensorNet as an execution backend;
8. add irregular 1D and shallow 2D holdout circuits.

## 12. Success Criteria for the Repository

The initial repository is complete when it contains:

- an installable Python package;
- validated VQE specifications and program configurations;
- correct unrolled and scan energy functions;
- default, rematerialized, and segmented value-and-gradient executables;
- fresh-process benchmark execution;
- Pareto and iteration-aware candidate selection;
- machine-readable JSON reports;
- unit and integration tests;
- a reproducible CLI example;
- documentation that distinguishes static estimates, CPU RSS, JAX memory
  analysis, and true GPU peak memory.
