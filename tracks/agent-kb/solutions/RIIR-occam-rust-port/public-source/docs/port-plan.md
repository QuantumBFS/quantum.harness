# Port Plan

## Stage 1: Oracle Compatibility

- [x] Download and checksum-verify the #71 data package.
- [x] Run the Julia verifier on the official example, `practice-add-n4`, and
  `practice-mul-n4`.
- [x] Store gate count, exact-match accuracy, and bit accuracy.
- [x] Add controlled runtime and process-level peak-memory benchmarks.

## Stage 2: Rust Netlist Verifier

- [x] Parse `INPUTS <n>`.
- [x] Parse assignments of the form `w1 = XOR x1 x9`.
- [x] Support free operand and output inversion with `~`.
- [x] Parse `OUTPUTS <wire>...`.
- [x] Evaluate each sample and compare output bitstrings.

## Stage 3: Bit-Parallel Evaluation

- [x] Store each input wire as packed `u64` blocks over samples.
- [x] Evaluate gates with bitwise operations and mask the final partial block.
- [x] Compare packed Rust results against scalar Rust results and Julia outputs.

## Stage 4: Reference Circuit Generator

- [x] Generate a ripple-carry adder netlist for practice addition.
- [x] Generate a deterministic shift-and-add multiplier for practice
  multiplication.
- [x] Verify both generated netlists with Julia and Rust.

## Stage 5: Report

- [x] Produce Julia scalar vs Rust scalar vs Rust bit-parallel timing tables.
- [x] Start the Rust ecosystem friction and future-work gap report.
