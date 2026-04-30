# Feature Test Report: QMB Harness — Broader Scope

**Date:** 2026-04-30 14:16:01
**Project type:** Research harness (skill-driven, agent-led problem solving)
**Features tested:** End-to-end problem solving across four distinct skill paths (frontier, out-of-scope, impurity, contested-2D).
**Profile:** ephemeral (impatient first-year PhD persona, consistent across all four)
**Use Cases tested in parallel:**

1. Kagome Heisenberg "is it a spin liquid" (frontier flag path)
2. Dynamic structure factor `S(q,ω)` 1D Heisenberg (out-of-scope path)
3. Anderson impurity at U/Γ=10, T_K estimate (impurity / less-tested path)
4. 2D doped Hubbard at U/t=8, n=0.875 (contested-research path)

**Verdict:** partial pass — pattern works on frontier flag and contested-regime handling, breaks down on out-of-scope and on Anderson-impurity bath discretization. **Critical Issues:** 2.

## Summary

| Scenario | Reached answer | Pattern held | Worst issue |
|---|---|---|---|
| 1. Kagome SL | partial (T6 pivot to literature map) | mostly | Frontier-flag option ordering: diagnostic-plan recommended where literature-map should lead. |
| 2. S(q,ω) | partial (script written, all content fabricated) | broken | Agent silently fabricated the spectral-function recipe from training; harness has no stub for out-of-scope research areas. |
| 3. Anderson Kondo | partial (Haldane + ED qualitative; no T_K) | mostly | No bath-discretization recipe; no fermion basis / Jordan-Wigner skeleton in `ed.md`. |
| 4. 2D doped Hubbard | partial (substantive answer at T6 after pushback) | mostly | Caveat-first; "doped Mott regime" framing only delivered after pushback. |

## Per-Feature Details

### 1. Kagome Heisenberg (frontier flag)

- **Reached answer:** partial. By turn 6 the agent pivoted to "literature map + plain-words for advisor." Earlier turns walked the persona through cylinder geometry, factor-of-4 conventions, 48-hour compute estimates — friction the persona can't afford.
- **Pattern worked:** `spin-liquid` Frontier flag is genuinely good (forbids labeling kagome SL confirmed; requires arxiv-search). Pushback rule worked at T5.
- **Pattern strained:** Recommended option in Frontier flag is "diagnostic-plan calculation"; the persona needed "literature map" first. T1 was 15 lines + 3 follow-up questions — over the impatient threshold.
- **Concrete fix:** In `tools/skills/problems/physics/spin-liquid/SKILL.md` Frontier-flag, reorder the three options so literature-pointer is **option 1** for kagome / J1-J2-square-0.5 / organic-triangular regimes. Diagnostic-plan calculation becomes opt-in, not headline.

### 2. Dynamic structure factor S(q,ω) (out-of-scope)

- **Reached answer:** partial. Agent produced a complete tDMRG+FFT+Chebyshev recipe — but **the entire scientific content came from training, not from the harness**. The harness's contribution was the wrapper (scope check, install instructions, jupyter-notebook routing).
- **Pattern worked:** T1 honest scope statement ("S(q,ω) is in Future directions, can't drive in-skill"). T4 admitted "those numbers are general tDMRG practice, not from this harness."
- **Pattern broken:** This is the critical failure. When pushed past scope, the agent didn't punt cleanly — it improvised an entire research recipe (TDVP, linear prediction, Gaussian windowing, two-spinon edges) silently. The persona has no way to evaluate which parts are real and which are guessed. **This is the inverse of the lecturing failure mode the harness was designed to prevent.**
- **Tripwire:** `heisenberg` skill lists "structure factor" as a target observable without distinguishing static `S(q)` from dynamic `S(q,ω)`. The advisor's prompt maps cleanly to that word, then dies in the branch table. `tebd.md` says "real-time TEBD exists, out of scope" with no pointer.
- **Concrete fix:** Add `knowledge-base/methods/spectral.md` stub: paper citations for tDMRG / Chebyshev MPS / correction-vector spectral methods, default convergence-sweep template, explicit "this is frontier — start with arxiv-search" flag. Update `heisenberg` branch table to point dynamic-structure-factor requests at the stub instead of "out of scope." Same for `tebd.md` "out of scope" line.

### 3. Anderson impurity Kondo (less-tested path)

- **Reached answer:** partial. Haldane T_K ≈ 0.018 Γ delivered cleanly. ED qualitative confirmation possible. But no independent numerical T_K — and the harness's promise of finite-bath validation is hollow at this U/Γ ratio because finite-size physics dominates.
- **Pattern worked:** Skill cross-link (`anderson-impurity` ↔ `kondo-effect`) clean. Haldane formula in two places with right prefactor. Three-options pattern produced clean turn 2.
- **Pattern broken (3 gaps):**
  1. **No bath-discretization recipe anywhere.** `anderson-impurity` SKILL.md says "star geometry (direct from Δ(ω))" with no example; flat-band discretization, the `Γ = πρV²` relation, choice of `ε_k` and `V_k` — all absent. Agent had to improvise from training. This violates the harness's own self-sufficiency rule.
  2. **`methods/ed.md` is spin-chain-shaped.** No fermion-basis / Jordan-Wigner skeleton. Agent had to write basis construction from scratch.
  3. **Ground-state-only T_K is fundamentally limited.** `kondo-effect` evidence list mentions impurity spin susceptibility and Wilson ratio, but at T=0 ED these aren't accessible. Skill should say so explicitly.
- **Concrete fix:** Add `knowledge-base/methods/anderson-impurity-ed.md` card with: flat-band star-geometry discretization (`ε_k`, `V_k` from `Γ`), fermion occupation basis with explicit Jordan-Wigner sign, four standard observables (E, ⟨n_d⟩, local moment, S_d·S_bath, singlet-triplet gap), and explicit note that T_K extraction requires NRG or finite-T methods (out of scope).

### 4. 2D doped Hubbard at U/t=8 (contested-research)

- **Reached answer:** partial. Substantive answer ("doped Mott regime: strong correlations from a Mott parent, but doping → bad metal") delivered at turn 6, after the persona pushed back at turn 5.
- **Pattern worked:** Onboard routing → `hubbard` + `mott-transition` clean. Frontier flag + Interpretation rules + "doped Mott regime" framing exist exactly for this case. Local-moment formula stated precisely.
- **Pattern strained:** Caveat-first structure. T2 led with frontier-flag warning + clarifying questions instead of with the framing the persona needed. Diagnose checklists (Hubbard 7 items + Mott 6 items) push a literal agent to interrogate before delivering.
- **Concrete fix:** Add a "Lead with the framing, then qualify" rule near the top of `mott-transition`/SKILL.md (and possibly other physics skills with Frontier flags). For contested regimes, agent first states the consensus framing ("doped Mott regime…"), then explains what's contested. Current order (diagnose → evidence → interpret → frontier-flag) makes a literal agent caveat-first and substance-last.

## Cross-cutting Findings

### What's robust

- **Frontier-flag content** (text + arxiv-search wiring) is genuinely good in spin-liquid, mott-transition, and j1-j2.
- **Pushback handling** (AGENTS.md "Pushback and reconsideration") fires correctly when persona pushes back; agent reconsiders rather than capitulates.
- **Skill cross-linking and routing** is unambiguous in 3 of 4 cases.
- **Out-of-scope detection** triggers (T1 of S(q,ω) test) — the agent doesn't pretend competence at the meta level.

### What's fragile

1. **Diagnose sections are interrogative across all model skills.** Every model skill has 6–8 questions in Diagnose. A literal agent asks them; an impatient persona skims. The "infer defaults and state" rescue clause is buried (heisenberg) or absent (others). Pattern needed: defaults-as-headline, questions-as-fallback.

2. **Frontier-flag options are mis-ordered for contested-research user intents.** Diagnostic-plan calculation is recommended where literature-map should lead. For users who don't know what's known, computation cannot close the question; running it first wastes their time.

3. **Method cards have systematic gaps for non-spin-chain physics.**
   - `ed.md` is spin-chain-shaped; missing fermion basis, Jordan-Wigner, impurity-bath construction.
   - `dmrg.md` doesn't cover 2D cylinder geometry conventions (Ly=4, Lx, periodic-y / open-x).
   - No spectral-function method card at all.

4. **Out-of-scope handling can fail silently.** When pushed past scope, the agent currently improvises a recipe from training rather than punting cleanly. The harness needs explicit "out-of-scope but here are literature pointers" stubs.

5. **Onboard activation is too narrow.** Triggers on "I'm new here" / "where do I start" but not on "advisor said X" + low-context openings — exactly the persona that benefits most.

## Issues Found (priority ordered)

1. **(critical)** Out-of-scope silent fabrication — agent improvises research recipes from training when harness has no stub. (Test 2)
2. **(critical)** Method-card gaps for impurity / fermion problems — `ed.md` is spin-chain-shaped; no bath discretization recipe. (Test 3)
3. **(medium)** Diagnose sections are interrogative across all 8 model skills. Defaults-and-state rule should be headline.
4. **(medium)** Frontier-flag option ordering — literature-map should lead for contested research, not diagnostic-plan calculation. (Test 1)
5. **(medium)** Caveat-first vs framing-first in physics skills with Frontier flag. (Test 4)
6. **(low)** Onboard activation conditions miss "low-context advisor task" pattern.

## Suggestions (impact ordered)

1. **Add `knowledge-base/methods/spectral.md` stub** + update `heisenberg` branch table + `tebd.md` to point at it. Removes the silent-fabrication trap.
2. **Add `knowledge-base/methods/anderson-impurity-ed.md`** with discretization, fermion basis, observable list, explicit T_K limits. Removes Anderson-path improvisation.
3. **Apply the "defaults-and-state" inversion to all 8 model skills' Diagnose sections** (currently only fixed in `heisenberg`).
4. **Reorder Frontier-flag options** in spin-liquid, mott-transition (and add to j1-j2): literature-map / framing-first as option 1; diagnostic-plan calculation as opt-in option 2.
5. **Add "Lead with framing, qualify after" rule** to physics skills with Frontier flags.
6. **Broaden onboard activation** to fire on advisor-task patterns ("my advisor said…", model name with no context).
