#!/usr/bin/env python3
"""Unseal the Challenge 148 ratio only after all direct and independent gates pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from finalize_direct_route import PROTOCOL_ID, SCHEMA_VERSION, atomic_json


UNSEAL_SCHEMA = "challenge148-unsealed-verdict-v1"
INDEPENDENT_SCHEMA = "challenge148-paratoric-critical-analysis-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"summary is not a JSON object: {path}")
    return payload


def validate_direct(path: Path, target: str) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{target} direct summary uses the wrong schema")
    if payload.get("protocol_id") != PROTOCOL_ID or payload.get("target_lattice") != target:
        raise ValueError(f"{target} direct summary identity mismatch")
    if payload.get("ratio_computed") is not False:
        raise ValueError(f"{target} direct summary computed a ratio prematurely")
    if payload.get("accepted") is not True:
        raise ValueError(f"{target} direct route is not accepted")
    return payload


def validate_independent(path: Path, target: str) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("schema_version") != INDEPENDENT_SCHEMA:
        raise ValueError(f"{target} independent summary uses the wrong schema")
    if payload.get("protocol_id") != PROTOCOL_ID or payload.get("target_lattice") != target:
        raise ValueError(f"{target} independent summary identity mismatch")
    if payload.get("ratio_computed") is not False:
        raise ValueError(f"{target} independent summary computed a ratio prematurely")
    if payload.get("independent_route_accepted") is not True:
        raise ValueError(f"{target} independent route is not accepted")
    return payload


def build_verdict(
    triangular_direct_path: Path, honeycomb_direct_path: Path,
    triangular_independent_path: Path, honeycomb_independent_path: Path,
) -> dict[str, Any]:
    direct = {
        "triangular": validate_direct(triangular_direct_path, "triangular"),
        "honeycomb": validate_direct(honeycomb_direct_path, "honeycomb"),
    }
    independent = {
        "triangular": validate_independent(triangular_independent_path, "triangular"),
        "honeycomb": validate_independent(honeycomb_independent_path, "honeycomb"),
    }
    h_tri = float(direct["triangular"]["hc"])
    h_hon = float(direct["honeycomb"]["hc"])
    e_tri = float(direct["triangular"]["total_error"])
    e_hon = float(direct["honeycomb"]["total_error"])
    if not all(math.isfinite(value) for value in (h_tri, h_hon, e_tri, e_hon)):
        raise ValueError("direct summaries contain non-finite final values")
    if h_tri <= 0.0 or h_hon <= 0.0 or e_tri <= 0.0 or e_hon <= 0.0:
        raise ValueError("direct summaries contain non-positive fields or uncertainties")
    ratio = h_tri / h_hon
    sigma = ratio * math.hypot(e_tri / h_tri, e_hon / h_hon)
    root_five = math.sqrt(5.0)
    z = abs(ratio - root_five) / sigma
    verdict = "decisive rejection" if z >= 10.0 else "survival" if z <= 2.0 else "inconclusive"
    inputs = {
        "triangular_direct": triangular_direct_path,
        "honeycomb_direct": honeycomb_direct_path,
        "triangular_independent": triangular_independent_path,
        "honeycomb_independent": honeycomb_independent_path,
    }
    return {
        "schema_version": UNSEAL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "ratio_computed": True,
        "ratio": ratio,
        "ratio_error": sigma,
        "sqrt5": root_five,
        "difference": ratio - root_five,
        "z_score": z,
        "verdict": verdict,
        "field_source": "accepted direct-SSE summaries",
        "independent_route_role": "acceptance gate; not averaged",
        "inputs": {
            name: {"path": str(path.resolve()), "sha256": sha256_file(path.resolve())}
            for name, path in inputs.items()
        },
        "accepted_run_ids": {
            target: direct[target]["run_id"] for target in ("triangular", "honeycomb")
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--triangular-direct", type=Path, required=True)
    parser.add_argument("--honeycomb-direct", type=Path, required=True)
    parser.add_argument("--triangular-independent", type=Path, required=True)
    parser.add_argument("--honeycomb-independent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verdict = build_verdict(
        args.triangular_direct, args.honeycomb_direct,
        args.triangular_independent, args.honeycomb_independent,
    )
    atomic_json(args.output, verdict)
    print(
        f"R={verdict['ratio']:.10f} +/- {verdict['ratio_error']:.3g} "
        f"z={verdict['z_score']:.3f} verdict={verdict['verdict']}",
        flush=True,
    )
    print(f"unsealed verdict -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
