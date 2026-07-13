# Triangular-lattice Ising model — exact-solution oracle

Technique: T2 (2D classical / transfer matrix) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H(\{s\}) = -J \sum_{\langle ij\rangle} s_i s_j, \qquad s_i = \pm 1, \quad \text{triangular lattice (6 neighbours), PBC (torus)} $$

This is a **classical statistical model**: a Boltzmann ensemble, not an operator spectrum.

- Configurations: each site carries a classical spin $s_i \in \{+1, -1\}$; there are $2^{N}$ configurations on $N$ sites. Partition function $Z = \sum_{\{s\}} e^{-\beta H}$.
- Lattice: the triangular net, where every site has **6** nearest neighbours. Realized on an $L\times W$ grid as three bond families — horizontal (in-row), vertical (row-to-row, same column), and one diagonal family (row-to-row, column $j\to j{+}1$). The diagonal points one way along a row; this is what makes the triangular net non-bipartite.
- Units: $k_B = 1$, $\beta = 1/T$, $K \equiv \beta J$. Free energy per site $f = -T(\ln Z)/N$; residual entropy per site $s_0 = \lim_{T\to 0}(\ln Z)/N + \beta u$ (the $T=0$ ground-state entropy).

See `.knowledge/conventions.md` for the shared sign/units conventions. There is no model-zoo card for the classical triangular Ising model; the closest sibling is the square-lattice `ising-2d-onsager` card in this catalog.

**The headline is frustration.** Because the triangular lattice is not bipartite, the sign of $J$ is physical, and the two signs behave completely differently:

- **Ferromagnet ($J>0$):** all bonds can be satisfied simultaneously; there is a finite-temperature ordering transition at $kT_c/J = 4/\ln 3$ [@Wannier1950].
- **Antiferromagnet ($J<0$):** on any triangle the three AFM bonds cannot all be satisfied — one is always frustrated. The consequence is dramatic: **no finite-temperature transition at all ($T_c = 0$)** and a **macroscopically degenerate ground state** with a nonzero residual entropy per site $s_0 = \mathrm{Cl}_2(\pi/3)/\pi \approx 0.3231$ [@Wannier1950]. This FM/AFM asymmetry — order vs. a disordered, extensively degenerate ground manifold — is the central fact of this card.

## Solvability statement

T2 (2D classical / transfer matrix): the model is solved by diagonalizing the row-to-row transfer matrix. Exactly known and implemented here: the FM critical temperature (closed form), the AFM $T=0$ residual entropy (Wannier's exact integral, in closed form via the Clausen function), and the **exact finite $L\times W$-torus $\ln Z$** for both signs of $J$ from the transfer matrix, ground-truthed against brute-force enumeration. **Not exact:** nothing — the triangular Ising model is exactly solvable in full (Wannier 1950; the free energy, specific heat, and — for the FM — critical behaviour are all exactly known). Some exact quantities are simply not implemented in `oracle.py` (out of this card's scope): the full thermodynamic-limit free energy $f(T)$ (the finite-width transfer matrix gives only a width-limited strip value, documented below as such), the AFM spin-spin correlations (algebraically decaying, exactly known [@Wannier1950]), and the FM critical exponents. The AFM residual entropy is a genuine $T=0$ ground-state entropy, not an approximation to a finite-$T$ quantity.

## Exact results

- FM critical temperature: $kT_c/J = \dfrac{4}{\ln 3} \approx 3.6409569$ [@Wannier1950]
- AFM residual entropy per site: $s_0 = \dfrac{2}{\pi}\displaystyle\int_0^{\pi/3}\ln(2\cos x)\,dx = \dfrac{\mathrm{Cl}_2(\pi/3)}{\pi} \approx 0.3230659472$, where $\mathrm{Cl}_2$ is the Clausen function and $\mathrm{Cl}_2(\pi/3)$ is its maximum value (Gieseking's constant, $\approx 1.01494161$) [@Wannier1950]
- AFM transition temperature: $T_c = 0$ (frustration destroys long-range order at every $T>0$) [@Wannier1950]
- Finite $L\times W$ torus (both signs of $J$): $Z = \operatorname{tr} T^{L}$, with the width-$W$ row-to-row transfer matrix $T_{ab} = \exp\!\big[-\beta\big(\tfrac12 E_{\rm row}(a) + \tfrac12 E_{\rm row}(b) + E_{\rm inter}(a,b)\big)\big]$, $E_{\rm row}(s) = -J\sum_j s_j s_{j+1}$ and $E_{\rm inter}(a,b) = -J\sum_j (a_j b_j + a_j b_{j+1})$. $T$ is **non-symmetric** (the diagonal bond breaks $a\leftrightarrow b$ symmetry); its Perron eigenvalue is real and positive, the rest come in complex-conjugate pairs, and $\operatorname{tr}T^L$ is real.

> **Note on the residual-entropy value.** Wannier's 1950 paper first quoted $0.3383$; this was corrected in a **1973 erratum** [@Wannier1950]. The correct modern value is $\mathrm{Cl}_2(\pi/3)/\pi = 0.3230659472\ldots$, verified here three independent ways (adaptive quadrature, a 256-point Gauss–Legendre rule, and the closed form). It is **not** $0.3230659669$ (a value that circulates in some secondary sources but disagrees with the integral at the 8th digit).

## Quantum / duality connection

Like the square-lattice Ising model, the 2D classical triangular Ising model maps under the transfer matrix to a 1D quantum chain; the anisotropic limit relates the classical ensemble to a $(1{+}1)$-dimensional quantum path integral. The frustrated AFM triangular Ising model is the canonical example of geometric frustration and is the classical parent of a large family of frustrated magnets and quantum spin liquids. Its extensive ground-state degeneracy — the reason $s_0>0$ — is the same phenomenon that, upon adding quantum dynamics, drives triangular-lattice quantum spin-liquid physics.

## Oracle script

`python oracle.py --T 2.0 --J 1.0 --L 4` → prints `tc_ferro`, `residual_entropy_afm`, `logZ_finite` (natural log of the exact $L\times L$-torus $Z$ at $\beta=1/T$ with coupling `J`), `free_energy_per_site_width6`. Importable: `compute(T=2.0, J=1.0, L=4)`; individual functions `tc_ferro()`, `residual_entropy_afm()`, `logZ_finite(L, beta, J, W=None)` (returns $\ln Z$, log-space via a scaled matrix power), `free_energy_per_site(T, J, W=6)`.

`free_energy_per_site_width6` is the free energy of an infinitely long **strip of width 6** ($f = -T\ln\lambda_{\max}/W$, $\lambda_{\max}$ the transfer-matrix Perron eigenvalue) — this is **width-limited (semi-1D), NOT the 2D thermodynamic limit**, and converges to the bulk value only as $W\to\infty$.

Self-test anchors: (1) `tc_ferro()` $= 4/\ln 3$ to `1e-12`; (2) `residual_entropy_afm` — two independent quadratures agree to `1e-10` and both match the closed form $\mathrm{Cl}_2(\pi/3)/\pi$ to `1e-9`; (3) **ground truth** — `logZ_finite` equals brute-force enumeration over all $2^{16}$ configurations on the $4\times4$ torus, for **both** $J=\pm 1$ at $\beta\in\{0.3, 0.8\}$, relative tol `1e-10` (log-space); plus a guard that the width-6 strip free energy is finite and lower for the FM than the AFM at $T=2$.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `tc_ferro` | $J=1$ | $4/\ln 3 \approx 3.6409569$ | [@Wannier1950] |
| `residual_entropy_afm` | $J<0$, $T\to 0$ | $\mathrm{Cl}_2(\pi/3)/\pi \approx 0.3230659$ | [@Wannier1950] |
| `logZ_finite` | $4\times4$ torus, $\beta=0.8$, $J=1$ | $39.0942362$ (= enumeration) | this work |

## Verification recipes

- To check a classical Monte Carlo run of the FM triangular Ising model: compare its estimated $T_c$ against `tc_ferro()`.
- To check a claimed AFM ground-state entropy (e.g. from a residual-entropy measurement or a tensor-network estimate): compare against `residual_entropy_afm()`, tolerance set by the method's error bars.
- To check a finite $L\times W$ transfer-matrix / tensor-network / enumeration code (either sign of $J$): compare $\ln Z$ against `logZ_finite(L, beta, J)`, tolerance `1e-8` (exact).

## Key reference

[@Wannier1950] — Wannier's exact treatment of the triangular Ising net: source of the FM critical temperature $4/\ln 3$, the AFM absence of a transition, and the frustrated antiferromagnet's residual entropy (value corrected in the 1973 erratum to $\mathrm{Cl}_2(\pi/3)/\pi$). Rendered: _(Wave 3)_.
