# Harness Content Fill — Design

Date: 2026-04-30
Branch: codex/wheel

## Goal

The harness has 13 problem skills (8 models, 5 physics) and a near-empty `knowledge-base/`. Skills tell the agent *what to consider* but not enough to actually carry an entry/medium-level problem from intake to a verified result. KB has no data to back verification, conventions, or method-specific reference. Two-part fill to make the harness usable: tighten skills into procedural workflows, populate KB with the data they cite.

## Principle

- **Skill** = reusable generic workflow, decision rules, verification pattern. Parameterized. No hardcoded numbers, no code skeletons, no canonical recipes.
- **KB** = data: reference numbers, citations, conventions, limits, symmetry tables, method-specific code shapes.
- A skill cites KB for any value, convention, or method-specific shape. Updating KB never breaks a skill.

## Scope of change

### A. Tighten the 13 problem skills

For each skill in `tools/skills/problems/{models,physics}/*/SKILL.md`:

- **Diagnose** — questions to fix the problem (lattice, filling, observable, accuracy goal).
- **Workflow** — generic phases: setup → first run → convergence sweep → verification → branch.
- **Method recommendations** — regime → method. No code, no hardcoded knobs. Cites the KB method card.
- **Branch table** — condition → next skill / next method.
- **Verification** — phrased generically. Cites `knowledge-base/benchmark-numbers.md#<key>`, `knowledge-base/limits.md`, `knowledge-base/symmetry-cheatsheet.md` as relevant.

Most existing skills are close to this shape; the change is a tightening pass, not a rewrite. Embedded method-setup details migrate to KB method cards.

### B. Populate `knowledge-base/`

| File | Holds |
|---|---|
| `conventions.md` | Sign and normalization defaults; common alternatives noted. |
| `benchmark-numbers.md` | Reference E/N, gaps, order parameters, with citations. Tightly-constrained values single-valued; debated values given as a range with notes. |
| `limits.md` | Exact reductions and mappings: U=0 → free fermions, U→∞ + finite holes → t-J, XXZ Δ=1 = Heisenberg, half-filled bipartite Hubbard at U≫t, large-S → semiclassical, J₂=0 → Heisenberg, etc. |
| `symmetry-cheatsheet.md` | Conserved quantities and lattice generators per common lattice (chain, square, triangular, kagome, pyrochlore). |
| `methods/{dmrg,ed,vmc,tebd,qmc,dmft,trg}.md` | Strictly factual cards: notation, canonical code shape, knobs, pitfalls, citations. |
| `2302.04919-variational-benchmarks.md` | Existing paper notes — stays. |

Not all method cards need to land in this pass. Start with `dmrg`, `ed`, `vmc` (most-cited by current skills). Others added when a skill begins citing them.

## Behavior under the new structure

User brings a concrete entry/medium-level problem. The skill activates on metadata, diagnoses, recommends a method, fetches code shape from the relevant method card, runs, verifies against KB benchmark numbers, reports discrepancy. Decisions surfaced only when there's a real branch (method choice when methods disagree, or interpretation when the problem is near a frontier).

Frontier problems (kagome ground state, contested phase diagrams) verify against literature *ranges* with honest uncertainty rather than claiming a single canonical match.

## Out of scope

- **Worked-example archive.** Tutorial-shaped, redundant with `benchmark-numbers.md`.
- **Skill template / authoring spec.** Process artifact, not content.
- **Cold-start triage skill.** Skills already activate on metadata; no separate entry layer needed.
- **New problem skills.** Coverage band is entry/medium across the existing 13. New skills (real-time dynamics, finite-T, open systems, topology beyond spin liquids) added when real problems demand them.
