## Team

| | |
|---|---|
| **Team name** | lifeIsShort |
| **Members** | Shigang Ou (@Osgood001) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Relate the open arboreal-gas edge negative-correlation problem to a proved local theorem: every weighted random-forest star marginal is real stable, so every adjacent edge pair is negatively correlated. |
| **Catalog issue** | Addresses #251 as a scoped positive result around the stated open problem, released by Kun Chen, Institute of Theoretical Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/other`, from the issue's `Method: Other` field. |

## Challenge relationship

Issue #251 asks for a finite weighted-forest counterexample to global pairwise edge negative correlation:

```text
For arbitrary distinct edges e, f:

    P(e,f) <= P(e) P(f)
```

This submission does not claim such a counterexample and does not close the disjoint-edge part of the open problem. It proves the adjacent-edge half instead:

```text
Original open problem

      arbitrary distinct edges e, f
                 |
                 v
          P(e,f) <= P(e) P(f)
                 |
          +------+------+
          |             |
          v             v
      adjacent       disjoint
     edge pairs     edge pairs
     (one star)   (four endpoints)
```

The submitted theorem fully resolves the left branch: for any finite loopless multigraph with nonnegative edge activities and any vertex `v`, the complete generating polynomial of selected incident edges at `v` is multiaffine and real stable. Therefore the incident-edge marginal is strongly Rayleigh, and adjacent incident edges are negatively correlated. The result also persists under feasible coordinate conditioning on edges outside the star.

## Submitted package

The complete author-prepared submission bundle is kept under `submission_package/`.

Key files:

| Path | Role |
|---|---|
| `submission_package/Stable_Incident_Edge_Marginals.pdf` | 12-page manuscript reading copy |
| `submission_package/incident_edge_marginals.tex` | self-contained LaTeX source |
| `submission_package/arxiv_source.zip` | arXiv-ready source archive |
| `submission_package/EJC_initial_submission_materials.zip` | initial E-JC submission materials |
| `submission_package/manuscript_source_and_audit.zip` | source plus exact finite regression script and logs |
| `submission_package/NOVELTY_AND_CLAIMS.md` | precise claim boundary and prior-art positioning |
| `submission_package/REQUIRED_AUTHOR_ACTIONS.md` | author-side checks required before arXiv or journal submission |
| `submission_package/full_submission_bundle.tar.gz` | original complete archive received for this PR update |

The package is a challenge submission artifact, not authorization for anyone else to submit the manuscript to arXiv or a journal in the named author's place. The author-action checklist is included unchanged.

## Verification

- Package checksums from the received bundle passed:

```bash
cd tracks/other/solutions/lifeIsShort-251/submission_package
sha256sum -c SHA256SUMS
```

- The package includes `arxiv_compile_test.log` for the LaTeX build check.
- The finite regression and audit material is archived in `manuscript_source_and_audit.zip`.

## Claim boundary

This PR should be reviewed as a rigorous local theorem and manuscript package connected to issue #251, not as a witness satisfying the original counterexample success gate. It establishes:

- real stability of arbitrary weighted random-forest star marginals;
- strong Rayleighness and negative association within a vertex star;
- adjacent-edge negative correlation for arbitrary inhomogeneous nonnegative activities;
- preservation under feasible exterior coordinate conditioning.

It explicitly does not establish:

- negative correlation for disjoint edges;
- strong Rayleighness of the full unrooted forest measure;
- a finite counterexample with `Z_ef Z > Z_e Z_f`.
