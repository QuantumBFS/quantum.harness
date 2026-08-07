# Issue #230 Research Delivery Design

## Objective

Turn the independently verifiable Issue #230 certificate package into a
complete research delivery on the existing public fork and upstream pull
request.  The delivery will make the scientific contribution easy to inspect:
an exact two-sided XXX/XXZ certification pipeline, a symmetry-compressed
calibration frontier, compact machine-readable data, and a polished Chinese
technical report with a rendered PDF.

## Scientific message

The central contribution is a proof-producing computational architecture, not
an isolated floating-point estimate.  Bethe ansatz is held behind an oracle
firewall and enters only the final containment audit.  Candidate generation,
strict-margin recovery, rational reconstruction, exact blockwise LDL checks,
and exact rational-MPS contraction remain model-derived and independently
verifiable.

The report will lead with the strongest positive results:

- a depth-47, bond-dimension-6 U(1)-blocked RG lower certificate;
- a rational bond-32, 1,000-site MPS upper certificate with explicit boundary
  contraction;
- 27 compact certificates over nine XXZ anisotropies and three levels;
- native symmetry reductions retaining only 7.4% of dense variables for the
  D=6, depth-12 benchmark;
- a deterministic exact verifier that reconstructs both endpoints rather than
  trusting solver status strings.

The record-width target remains a quantitative frontier in the data and
report.  It will be described constructively as the next certified threshold,
with the exact endpoint movement needed to cross it.  No record claim will be
made without a normalization-matched literature comparison and a passing
strict gate.

## Delivery architecture

All changes remain inside
`tracks/polyopt/solutions/WangTheoPhys/issue230/` on the existing
`agent/issue-230-xxz-certificate` branch.

1. `scripts/build_delivery_data.py` reads the selected certificate JSON files
   and emits deterministic CSV, JSON, TXT, and SHA-256 manifest artifacts.
2. `scripts/plot_delivery_summary.py` turns the audited summary into three
   report figures: interval nesting, endpoint error budget, and symmetry
   compression.
3. `docs/issue-230/technical-report-zh.md` is the reader-first technical
   report and source of the PR narrative.
4. `docs/issue-230/technical-report-zh.tex` is a standard XeLaTeX article that
   embeds the generated figures and tables.
5. `docs/issue-230/technical-report-zh.pdf` is committed as the stable review
   artifact requested for the challenge delivery.
6. `README.md`, the PR body, and one PR comment point reviewers to the report,
   data manifest, reproduction commands, and exact verification evidence.

## Data flow and trust boundaries

```text
selected certificate JSON
        |
        +--> exact verifier --> containment / proof status
        |
        +--> delivery builder --> CSV + record-gate JSON + manifest TXT
                                     |
                                     +--> plots --> Markdown / LaTeX / PDF
```

The delivery builder may summarize stored endpoints and metadata, but it does
not modify certificates or construct bounds.  Bethe intervals stay inside the
certificate/verifier boundary.  Generated summaries are checked against the
source JSON by regression tests.

## Writing and claim policy

The prose will be direct, positive, and specific.  Every innovation claim will
name the mechanism and the measured consequence.  Phrases such as “new” or
“first” will be limited to repository-grounded implementation contributions
unless a cited literature audit supports a broader priority claim.

Required claim boundaries will be expressed as forward-looking research
frontiers rather than hidden or deleted.  This preserves the challenge's hard
correctness contract while keeping the presentation ambitious and promising.

## Verification

The completed delivery must satisfy all of the following:

- deterministic regeneration of CSV, JSON, TXT, and figures;
- exact equality between summary endpoints and source certificates;
- passing strict record-gate arithmetic using decimal strings;
- XeLaTeX compilation with no undefined references or fatal errors;
- visual inspection of every PDF page after Poppler rendering;
- focused tests for delivery-data generation plus the existing fast suite;
- `git diff --check` and an allowlist proving every changed path is in the
  Issue #230 solution directory;
- a secrets scan before push;
- a GitHub check confirming the fork is public and PR #266 points to the pushed
  branch.

## Repository visibility

`JunkaiWang-TheoPhy/quantum.harness`, the fork backing PR #266, is already
public and is the authoritative delivery repository.  The separate
`Quantum-Harness-2607-Hefei` research workspace is intentionally excluded from
publication because it combines several challenge tracks and contains an
encrypted HPC-key archive in its Git history.  Publishing the existing public
fork gives reviewers complete access to the Issue #230 deliverables without
disclosing unrelated operational material.
