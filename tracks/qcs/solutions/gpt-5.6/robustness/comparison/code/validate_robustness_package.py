#!/usr/bin/env python3
"""Validate a freshly generated robustness comparison run.

This validator uses only the Python standard library.  It checks scientific
acceptance metadata, declared artifact counts, source hashes, and exact
manifest closure without importing the simulation stack.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_PATH = "artifact_manifest.json"
PROGRESS_PATH = "progress.json"
SOURCE_SCRIPT_PATH = "code/hessian_loop_failure_map.py"
REQUIREMENTS_PATH = "requirements.txt"

EXPECTED_FULL_FIGURES = [
    "figs/fig01_baseline_hessian.png",
    "figs/fig02_trajectories.png",
    "figs/fig03_failure_map.png",
    "figs/fig04_quadratic_breakdown.png",
    "figs/fig05_subspace_rotation.png",
    "figs/fig06_channel_decomposition.png",
    "figs/fig07_noise_conditioning.png",
    "figs/fig08_pathology_gallery.png",
    "figs/fig09_hamiltonian_channels.png",
]
EXPECTED_FULL_DATA = [
    "data/baseline.json",
    "data/baseline.npz",
    "data/channel_decomposition.csv",
    "data/core_scan.csv",
    "data/hamiltonian_error_scan.csv",
    "data/noise_scan.csv",
    "data/pathology_scan.csv",
    "data/subspace_rotation.csv",
]
EXPECTED_BASELINE_ARTIFACTS = {
    "data/baseline.json",
    "data/baseline.npz",
    "figs/fig01_baseline_hessian.png",
    "summary.json",
}
TEXT_SUFFIXES = {".csv", ".gitignore", ".json", ".md", ".py", ".tex", ".txt"}
PAPER_REFERENCE_NAMES = {"paper-fig1.png", "paper-fig5.png"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def is_safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and "\\" not in value
        and not path.is_absolute()
        and ".." not in path.parts
        and value == path.as_posix()
    )


def manifest_candidate(relative_path: str) -> bool:
    return (
        relative_path not in {MANIFEST_PATH, PROGRESS_PATH}
        and not relative_path.endswith(".tmp")
    )


class Audit:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.results.append((name, bool(passed), detail))

    def report(self) -> int:
        for name, passed, detail in self.results:
            suffix = f" — {detail}" if detail else ""
            print(f"[{'PASS' if passed else 'FAIL'}] {name}{suffix}")
        passed = sum(result for _, result, _ in self.results)
        total = len(self.results)
        print(f"\nValidation: {passed}/{total} checks passed.")
        return 0 if passed == total else 1


def read_text_safely(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def unsafe_text_hits(run_dir: Path, source_root: Path) -> list[str]:
    # Construct the legacy marker in pieces so this validator does not flag
    # its own source while still detecting the deprecated challenge-tree path.
    legacy_marker = "/".join(("tracks", "qcs"))
    personal_patterns = [
        re.compile(r"(?i)\b[a-z]:[\\/]"),
        re.compile(r"(?i)/mnt/[a-z]/users/[^/\s]+"),
        re.compile(r"/users/[^/\s]+"),
        re.compile(r"/home/[^/\s]+"),
    ]
    candidates: list[tuple[str, Path]] = []
    validator_path = Path(__file__).resolve()
    for path in run_dir.rglob("*"):
        if (
            path.is_file()
            and path.suffix.lower() in TEXT_SUFFIXES
            and path.resolve() != validator_path
        ):
            candidates.append((f"run:{path.relative_to(run_dir).as_posix()}", path))
    for path in source_root.rglob("*"):
        if (
            path.is_file()
            and path.suffix.lower() in TEXT_SUFFIXES
            and path.resolve() != validator_path
            and "data" not in path.relative_to(source_root).parts
            and "figs" not in path.relative_to(source_root).parts
        ):
            candidates.append(
                (f"source:{path.relative_to(source_root).as_posix()}", path)
            )

    hits = []
    for label, path in candidates:
        text = read_text_safely(path)
        reasons = []
        if legacy_marker in text.replace("\\", "/").lower():
            reasons.append("legacy challenge-tree path")
        if any(pattern.search(text) for pattern in personal_patterns):
            reasons.append("personal absolute path")
        if reasons:
            hits.append(f"{label} ({', '.join(reasons)})")
    return sorted(set(hits))


def validate_source_hashes(
    audit: Audit, summary: dict[str, Any], source_root: Path
) -> None:
    source = summary.get("provenance", {}).get("source", {})
    expected = {
        "script": SOURCE_SCRIPT_PATH,
        "requirements": REQUIREMENTS_PATH,
    }
    structure_ok = isinstance(source, dict) and set(source) == set(expected)
    audit.check("source_hash_records_present", structure_ok)
    if not structure_ok:
        return
    for name, expected_path in expected.items():
        record = source.get(name, {})
        relative_path = record.get("path")
        path_ok = relative_path == expected_path and is_safe_relative_path(relative_path)
        audit.check(f"{name}_path_is_portable", path_ok, str(relative_path))
        source_path = source_root / expected_path
        exists = source_path.is_file()
        audit.check(f"{name}_source_exists", exists, expected_path)
        if not exists:
            continue
        audit.check(
            f"{name}_byte_count_matches",
            record.get("bytes") == source_path.stat().st_size,
        )
        audit.check(
            f"{name}_sha256_matches",
            record.get("sha256") == sha256_file(source_path),
        )


def validate_manifest(
    audit: Audit,
    run_dir: Path,
    expected_artifacts: set[str],
) -> None:
    manifest_file = run_dir / MANIFEST_PATH
    audit.check("artifact_manifest_exists", manifest_file.is_file())
    if not manifest_file.is_file():
        return
    try:
        manifest = load_json(manifest_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        audit.check("artifact_manifest_json_valid", False, str(exc))
        return
    audit.check("artifact_manifest_json_valid", True)
    audit.check(
        "artifact_manifest_schema_version",
        manifest.get("schema_version") == 1,
    )
    audit.check(
        "artifact_manifest_declares_non_self_contained",
        manifest.get("manifest_is_self_contained") is False,
    )
    audit.check(
        "artifact_manifest_exclusions_declared",
        set(manifest.get("excluded_paths", []))
        == {MANIFEST_PATH, PROGRESS_PATH, "*.tmp"},
    )
    artifacts = manifest.get("artifacts")
    structure_ok = isinstance(artifacts, list) and all(
        isinstance(item, dict) for item in artifacts
    )
    audit.check("artifact_manifest_entries_are_objects", structure_ok)
    if not structure_ok:
        return

    paths = [item.get("path") for item in artifacts]
    unique_safe_paths = (
        all(isinstance(path, str) and is_safe_relative_path(path) for path in paths)
        and len(paths) == len(set(paths))
    )
    audit.check("artifact_manifest_paths_unique_and_portable", unique_safe_paths)
    if not unique_safe_paths:
        return

    declared = set(paths)
    actual = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
        and manifest_candidate(path.relative_to(run_dir).as_posix())
    }
    audit.check(
        "artifact_manifest_exact_filesystem_closure",
        declared == actual,
        f"declared={len(declared)}, actual={len(actual)}",
    )
    audit.check(
        "generated_artifact_set_exact",
        declared == expected_artifacts,
        f"declared={len(declared)}, expected={len(expected_artifacts)}",
    )
    audit.check(
        "paper_reference_images_not_generated",
        not any(PurePosixPath(path).name in PAPER_REFERENCE_NAMES for path in declared),
    )

    metadata_ok = True
    for item in artifacts:
        artifact_path = run_dir / item["path"]
        if (
            not artifact_path.is_file()
            or item.get("bytes") != artifact_path.stat().st_size
            or item.get("sha256") != sha256_file(artifact_path)
        ):
            metadata_ok = False
            break
    audit.check("artifact_manifest_sizes_and_hashes_match", metadata_ok)


def validate_inputs_and_counts(
    audit: Audit, summary: dict[str, Any], run_dir: Path, mode: str
) -> None:
    settings = summary.get("input_settings", {})
    execution = settings.get("execution", {})
    model = settings.get("model", {})
    scan = settings.get("scan", {})
    expected_eta = [0.01, 0.03, 0.06, 0.1, 0.2, 0.35, 0.6, 1.0]
    expected_p = [0.0, 0.5, 1.0]
    expected_noise = [0.0, 1e-6, 1e-5, 1e-4, 1e-3]
    settings_ok = (
        model.get("n_time") == 256
        and model.get("real_control_coordinates") == 512
        and scan.get("eta_values") == expected_eta
        and scan.get("p_parallel_values") == expected_p
        and scan.get("noise_values") == expected_noise
        and scan.get("success_target") == 1e-5
        and scan.get("maximum_cycles") == 8
        and scan.get("line_fit_samples") == 7
        and scan.get("active_rank_relative_threshold") == 1e-8
        and execution.get("baseline_only") is (mode == "baseline")
    )
    audit.check("machine_readable_input_settings_match_contract", settings_ok)

    seeds = execution.get("seeds_per_cell")
    scope = summary.get("scope", {})
    seeds_ok = seeds == 10
    audit.check("seeds_per_cell_matches_sealed_contract", seeds_ok)
    seed_count = seeds if seeds_ok else 0
    if mode == "baseline":
        expected_scope = {
            "core_trials": 0,
            "seeds_per_cell": seed_count,
            "noise_trials": 0,
            "pathology_trials": 0,
            "hamiltonian_error_points": 0,
        }
        audit.check("baseline_scope_counts_match", scope == expected_scope)
        return

    expected_scope = {
        "core_trials": len(expected_eta) * len(expected_p) * seed_count,
        "seeds_per_cell": seed_count,
        "noise_trials": 2 * len(expected_noise) * seed_count,
        "pathology_trials": 6,
        "hamiltonian_error_points": 10,
    }
    audit.check("full_scope_counts_match", seeds_ok and scope == expected_scope)
    csv_expectations = {
        "data/core_scan.csv": expected_scope["core_trials"],
        "data/subspace_rotation.csv": len(expected_eta) * len(expected_p),
        "data/channel_decomposition.csv": 6,
        "data/noise_scan.csv": expected_scope["noise_trials"],
        "data/pathology_scan.csv": expected_scope["pathology_trials"],
        "data/hamiltonian_error_scan.csv": expected_scope[
            "hamiltonian_error_points"
        ],
    }
    rows_ok = all(
        (run_dir / relative_path).is_file()
        and csv_row_count(run_dir / relative_path) == expected_rows
        for relative_path, expected_rows in csv_expectations.items()
    )
    audit.check("csv_row_counts_match_declared_scope", rows_ok)


def validate_run(run_dir: Path, source_root: Path, requested_mode: str) -> int:
    audit = Audit()
    summary_file = run_dir / "summary.json"
    audit.check("summary_exists", summary_file.is_file())
    if not summary_file.is_file():
        return audit.report()
    try:
        summary = load_json(summary_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        audit.check("summary_json_valid", False, str(exc))
        return audit.report()
    audit.check("summary_json_valid", True)

    status = summary.get("status")
    inferred_mode = (
        "baseline"
        if status == "baseline_complete"
        else "full"
        if status == "complete"
        else "unknown"
    )
    mode = inferred_mode if requested_mode == "auto" else requested_mode
    audit.check(
        "summary_status_matches_mode",
        inferred_mode == mode,
        f"status={status!r}, mode={mode!r}",
    )

    baseline = summary.get("baseline", {})
    baseline_ok = (
        baseline.get("accepted") is True
        and isinstance(baseline.get("baseline_infidelity"), (int, float))
        and baseline["baseline_infidelity"] <= 1e-5
        and baseline.get("active_rank") == 5
        and isinstance(baseline.get("sixth_to_first_eigenvalue"), (int, float))
        and baseline["sixth_to_first_eigenvalue"] <= 1e-8
        and isinstance(baseline.get("phase_error_to_pi"), (int, float))
        and baseline["phase_error_to_pi"] <= 5e-4
    )
    audit.check("baseline_acceptance_contract_passes", baseline_ok)

    baseline_file = run_dir / "data" / "baseline.json"
    baseline_record_matches = False
    if baseline_file.is_file():
        try:
            baseline_record_matches = load_json(baseline_file) == baseline
        except (OSError, ValueError, json.JSONDecodeError):
            baseline_record_matches = False
    audit.check("baseline_record_matches_summary", baseline_record_matches)

    expected_figures = (
        [EXPECTED_FULL_FIGURES[0]] if mode == "baseline" else EXPECTED_FULL_FIGURES
    )
    figures = summary.get("figures")
    figures_ok = figures == expected_figures and all(
        (run_dir / relative_path).is_file() for relative_path in expected_figures
    )
    audit.check("figure_list_and_files_match_contract", figures_ok)

    timing = summary.get("timing", {})
    wall_seconds = timing.get("wall_seconds")
    timing_ok = (
        isinstance(wall_seconds, (int, float))
        and wall_seconds >= 0
        and timing.get("clock") == "time.perf_counter"
        and timing.get("jax_warm_cold_state") == "uncontrolled"
        and isinstance(timing.get("scope"), str)
        and isinstance(timing.get("interpretation"), str)
        and summary.get("elapsed_seconds") == wall_seconds
    )
    audit.check("timing_semantics_are_explicit", timing_ok)
    audit.check(
        "provenance_schema_version",
        summary.get("provenance", {}).get("schema_version") == 1,
    )

    validate_inputs_and_counts(audit, summary, run_dir, mode)
    validate_source_hashes(audit, summary, source_root)

    expected_artifacts = (
        EXPECTED_BASELINE_ARTIFACTS
        if mode == "baseline"
        else set(EXPECTED_FULL_DATA + EXPECTED_FULL_FIGURES + ["summary.json"])
    )
    validate_manifest(audit, run_dir, expected_artifacts)

    unsafe_hits = unsafe_text_hits(run_dir, source_root)
    audit.check(
        "no_personal_or_legacy_paths_in_machine_readable_or_source_text",
        not unsafe_hits,
        ", ".join(unsafe_hits),
    )
    return audit.report()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Comparison source root containing code/ and requirements.txt.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "baseline", "full"),
        default="auto",
    )
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    source_root = args.source_root.expanduser().resolve()
    if not run_dir.is_dir():
        parser.error(f"--run-dir is not a directory: {args.run_dir}")
    if not source_root.is_dir():
        parser.error(f"--source-root is not a directory: {args.source_root}")
    raise SystemExit(validate_run(run_dir, source_root, args.mode))


if __name__ == "__main__":
    main()
