#!/usr/bin/env python3
"""Attempt 49: preregistered one-shot fresh confirmation.

The default mode performs source/firewall validation only. Simulator imports
and truth construction occur exclusively inside ``--run``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
REPO_ROOT = CORE.parent
CONFIG_PATH = HERE / "attempt49_fresh_confirmation_config.json"
PROTOCOL_PATH = CORE / "docs" / "ATTEMPT49_PROTOCOL.md"
MANIFEST_PATH = HERE / "attempt49_preregistration_manifest.json"
PARTIAL_PATH = (
    CORE
    / "results_summary"
    / "QL1F-attempt49-fresh-confirmation.partial.json"
)
OUTPUT_PATH = (
    CORE / "results_summary" / "QL1F-attempt49-fresh-confirmation.json"
)
REPORT_PATH = CORE / "docs" / "ATTEMPT49_REPORT.md"
PLOT_PNG = CORE / "plots" / "attempt49-fresh-confirmation.png"
PLOT_SVG = CORE / "plots" / "attempt49-fresh-confirmation.svg"

METHODS = (
    "model-informed-k15",
    "model-informed-k40",
    "raw-coordinate-global-40",
)
FAMILIES = ("control-map", "drift", "combined")
ALLOWED_RUNTIME_OUTPUTS = {
    path.relative_to(REPO_ROOT).as_posix()
    for path in (PARTIAL_PATH, OUTPUT_PATH, REPORT_PATH, PLOT_PNG, PLOT_SVG)
}
REQUIRED_SEALED_FILES = {
    "code/attempt44_dimension_cost.py",
    "code/attempt44_dimension_cost_config.json",
    "code/attempt49_fresh_confirmation.py",
    "code/attempt49_fresh_confirmation_config.json",
    "code/cycle5_statistics.py",
    "code/phase3_common.py",
    "docs/ATTEMPT44_PROTOCOL.md",
    "docs/ATTEMPT48_PROTOCOL.md",
    "docs/ATTEMPT49_PROTOCOL.md",
    "results_summary/QL1F-attempt44-dimension-cost.json",
    "results_summary/QL1F-attempt48-integrity-audit.json",
}
AUDITED_CHECKPOINT = "375e1bf175bc9ba66f862b3b9fb20a1a84734433"


def canonical_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        text.rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def resolve_manifest_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.parts and path.parts[0] in {"core-sim-to-real", "robustness"}:
        return REPO_ROOT / path
    return CORE / path


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    benchmark = config["benchmark"]
    seeds = tuple(int(value) for value in benchmark["fresh_truth_seeds"])
    epsilon_by_family = {
        str(key): float(value)
        for key, value in benchmark["fixed_epsilon_by_family"].items()
    }
    methods = tuple(row["name"] for row in config["methods"])
    method_rows = {row["name"]: row for row in config["methods"]}
    expected_caps = {
        "model-informed-k15": (66, 2_099_200, 15),
        "model-informed-k40": (166, 5_376_000, 40),
        "raw-coordinate-global-40": (166, 5_376_000, 40),
    }
    expected_gates = {
        "destructive_accepted_step_rate_ucb95_max": 0.05,
        "full_cap_cost_ratio_max_exclusive": 0.6,
        "pooled_k15_success_lcb95_min": 0.75,
        "success_difference_k15_minus_k40_lcb95_min_exclusive": -0.1,
        "success_difference_k15_minus_raw40_lcb95_min_exclusive": 0.0,
    }
    checks = {
        "attempt_is_49": int(config["attempt"]) == 49,
        "families_exact": tuple(benchmark["families"]) == FAMILIES,
        "fixed_epsilon_map_exact": epsilon_by_family
        == {"control-map": 0.05, "drift": 0.10, "combined": 0.05},
        "fresh_seeds_exact": seeds == tuple(range(260_641, 260_649)),
        "fresh_seeds_disjoint_from_previous": (
            min(seeds) > int(config["firewall"]["previous_truth_seed_max"])
        ),
        "four_nested_replicates": (
            int(benchmark["replicates_per_truth_cell"]) == 4
        ),
        "all_truth_cells_retained": bool(
            benchmark["retain_all_truth_cells"]
        ),
        "methods_exact": methods == METHODS,
        "method_caps_exact": all(
            (
                int(method_rows[name]["full_query_cap"]),
                int(method_rows[name]["full_shot_cap"]),
                int(method_rows[name]["search_dimension"]),
            )
            == expected
            for name, expected in expected_caps.items()
        ),
        "method_constants_exact": (
            int(config["method"]["cycles"]) == 2
            and float(config["method"]["central_difference_delta"]) == 0.05
            and int(config["method"]["shots_per_decision_query"]) == 32_768
            and int(config["method"]["sentinel_shots"]) == 1_024
            and float(config["method"]["trust_radius"]) == 0.25
            and float(config["method"]["ridge_multiplier"]) == 0.1
            and float(config["method"]["confidence"]) == 0.995
            and float(config["method"]["target_infidelity"]) == 1e-3
        ),
        "bootstrap_exact": (
            int(config["bootstrap"]["draws"]) == 20_000
            and int(config["bootstrap"]["seed"]) == 113_049
            and float(config["bootstrap"]["confidence"]) == 0.95
            and config["bootstrap"]["independent_unit"] == "truth-cell"
            and config["bootstrap"]["family_weighting"]
            == "equal-macro-average"
            and config["bootstrap"]["stratify_by"] == "family"
        ),
        "completion_exact": config["completion"]
        == {
            "gram_schmidt_norm_min": 1e-10,
            "raw_coordinate_order": "ascending-index",
            "sign_rule": "largest-absolute-component-positive",
        },
        "gates_exact": config["gates"] == expected_gates,
        "noise_seed_derivation_exact": (
            config["noise_seed_derivation"]["algorithm"]
            == "numpy.random.SeedSequence"
            and config["noise_seed_derivation"]["components"]
            == [113, 49, "family_index", "truth_seed", "replicate"]
            and config["noise_seed_derivation"]["paired_across_methods"] is True
        ),
        "headline_semantics_full_cap": (
            config["semantics"]["cost_headline"] == "full-cap-online"
        ),
        "success_semantics_exact": (
            config["semantics"]["success"]
            == "posthoc accepted-incumbent exact infidelity <= target"
            and config["semantics"]["oracle_scored_first_hit"]
            == "supplementary-hidden-exact-only"
            and config["semantics"]["destructive_safety_interval"]
            == (
                "one-sided-95pct-exact-clopper-pearson-on-accepted-"
                "nonzero-steps"
            )
        ),
        "audited_checkpoint_exact": (
            config["provenance"]["audited_checkpoint_commit"]
            == AUDITED_CHECKPOINT
        ),
    }
    return {
        "checks": checks,
        "all_pass": all(checks.values()),
        "truth_cells": len(FAMILIES) * len(seeds),
        "expected_runs": (
            len(FAMILIES)
            * len(seeds)
            * int(benchmark["replicates_per_truth_cell"])
            * len(METHODS)
        ),
    }


def validate_preregistration(
    *,
    require_public_commit: bool,
    allow_runtime_outputs: bool,
) -> dict[str, Any]:
    for path in (CONFIG_PATH, PROTOCOL_PATH, MANIFEST_PATH, Path(__file__)):
        if not path.is_file():
            raise FileNotFoundError(path)
    config = load_json(CONFIG_PATH)
    manifest = load_json(MANIFEST_PATH)
    config_validation = validate_config(config)

    sealed = manifest["sealed_files"]
    sealed_set = set(sealed)
    safe_relative_seal_paths = all(
        not Path(path_text).is_absolute()
        and ".." not in Path(path_text).parts
        for path_text in sealed
    )
    seal_checks: dict[str, bool] = {}
    seal_details: dict[str, Any] = {}
    sealed_files_tracked = True
    for path_text, expected in sealed.items():
        path = resolve_manifest_path(path_text)
        actual = canonical_sha256(path) if path.is_file() else "missing"
        seal_checks[path_text] = actual == expected
        seal_details[path_text] = {"expected": expected, "actual": actual}
        if path.is_file():
            repository_path = path.relative_to(REPO_ROOT).as_posix()
            sealed_files_tracked = sealed_files_tracked and (
                git(
                    "ls-files",
                    "--error-unmatch",
                    repository_path,
                    check=False,
                ).returncode
                == 0
            )
        else:
            sealed_files_tracked = False

    manifest_tracked = (
        git(
            "ls-files",
            "--error-unmatch",
            MANIFEST_PATH.relative_to(REPO_ROOT).as_posix(),
            check=False,
        ).returncode
        == 0
    )

    head = git("rev-parse", "HEAD").stdout.strip()
    parent = config["provenance"]["audited_checkpoint_commit"]
    parent_is_ancestor = (
        git("merge-base", "--is-ancestor", parent, head, check=False).returncode
        == 0
    )
    tracked_clean = (
        git("diff", "--quiet", "--", check=False).returncode == 0
        and git("diff", "--cached", "--quiet", check=False).returncode == 0
    )
    untracked = {
        line.strip()
        for line in git(
            "ls-files", "--others", "--exclude-standard"
        ).stdout.splitlines()
        if line.strip()
    }
    untracked_allowed = (
        untracked.issubset(ALLOWED_RUNTIME_OUTPUTS)
        if allow_runtime_outputs
        else not untracked
    )
    remote_fetch_succeeded = True
    remote_main_sha = None
    origin_contains_head = True
    if require_public_commit:
        fetch = git("fetch", "--quiet", "origin", "main", check=False)
        remote_fetch_succeeded = fetch.returncode == 0
        if remote_fetch_succeeded:
            remote_main_sha = git("rev-parse", "FETCH_HEAD").stdout.strip()
            origin_contains_head = (
                git(
                    "merge-base",
                    "--is-ancestor",
                    head,
                    remote_main_sha,
                    check=False,
                ).returncode
                == 0
            )
        else:
            origin_contains_head = False
    checks = {
        **{
            f"sealed:{path}": passed
            for path, passed in seal_checks.items()
        },
        **{
            f"config:{name}": passed
            for name, passed in config_validation["checks"].items()
        },
        "manifest_attempt_is_49": int(manifest["attempt"]) == 49,
        "manifest_parent_matches_config": (
            manifest["audited_checkpoint_commit"] == parent
        ),
        "manifest_required_seal_set_exact": (
            sealed_set == REQUIRED_SEALED_FILES and bool(sealed_set)
        ),
        "manifest_seal_paths_are_safe_relative_paths": (
            safe_relative_seal_paths
        ),
        "all_sealed_files_are_git_tracked": sealed_files_tracked,
        "manifest_is_git_tracked": manifest_tracked,
        "audited_checkpoint_is_ancestor": parent_is_ancestor,
        "tracked_files_clean": tracked_clean,
        "untracked_files_allowed": untracked_allowed,
        "live_remote_main_fetch_succeeded": remote_fetch_succeeded,
        "current_commit_is_public_on_origin_main": origin_contains_head,
        "final_result_absent_before_run": not OUTPUT_PATH.exists(),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "seal_details": seal_details,
        "config_validation": config_validation,
        "git": {
            "head": head,
            "audited_checkpoint": parent,
            "untracked": sorted(untracked),
            "remote_main_sha": remote_main_sha,
            "live_remote_main_fetch_succeeded": remote_fetch_succeeded,
            "origin_contains_head": origin_contains_head,
        },
        "manifest_canonical_sha256": canonical_sha256(MANIFEST_PATH),
    }


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    return False


def write_checkpoint(
    *,
    preregistration: dict[str, Any],
    runs: list[dict[str, Any]],
) -> None:
    payload = {
        "schema": "QL1F-attempt49-partial-v1",
        "attempt": 49,
        "status": "incomplete",
        "preregistration_commit": preregistration["git"]["head"],
        "manifest_canonical_sha256": preregistration[
            "manifest_canonical_sha256"
        ],
        "completed_run_count": len(runs),
        "runs_canonical_json_sha256": canonical_json_sha256(runs),
        "runs": runs,
        "rule": "resume-only; intermediate outcomes cannot change protocol",
    }
    atomic_write_json(PARTIAL_PATH, payload)


def load_checkpoint(
    preregistration: dict[str, Any],
    np: Any,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not PARTIAL_PATH.exists():
        return []
    payload = load_json(PARTIAL_PATH)
    runs = payload.get("runs", [])
    if (
        payload.get("schema") != "QL1F-attempt49-partial-v1"
        or payload.get("preregistration_commit")
        != preregistration["git"]["head"]
        or payload.get("manifest_canonical_sha256")
        != preregistration["manifest_canonical_sha256"]
        or int(payload.get("completed_run_count", -1)) != len(runs)
        or payload.get("runs_canonical_json_sha256")
        != canonical_json_sha256(runs)
        or not finite_tree(runs)
    ):
        raise RuntimeError("partial checkpoint integrity mismatch")

    method_config = {row["name"]: row for row in config["methods"]}
    expected: list[tuple[str, int, str]] = []
    for family in FAMILIES:
        epsilon = float(
            config["benchmark"]["fixed_epsilon_by_family"][family]
        )
        for truth_seed in config["benchmark"]["fresh_truth_seeds"]:
            selected_cell = f"{family}:{int(truth_seed)}:{epsilon:g}"
            for replicate in range(4):
                for method in METHODS:
                    expected.append((selected_cell, replicate, method))
    observed = [
        (
            run.get("selected_cell"),
            int(run.get("replicate", -1)),
            run.get("method"),
        )
        for run in runs
    ]
    if observed != expected[: len(observed)]:
        raise RuntimeError(
            "partial checkpoint is not the canonical run-order prefix"
        )
    for run in runs:
        family = str(run["family"])
        truth_seed = int(run["truth_seed"])
        replicate = int(run["replicate"])
        method = str(run["method"])
        epsilon = float(
            config["benchmark"]["fixed_epsilon_by_family"][family]
        )
        expected_seed = paired_noise_seed(
            np,
            FAMILIES.index(family),
            truth_seed,
            replicate,
        )
        method_row = method_config[method]
        if not (
            truth_seed in config["benchmark"]["fresh_truth_seeds"]
            and float(run["epsilon"]) == epsilon
            and run["selected_cell"]
            == f"{family}:{truth_seed}:{epsilon:g}"
            and int(run["noise_seed"]) == expected_seed
            and int(run["search_dimension"])
            == int(method_row["search_dimension"])
            and run["charged_full_cap"]
            == {
                "queries": int(method_row["full_query_cap"]),
                "shots": int(method_row["full_shot_cap"]),
            }
        ):
            raise RuntimeError(
                "partial checkpoint row differs from frozen run grid"
            )
    return runs


def paired_noise_seed(
    np: Any,
    family_index: int,
    truth_seed: int,
    replicate: int,
) -> int:
    sequence = np.random.SeedSequence(
        [113, 49, family_index, int(truth_seed), int(replicate)]
    )
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def make_fresh_truth(
    np: Any,
    model: Any,
    family: str,
    epsilon: float,
    seed: int,
    config: dict[str, Any],
) -> tuple[Any, Any, dict[str, Any]]:
    """Extend the frozen truth formula only to preregistered fresh seeds."""

    epsilon_map = {
        key: float(value)
        for key, value in config["benchmark"][
            "fixed_epsilon_by_family"
        ].items()
    }
    allowed_seeds = {
        int(value) for value in config["benchmark"]["fresh_truth_seeds"]
    }
    if family not in FAMILIES:
        raise ValueError(f"unknown fresh truth family {family!r}")
    if float(epsilon) != epsilon_map[family]:
        raise ValueError(
            f"epsilon {epsilon!r} differs from frozen {family} epsilon"
        )
    if int(seed) not in allowed_seeds:
        raise ValueError(f"seed {seed!r} is not an Attempt-49 fresh seed")

    nominal_drift = np.asarray(model.h_drift, dtype=np.complex128)
    nominal_controls = np.asarray(model.h_controls, dtype=np.complex128)
    dimension = int(nominal_drift.shape[0])
    n_controls = int(nominal_controls.shape[0])
    seed_sequence = np.random.SeedSequence([113, 11, int(seed)])
    map_ss, drift_ss = seed_sequence.spawn(2)
    map_rng = np.random.default_rng(map_ss)
    drift_rng = np.random.default_rng(drift_ss)

    mismatch = map_rng.normal(size=(n_controls, n_controls))
    mismatch /= np.linalg.norm(mismatch, ord=2)
    control_map = np.eye(n_controls) + float(epsilon) * mismatch

    raw = drift_rng.normal(size=(dimension, dimension)) + 1j * (
        drift_rng.normal(size=(dimension, dimension))
    )
    drift_direction = (raw + raw.conj().T) / 2
    drift_direction -= (
        np.trace(drift_direction) * np.eye(dimension) / dimension
    )
    drift_direction /= np.linalg.norm(drift_direction, ord="fro")

    drift_scale = np.linalg.norm(nominal_drift, ord="fro")
    true_drift = np.array(nominal_drift, copy=True)
    true_controls = np.array(nominal_controls, copy=True)
    if family in ("drift", "combined"):
        true_drift += float(epsilon) * drift_scale * drift_direction
    if family in ("control-map", "combined"):
        true_controls = np.einsum(
            "ij,jab->iab", control_map, nominal_controls
        )
    metadata = {
        "family": family,
        "epsilon": float(epsilon),
        "seed": int(seed),
        "paired_seed_sequence": [113, 11, int(seed)],
        "truth_formula": "phase3-common-v1-extended-to-preregistered-seed",
        "control_map_minus_identity_spectral_norm": float(
            np.linalg.norm(control_map - np.eye(n_controls), ord=2)
        ),
        "relative_drift_frobenius_norm": float(
            np.linalg.norm(true_drift - nominal_drift, ord="fro")
            / drift_scale
        ),
        "true_drift_sha256": hashlib.sha256(
            np.ascontiguousarray(true_drift).view(np.float64).tobytes()
        ).hexdigest(),
        "true_controls_sha256": hashlib.sha256(
            np.ascontiguousarray(true_controls).view(np.float64).tobytes()
        ).hexdigest(),
    }
    return true_drift, true_controls, metadata


def run_one(
    *,
    np: Any,
    jnp: Any,
    attempt44: Any,
    model: Any,
    family: str,
    epsilon: float,
    truth_seed: int,
    replicate: int,
    method: str,
    geometry: tuple[Any, Any],
    common_ridge: float,
    constants: dict[str, Any],
    method_config: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    family_index = FAMILIES.index(family)
    noise_seed = paired_noise_seed(
        np, family_index, truth_seed, replicate
    )
    expected_queries = int(method_config["full_query_cap"])
    expected_shots = int(method_config["full_shot_cap"])
    client = None
    started = time.perf_counter()
    base = {
        "selected_cell": f"{family}:{truth_seed}:{epsilon:g}",
        "family": family,
        "truth_seed": truth_seed,
        "epsilon": epsilon,
        "replicate": replicate,
        "method": method,
        "search_dimension": int(method_config["search_dimension"]),
        "noise_seed": noise_seed,
        "paired_seed_shared_across_methods": True,
        "black_box_boundary": {
            "calibration_interface": (
                "query(parameters, shots) -> sampled scalar fidelity"
            ),
            "truth_derivatives_available_during_calibration": False,
            "posthoc_started_after_client_end": True,
            "posthoc_values_used_in_decisions": False,
        },
    }
    try:
        drift, controls, truth_metadata = make_fresh_truth(
            np, model, family, epsilon, truth_seed, config
        )

        def exact_evaluator(parameters: Any) -> float:
            return float(
                np.asarray(
                    model.average_fidelity(
                        jnp.asarray(parameters),
                        jnp.asarray(drift),
                        jnp.asarray(controls),
                    )
                )
            )

        client = attempt44.LedgerClient(exact_evaluator)
        client.start(noise_seed)
        scan = attempt44.global_calibration(
            client,
            np.asarray(model.optimized_parameters, dtype=np.float64),
            geometry[0],
            geometry[1],
            common_ridge,
            constants,
        )
        if client.active:
            raise AssertionError("client remained active after calibration")
        scan = attempt44.attach_posthoc(scan, exact_evaluator, constants)
        scan = attempt44.compact_full_scan(scan)
        if (
            int(scan["query_cap"]) != expected_queries
            or int(scan["shot_cap"]) != expected_shots
        ):
            raise AssertionError("method cap differs from preregistration")
        record = {
            **base,
            "truth_metadata": truth_metadata,
            "exception": None,
            "charged_full_cap": {
                "queries": expected_queries,
                "shots": expected_shots,
            },
            "elapsed_seconds": time.perf_counter() - started,
            "scan": scan,
        }
        if not finite_tree(record):
            raise FloatingPointError(
                "non-finite value detected in completed run record"
            )
        return record
    except Exception as error:  # retained failure; never retried
        actual = {"query_count": 0, "total_shots": 0}
        if client is not None:
            if client.active:
                actual = client.end()
            else:
                actual = {
                    "query_count": int(client.query_count),
                    "total_shots": int(client.total_shots),
                }
        return {
            **base,
            "truth_metadata": None,
            "exception": {
                "type": type(error).__name__,
                "message": str(error),
                "retained_as_failure": True,
                "replacement_or_retry": False,
            },
            "charged_full_cap": {
                "queries": expected_queries,
                "shots": expected_shots,
            },
            "elapsed_seconds": time.perf_counter() - started,
            "scan": {
                "query_cap": expected_queries,
                "shot_cap": expected_shots,
                "service_query_count_before_exception": int(
                    actual["query_count"]
                ),
                "service_total_shots_before_exception": int(
                    actual["total_shots"]
                ),
                "oracle_scored_success": False,
                "accepted_nonzero_steps": 0,
                "destructive_accepted_steps": 0,
                "posthoc_values_used_in_calibration": False,
                "exception_run": True,
            },
        }


def truth_rows_from_runs(
    np: Any,
    runs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[(run["method"], run["selected_cell"])].append(run)
    output: dict[str, list[dict[str, Any]]] = {method: [] for method in METHODS}
    family_order = {family: index for index, family in enumerate(FAMILIES)}
    for method in METHODS:
        cells = [
            (cell, group)
            for (row_method, cell), group in grouped.items()
            if row_method == method
        ]
        cells.sort(
            key=lambda item: (
                family_order[item[1][0]["family"]],
                int(item[1][0]["truth_seed"]),
            )
        )
        for selected_cell, group in cells:
            successes = [
                0.0
                if run["exception"] is not None
                else float(run["scan"]["oracle_scored_success"])
                for run in group
            ]
            output[method].append(
                {
                    "selected_cell": selected_cell,
                    "family": group[0]["family"],
                    "truth_seed": int(group[0]["truth_seed"]),
                    "nested_replicates": len(group),
                    "oracle_scored_success": float(np.mean(successes)),
                    "accepted_nonzero_steps": int(
                        sum(
                            int(run["scan"]["accepted_nonzero_steps"])
                            for run in group
                        )
                    ),
                    "destructive_accepted_steps": int(
                        sum(
                            int(run["scan"]["destructive_accepted_steps"])
                            for run in group
                        )
                    ),
                    "full_cap_queries": float(
                        np.mean(
                            [
                                int(run["charged_full_cap"]["queries"])
                                for run in group
                            ]
                        )
                    ),
                    "full_cap_shots": float(
                        np.mean(
                            [
                                int(run["charged_full_cap"]["shots"])
                                for run in group
                            ]
                        )
                    ),
                }
            )
    return output


def bootstrap_indices(
    np: Any,
    rows: list[dict[str, Any]],
    *,
    draws: int,
    seed: int,
) -> Any:
    rng = np.random.default_rng(seed)
    output = np.empty((draws, len(rows)), dtype=np.int64)
    offset = 0
    for family in FAMILIES:
        group = np.asarray(
            [
                index
                for index, row in enumerate(rows)
                if row["family"] == family
            ],
            dtype=np.int64,
        )
        if len(group) != 8:
            raise RuntimeError(f"family {family} has {len(group)} truth cells")
        choices = rng.integers(0, len(group), size=(draws, len(group)))
        output[:, offset : offset + len(group)] = group[choices]
        offset += len(group)
    return output


def interval_from_draws(
    np: Any,
    *,
    estimate: float,
    draws: Any,
    independent_cells: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "estimate": float(estimate),
        "lower_95": float(np.quantile(draws, 0.025)),
        "upper_95": float(np.quantile(draws, 0.975)),
        "independent_truth_cells": independent_cells,
        "bootstrap_draws": int(config["bootstrap"]["draws"]),
        "bootstrap_seed": int(config["bootstrap"]["seed"]),
        "family_weighting": "equal-macro-average",
    }


def summarize(
    np: Any,
    runs: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    from scipy.stats import beta

    truth_rows = truth_rows_from_runs(np, runs)
    draws = int(config["bootstrap"]["draws"])
    seed = int(config["bootstrap"]["seed"])
    indices = bootstrap_indices(
        np,
        truth_rows[METHODS[0]],
        draws=draws,
        seed=seed,
    )

    methods: dict[str, Any] = {}
    for method in METHODS:
        rows = truth_rows[method]
        success = np.asarray(
            [row["oracle_scored_success"] for row in rows], dtype=float
        )
        success_draws = np.mean(success[indices], axis=1)
        methods[method] = {
            "truth_level_rows": rows,
            "success": interval_from_draws(
                np,
                estimate=float(np.mean(success)),
                draws=success_draws,
                independent_cells=len(rows),
                config=config,
            ),
            "by_family": {
                family: {
                    "truth_cells": sum(
                        row["family"] == family for row in rows
                    ),
                    "nested_runs": sum(
                        row["nested_replicates"]
                        for row in rows
                        if row["family"] == family
                    ),
                    "success": float(
                        np.mean(
                            [
                                row["oracle_scored_success"]
                                for row in rows
                                if row["family"] == family
                            ]
                        )
                    ),
                }
                for family in FAMILIES
            },
            "full_cap": {
                "queries_per_run": int(rows[0]["full_cap_queries"]),
                "shots_per_run": int(rows[0]["full_cap_shots"]),
            },
        }

    reference_cells = {
        method: {
            row["selected_cell"]: row for row in truth_rows[method]
        }
        for method in METHODS
    }
    paired: dict[str, Any] = {}
    for reference in METHODS[1:]:
        difference = np.asarray(
            [
                reference_cells[METHODS[0]][row["selected_cell"]][
                    "oracle_scored_success"
                ]
                - reference_cells[reference][row["selected_cell"]][
                    "oracle_scored_success"
                ]
                for row in truth_rows[METHODS[0]]
            ],
            dtype=float,
        )
        paired[reference] = interval_from_draws(
            np,
            estimate=float(np.mean(difference)),
            draws=np.mean(difference[indices], axis=1),
            independent_cells=len(difference),
            config=config,
        )

    k15_rows = truth_rows[METHODS[0]]
    accepted = np.asarray(
        [row["accepted_nonzero_steps"] for row in k15_rows], dtype=float
    )
    destructive = np.asarray(
        [row["destructive_accepted_steps"] for row in k15_rows], dtype=float
    )
    accepted_count = int(np.sum(accepted))
    destructive_count = int(np.sum(destructive))
    if accepted_count == 0:
        destructive_estimate = (
            0.0 if destructive_count == 0 else math.inf
        )
        destructive_upper = 1.0
    else:
        destructive_estimate = destructive_count / accepted_count
        destructive_upper = (
            1.0
            if destructive_count == accepted_count
            else float(
                beta.ppf(
                    0.95,
                    destructive_count + 1,
                    accepted_count - destructive_count,
                )
            )
        )
    destructive_interval = {
        "estimate": float(destructive_estimate),
        "lower_95": 0.0,
        "upper_95": float(destructive_upper),
        "confidence": 0.95,
        "interval": "one-sided exact Clopper-Pearson upper bound",
        "event_unit": "accepted nonzero step",
        "accepted_nonzero_steps": accepted_count,
        "destructive_accepted_steps": destructive_count,
        "ratio_definition": (
            "destructive accepted nonzero steps / accepted nonzero steps"
        ),
        "warning": (
            "step events are a safety diagnostic and do not increase the "
            "24-truth-cell sample size used for performance inference"
        ),
    }

    k15_queries = methods[METHODS[0]]["full_cap"]["queries_per_run"]
    k15_shots = methods[METHODS[0]]["full_cap"]["shots_per_run"]
    cost_ratios = {
        reference: {
            "query_ratio": (
                k15_queries
                / methods[reference]["full_cap"]["queries_per_run"]
            ),
            "shot_ratio": (
                k15_shots
                / methods[reference]["full_cap"]["shots_per_run"]
            ),
            "semantics": "deterministic full-cap online; no sampling interval",
        }
        for reference in METHODS[1:]
    }

    grouped_grid: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(
        list
    )
    for run in runs:
        grouped_grid[(run["selected_cell"], int(run["replicate"]))].append(run)

    def ledger_closes(run: dict[str, Any]) -> bool:
        if run["exception"] is not None:
            return False
        scan = run["scan"]
        closure = scan["query_ledger_closure"]
        return (
            int(scan["service_query_count"])
            == int(closure["row_count"])
            == int(scan["query_cap"])
            == int(run["charged_full_cap"]["queries"])
            and int(scan["service_total_shots"])
            == int(closure["total_shots"])
            == int(scan["shot_cap"])
            == int(run["charged_full_cap"]["shots"])
        )

    expected_cells = {
        f"{family}:{truth_seed}:{float(config['benchmark']['fixed_epsilon_by_family'][family]):g}"
        for family in FAMILIES
        for truth_seed in config["benchmark"]["fresh_truth_seeds"]
    }
    checks = {
        "expected_288_runs": len(runs) == 288,
        "exact_24_truth_cells_retained": (
            {run["selected_cell"] for run in runs} == expected_cells
        ),
        "all_methods_present_per_cell_replicate": (
            len(grouped_grid) == 96
            and all(
                Counter(run["method"] for run in group)
                == Counter({method: 1 for method in METHODS})
                for group in grouped_grid.values()
            )
        ),
        "paired_noise_seed_shared_across_methods": all(
            len({int(run["noise_seed"]) for run in group}) == 1
            for group in grouped_grid.values()
        ),
        "noise_seed_formula_exact": all(
            int(run["noise_seed"])
            == paired_noise_seed(
                np,
                FAMILIES.index(run["family"]),
                int(run["truth_seed"]),
                int(run["replicate"]),
            )
            for run in runs
        ),
        "all_runs_exception_free": all(
            run["exception"] is None for run in runs
        ),
        "all_ledgers_close": all(ledger_closes(run) for run in runs),
        "posthoc_separated": all(
            run["black_box_boundary"]["posthoc_started_after_client_end"]
            and not run["black_box_boundary"][
                "posthoc_values_used_in_decisions"
            ]
            and not run["scan"]["posthoc_values_used_in_calibration"]
            for run in runs
        ),
        "all_numeric_values_finite": finite_tree(runs),
        "fresh_truth_seed_firewall": all(
            260_641 <= int(run["truth_seed"]) <= 260_648 for run in runs
        ),
        "all_nested_replicates_present": all(
            {int(run["replicate"]) for run in runs if run["selected_cell"] == cell}
            == {0, 1, 2, 3}
            for cell in expected_cells
        ),
    }
    gate_config = config["gates"]
    gate_checks = {
        "k15_success_lcb95_at_least_0_75": (
            methods[METHODS[0]]["success"]["lower_95"]
            >= float(gate_config["pooled_k15_success_lcb95_min"])
        ),
        "k15_minus_k40_lcb95_above_minus_0_10": (
            paired[METHODS[1]]["lower_95"]
            > float(
                gate_config[
                    "success_difference_k15_minus_k40_lcb95_min_exclusive"
                ]
            )
        ),
        "k15_minus_raw40_lcb95_above_zero": (
            paired[METHODS[2]]["lower_95"]
            > float(
                gate_config[
                    "success_difference_k15_minus_raw40_lcb95_min_exclusive"
                ]
            )
        ),
        "full_cap_query_ratios_below_0_60": all(
            row["query_ratio"]
            < float(gate_config["full_cap_cost_ratio_max_exclusive"])
            for row in cost_ratios.values()
        ),
        "full_cap_shot_ratios_below_0_60": all(
            row["shot_ratio"]
            < float(gate_config["full_cap_cost_ratio_max_exclusive"])
            for row in cost_ratios.values()
        ),
        "destructive_rate_ucb95_at_most_0_05": (
            destructive_interval["upper_95"]
            <= float(
                gate_config["destructive_accepted_step_rate_ucb95_max"]
            )
        ),
    }
    return (
        {
            "success_scoring": (
                "hidden exact post-hoc accepted-incumbent target event"
            ),
            "cost_semantics": "deterministic full-cap online",
            "methods": methods,
            "paired_success_differences": paired,
            "k15_destructive_accepted_step_rate": destructive_interval,
            "cost_ratios": cost_ratios,
            "gate_checks": gate_checks,
            "confirmation_pass": (
                all(checks.values()) and all(gate_checks.values())
            ),
        },
        checks,
    )


def make_plot(
    np: Any,
    summary: dict[str, Any],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ["model k=15", "completed k=40", "raw k=40"]
    estimates = [
        summary["methods"][method]["success"]["estimate"] for method in METHODS
    ]
    lower = [
        estimate - summary["methods"][method]["success"]["lower_95"]
        for estimate, method in zip(estimates, METHODS, strict=True)
    ]
    upper = [
        summary["methods"][method]["success"]["upper_95"] - estimate
        for estimate, method in zip(estimates, METHODS, strict=True)
    ]
    query_ratios = [
        1.0,
        summary["methods"][METHODS[1]]["full_cap"]["queries_per_run"]
        / summary["methods"][METHODS[1]]["full_cap"]["queries_per_run"],
        summary["methods"][METHODS[2]]["full_cap"]["queries_per_run"]
        / summary["methods"][METHODS[2]]["full_cap"]["queries_per_run"],
    ]
    query_ratios[0] = summary["cost_ratios"][METHODS[1]]["query_ratio"]
    shot_ratios = [
        summary["cost_ratios"][METHODS[1]]["shot_ratio"],
        1.0,
        1.0,
    ]
    x = np.arange(len(METHODS))
    colors = ("#00796B", "#607D8B", "#B45F06")
    figure, axes = plt.subplots(1, 2, figsize=(11.4, 4.7))
    axes[0].bar(x, estimates, color=colors, alpha=0.9)
    axes[0].errorbar(
        x,
        estimates,
        yerr=np.asarray([lower, upper]),
        fmt="none",
        color="black",
        capsize=4,
        linewidth=1.2,
    )
    axes[0].axhline(0.75, color="#A51C30", linestyle="--", linewidth=1)
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Oracle-scored target success")
    axes[0].set_title("Fresh truth-cell success (95% bootstrap CI)")
    axes[0].set_xticks(x, labels, rotation=12, ha="right")
    axes[0].grid(axis="y", alpha=0.22)

    width = 0.36
    axes[1].bar(
        x - width / 2,
        query_ratios,
        width,
        label="query cap ratio",
        color="#3366AA",
    )
    axes[1].bar(
        x + width / 2,
        shot_ratios,
        width,
        label="shot cap ratio",
        color="#AA4499",
    )
    axes[1].axhline(0.60, color="#A51C30", linestyle="--", linewidth=1)
    axes[1].set_ylim(0.0, 1.12)
    axes[1].set_ylabel("Ratio to corresponding k=40 full cap")
    axes[1].set_title("Deterministic full-cap online resources")
    axes[1].set_xticks(x, labels, rotation=12, ha="right")
    axes[1].legend(frameon=False)
    axes[1].grid(axis="y", alpha=0.22)
    figure.suptitle(
        "Attempt 49 fresh confirmation — synthetic CNOT, not hardware",
        fontsize=12,
    )
    figure.tight_layout()
    PLOT_PNG.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(PLOT_PNG, dpi=180, bbox_inches="tight")
    figure.savefig(PLOT_SVG, bbox_inches="tight")
    plt.close(figure)


def percent(interval: dict[str, Any]) -> str:
    return (
        f"{100 * interval['estimate']:.2f}% "
        f"[{100 * interval['lower_95']:.2f}, "
        f"{100 * interval['upper_95']:.2f}]"
    )


def write_report(result: dict[str, Any]) -> None:
    summary = result["summary"]
    rows = []
    for method in METHODS:
        record = summary["methods"][method]
        rows.append(
            "| "
            + " | ".join(
                [
                    method,
                    percent(record["success"]),
                    str(record["full_cap"]["queries_per_run"]),
                    str(record["full_cap"]["shots_per_run"]),
                ]
            )
            + " |"
        )
    paired = summary["paired_success_differences"]
    decision = (
        "PASS" if summary["confirmation_pass"] else "FAIL"
    )
    report = f"""# Attempt 49 — fresh confirmation

Date: 2026-07-29

Decision: **{decision}**

This one-shot confirmation uses 24 previously unopened synthetic CNOT truth
cells, four nested finite-shot replicates, and three frozen methods. Hidden
exact fidelity is used only after each black-box client closes. It is not an
online target certificate and it is not hardware evidence.

## Result

| Method | Oracle-scored success (95% truth-cell CI) | Full queries/run | Full shots/run |
|---|---:|---:|---:|
{chr(10).join(rows)}

Paired `k=15 - completed k=40` success:
{percent(paired[METHODS[1]])}.

Paired `k=15 - raw k=40` success:
{percent(paired[METHODS[2]])}.

The `k=15` full-cap query ratio is
{summary["cost_ratios"][METHODS[1]]["query_ratio"]:.6f}; its shot ratio is
{summary["cost_ratios"][METHODS[1]]["shot_ratio"]:.6f}. These are
deterministic two-cycle protocol caps, not empirically observed online
queries-to-target.

The `k=15` destructive accepted-step rate is
{percent(summary["k15_destructive_accepted_step_rate"])}.

## Frozen gate

```json
{json.dumps(summary["gate_checks"], indent=2, sort_keys=True)}
```

All integrity checks:

```json
{json.dumps(result["checks"], indent=2, sort_keys=True)}
```

## Claim boundary

- Fresh confirmation is limited to the fixed 24-cell synthetic CNOT benchmark.
- The tested grid, not all possible dimensions, selected `k=15`.
- The resource claim is a 60.24% query-cap and 60.95% shot-cap reduction
  relative to the frozen `k=40` two-cycle protocols.
- Oracle-scored first hit is post-hoc and supplementary.
- No cesium-specific, neutral-atom-platform, or real-hardware generalization
  follows from this confirmation.

## Artifacts

- Protocol: `ATTEMPT49_PROTOCOL.md`
- Runner: `../code/attempt49_fresh_confirmation.py`
- Config: `../code/attempt49_fresh_confirmation_config.json`
- Preregistration manifest:
  `../code/attempt49_preregistration_manifest.json`
- Machine result:
  `../results_summary/QL1F-attempt49-fresh-confirmation.json`
- Figure: `../plots/attempt49-fresh-confirmation.{{png,svg}}`
"""
    atomic_write_text(REPORT_PATH, report)


def run_confirmation() -> None:
    if OUTPUT_PATH.exists() and not PARTIAL_PATH.exists():
        raise RuntimeError(
            "final Attempt-49 result already exists; one-shot rerun refused"
        )
    preregistration = validate_preregistration(
        require_public_commit=True,
        allow_runtime_outputs=True,
    )
    if preregistration["status"] != "pass":
        raise RuntimeError(
            "preregistration validation failed:\n"
            + json.dumps(preregistration, indent=2, sort_keys=True)
        )

    # Simulator and numerical imports are intentionally deferred until here.
    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    import jax
    import jax.numpy as jnp
    import numpy as np

    sys.path.insert(0, str(HERE))
    import attempt44_dimension_cost as attempt44
    from phase3_common import (
        TRUTH_FAMILIES,
        build_nominal_model,
        environment_summary,
    )

    config = load_json(CONFIG_PATH)
    if tuple(TRUTH_FAMILIES) != FAMILIES:
        raise RuntimeError("phase3 truth-family order changed")
    environment = {
        **environment_summary(),
        "devices": [str(device) for device in jax.devices()],
        "platform_request": os.environ["JAX_PLATFORMS"],
    }
    if environment["backend"] != "cpu" or environment["x64"] is not True:
        raise RuntimeError(f"frozen CPU/x64 environment required: {environment}")

    model = build_nominal_model()
    geometries, basis_audit, common_ridge = (
        attempt44.build_search_geometries(model, config)
    )
    constants = attempt44.frozen_constants(config)
    method_config = {row["name"]: row for row in config["methods"]}
    cells = [
        {
            "family": family,
            "epsilon": float(
                config["benchmark"]["fixed_epsilon_by_family"][family]
            ),
            "truth_seed": int(truth_seed),
        }
        for family in FAMILIES
        for truth_seed in config["benchmark"]["fresh_truth_seeds"]
    ]

    runs = load_checkpoint(preregistration, np, config)
    identities = {
        (
            run["selected_cell"],
            int(run["replicate"]),
            run["method"],
        )
        for run in runs
    }
    if len(identities) != len(runs):
        raise RuntimeError("partial checkpoint contains duplicate runs")

    expected_total = len(cells) * 4 * len(METHODS)
    started = time.perf_counter()
    for cell in cells:
        selected_cell = (
            f"{cell['family']}:{cell['truth_seed']}:{cell['epsilon']:g}"
        )
        for replicate in range(4):
            for method in METHODS:
                identity = (selected_cell, replicate, method)
                if identity in identities:
                    continue
                run = run_one(
                    np=np,
                    jnp=jnp,
                    attempt44=attempt44,
                    model=model,
                    family=cell["family"],
                    epsilon=cell["epsilon"],
                    truth_seed=cell["truth_seed"],
                    replicate=replicate,
                    method=method,
                    geometry=geometries[method],
                    common_ridge=common_ridge,
                    constants=constants,
                    method_config=method_config[method],
                    config=config,
                )
                runs.append(run)
                identities.add(identity)
                write_checkpoint(
                    preregistration=preregistration,
                    runs=runs,
                )
                print(
                    f"[attempt49] {len(runs)}/{expected_total} "
                    f"{selected_cell} rep={replicate} method={method} "
                    f"success={run['scan']['oracle_scored_success']} "
                    f"exception={run['exception'] is not None}",
                    flush=True,
                )

    final_validation = validate_preregistration(
        require_public_commit=True,
        allow_runtime_outputs=True,
    )
    if (
        final_validation["status"] != "pass"
        or final_validation["git"]["head"] != preregistration["git"]["head"]
        or final_validation["manifest_canonical_sha256"]
        != preregistration["manifest_canonical_sha256"]
    ):
        raise RuntimeError(
            "post-run source/commit validation failed; result remains partial"
        )

    summary, checks = summarize(np, runs, config)
    checks.update(
        {
            "preregistration_validation_passed_before_truth": (
                preregistration["status"] == "pass"
            ),
            "source_manifest_seals_all_match": all(
                value
                for key, value in preregistration["checks"].items()
                if key.startswith("sealed:")
            ),
            "audited_checkpoint_is_ancestor": preregistration["checks"][
                "audited_checkpoint_is_ancestor"
            ],
            "preregistration_commit_public": preregistration["checks"][
                "current_commit_is_public_on_origin_main"
            ],
            "postrun_source_and_commit_revalidation_passed": (
                final_validation["status"] == "pass"
                and final_validation["git"]["head"]
                == preregistration["git"]["head"]
                and final_validation["manifest_canonical_sha256"]
                == preregistration["manifest_canonical_sha256"]
            ),
        }
    )
    summary["confirmation_pass"] = (
        all(checks.values()) and all(summary["gate_checks"].values())
    )
    result = {
        "schema": "QL1F-attempt49-fresh-confirmation-v1",
        "attempt": 49,
        "status": "complete",
        "evidence_status": "fresh-confirmation",
        "confirmation_decision": (
            "pass" if summary["confirmation_pass"] else "fail"
        ),
        "claim_boundary": {
            "synthetic_cnot": True,
            "real_hardware": False,
            "cesium_specific": False,
            "online_target_certificate": False,
            "cost_semantics": "deterministic-full-cap-online",
            "dimension_claim": (
                "smallest passing tested development-grid dimension, "
                "freshly evaluated without changing k"
            ),
        },
        "preregistration": {
            "before_truth": preregistration,
            "after_runs": final_validation,
        },
        "config": config,
        "environment": environment,
        "basis_audit": basis_audit,
        "common_ridge": common_ridge,
        "runs": runs,
        "summary": summary,
        "checks": checks,
        "elapsed_seconds_this_process": time.perf_counter() - started,
        "source_hashes": {
            path: canonical_sha256(resolve_manifest_path(path))
            for path in load_json(MANIFEST_PATH)["sealed_files"]
        },
    }
    make_plot(np, summary)
    write_report(result)
    result["artifacts"] = {
        "report": {
            "path": REPORT_PATH.relative_to(CORE).as_posix(),
            "canonical_sha256": canonical_sha256(REPORT_PATH),
        },
        "plot_png": {
            "path": PLOT_PNG.relative_to(CORE).as_posix(),
            "binary_sha256": binary_sha256(PLOT_PNG),
        },
        "plot_svg": {
            "path": PLOT_SVG.relative_to(CORE).as_posix(),
            "canonical_sha256": canonical_sha256(PLOT_SVG),
        },
    }
    atomic_write_json(OUTPUT_PATH, result)
    PARTIAL_PATH.unlink()
    print(
        f"attempt49 complete; decision={result['confirmation_decision']}; "
        f"runs={len(runs)}",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--validate-preregistration",
        action="store_true",
        help="validate committed sources without importing the simulator",
    )
    modes.add_argument(
        "--run",
        action="store_true",
        help="open frozen fresh truths and run the one-shot confirmation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.run:
        run_confirmation()
        return
    validation = validate_preregistration(
        require_public_commit=True,
        allow_runtime_outputs=False,
    )
    print(json.dumps(validation, indent=2, sort_keys=True))
    if validation["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
