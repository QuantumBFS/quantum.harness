# Magic / Nonstabilizerness Benchmark Numbers

Reference values for stabilizer Rényi entropies (SREs) and long-range magic across canonical models. Cited from the `physics/magic` skill's verification step and from model-skill magic branches. Per AGENTS.md "Verification practice §6", contested or method-sensitive values are reported as ranges, not single points.

Convention: the harness `M_n` definition lives in `knowledge-base/magic-conventions.md`. Numbers below assume that convention; if a paper uses a different normalization, translate before comparing.

## 1D quantum Ising chain

Hamiltonian: `H = − Σ_{⟨ij⟩} σ^x_i σ^x_j − h Σ_i σ^z_i`. Critical point `h_c = 1`, central charge `c = 1/2`.

| Quantity | Reference behavior | Source |
|---|---|---|
| `m_1(h)` | Sharp peak at `h_c = 1`; volume-law in `h ≠ 1` regions. | See `knowledge-base/literature/magic/INDEX.md` for the methodology reference that established `m_n` peaks at criticality. |
| `m_1(h_c)` | Reference range bracketing the established critical density: `m_1(h_c) ≈ 0.10 – 0.14` (entry-level `L = 32–128` and `χ = 30` from the methodology reference). Treat as a literature *range*, not a point — finite-`L` corrections push the value upward by `O(1/L)`. | `knowledge-base/literature/magic/INDEX.md` — methodology-reference entry for 1D Ising `m_n(h_c)`. |
| `m_2(h)` (increment-trick) | Same peak at `h_c = 1`; the increment construction recovers a sub-`log L` error scaling. | Same reference; the entry that introduces the increment-trick estimator. |
| `m_2(h_c)` | Reference range `m_2(h_c) ≈ 0.07 – 0.11` (same `L`, `χ` window; `M_2` is consistently smaller than `M_1` per the inequality `M_n ≥ M_m` for `n ≤ m`). | Same reference. |
| `L(ρ_AB)(h)` | Peaks at `h_c = 1`; logarithmic growth in `L` at criticality (consistent with a CFT mutual-information form). | Same reference; the entry establishing long-range magic as a critical diagnostic in 1D. |
| `L(ρ_AB)(h_c)` | Reference range: negative extremum, magnitude growing as `~log L` with `L`-dependence consistent with the Calabrese-Cardy mutual-information form. Methodology reference reports `L(ρ_AB)(h_c) ≈ −(0.04 – 0.10)` across `L = 16–128` (negative; magnitude scaling logarithmically). Report the literature *range* and the size-trend, not a single number. | Same reference. |
| `L(ρ_AB)` sign at the Ising critical point | Negative extremum (a minimum, not a maximum). | Same reference. SRE does not satisfy subadditivity; sign is physical. |

Use as a verification target whenever the user runs magic on 1D TFIM. For finite `L`, expect `L`-dependent corrections; report your trend, do not overclaim agreement. The two numerical ranges above are the harness's literature anchors per AGENTS.md verification rule §6 — compare to the *range*, not a trophy point.

## 1D quantum 3-state Clock / Potts model

Hamiltonian (qutrit, `d=3`): `H = − Σ_{⟨ij⟩} (X_i X_j^† + X_i^† X_j) − h Σ_i (Z_i + Z_i^†)`. Critical point `h_c = 1`, `Z_3` parafermion CFT with central charge `c = 4/5`.

| Quantity | Reference behavior | Source |
|---|---|---|
| `m_1(h)` | Maximum at `h_c = 1`. | `knowledge-base/literature/magic/INDEX.md` — entry providing the Potts magic-density benchmark. |
| Critical exponent `ν` (data-collapse on `m_1`) | Literature range: `ν ∈ [0.83, 0.85]`, anchored at the analytic CFT value `ν_Potts = 5/6 ≈ 0.833` (limit-check anchor) and bracketing the methodology reference's reported `ν ≈ 0.844` from finite-size collapse. Report extracted `ν` against this range; agreement within the range is the verification standard. | Same reference + analytic CFT. |
| Critical exponent `γ/ν` | Reference range of order `0.65 – 0.67`; methodology reference reports `γ/ν ≈ 0.66`. | Same reference. |

`ν_Potts = 5/6` is the analytic Potts value from the parafermion CFT — this is the *limit-check anchor*, the trustworthy point inside the range. The numerically extracted `ν ≈ 0.844` is a finite-size-collapse fit subject to method bias and lies inside the range. Always compare to the range, not to the trophy number.

## 1D spin-1 XXZ chain with single-ion anisotropy

Hamiltonian: `H = − Σ_{⟨ij⟩} (S_i^x S_j^x + S_i^y S_j^y + Δ S_i^z S_j^z) + D Σ_i (S_i^z)²`. At `Δ = 1` (isotropic): three phases — Néel (`D ≪ −0.3`), Haldane SPT (`−0.3 ≲ D ≲ 0.97`), large-`D` trivial (`D ≳ 0.97`).

| Quantity | Reference behavior | Source |
|---|---|---|
| `m_1(D)` in the Haldane phase | Large and roughly constant; saturates near the single-qutrit-product upper bound `(2/3) log 4 ≈ 0.92`. Drops in neighboring phases. | `knowledge-base/literature/magic/INDEX.md` — entry providing the spin-1-XXZ magic benchmark. |
| `m_1(D)` at the transitions | No sharp peak; full-state magic *misses* both Néel-Haldane and Haldane-large-`D` transitions. | Same reference; the failure mode that motivates `L(ρ_AB)`. |
| `L(ρ_AB)(D)` | Clear extrema at both transitions. Peak near the Haldane / large-`D` Gaussian transition is consistent with `D ≈ 0.97` from large-system DMRG references. | Same reference; same entry. |
| Néel / Haldane transition | Reference `D ≈ −0.3` (Ising universality). | DMRG references cited from the same entry. |
| Haldane / large-`D` transition | Reference `D ≈ 0.97` (Gaussian universality). | DMRG references cited from the same entry. |

## 2D `Z_2` lattice gauge theory ≡ 2D transverse-field Ising on the dual square lattice

Wegner duality preserves SREs (`knowledge-base/magic-conventions.md`); the actual numerical computation goes through 2D TFIM. Hamiltonian on the dual: `H_{2D-Ising} = − Σ_{⟨ij⟩} σ^x_i σ^x_j − h Σ_i σ^z_i`.

| Quantity | Reference value | Source |
|---|---|---|
| Critical field `h_c` | `h_c ≃ 3.04` (3D Ising universality) | `knowledge-base/literature/magic/INDEX.md` — entry that establishes the 2D magic crossing at this point; original `h_c` from QMC literature cited within. |
| `m_1(h)`, `m_2(h)` qualitative behavior | *Crossing* near `h_c` (Binder-cumulant-like), not a peak; both confined and deconfined phases are volume-law in magic. | Same reference. |
| Correlation-length exponent `ν` (from data collapse on `m_1`) | Literature range: `ν ∈ [0.59, 0.69]`, anchored at the established 3D-Ising universality value `ν_{3D} ≃ 0.63` (limit-check anchor from the QMC literature) and bracketing the methodology reference's reported `ν = 0.64 ± 0.05` from finite-size collapse on `m_1`. Both numbers sit inside the range. Report extracted `ν` against the range, not against either single number. | Same reference + 3D Ising QMC literature. |
| Robustness vs `χ` | `m_1` extracts `ν` even at `χ = 30`; the Binder cumulant fails at the same `χ`. Report the magic-vs-Binder cross-check whenever bond dimension is the limiting resource. | Same reference. |
| 2D limit-check endpoints | `h ≪ J`: ground state is the all-aligned ferromagnet `|↑…↑⟩`, a +1 stabilizer of all `σ^z`; `m_n → 0` analytically. `h ≫ J`: ground state is the all-aligned paramagnet `|+…+⟩`, a +1 stabilizer of all `σ^x`; `m_n → 0` analytically. The crossing lives between these two endpoints. | Stabilizer-state limit; `knowledge-base/magic-conventions.md`. |

`ν_{3D} ≃ 0.63` is the analytic / consensus 3D Ising universality value from a long QMC literature — the *limit-check anchor*. The methodology reference's `ν = 0.64 ± 0.05` is the magic-derived collapse result, which sits inside the range and agrees with the universality class. Compare to the range, not to either number alone.

## Single-qudit limit

For verification at `N = 1`:

| State family | Quantity | Value |
|---|---|---|
| Qubit `|ψ(θ)⟩ = (|0⟩ + e^{iθ}|1⟩)/√2` | `m_1(θ)`, `m_2(θ)` | Analytic from `M_n` definition; both vanish at `θ = mπ/2`. Maximum near `θ = π/4` (`|T⟩`). |
| Qutrit `|φ(θ)⟩ = (|0⟩ + e^{iθ}|1⟩ + e^{−iθ}|2⟩)/√3` | `m_1(θ)`, `m_2(θ)` | Analytic; vanish at `θ = m·2π/3`. Maximum near `θ = 2π/9` (qutrit `|T⟩`). |

These analytics are the limit-check anchor for any new magic implementation: it must recover them within machine precision.

## How to use this file

- Cite as `knowledge-base/magic-benchmarks.md#<model>` from `physics/magic` and the relevant model skills' verification steps.
- For the 2D `Z_2` ↔ 2D Ising row, cite alongside the `magic-conventions.md` "Wegner-duality preservation" note.
- If your problem is not listed: report converged values with bond-dim and `N_S` trends, *do not fabricate a benchmark*. Per AGENTS.md verification rule 6, contested values get the literature *range*, not a single number.
- New benchmarks land here when a real workflow begins citing them. Citation is by *what the reference provides* (a benchmark, a method) rather than by author/year, per the milestone authoring discipline.
