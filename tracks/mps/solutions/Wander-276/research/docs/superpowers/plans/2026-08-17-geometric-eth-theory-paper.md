# Geometric ETH Theory Paper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Formulate and test a gauge-covariant Geometric-ETH theory for exactly degenerate quantum-state bundles, derive an effective-channel cumulant law, validate it in a new chiral-index kernel ensemble, and connect the result to source-verified BPS, SYK, super-JT, and black-hole microstate literature.

**Architecture:** The paper is gated by theory rather than prose. A task-local analytic module proves cumulant scaling for weighted independent response channels and records the response-algebra irreducibility criterion; a new chiral rectangular-kernel model supplies a prospective exact-degeneracy test; archival condensed-matter and SYK data provide a clearly labelled cross-model comparison. Only a passed theorem-and-prediction gate enables a research manuscript titled *The Geometric ETH*.

**Tech Stack:** Python 3.14, NumPy, SciPy, SymPy where symbolic checks are useful, Matplotlib, pytest, REVTeX 4.2, latexmk, BibTeX, DOI/arXiv/OpenAlex metadata, pdftotext, pdfinfo, pdftoppm.

## Global Constraints

- Execute only after Paper I has a frozen evidence registry and stable claim boundary.
- Work on branch codex/two-paper-geometric-eth in the isolated v12-delivery worktree.
- Store theory code under 01_task_folder/task_05/script/lgeth/ and v14 runners under 01_task_folder/task_05/script/.
- Store generated theory artifacts under 01_task_folder/task_05/script/output/geometric_eth_theory_v14/.
- Store manuscript sources under overleaf_sync/geometric_eth_theory/.
- Do not alter v1--v13 files or import prose from Paper I.
- The title *The Geometric ETH* is enabled only if the theory gate, exact chiral-kernel gate, sealed prediction gate, and at least one quantitative validation gate pass.
- If the theory gate fails, produce a bounded theory note titled *Geometric Response of Exactly Degenerate Quantum State Bundles* and record the failed gate; do not soften thresholds after seeing data.
- Distinguish conventional ETH, thermalization, spectral chaos, projector geometry, and BPS protection throughout.
- Use a complete real-augmented covariance or equivalent covariance-plus-pseudocovariance representation for complex response variables.
- Treat the response-algebra commutant criterion as necessary for full matrix mixing, not sufficient for ETH.
- Treat \(N_{\mathrm{eff}}\) scaling as a derived prediction only within its channel-independence assumptions.
- Verify all literature claims from primary sources. The named work involving Lingxin Kong, Hao Geng, Yikun Jiang, and “it from ETH” must be identified by exact bibliographic record before it enters prose.
- New tests may not depend on PyYAML because the current project-owned Python environment does not provide it.
- Update task and main dashboards with stamped entries for every theory, numerical, manuscript, and delivery milestone.

---

## File map

### Literature and theory specification

- Create: docs/literature/2026-08-17-geometric-eth-bps-black-hole-audit.md
- Create: docs/plans/2026-08-17-geometric-eth-theorem-specification.md
- Create: 01_task_folder/task_05/script/lgeth/geometric_eth_channel_theory.py
- Create: 01_task_folder/task_05/script/tests/test_geometric_eth_channel_theory_v14.py
- Create: 01_task_folder/task_05/script/derive_geometric_eth_channel_theory_v14.py
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/channel_theory_v14.json

### New chiral-index benchmark

- Create: 01_task_folder/task_05/script/lgeth/chiral_kernel_parent.py
- Create: 01_task_folder/task_05/script/run_chiral_kernel_geometric_eth_v14.py
- Create: 01_task_folder/task_05/script/seal_chiral_kernel_prediction_v14.py
- Create: 01_task_folder/task_05/script/analyze_chiral_kernel_geometric_eth_v14.py
- Create: 01_task_folder/task_05/script/tests/test_chiral_kernel_parent_v14.py
- Create: 01_task_folder/task_05/script/tests/test_chiral_kernel_runner_v14.py
- Create: 01_task_folder/task_05/script/tests/test_chiral_kernel_analysis_v14.py
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/chiral_prediction_v14.json
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/chiral_prediction_v14.sha256
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/chiral_outcomes_v14.json
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/chiral_inference_v14.json

### Cross-model theory test

- Create: 01_task_folder/task_05/script/analyze_geometric_eth_effective_channels_v14.py
- Create: 01_task_folder/task_05/script/tests/test_geometric_eth_effective_channels_v14.py
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/effective_channel_inference_v14.json
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/theory_gate_v14.json

### Figures and manuscript

- Create: 01_task_folder/task_05/script/make_geometric_eth_theory_figures_v14.py
- Create: 01_task_folder/task_05/script/tests/test_geometric_eth_theory_figures_v14.py
- Create: overleaf_sync/geometric_eth_theory/main.tex
- Create: overleaf_sync/geometric_eth_theory/supplement.tex
- Create: overleaf_sync/geometric_eth_theory/references.bib
- Create: overleaf_sync/geometric_eth_theory/generated/results_v14.tex
- Create: overleaf_sync/geometric_eth_theory/generated/protection_classes_v14.tex
- Create: overleaf_sync/geometric_eth_theory/figures/figure_1_eth_to_bundle_v14.pdf
- Create: overleaf_sync/geometric_eth_theory/figures/figure_2_response_algebra_v14.pdf
- Create: overleaf_sync/geometric_eth_theory/figures/figure_3_covariance_closure_v14.pdf
- Create: overleaf_sync/geometric_eth_theory/figures/figure_4_topology_statistics_v14.pdf
- Create: overleaf_sync/geometric_eth_theory/figures/figure_5_bps_comparison_v14.pdf
- Create: overleaf_sync/geometric_eth_theory/figures/figure_6_effective_channel_test_v14.pdf
- Create: overleaf_sync/geometric_eth_theory/sections/01_eth_failure.tex
- Create: overleaf_sync/geometric_eth_theory/sections/02_bundle_geometry.tex
- Create: overleaf_sync/geometric_eth_theory/sections/03_geometric_eth_ansatz.tex
- Create: overleaf_sync/geometric_eth_theory/sections/04_channel_theorem.tex
- Create: overleaf_sync/geometric_eth_theory/sections/05_protection_classes.tex
- Create: overleaf_sync/geometric_eth_theory/sections/06_chiral_test.tex
- Create: overleaf_sync/geometric_eth_theory/sections/07_bps_black_holes.tex
- Create: overleaf_sync/geometric_eth_theory/sections/08_topology.tex
- Create: overleaf_sync/geometric_eth_theory/sections/09_predictions.tex
- Create: overleaf_sync/geometric_eth_theory/sections/10_discussion.tex

### Verification

- Create: 01_task_folder/task_05/script/verify_geometric_eth_theory_v14.py
- Create: 01_task_folder/task_05/script/run_geometric_eth_theory_delivery_v14.sh
- Create: 01_task_folder/task_05/script/tests/test_geometric_eth_theory_manuscript_v14.py
- Create: 01_task_folder/task_05/script/tests/test_geometric_eth_theory_delivery_v14.py
- Create: 01_task_folder/task_05/script/output/geometric_eth_theory_v14/delivery_audit_v14.json
- Create conditionally after the title gate: 01_task_folder/task_05/script/output/the_geometric_eth_v14.pdf

---

### Task 1: Build the primary-source literature audit

**Files:**
- Create: docs/literature/2026-08-17-geometric-eth-bps-black-hole-audit.md
- Create: overleaf_sync/geometric_eth_theory/references.bib
- Create: 01_task_folder/task_05/script/tests/test_geometric_eth_theory_manuscript_v14.py

**Interfaces:**
- Consumes: docs/paper-summary.md, existing SYK/cohomology literature notes, lib/references.bib, and primary web records.
- Produces: a markdown table with fields citation_key, exact_title, authors, year, DOI_or_arXiv, primary_claim, section_role, and verified_date; a deduplicated BibTeX file using the same keys.

- [ ] **Step 1: Write the audit-contract test**

~~~python
def test_black_hole_audit_contract():
    text = AUDIT.read_text()
    for field in ["citation_key", "exact title", "authors", "primary claim", "section role"]:
        assert field in text.lower()
    assert "Lingxin Kong" in text
    assert "Hao Geng" in text
    assert "Yikun Jiang" in text
    assert "to be verified" not in text.lower()
~~~

- [ ] **Step 2: Verify failure**

Expected: FAIL because the audit and theory bibliography do not exist.

- [ ] **Step 3: Search and verify exact records**

Search official journal, DOI, and arXiv records for conventional ETH, subsystem ETH or code-subspace ETH, BPS chaos, fortuity, non-Abelian Berry curvature in BPS multiplets, \(\mathcal N=2\) SYK, super-JT, moduli-space topology, and the exact work referred to as “it from ETH.” For each source, record only the claim directly supported by the primary paper. If a named-author query does not resolve to a unique paper, exclude it and record the ambiguity outside the manuscript.

- [ ] **Step 4: Build BibTeX and run the audit test**

Require at least 35 verified primary records, zero duplicate DOI/arXiv identifiers, and exact author spelling from metadata.

- [ ] **Step 5: Commit**

Commit audit, bibliography, and test with message docs: audit geometric ETH gravity sources.

### Task 2: Freeze the theorem specification

**Files:**
- Create: docs/plans/2026-08-17-geometric-eth-theorem-specification.md
- Create: 01_task_folder/task_05/script/tests/test_geometric_eth_channel_theory_v14.py

**Interfaces:**
- Consumes: the approved two-paper design.
- Produces: a precise theorem statement for weighted independent response channels and a separate proposition for response-algebra irreducibility.

- [ ] **Step 1: Write theorem-specification tests**

Require the specification to define centered channel variables \(Y_\alpha\), normalized weights \(w_\alpha\), \(Z=\sum_\alpha w_\alpha Y_\alpha\), ordinary and pseudocovariance, connected cumulants, \(N_{\mathrm{eff}}=(\sum_\alpha w_\alpha^2)^2/\sum_\alpha w_\alpha^4\), assumptions, conclusion, and failure cases.

- [ ] **Step 2: Verify failure**

Expected: FAIL because the specification is absent.

- [ ] **Step 3: Write the result-independent theorem specification**

State and prove at the specification level that independent centered channels give

$$\kappa_k(Z)=\sum_\alpha w_\alpha^k\kappa_k(Y_\alpha),$$

and, after variance normalization with comparable channel cumulants, the fourth connected contribution is controlled by

$$\sum_\alpha w_\alpha^4=\frac{1}{N_{\mathrm{eff}}}.$$

State separately that a scalar commutant of \(\mathcal A_X\) implies irreducibility over the complex fiber through Burnside's theorem, while irreducibility alone does not imply Gaussianity or ETH.

- [ ] **Step 4: Record falsification branches**

The specification must name correlated channels, heavy-tailed channels without fourth moments, growing single-channel dominance, symmetry-unresolved blocks, nonstationary tangent ensembles, and closing external gap as explicit failure branches.

- [ ] **Step 5: Commit**

Commit with message docs: specify effective channel theorem.

### Task 3: Implement and verify the effective-channel theorem

**Files:**
- Create: 01_task_folder/task_05/script/lgeth/geometric_eth_channel_theory.py
- Create: 01_task_folder/task_05/script/derive_geometric_eth_channel_theory_v14.py
- Modify: test_geometric_eth_channel_theory_v14.py
- Create: channel_theory_v14.json

**Interfaces:**
- Produces: normalize_weights(weights: ndarray) -> ndarray; effective_channel_number(weights: ndarray) -> float; predicted_cumulant_scale(weights: ndarray, channel_kappa4: ndarray) -> float; commutant_dimension(matrices: list[ndarray], tolerance: float) -> int; and run_theory_audit() -> dict.

- [ ] **Step 1: Write analytic unit tests**

~~~python
def test_equal_weight_effective_channels():
    for count in (2, 8, 32):
        w = normalize_weights(np.ones(count))
        assert effective_channel_number(w) == pytest.approx(count)
        assert np.sum(w**4) == pytest.approx(1.0 / count)

def test_scalar_commutant_for_irreducible_pair():
    sx = np.array([[0, 1], [1, 0]], complex)
    sz = np.array([[1, 0], [0, -1]], complex)
    assert commutant_dimension([sx, sz], 1e-12) == 1
~~~

- [ ] **Step 2: Verify failure**

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement analytic functions and Monte Carlo oracle**

Use an SVD nullspace of the stacked commutator superoperators for commutant_dimension. Add a deterministic Monte Carlo oracle using non-Gaussian centered complex channel matrices to verify the \(1/N_{\mathrm{eff}}\) fourth-cumulant law over equal and unequal weights without fitting an exponent.

- [ ] **Step 4: Generate the theory audit**

Require exact algebraic checks, Monte Carlo coverage at channel counts 4, 8, 16, 32, 64, and a fixed maximum relative error of 0.08 for the normalized fourth-cumulant prediction. Record seeds, draws, and uncertainty in channel_theory_v14.json.

- [ ] **Step 5: Commit**

Commit module, runner, tests, and audit with message feat: derive geometric ETH channel law.

### Task 4: Implement the chiral-index exact-degeneracy model

**Files:**
- Create: 01_task_folder/task_05/script/lgeth/chiral_kernel_parent.py
- Create: 01_task_folder/task_05/script/tests/test_chiral_kernel_parent_v14.py

**Interfaces:**
- Produces: build_chiral_hamiltonian(T: ndarray) -> ndarray; zero_mode_frame(T: ndarray, tolerance: float) -> ndarray; chiral_response(T: ndarray, dT: ndarray) -> ndarray; and audit_chiral_case(n_a: int, n_b: int, seed: int) -> dict.

- [ ] **Step 1: Write exact-index tests**

For complex full-row-rank \(T\in\mathbb C^{n_b\times n_a}\) with \(n_a>n_b\), require the block Hamiltonian to anticommute with the chiral matrix, have exactly \(D=n_a-n_b\) zero modes, positive external gap equal to the smallest singular value of \(T\), and a response matching a centered finite difference of the projector.

- [ ] **Step 2: Verify failure**

Expected: FAIL because the chiral parent module is absent.

- [ ] **Step 3: Implement the dense exact backend**

Use SVD for rank and zero-mode frames. Construct the full chiral Hamiltonian only in tests; compute production response from the rectangular factor and reduced singular-system formulas. Return explicit residual, orthonormality, chiral-symmetry, gap, response, and gauge-covariance checks.

- [ ] **Step 4: Add structured and random tangent classes**

Implement iid complex tangents, bandwidth-limited one-dimensional tangents, and a repeated-cell structured tangent. Use the same Frobenius normalization and channel count across classes.

- [ ] **Step 5: Commit**

Commit with message feat: add chiral index kernel geometry.

### Task 5: Seal and execute the prospective chiral scaling test

**Files:**
- Create: seal_chiral_kernel_prediction_v14.py
- Create: run_chiral_kernel_geometric_eth_v14.py
- Create: test_chiral_kernel_runner_v14.py
- Create: chiral_prediction_v14.json and .sha256
- Create: chiral_outcomes_v14.json

**Interfaces:**
- Consumes: channel_theory_v14.json and the chiral parent module.
- Produces: a prediction sealed before outcomes and a deterministic production grid.

- [ ] **Step 1: Write seal-order and leakage tests**

Require sizes \((n_b,n_a)=(16,24),(24,36),(32,48),(48,72),(64,96),(96,144)\), 64 independent base matrices per size, 16 tangents per base, fixed development sizes through \(n_b=32\), sealed validation sizes 48, 64, 96, and separate random/local/structured seeds. The prediction JSON may contain thresholds and hashes but no observed fourth cumulant.

- [ ] **Step 2: Verify failure**

Expected: FAIL because the seal and runner are absent.

- [ ] **Step 3: Write and hash the prediction**

Freeze the primary prediction: random-channel covariance-whitened fourth residual multiplied by \(N_{\mathrm{eff}}\) remains within the development-derived simultaneous 95% band at all three validation sizes; the local and repeated-cell controls are not required to enter that band. Freeze the branch precedence before production.

- [ ] **Step 4: Run production after the seal exists**

The runner must refuse to start if source hashes or the prediction hash differ. Save per-realization safe covariates separately from outcome tensors, then aggregate only after all registered cases pass rank, gap, finite-difference, gauge, and reproducibility checks.

- [ ] **Step 5: Commit**

Commit seal, runner, tests, and split outputs with message feat: run sealed chiral kernel test.

### Task 6: Analyze the chiral and archival cross-model evidence

**Files:**
- Create: analyze_chiral_kernel_geometric_eth_v14.py
- Create: analyze_geometric_eth_effective_channels_v14.py
- Create: test_chiral_kernel_analysis_v14.py
- Create: test_geometric_eth_effective_channels_v14.py
- Create: chiral_inference_v14.json
- Create: effective_channel_inference_v14.json
- Create: theory_gate_v14.json

**Interfaces:**
- Produces: evaluate_chiral_prediction(prediction: dict, outcomes: dict) -> dict and evaluate_theory_gate(channel_theory: dict, chiral: dict, archival: dict) -> dict.

- [ ] **Step 1: Write branch-precedence tests**

The analysis must select exactly one of channel_law_validated, deformed_locality_class, random_channel_failure, or feasibility_failure. A failed exact-index or seal-order gate has precedence over a favorable statistic.

- [ ] **Step 2: Implement uncertainty and archival mapping**

Use base-matrix bootstrap for the chiral ensemble. For archival data, compute \(N_{\mathrm{eff}}\) only from stored response covariances with documented independent units. Label the comparison retrospective and exclude any model lacking the required covariance arrays rather than imputing values.

- [ ] **Step 3: Evaluate the theory gate**

The title gate passes only if the analytic audit passes, the random chiral validation passes without refitting, at least one structured control separates from the random law, all exact-degeneracy gates pass, and the manuscript can state one quantitative prediction. Archival agreement is supporting evidence, not mandatory universality.

- [ ] **Step 4: Run corruption tests**

Reject altered prediction timestamps, source hashes, missing validation sizes, post-outcome threshold edits, and a theory-gate result inconsistent with its component gates.

- [ ] **Step 5: Commit**

Commit analysis, tests, and inference artifacts with message feat: test geometric ETH channel prediction.

### Task 7: Generate the six theory figures

**Files:**
- Create: make_geometric_eth_theory_figures_v14.py
- Create: test_geometric_eth_theory_figures_v14.py
- Create: six vector PDFs, six previews, and a figure manifest.

**Interfaces:**
- Consumes: theorem audit, chiral inference, archival inference, Paper I's frozen evidence registry, and the primary-source literature audit.
- Produces: make_all_figures(repo_root: Path) -> dict with source and output hashes.

- [ ] **Step 1: Write figure-contract tests**

Require the six exact filenames in the file map, 7.0-inch canonical width, 300-dpi previews, panel labels, source hashes, and a distinction between data panels and conceptual diagrams.

- [ ] **Step 2: Implement Figures 1--4**

Draw the ETH-to-bundle mapping, response-algebra classification, covariance/Wick hierarchy, and \(U(1)\)-versus-\(SU(D)\) topology schematic from equations and registry categories. Do not use decorative network imagery.

- [ ] **Step 3: Implement Figure 5 from verified sources**

Build a comparison table/diagram whose text is generated from the literature audit. Each BPS/black-hole row must cite a verified key and distinguish observation, calculation, and conjecture.

- [ ] **Step 4: Implement Figure 6 from inference data**

Plot the sealed chiral \(N_{\mathrm{eff}}\) prediction and validation sizes, with local/structured controls and simultaneous intervals. Add archival points only where the covariance mapping is valid and label them by mechanism.

- [ ] **Step 5: Inspect and commit**

Render at original size, check mathematical glyphs and legends, then commit with message feat: draw geometric ETH theory figures.

### Task 8: Scaffold the result-gated REVTeX manuscript

**Files:**
- Create: main.tex, supplement.tex, ten section files, generated/results_v14.tex, and protection_classes_v14.tex.
- Create: test_geometric_eth_theory_manuscript_v14.py

**Interfaces:**
- Consumes: theory_gate_v14.json.
- Produces: a REVTeX PRD/PRB-compatible project whose title is selected by the gate.

- [ ] **Step 1: Write title-gate tests**

If theory_gate_v14.json passes, require the title *The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles*. If it fails, require *Geometric Response of Exactly Degenerate Quantum State Bundles* and reject the phrase “we establish Geometric ETH.”

- [ ] **Step 2: Verify failure**

Expected: FAIL because the manuscript project is absent.

- [ ] **Step 3: Create the modular source tree**

Use REVTeX 4.2 and the ten section inputs from the file map. Input generated results and protection-class table. Include six figure environments and a separate supplement with theorem derivations, covariance conventions, chiral construction, and full literature table.

- [ ] **Step 4: Compile the empty-shell project**

Require latexmk success and resolved labels before prose writing.

- [ ] **Step 5: Commit**

Commit with message docs: scaffold geometric ETH theory paper.

### Task 9: Write the ETH, bundle, ansatz, and theorem sections

**Files:**
- Modify: sections/01_eth_failure.tex through sections/04_channel_theorem.tex.
- Modify: supplement.tex and theorem appendices.
- Modify: test_geometric_eth_theory_manuscript_v14.py

**Interfaces:**
- Consumes: theorem specification and channel_theory_v14.json.
- Produces: a self-contained definition and proof path.

- [ ] **Step 1: Add semantic equation tests**

Require the conventional ETH ansatz, projector bundle, QGT and curvature, trace/traceless split, complete covariance and pseudocovariance, weak/strong/deformed definitions, cumulant-additivity theorem, \(N_{\mathrm{eff}}\), and commutant proposition.

- [ ] **Step 2: Write the sections in logical order**

State precisely which part of conventional ETH is being generalized and which is not. Define the ensemble before stating convergence. Separate exact theorem, random-channel model, conjectural extension, and numerical test with explicit textual labels.

- [ ] **Step 3: Write the proof appendix**

Give cumulant-additivity and weighted-channel derivations, the relation to covariance eigenvalues, and the commutant linear-system construction. State every independence and finite-moment assumption.

- [ ] **Step 4: Compile and check notation**

Search for symbol collisions and verify all variables are defined before use.

- [ ] **Step 5: Commit**

Commit with message docs: formulate and derive geometric ETH.

### Task 10: Write protection classes and the chiral prediction test

**Files:**
- Modify: sections/05_protection_classes.tex
- Modify: sections/06_chiral_test.tex
- Modify: generated/protection_classes_v14.tex
- Modify: test_geometric_eth_theory_manuscript_v14.py

**Interfaces:**
- Consumes: protection mechanism registry, chiral inference, and Figure 6.
- Produces: the theory-to-model bridge and the new independent test.

- [ ] **Step 1: Add mechanism and result tests**

Require common-kernel, cohomological, stabilizer, chiral/index, symmetry, and integrable classes; require exact nullity \(D=n_a-n_b\), gap conditions, prediction-seal order, validation sizes, selected branch, and control behavior.

- [ ] **Step 2: Write the protection-class analysis**

For each class identify what fixes \(D\), what moves \(P\), expected response-algebra commutant, and what breaks exactness. Do not claim that mechanism classification alone predicts a random-matrix class.

- [ ] **Step 3: Write the sealed chiral result**

Present the analytic prediction before the observed validation. Report both positive and negative branches exactly as selected by the inference JSON. Keep archival comparisons separate from the prospective chiral result.

- [ ] **Step 4: Compile and inspect Figures 2 and 6**

Ensure the theory diagram and quantitative test are readable without referring to Paper I.

- [ ] **Step 5: Commit**

Commit with message docs: test geometric ETH in chiral kernels.

### Task 11: Write the BPS, black-hole, topology, and prediction sections

**Files:**
- Modify: sections/07_bps_black_holes.tex through sections/10_discussion.tex.
- Modify: main.tex abstract.
- Modify: test_geometric_eth_theory_manuscript_v14.py

**Interfaces:**
- Consumes: verified literature audit, Figures 4--5, Paper I frozen evidence registry, and theory gate.
- Produces: a source-grounded gravitational application and bounded conclusion.

- [ ] **Step 1: Add citation-proximity and claim-boundary tests**

Require primary citations near claims about smooth/horizonless curvature, super-JT, SYK, fortuity, large Chern numbers, and black-hole microstates. Reject unsupported phrases “black holes satisfy Geometric ETH,” “universal,” “thermalization of BPS states,” and “proves the horizon.”

- [ ] **Step 2: Write the BPS comparison by mechanism**

Organize the section by protection, response algebra, curvature statistics, higher cumulants, and topology. Use the smooth/horizonless versus black-hole-like contrast only where a primary calculation supports it. Identify extrapolations from Paper I as conjectures.

- [ ] **Step 3: Write topology and predictions**

Separate integrated trace curvature from local traceless statistics. State model-specific falsification tests with observable, ensemble, size variable, and failure branch.

- [ ] **Step 4: Write the abstract and discussion last**

The abstract states the theorem, new chiral test, and bounded gravitational implication. The discussion distinguishes research result from programmatic conjecture and names the assumptions under which \(N_{\mathrm{eff}}\) is the correct variable.

- [ ] **Step 5: Commit**

Commit with message docs: connect geometric ETH to protected black hole sectors.

### Task 12: Citation, prose, compilation, and delivery audit

**Files:**
- Create: verify_geometric_eth_theory_v14.py
- Create: run_geometric_eth_theory_delivery_v14.sh
- Create: test_geometric_eth_theory_delivery_v14.py
- Create: delivery_audit_v14.json and gated final PDF.
- Modify: task_05_dashboard.md and 00_main/main_dashboard.md.

**Interfaces:**
- Consumes: complete theory artifacts, source audit, figures, manuscript, and theory gate.
- Produces: verify_theory_delivery(repo_root: Path) -> dict and deterministic archived PDFs.

- [ ] **Step 1: Write fail-closed corruption tests**

Reject a false title gate, altered prediction seal, missing primary citation, unsupported gravitational claim, changed theorem hash, missing figure source, undefined reference, overfull box, mismatched archived PDF, and repeated verification that rewrites an unchanged audit.

- [ ] **Step 2: Perform the human-style prose audit**

Remove formulaic transitions, repetitive section summaries, marketing language, unexplained analogies, and literature name-dropping. Preserve technical qualifications, first-person authorship where natural, and explicit distinctions among result, consistency, suggestion, and conjecture.

- [ ] **Step 3: Implement and run the delivery pipeline**

The pipeline runs theory and chiral tests, verifies seal order, regenerates macros and figures, compiles main and supplement, validates citations, checks logs, archives PDFs conditionally on the title gate, renders every page, and writes a source-hashed audit. It contains no journal upload or remote push.

- [ ] **Step 4: Inspect all rendered pages**

Check equations, multi-column figures, literature table, citations, and page breaks at 180 and 300 dpi. Record page hashes and visual verdicts.

- [ ] **Step 5: Synchronize dashboards and run focused tests**

Append stamped v14 entries, place the most important result figure in the task Canvas, retain ongoing status, and run all v14 focused tests in one command.

- [ ] **Step 6: Commit**

Commit all v14 sources, theory code, sealed calculations, figures, PDFs, audits, and dashboards with message deliver: geometric ETH theory paper.

## Self-review

- Spec coverage: Tasks 1--12 cover exact literature identification, a theorem specification, executable analytic checks, a new exact-degeneracy mechanism, prospective sealing, quantitative inference, six figures, ten manuscript sections, primary-source gravitational integration, prose audit, and fail-closed delivery.
- Independent contribution: the weighted-channel cumulant theorem, response-algebra criterion, and sealed chiral-index test are not repetitions of Paper I.
- Result dependence: a failed theory or chiral gate changes the title and claim automatically; no task instructs the writer to conceal a negative outcome.
- Interface consistency: channel_theory_v14.json fixes the prediction; the sealed chiral runner produces outcomes; the inference files determine theory_gate_v14.json; that gate determines the manuscript title and delivery filename.
- Placeholder scan: exact bibliographic records are produced through a verified audit task, and every unresolved scientific condition maps to an explicit failure branch rather than deferred prose.
