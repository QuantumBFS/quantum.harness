# Detailed Research Narrative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a detailed, source-backed, all-English explanation of the Issue #265 research result and its confirmatory program.

**Architecture:** Use a three-level documentation hierarchy: a navigable README, a long-form scientific case, and a dated status ledger.  Keep the PR body self-contained while linking to the committed evidence and frozen machine-readable protocol.

**Tech Stack:** Markdown, JSON evidence records, Python/pytest validation, Git, GitHub CLI.

## Global Constraints

- Preserve the frozen hypotheses, conditions, time splits, thresholds, hashes, and unblinding policy.
- Distinguish exact statements, numerical pilot evidence, and pending confirmatory evidence.
- Use constructive language and avoid turning unavailable production data into a model preference.
- Cite primary literature and committed repository evidence for substantive claims.
- Keep the existing ready-for-review PR, team identity, and Issue #265 linkage.

---

### Task 1: Long-form scientific case

**Files:**
- Create: `SCIENTIFIC_CASE.md`
- Reference: `docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md`
- Reference: `docs/CLOSED_LOOP_VERDICT.md`
- Reference: `docs/IMPLEMENTATION_STATUS_BURGERS_RESEARCH.md`

**Interfaces:**
- Consumes: primary-literature links, public-pilot measurements, frozen JSON rules, and archived HPC evidence.
- Produces: the authoritative reviewer-facing scientific argument linked by the README and PR body.

- [ ] **Step 1: Write the claim/evidence hierarchy**

Include exact, controlled, empirical, and registered claims as separate
sections, with equations and evidence paths.

- [ ] **Step 2: Explain the central theoretical tension**

Derive the spin-flip gate, nonlinear averaging term, two-mode chiral fields,
moment bridge, and scalar rarefaction crossover.

- [ ] **Step 3: State the pilot and confirmatory claims quantitatively**

Include the public fit, profile error, width/moment exponents,
`A_B/A_W`, synthetic recovery checks, conditions, thresholds, and allowed
selection outcomes.

- [ ] **Step 4: Add traceable references**

Link every primary paper and provide a repository evidence index.

### Task 2: Entry-point and status documents

**Files:**
- Modify: `README.md`
- Modify: `CURRENT_STATUS.md`

**Interfaces:**
- Consumes: `SCIENTIFIC_CASE.md` and committed status records.
- Produces: a fast reviewer path and a dated execution snapshot.

- [ ] **Step 1: Expand the README**

Add the scientific answer, evidence ladder, model-selection flow, package map,
and reproducibility commands.

- [ ] **Step 2: Expand the status ledger**

Record completed analytical/numerical infrastructure, archived SCNet job
evidence, production gates, and the next decisive readouts.

### Task 3: Verification and publication

**Files:**
- Modify: GitHub PR #284 body
- Verify: all files under `tracks/mps/solutions/Wander/issue265/`

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: a pushed commit and a remotely verified PR description.

- [ ] **Step 1: Audit prose and links**

Run Markdown-link, placeholder, negative-tone, secret/path, and consistency
searches; inspect the rendered structure through heading and link checks.

- [ ] **Step 2: Run code checks**

Run `python3 -m compileall -q src scripts hpc tests`, the focused pytest suite,
and `git diff --check` from the solution directory.

- [ ] **Step 3: Commit and push scoped files**

Stage only the design, plan, scientific case, README, and status files; commit
and push the current `codex/issue-265-burgers-pilot` branch.

- [ ] **Step 4: Replace and verify the PR body**

Update PR #284 with the detailed self-contained narrative, preserve the team
table and issue linkage, and read the remote PR back through `gh pr view`.
