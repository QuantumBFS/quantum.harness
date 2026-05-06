# Phase 3 Persona Validation — Pragmatist

**Date:** 2026-05-06
**Profile:** docs/agent-profiles/harness-magic-paper-reproduction-pragmatist.md
**Target:** QMB harness — magic-paper reproduction (arXiv 2305.18541, 2401.16498)
**Verdict:** partial
**Critical issues:** 3

## Summary

The Pragmatist drives forward through the recommended-default path and reaches the *physics*-result figures (Fig. 5–7 1D criticality, Fig. 8–9 2D crossing) within their hour, plus the auto-generated convergence proxy that maps to Fig. 13. They never look at alternatives, never read method cards, and never click anything but the first option. The harness's act-first defaults serve them well for the canonical 1D/2D physics figures but leave the methodology figures (Fig. 1 single-qudit, Fig. 2–3 schematics, Fig. 10–12 experimental + autocorrelation) un-reached because no skill *recommends* them as the front-of-house result. The Pragmatist hits the time-box at ~55 min, ratifies whatever last result the harness shows, and stops.

## Coverage

Reading the validation paper, the 14 figures split as: methodology / setup (Fig. 1–3, 10–13), 1D physics (Fig. 4–7), 2D physics (Fig. 8–9, 14), and companion-paper Pauli-MPS (Fig. 1–3 + S1–S7 of 2401.16498). Six "main scientific results" map to: (R1) Fig. 4 increment-trick efficient `m_2`, (R2) Fig. 5 Potts critical exponent collapse, (R3) Fig. 6 spin-1 XXZ `L(ρ_AB)` two transitions, (R4) Fig. 7 1D Ising `L(ρ_AB)` peak/log-`L` growth, (R5) Fig. 8–9 2D `Z_2` gauge magic crossing + `ν` collapse, (R6) Fig. 14 Binder vs magic robustness.

| Fig / main result | Reached? | Friction |
|---|---|---|
| Fig 1 — single-qudit `m_n(θ)` | no | Verification anchor; never auto-rendered for the user. KB lists it as a check, no skill turns it into a plot. |
| Fig 2 — partition schematics | no | Methodology; persona doesn't ask. |
| Fig 3 — TTN sampling schematic | no | Methodology; persona doesn't ask. |
| Fig 4 — `m_2` density (increment-trick) | partial | Reached as `m_2(h)` plot; whether the "increment construction" actually fires is buried in pauli-markov stage 2. Persona ratifies the "auto-converged" headline. |
| Fig 5 — Potts criticality (R2) | yes | Skill `potts-clock` → magic → `m_1(h)` + criticality FSS data collapse. Recommended path runs cleanly. |
| Fig 6 — spin-1 XXZ `L(ρ_AB)` (R3) | yes | Skill `spin-1-xxz` branch table makes `L(ρ_AB)` the *default* — well-routed. |
| Fig 7 — 1D Ising `L(ρ_AB)` (R4) | yes | First problem the persona asks for ("magic in 1D Ising") → TFIM → magic → `L(ρ_AB)`. Direct hit. |
| Fig 8–9 — 2D `Z_2` magic crossing (R5) | yes | TFIM 2D row + Wegner duality + `physics/confinement` recommended path → magic crossing + `ν` collapse. Persona accepts. |
| Fig 10–11 — experimental finite-shot SREs | no | Experimental-protocol variant lives in pauli-markov method card; no skill or default surfaces it. Persona never asks "what about an experiment?" |
| Fig 12 — autocorrelation `τ_int(N)` | no | Internal diagnostic in the pauli-markov stage 3; the harness UI norm is to report it only if the user asks. Persona never asks. |
| Fig 13 — `χ`-convergence | partial | Auto-generated convergence plot (per AGENTS.md "convergence plot with every calculation") is the persona-facing analogue. Strictly speaking it's `E(χ)`, not `m_n(χ)`; the persona is unlikely to notice the substitution. |
| Fig 14 — Binder vs magic at fixed `χ` | no | Lives behind the `confinement` skill's *Cross-checks* table. Never auto-emitted. |
| Companion 2401.16498 Fig 1–3 — Pauli-MPS deterministic lift | no | Method-card variant only. Routing: pauli-markov "Deterministic Pauli-basis lift" section. No skill recommends this path; the Pragmatist would only see it if a skill said "this is a different way and here it is." |
| Companion S3–S5 — XXZ derivatives, additive Bell magic | no | Bell magic / stabilizer nullity are listed in pauli-markov as "deterministic Pauli-basis lift" outputs. Never surfaced by default. |
| (R1) increment-trick scaling | partial | Same as Fig 4 — runs internally, not headlined. |
| (R6) magic-vs-Binder robustness | no | `confinement` skill *Cross-checks* row, not a default deliverable. |

**Tally for the Pragmatist:** 4 figures reached cleanly (Fig 5, 6, 7, 8–9 → results R2, R3, R4, R5), 2 partial (Fig 4 / R1 increment-trick, Fig 13 χ-convergence proxy), 8 not reached. Of 6 main results: 4 reached, 1 partial, 1 not reached.

## Discoverability

**First prompt hits.** The persona types something like *"I want to compute many-body magic on the 1D Ising chain"*. Skill descriptions are well-keyed:

- `magic` description: *"...how non-Clifford is this state? question across spin / fermion / gauge models"* — direct match.
- `transverse-field-ising` description: *"...transverse-field Ising ground-state problem... criticality at the field-coupling balance"* — direct match.

The harness routes via `solve` → `transverse-field-ising` → branch-table row "Question is about magic" → `physics/magic`. This is one of the cleanest routings in the harness; the Pragmatist would not notice they're being routed at all.

**Routing into the secondary models** (Potts/Clock, spin-1 XXZ): less obvious. If the persona reads the paper abstract and types *"reproduce the Potts magic figure"*, the Pragmatist would ratify whatever the harness does. The `magic` skill *Model hooks* line lists `potts-clock` and `spin-1-xxz` explicitly — well-mapped. The harness can drive the loop without re-asking.

**Routing into 2D `Z_2` gauge theory**: cleanest path of all. `transverse-field-ising` 2D row says "compute on the dual via Wegner duality, hand off to physics/confinement". A Pragmatist who types *"how about the 2D gauge theory result?"* gets routed through duality without needing to understand it; the report's one-line reasoning ("Computed via dual 2D Ising; Wegner duality preserves SREs") is exactly the absorption pattern AGENTS.md targets.

**Failure modes:**

- The Pragmatist would never type *"reproduce Fig. 1"* or *"reproduce the autocorrelation Fig. 12"* — those require methodological framing the Pragmatist does not have.
- The Pauli-MPS deterministic lift (companion paper) is buried as a runtime variant inside `pauli-markov.md` rather than fronted as a distinct workflow. There is no skill description that says *"use Bell magic as a diagnostic"*.

## Functionality (simulated)

The Pragmatist could, with this harness, set up:

1. **1D TFIM `L(ρ_AB)(h)` peak** — via `transverse-field-ising` + `magic` + DMRG ground state + Pauli-Markov sampling on disjoint A=`{1..L/4}`, B=`{L/2+1..3L/4}`. Defaults are explicit in `magic-conventions.md` "Partition modes". Setup is routine.

2. **1D Potts `m_1(h)` collapse** — `potts-clock` + `magic` + DMRG/TTN at `q=3` + two-site Pauli updates (the skill flags that two-site is required for `Z_3`, the persona doesn't read but the default fires). Critical exponent `ν_Potts = 5/6` is in `magic-benchmarks.md` as the limit anchor — the harness's verification step would flag a mismatched extracted `ν` automatically.

3. **Spin-1 XXZ `L(ρ_AB)` two transitions** — `spin-1-xxz` + `magic` defaulting straight to `L(ρ_AB)` because the skill explicitly says full-state magic *misses* both transitions. This is exactly the kind of routing the Pragmatist needs.

4. **2D `Z_2` confinement-deconfinement crossing** — `transverse-field-ising` 2D + Wegner duality (cited from `magic-conventions.md`) + `confinement` cross-check + magic crossing at `h_c ≈ 3.04`. The reference value is in `magic-benchmarks.md` for the harness to compare against.

**Where the Pragmatist would stick (without running real compute):**

- **At the `χ` budget.** The 2D `Z_2` result requires `χ ~ 30–60` for the magic crossing (`magic-benchmarks.md`: "even at `χ = 30`, magic extracts `ν`"). Whether the harness's installed Julia + ITensors stack converges on a 1-hour budget is the live question; the Pragmatist would simply ratify whatever number prints. The harness's auto-generated convergence plot would catch a non-convergent run.

- **At the increment-trick stage (Stage 2 of pauli-markov).** This is multi-stage: stages 1 at `N`, `N/2`, `N/4`, then combination. The harness's `run-stage` + `slurm-grid` primitives are designed for this but the Pragmatist would not invoke them by name. They'd type "run it" and trust the skill orchestration. The `pauli-markov` card declares the stage shape but does not have a tested orchestration recipe end-to-end visible to a persona this early in their journey.

- **At the partition spec for 2D.** The 1D default `A = {1..L/4}, B = {L/2+1..3L/4}` is explicit; the 2D analogue is not pinned down in the conventions card ("replace by lattice analogues for 2D"). A Pragmatist running the 2D-confinement workflow may sit on a default that doesn't actually exist, and the harness would have to invent one mid-run.

## Style genericness (Pragmatist-specific)

The harness's act-first + "(Recommended)" labelling is **strongly aligned** with the Pragmatist style:

- Every fork the persona hits (model choice, partition, estimator, `n=1` vs `n=2`, finite-size scan vs single point) has a recommended default that the skill picks confidently. The Pragmatist clicks; forward motion guaranteed.
- The ≤3-line report norm matches the "what's the result?" pattern. The persona reads the headline, doesn't follow up.
- The auto-generated convergence plot doubles as Fig. 13 in this paper — the persona absorbs the verification without ever asking for it.

**Where the Pragmatist style exposes the harness's blind spots:**

- The Pragmatist *will not push back* when something looks wrong. If `L(ρ_AB)` comes out positive at the Ising critical point, contradicting the benchmark "negative extremum", the Pragmatist will ratify and stop. The harness's verification step against `magic-benchmarks.md` is the only safety net — and it works only if the harness actually runs that comparison and reports a verification flag, not a verbose checklist.
- The Pragmatist *will not invoke `arxiv-search` voluntarily*. The frontier-flag protocol relies on the agent — not the user — invoking it. For magic in 2D `Z_2`, the harness should auto-call arxiv-search before interpreting; if that step is silently skipped, the persona ends up with a number but no anchoring.
- The Pragmatist *will not ask for the deterministic Pauli-basis lift* or *Bell magic*. These exist as variants in the method card but never surface. For the *companion paper's* main result (Fig 2: SRE derivatives across XXZ via Pauli-MPS), the Pragmatist has zero path. The harness has no skill description containing the phrase "Pauli-MPS" or "Bell magic" as a front-door entry.

**Forks where the harness asks too many questions for this style:** none observed in the recommended path. The skill diagnose sections all use *"Going with: [defaults]. Override any, or pick: [alternatives]"* — propose-and-ratify, not ask. The Pragmatist's "just do it" instinct is met without trigger.

## Friction points

1. **Companion-paper coverage is structurally absent.** Pauli-MPS deterministic lift, Bell magic, stabilizer nullity exist only as bullet points inside `pauli-markov.md` "Deterministic Pauli-basis lift (variant)" section. No skill recommends them. The persona who wants "the 2024 companion result" gets nothing without methodological re-framing they can't do.

2. **Methodology figures (Fig 1, 10–12, 14) have no surfacing path.** They're either single-site verification anchors (Fig 1), experimental-protocol mode (Fig 10–11), internal diagnostics (Fig 12), or cross-check robustness claims (Fig 14). The harness's UI norm (`Never dump checklists, verification details... unless the user explicitly asks`) is well-tuned for a Pragmatist *receiving* a result, but the Pragmatist will never explicitly ask for these. Result: 4–5 of 14 figures unreachable for this persona by design.

3. **Increment-trick (Stage 2 of pauli-markov) is described in the method card but not orchestrated end-to-end visibly.** A Pragmatist running an `m_2` calculation in a volume-law regime would expect "the magic just works" and would trust whatever the harness does. The card declares stages 0–3, the `run-stage` / `slurm-grid` primitives exist, but there is no skill-level integration that says "for `m_2`, the harness automatically does increment + recursion". A Pragmatist would conflate `m_2(h)` (Fig 4) with what they actually got, which may be a single-`N` `M_2` estimate in a regime where that is exponentially-cost-prohibitive.

4. **2D partition spec is under-specified in the conventions.** `magic-conventions.md` "Partition modes" pins 1D defaults; 2D says "replace by lattice analogues". The harness would have to make this up at runtime. For Fig 8–9 reproduction this is a real gap.

5. **Pragmatist does not exercise the `arxiv-search` frontier-flag protocol.** The harness's safety against frontier-regime over-claims relies on the *agent* invoking arxiv-search; this is correctly designed as agent-driven, but it is also the most fragile part of the verification chain because it depends on a single conditional that the persona never tests.

6. **Convergence plot vs Fig 13 mapping is implicit.** The auto-saved plot is `E(χ)`; Fig 13 is `m_n(χ)`. A Pragmatist reading the headline "converged ✓" would not realize what was checked. Both are valid χ-convergence diagnostics; harness should make this substitution transparent.

## Suggestions

To raise Pragmatist coverage from 4/14 figures cleanly to ~8/14:

- **Add a `magic-experimental-shots` row in `physics/magic` Estimator-choice table that auto-fires** when the persona's prompt contains "experimental", "shot", "measurement", "noise", "finite-N_M". Fig 10–11 then become reachable by a Pragmatist who hears about an experiment from a paper abstract. (Currently the row exists; surfacing language could be more keyword-permissive.)

- **Front-of-house Pauli-MPS / Bell magic.** Either a new physics skill (`magic-bell`) or a prominent branch in `physics/magic` Estimator-choice table. The Pragmatist needs a description that triggers on "Bell magic", "stabilizer nullity", "MPS-Pauli". Right now those phrases only appear in the method-card variant section.

- **Auto-emit Fig 13 as an `m_n(χ)` convergence plot whenever the magic skill runs**, not just `E(χ)`. The cost is one extra computation per `χ` value, already paid for by the bond-dim sweep.

- **Pin a 2D partition spec in `magic-conventions.md`** with explicit shapes (e.g., `A` = top-left `L/4 × L/4` block, `B` = bottom-right `L/4 × L/4` block, separation ≥ correlation length). Currently "replace by lattice analogues" leaves a hole.

- **Add an explicit increment-trick orchestration in the magic skill workflow**, citing pauli-markov stages 0–2 by name and showing the volume-law detection that triggers the switch. The Pragmatist won't read it, but a verification flag — "increment-trick auto-engaged because `M_2(N) ~ N`" — would land in the report and let the Pragmatist absorb that judgment without reading the method card.

- **Strengthen the verification fail-loud path for the benchmark comparison.** If `L(ρ_AB)` extremum sign disagrees with `magic-benchmarks.md`, the report needs to flag-and-stop, not flag-and-continue. The Pragmatist's tendency to ratify wrong-looking answers makes this the highest-value safety net.

- **Have the agent auto-invoke `arxiv-search` for any 2D-gauge magic computation**, not just on user request. The frontier flag is currently a strong norm but a soft trigger; for the Pragmatist style, soft is not enough.

- **Add a "what figures of paper X does this reproduce?" surfacer in the run-report skill.** When the user (Pragmatist) types "reproduce paper 2305.18541", the harness has all the pieces to plan an end-to-end multi-stage run that hits Fig 5, 6, 7, 8, 9 in sequence. Currently each figure is a separate solve-loop iteration; a paper-level orchestrator would let the Pragmatist clear most of the paper in one ratification.
