# Track 1 — Setup check

**Time:** ~0.5 h · **Prereq:** none · **You will not learn a new physics tool
here** — you'll build the habit of checking your tools before trusting them.

Part of the harness beginner training. Run via `/beginner-training`; every step
follows the Teaching Protocol in `skills/beginner-training/SKILL.md`.

## Goal

Before you trust a tool with something that matters, you check that it actually
works. Professional software teams call this a **smoke test** — a fast, shallow
check that the basic plumbing works before you rely on it. Four small checks
now save the later tracks from stalling thirty minutes in on a missing piece.

| Check | Verifies | Needed by |
|---|---|---|
| Step 1 — harness skills | Ion-managed skills installed and in sync | every track |
| Step 2 — pdf-render | PDF → markdown library importable | Tracks 2 & 3 (paper reading, `/download-ref`) |
| Step 3 — Julia environment | `julia-env` project instantiates | Track 2 (method stacks) |
| Step 4 — GitHub CLI | `gh` logged in, `QuantumBFS/qsym-rs` visible | Track 4 (issues, PRs) |

## Before you start

You'll run four short checks, each one small command block, and compare the
real output against what's expected. No coding, nothing to build.

## Steps

### Step 1 — Sync the harness skills

**What**: `make skills` installs the Ion skill manager if missing, then runs
`ion add` to sync every skill listed in `Ion.toml` into `skills/`.
**Why**: skills are the agent workflows you'll invoke as `/name`; a stale or
missing skill means the agent silently improvises instead.

```bash
make skills
```

Expected: Ion reports the skill set in sync (no errors). Spot-check:
`ls skills/reproduce-paper/SKILL.md skills/survey` both resolve.

### Step 2 — pdf-render (paper → markdown)

**What**: the `/download-ref` skill turns downloaded papers into markdown via
the Python library `pymupdf4llm`, installed in a repo-local virtual
environment `.venv` (a private Python that can't clash with your system one).
**Why**: Track 3 downloads real papers; without this library it can fetch PDFs
but not read them.

```bash
.venv/bin/python -c "import pymupdf4llm; print('pdf-render OK')"
```

Expected: `pdf-render OK`. If it fails: `make install pdf-render`, then rerun.

### Step 3 — Julia environment

**What**: most method stacks (ITensors, PEPSKit, …) are Julia packages living
in the repo-local project `julia-env` (Julia's equivalent of `.venv`).
**Why**: Track 2's reproduction almost certainly runs Julia code.

```bash
julia --project=julia-env -e 'using Pkg; Pkg.instantiate(); Pkg.status()'
```

Expected: a package list prints without errors. If `julia` is not found:
`make install julia`, then rerun.

### Step 4 — GitHub CLI

**What**: `gh` is GitHub's command-line client — it forks repos, files issues,
and opens **pull requests** (PRs: a request to merge your changes into a
shared repo) without a browser.
**Why**: Track 4 works against the training repo `QuantumBFS/qsym-rs`, which
needs an authenticated `gh` that can see it.

```bash
gh auth status && gh repo view QuantumBFS/qsym-rs --json name -q .name
```

Expected: your login is reported, then `qsym-rs`. If auth fails: `gh auth login`
(the student runs this themselves — it's interactive). If the repo view fails,
they may need an invite; note it and continue — only Track 4 blocks on it.

## Checkpoint — prove the checks have teeth (negative control)

A check that can't fail is decoration. Run one availability check that
**should** fail, and watch it fail:

```bash
.venv/bin/python -c "import a_package_that_is_not_installed"
```

Expected: `ModuleNotFoundError: No module named 'a_package_that_is_not_installed'`.

Explain to the student: this is a **negative control** — the same idea as a
blank in a lab experiment. Because this check visibly fails on a missing
package, the passes in Steps 1–4 mean something. Checkpoint passes when the
student can say, in their own words, why a deliberate failure makes the other
results trustworthy.
