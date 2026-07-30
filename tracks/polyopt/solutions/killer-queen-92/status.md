# Issue #92 central algorithm and calculation status

Last updated: **2026-07-30 17:41 CST**
Source of truth: [Quantum Harness issue #92](https://github.com/QuantumBFS/quantum.harness/issues/92)
Primary method: Xu *et al.*, [*The bulk spectral gap is semi-decidable: a
convergent family of certified upper bounds*](https://arxiv.org/abs/2606.03836)

Workflow state: **Gate 3 active — nested, geometry-sensitive lattice levels**
Carried blocker: **W0.5 — the pinned upstream Ising/Mosek reproduction cannot
run locally or on the configured SCNet account because no Mosek license is installed**

## 0. Purpose and status rules

This file tracks only the work needed to implement the paper's thermodynamic
state-polynomial hierarchy and complete the calculations requested in issue
#92. It deliberately does not count documentation, software surveys, or
finite-cluster exact diagonalization as completion of the central deliverable.

Status labels:

| label | meaning |
|---|---|
| `DONE` | matches a defined requirement and passes its acceptance test |
| `PARTIAL` | reusable work exists, but the issue's requested object is not yet produced |
| `MISSING` | central required implementation or result does not exist |
| `BLOCKED` | attempted, but numerical or external limitations currently prevent completion |
| `DIAGNOSTIC` | validation evidence only; not a thermodynamic challenge result |

Workflow states are separate from scientific result labels:

| workflow state | meaning |
|---|---|
| `ACTIVE` | the only gate on which implementation work should currently proceed |
| `WAITING` | depends on acceptance of an earlier gate |
| `BLOCKED` | the active gate cannot proceed; record the blocker and required input |
| `COMPLETE` | every checkbox has evidence and every acceptance test passes |

The current root-supported model in `src/issue92/rooted_sdp.py` is called the
**root-local outer test** in this file. “Rooted SDP” is our internal historical
name, not terminology from the paper. It is not assigned an `(L,d)` label.

### 0.1 How to use this file as the workflow

At the start of a work session:

1. read the dashboard below;
2. work only on the `ACTIVE` gate unless this file first records a dependency
   change;
3. choose the first unchecked work item in that gate;
4. do not launch Target 2 scans while Gates 0--3 remain incomplete.

At the end of a work session:

1. check an item only when its evidence artifact exists;
2. add the evidence path immediately below that item or in the gate evidence
   list;
3. run the gate's acceptance tests;
4. update the dashboard, calculation coverage, and dated workflow log;
5. update `agent.md` only if a scientific decision, correction, blocker, or
   handoff instruction changed.

### 0.2 Gate dashboard

| gate | purpose | state | checklist progress | opens when |
|---|---|---|---:|---|
| 0 | paper-to-code specification and reference reproduction | `BLOCKED` | 4/5 | Mosek license |
| 1 | hierarchy basis engine | `COMPLETE` | 5/5 | specification frozen |
| 2 | complete paper-defined SDP level | `COMPLETE` | 5/5 | SCNet atomic exact-certificate acceptance passed |
| 3 | nested, geometry-sensitive lattice levels | `ACTIVE` | 1/4 | Gate 2 accepted |
| 4 | complete Target 2 calculations | `WAITING` | 0/5 | Gate 3 accepted |
| 5 | verify exclusions and finalize results | `WAITING` | 0/5 | Gate 4 complete; checker is demonstrated on the deadline subset |

### 0.3 Current active work packet

| item | required output | completion evidence | state |
|---|---|---|---|
| `W3.1` | genuine `Lambda(L)` graph windows and interaction buffers | radius-guarded exports plus Julia/Python graph tests | `DONE` |
| `W3.2` | two nested `nmax=1` levels at selected points | SCNet dry assemblies and checked numerical rows | `ACTIVE` |
| `W3.3` | graph-automorphism reduction if required by resources | dry-assembly resource evidence | `WAITING` |
| `W3.4` | distinguish `{12,4}` from `L({8,3})` at sufficient support | different level fingerprints exist; numerical rows pending | `WAITING` |

`LEVEL_SPEC.md` and `THIRD_PARTY.md` now freeze the primary matrix hierarchy,
ladder cross-check convention, sparse-family label, and pinned upstream
revisions.  The user-directed Julia implementation proceeded while the
external W0.5 blocker was recorded; no production result is accepted until
the reference reproduction is run.

## 1. Executive status

**Current conclusion:** the exact truncated-boson algebra, lattice generators,
atomic benchmark, complete matrix- and ladder-basis hierarchy engine, reusable
JuMP/Clarabel/Mosek solve path, resumable campaign manifest, independent
primal/dual checks, exact exclusion certificates, and exact conservative
observable-bound certificates now exist.  The SCNet MKL deadline subset has
twenty-six checked one-sided observable objectives and one hundred additional
floating optima at complete hard-core `(L,d)=(1,2)` cells.  It has also
produced verified non-atomic exclusions for `{8,3}` P1 at `gamma/U=0.505`,
P2 at `0.511`, P3 at `0.518`, P4 at `0.165`, and P5 at `0.755`, with multiple larger redundant samples.  The first
excluded samples give certified coarse upper statements
`Gamma_(1,2)/U <= 0.505` at P1, `<= 0.511` at P2, `<= 0.518` at P3, `<= 0.165`
at P4, and `<=0.755` at P5, within the stated `U(1)`-invariant hard-core matrix hierarchy.  P1, P4,
and P5 have requested `0.005U` spacing.  P2 now
has a `0.002U` search span from checked FEASIBLE `0.509` to verified EXCLUDED
`0.511`; `0.510` remains unresolved after numerical errors/slow progress.  It is not yet
a requested-width endpoint because unresolved
points never move a search endpoint.  P4 has reached the requested `0.005U`
spacing: checked FEASIBLE `0.160` and exact-projected EXCLUDED `0.165`, with no
unresolved interior sample.  P3 now has checked FEASIBLE `0.514` and
exact-projected EXCLUDED `0.518`; the interior `0.515` and `0.516` trials remain
numerical `UNKNOWN`, so the `0.004U` search span is not called a clean bracket.  The
`{12,4}` now has exact-projected exclusion at `0.520` above checked FEASIBLE
`0.510`, while the line graph now has exact exclusion `0.530` and checked
FEASIBLE `0.510`; unresolved interior transition samples remain visible.  The
extended geometry grid additionally exact-certified coarse `{12,4}` upper
statements `Gamma/U<=0.300` at P4 and `<=1.000` at P5, plus line-graph P4
`<=0.300`.  Each has a primal-checked `gamma/U=0` anchor, giving coarse search
spans rather than requested-precision endpoints.  P5 at
`gamma/U=0.050` has the first two accepted two-sided
intervals: `0.9944073 <= rho0 <= 0.9999995` and, by the exact hard-core
identity, `4.879816e-7 <= F0 <= 0.005592673`.  No accepted `K0` interval or
nested-level comparison exists.  The representative P4 `gamma/U=0.100` cell
additionally has exact-projected one-sided bounds `rho0>=0.9455347492001175`,
`F0<=0.0544652507998825`, and `K0<=0.30258382329239936`.  Both nested `{8,3}` attempts
recorded `UNKNOWN` after Julia `OutOfMemoryError`.  The complete cutoff-two
baseline likewise remains `UNKNOWN`: a 192-GiB attempt assembled in 158.5 seconds
and was then cgroup-killed, while the 128-CPU/237-GiB retry assembled in 162.1
seconds and caught `OutOfMemoryError` on all four probes at 237,910,752 KiB
maximum RSS.  An eight-thread MKL retry also OOMed at 233,357,596 KiB MaxRSS.
QDLDL also OOMed at 214,327,588 KiB MaxRSS, so the complete cutoff-two baseline
has hit a structural resource gate.  Geometry refinement/recovery and the
cutoff-two TS2 dry gate remain active through the extended 20:00 CST presentation deadline.
The current auditable snapshot is
[`results/deadline_analysis/CURRENT_HPC_REPORT.html`](results/deadline_analysis/CURRENT_HPC_REPORT.html).

| area | status | concise assessment |
|---|---|---|
| truncated local boson algebra | `DONE` | exact finite matrix algebra implemented and tested |
| three lattice constructors | `DONE` | local graphs generated and checked |
| atomic analytical benchmark | `DONE` | `Δ=0.5`, `ρ=1`, `F=K=0` reproduced |
| paper-faithful level `(L,d)` | `DONE` in code | complete atomic acceptance and complete hard-core lattice records exist at `(1,2)` |
| two or more nested levels | `BLOCKED` | `(1,3)` and `(2,2)` workspaces built, but both 192-GiB solve attempts recorded `OutOfMemoryError` and explicit `UNKNOWN` rows |
| Target 2 gap upper bounds | `PARTIAL` | certified `{8,3}` P1 `<=0.505U`, P2 `<=0.511U`, P3 `<=0.518U`, P4 `<=0.165U`, P5 `<=0.755U`; P1/P4/P5 have requested `0.005U` spacing |
| Target 2 observable bounds | `PARTIAL` | 26 checked one-sided objectives, 100 floating optima, and the first 2 complete accepted intervals (`rho0`, `F0`) at P5 `gamma/U=0.050`; `K0` remains one-sided/floating |
| geometry-sensitive thermodynamic result | `PARTIAL` | `{12,4}` P2/P4/P5 are certified `<=0.520U`/`<=0.300U`/`<=1.000U`; line-graph P2/P4 are certified `<=0.530U`/`<=0.300U`; no true-gap ordering is inferred |
| verified numerical certificate | `PARTIAL` | atomic certificates and 49 non-atomic fixed-`gamma` rows pass exact projection, 256-bit Arb interval/exact-fallback PSD LDL, and positive Farkas margin checks |

This is therefore a **partial hierarchy campaign**, not a completed challenge solution.

## 2. The model that must be calculated

### 2.1 Hamiltonian and cutoff algebra

For every graph, calculate the occupation-truncated Bose--Hubbard model

\[
H=-t\sum_{\langle i,j\rangle}
  (b_i^\dagger b_j+b_j^\dagger b_i)
  +\frac{U}{2}\sum_i n_i(n_i-1)-\mu\sum_i n_i,
\qquad U=1.
\]

At cutoff `nmax`, one site is

\[
\mathcal H_i=\operatorname{span}\{|0\rangle,\ldots,|n_{\max}\rangle\},
\qquad D=n_{\max}+1,
\]

with exact matrix units

\[
E_{rs}=|r\rangle\langle s|,\qquad
E_{rs}E_{uv}=\delta_{su}E_{rv},\qquad E_{rs}^\dagger=E_{sr}.
\]

The cutoff commutator is

\[
[b,b^\dagger]=I-D E_{n_{\max},n_{\max}},
\]

not the infinite-dimensional canonical commutation relation.

Required cutoffs:

| cutoff | requirement | current algebra support |
|---:|---|---|
| `nmax=1` | mandatory | `DONE` |
| `nmax=2` | mandatory | `DONE` |
| `nmax=3` | whenever computationally feasible | `DONE` algebra; `BLOCKED` in larger pilot SDPs |

### 2.2 Infinite lattice geometries

| ID | infinite graph | coordination `z` | geometry that a sufficient level must see |
|---|---|---:|---|
| `G83` | regular `{8,3}` tiling | 3 | octagonal loop structure |
| `G124` | regular `{12,4}` tiling | 4 | dodecagonal loop structure |
| `LG83` | line graph `L({8,3})` | 4 | triangles from parent vertices |

The current root-local outer test distinguishes `z=3` from `z=4`, but it
cannot distinguish `G124` from `LG83`. Multi-site excitations or a larger
support level are required.

### 2.3 Target 2 parameter grid

After storing the duplicated center point only once, the requested grid has
five distinct `(t,mu)` points:

| point | `t/U` | `mu/U` | scan | issue's qualitative expectation |
|---|---:|---:|---|---|
| `P1` | 0.03 | 0.50 | fixed `mu` | all graphs Mott-like |
| `P2` | 0.05 | 0.50 | fixed `mu` | `{8,3}` more Mott-like; `z=4` more delocalized |
| `P3` | 0.06 | 0.50 | fixed `mu` | all graphs outside mean-field unit-filling Mott region |
| `P4` | 0.03 | 0.15 | fixed `t` | `{8,3}` expected more Mott-like than `z=4` graphs |
| `P5` | 0.03 | 0.75 | fixed `t` | `{8,3}` expected more Mott-like than `z=4` graphs |

The requested assumed gaps for observable optimization are

\[
\gamma/U\in\{0,0.05,0.10\},
\]

plus any additional values suggested by the computed `Γ_(L,d)`.

### 2.4 Target observables

At distinguished site `0`, calculate certified outer bounds on

\[
\rho_0=\omega(n_0),\qquad
F_0=\omega((n_0-1)^2),
\]

and

\[
K_0=\frac1z\sum_{j\sim0}
\omega(b_0^\dagger b_j+b_j^\dagger b_0).
\]

For every selected `gamma`, graph, cutoff, parameter point, and `(L,d)`, both
the minimum and maximum must be calculated.

### 2.5 Required calculation count per `(L,d)` level

The counts below are scientific deliverables, not the number of internal
bisection feasibility solves.

| deliverable at one `(L,d)` | mandatory `nmax=1,2` | adding `nmax=3` | total with all three |
|---|---:|---:|---:|
| gap endpoints `Γ_(L,d)` | `3 graphs × 2 cutoffs × 5 points = 30` | 15 | 45 |
| observable min/max values | `3 × 2 × 5 × 3 gamma × 3 observables × 2 senses = 540` | 270 | 810 |

Issue #92 asks for **several accessible `(L,d)`**. At least two explicitly
nested levels are needed before a change with level can be reported; three
levels are preferable for a trend. The final calculation count is the table
above multiplied by the number of completed levels.

## 3. Central algorithm required by the paper

### 3.1 Thermodynamic gap condition

For every local excitation `a`, a ground state with bulk gap at least `gamma`
must satisfy

\[
\frac12\omega\!\left(
 a^\dagger[H,a]-[H,a^\dagger]a\right)
\geq
\gamma\left(\omega(a^\dagger a)-|\omega(a)|^2\right).
\]

Because `a` is local and the Hamiltonian has finite range, `[H,a]` contains
only finitely many Hamiltonian terms. `Lambda(L)` is a local consistency
window with an outer commutator buffer, not a finite system with a chosen
boundary condition.

### 3.2 State-polynomial lift

The nonlinear product `|omega(a)|^2` requires formal state symbols
`varsigma(w)` representing `omega(w)` and lifted pseudo-moments for products of
these symbols. At level `(L,d)`, the implementation must enumerate a complete
specified basis of operator/state-polynomial monomials supported in the
allowed window and degree.

The positivity moment matrix has entries

\[
[M_d(\mathcal L)]_{s,t}
=\mathcal L(\varsigma(s^\dagger t)).
\]

The gap matrix has entries

\[
\begin{aligned}
[M^{\mathrm{gap},\gamma}(\mathcal L)]_{s,t}
=\mathcal L\!\Big[&\tfrac12\varsigma(
s^\dagger[H^{\Lambda(L)},t]
-[H^{\Lambda(L)},s^\dagger]t)\\
&-\gamma(\varsigma(s^\dagger t)
-\varsigma(s^\dagger)\varsigma(t))\Big].
\end{aligned}
\]

### 3.3 Complete fixed-`gamma` level

At a declared `(L,d)`, solve

\[
\begin{array}{ll}
\text{find} & \mathcal L\\
\text{such that}
 & \mathcal L(1)=1,\\
 & M_d(\mathcal L)\succeq0,\\
 & \text{all truncated-algebra and ideal equalities hold},\\
 & \mathcal L(\varsigma([H^{\Lambda(L)},w]))=0
   \text{ for all required interior }w,\\
 & M^{\mathrm{gap},\gamma}(\mathcal L)\succeq0.
\end{array}
\]

Any symmetry restriction must be explicit. The current implementation imposes
`U(1)` invariance, so its statements concern only `U(1)`-invariant KMS ground
states.

### 3.4 Extracting the requested quantities

For each graph, cutoff, parameter point, symmetry choice, and `(L,d)`:

1. solve reliable fixed-`gamma` feasibility problems;
2. bracket and bisect the feasibility threshold;
3. report
   `Γ_(L,d) = sup{gamma : level (L,d) is feasible}`;
4. at each requested assumed `gamma`, minimize and maximize `rho0`, `F0`, and
   `K0` over the same relaxation;
5. repeat at larger nested `(L,d)`.

Required monotonic directions:

\[
\Gamma_{L,d}\downarrow,\qquad
O_{\min}(L,d;\gamma)\uparrow,\qquad
O_{\max}(L,d;\gamma)\downarrow.
\]

Feasibility at one level proves nothing about the existence of a gap.
Infeasibility in exact arithmetic excludes the assumed gap.

## 4. Algorithm implementation crosswalk

| ID | required component | current implementation | status | condition for `DONE` |
|---|---|---|---|---|
| `A0` | reproduce one published `SpectralGap.jl` reference | exact `a1171c9` driver, expected blocks `[67,26,5,6]`, and blocked record | `BLOCKED` | run on Mosek host and match Table S1 endpoint `0.52` within `0.01` |
| `A1` | exact finite local algebra | matrix units, adjoint, multiplication, cutoff commutator | `DONE` | existing algebra tests remain exact for all cutoffs |
| `A2` | `Lambda(L)` graph window plus interaction buffer | arbitrary `L`, exact BFS interior, induced edges, graph JSON bridge | `DONE` | graph/buffer tests remain green |
| `A3` | complete operator-word basis at degree `d` | complete canonical matrix encoding plus exact charge-adapted ladder-word combinations selected by graded row reduction | `DONE` | filtered-span, adjoint, charge, rebasing, and multiplication tests remain green through cutoff 3 |
| `A4` | complete state-polynomial basis | all commuting state-symbol multisets and one operator factor enumerated in either filtered coordinate basis | `DONE` | basis embedding and adjoint-closure tests remain green |
| `A5` | complete moment matrix `M_d` | exact entries assembled in charge blocks | `DONE` | complete atomic level passed Gate 2 acceptance |
| `A6` | all required algebra/ideal equalities | exact quotient canonicalization plus normalization | `DONE` in code | regression tests remain exact |
| `A7` | stationarity/KMS equations | all interior monomials through `2d-deg(H)` | `DONE` in code | residual checks pass on accepted solves |
| `A8` | complete gap localizing matrix | Definition 2.4 index and covariance term implemented | `DONE` | atomic exclusion passed exact dual verification; lattice rows remain Gate 3/4 work |
| `A9` | explicit level metadata `(L,d)` | level/result metadata and dry-summary schema implemented | `DONE` | every production row preserves it |
| `A10` | `U(1)` charge decomposition | exact charge blocks assembled; unrestricted comparison supported | `DONE` | block-union test remains green |
| `A11` | fixed-`gamma` reusable template | one live JuMP constraint graph with exact coefficient maps; attached solver is refreshed after parameter changes | `DONE` | model-identity, update, and min/max dual regressions remain green |
| `A12` | reliable feasibility/bisection | atomic bisection works; pilot lattice errors at larger cutoff | `PARTIAL` | three-way feasible/infeasible/unknown logic works for all target cases |
| `A13` | observable optimization on same level | interface exists; 36 pilot objectives | `PARTIAL` | full requested grid at every completed level |
| `A14` | nestedness validation | structural basis embedding and geometry fingerprints tested | `PARTIAL` | numerical bound directions checked across production levels |
| `A15` | numerical infeasibility evidence | dual preservation plus exact field projection, Arb signs, exact LDL, and Farkas margin implemented | `PARTIAL` | first production ray passes independently |

### 4.1 Exact relationship of the current root-local test to the paper

The current model preserves several correct ingredients:

- exact finite matrix-unit algebra;
- local positivity;
- root stationarity equations;
- a lifted covariance term;
- the thermodynamic gap inequality for every one-site root operator;
- exact locality of `[H,a]` for those root-supported operators.

Consequently, exact infeasibility of this custom test has a valid one-way
thermodynamic implication for the stated `U(1)` state class.

It is not a paper-defined level because:

- the positivity basis excludes general multi-site words;
- the state lift contains only products of root occupation probabilities;
- the stationarity and gap matrices are indexed only by root matrix units;
- no complete degree-`d` state-polynomial basis is generated;
- no `(L,d)` metadata or nested family exists.

The core of `rooted_sdp.py` therefore requires a major extension or replacement,
not merely a larger graph radius.

## 5. Calculation status

### 5.1 Atomic target

At `t=0`, `U=1`, `mu=0.5`, the analytical result is

\[
\Delta_{\mathrm{bulk}}=0.5,\qquad
\rho_0=1,\qquad F_0=0,\qquad K_0=0.
\]

| item | current result | status |
|---|---|---|
| exact analytical benchmark | reproduced for `nmax=1,2,3` | `DONE` |
| atomic numerical bracket | `[0.5, 0.5000009537)` | `DONE` as validation |
| complete Julia hierarchy, matrix `(L,d)=(1,2)`, `nmax=1` | `gamma=0.49` feasible; `gamma=0.51` exactly excluded | `DONE` as Gate-2 validation |
| exact exclusion checker | zero affine residual, PSD LDL accepted, 256-bit Arb signs, normalized Farkas margin `1` | `DONE` as Gate-2 validation |
| `rho0` at `gamma=0` | min `0.9999999863`, max `0.9999999722`; both primal/dual checked | `DONE` as Gate-2 validation |
| graph independence at multiple levels | only simplified atomic/root tests | `PARTIAL` |

The atomic test validates signs, lifting, and certificate direction, but it does
not replace the requested multi-level hierarchy validation.

### 5.2 Target 2 fixed-`gamma` pilot

The current 135-row scan covers

`3 graphs × 3 cutoffs × 5 parameter points × 3 assumed gaps`.

| status | rows |
|---|---:|
| `optimal` | 57 |
| `optimal_inaccurate` | 54 |
| `solver_error` | 24 |

No usable row is infeasible at `gamma=0,0.05,0.10`. These runs demonstrate
parameter-loop and result-schema coverage only. They do not produce a gap
lower bound, and because the test has no `(L,d)` label, they are not requested
`Γ_(L,d)` results.

### 5.3 Gap endpoint coverage

| requested object | completed |
|---|---|
| 30 mandatory `Γ_(L,d)` endpoints per level for `nmax=1,2` | 3 / 30 at requested `0.005U` spacing |
| 15 additional endpoints per level for `nmax=3` | 0 |
| certified complete-level upper statements | 10: all five `{8,3}` hard-core `(1,2)` points, `{12,4}` P2/P4/P5, and line-graph P2/P4 |
| verified non-atomic fixed-`gamma` exclusion records | 49 in the current report snapshot |
| coarse root-local floating candidates | 3, only at `P3`, `nmax=1` |
| requested-width (`0.005U`) lattice endpoints | 3: `{8,3}` P1, P4, and P5 hard-core complete `(1,2)` |

The three pilot candidates are `<0.6` for `{8,3}` and `<0.8` for the two
`z=4` graphs, subject to `U(1)` symmetry. They are not counted as challenge
deliverables because they are neither paper-defined `Γ_(L,d)` values nor
independently verified numerical certificates.

The separate complete-hierarchy deadline scan is paper-defined and does have
independently verified certificates.  Its coarse P2 search currently has a
checked FEASIBLE sample at `0.509` and a verified EXCLUDED sample at `0.511`.
The exact `0.510` trial remains unresolved.  P4 has a checked FEASIBLE
sample at `0.160` and verified EXCLUDED sample at `0.165`, with no unresolved
refinement value between them.  P4 therefore reaches the requested spacing.
P2 remains a **search span**, not a bracket: `UNKNOWN` trials cannot be stepped
over.

### 5.4 Observable coverage

Current objective models:

`3 graphs × 2 cutoffs × 1 parameter point × 1 gamma × 3 observables × 2 senses = 36`.

They use only `P3=(t,mu)=(0.06,0.5)`, `gamma=0.1`, and `nmax=1,2`.

| requested at one level | current pilot | coverage |
|---|---:|---:|
| 540 mandatory objectives for `nmax=1,2` | 36 | 6.7% |
| 270 additional objectives for `nmax=3` | 0 | 0% |

The current complete-hierarchy deadline manifest is a deliberately smaller
hard-core subset.  At the 13:44 snapshot it contains 11 independently checked
one-sided objectives, 60 floating numerical objectives, and no accepted
two-sided interval.  Every absent, resource-failed, or residual-failed row
remains explicit `UNKNOWN` in the long-form CSV.
| several nested levels | 0 | 0% |

The 36 results are floating outer intervals of the custom root-local test, not
certified observable optima of a declared `(L,d)` hierarchy.

### 5.5 Geometry, parameter, and cutoff conclusions

| requested interpretation | current state | status |
|---|---|---|
| dependence on `t` | finite ED trend only; no `Γ_(L,d)` trend | `MISSING` |
| dependence on `mu` | finite ED trend only; no `Γ_(L,d)` trend | `MISSING` |
| `{8,3}` versus `{12,4}` | root-local test distinguishes `z=3` and `z=4` weakly | `PARTIAL` |
| `{12,4}` versus line graph | identical in root-local SDP | `MISSING` |
| `nmax=1` versus 2 versus 3 | diagnostic ED exists; SDP errors at larger cutoff | `BLOCKED` |
| change with `(L,d)` | no levels | `MISSING` |

Finite ED is retained as a validation baseline, but none of its gaps or trends
is counted as a thermodynamic result.

## 6. Required result schema

Every future calculation row must include:

| field | current root-local CSV | required hierarchy CSV |
|---|---|---|
| geometry | present | required |
| `t`, `U`, `mu` | present | required |
| `nmax` | present | required |
| symmetry/state class | present (`U1`) | required; unrestricted or restricted must be explicit |
| `L` | absent | required |
| `d` | absent | required |
| support/interior/buffer convention | absent | required |
| operator/state basis convention | absent | required |
| moment and gap matrix sizes, including charge blocks | partial | required |
| scalar variables/equalities/inequalities | present | required |
| solver and status | present | required |
| wall time and solver time | solver time present | both required |
| minimum PSD eigenvalues and residuals | partial | required |
| feasible/infeasible/unknown classification | present | required |
| gap bracket and `Γ_(L,d)` | absent | required |
| observable, sense, optimum | partial | required |
| dual certificate/checker result for exclusions | absent | required for verified claim |

## 7. Implementation plan and acceptance gates

Work must proceed in this order. Running more parameter scans with the current
root-local test does not advance the central algorithm.

### Gate 0 — Freeze the paper-to-code specification

Workflow state: `BLOCKED` only on the external Mosek reproduction

Tasks:

- [x] `W0.1` Define exactly what `L` means on a general rooted graph, including
  the excitation interior and interaction-range buffer.
- [x] `W0.2` Define total degree `d` for the finite
  matrix-algebra/state-polynomial basis.
- [x] `W0.3` Write the exact index sets for the moment, ideal, stationarity,
  covariance, and gap matrices.
- [x] `W0.4` Select and justify the first two feasible nested levels for
  `nmax=1`.
- [ ] `W0.5` Reproduce one small published `SpectralGap.jl` Ising result.
  **BLOCKED locally:** `results/reference/ising-L2-d2-g0.5-a1171c9.json`
  records the missing Mosek license.  The pinned driver and expected blocks
  `[67,26,5,6]` are ready for SCNet.

Required evidence:

- `LEVEL_SPEC.md` covering `W0.1`--`W0.4`;
- `scripts/reproduce_reference.py` or an equivalent reproducible driver;
- a raw reference-result file and term/block-size comparison table.

Acceptance:

- a mathematical level `(L,d)` determines a unique finite list of variables
  and constraints;
- a term-by-term comparison with one reference model agrees.

### Gate 1 — Implement the hierarchy basis engine

Workflow state: `COMPLETE` for both the primary matrix encoding and the
separately labelled ladder cross-check encoding

Tasks:

- [x] `W1.1` Use an independent local matrix basis or remove exact matrix-unit
  dependencies.
- [x] `W1.2` Enumerate canonical multi-site operator words with support and
  degree.
- [x] `W1.3` Enumerate noncommutative state-polynomial monomials.
- [x] `W1.4` Implement adjoint, multiplication, charge, support, and degree.
- [x] `W1.5` Explicitly assemble `U(1)` charge blocks.

Acceptance:

- bases are deterministic, adjoint closed, and free of exact duplicates;
- basis counts and multiplication tables pass exact unit tests;
- increasing `L` or `d` embeds the preceding basis.

### Gate 2 — Assemble a complete paper-defined level

Workflow state: `COMPLETE`

Tasks:

- [x] `W2.1` Assemble `M_d`.
- [x] `W2.2` Generate algebra/ideal and stationarity equalities systematically.
- [x] `W2.3` Assemble the covariance and gap localizing matrices.
- [x] `W2.4` Parameterize `t`, `mu`, and fixed `gamma` without rebuilding
  expressions.
- [x] `W2.5` Record all required level metadata and block sizes.

Acceptance:

- atomic `Δ=0.5` is recovered without special-case physics constraints;
- every returned feasible solution passes residual and PSD checks;
- every returned observable bound also passes dual stationarity, cone, and
  primal--dual-gap checks.

The pinned Ising cross-check is accepted separately by Gate 0 and remains a
hard prerequisite for production claims, not an unchecked Gate-2 code task.

Evidence: `results/atomic/julia-hierarchy-certificate.json`, produced by SCNet
Slurm job `41493313` on compute node `b10r4n13`.  The complete level has 36
moment-basis monomials, charge blocks `[1,8,18,8,1]`, 39 real scalar
variables, and gap blocks `[1,3,1]`.

### Gate 3 — Demonstrate nested lattice levels

Workflow state: `ACTIVE`

Tasks:

- [x] `W3.1` Integrate genuine `Lambda(L)` graph windows and buffers.
- [ ] `W3.2` Implement at least two nested levels for `nmax=1` on selected
  points.
- [ ] `W3.3` Add rooted graph-automorphism reduction if needed.
- [ ] `W3.4` Show that a sufficient level distinguishes `{12,4}` from
  `L({8,3})`.

Acceptance:

- feasible sets nest numerically and structurally;
- `Γ` moves downward or stays fixed;
- observable intervals shrink or stay fixed;
- both `z=4` lattices no longer have identical SDP data.

### Gate 4 — Run the complete Target 2 grid

Workflow state: `WAITING` on Gate 3

Ordered checklist:

- [ ] `W4.1` Compute all 30 mandatory gap endpoints per level for
  `nmax=1,2`.
- [ ] `W4.2` Compute all 540 mandatory observable objectives per level.
- [ ] `W4.3` Repeat for `nmax=3` where computationally feasible.
- [ ] `W4.4` Run at least a second nested level on the full grid or a clearly
  justified resource-limited subset.
- [ ] `W4.5` Analyze `t`, `mu`, geometry, cutoff, and level dependence.

Acceptance:

- every requested cell is either a result or explicitly `UNKNOWN` with a
  reason;
- no finite-ED value is mixed into the thermodynamic tables;
- all symmetry restrictions are visible in every table and figure.

### Gate 5 — Verify exclusions and finalize the scientific report

Workflow state: `WAITING` on reliable Gate 4 exclusions

Tasks:

- [ ] `W5.1` Preserve dual infeasibility rays.
- [ ] `W5.2` Independently check affine residuals and cone membership using
  higher precision, intervals, or rational reconstruction.
- [ ] `W5.3` Report exactly which `gamma` values are excluded.
- [ ] `W5.4` Report monotone changes across `(L,d)`.
- [ ] `W5.5` Separate verified bounds, floating candidates, and unknowns.

Acceptance:

- at least one non-atomic `Γ_(L,d)` upper endpoint has an independently
  checkable certificate;
- the final report satisfies every field in Section 6.

## 8. Central code structure

```text
julia/src/
  Algebra.jl                exact Q(sqrt2,sqrt3) cutoff algebra   [exists]
  StatePolynomials.jl       operator/state-polynomial bases      [exists]
  Hierarchy.jl              complete/TS2 level assembly          [exists]
  Solver.jl                 JuMP, Clarabel/Mosek, bisection       [exists]
  Certificates.jl           dual projection and verification     [exists]
scripts/
  reproduce_reference.py    pinned SpectralGap.jl comparison     [blocked: license]
  export_hierarchy_graphs.py Python-to-Julia graph bridge         [exists]
  build_campaign.py          complete level-aware issue grid      [exists]
  run_campaign_cell.py       resumable per-cell driver            [exists]
```

The current `atomic_sdp.py` and `rooted_sdp.py` should remain as regression
tests/prototypes while the complete hierarchy is developed.

## 9. Immediate next action

Do **not** run more root-local scans.  Finish the SCNet JuMP model-build and
cutoff-two `TS2` resource gates, then prepare the first two nested selected-point
cells for Gate 3.  Separately, install or point to a valid Mosek license and run
the pinned Ising reference before treating any lattice hierarchy number as a
production result.

For the 30 July presentation, SCNet array `41501751` is running a separate
low-precision diagnostic subset: P2 on all three geometries and P4 on `{8,3}`,
all at `gamma=0,0.05,0.10`, for 72 observable extrema.  Every solve has a
600-second/60-iteration cap, while the independent `1e-6` acceptance test is
unchanged.  Pending cutoff-two dry arrays `41496956` and `41496972` are held
temporarily so this four-way 64-GB array and the active 192-GB model gate stay
within the 450-GB issue budget.  Resume those arrays after the presentation
pilot leaves the queue.

With an 18-hour deadline, job `41502198` retries the large `{12,4}` complete
`(2,2)` JuMP workspace on a different node.  Its first attempt ended in
`SIGBUS` after 5,938 seconds at 141.3 GiB peak RSS, below the 192-GB request;
that attempt is an explicit model-gate `ERROR`, not a completed build.  Array
`41502207` holds the two `{8,3}` nested observable levels behind this single
large lane, while array `41502205` holds 35 independent fixed-`gamma` trials
behind the baseline presentation array.  The dependency graph keeps the
maximum simultaneous issue-92 request at 448 GB.

## 10. Update log

### 2026-07-29

- Froze `LEVEL_SPEC.md` and `THIRD_PARTY.md`, including the exact radius/interior
  convention, Definition 2.4 index offsets, primary matrix encoding, ladder
  cross-check, `TS2`, and pinned upstream revisions.
- Added the Julia/JuMP hierarchy core with exact `Q(sqrt2,sqrt3)` matrix
  algebra, complete matrix-family state monomials, U(1) charge blocks,
  stationarity/gap matrices, Clarabel/Mosek interfaces, observables, bisection,
  and a round/project certificate checker using 256-bit Arb signs.
- Added genuine graph exports, a mandatory 90-gap/1,620-observable production
  manifest, resumable cell execution, long-form gap/observable/level/solver
  aggregation that emits explicit `UNKNOWN` rows for unrun cells, and the
  SCNet sbatch profile.
- Passed 546 Julia assertions and 17 Python tests.  Coverage now includes
  exact sparse projection, JSON-safe full primal/dual checkpoints,
  deterministic gap resume, cached parameter changes, min/max dual checks,
  complete-basis embeddings, interaction buffers, TS1-in-TS2 edges, stable
  graph balls, distinct radius-two degree-four windows, and exact
  ladder-adapted filtered spans/products through cutoff three, plus mandatory
  campaign and 38-level dry-manifest counts.
- Separated exact observable certificates from Farkas exclusions.  The atomic
  complete hierarchy now verifies `rho0` with the conservative exact interval
  `[986498/986499, 5806375/5806374]`; both projected identities have zero
  exact affine residual and exact PSD Gram matrices.  A feasible record is
  explicitly rejected by the exclusion-checking branch.
- Dry-assembled all nine complete primary hard-core lattice levels on SCNet.
  The three baselines use 147/231/231 moment-basis monomials and 1.03/1.57/1.78
  GiB peak RSS for `{8,3}`/`{12,4}`/`L({8,3})`.  At `(1,3)`, the corresponding
  counts are 927/1881/1881 and 8.27/25.28/25.12 GiB.  At `(2,2)`, completed
  `{8,3}`/`{12,4}`/`L({8,3})` rows use 936/2721/1587 monomials and
  9.30/55.40/21.50 GiB.  The `{12,4}` row was deliberately cancelled after
  reaching 51.61 GiB in its original 64-GB trial, then completed safely in
  50.45 minutes with 192 GB/104 CPUs.  These are structural resource results,
  not gap calculations.
- Dry-assembled all three cutoff-two complete `(1,2)` baselines: 801/1286/1286
  moment-basis monomials and 5.29/10.53/10.11 GiB peak RSS.  The three
  hard-core baseline unsolved JuMP/Clarabel model builds also completed at
  1.82/3.03/3.17 GiB, confirming that their 64-GB production tier is safe.
  Five tighter hard-core models have completed: all three `(1,3)` models use
  23.15/80.85/80.83 GiB, while the `{8,3}` and line-graph `(2,2)` models use
  25.06/65.41 GiB.  The first `{12,4}` `(2,2)` workspace attempt failed with
  `SIGBUS` at 141.3 GiB peak RSS despite remaining below its 192-GB request;
  retry `41502198` excludes that node.
- Recorded the upstream Ising reference as `BLOCKED`: exact driver and expected
  blocks exist, but this host has no Mosek license.  No endpoint was fabricated
  with a substituted solver.
- Configured SCNet host access and the live `wzacnormal03` partition
  (128 CPUs, 255,551 MB/node, `DefMemPerCPU=1916M`).  Resource-gated arrays are
  running through an explicit dependency chain under a global 450-GB cap; no
  unrelated PEPS job was altered.
- Kept one live JuMP constraint graph across all six observables and bisection
  trials.  After a parameter change the attached optimizer is reset and fed
  the updated JuMP cache because a regression test showed that Clarabel could
  otherwise retain stale internal PSD-cone data.
- For `nmax=1`, derive both `F0` endpoints from the exact identity
  `F0=1-rho0`, preserving the opposite-sense `rho0` primal/dual record and
  avoiding two mathematically redundant SDP solves per newly started cell.
- Added an explicit short-deadline analyzer that retains all 84 observable
  objectives and 35 fixed-gap trials, accepts an interval only when both
  endpoints pass the independent checks, and leaves every missing row
  `UNKNOWN`.
- Made cell checkpoints genuinely resumable and JSON-safe, preserving every
  primal moment, equality multiplier, and dual PSD matrix.  Observable rows
  now require independent dual stationarity, dual-cone, and objective-gap
  residuals; a detailed certificate table is aggregated separately.
- Corrected `TS2` to seed every moment and gap diagonal support, in addition
  to Hamiltonian, stationarity, and objective supports.
- Replaced the provisional per-matrix-unit ladder grading by an exact
  charge-adapted coordinate basis selected from graded `b,bdag` words.  Raw
  Hamiltonians and observables are rebased exactly, while multiplication and
  adjoint continue through the shared finite-matrix algebra.
- Obtained SCNet compute allocation `41493313` on `b10r4n13`.  All 520 Julia
  assertions passed there, followed by the complete-hierarchy atomic Gate-2
  check: `gamma=0.49` was feasible, `gamma=0.51` was exactly projected and
  excluded with zero affine residual and normalized Farkas margin one, and
  both `rho0` extrema passed independent primal/dual checks.
- Re-ran the enlarged suite on SCNet; the then-current 544 assertions passed in
  job `41500730` (following the 543-assertion run in `41499485`).  Job
  `41499566` regenerated the durable atomic JSON
  with exact-projected exclusion, lower-bound, and upper-bound certificates.
- Made SCNet execution offline-safe by staging pinned Julia sources/artifacts,
  prepending the solution-local depot, and disabling registry updates.  The
  compute nodes cannot resolve public package hosts; no compilation was moved
  to the login node.
- Relocated the staged Mosek 11.2 binary on compute node `j11r3n29`, loaded
  `compiler/gcc/12.2.0` for its required C++ ABI, and successfully imported
  both `Mosek` and `MosekTools` in Slurm job `41494411`.  W0.5 is now blocked
  only by the absent license, not by package, binary, or runtime setup.
- Promoted the empirically unsafe `{12,4}` hard-core `(2,2)` dry row to
  192 GB/104 CPUs in the generated manifest itself.  Slurm wrappers now reject
  undersized CPU or memory allocations, apply the 450-GB cap across arrays,
  and preserve wall time, peak RSS, allocation, and job identity in every
  completed or resumable campaign record.
- Enforced `FEASIBLE`, `EXCLUDED`, and `UNKNOWN` as the only scientific result
  classifications.  Gap endpoint classifications and independent checker
  classifications now have separate table columns, preventing
  `VERIFIED_EXCLUSION` metadata from overwriting a solver result class.
- Completed the first nonproduction end-to-end Clarabel cell on the hard-core
  `{8,3}` baseline at Target-2 point P2.  `gamma=0` passed the primal checker
  after 3407.4 seconds, but `gamma=1` ended `NUMERICAL_ERROR` after 2569.7
  seconds, so the scientific result is explicitly `UNKNOWN` with unchanged
  bracket `[0,1]`.  The 4.82-GiB pilot is a driver/conditioning diagnostic,
  not a finished Mosek gap endpoint.

- Created this central status document from Target 2 and “Results to report.”
- Reclassified the historical “rooted SDP” as a custom root-local outer test,
  not a paper-defined `(L,d)` relaxation.
- Counted the mandatory per-level Target 2 workload: 30 gap endpoints and 540
  observable objectives for `nmax=1,2`, plus 15 and 270 respectively for
  `nmax=3`.
- Recorded that current objective coverage is 36/540 at one parameter/gap
  point and that no proper `Γ_(L,d)` has been computed.
- Set Gate 0—the paper-to-code level specification and reference
  reproduction—as the next central task.
- Converted the implementation plan into an operational workflow with one
  active gate, dependency-locked later gates, task IDs `W0.1`--`W5.5`,
  evidence requirements, checkboxes, and end-of-session update rules.
- Made `W0.1` and the planned `LEVEL_SPEC.md` the single current work item and
  prohibited further Target 2 scans until the hierarchy gates are accepted.

### 2026-07-30 — SCNet MKL campaign and progress report

- Activated Clarabel's MKL/Pardiso direct solver through SCNet's pinned Intel
  2021 module.  Smoke job `41510269` returned `OPTIMAL` and independently
  checked `FEASIBLE` in 13.8 seconds.
- Submitted observable array `41510919`, nested array `41510920`, and dependent
  fixed-`gamma` array `41510940`, keeping live requested memory at or below the
  450-GiB issue cap.
- Completed `{8,3}` P2 baseline cells at `gamma/U=0,0.05,0.10`.  Six one-sided
  objective endpoints passed independent checks; eighteen additional current
  optima are retained as floating calculations and remain scientifically
  `UNKNOWN`.
- Recorded both 192-GiB nested runs as explicit `UNKNOWN` after Julia
  `OutOfMemoryError`; Slurm shell completion is not counted as a bound.
- Added a refreshable current-report generator with accepted/floating endpoint
  tiers, working intervals, residual tables, resource outcomes, gap status,
  and a presentation plot.  The report does not weaken the closed scientific
  classifications `FEASIBLE`, `EXCLUDED`, and `UNKNOWN`.
- Expedited independent complete-level fixed-`gamma` trials produced the first
  verified non-atomic lattice exclusions: first `{8,3}` P2 at
  `gamma/U=0.515` and first P4 at `0.20`, with multiple redundant larger
  excluded samples.  Exact
  `Q(sqrt(2),sqrt(3))` projection, 256-bit Arb
  signs, PSD LDL, and positive normalized Farkas-margin checks all passed.
- Started serial `0.005U` refinement array `41523716`.  P2 `0.500` and `0.505`
  passed primal feasibility checks; `0.510` and `0.515` are explicit `UNKNOWN`
  after Clarabel zero-pivot numerical errors.  The report therefore labels the
  reduced-thread MKL retry then exactly verified exclusion at `0.515`, leaving
  a `0.010U` search span with only `0.510` unresolved.
- P4 refinement exactly verified exclusion at `0.165` immediately above a
  checked FEASIBLE `0.160` sample.  This is the first requested-spacing
  (`0.005U`) non-atomic lattice endpoint in the campaign.
- Submitted alternate-QDLDL retry `41525914` for only P2 `0.510` and `0.515`,
  dependent on completion of both nearly finished `{12,4}` observable tasks
  `41510923` and `41510924`; after their one pending replacement starts, this
  still leaves exactly one 64-GiB slot under the 450-GiB cap.
- QDLDL remained healthy but single-threaded on `0.510`, so submitted a
  reduced-thread MKL hedge `41531990` in the next free 64-GiB slot.  The old
  dependency-delayed array `41510940` is reversibly user-held before its
  dependency clears, preventing four duplicate cells from oversubscribing the
  campaign when the final presentation tasks finish.
- Queued CHOLMOD fallback `41532367` behind the reduced-thread MKL hedge, so it
  reuses the same released 64-GiB slot if `0.510` remains unresolved.
- CHOLMOD returned `UNKNOWN/ERROR` for `0.510` after 888 seconds.  Queued an
  8-thread MKL pivot-order variant `41533826` behind that same slot; no endpoint
  moved through either failed attempt.
- Released line-graph observable cells `41510919_7` and `_8` only after
  rechecking that live issue-92 requests stay within the 450-GiB campaign cap.
- After the presentation deadline moved to 20:00 CST, submitted transition
  micro-scan `41534382` at P2 `gamma/U=0.508,0.509,0.511,0.512` and
  dependency-safe `{12,4}`/line-graph refinements `41534386`/`41534390` in the
  coarse `0.50--0.60` span.  Each follow-up replaces a released 64-GiB lane,
  so the aggregate issue-92 request remains at or below 448 GiB.
- The transition micro-scan exactly verified P2 `gamma/U=0.511`, strengthening
  the complete-level thermodynamic statement from `Gamma/U<=0.515` to
  `Gamma/U<=0.511`; exact affine residual zero, 256-bit interval signs, PSD
  LDL, and normalized Farkas margin one all passed.
- The same micro-scan independently checked P2 `gamma/U=0.509` as FEASIBLE,
  leaving a `0.002U` search span with only the exact interior sample `0.510`
  unresolved; feasibility is retained solely as non-exclusion evidence.
- The remaining-point serial scan exactly verified `{8,3}` P1 exclusion at
  `gamma/U=0.600` above checked FEASIBLE `0.500`, adding the third certified
  hard-core `(1,2)` Target-2 upper statement.  P3 and P5 reuse that lane.
- Submitted nine P1/P3/P5 `{8,3}` observable cells as dependency-safe array
  `41534723`, exact P4 observable representative `41535927`, and corrected-tier
  cutoff-two representative `41535172`.  The first cutoff-two wrapper attempt
  `41535104` was rejected before a solve because 40 CPUs did not meet the
  generated 104-CPU/192-GiB request; the corrected job waits until enough
  64-GiB lanes have finished, preserving the 448-GiB aggregate ceiling.
- Corrected the hard-core exact-observable shortcut so `F0=1-rho0` transforms
  the conservative exact projected `rho0` endpoint rather than its floating
  optimum.  The derived record now preserves both values and the source
  256-bit certificate evidence.
- Passed 19 Python tests and 550 Julia assertions at the current code state.
- Replaced exact-observable job `41535927` after finding that its auxiliary
  strictly-interior SDP silently used single-threaded QDLDL.  Job `41536972`
  uses the configured MKL/Pardiso backend; certificate-stage progress logging
  now distinguishes exact-system assembly, rational projection, PSD checks,
  and interior-SDP attempts.  All 547 Julia assertions pass after the change.
- The remaining-point scan exactly verified `{8,3}` P3 exclusion at
  `gamma/U=0.600` above checked FEASIBLE `0.500`.  The `{12,4}` and line-graph
  P2 coarse scans independently verified the same `0.600` exclusion; finer
  geometry probes remain dependency-queued.
- Independently audited the first exact P4 observable checkpoint from job
  `41536972`: `rho0 >= 0.9455347492001175` with exact coefficient
  `1445994/1529287`, zero affine residual, exact PSD, 256-bit interval checks,
  and normalized objective gap `2.0e-6`.  Its hard-core consequence is the
  conservative `F0 <= 0.0544652507998825`, derived from the certified rather
  than floating endpoint.  The completed cell also exactly verifies
  `K0 <= 0.30258382329239936` (`578251/1911044`), with zero affine residual,
  eight PSD blocks, 256-bit checks, and normalized gap `9.9999e-6`.
- Submitted transition-refinement array `41538360`: seven early P5
  probes in the coarse `0.75--1.0` region followed by complete missing
  `0.005U` grids for P1 and P3 between their checked `0.500`/`0.600` anchors.
  QDLDL ultimately recorded P2 `0.510` as `UNKNOWN/NUMERICAL_ERROR` after
  6,298 seconds; its subsequent `0.515` solve was canceled as redundant with
  an existing exact MKL certificate.  Preserving that checkpoint freed a
  second 64-GiB lane, so the refinement has throttle two.  After the rigorous
  Arb interval-LDL fast path passed 550 Julia assertions, the three-minute-old
  tasks from `41538360` were replaced by resumable array `41539201` so future
  exact exclusions use it.  The array depends on `41534717` and retains the
  448-GiB aggregate request ceiling.
- Benchmarked the rigorous interval-PSD path on the stored P3 `gamma/U=0.600`
  certificate: all eight exact-projected Gram blocks passed at 256 bits, the
  largest `142x142` block took 0.723 seconds, and total PSD verification was
  under 0.8 seconds.  The previous exact-rational LDL took 199.7 seconds on
  P5 `gamma/U=1.000`; singular/inconclusive blocks still use that exact
  fallback.
- Completed the nine-cell P1/P3/P5 observable extension far enough to obtain
  the first accepted two-sided thermodynamic intervals, at P5
  `gamma/U=0.050`: `0.9944073 <= rho0 <= 0.9999995` and, through exact
  `F0=1-rho0`, `4.879816e-7 <= F0 <= 0.005592673`.  Both source density
  endpoints pass the independent primal/dual checks; `K0` remains floating.
- Completed and audited exact-observable job `41536972`; its release triggered
  the dependency-safe 104-CPU/192-GiB cutoff-two representative `41535172` on
  node `j11r3n16`.  That cell assembled its workspace in 158.5 seconds but was
  cgroup-killed during the first `gamma/U=0.750` solve, so cutoff two remains
  explicit `UNKNOWN`.  The partition exposes 255,551 MB/node but enforces
  1.9 GB/CPU; literal 249/256-GiB requests were rejected before submission.
  Retry `41540049` is accepted at the actual 128-CPU/237-GiB maximum and waits
  for P5 fine job `41539896`, giving a checked 429-GiB aggregate request.
- Cutoff-two retry `41540049` started on `j11r3n19` and rebuilt the complete
  `nmax=2`, `(L,d)=(1,2)` P2 workspace in 162.1 seconds.  It then caught
  `OutOfMemoryError` on `gamma/U=0.750` after 247.5 seconds and on all three
  subsequent probes, checkpointing four explicit `UNKNOWN` rows.  Slurm
  reports 237,910,752 KiB maximum RSS; wrapper completion is not a bound.
- P3 micro-refinement job `41540154` checked `gamma/U=0.512` and `0.514` as
  FEASIBLE and exactly verified exclusion at `0.518`.  Its coefficient
  projection has zero affine residual; the 256-bit rigorous PSD check took
  0.7 seconds and the normalized Farkas margin is one.  Thus the certified
  upper statement is now `Gamma/U<=0.518`; `0.515` and `0.516` remain
  numerical `UNKNOWN`, so the `0.004U` distance is reported as a search span.
- Regenerated the HTML/Markdown/CSV snapshot with 63 FEASIBLE, 43 EXCLUDED,
  and 83 UNKNOWN fixed-`gamma` trial-attempt rows (138/189 durable), added the
  cutoff-two OOM/retry resource record, and reran all 20 Python tests successfully.
- Made the gap wrapper's Julia, BLAS, MKL, OpenMP, and Clarabel thread caps
  independently overridable.  Submitted recovery job `41540879` with the same
  maximum 128-CPU/237-GiB allocation but all numerical pools capped at eight;
  it still caught `OutOfMemoryError` on every probe, with Slurm MaxRSS reduced
  only to 233,357,596 KiB.  Submitted 24-hour QDLDL recovery `41541639` at one
  numerical thread to trade factorization speed for memory; it also caught
  `OutOfMemoryError` on all probes at 214,327,588 KiB MaxRSS.  This rules out
  thread tuning and the available Clarabel KKT backends as a complete-level
  recovery on this node class.
- Added a rigorous fast rejection before expensive exact-field PSD LDL: a
  floating eigenvector only proposes integer directions, and a block is
  rejected only when exact `Q(sqrt(2),sqrt(3))` arithmetic proves a negative
  quadratic form.  Inconclusive and singular PSD cases retain the exact LDL
  fallback.  The fallback itself now uses symmetrically pivoted exact Schur
  complements; a rank-deficient `100x100` integer Gram test certifies in 4.7
  seconds.  All 575 Julia assertions and 21 Python tests pass.
- Submitted independent `{12,4}` recovery `41541949` for `gamma/U=0.510`
  followed by `0.540`, using the improved checker while the original `0.520`
  projected Gram matrix remains in the old exact LDL fallback.  Also queued
  serial cutoff-two TS2 dry levels `(1,3)` and `(2,2)` as `41541783` after both
  geometry arrays.  After QDLDL failed, the dependency was safely released:
  task 28 is running and the active request is 384 GiB.
- The original `{12,4}` P2 refinement exactly certified `gamma/U=0.520` after
  a 1,943-second exact PSD fallback (zero affine residual, PSD true, 256 bits,
  Farkas margin one), tightening its upper statement from `0.600` to `0.520`.
  Its duplicated continuation was canceled only after checkpoint sync because
  recovery `41541949` was already ahead on the same `0.510`/`0.540` probes.
- Replayed that stored certificate with the optimized checker: all eight Gram
  blocks, largest `222x222`, pass rigorous interval LDL in 3.125 seconds
  instead of the legacy job's 1,943-second exact fallback.  Exact affine
  residual zero and Farkas margin one are unchanged.
- Filled the two released 64-GiB lanes with midpoint array `41542751`:
  `{12,4}` at `0.515` and the line graph at `0.530`.  Together with the TS2
  dry gate, original line refinement, and `{12,4}` recovery, active requested
  memory is exactly 448 GiB; both midpoint results remain `UNKNOWN` until
  independently checked.
- TS2 dry task `41541783_28`, the cutoff-two `(L,d)=(1,3)` assembly, died with
  `SIGBUS` after 648 seconds at only 1,878,056 KiB MaxRSS and produced no level
  record.  This is a node/runtime `UNKNOWN`, not evidence of OOM or an
  infeasible level.  Task 31, `(L,d)=(2,2)`, remains active on `j11r3n19`;
  different-node retry `41542822` for task 28 is dependency-queued and excludes
  that node, so it can start only after task 31 releases the 192-GiB lane.
- Independent `{12,4}` recovery `41541949` checked `gamma/U=0.510` as
  FEASIBLE after primal and dual diagnostics.  Together with the previously
  exact-certified exclusion at `0.520`, this gives a `0.010U` search span with
  the unresolved `0.515` midpoint still visible.  The regenerated report now
  contains 64 FEASIBLE, 43 EXCLUDED, and 82 UNKNOWN trial-attempt rows
  (139/189 durable).
- Added and tested an extended-deadline geometry-grid campaign covering the
  eight remaining hard-core complete `(1,2)` Target-2 cells on `{12,4}` and
  `L({8,3})` at P1/P3/P4/P5.  Job `41543225` contains 16 independent trials:
  one point-informed coarse exclusion candidate and `gamma/U=0` per cell.
  Its four-way 64-GiB array is dependency-held behind all current 64-GiB
  refinements, excludes the four failed/suspect nodes, and therefore remains
  at 448 GiB even if the serial 192-GiB TS2 retry lane is active.
- Removed an avoidable cubic scan from deterministic TS2 chordal completion:
  minimum active degrees are now maintained incrementally across fill and
  elimination while preserving the exact old tie-breaking and clique order.
  Nineteen reference-equivalence cases and the full 575-assertion Julia suite
  pass; a 220-vertex kernel benchmark improved from 0.188 s to 0.0091 s
  (20.6x).  The tested source is staged for queued retry `41542822`; the
  already-running task 31 continues with its in-memory pre-change code.
- Parallelized the TS2 pair-support pass over Julia threads with a read-only
  candidate phase followed by lexicographically ordered merging.  Cutoff-two
  `(1,3)` has 10,921 moment monomials and 11,595,621 charge-compatible pairs
  per pass; `(2,2)` has 5,421 and 3,109,596, respectively.  The full
  575-assertion suite passes under four Julia threads, and the 104-thread code
  plus deterministic phase logging is staged for retry `41542822`.
- Line-graph refinement `41534390_1` exact-certified `gamma/U=0.540` after the
  legacy checker completed its 1,950-second PSD fallback (affine residual
  zero, PSD true, 256 bits, Farkas margin one).  Its already-started redundant
  `0.560` continuation was canceled only after the `0.540` proof was copied
  locally.  The report now contains 64 FEASIBLE, 44 EXCLUDED, and 97 UNKNOWN
  rows, 140/205 with durable solver records; the line statement is `<=0.540U`.
- Released only geometry-grid task `41543225_0` into the 64-GiB lane freed by
  the canceled redundant line continuation.  The other seven tasks retain
  their dependencies; task 0 plus three refinements plus the TS2 dry lane keeps
  the active request exactly at 448 GiB.
- Recovery `41541949` independently exact-certified its redundant `{12,4}`
  `gamma/U=0.540` probe; the optimized checker completed all eight PSD blocks
  in 0.87 seconds.  Its completion released geometry-grid task
  `41543225_1`; tasks 2-7 remain dependency-held and total requested memory
  remains 448 GiB.  The report has 141/205 durable trials: 64 FEASIBLE,
  45 EXCLUDED, and 96 UNKNOWN.
- Queued resumable optimized TS2 `(2,2)` guard `41544379` after different-node
  `(1,3)` retry `41542822`.  The two 192-GiB retries are strictly serial; if
  current task 31 has already written `COMPLETE`, the guard skips it, otherwise
  it uses the tested threaded closure.  This adds recovery coverage without
  increasing concurrent memory.
- Line midpoint job `41542751_1` exact-certified `gamma/U=0.530`: zero exact
  affine residual, all eight PSD blocks verified at 256 bits in 0.67 seconds,
  and normalized Farkas margin one.  The line-graph statement is now
  `Gamma/U<=0.530` above checked FEASIBLE `0.510`; unresolved `0.520` remains
  visible, so `0.020U` is a search span rather than a clean bracket.  Its freed
  lane now runs grid task 2.  The report has 142/205 durable rows: 64 FEASIBLE,
  46 EXCLUDED, and 95 UNKNOWN.
- `{12,4}` midpoint `41542751_0` finished as explicit `UNKNOWN/ERROR` after
  2,495 seconds.  It does not move the checked `0.510` or certified `0.520`
  endpoints, and unresolved `0.515` stays visible.  Its completion released
  the last dependency: geometry-grid tasks 0-3 now fill all four 64-GiB lanes,
  tasks 4-7 are array-throttled, and the report has 143/205 durable rows.
- Canceled pre-optimization TS2 `(2,2)` task `41541783_31` after 50 minutes,
  6.2 GiB peak RSS, no phase output, and no structural checkpoint.  Its
  completion released optimized different-node `(1,3)` retry `41542822` on
  `b11r2n01`; the resumable optimized `(2,2)` guard `41544379` remains next in
  the same serial 192-GiB lane.  The four grid cells plus this retry still
  request exactly 448 GiB.
- Added a non-destructive `submission/` layer generated from the live aggregate:
  a self-contained Harness HTML report, GitHub-readable final report, structured
  run/report JSON, curated accepted/certified CSVs, embedded figures, source
  hashes, and a directory-level raw-data manifest.  Raw primal/dual payloads
  remain under ignored `results/`; the full page passed JSON/CSV/HTML and visual
  audits.  The release suite now passes 21 Python tests and 575 Julia assertions.
- Synchronized the first extended-grid checkpoints.  `{12,4}` P4 at
  `gamma/U=0.300` and P5 at `1.000` passed exact projection, zero affine
  residual, eight 256-bit PSD blocks, and Farkas margin one, giving coarse
  upper statements without FEASIBLE-side anchors yet.  The aggregate now has
  146/205 durable rows: 64 FEASIBLE, 48 EXCLUDED, and 93 UNKNOWN.
- Geometry task `41543225_0` found an infeasible `{12,4}` P1 candidate at
  `0.600` but died with node-level `SIGBUS` on `b10r4n25` during exact
  projection, so it remains `UNKNOWN`.  Scheduler-tested recovery `41546113`
  is dependency-held after the full geometry array and excludes that node plus
  the four earlier suspect nodes, preserving the 450-GiB issue cap.
- Geometry tasks `41543225_1` and `_2` completed normally.  `{12,4}` P3 adds
  only primal-checked `FEASIBLE(0)` plus numerical `UNKNOWN(0.600)`, so it gives
  no upper statement.  P4 combines `FEASIBLE(0)` with the exact-projected
  `EXCLUDED(0.300)` row; this is a certified coarse search span, not a refined
  endpoint.  The refreshed aggregate has 150/205 durable rows: 67 FEASIBLE,
  48 EXCLUDED, and 90 UNKNOWN.
- Published the deadline-safe baseline as commit `d1ebd7d` and opened Harness
  PR #267.  The PR contains only `tracks/polyopt/solutions/killer-queen-92/`;
  subsequent SCNet evidence is added only after the same independent checks.
- Parallelized final TS2 clique-entry materialization across deterministic
  interleaved thread lanes after the live `(1,3)` log exposed that serial phase
  as the next bottleneck.  Indexed output preserves exact clique order, and two
  new entry-by-entry comparisons against dense-reference sparsification bring
  the passing Julia suite to 577 assertions.  The already-running task is
  unchanged; the optimization is staged only for the queued `(2,2)` guard and
  any later retry.
- Geometry array `41543225` completed tasks 1--7 normally.  Line-graph P4 adds
  primal-checked `FEASIBLE(0)` and exact-projected `EXCLUDED(0.300)`, the tenth
  certified hard-core upper statement.  Line P1/P3/P5 add checked zero anchors
  but their positive coarse trials are numerical `UNKNOWN`, so they create no
  bound.  The refreshed aggregate has 157/205 durable rows: 71 FEASIBLE,
  49 EXCLUDED, and 85 UNKNOWN.  Isolated task-0 recovery `41546113_0` is active
  on a different node.
