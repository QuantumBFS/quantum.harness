# Cross-check — Theory problems for offloading (square-lattice J1-J2 SDP gap)

> Independent attempt by the assistant as a cross-check against Sihan's model run.
> Companion to `theory-problems-for-offloading.md`. Read that first.
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

### 0.2 [SOLID] "Orthogonality to an unknown ground state" is never encoded literally — it is side-stepped by a symmetry

This is the single most important thing the code makes clear, and it is the
answer to Problem A.2. In **both** implemented models the ground state and the
first excitation lie in **different irreps of a symmetry**, so orthogonality is
automatic (Schur), and the "unknown ground state" never has to be represented.

| Model | Symmetry used to separate gs / 1st excitation | Code evidence |
|---|---|---|
| 1D TFIM | global Z₂ spin-flip (σ^z_i → −σ^z_i ∀i) | `basis = [get_basis(N,d,label=i) for i in [1,2]]`, `reduce_mirror` |
| Kagome Heisenberg | triangle permutation + sign | `reduce_perm`, `get_kagome_basis(...,label=i)` |
| **Square J1-J2 Heisenberg (target)** | **SU(2) spin: gs is S=0 singlet, 1st exc. is S=1 triplet** | not yet implemented; this is the derivation gap |

So Problem A.2 for the square Heisenberg reduces to: **block-diagonalize the
moment matrix into SU(2) spin sectors, keep S=1 for the gap matrix.** The
Casimir S²_tot does this. This is standard angular-momentum algebra, not an open
problem — see §3 below.

---

## 1. Problem B — Strengthening identities for the square lattice  [mostly SOLID]

This is the part I can deliver with highest confidence: it is spin-1/2 angular
momentum algebra, derivable from scratch and verifiable on product states. I
verified every identity below two ways (Casimir/eigenvalue argument + evaluation
on |↑…↑⟩).

Notation: X_{ij} := S⃗_i·S⃗_j. For two spin-1/2, eigenvalues of X_{ij} are
−3/4 (singlet) and +1/4 (triplet).

### B1 [SOLID] Bond identity (degree 4, always applies, **highest value**)

$$
(X_{ij})^2 = \frac{3}{16} - \frac{1}{2} X_{ij}.
$$

*Derivation.* Minimal polynomial of X_{ij}: (X_{ij}+3/4)(X_{ij}−1/4)=0 ⇒
X_{ij}² = 3/16 − X_{ij}/2. Equivalent to P⁽⁰⁾=1/4−X_{ij}, P⁽¹⁾=3/4+X_{ij}
being idempotent and mutually orthogonal (P⁽⁰⁾+P⁽¹⁾=1).

*Why it tightens:* pins the degree-4 moment y[(S⃗_i·S⃗_j)²] to the degree-2
moment y[X_{ij}]. In a raw level-d≥2 relaxation these are independent variables;
this identity removes one DOF per bond. Apply on **every** bond (J1 and J2).

### B2 [SOLID] Triangle sum identity (degree 4, applies to J1-J2 because of J2 diagonals)

For any three spin-1/2 sites {1,2,3}:
$$
\bigl(X_{12}+X_{23}+X_{31}\bigr)^2 = \frac{9}{16}.
$$

*Derivation.* S_tot = S_1+S_2+S_3 ⇒ S_tot² = 9/4 + 2σ₃ with
σ₃ := X_{12}+X_{23}+X_{31}. For 3 spin-1/2, S_tot ∈ {1/2, 3/2} ⇒ S_tot² ∈
{3/4, 15/4} ⇒ σ₃ ∈ {−3/4, +3/4} ⇒ σ₃² = 9/16.

*Crucial lattice point:* **the pure-J1 square lattice has no 3-site loops**, so
σ₃ never appears and this identity is vacuous at g=0. The moment you turn on J2,
each plaquette contains four right triangles (two J1 edges + one J2 diagonal),
so σ₃ identities become live and are **the J2-specific strengthening** the note
asks for in B.4. This is the cleanest answer to "Do J2 bonds create new
polynomial structures?": yes — they create 3-loops, which activate the triangle
identity.

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
(i, i+x̂, i+2x̂): pins a degree-4 moment involving a J3 (next-next-neighbor)
operator X_{i,i+2x̂} to a J1 bond — free tightening whenever that J3 moment
appears in M_d.

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

### B.5 [SOLID] Prioritization (direct answer to the note's deliverable)

In expected tightening-per-SDP-cost order, feed these to the moment vector as
**linear equality constraints** y[LHS] = y[RHS]:

1. **B1 on every bond** — always on, biggest win, degree 4.
2. **B2 on every J1-J1-J2 triangle** — the J2-specific win, degree 4.
3. **B3 on every collinear J1-J1-J3 triple** — free degree-4 tightening.
4. **B4 on every plaquette** — only if you can afford d≥3.

The kagome projector identity quoted in the note (with the (4/3)(S⃗i·S⃗j)(S⃗i·S⃗k)
terms) is the *expansion* of B2+B3 for that geometry; the compact forms above
are easier to emit from code.

---

## 2. Problem A — Gap-certification SDP for square J1-J2

### A.1 [CODE + SOLID] Moment-matrix structure

At relaxation level d, the moment matrix M_d is indexed by NC monomials in
{S_i^α : i=1..N, α∈{x,y,z}} of total degree ≤ d, reduced by the on-site rule
(S_i^α)² = 1/4. Concretely the code builds two blocks per symmetry sector:
`get_basis(N, d, label=sector)` for the **ground-state moment matrix** `pos`
(level d) and `get_bulkbasis(N, d−1, ...)` for the **gap matrix** `gpos`
(level d−1, one lower because it is multiplied by H which is degree 2). The gap
SDP couples `pos` and `gpos` through a shared affine constraint vector `cons`.

For the square Heisenberg you will need sector labels = SU(2) spin sectors
(S=0 for `pos`, S=1 for `gpos`), built by projecting monomials with the Casimir
(see A.2).

### A.2 [SOLID + CODE] Orthogonality encoding — the actual answer

**The encoding is: do not encode orthogonality to the ground state; encode
membership in a different symmetry irrep.** For the square Heisenberg:

- Ground state lives in the **S_tot = 0 singlet** sector of global SU(2).
- First bulk excitation is a **S_tot = 1 triplet** (one-magnon).
- Different spin sectors ⟹ automatically orthogonal.

Implementation: add the quadratic Casimir as a localization constraint.
S²_tot = Σ_i S_i² + 2Σ_{i<j} X_{ij} = 3N/4 + 2Σ_{i<j} X_{ij}. In the gap block
require the moment vector to satisfy y[S²_tot · monomial] = S(S+1)·y[monomial]
with S=1, i.e. eigenvalue 2. This is a set of **linear** constraints on y (one
per monomial up to degree d−1), exactly analogous to how the Ising code uses
`reduce_mirror` to fix the Z₂ parity of every monomial. Block-diagonalization is
then by simultaneous diagonalization of S²_tot, lattice translations, and D₄.

⚠️ **Note the J2 caveat:** at g=0 the bipartite Marshall sign symmetry (a discrete
Z₂, same family as the Ising code's `reduce_mirror`) gives a *second* natural
sector split. **J2 ≠ 0 breaks that bipartite Z₂.** SU(2) is intact for all g, so
build the orthogonality on SU(2), not on the Marshall sign. If you additionally
want to use the Marshall block structure, restrict it to the g=0 run only.

### A.3 [INFERENCE — calibrate before trusting] Bisection protocol & status semantics

Mechanics, read from the code: at a fixed candidate γ, the SDP maximizes a slack
λ (`@variable λ; cons[1] += λ; @objective Max λ; @constraint cons .== 0`) with γ
entering the gap matrix as a constant shift on `gpos` (`−c*gamma` and `+gamma`
on the mirrored entry). The caller bisects on γ externally and reads
`termination_status == OPTIMAL ? 1 : 0`.

**Physical meaning — I am not 100% sure of the direction from static code
reading alone.** Two readings are consistent with the source:

- **(i)** OPTIMAL @ γ ⇒ "a state with gap ≥ γ is consistent with this
  relaxation" ⇒ γ ≤ Γ_{L,d}. Then sup{feasible γ} = Γ_{L,d} and (per challenge-88)
  Γ_{L,d} ↘ Δ_bulk **from above** → upper bound on Δ.
- **(ii)** the dual reading, OPTIMAL ⇒ certificate of gap ≥ γ ⇒ lower bound.

The challenge-88 doc states reading (i) ("certified upper bounds on the bulk
spectral gap", "Γ_{L,d} ↘ Δ_bulk"), and that is what I would bet on. **But
resolve it empirically, not from this doc:** run the **Shastry–Sutherland g=0**
benchmark where Δ_bulk = 1 exactly (product of singlets). At convergence,
- if Γ_{L,d} approaches 1 **from above** → confirms (i), upper bound;
- if from below → (ii), lower bound.

This is a one-line experiment and removes all doubt. Do it on Day 1 before
writing `certify_Heisenberg_square_gap`. Until then, treat any Γ you produce as
"an upper bound on Δ, pending g=0 calibration".

### A.4 [SOLID-ish] Scaling estimate

Moment-matrix dimension before symmetry ≈ (3N)^d / (degree-d factorial slack);
with (S_i^α)² = 1/4 it is smaller but still exponential in d. After imposing
translations (Z_L×Z_L), D₄, and SU(2), the distinct moments at degree d scale
roughly as N^{⌊d/2⌋}/|stabilizer| (very rough; the paper reaches 16×16 for
*energy* at d=2, which sets the reference point).

Concretely for the **gap** SDP (which carries two coupled matrices `pos` at d
and `gpos` at d−1, so ~2× the energy cost):

| L | N | d=2 | d=3 |
|---|---|-----|-----|
| 2 | 4  | trivial, calibration only | small |
| 3 | 9  | feasible (minutes) | large |
| 4 | 16 | feasible (the paper's energy scale) | borderline / > 10⁴ blocks |
| ≥6 | ≥36 | feasible w/ full symmetry | infeasible |

**Expectation:** the accessible frontier for the square-lattice *gap* SDP is
**L ≤ 4–6 at d = 2**, with d = 3 only at L ≤ 3. This is consistent with the
note's "matrices > 10⁴×10⁴ are expensive" rule of thumb. Extrapolation to the
thermodynamic limit then relies on Γ_{L,d}(L) converging in L at fixed d=2,
exactly as the energy-certification paper does.

---

## 3. Problem C — Symmetry block-diagonalization  [INFERENCE, brief]

Group: G = (Z_L × Z_L) ⋊ D₄ × SU(2) (translations ⋊ point group × spin).

- **Ground-state irrep:** (k=0, A₁ of D₄, S=0). Trivial everywhere.
- **First-excited irrep (the gap block):** (k=(π,π), A₁ of the little group, S=1)
  for the Néel side (g≲0.5); the ordering vector tracks the magnetic order — at
  g=0 it is unambiguously (π,π). For g≳0.5 (VBS side) the spin sector is still
  S=1 but the relevant momentum can change; this is part of what the gap
  computation is meant to *determine*, so do not hard-code it — scan momenta.
- **Block sizes:** obtain by character projection of the monomial basis at degree
  d. The dimension of the (k, S) block is roughly the number of degree-≤d
  monomials whose translation momentum is k and whose spin is S. Closed forms are
  tedious and error-prone; **do not hand-derive** — reuse the symmetry-reduction
  machinery already in `QMBCertify.jl` (it handles square-Heisenberg energy
  certification and already projects these irreps).

**Deliverable shortcut:** the block-diagonal structure for the square Heisenberg
already exists inside QMBCertify for the energy SDP; Problem C for the gap
amounts to (a) reusing that projection and (b) additionally tagging each block
by S_tot so the S=0 (`pos`) and S=1 (`gpos`) matrices can be carved out. The
representation theory itself is not new work.

---

## 4. What I am *not* asserting, and recommended next checks

- I did **not** run the code, so the OPTIMAL/INFEASIBLE direction (A.3) is
  [INFERENCE] until the g=0 Shastry–Sutherland calibration fixes it.
- I did **not** derive the closed-form block sizes (C); I recommend lifting them
  from QMBCertify rather than re-deriving.
- The identities in §1 are the parts I will defend hardest; if Sihan's model
  output disagrees with any of B1/B2/B3, the model is wrong, not the identities
  (they are textbook angular-momentum algebra, independently re-derived here and
  checked on |↑↑↑⟩).

**Suggested Day-1 calibration sequence (cheap, removes all A.3 ambiguity):**
1. `certify_Heisenberg_kagome_gap` on a tiny kagome cluster — sanity that the
   existing code path still runs.
2. **Shastry–Sutherland g=0** → must recover Δ=1; record whether Γ approaches 1
   from above or below. This single number fixes the bound direction for the rest
   of the week.
3. Square J1-J2 **g=0** at L=2,d=2 — smallest non-trivial run, exposes the
   moment-matrix size and whether SU(2) projection is correctly wired.
