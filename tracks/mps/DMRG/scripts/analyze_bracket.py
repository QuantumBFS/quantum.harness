from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def load_couplings(directory: Path) -> np.ndarray:
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    return np.asarray(summary["final_renormalized_couplings"], dtype=float)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a two-endpoint RG bracket")
    parser.add_argument("--low-k", type=float, required=True)
    parser.add_argument("--high-k", type=float, required=True)
    parser.add_argument("--low-rg2", type=Path, required=True)
    parser.add_argument("--low-rg3", type=Path, required=True)
    parser.add_argument("--high-rg2", type=Path, required=True)
    parser.add_argument("--high-rg3", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    low2, low3 = load_couplings(args.low_rg2), load_couplings(args.low_rg3)
    high2, high3 = load_couplings(args.high_rg2), load_couplings(args.high_rg3)
    low_delta, high_delta = low3 - low2, high3 - high2
    low_f, high_f = float(low_delta[0]), float(high_delta[0])
    if not low_f < 0.0 < high_f:
        interpolated = None
    else:
        interpolated = args.low_k - low_f * (args.high_k - args.low_k) / (
            high_f - low_f
        )
    report = {
        "low_initial_coupling": args.low_k,
        "high_initial_coupling": args.high_k,
        "low_signed_flow": low_f,
        "high_signed_flow": high_f,
        "low_full_vector_distance": float(np.linalg.norm(low_delta)),
        "high_full_vector_distance": float(np.linalg.norm(high_delta)),
        "sign_bracket_pass": bool(low_f < 0.0 < high_f),
        "single_flow_linear_interpolation": interpolated,
        "warning": "Pilot only; independent complete-flow repeats are required.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
