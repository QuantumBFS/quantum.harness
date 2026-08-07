# Interface barriers for weighted random-forest edge correlation

## Team

| | |
|---|---|
| **Team name** | yanwang |
| **Members** | W.W |

## Challenge

| Row | |
|---|---|
| **Challenge** | Identify structural mechanisms that can or cannot produce a finite weighted-forest counterexample to edge negative correlation. |
| **Catalog issue** | Structural advances on the unresolved disjoint-edge core of #251. |
| **Track** | `tracks/other`, following the issue's `Method: Other` field. |

## Result in one paragraph

Issue #251 asks for a positive-weight graph with
`Z_ef Z > Z_e Z_f`.  This submission does **not** claim such a graph.
Instead, it proves a hierarchy of interface obstructions.  Positive
two-terminal replacements reduce exactly to an effective edge activity and
cannot change the Rayleigh sign.  Parallel composition through three
terminals preserves nonpositivity by an explicit five-state identity.  At
four terminals that closure fails in the ambient partition-signature cone:
two exact positive integer signatures that are individually nonpositive for
all three disjoint target matchings compose to a strictly positive signature
for all three.  A separate Newton-face argument shows why a minor-minimal
counterexample cannot first appear on a single monomial asymptotic face.  It
must use finite-scale interference between layers, with four terminals the
first interface width at which the abstract sign obstruction disappears.

## Results at a glance

The contribution inventory contains **11 non-duplicate results**.  Failed
optimizer runs and raw trial counts are not included in this number.

| Class | Count | Principal content |
|---|---:|---|
| Theorem/lemma level | 4 | Two-terminal effective activity; single-face obstruction; three-terminal closure; symmetric-book theorem. |
| Exact computer-assisted propositions | 4 | Complete HSW augmentations; two grouped HSW certificates; the `3^18` double-bridge tensor; the 337-seed tangent census. |
| Mechanism and search-geometry results | 3 | Exact four-terminal ambient escape; numerical full-rank signature maps and their singular wall; bounded exact atlas reduction. |

The precise statement, evidence type, scope, and limitation of every item are
listed in `submission_package/RESULTS_LEDGER.md`.  This separation matters:
theorems are not conflated with finite exhaustive results, and neither is
conflated with numerical mechanism evidence.

## Submitted package

| Path | Role |
|---|---|
| `submission_package/RESEARCH_NOTE.md` | Self-contained statements, proofs, exact certificates, and limitations. |
| `submission_package/RESULTS_LEDGER.md` | Structured inventory of all 11 results and their evidence strength. |
| `submission_package/NOVELTY_AND_CLAIMS.md` | Prior-art positioning and precise claim boundary. |
| `submission_package/verify_interface_certificates.py` | Standard-library exact verifier for the finite claims. |
| `submission_package/README.md` | Reproduction instructions. |

## Verification

From the repository root:

```bash
python3 tracks/other/solutions/yanwang-251/submission_package/verify_interface_certificates.py
```

The verifier uses Python integers only for the terminal-signature identities
and crossover.  Its symmetric-book regression enumerates every forest using
integer activities.

## Claim boundary

This submission establishes:

- an exact effective-activity reduction for positive two-terminal networks;
- an exact nonpositivity-preserving formula for three-terminal parallel
  composition;
- an exact four-terminal crossover in the unrestricted positive
  partition-signature cone;
- a conditional single-exposed-face obstruction for a minor-minimal
  counterexample; and
- strict negative correlation for every edge-pair orbit on a symmetric
  `K3 join independent(r)` activity slice.

It explicitly does **not** establish:

- a graph realization of the two abstract four-terminal signatures;
- negative correlation for all disjoint edges;
- the I-Rayleigh conjecture for all graphs; or
- a verifier-accepted counterexample satisfying the success gate of #251.
