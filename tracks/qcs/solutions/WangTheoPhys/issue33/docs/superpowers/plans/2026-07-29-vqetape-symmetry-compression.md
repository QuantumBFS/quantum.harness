# VQETape Exact Symmetry Compression Implementation Plan

**Goal:** Prove and exploit the exact global-\(X\) \(\mathbb Z_2\)
symmetry of the TFIM RZZ–RX VQE family so forbidden spatial-boundary
sectors are removed from the recurrent state without changing energy or
complete gradients.

**Architecture:** A pure charge-analysis module assigns \(\mathbb Z_2\)
charges to every ket/bras RZZ Schmidt leg and to the three TFIM MPO
channels. It serializes the active flattened boundary positions satisfying
the total-charge rule. A dense expand/contract/gather reference proves the
compression. The rolled runtime then stores only the compressed carry and
uses a charge-native transition when supported; an explicitly labelled
expand/gather fallback remains the correctness oracle. Unsupported initial
states or tensor families return a structured inapplicability reason.

**Constraints:**

- Compression is exact; there is no singular-value or amplitude truncation.
- The positive global-\(X\) sector is valid only for the `plus` initial
  state and the supported TFIM/RZZ–RX tensor family.
- Every supposedly forbidden component must be numerically zero on audited
  small workloads.
- The compressed recurrent carry contains exactly the active positions.
- The fallback may reconstruct a dense carry but must never be reported as a
  charge-native memory result.
- Promotion requires exact energy/full-gradient agreement and measured
  compile/warm/compiler-memory evidence.

---

## Task 1: Define and test the boundary charge rule

**Files:**
- Create: `src/vqetape/symmetry.py`
- Create: `tests/test_symmetry.py`

Implement immutable `Z2BoundarySector` metadata containing the dense shape,
active flattened positions, forbidden positions, active count, dense count,
compression ratio, and a serialization method.

For a boundary ordered as \(L\) ket Schmidt legs, \(L\) bra Schmidt legs,
and one MPO leg, assign:

\[
q_{\mathrm{RZZ}}(0)=0,\quad q_{\mathrm{RZZ}}(1)=1,
\qquad q_{\mathrm{MPO}}=(0,1,0).
\]

An entry is active iff:

\[
\bigoplus_{\ell=1}^{L} a_\ell
\bigoplus_{\ell=1}^{L} b_\ell
q_{\mathrm{MPO}}(h)=0\pmod 2.
\]

Tests must prove:

- shape `(2, 2, 3)` has six active and six forbidden entries;
- depth two has 24 active of 48 entries;
- active and forbidden positions are disjoint and exhaustive;
- all positions are deterministic and sorted;
- a nonconforming boundary shape is rejected.

Commit: `feat: derive exact Z2 boundary sectors`

---

## Task 2: Prove forbidden-sector invariance

**Files:**
- Modify: `src/vqetape/symmetry.py`
- Modify: `tests/test_symmetry.py`

Add `compress_boundary`, `expand_boundary`, and
`forbidden_boundary_norm`. For depth one and two:

1. plan first/bulk/last spatial programs;
2. execute the dense first boundary at deterministic parameters;
3. assert the forbidden norm is below dtype tolerance;
4. apply each dense bulk transition and repeat the assertion;
5. prove `expand(compress(boundary)) == boundary`;
6. compare final energies after round trips.

Add an explicit applicability function returning `(bool, reason)`. It must
accept `initial_state="plus"` and reject `initial_state="zero"` with a
specific reason.

Commit: `test: prove Z2 spatial sector invariance`

---

## Task 3: Add a serialized symmetry execution mode

**Files:**
- Modify: `src/vqetape/spec.py`
- Modify: `tests/test_spec.py`

Add:

```python
SpatialSymmetry = Literal["none", "z2-reference", "z2-native"]
```

and a `symmetry` field to `SpatialProgramConfig`, defaulting to `"none"` for
old reports. Labels and round trips must distinguish all three modes.
Validation rejects unknown modes. Planning or runtime rejects Z2 modes when
the applicability check fails.

Commit: `feat: configure exact spatial symmetry modes`

---

## Task 4: Execute an exact compressed recurrent carry

**Files:**
- Modify: `src/vqetape/spatial_programs.py`
- Modify: `tests/test_spatial_programs.py`
- Modify: `tests/test_tape.py`

Implement the `z2-reference` runtime:

- first dense output is compressed immediately;
- the scan carry has shape `(active_count,)`;
- every transition expands the carry, executes the verified dense role, and
  compresses the output;
- tail follows the same rule;
- last expands once before scalar contraction.

Compare value and complete gradient with the uncompressed program for
depths one and two, block widths one through four, and both complex dtypes.
Lowered IR must show the compressed scan carry. Residual profiling must
report a smaller recurrent carry category or, if compiler categorization
cannot isolate it, the test records both profiles without claiming a win.

Commit: `feat: run exact Z2-compressed spatial carries`

---

## Task 5: Lower charge-native transitions

**Files:**
- Create: `src/vqetape/symmetry_programs.py`
- Create: `tests/test_symmetry_programs.py`
- Modify: `src/vqetape/spatial_programs.py`

Build a charge-block contraction executor from the serialized local network:

1. propagate charges through every tensor index;
2. split tensors into nonzero charge-compatible blocks;
3. contract only compatible block pairs following the same serialized tree;
4. retain the compressed boundary key as a sector/block coordinate;
5. contract a sparse one-hot output selector so the role directly emits
   canonical compressed data.

The executor must not reconstruct the dense recurrent carry with
scatter/`todense`, and it must directly emit the active output vector.
Ordinary dense local intermediates are allowed because their shapes follow
the contraction path rather than carry storage. Add a JAXPR audit requiring
BCOO contractions and rejecting carry scatter/`bcoo_todense`. Compare every
role output and VJP with `z2-reference`.

If the planner encounters an unsupported charge pattern, it raises a
structured error and the candidate is skipped; it never silently falls back
while retaining the `z2-native` label.

Commit: `feat: lower charge-native spatial contractions`

---

## Task 6: Search, benchmark, and report symmetry candidates

**Files:**
- Modify: `src/vqetape/spatial_candidates.py`
- Modify: `src/vqetape/worker.py`
- Modify: `tests/test_spatial_candidates.py`
- Modify: `tests/test_benchmark.py`
- Create:
  - `outputs/vqetape-symmetry-report-n8-d2.json`
  - `outputs/vqetape-symmetry-report-n12-d2.json`
  - `outputs/vqetape-symmetry-findings.md`
- Modify: `README.md`

Enumerate paired `none`, `z2-reference`, and `z2-native` candidates only for
applicable TFIM workloads, using identical paths, block widths, unrolls, and
adjoint policies. Fresh workers report sector metadata, compressed bytes,
dense bytes, fallback/native mode, correctness, compile, warm, logical tape,
and compiler memory.

Promotion gate:

- all paired energy/gradient checks pass;
- `z2-native` removes exactly half of the boundary entries;
- it is nondominated on compile, warm, and compiler temporary memory for at
  least one holdout candidate;
- `z2-reference` is never presented as a native workspace-memory win.

Run both audited workloads, validate JSON, run the full test suite, and
document negative as well as positive results.

Commit: `docs: report exact symmetry-compressed VQETape results`
