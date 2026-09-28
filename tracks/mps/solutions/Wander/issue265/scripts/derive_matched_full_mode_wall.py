#!/usr/bin/env python3
"""Gate finite-window wall construction on microscopic full-mode matching.

This entry point intentionally has no fallback fit.  If the complete
fluctuating-GHD kernel has not passed the positive-spectrum, exact-moment, and
joint-regulator gates, it returns a blocked certificate without `a` or `D`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def derive_matched_wall(
    matching_certificate: dict[str, object],
    *,
    t_start: float,
    t_stop: float,
) -> dict[str, object]:
    if not (0.0 < t_start < t_stop):
        raise ValueError("require 0 < t_start < t_stop")
    inputs = dict(matching_certificate.get("inputs", {}))
    if inputs.get("trajectory_data_used") or inputs.get("target_coefficients_used"):
        raise RuntimeError("matched wall construction refuses target-contaminated input")
    gates = dict(matching_certificate.get("gates", {}))
    terminator = bool(gates.get("continuum_terminator_matching_complete", False))
    physical_f1 = bool(gates.get("physical_F1_perp_certified", False))
    if not (terminator and physical_f1):
        failed = []
        if not terminator:
            failed.append("continuum_terminator_matching_complete")
        if not physical_f1:
            failed.append("physical_F1_perp_certified")
        return {
            "schema": 1,
            "status": "blocked",
            "window": [float(t_start), float(t_stop)],
            "failed_gates": failed,
            "physical_F1_perp_certified": False,
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "projection_performed": False,
            "reason": (
                "The bare complete fluctuating-GHD loop has not been matched "
                "to a positive continuum behind the exact microscopic Mori "
                "prefix.  A wall or Burgers pair would therefore depend on "
                "the hydrodynamic UV regulator."
            ),
        }
    return {
        "schema": 1,
        "status": "eligible_pending_time_domain_certificate",
        "window": [float(t_start), float(t_stop)],
        "physical_F1_perp_certified": True,
        "trajectory_data_used": False,
        "target_coefficients_used": False,
        "projection_performed": False,
        "reason": (
            "Frequency-domain matching passed, but this certificate does not "
            "contain the normalized time-domain structure needed to construct "
            "the wall.  No coefficient is emitted from incomplete input."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matching_certificate", type=Path)
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    certificate = json.loads(args.matching_certificate.read_text())
    result = derive_matched_wall(
        certificate,
        t_start=args.t_start,
        t_stop=args.t_stop,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
