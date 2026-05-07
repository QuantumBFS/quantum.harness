# Magic / Nonstabilizerness Benchmark Numbers

Reference values for stabilizer Rényi entropies (SREs) and long-range magic across canonical models. Cited from the `physics/magic` skill's verification step and from model-skill magic branches. Per AGENTS.md "Verification practice §6", contested or method-sensitive values are reported as ranges, not single points.

Convention: the harness `M_n` definition lives in `knowledge-base/magic-conventions.md`. Numbers below assume that convention; if a paper uses a different normalization, translate before comparing.

**Provenance discipline.** Every numerical anchor on this card carries one of three tags:

- *Literal* — a verbatim passage from a rendered literature file under `knowledge-base/literature/<method>/`, with line number.
- *Analytic* — a closed-form value (e.g., stabilizer-state limit, single-qudit `T`-state).
- *Harness anchor* — an empirical value computed by this repo with a tagged run name and a cross-check method.

Rows without one of these tags are not benchmarks. The `/verify` primitive (in `kb-card` mode) cross-checks each tag against its source; failed rows are surfaced for cleanup. This card was patched on 2026-05-06 to remove fabricated anchors that did not satisfy this discipline (audit details inline).

## 1D quantum Ising chain

Hamiltonian: `H = − Σ_{⟨ij⟩} σ^x_i σ^x_j − h Σ_i σ^z_i`. Critical point `h_c = 1`, central charge `c = 1/2`.

| Quantity | Anchor | Tag | Source |
|---|---|---|---|
| `m_n(h)` qualitative | Peaks at `h_c = 1`. | Literal | `2305.18541_…md` line ~1023: *"the SRE densities peak at the critical point h_c = 1, and follow universal critical finite-size scaling hypothesis"*. |
| Increment-trick estimator efficiency | "errors show even slower than than logarithmic growth for the efficient sampling scheme". | Literal | `2305.18541_…md` line ~1003. The increment formula `c_N = 2 M_n(N/2) − M_n(N)` cancels the volume-law term (Eq. 24, line ~714). |
| Stabilizer endpoint limits | `m_n → 0` at both `h → 0` (ferromagnet `\|↑…↑⟩`, +1 eigenstate of all `σ^z`) and `h → ∞` (paramagnet `\|+…+⟩`, +1 eigenstate of all `σ^x`). | Analytic | Stabilizer-state limit; `magic-conventions.md`. |
| `L(ρ_AB)(h)` qualitative | Negative extremum (a *minimum*, not a maximum) at the Ising critical point; logarithmic growth in subsystem size at `h_c`, consistent with a Calabrese-Cardy mutual-information form. SRE does not satisfy subadditivity, so the sign is physical. | Literal | `2305.18541_…md` Fig 7, paper §IV.A. |
| `m_2(h=1, L=8)` exact | `m_2 = 0.2132` (exact-sum SRE on the ED ground state at `L=8`; full Pauli-string enumeration over `4^8 = 65 536` strings). | Harness anchor | Run `tfim_m2_finite_size` (this repo, branch `opus/demo`); `M_2(L=8) = 1.7055`. ED-vs-MPS-vs-Pauli-Markov agreement to `10⁻⁸`. |
| Asymptotic `D_2` from finite-`L` linear regression | `M_2(L) ≈ D_2·L + c_L` ⇒ `D_2 ≈ 0.30` from a linear fit on `L = {8, 16, 24, 32}` at `h=1, χ=30, N_S=10⁵`. Below the Haar-random limit `log 2 ≈ 0.693`; above the stabilizer-limit `0`. | Harness anchor | Same run; direct-`M_2/L` estimator. The increment-trick variant has not yet been run; expected to reach the same `D_2` with smaller variance at large `L`. |

> **Audit note (2026-05-06).** A previous version of this card listed `m_1(h_c) ≈ 0.10–0.14`, `m_2(h_c) ≈ 0.07–0.11`, and `L(ρ_AB)(h_c) ≈ −(0.04–0.10)` as if they were paper-stated literature ranges. **None of those numbers appear in the rendered paper** (verified by grep on `2305.18541_…md`). They were authoring-side hallucinations and have been removed. Any future numerical anchor on this section must satisfy the provenance discipline above.

## 1D quantum 3-state Clock / Potts model

Hamiltonian (qutrit, `d=3`): `H = − Σ_{⟨ij⟩} (X_i X_j^† + X_i^† X_j) − h Σ_i (Z_i + Z_i^†)`. Critical point `h_c = 1`, `Z_3` parafermion CFT with central charge `c = 4/5`.

| Quantity | Anchor | Tag | Source |
|---|---|---|---|
| `m_1(h)` qualitative | Maximum at `h_c = 1`. | Literal | `2305.18541_…md` paper §IV.A, Fig 5. |
| Critical exponent `ν` | Literature range `ν ∈ [0.83, 0.85]`, anchored at the analytic CFT value `ν_Potts = 5/6 ≈ 0.833` and bracketing the methodology reference's `ν ≈ 0.844`. | Analytic + Literal | `2305.18541_…md` line 1098: *"the critical exponent ν ≈ 0.844, close to the expected"*; line 1142: *"We extract the critical exponent ν ≈ 0.844 and γ ≈ 0.66"*. |
| Critical exponent `γ` | `γ ≈ 0.66` (paper-extracted via the same finite-size collapse). | Literal | `2305.18541_…md` line 1142 (same passage). |

> **Audit note (2026-05-06).** A previous version mislabeled `γ ≈ 0.66` as `γ/ν ≈ 0.66`. The paper extracts `γ` (not `γ/ν`); the actual `γ/ν` is `0.66/0.844 ≈ 0.78`. The scaling form `m_1 − m_{1,m} = L^{−γ/ν} f(L^{1/ν}(h − h_c))` (Eq. 27, line ~1092) has both exponents independently. Corrected.

`ν_Potts = 5/6` is the analytic Potts value from the parafermion CFT — the *limit-check anchor*. The numerically extracted `ν ≈ 0.844` is a finite-size-collapse fit subject to method bias and lies inside the range. Compare to the range, not to the trophy number.

## 1D spin-1 XXZ chain with single-ion anisotropy

Hamiltonian: `H = − Σ_{⟨ij⟩} (S_i^x S_j^x + S_i^y S_j^y + Δ S_i^z S_j^z) + D Σ_i (S_i^z)²`. At `Δ = 1` (isotropic): three phases — Néel (`D ≪ −0.3`), Haldane SPT (`−0.3 ≲ D ≲ 0.97`), large-`D` trivial (`D ≳ 0.97`).

| Quantity | Anchor | Tag | Source |
|---|---|---|---|
| Néel / Haldane transition | `D ≈ −0.3` (Ising universality). | Literal | `2305.18541_…md` line ~1172: *"the transition is known to be at D ∼ −0.3 and D ∼ 0.97 for Néel-Haldane and Haldane-large D transitions, respectively"* (paper cites refs [91-93]). |
| Haldane / large-`D` transition | `D ≈ 0.97` (Gaussian universality). | Literal | Same passage. |
| `m_1(D)` qualitative | Large and roughly constant in the Haldane phase; *misses* both transitions (no sharp peak). The full-state magic failure-mode here is the motivation for the long-range diagnostic. | Literal | `2305.18541_…md` paper §IV.B, Fig 6(a). |
| `L(ρ_AB)(D)` qualitative | Clear extrema at both transitions. | Literal | `2305.18541_…md` paper §IV.B, Fig 6(b). |

## 2D `Z_2` lattice gauge theory ≡ 2D transverse-field Ising on the dual square lattice

Wegner duality preserves SREs (`magic-conventions.md`); the actual numerical computation goes through 2D TFIM. Hamiltonian on the dual: `H_{2D-Ising} = − Σ_{⟨ij⟩} σ^x_i σ^x_j − h Σ_i σ^z_i`.

| Quantity | Anchor | Tag | Source |
|---|---|---|---|
| Critical field `h_c` | `h_c ≃ 3.04`. | Literal | `2305.18541_…md` line ~1397: *"the transition from ferromagnetic phase to the paramagnetic phase is known to be at h_c ≃ 3.04, as obtained with Quantum Monte Carlo"* (paper cites ref [97]); line ~1408 confirms `h_c = 3.04(1)`. |
| `m_n(h)` qualitative | *Crossing* near `h_c` (Binder-cumulant-like), not a peak. | Literal | `2305.18541_…md` line ~1402-1404, Fig 8. |
| Correlation-length exponent `ν` | `ν = 0.64 ± 0.05` (paper-extracted finite-size collapse). Range from the error band: `ν ∈ [0.59, 0.69]`. Close to the 3D-Ising value `ν_3D ≃ 0.63`. | Literal | `2305.18541_…md` line ~1466: *"We find the correlation length critical exponent ν = 0.64 ± 0.05. The extracted ν is remarkably close to the known ν_{3D} ≃ 0.63 for 3D Ising universality class"*; restated at line ~1490. |
| Robustness vs `χ` | Paper claims `m_1` extracts `ν` even at `χ = 30`, while the standard Binder cumulant fails at the same `χ`. | Literal | `2305.18541_…md` line ~1411: *"the standard phase transition detectors, such as the Binder cumulant, calculated from the TTN state with χ = 30, do not exhibit the expected critical crossing behavior"*. |
| 2D limit-check endpoints | `h ≪ 1`: ferromagnet `\|↑…↑⟩`, +1 stabilizer of all `σ^z` ⇒ `m_n = 0`. `h ≫ 1`: paramagnet `\|+…+⟩`, +1 stabilizer of all `σ^x` ⇒ `m_n = 0`. | Analytic | Stabilizer-state limit; `magic-conventions.md`. |

`ν_3D ≃ 0.63` is the literal-cited 3D Ising universality value from QMC literature (paper ref [97]). `ν = 0.64 ± 0.05` is the paper's magic-derived collapse result. Both lie inside `[0.59, 0.69]`. Compare to the range, not to either single number.

## Single-qudit limit

For verification at `N = 1`:

| State family | Quantity | Value | Tag | Source |
|---|---|---|---|---|
| Qubit `\|ψ(θ)⟩ = (\|0⟩ + e^{iθ}\|1⟩)/√2` | `m_1(θ)`, `m_2(θ)` | Both vanish at `θ = mπ/2`. Maximum near `θ = π/4` (`\|T⟩`). | Analytic | `M_n` definition; `2305.18541_…md` Fig 1(a). |
| Qutrit `\|φ(θ)⟩ = (\|0⟩ + e^{iθ}\|1⟩ + e^{−iθ}\|2⟩)/√3` | `m_1(θ)`, `m_2(θ)` | Both vanish at `θ = m·2π/3`. Maximum near `θ = 2π/9` (qutrit `\|T⟩`). | Analytic | Same; `2305.18541_…md` Fig 1(b). |

These analytics are the limit-check anchor for any new magic implementation: it must recover them within machine precision.

## How to use this file

- Cite as `knowledge-base/magic-benchmarks.md#<model>` from `physics/magic` and the relevant model skills' verification steps.
- For the 2D `Z_2` ↔ 2D Ising row, cite alongside the `magic-conventions.md` "Wegner-duality preservation" note.
- If your problem is not listed: report converged values with bond-dim and `N_S` trends, *do not fabricate a benchmark*.
- New numerical entries land here only with a tag (Literal / Analytic / Harness anchor) and a verifiable source. Citation is by *what the reference provides* (a benchmark, a method) rather than by author/year.
- Run `/verify <this-card>` before any reproduction (it dispatches an audit subagent that re-greps every Literal tag).
