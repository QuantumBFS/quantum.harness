# Issue 128 Final Delivery Design

**Date:** 2026-07-30

**Status:** Approved by the user (option A)

**Target:** Existing pull request `QuantumBFS/quantum.harness#248`

## Objective

Finish Issue 128 as a reviewer-ready, reproducible package. Preserve the
proved `11791/2911 = 4.050498110614909...x` resource improvement as the
official result, add a polished technical report and machine-readable
summaries, and report the strict fivefold investigation as an honest
feasibility appendix rather than a completed certificate.

## Frozen Scientific Claim

The benchmark is the periodic `12 x 12` spin-1/2 isotropic Heisenberg model

```text
H = sum_<i,j> (X_i X_j + Y_i Y_j + Z_i Z_j) / 4,
T = 1, operator-norm tolerance = 1e-6.
```

The pinned published rigorous baseline uses 393 Trotter steps and 11,791
merged group exponentials. The submitted certificate uses 97 steps and 2,911
merged group exponentials. The 97-step exact-rational error bound is below
`1e-6`; the 96-step bound is above it. The proof, circuit, normalization,
tolerance, resource model, main certificate, and D4 sidecar are immutable.

## Chosen Approach

Extend the existing proof branch with four reviewer-facing layers:

1. a standard LaTeX article of approximately 6--8 pages;
2. compact JSON and plain-text result summaries;
3. a verifier transcript and SHA-256 manifest; and
4. a precise update to the existing PR description.

The exact D5 artifact is follow-up evidence only. No `5x` result may be stated
or implied. The unresolved translation-coupled D4 and explicit D8/tail proof
gates, and the absence of an accepted 78-step global certificate, must be
visible wherever the conditional fivefold arithmetic appears.

## Deliverables

All final files live under
`tracks/qcs/solutions/WangTheoPhys/issue128`:

```text
docs/report/issue128-technical-report.tex
docs/report/references.bib
docs/report/output/issue128-technical-report.pdf
artifacts/issue128-summary.json
artifacts/issue128-summary.txt
artifacts/verification-transcript.txt
artifacts/SHA256SUMS
```

The PDF is versioned because it is a competition deliverable. Auxiliary LaTeX
files and rendered page images are temporary and are not committed.

## Report Structure

No challenge template exists, so the report uses the standard `article` class.
It contains:

1. abstract and contribution summary;
2. benchmark and resource accounting;
3. reconstruction of the published rigorous baseline;
4. local logarithm, Lie projection, concrete Pauli representation, and exact
   anticommuting-group method;
5. finite-step right-generator error ledger;
6. verifier architecture and small-size dense cross-check;
7. certified result and exact integer boundary;
8. strict fivefold feasibility evidence and unresolved gates; and
9. limitations and copy-paste reproduction commands.

External citations are restricted to verified primary sources.

## Trust Boundary and Data Flow

The certificate and sidecars remain the source of truth. A packaging script
checks their frozen hashes, projects exact fields into JSON and text, runs the
fast main verifier and exact D5 verifier, and records their complete output.
The final manifest binds the PDF, summaries, transcript, certificates, and
report sources.

- integers, `Fraction`, rational intervals, and symplectic Pauli algebra are
  trusted;
- heuristic grouping is untrusted discovery and is rechecked exactly;
- floating point is presentation-only or part of the dense sanity check;
- PDF and summaries explain the certificate but never replace it.

## Fivefold Reporting Policy

At 78 steps the unchanged compilation rule gives 2,341 groups and the
conditional ratio `11791/2341 = 5.036736...`. This arithmetic does not prove a
78-step error bound. The D5 sidecar has 605,832 exact terms, 123,106
same-support pairwise-anticommuting groups, and site-density upper bound
`11.23706750025696`; it narrows the gap without closing D4 or D8/tail.

Every conditional fivefold statement must be accompanied by:

```text
No 78-step global error certificate is claimed or supplied.
```

## Validation

Release requires all of the following:

- the full default Issue 128 test suite;
- the main fast verifier and exact D5 verifier;
- the 97-accept/96-reject boundary checks;
- frozen main-certificate and D4 hashes;
- deterministic JSON/text regeneration;
- SHA-256 verification of every manifest entry;
- LaTeX compilation without fatal errors, undefined references, or missing
  citations;
- PDF text/page checks and visual inspection of every rendered page;
- an unsupported-fivefold-language scan;
- an explicit Git allowlist and remote-head drift check.

If a follow-up check fails, remove its affirmative claim; never weaken the
official 4.050x proof or substitute a numerical estimate.

## Git and PR Strategy

Work only in the isolated Issue 128 clone. Explicitly stage approved files;
never use `git add -A`. Push to the existing fork head branch
`JunkaiWang-TheoPhy:codex/issue-128-trotter-certificate` only if its remote head
is still an ancestor of the audited local head. Do not force-push and do not
open a competing PR. Update PR #248 with artifact links, exact results,
validation commands, and the fivefold non-claim.

## Definition of Done

The report and data package are committed, every validation gate passes, the
audited history is fast-forward pushed to the existing PR branch, the remote
SHA equals the local SHA, and PR #248 exposes accurate reproduction steps and
limitations. Maintainer review and merge are external outcomes.
