# Issue #115 — Public Rust Occam Verifier Port

## Team

| Field | Value |
|---|---|
| Team | Wander (漫步者) |
| Members | Chenxi Wan, Yedi Shen, Junkai Wang |
| Track | `agent-kb` |
| Source challenge | #71 Occam's Circuit |

## Public review status

This PR now contains the complete, self-contained Rust source-and-evidence
snapshot for the #115 port. Review no longer depends on access to a private
companion repository or Release.

The snapshot was exported from the audited `v0.5.0` implementation commit
`e9120224fe0b1f45ed309ad6b40bf7c9c381af38`. It contains the Rust crate,
locked dependencies, tests, fuzz targets, benchmark records, Julia oracle
scripts, migration reports, bounded-synthesis evidence, and an AGPL-3.0
license under [`public-source/`](public-source/).

## What #115 implements

- a strict parser for the official CSV and gate-netlist formats;
- all six fan-in-two gate operations with free input inversion;
- scalar, sample-packed, compiled, and cross-check evaluators;
- gate count, exact-match accuracy, and bit accuracy;
- deterministic reference-circuit and benchmark generation;
- Julia/Rust differential checks;
- resource limits, property tests, malformed-input tests, and fuzz targets;
- pinned logic-tool provenance and reproducible benchmark records;
- bounded exact SAT synthesis with independent extracted-circuit verification.

## Clean-checkout reproduction

From the root of a checkout of this PR branch:

```bash
cd tracks/agent-kb/solutions/RIIR-occam-rust-port/public-source
cargo fmt --all --check
cargo test -p occam71_rust --lib --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

The most relevant verifier checks can also be run directly:

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

Fetch the official #71 data and run the cross-language oracle checks with:

```bash
./scripts/fetch-occam-data.sh
./scripts/verify-oracles.sh
```

The dataset downloader verifies the organizer-published SHA-256 before
installing files under the ignored `vendor/occam-circuit/` directory.

## Evidence map

- [`public-source/README.md`](public-source/README.md) — CLI usage and detailed
  implementation map.
- [`public-source/docs/oracle-results.md`](public-source/docs/oracle-results.md)
  — Julia/Rust compatibility results.
- [`public-source/docs/gap-report.md`](public-source/docs/gap-report.md) —
  migration differences and explicit proof boundary.
- [`public-source/benchmarks/results/`](public-source/benchmarks/results/) — raw
  Apple M4 and Linux x86-64 benchmark evidence.
- [`public-source/docs/synthesis/`](public-source/docs/synthesis/) — bounded SAT
  examples and their limitations.
- [`public-source/SOURCE-MANIFEST.sha256`](public-source/SOURCE-MANIFEST.sha256)
  — hashes for every published snapshot file.

## Scope boundary

This PR proves that the #71 verifier workflow was ported to Rust and is
publicly reproducible. It does not claim that the four large #71 circuits are
globally minimal, and its internal SAT/UNSAT status records are not DRAT/LRAT
proof objects. The public forward challenge submission remains PR #220; the
later inverse-relation certified-optimum work is a separate follow-up.

## License

The public snapshot is licensed under the GNU Affero General Public License
v3.0; see [`public-source/LICENSE`](public-source/LICENSE).
