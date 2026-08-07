# Issue 71: train-only symbolic, incomplete Espresso, and BDD/ABC hybrid

This directory is an independent, reproducible experiment for
`QuantumBFS/quantum.harness#71`.

Safety and information boundaries:

- `routes.py discover` receives only explicit `train.csv` paths. It does not
  scan the repository, import a generator, read test inputs/commitments, or
  consume competitor PR content.
- Public commitment auditing is a separate post-freeze process.
- The incomplete PLA uses `.type fr`: observed `1` and `0` bits are the ON/OFF
  sets and omitted minterms are don't-cares under Espresso semantics.
- The companion BLIF does not rely on omission: `.exdc` explicitly lists every
  unseen minterm for every output.
- Official Berkeley ABC source is pinned by commit and statically inspected
  before execution. The standalone Espresso entry point uses the embedded
  Berkeley Espresso implementation, passing `F`, `D`, and `R` to `espresso`.
- Heavy tool builds and synthesis run under Slurm. Root random seed is 42.

The semantic hybrid builds four shared reduced ordered BDDs from each frozen
hypothesis, selects the smallest, hands its cofactors to ABC, maps to K=2 LUTs,
then translates each two-input truth table to one challenge gate (free
complemented signal tokens). Every resulting challenge circuit is evaluated
bit-parallel over its entire input domain.
