# Exact Diagonalization — Reproduction-Grade Methodology Reference

Method slug: `ed`. This file is the *algorithm* reference distilled from the harness
knowledge base; it complements `skills/method-ed/SKILL.md`, which owns routing and
tool selection. Math is UTF-8 unicode (no LaTeX). Primary KB sources:

- Sandvik, *Computational Studies of Quantum Spin Systems* — `1101.3281` (the workhorse
  pedagogy: spin basis, momentum/parity/spin-inversion bases, Lanczos, finite-T spectra).
- Weiße & Fehske, *Exact Diagonalization Techniques* — `10-1007-978-3-540-74686-7-18`
  (fermion/Hubbard basis, translation symmetry, Lanczos, Jacobi-Davidson).
- Wietek et al., *XDiag* — `2505.02901` (modern algorithmic vocabulary: Lin tables,
  sublattice coding, spectral functions, TPQ/FTLM thermodynamics).

Two reproduction-grade ingredients are **named but not derived** anywhere in the KB —
the Lanczos continued-fraction spectral estimator and the FTLM/TPQ thermal estimators.
Those are supplied below from canonical literature; see *Reproduction-sufficiency assessment*.

---

## Overview

ED constructs an explicit finite many-body basis, represents H exactly in it (or applies
H matrix-free), and extracts eigenvalues, eigenvectors, dynamics, or thermal traces with
**no approximation beyond finite system size**. It is the gold-standard small-system oracle
and the cross-method check for DMRG/QMC/VMC/NQS.

**What it computes.** Ground and low-lying states (Lanczos/Krylov); full spectra (dense
diagonalization, for thermodynamics and level statistics); static and dynamical correlation
functions; real-time evolution; finite-T thermal averages (full spectrum, FTLM, or TPQ).

**When it applies.** Clusters small enough that the largest symmetry block fits in memory.
Practical S=½ limits: full diagonalization to N ≈ 20 spins (block dim ≲ 10⁴–10⁵); Lanczos
ground states to N ≈ 40–48 with symmetry reduction (sparse blocks up to ~10⁹–10¹⁰ with
distributed memory). [Sandvik 4.1.6, 4.2; XDiag benchmarks]

**Cost scaling.**
- Full Hilbert dim before symmetry: dim = d^N, d = local dimension (2 for S=½, 4 for a
  Hubbard/electron site, 3 for S=1, M+1 for a phonon mode truncated at M).
- Largest fixed-(N↑,N↓) Hubbard block ≈ (L choose L/2)² , a factor ≈ √(πL/2)² smaller than 4^L;
  fixed-Sz spin block = (N choose N↑). Translation gives a further ≈ 1/N; full space group ≈ 1/(N·g).
  [Weiße §18.1.3]
- **Dense diagonalization:** O(M³) time, O(M²) memory — even sparse H loses sparsity in the
  eigenvector matrix. M ≈ 10⁴ on a workstation, a few× more on a node. [Sandvik 4.1.6]
- **Lanczos:** dominated by the matrix-vector product (MVM). Sparse MVM ≈ O(nnz) ≈ O(z·M)
  per iteration (z = nonzeros/row ≈ number of Hamiltonian bonds). Memory: 2–3 state vectors
  of length M (+ stored matrix or on-the-fly apply; + all Λ vectors if reorthogonalizing).
  Λ ≈ tens–hundreds iterations for extremal eigenvalues. [Weiße §18.2.1; Sandvik 4.2]

---

## Hilbert-space & basis construction

### Local state encoding (bit representation)

Encode each product (computational-basis) state as an integer; one or more bits per site.

- **S=½ spins:** 1 bit/site, ↓=0 ↑=1, e.g. ↓↑↓↓ → 0100. [Sandvik §4.1; Weiße §18.1.6]
- **Hubbard/electrons:** 4 local states (|0⟩, ↓, ↑, ↑↓). Convention that minimizes fermion
  sign bookkeeping: store two separate L-bit integers (up channel, down channel), and order
  creation operators spin-first then site-index. Then nearest-neighbor hopping is a bit-shift
  without complicated phases (signs only at the boundary / longer-range / 2D). [Weiße §18.1.3–4]
- **S>½:** ⌈log₂(2S+1)⌉ bits/site, or pack mixed-radix. [Weiße §18.1.6]
- **Bosons/phonons:** infinite local space → truncate to ≤ M total quanta; dim = (L+M choose M).
  Shift the k=0 phonon mode (Lang-Firsov-type) to shrink the required M at strong coupling.
  [Weiße §18.1.7]

### Conserved-sector restriction

H block-diagonalizes over eigenspaces of any operator that commutes with it. Always impose
the cheap abelian charges first:

- **Total Sz / particle number:** enumerate only integers with the right popcount.
  Spin block dim = (N choose N↑) where N↑ = N/2 + Sz. Hubbard: (L choose N↑)·(L choose N↓).
  Conserving (N↑, N↓) ≡ conserving both Ne and Sz. [Weiße §18.1.2–3; Sandvik §4.1.1]
- Enumerate by sweeping all 2^N (or 4^L) integers and keeping those with the target popcount,
  or generate combinations directly (Gosper's hack / next-bit-permutation) for large N.

### Lookup / hashing (state → index)

Applying H produces a basis state; you need its index in the (sorted) basis list.

- **Small / two-channel:** a direct table of length 2^L mapping integer → index (Weiße's
  Hubbard trick: separate up/down tables, combined index n = i·(#down) + j). Fast but the
  table costs 2^L — infeasible for single-integer spin/phonon encodings of large N. [Weiße §18.1.4]
- **Sorted list + binary search:** store the sorted basis; locate by O(log M) bisection. [Sandvik §4.1.2]
- **Hash tables:** O(1) average lookup; standard for large bases. [Sandvik §4.1.2; XDiag "random-hashing"]
- **Lin tables / two-substring split:** split the bit string into two halves, tabulate each
  half's partial index, combine. Memory ~2·2^(N/2) instead of 2^N. The standard scalable lookup.
  [XDiag §"Lin table algorithms"; "sublattice coding"]

### Building the Hamiltonian matrix

For each basis state |a⟩ apply each term of H. For S=½ rewrite
**Sᵢ·Sⱼ = ½(Sᵢ⁺Sⱼ⁻ + Sᵢ⁻Sⱼ⁺) + SᵢᶻSⱼᶻ**: the diagonal SᶻSᶻ counts aligned bonds; the
ladder term flips an antiparallel pair, giving one off-diagonal element per such bond, sign-free
(spins commute on different sites). [Sandvik §4.1; Weiße eq. 18.24]
For fermions, hopping is a bit-shift; multiply by (−1)^(electrons jumped over) for the anticommutation
sign (boundary wrap, and generic processes in 2D). [Weiße §18.1.4]
Each row has ≤ (#bonds) off-diagonal entries → H is sparse; **store in CSR or apply on-the-fly**.
On-the-fly `apply` (regenerate matrix elements each MVM) trades CPU for memory and is mandatory
for the largest blocks. [Weiße §18.2.1(ii)]

---

## Symmetry adaptation

Non-abelian and lattice symmetries shrink blocks further and, crucially, **separate sectors that
must not be mixed** (level statistics are meaningless otherwise — see Pitfalls in SKILL.md).

### Momentum (translation) states

For PBC, T (translate by one site) commutes with H, T^N = 1, eigenvalues exp(−2πik/N),
k = 0,…,N−1 (lattice momentum 2πk/N). Project with

  **Pₖ = (1/N) Σ_{j=0..N−1} exp(2πi j k / N) · T^j .**     [Weiße eq. 18.14; Sandvik eq. 115]

**Representatives.** Group basis states into cycles (orbits) under T. Pick the orbit member
with the *smallest integer* as the representative |a⟩. The symmetrized (momentum) state is

  **|a(k)⟩ = (1/√(Nₐ)) Σ_{r=0..Rₐ−1} exp(2πi k r / N) · T^r |a⟩ ,**

where Rₐ = periodicity (smallest R>0 with T^R|a⟩ = |a⟩, a divisor of N) and the normalization
constant follows from ⟨a|Pₖ|a⟩. [Weiße eq. 18.17–18.21; Sandvik §4.1.3]

**Compatibility / excluded representatives.** A representative is allowed only if its momentum
is compatible with its periodicity: ⟨a|Pₖ|a⟩ ≠ 0, i.e. k·Rₐ ≡ 0 (mod N). States with
⟨a|Pₖ|a⟩ = 0 are dropped. Summing the surviving block dims over all k recovers the fixed-Sz dim.
[Weiße eqs. 18.17, around p.536; Sandvik §4.1.3]

**Reduced block Hamiltonian.** Because [H,Pₖ]=0, apply H once to the representative, then
project: each generated state |b'⟩ = Hⱼ|a⟩ is mapped to its representative |b⟩ with some number
of translations l (and the matrix element carries the phase exp(2πi k l / N) and a √(Nₐ/N_b)
normalization ratio). [Weiße eq. 18.22; Sandvik eqs. around 4.1.3] Off-diagonal blocks vanish;
each k gives an independent ~M/N matrix.

### Point-group: reflection (parity) and "semi-momentum" states

For a chain with a reflection P (and at k = 0 or π where P maps k→k), combine P with T to form
**semi-momentum states** with parity quantum number p = ±1. The representative may now appear
once or twice in the list (σ = ±1 copies); the `representative` subroutine returns both the orbit
leader and the translation/reflection indices (l, q) needed to phase-correct matrix elements.
[Sandvik §4.1.4] General space-group adaptation (any abelian rep of the cluster's automorphism
group) generalizes this: a character χ_g per group element g, projector P = (1/|G|) Σ_g χ_g* g.
[XDiag §"symmetry-adapted block"]

### Spin-inversion (Z₂)

At Sz = 0, the global spin flip Z (↑↔↓ on every site) commutes with H; eigenvalue z = ±1.
Build it like parity (combine with T, P). Useful diagnostic: an Sz=0 state of total spin S has
z = +1 iff N/2 and S have the same parity, else z = −1 — so z partially labels S without computing S².
[Sandvik §4.1.5, Table 2]

### Practical ordering

Impose abelian charges (Sz / N↑,N↓) at enumeration time; impose translation/point-group/spin-inversion
at the representative-construction stage. Total spin S² is *not* used to block-diagonalize (eigenstate
construction too costly); instead compute S(S+1) afterward as a diagonal expectation, treating S² as a
long-range Heisenberg operator. [Sandvik §4.1.6 "Total spin"]

---

## Diagonalization

### Lanczos for low-lying states

Build a Krylov space {|φ₀⟩, H|φ₀⟩, H²|φ₀⟩, …} from a random start vector |φ₀⟩ (must have nonzero
overlap with the target). Orthogonalize on the fly into a tridiagonal H. **Normalized-vector
recurrence** (numerically preferred — avoids overflow of the unnormalized Nₘ):

```
choose random normalized |φ_0⟩ ;  |φ_{-1}⟩ = 0 ;  b_0 = 0
for m = 0, 1, 2, ... :
    |w⟩   = H |φ_m⟩                          # the one expensive step (MVM)
    a_m   = ⟨φ_m | w⟩                        # diagonal Lanczos coefficient
    |w⟩   = |w⟩ - a_m |φ_m⟩ - b_m |φ_{m-1}⟩  # 3-term orthogonalization
    b_{m+1} = ‖w‖
    if b_{m+1} < tol: break                  # invariant subspace found
    |φ_{m+1}⟩ = |w⟩ / b_{m+1}
```
[Sandvik eqs. 183–186 (normalized form); Weiße eqs. 18.32–18.33 (unnormalized form)]

The {aₘ} (diagonal) and {bₘ} (off-diagonal) form a real symmetric tridiagonal matrix
T_Λ = tridiag(b, a, b). Diagonalize T_Λ (LAPACK `stev`/`steqr`, negligible cost since Λ ≪ M)
to get Ritz values E_n. Extremal eigenvalues converge first, typically Λ ≈ 50–200. [Weiße §18.2.1]

**Eigenvector recovery.** Let v_n be the eigenvector of T_Λ. Then |ψ_n⟩ = Σ_{m=0}^{Λ−1} v_n(m) |φ_m⟩.
With limited memory, **re-run the recurrence from the same |φ₀⟩** accumulating Σ v_n(m)|φ_m⟩ on the
second pass (coefficients aₘ,bₘ already known). [Weiße eq. 18.34; Sandvik §4.2.2 "Eigenstates"]

**Convergence criterion.** Diagonalize T after each new vector; stop when the target Ritz value
changes by < ε between iterations, or when the residual ‖H|ψ⟩ − E|ψ⟩‖ = |b_Λ · v_n(Λ−1)| is below
tolerance (this last quantity is free from the tridiagonal data). [Sandvik §4.2.2]

**Reorthogonalization & Lanczos "ghosts".** Finite precision destroys orthogonality of {|φ_m⟩} as
Λ grows, spawning *spurious copies* of already-converged eigenvalues. For the ground state alone this
is harmless. For excited states / spectra, **full reorthogonalization**: after forming each new |φ_{m+1}⟩,
subtract its projection on all stored previous vectors,

  **|φ_{m+1}⟩ ← (|φ_{m+1}⟩ − Σ_i q_i |φ_i⟩) / norm,  q_i = ⟨φ_i|φ_{m+1}⟩**     [Sandvik eq. 188]

(stores all Λ vectors), or target excited states one at a time from start vectors orthogonalized to
converged states. Cheaper alternatives: selective/partial reorthogonalization; or thick-restart /
implicitly restarted Lanczos (ARPACK) to bound memory while keeping Λ effective large. [Sandvik §4.2.2;
Weiße §18.2.1] **Degeneracy:** plain Lanczos returns only one member of a degenerate multiplet (the start
vector fixes the combination); use block/band Lanczos or Jacobi-Davidson to resolve. [Weiße §18.2.1–2,
Fig. 18.5]

### Jacobi-Davidson (interior / degenerate states)

Davidson-type subspace expansion that, unlike Lanczos, adds a vector orthogonal to current Ritz
approximations (not a raw Krylov vector), so it resolves degeneracies and reaches interior states.
Each step: form the subspace matrix, get a Ritz pair (|u⟩, θ), residual |r⟩ = (H−θ)|u⟩; if ‖r‖
small stop, else approximately solve the *correction equation*
**(1−|u⟩⟨u|)(H−θ)(1−|u⟩⟨u|)|t⟩ = −|r⟩** (a few GMRES/QMR steps), orthogonalize |t⟩ into the subspace,
restart periodically to cap memory; project out converged states to find more. [Weiße §18.2.2, eq. 18.35]
For interior eigenstates the standard alternative is **shift-invert Lanczos** ((H−σ)⁻¹ via a sparse
solver), used only when the linear-solve memory budget is explicit. [SKILL.md Notation]

### Full (dense) diagonalization

For thermodynamics, level statistics, and all-eigenstate quantities, diagonalize each symmetry block
densely: H = U E U†, eigenvectors are the columns of U, ⟨n|A|n⟩ = [U†AU]_nn. O(M³)/O(M²). Limited to
M ≲ 10⁴ ⇒ S=½ chains to N ≈ 20. [Sandvik §4.1.6, eqs. 165–166]

---

## Observables

### Ground-state / eigenstate expectations

Implement an `apply(O, ψ)` exactly like H (bit operations on the basis). Then ⟨ψ|O|ψ⟩ = ⟨ψ|Oψ⟩.
**Residual check** every reported eigenpair: ‖apply(H,ψ) − E·ψ‖ small. [SKILL.md Verification]

### Static correlation functions & structure factor

Equal-time correlators e.g. C(r) = ⟨SᵢᶻSᵢ₊ᵣᶻ⟩, and the static structure factor
**S(q) = (1/N) Σ_{i,j} e^{iq·(rᵢ−rⱼ)} ⟨SᵢᶻSⱼᶻ⟩** (real-valued; the FT of C(r)). [Sandvik §3.2 structure factor]
Total spin from S² as a long-range Heisenberg operator: S(S+1) = ⟨ψ|S²|ψ⟩. [Sandvik §4.1.6]

### Dynamical / spectral functions (continued fraction)

Target (zero-T) dynamical correlation for an operator A acting on the ground state |ψ₀⟩ (E₀):

  **I_A(ω) = Σ_n |⟨ψ_n|A|ψ₀⟩|² δ(ω − (E_n − E₀))  =  −(1/π) Im G_A(ω + E₀ + iη),**

with **G_A(z) = ⟨ψ₀| A† (z − H)⁻¹ A |ψ₀⟩.** Run a **second Lanczos** starting from the *normalized*
vector |φ₀⟩ = A|ψ₀⟩ / ‖A|ψ₀⟩‖. The Lanczos coefficients {aₙ}, {bₙ} of *this* run give G_A as a
**continued fraction** (Gagliano–Balseiro / Dagotto):

```
G_A(z) = ‖A|ψ_0⟩‖² / ( z - a_0 - b_1² / ( z - a_1 - b_2² / ( z - a_2 - b_3² / ( ... ) ) ) )
```

Evaluate at z = ω + E₀ + iη (small broadening η>0), build the fraction from the bottom up, take
A(ω) = −(1/π) Im G_A. This is the standard route for S^{zz}(k,ω) (A = S^z_k), the single-particle
Green's function G(k,ω) (A = c_k / c_k†), and σ(ω) (A = current J). [continued fraction: Gagliano &
Balseiro PRL 1987; Dagotto RMP 66, 763 (1994). KB defines the *quantities* — XDiag §4.4, eqs. 35–37 —
but not this estimator.]

### Level statistics

Within **one fully resolved symmetry sector** (all of Sz, k, p, z fixed — otherwise independent
sectors superpose and the statistics are meaningless), sort eigenvalues, form gaps sₙ = E_{n+1}−E_n,
and use the gap-ratio **rₙ = min(sₙ,s_{n−1})/max(sₙ,s_{n−1})** (no unfolding needed). ⟨r⟩ ≈ 0.386
(Poisson, integrable) vs ≈ 0.5295 (GOE, chaotic). [SKILL.md "Level-spacing ratio"; standard diagnostic]

---

## Finite temperature

For modest N, **full diagonalization of every symmetry block** gives exact thermodynamics:

  **⟨A⟩ = (1/Z) Σ_j Σ_{n=1}^{M_j} e^{−βE_{j,n}} [U_j† A_j U_j]_nn ,   Z = Σ_j Σ_n e^{−βE_{j,n}} ,**

j running over all (Sz,k,p,z) blocks. Specific heat C = (⟨H²⟩−⟨H⟩²)/T² and susceptibility
χ = (⟨m_z²⟩−⟨m_z⟩²)/T follow from energy moments; for spin-conserving models these need only the
Sz=0 sector weighted by (2S+1) multiplet degeneracies. [Sandvik §4.1.6, eqs. 167–169] Limited to
N ≈ 18–20 (S=½) by the O(M²) eigenvector storage.

For larger N, **trace-estimator (typicality) methods** replace the full spectral sum by a stochastic
trace over R random vectors |r⟩ (R ≈ 10–100), each Lanczos-diagonalized in a small Krylov space.
*(The KB names FTLM/TPQ — XDiag §4.6 — but gives no estimator; the formulas below are from the
canonical references.)*

### Finite-Temperature Lanczos Method (FTLM)

For each random vector |r⟩ run M_L Lanczos steps, get Ritz pairs (ε_i^{(r)}, |ψ_i^{(r)}⟩). Then

  **Z ≈ (D/R) Σ_{r=1}^{R} Σ_{i=0}^{M_L−1} e^{−βε_i^{(r)}} |⟨r|ψ_i^{(r)}⟩|² ,**

  **⟨A⟩ ≈ (1/Z)·(D/R) Σ_{r=1}^{R} Σ_{i,j=0}^{M_L−1} e^{−βε_i^{(r)}} ⟨r|ψ_i^{(r)}⟩ ⟨ψ_i^{(r)}|A|ψ_j^{(r)}⟩ ⟨ψ_j^{(r)}|r⟩**

(D = Hilbert/sector dimension; the D/R prefactors cancel in ⟨A⟩=numerator/Z). A convenient
diagonal-only low-temperature variant (LTLM) uses ⟨A⟩ ≈ Σ_r Σ_i e^{−βε_i} ⟨r|ψ_i⟩⟨ψ_i|A|r⟩ / Z.
Shift energies by E₀ before exponentiating to avoid overflow; M_L ≈ 50–100, R ≈ 20–100, run per
symmetry block and sum. [Jaklič & Prelovšek, PRB 49, 5065 (1994); review Prelovšek-Bonča 2013;
QuSpin example21 implements exactly this with R≈100 and bootstrap error bars.]

### Thermal Pure Quantum (TPQ) states

A single random |r⟩ approximates the *canonical* ensemble via imaginary-time evolution.
Canonical TPQ: **|β⟩ = e^{−βH/2}|r⟩** (built by Taylor/Krylov action of e^{−βH/2}); then

  **⟨A⟩_β ≈ ⟨β|A|β⟩ / ⟨β|β⟩ ,   Z(β) ≈ (D/R) Σ_r ⟨r|e^{−βH}|r⟩ ,**

averaged over R random vectors with the same bootstrap error analysis. Microcanonical TPQ instead
iterates |k+1⟩ ∝ (ℓ − H/N)|k⟩ and reads off (E,T) along the chain. TPQ and FTLM agree within their
random-vector error budgets and are the standard finite-T ED route for N beyond full diagonalization.
[Sugiura & Shimizu, PRL 108, 240401 (2012) & PRL 111, 010401 (2013); XDiag §4.6 uses both.]

---

## Key parameters & convergence

| Parameter | Role | Sensible default | Convergence signal |
|---|---|---|---|
| Λ (Lanczos iterations) | Krylov dim for eigenvalues | 50–200 | target Ritz value stable to ε; residual |b_Λ v_n(Λ−1)| < tol |
| Reorthogonalization | kills ghost eigenvalues | off for GS, **full for excited/spectra** | no spurious repeated eigenvalues |
| Sector (Sz,k,p,z) | block to target | sector of the expected GS / observable | GS sits in claimed sector; level stats need *one* full sector |
| η (spectral broadening) | δ→Lorentzian width | a few × mean level spacing | spectrum stable as η→0 with more Λ |
| M_L (FTLM Lanczos depth) | Krylov dim per random vector | 50–100 | thermodynamics stable vs M_L |
| R (random vectors) | trace-estimator samples | 20–100 (more at low T) | error bar (bootstrap) below target; FTLM≈TPQ |

---

## Validation / benchmarks

In priority order (mirrors SKILL.md Verification; opt-in per harness policy):

1. **Dimension check** — block dim vs combinatorics: spin (N choose N↑); Hubbard (L choose N↑)(L choose N↓);
   momentum blocks sum to the fixed-Sz dim. [Weiße §18.1.3; Sandvik §4.1.1]
2. **Hermiticity** — verify H = H† before diagonalizing whenever complex (momentum) or custom matrices appear.
3. **Residual** — ‖apply(H,ψ) − Eψ‖ small for every reported eigenpair.
4. **Symmetry** — measure all imposed conserved quantities on returned states; confirm the expected sector.
5. **Dense vs sparse cross-check** — on a small block compare full diagonalization against Lanczos.
6. **Exact small-system anchors:** 2-site Heisenberg E₀ = −3J/4 (singlet); N=16 S=½ chain GS is a singlet
   E₀ = −7.1422964 J in (k=0,p=+1,z=+1), first excited a k=π triplet E=−6.87210668 [Sandvik Table 2];
   1D Hubbard ring GS matches Bethe ansatz to ~10⁻¹³ at Λ≈90 [Weiße Fig. 18.4]. High-T limits:
   χ → 1/(4T), C → 3/(13 T²) for the Heisenberg chain [Sandvik §4.1.6].
7. **Sum rules** — spectral weight ∫ A(ω) dω = ⟨ψ₀|A†A|ψ₀⟩ (= ‖A|ψ₀⟩‖², the continued-fraction prefactor);
   total-Sz / particle-number sum rules on structure factors.
8. **Level-statistics check** — ratio statistic only within one fully resolved sector.
9. **Limit checks** — trivial-parameter and sign-convention limits via `.knowledge/limits.md`.

---

## Reproduction-sufficiency assessment

**Verdict: the KB is sufficient for the *core* ED pipeline; two reproduction-grade ingredients were
missing and are filled here from canonical literature.**

Fully covered by the KB (a competent programmer could reproduce from these alone):
- Basis construction — bit encoding, conserved-sector enumeration, lookup/hashing/Lin tables, sparse
  Hamiltonian assembly and on-the-fly apply. [Weiße §18.1; Sandvik §4.1.1–2; XDiag §5.1]
- Symmetry adaptation — momentum projectors, representatives, normalization, excluded states, reduced
  block Hamiltonian; reflection/semi-momentum and spin-inversion. [Weiße §18.1.5; Sandvik §4.1.3–5]
- Diagonalization — Lanczos recurrence (both forms), eigenvector recovery, convergence, ghosts and
  reorthogonalization, Jacobi-Davidson, dense diagonalization. [Weiße §18.2; Sandvik §4.2]
- Static observables and full-spectrum finite-T thermodynamics (Z, ⟨A⟩, C, χ). [Sandvik §4.1.6]

**Gaps filled from the web** (the KB *names* these but gives no estimator):
1. **Lanczos continued-fraction spectral estimator.** XDiag §4.4 defines S(k,ω), G(k,ω), σ(ω) and the
   KB notes the tridiagonal form is "convenient for spectral functions" but never writes the continued
   fraction. Supplied the explicit G_A(z) continued fraction and A(ω) = −(1/π)Im G from Gagliano–Balseiro
   PRL 59, 2999 (1987) and Dagotto RMP 66, 763 (1994).
2. **FTLM / TPQ thermal estimators.** XDiag §4.6 names "thermal pure quantum states" and "finite-temperature
   Lanczos method" only as feature labels with citations; SKILL.md explicitly lists finite-T as "out of
   current scope." Supplied the FTLM Z and ⟨A⟩ random-vector sums (Jaklič–Prelovšek PRB 49, 5065 (1994))
   and the canonical/microcanonical TPQ estimators (Sugiura–Shimizu PRL 2012/2013), cross-checked against
   the QuSpin FTLM reference implementation (R≈100, bootstrap errors).

Minor items adequately citable from the KB without web help: interior-state shift-invert (named in
SKILL.md), structure-factor definition (XDiag/Sandvik), level-ratio statistic (SKILL.md).

---

## Source links

KB (relative to repo root):
- `.knowledge/literature/ed/1101.3281_computational-studies-of-quantum-spin-systems.md` — Sandvik, basis/symmetry/Lanczos/finite-T (§4.1–4.2).
- `.knowledge/literature/ed/10-1007-978-3-540-74686-7-18.md` — Weiße & Fehske, fermion basis, translation symmetry, Lanczos, Jacobi-Davidson (§18.1–18.2).
- `.knowledge/literature/ed/2505.02901_xdiag-exact-diagonalization-for-quantum-many-body-systems.md` — Wietek et al., Lin tables, sublattice coding, spectral functions, TPQ/FTLM (§4.4, §4.6, §5.1).
- `.knowledge/literature/ed/1610.03042_quspin-a-python-package-for-dynamics-and-exact-diagonalisati.md` — QuSpin (tool reference).

Web (gap-filling references):
- E. Dagotto, *Correlated electrons in high-Tc superconductors*, Rev. Mod. Phys. **66**, 763 (1994) — DOI 10.1103/RevModPhys.66.763 (continued-fraction dynamics review).
- E. R. Gagliano & C. A. Balseiro, *Dynamical properties of quantum many-body systems at zero temperature*, Phys. Rev. Lett. **59**, 2999 (1987) — DOI 10.1103/PhysRevLett.59.2999.
- J. Jaklič & P. Prelovšek, *Lanczos method for the calculation of finite-temperature quantities…*, Phys. Rev. B **49**, 5065 (1994) — DOI 10.1103/PhysRevB.49.5065 (FTLM).
- S. Sugiura & A. Shimizu, *Thermal pure quantum states at finite temperature*, Phys. Rev. Lett. **108**, 240401 (2012) — DOI 10.1103/PhysRevLett.108.240401; and *Canonical TPQ state*, Phys. Rev. Lett. **111**, 010401 (2013) — DOI 10.1103/PhysRevLett.111.010401 (TPQ).
- QuSpin FTLM example: http://quspin.github.io/QuSpin/examples/example21.html (reference implementation cross-check).
