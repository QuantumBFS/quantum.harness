# BOTS:848 Final Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every software behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the central charge-channel physics, make the executable scope honest and numerically safe, and make the complete reviewer check repeatable from a clean clone.

**Architecture:** The report uses a complete physical-to-DFPT correction ratio and separates one- and two-body vertices.  The Python MVP decomposes a Hermitian standing-wave operator into global-charge, site-charge, internal, and nonlocal channels; only an explicitly verified uniform q=0 global shift is safe.  Report builds are isolated from the distributed PDF.

**Tech Stack:** Python 3 standard library, JSON-compatible YAML, `unittest`, GNU Make, XeLaTeX/latexmk, Poppler.

---

### Task 1: Correct the physical definitions and claim boundaries

**Files:**
- Modify: `report/sections/02_dfpt_baseline.tex`
- Modify: `report/sections/03_many_body_constraints.tex`
- Modify: `report/sections/04_ueg_benchmark.tex`
- Modify: `report/sections/05_material_channels.tex`
- Modify: `report/sections/06_working_hypothesis.tex`
- Modify: `report/sections/07_next_generation_dfpt.tex`
- Modify: `report/sections/08_ai_research_program.tex`
- Modify: `report/appendices/A_derivations.tex`
- Modify: `README.md`, `RESULTS.md`, `agent/SKILL.md`, `agent/workflow.md`
- Modify: `knowledge/claims.yaml`, `knowledge/schema.yaml`, `eval/cases.yaml`

- [ ] Replace `K_rho = P/chi_s` with the complete `K_total` ratio and show that the scalar electron-gas matching gives `K_total approximately 1`.
- [ ] Separate global q=0 identity, relative site density, on-site traceless, nonlocal one-body, and two-body interaction vertices.
- [ ] State `D(q)^dagger = D(-q)` and restrict the executable Hermitian API to Gamma/real-space/standing-wave inputs.
- [ ] Define the fitted target as a convention-matched fixed-basis one-body vertex and keep external-leg quasiparticle factors outside it.
- [ ] Change “three-level gate” to the four actual outputs and classify method definitions as established rather than exact constraints.
- [ ] Run claim/wording searches and JSON parsing; require no remaining universal `K_rho = P/chi_s` prescription or ambiguous three-channel charge claim.

### Task 2: Fix channel decomposition and guarded decisions with TDD

**Files:**
- Modify: `tests/test_channel_decomposition.py`
- Modify: `tests/test_invariance.py`
- Modify: `tests/test_correction_model.py`
- Modify: `tests/test_decision_gate.py`
- Modify: `src/channel_decomposition.py`
- Modify: `src/correction_model.py`
- Modify: `src/decision_gate.py`
- Modify: `examples/toy_common_shift.yaml`, `examples/toy_orbital_splitting.yaml`, `examples/run_example.py`

- [ ] Add a failing regression test requiring `diag(1,1,-1,-1)` with two site blocks to have zero `global_charge` and unit `site_charge` weight.
- [ ] Add a failing test requiring `dfpt-safe` only when `uniform_q_zero is True`; the same weights without that evidence must abstain.
- [ ] Add failing tests rejecting NaN/Inf weights, thresholds, ratios and matrix entries, plus complex or non-finite static kernels.
- [ ] Verify the tests fail for the audited reasons.
- [ ] Implement the four-channel orthogonal decomposition and evidence gate with finite real validation.
- [ ] Re-run the focused tests and require zero failures.

### Task 3: Fix response and cost numerical contracts with TDD

**Files:**
- Modify: `tests/test_response_model.py`
- Modify: `tests/test_cost_model.py`
- Modify: `src/response_model.py`
- Modify: `src/cost_model.py`

- [ ] Add a failing regression in which the exact response coefficient is `5e-15` and prediction remains `5.0` for input `1e15`.
- [ ] Add failing tests rejecting boolean coefficients and any cost calculation whose products are non-finite.
- [ ] Verify each regression fails before production edits.
- [ ] Preserve the full finite complex response internally and encode small nonzero values without threshold truncation.
- [ ] Add finite-result checks to cost accounting and re-run focused tests.

### Task 4: Make the report build idempotent

**Files:**
- Modify: `Makefile`
- Modify: `report/Makefile`
- Create: `report/.gitignore`
- Modify: `tests/test_submission_contract.py`
- Modify: `REPRODUCE.md`, `report/README.md`

- [ ] Add a failing submission-contract test requiring reviewer builds to use `report/build/` and not overwrite `report/main.pdf`.
- [ ] Verify the test fails against the current in-place `latexmk` target.
- [ ] Build and check `build/main.pdf`; add a separate maintainer `dist` target for updating the distributed PDF.
- [ ] Document that the SHA-256 checks the distributed artifact rather than a bitwise-identical TeX rebuild.
- [ ] Run `make check-all` twice and require identical Git status after both runs.

### Task 5: Integrate, rebuild, and verify

**Files:**
- Update: `report/main.pdf`
- Update: the distributed PDF SHA-256 in `REPRODUCE.md`
- Update: completed checkboxes in this plan

- [ ] Run all focused tests, then `make check`.
- [ ] Build the report, update the distributed PDF, and record its actual SHA-256.
- [ ] Render all PDF pages and inspect for clipping, overlaps, missing glyphs, unresolved citations, and overfull boxes.
- [ ] Clone the candidate commit to a temporary directory; run `make check-all` twice and require both runs to exit zero with a clean status.
- [ ] Run `git diff --check`, path-scope audit, link/claim searches, and final scientific/software review.
- [ ] Commit with Author `Codex <codex@openai.com>` and Committer `AroundPeking <gonghuanjing@iphy.ac.cn>`, merge the fix branch into the challenge branch, verify attribution, and push to AroundPeking.
