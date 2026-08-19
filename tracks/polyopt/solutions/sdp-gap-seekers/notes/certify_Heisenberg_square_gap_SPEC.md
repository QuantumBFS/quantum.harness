# Compatibility audit — `certify_Heisenberg_square_gap`

> **Status:** integration note, not the implementation specification.
>
> The first version of this file translated the model-specific Kagome code too
> literally. In particular, it treated a parity filter as a complete SU(2)
> sector decomposition, assumed the lowest excitation was a triplet, used a
> periodic finite lattice as the bulk window, and collapsed every non-optimal
> solver status into infeasibility. Those assumptions are not valid for the
> unrestricted hierarchy of arXiv:2606.03836.
>
> The authoritative mathematical and public-interface contract is
> [`../square-j1j2-gap-sdp-spec.md`](../square-j1j2-gap-sdp-spec.md). The
> migration sequence is
> [`../spectralgap-refactor-plan.md`](../spectralgap-refactor-plan.md).

## 1. What can be reused from the legacy code

### Pauli encoding

The upstream integer convention is reusable:

```text
site i, component α  ->  3(i-1)+α,   α=1,2,3 for X,Y,Z.
```

For spin operators `S=σ/2`,

```text
S_i·S_j = 1/4 (X_iX_j + Y_iY_j + Z_iZ_j).
```

The Square adapter in `../src/GenericGapModel.jl` produces these supports and
coefficients exactly, then exports them through `legacy_ncpoly_data` without
loading a solver.

### Pauli-word reduction

The following operations are model independent and worth extracting:

- commute factors on different sites;
- reduce same-site Pauli products with their exact complex phase;
- use deterministic canonical ordering;
- deduplicate equal affine constraints.

Randomized word hashes and `Float16` coefficient storage should not be carried
into the new assembly.

### Model-independent solver plumbing

JuMP model construction, solver selection, residual collection, and result
serialization can be shared after their interfaces are separated from
Kagome-specific geometry and basis generation. Reuse does not imply retaining
the legacy Boolean result.

## 2. What must not be copied as a correctness assumption

### A periodic `L×L` lattice is not the bulk test window

The target is an infinite-system KMS ground state. A finite patch is used only
so local commutators are finite:

```text
outer patch Λ_L = [-L,L]²,
inner patch I_L = [-(L-1),L-1]².
```

Every interaction touching `I_L` must be contained in `Λ_L`. No OBC or PBC is
assigned to the physical system. The generic adapter validates this buffer.

### Component parity is not a full SU(2) irrep label

Requiring even counts of `X`, `Y`, and `Z` is compatible with invariance under
three global π rotations. It does not by itself project an operator onto the
full SU(2)-scalar subspace, and a single `XX` word is not an SU(2) scalar:
`XX+YY+ZZ` is.

Consequently:

- a legacy `label` must be documented by its actual word-selection rule;
- it must not be renamed `S=0` or `S=1` without a representation-theoretic
  proof;
- a finite-patch `S_total²` constraint is not the generic orthogonality
  mechanism.

### The lowest bulk excitation need not be a triplet

Near the frustrated J1-J2 regime, a low singlet/VBS excitation can lie below a
triplet. Keeping only a vector block would target a spin gap, not the
unrestricted bulk gap.

The full gap condition instead centers every local operator through

```text
ω(a†a) - |ω(a)|².
```

State-polynomial variables represent this nonlinear covariance term.
Symmetries may reduce all represented blocks after the target state class is
declared, but they cannot silently delete candidate low-energy sectors.

### Non-optimal is not the same as infeasible

The legacy expression

```text
termination_status == OPTIMAL ? 1 : 0
```

mixes mathematical infeasibility with timeout, iteration limit, numerical
failure, and ambiguous conic statuses. The replacement result has three
conclusions:

```text
feasible | infeasible | unknown.
```

Only independently validated infeasibility excludes `gap ≥ γ`. A known analytic
model can check assembly and threshold direction; it cannot relabel a timeout
as a proof.

### Floating-point status is not yet a strict certificate

The exact hierarchy yields rigorous upper bounds, but the current upstream
calculations do not account for floating-point error. Until an infeasibility
witness passes rational or interval post-processing, report a numerical SDP
bound with its residuals and tolerances.

## 3. Code-ready implementation boundary

Implement in this order:

1. Snapshot legacy Ising/Kagome basis words, PSD blocks, affine constraints,
   and coefficient hashes for small published instances.
2. Freeze a deterministic, nested Square structured-basis rule. Record the
   selected words and SHA-256 fingerprint; `(L,d)` alone is insufficient.
3. Assemble the state-polynomial positivity and gap matrices from the
   specification, including the covariance products.
4. Compare a generic legacy wrapper coefficient by coefficient with the
   original Ising/Kagome assembly.
5. Add the three-way solver-result adapter and deliberately test timeout and
   numerical-failure paths.
6. Add witness extraction and independent validation before using the word
   “certified.”

The complete formal basis is not a practical default. Exact solver-free counts
in [`../basis-counts.md`](../basis-counts.md) already give dimension
`1,032,626` and raw dense storage `15.52 TiB` for `(L,d)=(2,3)`.

## 4. Existing foundation and tests

The current branch contains:

- square geometry, exact J1/J2 interaction templates, and buffer validation;
- deterministic Pauli canonicalization and basis counting;
- exact two-, three-, and four-site spin identities;
- a solver-free assembly manifest and problem fingerprint;
- an independent 9-site finite-patch ED construction oracle.

Run:

```bash
julia --startup-file=no \
  tracks/polyopt/solutions/sdp-gap-seekers/test/runtests.jl
```

These tests validate geometry, algebra, normalization, and bookkeeping. They do
not assemble an SDP or report a Square J1-J2 bulk-gap bound.
