---
name: method-mcrg
description: Use when a Monte Carlo Renormalization Group reproduction or calculation needs method-level route and tool selection — real-space block-spin RG on lattice spin models, extracting renormalized coupling constants and critical exponents from the eigenvalues of the RG Jacobian. Covers Swendsen's classic MCRG and the variational (bias-potential) MCRG that removes critical slowing down.
---

# Method MCRG

## Overview

MCRG computes the critical behavior of a classical spin model by repeatedly **coarsening the lattice and tracking how the model's interactions change.**

- **What it does.** The spins obey a Hamiltonian H — a set of interaction strengths (*coupling constants* K: nearest-neighbor, next-nearest, four-spin, …). Group the spins into blocks (e.g. 3×3), replace each block by one coarse spin via a fixed rule (usually majority vote); the coarse spins then obey an **effective Hamiltonian H′ with new couplings K′**. Repeating traces a flow K → K′ → K″ … in coupling space.
- **Target.** The renormalized couplings K′, and the **critical exponents** — read from how strongly K′ responds to a small change in K near the flow's stationary point.
- **What's approximated.** H′ exactly contains *infinitely many* couplings (blocking always generates new longer-range, multi-spin terms). The method **keeps a finite short-range set and discards the rest** — valid because dropped terms are short-range-small or irrelevant to the critical behavior. The number of couplings kept is the main accuracy knob.
- **General features.** Dimension-agnostic (block in any d; only the cost grows with d); applies to any classical spin model where you can sample configurations (and quantum models mapped to classical); needs only Monte-Carlo-sampled configurations; no sign problem.

**Two variants.** *Swendsen MCRG* reads exponents from Monte-Carlo-measured correlation functions without building H′ (truncation uncontrolled). *Variational MCRG* (this card's focus) builds the best H′ within the kept couplings by convex optimization — removing critical slowing down and making the truncation error estimable.

> **When this card is invoked, before any choice, orient the user with this table (interaction principles below), filling the right column with *their* actual problem — their Hamiltonian, lattice, and setup. If those aren't fixed yet, use the table to elicit them; if the user has no specific problem in mind, fall back to 2D Ising (square, nearest-neighbor) as the illustration.**

| Ingredient | What it is | Your setup |
|---|---|---|
| Starting Hamiltonian H | the spin model's interaction strengths (couplings K) | *(user's model + couplings; default 2D Ising H = −K Σ⟨ij⟩ sᵢsⱼ)* |
| Coarse-graining | group spins into blocks, one coarse spin per block by a fixed rule | *(block size + rule; default 3×3 majority, b=3)* |
| Effective Hamiltonian H′ | the new couplings K′ the coarse spins obey | *(generated couplings to keep)* |
| Target | renormalized couplings + critical exponents | *(which exponents / couplings wanted)* |
| What's approximated | infinite generated couplings → keep a finite short-range set | *(how many couplings kept)* |
| Variant | Swendsen or Variational MCRG | *(which, and why)* |

> **Interaction principles — all user-facing surfacing in this card.** Plain language, no jargon: define every term, symbol, and axis before first use. No walls of words — a few sentences or one compact table per turn. One decision at a time, recommendation-first with one-line pros/cons. Precise and concise; let the user feel each choice, never a silent default.

## Sources

- **Methodology reference** (reproduction-grade algorithm, parameters, validation, gap analysis): `references/mcrg-methodology.md`
- Tool skill: `/using-jax` — the algorithm is implemented from scratch on JAX (see Step 2).
- Primary literature (rendered in `.knowledge/literature/monte-carlo-renormalization-group/`):
  - **1707.08683** — Wu & Car, PRL 119, 220602 (2017) — variational MCRG, 2D Ising.
  - **1903.08231** — Wu & Car, PRE 100, 022138 (2019) — critical-manifold tangent space + curvature.
  - **1810.09579** — Wu & Car, arXiv:1810.09579 (2018) — MCRG for quenched disorder.

## Select method — step 1

### Suited for
- Extracting **critical exponents** (thermal, magnetic, correction-to-scaling — from the eigenvalues of the **RG Jacobian** ∂K′/∂K, the matrix of how each renormalized coupling K′ responds to each bare coupling K, via y = ln λ / ln b) and **renormalized coupling constants** of lattice models at/near a critical fixed point. Spin-flip symmetry splits the couplings (and the Jacobian) into **even** (symmetric under flipping all spins → thermal) and **odd** (antisymmetric → magnetic) sectors.
- Real-space and configuration-based: works directly from Monte-Carlo-sampled configurations (the variational variant samples inside a bias-potential optimization).
- **Variational variant** when critical slowing down blocks large systems, or when you want the truncation error estimated.
- Validated mainly in **2D and 3D**; the formalism is dimension-general.

### Worked examples

All from the variational MCRG lineage; rendered papers in `.knowledge/literature/monte-carlo-renormalization-group/`. **Use this with the user: anchor their problem to the nearest row and quote its scale as a concrete reference point** — *walkers* are the independent Monte-Carlo chains run in parallel (e.g. "closest to 2D Ising critical exponents — they reached L=300 with 16 walkers").

| Ref | Model | Problem type | Scale | Calculated |
|---|---|---|---|---|
| 1707.08683 | 2D Ising, square | critical exponents | b=3 (3×3 majority); L=45–300; 13 even (7 two-spin + 6 four-spin) + 5 odd couplings; ~10⁶ sweeps; 16 walkers | even/odd Jacobian eigenvalues → thermal & magnetic exponents; renormalized couplings |
| 1903.08231 | 2D Ising, square | critical-manifold tangent space + curvature | b=2; L=256; n=4–5; 16×3×10⁶ sweeps | tangent-space normal vectors + curvature of the critical manifold |
| 1903.08231 | 3D Ising, cubic | tangent space | b=2; L=64; n=3; 16×3×10⁵ sweeps | tangent space in 8-coupling space |
| 1903.08231 | 2D anisotropic Ising | tangent space (marginal operator: RG eigenvalue 1, neither grows nor shrinks) | b=2; 4 couplings | tangent space with the marginal operator |
| 1903.08231 | 2D tricritical Ising (Blume–Capel) | tangent space, co-dim 2 | b=2; L=256; n=5; 5–6 couplings | tangent space confirming co-dimension 2 |
| 1810.09579 | 2D dilute Ising | disorder critical exponent | b=2; L=128(+256); Metropolis+Wolff; 3 couplings | leading even eigenvalue → disorder critical exponent |
| 1810.09579 | 2D & 3D RFIM | disorder RG flow | b=2; L=64(+128) 2D | RG flow to the disorder fixed point |
| 1810.09579 | random TFIM chain | disorder RG flow (quantum→2D) | m=8 Trotter, β=16, 128×128; b=2 | RG flow to a strong-disorder fixed point |

References: the rendered files under `.knowledge/literature/monte-carlo-renormalization-group/` (see Sources) — each carries its source URL in the frontmatter.

### Route elsewhere — when MCRG isn't the right tool

MCRG fits only when the target is **critical-point data** (exponents or renormalized couplings), or a quantum model mapped to classical.

> **When the user's goal falls outside this:** recognize it before any setup; explain *what fits better and why* in a short table (what / why); stay warm — guide, don't dismiss. (Interaction principles above.)

### Options & trade-offs

| Variant | Good at | Weak at | When to use |
|---|---|---|---|
| **Variational MCRG** | no critical slowing down → large L near T_c; truncation error estimable; couplings + exponents from one convex optimization | extra bias-potential optimization to implement and tune | large systems near criticality, or when you want truncation control |
| **Swendsen MCRG** | simple, minimal code; textbook | critical slowing down at large L; truncation uncontrolled | small/moderate L; a quick exponent estimate; baseline/validation |

### Routing — surface to the user

> **When routing, present the choice to the user as a table:** which variant, when to choose it, and which fits their case (why from Options & trade-offs above). Make the user feel the one consequence that actually decides it: **critical slowing down** — on a large lattice near the critical point, Swendsen's sampling crawls and may never converge, while the variational bias keeps it fast — or, when reproducing, which variant the paper used.

## Select software — step 2

### No canonical open-source code
There is **no canonical open-source code repository** for MCRG — the variational method's original code was never released, and no maintained package implements it. **Implement from scratch.** The algorithm lives in `## Details`; the primitives that express it live in `/using-jax`.

### Route — Python + JAX
The compute is a custom classical Monte Carlo (Metropolis/Wolff) sampling multiple walkers over many sweeps, plus stochastic optimization of the bias potential and a small Jacobian eigensolve. The two JAX features that matter:

- **`vmap`** — run the multiple walkers together in one vectorized pass.
- **`jit`** — compile the Metropolis/Wolff sweep so sampling is fast.

(Autodiff is *not* the reason for JAX — the optimization gradients are Monte Carlo estimators, not differentiated.)

### Surface to the user

> **Surface the software choice to the user** as a short what/why table (interaction principles above): (1) there's no off-the-shelf MCRG tool, so this is a **from-scratch build** — be honest about the cost (more code to write, and it must be validated against known/exact answers); (2) the route is **JAX**, because the work is sampling many walkers over many sweeps, which `vmap` + `jit` make fast — plain Python would crawl at large L. Even with no competing option, let the user feel *why* this is the deliberate choice, not an accident.

### Handoff
Invoke **/using-jax** once the route is fixed — it owns JAX CPU/GPU setup, jit/vmap/PRNG mechanics, and runtime troubleshooting. This card owns the algorithm (`## Details`), the operator basis, and the convergence plan.

## Method setup — step 3

Each knob with its default and a consolidated principle/effect (with scaling where it matters). Defaults are the paper's 2D-Ising values — parenthesized where model/paper-specific; the principle transfers to other models. K_c = the critical coupling, where the exponents are defined. Software-side values (JAX device, JIT boundary) live in `/using-jax`. *(Math unicode/plain.)*

| Knob | Default | Principle, effect & scaling |
|---|---|---|
| **Block size & rule** | 3×3 majority rule, b=3 (Ising) | compose several small-b steps to a net rescaling b^n rather than one big block — fewer steps at fixed b^n means less accumulated truncation + finite-size error; the rule must respect the model's symmetry (majority for Ising; decimation proliferates couplings and fails) |
| **Operator basis & truncation** | 13 even (pruned from 26) + 5 odd chosen directly (Ising even/odd sectors) | start from a generous symmetry-allowed set, prune operators with small variational coefficient (\|coupling\| < 0.001), enlarge until the leading eigenvalues stop moving; the dominant accuracy lever — too few biases the exponents; optimization cost grows ~linearly in the number of coefficients; the residual p_V vs target gauges the truncation error |
| **Target distribution p_t** | uniform | choose p_t with analytic averages; uniform makes block spins uncorrelated → removes critical slowing down; p_t = the model's own block distribution recovers Swendsen; for continuous/unbounded variables a Gaussian p_t is the convenient target choice |
| **Coarsening steps** | 5 per run + 1 preliminary (this paper) | enough steps to read the coupling flow; near a known K_c one step gives the Jacobian; each step compounds truncation + finite-size error; at K_c the couplings stay constant (the convergence signature) |
| **Sampling budget** | trajectory 3000→1240 steps, 20 sweeps/step, 16 walkers (this paper) | keep sweeps/step small — the trajectory averages per-step noise out; statistical error on the biased averages ~ 1/√samples and averaging over the walkers (the independent Monte-Carlo chains run in parallel) cuts variance ~ 1/(number of walkers), so lengthen the trajectory or add walkers to tighten the exponents |
| **Locating K_c** | K_c ≈ 0.436 (2D Ising, b=3; exact 0.4407) | bracket by the coupling flow direction — couplings grow above K_c, shrink below; a tighter bracket → more accurate exponents and lets one small-b step give the Jacobian; near K_c the optimization is noise-sensitive |
| **Optimizer** | averaged SGD (Bach–Moulines), µ = 5×10⁻⁵→5×10⁻⁶ (L-dependent) | build the bias from the running mean J̄, not instantaneous J; shrink µ as L grows for stability; reset the running mean at 10%/20% to drop its lag; averaged SGD converges ~ O(1/steps); stop at the J̄ plateau |
| **Spin update** | single-spin Metropolis | local Metropolis on σ under weight e^{−(H+V(τ(σ)))}; rely on the bias (not cluster moves) to kill the correlation time, which otherwise diverges as τ ~ ξ^z near T_c |

> **Confirm the setup with the user before running — one knob per turn, never batched (interaction principles above).** Run this loop:
>
> 1. **Orient once.** Open with a one-sentence plain hook — e.g. *"Add a gentle push (bias) on the blocked spins so they look random and are fast to sample; the push you need turns out to be the renormalized model itself — so one fit gives both fast sampling and the answer."* Then tie each knob to its role: the bias potential V flattening block spins toward a uniform target (target distribution), the optimization of V (optimizer + sampling budget), the finite operator set kept (operator basis & truncation), the block map (block size & rule), the fixed point where the exponents live (locating K_c) — so the user feels the algorithm and the setup together. Keep the KL / convex-Ω[V] / partial-trace detail (Details → The idea) as your own backing, not a user line.
> 2. **Then loop, one knob per turn.** Send ONE message: the recommended option first, labeled "(Recommended)" when there's a technical reason (the paper's value when reproducing), with a one-line why, then 1–2 real alternatives each with a one-line pro/con from the Default and Principle columns.
> 3. **Ask one question, then STOP and wait for the answer before the next knob.** Never batch; never accept a silent default.
> 4. **Walk the knobs leading with the two that decide the result:** (1) **operator basis & truncation** — the accuracy lever; too few interactions bias the exponents, fix is to enlarge until the leading eigenvalues stop moving; (2) **block size & rule** — a larger block needs fewer steps but costs more, and the rule must respect the model's symmetry (majority works; decimation fails). Then the rest.

### Cost & resource estimate

Wall time is **one measured rate × a fixed amount of work**: the work (flip count) is *exact*, only the updater throughput is unknown; memory is negligible, so compute is the binding resource. Model-generic scaling, written in four quantities: **L** = lattice linear size, **d** = spatial dimension, **n_w** = number of walkers (the independent Monte-Carlo chains run in parallel), **n_op** = number of operators in the basis (the kept couplings).

| Axis | Scaling |
|---|---|
| **Compute (FLOPs)** | ∝ (total sweeps) × Lᵈ × n_w flips; per flip O(1) for ΔH + occasional O(operator support — how many spins an operator spans, its footprint) for ΔV when a block vote tips; plus one n_op-operator lattice pass and an n_op×n_op covariance (Hessian) per step |
| **Memory** | O(Lᵈ·n_w) spins + O(n_op²) Hessian — small, rarely the constraint |
| **Throughput** | `vmap` over walkers is clean; the bias couples fine spins across each operator's block neighborhood, **breaking the simple checkerboard** (the usual trick of updating each interleaved sublattice in parallel) → within-lattice vectorization capped. The dominant 1–2 order-of-magnitude unknown; settle it with one jit timing probe |
| **Wall time** | flips ÷ updater rate, × number of optimizations (locate K_c bracket + the coarsening iterations the Jacobian needs) |

*2D Ising illustration (b=3, n_op≈18, n_w=16): at the paper's budget the flip count runs ~3×10¹⁰ (L=45) to ~7×10¹¹ (L=300) — small L laptop-feasible (minutes–hours CPU, ~10× faster GPU), the largest L wants a GPU/cluster (`/using-slurm`).*

> **Surface the cost to the user before any scale choice (reproduce-paper step 4).** Plain language: the wall time is *one measured rate × a fixed amount of work* — show the firm flip count for their lattice, name the single unknown (how fast the bias-coupled updater runs, which one short timing probe settles), and the per-size reality (small lattices on a laptop; the largest on a GPU/cluster). Let the user feel that **large-L compute is the only real gate** and that picking L sets the cost — never quote a single wall-time number before the probe.

## Details

Generic methodology; paper/model facts live in `/reproduce-paper` and `.knowledge/models/`. Math is unicode/plain.

### The idea

Near a critical point the coarse-grained (block-spin) distribution has a diverging correlation length, so sampling it directly suffers critical slowing down — the obstacle for standard MCRG. VMCRG sidesteps this: add a **bias potential V on the block spins** that forces their distribution to a simple **target p_t** (usually uniform → block spins uncorrelated → fast to sample).

The bias is found by minimizing a convex functional Ω[V] which — up to a V-independent constant — is the Kullback–Leibler divergence KL(p_t ‖ p_V) between the target and the biased block-spin distribution p_V. Minimizing it drives p_V → p_t.

The payoff is an identity: at the optimum, V_min = −H′ − log p_t + const, so for uniform p_t the **flattening bias is exactly minus the renormalized Hamiltonian**, H′ = −V_min. One convex optimization delivers both a fast, decorrelated sampler *and* the renormalized couplings K′_α = −J_min,α. (Reason: H′ is by definition −log of the block-spin distribution — an effective free energy — so a bias that cancels it to leave p_t must equal −H′ − log p_t.)

Two pieces make it practical:
- **Sampling without ever forming H′.** The biased average ⟨·⟩_V is sampled by ordinary Monte Carlo on the *fine* spins σ with weight e^{−H(σ)}·e^{−V(τ(σ))}; tracing out σ happens automatically, so the intractable partial trace defining H′ is never computed.
- **Exponents from the linearized map.** Differentiating the optimum condition w.r.t. the couplings gives the RG Jacobian ∂K′/∂K at K_c; its eigenvalues give the exponents (λ = b^y), split by spin-flip symmetry into even (thermal) and odd (magnetic).

Swendsen's classic MCRG is the **zero-bias corner**: take the target to be the model's own physical block distribution → V_min = 0 → Swendsen's formulae. A uniform target is the deliberate distortion that kills critical slowing down at no cost; the residual KL(p_t ‖ p_V) under a truncated basis is a built-in truncation-error monitor.

### Notation
- σ: fine spins; σ′ = τ(σ): block spins via block map τ; b: rescaling factor.
- H = Σ_α K_α S_α: Hamiltonian (operators S_α, couplings K_α); H′, K′_α: renormalized.
- V = Σ_α J_α S_α(σ′): bias potential; p_t: target; p_V ∝ e^{−(H′+V)}: biased block-spin distribution.
- Ω[V]: convex functional; ⟨·⟩_V: biased-ensemble average; ⟨·⟩_pt: target average; K_c: critical coupling.

### Algorithm

1. **Block transformation & exact effective Hamiltonian.** Choose σ′ = τ(σ) (e.g. 3×3 majority, b=3). The block-spin distribution is the constrained partial trace p(σ′) = (1/Z) Σ_σ δ(τ(σ),σ′) e^{−H(σ)} = e^{−H′(σ′)}/Z′ (2), Z′=Z, so H′(σ′) = −log Σ_σ δ(τ(σ),σ′) e^{−H(σ)} (4). H′ generically grows all symmetry-allowed operators (even products only, zero-field Ising); Eq 4 is intractable and never evaluated.

2. **Variational functional.** Ω[V] = log(Σ_σ′ e^{−[H′+V]} / Σ_σ′ e^{−H′}) + Σ_σ′ p_t V (5). Convex (first term is a log-partition); unique minimizer (up to a constant) gives H′ = −V_min − log p_t + const (6) and p_{V_min} = p_t (7).

3. **Parametrize, gradient, Hessian.** V_J = Σ_α J_α S_α(σ′) (8) → Ω convex in J. Gradient ∂Ω/∂J_α = −⟨S_α⟩_V + ⟨S_α⟩_pt (9) — target minus biased average; zero at the optimum (⇔ p_V = p_t). Hessian ⟨S_α S_β⟩_V − ⟨S_α⟩_V⟨S_β⟩_V (10) — connected covariance, PSD (convexity).

4. **The sampling crux.** Since V depends on σ only through σ′=τ(σ), e^{−V} pulls inside the trace: e^{−(H′+V)} = Σ_σ δ(τ(σ),σ′) e^{−H(σ)} e^{−V(τ(σ))}. So the biased block distribution is the marginal of the fine-spin distribution P(σ) ∝ e^{−H(σ)} e^{−V(τ(σ))}. **In practice:** run Metropolis on the *fine* spins σ with weight e^{−H}e^{−V(τ(σ))}; for any coarse operator, compute σ′=τ(σ) per sample and average. H′ and the partial trace are never formed. ⟨·⟩_pt is analytic for simple p_t (uniform → independent fair coins).

5. **Optimize.** Minimize Ω(J) by averaged SGD (Bach–Moulines): keep a running mean J̄ₙ = (1/n) Σ_i J^[i] and build the bias from it; update J^[n+1] = J^[n] − µ[Ω′(J̄) + Ω″(J̄)(J^[n] − J̄)] from noisy gradient (9)/Hessian (10), with multiple walkers cutting variance. Sweeps/step are small (noise averages out); reset the running mean at 10% and 20% of the trajectory to remove its lag; µ shrinks with L (5×10⁻⁵ → 5×10⁻⁶). Take J̄ at the plateau as J_min.

6. **Renormalized couplings & truncation.** With uniform p_t, K′_α = −J_min,α (11–12) — *mind the minus.* Drop operators with small |J_min,α| (variational truncation); gauge quality by the residual departure of p_{V_min} from p_t.

7. **Jacobian & exponents.** The optimum condition (9)=0 defines K′ implicitly as a function of K. Perturb K_β→K_β+δK_β; K′ responds by δK′. Linearizing (13→15) gives A_βγ = Σ_α (∂K′_α/∂K_β) B_αγ (15), with biased-ensemble connected correlations
   - A_βγ = ⟨S_β(σ) S_γ(σ′)⟩_V − ⟨S_β(σ)⟩_V⟨S_γ(σ′)⟩_V (16) — **fine** operator S_β(σ) vs **coarse** S_γ(σ′) (response to the bare coupling);
   - B_αγ = ⟨S_α(σ′) S_γ(σ′)⟩_V − ⟨S_α(σ′)⟩_V⟨S_γ(σ′)⟩_V (17) — two **coarse** operators (response to the renormalized coupling).

   Solve the linear system (15) for the Jacobian ∂K′/∂K (invert B); diagonalize. Eigenvalues give exponents via λ = b^y. Spin-flip symmetry block-diagonalizes the Jacobian into **even** (thermal → ν) and **odd** (magnetic) sectors — build A, B block-diagonally in parity. Setting the target to the unbiased block distribution makes V_min=0 and collapses (16–17) to **Swendsen's** formulae.

8. **Locate K_c and evaluate there.** Bracket K_c by the flow direction of the couplings across iterations (grow → ordered, shrink → disordered); at K_c they stay constant (paper: window 0.4355–0.4365, b=3; fixed at 0.436). Evaluate the Jacobian at K_c — e.g. couplings after iteration 1 = K_α, after iteration 2 = K′_α; an accurate K_c lets a single coarsening step suffice.

## Verification

### Intermediate (mid-run)
- **Optimization converged.** The running-average J̄ curves flatten to a plateau — read it *after* the periodic running-average resets (those are deliberate, non-physical jumps, not coupling flow). A J̄ still drifting at the trajectory's end = not converged. Per-step gradient/Hessian noise is expected.
- **Critical slowing down removed.** Block-averaged standard error vs block size (Flyvbjerg–Petersen) plateaus at small block size in the biased ensemble — far later in the unbiased one. A biased curve that plateaus slowly, or whose plateau grows with system size, means the bias isn't decorrelating → eigenvalues won't converge.
- **Bias adequate (truncation monitor).** The biased block-spin distribution approaches the target — equivalently ⟨S_α⟩_V → ⟨S_α⟩_pt operator by operator (gradient → 0). A persistent gap → the operator basis is too truncated.
- **Coupling flow.** Monotonic drift away from K_c (grow above, shrink below), constant at K_c. Near K_c the direction is noise-sensitive — don't over-read a single close pair.

### Final verification + expert criticism
- **Benchmark.** The leading even (thermal) and odd (magnetic) Jacobian eigenvalues reproduce the model's known exponents via λ = b^y, *simultaneously*. A few-percent residual at fixed basis is truncation, not finite size, so it need not shrink with system size.
- **Fixed point & bracketing.** Renormalized couplings stay constant across iterations at K_c (drift → off the fixed point → biased exponents); the bracketing window — flow reversing across K_c — is consistent across sizes.
- **Convergence & cross-checks.** Enlarge the operator basis until the leading eigenvalues stop moving; cross-check biased vs unbiased (consistent up to a small truncation offset; the unbiased fails to converge at large size). Error bars from block averaging and the spread over walkers.

> **Criticize:** eigenvalues read at an un-converged K_c (couplings still drifting); too-small basis with no eigenvalue-convergence test; reading instantaneous instead of running-average coefficients, or stopping before the plateau; single-lattice finite-size bias (the L and L/b lattices carry different errors — use two lattices to cancel); sign error K′ = −J_min; mistaking the running-average resets for coupling flow; mistaking noise-driven flow inversion near K_c for a K_c shift; trusting an unbiased eigenvalue at large size; conflating the truncation-error-free tangent space with the truncation-sensitive exponents.

## Citations

Rendered under `.knowledge/literature/monte-carlo-renormalization-group/`:

- `1707.08683_variational-approach-to-monte-carlo-renormalization-group.md` + `1707.08683_SM_supplementary-material.md` — Wu & Car, PRL 119, 220602 (2017) — variational MCRG; the primary source for Details, Step 3, and Verification (with its Supplementary Material).
- `1903.08231_determination-of-the-critical-manifold-tangent-space-and-cur.md` — Wu & Car, PRE 100, 022138 (2019) — critical-manifold tangent space + curvature.
- `1810.09579_monte-carlo-renormalization-group-for-systems-with-quenched.md` — Wu & Car, arXiv:1810.09579 (2018) — MCRG for quenched disorder.
- Foundational classic MCRG (not yet in `.knowledge`; pull with `/download-ref`): Swendsen, PRL 42, 859 (1979) and PRL 52, 1165 (1984).
- JAX setup, primitives, and runtime live in `/using-jax`.

