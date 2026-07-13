# 2D square-lattice Ising model (Onsager) — exact-solution oracle

Technique: T2 (2D classical / transfer matrix) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H(\{s\}) = -J \sum_{\langle ij\rangle} s_i s_j, \qquad s_i = \pm 1, \quad \text{square lattice, PBC (torus)} $$

This is a **classical statistical model** — the first in the catalog — so the setup is a Boltzmann ensemble, not an operator spectrum:

- Configurations: each site carries a classical spin $s_i \in \{+1, -1\}$; a configuration is one assignment $\{s\}$ of all $mn$ spins. There are $2^{mn}$ of them.
- Partition function: $Z = \sum_{\{s\}} e^{-\beta H(\{s\})}$, the sum running over all configurations.
- Units: $J = 1$ (ferromagnetic Ising coupling), $k_B = 1$, so $\beta = 1/T$ and $K \equiv \beta J = 1/T$ is the dimensionless coupling. The sum $\langle ij\rangle$ is over nearest-neighbour bonds, each counted once.
- Free energy per site $f = -T (\ln Z)/N$; internal energy per site $u = -\partial_\beta (\ln Z)/N = f - T\,\partial_T f$; spontaneous magnetization $m = \lim_{h\to 0^+}\langle s_i\rangle$.

See `.knowledge/conventions.md` for the shared sign/units conventions. There is no model-zoo card for the classical 2D Ising model; the closest physics card is the quantum `transverse-field-ising` (`.knowledge/models/transverse-field-ising/MODEL.md`), linked by the transfer-matrix mapping described under Solvability.

## Solvability statement

T2 (2D classical / transfer matrix): the model is solved by diagonalizing the row-to-row transfer matrix. Onsager (1944) obtained the thermodynamic-limit free energy; Kaufman (1949) recast the transfer matrix as a product of anticommuting spinor rotations, giving the **exact partition function of any finite $m\times n$ torus** as a sum of four products over Bogoliubov angles $\gamma_r$. Exactly known and implemented here: the critical temperature, the thermodynamic-limit free energy (double integral), internal energy (elliptic-$K$ closed form), the spontaneous magnetization **for $T<T_c$** (Yang 1952), and the finite-torus $\ln Z$ (Kaufman). **Not exact:** nothing — everything about this model is exact. Some exact quantities are simply not implemented in `oracle.py` (out of this card's scope): the two-spin correlation functions $\langle s_0 s_r\rangle$ (exactly known as Toeplitz determinants — the diagonal correlator is a closed Toeplitz form) and the finite-torus magnetization. The magnetization formula below is a genuine closed form **valid only in the ordered phase $T<T_c$**; it does not describe $T\ge T_c$ (where $m=0$ identically) and is not an approximation to anything above $T_c$.

## Exact results

- Critical temperature (Kramers–Wannier self-dual point $\sinh 2K_c = 1$): $T_c = \dfrac{2J}{\ln(1+\sqrt 2)} \approx 2.269185$ [@Onsager1944]
- Free energy per site (thermodynamic limit): $-\beta f = \dfrac{\ln Z}{N} = \ln 2 + \dfrac{1}{8\pi^2}\displaystyle\int_0^{2\pi}\!\!\int_0^{2\pi} \ln\!\big[\cosh^2 2K - \sinh 2K(\cos\theta_1 + \cos\theta_2)\big]\,d\theta_1 d\theta_2$ [@Onsager1944]
- Internal energy per site: $u = -J\coth 2K\left[1 + \dfrac{2}{\pi}(2\tanh^2 2K - 1)\,\mathbf{K}(\kappa)\right]$, $\kappa = \dfrac{2\sinh 2K}{\cosh^2 2K}$, $\mathbf{K}$ the complete elliptic integral of the first kind. At $T_c$ the prefactor $2\tanh^2 2K_c - 1 = 0$ cancels the log-divergent $\mathbf{K}(1)$, giving the exact value $u(T_c) = -\sqrt 2\,J$ [@Onsager1944]
- Spontaneous magnetization (**$T<T_c$ only**): $m(T) = \left(1 - \sinh^{-4}(2J/T)\right)^{1/8}$; $m = 0$ for $T\ge T_c$. Critical exponent $\beta = 1/8$ [@Onsager1944]
- Finite $m\times n$ torus (Kaufman): $Z = \tfrac12 (2\sinh 2K)^{mn/2}(Z_1+Z_2+Z_3+Z_4)$ with $Z_1,Z_2 = \prod_{r=0}^{n-1} 2\{\cosh,\sinh\}(\tfrac m2 \gamma_{2r+1})$ and $Z_3,Z_4 = \prod_{r=0}^{n-1} 2\{\cosh,\sinh\}(\tfrac m2\gamma_{2r})$, where $\cosh\gamma_\ell = \cosh 2K\coth 2K - \cos(\pi\ell/n)$ and the $\ell=0$ branch takes the signed $\gamma_0 = 2K + \ln\tanh K$ [@Kaufman1949]

## Quantum connection

The 2D classical Ising model maps to the 1D quantum transverse-field Ising chain: the row-to-row transfer matrix $\hat T$ is, in the anisotropic (Hamiltonian) limit, $\hat T \approx e^{-\tau H_{\rm TFIM}}$, so a $(1{+}1)$-dimensional path integral of the quantum chain reproduces the 2D classical partition function. The classical inverse temperature $\beta$ and the quantum transverse field $\Gamma$ trade places under this Wick rotation, and the free-fermion (Jordan–Wigner) diagonalization of the quantum chain is precisely Kaufman's spinor analysis of the transfer matrix (see the `tfim-chain` card and `.knowledge/models/transverse-field-ising/MODEL.md`). The self-duality that fixes $T_c$ is Kramers–Wannier duality: it maps the high-$T$ and low-$T$ expansions onto each other with $\sinh 2K \leftrightarrow 1/\sinh 2K$, so the critical point is the fixed point $\sinh 2K_c = 1$, i.e. $T_c = 2J/\ln(1+\sqrt 2)$ — an exact determination of $T_c$ that needs no solution of the model, only its duality.

## Oracle script

`python oracle.py --T 2.0 --L 4` → prints `tc`, `free_energy`, `magnetization`, `internal_energy`, `logZ_finite` (natural log of the exact $L\times L$-torus partition function at $\beta=1/T$). Importable: `compute(T=2.0, L=4)`; individual functions `tc()`, `free_energy(T)`, `internal_energy(T)`, `magnetization(T)`, `partition_function_finite(m, n, beta)` (returns $\ln Z$, log-space to avoid overflow).

Self-test anchors: (1) `tc()` matches the closed form to `1e-12`; (2) **ground truth** — `partition_function_finite` equals brute-force enumeration over all $2^{mn}$ configurations for $(m,n)\in\{(3,3),(4,4)\}$ at $\beta\in\{0.2, 0.4406868, 1.0\}$ plus the asymmetric torus $(3,4)$ at $\beta=0.4406868$ (exercising the $m/n$ role assignment), relative tol `1e-10` (log-space); (3) `internal_energy(Tc) == -√2` to `1e-10`; (4) free-energy consistency — the numerical $T$-derivative of `free_energy` reproduces `internal_energy` at `T=3.0` via $u = f - T\,\partial_T f$ within `1e-6` (independent path: double integral vs elliptic closed form); plus the magnetization regime guard ($m=0$ at $1.01\,T_c$, $m(2.0)=0.9113$).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `tc` | $J=1$ | $2/\ln(1+\sqrt2) \approx 2.2691853$ | [@Onsager1944] |
| `internal_energy` | $T=T_c$ | $-\sqrt2 \approx -1.4142136$ (per site, $J=1$) | [@Onsager1944] |
| `magnetization` | $T=2$, $J=1$ | $(1-\sinh^{-4}1)^{1/8} = 0.9113194$ | [@Onsager1944] |

## Verification recipes

- To check a classical Monte Carlo run (Metropolis / Wolff) of the 2D Ising model: compare its measured internal energy per site $u(T)$ against `internal_energy(T)` and its magnetization $|m|(T)$ against `magnetization(T)` (the latter only for $T<T_c$, and only in the large-$L$ / low-autocorrelation limit), tolerance set by the MC error bars.
- To check a finite $L\times L$ code (exact transfer matrix, tensor network, or small-lattice enumeration): compare $\ln Z$ against `oracle.py --T <T> --L <L>` field `logZ_finite`, tolerance `1e-8` (exact).
- To check a claimed $T_c$ from a finite-size-scaling crossing: compare against `tc()`.

## Key reference

[@Onsager1944] — Onsager's exact solution of the 2D Ising model, the source of $T_c$, the free energy, the internal energy, and (via the same transfer-matrix machinery, completed by [@Kaufman1949]) the finite-torus partition function. Rendered: _(Wave 3)_.
