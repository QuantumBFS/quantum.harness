#!/usr/bin/env python3
"""Build the resumable Target-2 production-cell manifest."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable

GEOMETRIES = ("83", "124", "line83")
POINTS = {
    "P1": (0.03, 0.50),
    "P2": (0.05, 0.50),
    "P3": (0.06, 0.50),
    "P4": (0.03, 0.15),
    "P5": (0.03, 0.75),
}
GAMMAS = (0.0, 0.05, 0.10)
MEMORY_TIERS_CPUS = {64: 40, 192: 104, 225: 128}
DRY_SPEC_FIELDS = (
    "geometry", "graph_path", "nmax", "L", "d", "encoding", "basis_family", "symmetry",
)


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def cell(
    campaign: str,
    kind: str,
    geometry: str,
    nmax: int,
    L: int,
    d: int,
    encoding: str,
    family: str,
    symmetry: str,
    point: str,
    gamma: float | None = None,
    optional: bool = False,
) -> dict[str, object]:
    t, mu = (0.0, 0.50) if point == "A" else POINTS[point]
    gamma_tag = "gap" if gamma is None else f"g{gamma:.2f}"
    identifier = "-".join(
        map(
            str,
            (campaign, kind, geometry, f"n{nmax}", f"L{L}", f"d{d}", encoding, family, symmetry, point, gamma_tag),
        )
    )
    requested_memory = 225 if nmax == 3 else 192 if nmax == 2 else 64
    # Empirical completed hard-core dry assemblies use up to 25.3 GiB before
    # a JuMP/Mosek workspace exists; the largest {12,4} (2,2) assembly had
    # already reached 51.6 GiB when its 64-GB trial was stopped.  Keep the
    # baseline at 64 GB, but give every tighter production solve the next
    # tier's headroom.
    if (nmax, encoding, symmetry) == (1, "matrix", "U1_INVARIANT_KMS_STATES") and (L, d) != (1, 2):
        requested_memory = 192
    requested_cpus = MEMORY_TIERS_CPUS[requested_memory]
    if requested_memory * 1024 > requested_cpus * 1916:
        raise RuntimeError("SCNet memory request exceeds the partition's per-CPU allowance")
    return {
        "id": identifier,
        "campaign": campaign,
        "kind": kind,
        "geometry": geometry,
        "graph_path": f"results/graphs/{geometry}-L{L}.json",
        "nmax": nmax,
        "L": L,
        "d": d,
        "encoding": encoding,
        "basis_family": family,
        "symmetry": symmetry,
        "point": point,
        "t": t,
        "U": 1.0,
        "mu": mu,
        "gamma": gamma,
        "requested_cpus": requested_cpus,
        "requested_memory_gb": requested_memory,
        "requested_walltime": "24:00:00",
        "optional_resource_gate": optional,
        "status": "PENDING",
    }


def primary_cells() -> Iterable[dict[str, object]]:
    levels = {
        1: ((1, 2, "complete"), (2, 2, "complete"), (1, 3, "complete")),
        2: ((1, 2, "complete"), (2, 2, "ts2"), (1, 3, "ts2")),
    }
    for nmax, selected_levels in levels.items():
        for L, d, family in selected_levels:
            for geometry in GEOMETRIES:
                for point in POINTS:
                    yield cell("primary", "gap", geometry, nmax, L, d, "matrix", family,
                               "U1_INVARIANT_KMS_STATES", point)
                    for gamma in GAMMAS:
                        yield cell("primary", "observable", geometry, nmax, L, d, "matrix", family,
                                   "U1_INVARIANT_KMS_STATES", point, gamma)


def comparison_cells() -> Iterable[dict[str, object]]:
    ladder_degrees = {1: (2, 3), 2: (3, 4)}
    for nmax, degrees in ladder_degrees.items():
        for d in degrees:
            for geometry in GEOMETRIES:
                for point in ("P2", "P4"):
                    yield cell("ladder", "gap", geometry, nmax, 1, d, "ladder", "complete",
                               "U1_INVARIANT_KMS_STATES", point)
                    for gamma in GAMMAS:
                        yield cell("ladder", "observable", geometry, nmax, 1, d, "ladder", "complete",
                                   "U1_INVARIANT_KMS_STATES", point, gamma)
    for nmax, degrees in {1: (2, 3), 2: (3, 4), 3: (3, 4)}.items():
        for d in degrees:
            yield cell("ladder-atomic", "gap", "83", nmax, 1, d, "ladder", "complete",
                       "U1_INVARIANT_KMS_STATES", "A")
            for gamma in GAMMAS:
                yield cell("ladder-atomic", "observable", "83", nmax, 1, d, "ladder", "complete",
                           "U1_INVARIANT_KMS_STATES", "A", gamma)
    for geometry in GEOMETRIES:
        for point in ("P2", "P3"):
            yield cell("unrestricted", "gap", geometry, 1, 1, 2, "matrix", "complete",
                       "UNRESTRICTED_KMS_STATES", point)
            for gamma in GAMMAS:
                yield cell("unrestricted", "observable", geometry, 1, 1, 2, "matrix", "complete",
                           "UNRESTRICTED_KMS_STATES", point, gamma)


def optional_cells() -> Iterable[dict[str, object]]:
    for geometry in GEOMETRIES:
        for point in POINTS:
            yield cell("optional-nmax3", "gap", geometry, 3, 1, 2, "matrix", "complete",
                       "U1_INVARIANT_KMS_STATES", point, optional=True)
            for gamma in GAMMAS:
                yield cell("optional-nmax3", "observable", geometry, 3, 1, 2, "matrix", "complete",
                           "U1_INVARIANT_KMS_STATES", point, gamma, optional=True)


def dry_levels(cells: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    unique: dict[tuple[object, ...], dict[str, object]] = {}
    for campaign_cell in cells:
        key = tuple(campaign_cell[field] for field in DRY_SPEC_FIELDS)
        if key not in unique:
            unique[key] = {field: campaign_cell[field] for field in DRY_SPEC_FIELDS}
            unique[key]["production_requested_cpus"] = campaign_cell["requested_cpus"]
            unique[key]["production_requested_memory_gb"] = campaign_cell["requested_memory_gb"]
        elif (
            unique[key]["production_requested_cpus"] != campaign_cell["requested_cpus"]
            or unique[key]["production_requested_memory_gb"] != campaign_cell["requested_memory_gb"]
        ):
            raise RuntimeError(f"inconsistent production resources for dry level {key}")
    levels = sorted(
        unique.values(),
        key=lambda item: (
            item["nmax"], item["encoding"],
            item["symmetry"], item["basis_family"], item["L"], item["d"],
            item["geometry"],
        ),
    )
    for item in levels:
        empirical_124_l2 = (
            item["geometry"] == "124"
            and item["nmax"] == 1
            and item["L"] == 2
            and item["d"] == 2
            and item["encoding"] == "matrix"
            and item["basis_family"] == "complete"
            and item["symmetry"] == "U1_INVARIANT_KMS_STATES"
        )
        dry_memory = (
            225 if item["nmax"] == 3
            else 192 if item["nmax"] == 2 or empirical_124_l2
            else 64
        )
        item["requested_memory_gb"] = dry_memory
        item["requested_cpus"] = MEMORY_TIERS_CPUS[dry_memory]
        item["id"] = "-".join(
            map(
                str,
                (
                    "dry", item["geometry"], f"n{item['nmax']}", f"L{item['L']}",
                    f"d{item['d']}", item["encoding"], item["basis_family"],
                    item["symmetry"],
                ),
            )
        )
        item["requested_walltime"] = "06:00:00"
        item["status"] = "PENDING"
    return levels


def dry_tiers(levels: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    def array_spec(indices: list[int]) -> str:
        ranges: list[str] = []
        start = previous = indices[0]
        for index in indices[1:]:
            if index == previous + 1:
                previous = index
                continue
            ranges.append(str(start) if start == previous else f"{start}-{previous}")
            start = previous = index
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        return ",".join(ranges)

    result: dict[str, dict[str, object]] = {}
    for memory_gb in MEMORY_TIERS_CPUS:
        indices = [index for index, level in enumerate(levels)
                   if level["requested_memory_gb"] == memory_gb]
        if not indices:
            continue
        concurrency = min(8, 450 // memory_gb)
        result[str(memory_gb)] = {
            "first_index": indices[0],
            "last_index": indices[-1],
            "indices": indices,
            "slurm_array_spec": array_spec(indices),
            "count": len(indices),
            "requested_cpus": MEMORY_TIERS_CPUS[memory_gb],
            "max_concurrency": concurrency,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/campaign_manifest.json"))
    parser.add_argument("--dry-output", type=Path, default=Path("results/dry_level_manifest.json"))
    args = parser.parse_args()
    cells = [*primary_cells(), *comparison_cells(), *optional_cells()]
    primary = [item for item in cells if item["campaign"] == "primary"]
    primary_gap = sum(item["kind"] == "gap" for item in primary)
    primary_observable_cells = sum(item["kind"] == "observable" for item in primary)
    summary = {
        "schema_version": 1,
        "generated_by": "scripts/build_campaign.py",
        "primary_gap_endpoints": primary_gap,
        "primary_observable_cells": primary_observable_cells,
        "primary_observable_optima": primary_observable_cells * 6,
        "total_cells_including_comparisons_and_optional": len(cells),
        "concurrency_rule": "min(8, floor(450 GB / requested_cell_memory_gb))",
        "scheduler_memory_rule": "wzacnormal03 requires memory <= 1916M * requested_cpus",
        "resource_tier_cell_counts": {
            str(memory): sum(cell["requested_memory_gb"] == memory for cell in cells)
            for memory in MEMORY_TIERS_CPUS
        },
        "cells": cells,
    }
    if (primary_gap, primary_observable_cells * 6) != (90, 1620):
        raise RuntimeError("mandatory campaign count regression")
    levels = dry_levels(cells)
    if len(levels) != 38:
        raise RuntimeError(f"dry-level count regression: expected 38, got {len(levels)}")
    dry_summary = {
        "schema_version": 1,
        "generated_by": "scripts/build_campaign.py",
        "level_count": len(levels),
        "concurrency_rule": "min(8, floor(450 GB / requested_cell_memory_gb))",
        "tiers": dry_tiers(levels),
        "levels": levels,
    }
    atomic_json(args.output, summary)
    atomic_json(args.dry_output, dry_summary)
    print(
        f"wrote {args.output}: {primary_gap} primary gaps and "
        f"{primary_observable_cells * 6} primary observable optima; "
        f"{args.dry_output}: {len(levels)} unique levels",
        flush=True,
    )


if __name__ == "__main__":
    main()
