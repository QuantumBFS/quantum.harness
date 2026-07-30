# Challenge 115 Brief

Source: https://github.com/QuantumBFS/quantum.harness/issues/115

## Objective

Port one Quantum Harness challenge to Rust, using the original implementation as
the oracle and benchmark reference.

## Local Choice

This repo chooses #71 Occam's Circuit as the source challenge because its
verification path is discrete and bit-exact:

- no floating-point tolerance;
- no eigensolver convergence;
- no Monte Carlo error bars;
- no GPU nondeterminism;
- clear Julia verifier reference.

## Deliverables

- Working Rust port reproducing reference observables.
- Benchmark table against the original Julia workflow.
- Gap list covering missing operations, performance gaps, and API friction.
- Porting report for maintainers.
