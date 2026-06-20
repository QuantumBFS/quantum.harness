# Monte Carlo Renormalization Group — reproduction-grade methodology reference

Method slug: `monte-carlo-renormalization-group`

Scope: real-space block-spin RG on classical lattice spin models, extracting
**renormalized coupling constants** and **critical exponents** from the
eigenvalues of the linearized RG transformation matrix (the RG Jacobian). Covers
**both** Swendsen's classic MCRG (1979/1984) and the **variational / bias-potential
MCRG** of Wu & Car (2017/2018/2019). Math is UTF-8 unicode/plain throughout.

This file complements `skills/method-mcrg/SKILL.md`: the SKILL owns routing, the
knob-by-knob user-facing setup loop, and cost estimates; this file is the
standalone algorithmic record an agent with no chat history can implement from.

---

## 1. Overview

**Block-spin RG.** A classical spin model is defined by a Hamiltonian written as
a sum of couplings × operators,

    H(σ) = Σ_α K_α S_α(σ),

where σ = {σ_i} are the spins, S_α are lattice sums of spin products (S₁ = Σ_i σ_i
the magnetization, S₂ = Σ_⟨ij⟩ σ_i σ_j the nearest-neighbor sum, …) and K_α the
(dimensionless, kT-absorbed) couplings. (Sign convention: this card and the KB
write H = +Σ K_α S_α in the variational papers and H = −Σ K_α S_α in Guo-Blöte /
Swendsen; the RG matrix and exponents are convention-independent — only mind the
overall sign when reading off K′ = ±J_min, see §3 step 6.)

A **coarse-graining / block-spin transformation** σ′ = τ(σ) groups spins into
blocks (e.g. b×b) and assigns each block one coarse spin σ′ by a fixed rule,
usually the **majority rule** (with a random tie-break for even block counts).
The linear size shrinks by a factor **b** (the rescaling factor). The block spins
obey an **effective (renormalized) Hamiltonian** H′(σ′) = Σ_α K′_α S_α(σ′), with
new couplings K′. Iterating traces a flow K → K′ → K″ → … in coupling space.

**Goal.** The fixed point K* of the flow (the critical Hamiltonian) and the
**critical exponents**, read from how strongly K′ responds to a small change in K
near K* — i.e. from the eigenvalues of the linearized map ∂K′/∂K.

**Why Monte Carlo.** The exact renormalized Hamiltonian is a constrained partial
trace,

    H′(σ′) = −log Σ_σ δ(τ(σ), σ′) e^{−H(σ)},

which generically contains *infinitely many* couplings (blocking always generates
new longer-range and multi-spin terms) and is analytically intractable beyond 1D.
MC sidesteps it: one samples spin configurations from e^{−H}, applies the block
map, and measures *correlation functions* of the lattice sums — from which both
the renormalized couplings and the RG Jacobian can be reconstructed **without ever
forming H′**. There is no sign problem (classical Boltzmann weights).

**The truncation.** Both variants keep a finite short-range set of operators and
discard the rest, justified because dropped terms are short-range-small or
irrelevant to the critical behavior. The number kept is the dominant accuracy
knob.

**Two variants.**

| | Classic Swendsen MCRG | Variational (bias-potential) MCRG |
|---|---|---|
| Builds H′? | No — reads exponents from MC correlations only | Yes — H′ = −V_min from a convex fit |
| Sampling | unbiased MC on the fine spins (cluster moves help) | biased MC: a bias potential V flattens block spins → no critical slowing down |
| Truncation error | uncontrolled | estimable (residual KL of biased dist. vs target) |
| Couplings K′ | needs a separate Callen-equation inversion (Swendsen 1984) | falls out of the same optimization |
| Relation | the **zero-bias corner** of the variational scheme | reduces to Swendsen when target = the physical block distribution (V_min = 0) |

---

## 2. Classic Swendsen MCRG

*(Swendsen, PRL 42, 859 (1979); PRL 52, 1165 (1984); reviewed in Guo, Blöte &
Ren, PRE 71, 046126 (2005), whose Eqs. 1–6 are quoted below. This section was
added from the web — see §8.)*

### 2.1 The block-spin transformation

Divide the lattice into blocks and replace each block of spins {s₁, …, s_{b^d}}
by one block spin s′ drawn from a conditional probability P(s′ | s₁,…,s_{b^d}) that
defines the RG transformation. The **majority rule** sets s′ = sign(Σ s_i) (random
pick on a tie). Square lattice: b=3 (3×3 majority) avoids ties; b=2 needs a
tie-breaker. Triangular lattice (Niemeijer–van Leeuwen / Guo-Blöte): 3-site
triangles → b = √3 per step, giving more, finer steps. **Decimation** (keep one
spin per block, discard the rest) is a legal map but proliferates couplings and in
d>1 its flow does *not* reach a clean fixed point — majority is the standard.

The block spins form a new lattice of the same type; iterate. After i steps the
Hamiltonian is H^(i) with couplings K_α^(i) and lattice sums S_α^(i) measured on
the i-times-blocked configuration.

### 2.2 Renormalized correlation functions

On each MC configuration, after each blocking level, measure the lattice sums
⟨S_α^(i)⟩ and the **cross products** S_α^(i) S_β^(j) (same and adjacent levels),
accumulated over many configurations (a "cycle" = generate one critical config →
block repeatedly → measure all sums and cross products at every level).

### 2.3 The linearized RG transformation matrix

The object whose eigenvalues give the exponents is

    T_αβ^(i) ≡ ∂K_α^(i) / ∂K_β^(i−1)        (Guo-Blöte Eq. 2)

— the response of a renormalized coupling at level i to a coupling at level i−1.
T is **not measured directly**; it is reconstructed from MC correlations via the
chain rule. Define two connected-correlation matrices, both measurable by MC:

    B_αβ^(i) = ⟨⟨ S_α^(i) S_β^(i) ⟩⟩ = ⟨S_α^(i) S_β^(i)⟩ − ⟨S_α^(i)⟩⟨S_β^(i)⟩
             = ∂⟨S_α^(i)⟩ / ∂K_β^(i)        (two operators at the SAME level i; Eq. 4)

    C_αβ^(i) = ⟨⟨ S_α^(i) S_β^(i−1) ⟩⟩ = ⟨S_α^(i) S_β^(i−1)⟩ − ⟨S_α^(i)⟩⟨S_β^(i−1)⟩
             = ∂⟨S_α^(i)⟩ / ∂K_β^(i−1)      (operators at ADJACENT levels i, i−1; Eq. 5)

(The identities ∂⟨S_α⟩/∂K_β = ⟨S_α S_β⟩ − ⟨S_α⟩⟨S_β⟩ are exact: derivatives of a
Boltzmann average w.r.t. a coupling are connected correlations — Callen's identity
is the same statement.) The chain rule ∂⟨S_α^(i)⟩/∂K_β^(i−1) =
Σ_γ (∂⟨S_α^(i)⟩/∂K_γ^(i)) (∂K_γ^(i)/∂K_β^(i−1)) then gives the linear system

    Σ_{γ>0} B_αγ^(i) T_γβ^(i) = C_αβ^(i)      (Guo-Blöte Eq. 3)

i.e. **T^(i) = (B^(i))⁻¹ C^(i)**. Solve in a finite n_c-operator subspace by
inverting B and diagonalizing T. Because even (spin-flip symmetric) and odd
(antisymmetric) lattice sums do not correlate, B, C, T **block-diagonalize into
even and odd sectors** — analyze each separately. The even sector carries the
**thermal** exponent, the odd sector the **magnetic** exponent.

### 2.4 Two-lattice / large-cell matching

A single-lattice analysis is biased: after i blockings an L×L lattice has shrunk
to (L/b^i)×(L/b^i), so the level-i and level-(i−1) sums carry *different*
finite-size errors. **Two-lattice matching** (Swendsen, PRB 30, 3866 (1984);
Landau & Swendsen, PRL 46, 1437 (1981)) removes this: run the analysis on two
lattices, L×L and (L/b)×(L/b), so that the configuration blocked **n** times from
L×L has the same physical size as the one blocked **n−1** times from (L/b)×(L/b).
Matching observables (lattice sums / correlations) between these two equal-size
blocked systems makes the residual finite-size errors of two successive RG steps
**cancel**, leaving the renormalization effect clean. Equivalently (Guo-Blöte
Eq. 6), the distance δK of the simulated Hamiltonian from the fixed point is
solved from

    ⟨S_α^(p+m, n+m)⟩ − ⟨S_α^(p, n)⟩ = Σ_β [ ⟨⟨S_α^(p+m,n+m) S_β^(p+m,0)⟩⟩
                                            − ⟨⟨S_α^(p,n) S_β^(p,0)⟩⟩ ] δK_β

where S_α^(p,n) = the lattice sum after n blockings of a system that started with
p (here 3^p) spins. The Wu & Car PRL endorses exactly this two-lattice scheme as
the correct way to cancel finite-size error (1707.08683, final section).

### 2.5 From eigenvalues to exponents

At the fixed point the leading eigenvalues λ of T give the relevant RG exponents
via

    y = ln λ / ln b      (so λ = b^y)

- **Even (thermal) sector:** leading eigenvalue λ_e → thermal exponent **y_t**
  (= 1/ν). The thermal eigenvalue λ_T = b^{y_t}.
- **Odd (magnetic) sector:** leading eigenvalue λ_o → magnetic exponent **y_h**
  (= (d + 2 − η)/2). The magnetic eigenvalue λ_H = b^{y_h}.

All other standard exponents follow from y_t, y_h and hyperscaling
(α = 2 − d/y_t, β = (d − y_h)/y_t, γ = (2 y_h − d)/y_t, δ = y_h/(d − y_h),
ν = 1/y_t, η = d + 2 − 2 y_h). Subleading eigenvalues give **correction-to-scaling**
(irrelevant) exponents y_i < 0; finite-i, finite-n_c eigenvalues are extrapolated
to the fixed point (Guo-Blöte Eq. 12 fits both the renormalization approach
∝ b^{i y_i} and a finite-size series in 1/(number of sites)).

### 2.6 Renormalized couplings (Swendsen 1984)

Reading the *couplings* K′ (not just exponents) classically needs a second step:
Callen's identity rewrites each measured correlation ⟨S_α′⟩ as a function
explicitly depending on the K′; imposing that the standard MC value and the Callen
form agree gives equations whose iterative solution yields K′ (Swendsen, PRL 52,
1165). The variational variant (§3) gets K′ directly from one optimization, which
is its main practical advantage for couplings.

---

## 3. Variational / bias-potential MCRG (Wu & Car)

*(1707.08683, PRL 119, 220602 (2017) + Supplementary Material; this is the KB's
primary algorithmic source. Equation numbers below are the PRL's.)*

### 3.1 The variational principle

Near criticality the block-spin distribution p(σ′) has a diverging correlation
length, so sampling it directly suffers critical slowing down — the obstacle for
classic MCRG. The fix: add a **bias potential V(σ′)** on the block spins that
forces their biased distribution p_V toward a chosen simple **target p_t**
(usually uniform → block spins uncorrelated → fast to sample even at T_c).

V is found by minimizing the convex functional

    Ω[V] = log( Σ_σ′ e^{−[H′(σ′)+V(σ′)]} / Σ_σ′ e^{−H′(σ′)} )  +  Σ_σ′ p_t(σ′) V(σ′)   (5)

Up to a V-independent constant Ω[V] is the Kullback–Leibler divergence
KL(p_t ‖ p_V); minimizing it drives p_V → p_t. Properties (proved in Valsson &
Parrinello, PRL 113, 090601 (2014)): Ω is convex and bounded below; its minimizer
V_min is unique up to a constant; and

    H′(σ′) = −V_min(σ′) − log p_t(σ′) + const   (6),     p_{V_min}(σ′) = p_t(σ′)   (7).

**The payoff identity.** For uniform p_t the flattening bias is exactly minus the
renormalized Hamiltonian: **H′ = −V_min**. One convex optimization delivers *both*
a fast decorrelated sampler *and* the renormalized couplings. (Reason: H′ is by
construction −log of the block-spin distribution; a bias that cancels it down to a
uniform p_t must equal −H′ − log p_t.)

### 3.2 Parametrization, gradient, Hessian

Expand V in the same finite operator basis as H:

    V_J(σ′) = Σ_α J_α S_α(σ′)   (8)     → Ω convex in J.

Gradient and Hessian (both MC-measurable):

    ∂Ω/∂J_α = −⟨S_α(σ′)⟩_V + ⟨S_α(σ′)⟩_{p_t}                          (9)
    ∂²Ω/∂J_α∂J_β = ⟨S_α S_β⟩_V − ⟨S_α⟩_V ⟨S_β⟩_V   (connected, PSD)   (10)

The gradient is **target minus biased average**; it vanishes (⟨S_α⟩_V = ⟨S_α⟩_{p_t})
exactly when p_V = p_t. For uniform p_t the target averages ⟨S_α⟩_{p_t} are
analytic (independent fair coins).

### 3.3 The sampling crux

Since V depends on σ only through σ′ = τ(σ), the factor e^{−V} pulls inside the
trace: the biased block distribution is the marginal of the *fine-spin*
distribution P(σ) ∝ e^{−H(σ)} e^{−V(τ(σ))}. **In practice:** run ordinary
Metropolis (or Wolff) on the fine spins σ with weight e^{−H} e^{−V(τ(σ))}; for any
coarse operator compute σ′ = τ(σ) per sample and average. H′ and the intractable
partial trace are **never formed**.

### 3.4 Optimization

Minimize Ω(J) with **averaged stochastic gradient descent** (Bach–Moulines,
NeurIPS 2013): keep a running mean J̄_n = (1/n) Σ_{i≤n} J^[i] and build the bias
from J̄ (Eq. S2), while updating the instantaneous J by

    J^[n+1] = J^[n] − µ [ Ω′(J̄) + Ω″(J̄)(J^[n] − J̄) ]   (S3)

from the noisy gradient (9) / Hessian (10). MC sweeps per variational step are
small (~20) — the trajectory averages per-step noise out; **multiple walkers**
(independent chains, e.g. 16) cut variance ~1/n_w. Reset the running mean at 10%
and 20% of the trajectory to drop its lag (the visible jumps in J̄ curves are
these resets, **not physics**). µ shrinks with L (5×10⁻⁵ → 5×10⁻⁶). Take J̄ at the
plateau as **J_min**. (For disordered systems with many couplings, Wu & Car use
only the diagonal of the Hessian; cost grows ~linearly in the number of
coefficients — 1810.09579.)

### 3.5 Renormalized couplings and truncation control

With uniform p_t:

    K′_α = −J_min,α   (11–12)   ← mind the minus sign.

Prune operators whose |J_min,α| < 0.001 (variational truncation). Gauge the
truncation error by the residual departure of p_{V_min} from p_t (gradient not
quite zero ⇒ basis too small).

### 3.6 Jacobian and exponents

Differentiate the optimum condition (9)=0 w.r.t. the bare couplings. Perturb
K_β → K_β + δK_β; K′ responds by δK′. Linearizing (PRL Eqs. 13→15, derived in SM
§V) gives the linear system

    A_βγ = Σ_α (∂K′_α / ∂K_β) B_αγ        (15)

with **biased-ensemble** connected correlations

    A_βγ = ⟨S_β(σ) S_γ(σ′)⟩_V − ⟨S_β(σ)⟩_V ⟨S_γ(σ′)⟩_V    (16)   — FINE σ vs COARSE σ′
    B_αγ = ⟨S_α(σ′) S_γ(σ′)⟩_V − ⟨S_α(σ′)⟩_V ⟨S_γ(σ′)⟩_V   (17)   — two COARSE σ′

Solve (15) for the Jacobian ∂K′/∂K (invert B), diagonalize, read y = ln λ / ln b.
This is the **same structure as Swendsen's Eqs. (3)–(5)** — A↔C, B↔B — but with the
averages taken in the *biased* ensemble. Setting the target to the unbiased
physical block distribution makes V_min = 0 and collapses (16–17) exactly onto
Swendsen's formulae: the variational scheme **contains** classic MCRG. Spin-flip
symmetry block-diagonalizes A, B into even (thermal) and odd (magnetic) sectors —
build them block-diagonally in parity.

### 3.7 Locating K_c and evaluating there

Bracket K_c by the **flow direction** of the couplings across iterations: above
K_c they grow, below K_c they shrink; at K_c they stay constant. (2D Ising, b=3:
window 0.4355–0.4365, fixed at K_c ≈ 0.436; exact 0.4407.) Evaluate the Jacobian
at K_c — couplings after iteration 1 = K_α, after iteration 2 = K′_α. An accurate
K_c lets a **single** coarsening step give the Jacobian (and permits small blocks
with smaller statistical error).

### 3.8 Critical-manifold tangent space & curvature (Wu & Car 2019)

*(1903.08231, PRE 100, 022138.)* A bonus structure from the *same* biased
correlations. The critical manifold (set of couplings flowing to one fixed-point
field theory) has co-dimension = number of relevant operators. Its **tangent
space (CMTS)** at a critical point is the **kernel of the truncated RG Jacobian**
A^(n,0) = ∂K^(n)/∂K^(0) (Eq. 6); when marginal operators are present, the kernel of
A^(n+1,0) − A^(n,0) (Eq. 15). The Jacobian rows are normal vectors to the CMTS; the
normalized-row matrix P (Eq. 16) has identical rows for co-dimension 1, and rows
spanning a k-dim space for co-dimension k (verified on 2D tricritical Ising,
co-dim 2). **Key fact: the CMTS is truncation-error-free** (the kernel structure
survives any well-defined truncation, because irrelevant directions decay
∝ exp along the flow) — unlike the *exponents*, which remain truncation-sensitive.
**Curvature** comes from the second-order expansion (Eqs. 22–24), but each extra
derivative order raises the sampled correlation order by one (∝ N^{m+1} variance
for an m-th derivative), so only low-order geometry is practically accessible.

---

## 4. Disorder (quenched) extension

*(1810.09579, Wu & Car 2018.)* For quenched-disordered models (random-bond /
random-field / dilute), each disorder realization has its own extensive set of
random couplings K ∼ P_v(K). VMCRG renormalizes K′ = R(K) = −J_min for N_D
realizations, building the **flow of the coupling *distribution*** P_v(K) →
P_{v′}(K′), visualized as histograms Q_v(K_α) (Eq. 9). The scaling variable is now
**v** (the distribution's parameters). If the renormalized couplings stay
short-range-correlated, expand −log P_v(K) = C + Σ_β v_β U_β(K) in correlation
basis functions U_β (one-body, two-body, …); the disorder critical exponents come
from the leading eigenvalue of the Jacobian ∂v′/∂v at the critical distribution
v*, via the connected-correlation relation (Eq. 11):

    ⟨U_β U_γ′⟩ − ⟨U_β⟩⟨U_γ′⟩ = Σ_α (∂v_α′/∂v_β)(⟨U_α′ U_γ′⟩ − ⟨U_α′⟩⟨U_γ′⟩)

Two fixed-point types are distinguished by the flow of the distribution's variance:
**finite-disorder** (variance converges; exponents computable — e.g. 2D dilute
Ising, λ_e = 2.018(6) vs pure-Ising 2) and **strong-disorder** (variance diverges;
exponents NOT computable this way — e.g. random TFIM chain via Trotter→2D map, 3D
RFIM). The bias still kills critical slowing down; cluster (Wolff) moves can be
layered on top for the largest blocks.

---

## 5. Algorithm (step-by-step)

### 5.A Classic Swendsen MCRG (exponents)

```
choose lattice L (and L/b for two-lattice matching), block factor b, rule (majority)
choose operator basis {S_α}, split even/odd; pick coupling K near K_c
for cycle in 1..N_cycles:
    generate a critical config σ ~ e^{-H(σ)}      # Metropolis + Wolff to fight slowing down
    measure lattice sums S_α^(0)
    for i in 1..n_levels:
        σ = τ(σ)                                  # block once, size shrinks by b
        measure S_α^(i)
        accumulate cross products S_α^(i) S_β^(i)  (-> B^(i))
                              and S_α^(i) S_β^(i-1) (-> C^(i))
for each level i, each parity sector:
    B^(i)_αβ = <S_α^(i) S_β^(i)> - <S_α^(i)><S_β^(i)>     # Eq.4
    C^(i)_αβ = <S_α^(i) S_β^(i-1)> - <S_α^(i)><S_β^(i-1)> # Eq.5
    T^(i) = (B^(i))^{-1} C^(i)                            # Eq.3
    diagonalize T^(i); leading even -> lambda_e, leading odd -> lambda_o
extrapolate lambda(i, n_c) -> fixed-point lambda (Eq.12)
y_t = ln lambda_e / ln b ;  y_h = ln lambda_o / ln b
# couplings K' (optional): Swendsen-1984 Callen-equation inversion
```

### 5.B Variational MCRG (couplings + exponents)

```
choose L, b, rule; operator basis {S_α} (even+odd); target p_t = uniform
locate K_c: for trial K, run VRG and watch coupling flow (grow above / shrink below)
for each RG level n at K = K_c:
    # --- optimize the bias to get K'^(n) ---
    init J = 0
    for vstep in 1..T_traj:                       # ~few thousand
        run ~20 biased MC sweeps over n_w walkers on fine spins,
            weight e^{-H} e^{-V_Jbar(tau(sigma))}
        estimate grad (Eq.9) and Hessian (Eq.10) from sampled S_α(sigma')
        J^[n+1] = J^[n] - mu[ Omega'(Jbar) + Omega''(Jbar)(J^[n]-Jbar) ]   # Eq.S3
        update running mean Jbar; reset at 10% and 20%
    J_min = Jbar at plateau ;  K'_α^(n) = -J_min,α                          # Eq.11-12
    prune |J_min,α| < 0.001
# --- Jacobian at K_c (one step if K_c accurate) ---
in the biased ensemble at K_c, measure:
    A_βγ = <S_β(σ) S_γ(σ')>_V - <S_β(σ)>_V<S_γ(σ')>_V    # Eq.16
    B_αγ = <S_α(σ') S_γ(σ')>_V - <S_α(σ')>_V<S_γ(σ')>_V  # Eq.17
solve A = (∂K'/∂K) B  for the Jacobian (invert B), per parity sector  # Eq.15
diagonalize; y_t = ln lambda_e^1 / ln b ;  y_h = ln lambda_o^1 / ln b
```

Iteration to the fixed point: refine K_c by re-running until couplings are
constant across successive RG levels; then a single level gives the Jacobian.

---

## 6. Key parameters & convergence

| Knob | Typical (2D Ising) | Effect / scaling |
|---|---|---|
| Lattice size L | 45–300 (b=3); 64–256 (b=2) | larger L → smaller finite-size bias; cost ∝ L^d per sweep; the binding compute axis |
| Block factor b & rule | 3×3 majority (b=3); √3 triangular; b=2 + tie-break | larger b = fewer steps to a given net b^n (less accumulated truncation+FS error) but costlier; rule must respect model symmetry — decimation fails |
| RG levels / iterations n | 5 (+1 preliminary); single step if K_c accurate | enough to read the flow; each step compounds truncation+FS error |
| Operators kept n_c | 13 even (7 two-spin + 6 four-spin) + 5 odd (Ising) | **dominant accuracy lever**; start generous, prune small-|coupling|, enlarge until leading eigenvalues stop moving |
| MC statistics | ~10⁶ sweeps (L≤90), 5×10⁵ (L=300); 16 walkers | stat. error ~ 1/√samples, ~ 1/n_w over walkers |
| (variational) µ, T_traj, sweeps/vstep | 5×10⁻⁵→5×10⁻⁶; ~1240–3000; 20 | averaged-SGD ~O(1/steps); shrink µ with L; stop at J̄ plateau |
| (variational) target p_t | uniform | uniform → uncorrelated block spins → no critical slowing down; Gaussian for continuous variables; physical block dist → Swendsen |
| K_c bracket | 0.4355–0.4365 → 0.436 (b=3) | tighter bracket → more accurate exponents + single-step Jacobian |

**Convergence signatures.** (i) Couplings **constant across RG levels** at K_c
(drift ⇒ off the fixed point ⇒ biased exponents). (ii) Leading eigenvalues
**stop moving** as n_c grows (else basis too small). (iii) Variational only:
running-average J̄ flattens to a plateau (read after the 10%/20% resets); biased
block-averaged standard error (Flyvbjerg–Petersen) plateaus at small block size
(critical slowing down removed). (iv) A few-percent eigenvalue residual at fixed
n_c is **truncation**, not finite size — it need not shrink with L.

---

## 7. Validation / benchmarks

**Canonical check — 2D Ising, square lattice:** the exact exponents are
**y_t = 1** and **y_h = 15/8 = 1.875**, with the only marginal/irrelevant
correction exponent y_i = −2. The leading even and odd eigenvalues must reproduce
these *simultaneously* via y = ln λ / ln b:

- b = 3: λ_e → 3^1 = **3**, λ_o → 3^{15/8} = **7.8452**. (Wu & Car biased VMCRG,
  L=300: λ_e = 3.03(1), λ_o = 7.885(5) — Table I of 1707.08683. Exact: 3, 7.8452.)
- triangular, b = √3: λ_e → √3 = 1.732, λ_o → (√3)^{15/8} = 2.8003. (Guo-Blöte
  modified rule: λ_e = 1.7319(2), λ_o = 2.80078(9).)

Other independent anchors in the KB: 3D Ising critical coupling K_c = 0.22165
(b=2, 1903.08231); 2D anisotropic Ising critical line sinh(2K_x) sinh(2K_y) = 1
with a marginal operator; 2D tricritical (Blume–Capel) co-dimension-2 manifold;
2D dilute Ising K_c = 0.609377 with λ_e = 2.018(6) (1810.09579).

**Verification ladder** (apply when a result is challenged): limit check (sign +
trivial-parameter); symmetry (even/odd sectors decouple as expected); convergence
(eigenvalues vs n_c and vs RG level); cross-check biased vs unbiased ensemble
(consistent up to a small truncation offset; unbiased fails to converge at large
L); literature comparison against the exact exponents above.

**Common failure modes** (criticize a candidate result for these): eigenvalues
read at an un-converged K_c; too-small basis with no eigenvalue-convergence test;
single-lattice finite-size bias (use two-lattice matching, §2.4); sign error
K′ = −J_min; mistaking running-average resets for coupling flow; mistaking
noise-driven flow inversion near K_c for a K_c shift; trusting an unbiased
eigenvalue at large L; conflating the truncation-free CMTS with the
truncation-sensitive exponents; using decimation/majority where the fixed point
sits far from the simulated Hamiltonian (Guo-Blöte: the plain majority-rule fixed
point lies well away from the nearest-neighbor critical point, inflating
corrections — a modified/optimized rule restores it).

---

## 8. Reproduction-sufficiency assessment

**The KB alone is NOT reproduction-sufficient for the full task as stated.** The
three KB papers (1707.08683 + SM, 1903.08231, 1810.09579) are the *variational /
bias-potential* lineage by Wu & Car. They are fully sufficient — equation by
equation, with all knobs, optimizer details, and 2D Ising benchmarks — to
reproduce **variational MCRG**, the critical-manifold tangent space/curvature, and
the quenched-disorder extension. The PRL even gives the reduction to Swendsen as a
special case and endorses two-lattice matching.

What the KB **lacks** is the self-contained *classic Swendsen* formulation: the
explicit block-spin matrix T_αβ = ∂K_α′/∂K_β with its two connected-correlation
matrices B (same-level) and C (adjacent-level) and the linear system B·T = C; the
mechanics of two-lattice matching; and the eigenvalue→exponent reading with the
triangular benchmark. **This was filled from the web**, primarily from a clean
text source — Guo, Blöte & Ren, *Monte Carlo renormalization: the triangular Ising
model as a test case*, PRE 71, 046126 (2005), Eqs. 1–6 and §IV (a standard review
+ test of Swendsen MCRG) — cross-checked against Donohue, arXiv:physics/0402090,
and the original Swendsen PRL 42, 859 (1979) / PRL 52, 1165 (1984) as cited in the
KB papers themselves. With §2 added, the reference is now reproduction-grade for
**both** variants.

Residual gaps (minor, not blocking): the original Swendsen PRLs (1979/1984) are
not rendered in the KB — only their formulae, transmitted through Guo-Blöte and
Wu & Car. For a beginner reproduction of *classic* MCRG, ingesting Swendsen 1979
(exponents) and 1984 (couplings) into the KB is recommended (see INGEST below).
The Callen-equation coupling inversion of Swendsen 1984 is described here only at
the level of "what it does", not term-by-term.

---

## 9. Source links

**Knowledge base (rendered, relative to repo root):**
- `.knowledge/literature/monte-carlo-renormalization-group/1707.08683_variational-approach-to-monte-carlo-renormalization-group.md` — Wu & Car, PRL 119, 220602 (2017) — primary variational source (Eqs. 1–18).
- `.knowledge/literature/monte-carlo-renormalization-group/1707.08683_SM_supplementary-material.md` — operator basis, minimization details (Eqs. S1–S15).
- `.knowledge/literature/monte-carlo-renormalization-group/1903.08231_determination-of-the-critical-manifold-tangent-space-and-cur.md` — Wu & Car, PRE 100, 022138 (2019) — CMTS + curvature.
- `.knowledge/literature/monte-carlo-renormalization-group/1810.09579_monte-carlo-renormalization-group-for-systems-with-quenched.md` — Wu & Car (2018) — quenched disorder.

**Web (classic Swendsen MCRG, filled here):**
- Guo, Blöte & Ren, PRE 71, 046126 (2005): https://physicsfaculty.bnu.edu.cn/Public/web/application/research/statistics_group/research/papers/pre2005.pdf — Eqs. 1–6 (T = B⁻¹C), §IV (eigenvalues → y_t=1, y_h=15/8).
- Donohue, arXiv:physics/0402090 (2004): https://arxiv.org/abs/physics/0402090 — "Another MCRG Algorithm" (cross-check).
- Swendsen, PRL 42, 859 (1979): https://doi.org/10.1103/PhysRevLett.42.859 — original MCRG exponents.
- Swendsen, PRL 52, 1165 (1984): https://doi.org/10.1103/PhysRevLett.52.1165 — renormalized couplings via Callen identity.

**Implementation:** no canonical open-source MCRG package; implement from scratch
on Python + JAX (`vmap` over walkers, `jit` the sweep) — see `skills/using-jax`.
