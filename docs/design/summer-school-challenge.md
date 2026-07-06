# `/challenge` — Product Design

A new harness skill that carries a Harnessing Quantum 2026 participant from a finished
paper reproduction to a submitted, presentable challenge PR — by orchestrating the
existing harness skills and the borrowed sci-brain ideation pipeline, with a mentor
behavior woven through.

## Need

**Event.** Harnessing Quantum 2026 — a week-long on-site hackathon (July 27–31, 2026,
Hefei National Laboratory, ~70 graduate students, 7 method tracks). Four phases per
student: pick a track → onboard by reproducing a reference result → go *beyond* it as a
challenge PR → present to advisors for prizes.

**Gap.** The harness already covers setup (`/onboard`), track choice (`/beginner-training` Track 2),
reproduction (`/reproduce-paper`), and reporting (`/challenge-report`). Nothing drives
the phase between reproduction and reporting — the part where the student must invent and
execute a challenge. There is also no mentorship layer for a stuck student.

**Need (agreed).** A single guided skill that fills that hole: after reproduction, help
the student discover a worthy-but-feasible challenge (grounded in the track's frontier
maps and literature), get it ratified at the on-site help desk, drive the attempt within
hackathon time, and hand off to `/challenge-report`. It teaches and guides — it does not
auto-solve the challenge for the student.

**Success criteria.** A median participant, after reproduction, ends the week with: a
challenge they understood and chose; a clean PR limited to allowed locations; a
presentable report; and the sense that they learned the method — not that an agent did
the work.

**Constraints.** On-site, ~2.5 working days left after reproduction. Advisors are humans
at a physical help desk (no async/agent advisor integration). Reuse existing skills;
add no new heavy machinery. Harness UI norms apply (one decision at a time, lead with the
answer, plot + ≤3-line results, unicode math in chat).

### Participant walkthrough (the design's grounding)

| Moment | What the participant feels | What the skill must do |
|---|---|---|
| Reproduction just landed | "Go beyond it" — blank-page terror | Offer *ranked candidate challenges*, not "go think of something" |
| ~2.5 days left | Instinct to bite off a PhD chapter | Hard time-box + compute-cost guardrail before any commit |
| 11pm, method won't converge | Wants a nudge, not a lecture | Graded hints; "I'm stuck" handler |
| Walking to the help desk | Wants to look prepared | A crisp one-page digest, advisor-ready |
| "Good enough to present?" | Uncertain when to stop | Success/pivot signals + `challenge-report` gate |
| Closes laptop, returns next day | Lost context | Resume state across sessions |

## Prior art & landscape

The survey is **lightweight by design** — the landscape is internal (harness skills +
the sci-brain set); there is no external product to price.

**In-repo skills (the journey, reused as-is):**

| Skill | Role | Relationship to `/challenge` |
|---|---|---|
| `/onboard` | first-touch setup, audience calibration | upstream; mentor borrows its audience handling |
| `/beginner-training` (Track 2) | pick track + reproduction target | upstream |
| `/reproduce-paper` | reproduce the reference (phase 2) | upstream; `/challenge` begins where it ends |
| `/challenge-report` | report + submission-cleanliness gate | downstream; `/challenge` hands off to it |
| `/solve` | ad-hoc problem-solving loop | reused inside the attempt driver |

**Candidate tools to borrow (sci-brain pipeline) — this is what makes ideation cheap:**

| Tool | Capability covered |
|---|---|
| `sci-brain:survey` | parallel literature exploration → survey registry (`summary.md` + `.bib`) |
| `sci-brain:ideas` | two-agent ideation (Ideator proposes, Polya critique), adversarial ranking |
| `sci-brain:idea-writer` | structured ideas report: research question, **minimum-viable experiment**, success/hope/pivot signals |

**Gaps nothing off-the-shelf covers (so `/challenge` must own them):** the orchestration
spine and resume state; grounding ideation in the *track's* frontier maps and
hackathon-time feasibility; the advisor digest + help-desk handoff; the graded-hint
mentor behavior.

## Features

**In scope:**

- **Journey spine + resume state** — track where the student is, route to the right skill,
  resume across days. The skeleton everything hangs on.
- **Challenge ideation wiring** — run `sci-brain:survey → ideas → idea-writer`, grounded in
  the track's frontier maps; output is *ranked, feasibility-tagged* candidates.
- **Feasibility / time-box guardrail** — "can you finish this in the days left?" plus a
  compute-cost sanity check (reuses the harness cost rules and `/using-slurm`). Gates every
  candidate before the help desk. *Highest participant value.*
- **Advisor digest + help-desk handoff** — condense the ideas report into a one-page
  proposal (question, MVP, feasibility, risk); tell the student to take it to the help
  desk; record the go/no-go verdict back into the run.
- **Attempt driver** — on "go", scope the MVP, scaffold the run under `tracks/<track>/`,
  iterate with intermediate output, hand off to `/challenge-report`. Reuses `/solve`.
- **Mentor / get-unstuck behavior** — graded hints (nudge → direction → concrete step,
  never a spoiler first), explain-on-demand, "I'm stuck" handler, progress check-ins.
  Woven through the whole skill, not a separate command.

**Deferred (reason):**

- *Student progress map* — a visible "where am I / what's next" card. Defer to polish; the
  spine already tracks state internally. → post-event milestone.
- *Hint-level personalization* — calibrate hint depth to the student's background. Defer;
  `/onboard` audience calibration is a good-enough first cut. → post-event milestone.

Nothing dropped.

## Modules

`/challenge` is one skill. Internally it decomposes into modules with one purpose each.

| Module | Purpose | Interface (in → out) | Depends on |
|---|---|---|---|
| **Spine / state** | own the journey position; route; resume | session start → current step + next action; reads/writes a small run-state file under `tracks/<track>/` | — |
| **Ideation** | produce ranked, feasible challenge candidates | track + reproduction context → ranked candidates | `sci-brain:survey/ideas/idea-writer`, track frontier maps |
| **Feasibility guard** | gate candidates on time + compute | candidate → feasible? (time band, compute estimate, cluster need) | harness cost rules, `/using-slurm` |
| **Advisor digest** | make the help-desk one-pager; record verdict | chosen candidate → digest + recorded go/no-go | idea-writer report |
| **Attempt driver** | scope MVP, scaffold + run, iterate | go-verdict → run dir with results | `/solve`, harness run scaffolding |
| **Mentor** (cross-cut) | graded hints, explain, unstuck | "I'm stuck" / question → escalating help | `/onboard` audience calibration |
| **Handoff** | pass a finished run to reporting | run dir → invoke `/challenge-report` | `/challenge-report` |

## Technical approaches

### Module: Spine / state

- **A — One SKILL.md with an explicit step machine + a tiny state file** *(recommended)* —
  steps (`ideate → guard → digest → advisor → attempt → handoff`) recorded in a small
  per-run state file under `tracks/<track>/`. Resume reads the file. Matches how
  `reproduce-paper` keeps `run.json`. Simple, inspectable, resumable.
- **B — Stateless, re-infer position from git/run artifacts each session.** No state file;
  detect step from what files exist. Less to maintain, but brittle and ambiguous mid-step.
- **C — Heavy state in a sidecar DB / JSON registry.** Over-engineered for ~2.5 days of
  single-student work.
- *Reason:* A mirrors the existing `run.json` convention and gives clean resume without new
  infrastructure.

### Module: Ideation

- **A — Thin orchestrator over the sci-brain pipeline, pre-seeded with the track's frontier
  map** *(recommended)* — pass the track's frontier/literature context into
  `sci-brain:survey`, let `ideas` brainstorm, `idea-writer` write; `/challenge` only adds
  the hackathon-feasibility lens and ranking. Maximum borrow, minimum build.
- **B — Custom ideation prompt inside `/challenge`.** Full control, but reimplements what
  sci-brain already does well and diverges from it over time.
- **C — Curated static challenge list per track.** Cheapest, but kills the "students invent
  their own challenge" goal and dates quickly.
- *Reason:* A reuses a maintained pipeline and keeps the student inventing, while the
  frontier-map seeding keeps ideas on-method and the ranking keeps them feasible.

### Module: Feasibility guard

- **A — Rule-of-thumb estimator from the harness cost rules + a time-band check against
  days remaining** *(recommended)* — reuse the ED/DMRG/QMC cost formulas already in
  `CLAUDE.md`; map to a wall-time band; compare to remaining hackathon time; flag
  cluster-only work and route to `/using-slurm`. Cheap, already-specified math.
- **B — Trial micro-run to measure cost empirically.** More accurate, but spends scarce
  hackathon time to measure rather than to do.
- *Reason:* A is good enough to catch the "this is a PhD, not a hackathon" failure, which is
  the actual risk; B's precision isn't worth the time cost.

### Module: Advisor digest

- **A — Condense the idea-writer report into a fixed one-page template; print "take this to
  the help desk"; prompt for the verdict and record it** *(recommended)* — no integration,
  fits the on-site format, makes the student look prepared.
- **B — Async post to a Zulip track stream.** Needs the event Zulip wired up; out of scope
  per the help-desk decision.
- *Reason:* A matches the user's explicit "tell the student to go to the help desk" choice.

### Module: Attempt driver

- **A — Orchestrate `/solve` + harness run scaffolding, scoped to the MVP from the digest**
  *(recommended)* — reuse the existing problem-solving loop and run/plot/intermediate-output
  machinery; `/challenge` only enforces MVP scope and intermediate progress.
- **B — Bespoke run loop inside `/challenge`.** Duplicates `/solve`; drift risk.
- *Reason:* A avoids reimplementing a loop that already exists and already obeys the UI norms
  (plot + ≤3 lines, flushed progress).

### Module: Mentor (cross-cutting)

- **A — A hint-escalation protocol woven into every step** *(recommended)* — on "I'm stuck"
  or a question, escalate nudge → direction → concrete step, never spoiler-first; reuse
  `/onboard` audience calibration for tone. Always present, no separate command.
- **B — A standalone `/unstuck` skill.** Cleaner separation, but a stuck student won't
  break flow to invoke a second command; help should be in-context.
- *Reason:* A keeps help where the friction is; the participant walkthrough shows stuck
  moments happen mid-attempt, not at a command prompt. (Revisit B if the protocol grows
  large enough to deserve its own skill.)

## Quality requirements

- **Pedagogy (the one that matters).** The skill must *teach*, not solve. Graded hints
  never lead with the answer; the student makes every consequential decision. This is the
  event's whole point and the primary acceptance criterion.
- **Time-honesty.** Every candidate carries a wall-time band against days remaining; the
  guard refuses to wave through infeasible scope.
- **Submission cleanliness.** Inherited from `/challenge-report`'s gate — changes confined
  to allowed locations under `tracks/<track>/`.
- **Resumability.** A student can stop and resume across days without losing position.

(Performance, security, and uptime do not apply — single-student, on-site, local-or-cluster.)

## Open questions / out of scope

- **Frontier-map coverage.** Ideation grounding is only as good as each track's frontier
  map; tracks without one fall back to a literature-survey-only seed. Filling frontier maps
  per track is track-lead work, not part of this skill.
- **Out of scope:** async/agent advisor integration; organizer-side tooling (progress across
  all ~70 students, PR evaluation, prize allocation); the two deferred polish features.
