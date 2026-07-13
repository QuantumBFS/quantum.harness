# Tonks–Girardeau gas — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter — Bose–Fermi mapping) · Tier: A (full solution) · Script: S

## Continuum conventions

$$ H = -\sum_{i=1}^{N}\frac{\partial^2}{\partial x_i^2} + 2c\sum_{i<j}\delta(x_i-x_j), \qquad c\to+\infty $$

- **Units:** `ħ = 1`, `m = 1/2` (Lieb–Liniger units); a general mass `m` (and `ħ`) is carried symbolically in the script so the free-fermion identities read in physical units too.
- **Limit:** the impenetrable (`γ = c/n → ∞`) endpoint of the `lieb-liniger` gas — hard-core bosons. Density `n = N/L`, Fermi momentum `k_F = πn`.
- **Energy scaling:** `E/N = n² e` with the *single universal number* `e = π²/3` (no free parameter — the coupling has been sent to infinity). This is exactly `lieb-liniger`’s `e(γ → ∞)`.
- Shared with `lieb-liniger` (this is its `γ → ∞` endpoint) and `yang-gaudin` (whose `γ → ∞` balanced-fermion limit approaches this *same* `π²/3` — the spin-incoherent impenetrable point). See `.knowledge/conventions.md`.

## Solvability statement

Tier A: the Tonks–Girardeau gas is **exactly solvable in closed form** via Girardeau’s Bose–Fermi mapping [@Girardeau1960]. An impenetrable-boson wavefunction is the modulus of a free spinless-fermion Slater determinant, `Ψ_B = |Ψ_F| = Ψ_F · ∏_{i<j}\mathrm{sgn}(x_i-x_j)`. Consequently **every local, permutation-symmetric observable is identical to the free Fermi gas**: the ground state is a filled Fermi sea to `k_F = πn`, and the ground-state energy, density profile, pair correlation, and density–density response are literally the free-fermion ones. The mapping is exact for all `N` — hence tier A, the strongest in this catalog — and needs no integral equation. **What is exact but not a filled-Fermi-sea number:** the momentum distribution `n(k)` (see below).

## The Bethe-ansatz-in-the-continuum story

The `c → ∞` limit is the point where the Bethe ansatz degenerates into something even simpler. The two-body phase `θ(k) = 2\arctan(k/c) → 0`, so the Bethe equations become **free-fermion quantization** `k_j L = 2π I_j` with distinct integers `I_j` (the impenetrability enforces the Pauli-like exclusion of coincident rapidities). The ground state packs `I_j` symmetrically, filling `[-k_F, k_F]` with the *flat* rapidity density `ρ(k) = 1/2π` — precisely the `λ → ∞` (`g → 1/2π`) limit of the `lieb-liniger` scaled equation. The Fermi-sea energy is then elementary:

$$ \frac{E}{L} = \frac{1}{2\pi}\int_{-k_F}^{k_F}\frac{\hbar^2 k^2}{2m}\,dk = \frac{\pi^2\hbar^2 n^3}{6m}, \qquad \frac{E}{N} = \frac{\pi^2\hbar^2 n^2}{6m}, $$

and in Lieb–Liniger units (`ħ=1, m=1/2`) this is `E/N = n²·(π²/3)`, i.e. **`e = π²/3`**.

## Regimes & exact statements

| Quantity | Value | Status |
|---|---|---|
| `E/L` | `π²ħ²n³/(6m)` | exact (free-fermion sea) |
| `E/N` | `π²ħ²n²/(6m)` | exact |
| `e` (LL units) | `π²/3 ≈ 3.289868` | exact `= lieb-liniger e(γ→∞)` |
| `g₂(0)` | `0` | exact — impenetrability forbids coincident bosons |
| `n(k)` (momentum dist.) | **not** the free-fermion step | interaction signature — see below |

**Momentum distribution — exact but not scripted.** Unlike energy or density, `n(k)` is *not* a local observable: it is the Fourier transform of the one-body density matrix `ρ₁(x,x') = ⟨ψ†(x)ψ(x')⟩`, and the `∏\mathrm{sgn}` factor in the mapping does **not** cancel between `x` and `x'`. So `n(k)` is *not* the free-fermion step function — it has a `1/\sqrt{k}` singularity near `k = 0` and a `∝ 1/k^4` tail, computed from Lenard’s determinant/Toeplitz representation of `ρ₁`. This card asserts the energy and `g₂(0)=0` numbers; `n(k)` is flagged exact-but-not-a-number here.

## Exact results

- Fermi momentum `k_F = πn` [@Girardeau1960]
- Ground-state energy `E/L = π²ħ²n³/(6m)`, `E/N = π²ħ²n²/(6m)` [@Girardeau1960]
- Energy coefficient (LL units) `e = π²/3`, equal to `lieb-liniger e(γ → ∞)` [@LiebLiniger1963]
- Pair-correlation contact value `g₂(0) = 0` (exact, from `Ψ_B = |Ψ_F|`) [@Girardeau1960]
- Momentum distribution `n(k)` ≠ free-fermion step (`1/\sqrt{k}` singularity, `1/k⁴` tail) — exact but not scripted

## Oracle script

`python oracle.py --n 1.0 --m 0.5 --hbar 1.0` → prints `k_F` (`πn`), `E_over_L` (`π²ħ²n³/6m`), `E_over_N` (`π²ħ²n²/6m`), `e_ll_units` (`π²/3`), `g2_zero` (`0`). Importable: `compute(n=1.0, m=0.5, hbar=1.0)`.

Self-test anchors: (1) the three free-fermion arithmetic identities at `n=1, m=1/2, ħ=1` to `1e-12`; (2) general-mass/density consistency `E/L = n·E/N` and `E/N = π²ħ²n²/6m` at `(n,m,ħ)=(2.3,0.75,1.4)`; (3) **cross-card** — `e = π²/3` equals `lieb-liniger.e_of_gamma(1000)` within the `O(4/γ)` strong-coupling band (`5e-3`), and equals its `TONKS_E` constant exactly (imported, not duplicated); (4) `g₂(0) = 0` exactly.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e_ll_units` | LL units | `π²/3 ≈ 3.289868` | [@Girardeau1960] |
| `E_over_N` | `n=1, m=1/2, ħ=1` | `π²/3 ≈ 3.289868` | [@Girardeau1960] |
| `k_F` | `n=1` | `π ≈ 3.141593` | [@Girardeau1960] |
| `g2_zero` | — | `0` (exact) | [@Girardeau1960] |

## Verification recipes

- To check an ED/DMRG/QMC energy of hard-core bosons (or the `γ ≳ 100` Lieb–Liniger gas): compare `(E/N)/n²` against `π²/3`, tolerance `1e-8` — this is the exact fermionized value.
- To check a pair-correlation measurement: `g₂(0)` must be `0` (impenetrability); any non-zero contact value signals finite `γ` (compare instead to a `lieb-liniger` finite-`γ` calculation).
- To check a momentum-distribution calculation: it must **not** match the free-fermion step — the `1/\sqrt{k}` low-`k` singularity is the correct impenetrable-boson signature (Lenard), distinguishing bosons from the fermions they share an energy with.

## Key reference

[@Girardeau1960] — Girardeau, "Relationship between Systems of Impenetrable Bosons and Fermions in One Dimension", J. Math. Phys. **1**, 516 (1960): the Bose–Fermi mapping `Ψ_B = |Ψ_F|`, the identity of all local observables with the free Fermi gas (hence the energy and `g₂(0)=0`), and the crucial caveat that the momentum distribution differs. The `π²/3` energy is the `γ→∞` endpoint of [@LiebLiniger1963]. Rendered: _(Wave 3)_.
