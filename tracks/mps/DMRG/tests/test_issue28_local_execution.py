from __future__ import annotations

import os
from pathlib import Path
import sys

import numpy as np
import pytest

from scripts.issue28_five_round import build_parser as build_n3_parser
from vmcrg_ref.hybrid_neural import HybridNeuralVMCRGOptimizer
from vmcrg_ref.multi_optimizer import MultiOperatorOptimizer
from vmcrg_ref.neural_energy import D4EvenLocalMLP
from vmcrg_ref.operators import EVEN_SHAPES


def _timed_child_commands(root: Path, names: list[str]) -> dict[str, list[str]]:
    code = (
        "from pathlib import Path; import sys, time; "
        "p=Path(sys.argv[1]); p.write_text('started', encoding='ascii'); "
        "time.sleep(0.12); p.with_suffix('.done').write_text('done', encoding='ascii')"
    )
    return {
        name: [sys.executable, "-c", code, str(root / f"{name}.started")]
        for name in names
    }


def _failing_child_commands(root: Path) -> dict[str, list[str]]:
    fail = [sys.executable, "-c", "raise SystemExit(7)"]
    success = [
        sys.executable,
        "-c",
        "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('ok', encoding='ascii')",
        str(root / "formal-2.ok"),
    ]
    return {
        "formal-1": fail,
        "formal-2": success,
        "formal-3": success,
        "formal-4": success,
        "formal-5": success,
    }


def test_worker_limit_is_bounded_by_tasks_not_cpu_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vmcrg_ref.local_execution import resolve_worker_limit

    monkeypatch.setattr(os, "cpu_count", lambda: 256)
    assert resolve_worker_limit(3, 8) == 3
    assert resolve_worker_limit(20, 8) == 8
    assert resolve_worker_limit(None, 8) == 8
    with pytest.raises(ValueError, match="positive"):
        resolve_worker_limit(0, 8)


def test_local_host_provenance_records_declared_worker_budget() -> None:
    from vmcrg_ref.local_execution import local_host_provenance

    record = local_host_provenance(
        workers_per_bundle=3,
        max_parallel_bundles=2,
    )
    assert record["node"]
    assert record["logical_cpus"] >= 1
    assert record["memory_total_bytes"] > 0
    assert record["memory_available_bytes"] > 0
    assert record["workers_per_bundle"] == 3
    assert record["max_parallel_bundles"] == 2


def test_n3_cli_exposes_explicit_large_local_gate() -> None:
    args = build_n3_parser().parse_args(
        [
            "--preset",
            "pilot",
            "--rounds",
            "5",
            "--backend",
            "local",
            "--workers",
            "8",
            "--allow-large-local",
            "--output",
            "run",
        ]
    )
    assert args.allow_large_local is True
    assert args.workers == 8


def test_neural_and_linear_optimizers_retain_declared_worker_limit() -> None:
    couplings = np.asarray([0.2, *([0.0] * 12)], dtype=np.float64)
    neural = HybridNeuralVMCRGOptimizer(
        21,
        couplings,
        np.zeros(13, dtype=np.float64),
        D4EvenLocalMLP.random(1, 3, 41, feature_mode="patch"),
        EVEN_SHAPES,
        walkers=4,
        seed=42,
        max_workers=2,
    )
    linear = MultiOperatorOptimizer(
        21,
        couplings,
        EVEN_SHAPES,
        walkers=4,
        seed=43,
        max_workers=2,
    )
    assert neural.max_workers == 2
    assert linear.max_workers == 2


def test_schedule_runs_five_unique_cells_with_peak_two(tmp_path: Path) -> None:
    from vmcrg_ref.local_execution import run_bounded_process_schedule

    names = [f"formal-{index}" for index in range(1, 6)]
    result = run_bounded_process_schedule(
        _timed_child_commands(tmp_path, names),
        output=tmp_path / "state",
        max_parallel=2,
        minimum_memory_for_parallel_bytes=1,
        resume=False,
    )
    assert result["dispatch_order"] == names
    assert result["maximum_observed_parallel"] == 2
    assert result["attempts"] == {name: 1 for name in names}
    assert result["completed"] == names


def test_memory_floor_downgrades_second_bundle(monkeypatch, tmp_path: Path) -> None:
    import vmcrg_ref.local_execution as local_execution

    monkeypatch.setattr(local_execution, "available_memory_bytes", lambda: 0)
    from vmcrg_ref.local_execution import run_bounded_process_schedule

    names = ["formal-1", "formal-2", "formal-3"]
    result = run_bounded_process_schedule(
        _timed_child_commands(tmp_path, names),
        output=tmp_path / "state",
        max_parallel=2,
        minimum_memory_for_parallel_bytes=12 * 1024**3,
        resume=False,
    )
    assert result["maximum_observed_parallel"] == 1
    assert result["memory_downgrade_count"] >= 1


def test_nonzero_child_stops_new_launches(tmp_path: Path) -> None:
    from vmcrg_ref.local_execution import run_bounded_process_schedule

    result = run_bounded_process_schedule(
        _failing_child_commands(tmp_path),
        output=tmp_path / "state",
        max_parallel=1,
        minimum_memory_for_parallel_bytes=1,
        resume=False,
    )
    assert result["classification"] == "PROTOCOL_FAILURE"
    assert result["completed"] == []
    assert result["not_launched"] == ["formal-2", "formal-3", "formal-4", "formal-5"]


def test_resume_skips_completed_cells_without_replacement_or_retry(tmp_path: Path) -> None:
    from vmcrg_ref.local_execution import run_bounded_process_schedule

    commands = _timed_child_commands(tmp_path, ["formal-1", "formal-2"])
    first = run_bounded_process_schedule(
        commands,
        output=tmp_path / "state",
        max_parallel=2,
        minimum_memory_for_parallel_bytes=1,
        resume=False,
    )
    second = run_bounded_process_schedule(
        commands,
        output=tmp_path / "state",
        max_parallel=2,
        minimum_memory_for_parallel_bytes=1,
        resume=True,
    )
    assert first["attempts"] == {"formal-1": 1, "formal-2": 1}
    assert second["attempts"] == first["attempts"]
    assert second["dispatch_order"] == first["dispatch_order"]


def test_local_formal_requires_explicit_authorization(tmp_path: Path) -> None:
    from vmcrg_ref.local_execution import run_local_formal

    with pytest.raises(ValueError, match="allow_large_local"):
        run_local_formal(
            Path("config/issue28_easy_v1.json"),
            tmp_path / "formal",
            allow_large_local=False,
        )
    assert not (tmp_path / "formal").exists()


def test_local_formal_cli_exposes_bounded_wave_options() -> None:
    from scripts.issue28_local_formal import build_parser

    args = build_parser().parse_args(
        [
            "--output",
            "results/n4",
            "--workers-per-bundle",
            "8",
            "--max-parallel-bundles",
            "2",
            "--minimum-available-gib",
            "12",
            "--allow-large-local",
        ]
    )
    assert args.workers_per_bundle == 8
    assert args.max_parallel_bundles == 2
    assert args.minimum_available_gib == 12.0
    assert args.allow_large_local is True


def test_local_execution_api_is_exported_from_package_root() -> None:
    import vmcrg_ref

    from vmcrg_ref.local_execution import run_local_formal

    assert vmcrg_ref.run_local_formal is run_local_formal
