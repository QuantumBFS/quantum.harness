# Issue #133 Five-New-Problem Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish five new human-supervised problems and five exact solved-gate receipts in the public #209 capsule.

**Architecture:** A deterministic Solver emits certificates but never verdicts.  A separate standard-library Verifier CLI derives every verdict from frozen challenge and gate documents in fresh subprocesses; the runner publishes all bindings, negative controls, decisions, receipts, and checksums.

**Tech Stack:** Python 3 standard library, JSON, SHA-256, `unittest`.

## Global Constraints

- Edit only `tracks/agent-kb/solutions/WangTheoPhys/`.
- Count five new problems; never count #124--#128 calibration items.
- Use exact integer/rational arithmetic and fail closed.
- Record `human.junkaiwang` as `human expert supervision`.
- Leave refereed publications at `0` and upstream catalog determination pending.

---

### Task 1: Freeze and solve five new problems

**Files:**
- Create: `issue133-campaign/campaign_solver.py`
- Test: `issue133-campaign/tests/test_campaign.py`

**Interfaces:**
- Produces: `frozen_challenges()`, `solve_challenge()`, and `negative_control()`.

- [ ] Define five immutable challenge records and canonical digests.
- [ ] Emit deterministic exact certificates without acceptance claims.
- [ ] Emit one essential corruption for every certificate type.

### Task 2: Independently verify every gate

**Files:**
- Create: `issue133-campaign/campaign_verifier.py`
- Test: `issue133-campaign/tests/test_campaign.py`

**Interfaces:**
- Consumes: one challenge, one separately frozen gate, and one certificate.
- Produces: an exact derived acceptance record or exit code `3`.

- [ ] Check all challenge, gate, and certificate identity bindings.
- [ ] Derive rank, global contraction optimum, spectrum, and gauge equations.
- [ ] Prove all five positives pass and all five corruptions fail.

### Task 3: Publish the evidence graph

**Files:**
- Create: `issue133-campaign/run_campaign.py`
- Create: `issue133-campaign/README.md`
- Generate: `issue133-campaign/artifacts/**`

**Interfaces:**
- Consumes: Solver and Verifier source identities.
- Produces: five challenge/gate/certificate/negative/acceptance/receipt sets, `campaign.json`, `REPORT.md`, and `SHA256SUMS.txt`.

- [ ] Materialize all challenges and gates before solving.
- [ ] Execute each positive and negative gate in a fresh subprocess.
- [ ] Bind the authorized human decision and exact verifier result.
- [ ] Generate the campaign manifest, table, and checksums deterministically.

### Task 4: Integrate and deliver PR #209

**Files:**
- Modify: `README.md`
- Modify: PR #209 body

**Interfaces:**
- Consumes: public campaign manifest and receipt digests.
- Produces: a five-row acceptance/solve table and one-command replay surface.

- [ ] Run direct tests, replay generation, checksum verification, Ruff, and diff checks.
- [ ] Commit and push the submission branch.
- [ ] Update PR #209 with five rows and exact replay commands.
