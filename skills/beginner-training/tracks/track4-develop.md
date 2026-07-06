# Track 4 — Develop code like an expert

**Time:** ~3–5 h · **Prereq:** Track 1 Step 4 (GitHub CLI) ·
**Live exercise:** take a real issue in the training repo to a reviewed pull
request, using the same disciplined loop professionals use.

Part of the harness beginner training. Every step follows the Teaching
Protocol in `skills/beginner-training/SKILL.md`.

## Goal

Research code is still code: it needs a clear problem statement, a design, a
plan, tests, and review. This track walks one full loop —
**issue → brainstorm → plan → implement → review → PR** — on the training repo
`QuantumBFS/qsym-rs`, a small Rust library for symbolic Pauli-operator
algebra sized for first contributions. Scope: one issue to one merged-ready PR.

## Scoped precheck

1. `gh auth status` — logged in.
2. `gh repo view QuantumBFS/qsym-rs --json name -q .name` — prints `qsym-rs`.
   On failure the student likely needs an invite; stop and resolve first.
3. Superpowers loop resolves:
   `ls skills/brainstorming/SKILL.md skills/writing-plans/SKILL.md skills/requesting-code-review/SKILL.md`
   — all three exist. On failure → `make skills` (Track 1 Step 1).

## Steps

### Step 1 — Fork and clone

Explain what a **fork** is (your own copy of the repo on GitHub, where you can
push freely) and why teams work fork → branch → PR:

```bash
gh repo fork QuantumBFS/qsym-rs --clone
```

Expected: a local `qsym-rs/` directory whose `origin` is the student's fork
and whose `upstream` is `QuantumBFS/qsym-rs`.

### Step 2 — The student picks a starter issue (explicit gate)

List the open starter issues **once**:

```bash
gh issue list -R QuantumBFS/qsym-rs --label "good first issue"
```

The student must choose. Do not open, assume, or start driving any specific
issue before they explicitly pick one. Answer questions about what each issue
involves if asked.

### Step 3 — Brainstorm the design

Invoke the `brainstorming` skill on the chosen issue: what is actually being
asked, what are 2–3 ways to do it, which is right and why. The design gets the
student's approval before any code.

### Step 4 — Write the plan

Invoke the `writing-plans` skill: bite-sized tasks, each with a failing test
first. Explain **TDD** (test-driven development: write the test that fails,
then the minimal code that passes it — so every behavior is pinned by a test).

### Step 5 — Implement, test-first

Execute the plan one task at a time under the Teaching Protocol: failing test
→ run it (must fail) → minimal implementation → run it (must pass) → commit.
Small commits with clear messages — each one a checkpoint you can retreat to.

### Step 6 — Request review, then open the PR

Invoke `requesting-code-review` on the finished branch and fix what it finds.
Then:

```bash
git push -u origin <branch>
gh pr create -R QuantumBFS/qsym-rs --title "<summary>" --body "Closes #<issue>. <what and why>"
```

## Checkpoint — the PR itself, plus its attached self-review (integrity check)

The checkpoint artifact is the open PR. Verify together, confirm-gated:

1. The PR links its issue (`Closes #N`), CI/tests pass, and every commit
   builds a reviewable story.
2. A **self-review record** — the output of the review skill in Step 6, listing
   what was checked and what was fixed — is posted as a PR comment. A PR that
   says "reviewed" without the record is a claim, not evidence.

Checkpoint passes when both are visible on the PR page.
