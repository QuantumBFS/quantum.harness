# Certified `n=2` Inverse-Relation Controls

This directory contains exact-synthesis artifacts for the two linear controls requested in the
Occam #71 inverse follow-up. The gate basis is `AND OR XOR NAND NOR XNOR`, fan-in two, with free
input inversion. The circuit output is `(x, y, valid)` and may choose any accepted preimage.

| Relation | SAT circuit | Final UNSAT bound | Exhaustive verification | DRAT check |
|---|---:|---:|---:|---:|
| inverse Add, `n=2` | 5 gates | 4 gates | 8/8 rows, 0 mismatch | `VERIFIED` |
| inverse AbsDiff, `n=2` | 1 gate | 0 gates | 4/4 rows, 0 mismatch | `VERIFIED` |

The exact CNF, text DRAT proof, circuit, synthesis record, and SHA-256 manifest are under
`add-n2/` and `abs-diff-n2/`. `checker.txt` records the independently built checker revision and
complete results. `source/` is the frozen Rust source snapshot that generated these artifacts,
including the relation semantics, forbidden-tuple CNF, proof exporter, CLI, and tests.

Generator invocations used in the mapped build tree described by `source/README.md`:

```bash
cargo run -p occam71_rust --bin occam_inverse_certify -- \
  add 2 8 60 tracks/qcs/solutions/rewrite-it-in-rust/inverse-certification/add-n2
cargo run -p occam71_rust --bin occam_inverse_certify -- \
  abs-diff 2 8 60 tracks/qcs/solutions/rewrite-it-in-rust/inverse-certification/abs-diff-n2
```

Reproduce independent checking with `drat-trim` commit
`2e3b2dc0ecf938addbd779d42877b6ed69d9a985`:

```bash
drat-trim tracks/qcs/solutions/rewrite-it-in-rust/inverse-certification/add-n2/k-minus-1.cnf \
  tracks/qcs/solutions/rewrite-it-in-rust/inverse-certification/add-n2/k-minus-1.drat
drat-trim tracks/qcs/solutions/rewrite-it-in-rust/inverse-certification/abs-diff-n2/k-minus-1.cnf \
  tracks/qcs/solutions/rewrite-it-in-rust/inverse-certification/abs-diff-n2/k-minus-1.drat
```

These are certified minima for the stated `n=2` controls only. The `n=2` Multiply run timed out at
gate bound 7 after in-process UNSAT results for bounds 0 through 6; no Multiply minimum is claimed.
