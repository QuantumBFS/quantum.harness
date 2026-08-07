#!/usr/bin/env python3
"""Merge independently opened v7 pilot sizes into one audited artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from run_susy_hodge_geometric_eth_v7 import _atomic_json, _atomic_npz, sha256


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
DEFAULT_JSONS = (
    OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_banked.json",
    OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_N10_banked.json",
    OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_N12_banked.json",
)
DEFAULT_NPZS = (
    OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_banked.npz",
    OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_N10_banked.npz",
    OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_N12_banked.npz",
)
OUTPUT_JSON = OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_combined.json"
OUTPUT_NPZ = OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_combined.npz"


def _load_passed(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("version") != "v7"
        or not payload.get("passed")
        or not all(payload.get("checks", {}).values())
    ):
        raise ValueError(f"pilot source failed its audit: {path}")
    return payload


def merge_pilot_artifacts(
    json_paths: Sequence[Path],
    npz_paths: Sequence[Path],
    *,
    output_json: Path = OUTPUT_JSON,
    output_npz: Path = OUTPUT_NPZ,
    expected_sizes: Sequence[int] = (8, 10, 12),
) -> dict[str, Any]:
    """Merge compact per-size artifacts without reopening raw outcome sidecars."""

    json_sources = tuple(Path(path) for path in json_paths)
    npz_sources = tuple(Path(path) for path in npz_paths)
    sizes = tuple(int(size) for size in expected_sizes)
    if not json_sources or len(json_sources) != len(npz_sources):
        raise ValueError("pilot merge requires paired JSON and NPZ sources")
    if len(sizes) != len(set(sizes)):
        raise ValueError("expected pilot sizes must be unique")

    payloads = [_load_passed(path) for path in json_sources]
    uncertainty_units = {item.get("uncertainty_unit") for item in payloads}
    null_counts = {int(item.get("null_replicates", -1)) for item in payloads}
    bootstrap_counts = {
        int(item.get("physical_bootstrap_replicates", -1)) for item in payloads
    }
    coverages = {float(item.get("prediction_coverage", -1.0)) for item in payloads}
    if (
        len(uncertainty_units) != 1
        or len(null_counts) != 1
        or len(bootstrap_counts) != 1
        or len(coverages) != 1
    ):
        raise ValueError("pilot source protocols disagree")

    groups: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    source_records: list[dict[str, Any]] = []
    for json_path, npz_path, payload in zip(
        json_sources, npz_sources, payloads, strict=True
    ):
        if payload.get("arrays_sha256") != sha256(npz_path):
            raise ValueError(f"pilot NPZ hash mismatch: {npz_path}")
        with np.load(npz_path, allow_pickle=False) as source_arrays:
            for key in source_arrays.files:
                if key in arrays:
                    raise ValueError(f"duplicate pilot array key: {key}")
                arrays[key] = np.asarray(source_arrays[key]).copy()
        groups.extend(list(payload.get("groups", [])))
        source_records.append(
            {
                "json_file": json_path.name,
                "json_sha256": sha256(json_path),
                "npz_file": npz_path.name,
                "npz_sha256": sha256(npz_path),
                "safe_covariates_sha256": payload.get("safe_covariates_sha256"),
            }
        )

    identities = [
        (int(item["N"]), str(item["sector"]), str(item["panel_kind"]))
        for item in groups
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("pilot merge contains duplicate size/sector/panel groups")
    expected_grid = {
        (size, sector, panel)
        for size in sizes
        for sector in ("central", "adjacent")
        for panel in ("sparse", "isotropic")
    }
    observed_grid = set(identities)
    expected_array_keys = {
        f"N{size}_{sector}_{panel}_{suffix}"
        for size, sector, panel in expected_grid
        for suffix in (
            "physical",
            "physical_bootstrap",
            "collapsed_null",
            "hodge_null",
        )
    }
    if observed_grid != expected_grid:
        raise ValueError("pilot merge does not match the registered size grid")
    if set(arrays) != expected_array_keys:
        raise ValueError("pilot merge arrays do not match the registered groups")

    _atomic_npz(output_npz, **arrays)
    checks = {
        "all_sources_passed": all(
            payload.get("passed") and all(payload.get("checks", {}).values())
            for payload in payloads
        ),
        "complete_registered_grid": observed_grid == expected_grid,
        "unique_group_identities": len(identities) == len(set(identities)),
        "complete_array_grid": set(arrays) == expected_array_keys,
        "finite_arrays": all(np.all(np.isfinite(value)) for value in arrays.values()),
        "common_complete_realization_protocol": uncertainty_units
        == {"complete_disorder_realization"},
        "positive_registered_counts": next(iter(null_counts)) > 0
        and next(iter(bootstrap_counts)) > 0,
    }
    result = {
        "version": "v7",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "uncertainty_unit": next(iter(uncertainty_units)),
        "null_replicates": next(iter(null_counts)),
        "physical_bootstrap_replicates": next(iter(bootstrap_counts)),
        "prediction_coverage": next(iter(coverages)),
        "registered_sizes": list(sizes),
        "groups": sorted(
            groups,
            key=lambda item: (
                int(item["N"]),
                str(item["sector"]),
                str(item["panel_kind"]),
            ),
        ),
        "source_pilot_artifacts": source_records,
        "arrays_sha256": sha256(output_npz),
        "sources": {Path(__file__).name: sha256(Path(__file__))},
        "checks": checks,
        "passed": all(checks.values()),
    }
    if not result["passed"]:
        raise RuntimeError(f"pilot merge failed: {checks}")
    _atomic_json(output_json, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsons", type=Path, nargs="+", default=list(DEFAULT_JSONS))
    parser.add_argument("--npzs", type=Path, nargs="+", default=list(DEFAULT_NPZS))
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-npz", type=Path, default=OUTPUT_NPZ)
    parser.add_argument("--sizes", type=int, nargs="+", default=[8, 10, 12])
    return parser


def main() -> None:
    args = _parser().parse_args()
    payload = merge_pilot_artifacts(
        args.jsons,
        args.npzs,
        output_json=args.output_json,
        output_npz=args.output_npz,
        expected_sizes=args.sizes,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
