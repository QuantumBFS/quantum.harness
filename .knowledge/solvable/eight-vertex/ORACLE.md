# Eight-vertex model (Baxter) — exact-solution oracle

Technique: T2 (2D classical / transfer matrix) · Tier: B (integrable, Yang–Baxter) · Script: P

## Model & conventions

$$ Z = \sum_{\text{configs}} a^{n_a} b^{n_b} c^{n_c} d^{n_d}, \qquad \text{even number of arrows in (0, 2, or 4) at every vertex} $$

Baxter's **eight-vertex model** relaxes the six-vertex ice rule: an *even* number of in-arrows is allowed, so besides the six ice vertices there are two new ones — **all arrows in** and **all arrows out** — with weight $d$.

- Edge encoding as in `six-vertex` ($+1$ = right/up). The six ice configs satisfy $L+B=R+T$ (weights $a,b,c$ exactly as there); the two $d$-configs are $(L,B,R,T)=(+,+,-,-)$ (all in) and $(-,-,+,+)$ (all out).
- Anisotropy parameters $\displaystyle \Delta=\frac{a^2+b^2-c^2-d^2}{2(ab+cd)}$, $\displaystyle \Gamma=\frac{ab-cd}{ab+cd}$. Commuting transfer matrices (integrability) require $\Delta,\Gamma$ fixed along a family; $d\to0$ recovers the six-vertex model ($\Delta\to\Delta_{6v}$, weights reduce term-by-term).
- Partition function per vertex $\kappa=Z^{1/N}$, $\ln\kappa=-\beta f$.

See `.knowledge/conventions.md`. There is no model-zoo card; the catalog siblings are `six-vertex` (the $d=0$ face of this model) and `ising-2d-onsager` (recovered along the free-fermion manifold).

## Solvability statement

T2 (2D classical / transfer matrix): Baxter (1971) solved the zero-field eight-vertex model by the **star–triangle / Yang–Baxter equation**, showing that transfer matrices with common $\Delta,\Gamma$ commute; the free energy follows from an elliptic-function parametrization and has a **continuously varying critical exponent** — the archetype of non-universal criticality. **Not exact:** nothing — the model is exactly solvable in its entirety; nothing about it is approximate.

**Script scope — this is a P (partial) card.** What the script *does*: (i) the **exact ground truth** for *any* weights — the row-to-row transfer matrix $V_N$ in the vertical-arrow basis, whose $\mathrm{tr}\,V_N^{\,M}$ equals a brute-force enumeration of eight-vertex configurations on the $N\times M$ torus (exact integer/float equality); (ii) the **free-fermion manifold** $a^2+b^2=c^2+d^2$ (equivalently $\Delta=0$), where the model is dimer/Pfaffian-reducible and the per-vertex free energy has the closed **Fan–Wu double integral** [@FanWu1970], computed and independently verified here; (iii) the $d\to0$ reduction to the `six-vertex` oracle (cross-loaded, not duplicated). What it deliberately does **not** compute (exact, but only tabulated below with citation): **Baxter's general free energy** off the free-fermion manifold — the elliptic-theta-function series with its continuously varying exponent $\pi/(2\mu)$ — and the critical/ordered-phase structure. The precise split: *free-fermion free energy = scripted; general Baxter free energy = tabulated.*

## Why only the free-fermion point is scripted

On the free-fermion manifold $\Delta=0$ the eight-vertex model maps to a system of non-interacting lattice fermions (a dimer problem), so its free energy is an elementary double integral — the Fan–Wu form below — which the script evaluates and checks two independent ways. Off that manifold the exact free energy is Baxter's, expressed through elliptic integrals $K$, $K'$ and Jacobi theta functions with a modulus fixed by $\Delta,\Gamma$; it carries the famous continuously varying exponent and is **not** an elementary integral. Rather than transcribe that machinery, the card ships the free-fermion closed form (verified) and **tabulates** Baxter's general result with its reference. The transfer-matrix/enumeration ground truth, by contrast, is exact for every weight set and is the card's real gate.

## Exact results

- Free-fermion free energy ($a^2+b^2=c^2+d^2$), Fan–Wu double integral [@FanWu1970]:
$$ \ln\kappa = \frac{1}{16\pi^2}\!\int_0^{2\pi}\!\!\int_0^{2\pi}\! \ln\!\big[\,2A + 2D\cos(x{-}y) + 2E\cos(x{+}y) + 4\Delta_1\sin^2 y + 4\Delta_2\sin^2 x\,\big]\,dx\,dy $$
with $A=4a^2b^2+4c^2d^2$, $D=E=2c^2d^2-2a^2b^2$, $\Delta_1=(a^2-c^2)^2$, $\Delta_2=(b^2-c^2)^2$.
- Free-fermion condition $\Leftrightarrow \Delta=0$; $d\to0$ then gives the six-vertex free-fermion line $\Delta_{6v}=0$ (e.g. $a=b=1$, $c=\sqrt2$).
- Finite $N\times M$ torus: $Z=\mathrm{tr}\,V_N^{\,M}$, equal to the exact enumeration for any $(a,b,c,d)$.
- **Tabulated (not scripted)** — Baxter's general free energy [@Baxter1971]: parametrize $\Delta=-\cos2\mu$, $\Gamma=\ldots$ (elliptic); the singular free energy near criticality scales with exponent $2-\alpha=\pi/\mu$, i.e. $\alpha$ **varies continuously** with the weights — the hallmark of the eight-vertex universality line.

## Oracle script

`python oracle.py --a 1 --b 1 --c 1.2 --d 0.7483314773547883 --N 4 --M 4` → prints `Delta`, `Gamma`, `free_fermion` (bool), `logZ_torus`, and `free_energy_free_fermion` (when on the manifold; the default weights are a free-fermion point). Importable: `compute(a,b,c,d,N,M)`; helpers `delta(a,b,c,d)`, `is_free_fermion(...)`, `transfer_matrix(N,a,b,c,d)`, `logZ_torus(N,M,a,b,c,d)`, `free_energy_free_fermion(a,b,c,d)`.

Self-test anchors: (1) **ground truth** — `tr(V_N^M)` equals brute-force torus enumeration for a generic (non-free-fermion) point, a free-fermion point, and the $d=0$ six-vertex sub-case (tol `1e-8`); (2) $d\to0$ reproduces the `six-vertex` oracle **exactly** — identical transfer matrix and torus $\ln Z$ (cross-loaded by path, `1e-12`), and the ice point recovers the $4\times4$ count $2970$; (3) free-fermion $\Leftrightarrow\Delta=0$; (4) the Fan–Wu free energy is **independently verified** — (a) at $d\to0$ it equals the six-vertex disordered free energy from the sibling oracle to `1e-8`, and (b) at $d\ne0$ free-fermion points it matches the transfer-matrix free energy $\tfrac1N\ln\Lambda_{\max}$ (these points are gapped, so width-8 already agrees to `<1e-4`).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `free_energy_free_fermion` | $a=b=1,c=\sqrt2,d=0$ | $=$ six-vertex $\Delta{=}0$ value $0.5831218$ | [@FanWu1970] |
| `free_energy_free_fermion` | $a=b=1,c=1.2,d=\sqrt{2-1.44}$ | $0.6803218$ | [@FanWu1970] |
| `Delta` | free-fermion manifold | $0$ | [@Baxter1971] |
| `logZ_torus` | $4\times4$, $a{=}b{=}c{=}1,d{=}0$ | $\ln 2970$ (six-vertex ice point) | [@Baxter1971] |

## Verification recipes

- To check any eight-vertex transfer-matrix / tensor-network code (arbitrary $a,b,c,d$): compare $\ln Z$ against `logZ_torus(N, M, a, b, c, d)` on a torus small enough to enumerate — exact equality.
- To check a free-fermion / dimer-mapping free-energy code: compare against `free_energy_free_fermion(a, b, c, d)` on the manifold $a^2+b^2=c^2+d^2$, cross-validated by the $d\to0$ six-vertex limit.
- To check a Baxter-parametrization solver **off** the free-fermion line: this card tabulates $\Delta,\Gamma$ and the continuously varying exponent only — compute the transfer-matrix $\ln Z$ on a finite torus and compare to `logZ_torus` as the exact anchor there.

## Key reference

[@Baxter1971] — Baxter's exact solution of the eight-vertex model via the star–triangle (Yang–Baxter) equation: the source of the elliptic-function free energy and the continuously varying critical exponent. The scripted free-fermion closed form is Fan and Wu's [@FanWu1970] dimer reduction of the $\Delta=0$ manifold. Rendered: _(Wave 3)_.
