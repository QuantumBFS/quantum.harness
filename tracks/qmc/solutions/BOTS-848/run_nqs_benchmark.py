from __future__ import annotations

import argparse
from pathlib import Path

from benchmark_v0.nqs_benchmark import run_nqs_benchmark, write_json_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Challenge #15 Benchmark v0 NQS")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=20_000)
    args = parser.parse_args()

    result = run_nqs_benchmark(
        n_samples=args.samples,
        progress=lambda message: print(message, flush=True),
    )
    write_json_report(result, args.output)
    raw = result["energies"]["candidate"]["raw_lll"]
    statistics = result["statistics"]
    print(
        f"E0={raw['ground_energy']:.12f} "
        f"Delta2={raw['gap']:.12f} "
        f"gap_uncertainty={statistics['gap']['total_uncertainty']:.3e} "
        f"pass={result['gates']['benchmark_v0_pass']}",
        flush=True,
    )
    print(f"wrote {args.output}", flush=True)
    return 0 if result["gates"]["benchmark_v0_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
