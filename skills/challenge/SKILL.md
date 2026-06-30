---
name: challenge
description: Use when a student has finished reproducing their track's reference paper and wants to take on a challenge — go beyond the reference and ship a PR. Drives challenge ideation (literature survey → brainstorm → write-up), a help-desk go/no-go, the attempt, then hands off to /challenge-report. Triggers include "I reproduced the paper, now what", "take on a challenge", "go beyond the reproduction", "what should I try next on this track", "/challenge", or right after /reproduce-paper completes a run.
---

# challenge

The missing spine between **reproduction** and **report**. A Harnessing Quantum 2026
participant has reproduced their track's reference paper; now they must invent and execute
a *challenge* — something beyond the reference — and ship it as a clean PR. This skill
carries them through that: discover a worthy-but-feasible challenge, get it ratified at the
on-site help desk, drive the attempt within hackathon time, and hand off to
`/challenge-report`.

It **teaches and guides** — it never auto-solves the challenge. The student makes every
consequential decision; the skill lowers the blank-page terror, keeps scope honest about
time, and unblocks them when they're stuck. That *is* the value.

## Scope — what this owns vs delegates

- **Owns:** the journey spine and resume state; grounding ideation in the track's frontier
  maps; the feasibility / time-box guard; the advisor digest + help-desk handoff; the
  graded-hint mentor behavior; the handoff to reporting.
- **Delegates ideation** to the sci-brain pipeline — `/survey` (literature) → `/ideas`
  (brainstorm) → `/idea-writer` (write-up). Do not reimplement these.
- **Delegates the attempt** to `/solve` and the run machinery (script → `tracks/<track>/`,
  plot + intermediate output). Do not write a second run loop.
- **Delegates the report** to `/challenge-report` (which gates submission cleanliness).
- Reuses harness cost rules (`CLAUDE.md`) and `/using-slurm` for the feasibility guard.

## State — one small file, resumable

The journey position lives in `challenge.json` inside a timestamped run directory:
`tracks/<track>/results/YYYYMMDD-HHMMSS-challenge-<brief>/challenge.json`. Re-read it on
resume; never reconstruct state from conversation memory. Representative shape:

```json
{
  "track": "ed",
  "step": "ideate | guard | advisor | attempt | done",
  "reproduction_run": "tracks/ed/results/<repro-run>/",
  "days_left": 2.5,
  "survey_registry": "<path from /survey>",
  "ideas_log": "<path from /ideas>",
  "ideas_report": "<path from /idea-writer>",
  "candidates": [
    { "title": "…", "question": "…", "wall_band": "~hours on a laptop",
      "compute": "local | cluster", "feasible": true, "why": "…" }
  ],
  "chosen": { "title": "…", "mvp": "the smallest experiment that tests it",
              "success_signal": "…", "pivot_signal": "…" },
  "advisor": { "verdict": "go | revise | no-go", "notes": "…", "when": "…" },
  "hints_used": 0
}
```

The **attempt** writes a normal `run.json` (the `/reproduce-paper` schema) in the same run
directory, so `/challenge-report` picks it up unchanged.

## Mentor behavior — always on, every step

Graded hints, never spoiler-first. When the student is stuck or asks "how", escalate one
rung at a time and stop at the lowest rung that unblocks them:

1. **Nudge** — name the thing to look at ("what does the energy-vs-step curve do near the end?").
2. **Direction** — the kind of fix, not the fix ("this smells like a bond-dimension convergence issue — there's a knob for it").
3. **Concrete step** — the specific action, only after 1–2 didn't land ("raise the DMRG bond dimension to 400 and re-run the last sweep").

Tone follows the student's level (reuse `/onboard`'s audience calibration). Increment
`hints_used`. Explain-on-demand: if they ask what a term/knob means, give the one-sentence
consequence ("bond dimension = how much entanglement the state can hold; too small →
energy biased high"), then return to their decision. Never lead with the answer; never
lecture.

## Flow

### Step 0 — Confirm the launch point

`/challenge` begins where `/reproduce-paper` ended. Before ideating, confirm the
reproduction actually landed and read the context:

1. **Find the reproduction run.** Scan `tracks/<track>/results/*/run.json` for a completed
   run (≥1 figure with a non-empty `results`). If several, ask which one this challenge
   builds on. If none, say so and route the student back to `/reproduce-paper` — there is
   no foundation to build a challenge on yet.
2. **Read the track frontier map** — `tracks/<track>/README.md` plus any frontier/limitation
   notes in the relevant `/method-*` card and `.knowledge/` cards. This is what ideation is
   grounded in; a track with no frontier map falls back to a survey-only seed (say so).
3. **Ask the one thing that sizes everything: how much working time is left** (days/hours
   until the presentation). Record `days_left`. Every later feasibility call is relative to
   this number — there is no "good challenge" in the abstract, only one that fits the time.

Create the run directory, write `challenge.json` with `step: "ideate"`, and state in one or
two lines what the challenge will build on. Confirm before ideating.

### Step 1 — Ideate (delegate to sci-brain)

The goal of this step is **ranked, feasibility-tagged candidate challenges** — not a blank
page. Run the sci-brain pipeline, seeded with the track context from Step 0:

1. **`/survey`** — literature around the track's frontier (pass the frontier-map topics as
   the seed). Produces a survey registry the next step reads.
2. **`/ideas`** — brainstorm challenges grounded in that survey. Frame the brief explicitly
   as *"hackathon challenges that go one concrete step beyond <reference paper>, doable in
   ~`days_left`"* so the Ideator stays scoped. The output is a ranked shortlist.
3. **`/idea-writer`** — write the chosen direction into a structured proposal: research
   question, **minimum-viable experiment**, success / hope / pivot signals.

Record the registry, ideas-log, and report paths in `challenge.json`, and the shortlist as
`candidates`. Keep the student steering throughout (these skills already do one-at-a-time);
`/challenge` only adds the hackathon-feasibility lens. Set `step: "guard"`.

### Step 2 — Feasibility / time-box guard (the highest-value gate)

Before anything goes to the help desk, price each surviving candidate against the clock —
this is what stops a student committing to a PhD chapter:

- **Wall-time band.** Use the `/method-*` cost model and the harness cost rules
  (`CLAUDE.md`: ED `D²·8 B` / `O(D³)`; DMRG `χ²·L·8 B` / `#sweeps·D·χ³`; QMC per-MCS · steps)
  to put a coarse band on the candidate — minutes / hours / days. No micro-run; the band is
  enough to catch the failure mode.
- **Compute placement.** If it only finishes on the cluster, flag it and note that the
  attempt will compose with `/using-slurm` (and that setup eats into `days_left`).
- **Time-box verdict.** Mark each candidate `feasible: true/false` against `days_left`,
  leaving slack for the write-up and presentation. Refuse to wave through a candidate whose
  band exceeds the time left — say plainly why, and offer the scoped-down MVP instead.

Before asking the student to choose, present the surviving candidates as a ranked comparison
table. This is a user-facing presentation of the existing candidate content, not a new
pipeline stage:

| Column | Meaning |
|---|---|
| Rank | Feasibility / continuity order; omit a recommended label unless the reason is technical. |
| Challenge | The concrete next experiment. |
| Why it follows | How it extends the reproduced paper or previous result. |
| MVP | The smallest run that tests the idea. |
| Cost | Local/cluster placement and wall-time band. |
| What it teaches | The consequence: what the result would decide or clarify. |
| Risk / pivot | What can fail, and the scoped fallback signal. |

Ask one question: `Which challenge should we take to the help desk?` Include
`Other / advisor suggestion` as the final option when the host supports options, or as a
numbered row otherwise.

Land on **one** chosen challenge with its MVP. Record `chosen` (title, MVP, success/pivot
signals) and set `step: "advisor"`.

### Step 3 — Advisor digest + help-desk go/no-go

Condense the proposal into a **one-page digest** the student can hand to a human advisor —
crisp enough to make them look prepared:

| Digest row | Content |
|---|---|
| Challenge | One-sentence research question, and the reference it goes beyond. |
| MVP | The smallest experiment that tests it — what runs, what's measured. |
| Feasibility | Wall-time band, local vs cluster, fit against time left. |
| Risk | The one thing most likely to sink it, and the pivot signal. |

Save the digest into the run directory. Then tell the student plainly:

> **Take this to the help desk for a go / no-go before you spend the hours on it.**

When they return, record the verdict in `challenge.json` → `advisor`: **go** → proceed to
the attempt; **revise** → loop back to Step 1 or 2 with the advisor's note; **no-go** →
pick another candidate. Do not start the attempt without a recorded `go`.

### Step 4 — Drive the attempt (delegate the loop)

On `go`, execute the MVP — reusing `/solve` and the run machinery, never a bespoke loop:

- Scope strictly to the MVP from the digest; resist scope creep (the student can extend
  *after* a first result lands).
- Script → `tracks/<track>/solutions/`; data + plots → `tracks/<track>/results/<run>/`;
  write the computation as a normal `run.json` so `/challenge-report` reads it.
- **Emit intermediate output**, not just a final number — the method card says which signal
  to watch (QMC: energy-vs-imaginary-time flattening + average sign; DMRG: energy vs sweep +
  truncation error). Surface short status lines so the student sees it converging.
- Mentor behavior is live here — this is where "I'm stuck" happens most. Give graded hints,
  don't take the keyboard.
- Check the **success / pivot signals** from the proposal: a clear pivot signal means stop
  and say so honestly, rather than burning the remaining time.

Set `step: "done"` once a result (even a partial one) is in `run.json`.

### Step 5 — Handoff to reporting

Invoke **`/challenge-report`** on the run directory. It gates submission cleanliness
(changes confined to allowed locations) and walks the student through the narrative report
for their presentation. `/challenge` stops here — it does not build the report itself.

## UX rules

- **One decision at a time**, recommendation-first only when there's a real technical
  reason; scientific choices stay neutral. Use the question tool; otherwise number choices.
- **Lead with the answer**, then a one-line reason. Results in ≤3 lines + a plot.
- **Plain English** — gloss any non-standard term with its consequence on first use; common
  method families (ED, DMRG, QMC, VMC, NQS) need no gloss.
- **Use tables for comparison.** When the student is choosing among 2+ challenges, show a
  compact table with the action, reason, MVP, cost, consequence, and risk; use short prose
  after a choice is made.
- **Unicode math in chat** (`E₀/N`, `J₂/J₁`, `χ`, `Δ`), never `$…$`.
- **Time-honest, always.** Every candidate carries a wall-time band against time left; the
  guard never waves through infeasible scope.

## Not this

- Don't auto-solve the challenge or take over the keyboard — guide, hint, let the student
  decide and type. Pedagogy is the primary acceptance criterion.
- Don't reimplement ideation (`/survey` `/ideas` `/idea-writer`), the run loop (`/solve`),
  or the report (`/challenge-report`) — delegate and compose.
- Don't start the attempt before a recorded help-desk `go`.
- Don't let scope exceed the time left — refuse and offer the scoped-down MVP.
- Don't reconstruct journey state from memory — `challenge.json` is the single source.
- Don't dump walls of text — short status lines, one question at a time.
