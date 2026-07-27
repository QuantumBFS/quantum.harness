# Rewrite It In Rust! — Occam's Circuit

## Team

| | |
|---|---|
| **Team name** | Rewrite It In Rust! |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Recover a hidden Boolean function from polynomially many input-output examples by finding a small circuit consistent with the training data, then use that circuit to predict the hidden test outputs. |
| **Catalog issue** | Addresses #71 — “Occam's Circuit — recover a hidden logic function from polynomially many examples”, released by Jin-Guo Liu, HKUST(Guangzhou). |
| **Track** | `qcs`, following the deliverable path specified by challenge #71. |

## Research Question

The training data reveal only a small fraction of each Boolean truth table, so
many functions can fit every observed row. The challenge asks whether an
explicit Occam objective—prefer the smallest consistent circuit—recovers the
hidden arithmetic rule and generalizes to the withheld inputs.

We will study the relationship between:

- consistency with the partial truth table;
- circuit size;
- hidden-test generalization;
- the different structural difficulty of addition, absolute difference,
  multiplication, and sum-of-squares-like functions.

## Approach

We will compare complementary routes allowed by the challenge:

1. infer simple semantic arithmetic hypotheses from the training examples;
2. synthesize official-format Boolean circuits for consistent hypotheses;
3. minimize the circuits with Boolean simplification and structural sharing;
4. use bounded exact synthesis on small instances as a reference for
   minimality;
5. evaluate whether smaller consistent circuits generalize better than
   memorizing constructions.

Candidate selection uses the training data only. The hidden-output commitments
are reserved for final verification.

## Deliverables

Following challenge #71, this solution branch will contain:

- `mystery-*.txt` circuits in the official fanin-2 netlist format;
- predicted `test_outputs.csv` files for the mystery instances;
- committed search and circuit-synthesis scripts;
- a pitch-style README explaining the method;
- the inferred hidden functions;
- training and hidden-test accuracy;
- gate counts and comparisons between search strategies;
- reproduction instructions and limitations.

Generated intermediate data will remain outside the committed solution tree as
required by the challenge.

## Status

**Registered and in progress.** Results and final submission artifacts will be
added to this same branch as the investigation proceeds.
