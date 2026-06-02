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

- Tool skill: *(set in Step 2 — software routing)*
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
