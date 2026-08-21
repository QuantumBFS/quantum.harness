#!/usr/bin/env python3
"""Build the machine-readable public release contract for task 05."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = SCRIPT_ROOT.parents[2]
DEFAULT_OUTPUT = SCRIPT_ROOT / "output"
DEFAULT_MANIFEST = DEFAULT_OUTPUT / "release_manifest_v1.json"

FIGURES = tuple(
    f"figure_{index}_{name}"
    for index, name in (
        (1, "spectral_silence_v2.png"),
        (2, "falsification_triangle_v2.png"),
        (3, "independent_channels_v2.png"),
        (4, "geometric_hierarchy_v2.png"),
        (5, "jacobi_atoms_v2.png"),
        (6, "wick_factorization_v3.png"),
        (7, "topological_holonomy_v3.png"),
    )
)

COMPACT_ARTIFACTS = (
    "citation_audit_v1.json",
    "geometric_eth_topology_assets_v3.json",
    "geometric_eth_topology_delivery_audit_v3.json",
    "matrix_element_delivery_audit_v3.json",
    "matrix_element_geometric_eth_v3.json",
    "matrix_element_geometric_eth_v3.npz",
    "matrix_element_topology_theory_v3.json",
    "spectral_silence_delivery_audit_v2.json",
    "spectral_silence_statistics_v2.json",
    "spectral_silence_statistics_v2.npz",
    "spectral_silence_v2.json",
    "topological_holonomy_delivery_audit_v3.json",
    "topological_holonomy_v3.json",
    "topological_holonomy_v3.npz",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _producer_for(relative: str) -> str:
    if relative.startswith(("physical_ensemble", "covariance_model")):
        return "bash run_large_scale_article_v1.sh"
    if relative.startswith(("rank_scaling", "statistical_analysis")):
        return "bash run_large_scale_article_v1.sh"
    if relative.startswith("spectral_silence"):
        return "bash run_spectral_silence_article_v2.sh"
    if "matrix_element" in relative:
        return "FULL_RECOMPUTE=1 bash run_geometric_eth_topology_article_v3.sh"
    if "topology" in relative or "topological_holonomy" in relative:
        return "FULL_RECOMPUTE=1 bash run_geometric_eth_topology_article_v3.sh"
    return "Run the registered task-05 production pipeline"


def _tracked_relative_paths(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return {
        item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    }


def build_manifest(
    *,
    repo_root: Path,
    bulk_output: Path,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Build a release manifest from current compact and optional bulk data."""
    repo_root = repo_root.resolve()
    compact_output = (
        repo_root / "01_task_folder" / "task_05" / "script" / "output"
    )
    matrix = json.loads(
        (compact_output / "matrix_element_geometric_eth_v3.json").read_text(
            encoding="utf-8"
        )
    )
    topology = json.loads(
        (compact_output / "topological_holonomy_v3.json").read_text(
            encoding="utf-8"
        )
    )
    audit = json.loads(
        (
            compact_output / "geometric_eth_topology_delivery_audit_v3.json"
        ).read_text(encoding="utf-8")
    )
    paper = compact_output / "spectral_silence_and_geometric_chaos_v3.pdf"

    figures = []
    for name in FIGURES:
        record = _record(compact_output / name, repo_root)
        record["role"] = (
            "principal_result"
            if name.startswith("figure_1_")
            else "main_figure"
        )
        figures.append(record)

    compact = [
        {**_record(compact_output / name, repo_root), "storage_class": "git"}
        for name in COMPACT_ARTIFACTS
    ]

    external = []
    tracked = _tracked_relative_paths(repo_root)
    bulk_output = bulk_output.resolve()
    if bulk_output.is_dir():
        for source in sorted(bulk_output.rglob("*.npz")):
            relative = source.relative_to(bulk_output)
            compact_path = compact_output / relative
            compact_relative = compact_path.relative_to(repo_root).as_posix()
            if (
                compact_relative in tracked
                and compact_path.is_file()
                and _sha256(compact_path) == _sha256(source)
            ):
                continue
            external.append(
                {
                    "path": (
                        "01_task_folder/task_05/script/output/"
                        + relative.as_posix()
                    ),
                    "size_bytes": source.stat().st_size,
                    "sha256": _sha256(source),
                    "storage_class": "recompute_or_release_asset",
                    "producer": _producer_for(relative.as_posix()),
                }
            )

    existing_manifest = compact_output / "release_manifest_v1.json"
    existing: dict[str, Any] = {}
    if existing_manifest.is_file():
        existing = json.loads(existing_manifest.read_text(encoding="utf-8"))
    if not external:
        external = existing.get("external_artifacts", [])

    timestamp = (
        generated_utc
        or existing.get("generated_utc")
        or datetime.now(timezone.utc).isoformat()
    )
    return {
        "schema_version": 1,
        "release_id": "task05-geometric-chaos-v1",
        "generated_utc": timestamp,
        "headline": "Exact degeneracy turns quantum geometry into the signal.",
        "result_branches": {
            "matrix_element": matrix["result_branch"],
            "topology": topology["result_branch"],
        },
        "paper": {
            **_record(paper, repo_root),
            "page_count": audit["page_count"],
            "title": (
                "Spectral Silence and Geometric Chaos in an Exactly "
                "Degenerate Topological Manifold"
            ),
        },
        "figures": figures,
        "compact_artifacts": compact,
        "external_artifacts": external,
        "verification": {
            "quick": "bash run_quick_verify_v1.sh",
            "article": "bash run_geometric_eth_topology_article_v3.sh",
            "full": "bash run_full_recompute_v1.sh",
        },
        "scientific_scope": [
            "exact-degeneracy projector geometry",
            "finite-rank local Jacobi universality",
            "structured matrix-element and Wilson correlations",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--bulk-output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--generated-utc")
    args = parser.parse_args()

    manifest = build_manifest(
        repo_root=args.repo_root,
        bulk_output=args.bulk_output,
        generated_utc=args.generated_utc,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
