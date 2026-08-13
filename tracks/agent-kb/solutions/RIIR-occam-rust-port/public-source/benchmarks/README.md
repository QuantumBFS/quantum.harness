# Verifier Benchmarks

Run the complete correctness and performance suite:

```bash
./scripts/run-benchmarks.sh
```

Run only the Julia/Rust correctness preflight:

```bash
./scripts/run-benchmarks.sh --verify-only
```

The driver builds the release binary and creates these deterministic cases:

| Label | Operation | Bits | Samples | Seed |
|---|---|---:|---:|---:|
| `official-add-8` | disclosed official adder/mystery-A training data | 8 | 2,000 | official |
| `add-8-100000` | addition | 8 | 100,000 | 115008 |
| `add-16-100000` | addition | 16 | 100,000 | 115016 |
| `mul-4-100000` | multiplication | 4 | 100,000 | 115004 |

Every case must pass Rust scalar/packed cross-check and the official Julia
verifier before it is timed.

Run the manifest-driven Julia oracle suite independently:

```bash
./scripts/verify-oracles.sh
```

Rust JSON files under `results/` contain evaluator-only statistics after
parsing and, for the packed backend, after packing. Generated CSV/netlist files
and raw process logs are ignored. The raw logs include startup-inclusive Julia
and Rust wall time plus macOS peak process RSS from `/usr/bin/time -l`.

Reported timings are machine-specific and must not be compared across hardware
without recording a new environment profile.

Optimization A/B evidence is retained separately under `experiments/`.
In particular, the
[flat wire arena retention report](experiments/2026-07-28-flat-wire-apple-m4/report.md)
records the predeclared decision gate and all raw measurements for the current
packed wire layout. The subsequent
[compiled execution retention report](experiments/2026-07-28-compiled-execution-apple-m4/report.md)
records why the compiled plan became the packed evaluator default.
Run `./scripts/run-ingestion-benchmarks.sh` to regenerate the 100k/1M-row
direct-ingestion, one-shot, and fresh-process RSS comparison.
