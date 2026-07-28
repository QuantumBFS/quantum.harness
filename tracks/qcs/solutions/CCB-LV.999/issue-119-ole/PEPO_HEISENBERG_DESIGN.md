# PEPO / Heisenberg-picture design for the operator Loschmidt echo

- Status: approved design
- Date: 2026-07-28
- Scope: QuantumBFS/quantum.harness issue 119, OLE primary route

## 1. Decision summary

This design adds a deterministic projected entangled-pair operator (PEPO)
calculation of the operator Loschmidt echo (OLE). It is an independent
Heisenberg-picture check of the existing belief-propagation tensor-network
(BP-TN) calculation, which evolves sampled computational-basis states in the
Schrödinger picture.

The implementation will:

1. pin the upstream `quimb` development revision
   `3c89529fe0a3487133a3928201691161e110abdf`;
2. reuse `CircuitPEPOSimpleUpdate` for arbitrary-geometry simple-update
   evolution and reverse-light-cone pruning;
3. add only a thin adapter for a nonlocal three-site Pauli product and its
   normalized Hilbert–Schmidt overlap;
4. validate the implementation against an independent dense calculation on a
   nontrivial seven-qubit crop of the real circuit;
5. perform an adaptive two-axis convergence scan on the full 49-active-qubit
   circuit;
6. compare the converged PEPO value with the existing BP-TN result using the
   accuracy budgets approved below.

The existing Julia BP-TN implementation and its `runs/` artifacts remain
unchanged.

## 2. Physical quantity

Let `C` be the complete frozen OLE circuit stored in the supplied OpenQASM
file, and let

```text
O = Z52 Z59 Z72.
```

For a computational-basis bit string `z`, the existing BP-TN estimator is

```text
s(z) = o(z) ⟨z|C† O C|z⟩,
o(z) = ⟨z|O|z⟩ ∈ {−1,+1}.
```

Because `O` is diagonal in this basis, averaging uniformly over all basis
states gives

```text
F = 2⁻ⁿ Σ_z ⟨z|O C† O C|z⟩
  = 2⁻ⁿ Tr[O C† O C].
```

The PEPO path computes this normalized trace directly:

```text
O(t) = C† O C,
F    = 2⁻ⁿ Tr[O O(t)].
```

Consequences:

- there is no sampled initial bit string;
- there is no random seed or `N_init` statistical error;
- the PEPO result has operator-compression and final-contraction errors
  instead;
- when the perturbation is removed and the echo circuit becomes the identity,
  `F = 1`.

## 3. Fixed full-system protocol

The full validation uses the already audited baseline configuration:

| Item | Value |
|---|---|
| Input | `inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm` |
| QASM register | 156 labels |
| Active qubits | 49 |
| Barrier-delimited layers | 73 |
| CZ gates | 648 |
| Non-barrier gates | 4756 |
| Circuit parameters | `L=3`, `b=0.25`, `δ=0.15` |
| Perturbation encoding | 24 instances of `rz(0.3)` |
| Observable | `Z52 Z59 Z72` |
| Boundary/geometry | finite heavy-hex subgraph induced by QASM CZ edges |
| Target | `F = 2⁻⁴⁹ Tr[O C† O C]` |
| Control | replace only the 24 audited `rz(0.3)` gates by `rz(0)` |

The QASM identity is fixed by:

```text
bytes  = 150686
SHA256 = 1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455
```

The current BP-TN comparison point is:

```text
χBP = 512
N_init = 20
mean = 0.8183229131612796
SE   = 0.0019858353729792742
```

Its detailed provenance and comparison with the public values are in
[`OLE_G2_BASELINE_BENCHMARK_ASSESSMENT.md`](OLE_G2_BASELINE_BENCHMARK_ASSESSMENT.md).

## 4. Why PEPO is an independent check

The BP-TN route samples product states, evolves each state forward, and uses
belief propagation to approximate the state-network environment. The PEPO
route starts from the observable, evolves it backward, and computes a
deterministic normalized operator overlap.

The two methods therefore differ in:

- Schrödinger versus Heisenberg picture;
- sampled trace versus direct trace;
- state tensor network versus operator tensor network;
- BP environment approximation versus PEPO simple-update compression and a
  separately controlled final contraction.

They share only the physical input protocol. Agreement is consequently
meaningful, while disagreement remains diagnosable by separating protocol,
operator-bond, contraction-bond, and sampling errors.

The primary methodological reference is:

- H.-J. Liao, K. Wang, Z.-S. Zhou, P. Zhang, and T. Xiang,
  “Simulation of IBM's kicked Ising experiment with Projected Entangled Pair
  Operator,” [arXiv:2308.03082](https://arxiv.org/abs/2308.03082).

That work applies Heisenberg-picture PEPO evolution to heavy-hex kicked-Ising
circuits and reports strong performance in Clifford and near-Clifford regimes,
including direct comparisons with BP-TN and MPO calculations.

## 5. Software decision

### 5.1 Selected route

Use upstream `quimb` at the immutable revision:

```text
3c89529fe0a3487133a3928201691161e110abdf
```

Relevant upstream implementation:

- [`CircuitPEPOSimpleUpdate`](https://github.com/jcmgray/quimb/blob/3c89529fe0a3487133a3928201691161e110abdf/quimb/tensor/circuit/pepo.py)
- [upstream PEPO tests](https://github.com/jcmgray/quimb/blob/3c89529fe0a3487133a3928201691161e110abdf/tests/test_tensor/test_circuit/test_pepo.py)

The class:

- accepts arbitrary graph edges;
- records circuit gates;
- builds a bond-dimension-one operator network;
- traverses gates in reverse;
- skips gates outside the growing reverse light cone;
- applies `O ← G† O G` with Vidal-style simple-update gauging;
- compresses the operator bond to a configured maximum dimension.

### 5.2 Why a thin adapter is required

The upstream high-level method currently accepts only a one-site observable or
a two-site observable on an edge. The target `Z52 Z59 Z72` is a product on
three nonadjacent sites.

The project adapter will therefore:

1. build the same bond-dimension-one identity PEPO used upstream;
2. place `Z` on sites 52, 59, and 72;
3. start the reverse light cone from all three sites;
4. reuse the upstream `gate_simple_` evolution and gauge insertion;
5. apply the second copy of `O` on one physical side;
6. close upper and lower physical indices and contract the scalar network.

It will not reimplement gate splitting, simple-update gauging, SVD
compression, arbitrary-geometry tensor storage, or contraction optimization.

### 5.3 Dependency isolation

The PEPO route uses a separate Python project under `pepo/`, with a
`pyproject.toml` and `uv.lock`. The full git revision and all transitive Python
dependencies are recorded. No global or Julia dependency is modified.

The repository's stable `make install quimb` target may prepare the numerical
stack, but the PEPO project must then install the pinned revision rather than
silently use the PyPI 1.14.0 release, which does not contain the selected
high-level PEPO class.

## 6. Code architecture

```text
issue-119-ole/
├── pepo/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/ole_pepo/
│   │   ├── __init__.py
│   │   ├── qasm.py
│   │   ├── gates.py
│   │   ├── engine.py
│   │   ├── contraction.py
│   │   ├── exact.py
│   │   └── records.py
│   └── tests/
│       ├── test_qasm.py
│       ├── test_gate_conventions.py
│       ├── test_exact_oracle.py
│       └── test_pepo_convergence.py
├── scripts/
│   ├── validate_pepo_small.py
│   ├── run_pepo.py
│   └── analyze_pepo.py
```

Runtime artifacts use the repository-standard, gitignored
`<workspace>/results/issue119-pepo-*/` tree. Keeping runtime cells at the
workspace root lets the existing `parameter_scan.py` and
`harness_slurm.sh fetch/classify` paths work without a project-specific copy
of the cluster machinery.

Responsibilities:

- `qasm.py`: strict, independent parser for the audited OpenQASM subset;
- `gates.py`: explicit OpenQASM/Qiskit-convention matrices and quimb gate
  construction;
- `engine.py`: product-Pauli PEPO initialization, reverse light cone, and
  simple-update evolution;
- `contraction.py`: exact and compressed normalized trace contraction;
- `exact.py`: independent dense oracle for small circuits;
- `records.py`: atomic partial and final manifests, progress, timing, and
  resource diagnostics;
- `validate_pepo_small.py`: required preflight and seven-qubit oracle;
- `run_pepo.py`: one parameter-scan cell;
- `analyze_pepo.py`: convergence budget and BP-TN comparison.

## 7. Data flow

```text
audited QASM + configuration
             │
             ▼
strict Python parser ───── protocol digest check against Julia parser
             │
             ▼
ordered gates + physical labels + heavy-hex CZ edges
             │
             ▼
bond-1 product PEPO for O = Z52 Z59 Z72
             │
             ▼
reverse gate traversal with light-cone pruning
             │
             ▼
simple-update compression at operator bond Dop
             │
             ▼
insert second O and close physical indices
             │
             ├── exact contraction for the small oracle
             └── compressed contraction at χenv for the full system
             │
             ▼
F, diagnostics, manifest, convergence table, plot
```

`Dop` and `χenv` control distinct approximations:

- `Dop`: maximum virtual bond retained while evolving the operator PEPO;
- `χenv`: maximum intermediate bond retained while contracting the final
  closed two-dimensional tensor network.

Neither parameter may be described simply as “the PEPO χ” in reports.

## 8. Independent protocol parsing

The Python path does not call the Julia parser. It reads the original QASM and
independently supports only:

```text
rx, rz, cz, s, sdg, sx, sxdg, barrier
```

Unknown statements fail loudly.

To detect a shared-input but different-semantics error, both parsers produce a
canonical ordered-gate digest. Each record contains:

```text
layer index
gate index within layer
lowercase gate name
ordered physical qubit labels
IEEE-754 binary64 angle bits, or a no-angle marker
```

The newline-separated canonical records are hashed with SHA-256. Tests require
the Python and Julia digests and all audited counts to match.

Gate matrices follow:

```text
Rx(θ) = exp(−i θ X/2)
Rz(θ) = exp(−i θ Z/2)
CZ    = diag(1,1,1,−1)
```

`S`, `S†`, `√X`, and `√X†` are compared with their OpenQASM matrices up to
global phase. Global phase must cancel in `G† O G`.

## 9. Seven-qubit exact oracle

### 9.1 Sites and graph

The exact instance is the two-arm connected crop:

```text
sites = {33, 39, 53, 52, 51, 50, 49}
edges = {
  (33,39), (39,53), (53,52),
  (52,51), (51,50), (50,49)
}
observable = Z52
```

Sites 33 and 49 are the two nearest perturbed sites to observable site 52,
each at graph distance three. The crop therefore exercises both propagation
and the perturbation. In contrast, the minimal connected skeleton of the three
full-system observable sites contains no perturbation gates and would be an
artificially trivial oracle.

### 9.2 Cropping rule

- keep every one-qubit gate whose site is in the seven-site set;
- keep every two-qubit gate only if both endpoints are in the set;
- retain the original order and barrier positions;
- retain the `rz(0.3)` perturbations on sites 33 and 49;
- for the control, replace exactly those retained perturbations by `rz(0)`.

### 9.3 References and tolerances

The dense reference constructs the full `128 × 128` unitary independently with
NumPy and computes:

```text
F_dense = 2⁻⁷ Tr[O C† O C].
```

The exact PEPO reference uses no maximum bond and zero truncation cutoff, then
performs an exact final contraction.

Required checks:

```text
δ=0:    |F_dense − 1| ≤ 10⁻¹⁰
δ=0:    |F_PEPO  − 1| ≤ 10⁻¹⁰
δ=0.15: |F_PEPO − F_dense| ≤ 10⁻¹⁰
```

Truncated `Dop=1,2,4,…` values are also compared with the dense value. They
should approach the reference, but monotonicity is not assumed.

## 10. Test gates

Implementation follows red–green–refactor order. Production behavior is not
added before the corresponding test fails for the intended reason.

### 10.1 Protocol and convention tests

- reject changed input bytes or SHA;
- reject unsupported gates and malformed angles;
- preserve physical rather than dense register labels;
- match Julia and Python ordered-gate digests;
- verify all gate matrices, unitarity, qubit order, and dagger direction;
- verify one- and two-qubit hand-calculated `G† O G` examples.

### 10.2 Exact algorithm tests

- two-qubit synthetic OLE trace;
- a small nontrivial grid matching the upstream quimb PEPO tests;
- seven-qubit cropped circuit at `δ=0` and `δ=0.15`;
- equality of exact contraction and dense trace;
- approach of truncated PEPO values to the exact reference.

### 10.3 Full-system preconditions

The 49-qubit runner refuses execution unless the small-oracle success manifest
matches:

- the current source revision;
- the pinned quimb revision;
- the current QASM hash;
- the approved exact tolerance.

For every full result:

```text
|Im F| ≤ 10⁻⁸
−1 − 10⁻⁸ ≤ Re F ≤ 1 + 10⁻⁸
```

Repeating the same cell must reproduce the scalar within a declared
floating-point tolerance. No random seed appears in the PEPO interface.

## 11. Adaptive full-system scan

### 11.1 Pilot

The first full-system cells are:

```text
Dop  ∈ {2,4}
χenv ∈ {16,32}
δ    = 0.15
```

The corner `(Dop=4, χenv=32)` is repeated with `δ=0`.

The pilot measures actual wall time, peak resident memory, causal-gate count,
support growth, maximum realized bond, and contraction behavior. It is not by
itself a convergence claim.

### 11.2 Adaptive extension

After the pilot:

1. hold the current largest `χenv` fixed and extend
   `Dop = 8,16,32` as needed;
2. hold the current largest `Dop` fixed and extend
   `χenv = 64,128` as needed;
3. add only the new corner cells needed to separate the two axes;
4. require at least three completed levels along each axis before declaring a
   stable trend;
5. use a new run identifier if the axes or fixed settings change.

The convergence differences at the largest completed corner are:

```text
ΔD = |F(Dmax, χmax) − F(Dprev, χmax)|
Δχ = |F(Dmax, χmax) − F(Dmax, χprev)|.
```

The approved PEPO empirical error estimate is:

```text
εPEPO = ΔD + Δχ.
```

The full PEPO result is considered internally converged when:

```text
εPEPO ≤ 10⁻³
```

and neither axis shows a growing or unresolved oscillatory difference. If
`Dop=32` and `χenv=128` are reached without satisfying this condition, the
result is reported as unresolved within the current resource budget. No
uncontrolled infinite-bond extrapolation is substituted.

The generic repository `scripts/parameter_scan.py` owns cell enumeration,
collection, missing-cell visibility, and convergence plotting. The PEPO code
only defines the meaning of each cell and its result manifest.

## 12. Cross-method accuracy budget

### 12.1 PEPO

```text
target: εPEPO ≤ 0.001
high-precision label: εPEPO ≤ 0.0005
```

This is an empirical convergence envelope, not a rigorous norm bound.

### 12.2 BP-TN

The current BP-TN budget combines:

- the reported 95% statistical interval half-width, approximately `0.00416`;
- the paired `χBP=192 → 512` displacement, approximately `0.00024`.

The approved rounded budget is:

```text
εBP = 0.0044.
```

The BP message-passing systematic error is not rigorously bounded, so the
cross-method conclusion is explicitly a qualified numerical validation rather
than a theorem.

### 12.3 Agreement rule

Formal cross-method agreement requires:

```text
|FPEPO − FBP| ≤ εPEPO + εBP.
```

At the target PEPO budget this is:

```text
|FPEPO − FBP| ≤ 0.0054.
```

If internal PEPO convergence is not established, the values may still be
shown together, but the comparison is labelled diagnostic rather than
agreement.

## 13. Progress, records, and failure handling

### 13.1 Progress

During reverse evolution the runner emits and atomically records progress
approximately every 100 causal gates:

- processed and total causal gates;
- current light-cone support size;
- current maximum realized virtual bond;
- retained gauge-spectrum tail ratios as truncation proxies;
- elapsed time and peak resident memory;
- current phase: parse, evolve, close, contract, or finalize.

The final contraction reports contraction progress when supported by the
upstream API. A `.partial.json` record is updated after every progress block.
An interrupted cell may restart, but is never mistaken for a successful
result.

### 13.2 Cell manifest

Every cell writes the repository-standard
`<workspace>/results/<run>/cells/<cell-id>/manifest.json` with:

- status and timestamps;
- exact command and fixed settings;
- QASM, source, environment, and quimb revisions;
- observable, active sites, edges, and perturbation mode;
- `Dop`, `χenv`, evolution cutoff, and contraction cutoff;
- causal-gate and support diagnostics;
- raw complex result and normalized real result;
- wall time and peak RSS;
- validation flags and failure classification.

The manifest echoes the parameter-scan payload actually consumed, so global
settings are reported only after consensus across all completed cells.

### 13.3 Hard failures

The runner fails without producing a success tag on:

- QASM identity or protocol-digest mismatch;
- unknown or unsupported gate;
- a two-qubit gate absent from the declared graph;
- a missing observable site;
- nonfinite tensor data or result;
- an imaginary part or physical-range violation above tolerance;
- exact-oracle precondition failure.

OOM, timeout, and resource-limit failures are retained as visible failed
cells. Resources are not increased automatically.

### 13.4 Disagreement

If PEPO and BP-TN disagree:

1. do not average the two values;
2. confirm the common QASM and observable protocol;
3. inspect `Dop` and `χenv` axes separately;
4. inspect the BP sampling interval and paired bond-dimension shift;
5. report unresolved disagreement if neither method's declared budget explains
   it.

## 14. Compute policy

### 14.1 Local

The dense two-qubit and seven-qubit oracle is expected to require less than two
minutes and less than 1 GB, so it runs locally.

### 14.2 Remote

Every full 49-qubit cell is treated as remote compute unless a measured pilot
proves it finishes locally within ten minutes and 16 GB.

Provisional per-cell upper estimates are:

| Regime | CPU | Memory | Wall |
|---|---:|---:|---:|
| `Dop≤4`, `χenv≤32` | 8 | 16–32 GB | ≤2 h |
| `Dop≤16`, `χenv≤64` | 16 | 32–128 GB | 2–12 h |
| `Dop=32`, `χenv=128` | 32 | 128–256 GB | ≤24 h |

These are scheduling caps, not measured costs. The pilot's `MaxRSS` and
`Elapsed` determine later requests. No cell is automatically extended beyond
24 hours.

There is currently no active Slurm profile. The existing SCNet profile may be
used only as a hardware-capacity reference; this project must not submit PEPO
jobs to SCNet under the prior user instruction. Before a real full-system
submission, the workflow must restore or create a profile for
`zyli@172.16.42.215`, probe its actual partitions and queue, run the scheduler
test-only request, and obtain resource ratification.

Initial implementation uses the NumPy/SciPy CPU backend. GPU execution is out
of scope until the exact CPU path passes and a measured profile shows that GPU
porting is justified.

## 15. Deliverables

```text
PEPO_HEISENBERG_DESIGN.md
PEPO_HEISENBERG_IMPLEMENTATION_PLAN.md
PEPO_SMALL_VALIDATION.md
PEPO_49Q_VALIDATION.md
pepo/...
scripts/validate_pepo_small.py
scripts/run_pepo.py
scripts/analyze_pepo.py
<workspace>/results/issue119-pepo-small-oracle/...
<workspace>/results/issue119-pepo-49q-scan/run_spec.json
<workspace>/results/issue119-pepo-49q-scan/cells/*/manifest.json
<workspace>/results/issue119-pepo-49q-scan/parameter-scan.csv
<workspace>/results/issue119-pepo-49q-scan/pepo-convergence.png
```

The short final report must state:

1. the PEPO value and empirical `εPEPO`;
2. whether both `Dop` and `χenv` met the approved budget;
3. whether the value agrees with BP-TN under the approved combined budget;
4. the residual non-rigorous uncertainty.

## 16. Acceptance criteria

Implementation is complete only when:

- the pinned environment can be recreated from a fresh checkout;
- all protocol and gate-convention tests pass;
- the seven-qubit exact oracle meets `10⁻¹⁰`;
- the full runner produces deterministic, provenance-complete manifests;
- the adaptive scan either reaches `εPEPO≤10⁻³` or honestly records the
  approved resource cap as unresolved;
- the BP-TN comparison uses `εBP=0.0044` and the approved agreement rule;
- generated scripts, results, plots, and reports are linked from the issue
  README.

## 17. Out of scope

- replacing or modifying the completed BP-TN baseline;
- claiming a rigorous PEPO error bound from successive bond differences;
- silently extrapolating to infinite `Dop` or `χenv`;
- changing the physical circuit or observable to obtain agreement;
- submitting to SCNet;
- optimizing a GPU implementation before CPU correctness is established.
