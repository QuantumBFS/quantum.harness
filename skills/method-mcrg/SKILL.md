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

> **When this card is invoked, before any choice, orient the user in plain language (no jargon) with this table, filling the right column with *their* actual problem — their Hamiltonian, lattice, and setup. If those aren't fixed yet, use the table to elicit them; if the user has no specific problem in mind, fall back to 2D Ising (square, nearest-neighbor) as the illustration. Gloss each term on first use.**

| Ingredient | What it is | Your setup |
|---|---|---|
| Starting Hamiltonian H | the spin model's interaction strengths (couplings K) | *(user's model + couplings; default 2D Ising H = −K Σ⟨ij⟩ sᵢsⱼ)* |
| Coarse-graining | group spins into blocks, one coarse spin per block by a fixed rule | *(block size + rule; default 3×3 majority, b=3)* |
| Effective Hamiltonian H′ | the new couplings K′ the coarse spins obey | *(generated couplings to keep)* |
| Target | renormalized couplings + critical exponents | *(which exponents / couplings wanted)* |
| What's approximated | infinite generated couplings → keep a finite short-range set | *(how many couplings kept)* |
| Variant | Swendsen or Variational MCRG | *(which, and why)* |

## Sources

- Tool skill: `/using-jax` — the algorithm is implemented from scratch on JAX (see Step 2).
- Primary literature (rendered in `.knowledge/literature/monte-carlo-renormalization-group/`):
  - **1707.08683** — Wu & Car, PRL 119, 220602 (2017) — variational MCRG, 2D Ising.
  - **1903.08231** — Wu & Car, PRE 100, 022138 (2019) — critical-manifold tangent space + curvature.
  - **1810.09579** — Wu & Car, arXiv:1810.09579 (2018) — MCRG for quenched disorder.

## Select method — step 1

### Suited for
- Extracting **critical exponents** (thermal, magnetic, correction-to-scaling — from RG eigenvalues via y = ln λ / ln b) and **renormalized coupling constants** of lattice models at/near a critical fixed point.
- Real-space and configuration-based: works directly from Monte-Carlo-sampled configurations (the variational variant samples inside a bias-potential optimization).
- **Variational variant** when critical slowing down blocks large systems, or when you want the truncation error estimated.
- Validated mainly in **2D and 3D**; the formalism is dimension-general.

### Worked examples

All from the variational MCRG lineage; rendered papers in `.knowledge/literature/monte-carlo-renormalization-group/`. **Use this with the user: anchor their problem to the nearest row and quote its scale as a concrete reference point** (e.g. "closest to 2D Ising critical exponents — they reached L=300 with 16 walkers").

| Ref | Model | Problem type | Scale | Calculated |
|---|---|---|---|---|
| 1707.08683 | 2D Ising, square | critical exponents | b=3 (3×3 majority); L=45–300; 13 couplings (7 even+6 odd); ~10⁶ sweeps; 16 walkers | even/odd Jacobian eigenvalues → thermal & magnetic exponents; renormalized couplings |
| 1903.08231 | 2D Ising, square | critical-manifold tangent space + curvature | b=2; L=256; n=4–5; 16×3×10⁶ sweeps | tangent-space normal vectors + curvature of the critical manifold |
| 1903.08231 | 3D Ising, cubic | tangent space | b=2; L=64; n=3; 16×3×10⁵ sweeps | tangent space in 8-coupling space |
| 1903.08231 | 2D anisotropic Ising | tangent space (marginal operator) | b=2; 4 couplings | tangent space with a marginal operator |
| 1903.08231 | 2D tricritical Ising (Blume–Capel) | tangent space, co-dim 2 | b=2; L=256; n=5; 5–6 couplings | tangent space confirming co-dimension 2 |
| 1810.09579 | 2D dilute Ising | disorder critical exponent | b=2; L=128(+256); Metropolis+Wolff; 3 couplings | leading even eigenvalue → disorder critical exponent |
| 1810.09579 | 2D & 3D RFIM | disorder RG flow | b=2; L=64(+128) 2D | RG flow to the disorder fixed point |
| 1810.09579 | random TFIM chain | disorder RG flow (quantum→2D) | m=8 Trotter, β=16, 128×128; b=2 | RG flow to a strong-disorder fixed point |

References: the rendered files under `.knowledge/literature/monte-carlo-renormalization-group/` (see Sources) — each carries its source URL in the frontmatter.

### Route elsewhere — when MCRG isn't the right tool

MCRG fits only when the target is **critical-point data** (exponents or renormalized couplings), or a quantum model mapped to classical.

> **When the user's goal falls outside this, interact by these principles:** recognize it before any setup; explain *what fits better and why* in a short table (what / why); use plain language, no jargon, precise and concise; stay warm — guide, don't dismiss.

### Options & trade-offs

| Variant | Good at | Weak at | When to use |
|---|---|---|---|
| **Variational MCRG** | no critical slowing down → large L near T_c; truncation error estimable; couplings + exponents from one convex optimization | extra bias-potential optimization to implement and tune | large systems near criticality, or when you want truncation control |
| **Swendsen MCRG** | simple, minimal code; textbook | critical slowing down at large L; truncation uncontrolled | small/moderate L; a quick exponent estimate; baseline/validation |

### Routing — surface to the user

> **When routing, present the choice to the user as a table** — precise, concise, plain language: which variant, when to choose it, and which fits their case. Draw the *why* from Options & trade-offs above, and make the user feel the one consequence that actually decides it: **critical slowing down** — on a large lattice near the critical point, Swendsen's sampling crawls and may never converge, while the variational bias keeps it fast — or, when reproducing, which variant the paper used. Don't decide silently; let them see the choice.

## Select software — step 2

### No canonical open-source code
There is **no canonical open-source code repository** for MCRG — the variational method's original code was never released, and no maintained package implements it. **Implement from scratch.** The algorithm lives in `## Details`; the primitives that express it live in `/using-jax`.

### Route — Python + JAX
The compute is a custom classical Monte Carlo (Metropolis/Wolff) sampling multiple walkers over many sweeps, plus stochastic optimization of the bias potential and a small Jacobian eigensolve. The two JAX features that matter:

- **`vmap`** — run the multiple walkers together in one vectorized pass.
- **`jit`** — compile the Metropolis/Wolff sweep so sampling is fast.

(Autodiff is *not* the reason for JAX — the optimization gradients are Monte Carlo estimators, not differentiated.)

### Surface to the user

> **Surface the software choice to the user — don't default silently.** In plain language, a short what/why table: (1) there's no off-the-shelf MCRG tool, so this is a **from-scratch build** — be honest about the cost (more code to write, and it must be validated against known/exact answers); (2) the route is **JAX**, because the work is sampling many walkers over many sweeps, which `vmap` + `jit` make fast — plain Python would crawl at large L. Even with no competing option, let the user feel *why* this is the deliberate choice, not an accident.

### Handoff
Invoke **/using-jax** once the route is fixed — it owns JAX CPU/GPU setup, jit/vmap/PRNG mechanics, and runtime troubleshooting. This card owns the algorithm (`## Details`), the operator basis, and the convergence plan.

## Method setup — step 3

Conceptual knobs and the trick behind each. Values are from 1707.08683 (2D Ising, square). Software-side values (JAX device, JIT boundary) live in `/using-jax`. *(Math is unicode/plain per AGENTS.md; surface it as LaTeX on an app, plain in a terminal.)*

| Knob | Controls | Value in the paper | Trick / effect |
|---|---|---|---|
| **Block size & rule** | the rescaling factor b (linear shrink per step) and how each block maps to one coarse spin | 3×3 majority rule (b=3); also 2×2, 16×16 | larger b → fewer coarsening steps, less accumulated truncation + finite-size error, but costlier; majority rule = sign of the block's spin sum; decimation-type rules proliferate couplings and fail |
| **Operator basis & truncation** | which interaction terms the renormalized (coarse) Hamiltonian is expanded in, and how many are kept | 26 initial (13 two-spin + 13 four-spin; only even-parity terms, by the zero-field Ising symmetry) → keep 13 (drop any renormalized coupling below 0.001 after one preliminary step) | dominant accuracy lever; the drop is variational — a near-zero optimized coefficient flags an unimportant operator; too small a basis biases the exponents, so enlarge until the leading eigenvalues converge |
| **Target distribution** | the block-spin distribution the bias potential forces | uniform (flat) | a uniform target decorrelates the block spins → removes critical slowing down (sampling stalls near the critical point); also makes the target-side averages analytic and lets the renormalized couplings be read straight off the optimized bias |
| **Coarsening steps** | number of successive coarse-grainings per run | 5 (+1 preliminary to set the truncation) | deeper flow vs accumulating per-step error; all steps reuse the initial lattice |
| **Sampling budget** | the Monte Carlo effort behind each optimization step | 1240 optimization steps × 20 sweeps × 16 walkers (independent parallel runs); ~10⁶ sweeps total, 5×10⁵ at L=300 | more walkers lower the variance of the biased averages; the averaged stochastic-gradient optimizer tolerates the residual noise |
| **Locating the critical coupling K_c** | K_c — the coupling at which the system is exactly critical (the fixed point where couplings stop flowing), where the exponents are defined | bracket 0.4355–0.4365 (b=3); fix K_c=0.436 | bracket by the flow direction of the renormalized couplings (grow → ordered, shrink → disordered); at K_c they stay constant; an accurate K_c lets a single coarsening step give the Jacobian |
| **Optimizer** | the stochastic minimization of the bias potential's (convex) cost function | averaged stochastic gradient descent (Bach–Moulines); step size in the Supplement | constant-step averaged SGD handles the Monte Carlo noise in the gradient and curvature estimates; exact settings are in the unavailable Supplement |
| **Spin update** | the Monte Carlo move sampling the biased ensemble | Metropolis | local updates suffice — the bias potential, not cluster moves, removes critical slowing down |

> **Surface the consequential knobs to the user loudly, not silently.** Two decide the result and must be felt: (1) the **operator basis & truncation** — the main accuracy lever; keeping too few interactions biases the exponents, and the fix is to enlarge the set until the leading eigenvalues stop moving; (2) the **block size & rule** — a larger block needs fewer coarsening steps but costs more, and the rule must be sensible (majority works; decimation-type rules fail). Present each with its consequence and the paper's value, and let the user choose.

## Details

Generic methodology; paper/model facts live in `/reproduce-paper` and `.knowledge/models/`. Math is unicode/plain (surface as LaTeX on an app).

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

5. **Optimize.** Minimize Ω(J) by averaged stochastic gradient descent (Bach–Moulines) from noisy gradient (9)/Hessian (10) over short MC runs; multiple independent walkers reduce variance; the iterate average → J_min.

6. **Renormalized couplings & truncation.** With uniform p_t, K′_α = −J_min,α (11–12) — *mind the minus.* Drop operators with small |J_min,α| (variational truncation); gauge quality by the residual departure of p_{V_min} from p_t.

7. **Jacobian & exponents.** The optimum condition (9)=0 defines K′ implicitly as a function of K. Perturb K_β→K_β+δK_β; K′ responds by δK′. Linearizing (13→15) gives A_βγ = Σ_α (∂K′_α/∂K_β) B_αγ (15), with biased-ensemble connected correlations
   - A_βγ = ⟨S_β(σ) S_γ(σ′)⟩_V − ⟨S_β(σ)⟩_V⟨S_γ(σ′)⟩_V (16) — **fine** operator S_β(σ) vs **coarse** S_γ(σ′) (response to the bare coupling);
   - B_αγ = ⟨S_α(σ′) S_γ(σ′)⟩_V − ⟨S_α(σ′)⟩_V⟨S_γ(σ′)⟩_V (17) — two **coarse** operators (response to the renormalized coupling).

   Solve ∂K′/∂K = A B⁻¹ (matrix inversion); diagonalize. Eigenvalues give exponents via λ = b^y. Spin-flip symmetry block-diagonalizes the Jacobian into **even** (thermal → ν) and **odd** (magnetic) sectors — build A, B block-diagonally in parity. Setting the target to the unbiased block distribution makes V_min=0 and collapses (16–17) to **Swendsen's** formulae.

8. **Locate K_c and evaluate there.** Bracket K_c by the flow direction of the couplings across iterations (grow → ordered, shrink → disordered); at K_c they stay constant (paper: window 0.4355–0.4365, b=3; fixed at 0.436). Evaluate the Jacobian at K_c — e.g. couplings after iteration 1 = K_α, after iteration 2 = K′_α; an accurate K_c lets a single coarsening step suffice.

