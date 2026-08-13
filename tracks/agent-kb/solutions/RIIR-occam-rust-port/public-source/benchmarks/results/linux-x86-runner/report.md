# Linux x86-64 GitHub Actions Benchmark

- Provenance: [GitHub Actions run 30289355965](https://github.com/JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port/actions/runs/30289355965)
- Trigger: manual `workflow_dispatch` from commit `5ad82ee`
- Evidence: each scalar/packed row includes five batches of 30 raw measurements;
  all reported verification metrics are exact and agree between backends
- Platform: Linux-6.17.0-1020-azure-x86_64-with-glibc2.39
- Processor: AMD EPYC 7763 64-Core Processor
- Logical cores: 2
- Memory: 8.3 GB
- Rust: `rustc 1.97.1 (8bab26f4f 2026-07-14)`
- Julia: `julia version 1.12.6`

| Case | Samples | Gates | Scalar median ms | Packed median ms | Speedup |
|---|---:|---:|---:|---:|---:|
| official-add-8 | 2,000 | 37 | 0.333212 | 0.012614 | 26.42× |
| add-8-100000 | 100,000 | 37 | 16.107667 | 0.258788 | 62.24× |
| add-16-100000 | 100,000 | 77 | 29.405169 | 0.537087 | 54.75× |
| mul-4-100000 | 100,000 | 128 | 71.855768 | 0.789974 | 90.96× |
