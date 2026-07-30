#!/usr/bin/env python3
"""Canonical reproduction entry point for Challenge 113.

``--mwe`` runs one development truth cell with the frozen k=15, completed
k=40, and raw-coordinate k=40 methods.  It retains every finite-shot query
ledger row and is intended as the fast end-to-end demonstration.

``--full`` replays the public Attempt-49 benchmark
(24 truth cells x 4 nested replicates x 3 methods = 288 runs) into a new
directory.  Because the truths and result are already public, this is a
reproduction replay, never a second independent fresh confirmation.  Both
modes independently audit the immutable Attempt-49 result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
CODE = HERE / "code"
RESULTS = HERE / "results_summary"
RUN_OUTPUTS = HERE / "run_outputs"

MWE_METHODS = (
    "model-informed-k15",
    "model-informed-k40",
    "raw-coordinate-global-40",
)
TARGET_INFIDELITY = 1e-3


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


def git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


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


def prepare_output(mode: str, requested: Path | None) -> Path:
    if requested is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = RUN_OUTPUTS / f"{mode}-{timestamp}"
    else:
        output = requested.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError(
            f"output directory must be empty: {output}"
        )
    return output


def ledger_closes(run: dict[str, Any]) -> bool:
    scan = run["scan"]
    expected_queries = 4 * int(run["search_dimension"]) + 6
    expected_shots = (
        (4 * int(run["search_dimension"]) + 4) * 32768 + 2 * 1024
    )
    if "query_ledger" in scan:
        ledger = scan["query_ledger"]
        return (
            len(ledger)
            == int(scan["service_query_count"])
            == int(scan["query_cap"])
            == expected_queries
            and sum(int(row["shots"]) for row in ledger)
            == int(scan["service_total_shots"])
            == int(scan["shot_cap"])
            == expected_shots
        )
    closure = scan["query_ledger_closure"]
    return (
        int(closure["row_count"])
        == int(scan["service_query_count"])
        == int(scan["query_cap"])
        == expected_queries
        and int(closure["total_shots"])
        == int(scan["service_total_shots"])
        == int(scan["shot_cap"])
        == expected_shots
    )


def make_mwe_plot(
    plt: Any,
    np: Any,
    runs: list[dict[str, Any]],
    output: Path,
) -> None:
    labels = ["model k=15", "completed k=40", "raw k=40"]
    final_infidelity = [
        float(run["scan"]["final_infidelity"]) for run in runs
    ]
    query_caps = [int(run["scan"]["query_cap"]) for run in runs]
    x = np.arange(len(runs))
    colors = ("#00796B", "#607D8B", "#B45F06")
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4))
    axes[0].bar(x, final_infidelity, color=colors)
    axes[0].axhline(
        TARGET_INFIDELITY,
        color="#A51C30",
        linestyle="--",
        linewidth=1.2,
        label="target 1e-3",
    )
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Post-hoc exact final infidelity")
    axes[0].set_xticks(x, labels, rotation=12, ha="right")
    axes[0].set_title("One-cell end-to-end MWE")
    axes[0].legend(frameon=False)
    axes[0].grid(axis="y", alpha=0.22)
    axes[1].bar(x, query_caps, color=colors)
    axes[1].set_ylabel("Deterministic full query cap")
    axes[1].set_xticks(x, labels, rotation=12, ha="right")
    axes[1].set_title("Finite-shot black-box cost")
    axes[1].grid(axis="y", alpha=0.22)
    figure.suptitle(
        "Challenge 113 MWE — development truth, not confirmation evidence"
    )
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def make_full_plot(
    plt: Any,
    np: Any,
    summary: dict[str, Any],
    output: Path,
) -> None:
    methods = MWE_METHODS
    labels = ["model k=15", "completed k=40", "raw k=40"]
    success = [
        float(summary["methods"][method]["success"]["estimate"])
        for method in methods
    ]
    query_caps = [
        float(summary["methods"][method]["full_cap"]["queries_per_run"])
        for method in methods
    ]
    x = np.arange(len(methods))
    colors = ["#00796B", "#607D8B", "#B45F06"]
    figure, axes = plt.subplots(1, 2, figsize=(11.8, 4.6))
    axes[0].bar(x, success, color=colors)
    axes[0].axhline(
        0.75, color="#A51C30", linestyle="--", linewidth=1.2
    )
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Oracle-scored success")
    axes[0].set_xticks(x, labels, rotation=15, ha="right")
    axes[0].set_title("Public truth-cell replay")
    axes[0].grid(axis="y", alpha=0.22)
    axes[1].bar(x, query_caps, color=colors)
    axes[1].set_ylabel("Deterministic full query cap")
    axes[1].set_xticks(x, labels, rotation=15, ha="right")
    axes[1].set_title("Frozen online resource cap")
    axes[1].grid(axis="y", alpha=0.22)
    figure.suptitle(
        "Challenge 113 full replay — not a new independent confirmation"
    )
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def make_run_document(
    *,
    mode: str,
    output: Path,
    started: float,
    environment: dict[str, Any],
    runs: list[dict[str, Any]],
    metrics: dict[str, Any],
    checks: dict[str, bool],
    confirmation_audit: dict[str, Any],
    source_hashes: dict[str, str],
    plot_name: str,
) -> dict[str, Any]:
    elapsed = time.perf_counter() - started
    status = "complete" if all(checks.values()) else "failed-checks"
    figure_numbers = metrics["figure_numbers"]
    return {
        "schema": "quantum-harness-challenge-run-v1",
        "challenge": {
            "number": 113,
            "title": "Sim-to-Real for Quantum Gates",
            "track": "other",
            "issue_url": (
                "https://github.com/QuantumBFS/quantum.harness/issues/113"
            ),
        },
        "title": (
            "Model-informed low-dimensional black-box calibration "
            "for a synthetic CNOT"
        ),
        "scope": (
            "fast development-truth demonstration"
            if mode == "mwe"
            else (
                "public Attempt-49 benchmark replay; not an independent "
                "fresh confirmation"
            )
        ),
        "mode": mode,
        "status": status,
        "source_commit": git_head(),
        "environment": environment,
        "model": {
            "system": "synthetic two-qubit CNOT",
            "hilbert_dimension": 4,
            "pulse_parameters": 40,
            "nominal_hessian_rank": 15,
            "truth_access": "query-only scalar finite-shot fidelity",
        },
        "method": {
            "name": "model-informed principal-global calibration",
            "exact": False,
            "tool": "JAX autodiff model + finite-shot scalar oracle",
            "settings": (
                "two global cycles; central differences; 32768 shots/query; "
                "trust radius 0.25; frozen k=15"
            ),
            "note": (
                "The differentiable nominal simulator supplies a warm start "
                "and Hessian principal directions. Calibration of the "
                "mismatched device is derivative-free and receives only "
                "sampled scalar fidelities. Exact truth values are attached "
                "only after the client closes."
            ),
        },
        "estimate": [
            {
                "run_point": mode,
                "wall_time_seconds": elapsed,
                "memory": "CPU-only; not profiled",
            }
        ],
        "figures": [
            {
                "id": "headline",
                "plots": [
                    {
                        "src": plot_name,
                        "description": (
                            "MWE final infidelity and full query caps"
                            if mode == "mwe"
                            else (
                                "development success and full query caps "
                                "versus search dimension"
                            )
                        ),
                    }
                ],
                "results": {
                    "figure": plot_name,
                    "match": "pass" if status == "complete" else "fail",
                    "why": (
                        "All reproduction, ledger, environment, and immutable "
                        "confirmation-audit checks passed."
                        if status == "complete"
                        else "At least one frozen reproduction check failed."
                    ),
                    "numbers": figure_numbers,
                },
            }
        ],
        "results": {
            "checks": checks,
            "metrics_file": "metrics.json",
            "run_count": len(runs),
            "confirmation_audit": {
                "status": confirmation_audit["status"],
                "decision": confirmation_audit["decision"],
                "formal_attempt49_result": (
                    "../results_summary/"
                    "QL1F-attempt49-fresh-confirmation.json"
                ),
            },
        },
        "runs": runs,
        "artifacts": {
            "plot": {
                "path": plot_name,
                "binary_sha256": binary_sha256(output / plot_name),
            },
            "metrics": {
                "path": "metrics.json",
                "canonical_sha256": canonical_sha256(
                    output / "metrics.json"
                ),
            },
        },
        "source_hashes": source_hashes,
        "claim_boundary": {
            "development_reproduction": mode == "mwe",
            "public_confirmation_benchmark_replay": mode == "full",
            "independent_fresh_confirmation": False,
            "formal_confirmation_is_immutable_attempt49": True,
            "real_hardware": False,
            "cesium_specific": False,
            "online_target_certificate": False,
        },
        "elapsed_seconds": elapsed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--mwe", action="store_true")
    modes.add_argument("--full", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "empty output directory; defaults to an ignored timestamped "
            "directory under core-sim-to-real/run_outputs"
        ),
    )
    args = parser.parse_args()
    mode = "mwe" if args.mwe else "full"
    output = prepare_output(mode, args.output)

    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    os.environ.setdefault("JAX_ENABLE_X64", "True")
    sys.path.insert(0, str(CODE))

    import jax
    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    import attempt44_dimension_cost as attempt44
    import attempt49_fresh_confirmation as attempt49
    import attempt50_result_audit as attempt50_audit

    started = time.perf_counter()
    model = attempt44.build_nominal_model()
    environment = {
        **attempt44.environment_summary(),
        "devices": [str(device) for device in jax.devices()],
        "platform_request": os.environ["JAX_PLATFORMS"],
    }
    if environment["backend"] != "cpu" or environment["x64"] is not True:
        raise RuntimeError(
            f"CPU/x64 environment required, received {environment}"
        )

    if mode == "mwe":
        config, attempt35, _attempt42, _attempt43 = attempt44.load_inputs()
        constants = attempt44.frozen_constants(config)
        geometries, basis_audit, common_ridge = (
            attempt44.build_search_geometries(model, config)
        )
        selected_cells = attempt35["selected_cells"]
        grid = [(0, 0, method) for method in MWE_METHODS]
    else:
        config = json.loads(
            (
                CODE / "attempt49_fresh_confirmation_config.json"
            ).read_text(encoding="utf-8")
        )
        constants = attempt44.frozen_constants(config)
        geometries, basis_audit, common_ridge = (
            attempt44.build_search_geometries(model, config)
        )
        method_config = {row["name"]: row for row in config["methods"]}
        grid = [
            (
                family,
                float(
                    config["benchmark"]["fixed_epsilon_by_family"][family]
                ),
                int(truth_seed),
                replicate,
                method,
            )
            for family in attempt49.FAMILIES
            for truth_seed in config["benchmark"]["fresh_truth_seeds"]
            for replicate in range(4)
            for method in attempt49.METHODS
        ]

    print(
        f"[challenge113] mode={mode} runs={len(grid)} output={output}",
        flush=True,
    )
    runs: list[dict[str, Any]] = []
    if mode == "mwe":
        for position, (selected_index, replicate, method) in enumerate(
            grid, start=1
        ):
            run = attempt44.run_one(
                selected_cells[selected_index],
                selected_index,
                replicate,
                method,
                model,
                geometries[method],
                common_ridge,
                constants,
                compact=False,
            )
            runs.append(run)
            print(
                f"[challenge113] {position}/{len(grid)} "
                f"{run['selected_cell']} rep={replicate} method={method} "
                f"success={run['scan']['oracle_scored_success']}",
                flush=True,
            )
    else:
        for position, (
            family,
            epsilon,
            truth_seed,
            replicate,
            method,
        ) in enumerate(grid, start=1):
            run = attempt49.run_one(
                np=np,
                jnp=attempt44.jnp,
                attempt44=attempt44,
                model=model,
                family=family,
                epsilon=epsilon,
                truth_seed=truth_seed,
                replicate=replicate,
                method=method,
                geometry=geometries[method],
                common_ridge=common_ridge,
                constants=constants,
                method_config=method_config[method],
                config=config,
            )
            runs.append(run)
            print(
                f"[challenge113] {position}/{len(grid)} "
                f"{run['selected_cell']} rep={replicate} method={method} "
                f"success={run['scan']['oracle_scored_success']} "
                f"exception={run['exception'] is not None}",
                flush=True,
            )

    confirmation_audit = attempt50_audit.audit()
    if mode == "mwe":
        checks = {
            "exact_three_method_grid": (
                len(runs) == 3
                and tuple(run["method"] for run in runs) == MWE_METHODS
            ),
            "complete_query_ledgers_retained": all(
                "query_ledger" in run["scan"]
                and "query_ledger_closure" not in run["scan"]
                for run in runs
            ),
            "all_ledgers_close": all(ledger_closes(run) for run in runs),
            "all_runs_finite": finite_tree(runs),
            "posthoc_boundary_closed": all(
                run["black_box_boundary"][
                    "posthoc_started_after_client_end"
                ]
                and not run["black_box_boundary"][
                    "posthoc_values_used_in_decisions"
                ]
                and not run["scan"]["posthoc_values_used_in_calibration"]
                for run in runs
            ),
            "paired_noise_seed_shared": (
                len({int(run["noise_seed"]) for run in runs}) == 1
            ),
            "confirmation_static_audit_pass": (
                confirmation_audit["status"] == "pass"
            ),
        }
        metrics = {
            "schema": "challenge113-mwe-metrics-v1",
            "scope": "single development truth; not statistical evidence",
            "selected_cell": runs[0]["selected_cell"],
            "methods": {
                run["method"]: {
                    "oracle_scored_success": bool(
                        run["scan"]["oracle_scored_success"]
                    ),
                    "final_infidelity": float(
                        run["scan"]["final_infidelity"]
                    ),
                    "full_query_cap": int(run["scan"]["query_cap"]),
                    "full_shot_cap": int(run["scan"]["shot_cap"]),
                    "query_ledger_rows_retained": len(
                        run["scan"]["query_ledger"]
                    ),
                    "query_ledger_canonical_sha256": (
                        canonical_json_sha256(run["scan"]["query_ledger"])
                    ),
                }
                for run in runs
            },
            "figure_numbers": [
                [
                    run["method"],
                    f"{run['scan']['final_infidelity']:.6g}",
                    str(run["scan"]["query_cap"]),
                ]
                for run in runs
            ],
            "figure_columns": [
                "Method",
                "Final infidelity",
                "Full query cap",
            ],
        }
        plot_name = "mwe.png"
        make_mwe_plot(plt, np, runs, output / plot_name)
    else:
        summary, checks = attempt49.summarize(np, runs, config)
        archived = json.loads(
            (
                RESULTS / "QL1F-attempt49-fresh-confirmation.json"
            ).read_text(encoding="utf-8")
        )
        checks.update(
            {
                "archived_attempt49_summary_exactly_reproduced": (
                    canonical_json_sha256(summary)
                    == canonical_json_sha256(archived["summary"])
                ),
                "all_runs_finite": finite_tree(runs),
                "replay_is_labeled_non_independent": True,
                "confirmation_static_audit_pass": (
                    confirmation_audit["status"] == "pass"
                ),
            }
        )
        metrics = {
            "schema": "challenge113-full-public-replay-metrics-v1",
            "scope": (
                "Public Attempt-49 benchmark replay; this is reproducibility "
                "evidence, not a second independent fresh confirmation"
            ),
            "summary": summary,
            "figure_numbers": [
                [
                    method,
                    f"{summary['methods'][method]['success']['estimate']:.4f}",
                    str(
                        summary["methods"][method]["full_cap"][
                            "queries_per_run"
                        ]
                    ),
                ]
                for method in attempt49.METHODS
            ],
            "figure_columns": [
                "Method",
                "Replay success",
                "Full query cap",
            ],
        }
        plot_name = "full-replay.png"
        make_full_plot(plt, np, summary, output / plot_name)

    atomic_write_json(output / "metrics.json", metrics)
    source_paths = {
        "run_challenge.py": Path(__file__).resolve(),
        "code/attempt44_dimension_cost.py": (
            CODE / "attempt44_dimension_cost.py"
        ),
        "code/attempt44_dimension_cost_config.json": (
            CODE / "attempt44_dimension_cost_config.json"
        ),
        "code/attempt49_fresh_confirmation.py": (
            CODE / "attempt49_fresh_confirmation.py"
        ),
        "code/attempt49_fresh_confirmation_config.json": (
            CODE / "attempt49_fresh_confirmation_config.json"
        ),
        "code/attempt50_result_audit.py": (
            CODE / "attempt50_result_audit.py"
        ),
    }
    source_hashes = {
        relative: canonical_sha256(path)
        for relative, path in source_paths.items()
    }
    run_document = make_run_document(
        mode=mode,
        output=output,
        started=started,
        environment=environment,
        runs=runs,
        metrics=metrics,
        checks=checks,
        confirmation_audit=confirmation_audit,
        source_hashes=source_hashes,
        plot_name=plot_name,
    )
    atomic_write_json(output / "run.json", run_document)
    print(
        f"[challenge113] {run_document['status']}; "
        f"checks={sum(checks.values())}/{len(checks)}; "
        f"run={output / 'run.json'}",
        flush=True,
    )
    if run_document["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
