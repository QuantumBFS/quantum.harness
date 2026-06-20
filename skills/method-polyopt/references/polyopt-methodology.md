# Noncommutative Polynomial Optimization — Reproduction-Grade Methodology

Method slug: `polynomial-optimization`. Certified ground-state energy bounds (and observable
certification, Bell maxima) via the **moment-SOS / sum-of-Hermitian-squares (SOHS)** hierarchy —
the NPA hierarchy — solved as a semidefinite program (SDP), plus the **state-polynomial / tracial**
variants and the **structure-exploiting** certification used in this harness.

This file is the math/algorithm reference. Workflow, routing, software selection, and user-facing
interaction live in `skills/method-polyopt/SKILL.md`; per-package run mechanics live in
`/using-nctssos` and `/using-qmbcertify`. All math here is UTF-8 unicode (⪰ 0, ⟨·⟩, Σ, ⊗, tr, √, ≤, †).

Provenance tags on numerical anchors: **[Lit]** = verbatim from a rendered KB file (with file + line),
**[An]** = analytic from a stated definition/limit, **[Harness]** = verified empirical run in this repo.

---

## 1. Overview

### The problem

Minimize the expectation of a Hamiltonian (a Hermitian polynomial in noncommuting operators) over
*every* quantum state on *every* Hilbert space:

```
p★ = min over (H_space, X, φ)   ⟨φ | p(X) | φ⟩
     subject to   q_i(X) ⪰ 0   (operator inequalities),   ‖φ‖ = 1
```

where X = (X₁,…,Xₙ) are bounded operators on a Hilbert space `H_space` **of unspecified dimension**,
and p, q_i are Hermitian polynomials in the free ∗-algebra K⟨x, x∗⟩ (K = ℝ or ℂ). Equality
constraints e_i(X) = 0 enter as the pair e_i ⪰ 0, −e_i ⪰ 0.
(Pironio–Navascués–Acín = PNA, 0903.4368 lines 56–62, 112–120.)

Direct minimization is intractable — for a generic local Hamiltonian even deciding `p★ < 0` vs `p★ > 1`
is Turing-undecidable (Wang 2024, 2310.05844 line 181).

### Why a relaxation, and why it is *certified*

The hard object is the set of valid quantum states. Replace the state by its **moments** — the
expectation values ℓ(w) = ⟨w⟩ of operator words w — and require only the *necessary* conditions every
genuine state's moments satisfy: normalization ℓ(1) = 1, the algebra relations, and **positivity on
Hermitian squares** ℓ(p∗p) ≥ 0. The last condition is `M ⪰ 0` for the **moment matrix** M with
M_{u,v} = ℓ(u∗v). This is an SDP. Because every true state yields a feasible ℓ, the SDP optimum is a
**one-sided certificate**: a rigorous *lower* bound on a minimum (upper on a maximum), no matter the
solver heuristics. (PNA Lemma 1, lines 154–174; Burgdorf–Klep–Povh = BKP, Lemma 1.44.)

Two things are approximated, and they are independent:
1. **The relaxation.** A finite word basis gives a loose bound; enlarging the basis adds PSD
   constraints and tightens the bound **monotonically** (PNA Thm 1, line 188: pᵏ ≤ pᵏ⁺¹ ≤ p★).
2. **The numerics.** The interior-point solver returns the bound to finite precision. The digits you
   may claim are capped by the solver **residuals** (how exactly the returned point satisfies the
   constraints), not by printed decimals. A slightly infeasible "OPTIMAL" point can report a bound
   *above* the true optimum; beyond-residual claims need exact rational post-processing.

### Certified vs heuristic — the bracket

Every other harness method returns an *estimate* (variational upper bound, stochastic mean, finite-size
value). PolyOpt returns the rigorous *lower* half of the bracket E_lb ≤ E₀ ≤ E_var. It is a partner to
DMRG/QMC/VMC, not a competitor. No sign problem — frustrated spins and fermions are equally admissible.
Observable certification even *consumes* a variational upper bound as input (§7).

---

## 2. The NPA / moment-SOS hierarchy

### Words, the moment matrix, localizing matrices

Let W_d = all words of length ≤ d in the generators (a **monomial basis**). For 2n free generators
|W_d| = ((2n)^{d+1} − 1)/(2n − 1); for n Hermitian generators |W_d| = (n^{d+1} − 1)/(n − 1)
(PNA line 104, 416). A linear functional ℓ : K⟨x,x∗⟩_{2k} → K assigns a number ℓ(w) = y_w to each
word; these y_w are the **SDP decision variables**.

- **Moment matrix** of order k: rows/columns indexed by W_k,
  ```
  [M_k(y)]_{v,w} = ℓ(v∗ w) = y_{v∗w}                          (PNA eq for Mk, line 134)
  ```
- **Localizing matrix** for a constraint polynomial q = Σ_u q_u u of degree deg(q), with
  d_q = ⌈deg(q)/2⌉:
  ```
  [M_{k−d_q}(q y)]_{v,w} = ℓ(v∗ q w) = Σ_u q_u y_{v∗ u w}     (PNA eq for Mk(qy), line 140)
  ```

**Lemma (PNA Lemma 1, lines 154–174).** If y comes from a genuine state (y_w = ⟨φ| w(X) |φ⟩), then
y₁ = 1, M_k(y) ⪰ 0, and for every constraint q(X) ⪰ 0 the localizing matrix M_{k−d_q}(q y) ⪰ 0.

### The SDP

For 2k ≥ max(deg p, max_i deg q_i), the **moment relaxation of order k** is:

```
pᵏ = min_y   Σ_w p_w y_w
     s.t.    y₁ = 1                                  (normalization)
             M_k(y) ⪰ 0                              (moment matrix PSD)
             M_{k−d_i}(q_i y) ⪰ 0,  i = 1..m         (localizing matrices, one per inequality)
             [equality e_j: M_{k−d_j}(e_j y) = 0     (both signs)]
```

(PNA relaxation Rₖ, lines 180–186.) The objective Σ_w p_w y_w is **linear** in the moments. The bound
is monotone in k (a higher-order moment/localizing PSD constraint implies the lower-order ones):
pᵏ ≤ pᵏ′ for k ≤ k′.

### The dual SOHS view — what you actually solve

The SDP dual is a **sum-of-Hermitian-squares** certificate. A feasible dual point exhibits

```
p(X) − λ = Σ_j b_j∗ b_j  +  Σ_i Σ_j c_{ij}∗ q_i c_{ij}      (PNA eq 27, line 354;  BKP eq 4.6)
```

with b_j, c_{ij} polynomials. Any such decomposition proves p(X) ⪰ λ on the constraint set, so
λ ≤ p★. By the **Gram representation** (BKP Prop 1.16), an SOHS of degree ≤ 2d is exactly
f = W_d∗ G W_d for some G ⪰ 0 (rank-r G → r squares via Cholesky). The dual is preferred in practice:
fewer linear constraints, same optimum, **no duality gap** under Slater feasibility (the moment matrix
has unit diagonal → strictly feasible). Wang 2024 (line 922) and the harness both solve the dual SOHS
problem. (PNA Appendix B, lines 766–784; BKP §1.13, Thm 1.76.)

### Convergence

**Theorem (PNA Thm 1, line 188).** If the quadratic module M_Q is **Archimedean** — there is a
constant C with C² − Σ_i x_i∗ x_i ∈ M_Q, equivalently the feasible operators are uniformly bounded —
then lim_{k→∞} pᵏ = p★. For physical problems boundedness is automatic (spins, projectors); for free
variables add the ball constraint C² − Σ_i X_i∗ X_i ⪰ 0 to force it (PNA lines 120, 190).

The dual route to the same fact is the **Helton–McCullough Positivstellensatz** (BKP Thm 1.32): if M_Q
is Archimedean and f(A) ⪰ 0 on the constraint set, then f ∈ M_Q. The unconstrained special case is
**Helton's theorem** (BKP Thm 1.30): an NC polynomial is positive on all symmetric-matrix tuples **iff**
it is SOHS — so for *unconstrained* eigenvalue minimization a **single SDP** suffices, no hierarchy
(BKP Cor 4.2). This is the key NC-vs-commutative asymmetry; the commutative case needs the full ladder.

---

## 3. Algebra setup — how operator relations enter

The algebra is a *free win*: richer relations shrink the basis **and** tighten the bound at fixed order.
Pick the most specific algebra the operators obey. Relations enter as **equality constraints** that are
folded into a **normal form** — a Gröbner-style reduction to a canonical basis of the quotient ring
K⟨x⟩/I, where I is the ideal of the relations (PNA §3.5, lines 388–412).

| Operators | Algebra | Relations enforced | Notes |
|---|---|---|---|
| Pauli σ^x,σ^y,σ^z on spin-½ | **Pauli** | (σ^a)² = I; σ^x σ^y = i σ^z (+ cyclic); [σ_i^a, σ_j^b] = 0, i≠j | tightest for spins; needs **complex** coefficients (the i) |
| fermionic c, c† | **Fermionic (CAR)** | {a_i, a_j†} = δ_{ij}, {a_i, a_j} = 0; particle-number fix Σ a_i† a_i = N | Hubbard, t-J; halts at order N — products of >N normal-ordered ops vanish (PNA line 724) |
| bosonic a, a† | **Bosonic (CCR)** | [a_i, a_j†] = δ_{ij} | ∞-dim Hilbert space; GNS gives finite approximations |
| ±1 measurement outcomes | **Unipotent** | U² = I only | abstract Bell observables — **not** physical spins |
| projective measurements | **Projector** | P² = P, Σ_{i∈S} E_i = I per measurement | I3322, compatibility; minimizing over projectors is exact at order 1 (PNA line 460) |
| none | **free NonCommutative** | none | add custom constraints by hand |

**Pauli normal form (the load-bearing reduction).** The replacement rules collapse any word u to
```
NF(u) = c · σ_{i₁}^{a₁} σ_{i₂}^{a₂} ⋯ σ_{i_r}^{a_r},   c ∈ {1, −1, i, −i},   i₁ < i₂ < ⋯ < i_r
```
— at most one Pauli per site, sites ascending, a scalar phase out front. The moment matrix then obeys
`⟨u⟩ = ⟨NF(u)⟩`, collapsing distinct entries onto a small set of normal-form moments. The problem
becomes min ⟨H⟩ over the quotient ring ℂ⟨{σ}⟩/I ≅ ℂ⟨Ω⟩, Ω = {NF(u)}.
(Wang 2024, 2310.05844 lines 247–265, 654; Wang 2026, 2604.01555 line 112.)

> **Sign/coefficient pitfalls.** The SDP *minimizes* — maximize f by minimizing −f and negating.
> Pauli needs ℂ (σ^x σ^y = i σ^z). Too-loose algebra (Unipotent where Pauli applies) wastes tightness;
> too-tight (Pauli where Bell's dimension-freeness is the point) is *wrong*, not merely loose.

---

## 4. Sparsity & symmetry — shrinking the SDP

The dense hierarchy blows up as (2n)^d. Three reductions make large systems feasible; the structured
certifier (`/using-qmbcertify`) automates all three for Heisenberg, the general engine
(`/using-nctssos`) offers correlative/term sparsity *or* symmetry (one lever per run).

### Basis locality (correlative sparsity)

Restrict the basis to words supported on **contiguous sites** (1D blocks, 2D compact clusters), plus a
hand-chosen set of **long-range two-body** words σ_i^a σ_{i+j}^b out to range r to capture distant
correlations:
```
B_d = {1} ∪ {contiguous words of length ≤ d} ∪ {σ_i^a σ_{i+j}^b : j = 2..r}
```
(Wang 2026, 2604.01555 lines 244–250.) This is correlative sparsity in the chordal/clique sense —
variable cliques follow the interaction graph. **The basis is chosen for the Hamiltonian**; bounding a
*non-local* observable well needs words tailored to *it* (a Hamiltonian-local basis certifies energies
tightly but leaves long-range correlators uselessly wide — up to ~265% gap at L=16, 2604.01555 Table 9).

### Term sparsity (TSSOS)

*Term sparsity* finds block structure from the monomials that actually appear, via an iterative
chordal-extension fixed point (the TSSOS construction; available in `/using-nctssos`). **Caveat:
stabilization ≠ exactness** — the term-sparsity iteration can stop growing while the bound stays
*strictly below* the dense-basis bound at the same order. (Note: the *structured* Wang papers use
correlative sparsity + symmetry, not TSSOS by name; TSSOS is the general-engine lever.)

### Symmetry — Wedderburn / group block-diagonalization

A group acting on the problem averages (Reynolds projection) the feasible functional, block-diagonalizing
the SDP. For Heisenberg the cascade is (Wang 2024 Appendix B; Wang 2026 §4.2):

1. **Sign symmetry of the model** — flipping spin axes. Each monomial gets a signature in {±1}²; the
   moment matrix splits into **4 blocks**, one per signature.
2. **Sign symmetry of the Hamiltonian** + **degree parity** — extra zeros and a further even/odd split
   per block.
3. **Conjugate symmetry** — the whole SDP can be posed over the **reals** (each complex Hermitian block
   → a real symmetric block of doubled size; BKP Lemma 4.4 mechanics).
4. **Permutation of {x,y,z}** — blocks 2,3,4 become identical, keep one (3× reduction).
5. **Translation** (PBC) — each same-type sub-block is **circulant** of size L, diagonalized by the DFT
   matrix P (ω = e^{2πi/L}); M = U D U†, U = diag(1,P,…,P). Conjugate pairing halves the count. **2D does
   two rounds** (horizontal then vertical DFT) — the new ingredient that reaches 16×16.
6. **Mirror / dihedral** — chain mirror (1D) or the full D₄ point group (2D).

**The cascade in numbers (1D Heisenberg, N=100, d=4)** — the single most load-bearing scaling result
**[Lit, 2604.01555 Table 2, lines 659–670]**:

| Stage | Max block size |
|---|---|
| Original dense SDP | 8,127,090,301 (≈ 8.1×10⁹) |
| After Pauli equalities (normal forms) | 322,029,976 (≈ 3.2×10⁸) |
| After sparsity (contiguous basis) | 12,001 |
| After symmetry (full cascade) | **31** |

The symmetry step makes the max block **N-independent** ((3^{d+1}+5)/8 for even d) — that is what
enables N=100 (1D) and 256 spins (2D). Resulting block inventory at d=4 (2310.05844 line 746): 1D — one
block of size 3r+28, N−1 of size 3r+27, 3N of size 2r+28; 2D — one of 129L+1, L−1 of 129L, 3L of 111L.

> **Symmetric-sector caveat.** Symmetry reduction is exact for *symmetric* ground states; it restricts
> to the symmetric sector. Beware at degeneracies / critical points where the ground state may break the
> symmetry.

### Strengthenings (tighten at fixed order, extra SDP size)

- **RDM positivity.** Require the k-body reduced density matrix to be PSD:
  ```
  ρ^[k] = (1/2^k) Σ_{a₁…a_k} ⟨σ_{i₁}^{a₁} ⋯ σ_{i_k}^{a_k}⟩ · σ^{a₁} ⊗ ⋯ ⊗ σ^{a_k}  ⪰ 0,  a_i ∈ {0,x,y,z}
  ```
  a 2^k × 2^k matrix, **linear in the moments** so it drops straight into the SDP (2310.05844 Appendix C,
  lines 760–766). For U(1)-symmetric (Heisenberg) models it block-diagonalizes by total magnetization:
  ρ^[k] = ⊕_m ρ^[k]_m, block size C(k, k/2+m), only m = 0..⌊k/2⌋ needed (2604.01555 §5.1). **k ≈ 8 is the
  cost/benefit sweet spot** [Lit, 2310.05844: "we notice that k = 8 achieves a good balance"].
- **State-optimality.** The ground state is an *eigenstate*, so ⟨[H, u]⟩ = 0 for any operator u — a set
  of **linear** moment constraints (keep on). There is also a **PSD** variant (a Gram condition on
  commutators with H). **PSD state-optimality destabilizes the solver in frustrated regimes** — for the
  J₁-J₂ chain at 0.1 ≤ J₂ ≤ 0.9 and for the 2D J₁-J₂ model the authors **removed** it for Mosek
  numerical issues [Lit, 2604.01555 Remark 6.1, line 977]. Drop it and re-run; do not paper over a
  stalled solve. (Linear/PSD optimality from Araújo et al. 2311.18707 / Fawzi–Fawzi–Scalet 2311.18706;
  they let you certify observables *without* an energy upper bound — 2310.05844 line 523.)

---

## 5. State-polynomial / tracial optimization

Two distinct objects share the moment machinery but differ at the *scoring functional* and one SDP
constraint.

### Trace vs state expectation

- **Eigenvalue optimization** (the default, §2): the functional is a state expectation
  ℓ(w) = ⟨φ| w(X) |φ⟩. SDP bounds the extremal eigenvalue.
- **Tracial optimization**: the functional is a normalized **trace** ℓ(w) = tr(w(X)). This converges to
  a *different* value — the von Neumann (type-II₁) optimum, tr_min — not the ground-state energy. Use it
  only to study the tracial relaxation itself, or for Bell formulations posed in a single party group.

### The transpose / cyclicity trick — what changes in the SDP

Trace is **cyclic**: tr(pq) = tr(qp). At the SDP level this is one extra family of linear constraints —
the tracial moment matrix is invariant under **cyclic equivalence** of words, not just under u∗v = w∗z:

```
Eigenvalue Hankel condition:   (H_L)_{u,v} = (H_L)_{w,z}  whenever  u∗v = w∗z
Tracial   Hankel condition:    (H_L)_{u,v} = (H_L)_{w,z}  whenever  u∗v ∼_cyc w∗z   (cyclic perm.)
```

Equivalently, the tracial dual SDP adds the single constraint **L(pq − qp) = 0 for all p, q** (trace
kills commutators). The natural tracial certificate is therefore **SOHS + commutators**:
f − λ ∼_cyc Σ_j g_j∗ g_j (cyclically equivalent to an SOHS). (BKP Def 1.50–1.57, Thm 3.10, Lemma 5.9.)

**Deep asymmetry to know.** For eigenvalue positivity, SOHS is *exact* (Helton). For trace positivity it
is only *sufficient* — there exist trace-positive polynomials not cyclically equivalent to any SOHS
(the NC Motzkin polynomial X₁X₂⁴X₁ + X₂X₁⁴X₂ − 3X₁X₂²X₁ + 1, BKP eq 1.21). So the tracial hierarchy is
genuinely a relaxation, and is **not finite in general** (contrast the eigenvalue nc-ball case, which
terminates at order d+1). Convergence of the tracial hierarchy to tr_min^{II₁} requires the type-II₁
von Neumann model; whether it equals the matrix optimum is **Connes' embedding** territory (BKP §1.10).

### Bell-inequality formulation

A Bell expression is a linear functional Σ_{ij} c_{ij} P(ij) in joint outcome probabilities
P(ij) = ⟨φ| E_i E_j |φ⟩, maximized over all quantum realizations:
```
max_{φ,E}  Σ_{ij} c_{ij} ⟨φ| E_i E_j |φ⟩
s.t.  Σ_{i∈S_k} E_i = I  (each measurement resolves identity),  E_i E_j = E_j E_i  (i,j different parties)
```
(PNA §5, lines 700–710.) This is a degree-2 instance of the general problem; the **party-wise commuting
groups** (operators of different parties commute) is the *operator* Bell formulation — the standard
quantum-mechanics choice. The *tracial* Bell formulation puts all operators in one group via the
transpose trick and converges to the (possibly different) von Neumann value — use only to study that
object. The module is Archimedean (1 − Σ_{i∈S_k} E_i² ∈ M_Q), so the hierarchy converges
(PNA line 710). **State-polynomial** objectives (products of expectations ⟨A⟩⟨B⟩, variances) wrap
operator expressions as tr(·) or s(·) = "expectation in an arbitrary state" and assemble a polynomial in
those — the trickiest setup; the API lives in `/using-nctssos`.

---

## 6. Solving & extraction

### Passing to a solver

The assembled SDP goes to an interior-point solver: **Clarabel** (open-source, NCTSSoS default) or
**Mosek** (faster, free academic license; required by QMBCertify). A complex SDP (Pauli) is reformulated
as a real SDP — either by the conjugate-symmetry block reduction (§4) or generically by splitting real
and imaginary parts (Wang 2023, arXiv:2307.11599). Solve the **dual SOHS** side (fewer constraints).

### Reading the bound — and what you may claim

The objective value at a clean OPTIMAL status is the certified bound. **Only a clean optimal status is a
certificate** — stalled / slow-progress / iteration-limited = *no bound*. The trustworthy digits = the
solver **residuals / duality gap**, not the printed decimals. A slightly infeasible point can report a
"bound" *above* the true optimum (Naceur–Wang–Magron–Acín, arXiv:2512.17713). To claim beyond the
residual level, **exact rational certification**: round the Gram blocks to ℚ, project onto the affine
SOHS identity, then shift by a rigorous minimum-eigenvalue enclosure (BKP Peyrl–Parrilo round-and-project,
Thm 1.80; needs a strictly-interior solution, and not every feasible SDP has a rational point — BKP
Example 1.79). The harness bundles this for 1D chains as `certify_qmb` (`/using-qmbcertify`).

### Optimality detection & GNS reconstruction

**Flatness / flat-extension criterion (PNA Thm 2, line 300; BKP Curto–Fialkow Thm 1.69/1.71).** If the
moment matrix stops gaining rank as order rises —
```
rank M_{k}(y) = rank M_{k−d}(y)
```
— then the bound is exact at that order (pᵏ = p★) and a finite-dimensional minimizer exists, with
dim H_space = rank M_{k−d}(y). The numerical flatness proxy is
err_flat = ‖C − Z∗A Z‖_F / (1 + ‖C‖_F + ‖Z∗A Z‖_F) (BKP eq 1.15).

**GNS construction** recovers concrete operators and a state realizing the optimal moments (PNA proof of
Thm 2, lines 308–344; BKP Algorithm 1.1):

```
GNS extraction (from a flat optimal moment matrix M):
  1. C ← linearly independent columns of M (w₁ = 1, deg w_i ≤ k);  r = rank M
  2. M̂ ← principal submatrix on those columns;  Cholesky M̂ = G∗ G
  3. for each generator i:
       Ĉ_i ← [X_i w₁, …, X_i w_r]           # shift columns by left-multiplication
       solve C Ā_i = Ĉ_i  for Ā_i
       X_i ← G Ā_i G⁻¹                       # operator in the orthonormal basis
  4. φ ← G e₁                                # the realizing state
  return (X₁,…,Xₙ), φ                        # then ℓ(w) = ⟨φ| w(X) |φ⟩
```

For the **tracial** case GNS gives a convex combination of traces ℓ(p) = Σ_j λ_j tr p(A^(j)), via a
Wedderburn block-diagonalization of the algebra (BKP Algorithm 1.2, Thm 1.71). **Pitfall:** GNS rebuilds
*a* representation realizing the moments — **not** the lattice ground state. Do not read GNS moments as
ground-state correlations.

---

## 7. Observable certification (two-sided, energy window)

To bound a ground-state observable O (not the energy), add the energy as **two localizing constraints**
and optimize O both ways:

```
o_LB = min_y  ⟨O⟩  ;   o_UB = max_y  ⟨O⟩
s.t.   M_d(y) ⪰ 0,  Pauli normal-form rules,  ⟨1⟩ = 1
       E_R ≤ ⟨H⟩ ≤ E_A         # two extra positivity (localizing) constraints
```

so o_GS ∈ [o_LB, o_UB] (Wang 2024, 2310.05844 eq 6, lines 205–211). **E_A is a variational *input*** —
the best DMRG/VMC/QMC upper bound; **E_R** is the best SDP energy lower bound. The certificate is exact
(o^∞ = o_GS) only if E_A = E_GS; in practice the certified interval **inherits the variational gap** — a
loose E_A directly loosens the interval. This is the one workflow where PolyOpt consumes another method's
estimate; plan the variational run first or pull the value from the paper.

---

## 8. Complementary advanced variants — RG / coarse-grained bootstrap

The plain hierarchy caps the relaxation order (≈ region size) at ~10–13 because the moment/marginal
object grows like d^{2n}. Two KB references keep the SDP rigorous but **compress each hierarchy object to
fixed size with a tensor-network coarse-graining map**, decoupling accuracy from the exponential cost.

- **RG lower bounds (Kull–Schuch–Dive–Navascués, 2212.03014, PRX 2024).** Start from the
  reduced-density-matrix (Anderson/LTI) hierarchy: variables ρ^(m), minimize tr(h ρ^(2)) subject to
  ρ^(m−1) = Tr_L ρ^(m) = Tr_R ρ^(m), ρ^(m) ⪰ 0. Instead of *discarding* the high-level constraint,
  *compress* it with an MPS-derived isometry W_m (bond χ = D²): ω^(m) = (I ⊗ W_m ⊗ I) ρ (I ⊗ W_m† ⊗ I),
  fixed size and still PSD. The new ingredient over plain NPA is a **renormalization-flow consistency
  condition** W_{m+1} = L_m ∘ (I ⊗ W_m) (each coarse-grainer is one RG step more than the last). Gains
  **1–2 orders of magnitude** in energy precision; effective region size jumps from n ≲ 13 to n ≈ 60–180,
  at polynomial (algebraic) cost ΔE ∝ N_vars^{−β}, β ∈ [0.59, 0.74]; solutions dual-certified.
- **Coarse-grained bootstrap (Cho et al., 2412.07837, JHEP 2026).** Bootstrap = the same convex
  positivity (RDM PSD = NPA moment matrix), plus equations of motion ⟨[H,O]⟩ = 0 and, at T=0,
  **perturbative positivity** ⟨O† [H, O]⟩ ≥ 0 — an NPA moment SDP with an added commutator block.
  Generalizes the RG idea by coarse-graining the EOM and perturbative-positivity blocks too, giving
  **two-sided bounds on any local observable** (and finite T). Reaches N ≲ 100 (energy lower bound) /
  N ≲ 20 (two-sided), vs N ≲ 10 / N ≲ 5 uncompressed. Bond dim m = 2 throughout; the broken/gapless
  phases converge slowly and sometimes need quad-precision (sdpa-dd).

These are advanced/complementary — reach for them when the plain hierarchy's order cap is the binding
constraint. Mainstream harness reproductions use §2–§7.

---

## 9. Key parameters & convergence

| Knob | Meaning | Effect |
|---|---|---|
| **Relaxation order d** | max word length in the basis | monotone tightening; SDP size grows ~×n per step; lowest order containing the objective is usually d = 2 |
| **Range r** | longest two-body word σ_i^a σ_{i+j}^b kept | the per-cost tightness lever; re-tailor to a non-local target observable |
| **Sparsity (CS/TS)** | variable cliques / monomial blocks | big SDP shrink; **TS stabilization ≠ exactness** |
| **Symmetry** | group block-diagonalization | exact for symmetric ground states; restricts to symmetric sector |
| **RDM k** | k-body RDM positivity | tightens at fixed order; **k ≈ 8** sweet spot |
| **State-optimality** | linear ⟨[H,u]⟩=0 (on) / PSD (off in frustration) | tightens; PSD breaks solvers in frustrated regimes |
| **Solver tolerance** | interior-point residuals | caps claimable digits |

**Cost wall.** Interior-point iterations (~tens) × per-iteration factorization set by the **largest PSD
blocks** and the constraint count. The reductions are the whole game (§4 cascade: 8.1×10⁹ → 31).
**Memory is the first wall** — grows ~quadratically in the constraint count. The post-reduction block
inventory is known *before* solving (assemble without solving, read block statistics — abort if a huge
dense block where many small ones are expected means the reductions did not fire).

Wall-time anchors **[Lit, 2310.05844 line 922; single Mosek core, 128 GB]**: 1D chain N=40 ≈ 3.3 h,
N=100 ≈ 12 h; 2D L=6/8/10 ≈ 1.8 / 9.7 / 21 h per parameter point. The 16×16 record took 32 cores / 1 TB.

---

## 10. Validation / benchmarks

Read the **free** signals on every run before anything costs extra compute:
- Block statistics vs expectation (did the reductions fire?).
- Solver status (clean optimal only) + residuals (the claimable digits).
- The sandwich E_lb ≤ reference, and **monotone** rise with order — a *decrease* on enlarging the basis
  is mathematically impossible and signals a modeling bug.

**Known certified anchors** (use as end-to-end checks):

| Anchor | Value | Provenance |
|---|---|---|
| Majumdar–Ghosh point, J₁-J₂ chain J₂=0.5 | E/spin = −3/8 = −0.375 **exactly** (dimer product state) | [Lit] 2604.01555 Table 4 (gap 0.000%); [An] exact NN-singlet ground state |
| CHSH Bell maximum | 2√2, exact at the **first** hierarchy level | [Lit] BKP Example 4.26; PNA |
| 1D Heisenberg chain N=100, PBC | E/spin lb = −0.4432378 vs DMRG −0.4432295 (gap 0.0019%) | [Lit] 2604.01555 Table 3 |
| 1D Heisenberg chain N=6 | E/spin = −0.467129 (matches ED/DMRG, rank r=3) | [Lit] 2310.05844 Table II |
| 2D square Heisenberg L=16 (256 spins) | E/spin lb = −0.674580 vs QMC −0.669976 (0.69% gap) | [Lit] 2604.01555 Table 8 (scale record, 32 cores/1 TB) |
| I3322 Bell | upper bounds 0.375 (s=2) → 0.2509400561 (s=4); exact value still open | [Lit] BKP Example 4.27 |

**Bound sandwich.** PolyOpt's lower bound pairs with a variational upper bound (DMRG/QMC/VMC) to bracket
E₀; a small gap certifies both. Compose with `/cross-method-check`. Caveats: certified accuracy beyond 1D
is ~10⁻³…10⁻² relative (looser than QMC/DMRG estimates — certify *alongside*, don't replace); finite-size
SDP bounds grow looser with size and **cannot be extrapolated** to the thermodynamic limit (2D long-range
order certified positive only for L ≤ 8, sign lost by L=16 — 2310.05844 / 2604.01555).

---

## 11. Reproduction-sufficiency assessment

**Verdict: the KB is sufficient to reproduce the full pipeline** — moment matrix, localizing matrices,
the SDP and its SOHS dual, bound extraction, correlative sparsity, symmetry/Wedderburn
block-diagonalization, RDM and state-optimality strengthenings, and the tracial / state-polynomial /
Bell variants — at the math/algorithm level. The six KB files cover:

- **Hierarchy + convergence + dual + GNS + flatness**: PNA 0903.4368 (definitions, Lemma 1, Thm 1/2,
  Positivstellensatz link, Bell + fermionic applications) — complete and rigorous.
- **Tracial, exact certificates, GNS/Wedderburn, no-gap conditions, pseudocode**: BKP monograph — the
  single most complete source; all algorithm boxes (1.1, 1.2, 4.2, 5.1) digested.
- **The harness's structured certification** (Pauli normal form, the symmetry cascade with exact block
  sizes, RDM k=8, energy-window observable certification, wall-time anchors): Wang 2024 + Wang 2026 —
  these *are* the QMBCertify code's own papers.
- **Advanced complementary variants** (RG / coarse-grained bootstrap): Kull 2212.03014, Cho 2412.07837.

**Gaps and how they were handled (no web fill needed):**
- Several load-bearing *display equations* in the rendered Wang papers are embedded as figure images
  (gitignored `.figures/`), so the markdown carries them only as adjacent prose. The equations were
  reconstructed from the unambiguous Pauli/NPA conventions plus the verbatim text-rendered normal-form
  and replacement rules and the markdown tables; a reproducer transcribing into runnable code should
  recover exact typography from the arXiv source or the QMBCertify repo. This does **not** block
  reproduction — the algorithm content is fully determined by the prose + BKP/PNA equations.
- Two SKILL.md claims are *not* in the cited Wang 2024 paper (flagged for accuracy, not gaps): the
  U(1)-magnetization block structure of the RDM and the PSD-state-optimality solver instability are
  stated in **Wang 2026** (2604.01555 §5.1, Remark 6.1), and this file sources them there.
- Exact rational certification mechanics are sketched in BKP (Peyrl–Parrilo) and the harness bundles the
  modern pipeline; the dedicated paper (arXiv:2512.17713) is cited but not in the KB — not required for
  the numeric certified bound, only for *exact* claims. Pull with `/download-ref` if an exact-rounding
  reproduction is the goal.

No WebFetch/WebSearch fill was necessary; the KB is internally complete for reproduction.

---

## 12. Source links

KB (relative to repo root `.knowledge/literature/polynomial-optimization/`):
- `0903.4368_convergent-relaxations-of-polynomial-optimization-problems-w.md` — PNA, *Convergent
  Relaxations of Polynomial Optimization Problems with Noncommuting Variables*, SIAM J. Opt. 20 (2010).
- `10-1007-978-3-319-33338-0.md` — Burgdorf, Klep, Povh, *Optimization of Polynomials in Non-Commuting
  Variables*, SpringerBriefs (2016).
- `2310.05844_certifying-ground-state-properties-of-many-body-systems.md` — Wang et al., PRX 14, 031006
  (2024).
- `2604.01555_scalable-ground-state-certification-of-quantum-spin-systems.md` — Wang et al. (2026),
  structured certification to 16×16.
- `2212.03014_lower-bounds-on-ground-state-energies-of-local-hamiltonians.md` — Kull, Schuch, Dive,
  Navascués, PRX (2024).
- `2412.07837_coarse-grained-bootstrap-of-quantum-many-body-systems.md` — Cho et al., JHEP (2026).

Web (not in KB; `/download-ref` if needed):
- NPA original hierarchy: Navascués, Pironio, Acín, *New J. Phys.* 10, 073013 (2008),
  https://arxiv.org/abs/0803.4290
- Exact rational certification of solver bounds: Naceur, Wang, Magron, Acín,
  https://arxiv.org/abs/2512.17713
- NC KKT / state-optimality: Araújo et al. https://arxiv.org/abs/2311.18707 ;
  Fawzi–Fawzi–Scalet https://arxiv.org/abs/2311.18706

Software (harness skills): `/using-nctssos` (NCTSSoS.jl + Clarabel/Mosek, general engine);
`/using-qmbcertify` (QMBCertify.jl + Mosek, structured Heisenberg certifier). Method/modeling decisions:
`skills/method-polyopt/SKILL.md`.
