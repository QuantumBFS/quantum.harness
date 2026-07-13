# Transverse-field Ising chain — exact-solution oracle

Technique: T1 (free-fermion / Jordan–Wigner) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -J \sum_{i=1}^{L} \sigma^z_i \sigma^z_{i+1} - h \sum_{i=1}^{L} \sigma^x_i, \qquad \text{PBC } (\sigma_{L+1} \equiv \sigma_1) $$

Conventions: Pauli-matrix operators (`σ^a`, not `S^a` — a factor of 4 per bond vs the `S^a` convention); `J` is the Ising coupling, `h` the transverse field, both set to `1` by default; see `.knowledge/conventions.md`.

Physics card: `.knowledge/models/transverse-field-ising/MODEL.md`. That card uses the same Pauli convention and the same `H = -J Σ σ^z σ^z - Γ Σ σ^x` form (its field is named `Γ` where this card uses `h` — same object). No convention translation is needed between the two cards.

## Solvability statement

T1: the chain maps to free fermions via a Jordan–Wigner transformation, giving a quadratic (Bogoliubov-diagonalizable) fermion Hamiltonian. Everything reported here — the full spectrum (via the single-particle dispersion `ε(k)`), the ground-state energy at finite `L` and in the thermodynamic limit, the gap, and the transverse magnetization — is exact for any `L`, `J`, `h`. The model is exactly solvable in its entirety — there is no approximation anywhere. **Not exact:** nothing; everything about this model is exact. Some exact quantities are simply not implemented in `oracle.py` (out of this card's scope, ground-state statics only): longitudinal spin-spin correlators `⟨σ^z_i σ^z_j⟩` (exactly known as Toeplitz determinants of the JW correlation matrix, requiring determinant/Pfaffian machinery), and finite-temperature and non-equilibrium quench quantities (also exactly computable from the free-fermion solution).

## Exact results

- Single-fermion dispersion: $\varepsilon(k) = 2\sqrt{J^2 - 2Jh\cos k + h^2}$ [@Pfeuty1970]
- Thermodynamic-limit ground energy per site: $e_0(J,h) = -\dfrac{2}{\pi}(J+h)\,E(m)$, $m = \dfrac{4Jh}{(J+h)^2}$, $E$ the complete elliptic integral of the second kind [@Pfeuty1970]
- Finite-size (PBC spin chain, ABC fermion sector) ground energy per site: $e_0(L) = -\dfrac{1}{2L}\sum_k \varepsilon(k)$, $k = \pi(2n+1)/L$
- Single-fermion gap: $\Delta = 2|J-h|$, vanishing at the critical point $h = J$
- Critical point: $h = J$; order-parameter (magnetization) critical exponent $\beta = 1/8$

## Oracle script

`python oracle.py --L 16 --h 1.0` → prints `e0_per_site`, `e0_thermodynamic`, `gap_single_fermion`, `mx`. Importable: `compute(L=16, h=1.0, J=1.0)`.
Self-test anchors: (1) thermodynamic-limit energy at criticality equals closed form `-4/π`; (2) finite-`L` Jordan–Wigner energy matches brute-force ED for `(L,h) ∈ {(8,0.5),(8,1.0),(10,1.3)}`; (3) gap vanishes at `h=J` and equals `1.0` at `h=1.5, J=1`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_thermodynamic` | `h = J = 1` (critical) | `-4/π ≈ -1.27324` | [@Pfeuty1970] |
| `gap_single_fermion` | `h = 1.5, J = 1` | `1` | [@Pfeuty1970] |
| `m` (elliptic-integral parameter, `m = k²`) | definition | `m = 4Jh/(J+h)²` | [@Pfeuty1970] |

## Verification recipes

- To check a DMRG/ED run at size `L`, PBC: compare `e0_per_site` from `oracle.py --L <L> --h <h>`, tolerance `1e-8` (exact).

## Key reference

[@Pfeuty1970] — the original exact solution of the 1D transverse-field Ising chain via Jordan–Wigner, source of the dispersion, thermodynamic-limit energy, and gap used above. Rendered: _(Wave 3)_.
