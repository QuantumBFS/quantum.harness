# Track 2 — Reproduce a paper

**Time:** ~2–4 h (beginner tier, laptop) · **Prereq:** Track 1 recommended ·
**Live exercise:** reproduce a published figure and verify it yourself.

Part of the harness beginner training. Every step follows the Teaching
Protocol in `skills/beginner-training/SKILL.md`.

## Goal

Reproduction is how computational physicists calibrate themselves and their
tools: if you can independently regenerate a published figure, you've proven
you understand the model, the method, and the checks — before trying anything
new. This track picks one of the harness's method tracks (each curated by an
expert in that method, with a named reference paper) and reproduces its target
at **beginner tier** — system sizes small enough for a laptop.

## Scoped precheck

1. `ls tracks/*/README.md` — the method-track pages exist.
2. `.venv/bin/python -c "import pymupdf4llm"` — paper rendering works (the
   reproduction will read the paper). On failure → Track 1 Step 2 fix.

## Steps

### Step 1 — Scan the method tracks

Read all `tracks/*/README.md` files fresh and extract one compact row per
track: `track id | title | listed target | listed tasks`. The README is the
source of truth; do not invent a paper for a track whose README does not name
one — mark it `No paper listed yet`. Show the student the table and explain
what each method is in one line (what is exact diagonalization? DMRG? QMC?).

### Step 2 — The student picks a track (explicit gate)

Ask exactly one question, one option per track that has a paper (description:
the paper and all its figures/tasks), paperless tracks grouped into a single
catch-all option. Selecting a track means reproducing **all** figures/tasks its
README lists. Do not mark a recommendation unless a README explicitly labels a
starter. If the student picks the catch-all, ask which paperless track and then
for a concrete paper (arXiv/DOI/title) — no handoff until a paper exists.

### Step 3 — Preview what reproduction will involve

Before handing off, walk the student through what `/reproduce-paper` will do:
read the paper, extract the model and observable, propose beginner-tier sizes,
confirm the setup, run, and self-check (e.g. eigenpair residuals, convergence).
Define the jargon that track needs now, so the reproduction isn't a black box.

### Step 4 — Hand off to /reproduce-paper

Invoke `/reproduce-paper` with this exact block, then stay in teaching mode —
the Teaching Protocol continues to apply through the whole reproduction:

```text
/reproduce-paper
Track: <track id> — <track title>
Source: tracks/<track>/README.md
Paper: <paper title, DOI/arXiv if listed>
Target: all figures — <list all figures/tasks from README>
Track objective: <one sentence from the README summary>
Teaching mode: beginner training Track 2 — keep the confirm-gated Teaching
Protocol from skills/beginner-training/SKILL.md for every step.
```

## Checkpoint — signature match + a deliberate mismatch (negative control)

Two halves, both confirm-gated:

1. **Positive**: the reproduced figure shows the paper's signature (e.g. for
   the ED track: the Z₂ scar band sitting above the thermal bulk) and the
   run's own self-checks pass (residuals, sector dimensions).
2. **Negative control**: rerun the smallest case with one deliberately wrong
   parameter — e.g. the wrong symmetry sector or boundary condition — and
   watch the self-check or the figure visibly break. If a wrong input still
   "passes", the verification was decoration.

Checkpoint passes when the student can point at the two outputs and explain
which physics changed and why the check caught it.
