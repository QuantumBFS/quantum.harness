# Heisenberg XXX chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: S

## Hamiltonian & conventions

$$ H = J \sum_{i=1}^{N} \mathbf{S}_i\cdot\mathbf{S}_{i+1}, \qquad \text{PBC } (\mathbf{S}_{N+1}\equiv\mathbf{S}_1) $$

Conventions: spin-1/2 `S`-operators (`S^a = σ^a/2`), `J = 1` antiferromagnetic, nearest-neighbour bonds counted once, `N` even. This is the isotropic (`Δ=1`) point of the XXZ family. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/heisenberg/MODEL.md`. That card uses the **same** `S`-operator convention and the same `H = J Σ S_i·S_j` form, and quotes the identical thermodynamic-limit benchmark `E/N = 1/4 − ln 2 ≈ −0.443147` (Bethe/Hulthén, `J=1`). No convention translation is needed between the two cards. The `Δ`-tuned generalisation lives in the sibling card `xxz-chain`.

## Solvability statement

T3 (Bethe ansatz / Yang–Baxter): the chain is integrable by Bethe's 1931 coordinate ansatz [@Bethe1931]. Working in the `S^z` sectors above the ferromagnetic reference `|↑↑…↑⟩` (energy `N/4`), an `M`-magnon eigenstate is a superposition of `M` down-spins whose amplitudes are plane waves with two-body scattering phases fixed by the Yang–Baxter/Bethe equations. Each eigenstate is labelled by a set of rapidities `{λ_j}` solving the Bethe equations; **the antiferromagnetic ground state sits in the `S^z=0` sector (`M=N/2`) and is the "1-string" solution — all rapidities are real** (no bound states/strings, which would raise the energy). The exact finite-`N` ground energy (from the real-root solver), the thermodynamic-limit energy `1/4 − ln 2`, and the spinon velocity `π/2` are all reported here. **Not exact in closed form (Tier B, not A):** the full spectrum and dynamical/finite-`T` quantities require solving the Bethe equations state-by-state or the thermodynamic Bethe ansatz — integrable but not a single closed form; correlation functions are known only through much heavier (determinant / vertex-operator) machinery, out of this card's scope.

## The Bethe-ansatz story

A single flipped spin on the ferromagnetic sea is a **magnon**: the one-magnon states are exact plane waves `|k⟩ = Σ_n e^{ikn} S^-_n|↑…↑⟩` with energy `ε(k) = −J(1−\cos k)` above the reference. With `M` magnons the wavefunction is *not* a free product — Bethe's ansatz writes it as a sum over permutations of `M` plane waves, and consistency under two-magnon collisions plus periodicity gives the **logarithmic Bethe equations** for the rapidities `λ_j` (with `k(λ)` set by `e^{ik} = (λ+i/2)/(λ−i/2)`):

$$ 2\arctan(2\lambda_j) = \frac{2\pi}{N} I_j + \frac{2}{N}\sum_{k} \arctan(\lambda_j-\lambda_k). $$

The **Bethe quantum numbers** `I_j` are consecutive (half-)integers `{−(M−1)/2, …, +(M−1)/2}` (`M=N/2`) — integers when `M` is odd, half-integers when `M` is even. For the ground state they are *packed* (no gaps), which is exactly the choice that gives all-real roots. Each root lowers the energy by `ε(λ) = −2/(4λ²+1)`, so

$$ E = \frac{N}{4} - \sum_{j=1}^{N/2}\frac{2}{4\lambda_j^2+1}. $$

As `N→∞` the packed roots fill the real line with a density `ρ(λ) = 1/(2\cosh πλ)` (the solution of the linear integral equation obtained by taking the continuum limit of the Bethe equations). Sums over roots become **integrals over `ρ`**, and the ground energy per site collapses to the closed form

$$ \frac{E}{N} \to \frac14 - \int_{-\infty}^{\infty}\frac{d\lambda}{\cosh(\pi\lambda)\,(4\lambda^2+1)} = \frac14 - \ln 2. $$

The low-lying excitations are **spinons** — deconfined `S=1/2` objects created in pairs by removing a root and repacking — with dispersion `ε_s(k) = (π/2)|\sin k|` [@desCloizeauxPearson1962]; the slope at `k→0` is the spinon velocity `v = π/2` (`J=1`).

## Exact results

- Magnon dispersion (one flipped spin): `ε(k) = −J(1−\cos k)`, i.e. `ε(λ) = −2J/(4λ²+1)` [@Bethe1931]
- Finite-`N` ground energy: `E = N/4 − Σ_j 2/(4λ_j²+1)` over the `N/2` real ground-state roots [@Bethe1931]
- Thermodynamic-limit ground energy per site: `E/N = 1/4 − ln 2 ≈ −0.4431472` [@Hulthen1938]
- Spinon velocity: `v = π/2` (`J=1`, `S`-convention); two-spinon dispersion `ε_s(k) = (π/2)|\sin k|` [@desCloizeauxPearson1962]
- Ground state is a total-spin singlet in the `S^z=0` sector; the chain is gapless (quasi-long-range order, central charge `c=1`)

## Oracle script

`python oracle.py --N 12` → prints `e0_per_site_finite` (Bethe solver at `N`), `e0_thermodynamic` (`1/4 − ln 2`), `spinon_velocity` (`π/2`). Importable: `compute(N=12)`; the solver lives in `_lib/bethe.py` (`xxx_ground_roots(N)`, `xxx_energy(roots, N)`).

Self-test anchors: (1) **ground truth** — the Bethe-ansatz energy equals brute-force ED of `H = Σ S_i·S_{i+1}` (PBC) at `N=10` to `1e-10` (the shared `_lib/bethe` solver is pinned to ED at `N∈{8,10,12}` in `tests/test_lib.py`); (2) the `1/N²` (Richardson) extrapolation of `e0(N)` over `N∈{32,64,128}` reaches `1/4 − ln 2` within `1e-4`; (3) the thermodynamic constant equals the literal `1/4 − ln 2` to `1e-15`; (4) the spinon velocity equals `π/2`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_thermodynamic` | `J=1`, `N→∞` | `1/4 − ln 2 ≈ −0.4431472` | [@Hulthen1938] |
| `e0_per_site_finite` | `J=1`, `N=12` | `−0.4489492` (converges to `1/4 − ln 2`) | [@Bethe1931] |
| `spinon_velocity` | `J=1` | `π/2 ≈ 1.5707963` | [@desCloizeauxPearson1962] |

## Verification recipes

- To check a DMRG/ED run at finite `N` (PBC): compare `e0_per_site_finite` from `oracle.py --N <N>` (exact Bethe value), tolerance `1e-8`. Note the finite-size energy sits *below* `1/4 − ln 2` and rises toward it as the CFT correction `−πvc/(6N²) = −π²/(12N²)` (`v = π/2`, `c = 1`); do not compare a finite-`N` number directly to the thermodynamic constant.
- To check a thermodynamic-limit extrapolation: compare the `1/N²`-extrapolated `E/N` against `1/4 − ln 2`.
- To check a spin-wave/spinon-velocity measurement: compare against `π/2` (`J=1`).

## Key reference

[@Bethe1931] — Bethe's original coordinate ansatz for the linear Heisenberg chain, the source of the magnon plane-wave structure, the logarithmic Bethe equations, and the all-real-root ground state used above; the thermodynamic energy `1/4 − ln 2` is Hulthén's [@Hulthen1938] evaluation and the spinon velocity is des Cloizeaux–Pearson [@desCloizeauxPearson1962]. Rendered: _(Wave 3)_.
