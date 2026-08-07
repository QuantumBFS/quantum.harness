from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from vmcrg_ref.fixed_point import fixed_point_residual_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the complete 13-dimensional VMCRG fixed-point residual"
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--rg-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--absolute-tolerance", type=float, default=1.0e-3)
    parser.add_argument("--relative-l2-tolerance", type=float, default=5.0e-3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite residual report: {output}")
    candidate_data = json.loads(args.candidate.resolve().read_text(encoding="utf-8"))
    rg_summary_path = args.rg_output.resolve() / "summary.json"
    rg_summary = json.loads(rg_summary_path.read_text(encoding="utf-8"))
    candidate = np.asarray(candidate_data["candidate_couplings"], dtype=np.float64)
    input_couplings = np.asarray(rg_summary["input_couplings"], dtype=np.float64)
    if not np.array_equal(candidate, input_couplings):
        raise ValueError("RG verification did not use the exact fixed-point candidate")
    mapped = np.asarray(rg_summary["final_renormalized_couplings"], dtype=np.float64)
    result = fixed_point_residual_report(
        candidate,
        mapped,
        absolute_tolerance=args.absolute_tolerance,
        relative_l2_tolerance=args.relative_l2_tolerance,
    )
    result.update(
        {
            "candidate_file": str(args.candidate.resolve()),
            "rg_summary": str(rg_summary_path),
            "operator_names": rg_summary["operator_names"],
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
