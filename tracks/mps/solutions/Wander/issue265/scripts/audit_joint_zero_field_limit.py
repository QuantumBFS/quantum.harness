#!/usr/bin/env python3
"""Build a fail-closed joint ``h/string/rapidity/series`` limit certificate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import EXACT_D0_INFINITY_T  # noqa: E402
from src.joint_zero_field_audit import audit_joint_zero_field_limit  # noqa: E402


def _diagonal_payload(payload: dict[str, object]) -> dict[str, object]:
    """Merge every eligible Eq. (16) diagonal run without altering source data."""

    common = dict(payload.get("common_parameters", {}))
    default_cutoff = float(common.get("string_xi_cutoff", 8.0))
    rows: dict[tuple[float, float, int], dict[str, object]] = {}
    for source in payload.get("full_cross_runs", []):
        row = dict(source)
        if row.get("h_times_diagonal_diffusion") is None:
            continue
        key = (
            float(row["field"]),
            float(row["string_xi_cutoff"]),
            int(row["velocity_series_terms"]),
        )
        rows[key] = row
    for source in payload.get("runs", []):
        row = dict(source)
        field = float(row["field"])
        if field > 0.2 or row.get("diagonal_diffusion") is None:
            continue
        row["string_xi_cutoff"] = default_cutoff
        row["h_times_diagonal_diffusion"] = field * float(
            row["diagonal_diffusion"]
        )
        key = (field, default_cutoff, int(row["velocity_series_terms"]))
        rows[key] = {**rows.get(key, {}), **row}
    for check in payload.get("continuum_checks", []):
        check = dict(check)
        field = float(check["field"])
        terms = int(check["velocity_series_terms"])
        key = (field, default_cutoff, terms)
        if key in rows:
            rows[key]["rho_total_relative_l2_error"] = float(
                check["rho_total_relative_l2_error"]
            )
    return {"full_cross_runs": list(rows.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=ROOT / "docs/full_tba_finite_field_runs.json"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    diagonal = audit_joint_zero_field_limit(
        _diagonal_payload(payload),
        exact_leading=EXACT_D0_INFINITY_T,
        value_key="h_times_diagonal_diffusion",
        quantity_label="Eq16_diagonal_physical_through_D1",
        physical_d1_candidate=True,
    )
    full_cross = audit_joint_zero_field_limit(
        payload,
        exact_leading=EXACT_D0_INFINITY_T,
        value_key="h_times_full_diffusion",
        quantity_label="finite_cutoff_diagonal_minus_cross_order_of_limits_diagnostic",
        physical_d1_candidate=False,
    )
    result = {
        "schema_version": 2,
        "source_order_statement": (
            "Eq. (16) of the supplement to arXiv:2003.13708: "
            "D_spin=D_diagonal+O(h); finite-cutoff off-diagonal terms must "
            "not be used to extract the constant D1"
        ),
        "physical_diagonal_audit": diagonal,
        "finite_cutoff_full_cross_diagnostic": full_cross,
        "physical_D1_certified": bool(
            diagonal["joint_limit_audit"]["physical_D1_certified"]
        ),
        "withdrawn_previous_full_cross_D1_envelope": True,
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
