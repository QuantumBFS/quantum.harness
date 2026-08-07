# DFPT Channel Research Agent Implementation Plan

> Historical completed plan. The current four-channel and finite-q contract is
> specified by `../specs/2026-07-30-final-audit-fixes-design.md` and implemented
> by `2026-07-30-final-audit-fixes-implementation-plan.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a self-contained, source-traceable research agent and executable channel-resolved DFPT correction prototype for BOTS:848.

**Architecture:** A standard-library Python core separates operator decomposition, kernel correction, and scientific decision gating. Machine-readable knowledge records ground a concise Agent Skill; deterministic tests, toy examples, and an evaluation script expose both numerical invariants and unsupported scientific claims.

**Tech Stack:** Python 3 standard library, JSON-compatible YAML, `unittest`, LaTeX/latexmk for the report.

---

### Task 1: Freeze the approved design

**Files:**
- Create: `docs/superpowers/specs/2026-07-30-dfpt-channel-agent-design.md`
- Create: `docs/superpowers/plans/2026-07-30-dfpt-channel-agent-implementation-plan.md`

- [x] Save the approved architecture, interfaces, guardrails, and scope in the design file.
- [x] Scan both documents for placeholders, contradictions, ambiguous thresholds, and paths outside `BOTS-848`.

### Task 2: Specify the operator decomposition with failing tests

**Files:**
- Create: `tests/test_channel_decomposition.py`
- Create: `tests/test_invariance.py`
- Create: `src/channel_decomposition.py`

- [x] Write tests requiring exact reconstruction, traceless internal blocks, Hermitian outputs, common-shift classification, orbital-splitting classification, and local-unitary invariance.
- [x] Run `python3 -m unittest tests.test_channel_decomposition tests.test_invariance -v`; verify failure because the implementation is absent.
- [x] Implement `decompose_operator` and `channel_weights` with square/Hermitian/partition validation.
- [x] Re-run the two test modules and require zero failures.

The charge block on site `I` is `(Tr D_II / n_I) I_I`; the internal block is `D_II - D_charge,II`; the nonlocal part is the remaining off-site operator.

### Task 3: Specify correction and decision behavior with failing tests

**Files:**
- Create: `tests/test_correction_model.py`
- Create: `tests/test_decision_gate.py`
- Create: `src/correction_model.py`
- Create: `src/decision_gate.py`

- [x] Write a test requiring unit kernels to reconstruct the original operator and a second test requiring channel-specific scaling.
- [x] Write decision tests for a charge-dominated mode, an internal mode, a nonadiabatic mode, missing evidence, invalid reference states, and zero perturbations.
- [x] Run the new tests and verify that they fail because the requested functions are absent.
- [x] Implement `correct_operator` and `select_correction_level` with explicit defaults: charge-safe weight `0.80`, correction-channel weight `0.20`, and dynamic energy ratio `0.10`.
- [x] Re-run all unit tests and require zero failures.

### Task 4: Build and test the research-agent contract

**Files:**
- Create: `tests/test_agent_contract.py`
- Create: `agent/SKILL.md`
- Create: `agent/workflow.md`

- [x] Write a contract test for valid frontmatter, four claim-status labels, the four permitted decisions, source requirements, and a falsification output.
- [x] Run the contract test and verify it fails while the skill is absent.
- [x] Write a concise skill whose trigger is scientific evaluation of DFPT validity or beyond-DFPT electron-phonon corrections.
- [x] Add detailed input/output schemas and stop rules to `workflow.md`, then require the contract test to pass.

### Task 5: Add the machine-readable knowledge base

**Files:**
- Create: `knowledge/schema.yaml`
- Create: `knowledge/claims.yaml`
- Create: `knowledge/material_cases.yaml`
- Create: `knowledge/references.bib`

- [x] Encode the uniform electron gas, SrVO3 Jahn-Teller and breathing modes, CaCuO2 half/full breathing modes, CoO, and Ba1-xKxBiO3.
- [x] Attach a claim status, source ID, units, normalization note, limitation, and verification state to every numerical anchor.
- [x] Keep the quantitative DFPT-many-body matching relation labeled as literature-based numerical evidence rather than an exact Ward-identity consequence.

### Task 6: Add evaluation and examples

**Files:**
- Create: `eval/cases.yaml`
- Create: `eval/evaluate.py`
- Create: `eval/README.md`
- Create: `eval/EVALUATION.md`
- Create: `examples/toy_common_shift.yaml`
- Create: `examples/toy_orbital_splitting.yaml`
- Create: `examples/run_example.py`

- [x] Encode at least eight cases covering claim status, channel classification, citation grounding, unsupported generalization, and abstention.
- [x] Implement an evaluator that checks decision accuracy, knowledge completeness, citation coverage, and unsupported-claim rate without third-party packages.
- [x] Run both examples and the evaluator; record the actual summary in `EVALUATION.md`.

### Task 7: Package the report and reviewer entry point

**Files:**
- Replace: `README.md`
- Create: `Makefile`
- Copy: `report/main.pdf`, report source, figures, appendices, provenance, and bibliography.

- [x] Preserve team registration and `Addresses #35` while adding the research result, limitations, file map, and one-command checks.
- [x] Copy only report source and final PDF, excluding LaTeX intermediates and rendered page images.
- [x] Add `make test`, `make eval`, `make examples`, `make report`, and `make check` targets.

### Task 8: Verify and audit the submission

**Files:**
- Verify all files below `tracks/agent-kb/solutions/BOTS-848/`.

- [x] Run `make check` inside the solution and require zero failures.
- [x] Rebuild the report and check for undefined references, LaTeX errors, and overfull boxes.
- [x] Run the repository test target in an isolated local environment when dependencies are available.
- [x] Run `git status --short`, `git diff --check`, and a path-scope audit; require no edits outside `BOTS-848`.
- [x] Keep the branch local and unpushed for the team to review.
