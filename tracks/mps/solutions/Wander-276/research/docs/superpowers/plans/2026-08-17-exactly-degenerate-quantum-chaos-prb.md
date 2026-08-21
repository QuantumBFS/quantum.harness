# Exactly Degenerate Quantum Chaos PRB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Produce a self-contained 14--18 page PRB manuscript, Supplemental Material, seven-figure evidence package, and fail-closed delivery audit for *Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe* without modifying the audited v1--v12 artifacts.

**Architecture:** Build a v13 evidence registry from immutable task outputs, generate all numerical macros and tables from that registry, assemble verified copies or explicitly regenerated versions of seven logical figures, and write a modular REVTeX manuscript whose claim language is checked against the evidence matrix. The build is additive: the existing cross-mechanism v12 source and PDFs remain byte unchanged.

**Tech Stack:** Python 3.14, NumPy, SciPy, Matplotlib, pytest, REVTeX 4.2, latexmk, BibTeX, pdftotext, pdfinfo, pdftoppm.

## Global Constraints

- Work on branch codex/two-paper-geometric-eth in the isolated worktree /Users/thomasjwang/Documents/GitHub/Chaos-of-Quantum-Geometry-v12-delivery.
- Use apply_patch for source edits; formatting and LaTeX compilation commands may write generated files.
- Do not modify any file whose basename ends in v1 through v12.
- Store new manuscript sources under overleaf_sync/exactly_degenerate_quantum_chaos_prb/.
- Store new generated artifacts under 01_task_folder/task_05/script/output/paper1_prb_v13/ and use the v13 suffix.
- Generate every empirical number in LaTeX from audited JSON or NPZ input; do not type empirical values directly into prose.
- Preserve the canonical definitions of the non-Abelian connection, QGT, metric, and curvature from AGENTS.md.
- Keep Paper I's strongest conclusion finite-size and mechanism dependent; the verifier must reject “universal Geometric ETH,” “asymptotic Geometric ETH is established,” “thermalization,” and “Lyapunov” as positive claims.
- Use primary sources for technical claims and verify every new citation before final delivery.
- Canonical figures are vector PDF; every figure also has a 300-dpi PNG preview.
- The current system Python lacks PyYAML. New v13 tests may not introduce a YAML dependency. Run the v13 focused suite independently of the historical release-contract test until a project-owned environment supplies PyYAML.
- Update task_05_dashboard.md and 00_main/main_dashboard.md whenever sources, figures, PDFs, or conclusions change.

---

## File map

### Evidence and generated assets

- Create: 01_task_folder/task_05/script/build_paper1_evidence_registry_v13.py
- Create: 01_task_folder/task_05/script/make_paper1_prb_assets_v13.py
- Create: 01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json
- Create: 01_task_folder/task_05/script/output/paper1_prb_v13/figure_manifest_v13.json
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated/results_v13.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated/evidence_matrix_v13.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated/model_table_v13.tex

### Figures

- Create: 01_task_folder/task_05/script/make_paper1_protection_mixing_figure_v13.py
- Create: 01_task_folder/task_05/script/make_paper1_evidence_figures_v13.py
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_1_protection_mixing_v13.pdf
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_2_spectral_silence_v13.pdf
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_3_geometric_hierarchy_v13.pdf
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_4_independent_channels_v13.pdf
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_5_wick_parent_dependence_v13.pdf
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_6_fixed_chern_holonomy_v13.pdf
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_7_cross_mechanism_v13.pdf

### Manuscript

- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/main.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/supplement.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/references.bib
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/01_introduction.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/02_protected_response.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/03_statistics.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/04_models.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/05_laughlin_results.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/06_topology.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/07_cohomology.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/08_stabilizer.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/09_classification.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/10_discussion.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/supplement_methods.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/sections/supplement_numerics.tex

### Verification

- Create: 01_task_folder/task_05/script/verify_paper1_prb_v13.py
- Create: 01_task_folder/task_05/script/run_paper1_prb_delivery_v13.sh
- Create: 01_task_folder/task_05/script/tests/test_paper1_evidence_registry_v13.py
- Create: 01_task_folder/task_05/script/tests/test_paper1_figures_v13.py
- Create: 01_task_folder/task_05/script/tests/test_paper1_manuscript_v13.py
- Create: 01_task_folder/task_05/script/tests/test_paper1_delivery_v13.py
- Create: 01_task_folder/task_05/script/output/paper1_prb_v13/delivery_audit_v13.json
- Create: 01_task_folder/task_05/script/output/exactly_degenerate_quantum_chaos_prb_v13.pdf
- Create: 01_task_folder/task_05/script/output/exactly_degenerate_quantum_chaos_supplement_v13.pdf

---

### Task 1: Freeze the v13 project contract

**Files:**
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/main.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/supplement.tex
- Create: 01_task_folder/task_05/script/tests/test_paper1_manuscript_v13.py

**Interfaces:**
- Consumes: the approved design at docs/plans/2026-08-17-two-paper-geometric-eth-design.md.
- Produces: a REVTeX project with section inputs, generated-input paths, seven figure slots, and a separate supplement.

- [ ] **Step 1: Write the project-contract test**

~~~python
def test_prb_project_contract():
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    main = (root / "main.tex").read_text()
    assert r"\documentclass[aps,prb,reprint,superscriptaddress,longbibliography,floatfix]{revtex4-2}" in main
    assert r"\title{Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe}" in main
    assert main.count(r"\input{sections/") == 10
    assert main.count(r"\includegraphics") == 7
    assert (root / "supplement.tex").exists()
~~~

- [ ] **Step 2: Run the focused test and verify failure**

Run: PYTHONPATH=01_task_folder/task_05/script python3 -m pytest -q 01_task_folder/task_05/script/tests/test_paper1_manuscript_v13.py::test_prb_project_contract

Expected: FAIL because the v13 manuscript directory does not exist.

- [ ] **Step 3: Create the minimal REVTeX shells**

Create the exact document class and title above. Main.tex must input generated/results_v13.tex, the ten named section files in order, seven numbered figure environments with labels fig:protection through fig:mechanisms, acknowledgments, and references.bib. Supplement.tex must use REVTeX with one-column preprint layout and input the two supplemental section files.

- [ ] **Step 4: Run the focused test**

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

~~~bash
git add overleaf_sync/exactly_degenerate_quantum_chaos_prb 01_task_folder/task_05/script/tests/test_paper1_manuscript_v13.py
git commit -m "docs: scaffold exactly degenerate chaos PRB"
~~~

### Task 2: Build the machine-readable evidence registry

**Files:**
- Create: 01_task_folder/task_05/script/build_paper1_evidence_registry_v13.py
- Create: 01_task_folder/task_05/script/tests/test_paper1_evidence_registry_v13.py
- Create: 01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json

**Interfaces:**
- Consumes as required tracked evidence: spectral_silence_v2.json, matrix_element_geometric_eth_v3.json, topological_holonomy_v3.json, continuum_lll_replication_inference_v6.json, susy_hodge_v7_N14_inference.json, moore_read_v9/moore_read_pilot_v9.json, lattice_susy_v10/lattice_susy_pilot_v10.json, xcube_v11/xcube_geometric_control_v11.json, cross_complete_covariance_v12.json, and cross_mechanism_geometric_eth_v12.json. The historically referenced protected_scaling_inference_v4.json is absent from the tracked v12-delivery tree; record it explicitly as unavailable and never read it from another worktree or use its absence as numerical evidence.
- Produces: build_registry(repo_root: Path) -> dict with top-level keys sources, models, observables, gates, claims, and source_hashes.

- [ ] **Step 1: Write registry tests**

~~~python
def test_registry_keeps_missing_cells_explicit(tmp_path):
    payload = build_registry(REPO)
    assert payload["models"]["laughlin"]["complete_covariance_v12"] is False
    assert payload["models"]["susy_syk"]["complete_covariance_v12"] is False
    assert payload["models"]["moore_read"]["production_complete"] is False
    assert payload["models"]["lattice_susy"]["production_complete"] is False
    assert payload["models"]["xcube"]["role"] == "exact_structured_control"
    assert payload["claims"]["asymptotic_geometric_eth"] is False
    assert len(payload["source_hashes"]) >= 10
~~~

- [ ] **Step 2: Run the registry test and verify failure**

Expected: FAIL because build_paper1_evidence_registry_v13.py is absent.

- [ ] **Step 3: Implement strict source loading**

Implement load_json(path: Path, required: tuple[str, ...]) -> dict, sha256_file(path: Path) -> str, and build_registry(repo_root: Path) -> dict. Missing input files, false source all_checks_pass flags, contradictory production flags, and absent claim-boundary keys must raise RuntimeError. Do not infer a positive gate from prose.

- [ ] **Step 4: Generate and validate the registry**

Run:

~~~bash
PYTHONPATH=01_task_folder/task_05/script python3 01_task_folder/task_05/script/build_paper1_evidence_registry_v13.py
PYTHONPATH=01_task_folder/task_05/script python3 -m pytest -q 01_task_folder/task_05/script/tests/test_paper1_evidence_registry_v13.py
~~~

Expected: the JSON is written atomically and the focused suite passes.

- [ ] **Step 5: Commit**

~~~bash
git add 01_task_folder/task_05/script/build_paper1_evidence_registry_v13.py 01_task_folder/task_05/script/tests/test_paper1_evidence_registry_v13.py 01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json
git commit -m "feat: register paper one evidence boundary"
~~~

### Task 3: Generate LaTeX macros and tables from the registry

**Files:**
- Create: 01_task_folder/task_05/script/make_paper1_prb_assets_v13.py
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated/results_v13.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated/evidence_matrix_v13.tex
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated/model_table_v13.tex
- Modify: 01_task_folder/task_05/script/tests/test_paper1_evidence_registry_v13.py

**Interfaces:**
- Consumes: evidence_registry_v13.json.
- Produces: render_results(payload: dict) -> str, render_evidence_matrix(payload: dict) -> str, and render_model_table(payload: dict) -> str.

- [ ] **Step 1: Add deterministic-generation tests**

Assert that two consecutive renders are byte identical, every model row contains an explicit independent-ensemble and production cell, Moore--Read ranks 42 and 120 come from the registry, and the generated files contain no strings nan, unresolved-placeholder, or inferred universal.

- [ ] **Step 2: Verify the new tests fail**

Run the registry-focused test file and confirm the missing renderer failure.

- [ ] **Step 3: Implement the renderers**

Use stable ordering, fixed numerical formatting, LaTeX escaping, and source-hash comments. Emit macros for all empirical values used in the main text. Represent unavailable gates as \(\text{not tested}\), not zero.

- [ ] **Step 4: Regenerate twice and compare hashes**

Run the generator twice and verify sha256sum gives identical hashes for all three TeX files.

- [ ] **Step 5: Commit**

Commit the generator, tests, and generated TeX files with message feat: generate PRB evidence tables.

### Task 4: Create the protection--mixing figure

**Files:**
- Create: 01_task_folder/task_05/script/make_paper1_protection_mixing_figure_v13.py
- Create: 01_task_folder/task_05/script/tests/test_paper1_figures_v13.py
- Create: overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/figure_1_protection_mixing_v13.pdf
- Create: 01_task_folder/task_05/script/output/paper1_prb_v13/figure_1_protection_mixing_v13.png

**Interfaces:**
- Consumes: evidence_registry_v13.json.
- Produces: make_figure(registry: dict, pdf_path: Path, png_path: Path) -> dict with panel_labels, source_hash, dimensions_inches, and dpi.

- [ ] **Step 1: Write figure-contract tests**

~~~python
def test_protection_mixing_figure_contract(tmp_path):
    manifest = make_figure(REGISTRY, tmp_path / "f.pdf", tmp_path / "f.png")
    assert manifest["panel_labels"] == ["a", "b", "c"]
    assert manifest["dimensions_inches"] == [7.0, 5.6]
    assert manifest["dpi"] == 300
    assert (tmp_path / "f.pdf").stat().st_size > 20_000
    assert (tmp_path / "f.png").stat().st_size > 100_000
~~~

- [ ] **Step 2: Verify failure**

Expected: FAIL because the figure builder is absent.

- [ ] **Step 3: Implement the three-panel figure**

Panel (a) shows the \(P/Q\) block matrix and labels \(S_a\) and \(V_a\). Panel (b) shows the chain \(V_a\to X_a\to\mathcal Q_{ab}\to(g_{ab},F_{ab})\). Panel (c) is a four-column classification populated from audited examples: X-cube reweighting as frozen, X-cube transport as scalar, lattice SUSY as structured/reducible, and Moore--Read/Laughlin as stochastic geometry with an explicit finite-size label. Use mathematical labels, not promotional prose.

- [ ] **Step 4: Generate and visually inspect**

Run the builder, render the PDF at 300 dpi, and inspect the PNG at original resolution. Fix clipping, undersized labels, and color-only distinctions before accepting.

- [ ] **Step 5: Commit**

Commit the script, test, PDF, PNG, and per-figure manifest with message feat: draw protection mixing classification.

### Task 5: Assemble the six evidence figures

**Files:**
- Create: 01_task_folder/task_05/script/make_paper1_evidence_figures_v13.py
- Modify: 01_task_folder/task_05/script/tests/test_paper1_figures_v13.py
- Create: the six v13 evidence PDFs and PNG previews listed in the file map.
- Create: 01_task_folder/task_05/script/output/paper1_prb_v13/figure_manifest_v13.json

**Interfaces:**
- Consumes: immutable source figures and their source JSON/NPZ hashes.
- Produces: assemble_figures(repo_root: Path) -> dict keyed by figure number with source files, source hashes, output hashes, dimensions, and caption-data contract.

- [ ] **Step 1: Write provenance and dimension tests**

Require exactly seven figures including Figure 1, a vector PDF and preview for each, nonempty source hashes, no source/output path collision, and exact rejection if a source figure hash changes.

- [ ] **Step 2: Verify failure**

Expected: FAIL because the assembler is absent.

- [ ] **Step 3: Implement verified copying or explicit recomposition**

Use existing audited figures where their panel logic matches the new paper. Recompose Figure 3 from geometric-hierarchy and covariance-mechanism assets only if the resulting panels share uncertainty units. Recompose Figure 5 from Wick-factorization and continuum-parent assets. Expand Figure 7 from cross-mechanism inputs so its model labels and gate meanings are legible at PRB column width. Never rasterize a vector source to create the canonical PDF.

- [ ] **Step 4: Run all figure tests and inspect previews**

Record visual-audit notes in figure_manifest_v13.json. Every panel must be readable at 100% page zoom.

- [ ] **Step 5: Commit**

Commit the assembler, tests, seven PDFs, seven previews, and manifest with message feat: assemble PRB evidence figures.

### Task 6: Write the formalism and statistical-method sections

**Files:**
- Modify: sections/02_protected_response.tex
- Modify: sections/03_statistics.tex
- Modify: sections/supplement_methods.tex
- Modify: test_paper1_manuscript_v13.py

**Interfaces:**
- Consumes: the shared notation in the approved design and generated macros.
- Produces: a self-contained derivation of the block separation, QGT, curvature, gauge covariance, spectral and four-point observables, and uncertainty units.

- [ ] **Step 1: Add semantic manuscript tests**

Require labels eq:splitting, eq:response, eq:qgt, eq:curvature, eq:fourpoint, and eq:wickresidual; require the three Wick pairings and pseudocovariance to be stated; reject raw Berry-connection entries as primary observables.

- [ ] **Step 2: Verify failure**

Expected: FAIL because the section shells do not contain the required definitions.

- [ ] **Step 3: Write the derivation**

Write complete paragraphs around each equation. State assumptions before using the reduced resolvent. Distinguish gauge covariance from gauge invariance. Define the connected SFF normalization and the independent statistical unit for every estimator. Move long Wick contractions and finite-Jacobi kernel details to the supplement while keeping the logical definitions in the main text.

- [ ] **Step 4: Compile main and supplement**

Run latexmk -pdf main.tex and latexmk -pdf supplement.tex from the manuscript directory. Fix all undefined references before continuing.

- [ ] **Step 5: Commit**

Commit formalism, statistics, supplement methods, and tests with message docs: derive protected projector response.

### Task 7: Write the model and exact-mechanism sections

**Files:**
- Modify: sections/04_models.tex
- Modify: sections/supplement_numerics.tex
- Modify: references.bib
- Modify: test_paper1_manuscript_v13.py

**Interfaces:**
- Consumes: model_table_v13.tex and primary citations already present in v12 or verified from the repository literature notes.
- Produces: model definitions organized by two-body clustering, three-body clustering, random and local cohomology, stabilizer constraints, and lattice FCI replication.

- [ ] **Step 1: Add model-coverage tests**

Require equations for \(H=C^\dagger C\), Moore--Read three-body factors, \(H=\{Q,Q^\dagger\}\), and the X-cube stabilizer sum. Require a sentence stating how each exact degeneracy is broken. Require the checkerboard model to be labelled a quasi-degenerate replication rather than an exact-zero-mode mechanism.

- [ ] **Step 2: Verify failure**

Run the manuscript test and confirm missing-model failures.

- [ ] **Step 3: Write the model section**

For each model state Hilbert space, boundary conditions, protected rank, exactness mechanism, gap condition, tangent class, and role in the comparison. Use generated tables for numerical ranks and gaps. Do not insert experimental claims unless they have a verified primary citation.

- [ ] **Step 4: Compile and inspect table layout**

Render the pages containing model_table_v13.tex; keep columns within the PRB text width and move long solver parameters to the supplement.

- [ ] **Step 5: Commit**

Commit with message docs: explain exact degeneracy mechanisms.

### Task 8: Write the Laughlin, topology, and channel-separation results

**Files:**
- Modify: sections/05_laughlin_results.tex
- Modify: sections/06_topology.tex
- Modify: test_paper1_manuscript_v13.py

**Interfaces:**
- Consumes: Figures 2--6 and generated empirical macros.
- Produces: the data-led narrative from spectral silence through local/global geometry, Wick residuals, parent dependence, and fixed-Chern holonomy.

- [ ] **Step 1: Add claim-boundary tests**

Require the exact identity for the flat energy connected SFF, the finite-size qualifier on Jacobi agreement, the rejected no-refit parent law, the distinction between \(PHP\) and \(Q(\partial H)P\), and the statement that Wilson-loop parameter is not physical time.

- [ ] **Step 2: Verify failure**

Expected: FAIL on the empty result sections.

- [ ] **Step 3: Write results in inference order**

For each figure, state the question before the measurement, then parameters and uncertainty, then the result, then the allowed interpretation. Do not repeat captions in the prose. Preserve negative results: long-range deviations, rejected scaling laws, and fixed-projector controls.

- [ ] **Step 4: Compile and review figure placement**

Require every figure to appear after first citation, no caption split from its figure, and no more than two consecutive pages dominated by floats.

- [ ] **Step 5: Commit**

Commit with message docs: present spectral silence and geometric response.

### Task 9: Write Moore--Read, cohomology, and stabilizer results

**Files:**
- Modify: sections/07_cohomology.tex
- Modify: sections/08_stabilizer.tex
- Modify: test_paper1_manuscript_v13.py

**Interfaces:**
- Consumes: Figure 7, cross_complete_covariance_v12.json, and the evidence registry.
- Produces: mechanism-resolved result text with explicit inference units and open gates.

- [ ] **Step 1: Add result-status tests**

Require Moore--Read \(N=4,6\) and \(D=42,120\), the fixed-base panel qualification, the lattice-SUSY ranks \(2,4,8\), the statement that failure of one directional gate does not prove Gaussianity, the SYK separable-null boundary, and both X-cube exact controls.

- [ ] **Step 2: Verify failure**

Expected: FAIL until the model-specific result sections are written.

- [ ] **Step 3: Write the cross-mechanism narrative**

Keep Moore--Read, random-supercharge SYK, local lattice SUSY, and X-cube in separate subsections. Explain the algebra before the statistics. State the exact covariance protocol used in each model and do not pool incompatible uncertainty units.

- [ ] **Step 4: Compile and inspect Figure 7**

Verify all model names, ranks, and gate colors remain legible in the reprint layout.

- [ ] **Step 5: Commit**

Commit with message docs: compare clustering cohomology and stabilizers.

### Task 10: Write introduction, classification, discussion, and abstract

**Files:**
- Modify: sections/01_introduction.tex
- Modify: sections/09_classification.tex
- Modify: sections/10_discussion.tex
- Modify: main.tex
- Modify: test_paper1_manuscript_v13.py

**Interfaces:**
- Consumes: all completed technical sections and the evidence registry.
- Produces: the final article-level argument and bounded abstract.

- [ ] **Step 1: Add title-level claim tests**

Reject the phrases “we establish universal Geometric ETH,” “thermalization is demonstrated,” “novel framework,” “comprehensive,” “robust evidence,” and “opens new avenues.” Require the abstract to mention exact degeneracy, projector response, at least one positive and one exact negative result, and the absence of an asymptotic claim.

- [ ] **Step 2: Verify failure**

Run the manuscript test to expose any inherited promotional or overbroad wording.

- [ ] **Step 3: Write the article-level prose**

The introduction follows problem, obstruction, geometric replacement, protection--mixing distinction, calculation, and result. The classification section uses response rank, commutant or branch structure, local correlations, and higher-order status. The discussion names the missing matched covariance cells and explains why mechanism-complete sampling is preferable to an unbounded model catalogue.

- [ ] **Step 4: Run texcount and compile**

Require 8,500--12,500 main-text words excluding bibliography and supplement, 14--18 reprint pages unless float placement gives a documented one-page deviation, and no undefined references.

- [ ] **Step 5: Commit**

Commit with message docs: complete exactly degenerate chaos manuscript.

### Task 11: Verify citations and prose

**Files:**
- Modify: references.bib
- Create: docs/literature/2026-08-17-paper1-prb-citation-audit.md
- Modify: test_paper1_manuscript_v13.py

**Interfaces:**
- Consumes: every citation key in main.tex, section files, and supplement.
- Produces: a clickable primary-source audit with title, authors, DOI or arXiv URL, and the exact claim supported.

- [ ] **Step 1: Enumerate citations and unsupported factual claims**

Generate the set difference between cited keys and BibTeX keys. List every sentence about experimental realization, exact degeneracy, zero-mode counting, or random-matrix law that lacks a nearby citation.

- [ ] **Step 2: Verify primary sources**

Use official journal pages, DOI metadata, or arXiv records. Record clickable links and claim mappings in the audit. Do not cite a review when an original model or theorem paper is available.

- [ ] **Step 3: Run citation checks**

Require zero missing keys, zero duplicate BibTeX keys, and no malformed DOI or arXiv identifiers. Compile twice through latexmk and confirm the log contains no undefined citations.

- [ ] **Step 4: Perform the physics-prose audit**

Read each section in isolation and then in article order. Remove repeated opening formulas, formulaic transitions, symmetrical three-item prose, empty “this highlights” sentences, and unquantified adjectives. Preserve necessary passive voice and technical terminology.

- [ ] **Step 5: Commit**

Commit with message docs: verify PRB citations and prose.

### Task 12: Build, render, and fail-close the delivery

**Files:**
- Create: 01_task_folder/task_05/script/verify_paper1_prb_v13.py
- Create: 01_task_folder/task_05/script/run_paper1_prb_delivery_v13.sh
- Create: 01_task_folder/task_05/script/tests/test_paper1_delivery_v13.py
- Create: delivery PDFs and delivery_audit_v13.json.
- Modify: task_05_dashboard.md
- Modify: 00_main/main_dashboard.md

**Interfaces:**
- Consumes: complete source tree, evidence registry, figure manifest, citation audit, and compiled PDFs.
- Produces: verify_delivery(repo_root: Path) -> dict and a deterministic one-command delivery.

- [ ] **Step 1: Write corruption tests**

Test rejection of a changed source hash, missing figure, manually altered empirical macro, absent claim-boundary sentence, undefined citation, overfull box, mismatched archived PDF, and a second run that rewrites an unchanged canonical audit timestamp.

- [ ] **Step 2: Verify failure**

Expected: FAIL because the verifier and delivery script are absent.

- [ ] **Step 3: Implement the delivery pipeline**

The shell script runs the evidence registry, generated assets, figures, focused v13 tests, latexmk for main and supplement, citation checks, PDF structural checks, page rendering, source-hash verification, archive copying, and final audit. It must stop at the first failed gate and contain no network upload or Git push.

- [ ] **Step 4: Execute and inspect every page**

Run run_paper1_prb_delivery_v13.sh. Render all pages at 180 and 300 dpi, inspect equations, tables, captions, and page breaks, and record page hashes and visual verdicts in delivery_audit_v13.json.

- [ ] **Step 5: Update dashboards and run final tests**

Append a stamped v13 version entry, embed the main result figure in the task Canvas, synchronize status as ongoing, and run:

~~~bash
PYTHONPATH=01_task_folder/task_05/script python3 -m pytest -q \
  01_task_folder/task_05/script/tests/test_paper1_evidence_registry_v13.py \
  01_task_folder/task_05/script/tests/test_paper1_figures_v13.py \
  01_task_folder/task_05/script/tests/test_paper1_manuscript_v13.py \
  01_task_folder/task_05/script/tests/test_paper1_delivery_v13.py
~~~

- [ ] **Step 6: Commit**

Commit all v13 sources, generated assets, PDFs, tests, audit, and synchronized dashboards with message deliver: exactly degenerate quantum chaos PRB.

## Self-review

- Spec coverage: Tasks 1--12 cover the new isolated source tree, evidence registry, seven figures, all ten main sections, supplement, citation audit, prose audit, compilation, visual inspection, fail-closed delivery, and dashboard synchronization.
- Placeholder scan: the plan contains no deferred content markers; missing scientific evidence is represented by explicit false gates rather than prose promises.
- Interface consistency: build_registry feeds the asset and figure builders; generated macros and figures feed the manuscript; the evidence registry, figure manifest, and compiled source feed verify_delivery.
- Baseline note: the clean v12 branch previously passed its delivery suite. The current host cannot collect the historical full suite because PyYAML is absent; the new focused v13 suite is intentionally YAML-free and does not reinterpret that environment error as a regression.
