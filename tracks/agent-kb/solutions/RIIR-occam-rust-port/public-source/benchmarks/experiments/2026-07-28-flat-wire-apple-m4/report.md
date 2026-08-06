# Flat Packed Wire Arena Retention Experiment

Date: 2026-07-28

Candidate parent: `1ce366f` (`Parse packed datasets with checked limits`)

Environment:

- Apple M4, aarch64
- macOS 15.6
- `rustc 1.95.0 (59807616e 2026-04-14) (Homebrew)`
- release profile

Method:

- Compare the former nested `Vec<Vec<u64>>` wire layout
  (`packed-reference`) with one flat column-major `Vec<u64>` (`packed`).
- Use the same already-packed dataset for each measured backend.
- Run five warmups before each of five batches of 30 measurements.
- Alternate invocation order by case: reference/flat, flat/reference,
  reference/flat, flat/reference.
- Require exact metrics from both implementations.
- Retain the flat default only if at least three cases improve by more than
  the sum of both median absolute deviations, with no meaningful regression
  in the fourth case.

| Case | Samples | Gates | Nested median (ms) | Nested MAD (ms) | Flat median (ms) | Flat MAD (ms) | Improvement |
|---|---:|---:|---:|---:|---:|---:|---:|
| official-add-8 | 2,000 | 37 | 0.010562 | 0.000021 | 0.008458 | 0.000041 | 24.88% |
| add-8-100000 | 100,000 | 37 | 0.467437 | 0.054624 | 0.382583 | 0.000416 | 22.18% |
| add-16-100000 | 100,000 | 77 | 1.109479 | 0.003020 | 0.783833 | 0.003687 | 41.55% |
| mul-4-100000 | 100,000 | 128 | 1.661520 | 0.247395 | 1.370854 | 0.034041 | 21.20% |

All eight reports contain 150 raw timings and exact verification metrics.
The difference exceeds the combined MAD in all four cases, so the flat arena
passes the predeclared retention gate and remains the default. The nested
implementation is retained only as a benchmark/differential reference.

The JSON files beside this report are the primary evidence.
