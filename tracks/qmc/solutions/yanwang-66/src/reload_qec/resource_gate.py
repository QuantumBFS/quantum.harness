"""Conservative discovery resource projection from validated SCNet timings."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


RESOURCE_SCHEMA = "q66-discovery-resource-gate-v1"
RUNTIME_SAFETY_FACTOR = 1.2
STORAGE_SAFETY_FACTOR = 1.5
DISCOVERY_GROUPS_PER_GEOMETRY = 70
VALIDATED_POLICIES_PER_GROUP = 4
POLICIES_PER_GROUP = 8
SHOTS_PER_CELL = 20_000
INITIAL_TOTAL_SHOTS = 2_240 * SHOTS_PER_CELL
MAX_GROUP_SECONDS = 45 * 60
MAX_INITIAL_BYTES = 20 * 1024**3
MAX_RSS_KIB = 16 * 1024**2
BUNDLE_GROUPS_BY_GEOMETRY = {(3, 3): 4, (3, 6): 3, (5, 5): 1, (5, 10): 1}


class ResourceGateError(ValueError):
    """Raised when validator evidence cannot support a resource projection."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )


def evaluate_resources(
    *,
    matrix_path: Path,
    results_root: Path,
    score_path: Path,
    out_path: Path,
    source_commit: str,
    environment_lock_sha256: str,
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise ResourceGateError("resource gate must run inside Slurm")
    matrix = json.loads(matrix_path.read_text(encoding="ascii"))
    score = json.loads(score_path.read_text(encoding="ascii"))
    matrix_sha256 = _sha256(matrix_path)
    if matrix.get("schema_version") != "q66-dev-validator-matrix-v1":
        raise ResourceGateError("development matrix schema mismatch")
    if score.get("schema_version") != "q66-dev-validator-score-v1":
        raise ResourceGateError("development score schema mismatch")
    if matrix.get("source_commit") != source_commit:
        raise ResourceGateError("source commit differs from validated matrix")
    if matrix.get("environment_lock_sha256") != environment_lock_sha256:
        raise ResourceGateError("environment lock differs from validated matrix")
    if score.get("status") != "passed":
        raise ResourceGateError("reference development score did not pass")
    if score.get("matrix_sha256") != matrix_sha256:
        raise ResourceGateError("score and development matrix hashes differ")
    if Path(score.get("results_root", "")) != results_root:
        raise ResourceGateError("score names a different validator result root")
    cells = matrix.get("cells")
    score_cells = score.get("cells")
    if not isinstance(cells, list) or not isinstance(score_cells, list):
        raise ResourceGateError("matrix/score cells are missing")
    if len(cells) != 16 or len(score_cells) != 16:
        raise ResourceGateError("resource gate requires all 16 validator cells")

    geometry_rates: dict[tuple[int, int], list[float]] = {}
    max_bytes_per_shot = 0.0
    max_rss_kib = 0
    for cell_index, (cell, score_cell) in enumerate(zip(cells, score_cells)):
        if cell.get("cell_index") != cell_index or score_cell.get(
            "cell_index"
        ) != cell_index:
            raise ResourceGateError("matrix/score cell ordering differs")
        request = cell["request"]
        if score_cell.get("shots") != request["shots"]:
            raise ResourceGateError(f"shot count mismatch in cell {cell_index}")
        seconds = float(score_cell["median_candidate_seconds"])
        if not math.isfinite(seconds) or seconds <= 0.0:
            raise ResourceGateError(f"invalid candidate timing in cell {cell_index}")
        key = (int(request["distance"]), int(request["rounds"]))
        geometry_rates.setdefault(key, []).append(seconds / int(request["shots"]))
        max_rss_kib = max(max_rss_kib, int(score_cell["peak_children_rss_kib"]))

        report_path = results_root / f"cell-{cell_index:02d}/runner-report.json"
        report = json.loads(report_path.read_text(encoding="ascii"))
        for repetition in range(1, 4):
            run = report["runs"][repetition]
            if run.get("validation") != "exact-replay-passed":
                raise ResourceGateError(
                    f"cell {cell_index} repeat {repetition} lacks exact replay"
                )
            manifest_path = (
                results_root
                / f"cell-{cell_index:02d}"
                / f"repeat-{repetition}"
                / "manifest.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="ascii"))
            bytes_per_shot = float(manifest["aggregate"]["bytes_per_shot"])
            if not math.isfinite(bytes_per_shot) or bytes_per_shot <= 0.0:
                raise ResourceGateError(
                    f"invalid storage rate in cell {cell_index}, repeat {repetition}"
                )
            max_bytes_per_shot = max(max_bytes_per_shot, bytes_per_shot)

    expected_geometries = {(3, 3), (3, 6), (5, 5), (5, 10)}
    if set(geometry_rates) != expected_geometries:
        raise ResourceGateError("validator timings do not cover all geometries")
    if any(
        len(rates) != VALIDATED_POLICIES_PER_GROUP
        for rates in geometry_rates.values()
    ):
        raise ResourceGateError("validator does not cover four policies per geometry")
    projections = []
    for distance, rounds in sorted(geometry_rates):
        validated_rates = geometry_rates[(distance, rounds)]
        mean_seconds_per_shot = sum(validated_rates) / len(validated_rates)
        projected_group_seconds = (
            mean_seconds_per_shot
            * SHOTS_PER_CELL
            * POLICIES_PER_GROUP
            * RUNTIME_SAFETY_FACTOR
        )
        groups_per_array_task = BUNDLE_GROUPS_BY_GEOMETRY[(distance, rounds)]
        projections.append(
            {
                "distance": distance,
                "rounds": rounds,
                "validated_policies": len(validated_rates),
                "mean_validated_seconds_per_shot": mean_seconds_per_shot,
                "worst_validated_seconds_per_shot": max(validated_rates),
                "projected_group_seconds": projected_group_seconds,
                "groups_per_array_task": groups_per_array_task,
                "projected_array_task_seconds": (
                    projected_group_seconds * groups_per_array_task
                ),
                "groups": DISCOVERY_GROUPS_PER_GEOMETRY,
                "projected_gpu_hours": (
                    projected_group_seconds * DISCOVERY_GROUPS_PER_GEOMETRY / 3600.0
                ),
            }
        )
    projected_initial_bytes = (
        max_bytes_per_shot * INITIAL_TOTAL_SHOTS * STORAGE_SAFETY_FACTOR
    )
    worst_array_task_seconds = max(
        row["projected_array_task_seconds"] for row in projections
    )
    passed = (
        worst_array_task_seconds <= MAX_GROUP_SECONDS
        and projected_initial_bytes <= MAX_INITIAL_BYTES
        and max_rss_kib <= MAX_RSS_KIB
    )
    report = {
        "schema_version": RESOURCE_SCHEMA,
        "status": "passed" if passed else "requires-resource-remediation",
        "slurm_job_id": slurm_job_id,
        "matrix": str(matrix_path),
        "matrix_sha256": matrix_sha256,
        "score": str(score_path),
        "score_sha256": _sha256(score_path),
        "results_root": str(results_root),
        "source_commit": source_commit,
        "environment_lock_sha256": environment_lock_sha256,
        "assumptions": {
            "runtime_safety_factor": RUNTIME_SAFETY_FACTOR,
            "storage_safety_factor": STORAGE_SAFETY_FACTOR,
            "groups_per_geometry": DISCOVERY_GROUPS_PER_GEOMETRY,
            "validated_policies_per_group": VALIDATED_POLICIES_PER_GROUP,
            "policies_per_group": POLICIES_PER_GROUP,
            "bundle_groups_by_geometry": {
                f"d{distance}-t{rounds}": groups
                for (distance, rounds), groups in sorted(
                    BUNDLE_GROUPS_BY_GEOMETRY.items()
                )
            },
            "shots_per_cell": SHOTS_PER_CELL,
            "initial_total_shots": INITIAL_TOTAL_SHOTS,
        },
        "limits": {
            "max_group_seconds": MAX_GROUP_SECONDS,
            "max_initial_bytes": MAX_INITIAL_BYTES,
            "max_rss_kib": MAX_RSS_KIB,
        },
        "geometry_projections": projections,
        "projected_total_gpu_hours": sum(
            row["projected_gpu_hours"] for row in projections
        ),
        "max_validated_bytes_per_shot": max_bytes_per_shot,
        "projected_initial_bytes": projected_initial_bytes,
        "worst_projected_array_task_seconds": worst_array_task_seconds,
        "max_validated_rss_kib": max_rss_kib,
        "discovery_authorized": passed,
    }
    if out_path.exists():
        raise ResourceGateError(f"resource report already exists: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _canonical_json(out_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--score", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--environment-lock-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate_resources(
        matrix_path=args.matrix,
        results_root=args.results_root,
        score_path=args.score,
        out_path=args.out,
        source_commit=args.source_commit,
        environment_lock_sha256=args.environment_lock_sha256,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
