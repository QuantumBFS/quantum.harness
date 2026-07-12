# p+ip superconductor (lattice) — exact-solution oracle

Technique: T1 (free-fermion / BdG) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H(\mathbf k) = \xi(\mathbf k)\,\tau_z + \Delta\,(\sin k_x\,\tau_x + \sin k_y\,\tau_y), \qquad \xi(\mathbf k) = -2t(\cos k_x + \cos k_y) - \mu $$

single-band spinless fermions on a square lattice with chiral `p+ip` pairing, written as a `2×2` Bogoliubov–de Gennes (Nambu) Bloch matrix; `τ_{x,y,z}` are the particle-hole Pauli matrices. Conventions: `t > 0` hopping (energy unit `t = 1` by default), `μ` the chemical potential, `Δ` the (real) `p`-wave pairing amplitude; the `d`-vector is `d(k) = (Δ\sin k_x, Δ\sin k_y, ξ(k))` with BdG bands `±E(k)`, `E(k) = |d(k)| = \sqrt{ξ^2 + Δ^2(\sin^2 k_x + \sin^2 k_y)}`, and the negative band filled (`nocc = 1`). See `.knowledge/conventions.md`. No model-zoo sibling card exists for this model.

## Solvability statement

T1: the Hamiltonian is quadratic in the fermions and translationally invariant, block-diagonalized exactly by Fourier transform into the `2×2` BdG matrix above and diagonalized exactly for every `k`. Everything reported here — the first **Chern number** of the filled BdG band (Fukui–Hatsugai–Suzuki lattice-gauge invariant, `_lib.topology.chern`) and the minimum **band gap** over the BZ — follows from the exact Bloch Hamiltonian with no approximation. **Not exact:** nothing about this model is approximate. The `gap` is obtained by a BZ grid minimum that converges to (and, because the closing momenta `(0,0),(0,π),(π,0),(π,π)` lie exactly on an even grid, reaches) the exact value rather than a closed-form substitution. Out of this card's scope entirely (still exact from the same quadratic solution, just not implemented): the real-space **chiral Majorana edge mode** and its dispersion under OBC, the BdG **quasiparticle wavefunctions** and the half-quantum-vortex Majorana zero mode, and finite-`T`/dynamical quantities.

## Exact results

- BdG spectrum: $E_\pm(\mathbf k) = \pm\sqrt{\xi^2 + \Delta^2(\sin^2 k_x + \sin^2 k_y)}$; band gap $\Delta_{\text{gap}} = 2\min_{\mathbf k} E_+(\mathbf k) = 2\min_{\mathbf k}|d(\mathbf k)|$ [@ReadGreen2000]
- **Gap closings** (`d = 0`): require `\sin k_x = \sin k_y = 0` and `ξ = 0`, giving the three critical lines
  $$ \mu = -4t\ \text{at}\ (0,0), \qquad \mu = 0\ \text{at}\ (0,\pi)\ \&\ (\pi,0), \qquad \mu = +4t\ \text{at}\ (\pi,\pi) $$
- **Phase diagram** (`t > 0`):
  - `|μ| > 4t` : **strong-pairing**, topologically trivial, `C = 0`
  - `−4t < μ < 0` and `0 < μ < 4t` : **weak-pairing**, topological, `|C| = 1`, with **opposite** Chern sign on the two sides (the `μ = 0` line closes **two** Dirac points, so `C` jumps by `2` across it) [@ReadGreen2000]
- **Sign convention** (do not over-read): with the pairing written `Δ(\sin k_x τ_x + \sin k_y τ_y)` and the FHS plaquette orientation of `_lib.topology.chern`, this script returns `C = +1` for `−4t < μ < 0` and `C = −1` for `0 < μ < 4t`. The **overall** sign is convention-dependent — it flips under `Δ → −Δ`, `τ_x ↔ τ_y`, or a reversed FHS orientation — so only `|C|` and the **relative** sign across `μ = 0` are convention-independent. The script reports whatever `_lib.topology.chern` yields and asserts no privileged sign.

The weak-pairing phase (`|C| = 1`) is the chiral topological superconductor: its ground state is in the same universality class as the **Moore–Read Pfaffian** quantum Hall state, and its boundary carries a single **chiral Majorana edge mode** (`c = 1/2` chiral CFT), the defining bulk–boundary signature of a `p+ip` superconductor [@ReadGreen2000].

## Oracle script

`python oracle.py --mu -1.0 --t 1.0 --delta 1.0` → prints `chern`, `gap`, `phase`. Importable: `compute(mu=-1.0, t=1.0, delta=1.0, nk=60, n_gap=120)`; `bloch(kx, ky, mu, t, delta)` returns the `2×2` BdG matrix; `hk(...)` returns the scalar closure for `_lib.topology.chern`; `gap(...)` the BZ-minimum gap. The default `μ = −1` sits in the (gapped) weak-pairing phase; `μ = 0` is a gapless critical line where `chern` is ill-defined.
Self-test anchors: (1) `|C| = 1` at `μ = −2` and `μ = +2` (`t=1, Δ=0.5`); (2) `C(μ=−2) = −C(μ=+2)` (opposite Chern sign across `μ = 0`); (3) `C = 0` at `μ = −5` (strong pairing); (4) `gap < 1e-3` at each critical `μ ∈ {−4, 0, +4}`, the gap grid (`n_gap = 120`, even) containing the closing momenta; (5) `phase` labels track `|C|`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `chern` | `μ=−2, t=1, Δ=0.5` (weak pairing) | `±1` (`+1` this convention) | [@ReadGreen2000] |
| `chern` | `μ=+2, t=1, Δ=0.5` (weak pairing) | `∓1` (`−1` this convention) — opposite sign to `μ=−2` | [@ReadGreen2000] |
| `chern` | `μ=−5, t=1, Δ=0.5` (strong pairing) | `0` | [@ReadGreen2000] |
| `gap` | `μ ∈ {−4, 0, +4}, t=1, Δ=0.5` | `0` (critical) | derived above |

## Verification recipes

- To check a BdG / mean-field topological-superconductor run at `(μ,t,Δ)`: compare `chern` from `oracle.py --mu <μ> --t <t> --delta <Δ>` (exact integer) and `gap` (tolerance `1e-6`, tighten by raising `n_gap`); confirm the `weak/strong`-pairing label.
- To locate a transition: sweep `μ` across `±4t` (single Dirac point, `|ΔC| = 1`) or across `0` (two Dirac points, `|ΔC| = 2`) and confirm `gap → 0` at the crossing with `chern` jumping by the stated amount.

## Key reference

[@ReadGreen2000] — Read & Green, "Paired states of fermions in two dimensions with breaking of parity and time-reversal symmetries and the fractional quantum Hall effect", Phys. Rev. B **61**, 10267 (2000): the defining analysis of the spinless `p+ip` paired state, the weak-pairing vs strong-pairing distinction, the chiral Majorana edge mode, and the connection of the weak-pairing phase to the Moore–Read Pfaffian quantum Hall state. Rendered: _(Wave 3)_.
