# Proof-Carrying Trotter Bound Paper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified 22--30 page English research manuscript that presents the Issue 128 result as a proof-carrying, model-aware compiler for rigorous Trotter resource bounds.

**Architecture:** Keep the frozen certificate package immutable and build a separate modular LaTeX project under `docs/manuscript/`.  Each scientific section consumes committed evidence or primary literature, while deterministic scripts generate figures and validate copied numerical claims.  Compile with `latexmk`, then render every PDF page with Poppler for visual review.

**Tech Stack:** LaTeX, BibTeX, latexmk, Python 3.12, matplotlib, JSON, gzip, exact committed certificate artifacts, Poppler.

## Global Constraints

- Preserve all existing uncommitted HPC work and do not stage it with manuscript commits.
- Do not modify the manifest-bound competition report or certificate artifacts.
- The only certified global result is `r=97`, 2,911 groups, and exact ratio `11791/2911`.
- State explicitly that no `r=78` global certificate is claimed or supplied.
- Use primary-source bibliographic metadata; do not invent references.
- Keep the manuscript in English and target at least 15 substantive PDF pages.
- Separate certified claims, empirical cross-checks, and conditional research directions.
- Use exact values from committed artifacts; plotted decimal values are display-only.

---

## File map

- `docs/manuscript/main.tex`: document class, packages, metadata, section order.
- `docs/manuscript/references.bib`: verified primary-source bibliography.
- `docs/manuscript/sections/abstract.tex`: scoped abstract and keywords.
- `docs/manuscript/sections/introduction.tex`: motivation, gap, contributions.
- `docs/manuscript/sections/problem.tex`: Hamiltonian, formula, norm, cost model.
- `docs/manuscript/sections/baseline.tex`: PRX theorem versus pinned instantiation.
- `docs/manuscript/sections/compiler.tex`: compiler data flow and invariants.
- `docs/manuscript/sections/free_lie.tex`: free-word logarithm and Lie projection.
- `docs/manuscript/sections/pauli.tex`: concrete symplectic Pauli evaluation.
- `docs/manuscript/sections/norm_certificate.tex`: canonicalization and anticommuting groups.
- `docs/manuscript/sections/finite_step.tex`: right generator and rational tail.
- `docs/manuscript/sections/verification.tex`: proof-carrying verifier architecture.
- `docs/manuscript/sections/results.tex`: resource result, ledgers, ablations.
- `docs/manuscript/sections/related_work.tex`: 2021--2026 literature taxonomy.
- `docs/manuscript/sections/limitations.tex`: fivefold and tenfold frontier.
- `docs/manuscript/sections/reproducibility.tex`: commands and evidence matrix.
- `docs/manuscript/sections/conclusion.tex`: scoped conclusion.
- `docs/manuscript/sections/appendices.tex`: technical derivations and schemas.
- `docs/manuscript/scripts/generate_figures.py`: deterministic PDF figure generation.
- `docs/manuscript/scripts/validate_claims.py`: compare manuscript constants with artifacts.
- `docs/manuscript/figures/*.pdf`: generated vector figures.
- `docs/manuscript/output/pdf/issue128-proof-carrying-trotter-paper.pdf`: final PDF.

### Task 1: Initialize the manuscript project and evidence validator

**Files:**
- Create: `docs/manuscript/main.tex`
- Create: `docs/manuscript/sections/*.tex`
- Create: `docs/manuscript/scripts/validate_claims.py`
- Create: `docs/manuscript/output/pdf/.gitkeep`

**Interfaces:**
- Consumes: committed `artifacts/issue128-summary.json` and `certificates/issue128-certificate.json`.
- Produces: a compilable manuscript skeleton and `validate_claims.py` returning exit code zero only when all headline constants match.

- [ ] **Step 1: Scan the existing LaTeX structure**

Run:

```bash
python3 /Users/thomasjwang/.codex/skills/academic-writer/scripts/writer_tools.py scan_template docs/report
```

Expected: identify the existing generic `article` report and its bibliography setup.

- [ ] **Step 2: Create the modular manuscript skeleton**

Use `article` at 11 pt with `geometry`, `amsmath`, `amssymb`, `mathtools`, `booktabs`, `microtype`, `graphicx`, `xcolor`, `hyperref`, `cleveref`, `algorithm`, `algpseudocode`, `siunitx`, and `natbib`.  Set the section order exactly as listed in the file map and place final output under `output/pdf/`.

- [ ] **Step 3: Implement exact headline-claim validation**

`validate_claims.py` must load the summary and certificate, assert:

```python
assert summary["published_baseline"]["steps"] == 393
assert summary["certified_result"]["steps"] == 97
assert summary["published_baseline"]["group_exponentials"] == 11791
assert summary["certified_result"]["group_exponentials"] == 2911
assert Fraction(11791, 2911) > 4
```

It must also assert the accepted and rejected error fractions against `10**-6` using integer cross multiplication.

- [ ] **Step 4: Run the validator**

Run:

```bash
python docs/manuscript/scripts/validate_claims.py
```

Expected output:

```text
headline_claims=PASS
```

- [ ] **Step 5: Compile the skeleton**

Run:

```bash
cd docs/manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Expected: successful one-page or two-page structural PDF with no LaTeX errors.

### Task 2: Build the verified bibliography and related-work taxonomy

**Files:**
- Create: `docs/manuscript/references.bib`
- Create: `docs/manuscript/sections/related_work.tex`

**Interfaces:**
- Consumes: primary pages for each cited paper.
- Produces: citation keys used throughout the manuscript and a comparison taxonomy that distinguishes direct bounds from changed-task algorithms.

- [ ] **Step 1: Add verified baseline and model-specific references**

Include complete BibTeX for Childs et al. PRX 2021 and Schubert--Mendl 2023, with DOI or arXiv identifiers checked against the primary publisher or arXiv record.

- [ ] **Step 2: Add special-state and average-case references**

Include the low-energy subspace paper, Chen--Brandao average-case paper, strong state-dependent error bounds, and Trotter lower bounds.

- [ ] **Step 3: Add changed-algorithm references**

Include dynamic MPF, explicit MPF commutator scaling, randomized order doubling, Chebyshev interpolation, Trotter error mitigation, Trotter LCU, THRIFT, optimized Suzuki schemes, commutation-based ordering, practical BCH estimation, and HNCC.

- [ ] **Step 4: Write the taxonomy**

Use four subsections:

1. worst-case commutator-scaling upper bounds;
2. low-energy, average-case, and observable-specific bounds;
3. MPF, LCU, interpolation, randomization, and compensation;
4. formula and ordering optimization.

For every comparison, state whether the work changes the circuit, state set, norm, sampling cost, or Hamiltonian model.

- [ ] **Step 5: Compile and reject unresolved citations**

Run:

```bash
cd docs/manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
rg -n "undefined citations|Citation.*undefined|There were undefined" main.log
```

Expected: `rg` returns no matches.

### Task 3: Write the problem, baseline, and contribution boundary

**Files:**
- Modify: `docs/manuscript/sections/abstract.tex`
- Modify: `docs/manuscript/sections/introduction.tex`
- Modify: `docs/manuscript/sections/problem.tex`
- Modify: `docs/manuscript/sections/baseline.tex`

**Interfaces:**
- Consumes: frozen benchmark values and bibliography keys.
- Produces: a self-contained statement of the scientific question and a non-misleading baseline reconstruction.

- [ ] **Step 1: Write the abstract**

Include the exact benchmark, unchanged circuit family, `393 -> 97`, `11791/2911`, 75.3117 percent reduction, machine certificate, and explicit non-claim for fivefold.

- [ ] **Step 2: Write the introduction**

Motivate the gap between general asymptotic bounds and finite-instance resource estimates.  End with a numbered list of five contributions: multi-IR compiler, norm-last Pauli evaluation, certified anticommuting partitions, finite-step rational closure, and independent artifact verification.

- [ ] **Step 3: Define the problem**

Define `H`, four matchings, normalized bond, `S_4`, global operator norm, `T=1`, `epsilon=10^-6`, `G(r)=30r+1`, 72 bonds per group, and three-CNOT upper bound.

- [ ] **Step 4: Reconstruct the baseline carefully**

Use the phrase "pinned interval instantiation of a published theorem."  Explain the 31 admissible centers, center 20, Pauli-l1 procedure, site-density bound, and `r=393`.  Do not imply that PRX 2021 printed the number 393.

- [ ] **Step 5: Compile and inspect extracted text**

Run:

```bash
cd docs/manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
pdftotext main.pdf - | sed -n '1,220p'
```

Expected: abstract and claim boundary read coherently without missing symbols.

### Task 4: Write the compiler and algebraic method

**Files:**
- Modify: `docs/manuscript/sections/compiler.tex`
- Modify: `docs/manuscript/sections/free_lie.tex`
- Modify: `docs/manuscript/sections/pauli.tex`
- Modify: `docs/manuscript/sections/norm_certificate.tex`

**Interfaces:**
- Consumes: implementation modules in `src/trottercert/` and committed D4/D5 statistics.
- Produces: precise algorithms, invariants, and verifier obligations for every structural optimization.

- [ ] **Step 1: Specify compiler inputs, IRs, and outputs**

Define source input `(H, F, S, T, epsilon, C)`, free-word IR, Lie IR, Pauli IR, certificate IR, and output `(r_star, resources, certificate)`.

- [ ] **Step 2: Add compiler pseudocode**

The pseudocode must include exact coefficient parsing, free-word multiplication, formal logarithm, order verification, DSW projection, local Pauli evaluation, canonicalization, identical-term aggregation, grouping, finite-tail closure, adjacent-step search, and resource compilation.

- [ ] **Step 3: Explain free-word formal logarithms**

Define truncated sparse series, convolution, `log(1+X)`, symmetry cancellations, degree-five and degree-seven defects, and why no matrix of dimension `2^144` is formed.

- [ ] **Step 4: Explain DSW projection**

Give the right-nested commutator map, homogeneous-degree factor, and the invariant checked by the implementation.

- [ ] **Step 5: Explain concrete Pauli evaluation**

Define symplectic `(x,z)` masks, phase tracking, commutation parity, local-support filtering, translation representatives, and exact coefficient aggregation.

- [ ] **Step 6: Explain anticommuting certification**

Prove that pairwise anticommutation gives an l2 group norm.  Describe the graph partition search as untrusted and list exact coverage, pairwise relation, coefficient, square-root, and hash checks.

- [ ] **Step 7: Quantify the D4 improvement**

Report 75,324 terms, 7,576 groups, maximum size 10, direct cell bound `20.160968407335066`, grouped bound `6.472926505087888`, and factor `3.114660484942633`.

### Task 5: Write finite-step analysis, soundness, and resource compilation

**Files:**
- Modify: `docs/manuscript/sections/finite_step.tex`
- Modify: `docs/manuscript/sections/verification.tex`
- Modify: `docs/manuscript/sections/appendices.tex`

**Interfaces:**
- Consumes: right-generator identity, local lemma, error ledger, verifier behavior.
- Produces: a theorem-level argument connecting local algebra to the global resource result.

- [ ] **Step 1: Prove the Heisenberg local lemma**

Enumerate the 16 phase-free two-qubit Paulis in an appendix table and prove that each anticommutes with zero or exactly two of `XX`, `YY`, `ZZ`, yielding bond Pauli-l1 growth constant one.

- [ ] **Step 2: Derive the right logarithmic generator through degree seven**

Present the `D4`, `D5`, `D6`, and `D7` terms with their exact coefficients and explain the degree shift from log defects to the right generator.

- [ ] **Step 3: State the finite-step soundness theorem**

The theorem must condition on verified free-word coefficients, Pauli ledgers, group partitions, local growth lemma, and tail ratio.  Its conclusion must be the certified global operator-norm upper bound for integer `r`.

- [ ] **Step 4: Explain the rational tail**

Describe support growth, conjugation Taylor factorials, Duhamel integration, the geometric ratio condition, and outward rational arithmetic.  State that omitted degrees are never silently discarded.

- [ ] **Step 5: Derive resource arithmetic**

Prove `G(r)=30r+1`, `B(r)=72G(r)`, and `CNOT(r)<=3B(r)`.  Cross-multiply exact fractions for `r=97` and `r=96`.

- [ ] **Step 6: Specify the trusted computing base**

Separate discovery code from trusted verification.  List integers, `Fraction`, outward rational intervals, symplectic multiplication, digest verification, negative mutation tests, and deep regeneration.

### Task 6: Generate figures and write results, ablations, and limitations

**Files:**
- Create: `docs/manuscript/scripts/generate_figures.py`
- Create: `docs/manuscript/figures/resources.pdf`
- Create: `docs/manuscript/figures/error_ledger.pdf`
- Create: `docs/manuscript/figures/d4_norm.pdf`
- Create: `docs/manuscript/figures/fivefold_gap.pdf`
- Modify: `docs/manuscript/sections/results.tex`
- Modify: `docs/manuscript/sections/limitations.tex`

**Interfaces:**
- Consumes: frozen summary and committed fivefold audit.
- Produces: deterministic vector figures and a results narrative with explicit certified/conditional labels.

- [ ] **Step 1: Implement deterministic figure generation**

Use matplotlib with embedded data loaded from JSON where available.  Use a fixed style, vector PDF output, color-blind-safe colors, and labels that remain legible at single-column width.

- [ ] **Step 2: Generate the resource comparison**

Plot baseline and candidate values for steps, groups, bond propagators, and CNOTs using normalized or log-scaled panels so all metrics remain readable.

- [ ] **Step 3: Generate the `r=97` error ledger**

Plot D4, D5, D6, D7, and D8-plus contributions with a horizontal `10^-6` total target annotation.

- [ ] **Step 4: Generate D4 norm reduction**

Plot direct Pauli-l1 versus grouped anticommuting bound and annotate the exact reduction factor.

- [ ] **Step 5: Generate the fivefold bottleneck figure**

Use the committed audit values at `r=78`; label the entire panel "conditional feasibility audit, not a global certificate."

- [ ] **Step 6: Write results and ablations**

Cover the main result, adjacent boundary, D4 grouping, local lemma, recursive Suzuki audit, degree-three rank, three-site cluster result, small-system cross-check, and D5 side study.

- [ ] **Step 7: Write limitations**

Explain the single-model limitation, constant-factor rather than asymptotic improvement, incomplete comparison with optimized formulas, D4/D6/tail gates for fivefold, and order-lift requirement for tenfold.

- [ ] **Step 8: Regenerate and validate figures**

Run:

```bash
python docs/manuscript/scripts/generate_figures.py
python docs/manuscript/scripts/validate_claims.py
```

Expected: four figure PDFs and `headline_claims=PASS`.

### Task 7: Write reproducibility, conclusion, and paper metadata

**Files:**
- Modify: `docs/manuscript/sections/reproducibility.tex`
- Modify: `docs/manuscript/sections/conclusion.tex`
- Modify: `docs/manuscript/main.tex`

**Interfaces:**
- Consumes: README reproduction commands, transcript metadata, manifest hashes.
- Produces: a reviewer-executable handoff and compliant manuscript metadata.

- [ ] **Step 1: Add the claim-to-evidence matrix**

Map baseline, `r=97`, `r=96`, D4 partition, D5 sidecar, small cross-check, report, and manifest to exact paths and commands.

- [ ] **Step 2: Add reproduction commands**

Include environment installation, tests, fast verification, deep verification, D5 verification, package check, and checksum validation.

- [ ] **Step 3: Add availability and contribution statements**

Include Data Availability, Code Availability, Author Contributions, Acknowledgments, and an AI-assistance disclosure stating the actual role of language models in drafting, code assistance, and literature organization while assigning scientific responsibility to the author.

- [ ] **Step 4: Write the conclusion**

Restate the proof-compiler contribution, scoped best-known certificate, and complementary relationship to MPF/LCU/observable-specific methods.

### Task 8: Compile, audit, and freeze the manuscript PDF

**Files:**
- Produce: `docs/manuscript/output/pdf/issue128-proof-carrying-trotter-paper.pdf`
- Produce temporarily: `tmp/pdfs/issue128-paper/page-*.png`

**Interfaces:**
- Consumes: all manuscript sources and generated figures.
- Produces: the final validated PDF and a clean audit report.

- [ ] **Step 1: Compile with latexmk**

Run:

```bash
cd docs/manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
mkdir -p output/pdf
cp main.pdf output/pdf/issue128-proof-carrying-trotter-paper.pdf
```

- [ ] **Step 2: Run structural checks**

Run:

```bash
pdfinfo output/pdf/issue128-proof-carrying-trotter-paper.pdf
pdftotext output/pdf/issue128-proof-carrying-trotter-paper.pdf - | wc -w
rg -n "undefined|Overfull|Underfull|multiply defined" main.log
```

Expected: at least 15 pages, no unresolved citation/reference diagnostics, and no material overfull boxes.

- [ ] **Step 3: Scan for claim and drafting hazards**

Run searches for placeholder markers, unqualified fivefold claims, accidental "published 393-step result" wording, and unqualified global-SOTA language.  Correct every occurrence in context.

- [ ] **Step 4: Render every page**

Run:

```bash
mkdir -p tmp/pdfs/issue128-paper
pdftoppm -png -r 120 output/pdf/issue128-proof-carrying-trotter-paper.pdf tmp/pdfs/issue128-paper/page
```

Inspect every rendered page for clipping, overlap, broken equations, illegible plots, excessive whitespace, bad table breaks, and orphaned headings.

- [ ] **Step 5: Re-run evidence checks**

Run:

```bash
python scripts/validate_claims.py
cd ../..
PYTHONPATH=src python scripts/verify.py certificates/issue128-certificate.json
PYTHONPATH=src python scripts/package_delivery.py --check
shasum -a 256 -c artifacts/SHA256SUMS
```

Expected: manuscript claims pass, certificate valid, delivery check passes, and all ten frozen hashes are unchanged.

- [ ] **Step 6: Report the final artifact**

Record page count, word count, PDF SHA-256, compiler command, and any remaining non-fatal typography warnings in the handoff.  State explicitly that the manuscript is a local follow-up and has not been pushed to the frozen judged PR.

## Self-review

- Spec coverage: all requested detailed explanations, implementation guidance, long-form PDF, complete algorithm chain, and verification steps are assigned to Tasks 1--8.
- Placeholder scan: the plan contains no unresolved implementation placeholders.
- Interface consistency: manuscript paths, script names, figure names, and final PDF name are used consistently across tasks.
- Scope integrity: no task modifies frozen certificate artifacts or incorporates unrelated HPC work.
