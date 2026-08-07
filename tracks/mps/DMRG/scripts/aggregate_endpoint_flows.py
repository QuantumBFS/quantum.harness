from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def couplings(directory: Path) -> np.ndarray:
    data = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    return np.asarray(data["final_renormalized_couplings"], dtype=float)


def endpoint(rg2: list[Path], rg3: list[Path]) -> dict[str, object]:
    if len(rg2) != len(rg3) or len(rg2) < 2:
        raise ValueError("each endpoint needs matching rg2/rg3 lists with at least 2 flows")
    deltas = np.stack([couplings(b) - couplings(a) for a, b in zip(rg2, rg3)])
    signed = deltas[:, 0]
    distances = np.linalg.norm(deltas, axis=1)
    signed_mean = float(signed.mean())
    signed_se = float(signed.std(ddof=1) / np.sqrt(len(signed)))
    interval = [signed_mean - 2.0 * signed_se, signed_mean + 2.0 * signed_se]
    return {
        "flows": len(signed),
        "signed_flow_samples": signed.tolist(),
        "full_vector_distance_samples": distances.tolist(),
        "signed_flow_mean": signed_mean,
        "signed_flow_standard_error": signed_se,
        "two_standard_error_interval": interval,
        "strictly_negative_at_two_se": bool(interval[1] < 0.0),
        "strictly_positive_at_two_se": bool(interval[0] > 0.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate independent endpoint RG flows")
    for side in ("low", "high"):
        parser.add_argument(f"--{side}-rg2", type=Path, action="append", required=True)
        parser.add_argument(f"--{side}-rg3", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    low = endpoint(args.low_rg2, args.low_rg3)
    high = endpoint(args.high_rg2, args.high_rg3)
    report = {
        "low": low,
        "high": high,
        "statistical_sign_bracket_pass": bool(
            low["strictly_negative_at_two_se"]
            and high["strictly_positive_at_two_se"]
        ),
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
