# VQETape Innovation-First Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a reviewer-ready, self-contained VQETape delivery for Quantum Harness Issue #33 with an innovation-first technical narrative, regenerated PDF/data/text artifacts, a public standalone repository, and synchronized PR communication.

**Architecture:** Keep committed canonical benchmark JSON as the immutable evidence layer. Generate the reviewer-facing Markdown, HTML, status map, tabular data, manifest, and PDF from those sources; mirror the implementation and selected evidence into a standalone public repository; connect Issue #33, PR #263, and the showcase repository with stable links.

**Tech Stack:** Python 3.11+, JAX, TensorNetwork, TensorCircuit-NG, ReportLab, pytest, Git, GitHub CLI.

## Global Constraints

- Preserve every measured number and canonical JSON record.
- Use the approved thesis: “Compile the forward contraction, reverse program, and variational ansatz as one optimization problem.”
- Use reviewer-facing labels: Demonstrated result, Measured trade-off, Validated protocol, Next optimization frontier, Scale-up target.
- Keep raw evidence auditable while removing defensive status language from README, generated delivery artifacts, PR body, and PR comments.
- Do not expose credentials, private keys, tokens, local absolute paths, or cluster access details.
- Apply visibility changes only after the standalone repository passes its content and secret audit.
- Use Lore-formatted commits with the required `Co-authored-by` trailer.

---

## Task 1: Reframe the Canonical Reviewer Package

**Files:**
- Modify: `tracks/qcs/solutions/WangTheoPhys/issue33/README.md`
- Modify: `tracks/qcs/solutions/WangTheoPhys/issue33/scripts/build_submission_report.py`
- Regenerate: `tracks/qcs/solutions/WangTheoPhys/issue33/submission/`

- [ ] Rewrite the README opening around the differentiated co-design compiler thesis and four innovations.
- [ ] Preserve the exact RTX 3090, RTX 3080, adaptive-ansatz, correctness, and regression values.
- [ ] Rewrite generated Markdown, HTML, JSON status fields, text status map, and PDF labels using the approved result vocabulary.
- [ ] Keep the six canonical evidence files as the only numerical inputs to the report builder.
- [ ] Run the report builder and confirm it refreshes the artifact manifest.

**Verification:**

Run: `python tracks/qcs/solutions/WangTheoPhys/issue33/scripts/build_submission_report.py`

Expected: exit 0 and refreshed files under `submission/`.

## Task 2: Validate Content, Data, and PDF

**Files:**
- Verify: `tracks/qcs/solutions/WangTheoPhys/issue33/submission/vqetape-matched-benchmark.tsv`
- Verify: `tracks/qcs/solutions/WangTheoPhys/issue33/submission/report.json`
- Verify: `tracks/qcs/solutions/WangTheoPhys/issue33/submission/vqetape-technical-report.md`
- Verify: `tracks/qcs/solutions/WangTheoPhys/issue33/submission/output/pdf/vqetape-technical-report.pdf`

- [ ] Compare generated benchmark fields to canonical JSON inputs.
- [ ] Scan reviewer-facing text for defensive labels and local/private path leakage.
- [ ] Extract PDF text and confirm the headline metrics and artifact links are present.
- [ ] Render every PDF page to PNG and inspect every page for clipping, overlap, tiny text, or blank regions.
- [ ] Run the targeted report and benchmark tests, followed by the full Issue #33 regression suite.

**Verification:**

Run: `pytest -q tracks/qcs/solutions/WangTheoPhys/issue33/tests`

Expected: all executable tests pass and only the six declared structural cases remain skipped.

## Task 3: Assemble the Standalone Public Repository

**Files:**
- Modify: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/README.md`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/DELIVERY.md`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/TECHNICAL_REPORT.md`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/data/`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/output/pdf/`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/src/`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/tests/`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/scripts/`
- Add: `/Users/thomasjwang/Documents/GitHub/issue-33-extreme-efficiency-vqe/selected-evidence/`

- [ ] Copy the implementation, tests, report builder, generated data/text/PDF, and six selected canonical JSON records.
- [ ] Author a standalone README with the compiler thesis, measured anchors, architecture, quickstart, and bidirectional challenge links.
- [ ] Author `DELIVERY.md` as a compact reviewer artifact index.
- [ ] Scan tracked content and Git history for secret-like filenames, credentials, tokens, cluster aliases, and private paths.
- [ ] Run the standalone test suite and report regeneration command.
- [ ] Commit and push the standalone repository while it is still private.
- [ ] Change repository visibility to public and update its description, homepage, and topics.

## Task 4: Publish the Upstream PR Delivery

**Files:**
- Commit: `tracks/qcs/solutions/WangTheoPhys/issue33/**`
- Update: `QuantumBFS/quantum.harness#263` body
- Update: PR comment `5124997441`
- Add: final PR delivery comment tagging `@fliingelephant`

- [ ] Review the exact staged diff and confirm only Issue #33 delivery files changed.
- [ ] Commit and push branch `codex/issue-33-vqetape` to the fork.
- [ ] Rewrite the PR body with the thesis, four innovations, exact quantitative anchors, verification, and public artifact links.
- [ ] Convert the existing GPU comment into a positive precision-aware co-design milestone.
- [ ] Add one final delivery comment tagging `@fliingelephant` and linking the PDF, data/text report, code, and standalone public repository.

## Task 5: Remote Completion Audit

- [ ] Confirm the PR is open, mergeable, non-draft, and points at the pushed head commit.
- [ ] Confirm the standalone repository is public and its default branch contains README, delivery guide, report, data, PDF, source, tests, scripts, and evidence.
- [ ] Confirm all raw GitHub links return successfully and the PDF is downloadable.
- [ ] Confirm the final PR body and both comments show the intended positive narrative and exact evidence.
- [ ] Record final commit SHAs, URLs, test counts, and delivery status for handoff.
