# Rewrite It in Rust — Complete Occam #71 Solution

This submission recovers all four hidden functions from the supplied training
examples, synthesizes compact official-format Boolean circuits, and predicts
the withheld rows by evaluating those circuits.

The result is not a table of memorized answers. One deterministic Rust command
relearns every function, regenerates every circuit and prediction, checks the
organizer's frozen SHA-256 commitments, and reproduces the checked-in artifacts
byte for byte.

## Results

Inputs contain two equal-width, LSB-first unsigned operands `x` and `y`.

| Instance | Recovered function | Widths (in → out) | Train | Test | Gates | Exhaustive cases | Prediction SHA-256 |
|---|---|---:|---:|---:|---:|---:|---|
| mystery-A | `x + y` | 16 → 9 | 2,000 | 2,000 | 37 | 65,536 | `51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7` |
| mystery-B | `abs(x - y)` | 14 → 7 | 1,500 | 2,000 | 50 | 16,384 | `e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28` |
| mystery-C | `x * y` | 12 → 12 | 1,200 | 1,500 | 167 | 4,096 | `c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d` |
| mystery-D | `x² + y²` | 10 → 11 | 400 | 624 | 186 | 1,024 | `b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580` |

All training rows match under both Rust verification backends. Every circuit
also agrees with its recovered arithmetic semantics over its complete input
domain, with zero mismatches. Each prediction hash equals the corresponding
organizer commitment.

## Size–Generalization Study

The release also fixes and executes a complete
`16 tasks × 8 observed fractions × 20 seeds × 8 methods = 20,480 trials`
protocol. It records held-out exact/bit accuracy, full semantic recovery,
description length, official-basis gate count, ambiguity, status, and declared
resource fields for every trial key. All 20,480 keys are unique and all 1,024
task/method/fraction groups contain the expected 20 seeds.

The central result is nuanced: among 8,380 successful trials with both size
measures, gate count and held-out exact accuracy have Spearman
`ρ = +0.3280`; description length and gate count have `ρ = +0.4353`.
Therefore this matrix does **not** support a universal “smaller circuits always
generalize better” rule. Larger successful hypotheses are associated with
higher accuracy here, with task difficulty, method, and sample fraction all
acting as confounders. This is a measured association under the declared
grammar and bounds, not a causal or universal law.

The generic MDL enumerator recovers the full semantics in 2,265/2,560 trials.
Its recovery rises from 104/320 at 0.5% observations to 262/320 at 1%,
300/320 at 2%, 319/320 at 3%, and 320/320 from 5% onward. The bounded
grammar-guided baseline recovers 2,141/2,560; the four-family legacy registry
recovers 800/2,560; the evaluator-only oracle recovers all 2,560. The declared
partial-logic baselines use conservative zero completion and are not presented
as complete ABC/BDD/CEGIS implementations. Runtime and RSS values are
normalized to zero for the deterministic release matrix and are not
performance measurements.

The [full report](research/report.md), [aggregate JSON](research/aggregate.json),
and three hash-locked figures are committed:

- [gate count versus held-out accuracy](research/figures/gates-vs-accuracy.svg)
- [observed fraction versus recovery](research/figures/fraction-vs-recovery.svg)
- [description length versus gate count](research/figures/description-vs-gates.svg)

## How the Learner Works

The production learner follows the challenge's semantic Occam route without a
registry of the four answers:

1. Strictly parse `train.csv` and split each input into two equal LSB-first
   operands.
2. Enumerate a declared, instance-independent expression grammar in increasing
   description cost. Its terminals are `x`, `y`, `0`, and `1`; its operators
   include fixed-width arithmetic, bitwise operations, `min`, `max`, square,
   and small constant shifts.
3. Hash each expression by its behavior on the observed rows, retain one
   deterministic representative per semantic class, and select the first
   zero-error class at minimum description cost.
4. Lower the selected expression through a canonical Boolean builder.
5. Reparse the emitted official netlist and require perfect scalar and packed
   training verification.
6. Exhaustively compare the circuit with the selected expression semantics.
7. Evaluate the reparsed circuit—not the arithmetic helper—on every
   `test_inputs.csv` row.
8. Hash the canonical `input,output\n` bytes and compare them with the frozen
   commitment.

Output width defines fixed-width evaluation semantics; it is not used to
pre-filter candidates by a presumed arithmetic family. Selection never reads
the instance name, test outputs, or commitment. The commitment is a post-hoc
integrity check only. The former four-family registry remains available only
as the explicitly named `legacy-registry` experimental baseline.

Behavioral anti-hardcoding tests recover all four official functions after
renaming the instances, remove each corresponding legacy family in turn, and
exercise twelve previously unseen synthetic functions. Random-label and
permuted-output controls prevent a successful search from being confused with
full-domain semantic recovery.

This is still an inductive-bias claim, not a universality claim: functions
outside the declared grammar or search budget can time out or exhaust their
bound, and training data can leave several minimum-cost expressions
observationally indistinguishable. Reports expose both the termination reason
and equal-cost ambiguity.

## Circuit Construction

The canonical builder orders commutative operands, hash-conses identical
gates, represents inversion for free, applies Boolean identities, and removes
unreachable gates before dense wire renumbering.

- Addition uses a half adder followed by ripple-carry full adders.
- Absolute difference uses ripple borrow plus conditional two's-complement.
- Multiplication compresses weighted partial-product columns.
- Sum of squares feeds both ordered square products into one shared column
  compressor; symmetric products are structurally reused.

The checked-in gate counts are deterministic measured counts. This submission
does not claim globally minimal circuits. The crate's bounded SAT synthesizer
remains independent small-scale evidence for exact minimality where exhaustive
SAT is tractable.

The final circuits also pass a reproducible optimization portfolio. Berkeley
ABC is pinned by commit, archive size, and SHA-256; its candidates are mapped
back into the six unit-cost official gates and accepted only after ABC `cec`
and independent Rust full-domain comparison. A separate exact SAT peephole
pass solves bounded convex windows and rejects timeouts, non-improvements, and
whole-circuit mismatches. Relative to the frozen v0.2.0 baseline
`37/52/168/187`, the verified counts are `37/50/167/186`.

## Reproduce

From the repository root:

```bash
./scripts/fetch-occam-data.sh
./scripts/solve-occam71.sh --check
```

The standard submission directory is independently runnable without private
Git history:

```bash
challenge-71-occam/solutions/rewrite-it-in-rust/search/run-all.sh --check
```

To learn one instance directly through the generic grammar:

```bash
cargo run --release -p occam71_rust -- learn-mdl \
  --train vendor/occam-circuit/datasets/mystery-A/train.csv \
  --test-inputs vendor/occam-circuit/datasets/mystery-A/test_inputs.csv \
  --commitment vendor/occam-circuit/datasets/mystery-A/commitment.sha256 \
  --circuit target/occam71-mdl/mystery-A/circuit.txt \
  --predictions target/occam71-mdl/mystery-A/test_outputs.csv \
  --report target/occam71-mdl/mystery-A/report.json
```

The schema-v2 [`manifest.json`](manifest.json) transitively hashes the
optimized solution, four official MDL reports, research aggregates, figures,
and limitations. The raw 20,480-row matrix remains in the private release
evidence archive; its SHA-256 is rooted in
[`research-manifest.json`](research-manifest.json).

## Verify Independently

```bash
cargo test -p occam71_rust --test solution_artifacts -- --nocapture
julia --startup-file=no scripts/verify-occam71.jl
```

The Rust artifact test reparses every circuit and checks training plus predicted
test rows with scalar and packed backends. The Julia command uses the official
organizer verifier independently.

Remote evidence:

- [Complete standard #71 submission PR](https://github.com/QuantumBFS/quantum.harness/pull/220)

Because the implementation repository is private, GitHub Actions and release
links are visible only to authorized reviewers. Exact v0.3.0 run links are
recorded in the private completion report and both PR descriptions.
