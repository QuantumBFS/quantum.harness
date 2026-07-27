# Cross-check — Theory problems for offloading (square-lattice J1-J2 SDP gap)

> Independent attempt by the assistant as a cross-check against Sihan's model run.
> Companion to `theory-problems-for-offloading.md`. Read that first.
>
> **Integration status.** This note records the independent cross-check and its
> useful algebra, but its early symmetry-sector reconstruction was not the
> complete state-polynomial hierarchy. The authoritative implementation
> contract is now
> [`../square-j1j2-gap-sdp-spec.md`](../square-j1j2-gap-sdp-spec.md), with exact
> formal counts in [`../basis-counts.md`](../basis-counts.md) and exact local
> checks in [`../local-identities.md`](../local-identities.md).
>
> **Confidence markers** (the user asked that anything I write be reliable):
> - **[SOLID]** — derived from first principles below, algebraically verified, or
>   directly confirmed by reading `wangjie212/SpectralGap/src/*.jl`.
> - **[CODE]** — read in the SpectralGap source (Ising / kagome paths); the
>   square-lattice analog is my faithful translation.
> - **[INFERENCE]** — plausible reconstruction; flagged because I cannot verify
>   without running the code. Treat as a hypothesis to calibrate, not a result.
>
> **Sources I actually pulled** (working, this session):
> - arXiv:2604.01555 abstract — Wang/Jansen/Frérot/Renou/Magron/Acín, *Scalable
>   Ground-State Certification...*. Confirms it is **energy + observable**
>   certification (not the gap hierarchy).
> - **arXiv:2606.03836 abstract — Xu/Schötz/Wang/Magron/Klep/Fawzi/Renou, *The
>   bulk spectral gap is semi-decidable: a convergent family of certified upper
>   bounds*.** This is the actual gap-hierarchy paper. Its abstract settles §A.3
>   definitively: the SDP family gives **certified UPPER bounds** on Δ_bulk,
>   convergent from above; the gap is **semi-decidable** (no finite lower bound /
>   gappedness proof is possible with this method).
> - `src/sdp.jl` — `certify_Ising_gap`, `certify_Ising_gap_nosignsymmetry`,
>   `certify_Heisenberg_kagome_gap`, `certify_Heisenberg_kagome_gap_nosignsymmetry`.
> - `src/strengthening.jl` — `posepsd6!/7!/8!/9!` (Pauli-tensor PSD blocks).
> - `notes/challenge-88-sdp-spectral-gap.md` — establishes that the gap hierarchy
>   is **arXiv:2606.03836** (Xu et al.), and that **Shastry–Sutherland g=0 has
>   Δ_bulk = 1 exactly** (product of singlets). This is the calibration anchor.

---

## 0. Two framing corrections before the math

These affect how you read Problem A. Neither changes the deliverable spec, but
getting them wrong would burn implementation time.

### 0.1 [SOLID] The note's "upper bound on the gap" wording is correct, but the *method* it describes is not the method the code uses

The note (Problem A, "The open problem") says: to certify Δ ≤ γ, exhibit a state
with energy ≤ E₀ + γ orthogonal to the ground state. That is the **primal /
finite-system** route: build an excited-state trial, read off Δ ≤ ⟨H⟩_trial − E₀.

The SpectralGap code does something different (and the challenge-88 doc states
it explicitly): it postulates a **thermodynamic-limit ground state ω whose gap is
≥ γ**, asks the SDP whether such an ω is consistent with the relaxation, and
reads **infeasibility** as "no such state → Δ < γ". Maximizing feasible γ gives
Γ_{L,d} ↘ Δ_bulk. This is the Xu et al. 2606.03836 route.

Both yield **upper bounds on Δ**, but the SDP you write is not the same. The
deliverable in Problem A should target the Xu et al. / code route, not the
"exhibit an orthogonal trial state" route — otherwise you will not reproduce the
existing Ising/kagome results.

### 0.2 [CORRECTED] Orthogonality is encoded by centering, not by assuming an excitation irrep

The hierarchy does not introduce an unknown ground-state vector and does not
need a different symmetry irrep to make an excitation orthogonal. For a local
operator `a`, the gap condition contains

```text
ω(a†a) - |ω(a)|².
```

In the GNS representation this is exactly the squared norm of the component of
`π_ω(a)|Ω_ω⟩` perpendicular to the ground vector. State-polynomial variables
represent the nonlinear product `|ω(a)|²`.

Symmetry remains useful for orbit reduction and block diagonalization. It can
also force `ω(a)=0` for operators in nontrivial irreps. It is not valid,
however, to assume that the full bulk gap of frustrated J1-J2 is always in an
`S=1` sector. A low singlet/VBS excitation may be lower, and an infinite-volume
symmetry-broken KMS state need not be represented by a finite-patch
`S_total=0` vector. Keeping only `S=1` would target a spin gap or another
explicitly restricted quantity, not the unrestricted bulk gap.

---

## 1. Problem B — Strengthening identities for the square lattice  [VERIFIED]

This is the part I can deliver with highest confidence: it is spin-1/2 angular
momentum algebra, derivable from scratch. Every identity below is now verified
**three** ways: (a) Casimir/eigenvalue argument, (b) evaluation on |↑…↑⟩, and
(c) **machine-checked as an exact operator equality on the full 2ⁿ Hilbert
space** (`verify_identities.py` — Frobenius norm |LHS−RHS|_F = 0 to machine
precision for all five identities, and the eigenvalue spectra match prediction
exactly). If a model run contradicts any of B1–B4, the model is wrong.

Notation: X_{ij} := S⃗_i·S⃗_j. For two spin-1/2, eigenvalues of X_{ij} are
−3/4 (singlet) and +1/4 (triplet).

### B1 [SOLID] Bond identity (degree 4, always applies, **highest value**)

$$
(X_{ij})^2 = \frac{3}{16} - \frac{1}{2} X_{ij}.
$$

*Derivation.* Minimal polynomial of X_{ij}: (X_{ij}+3/4)(X_{ij}−1/4)=0 ⇒
X_{ij}² = 3/16 − X_{ij}/2. Equivalent to P⁽⁰⁾=1/4−X_{ij}, P⁽¹⁾=3/4+X_{ij}
being idempotent and mutually orthogonal (P⁽⁰⁾+P⁽¹⁾=1).

*Relaxation role.* In a complete Pauli quotient this equality is already
implied by canonical word reduction, so adding it again is redundant. It is a
mandatory reducer regression test. In an incomplete structured basis it may
restore a relation that the selected affine inventory would otherwise miss;
more systematically, two-site projector or RDM positivity can strengthen the
truncated relaxation.

### B2 [SOLID] Triangle sum identity (degree 4, applies to J1-J2 because of J2 diagonals)

For any three spin-1/2 sites {1,2,3}:
$$
\bigl(X_{12}+X_{23}+X_{31}\bigr)^2 = \frac{9}{16}.
$$

*Derivation.* S_tot = S_1+S_2+S_3 ⇒ S_tot² = 9/4 + 2σ₃ with
σ₃ := X_{12}+X_{23}+X_{31}. For 3 spin-1/2, S_tot ∈ {1/2, 3/2} ⇒ S_tot² ∈
{3/4, 15/4} ⇒ σ₃ ∈ {−3/4, +3/4} ⇒ σ₃² = 9/16.

*Crucial lattice point:* the identity holds for any three spin-1/2 sites,
independently of which bonds are present. J2 makes right triangles with two J1
edges and one diagonal align naturally with the local Hamiltonian, so their
projector/RDM constraints become attractive structured localizers. J2 creates
new interaction geometry, not a new onsite operator algebra.

### B3 [SOLID] Shared-site symmetric identity (degree 4, collinear triples)

For distinct sites i,j,k with j,k both bonded to i (collinear i−j−k, or any
"V" configuration):
$$
\{X_{ij},X_{ik}\} := X_{ij}X_{ik}+X_{ik}X_{ij} = \frac{1}{2} X_{jk}.
$$

*Derivation.* Use S_i^α S_i^β = (1/4)δ^{αβ} + (i/2)ε^{αβγ}S_i^γ and the fact
that different sites commute. The Hermitian (symmetrized) part collapses to
(1/4)X_{jk} per copy → (1/2)X_{jk} summed; the antisymmetric part is the purely
imaginary commutator [X_{ij},X_{ik}] = i S⃗_i·(S⃗_j×S⃗_k), which drops out of
the symmetric combination. *Verified on |↑↑↑⟩:* LHS = 1/8, RHS = (1/2)(1/4) = 1/8. ✓

*Use.* On the square lattice this applies to collinear triples
(i, i+x̂, i+2x̂) and is an exact reducer relation whenever the corresponding
degree-four product appears. It is not an additional tightening constraint in
a complete Pauli quotient; in a structured truncation its practical effect
must be measured against the declared affine inventory.

### B4 [SOLID, but high degree] Plaquette Casimir (degree 6, lower priority)

On a 4-site square plaquette, σ₄ := Σ_{i<j∈{1,2,3,4}} X_{ij} (all six pairs:
4 edges + 2 diagonals). For 4 spin-1/2, S_tot ∈ {0,1,2} ⇒ σ₄ ∈ {−3/2,−1/2,+3/2}.
Minimal polynomial:
$$
(\sigma_4+\tfrac32)(\sigma_4+\tfrac12)(\sigma_4-\tfrac32)=0
\;\Longleftrightarrow\;
\sigma_4^3+\tfrac12\sigma_4^2-\tfrac94\sigma_4-\tfrac98=0.
$$
Degree 6 in spin operators — only bites at d≥3, so unlikely to help at the
relaxation levels you can actually afford (see §A4). Note it.

### B.5 [CORRECTED] Prioritization

1. Canonicalize the Pauli algebra and use B1--B4 as exact reducer tests.
2. For a structured basis, add two-site projector/RDM positivity.
3. Add J1-J1-J2 triangle total-spin projector positivity.
4. Add four-site plaquette RDM or joint-projector blocks only when memory
   permits.
5. Do not add an equality that already reduces identically to zero merely to
   increase the affine constraint count.

The compact identities are useful for code generation and tests, but their
being exact operator identities does not by itself prove that repeating them
tightens a correctly reduced complete relaxation.

---

## 2. Problem A — Gap-certification SDP for square J1-J2

### A.1 [CORRECTED] Moment and gap matrices

The legacy code builds model-specific `pos` and `gpos` blocks from selected
Pauli words. That is an implementation pattern, not a justification for
labeling one block as an `S=0` ground sector and the other as an `S=1`
excitation sector.

The complete formulation starts from operator words and scalar state symbols
representing expectations. Positivity gives a state-polynomial moment matrix.
For a local excitation basis `v`, the gap matrix represents the Hermitian
quadratic form

```text
1/2 ω(v_i†[H,v_j] - [H,v_i†]v_j)
  - γ(ω(v_i†v_j) - conjugate(ω(v_i))ω(v_j)).
```

Both matrices share the same state-polynomial moments and Pauli reductions.
The exact finite-level inventory and degree conventions are specified in
`../square-j1j2-gap-sdp-spec.md`; a structured implementation must declare its
selected words, blocks, and fingerprint explicitly.

### A.2 [CORRECTED] Orthogonality encoding

Use the centered covariance term

```text
ω(v_i†v_j) - conjugate(ω(v_i))ω(v_j).
```

It removes the ground-vector component for every local operator without
knowing a wavefunction. SU(2), translations, and D4 may reduce the selected
word basis or define a separately reported symmetry-restricted state class.
They must not discard possible lower excitations from the unrestricted
problem. A finite-patch Casimir-sector constraint is therefore not the generic
replacement for the nonlinear state-polynomial term.

### A.3 [CONFIRMED via 2606.03836] Bound direction & status semantics

**Resolved — no longer inference.** I pulled the abstract of the gap-hierarchy
paper: arXiv:2606.03836, Xu/Schötz/Wang/Magron/Klep/Fawzi/Renou, *"The bulk
spectral gap is semi-decidable: a convergent family of certified upper bounds."*
It states unambiguously:

- the SDP family produces **certified UPPER bounds** on Δ_bulk;
- the bounds "become arbitrarily tight at the cost of more computational
  resources" — i.e. Γ_{L,d} ↘ Δ_bulk **from above**;
- the bulk spectral gap is **semi-decidable**: upper bounds are computable, but
  this method **cannot certify a finite lower bound, nor prove gappedness**.

So the note's framing ("prove Δ ≤ γ") is correct, and the upper-bound reading is
confirmed. The exact hierarchy supports rigorous upper bounds; a floating-point
solver output remains a numerical SDP bound until infeasibility and numerical
error are independently validated. A proof that the system is gapped is out of
scope for this upper-bound hierarchy. For the contested
Shastry-Sutherland `g≈0.8` point, a small validated upper bound would still be
physically meaningful because it caps how gapped the system can be.

The legacy caller maps `termination_status == OPTIMAL` to one and every other
status to zero. That is not safe certification logic. A known model can test
the assembly and expected threshold direction, but it cannot turn timeout,
iteration limit, numerical error, or an ambiguous conic status into a proof of
infeasibility. The implementation must return `feasible`, `infeasible`, or
`unknown`, retain solver residuals, and require auditable infeasibility evidence
before reporting a physical upper bound.

### A.4 [SUPERSEDED] Scaling estimate

The rough estimates in the first version are replaced by deterministic formal
counts in `../basis-counts.md`. With square patches
`Λ_L=[-L,L]²`, no symmetry quotient, and the complete formal state-polynomial
basis, representative positive-matrix dimensions are:

| L | d | sites | dimension | one dense ComplexF64 matrix |
|---:|---:|---:|---:|---:|
| 1 | 2 | 9 | 1,810 | 49.99 MiB |
| 1 | 3 | 9 | 46,450 | 32.15 GiB |
| 2 | 2 | 25 | 14,026 | 2.931 GiB |
| 2 | 3 | 25 | 1,032,626 | 15.52 TiB |

These are not solver-memory estimates; they omit affine maps, other PSD blocks,
factorization workspace, and the KKT system. Upstream hand-selected structured
bases can be much smaller, so `(L,d)` alone is not reproducible. The selection
rule and its fingerprint are part of the relaxation definition.

---

## 3. Problem C — Symmetry reduction  [CORRECTED]

The infinite lattice has translation, D4, and SU(2) automorphisms. A finite
local window is not a periodic torus, so translation invariance should be
implemented through state constraints and word orbits, not by silently
replacing the problem with `Z_L×Z_L` PBC.

For an unrestricted bulk-gap bound, the local excitation space must retain all
irreps that can contain the lowest excitation. Symmetry may block-diagonalize
that space, but all relevant blocks contribute to the PSD condition. If the
state itself is required to be SU(2)-, translation-, or D4-invariant, the
result is a symmetry-restricted bulk gap and must be labeled accordingly.

QMBCertify's square-energy symmetry code is a useful source of orbit machinery,
not a drop-in proof that an `S=0` positive block and `S=1` gap block suffice.
Block sizes must be enumerated from the exact structured state-polynomial basis
selected for this problem.

---

## 4. Recommended next checks

- Snapshot the complete legacy Ising/Kagome basis, PSD-block, and affine
  inventories before refactoring.
- Freeze a nested Square structured-basis rule and record its SHA-256
  fingerprint.
- Compare generic and legacy assembly coefficient by coefficient on an existing
  model.
- Exercise genuine feasible, genuine infeasible, forced-timeout, and numerical
  failure paths; only the first two are decisive.
- Use Shastry-Sutherland `g=0` as an analytic positive-gap assembly control, not
  as a way to relabel arbitrary solver statuses.
- Keep exact operator identities as reducer tests, then measure whether added
  projector/RDM positivity actually changes a declared structured relaxation.
