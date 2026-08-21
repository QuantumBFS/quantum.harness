#!/usr/bin/env python3
"""Build result-conditioned manuscript assets from audited v7 artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from merge_susy_hodge_pilot_v7 import OUTPUT_JSON as PILOT_JSON
from make_susy_hodge_figure_v7 import (
    FIGURE_PDF,
    MANIFEST_JSON as FIGURE_MANIFEST_JSON,
)
from run_susy_hodge_geometric_eth_v7 import _atomic_json, sha256
from analyze_susy_hodge_geometric_eth_v7 import N14_INFERENCE_JSON


SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output"
MANUSCRIPT_ROOT = REPO_ROOT / "overleaf_sync" / "cohomological_geometric_eth"
RESULTS_TEX = MANUSCRIPT_ROOT / "generated" / "results_v7.tex"
FIGURE_TARGET = MANUSCRIPT_ROOT / "figures" / FIGURE_PDF.name
MANIFEST_JSON = OUTPUT_ROOT / "susy_hodge_manuscript_assets_v7.json"
PUBLISHABLE_BRANCHES = {
    "strong_covariance_universality",
    "hodge_resolved_geometric_eth",
    "cohomological_non_gaussian_class",
    "structured_cohomology",
}


def _load_passed(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("version") != "v7"
        or not payload.get("passed")
        or not all(payload.get("checks", {}).values())
    ):
        raise ValueError(f"manuscript source failed its audit: {path}")
    return payload


def _atomic_text(path: Path, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(target)


def _atomic_copy(source: Path, target: Path) -> None:
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _macro(name: str, value: str) -> str:
    return rf"\newcommand{{\{name}}}{{{value}}}"


def _expected_pilot_grid(groups: list[dict[str, Any]]) -> bool:
    observed = {
        (int(item["N"]), str(item["sector"]), str(item["panel_kind"]))
        for item in groups
    }
    expected = {
        (size, sector, panel)
        for size in (8, 10, 12)
        for sector in ("central", "adjacent")
        for panel in ("sparse", "isotropic")
    }
    return observed == expected


def _expected_primary_pair(records: list[dict[str, Any]]) -> bool:
    return {
        (int(item["N"]), str(item["sector"]), str(item["panel_kind"]))
        for item in records
    } == {(14, "central", "sparse"), (14, "adjacent", "sparse")}


def _branch_abstract(branch: str, rejected_groups: int) -> str:
    opening = (
        "Exactly degenerate quantum manifolds have no internal level statistics, "
        "but their projectors move over coupling space. We formulate this motion as "
        "a response complex and compare one-sided frustration-free constraints with "
        "the orthogonal exact/coexact response of charge-resolved cubic "
        r"$\mathcal N=2$ Sachdev--Ye--Kitaev cohomology. "
        f"In the sequential $N=8,10,12$ pilot, {rejected_groups} of 12 "
        "size/sector/panel groups reject both registered separable covariance nulls. "
    )
    endings = {
        "strong_covariance_universality": (
            "A prediction sealed before the held-out $N=14$ opening covers the "
            "central/adjacent sparse pair under both nulls, supporting a finite-size "
            "covariance-universal response law."
        ),
        "hodge_resolved_geometric_eth": (
            "A prediction sealed before the held-out $N=14$ opening covers the "
            "central/adjacent sparse pair only after resolving the Hodge branches, "
            "establishing predictive mechanism dependence beyond collapsed covariance."
        ),
        "cohomological_non_gaussian_class": (
            "A prediction sealed before the held-out $N=14$ opening is rejected by "
            "both nulls for the central/adjacent sparse pair, establishing structured "
            "four-point memory beyond the frozen separable Hodge-covariance law, "
            "without claiming complete entrywise covariance matching."
        ),
        "structured_cohomology": (
            "The held-out $N=14$ response remains statistically indistinguishable "
            "from the registered decomposable cohomological control, selecting a "
            "structured rather than covariance-universal response class."
        ),
    }
    return opening + endings[branch]


def _interval_macro(interval: list[float]) -> str:
    return rf"$[{float(interval[0]):.6f},\,{float(interval[-1]):.6f}]$"


def build_manuscript_assets(
    *,
    pilot_json: Path = PILOT_JSON,
    inference_json: Path = N14_INFERENCE_JSON,
    figure_manifest_json: Path = FIGURE_MANIFEST_JSON,
    figure_pdf: Path = FIGURE_PDF,
    results_tex: Path = RESULTS_TEX,
    figure_target: Path = FIGURE_TARGET,
    manifest_json: Path = MANIFEST_JSON,
) -> dict[str, Any]:
    """Enable result prose only after all compact sources and hashes pass."""

    pilot = _load_passed(pilot_json)
    inference = _load_passed(inference_json)
    figure_manifest = _load_passed(figure_manifest_json)
    groups = list(pilot.get("groups", []))
    primary = list(inference.get("primary_pair", []))
    branch = str(inference.get("selected_branch"))
    if not _expected_pilot_grid(groups):
        raise ValueError("manuscript pilot grid is incomplete")
    if not _expected_primary_pair(primary):
        raise ValueError("manuscript held-out primary pair is incomplete")
    if branch not in PUBLISHABLE_BRANCHES:
        raise ValueError("held-out branch is not publishable")
    if (
        figure_manifest.get("inputs", {}).get(Path(pilot_json).name)
        != sha256(pilot_json)
        or figure_manifest.get("inputs", {}).get(Path(inference_json).name)
        != sha256(inference_json)
        or figure_manifest.get("outputs", {}).get(Path(figure_pdf).name)
        != sha256(figure_pdf)
        or figure_manifest.get("selected_branch") != branch
    ):
        raise ValueError("figure manifest does not match manuscript sources")

    rejected_groups = sum(
        not bool(item.get("collapsed_covered"))
        and not bool(item.get("hodge_covered"))
        for item in groups
    )
    primary_by_sector = {str(item["sector"]): item for item in primary}
    adjacent = primary_by_sector["adjacent"]
    central = primary_by_sector["central"]
    pilot_sentence = (
        f"Across the complete $N=8,10,12$ pilot, {rejected_groups} of 12 "
        "groups reject both registered separable covariance nulls under "
        "complete-realization resampling."
    )
    result_sentence = (
        "The held-out adjacent and central medians are "
        f"{float(adjacent['observed_median']):.6f} and "
        f"{float(central['observed_median']):.6f}; their complete-realization "
        "confidence intervals do not overlap either sealed covariance prediction."
    )
    prediction_sha = str(inference.get("prediction_sha256", ""))
    if len(prediction_sha) != 64:
        raise ValueError("inference does not contain a full prediction hash")
    lines = [
        "% Generated from audited v7 inference; do not edit.",
        r"\newif\ifheldoutcomplete",
        r"\heldoutcompletetrue",
        _macro("HeldoutAbstract", _branch_abstract(branch, rejected_groups)),
        _macro("HeldoutBranch", branch.replace("_", r"\_")),
        _macro("HeldoutResultSentence", result_sentence),
        _macro("PilotResultSentence", pilot_sentence),
        _macro("HeldoutSeal", prediction_sha[:12]),
        _macro(
            "HeldoutAdjacentObserved",
            f"{float(adjacent['observed_median']):.6f}",
        ),
        _macro(
            "HeldoutAdjacentPhysical",
            _interval_macro(adjacent["physical_bootstrap_interval"]),
        ),
        _macro(
            "HeldoutAdjacentCollapsed",
            _interval_macro(adjacent["collapsed_prediction_interval"]),
        ),
        _macro(
            "HeldoutAdjacentHodge",
            _interval_macro(adjacent["hodge_prediction_interval"]),
        ),
        _macro(
            "HeldoutCentralObserved",
            f"{float(central['observed_median']):.6f}",
        ),
        _macro(
            "HeldoutCentralPhysical",
            _interval_macro(central["physical_bootstrap_interval"]),
        ),
        _macro(
            "HeldoutCentralCollapsed",
            _interval_macro(central["collapsed_prediction_interval"]),
        ),
        _macro(
            "HeldoutCentralHodge",
            _interval_macro(central["hodge_prediction_interval"]),
        ),
    ]
    _atomic_text(results_tex, "\n".join(lines) + "\n")
    _atomic_copy(figure_pdf, figure_target)
    checks = {
        "complete_pilot_grid": _expected_pilot_grid(groups),
        "complete_primary_pair": _expected_primary_pair(primary),
        "publishable_registered_branch": branch in PUBLISHABLE_BRANCHES,
        "figure_manifest_matches_sources": True,
        "result_macro_enabled": r"\heldoutcompletetrue"
        in Path(results_tex).read_text(encoding="utf-8"),
        "figure_copy_exact": sha256(figure_target) == sha256(figure_pdf),
    }
    manifest = {
        "version": "v7",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selected_branch": branch,
        "prediction_sha256": prediction_sha,
        "inputs": {
            Path(pilot_json).name: sha256(pilot_json),
            Path(inference_json).name: sha256(inference_json),
            Path(figure_manifest_json).name: sha256(figure_manifest_json),
            Path(figure_pdf).name: sha256(figure_pdf),
        },
        "outputs": {
            str(Path(results_tex).name): sha256(results_tex),
            str(Path(figure_target).name): sha256(figure_target),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    if not manifest["passed"]:
        raise RuntimeError(f"manuscript asset build failed: {checks}")
    _atomic_json(manifest_json, manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-json", type=Path, default=PILOT_JSON)
    parser.add_argument("--inference-json", type=Path, default=N14_INFERENCE_JSON)
    parser.add_argument(
        "--figure-manifest-json", type=Path, default=FIGURE_MANIFEST_JSON
    )
    parser.add_argument("--figure-pdf", type=Path, default=FIGURE_PDF)
    return parser


def main() -> None:
    args = _parser().parse_args()
    payload = build_manuscript_assets(
        pilot_json=args.pilot_json,
        inference_json=args.inference_json,
        figure_manifest_json=args.figure_manifest_json,
        figure_pdf=args.figure_pdf,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
