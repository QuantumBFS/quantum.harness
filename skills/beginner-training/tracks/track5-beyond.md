# Track 5 — Go beyond

**Time:** open-ended (time-boxed candidates: hours → half a day) ·
**Prereq:** a completed reproduction (Track 2) · **Live exercise:** extend a
published result with your own question, and ship the report.

Part of the harness beginner training — the **capstone**. Every step follows
the Teaching Protocol in `skills/beginner-training/SKILL.md`.

## Goal

Reproduction proves you can stand where the authors stood; a **challenge** is
your first step past them — a feasible extension the paper didn't do (a larger
size, a new term, a different observable). This track uses `/take-challenge` to
pick one from the school's challenge catalog and register it as a PR, the
sci-brain pipeline (`/survey` → `/brainstorm-ideas` → `/autoresearch`) to do
the work, and `/challenge-report` to ship the outcome. Tracks 3 and 4 pay
off here: the survey library grounds the idea, and the development loop ships it
cleanly.

## Scoped precheck

A completed reproduction exists: results under `tracks/<track>/results/` from
Track 2, or the student names what they reproduced. A challenge extends a
calibrated result — without one there is nothing to go beyond.

## Steps

### Step 1 — See the challenge candidates

Run `/take-challenge`. It fetches the school's catalog of released challenge
issues and presents it index-first — totals, then one row per method group.
The student says which groups to expand; the reproduced track is a natural
starting point, but any group is open. Explain the labels as they come up:
`accepted` means organizer-ratified, `autoresearch` means the challenge ships
its own pass/fail gate. Feasibility at the student's compute budget is the
student's call to reason through — `/take-challenge` registers a pick, it
doesn't price or rank one.

### Step 2 — The student picks one (explicit gate)

The student chooses; the mentor gives graded hints but must not auto-solve.
This mirrors the summer-school rule: the harness guides, the student thinks.
`/take-challenge` then registers the choice by opening and submitting the PR —
that PR is the claim, and everything after lands on its branch.

### Step 3 — Plan before compute

Before running anything: what exactly will be computed, at what sizes, what
does success look like, and what is the **kill criterion** — the observation
that would tell you to stop early. Write these four answers down; they become
the report's skeleton.

### Step 4 — Execute the challenge

Run the attempt through the sci-brain pipeline, confirm-gated: `/survey` to
ground it in a real reference library, `/brainstorm-ideas` to shape the
approach into a minimum viable experiment, and `/autoresearch` to drive the
runs — checking convergence/verification at each size the way the reproduction
did. Save scripts under the team folder `tracks/<track>/solutions/<team-name>/`
(the registered claim's folder) and data + plots under
`tracks/<track>/results/<run>/` so every number is regenerable.

### Step 5 — Ship it

Run `/challenge-report`: it gates a clean PR under `tracks/<track>/` containing
the report, scripts, and figures.

## Checkpoint — report integrity (integrity check)

Go through the generated report together, confirm-gated, and verify:

1. **Self-contained**: a reader with only the report can say what was run, at
   which parameters, and what came out.
2. **Placeholder-free**: no TODO / TBD / "figure to be added" anywhere.
3. **Every number traces to a run**: each figure and quoted value maps to a
   script under `tracks/<track>/solutions/<team-name>/` and data under
   `tracks/<track>/results/` that actually exist — spot-check at least two.

A staged negative control would be artificial here — the report *is* the
deliverable, so its integrity *is* the trust proof. Checkpoint passes when all
three hold and the student can defend the kill-criterion decision they made.
