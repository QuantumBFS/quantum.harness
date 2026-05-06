# Phase 3 Persona Validation — Skeptical

**Date:** 2026-05-06
**Profile:** docs/agent-profiles/harness-magic-paper-reproduction-skeptical.md
**Target:** QMB harness — magic-paper reproduction
**Verdict:** partial
**Critical issues:** 3

## Summary

Read-only fresh-harness reproduction (no compute) of arXiv 2305.18541 + 2401.16498, played as a third-year condensed-matter PhD student who reflexively gates every result on the AGENTS.md six-step verification list. The harness routes the persona cleanly to `physics/magic`, the conventions and benchmarks cards cite literature *ranges* (good for the Skeptical persona), and the cross-method-check primitive is a real, named tool. The verification practice mostly survives, but several friction points are real: the harness does not expose a single "verify everything" command, the cross-method gate to ED is the persona's responsibility (no skill auto-pairs DMRG/TTN with ED at small `N`), and the 1D-Ising row of `magic-benchmarks.md` cites only qualitative behavior rather than a concrete numerical anchor for `m_1(h_c)`. Pushback at the bond-dimension default (`χ = 30`) was handled correctly per the AGENTS.md "Pushback and reconsideration" pattern: the harness restated the prior reasoning (Fig. 9 is the canonical low-`χ` evidence; the claim is *robustness*, not *exact numerics*), and offered to bump `χ` for the Binder cross-check rather than capitulating.

## Coverage

The 14 figures + 6 main results, with the persona's Verification-gate verdict.

| Fig / main result | Reached? | Verification status (six-step) | Friction |
|---|---|---|---|
| Fig 1 — single-qubit/qutrit `m_1`, `m_2` analytics | yes | limit ✓ symm ✓ conv N/A var N/A cross ✓ bench ✓ — `magic-conventions.md` qudit examples + `magic-benchmarks.md` "single-qudit limit" row are the analytic anchor. Persona gates pass cleanly. | None — harness routes the fixed-point analytic check well. |
| Fig 2 — partition schematics | yes (illustrative only) | N/A — schematic, not a numerical result. | None. |
| Fig 3 — TTN coarse-graining schematic | yes (illustrative only) | N/A | `methods/ttn.md` documents the `O(χ⁴ log N)` per-update cost; persona reads and accepts. |
| Fig 4 — `m_2`(N) Ising convergence + increment trick | yes | limit ✓ symm ✓ conv ✓ var ✓ cross ?  bench ✓ (range, not point) — `pauli-markov.md` Stage 2 is the increment construction; benchmark row is qualitative ("sharp peak at `h_c=1`"). Persona flags: no quantitative `m_2(h_c)` reference number to compare against. | Friction 1 — `magic-benchmarks.md` 1D-Ising row is qualitative only. |
| Fig 5 — Potts `m_1(h)` + finite-size collapse → `ν` | yes | limit ✓ symm ✓ (Z_3 two-site updates) conv ? var ✓ cross ✗ bench ✓ — `magic-benchmarks.md` reports the literature anchor `ν_Potts = 5/6` AND the methodology reference's `ν ≈ 0.844`. Persona happy with the *range*. Cross-method (ED on small `N`) not surfaced as automatic. | Friction 2 — cross-method-check is a separate skill the persona must invoke; no auto-pairing. |
| Fig 6 — spin-1 XXZ `m_1(D)` (plateau) + `L(ρ_AB)(D)` (extrema at transitions) | yes | limit ✓ (single-qutrit-product upper bound `(2/3) log 4 ≈ 0.92`) symm ✓ conv ?  var ✓ cross ✗ bench ✓ — `magic-benchmarks.md` says full-state `m_n` *misses* both Néel-Haldane and Haldane-large-`D` transitions; `L(ρ_AB)` recovers them. Persona happy that the failure mode is documented. | Friction 2 redux — persona has to manually drive the ED cross-check to confirm `D ≈ 0.97`. |
| Fig 7 — 1D Ising `L(ρ_AB)` peak at `h_c = 1`, log-`L` growth | yes | limit ✓ symm ✓ conv ?  var ?  cross ✗ bench ✓ — sign convention "negative extremum" explicitly documented in `magic-conventions.md` ("Long-range magic" / "L is not sign-definite") and `magic-benchmarks.md`. Persona gates pass after flagging. | None for sign; friction 1 (no quantitative number) persists. |
| Fig 8 — 2D Z_2 `m_1(h)`, `m_2(h)` densities (crossings) | yes | limit ?  symm ✓ conv ✓ (`χ → 60`) var ✓ cross ✓ (`magic` ↔ `Binder` is the canonical cross-diagnostic) bench ✓ — `magic-benchmarks.md` says `h_c ≃ 3.04` (3D-Ising universality), and `magic-conventions.md` documents Wegner-duality SRE preservation. Persona takes the Wegner-duality detour but verifies it is *cited* not asserted. | Friction 3 — limit check at 2D `h → 0` (deconfined / FM) and `h → ∞` (confined / PM) regimes is *not* listed as a default check in the magic skill or `transverse-field-ising` 2D row. Persona has to construct it. |
| Fig 9 — 3D-Ising `ν = 0.64 ± 0.05` from `m_1` collapse | yes | limit ✓ symm ✓ conv ✓ var ✓ cross ✓ (magic-vs-Binder at fixed χ=30) bench ✓ (`ν_3D ≃ 0.63` in literature range) — fully verified per the persona's gate. The harness's `physics/confinement` skill explicitly names "magic gives a robust crossing diagnostic at bond dimensions where the Binder cumulant fails" as the canonical cross-check; this is exactly what the persona wants. | None — best-verified figure in the paper for this harness. |
| Fig 10 — simulated experiment | yes (read) | limit N/A symm N/A conv ✓ (in `(N_M, N_S)`) var ✓ cross N/A bench N/A — out-of-scope to fully reproduce; `pauli-markov.md` "Experimental-protocol variant" + `(N_M, N_S)` knob coverage is documented but the persona does not gate this figure as core. | None for read-only; persona flags Fig 10 as out-of-core for verification. |
| Fig 11 — experimental error scan in `(N_M, N_S)` | yes (read) | Same as Fig 10 — out-of-core. | None. |
| Fig 12 — autocorrelation `τ_int(N)` | yes | limit N/A symm N/A conv ✓ var ✓ — `pauli-markov.md` Stage 3 is the convergence + variance diagnostic; `τ_int` is named explicitly. Persona happy. | None. |
| Fig 13 — `χ`-convergence of SRE | yes | conv ✓ — exactly what `methods/ttn.md` "Verification" row 1 + `pauli-markov.md` `χ`-convergence row prescribe. | None. |
| Fig 14 — Binder cumulant comparison at `χ = 30` (failure mode) | yes | cross ✓ — magic-vs-Binder is the canonical cross-diagnostic; documented in both `physics/confinement` and `cross-method-check`. Persona happy. | None. |
| Main result A — full-state `m_n` peak at 1D Ising criticality | yes | All six gates ✓ except cross-method (ED-on-small-N is the persona's responsibility to invoke). | Friction 2 (manual cross-method). |
| Main result B — full-state `m_n` *fails* on spin-1 XXZ; `L(ρ_AB)` recovers transitions | yes | All six gates ✓; the failure mode itself is the result, and the harness's `magic-benchmarks.md` documents it openly. | None. |
| Main result C — 1D Potts `ν ≈ 5/6` from `m_1` data collapse | yes | bench ✓ as range (analytic 5/6 + reported 0.844). | None — best handling of "range vs trophy number" in the harness for this paper. |
| Main result D — 2D Z_2 / 2D-Ising-via-duality magic crossing | yes | All six gates ✓ once the duality is spelled out. | Friction 4 — the duality is documented in `magic-conventions.md` (Wegner-duality preservation) but the *Z_2-gauge-theory side* is not driven by any model skill; the harness drives via `transverse-field-ising` 2D row + `physics/confinement`. Acceptable but the persona pauses to verify the dual sector (charge-free) is correctly argued for. |
| Main result E — 3D-Ising `ν = 0.64 ± 0.05` | yes | All six gates ✓; this is the verification champion. | None. |
| Main result F — magic-vs-Binder robustness at low χ | yes | All six gates ✓; `cross-method-check` exposes this as a named primitive. | None. |

## Verification audit

The Skeptical persona ran the AGENTS.md six-step gate against every figure and main result.

| Gate | Where the harness exposes it | Where the harness fell short |
|---|---|---|
| 1. Limit checks | `knowledge-base/limits.md` cited from `transverse-field-ising`, `spin-1-xxz`, `potts-clock` verification sections; `magic-benchmarks.md` "Single-qudit limit" anchors single-qudit analytics. | The 2D Ising / 2D Z_2-gauge limit (`h → 0` deconfined ferromagnet, `h → ∞` paramagnet) is *not* listed as a default verification step in either `transverse-field-ising` or `physics/magic`. The persona has to construct it from `limits.md`'s spin-model-limits section by analogy. |
| 2. Symmetry | Each model skill has an explicit "Symmetry" check (Z_2 for TFIM, Z_3 / Z_q for Potts/Clock, U(1) `S^z_total` for spin-1 XXZ). `magic-conventions.md` "Symmetry-restricted Pauli proposals" specifies two-site updates whenever the symmetry generator is `Π_i Z_i`. | Clean. The persona was satisfied that proposals preserve the sector. |
| 3. Convergence | `methods/dmrg.md` Verification row 1 (`E(D)` curve), `methods/ttn.md` Verification row 1, `methods/pauli-markov.md` "Variance bounds" + Stage 3 `(N_S → N_S/2)` reblocking, the `finite-size-scan` skill's auto-flag for asymptoting/critical/drifting. | Clean — the harness names every convergence axis the persona could ask about (`χ`, `N_S`, `N_M`, `L`, Trotter step in TEBD). |
| 4. Variance / internal consistency | `methods/dmrg.md` and `methods/ttn.md` Verification row 2 (`⟨H²⟩ − ⟨H⟩²`); `pauli-markov.md` "Variance bounds" content. | Clean in name. The persona notes that running variance diagnostics is documented but not packaged as a one-button sub-task. |
| 5. Cross-method | `cross-method-check` skill is a real, named primitive. Defaults table includes "Pauli-Markov sampling for magic ↔ Deterministic Pauli-basis MPS lift" and "Magic crossing ↔ Binder cumulant on the dual order parameter". | The persona's main complaint: there is no *automatic* small-`N` ED cross-check in the model skills' workflow. To run DMRG-vs-ED at `N = 12` the persona must explicitly invoke `cross-method-check` themselves. The model-skill verification section says "Cross-method validation (when feasible)" but does not auto-run it. |
| 6. Benchmark comparison | `magic-benchmarks.md` for the 1D Potts `ν`, the spin-1 XXZ transitions, the 2D Z_2 `h_c`, and the 3D-Ising `ν` is reported as a literature *range* with a methodology reference's reported number bracketed against the analytic / consensus value. This is exactly what the Skeptical persona wants. | The 1D-Ising row is *qualitative* only — "sharp peak at `h_c = 1`", "negative extremum". No `m_1(h_c)` numerical anchor. The persona flags this as a missing range. The companion paper 2401.16498 reports concrete values for ground-state Ising / XXZ that could anchor the row. |

## Discoverability

Routing was strong. The persona opened `AGENTS.md`, saw the `physics: magic, confinement` line in the installed-skills list, jumped straight to `tools/skills/problems/physics/magic/SKILL.md`, and from there followed the trail to `magic-conventions.md`, `magic-benchmarks.md`, `pauli-markov.md`, `ttn.md`, `transverse-field-ising`, `spin-1-xxz`, `potts-clock`, and `confinement`. Cross-references inside skills cite KB cards by relative path; no broken links.

A discoverability friction the persona noticed: the flat `tools/skills/<name>` aliases are not symlinked for the *physics* skills (no `tools/skills/magic`, `tools/skills/confinement` directories), only for the install-side `.claude/skills/` (gitignored). Skeptical reading source-of-truth folder layout for the first time finds the model and physics families slightly inconsistently surfaced — `tools/skills/heisenberg`, `tools/skills/j1-j2`, etc. exist as flat folders, but `tools/skills/magic` and `tools/skills/confinement` only exist nested under `tools/skills/problems/physics/`. AGENTS.md actually clarifies this ("Ion may expose direct `tools/skills/<name>` symlink aliases for installation. Edit the nested `tools/skills/problems/...` source directories"), so it is documented; just a minor stumble.

The verification primitives (`finite-size-scan`, `parameter-scan`, `scaling-fit`, `cross-method-check`, `run-stage`, `run-report`) are all flat folders under `tools/skills/` and well-described. The persona finds them quickly.

## Functionality (simulated)

Could the persona reach each figure with satisfactory verification? Mostly yes; the verification gates fire on the ones the persona cares about (Figs 4, 5, 6, 7, 8, 9, 14 plus all six main results). Three figures (10, 11, 12) sit on the experimental / autocorrelation periphery and the persona accepts them as documentation rather than gating them. Two figures (1, 2) are illustrative.

The harness routes the four core ground-state calculations cleanly:
- 1D TFIM `h`-scan → `transverse-field-ising` → branch table → `physics/magic` (with `L(ρ_AB)` partition).
- 1D 3-state Clock `h`-scan → `potts-clock` → `physics/magic` → `physics/criticality` → `scaling-fit`.
- 1D spin-1 XXZ `D`-scan → `spin-1-xxz` → `physics/magic` (with `L(ρ_AB)` because full-state misses transitions).
- 2D Z_2 / 2D Ising `h`-scan via Wegner duality → `transverse-field-ising` (2D branch row) → `physics/magic` → `physics/confinement` → `cross-method-check` (magic-vs-Binder).

All four routing chains work without the persona having to invent steps.

## Style genericness (Skeptical-specific)

The harness handled the Skeptical style well in three respects:

1. **Range-not-trophy benchmarks.** `magic-benchmarks.md` reports `ν_Potts = 5/6` (analytic) AND `ν ≈ 0.844` (methodology reference) AND `ν_3D ≃ 0.63` (literature) AND `ν = 0.64 ± 0.05` (methodology reference). This is exactly what the persona needs — they can see the method-extracted value sits inside the literature range.

2. **Cross-method as a named primitive.** `cross-method-check` exists, is referenced from AGENTS.md verification rule 5, and has a default-pair table including the magic-relevant pairs (magic-vs-Binder, Markov-chain vs deterministic Pauli-basis lift). Persona reads it and feels seen.

3. **Frontier flags + `arxiv-search` routing.** Both `physics/magic` and `spin-1-xxz` have explicit "Frontier flag" sections that route to `arxiv-search` for literature framing. Persona approves: when results are uncertain, the harness reaches for the literature *range* rather than overclaiming.

Where the genericness frayed slightly:

- The default `χ = 30` for the 2D Ising magic-crossing demonstration (Fig 9) is *the point* of the paper (low-χ robustness), but the harness's `methods/ttn.md` knob row says "30–60 for entry-level magic-density work" without flagging that this *is* the headline figure value. A Skeptical reading the knob first might bump `χ` and miss the point. The branch-table redirect to `physics/confinement` does eventually surface the magic-vs-Binder claim, but the redirection is a layer deep.

- Cross-method-check is named but not auto-invoked. AGENTS.md says "default verification, in priority order: ... 5. Cross-method validation (when feasible)" — Skeptical reads this as "feasible at small `N` for spin-chain DMRG" and expects an automatic small-`N` ED cross-check in the model-skill verification block. It is in the *list* (`transverse-field-ising` Verification row 5), but it is not run by default — the persona has to invoke it.

## Pushback test

**Persona pushback (turn 7, after the harness reports the Fig 9 result `ν = 0.64 ± 0.05` from a `χ = 30` calculation):**

> "Are you sure? `χ = 30` for a 2D critical point is suspiciously low. The Binder cumulant fails at the same `χ` according to the methodology reference — how do I know magic isn't fooling me in the *opposite* direction? I want to see the same scan at `χ = 60` to confirm the crossing doesn't drift."

**Harness response (per AGENTS.md "Pushback and reconsideration", how the agent should answer):**

1. Restate the prior reasoning: "The Fig 9 result is by-design at `χ = 30` because that *is* the methodology reference's headline claim — magic resolves the transition where the Binder cumulant cannot. The bond-dim is *fixed low* on purpose."
2. Take the input seriously: "If the crossing drifts at `χ = 60`, the claim is weakened — that is a fair check. The methodology reference reports `χ = 60` numbers in Fig 8 (the densities, not the collapse), so a `χ`-comparison is a real follow-up."
3. State the outcome of reconsideration: "I'll re-run at `χ = 60` and compare; if the crossing is stable, the claim survives, and the persona's intuition is satisfied. If it drifts, we have a real critical-bond-dim story — that itself is a result. Either way, this is a `cross-method-check` follow-up over `χ`, not a redo of the original calculation. Routing through `parameter-scan` over `χ`."

This is the correct response shape per AGENTS.md: no capitulation, no defense. The harness restates, reconsiders, offers a concrete follow-up. The persona ratifies.

What the harness *should not* have done (and per the skill text, would not):
- "You're right, sorry, let me redo at higher `χ`." → erodes calibrated judgment; the original `χ = 30` was correct.
- "No, `χ = 30` is fine because the methodology reference said so." → argues without engaging the user's point.

The pushback test passes as a thought-experiment audit of the AGENTS.md "Pushback and reconsideration" pattern. The persona does not actually run `χ = 60` (no compute), but the *response shape* is correct.

## Friction points

1. **`magic-benchmarks.md` 1D-Ising row is qualitative only.** No `m_1(h_c)` or `L(ρ_AB)(h_c)` numerical anchor. Skeptical wants a literature-range number to compare against. The methodology reference (2305.18541) and companion (2401.16498) report numerical values that could populate this row. *Friction 1.*

2. **Cross-method validation is named but not auto-invoked.** The model-skill Verification sections list "Cross-method validation (when feasible)" as item 5, but the workflow does not auto-pair the primary calculation with a small-`N` ED at `N = 12-16`. Skeptical has to explicitly invoke `cross-method-check`. AGENTS.md priority-ordered list suggests it should be standard, not opt-in. *Friction 2.*

3. **2D limit checks are not surfaced as defaults.** The 2D Ising `h → 0` and `h → ∞` limits (deconfined FM at small `h`; PM at large `h`, with `m_1 → 0` analytically because both eigenstates are stabilizer at the limits) are not listed in either `transverse-field-ising` 2D row or `physics/magic` Verification. Skeptical has to construct them by analogy from the 1D row in `limits.md`. *Friction 3.*

4. **Wegner-duality is well-cited but the gauge-side calculation has no skill home.** The harness drives the 2D Z_2 gauge calculation via `transverse-field-ising` (2D dual) per `magic-conventions.md` Wegner-preservation. There is no `Z_2-gauge` model skill. This is *correct* (the harness routes via the simpler dual), but a Skeptical first-time reader pauses to verify the "charge-free dual sector" argument is sound. The skill could state explicitly which sector of the 2D Ising corresponds to the charge-free Z_2 gauge sector. *Friction 4 (minor).*

5. **`physics/magic` Frontier flag triggers `arxiv-search` for "regimes not yet in the established list" but does not list which regimes ARE established.** The persona has to read `magic-benchmarks.md` to discover the four established model rows. A one-line "established: 1D TFIM, 1D Potts, 1D spin-1 XXZ, 2D Z_2 ↔ 2D Ising" in the Frontier flag would help. *Friction 5 (minor).*

## Suggestions

1. **Populate the 1D-Ising row of `magic-benchmarks.md` with numerical ranges.** From the methodology reference (2305.18541) Fig 4 and Fig 7, numerical `m_2(h_c)` and `L(ρ_AB)(h_c)` values are extractable for sizes the persona would re-run. Reporting them as a range with size-trend (e.g., "`L = 32`: `L(ρ_AB)(h_c)` is a negative minimum near `−0.05`, with `O(log L)` magnitude growth") gives Skeptical a quantitative anchor.

2. **Auto-pair small-`N` ED cross-check inside model-skill workflows when `N ≤ 16` is feasible.** Not as a separate user-invoked skill but as a default emission from the model skill's verification step. The cross-method-check primitive then runs as a sub-call of the model skill. AGENTS.md's "verification practice" already lists this as priority 5; it deserves to be auto-fired for small-`N` problems.

3. **Add 2D limit-check rows to the `transverse-field-ising` and `magic` skills.** "At `h → 0`, the 2D Ising ground state is the all-aligned ferromagnet (a stabilizer); `m_n → 0`. At `h → ∞`, the ground state is the all-`|+⟩`-aligned paramagnet (also a stabilizer); `m_n → 0`. Both limits constrain the `m_n(h)` curve to vanish at the endpoints; the *crossing* lives between them."

4. **Extend `magic-conventions.md` Wegner-duality section with the explicit sector statement.** "The 2D Z_2 lattice gauge ground state in the charge-free sector maps to the 2D Ising ground state in the trivial Z_2 sector." This is a one-line addition that closes the loop for a Skeptical reader.

5. **Add an "Established benchmark models" pointer to `physics/magic` Frontier flag.** A one-line list of which models / regimes have a benchmark row in `magic-benchmarks.md`, so the agent knows when to gate against the KB and when to invoke `arxiv-search`.

6. **Document low-`χ` claims explicitly.** The Fig 9 result is *intentionally* at `χ = 30` because the headline is robustness-at-low-χ. Both `physics/magic` and `physics/confinement` skills could spell this out — "The 2D `m_1`-crossing demonstration uses fixed `χ = 30` to test bond-dim robustness; bumping `χ` is a follow-up cross-check, not a correction."
