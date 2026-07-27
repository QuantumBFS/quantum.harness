# Reproduction Prompt

Reproduce and audit the `WangTheoPhys` solution to Quantum Harness
[#129](https://github.com/QuantumBFS/quantum.harness/issues/129) without using
private chat history.

## Source

```text
repository:
https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust

validated submission revision:
006aae252e50a469934d11d0d12e1cb05a57477c

public release:
https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust/releases/tag/v0.1.0

validated numerical calculation revision:
c5a3aa698c26826b5feae470caea9c4b47680268

license:
AGPL-3.0
```

Clone and build the exact submission revision with its committed lockfile:

```bash
git clone \
  https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust.git
cd quantum-harness-129-workbench-rust
git checkout v0.1.0
cargo build --release --locked
```

The recorded run used Rust 1.95.0, Cargo 1.95.0, arm64 Apple M4, 16 GiB RAM,
and 10 Rayon workers. Record any environment difference.

## Input and units

Use only `fixtures/h2o-631g-fc/FCIDUMP` with SHA-256:

```text
826dd373a8b6047dff8136168431a803b59d9ef029a074da3b8f74f22603db3e
```

Verify it before calculation:

```bash
shasum -a 256 fixtures/h2o-631g-fc/FCIDUMP
```

The system is H2O/6-31G in canonical RHF orbitals, with the oxygen 1s spatial
orbital frozen, 12 active spatial orbitals, 8 active electrons, and 245,025
determinants. Geometry is `R(O-H)=0.967 Å` and
`angle(H-O-H)=107.6°`. Coordinate inputs are Angstrom; PySCF/libcint converts
them internally to Bohr. Energies and energy-valued integrals are Hartree.
Wavefunction coefficients, amplitudes, overlaps, and orbital coefficients are
dimensionless.

## Quality gates

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --locked
git diff --check
find fixtures -name '*.json' -print0 | xargs -0 -n1 jq empty
```

For an optional PySCF oracle audit:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python \
  -r scripts/oracle/requirements.txt
.venv/bin/python -m unittest scripts.oracle.test_units -v
```

Python is oracle-only. Do not regenerate or overwrite committed fixtures as a
prerequisite for the Rust calculations.

## FCI

```bash
RAYON_NUM_THREADS=10 target/release/ed_workbench_rs davidson \
  fixtures/h2o-631g-fc/FCIDUMP \
  --residual-tolerance 1e-7 \
  --max-iterations 60 --max-subspace 20
```

Expected energy: `-76.12117420414197` hartree. Require residual at most
`1e-7` and error at most `1e-8` hartree against the committed PySCF value.
Do not run the dense `verify` subcommand on this 245,025-determinant space.

## CC(1)-CC(8)

```bash
RAYON_NUM_THREADS=10 target/release/ed_workbench_rs cc-series \
  fixtures/h2o-631g-fc/FCIDUMP \
  fixtures/h2o-631g-fc/reference.json \
  --published-reference fixtures/h2o-631g-fc/hirata2000-table2.json \
  --max-rank 8 --residual-tolerance 1e-6 --max-iterations 100
```

Expected total energies by rank:

```text
-75.984502842520712
-76.119629519205702
-76.120725652588177
-76.121162423556896
-76.121170991020350
-76.121174144494702
-76.121174198217162
-76.121174196144139
```

Expected `E(CC)-E(FCI)`:

```text
0.136671361621254
0.001544684936263
0.000448551553788
0.000011780585069
0.000003213121616
0.000000059647263
0.000000005924804
0.000000007997826
```

Require every rank to converge below residual `1e-6`, and published
verification to report `PASS`. CC(2), meaning CCSD here, must agree with
PySCF CCSD `-76.119629518903210` within `1e-8` hartree.

## CI(1)-CI(8) and MBPT(1)-MBPT(20)

```bash
RAYON_NUM_THREADS=10 target/release/ed_workbench_rs level3-series \
  fixtures/h2o-631g-fc/FCIDUMP \
  fixtures/h2o-631g-fc/reference.json \
  --published-reference fixtures/h2o-631g-fc/hirata2000-table2.json \
  --max-ci-rank 8 --max-mbpt-order 20 \
  --ci-residual-tolerance 1e-7 \
  --max-iterations 100 --max-subspace 24
```

Expected `E(CI)-E(FCI)` by rank:

```text
0.136671361621538
0.006857789058358
0.005853940551802
0.000174843492616
0.000103257047385
0.000001416471065
0.000000369418771
-0.000000000002004
```

Expected `E(MBPT)-E(FCI)` partial-sum differences, orders 1 through 20:

```text
0.136671361621538  0.008214955387700  0.006577356213612
0.001299545129385  0.000582527596691  0.000178442636724
0.000084838275626  0.000022489352006  0.000013644732491
0.000003004694747  0.000002247016397  0.000000374837001
0.000000394209707  0.000000029304132  0.000000075118919
-0.000000004699885 0.000000015783101 -0.000000003661626
0.000000003714234 -0.000000001489667
```

Require CI residuals at most `1e-7`, a variationally non-increasing CI
sequence, CI(8)-FCI absolute difference below `1e-8` hartree, and published
verification `PASS`.

## Published precision

Compare `E(method)-E(FCI)` with the equilibrium CC, CI, and MBPT columns in
Hirata and Bartlett, Chemical Physics Letters 321, 216-224 (2000), Table 2,
DOI `10.1016/S0009-2614(00)00387-0`. The table prints six digits after the
decimal point. Round both computed and published values to integer
microhartree; do not infer unprinted precision.

## Failure report

For any mismatch, report:

- checked-out commit and whether `Cargo.lock` changed;
- `rustc -V`, `cargo -V`, OS, CPU, RAM, and `RAYON_NUM_THREADS`;
- FCIDUMP SHA-256 and complete command;
- exit code and stderr;
- method, rank/order, energy, oracle difference, residual, and iterations;
- whether geometry, basis, frozen-core choice, units, input bytes, or
  six-decimal rounding differ from the contract above.

The complete machine-readable records are
`fixtures/h2o-631g-fc/cc_series_results.json` and
`fixtures/h2o-631g-fc/level3_series_results.json`. The Kállay 2001 DZ/DZP
systems are extended targets and are not included in this validated
submission.
