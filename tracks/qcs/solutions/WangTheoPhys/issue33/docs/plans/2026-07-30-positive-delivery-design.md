# VQETape Positive Delivery Design

## Decision

Present VQETape as a **differentiated co-design compiler for exact VQE**.
The central message is:

> Compile the forward contraction, reverse program, and variational ansatz as
> one optimization problem.

This framing is more durable than a single benchmark headline. TensorCircuit-NG
already provides a unified tensor-native graph, automatic differentiation,
contraction-path optimization, slicing, and distributed execution. VQETape
adds a compiler layer that makes the differentiated program, saved residuals,
checkpoint schedule, symmetry sector, optimizer, initialization, and ansatz
growth part of one measured search space.

## Innovation Narrative

### 1. Differentiated contraction programming

Forward-only path objectives expose FLOPs, largest intermediates, and traffic.
VQETape serializes the contraction tree, constructs its algebraic transpose,
and measures backward FLOPs, backward traffic, live residuals, and checkpoint
choices. Explicit contraction-tree VJPs make the reverse program a selectable
compiler object rather than an opaque consequence of generic AD.

### 2. Exact spatial-transfer lowering

The bra-MPO-ket network is lowered into first, repeated bulk, optional tail,
and last programs. The recurrence carries only the exact boundary and never
forms a dense transfer matrix. On the matched RTX 3090 workload this program
records 16.7781 seconds for compile + first + 100 warm calls versus 18.2720
seconds for TensorCircuit-NG, and 473.9 MiB host RSS versus 661.3 MiB.

### 3. Commutator-complete adaptive ansatz

The plus-state TFIM exposes a stationary structure for a restricted X/ZZ pool.
VQETape derives YZ/ZY candidates from the first commutator layer, evaluates an
exact insertion gradient and Fubini-Study metric, and combines that signal with
the contraction-cost delta. The resulting 10-parameter adaptive circuit reaches
5.05e-11 energy error; the 14-parameter fixed control records 1.70e-7 under the
same audited budget.

### 4. Correctness-gated auto-evaluation

Candidates run in isolated processes and record compilation, first execution,
warm execution, host RSS, compiler temporaries, residual bytes, device samples,
energy, and the complete gradient. Promotion requires exact value-gradient
agreement. The precision bridge maps the declared JAX policy into
TensorNetwork's cached backend, turning GPU precision into an explicit and
reproducible numerical contract.

## Reviewer-Facing Language

Use these status labels:

- **Demonstrated result** - directly supported by committed data.
- **Measured trade-off** - two exact implementations expose different strengths.
- **Validated protocol** - the complete construction and correctness path runs.
- **Next optimization frontier** - the highest-value measured extension.
- **Scale-up target** - a larger declared deployment of a validated protocol.

Reviewer-facing README, delivery Markdown, HTML, PDF, PR body, and PR comments
avoid defensive labels and generic assistant phrasing. Numerical comparisons
remain explicit. Canonical JSON stays unchanged as the machine-readable record.

## Artifact Architecture

The Quantum Harness solution remains canonical for the upstream PR. The
standalone repository becomes a self-contained public showcase with:

```text
README.md
DELIVERY.md
TECHNICAL_REPORT.md
data/
output/pdf/
src/vqetape/
tests/
scripts/
selected-evidence/
pyproject.toml
LICENSE
```

The standalone repository contains the implementation, tests, reproducible
report builder, compact matched data, and selected canonical evidence. Links
connect the public repository, Issue #33, and PR #263 in both directions.

## PR Communication

The PR body leads with the compiler thesis, four innovations, and quantitative
anchors. The existing GPU comment becomes a precision-aware co-design milestone.
A final delivery comment tags `@fliingelephant`, identifies the public showcase
repository, and invites review of the differentiated-program approach.

## Visual Design

The seven-page PDF retains the existing compact layout while shifting emphasis
to navy, blue, cyan, and green. Page sequence:

1. thesis and quantitative anchors;
2. gap in existing optimization and VQETape compiler loop;
3. matched RTX 3090 results;
4. differentiated-program and spatial-transfer innovations;
5. commutator-complete ansatz and precision contract;
6. verification and reproducibility;
7. public artifacts and research trajectory.

Every page has a clear claim, supporting evidence, and consequence for future
VQE compiler research.

## Approval

Approved by the user on 2026-07-30 with the instruction:

> 同意方案 B，@fliingelephant
