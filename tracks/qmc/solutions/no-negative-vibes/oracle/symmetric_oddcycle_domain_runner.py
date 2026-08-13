"""Batch runner for parameter-scan oddcycle discovery cells."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .symmetric_oddcycle_discovery import screen_oddcycle_parameters


ScreenFunction = Callable[..., dict[str, object]]
MetricFunction = Callable[..., dict[str, object]]
_SCREEN_SETTING_KEYS = (
    "short_depth",
    "determinant_tolerance",
    "entry_tolerance",
    "ratio_tolerance",
    "tail_start",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            _json_safe(payload),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _finish(
    manifest: dict[str, object],
    started: float,
    *,
    classification: str,
    compute_success: bool,
) -> dict[str, object]:
    manifest["classification"] = classification
    manifest["compute_success"] = compute_success
    manifest["elapsed_seconds"] = time.perf_counter() - started
    return manifest


def run_cell(
    cell_id: str,
    params: Mapping[str, object],
    settings: Mapping[str, object],
    provenance: Mapping[str, object],
    *,
    screen_fn: ScreenFunction = screen_oddcycle_parameters,
    common_metric_fn: MetricFunction | None = None,
) -> dict[str, object]:
    """Run one cell and classify scientific failures separately from errors."""

    started = time.perf_counter()
    manifest: dict[str, object] = {
        "cell_id": str(cell_id),
        "params": dict(params),
        "settings": dict(settings),
        "provenance": dict(provenance),
        "screen": None,
        "log_gate": {"status": "not-evaluated"},
        "common_metric": {"status": "not-run", "reason": "not-evaluated"},
    }
    try:
        p = float(params["p"])
        q = float(params["q"])
        r = float(params["r"])
        screen_options = {
            key: settings[key]
            for key in _SCREEN_SETTING_KEYS
            if key in settings
        }
        screen = screen_fn(p, q, r, **screen_options)
        manifest["screen"] = screen
    except Exception as error:
        manifest["screen"] = {
            "status": "compute-error",
            "error_type": type(error).__name__,
            "error": str(error),
        }
        manifest["common_metric"] = {
            "status": "not-run",
            "reason": "screen-error",
        }
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
        )

    if screen.get("status") != "passed-all-gates":
        manifest["common_metric"] = {
            "status": "not-run",
            "reason": "exterior-failed",
        }
        return _finish(
            manifest,
            started,
            classification="exterior-failed",
            compute_success=True,
        )

    product = p * q * r
    log_gate_passed = product < 8.0
    manifest["log_gate"] = {
        "status": "passed" if log_gate_passed else "failed",
        "p_q_r": product,
        "required_strict_upper_bound": 8.0,
    }
    if not log_gate_passed:
        manifest["common_metric"] = {
            "status": "not-run",
            "reason": "p*q*r is not strictly below 8",
        }
        return _finish(
            manifest,
            started,
            classification="log-gate-failed",
            compute_success=True,
        )

    try:
        metric = common_metric_fn
        if metric is None:
            from .oddcycle_contraction_sdp import common_metric_sdp

            metric = common_metric_sdp
        metric_options: dict[str, object] = {}
        if "sdp_solver" in settings:
            metric_options["solver"] = settings["sdp_solver"]
        if "sdp_validation_tolerance" in settings:
            metric_options["validation_tolerance"] = settings[
                "sdp_validation_tolerance"
            ]
        if "sdp_solver_options" in settings:
            metric_options["solver_options"] = settings["sdp_solver_options"]
        common_metric = metric(p, q, r, **metric_options)
        manifest["common_metric"] = common_metric
    except Exception as error:
        manifest["common_metric"] = {
            "status": "compute-error",
            "error_type": type(error).__name__,
            "error": str(error),
        }
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
        )

    metric_status = common_metric.get("status")
    if metric_status == "strict-common-metric-found":
        classification = "known-common-metric"
    elif metric_status == "no-strict-common-metric-numerically":
        classification = "novelty-survivor"
    else:
        manifest["common_metric"] = {
            **common_metric,
            "runner_error": "common-metric solver did not return a terminal status",
        }
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
        )
    return _finish(
        manifest,
        started,
        classification=classification,
        compute_success=True,
    )


def _successful_manifest(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("compute_success") is True


def run_spec(
    path: str | Path,
    *,
    workers: int = 1,
    shard_index: int = 0,
    shard_count: int = 1,
    screen_fn: ScreenFunction = screen_oddcycle_parameters,
    common_metric_fn: MetricFunction | None = None,
) -> dict[str, int]:
    """Execute one deterministic shard of a parameter-scan run specification."""

    if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
        raise ValueError("workers must be a positive integer")
    if (
        not isinstance(shard_count, int)
        or isinstance(shard_count, bool)
        or shard_count < 1
        or not isinstance(shard_index, int)
        or isinstance(shard_index, bool)
        or not 0 <= shard_index < shard_count
    ):
        raise ValueError("require 0 <= shard_index < shard_count")

    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    declared_run_dir = Path(spec.get("run_dir", spec_path.parent))
    run_dir = (
        declared_run_dir
        if declared_run_dir.is_absolute()
        else spec_path.parent
    )
    shared_settings = dict(spec.get("settings", {}))
    shared_provenance = dict(spec.get("provenance", {}))
    selected = [
        cell
        for position, cell in enumerate(spec["cells"])
        if position % shard_count == shard_index
    ]

    pending: list[Mapping[str, object]] = []
    reused = 0
    for cell in selected:
        manifest_path = (
            run_dir / "cells" / str(cell["cell_id"]) / "manifest.json"
        )
        if _successful_manifest(manifest_path):
            reused += 1
        else:
            pending.append(cell)

    def execute(cell: Mapping[str, object]) -> dict[str, object]:
        settings = {**shared_settings, **dict(cell.get("settings", {}))}
        provenance = {
            **shared_provenance,
            **dict(cell.get("provenance", {})),
        }
        manifest = run_cell(
            str(cell["cell_id"]),
            dict(cell["params"]),
            settings,
            provenance,
            screen_fn=screen_fn,
            common_metric_fn=common_metric_fn,
        )
        manifest_path = (
            run_dir / "cells" / str(cell["cell_id"]) / "manifest.json"
        )
        _write_json_atomic(manifest_path, manifest)
        return manifest

    completed = 0
    compute_errors = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(execute, cell) for cell in pending]
        for future in as_completed(futures):
            manifest = future.result()
            completed += 1
            if manifest["compute_success"] is not True:
                compute_errors += 1
            print(
                "oddcycle runner: "
                f"{completed}/{len(pending)} new cells "
                f"({reused} reused, {compute_errors} compute errors)",
                flush=True,
            )
    return {
        "selected": len(selected),
        "completed": completed,
        "reused": reused,
        "compute_errors": compute_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_spec", help="parameter-scan run_spec.json")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    arguments = parser.parse_args()
    summary = run_spec(
        arguments.run_spec,
        workers=arguments.workers,
        shard_index=arguments.shard_index,
        shard_count=arguments.shard_count,
    )
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()


__all__ = ["main", "run_cell", "run_spec"]
