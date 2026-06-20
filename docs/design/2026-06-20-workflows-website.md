# Recommended-Workflows Website — Design

Date: 2026-06-20
Status: approved (brainstorming)

## Goal

A simple, self-contained website that introduces the harness's **recommended
workflows**, each illustrated by a **complete end-to-end example** captured from
a **real** run (true transcripts + real plots).

Audience: Harnessing Quantum 2026 summer-school participants (and, by extension,
anyone landing on the repo).

## Deliverable

A single self-contained page: `.github/template/index.html`.

- No build step, no external assets/CDN, no JS framework. Inline CSS only.
- Plots embedded as local image files saved next to the page under
  `.github/template/` (or base64-inlined). GitHub-Pages-ready.
- Matches the harness `/report` HTML convention (offline, single file).

## The two intended workflows

The site presents exactly **two** workflows. The "general user path" is the same
as the problem-solving path (cluster is just its heavy-compute branch), so it is
not a separate section.

### Workflow 1 — Summer school: reproduce, then challenge

Skill chain:

```
/onboard → /track-starter → /reproduce-paper → /challenge → /challenge-report
 setup     pick a track     reproduce the ref   go beyond     clean PR + report
```

End-to-end example: the **ED track**. Reproduce a small, fast exact-diagonalization
result (quantum-scar / level-statistics style figure) at a local-feasible size,
then a *challenge* that extends it (e.g. larger system / extra observable). Real
transcript + real plot.

### Workflow 2 — General problem-solving (everyday users)

Skill chain:

```
/solve (or /model) → /method-* → /using-* → /using-slurm → /report
 state the problem   pick method  pick tool   heavy compute  HTML writeup
```

End-to-end example: **J₁–J₂ Heisenberg chain ground state** via DMRG (ITensors),
with a real convergence plot. Show the `/using-slurm` branch as the "when compute
gets heavy" step (active cluster profile is `localhost`).

## Page structure

1. Short intro: what the harness is, the two journeys, "pick your path".
2. Workflow 1 section: step-strip diagram → annotated real transcript → result
   plot → one-line takeaway.
3. Workflow 2 section: same shape.
4. Footer: how to start (`/onboard`), links to skills.

Each transcript is annotated as: *user says X → harness does Y → result Z*, using
clean monospace blocks. Unicode math in text (no LaTeX `$…$`).

## Real-run plan (scope: small + local)

- Confirm/instal stacks: ED tool (`make install xdiag` or `quspin`) and ITensors
  in `julia-env` (`make install itensors` if absent).
- Run two **small, fast, local** calculations (minutes each). No real cluster.
- Save scripts under `scripts/`, results+plots under `results/`, then copy the
  plots the page needs into `.github/template/`.
- Capture true console transcripts for the annotated blocks.

## Out of scope

- Multi-page site, search, JS interactivity.
- Real remote-cluster submission (localhost profile only).
- The other verb skills (`/parameter-scan`, `/scaling-fit`, `/cross-method-check`)
  as their own sections — they appear only as mentioned next-steps.
