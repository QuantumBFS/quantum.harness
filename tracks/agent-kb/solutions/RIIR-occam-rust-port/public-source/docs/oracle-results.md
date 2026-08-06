# Julia–Rust Oracle Results

## Environment

- Julia: `1.12.6`
- Rust: `rustc 1.95.0 (59807616e 2026-04-14)`
- Cargo: `1.95.0 (f2d3ce0bd 2026-03-21)`
- Date: 2026-07-27

## Results

This generated section is derived from the locked
`tests/oracles/occam-v1.json` manifest.

<!-- BEGIN GENERATED ORACLE RESULTS -->

Official archive SHA-256: `c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b`

| Case | Verifier | Gates | Samples | Exact matches | Correct bits | Total bits | Exact-match accuracy | Bit accuracy |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| official-add-8 | Julia | 37 | 2000 | 2000 | 18000 | 18000 | 1.000000 | 1.000000 |
| official-add-8 | Rust scalar | 37 | 2000 | 2000 | 18000 | 18000 | 1.000000 | 1.000000 |
| official-add-8 | Rust packed | 37 | 2000 | 2000 | 18000 | 18000 | 1.000000 | 1.000000 |
| practice-add-n4 | Julia | 17 | 120 | 120 | 600 | 600 | 1.000000 | 1.000000 |
| practice-add-n4 | Rust scalar | 17 | 120 | 120 | 600 | 600 | 1.000000 | 1.000000 |
| practice-add-n4 | Rust packed | 17 | 120 | 120 | 600 | 600 | 1.000000 | 1.000000 |
| practice-mul-n4 | Julia | 128 | 120 | 120 | 960 | 960 | 1.000000 | 1.000000 |
| practice-mul-n4 | Rust scalar | 128 | 120 | 120 | 960 | 960 | 1.000000 | 1.000000 |
| practice-mul-n4 | Rust packed | 128 | 120 | 120 | 960 | 960 | 1.000000 | 1.000000 |

<!-- END GENERATED ORACLE RESULTS -->

The reference generators are also tested exhaustively over all 256 pairs of
four-bit integers. This checks disclosed practice semantics independently of
the sampled training rows.

## Reproduction

```bash
./scripts/fetch-occam-data.sh

oracle_dir=$(mktemp -d /tmp/occam71-oracle.XXXXXX)
cargo run --quiet --release -p occam71_rust -- generate-adder \
  --bits 4 --output "$oracle_dir/practice-add-n4.txt"
cargo run --quiet --release -p occam71_rust -- generate-multiplier \
  --bits 4 --output "$oracle_dir/practice-mul-n4.txt"

julia vendor/occam-circuit/verify.jl \
  vendor/occam-circuit/adder8.txt \
  vendor/occam-circuit/datasets/mystery-A/train.csv
julia vendor/occam-circuit/verify.jl \
  "$oracle_dir/practice-add-n4.txt" \
  vendor/occam-circuit/datasets/practice-add-n4/train.csv
julia vendor/occam-circuit/verify.jl \
  "$oracle_dir/practice-mul-n4.txt" \
  vendor/occam-circuit/datasets/practice-mul-n4/train.csv

cargo run --quiet --release -p occam71_rust -- verify \
  --circuit "$oracle_dir/practice-add-n4.txt" \
  --dataset vendor/occam-circuit/datasets/practice-add-n4/train.csv
cargo run --quiet --release -p occam71_rust -- verify \
  --circuit "$oracle_dir/practice-mul-n4.txt" \
  --dataset vendor/occam-circuit/datasets/practice-mul-n4/train.csv
```

These results establish verifier-format compatibility and equality of Julia,
Rust scalar, and Rust packed semantics. Controlled performance measurements
are recorded under `benchmarks/results/`.
