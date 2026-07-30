#!/usr/bin/env python3
"""Validate the explicit Challenge-113 team submission closure.

The validator uses only the Python standard library. It can run from the
public repository or from an extracted allowlisted candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".csv",
    ".html",
    ".json",
    ".md",
    ".py",
    ".svg",
    ".tex",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PERSONAL_PATH_PATTERNS = (
    re.compile(r"C:\\Users\\", re.IGNORECASE),
    re.compile(r"/home/coder_", re.IGNORECASE),
    re.compile(r"/mnt/c/Users/", re.IGNORECASE),
    re.compile(r"D:\\study\\", re.IGNORECASE),
)
TOKEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
)
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
EXCLUDED_TEAM_PATHS = {
    "robustness/AGENTS.md",
    "robustness/comparison/figs/paper-fig1.png",
    "robustness/comparison/figs/paper-fig5.png",
}
GUARD_SOURCE_PATHS = {
    "tools/validate_team_package.py",
    "core-sim-to-real/tests/test_final_contract.py",
}
ROBUSTNESS_SEAL_SOURCE_COMMIT = (
    "7bc049f8302e9b42c8f64590732291de92bef3a7"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(root: Path) -> list[str]:
    path = root / "team_submission_allowlist.txt"
    rows = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return rows


def actual_files(root: Path) -> set[str]:
    ignored_parts = {".git", "__pycache__", "run_outputs"}
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in ignored_parts for part in path.relative_to(root).parts)
        and path.suffix not in {".pyc", ".pyo"}
    }


def scan_text(
    root: Path, paths: list[Path]
) -> tuple[list[str], list[str]]:
    personal_hits: list[str] = []
    token_hits: list[str] = []
    for path in paths:
        if path.relative_to(root).as_posix() in GUARD_SOURCE_PATHS:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        if any(pattern.search(text) for pattern in PERSONAL_PATH_PATTERNS):
            personal_hits.append(path.as_posix())
        if any(pattern.search(text) for pattern in TOKEN_PATTERNS):
            token_hits.append(path.as_posix())
    return personal_hits, token_hits


def broken_manifest_links(
    root: Path, manifest_set: set[str], paths: list[Path]
) -> list[str]:
    failures: list[str] = []
    root_resolved = root.resolve()
    for path in paths:
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for raw_target in MARKDOWN_LINK_PATTERN.findall(text):
            target = raw_target.strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            else:
                target = target.split(maxsplit=1)[0]
            if (
                not target
                or target.startswith("#")
                or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
            ):
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            resolved = (path.parent / target).resolve()
            try:
                relative = resolved.relative_to(root_resolved).as_posix()
            except ValueError:
                failures.append(
                    f"{path.relative_to(root).as_posix()} -> {raw_target}"
                )
                continue
            if resolved.is_dir():
                prefix = relative.rstrip("/") + "/"
                accepted = any(row.startswith(prefix) for row in manifest_set)
            else:
                accepted = relative in manifest_set and resolved.is_file()
            if not accepted:
                failures.append(
                    f"{path.relative_to(root).as_posix()} -> {raw_target}"
                )
    return failures


def validate(root: Path, strict_closure: bool) -> dict[str, Any]:
    manifest = read_manifest(root)
    manifest_set = set(manifest)
    paths = [root / row for row in manifest]
    missing = [row for row, path in zip(manifest, paths) if not path.is_file()]

    core_manifest = [
        line.strip()
        for line in (
            root / "core-sim-to-real" / "submission_allowlist.txt"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    expected_core = {f"core-sim-to-real/{row}" for row in core_manifest}
    observed_core = {
        row for row in manifest if row.startswith("core-sim-to-real/")
    }

    personal_hits, token_hits = scan_text(
        root, [path for path in paths if path.is_file()]
    )
    broken_links = broken_manifest_links(
        root, manifest_set, [path for path in paths if path.is_file()]
    )
    protected_notebooks = [
        path.relative_to(root).as_posix()
        for path in root.rglob("neural_schrodinger.ipynb")
    ]

    final_run = load_json(root / "core-sim-to-real" / "final" / "run.json")
    final_report = load_json(
        root / "core-sim-to-real" / "final" / "report.json"
    )
    attempt49_path = (
        root
        / "core-sim-to-real"
        / "results_summary"
        / "QL1F-attempt49-fresh-confirmation.json"
    )
    attempt50 = load_json(
        root
        / "core-sim-to-real"
        / "results_summary"
        / "QL1F-attempt50-final-audit.json"
    )
    attempt51 = load_json(
        root
        / "core-sim-to-real"
        / "results_summary"
        / "QL1F-attempt51-queries-to-target.json"
    )
    attempt52 = load_json(
        root
        / "core-sim-to-real"
        / "results_summary"
        / "QL1F-attempt52-gap-invariant-audit.json"
    )
    robustness = load_json(
        root / "robustness" / "comparison" / "summary.json"
    )
    robustness_seal = load_json(
        root / "robustness" / "comparison" / "FRESH_RUN_SEAL.json"
    )
    robustness_root = root / "robustness" / "comparison"
    fresh_evidence_root = robustness_root / "fresh-run-evidence"
    fresh_full_root = fresh_evidence_root / "full"
    fresh_baseline_manifest_path = (
        fresh_evidence_root / "baseline" / "artifact_manifest.json"
    )
    fresh_baseline_summary_path = (
        fresh_evidence_root / "baseline" / "summary.json"
    )
    fresh_full_manifest_path = fresh_full_root / "artifact_manifest.json"
    fresh_full_summary_path = fresh_full_root / "summary.json"
    fresh_comparison_path = fresh_evidence_root / "comparison.json"
    fresh_full_manifest = load_json(fresh_full_manifest_path)
    fresh_comparison = load_json(fresh_comparison_path)
    full_manifest_records = {
        row["path"]: row for row in fresh_full_manifest["artifacts"]
    }
    fresh_scientific_paths = {
        "summary.json",
        "data/baseline.json",
        "data/channel_decomposition.csv",
        "data/core_scan.csv",
        "data/hamiltonian_error_scan.csv",
        "data/noise_scan.csv",
        "data/pathology_scan.csv",
        "data/subspace_rotation.csv",
    }
    comparison_process = subprocess.run(
        [
            sys.executable,
            str(robustness_root / "code" / "compare_robustness_runs.py"),
            "--reference-dir",
            str(robustness_root),
            "--candidate-dir",
            str(fresh_full_root),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    try:
        recomputed_comparison = json.loads(comparison_process.stdout)
    except json.JSONDecodeError:
        recomputed_comparison = {}

    expected_robustness_figures = {
        (
            "robustness/comparison/figs/"
            f"fig{index:02d}_{name}.png"
        )
        for index, name in enumerate(
            (
                "baseline_hessian",
                "trajectories",
                "failure_map",
                "quadratic_breakdown",
                "subspace_rotation",
                "channel_decomposition",
                "noise_conditioning",
                "pathology_gallery",
                "hamiltonian_channels",
            ),
            start=1,
        )
    }

    checks = {
        "manifest_has_no_duplicates": len(manifest) == len(manifest_set),
        "all_manifest_files_exist": not missing,
        "core_manifest_is_exactly_embedded": observed_core == expected_core,
        "excluded_working_or_reference_files_absent": not (
            manifest_set & EXCLUDED_TEAM_PATHS
        ),
        "protected_notebook_absent": not protected_notebooks,
        "personal_absolute_paths_absent": not personal_hits,
        "credential_token_patterns_absent": not token_hits,
        "allowlisted_markdown_links_close": not broken_links,
        "strict_candidate_closure": (
            actual_files(root) == manifest_set if strict_closure else True
        ),
        "core_challenge_complete": (
            final_run["challenge"]["number"] == 113
            and final_run["challenge"]["status"] == "complete"
        ),
        "core_three_figures_exact": (
            {figure["id"] for figure in final_run["figures"]}
            == {"queries-to-target", "headline", "gap-and-invariant"}
        ),
        "core_four_report_sections_exact": (
            [section["title"] for section in final_report["sections"]]
            == ["Challenge", "Approach", "Results", "Highlight"]
        ),
        "attempt49_hash_closes": (
            canonical_sha256(attempt49_path)
            == final_run["provenance"][
                "formal_result_canonical_sha256"
            ]
        ),
        "attempt50_all_checks_pass": (
            attempt50["status"] == "pass"
            and all(attempt50["checks"].values())
        ),
        "attempt51_all_checks_pass": (
            attempt51["status"] == "pass"
            and all(attempt51["checks"].values())
        ),
        "attempt52_all_checks_pass": (
            attempt52["status"] == "pass"
            and all(attempt52["checks"].values())
        ),
        "optional_paper_reproduction_absent_from_fallback": not any(
            row.startswith("reproduce/") for row in manifest
        ),
        "robustness_baseline_acceptance_pass": (
            robustness["status"] == "complete"
            and robustness["baseline"]["accepted"]
            and int(robustness["baseline"]["active_rank"]) == 5
            and float(robustness["baseline"]["baseline_infidelity"]) <= 1e-5
        ),
        "robustness_scope_counts_close": (
            robustness["scope"]
            == {
                "core_trials": 240,
                "seeds_per_cell": 10,
                "noise_trials": 100,
                "pathology_trials": 6,
                "hamiltonian_error_points": 10,
            }
        ),
        "robustness_nine_generated_figures_present": (
            expected_robustness_figures <= manifest_set
            and all((root / path).is_file() for path in expected_robustness_figures)
        ),
        "robustness_fresh_run_source_sealed": (
            robustness_seal["status"] == "pass"
            and robustness_seal["source_commit"]
            == ROBUSTNESS_SEAL_SOURCE_COMMIT
            and canonical_sha256(
                robustness_root
                / robustness_seal["source"]["simulation_script"]["path"]
            )
            == robustness_seal["source"]["simulation_script"][
                "canonical_sha256"
            ]
            and canonical_sha256(
                robustness_root
                / robustness_seal["source"]["requirements"]["path"]
            )
            == robustness_seal["source"]["requirements"]["canonical_sha256"]
            and canonical_sha256(
                robustness_root
                / robustness_seal["source"]["comparison_script"]["path"]
            )
            == robustness_seal["source"]["comparison_script"][
                "canonical_sha256"
            ]
        ),
        "robustness_fresh_run_validators_close": (
            robustness_seal["baseline_run"]["validator_checks_passed"]
            == robustness_seal["baseline_run"]["validator_checks_total"]
            == 32
            and robustness_seal["full_run"]["validator_checks_passed"]
            == robustness_seal["full_run"]["validator_checks_total"]
            == 33
            and robustness_seal["full_run"]["stable_artifact_count"] == 18
            and robustness_seal["full_run"]["core_trials"] == 240
            and robustness_seal["full_run"]["noise_trials"] == 100
            and robustness_seal["full_run"]["pathology_trials"] == 6
            and robustness_seal["full_run"]["hamiltonian_error_points"] == 10
        ),
        "robustness_fresh_run_scientific_comparison_pass": (
            robustness_seal["scientific_comparison"]["status"] == "pass"
            and robustness_seal["scientific_comparison"][
                "numeric_comparisons"
            ]
            == 3951
            and robustness_seal["scientific_comparison"][
                "categorical_comparisons"
            ]
            == 402
            and robustness_seal["scientific_comparison"]["mismatch_count"]
            == 0
            and float(
                robustness_seal["scientific_comparison"][
                    "maximum_tolerance_ratio"
                ]
            )
            < 1.0
        ),
        "robustness_fresh_evidence_hashes_close": (
            robustness_seal["evidence_root"] == "fresh-run-evidence"
            and sha256_file(fresh_baseline_summary_path)
            == robustness_seal["baseline_run"]["summary_sha256"]
            and sha256_file(fresh_baseline_manifest_path)
            == robustness_seal["baseline_run"][
                "artifact_manifest_sha256"
            ]
            and sha256_file(fresh_full_summary_path)
            == robustness_seal["full_run"]["summary_sha256"]
            and sha256_file(fresh_full_manifest_path)
            == robustness_seal["full_run"]["artifact_manifest_sha256"]
            and sha256_file(fresh_comparison_path)
            == robustness_seal["scientific_comparison"][
                "comparison_json_sha256"
            ]
        ),
        "robustness_fresh_scientific_artifacts_close": (
            fresh_scientific_paths <= set(full_manifest_records)
            and all(
                (fresh_full_root / relative_path).is_file()
                and (fresh_full_root / relative_path).stat().st_size
                == int(full_manifest_records[relative_path]["bytes"])
                and sha256_file(fresh_full_root / relative_path)
                == full_manifest_records[relative_path]["sha256"]
                for relative_path in fresh_scientific_paths
            )
        ),
        "robustness_fresh_comparison_recomputes": (
            comparison_process.returncode == 0
            and recomputed_comparison == fresh_comparison
            and fresh_comparison["status"] == "pass"
            and fresh_comparison["numeric_comparisons"] == 3951
            and fresh_comparison["categorical_comparisons"] == 402
            and fresh_comparison["mismatch_count"] == 0
        ),
        "two_requirements_files_are_separate": all(
            path in manifest_set
            for path in (
                "core-sim-to-real/requirements.txt",
                "robustness/comparison/requirements.txt",
            )
        ),
    }

    warnings = []
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "root": str(root),
        "strict_closure": strict_closure,
        "manifest_files": len(manifest),
        "checks": checks,
        "missing": missing,
        "personal_path_hits": personal_hits,
        "token_pattern_hits": token_hits,
        "broken_manifest_links": broken_links,
        "protected_notebooks": protected_notebooks,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="repository or extracted-candidate root",
    )
    parser.add_argument(
        "--strict-closure",
        action="store_true",
        help="require every file under root to appear in the manifest",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = validate(args.root.resolve(), args.strict_closure)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        passed = sum(payload["checks"].values())
        total = len(payload["checks"])
        print(
            f"team package {payload['status']}; "
            f"checks={passed}/{total}; "
            f"files={payload['manifest_files']}"
        )
        for warning in payload["warnings"]:
            print(f"warning: {warning}")
        if payload["status"] != "pass":
            for name, value in payload["checks"].items():
                if not value:
                    print(f"failed: {name}", file=sys.stderr)

    raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
