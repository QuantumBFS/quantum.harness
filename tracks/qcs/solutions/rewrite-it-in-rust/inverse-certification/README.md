# Certified `n=2` Inverse-Relation Controls

This directory contains exact-synthesis artifacts for the linear controls and the first nonlinear
target requested in the Occam #71 inverse follow-up. The gate basis is
`AND OR XOR NAND NOR XNOR`, fan-in two, with free input inversion. The circuit output is
`(x, y, valid)` and may choose any accepted preimage.

| Relation | SAT circuit | Final UNSAT bound | Exhaustive verification | DRAT check |
|---|---:|---:|---:|---:|
| inverse Add, `n=2` | 5 gates | 4 gates | 8/8 rows, 0 mismatch | `VERIFIED` |
| inverse AbsDiff, `n=2` | 1 gate | 0 gates | 4/4 rows, 0 mismatch | `VERIFIED` |
| inverse Multiply, `n=2` | 8 gates | 7 gates | 16/16 rows, 0 mismatch | `VERIFIED` |

The exact CNF, text DRAT proof, circuit, synthesis record, and SHA-256 manifest are under
`add-n2/`, `abs-diff-n2/`, and `multiply-n2-symmetry/`. `checker.txt` files record the
independently built checker revision and complete results. Multiply's SAT upper bound is the
explicit eight-gate `circuit.txt`; its earlier solver timeout is retained only as search provenance
and is not used in the minimum claim.

The v2 CNF orders the two operands of every gate. This is a sound symmetry break because all six
allowed gate operations are commutative: every removed selector assignment has an equivalent
assignment with the inputs exchanged. It changes neither the represented circuits nor the relation.

Reproduce synthesis and proof generation:

```bash
cargo run -p occam71_rust --bin occam_inverse_certify -- \
  add 2 8 60 docs/inverse-certification/add-n2
cargo run -p occam71_rust --bin occam_inverse_certify -- \
  abs-diff 2 8 60 docs/inverse-certification/abs-diff-n2
cargo run --release -p occam71_rust --bin occam_inverse_unsat_proof -- \
  multiply 2 7 docs/inverse-certification/multiply-n2-symmetry
```

Reproduce independent checking with `drat-trim` commit
`2e3b2dc0ecf938addbd779d42877b6ed69d9a985`:

```bash
drat-trim docs/inverse-certification/add-n2/k-minus-1.cnf \
  docs/inverse-certification/add-n2/k-minus-1.drat
drat-trim docs/inverse-certification/abs-diff-n2/k-minus-1.cnf \
  docs/inverse-certification/abs-diff-n2/k-minus-1.drat
drat-trim docs/inverse-certification/multiply-n2-symmetry/k-minus-1.cnf \
  docs/inverse-certification/multiply-n2-symmetry/k-minus-1.drat
```

These are certified minima for the stated `n=2` relations only. They do not establish minima for
larger widths or for the original forward A-D circuits.
