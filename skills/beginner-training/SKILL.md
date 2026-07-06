---
name: beginner-training
description: Use when a new harness user (assume undergraduate level) starts the beginner training and needs to choose which track to run — asks which of the five tracks (setup check, reproduce a paper, literature survey, develop code like an expert, go beyond) to take, then walks that track as a guided, confirm-gated tutorial that explains every step and waits for the student to confirm understanding before running anything. Triggers on "start the training", "beginner training", "/beginner-training", "which track should I take", "I'm new here, teach me the harness".
---

# beginner-training

## Overview

The launcher for the harness beginner training. It does two jobs: **(1)** ask
which track to take and route there, and **(2)** carry the **Teaching Protocol**
below — the rules for *how* every track is run. The track pages under
`skills/beginner-training/tracks/` hold each track's step content; this skill
holds the selector and the protocol.

**Assume the student is at undergraduate level.** Do not assume they have used
git, GitHub (`gh`), Julia, a literature-survey tool, or quantum many-body
jargon before. Define terms the first time they come up (what is a symmetry
sector? DMRG? a residual? a PR?), and explain *why* a step matters, not just
*how* to run it.

## Teaching Protocol — follow this for EVERY step of EVERY track

This is a training, not a script. Teach **one step at a time**, and **never run
a command before the student confirms they understand it.** For each step:

1. **Announce** where we are: "Step N of M — <name>."
2. **Explain what will happen**, in plain language a first-year student follows.
3. **State the purpose** — what they're learning, or why researchers work this way.
4. **Show the exact command** and **what a correct result looks like** (the
   observable expected output).
5. **Stop and wait.** Invite them to confirm or ask: *"Reply `ready` and I'll
   run it — or ask me anything first."* Do **not** run anything until they
   confirm. If they ask a question, answer it, then re-offer.
6. **Run it** (only after they confirm), show the real output, and **explain
   what actually happened**, tying it back to the purpose. If it failed,
   diagnose it *with* them before moving on.
7. Move to the next step.

**Hard rules**
- One step, one confirmation. Never batch-run steps.
- Never skip the explanation to save time — the explanation *is* the training.
- Define jargon on first use (what is a Hamiltonian sector? a bond dimension?
  a pull request?).
- If the student says "just do it" / "skip ahead," you may proceed, but still
  say what each step did as you go.
- Every track ends with a Checkpoint, run this same confirm-gated way, whose job
  is to **prove trustworthiness** — via a real **negative control** (a deliberately
  bad input that must fail) where that fits, or a cheaper **integrity check**
  (self-contained, placeholder-free, count matches what actually ran) where a
  staged negative control would be artificial. Run whichever the track specifies
  ("now let's prove the check actually has teeth"). Do not demand a literal
  negative control on a step whose real safeguard is an integrity check.

## Step 1 — Ask which track to take (do this first)

Present the track selector. The recommended order is 1 → 2 → 3 → 4 → 5, but any
track can be taken first and each stands alone. `AskUserQuestion` allows four
options, so offer: **Recommended full path (1→2→3→4→5)**, **Track 1**,
**Track 2**, and a catch-all **Another track (3, 4, or 5)**. If the catch-all
is picked, ask one follow-up question offering tracks 3, 4, and 5. The tracks:

1. **Track 1 — Setup check** → `tracks/track1-setup.md`. No prerequisite.
   Recommended before any other track.
2. **Track 2 — Reproduce a paper** → `tracks/track2-reproduce.md`. Precheck:
   `ls tracks/*/README.md` lists the method tracks, and pdf-render is available
   (`.venv/bin/python -c "import pymupdf4llm"`). Scans the method-track READMEs,
   lets the student pick one, then hands off to `/reproduce-paper` at beginner
   tier with teaching mode kept on.
3. **Track 3 — Conduct a literature survey** → `tracks/track3-survey.md`.
   Precheck: `.venv/bin/python -c "import pymupdf4llm"` succeeds. Builds a small
   reference library in `.knowledge/` with `/download-ref` and `/survey`.
4. **Track 4 — Develop code like an expert** → `tracks/track4-develop.md`.
   Precheck: `gh auth status` succeeds **and** `gh repo view QuantumBFS/qsym-rs`
   succeeds, **plus** the superpowers loop resolves
   (`skills/brainstorming/SKILL.md`, `skills/writing-plans/SKILL.md`,
   `skills/requesting-code-review/SKILL.md` all exist). The learner must
   explicitly pick which starter issue to work on — the trainer must not open,
   assume, or drive any specific issue before the learner picks it.
5. **Track 5 — Go beyond** → `tracks/track5-beyond.md`. The capstone. Precheck:
   a completed reproduction to extend (Track 2 done, or the student names a
   reproduced result). Runs `/challenge` → `/challenge-report`.

Plus **Recommended full path** → run 1 → 2 → 3 → 4 → 5 in order. Any track is
selectable first; do not force the order.

## Step 2 — Run the chosen track under the Teaching Protocol

1. Open the chosen track page. Give the student the track's **Goal** and
   **Before you start** overview, and confirm they're ready to begin.
2. Run that track's **scoped precheck** as the first teaching step(s) — explain
   what you're checking and why, then wait, then run. If a check fails, walk the
   student through the matching Track 1 fix before continuing.
3. Walk the track's **Steps** one at a time, each following the Teaching Protocol.
4. Run the **Checkpoint** the same confirm-gated way — proving trustworthiness via
   its **negative control** or **integrity check**, whichever that track specifies —
   and make sure the student understands why the checkpoint passed.
5. When the checkpoint passes, congratulate them and offer the next track in the
   recommended order.
