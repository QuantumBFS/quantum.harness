# Quantum Monte Carlo — methodology reference

Reproduction-grade distillation for the two QMC routes the harness supports:

- **SSE** — stochastic series expansion with operator-loop / directed-loop updates, for
  sign-problem-free spin and boson lattice models at finite temperature (and ground
  states via large β).
- **CPMC / AFQMC** — constrained-path and phaseless auxiliary-field QMC, for ground
  states (and, in the grand-canonical form, finite temperature) of interacting fermions.

Math is UTF-8 unicode (β, Δτ, Σ, ⟨·⟩, √, ≤, ⊗, †). All numerical anchors carry a
provenance tag (*Literal* / *Analytic* / *Harness anchor*). Source paths are relative to
the repo root and listed at the end.

---

## 1. Overview

### 1.1 The two mappings

Both routes start from the imaginary-time operator e^(−βĤ) (β = 1/T) but expand it
differently.

**SSE (power series).** Expand the partition function as a Taylor series and sample the
resulting operator strings directly — *no* Trotter discretization:

```
Z = Tr e^(−βĤ) = Σ_n (β^n / n!) Σ_{S_n} ⟨α| ∏_{p} Ĥ_{a(p),b(p)} |α⟩
```

where S_n is a string of n bond operators drawn from the Hamiltonian
Ĥ = −Σ_{a,b} Ĥ_{a,b}, and |α⟩ runs over a fixed computational basis (z-basis spins). The
sum over both the string and the basis is sampled by Monte Carlo. SSE is exact at any β
(its only "cut-off" L is a bookkeeping device that never limits the sampled order n —
*Literal*, Sandvik §5.2.1, line 4214).

**AFQMC (path integral in field space).** Discretize β into L slices of width Δτ = β/L,
Trotter-split each slice, and Hubbard–Stratonovich (HS) the two-body interaction into a
fluctuating one-body field x. Each slice becomes a one-body propagator B̂(x) acting on
Slater determinants. The fermion trace is done analytically, giving a determinant:

```
Z = ∫ dX P(X) det[ I + B(x_L) ⋯ B(x_2) B(x_1) ]        (finite-T, grand canonical)
```

with X = {x_1,…,x_L} a complete field path and P(X) = ∏_l p(x_l) (*Literal*, Zhang Eq. 25,
line 719). The T=0 (ground-state) form replaces the trace by projection of a trial
determinant: |Ψ_0⟩ ∝ lim_{τ→∞} e^(−τĤ)|Ψ_T⟩ (*Literal*, Zhang Eq. 13, line 501).

### 1.2 The sign problem and when each route is sign-free

- **SSE.** The configuration weight carries a factor (−1)^(n₂), n₂ = number of
  off-diagonal operators in the string. For a **bipartite / unfrustrated** lattice a
  sublattice rotation makes every contributing weight positive — the route is sign-free.
  A frustrated loop (e.g. three off-diagonal operators on a triangle) returns the spins
  to themselves with a net minus sign → sign problem (*Literal*, Sandvik Fig. 56, line
  4256). Diagnostic: average sign must stay ≈ 1.
- **AFQMC.** For **real** B̂(x) (short-range repulsive Hubbard, spin HS) the determinant
  D(X) can go negative → *sign problem*; for **complex** B̂(x) (Coulomb / ab-initio)
  D(X) wanders in the complex plane → *phase problem*. Origin: the |Ψ₀⟩ ↔ −|Ψ₀⟩ symmetry
  splits determinant space into two degenerate halves separated by the unknown nodal
  surface ⟨Ψ₀|φ⟩ = 0; paths touching it contribute only noise, and the average sign
  ⟨s⟩ = Σ D(X) / Σ |D(X)| decays exponentially with β (*Literal*, Zhang §3, lines 739–828).

### 1.3 Scaling

| Route | Per-step cost | Memory | Notes |
|---|---|---|---|
| SSE | O(β N) per sweep (N spins) | O(β N) (string length ∝ β⟨H⟩) | sign-free → no exponential factor |
| AFQMC | O(N³) per slice × walkers (N = basis size) | O(N²) per walker | constraint restores polynomial scaling |

AFQMC without a constraint is unbiased but variance ∝ 1/⟨s⟩² ∝ e^(+cβN) — the constraint
trades that exponential wall for a (small, controllable) systematic bias.

---

## 2. SSE — stochastic series expansion

Reference algorithm: S=½ Heisenberg antiferromagnet on a bipartite lattice
(Sandvik §5.2). Generalizes to XXZ, fields, J-Q, and hard-core bosons.

### 2.1 Configuration space

Write Ĥ as a sum of **bond** operators split into diagonal (a=1) and off-diagonal (a=2)
parts, with a constant added so all matrix elements are equal and positive:

```
Ĥ_{1,b} = ¼ − S^z_{i(b)} S^z_{j(b)}        (diagonal)
Ĥ_{2,b} = ½ ( S⁺_{i(b)} S⁻_{j(b)} + S⁻_{i(b)} S⁺_{j(b)} )   (off-diagonal)
Ĥ = −J Σ_b (Ĥ_{1,b} − Ĥ_{2,b}) + const
```

The ¼ constant makes all nonzero matrix elements equal to ½, which is what lets the loop
update accept with probability 1 (*Literal*, Sandvik §5.2.1, lines 4156–4204). A
configuration is a stored basis state |α(0)⟩ plus an operator string S_L of fixed length
L (padded with unit operators Ĥ_{0,0}=I so that n ≤ L always). With all matrix elements
½, the weight of an allowed configuration depends **only on the number of operators n**:

```
W(α, S_L) = (β/2)^n (L−n)! / L!          (sign factor (−1)^(n₂) ≡ +1 if bipartite)
```

(*Literal*, Sandvik Eq. 264 region, lines 4220–4226.)

### 2.2 Diagonal update (changes n)

Sweep p = 0…L−1 through the string. At each position attempt to insert a diagonal
operator into a fill-in slot, or remove an existing diagonal operator:

- Insert [0,0]_p → [1,b]_p: pick a random bond b ∈ {1,…,N_b}; allowed only if the spins
  on bond b are **antiparallel** in the propagated state |α(p)⟩.
- Remove [1,b]_p → [0,0]_p: always geometrically allowed.

Metropolis acceptance ratios (including the N_b selection-probability imbalance):

```
P_insert([0,0] → [1,b]) = min[ 1,  N_b β / ( 2 (L − n) ) ]
P_remove([1,b] → [0,0]) = min[ 1,  2 (L − n + 1) / ( N_b β ) ]
```

where n is the operator count *before* the attempt (*Literal* prose + Eq. 265, Sandvik
lines 4362–4378; the closed form is the standard SSE acceptance ratio, *Analytic* from
W above). Off-diagonal operators are never touched here; when one is encountered the two
bond spins are flipped to keep |α(p)⟩ current. Detailed balance over a full
forward+backward sweep is exact (Sandvik line 4378).

### 2.3 Off-diagonal / operator-loop update (changes types, not n)

Off-diagonal changes must involve ≥2 operators to preserve the periodicity
|α(L)⟩ = |α(0)⟩. Local pair updates are ergodic only with open boundaries; the efficient
solution is the **operator-loop (cluster) update** built on the *linked-vertex* data
structure (each bond operator is a 4-leg "vertex"; legs are linked to the next operator
acting on the same spin).

Because the weight depends only on n, flipping a loop that swaps diagonal↔off-diagonal at
each visited vertex **leaves n (hence W) unchanged → the flip is always accepted**
(*Literal*, Sandvik lines 4406–4422). Procedure per sweep:

```
1. diagonal update sweep (Sec 2.2)         # changes n, creates the operators loops live on
2. build the linked-vertex list X()
3. for each not-yet-visited leg v0:
       trace the unique loop from v0 (follow links + cross each vertex)
       flip the whole loop with probability ½         # always valid
       mark all visited legs
4. propagate flips back into the stored state |α(0)⟩ (free spins flip with prob ½)
```

The loop is **deterministic** once operator positions are fixed; every space-time spin
belongs to exactly one loop (Sandvik line 4418). Autocorrelation with loop updates is
typically a few sweeps or less (line 4496).

### 2.4 Directed-loop update (fields, anisotropy, general models)

When matrix elements are *not* all equal — XXZ anisotropy, a magnetic field, J-Q, soft-core
bosons — a flipped loop changes the weight, so deterministic always-accept loops no longer
exist. The **directed-loop** scheme (Syljuåsen & Sandvik, PRE 66, 046701) restores
efficiency: the loop is built leg-by-leg as a "worm"-like head that, on entering a vertex
at leg e, chooses an exit leg x **stochastically** with probabilities that satisfy detailed
balance locally.

Let W_s be the weight of vertex configuration s, and let a(s, e → x) be the (unnormalized)
weight assigned to entering at leg e and exiting at leg x (which flips the spins on e and x,
turning s into a new allowed vertex s'). The **directed-loop equations** are the
detailed-balance system:

```
(closure)        Σ_x  a(s, e → x) = W_s            for every (s, e)
(reversibility)  a(s, e → x) = a(s', x → e)         # process and its reverse have equal weight
(positivity)     a(s, e → x) ≥ 0
```

(*Literal* structure, Alet–Wessel–Troyer / JQ₂ improvement papers, confirmed against
Syljuåsen–Sandvik.) The exit probability is then P(e → x) = a(s, e → x) / W_s. There are
four leg-relation classes for S=½ (Sandvik Fig. 90, line 5504): (a) continue-straight,
(b) turn, (c) jump, and (d) **bounce** (exit = entrance leg, vertex unchanged).

**Solutions are not unique** (an infinite family solves the linear system). Two canonical
choices:

- **Heat-bath solution**: a(s, e → x) ∝ W_{s'}, i.e. exit weighted by the resulting
  vertex weight. Simple, always non-negative, but generally keeps a finite bounce weight.
- **Bounce-minimizing / "no-bounce" solution**: choose the solution that drives the bounce
  weight a(s, e → e) to zero whenever the triangle inequalities among the vertex weights
  allow it. Eliminating bounces sharply reduces autocorrelation; when achievable it reduces
  the directed loop to a standard deterministic loop (Sandvik lines 5510–5518). For
  Hamiltonians where the no-bounce solution would require a negative weight, keep the
  minimal bounce.

Worked S=½ example pattern (one vertex with three open exits, weights b₁,a,b,c and field
scale h_q): the closure equations read `4h = b₁+a+b`, `3h = a+b₂+c`, `0 = b+c+b₃`, whose
bounce-minimizing solution sets the spurious channels to zero (`b=c=0`) and distributes the
rest in proportion to the field scale — exit probabilities h/(4h), 3h/(4h), … (*Literal*,
JQ₂ improvements paper). World-line directed loops obey the identical equations; SSE and
world-line directed loops differ only in bookkeeping.

### 2.5 Estimators

All from the sampled string / propagated states (*Literal*, Sandvik §5.2.4–5.2.5):

| Observable | Estimator | Source |
|---|---|---|
| Energy | ⟨Ĥ⟩ = −⟨n⟩/β + (const) | E = −⟨n⟩/β, line 4516 |
| Specific heat | C = (⟨n²⟩ − ⟨n⟩² − ⟨n⟩)/ (since ⟨Ĥ²⟩ = ⟨n(n−1)⟩/β²) | line 4516 |
| Diagonal ⟨O_z⟩ | average over propagated states |α(p)⟩ (partial-p sum allowed) | line 4518 |
| Structure factor S(q) | accumulate \|m(q)\|² over the string; q=π is the staggered case | lines 4538–4544 |
| Uniform susceptibility | χ = β(⟨M_z²⟩ − ⟨M_z⟩²); ⟨M_z⟩=0 with no field | Eq. 273, line 4582 |
| Generalized χ_AB (diagonal A,B) | SSE Kubo formula summing A(p),B(p) over the string | Eq. 272, line 4572 |
| χ for two H-terms | counts N(A),N(B) of those operators in the string | Eq. 274, line 4596 |
| **Spin stiffness / superfluid density** | **ρ_s = ⟨W_a²⟩ / β**, W_a = (N⁺_a − N⁻_a)/L_a the winding number | Eq. 280, lines 4640–4654 |

Notes on the stiffness: W_a counts (off-diagonal events transporting spin in +a) minus
(−a) across the boundary, normalized by L_a. For a d-dim L^d system ρ_s = ⟨W_a²⟩/β per
direction. For a **Heisenberg** (SU(2)) state multiply by 3/2 (rotational averaging); for
the XY model use as-is (*Literal*, line 4656). **Improved estimators** (cluster averages
over the 2^m equal-weight loop orientations) further cut variance for S(q) and χ — exact
for q=0 since total M_z is conserved (lines 4676–4698).

---

## 3. AFQMC / CPMC

Reference algorithm: ground-state CPMC for the repulsive single-band Hubbard model
(CPMC-Lab, Nguyen et al.), with the phaseless generalization for complex fields (Zhang).

### 3.1 Trotter + Hubbard–Stratonovich

Second-order Trotter per slice (Hubbard, K̂ = kinetic, V̂ = interaction):

```
e^(−Δτ Ĥ) ≈ e^(−Δτ K̂/2) · e^(−Δτ V̂) · e^(−Δτ K̂/2) + O(Δτ³ per slice, O(Δτ²) total)
```

**Hirsch discrete spin HS** for the on-site Hubbard repulsion (real fields, sign problem):

```
e^(−Δτ U n↑ n↓)  =  (½) Σ_{x=±1} e^( γ x (n↑ − n↓) ) · e^(−Δτ U (n↑+n↓)/2)
with   cosh γ = e^(Δτ U / 2)
```

(*Literal*, CPMC-Lab Eq. 15, lines 230–246). The field x couples to the local spin
(n↑−n↓); a charge version couples to (n↑+n↓). A **continuous Gaussian HS** is the general
form used in ab-initio AFQMC: e^(−Δτλ v̂²/2) = ∫dx (2π)^(−½) e^(−x²/2) e^(x √(−Δτλ) v̂)
(*Literal*, Zhang Eq. 10, line 436). For general two-body interactions, decompose
V_ijkl into O(N) one-body operators v̂_γ via **modified Cholesky** (tolerance δ ≈ 10⁻⁴–10⁻⁶
Hartree) or plane-wave / density-fitting (Zhang Eq. 8–9, lines 345–393). **Subtract a
mean-field background before HS** — it lowers both variance and constraint bias (Zhang
lines 484–496).

Each field configuration turns the interacting slice into a one-body propagator
B̂(x) = exp(Σ_ij c†_i U_ij c_j); by **Thouless' theorem** B̂ maps a Slater determinant to
another Slater determinant, i.e. matrix-multiply the N×N matrix B onto the N×M orbital
matrix Φ (*Literal*, Zhang Eq. 12 & App. B, lines 456, 1691–1705).

### 3.2 Ground-state projection as a branching random walk

Represent |Ψ⟩ = Σ_φ w_φ |φ⟩ by a population of weighted walkers, each a Slater determinant.
One step propagates every walker by the half-K / V(x) / half-K sandwich, sampling the
fields x. The ground-state energy uses the **mixed estimator** (exact for Ĥ and anything
commuting with it):

```
E₀ = lim_{n→∞}  ⟨Ψ_T| Ĥ |Ψ^(n)⟩ / ⟨Ψ_T|Ψ^(n)⟩
```

(*Literal*, Zhang Eq. 16, line 525). Overlaps and observables use the determinant algebra
of non-orthogonal Slater determinants: ⟨φ|φ′⟩ = det(Φ†Φ′), Green function
G_ij = ⟨φ|c_i c†_j|φ′⟩ = [ I − Φ′(Φ†Φ′)⁻¹Φ† ]_ij (*Literal*, Zhang Eq. 54, 56, lines
1724, 1739).

### 3.3 Importance sampling

Sampling fields without guidance wastes effort. Define an **importance function** from the
trial wavefunction overlap O_T(φ) = ⟨Ψ_T|φ⟩ and reweight each field choice by the ratio of
overlaps before/after the proposed propagation. For the **discrete** Hubbard HS the field
is sampled from p̂(x_i) ∝ (overlap after) and the walker weight is multiplied by
[p(x_i=+1)+p(x_i=−1)] (*Literal*, CPMC-Lab Eq. 49, lines 574–584).

For **continuous** fields the same job is done by a **force bias** — shift the Gaussian by
x̄ = v̄ to minimize weight fluctuation:

```
x̄ = v̄ ≡ −⟨Ψ_T| v̂ |φ⟩ / ⟨Ψ_T|φ⟩  ~ O(√Δτ)
w_φ′(x) = w_φ · exp( −Δτ E_L(φ) ),   E_L(φ) ≡ ⟨Ψ_T| Ĥ |φ⟩ / ⟨Ψ_T|φ⟩   (local energy form)
```

(*Literal*, Zhang Eq. 39–41, lines 1160–1174). With an exact Ψ_T the local energy E_L is a
real constant and weights stay real.

### 3.4 Constrained-path approximation (real fields)

**Exact boundary condition (thought experiment).** A partial path contributes iff its
projected partial overlap P_l({x_1…x_l}) > 0 for **all** l; the nodal surface is an
infinitely absorbing boundary, and discarding paths that cross it leaves Z exact (*Literal*,
Zhang Eq. 28–29, lines 810–854). In practice the exact propagator is unknown, so replace it
by the trial-determinant propagator and impose, for each l,

```
P_l^T = det[ I + (∏ B_T) B(x_l) ⋯ B(x_1) ] > 0          (constrained path)
```

(*Literal*, Zhang Eq. 30, line 927). Operationally the **constraint is built into the
importance sampling**: a walker whose new overlap O_T′ ≤ 0 gets weight 0 and dies; the
walker distribution then vanishes smoothly at the nodal surface (CPMC-Lab Eq. 37/46,
lines 440–446). The CP energy is **non-variational** and sits *below* the exact value;
it is **exact iff Ψ_T = Ψ₀**. Bias reduction: better/UHF/multi-determinant or
symmetry-projected Ψ_T, mean-field background subtraction, constraint release / free
projection, or a self-consistent constraint fed back from the AFQMC density matrix.

### 3.5 Phaseless approximation (complex fields)

With complex B̂(x) the force bias alone cannot stop walkers from filling the complex
overlap plane symmetrically (the phase problem). The **phaseless** prescription projects
the walk back to (near) the positive real axis by an extra cosine weight factor:

```
w_φ′  ←  w_φ′ · max{ 0, cos(Δθ) },   Δθ = phase of ⟨Ψ_T|φ′⟩/⟨Ψ_T|φ⟩ ~ O(−x Im x̄)
```

and replace E_L by Re E_L in both the weight and the energy estimator (*Literal*, Zhang
Eq. 43–44, lines 1239–1251, 1311). The phaseless mixed energy is
E₀ = Σ_φ w_φ E_L(φ) / Σ_φ w_φ. (Equivalent tested variants: exp(−(Im x̄)²/2), or
Re⟨Ψ_T|φ′⟩>0.) For **real** v̂ the cosine factor is 1 and phaseless AFQMC reduces exactly
to CPMC.

### 3.6 Back-propagation for observables

The mixed estimator is biased for any Ô that does **not** commute with Ĥ (e.g. density,
spin correlations, double occupancy). The **pure** estimate uses back-propagation: sandwich
Ô between the forward-walked ket and a bra that has been propagated *backward* over the same
field path, ⟨Ψ_T| (∏ B over the BP segment). Restoring the E_L phases along the BP path
improves complex-field observables (*Literal*, Zhang lines 1259–1273; CPMC-Lab line 524).
Alternatively, energy-derivative observables (kinetic, potential) can be obtained by
Hellmann–Feynman finite differences in U (CPMC-Lab Eq. 52, lines 688–694).

### 3.7 Population control & stabilization

- **Population control.** Branching makes total walker weight drift to 0 or ∞. Periodically
  rescale by an adaptive E_T (CPMC-Lab Eq. 50). CPMC-Lab uses simple **"combing"** that
  discards all weight history; this **biases** the result when the total weight is modified
  — reduce the bias by keeping a short weight history or by extrapolating in walker count
  (*Literal*, CPMC-Lab §II.8.1, lines 528–534).
- **Re-orthonormalization.** Repeated B-multiplies make the orbital columns numerically
  collinear. Periodically QR-factor each walker Φ = QR via **modified Gram–Schmidt**,
  replace Φ by Q and the overlap O_T by O_T/det(R) (R is discarded under importance
  sampling) (*Literal*, CPMC-Lab §II.8.2, lines 536–538).

### 3.8 Algorithm skeleton (ground-state CPMC)

```
initialize all walkers to Ψ_T, weight = 1, overlap O_T = 1
repeat for each random-walk step:
    for each walker with nonzero weight:
        propagate by B_{K/2};  update overlap;  w ← w · O_T′/O_T
        for each site i:                       # V(x) propagation
            compute p̂(x_i); sample x_i; w ← w · [p(+1)+p(−1)]
            apply b_V(x_i); update O_T, O_inv
        propagate by B_{K/2}; update overlap
        w ← w · exp(Δτ E_T)                     # population normalization
        if O_T′ ≤ 0: w ← 0                       # constraint (CPMC) / cos(Δθ) (phaseless)
    every itv_pc steps:    population control (combing)
    every itv_modsvd steps: re-orthonormalize (modified Gram–Schmidt)
    after equilibration, every itv_Em steps: measure mixed energy
report E_ave ± E_err over measurement blocks
```

(*Literal*, CPMC-Lab §III, lines 540–614.)

---

## 4. Key parameters & convergence

| Knob | SSE | AFQMC / CPMC |
|---|---|---|
| β / projection | β = 1/T grid; ground state needs a β **sweep** to a plateau, not one low-T point | projection time τ=nΔτ long enough that the mixed energy flattens; β=LΔτ for finite-T |
| Trotter Δτ | **none** (series is exact) | error ∝ Δτ²; run several Δτ (e.g. 0.025/0.05/0.1) and extrapolate Δτ→0 |
| Sweeps / walkers | sweeps & MPI chains set the error bar | N_wlk (e.g. 1000–5000); extrapolate the population-control bias in N_wlk |
| Thermalization | drop early bins (watch cut-off L stabilize) | discard equilibration blocks (N_eqblk); read τ_eq off the energy-vs-τ plateau |
| Bin size & autocorr | raise bins near criticality (loop autocorr usually ≤ few sweeps) | block length ≥ autocorrelation; pick N_blksteps so blocks are independent |
| Stabilization interval | (linked-vertex rebuilt each sweep) | re-orthonormalize every itv_modsvd (≈1–5 steps); population control every itv_pc (≈5–40) |
| Boundary / twist | PBC | twist-average (TABC) to kill PBC shell effects; keep size × #twists ≈ const |

CPMC-Lab run-parameter anchor (from the timing benchmarks): deltau=0.01, N_wlk=1000,
N_blksteps=40, N_eqblk=10, N_blk=50, itv_modsvd=5, itv_pc=40, itv_Em=40 (*Literal*,
CPMC-Lab line 741).

---

## 5. Error analysis

- **Statistical.** Bin the per-block estimates; the error bar is the standard error across
  *independent* bins. Use **jackknife** for ratios/derived quantities (energy per site,
  gaps, stiffness, Binder ratios) so correlated numerator/denominator errors propagate
  correctly. Autocorrelation inflates error bars but never biases the mean.
- **Systematic — SSE.** Essentially only finite-β (for ground-state claims) and finite-size.
  No Trotter error. Sign must stay ≈1 (else the route is uncontrolled).
- **Systematic — AFQMC.**
  - *Trotter*: ∝ Δτ² → extrapolate Δτ→0.
  - *Constrained-path / phaseless bias*: the dominant systematic; CP energy is
    non-variational (below exact). Gauge it with free-projection / constraint release, a
    better or symmetry-projected Ψ_T, or self-consistency. Do **not** quote the CP energy
    as variational.
  - *Population-control bias*: extrapolate in N_wlk or carry a weight-history correction.
  - *Mixed-estimator bias*: non-commuting observables need back-propagation.
  - *Finite size*: twist-average + extrapolate E/N vs 1/L^d.

---

## 6. Validation / benchmarks

**SSE.** Cross-check small sign-free systems against ED (`/method-ed`); compare the 2D
square-lattice Heisenberg energy/order parameter to published QMC reference values; verify
β-convergence and finite-size scaling across several L. Sign ≈ 1 throughout.

**CPMC / AFQMC.** Anchors from the CPMC-Lab paper (Hubbard, U/t=4, *t*=1):

| System | Boundary | E₀ (exact) | Provenance |
|---|---|---|---|
| 1×2, 1↑1↓ | twist (0.0819,0) | −2.44260 | *Literal*, Table I, line 718 |
| 4×1, 2↑2↓ | twist | −2.11671 | *Literal*, Table I, line 719 |
| 8×1, 4↑4↓ | twist | −4.60591 | *Literal*, Table I, line 720 |
| 2×4, 3↑2↓ | twist | −12.1210 | *Literal*, Table I, line 721 |
| 3×4, 3↑3↓ | twist | −13.9918 | *Literal*, Table I, line 722 |
| 4×4, 5↑5↓ | (0,0) | −19.58094 | *Literal*, Table I, line 723 |

Thermodynamic-limit checks (half-filled 1D chain, U/t=4):

- Energy per site → **−0.573729** (Bethe ansatz); CPMC TABC extrapolation gives
  −0.5736(1) (*Literal*, CPMC-Lab lines 791–801).
- Charge gap → **1.28673** (exact); CPMC gives 1.266(21) (*Literal*, line 821).
- In **1D**, CPMC with a good trial WF is effectively exact (matches ED across U; line 755).

**Cross-method.** Independent check via unconstrained finite-T determinant QMC (ALF or
SmoQyDQMC.jl) where the sign permits, or ED on a small lattice. CP energy *below* exact is
expected, not a guarantee of correctness.

**Compute cost anchors** (CPMC-Lab, Intel i7-2600 3.40 GHz; *Literal*, lines 739–741):

| System | MATLAB CPMC-Lab | reference FORTRAN |
|---|---|---|
| 4×4, 5↑5↓, U=4 | ≈ 32 min | ≈ 1 min |
| 128×1, 65↑63↓, U=4 | ≈ 460 min | ≈ 186 min |

CPMC-Lab is single-core MATLAB; parallelize only by farming independent runs (twists,
sizes, Δτ) as array jobs. For anything beyond small Hubbard ground states, route to a
production phaseless-AFQMC code (ipie, QMCPACK).

---

## 7. Reproduction-sufficiency assessment

**SSE — sufficient, with one gap filled from the web.** Sandvik §5.2 gives the full
configuration space, the weight W ∝ (β/2)^n, the diagonal-update acceptance ratios, the
operator-loop construction (always-accept, prob-½ flip), and every estimator
(E=−⟨n⟩/β, C, S(q), χ, **stiffness ρ_s=⟨W²⟩/β**). One genuine gap: the **directed-loop
equations** are described conceptually (four leg classes, bounce, "solutions of the
directed-loop equations") but the explicit detailed-balance system is **not written** in
the KB — Sandvik defers to Syljuåsen–Sandvik (PRE 66, 046701). Filled here from that paper
(closure + reversibility + positivity, plus heat-bath and bounce-minimizing solutions),
cross-checked against the Alet–Wessel–Troyer generalized-directed-loop and JQ₂-improvement
papers. *Caveat*: several SSE equations in the KB render as figure images
(`.figures/...png`) rather than text; the prose around them is complete enough to
reconstruct the formulas, which is what this reference does, but the verbatim equation
images were not OCR-available.

**CPMC / phaseless AFQMC — sufficient from the KB alone.** Zhang (2019) supplies the HS
transformation (Gaussian + Cholesky), ground-state projection, mixed estimator,
finite-T grand-canonical det[I+B_L⋯B_1], the exact boundary condition and its trial-WF
approximation (constrained path), the **force bias** x̄ = −⟨Ψ_T|v̂|φ⟩/⟨Ψ_T|φ⟩, the local
energy form, the **phaseless cosine projection** max{0,cos Δθ}, back-propagation, and the
non-orthogonal-determinant algebra (Thouless, overlap, Green function). CPMC-Lab adds the
Hirsch discrete HS (cosh γ = e^(ΔτU/2)), the concrete step-by-step ground-state algorithm,
combing population control, modified-Gram–Schmidt stabilization, and the exact-energy
benchmark table. No web fill needed for the fermion route.

**Net verdict:** reproduction-grade for both routes. Only the SSE directed-loop equations
required a web supplement (Syljuåsen–Sandvik, cond-mat/0202316) — recommended for ingest.

---

## 8. Source links

KB (relative to repo root):

- SSE: `.knowledge/literature/quantum-monte-carlo/1101.3281_computational-studies-of-quantum-spin-systems.md` (Sandvik 2010, §5)
- AFQMC survey: `.knowledge/literature/quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.md` (Zhang 2019)
- CPMC algorithm + benchmarks: `.knowledge/literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md` (Nguyen et al. 2014)
- QMC textbook (KB stub, abstract only — no full text): `.knowledge/literature/quantum-monte-carlo/10-1017-9781316417041.md` (Becca & Sorella 2017)

Web (directed-loop fill):

- Syljuåsen & Sandvik, "Quantum Monte Carlo with directed loops", Phys. Rev. E **66**,
  046701 (2002), arXiv:cond-mat/0202316 — https://arxiv.org/abs/cond-mat/0202316
- Alet, Wessel, Troyer, "Generalized directed loop method", arXiv:cond-mat/0308495 —
  https://arxiv.org/abs/cond-mat/0308495 (cross-check of the directed-loop equation form)
