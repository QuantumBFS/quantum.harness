# Rewrite It In Rust! — Occam's Circuit

## Team

| | |
|---|---|
| **Team name** | Rewrite It In Rust! |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Recover the hidden arithmetic functions in Occam's Circuit from sparse examples, synthesize compact official-format Boolean circuits in Rust, and test whether a simple semantic hypothesis generalizes to the committed hidden outputs. |
| **Catalog issue** | Addresses #71 — “Occam's Circuit — recover a hidden logic function from polynomially many examples”, released by Jin-Guo Liu, HKUST(Guangzhou). |
| **Track** | `qcs`, as required by the challenge's standard fork-and-PR deliverable path. |

## Approach

We use a semantic Occam learner followed by deterministic Boolean circuit
synthesis:

1. decode the two LSB-first integer operands from each training row;
2. score a fixed registry of simple arithmetic families using training data
   only;
3. require one unique zero-error family;
4. synthesize its circuit with free-inversion normalization, Boolean
   simplification, structural sharing, dead-gate elimination, and optimized
   arithmetic building blocks;
5. produce withheld predictions by evaluating the generated circuit, not by
   calling the recovered arithmetic formula directly;
6. verify the serialized circuit with Rust scalar, Rust packed, and Julia
   evaluators;
7. exhaustively compare each circuit with its selected arithmetic semantics
   over the full input domain;
8. compare the prediction SHA-256 with the commitment published in issue #71.

Organizer commitments are used only for final verification. They are not used
to select a candidate family.

## Working Repository

- Repository:
  [`JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port)
- Rust workspace: `challenge-71-occam/`
- Planned submission directory:
  `challenge-71-occam/solutions/rewrite-it-in-rust/`
- Solver design:
  `docs/plans/2026-07-28-occam71-rust-solver-design.md`

The repository began as the completed #115 Rust migration of the official
Occam verifier. The #71 learner and submission artifacts are a separate
deliverable built on that independently checked parser, scalar evaluator,
packed evaluator, Julia oracle, fuzzing, and benchmark foundation.

## Current Evidence

Training-only candidate scoring has identified one zero-error arithmetic family
for each mystery instance:

| Instance | Selected family | Training agreement |
|---|---|---:|
| mystery-A | addition | 2000/2000 |
| mystery-B | absolute difference | 1500/1500 |
| mystery-C | multiplication | 1200/1200 |
| mystery-D | sum of squares | 400/400 |

As a separate post-selection check, predictions from these semantics match all
four SHA-256 commitments anchored in issue #71. This establishes the target
semantics, but it is not yet the final submission: the committed Rust learner
must still generate and evaluate the official circuits and reproduce the
prediction artifacts end to end.

## Deliverables on This Branch

This registration PR will accumulate the final #71 deliverables as they become
ready:

- `mystery-A.txt` through `mystery-D.txt` official-format circuits;
- predicted `test_outputs.csv` for every mystery instance;
- committed Rust learning, synthesis, optimization, and reporting code;
- deterministic per-instance reports and an aggregate manifest;
- a pitch-style solution README with recovered functions, gate counts, hashes,
  reproduction commands, and limitations;
- Rust scalar, Rust packed, Julia, full-domain, commitment, and
  byte-reproducibility evidence.

We will report actual gate counts and optimization results without claiming
global circuit minimality. Small bounded-SAT experiments remain supporting
evidence rather than the main solver.

## Status

**Registered and in progress.** The semantic recovery and solver design are
complete. The Rust learner, optimized circuit generation, official A–D
artifacts, and final end-to-end verification are being implemented and will be
added to this same PR branch.
