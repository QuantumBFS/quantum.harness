# Bounded exact circuit synthesis

This optional research extension turns a complete Boolean truth table into a
small verifier-compatible netlist. It is deliberately separate from the fast
verification path and does not claim to solve the full hidden-function
discovery problem from challenge #71.

## Method

For each gate bound, the Rust implementation builds a universal acyclic
circuit in CNF:

- exactly one of `AND`, `OR`, `XOR`, `NAND`, `NOR`, and `XNOR` is selected per
  gate;
- each gate input selects an input or earlier wire, with free inversion;
- per-row semantic variables enforce the selected truth table;
- every circuit output selects an input or wire, again with free inversion.

The embedded [Varisat 0.2.2 solver](https://docs.rs/varisat/0.2.2/varisat/)
checks bounds in increasing order. A deterministic SAT self-reduction chooses
the first satisfiable operation and literal in a fixed order, so checked-in
netlists are reproducible rather than dependent on an arbitrary solver model.
CNF variable, clause, literal, truth-table, gate, and wall-clock limits are all
explicit.

Input datasets must be complete, duplicate-free truth tables. Partial or noisy
training data are rejected because an exact result would otherwise be
misleading.

## Half-adder result

The complete two-input half-adder produced these attempts:

| Gate bound | Result | Variables | Clauses | Literals |
| ---: | --- | ---: | ---: | ---: |
| 0 | UNSAT | 8 | 30 | 48 |
| 1 | UNSAT | 38 | 222 | 636 |
| 2 | SAT | 72 | 472 | 1,376 |

The extracted two-gate netlist is:

```text
INPUTS 2
w1 = AND x1 x2
w2 = XOR x1 x2
OUTPUTS w2 w1
```

It is reparsed and checked against all four rows by both Rust scalar and packed
backends before the SAT result is returned. The reproducibility script also
checks it with the original Julia verifier. See
[`half-adder-certificate.json`](half-adder-certificate.json) and
[`half-adder.txt`](half-adder.txt).

The two UNSAT solver answers plus the independently verified 2-gate model
support minimality within this encoding. They are not DRAT or another
independently checkable formal UNSAT proof; no proof trace is emitted.

## Two-bit adder boundary experiment

The four-input, three-output exhaustive two-bit addition table was run with
`--max-gates 7 --timeout-seconds 30`. Bounds 0 through 5 returned UNSAT. The
wall-clock budget expired while solving bound 6, so bound 7 was not attempted
and no netlist was claimed. This honest bounded result is recorded in
[`two-bit-adder-certificate.json`](two-bit-adder-certificate.json).

This experiment identifies the next scaling bottleneck: proving absence at
small bounds is much harder than verifying a known seven-gate ripple-carry
adder. Useful next steps are symmetry breaking, incremental bound encoding, and
optional proof logging/checking.

## Usage

```bash
cargo run --release -p occam71_rust -- synthesize \
  --dataset challenge-71-occam/tests/fixtures/half-adder.csv \
  --max-gates 2 \
  --timeout-seconds 30 \
  --output /tmp/half-adder.txt \
  --certificate /tmp/half-adder-certificate.json
```

Regenerate the half-adder model and cross-check the checked-in evidence:

```bash
./scripts/verify-synthesis-evidence.sh
```

The timeout returns control at the configured deadline by abandoning the
in-process worker. Rust does not forcibly cancel that worker in a long-lived
embedding; command-line processes exit immediately after writing the timeout
certificate.
