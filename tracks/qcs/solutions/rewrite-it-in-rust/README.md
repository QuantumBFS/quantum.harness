# Rewrite It In Rust! — Complete Occam's Circuit Submission

## Team

| | |
|---|---|
| **Team name** | Rewrite It In Rust! |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Challenge** | Addresses #71 — Occam's Circuit |
| **Track** | `qcs` |
| **Releaser** | Jin-Guo Liu, HKUST(Guangzhou) |

## Result

We recovered every hidden arithmetic function from the training examples,
synthesized an official-format Boolean circuit, and generated every withheld
prediction by evaluating that circuit.

| Instance | Recovered function | Gates | Training | Test | Full domain | Prediction SHA-256 |
|---|---|---:|---:|---:|---:|---|
| mystery-A | `x + y` | 37 | 2,000/2,000 | 2,000/2,000 | 65,536/65,536 | `51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7` |
| mystery-B | `abs(x - y)` | 52 | 1,500/1,500 | 2,000/2,000 | 16,384/16,384 | `e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28` |
| mystery-C | `x * y` | 168 | 1,200/1,200 | 1,500/1,500 | 4,096/4,096 | `c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d` |
| mystery-D | `x² + y²` | 187 | 400/400 | 624/624 | 1,024/1,024 | `b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580` |

All four SHA-256 values exactly match the commitments anchored in #71.
Training and predicted test rows achieve exact-match and bit accuracy `1.0`
with Rust scalar, Rust packed, and the independent official Julia verifier.
The full-domain columns are circuit-versus-arithmetic comparisons with zero
mismatches.

## Method

We use the challenge's explicitly permitted semantic Occam route:

1. Strictly parse the polynomial training examples and split each input into
   equal LSB-first operands.
2. Score one instance-independent candidate registry: addition, absolute
   difference, multiplication, and sum of squares.
3. Require exactly one width-compatible family with zero training errors.
4. Lower that family through a canonical Rust Boolean builder.
5. Reparse the emitted circuit, cross-check scalar and packed training
   verification, and exhaustively validate the full input domain.
6. Evaluate the reparsed circuit on `test_inputs.csv`, emit canonical
   `input,output\n` bytes, and only then compare the organizer commitment.

The instance name and commitment never participate in candidate selection.

The circuit builder orders commutative operands, hash-conses repeated gates,
uses free inversion, applies Boolean identities, removes dead gates, and
dense-renumbers wires. Add and absolute difference use ripple carry/borrow.
Multiplication and the shared sum-of-squares construction compress weighted
partial-product columns.

Gate counts are deterministic measured results. We do not claim global
minimality for these large circuits; the companion bounded SAT implementation
provides exact minimality evidence only on small complete truth tables.

## Deliverables

- [`circuits/`](circuits/) — four official-format netlists;
- [`predictions/`](predictions/) — four predicted `test_outputs.csv` files;
- [`reports/`](reports/) — stable candidate, verifier, exhaustive-domain, and
  commitment evidence;
- [`manifest.json`](manifest.json) — aggregate paths, gate counts, and hashes;
- [`search/rust/`](search/rust/) — self-contained Rust 2024 source snapshot;
- [`search/run-all.sh`](search/run-all.sh) — deterministic A–D regeneration.

## Reproduce

Download and unpack the checksum-pinned package from issue #71, then pass its
`datasets/` directory to:

```bash
./tracks/qcs/solutions/rewrite-it-in-rust/search/run-all.sh \
  /path/to/occam-circuit/datasets \
  /tmp/rewrite-it-in-rust-regenerated

git diff --no-index --exit-code \
  tracks/qcs/solutions/rewrite-it-in-rust/circuits \
  /tmp/rewrite-it-in-rust-regenerated/circuits
git diff --no-index --exit-code \
  tracks/qcs/solutions/rewrite-it-in-rust/predictions \
  /tmp/rewrite-it-in-rust-regenerated/predictions
git diff --no-index --exit-code \
  tracks/qcs/solutions/rewrite-it-in-rust/reports \
  /tmp/rewrite-it-in-rust-regenerated/reports
```

The source snapshot builds with:

```bash
cargo build --release \
  --manifest-path tracks/qcs/solutions/rewrite-it-in-rust/search/rust/Cargo.toml
```

## Independent Evidence

The complete development repository retains property tests, fuzz targets,
benchmark evidence, the official Julia integration, and the bounded SAT
experiment:

- [Audited implementation commit](https://github.com/JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port/commit/ed9482b416cd366bf97abeaf867636f52ae6a52e)
- [Linux cross-platform correctness, clean regeneration, and Julia verification](https://github.com/JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port/actions/runs/30315885576)
- [Six-target nightly bounded fuzzing; zero crash artifacts](https://github.com/JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port/actions/runs/30315906994)
- [Complete solution pitch and implementation](https://github.com/JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port/tree/ed9482b416cd366bf97abeaf867636f52ae6a52e/challenge-71-occam/solutions/rewrite-it-in-rust)
