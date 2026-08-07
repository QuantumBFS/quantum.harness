# Sawtooth-chain localized magnons — exact-solution oracle

Technique: T5 (frustration-free / exact eigenstates) · Tier: C (exact eigenstates and degeneracies at special points) · Script: S

## Hamiltonian & conventions

$$ H = \sum_i \left[\, J_1\,\mathbf{S}_{A_i}\!\cdot\!\mathbf{S}_{A_{i+1}} + J_2\,(\mathbf{S}_{A_i}\!\cdot\!\mathbf{S}_{B_i} + \mathbf{S}_{B_i}\!\cdot\!\mathbf{S}_{A_{i+1}})\,\right] - h \sum_i S^z_i $$

Conventions: spin-½ `S`-operators (`d = 2`); sawtooth (delta) chain with `N = 2N_c` sites, base `A_i` = site `2i`, apex `B_i` = site `2i+1` (0-based), PBC. `J1` couples base–base along the chain, `J2` couples apex–base (two bonds per apex). Both AFM (`> 0`), `J1 = 1` sets the unit. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/sawtooth-chain/MODEL.md` (same `J1`/`J2` convention).

**Two distinct special points — do not conflate** (flagged trap in QuantumBFS/quantum.harness#112): the **flat-band point** `J2 = 2 J1` (localized magnons, high-field exactness) and the **Monti–Sütő point** `J2 = J1, h = 0` (exact two-fold valence-bond ground state).

## Solvability statement

T5: at `J2 = 2 J1` the lowest one-magnon band is **exactly flat** (destructive interference localizes a magnon on a single cell), so the many-magnon problem at the saturation field reduces to **independent localized particles with a hard-dimer exclusion** (no two magnons on adjacent cells). Exact: the flat-band energy, the saturation field, the magnetization jump, the full ground-state degeneracy at `h_sat` (hard-dimer/Lucas count), and the residual entropy; at `J2 = J1`, the two-fold ground state. **Not exact:** the spectrum away from these points, the detuned (`J2 ≠ 2 J1`) erosion curves, excitations, and finite-T thermodynamics — all numerical (see `tracks/agent-kb/solutions/problem-factory/briefs/sawtooth-erosion-001.md` for first erosion curves).

## Exact results

- Flat band: one-magnon energy `ε = −2 J2 = −4 J1` at `J2 = 2 J1`, dispersionless [@Schulenburg2002]
- Saturation field `h_sat = 2 J2 = 4 J1` [@Schulenburg2002]
- Magnetization jump at `h_sat`: `ΔM = M_sat/2` (macroscopic, from `N/4` zero-cost magnons) [@Schulenburg2002]
- Ground-state degeneracy at `h_sat` = number of hard-dimer coverings of the `N_c`-cell ring = **Lucas(`N_c`)**; `N = 12` (`N_c = 6`) → `18` [@ZhitomirskyHonecker2004]
- Residual entropy `S/N = (1/2) ln φ ≈ 0.2406 k_B` (φ golden ratio) [@ZhitomirskyHonecker2004]
- Monti–Sütő point `J2 = J1, h = 0`: exact two-fold valence-bond ground state [@MontiSuto1991]

## Oracle script

`python oracle.py --N 12 --j2 2.0 --h 4.0` → prints `one_magnon_band_min/max`, `e_ground`, `gs_degeneracy`, `entropy_per_site`. Importable: `compute(N=12, j2=2.0, j1=1.0, h=4.0)`; builder `sawtooth_hamiltonian(N, j2, j1, h, n_up)`. `python oracle.py self-test` runs the anchors.

Self-test anchors (all N=12): (1) one-magnon band flat, `min = max = −4` to 1e-10; (2) `e_ground` at `h_sat` equals the polarized-state energy `−16.5`; (3) `gs_degeneracy = 18` exactly; (4) `S/N = 0.2409 ≈ 0.2406`; (5) sector ground energies flat for `k ≤ N/4` and strictly rising above (hard-dimer constraint — the jump plateau); (6) Monti–Sütő doublet: `E₂−E₁ < 1e-10`, `E₃−E₁ > 1e-3`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `one_magnon_band_min=max` | `J2 = 2`, `h = 0` | `−4.0` | [@Schulenburg2002]; ED this card (dense, N=12) + XDiag cross-check |
| `e_ground` | `J2 = 2`, `h = 4`, N=12 | `−16.5` | Analytic (polarized energy); ED + XDiag |
| `gs_degeneracy` | `J2 = 2`, `h = 4`, N=12 | `18` (= Lucas(6)) | [@ZhitomirskyHonecker2004]; ED + XDiag |
| `entropy_per_site` | N=12 | `0.2409` (`→ 0.2406` as N→∞) | [@ZhitomirskyHonecker2004]; ED |
| `E₂−E₁` | `J2 = 1`, `h = 0`, N=12 | `0` (twofold) | [@MontiSuto1991]; ED + XDiag |

Cross-check: `tracks/agent-kb/solutions/problem-factory/scripts/xdiag_crosscheck.jl` (XDiag 0.5.0, julia-env) reproduces all anchors to ≤ 1e-8 — **Harness anchor**.

## Verification recipes

- To check any ED/DMRG sawtooth run at `J2 = 2 J1`: the one-magnon sector must be flat at `−4 J1` (spread < 1e-8), and the `h_sat` ground-state degeneracy must be an **exact integer** (Lucas(N_c)) — off by one is a bug, not a discrepancy.
- Convention trap: an energy per site off by a factor ~4 means Pauli-vs-spin mix-up; a "flat band" at `−2 J1` means the apex coupling was doubled by mistake (counting both `J2` bonds twice).

## Key reference

[@Schulenburg2002] — Schulenburg, Honecker, Schnack, Richter, Schmidt, PRL 88, 167207 (2002): the canonical localized-magnon paper (flat-band condition, jump, exact eigenstates). `bib stub — no PDF reachable (2026-07-28)`. Review: [@Derzhko2015].
