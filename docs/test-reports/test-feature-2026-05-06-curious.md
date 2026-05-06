# Phase 3 Persona Validation — Curious

**Date:** 2026-05-06
**Profile:** docs/agent-profiles/harness-magic-paper-reproduction-curious.md
**Target:** QMB harness — magic-paper reproduction (`2305.18541` + `2401.16498`)
**Verdict:** pass (with caveats; see Friction)
**Critical issues:** 0

## Summary

A second-year condensed-matter PhD student with no prior magic-computation experience walks into the harness, types one ambiguous opener, and within ~6 turns lands on a clean conceptual map of: (i) what `M_n` is and why `M_n=0 ↔` stabilizer, (ii) why Pauli-Markov sampling is the unique scalable estimator, (iii) why long-range magic `L(ρ_AB)` exists *separately* from full-state magic and is the right critical diagnostic in 1D. The Curious branched out three times: into `criticality/SKILL.md` end-to-end (when Fig. 9 finite-size collapse came up), into `confinement/SKILL.md` (to understand the 2D crossing), and into the companion paper `2401.16498` (to learn what Bell magic / stabilizer nullity *are*). All branches landed somewhere coherent. The session never required the user to read `pauli-markov.md` cover-to-cover — but the persona did, twice, and was rewarded each time with a sharper picture of the variance bounds.

## Coverage

| Fig / main result | Reached? | Friction |
|---|---|---|
| Fig. 1 — single-qubit / qutrit `m_n(θ)` | yes | none — `magic-conventions.md` qudit examples table is the limit-check anchor; trivial to reproduce |
| Fig. 2 — partition-mode schematics | yes | conceptual; `magic-conventions.md#Partition-modes` covers it directly |
| Fig. 3 — TTN sampling structure | partial | `methods/ttn.md` describes the `O(χ⁴ log N)` Pauli-flip update but no explicit cartoon; persona had to trust the prose |
| Fig. 4 — `c_L` increment for `m_2` in 1D Ising | yes | covered by `pauli-markov.md` Stage 2 + `magic-benchmarks.md` 1D Ising row; bench anchor present |
| Fig. 5 — 1D Clock `m_1(h)` + `ν` collapse | yes | persona reached via `potts-clock` skill → `magic` skill → `methods/pauli-markov.md`; `ν_Potts = 5/6` is the named limit anchor |
| Fig. 6 — spin-1 XXZ `m_1(D)` and `L(ρ_AB)(D)` | yes | `spin-1-xxz` skill explicitly says "full-state magic *misses* both transitions; default partition is `L(ρ_AB)`"; this is the most pedagogically clean entry point in the harness |
| Fig. 7 — 1D Ising `L(ρ_AB)(h)` w/ negative minimum | yes | bench row notes "negative extremum is physical — SRE is not subadditive"; persona absorbed this |
| Fig. 8 — 2D `Z_2` LGT `m_1, m_2` (via dual 2D TFIM) | yes | `magic-conventions.md#Wegner-duality-preservation` + `transverse-field-ising` 2D row + `confinement` skill all converge on the same dual-route |
| Fig. 9 — 2D `Z_2` LGT critical scaling, `ν = 0.64 ± 0.05` | yes | `magic-benchmarks.md` 2D row + `criticality` SKILL hand-off; `ν_{3D} ≃ 0.63` is the named anchor |
| Fig. 10 — simulated experiment (`N_M = 500`, `N_S = 10⁴`) | partial | `pauli-markov.md` "Experimental-protocol variant" exists but has fewer concrete knob defaults than the numerical variants; persona could imagine the calculation but not point at a stage-by-stage recipe |
| Fig. 11 — `δm_n` vs `(N_M, N_S)` joint convergence | partial | the variance-bias decomposition is in `pauli-markov.md` ("finite-`N_M` bias is `O(1/N_M)` and does NOT shrink with `N_S`"); persona understood the warning but no worked numerical illustration |
| Fig. 12 — `τ_int(N)` and `σ(N)` near 2D criticality | yes | "Stage 3 — convergence + variance diagnostics" is named in `pauli-markov.md`; pattern is clear |
| Fig. 13 — `m_n(χ)` convergence at 2D | yes | `methods/ttn.md` "Energy convergence as `χ` grows" gates downstream; magic-vs-Binder cross-check is in `confinement` skill |
| Fig. 14 — Binder cumulant fails at `χ = 30` | yes | `magic-benchmarks.md` 2D row literally states "the Binder cumulant fails at the same `χ`. Report the magic-vs-Binder cross-check" — this is the cleanest "method-on-problem robustness" claim in the harness |
| Main result A: full-state `m_n` peaks at 1D Ising critical | yes | bench anchor present |
| Main result B: full-state `m_n` *fails* in spin-1 XXZ | yes | flagged as the canonical motivation for `L(ρ_AB)` |
| Main result C: `L(ρ_AB)` peaks/extrema at all 1D criticalities | yes | bench rows + magic skill estimator-choice table |
| Main result D: 2D `Z_2` LGT magic *crossing* (Binder-like) | yes | `confinement` + `magic` skills both converge on this |
| Main result E: `ν` extracted from `m_1` collapse, robust at low `χ` | yes | flagged as the "magic vs Binder" robustness claim |
| Main result F: experimental protocol via Pauli measurements | partial | the *what* is in `pauli-markov.md`; the *quantitative* shot-budget table from Fig. 11 isn't mirrored in the bench card |

## Discoverability

Routing is **clean and pedagogically transparent**. From an ambiguous opener ("I want to compute magic in a critical Ising chain"), the harness routes:

1. `solve` → `transverse-field-ising` (model entry).
2. `transverse-field-ising` branch table line: *"Question is about magic / SRE / nonstabilizerness... Run wavefunction here; hand off to `physics/magic`. For 1D, the standard partition is `L(ρ_AB)`."* → tells the persona *exactly which partition* to use and *why* without asking.
3. `physics/magic` Estimator-choice table → tells which estimator for which question.
4. `methods/pauli-markov.md` → algorithm details with a clear stages declaration.
5. `magic-conventions.md` and `magic-benchmarks.md` → definitions and reference values.

The harness teaches as it goes through three mechanisms the Curious noticed:

- **Branch tables that name the failure mode.** "Full-state magic misses both Néel-Haldane and Haldane-large-`D` transitions; default to `L(ρ_AB)`" — this is the result of the paper *embedded as routing*. The persona absorbed the Fig. 6 lesson without reading Fig. 6.
- **Estimator-choice tables ranked by question.** `physics/magic` SKILL has a table mapping "Where is the critical point? (1D)" → "`L(ρ_AB)` on disjoint bipartite". The persona never had to derive the partition choice.
- **Wegner-duality preservation as a derivation result, not a runtime arg.** Living in `magic-conventions.md` once and cited from two model skills + one physics skill made the 2D `Z_2` ↔ 2D Ising route feel like a textbook fact, not a hack.

## Functionality (simulated)

Could the persona reach each figure with the harness's guidance? Yes — for 12 of 14 figures plus all 6 main results. The two partials (Fig. 10, Fig. 11) are about the *experimental* protocol where the harness has the conceptual shape (`pauli-markov.md` "Experimental-protocol variant") but no worked numerical recipe with the paper's `(N_M, N_S)` = `(500, 10⁴)` benchmark. The Curious flagged this gap explicitly.

For the numerical figures, the persona can articulate end-to-end:

- *what to compute*: `m_n` density at multiple `h`, multiple `L`; auto-correlation diagnostics; finite-size collapse on `m_1 − m_{1,m} = L^{-γ/ν} f(L^{1/ν}(h - h_c))`.
- *what bond dim to start at*: TTN `χ ∈ {30, 36, 60}` per `methods/ttn.md` "Starting point" + `magic-benchmarks.md` per-row guidance.
- *what to verify against*: limit checks (single-qudit baseline, stabilizer-state limit), `χ`-convergence, `N_S`-convergence (reblocked errors, `1/√N_S`), `ν` against the analytic anchor (`ν_Potts = 5/6` for Clock, `ν_{3D} ≃ 0.63` for 2D LGT).

## Style genericness (Curious-specific)

This is where the Curious profile most stress-tests the harness. Findings:

**Reasoning was embedded *enough*.** The reports the persona simulated had the form: "running `M_1` via Pauli-Markov on TTN at `χ = 30` because `m_1` has at-most-quadratic variance and TTN gives `O(log N)` Pauli-flip updates; the result is converged in `χ` to `10⁻³` and matches `magic-benchmarks.md` 2D Ising crossing point at `h_c ≃ 3.04`. Magic *crosses* (does not peak); both phases volume-law in magic. ✓". That's the right amount of *why*. The Curious does not feel they're being talked down to.

**Pros/cons are substantive.** The Curious explicitly tested non-recommended branches by reading them. Examples:

- `magic` SKILL Estimator-choice table: choosing `M_2` direct over the increment trick → routes to "When to switch" reasoning ("when SRE is volume-law, direct sampling is exponentially expensive — use the increment construction"). The non-recommended branch teaches what failure looks like.
- `methods/ttn.md` "TTN vs MPS" table: the Curious deliberately followed the MPS-perfect-sampling row to see what crossover point applied. The table answered ("crossover when `N/log N ≳ χ`") so the persona could compute their own break-even.
- `magic` SKILL "Cross-checks" table: each row reads "Competing explanation → Test that rules it out" rather than "do this, don't do that". This is exactly the philosophy a Curious wants — *constraints*, not *commands*.

**Non-recommended-option branches landed somewhere useful.** E.g., the Curious chose to read `confinement/SKILL.md` end-to-end (not strictly necessary for the 1D figures), and discovered the magic-vs-Binder robustness claim *before* it appeared in `magic-benchmarks.md`. The skill graph is dense enough that branching for curiosity is rewarded, not punished.

**One real gap:** the harness is *very* terse about the Bell magic / stabilizer nullity / Pauli-basis MPS lift (the companion paper `2401.16498`). `pauli-markov.md` mentions the variant in 7 lines and hands off; there is no model-skill row pointing the persona at "I want Bell magic on Ising" → which estimator? The Curious had to read the companion paper directly to fill this in. For a research user that is fine; for an undergraduate user it would be a wall.

## Judgment-transfer evidence

Persona's post-hoc summary, written as the Curious would write it:

> **What is magic, and why does this paper matter?**
>
> Magic is the resource cost of preparing a state with non-Clifford gates. Operationally: `M_n(ρ) = (1/(1-n)) log Σ_P |⟨P⟩|^{2n} / d^N` is the Rényi-`n` entropy of the Pauli expectation distribution `Ξ_P = |⟨P⟩|² / d^N`. It vanishes exactly when `ρ` is a stabilizer state. The *density* `m_n = M_n/N` is what gets reported for many-body states. Stabilizer states (eigenstates of Clifford-Pauli stabilizer groups) are classically simulable; magic is the gap to "yes, this is hard to simulate".
>
> **Why Pauli-Markov?** Direct evaluation of `M_n` requires summing over `4^N` Pauli strings — death. The trick: treat `Ξ_P` itself as the target distribution of a Metropolis chain on Pauli strings. Most Pauli expectation values are tiny; the chain finds the heavy ones. Variance bound for `M_1` is at most quadratic in `N` (polynomial cost). For `M_n` with `n > 1` and *volume-law* magic, variance grows exponentially in `N` — you fix this with the increment trick `c_N = 2 M_n(N/2) − M_n(N)`, which kills the volume-law term and leaves `O(log N)` substructure with polynomial sample cost. TTN as the wavefunction backbone gives `O(χ⁴ log N)` per Pauli-flip move because only the `log N` links from the modified site to the root need re-coarse-graining.
>
> **Why does this paper matter?** Three results, listed in increasing depth:
>
> 1. *Full-state magic detects 1D Ising and Potts criticality but FAILS for spin-1 XXZ Haldane transitions.* The lesson: full-state `m_n` is basis-dependent and UV-divergent in the field-theory limit; it cannot be a universal critical diagnostic.
> 2. *Long-range magic `L(ρ_AB) = M̃_2(ρ_AB) − M̃_2(ρ_A) − M̃_2(ρ_B)` IS UV-finite (mutual-information-like), and IT detects criticality everywhere they tried.* This is the conceptual fix — the analog of mutual information for the magic resource.
> 3. *In 2D `Z_2` lattice gauge theory ↔ 2D TFIM via Wegner duality, magic shows a Binder-cumulant-like CROSSING (not a peak) at the confinement-deconfinement transition, and finite-size collapse extracts `ν = 0.64 ± 0.05` (3D Ising universality, `ν_{3D} ≃ 0.63`) at modest `χ = 30` where the Binder cumulant itself is not yet converged.* This is a "method-on-problem robustness" claim: the magic estimator extracts the universality class at bond dimensions where the conventional order-parameter-based diagnostic fails.
>
> The companion paper `2401.16498` is the deterministic Pauli-basis MPS lift — same conceptual framework, traded Markov-chain variance for tensor-network truncation error, opens up Bell magic and stabilizer nullity as bonus monotones.

This articulation is *unprompted* in the sense that no skill ever lectured it; the Curious assembled it from `magic-conventions.md` + `magic-benchmarks.md` + `pauli-markov.md` + the four skill branch tables + ~8 minutes reading paper sections. That's the harness teaching by routing, exactly as advertised in the philosophy.

## Friction points

1. **`pauli-markov.md` "Experimental-protocol variant" is shallow vs the numerical variants.** Three runtime variants are declared at the top of the card but the experimental one gets one short paragraph plus a knob row. The Curious can imagine the calculation (Algorithm 1 with `Tr(ρP) → P̄`) but the harness doesn't surface a stage-by-stage recipe nor a benchmark anchor for `(N_M, N_S)` choice. Figs. 10–11 of the paper are reachable conceptually but not bench-able.

2. **No Bell magic / stabilizer nullity branch in the magic skill's estimator-choice table is *highlighted*.** It's there ("Bell magic / stabilizer nullity / stabilizer-group identification → Deterministic Pauli-basis MPS lift") but the persona had to read every row to find it. For a Curious branching out from the companion paper, a `Related: Bell magic, stabilizer nullity` block would shorten the route.

3. **The TTN-vs-MPS crossover in `methods/ttn.md` is correct but lacks a worked numerical example.** The Curious wanted "for `N = 64`, `χ = 60`, is TTN faster?" — the table says "crossover when `N/log N ≳ χ`" which yields `N/log N ≈ 10` — but a concrete number ("for `N ≥ 64`, TTN wins at `χ ≥ 30`") would have closed the loop without the persona doing arithmetic.

4. **`magic-benchmarks.md` reports the methodology-paper extracted `ν ≈ 0.844` for Clock alongside the analytic `ν_Potts = 5/6 ≈ 0.833`** with the right framing ("use the analytic value as the limit-check anchor"). But the analogous statement is missing for `ν_{3D} ≃ 0.63` — the 2D row reports `ν = 0.64 ± 0.05` from the methodology paper but doesn't make the analytic-anchor distinction quite as explicit. Minor; both numbers are within each other's error bars.

5. **No skill-level pointer to the *autocorrelation analysis* (Fig. 12) as a stand-alone deliverable.** It lives in `pauli-markov.md` Stage 3 but is presented as "diagnostics", not as something the user might ask for explicitly. The Curious wanted to reproduce Fig. 12 as its own plot and had to construct the request without harness help.

## Suggestions

1. **Flesh out `pauli-markov.md` "Experimental-protocol variant" to a peer of the numerical variants.** Same Stages 0–3 structure, with explicit `(N_M, N_S)` knobs, a noted `O(1/N_M)` bias floor, and at minimum the Fig. 10 / Fig. 11 benchmark anchors as a "Variant verification" subsection. ~30 lines.

2. **Add a "Related monotones" line at the top of the `physics/magic` skill** pointing at the Pauli-basis MPS lift's Bell-magic / nullity / stabilizer-group capability. One sentence: "When the question is *which* stabilizers, not *how much* magic, route to the deterministic Pauli-basis lift in `pauli-markov.md`."

3. **In `magic-benchmarks.md`, add a "single-qudit-product upper bounds" mini-table** as a quick limit anchor: `(2/3) log 4 ≈ 0.92` for spin-1 XXZ at the Haldane plateau, the `θ = π/4` and `θ = 2π/9` qubit/qutrit T-state values, and the Ising-product upper bound for the disordered-phase plateau. Saves the persona one round trip to `magic-conventions.md`.

4. **In `methods/ttn.md`, add one line under the TTN-vs-MPS crossover** with the worked break-even: "Practically: for `N ≳ 32` and `χ ≳ 30`, TTN wins." Removes the `log N` arithmetic step.

5. **Surface autocorrelation-time analysis as a named harness primitive.** Either as a `finite-size-scan` flavor or a one-line bullet under `pauli-markov.md` Stage 3 "Output: `τ_int(N)` and `σ(N)` curves with reblocked-error fits". This is a paper figure (Fig. 12) and a verification deliverable; right now it's diagnostic-only.
