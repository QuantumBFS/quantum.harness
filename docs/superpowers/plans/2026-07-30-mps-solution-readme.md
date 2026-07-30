# Reader-Oriented MPS Solution README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the jhzhu solution README into a concise, evidence-linked landing report for PR #218.

**Architecture:** Keep the report in one Markdown file and order it from conclusions to evidence, reproduction, and limitations. Use only committed figures and reports as links; summarize ignored pilot data numerically and label the high-statistics cluster run as ongoing.

**Tech Stack:** GitHub-flavored Markdown, existing Python command-line scripts, tracked JSON/CSV/PNG artifacts.

## Global Constraints

- Modify `tracks/mps/solutions/jhzhu/README.md`, not the repository root README.
- Write the report in English to match the repository and PR.
- Do not add raw trajectory data, credentials, hosts, or machine-specific paths.
- Name each uncertainty source explicitly; do not combine fit envelopes, bootstrap errors, and chi-systematic ranges.
- Do not claim that the Haar pilot reproduced the literature value.
- Do not present the dual-unitary `L^-4` fit as the preferred estimate.
- Do not run additional simulations or the full test suite; perform documentation-only checks.

---

### Task 1: Rewrite the solution landing report

**Files:**
- Modify: `tracks/mps/solutions/jhzhu/README.md`

**Interfaces:**
- Consumes: numerical claims and status labels from `docs/design/2026-07-30-mps-solution-readme-design.md`
- Produces: one standalone Markdown report linked from PR #218

- [x] **Step 1: Replace the metadata-only README with the approved reading order**

Use these top-level sections in this exact order:

```markdown
# Effective central charge in open quantum matter
## Executive summary
## Results at a glance
## Observable and numerical strategy
## Numerical evidence
### Clean Ising validation
### Random-bond Ising model at the Nishimori point
### Haar-circuit exact-state-vector pilot
### Dual-unitary MPS pilot
## Reproduction
## Limitations and running work
## Repository map
```

- [x] **Step 2: Add the result-status table**

Include the four completed stages with the exact labels and headline values:

```markdown
| Stage | Numerical scope | Headline estimate | Interpretation |
|---|---|---|---|
| Clean Ising | `L=8,10,12,16,20` | `c=0.4999188`, fit-envelope half-width `9.94e-5` | Validation |
| RBIM Nishimori | `L=4,5,6,8,9,10,12` | `c=0.45846`, bootstrap SE `0.00517` | Completed finite-statistics result |
| Haar circuit | 192 trajectories, `p=0.168` | `c_eff=1.559`, bootstrap SE `0.955` | Inconclusive workflow pilot |
| Dual-unitary MPS | 350 trajectories, `p=0.14`, `chi<=128` | `c_eff=0.21996`, bootstrap SE `0.04335` | MPS pilot; high-stat run pending |
```

- [x] **Step 3: Explain the shared estimator and method changes**

State the cylinder finite-size form

```text
f(L) = f_infinity - pi * alpha * c_eff / (6 L^2) + O(L^-4)
```

and distinguish matrix-free Ising transfer, quenched RBIM products, exact-state-vector Born sampling, and finite-chi MPS contraction followed by `chi -> infinity` extrapolation.

- [x] **Step 4: Add evidence, reproduction, and limitations**

Embed the two tracked figures:

```markdown
![Clean-Ising central-charge fit](../../../../results/clean_ising_transfer/central_charge_fit.png)
![RBIM Nishimori central-charge fit](../../../../results/random_bond_ising_nishimori_two_hour/central_charge_fit.png)
```

Link `docs/reports/2026-07-30-haar-mipt-checkpoint.md`, the relevant scripts and requirement files, and state that the running production grid has 400 samples per `(L,chi)`, `chi<=256`, and 5600 trajectories in 400 resumable Slurm tasks.

### Task 2: Documentation verification and PR update

**Files:**
- Verify: `tracks/mps/solutions/jhzhu/README.md`
- Verify: all relative targets linked from that README

**Interfaces:**
- Consumes: the rewritten Markdown report from Task 1
- Produces: a reviewed commit on `challenge/mps-open-criticality` and an updated PR #218

- [x] **Step 1: Scan for placeholders, accidental local paths, and credentials**

Run:

```powershell
rg -n "T[B]D|T[O]DO|C:\\|/home/|172\\.16\\.|password|passwd" tracks/mps/solutions/jhzhu/README.md
```

Expected: no matches.

- [x] **Step 2: Check formatting and relative links**

Run:

```powershell
git diff --check -- tracks/mps/solutions/jhzhu/README.md
```

Then resolve every relative Markdown target against `tracks/mps/solutions/jhzhu/` and require every local target to exist.

- [ ] **Step 3: Review the final diff and commit**

Run:

```powershell
git diff -- tracks/mps/solutions/jhzhu/README.md
git add -- tracks/mps/solutions/jhzhu/README.md docs/superpowers/plans/2026-07-30-mps-solution-readme.md
git commit -m "Rewrite MPS challenge solution report"
```

- [ ] **Step 4: Push and verify PR head**

Run:

```powershell
git push origin challenge/mps-open-criticality
```

Verify that PR #218 reports the new commit as its head.
