# Variational Monte Carlo & Neural Quantum States — Methodology Reference

Reproduction-grade reference for optimizing a parametrized trial wavefunction by Monte Carlo
sampling, with stochastic-reconfiguration / natural-gradient optimization, including
neural-network ansätze (NQS). Distilled from the harness KB plus canonical sources filled from
the web where the KB is thin (see *Reproduction-sufficiency assessment*).

Notation: ψ_θ(x) = ⟨x|ψ_θ⟩ is the (unnormalized, generally complex) amplitude of basis
configuration x for parameters θ. ⟨·⟩ without subscript denotes a Monte Carlo expectation over
the Born distribution p(x) = |ψ_θ(x)|² / Σ_x |ψ_θ(x)|². N_p = number of variational parameters,
N_s = number of Monte Carlo samples per step.

---

## 1. Overview — the variational principle

For any normalizable trial state |ψ_θ⟩ the Rayleigh quotient is an upper bound on the ground-state
energy E₀:

    E(θ) = ⟨ψ_θ|H|ψ_θ⟩ / ⟨ψ_θ|ψ_θ⟩  ≥  E₀ ,   with equality iff |ψ_θ⟩ ∝ ground state.

VMC minimizes E(θ) over θ. Two facts make it tractable for exponentially large Hilbert spaces:

1. **E(θ) is a Born-distribution average of a local quantity** (the *local energy*), so it can be
   estimated by Monte Carlo without ever enumerating the basis.
2. **Gradients and the metric (Section 4) are likewise averages** of cheaply computed
   per-configuration quantities, so gradient-based optimization is feasible.

The whole method is *zero-temperature, ground-state* by default; finite-T and real-time variants
exist (t-VMC, Section 4 note) but are out of scope here except where noted.

VMC's defining strength and limitation: it returns a **variational upper bound** with statistical
error bars on the energy, but **no rigorous bound on the gap to E₀**. A low energy with large
variance is not a converged result (Section 6, 7).

KB anchors: McMillan-style VMC originates in [McMillan 1965, ref 21 of Carleo–Troyer]; the modern
NQS framing is Carleo & Troyer (`1606.02318`, lines 245–265, 492–530).

---

## 2. Local energy & Metropolis sampling

### 2.1 The local energy

The central estimator. Define

    E_loc(x) = ⟨x|H|ψ_θ⟩ / ⟨x|ψ_θ⟩ = Σ_{x'} ⟨x|H|x'⟩ · ψ_θ(x') / ψ_θ(x).

For a *k*-local Hamiltonian the sum over x' runs only over the O(poly) configurations connected to
x by H, so each E_loc(x) costs O(connections × cost of one amplitude ratio). Then

    E(θ) = Σ_x p(x) E_loc(x) = ⟨E_loc⟩ .

(KB: Carleo–Troyer A2, `1606.02318` line 513–517; NetKet Eq. 5, `10-1016-j-softx-2019-100311`
lines 382–405, derives ⟨H⟩ = ⟨ Σ_{x'} ⟨x|H|x'⟩ ψ(x')/ψ(x) ⟩ over samples from p.)

**Zero-variance property.** If |ψ_θ⟩ is an exact eigenstate, E_loc(x) = E₀ for *every* x with
p(x) > 0, so the Monte Carlo variance of E_loc vanishes. Hence the energy variance

    σ²_E = ⟨E_loc²⟩ − ⟨E_loc⟩²  →  0

is the primary internal convergence diagnostic — it is exact only at an eigenstate, regardless of
sampling noise. (KB: SKILL `## Details`; NetKet Fig. 2 inset, line 318–320.)

### 2.2 Metropolis(-Hastings) sampling of |ψ_θ|²

Configurations are drawn from p(x) ∝ |ψ_θ(x)|² by a Markov chain. At each step propose x → x'
and accept with the Metropolis–Hastings probability

    A(x → x') = min( 1 ,  [q(x|x')/q(x'|x)] · |ψ_θ(x')|² / |ψ_θ(x)|² ).

For a symmetric proposal q the ratio q(x|x')/q(x'|x) = 1 and only the amplitude ratio is needed —
the normalization Σ_x|ψ|² cancels. (KB: Carleo–Troyer C6, `1606.02318` lines 613–627.)

**Move types** (the two NetKet exposes, lines 409–410, 464–465):

- **Local moves** (`MetropolisLocal`): flip/raise one site. Changes magnetization/particle number;
  use when no sector is conserved or when sampling the full space.
- **Exchange / hop moves** (`MetropolisExchange`, `MetropolisHop`): swap two neighboring spins or
  hop a particle. **Conserve total Sᶻ / particle number** — required to stay in a fixed sector
  (e.g. the Sᶻ = 0 sector for an antiferromagnet). Most ground-state spin runs use exchange moves.

**Efficiency trick.** Cache the "effective angles" θ_j(x) = b_j + Σ_i W_ij σ_iᶻ of an RBM and update
them in O(N) on a single flip via θ_j(x') = θ_j(x) − 2 W_{sj} σ_sᶻ, so a full sweep of O(N) flips
costs O(αN²). (KB: Carleo–Troyer C1–C7, lines 539–630.)

### 2.3 Monte Carlo estimators and statistical error

For any observable Ô define the local observable O_loc(x) = ⟨x|Ô|ψ_θ⟩/⟨x|ψ_θ⟩; then
⟨Ô⟩ ≈ (1/N_s) Σ_n O_loc(x_n) over chain samples {x_n}. The statistical error is **not**
σ/√N_s because samples are autocorrelated:

    err(⟨Ô⟩) ≈ √( σ²_O · (2 τ_int + 1) / N_s ) ,

where τ_int is the integrated autocorrelation time (in sweeps). Practically: thin/decorrelate the
chain by τ_int sweeps between recorded samples, or estimate τ_int and inflate the error bar (and/or
use binning/blocking). Report both the energy and its error bar. (See Section 6.)

---

## 3. Gradients

### 3.1 Log-derivatives

Define the per-parameter log-derivative ("score function"), the workhorse of every VMC gradient:

    O_k(x) = ∂_{θ_k} ln ψ_θ(x) = (1/ψ_θ(x)) ∂_{θ_k} ψ_θ(x).

(KB: Carleo–Troyer A1, `1606.02318` line 510–512.) For an RBM with effective angles
θ_j = b_j + Σ_i W_ij σ_iᶻ these are closed-form (KB lines 549–558):

    O_{a_i}    = σ_iᶻ ,
    O_{b_j}    = tanh θ_j(x) ,
    O_{W_ij}   = σ_iᶻ tanh θ_j(x).

For deep networks (CNN, Transformer, …) O_k(x) is obtained by **automatic differentiation /
backpropagation** of ln ψ_θ(x) — same role, no closed form needed. (KB: NetKet lines 419–422.)

### 3.2 The energy-gradient estimator

The exact gradient of the Rayleigh quotient is a **covariance** of the local energy with the
log-derivatives (the "force" vector, gradient ≡ 2·force for real, conjugate handling for complex):

    g_k = ∂_{θ_k} E(θ) = 2 Re[ ⟨E_loc · O_k*⟩ − ⟨E_loc⟩⟨O_k*⟩ ] .

In SR notation the (un-doubled, complex) force is

    F_k = ⟨E_loc · O_k*⟩ − ⟨E_loc⟩ ⟨O_k*⟩ .

(KB: Carleo–Troyer A5, `1606.02318` line 528–529; NetKet "energy gradient estimated at the same
time as ⟨H⟩", lines 417–419.) The subtraction of ⟨E_loc⟩⟨O_k*⟩ is a **control variate**: it does
not change the expectation (because ⟨O_k⟩ multiplies a constant) but kills variance, and inherits
the zero-variance property — g_k → 0 as ψ_θ → eigenstate. Always center.

Plain gradient descent / SGD then updates θ ← θ − λ g. This is what NetKet's `Sgd`/`AdaMax`/etc.
do (NetKet Eq. 2, line 310). It works but is poorly conditioned in the curved state manifold;
Section 4 fixes this.

---

## 4. Stochastic reconfiguration / natural gradient

### 4.1 The S-matrix (quantum geometric tensor / Fisher metric)

Plain gradient descent measures distance in Euclidean parameter space, which does not match
distance between the *quantum states* those parameters produce. SR preconditions the gradient with
the metric of the state manifold — the **quantum geometric tensor** (QGT), equivalently the
quantum Fisher information / Fubini–Study metric restricted to the variational family:

    S_{kk'} = ⟨O_k* O_{k'}⟩ − ⟨O_k*⟩⟨O_{k'}⟩ .

This is a positive-semidefinite N_p × N_p covariance matrix of the (centered) log-derivatives.
(KB: Carleo–Troyer A4, `1606.02318` line 526; NetKet SR docs, definition identical.) For ground
states one typically uses Re S (real part); the imaginary part matters for dynamics.

### 4.2 The SR update

    δθ = −η S⁻¹ g     (equivalently  δθ = −γ S⁻¹ F  in force notation).

(KB: Carleo–Troyer A3, `1606.02318` line 519–521.) Solve the linear system S δθ = −η g rather than
forming S⁻¹ explicitly.

**Natural-gradient identity.** S⁻¹ g is exactly Amari's natural gradient with the Fisher metric;
SR for quantum states is the **quantum natural gradient** of Stokes et al. — the steepest-descent
direction with respect to the Fubini–Study geometry rather than the Euclidean one. (Web:
Stokes et al., *Quantum* 4, 269 (2020); Amari 1998; NetKet SR docs and `10-1016-...` lines
427–431 note this correspondence but do not derive it — *filled from web*.)

**Imaginary-time / projector interpretation.** A single SR step equals one infinitesimal
imaginary-time step e^{−δτ H}|ψ_θ⟩ projected back onto the tangent space of the variational
manifold — SR is variational imaginary-time evolution. This is *why* it converges robustly toward
the ground state. (KB: Carleo–Troyer "effective imaginary-time evolution in the variational
subspace", line 503–504; the t-VMC equations of motion δθ̇ = −i S⁻¹ F, B3 line 515, are the
real-time analogue and require the Moore–Penrose pseudo-inverse.)

### 4.3 Regularization

S is Monte-Carlo-estimated and typically rank-deficient (many tiny/zero eigenvalues), so S⁻¹ is
ill-defined. Two standard fixes (KB: Carleo–Troyer A-appendix, lines 531–538):

- **Diagonal shift** (most common): S → S + λ I, or scale-invariant variant
  S_{kk}^{reg} = S_{kk} + λ S_{kk}. Typical λ ∈ [10⁻⁵, 10⁻²]; NetKet `diag_shift`. Carleo–Troyer
  use a *decaying* shift λ(p) = max(λ₀ bᵖ, λ_min) with λ₀ = 100, b = 0.9, λ_min = 10⁻⁴ — strong
  regularization early, weak late. (KB lines 535–538.)
- **Pseudo-inverse**: S⁻¹ → Moore–Penrose pseudo-inverse (mandatory in t-VMC, line 531–533).

For large N_p, never form S explicitly: use an **iterative linear solver** (conjugate-gradient /
MINRES-QLP) that needs only matvecs S·v, computed from the O-matrix in O(N_p · N_s). (KB:
Carleo–Troyer Appendix D, lines 633–675.)

### 4.4 minSR / kernel SR — the large-parameter variant

For deep NQS with N_p ≫ N_s (N_p up to ~10⁶), the O(N_p³) inversion is infeasible. The **kernel /
minimum-step SR (minSR)** trick moves the inversion into the *N_s-dimensional sample space* using
the **push-through (Woodbury) identity** (AB + λI)⁻¹ A = A (BA + λI)⁻¹:

    δθ = −η · O† (O O† + λ I_{N_s})⁻¹ ε ,

where O is the N_s × N_p matrix of **centered** log-derivatives (rows = samples), ε is the vector
of **centered** local energies (ε_n = E_loc(x_n) − ⟨E_loc⟩), and T = O O† is the N_s × N_s Gram
matrix (the **neural tangent kernel**). One inverts an N_s × N_s matrix instead of N_p × N_p.

- **Complexity**: O(N_s² N_p) + O(N_s³) instead of O(N_p³); memory O(N_s N_p) instead of O(N_p²).
- **Equivalence**: for N_p ≥ N_s and matching regularization, this yields the *same* update as
  standard SR — diagonal shift λ in parameter space ≡ diagonal shift in sample space. minSR
  (Chen–Heyl) frames it as minimizing the parameter step subject to the imaginary-time-projection
  constraint (a Rayleigh-quotient / least-squares view) and uses a pseudo-inverse with
  singular-value truncation; the push-through identity (Rende et al.) derives the same N_s × N_s
  inversion directly with ordinary diagonal regularization.
- **When to prefer**: use minSR/kernel SR whenever N_p > N_s (deep networks); use standard
  parameter-space SR when N_p ≲ N_s (shallow RBM, few parameters).

(Web: Chen & Heyl, *Nat. Phys.* 20, 1476 (2024) / arXiv:2302.01941; Rende, Viteritti, Becca et al.,
arXiv:2310.05715; NetKet SR docs kernel form δW = J†(JJ†)⁻¹E_loc. **Filled from web** — the KB
predates these and does not cover large-N_p SR.)

---

## 5. Ansätze

How ln ψ_θ(x) and O_k(x) = ∂_{θ_k} ln ψ_θ(x) are evaluated determines the cost. Symmetry-projected
forms reduce parameters and enforce conserved quantum numbers.

### 5.1 Jastrow / pair-product (especially fermions)

- **Spin/density Jastrow**: ln ψ_J(x) = Σ_{ij} v_{ij} n_i n_j (or σ_iᶻσ_jᶻ) on top of a reference
  state. Captures density–density correlations; O_k are products of occupations — trivial.
- **Pair-product / geminal (fermions)**: ψ = det/Pfaffian of a pairing matrix Φ (an AGP/BCS
  reference), optionally × Jastrow. Standard fermionic VMC ansatz; sign structure lives in the
  determinant/Pfaffian. This is the Becca–Sorella core material (see Section 8 — KB stub).
  Carleo–Troyer compare NQS against the spin-Jastrow ansatz (`1606.02318` Fig. 3 centre, line
  311–314) and beat it by orders of magnitude.

### 5.2 Neural-network states (RBM and beyond)

- **RBM** (Carleo–Troyer): visible layer = physical config, single hidden layer of M = αN units
  traced out analytically:

      ψ_M(x; W) = e^{Σ_i a_i σ_iᶻ} · Π_{j=1}^{M} 2 cosh θ_j(x) ,   θ_j = b_j + Σ_i W_ij σ_iᶻ ,

  weights {a, b, W} **complex-valued** to represent both amplitude and phase. Hidden density
  α = M/N plays the role of MPS bond dimension; accuracy improves systematically with α. O_k are
  the closed forms in 3.1. (KB: `1606.02318` lines 128–147, 539–558.)
- **Deeper architectures** (CNN, ResNet, RNN, Transformer, autoregressive): ln ψ from a forward
  pass, O_k from autodiff. Autoregressive nets allow *direct* sampling (no Markov chain).
  These are where minSR (Section 4.4) becomes essential.

### 5.3 Symmetries

- **Lattice symmetry (translation, point group)**: build a symmetric ansatz — for the RBM, weights
  become *feature filters* W_j^{(f)}, f ∈ [1, α], shared across the symmetry orbit (shift-invariant
  RBM ≈ CNN). For translation on N sites this cuts αN² → αN parameters and enforces momentum
  k = 0. (KB: Carleo–Troyer Appendix E, lines 638–686.)
- **U(1) / Sᶻ conservation**: enforce via the *sampler* (exchange/hop moves, Section 2.2) rather
  than the ansatz.
- **Sign / Marshall sign rule**: for bipartite antiferromagnets, initializing or factoring the
  Marshall sign exp(iπ Σ_{i∈A} S_iᶻ·…) makes the target amplitude positive and greatly eases
  optimization (KB: SKILL pitfalls). Frustrated / fermionic systems need the ansatz itself to learn
  the sign/phase structure — the hardest part of NQS.

---

## 6. Algorithm — full optimization loop

```
Input: Hamiltonian H, ansatz ψ_θ, init θ (small random), learning rate η,
       SR shift λ (optional decay), N_s samples, N_therm thermalization sweeps,
       N_decorr decorrelation sweeps, N_iter optimization steps.

for step = 1 .. N_iter:
    # --- 1. Sample p(x) ∝ |ψ_θ(x)|² by Metropolis ---
    thermalize chain for N_therm sweeps (discard)
    collect {x_1,...,x_N_s}, each separated by N_decorr sweeps
        (sweep = O(N) local or exchange/hop moves; accept via |ψ(x')/ψ(x)|²)

    # --- 2. Per-sample quantities ---
    for each x_n:
        E_loc(x_n) = Σ_{x'} ⟨x_n|H|x'⟩ · ψ_θ(x')/ψ_θ(x_n)      # local, k-local H
        O_k(x_n)   = ∂_θk ln ψ_θ(x_n)                          # closed form or autodiff

    # --- 3. Estimators ---
    E       = mean_n E_loc(x_n)
    σ²_E    = var_n  E_loc(x_n)                                # convergence diagnostic
    Ō_k     = mean_n O_k(x_n)
    g_k     = 2 Re[ mean_n (E_loc(x_n) - E) · (O_k(x_n) - Ō_k)* ]    # centered gradient

    # --- 4. Preconditioned step ---
    if SR and N_p <= N_s:                                      # parameter-space SR
        S_kk' = mean_n (O_k(x_n)-Ō_k)* (O_k'(x_n)-Ō_k')
        solve (Re S + λ I) δθ = -η g       (CG / MINRES; λ may decay)
    elif SR and N_p > N_s:                                     # kernel / minSR
        O_c[n,k] = O_k(x_n) - Ō_k ;  ε[n] = E_loc(x_n) - E
        T = O_c O_c† (N_s×N_s) ;  solve (T + λ I) y = ε ;  δθ = -η O_c† y
    else:                                                      # plain SGD / Adam
        δθ = -η g    (or optimizer update rule)

    θ ← θ + δθ
    log(step, E, σ²_E, acceptance_rate, ||g||)                # flush each line

return θ, E, σ²_E
```

(Loop structure: KB Carleo–Troyer "iterative scheme" lines 245–265 + appendices; NetKet `Vmc`
driver lines 373–438. Kernel branch: web, Section 4.4.)

---

## 7. Key parameters & convergence

| Knob | Role | Typical / guidance |
|---|---|---|
| N_s (samples/step) | gradient & S noise | 10³–10⁴; larger N_s → less noisy S, more stable SR |
| N_chains | parallel chains | many short chains > one long chain for decorrelation |
| N_therm | burn-in | discard until E_loc stationary; scale with τ_int |
| N_decorr | thinning | ≈ τ_int sweeps between samples (Section 2.3) |
| η (learning rate) | step size | 0.01–0.1 with SR; smaller for plain SGD |
| λ (SR shift) | regularize S | 10⁻⁵–10⁻²; or decay λ₀=100,b=0.9,λ_min=10⁻⁴ |
| ansatz size (α / depth) | expressivity | increase to lower energy; α like MPS bond dim |

**Diagnostics (all should be watched live, ~10–50 updates over the run):**

- **Energy variance σ²_E → 0** is the decisive internal check (exact eigenstate ⇔ zero variance).
  A low E with high σ²_E is *not* converged. (KB: SKILL `## Details`, NetKet Fig. 2 inset.)
- **Energy plateau**: E(step) flattens at the variational minimum (KB: Carleo–Troyer Fig. 5).
- **Acceptance rate**: tune proposal so it sits ~0.3–0.6; near 0 or 1 means bad moves.
- **Gradient/force norm** decreasing.
- **Sign/phase**: for frustrated & fermionic systems, plain real-positive ansätze fail — the model
  must carry phase (complex RBM weights) or a learned sign net; Marshall-sign init for bipartite
  AFM. Stalled high-energy optimization usually means the sign structure is not captured.
- **Local minima / seeds**: the landscape is non-convex — run 3–5 seeds and compare; restart on
  outliers. (KB: SKILL pitfalls.)

---

## 8. Validation / benchmarks

In priority order (aligns with harness verification practice):

1. **Variational upper bound**: the converged E must satisfy E ≥ E₀. If E < a trusted exact/QMC
   value, there is a bug (sampling, sign, or estimator). (KB: SKILL Verification.)
2. **Energy-variance check / extrapolation**: σ²_E small relative to E²; optionally extrapolate
   E vs σ²_E → 0 (zero-variance extrapolation) for a best estimate.
3. **Small-system cross-check vs ED**: for N where exact diagonalization is feasible, VMC energy
   (and observables) must agree within error bars. Route via `/method-ed` / `/using-xdiag`. (KB:
   SKILL route step 4.)
4. **Cross-method**: compare to DMRG (1D / cylinders) or QMC (sign-free regimes) on the same
   system; agreement within combined error budgets. (Harness verification practice item 5.)
5. **Literature comparison**: Carleo–Troyer anchors — 1D AFH chain (N=80, PBC) reaches MPS-grade
   accuracy at α≈4 (rel. error ~10⁻⁶–10⁻⁷); 2D 10×10 AFH beats EPS/PEPS at modest α; 1D AFH N=40
   E/N converges to −0.4438 region (Fig. 5). NetKet: 1D Heisenberg N=20 RBM α=1 reaches rel.
   error 4×10⁻⁵ in ~100–200 SR steps. Use these as smoke tests.

---

## 9. Reproduction-sufficiency assessment

**Verdict: KB is sufficient for the NQS/RBM VMC + stochastic-reconfiguration *core*, but the
Becca–Sorella book — the canonical VMC/SR/fermionic reference — is an abstract-only stub
(`10-1017-9781316417041.md`, `full_text: no`), so several pieces were filled from the web.**

What the KB **does** cover, reproduction-grade, from full-text sources:

- Local energy, Metropolis–Hastings acceptance, efficient angle updates — Carleo–Troyer
  Appendix C (full text).
- Log-derivatives O_k, force/gradient covariance estimator, zero-variance — Carleo–Troyer
  Appendix A.
- The S-matrix definition, SR update δθ = −γ S⁻¹ F, diagonal-shift & pseudo-inverse
  regularization, imaginary-time interpretation, iterative MINRES-QLP solver, symmetry-projected
  RBM — Carleo–Troyer Appendices A, D, E (full text).
- RBM ansatz, hidden density α, MC energy/variance estimator and the NetKet driver/sampler/optimizer
  mapping — Carleo–Troyer body + NetKet (full text).

What the KB **cannot** supply (Becca–Sorella stub) and was **filled from the web**:

- **Sorella's original stochastic-reconfiguration derivation** (Sorella 1998 PRL; Sorella 2000 PRB;
  Sorella 2001 PRB generalized Lanczos) — the KB cites SR only through Carleo–Troyer's appendix.
- **The natural-gradient / quantum-Fisher-metric equivalence** made explicit (Amari 1998; Stokes
  et al. 2020). NetKet/Carleo–Troyer assert the connection but do not derive it.
- **Detailed fermionic VMC machinery** (Slater–Jastrow, AGP/Pfaffian pair-product wavefunctions,
  determinant updates) — only named here; the book is the reference and is a stub.
- **Modern large-parameter SR** (minSR, Chen–Heyl 2023; push-through/kernel SR, Rende et al. 2023)
  — postdates the KB entirely.

Recommendation: ingest the Sorella SR papers and the Chen–Heyl minSR paper (below). For
fermionic pair-product VMC, the Becca–Sorella book needs a full-text render (currently only a DOI
stub) before that part of the KB is reproduction-grade.

---

## 10. Source links

KB (relative to repo root):

- `.knowledge/literature/variational-monte-carlo-neural-quantum-states/1606.02318_solving-the-quantum-many-body-problem-with-artificial-neural.md` — Carleo & Troyer, NQS + SR appendices (full text).
- `.knowledge/literature/variational-monte-carlo-neural-quantum-states/10-1016-j-softx-2019-100311.md` — NetKet (full text).
- `.knowledge/literature/variational-monte-carlo-neural-quantum-states/10-1017-9781316417041.md` — Becca & Sorella book (**abstract-only stub**).
- Harness convention/limit cards: `.knowledge/conventions.md`, `.knowledge/limits.md`, `.knowledge/symmetry-cheatsheet.md`.
- Method skill: `skills/method-vmc/SKILL.md`; tools `skills/using-netket/`, `skills/using-jax/`.

Web (filled gaps):

- Sorella, *Green Function Monte Carlo with Stochastic Reconfiguration*, PRL **80**, 4558 (1998) — arXiv:cond-mat/9803107. https://link.aps.org/doi/10.1103/PhysRevLett.80.4558
- Sorella, *GFMC with stochastic reconfiguration: remedy for the sign problem*, PRB **61**, 2599 (2000). https://doi.org/10.1103/PhysRevB.61.2599
- Sorella, *Generalized Lanczos algorithm for variational quantum Monte Carlo*, PRB **64**, 024512 (2001). https://doi.org/10.1103/PhysRevB.64.024512
- Stokes, Izaac, Killoran, Carleo, *Quantum Natural Gradient*, *Quantum* **4**, 269 (2020) — arXiv:1909.02108. https://quantum-journal.org/papers/q-2020-05-25-269/
- Amari, *Natural Gradient Works Efficiently in Learning*, Neural Comput. **10**, 251 (1998).
- Chen & Heyl, *Empowering deep neural quantum states through efficient optimization* (minSR), *Nat. Phys.* **20**, 1476 (2024) — arXiv:2302.01941. https://arxiv.org/abs/2302.01941
- Rende, Viteritti, Capelli, Becca, et al., *A simple linear algebra identity to optimize large-scale NQS* — arXiv:2310.05715. https://arxiv.org/abs/2310.05715
- NetKet QGT/SR user guide. https://netket.readthedocs.io/en/stable/user-guides/sr.html
