---
name: take-challenge
description: Use when a student or team wants to take on a Harnessing Quantum 2026 challenge — show the official catalog (upstream GitHub issues labelled `challenge`) and register the one they pick as a pull request against `QuantumBFS/quantum.harness`. Registration only; the attempt belongs to `/solve` and the report to `/challenge-report`. Triggers include "take a challenge", "which challenges are available", "show me the challenge list", "register our challenge", "open the challenge PR", "I reproduced the paper, now what", "/take-challenge".
---

# take-challenge

**Show the catalog, then register what they pick.** A Harnessing Quantum 2026 team stakes its
claim on one challenge as a pull request to `QuantumBFS/quantum.harness`. This skill gets the
paperwork right and then stops.

It is a registration skill. It does not do the science (`/solve`), does not write the report
(`/challenge-report`), and does not decide anything scientific — the team picks, the skill
files.

**The track is an output, not an input.** Never infer the team's track from run directories,
prior reproductions, git history, or which track folders exist. Any team may take any
challenge; guessing narrows the menu before they have seen it. The track is resolved in Step 3
from the challenge they chose.

## Step 1 — Show the catalog

Do this before asking anything. The school releases challenges as GitHub issues, so the team
is picking from a real menu.

```bash
gh issue list --repo QuantumBFS/quantum.harness --label challenge \
  --state open --limit 300 --json number,title,state,labels,body
gh pr list --repo QuantumBFS/quantum.harness --state open --limit 100
```

If `gh` is unauthenticated or offline, say so plainly — never silently skip the catalog and
pretend it was empty.

Read off three things:

| Axis | Source | Meaning |
|---|---|---|
| Method | the `### Method` field in the issue body | the seven tracks — `ed`, `mps`, `peps`, `qmc`, `qcs`, `polyopt`, `agent-kb` — plus `other` |
| Ratification | labels | `accepted` = organizer-ratified; without it, proposed only and riskier to register |
| Verification | labels | `autoresearch` = ships its own pass/fail gate, so "did it work?" is objective |
| Already claimed | open PRs | a challenge another team registered; still takeable, but say they'd be racing |

`Method` is a dropdown in the template but **free text in practice** — real values include
`Semidefinite programming / Noncommutative polynomial optimization` and `MPS / QMC / VMC-NQS`.
Normalize onto the seven tracks, list slash-separated values under each, and say the grouping
is approximate. It is a browsing aid, never a filter applied on the team's behalf.

**Present index-first.** Lead with the totals, then one row per method group with its count.
Ask which groups to expand — or, if the team already named a method, an area, or an issue
number, expand that immediately and skip the question. An expanded group is a table: issue #,
challenge, released by, labels, one-line objective from the body. "Show me everything" gets
all of them as one-liners.

## Step 2 — Team and choice

Ask for:

- **Team name** — it names the solution folder and the PR title.
- **Team members** — who is credited on the PR and the presentation. Record as given; don't
  chase affiliations or emails.

Then land on **one** challenge. **Read its full issue body before registering it** — the
objective, the verification plan, any stated target, and any instruction about where the
solution goes. Ask one question: `Which challenge should we register?`, with `Other / none of
these` as the final option.

Don't price the challenge, don't build a shortlist with wall-time estimates, and don't rank on
feasibility — that is the team's judgment and `/solve`'s job. Registration claims the
challenge; scoping the attempt belongs to `/solve`.

**Nothing fits.** If no catalog challenge suits the team, they write their own: file a new
`[challenge]:` issue with `.github/ISSUE_TEMPLATE/challenge-idea.yml`, then register that.
Don't run the ideation pipeline by default — 40 released challenges usually make it
unnecessary.

## Step 3 — Open the PR

**Where the track comes from**, in this order:

1. **The issue says so.** Several challenges name their solution folder outright (e.g. #71:
   "work under `tracks/qcs/solutions/<your-team>/`"). That wins over everything else,
   including the issue's own `Method` field, which can disagree with it.
2. **The `Method` field**, normalized onto the seven tracks.
3. **Ambiguous or spanning** (`MPS / QMC / VMC-NQS`, `Other`) — ask which track folder to file
   under. Don't pick for them.

**Already registered this challenge?** One pull request per team per challenge. A team may
register multiple challenges, each in its own PR. If `gh pr list` shows that the same team
already registered the same challenge, update that PR rather than opening a duplicate. An
existing PR for a different challenge does not block a new registration.

Then:

1. **Fork + branch.** Check `git remote -v` first: if `origin` is `QuantumBFS/quantum.harness`
   itself there is no fork yet — create one (`gh repo fork --remote-name <team>`) and push
   there. Branch `challenge/<track>-<brief>`. Never register from `main`.
2. **Seed the solution folder.** Write the filled-in PR body to
   `tracks/<track>/solutions/<team-name>-<issue-number>/README.md`; it doubles as the team's
   challenge README and keeps multiple registrations from the same team separate. Commit
   nothing outside that folder — `tracks/**/results/` and the root `results/` stay out of git.
3. **Fill the template.** `.github/PULL_REQUEST_TEMPLATE.md` is the single source for what a
   registration PR must say (team, members, challenge, catalog issue, track).
   The web UI prefills it; `gh pr create --body` does not, so pass the same sections yourself.
   If the template changes, follow the template — don't reproduce its fields here.
4. **Open it.** `gh pr create` targeting `QuantumBFS/quantum.harness:main`, title
   `[<track>] <team-name>: <one-line pitch>`. Reference the challenge as `Addresses #<n>` — a
   bare mention, not `Closes`, since one team's attempt rarely finishes a research-scale
   challenge.
5. **Submit it.** A draft does not register the claim — create it without `--draft`, or
   `gh pr ready <n>`. **Confirm with the team before pushing and submitting**: it is public and
   outward-facing.
6. **Print the URL.**

Registration is due **Day 4 (Thu) morning**, updatable until **Thu 20:00**. Register early —
an unregistered challenge doesn't count, however good the result. The on-site help desk is
consultation, not ratification: offer it as a sanity check, never block registration on it.

## Rules

- **One decision at a time.** Use the question tool; otherwise number the choices.
- **Never steer a scientific choice.** Explain terms on demand — one sentence, in terms of
  consequence — then hand the decision back.
- **Lead with the answer**, then a one-line reason. Plain English; gloss non-standard terms on
  first use. Common method families (ED, DMRG, QMC, VMC, NQS) need no gloss.
- **Tables for comparison**, short prose after a choice is made. Unicode math (`E₀/N`, `J₂/J₁`,
  `χ`, `Δ`), never `$…$`.
- **Don't detect the track**, don't pre-filter the catalog, and don't claim the method grouping
  is exact.
- **Don't dump 40 rows** unasked — index by method group, expand on request.
- **Don't leave the PR as a draft** and call it registered; don't push without confirming;
  don't register from `main`; don't commit outside the challenge-specific solution folder;
  don't open a duplicate PR for the same team and challenge.

## Done — hand off

Say this in two lines and stop:

- **Do the work** → `/solve`, which scopes the attempt. Scripts to
  `tracks/<track>/solutions/`, data and plots to `tracks/<track>/results/<run>/`, a normal
  `run.json`. Commits land on the same branch, so the PR accumulates the work.
- **Write it up** → `/challenge-report`, which gates submission cleanliness and builds the
  presentation report.
