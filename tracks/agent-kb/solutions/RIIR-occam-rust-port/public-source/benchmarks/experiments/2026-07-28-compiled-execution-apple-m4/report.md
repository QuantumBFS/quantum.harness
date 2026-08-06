# Compiled Packed Execution Retention Experiment

Date: 2026-07-28

Candidate parent: `1ec2bc1` (`Use evidence-backed flat packed wires`)

Environment:

- Apple M4, aarch64
- macOS 15.6
- `rustc 1.95.0 (59807616e 2026-04-14) (Homebrew)`
- release profile

Method:

- Compare the flat interpreted packed evaluator (`packed`) with a compiled
  execution plan (`compiled`).
- The compiled plan maps inputs and wires to unified column identifiers,
  turns inversion branches into XOR masks, and hoists column-offset
  calculations outside block loops.
- Compile once outside the evaluator timing, as a circuit is normally reused
  for all samples and repeated evaluations. Dataset packing is also outside
  evaluator timing for both sides.
- Run five warmups before each of five batches of 30 measurements.
- Alternate invocation order by case: interpreted/compiled,
  compiled/interpreted, interpreted/compiled, compiled/interpreted.
- Require exact metrics from both implementations.
- Retain compiled execution as the packed default only if at least three cases
  improve by more than the sum of both median absolute deviations, with no
  meaningful regression in the fourth case.

| Case | Samples | Gates | Interpreted median (ms) | Interpreted MAD (ms) | Compiled median (ms) | Compiled MAD (ms) | Speedup |
|---|---:|---:|---:|---:|---:|---:|---:|
| official-add-8 | 2,000 | 37 | 0.011479 | 0.000521 | 0.003875 | 0.000125 | 2.96× |
| add-8-100000 | 100,000 | 37 | 0.461854 | 0.027312 | 0.185854 | 0.012271 | 2.49× |
| add-16-100000 | 100,000 | 77 | 0.885499 | 0.031894 | 0.288354 | 0.012437 | 3.07× |
| mul-4-100000 | 100,000 | 128 | 1.762291 | 0.149021 | 0.535333 | 0.107770 | 3.29× |

All eight reports contain 150 raw timings and exact verification metrics.
The difference exceeds the combined MAD in all four cases, so compiled
execution passes the predeclared retention gate and becomes the packed
evaluator default. The interpreted implementation remains available for
differential tests and future A/B measurements.

This is evaluator-only evidence. Compilation cost is deliberately excluded
and is charged separately in the direct-ingestion/end-to-end experiment.
The JSON files beside this report are the primary evidence.
