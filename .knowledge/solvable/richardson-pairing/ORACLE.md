# Richardson pairing (reduced BCS) — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: S

## Hamiltonian & conventions

$$ H = \sum_{j=1}^{N} \varepsilon_j\,(n_{j\uparrow}+n_{j\downarrow}) \;-\; g\sum_{j,k=1}^{N} b^\dagger_j b_k, \qquad b_j = c_{j\downarrow}c_{j\uparrow}, \quad \varepsilon_j = j $$

Conventions: the **reduced BCS / Richardson pairing** Hamiltonian on `N` doubly-degenerate single-particle levels `ε_j = j` (`j=1..N`), with `M` pairs and pairing strength `g>0` (attractive). `b^\dagger_j = c^\dagger_{j\uparrow}c^\dagger_{j\downarrow}` creates a pair on level `j`; the `j=k` terms of the pairing sum contribute the diagonal `-g\sum_j b^\dagger_j b_j`. We work in the **seniority-zero** sector: every level is either empty or doubly occupied (no broken/unpaired "blocked" levels), which holds the ground state for attractive `g` (verified in-card against the full Fock space). The natural per-pair level energy is `2ε_j`. See `.knowledge/conventions.md`.

Model-zoo sibling: none under `.knowledge/models/`; the pair-hopping structure is the finite-level cousin of the attractive Hubbard/BCS physics (`.knowledge/models/attractive-hubbard`), but the Hamiltonian and exact solution here are the level-space Richardson model, not a lattice.

## Solvability statement

T3 (Bethe ansatz / Richardson–Gaudin): the reduced BCS Hamiltonian is exactly solvable by Richardson's 1963 exact eigenstate construction, a Bethe-ansatz-type solution [@Richardson1963]. In the seniority-zero sector the `M`-pair eigenstates are products of collective pair-creation operators whose `M` spectral parameters `E_a` (the Richardson roots) solve the coupled Richardson equations, and the eigen-energy is the plain sum of roots `E=\sum_a E_a`. Written consistently with the Hamiltonian above (attractive `-g` pairing, pair-level energy `2ε_j`), the equations are `1 - g\sum_{j} 1/(2ε_j-E_a) - 2g\sum_{b\ne a} 1/(E_a-E_b)=0` for each `a`. As `g\to0^+` the roots start at `2ε_a` of the `M` lowest levels; as `g` grows a pair of real roots can collide at a level `2ε_j` and split into a complex-conjugate pair, so the roots must be tracked in the complex plane. This is Tier B (integrable), not a single closed form: the roots are the solution of `M` coupled nonlinear (Bethe) equations, solved here by homotopy in `g`, not a closed-form expression.

## The Richardson story

Because each pairing move `b^\dagger_j b_k` hops a whole pair between levels, the seniority-zero dynamics is that of `M` hard-core "pair bosons" on `N` levels. Richardson showed the exact eigenstates are `|\{E\}\rangle = \prod_{a=1}^{M} B^\dagger_a|0\rangle` with `B^\dagger_a = \sum_j b^\dagger_j/(2ε_j-E_a)`; imposing that this be an eigenstate collapses to the `M` Richardson equations for the `E_a`. The **homotopy/continuation** solver starts from `g\to0^+` (roots `E_a\to2ε_a`, the `M` lowest pair levels) and marches `g` up: at small `g` all roots are real and just below their bare levels; past a critical coupling two roots meet on the real axis at a level `2ε_j` and move off as a complex-conjugate pair `x\pm iy`. The **sum** of roots stays exactly real (conjugate pairs cancel their imaginary parts), reproducing the real ground energy. The solver handles the collision by seeding a conjugate imaginary part at a near-degeneracy and refining each `g`-step with a residual-guarded step size.

## Exact results

- Exact eigenstates of the reduced BCS pairing Hamiltonian from the Richardson equations; energy `E=\sum_{a=1}^{M}E_a` [@Richardson1963]
- Richardson equations (this card's convention): `1 - g\sum_{j}1/(2ε_j-E_a) - 2g\sum_{b\ne a}1/(E_a-E_b)=0`, `a=1..M` [@Richardson1963]
- `g\to0^+`: `E_a\to2ε_a` (the `M` lowest levels), so `E\to2(ε_1+\dots+ε_M)`; the approach is linear in `g` (leading `-gM` from the diagonal pairing term)
- Root collisions/complexification: with growing `g`, pairs of roots leave the real axis as complex-conjugate pairs at the pairing points `2ε_j`; the energy `\sum_a E_a` remains real [@Richardson1963]
- Ground state is seniority-zero (fully paired) for attractive `g` — matched here to the full spinful Fock-space ED in the `2M`-particle sector

## Oracle script

`python oracle.py --N 6 --M 3 --g 0.5` → prints `e0` (`=\sum_a E_a`), `richardson_roots` (as `[re, im]` pairs), `n_levels`, `n_pairs`. Importable: `compute(N=6, M=3, g=0.5)`; the solver is `richardson_roots(N, M, g)` and the ground truth is `seniority_zero_ed(N, M, g)`.

Self-test anchors: (1) **ground truth** — `\mathrm{Re}\sum_a E_a` equals the seniority-zero ED (`C(N,M)`-dim pair-occupation Hamiltonian) at `1e-10` for `(N,M)=(6,3)`, `g\in\{0.1,0.5,1.0\}`; (2) the root-sum is real (`|\mathrm{Im}\sum_a E_a|<1e-12`) and the roots solve the Richardson equations (residual `<1e-9`); (3) `g\to0` limit — at `g=10^{-8}` the roots sit at `2ε_a` and the energy matches both the ED (`1e-10`) and the physical limit `2(ε_1+ε_2+ε_3)` (`1e-6`, the offset being `\sim Mg`); (4) the seniority-zero ground state is the **true** ground state — matched to a full spinful Fock-space ED in the `2M`-particle sector for `(N,M)\in\{(3,1),(4,2)\}`; (5) continuation robustness at other `(N,M)`.

## Benchmarks

`e0 = \sum_a E_a` (total ground energy). Seniority-zero ED = Richardson-root sum (equal to `1e-10`), `ε_j=j`, `N=6`, `M=3`.

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0` | `N=6`, `M=3`, `g=0.1` | `11.6798192419` | [@Richardson1963] (roots = ED) |
| `e0` | `N=6`, `M=3`, `g=0.5` | `9.8015279710` | [@Richardson1963] (roots = ED) |
| `e0` | `N=6`, `M=3`, `g=1.0` | `5.8108407474` | [@Richardson1963] (roots = ED) |
| `e0` (`g\to0`) | `N=6`, `M=3` | `2(ε_1{+}ε_2{+}ε_3)=12` | [@Richardson1963] |
| roots at `g=1.0` | `N=6`, `M=3` | one real `\approx0.8319`, one conjugate pair `2.4894\pm2.5843i` | this card (solver) |

The three finite-`g` energies are exact to `1e-10` (Richardson-root sum pinned to the seniority-zero ED). At `g=1.0` two of the three roots have complexified into a conjugate pair — the physical fingerprint of the pairing collision — while their sum stays real.

## Verification recipes

- To check a pairing/BCS ED (or a Richardson-equation solver): build the seniority-zero Hamiltonian on the `C(N,M)` pair-occupation basis — diagonal `\sum_{j\in\mathrm{occ}}2ε_j - gM`, off-diagonal `-g` between configurations differing by one pair move — and reproduce `e0(N=6,M=3,g=0.5)=9.8015279710` to `1e-8`. A mismatch usually means the diagonal `-gM` term (the `j=k` part of the pairing sum) was dropped, a `2ε_j`-vs-`ε_j` level convention slip, or a sign on `g`.
- To check a Richardson-root solver: the root-sum must equal the ED energy AND the roots must solve `1 - g\sum_j1/(2ε_j-E_a) - 2g\sum_{b\ne a}1/(E_a-E_b)=0`. If your roots stay real at large `g` (and the sum drifts from the ED), your continuation is stuck on the real axis at a pairing point `2ε_j` — the correct branch is a complex-conjugate pair.
- To confirm the seniority-zero reduction: for attractive `g` the full-Fock-space ground state (in the `2M`-particle sector) equals the seniority-zero energy — a broken-pair (seniority `>0`) state never wins at `g>0`.

## Key reference

[@Richardson1963] — R. W. Richardson, "A restricted class of exact eigenstates of the pairing-force Hamiltonian", Phys. Lett. **3**, 277 (1963): the exact algebraic-Bethe-ansatz eigenstates of the reduced BCS Hamiltonian and the Richardson equations whose root-sum is the energy — the level-space integrable model this card scripts (the rational Gaudin limit; cf. `gaudin-central-spin`). Rendered: _(Wave 3)_.
