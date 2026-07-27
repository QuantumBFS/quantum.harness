# Minimal generic refactor plan for SpectralGap

Status: design plus solver-free adapter prototype. No change has been made to
the upstream package and no SDP has been run.

## 1. Why the current function boundary is the problem

Upstream v0.3.0 exposes four model-specific functions:

```text
certify_Ising_gap(...)
certify_Ising_gap_nosignsymmetry(...)
certify_Heisenberg_kagome_gap(...)
certify_Heisenberg_kagome_gap_nosignsymmetry(...)
```

The Kagome entry receives `N`, hand-written `triples`, `edges`,
`inner_triples`, and `inner_edges`. Its basis builder also maps only
`N=5,13,27,45` to hard-coded inner patches. The functions simultaneously own:

- lattice geometry and the bulk buffer;
- Hamiltonian term generation;
- basis selection;
- state-symmetry restriction;
- Gram/affine SDP assembly;
- Mosek construction and optimization;
- raw-status interpretation.

Square J1-J2 cannot be safely added by copying another such function. The
geometry and solver semantics must be separated first.

## 2. Minimal object boundary

The proposed top-level object is:

```text
GapProblem
├── model: finite-range local Pauli interaction
├── patch: outer sites, inner sites, coordinates
├── hierarchy: d, γ, basis specification
├── state symmetry: none or explicit automorphism generators
└── numerical policy: formulation, solver, tolerances, witness policy
```

The first four fields determine the mathematical relaxation. The numerical
policy determines how it is assembled/solved, not what physical state class is
being discussed.

### Geometry interface

```text
outer_sites(patch)
inner_sites(patch)
coordinates(patch)
instantiate_terms(model, patch)
validate_interaction_buffer(model, patch)
```

The validation condition is:

```text
every translated interaction touching inner_sites
has its complete support in outer_sites.
```

It must be checked from interaction templates or an exact incident-term
oracle. Merely checking the already-truncated bond list is circular.

### Algebra interface

```text
canonicalize(word) -> exact coefficient, canonical word
multiply(left,right)
adjoint(word)
degree(word)
```

The initial implementation remains spin-1/2 Pauli-specific. “Generic lattice”
does not require prematurely generalizing the onsite algebra.

### Basis interface

```text
positive_basis(problem)
stationarity_basis(problem)
gap_basis(problem)
basis_manifest(problem)
```

Every entry is a canonical noncommutative state monomial
`ζ(w1)...ζ(wk)v`. The manifest records the exact selection rule, entries,
ordering, symmetry quotient, and SHA-256 hash.

The API must distinguish:

```text
complete formal basis at (L,d)
declared structured sub-basis at (L,d,basis_spec)
```

Only an exhausting nested family inherits the paper's completeness theorem.

### Assembly interface

```text
assemble_positive_matrix(problem, basis)
assemble_stationarity(problem, basis)
assemble_gap_matrix(problem, basis)
assemble_observable(problem, observable)
```

Assembly produces solver-independent sparse affine data plus an inventory. It
does not call `optimize!`.

### Solve and result interface

```text
solve(assembled_problem, optimizer_factory, tolerance_policy)
audit_result(raw_result, certificate_policy) -> GapTestResult
```

`GapTestResult.conclusion` has three values:

```text
feasible | infeasible | unknown
```

No bisection code may consume a Boolean or branch on
`status != OPTIMAL`.

## 3. Safe migration sequence

### D1. Introduce data objects and legacy wrappers

- Create `Patch`, `LocalTerm`, `BasisSpec`, `GapProblem`, and `GapTestResult`.
- Keep the four public legacy functions as wrappers.
- Make wrappers construct a `GapProblem` and select the existing legacy basis.
- Add snapshot tests for every old block size and affine-constraint count.

No numerical result should change in this step.

### D2. Separate assembly from optimization

- Return an `AssembledGapSDP` before constructing a JuMP model.
- Store PSD block dimensions, exact coefficient type, constraint inventory,
  and basis hash.
- Skip genuinely empty PSD blocks and test that doing so adds no constraint.
- Parameterize the optimizer factory; do not hard-code Mosek in model logic.

### D3. Repair deterministic algebra and constraint selection

- Replace `Float16`/`ComplexF16` intermediate coefficients with exact
  rationals where possible, otherwise `Float64`/`ComplexF64`.
- Remove randomized `filter_mons`.
- Safest first version: keep all exactly deduplicated stationarity rows.
- Later optimization: exact sparse row reduction, or a deterministic
  rank-revealing method with an audited tolerance.

Removing dependent equalities is only a performance optimization. It must
never change soundness or reproducibility.

### D4. Repair result semantics

- Preserve raw termination, primal, and dual statuses.
- Treat timeout, iteration limit, numerical error, and
  infeasible-or-unbounded as `unknown`.
- Extract a primal-infeasibility/Farkas witness for an excluded `γ`.
- Validate residuals and PSD conditions independently.
- Reserve “certified” for a witness that survives rational or interval
  post-processing.

### D5. Add Square J1-J2 geometry

- Instantiate exact NN and diagonal NNN Pauli terms.
- Use `Λ_L=[-L,L]²` and its one-layer erosion initially.
- Verify bond counts, unique support, coefficient normalization, and the
  commutator buffer before basis construction.
- Begin with no state symmetry.
- Add each optional translation/point-group/spin symmetry as an explicit
  separate mode and label its result as symmetry-restricted.

### D6. Add structured basis families

Start from a named, deterministic family rather than the impossible complete
dense basis:

```text
local bare Pauli words
+ one-state-symbol lifts needed by the variance term
+ Hamiltonian/observable-aligned two-site words
+ optional triangle/plaquette RDM blocks
```

Define an inclusion order so increasing the basis cannot accidentally drop a
previous constraint. Save the explicit list and hash.

## 4. Solver-free prototype implemented here

`src/GenericGapModel.jl` implements:

- translation-invariant Pauli interaction templates;
- exact Square J1-J2 terms with the required factor `1/4`;
- exact interaction-buffer validation from the templates;
- solver-independent `GapProblem` and `AssemblyPlan`;
- complete-formal or one-symbol basis counts without allocating an SDP;
- deterministic SHA-256 problem fingerprints;
- a compatibility exporter for upstream `ncpoly` support/coefficient arrays.

It deliberately does not:

- claim that symmetry metadata has been imposed;
- build the full state-polynomial affine matrices;
- call JuMP, Mosek, or Clarabel;
- interpret a solver status;
- produce a bulk-gap bound.

This narrow prototype tests the refactor boundary without creating a second,
unreviewed SDP implementation.

## 5. Acceptance tests before touching solver code

1. Repeated construction yields byte-identical manifests and hashes.
2. Square patch bond/term counts agree with closed-form geometry.
3. Every inner-touching interaction is fully contained in the outer patch.
4. Exported `ncpoly` coefficients equal `1/4` for J1 and `g/4` for J2.
5. Two-spin singlet/triplet and local plaquette identities pass exactly.
6. Legacy Ising/Kagome wrappers reproduce old basis/block inventories.
7. A forced timeout returns `unknown`.
8. A deliberately inconsistent toy SDP yields a validated infeasibility
   witness before the word “certified” appears anywhere in output.

Only after tests 1–6 should the Square basis be connected to SDP assembly.
Tests 7–8 gate any threshold scan.
