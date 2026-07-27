from __future__ import annotations

import argparse
from pathlib import Path

from benchmark_v0.ed_oracle import run_ed_oracle, write_json_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Challenge #15 Benchmark v0 ED")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-theta", type=int, default=None)
    parser.add_argument("--n-phi", type=int, default=None)
    args = parser.parse_args()

    result = run_ed_oracle(
        n_theta=args.n_theta,
        n_phi=args.n_phi,
        progress=lambda message: print(message, flush=True),
    )
    write_json_report(result, args.output)
    raw = result["energies"]["raw_lll"]
    print(
        f"E0={raw['ground_energy']:.12f} "
        f"Delta2={raw['gap']:.12f} "
        f"oracle_pass={result['gates']['ed_oracle_valid']}",
        flush=True,
    )
    print(f"wrote {args.output}", flush=True)
    return 0 if result["gates"]["ed_oracle_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
