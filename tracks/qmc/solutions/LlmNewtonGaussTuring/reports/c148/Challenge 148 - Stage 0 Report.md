---
title: "Challenge 148: Stage 0 Report"
date: 2026-07-27
tags:
  - quantum-harness
  - challenge-148
  - stage-report
  - literature-audit
  - preregistration
status: complete
stage: 0
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
  - 文献库/QMC/TFIM/Challenge-148/MINERU_INDEX.md
---

# Challenge 148: Stage 0 Report

## 1. Stage status

| Item | Status |
|---|---|
| Scientific content | Complete |
| Literature archive | Complete |
| Preregistration freeze | Complete |
| Validation | Complete for Stage 0 artifacts |
| Formal repository gate | Satisfied by the notes commit containing this report |
| Overall stage | Complete |

Stage 0 completed its research content and formal documentation gate in the notes commit containing this report. The future challenge-code repository remains separate and must import or reference the frozen protocol before production work begins.

## 2. Previous work summary

Before Stage 0 began, the project had an extensive planning note based on QuantumBFS challenge issue 148. That note established the following starting point:

- Target Hamiltonian:
  $$
  H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z-h\sum_i\sigma_i^x,
  \qquad J>0.
  $$
- Published critical fields:
  $$
  (h_c/J)_\triangle=4.76811(9),\qquad
  (h_c/J)_\hexagon=2.13250(4).
  $$
- Published ratio:
  $$
  R=2.23592497069,
  \qquad R-\sqrt{5}=-1.43007\times10^{-4},
  \qquad \sigma_R=5.9499\times10^{-5}.
  $$
- The existing `src/sse_new` implementation had already been classified as one-dimensional Rydberg-oriented reference material, not as a valid base for the target two-dimensional ferromagnetic TFIM.
- The proposed research sequence already required literature review, graph-based lattice infrastructure, exact diagonalization oracles, a new serial SSE implementation, finite-size scaling, and an independent thermodynamic route.

Stage 0 converted that plan into a source-audited and preregistered protocol.

## 3. Stage objective

Stage 0 had four objectives:

1. determine whether a post-2002 result supersedes the Blote-Deng critical-field pair;
2. freeze the Hamiltonian, lattice, observable, fit, uncertainty, blinding, and verdict conventions;
3. define a valid independent thermodynamic route;
4. preserve the primary literature in the private local knowledge workflow with reproducible source hashes.

## 4. Work completed

### 4.1 Method and skill routing

The research route was selected as sign-problem-free QMC with a serial SSE primary implementation. Small-system finite-temperature ED was selected as the exact implementation oracle. Criticality diagnostics require at least two consistent dimensionless observables rather than a single crossing. The software documentation review used local harness knowledge first and official upstream sources when the local KB lacked ParaToric coverage.

### 4.2 Literature audit

The audit checked the official issue, OpenAlex citations to Blote-Deng, Semantic Scholar citations, Crossref metadata, local knowledge bases, and primary texts. Four sources received detailed normalization checks:

| Source | Finding |
|---|---|
| Blote and Deng (2002) | Still the most precise direct pair; continuous-time Wolff cluster, PBC, sizes through $L=20$ for both target lattices |
| Kott et al. (2024) | The precise mapped values are imported from Blote-Deng; the paper's own tenth-order DLogPade estimates are much less precise |
| Linsel, Pollet, and Grusdt (2025/2026) | Independent continuous-time QMC reaches $L=32$ but reports much larger critical-field uncertainties |
| ParaToric 1.0 (2026) | Publishes a reusable independent C++ continuous-time QMC code, but no sharper triangular/honeycomb TFIM pair |

The Stage 0 conclusion is that Blote-Deng remains the current baseline. This conclusion is a dated search result, not a proof that bibliographic databases are complete.

### 4.3 Normalization audit

The direct Blote-Deng convention matches the target $g=h/J$. The Kott toric-code dual Hamiltonian uses a transverse coefficient $1/2$, giving

$$
g=\frac{1}{2h_{\mathrm{TC}}}.
$$

The later Linsel toric-code work uses unit stabilizer coefficients, giving

$$
g=\frac{1}{h_{\mathrm{TC}}}.
$$

The two toric-code normalizations are now explicitly separated in the preregistration.

### 4.4 Protocol freeze

The following decisions were frozen:

- Pauli normalization, $J=1$, $h\ge0$, no longitudinal field, and PBC.
- Explicit graph representations for all lattices and immutable geometry metadata.
- Primary observable:
  $$
  Q_L=\frac{\langle m^2\rangle^2}{\langle m^4\rangle}.
  $$
- Mandatory secondary observable: $\xi_L/L$ from lattice-correct second-moment structure factors.
- Primary finite-size fit with fixed $\nu=0.629971$ and $\omega=0.83$.
- End-to-end chain/block bootstrap for nonlinear estimators and fitted critical fields.
- Separate triangular and honeycomb analysis before unsealing the ratio.
- Verdict gate: rejection at or above $10\sigma$, survival within $2\sigma$, inconclusive otherwise, with all systematic gates required.

### 4.5 Independent-route selection

ParaToric v1.0.3, commit `e7bc78446ba083aeeae1ada9c883fa03bf205890`, was selected as the preferred Stage 7 route. It is independent in algorithm, code, observable family, and output path from the planned SSE implementation.

Its qualification remains conditional on:

1. exact normalization derivation for the ParaToric Hamiltonian;
2. suppression of unwanted toric-code sectors at finite $\beta$;
3. agreement with direct TFIM ED on dual small tori;
4. agreement with direct finite-size TFIM simulations before extrapolation.

A local fixed-tag configure smoke used GCC 15.2, CMake 4.2, tests enabled, native optimization disabled, and fast-math disabled. Configuration stopped at the missing Boost development package. No test executable ran and no system dependency was installed.

### 4.6 Private literature archive

Four public PDFs were saved under ignored `library/sources/papers/challenge-148/` and parsed with MinerU using model `vlm`, language `en`, formulas enabled, tables enabled, and OCR disabled. The generated Markdown, source hashes, and index are stored under `notes/文献库/QMC/TFIM/Challenge-148/`.

All four conversions completed successfully:

- Blote-Deng: 8 pages;
- Kott et al.: 26 pages;
- Linsel et al.: 12 pages;
- ParaToric: 42 pages.

## 5. Artifacts

| Artifact | Purpose |
|---|---|
| `Challenge 148 - TFIM Critical-Field Ratio.md` | Master research plan and stage gates |
| `Challenge 148 - Stage 0 Preregistration.md` | Frozen scientific and statistical protocol |
| `Challenge 148 - Stage 0 Report.md` | Stage summary, gate state, next plan, and review record |
| `文献库/QMC/TFIM/Challenge-148/MINERU_INDEX.md` | Private full-text index with source hashes |
| `library/sources/papers/challenge-148/` | Ignored source PDFs |
| `library/mineru/work/` | Ignored MinerU requests, API responses, and result manifests |

## 6. Validation evidence

- Recomputed the published ratio and independent-error propagation.
- Checked the Blote-Deng primary PDF for Hamiltonian convention, Binder definition, fit exponents, size windows, and critical values.
- Checked the Kott and Linsel dual Hamiltonians before converting their field values.
- Verified all four local PDF SHA-256 hashes against MinerU frontmatter and the generated index.
- Verified that the critical values and Binder conventions are searchable in the generated Markdown.
- Verified all MinerU image links resolve to ignored local assets.
- Confirmed `library/` and MinerU job artifacts remain Git-ignored.
- Ran `git diff --check` on tracked edits and explicit whitespace checks on the new preregistration file.

## 7. Deviations and unresolved risks

- The literature audit is broad but database coverage is not mathematically exhaustive. Citation snowballing must continue and every new normalization must enter the ledger.
- MinerU extraction of the older 2002 PDF contains some character noise in prose, although its key tables and numeric values were extracted correctly.
- ParaToric has not built locally because Boost development files are absent.
- ParaToric's documented Binder ratio is the inverse of the registered $Q_L$ convention for a generic observable.
- The final development worktree does not exist because no real training team name has been configured. Repository rules prohibit a placeholder `group-*` worktree.
- The future development worktree must preserve or explicitly reference this frozen protocol before production data are generated.

## 8. Stage-gate assessment

The scientific requirements of Stage 0 are satisfied:

- source table: complete;
- normalization ledger: complete;
- preregistered estimators and fit family: complete;
- verdict and blinding protocol: complete;
- independent-route definition: complete;
- private source archive: complete.

Stage 0 is complete in the notes commit containing these artifacts. No production data may be generated until the future development worktree references this frozen protocol and passes its own repository checks.

## 9. Stage 1 work plan

Stage 1 will build lattice and exact-oracle infrastructure before any SSE kernel work.

### 9.1 Repository setup

1. obtain the real training team name;
2. create or select the unique authorized `group-*` worktree;
3. re-check local `AGENTS.md`, branch remotes, and dirty state;
4. place reproducible source under the challenge track solution path without absolute personal-workspace dependencies.

### 9.2 Lattice implementation

1. define an explicit lattice interface containing sites, bonds, primitive vectors, basis positions, translations, reciprocal vectors, and allowed smallest momenta;
2. implement periodic chain, square, triangular, and two-basis honeycomb constructors;
3. test site and bond uniqueness, coordination, connectivity, translation invariance, wrapping, bond formulas, and momentum compatibility;
4. serialize geometry metadata for later run manifests.

### 9.3 Exact oracle

1. construct the Pauli-normalized TFIM from the same bond lists used by the lattice layer;
2. use dense full-spectrum ED only where the Hilbert dimension permits exact finite-temperature traces;
3. use sparse Lanczos only for larger ground-state checks;
4. compute energy, $m$, $m^2$, $m^4$, and structure factors directly;
5. verify Hermiticity, Hilbert-space dimension, limiting cases, spectra, partition functions, and dense/sparse agreement.

### 9.4 Stage 1 exit gate

Stage 1 closes only when all lattice invariants pass and ED reproduces hand-checkable spectra and partition functions. Its English report must include prior-work context, code and data artifacts, test output, cost limits, deviations, the Stage 2 plan, and an updated agent-review log.

## 10. Agent Review and Suggestions

This section is intentionally reserved for independent agent review. Reviewers should add concrete findings rather than general approval.

### 10.1 Requested review focus

- Is the post-2002 literature audit missing a credible higher-precision determination?
- Are the Kott and Linsel normalization conversions correct for their exact Hamiltonians?
- Is $Q_L$ the defensible primary estimator, with $\xi_L/L$ as the mandatory independent diagnostic?
- Are the fixed values and robustness range for $\nu$ and $\omega$ appropriate?
- Does ParaToric qualify as genuinely independent after the four stated validation gates?
- Is the blinding protocol strong enough to prevent fit choices from responding to the final ratio?
- Are any Stage 1 lattice or ED invariants missing?

### 10.2 Suggestions log

| Reviewer or agent | Date | Finding or suggestion | Disposition | Status |
|---|---|---|---|---|
| _Reserved_ | _Pending_ | _No review submitted yet_ | _Pending_ | Open |

### 10.3 Protocol-change rule

Suggestions that clarify documentation or add validation may be incorporated directly and logged above. Suggestions that change the Hamiltonian, primary estimator, fit family, error model, blinding, or verdict require a new preregistration revision with an explicit rationale and cannot silently overwrite the frozen Stage 0 protocol.
