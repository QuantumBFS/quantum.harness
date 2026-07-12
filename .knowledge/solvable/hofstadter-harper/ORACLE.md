# Hofstadter–Harper model — exact-solution oracle

Technique: T1 (free-fermion / Harper equation, magnetic-Bloch diagonalization) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -t \sum_{\langle ij\rangle} e^{i\theta_{ij}}\, c^\dagger_i c_j + \text{h.c.}, \qquad \sum_{\square} \theta_{ij} = 2\pi\alpha,\quad \alpha = \frac{p}{q} $$

In Landau gauge this reduces to the **Harper equation**: a `q×q` magnetic-Bloch matrix per magnetic crystal momentum,

$$ H(k_x, k_y)_{mm} = -2t\cos\!\Big(k_x + \tfrac{2\pi m p}{q}\Big),\quad m = 0,\dots,q-1 $$
$$ H(k_x,k_y)_{m,m+1} = H(k_x,k_y)_{m+1,m} = -t,\quad m = 0,\dots,q-2 $$
$$ H(k_x,k_y)_{0,q-1} = -t\,e^{-ik_y},\qquad H(k_x,k_y)_{q-1,0} = -t\,e^{+ik_y} \quad\text{(wrap corner)} $$

Conventions: spinless fermions, `t = 1` default, rational flux `α = p/q` (coprime `p, q`) per plaquette. **Coordinates (stated explicitly, per this card's freedom to pick any consistent full-torus parametrization):** `k_x` is the ordinary crystal momentum along the un-enlarged `x`-direction (period `2π`, single-site cell). `k_y` here denotes the **reduced** magnetic Bloch momentum conjugate to the `q`-site magnetic unit cell along `y` — i.e. `k_y^{\text{here}} = q\, k_y^{\text{phys}}`, where `k_y^{\text{phys}} ∈ [0, 2π/q)` is the actual transverse crystal momentum (whose true magnetic Brillouin zone has width `2π/q`, the enlarged real-space cell). Writing the wrap phase as `e^{∓ik_y}` with `k_y` already spanning a full `2π` period makes the plain `(k_x,k_y) ∈ [0,2π)²` grid used by `_lib.topology.chern` *exactly* one traversal of the magnetic Brillouin zone — the same "reduced coordinates" device used by `tight-binding-lattices/oracle.py`'s honeycomb/kagome/Lieb Bloch matrices, here applied to the enlarged magnetic cell instead of an enlarged real-space cell. (Using the literal `e^{∓iq k_y^{\text{phys}}}` form with `k_y^{\text{phys}}` swept over the *full* `[0,2π)` range over-covers the magnetic BZ `q` times and inflates every Chern number by an exact factor of `q` — this was caught during implementation by comparing against the known `p/q=1/3` benchmark `(1,-2,1)` before the reduced-coordinate convention above was adopted; see `oracle.py`'s module docstring.) See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/hofstadter/MODEL.md`. That card writes the identical Peierls-phase Hamiltonian, the same Landau-gauge reduction to the `q`-site Harper equation, and the same TKNN/Diophantine gap-labeling `r = q\,s + p\,C`. **Conventions match**; the model card does not fix a specific `(k_x,k_y)` axis/gauge choice for the magnetic-Bloch matrix, so this card's explicit `k_y = q\,k_y^{\text{phys}}` reduced-coordinate convention (stated above) is this card's own choice within the model card's freedom — no conflict.

## Solvability statement

T1: at rational flux `α = p/q` the Peierls-phase Hamiltonian is exactly block-diagonalized by Fourier transform into the `q×q` Harper matrix above, diagonalized exactly by `numpy.linalg.eigvalsh` (textbook, exact matrix diagonalization — the only "numerical" step, with no approximation in the physics). Everything reported here — the full `q`-subband spectrum (`band_edges`), the per-band Chern numbers (Fukui–Hatsugai–Suzuki, `_lib.topology.chern`, cumulative-occupied differencing `C_n = \text{chern}(H, n+1) - \text{chern}(H, n)`), and the joint Chern number of any exactly-touching subband group — is exact for any coprime `(p,q)`. The model is exactly solvable in its entirety at every rational flux. **Not exact:** nothing about this model is approximate. Two quantities are obtained via numerical routines that converge to the exact value rather than a closed-form substitution: the Fukui–Hatsugai–Suzuki Chern number is a lattice-gauge discretization of the exact Berry-curvature integral that returns the exact integer once `nk` is fine enough to avoid landing exactly on a degeneracy (it is not a continuum-limit approximation — any sufficiently fine grid gives the exact topological invariant, away from an actual gap closing), and `band_edges` is a finite-grid min/max scan of the exact eigenvalues that converges to the true extremum as `nk_bands → ∞` (no closed form is derived for it here, though one exists band-by-band). Out of this card's scope entirely (not attempted): irrational `α` (Cantor-set spectrum, not tractable by a finite Harper matrix), strip/ribbon edge-mode spectra, and the Hofstadter–Hubbard interacting extension (sign-problem-ful).

## Exact results

- **Subband count**: at flux `α = p/q` (coprime) the spectrum splits into exactly `q` subbands [@Hofstadter1976].
- **Diophantine gap-labeling** (TKNN): each of the `q-1` gaps, indexed by filling `r = 1, \dots, q-1` bands, carries an integer Chern number `C_r` (equivalently Hall conductance `σ_xy = C_r e^2/h`) solving
  $$ r = q\,s_r + p\,t_r, \qquad t_r = C_r,\ |t_r| \le q/2,\ s_r \in \mathbb{Z} $$
  This is an **exact** result — verified in `self_test()` against the actual cumulative FHS Chern numbers at `p/q = 1/3`: `C(r{=}1)=1` solves `1 = 3(0) + 1(1)`; `C(r{=}2)=-1` solves `2 = 3(1) + 1(-1)`. The per-band Chern number reported by this card, `chern_numbers[n]`, is exactly `C_{n+1} - C_n` (with `C_0 = C_q = 0` by convention — no field, trivial insulator at full/empty filling).
- **Self-similar butterfly**: the spectrum as a function of `α ∈ [0,1]` recurs at all scales (`α` and `α+1`, and the `q → q` structure under continued-fraction refinement) [@Hofstadter1976]. Not evaluated by this card (single rational `α = p/q` per call); stated for context only.
- **Band touching at even `q`** (verified numerically, not a universal `q`-even rule): the Harper spectrum can have an *exact* zero-gap touching between two consecutive subbands — confirmed here for `(p,q) = (1,4)` and `(1,8)` (a middle-band touching), but **not** for `(p,q)=(1,6)` (small but strictly nonzero middle gap `≈0.051t`) — so this card detects touching by an explicit numerical gap scan (`_GAP_TOL = 1e-6`), never a hardcoded parity rule. At a detected touching, the naive `chern_numbers` entries for the merged bands are **not** gauge-invariant / not robust to the FHS grid resolution `nk` — verified: at `(p,q)=(1,4)` the individual band-2/band-3 split flips between `[0,-2]` and `[-1,-1]` as `nk` ranges `40 → 120`, while their **sum** (the *joint* Chern number of the merged two-band group, computed as `C_{\text{end}+1} - C_{\text{start}}` using only the genuinely open gaps bracketing the group) stays exactly `-2` at every `nk` tested. This joint value is the physically meaningful invariant and is reported separately as `band_touching_groups`.

## Oracle script

`python oracle.py --p 1 --q 3 --t 1.0` → prints `n_bands`, `chern_numbers`, `band_edges`, `band_touching_groups`. Importable: `compute(p=1, q=3, t=1.0, nk=60, nk_bands=120)`; `bloch(p, q, t)` returns the `hk(kx, ky)` closure.
Self-test anchors: (1) `p/q=1/3`: `chern_numbers == [1, -2, 1]`, sum `0`, no touching (all three subbands genuinely gapped); (2) `p/q=1/4`: sum `0`, `n_bands=4`, detected touching group `{bands: [1,2], joint_chern: -2}` (0-indexed, i.e. the 2nd/3rd subbands), and the two gapped bands individually equal `1` and `1` (matching the Diophantine solutions for `r=1,3`); (3) `p/q=2/5`: sum `0`, `n_bands=5` (a second coprime cross-check); (4) the Diophantine equation `r = q s + p t` is solved exactly by the actual computed cumulative Chern numbers at `p/q=1/3`, `r=1,2`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `chern_numbers` | `p=1, q=3` | `[1, -2, 1]` | [@Hofstadter1976] (TKNN Diophantine labeling) |
| `n_bands` | `p=1, q=3` | `3` (`=q`) | [@Hofstadter1976] |
| `band_touching_groups` | `p=1, q=4` | `[{bands:[1,2], joint_chern:-2}]` | derived above (numerical gap scan + Diophantine cross-check) |
| `sum(chern_numbers)` | any coprime `p,q` | `0` (telescoping, `C_q - C_0 = 0-0`) | derived above |

## Verification recipes

- To check an ED/DMRG-with-flux or a strip-edge-mode calculation at flux `p/q`: compare `chern_numbers` (bulk) against the number of chiral edge modes crossing each gap in a strip geometry (bulk–boundary correspondence), tolerance exact (both are integers).
- To validate a new `(p,q)`: confirm `sum(chern_numbers) == 0` (always true by construction) and, where the middle gap is genuinely open (check `band_touching_groups == []`), confirm the reported `chern_numbers` solve the Diophantine equation `r = qs + pt` for `r=1,\dots,q-1`.
- Flux-doubling / continued-fraction self-similarity sanity check (not implemented as an assertion here): the gap Chern numbers at `p/q` and at `p/(q+p)` (or other Stern–Brocot neighbors) are related by the same Diophantine equation with the new `(p,q)` — a useful cross-check when sweeping `α` to trace the butterfly.

## Key reference

[@Hofstadter1976] — Hofstadter, "Energy levels and wave functions of Bloch electrons in rational and irrational magnetic fields", Phys. Rev. B **14**, 2239 (1976): the defining paper deriving the Harper equation, the `q`-subband structure at rational flux `p/q`, and the self-similar butterfly spectrum used throughout this card. Rendered: _(Wave 3)_.
