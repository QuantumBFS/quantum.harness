# Public v0.5.0 Occam Rust Port Snapshot

This directory is a self-contained public export of implementation commit
`e9120224fe0b1f45ed309ad6b40bf7c9c381af38` for Quantum Harness issue #115.
It is intentionally frozen before the separate inverse-relation extension.

## Layout

- `challenge-71-occam/src/` — parser, scalar/packed/compiled evaluators,
  verifier, circuit generators, learning code, optimizer, and bounded SAT
  synthesis.
- `challenge-71-occam/tests/` — CLI, property, differential, artifact, and
  synthesis tests.
- `fuzz/` — isolated cargo-fuzz package and seed corpus.
- `benchmarks/` — protocols, raw JSON records, and rendered reports.
- `scripts/verify-oracles.sh` — Rust/Julia oracle compatibility check.
- `docs/oracle-results.md` — recorded oracle results.
- `docs/gap-report.md` — migration gaps and formal-proof limitations.
- `docs/synthesis/` — small exact-synthesis examples.
- `SOURCE-MANIFEST.sha256` — hash manifest for the public snapshot.

## Build and test

Rust stable is sufficient for the main workspace:

```bash
cargo fmt --all --check
cargo test -p occam71_rust --lib --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

Run the core differential suite:

```bash
cargo test -p occam71_rust \
  --test cli \
  --test compiled_differential \
  --test direct_packed_parse \
  --test official_compat \
  --test packed_differential \
  --test packed_layout \
  --test properties \
  --test sat_synthesis \
  --locked
```

## Official data and cross-language verification

```bash
./scripts/fetch-occam-data.sh
./scripts/verify-oracles.sh
```

The fetch script downloads the organizer release and checks SHA-256
`c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b`
before extraction. Julia is needed only for the cross-language oracle command.

Verify an official circuit with all Rust backends:

```bash
cargo run --release -p occam71_rust -- verify \
  --backend cross-check \
  --circuit vendor/occam-circuit/adder8.txt \
  --dataset vendor/occam-circuit/datasets/mystery-A/train.csv
```

`cross-check` evaluates through the scalar and packed paths and rejects any
disagreement. `--backend scalar` and `--backend packed` are also available.

## Benchmarks

Correctness preflight:

```bash
./scripts/run-benchmarks.sh --verify-only
```

Full Julia/Rust benchmark:

```bash
./scripts/run-benchmarks.sh
```

Recorded Apple M4 results are in
`benchmarks/results/2026-07-28-apple-m4.md`; independently executed Linux
x86-64 records are in `benchmarks/results/linux-x86-runner/`.

## Fuzzing

With nightly Rust and `cargo-fuzz` installed:

```bash
cargo fuzz check --fuzz-dir fuzz
cargo fuzz run --fuzz-dir fuzz parse_evaluate -- -max_total_time=30
```

## Exact-synthesis boundary

The checked-in half-adder example records UNSAT at gate bounds 0 and 1, SAT
at bound 2, and independent exhaustive verification of the extracted circuit.
This is solver-backed development evidence within the implemented encoding.
It is not a machine-checkable minimality theorem because no DRAT/LRAT proof
object is emitted or checked. See `docs/synthesis/README.md` and
`docs/gap-report.md`.

## License

GNU Affero General Public License v3.0; see `LICENSE`.
