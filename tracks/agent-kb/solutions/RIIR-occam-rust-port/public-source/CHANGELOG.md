# Changelog

All notable releases of the implementation lineage are documented here. The
stable #115 v0.5.0 source is also published as a self-contained PR snapshot.

## [0.5.0] - 2026-07-28

### Added

- Genuine partial-PLA ABC, ROBDD, bounded SAT/CEGIS, seeded
  grammar-evolution, and explicit memorization research learners.
- One isolated child process per trial with positive wall-clock runtime and
  peak-RSS measurements.
- A deterministic, host-independent semantic projection linked one-to-one
  with the measured trial records.
- A complete measured study with 16 tasks, 8 fractions, 20 seeds, and 8
  methods: 20,480 total trials.
- Independent, provenance-locked Yosys, Yosys-ABC, and CHIPS Alliance
  Espresso audits whose outputs are reparsed and evaluated in Rust.
- Linux CI gates for full semantic reproduction and positive performance
  measurements.
- A standalone source snapshot containing the complete research
  implementation.

### Changed

- The Rust package and CLI version are now `0.5.0`.
- Runtime and RSS aggregates now use real successful-child measurements
  instead of deterministic zero placeholders.
- The research conclusion is restricted to grammar alignment on the declared
  tasks, grammar, completion rules, and search bounds.
- ABC output hashing records and removes only its volatile timestamp banner
  before hashing; the logic body remains unchanged.

### Preserved

- The four #71 solutions and organizer commitment hashes.
- Final gate counts `37`, `50`, `167`, and `186`.
- The immutable `v0.3.0` tag, original matrix, figures, report, and release
  assets.
- The checksum-pinned ABC optimization and Rust/Julia/full-domain evidence
  chain.

`v0.4.0` was a working candidate name for Scheme A and was superseded before
any tag or Release was created.

## [0.3.0] - 2026-07-28

- Added generic MDL recovery for all four official #71 tasks.
- Reduced verified official circuits to `37`, `50`, `167`, and `186` gates.
- Added the original deterministic 20,480-trial generalization matrix.
- Published the hash-locked source-and-evidence release lineage.

## [0.2.0] - 2026-07-28

- Completed all four #71 hidden-function instances.
- Matched every frozen prediction commitment.
- Added deterministic solution generation and exhaustive-domain validation.

## [0.1.0] - 2026-07-28

- Delivered the audited #115 migration from the Julia verification workflow
  to Rust.
- Added scalar, packed, and cross-check verification backends.
- Added reproducible benchmarks, Oracle comparisons, CI, and fuzz targets.
