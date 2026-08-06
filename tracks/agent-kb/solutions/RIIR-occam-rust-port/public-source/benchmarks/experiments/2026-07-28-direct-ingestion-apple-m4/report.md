# Direct Packed Ingestion Benchmark

Date: 2026-07-28

Implementation: raw CSV bytes → flat `PackedDataset` columns

- Platform: macOS-15.6-arm64-arm-64bit-Mach-O
- Processor: Apple M4
- Rust: `rustc 1.95.0 (59807616e 2026-04-14) (Homebrew)`
- Evaluator: compiled packed execution plan
- Timing: five preprocessing measurements, five batches of 30 evaluator measurements, and five fresh-process repetitions
- Correctness: every case has exact bit and sample metrics

| Case | Samples | Legacy parse+pack (ms) | Direct packed parse (ms) | Legacy/direct time ratio | Evaluate median (ms) | One-shot (ms) |
|---|---:|---:|---:|---:|---:|---:|
| add-8 | 100,000 | 11.623 | 12.917 | 0.90× | 0.123 | 13.129 |
| add-8 | 1,000,000 | 120.593 | 121.060 | 1.00× | 1.607 | 122.813 |
| mul-4 | 100,000 | 11.293 | 9.573 | 1.18× | 0.486 | 10.167 |
| mul-4 | 1,000,000 | 94.862 | 89.159 | 1.06× | 4.028 | 93.289 |

| Case | Samples | Direct RSS (MiB) | Legacy RSS (MiB) | RSS reduction | Direct process wall (s) | Legacy process wall (s) |
|---|---:|---:|---:|---:|---:|---:|
| add-8 | 100,000 | 5.56 | 13.30 | 2.39× | 0.020 | 0.030 |
| add-8 | 1,000,000 | 37.22 | 138.11 | 3.71× | 0.140 | 0.220 |
| mul-4 | 100,000 | 5.47 | 13.11 | 2.40× | 0.010 | 0.020 |
| mul-4 | 1,000,000 | 37.47 | 134.03 | 3.58× | 0.100 | 0.220 |

## Decision

Direct packed parsing is the production path because it avoids materializing one `Vec<bool>` pair per sample while preserving the exact flat layout produced by the legacy path.

Direct parsing time is mixed across the four medians (legacy/direct is 0.90–1.18×), so retention is not based on a uniform CPU-time improvement. It reduces fresh-process peak RSS by 2.39–3.71× and has equal or lower end-to-end process time in every case. The retention decision is therefore grounded in bounded memory behavior.

After the evaluator optimizations, direct CSV ingestion is now slower than one evaluator pass in all four cases; the bottleneck has therefore moved from Boolean circuit execution to text ingestion.

Each JSON file beside this report retains all 150 evaluator timings plus scalar parse, legacy pack, direct parse, compilation, and one-shot timings. `process.json` retains every fresh-process wall-time and RSS observation.
