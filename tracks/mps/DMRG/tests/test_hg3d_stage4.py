from __future__ import annotations

from dataclasses import FrozenInstanceError
import math
from pathlib import Path
from types import MappingProxyType

import pytest

from spinglass3d import workflow as stage4_workflow
from spinglass3d.workflow import StageManifest, classify_stage4, run_stage4


def test_stage4_refuses_a_failed_mps_gate() -> None:
    result = classify_stage4(
        gradient_error=3e-5,
        canonical_error=1e-13,
        delta_error=1e-13,
        checkpoint_equal=True,
    )
    assert result["classification"] == "CORRECTNESS_FAILURE"
    assert "gradient_error" in result["failed_gates"]


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_stage4_refuses_nonfinite_metrics(value: float) -> None:
    result = classify_stage4(
        gradient_error=value,
        canonical_error=0.0,
        delta_error=0.0,
        checkpoint_equal=True,
    )
    assert result["classification"] == "CORRECTNESS_FAILURE"
    assert result["failed_gates"] == ["gradient_error"]


def test_stage4_threshold_boundaries_pass() -> None:
    result = classify_stage4(
        gradient_error=2e-6,
        canonical_error=1e-12,
        delta_error=1e-10,
        checkpoint_equal=True,
    )
    assert result == {"classification": "PASS", "failed_gates": []}


def test_stage_manifest_is_immutable() -> None:
    manifest = StageManifest(
        stage="stage4",
        classification="PASS",
        failed_gates=(),
        artifacts={"metrics": "metrics.json"},
        hashes={"artifact:metrics.json": "a" * 64},
    )
    assert isinstance(manifest.artifacts, MappingProxyType)
    with pytest.raises(FrozenInstanceError):
        manifest.classification = "CORRECTNESS_FAILURE"  # type: ignore[misc]
    with pytest.raises(TypeError):
        manifest.artifacts["other"] = "other.json"  # type: ignore[index]


def test_stage4_refuses_to_overwrite_even_an_empty_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        run_stage4(Path("config/hard_goal/stage4_regression_v1.toml"), output)


def test_stage4_refuses_empty_destination_created_during_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "appears-during-run"

    monkeypatch.setattr(
        stage4_workflow,
        "_run_mps_tests",
        lambda _tests: {
            "command": ["pytest"],
            "started_at": "start",
            "finished_at": "finish",
            "exit_code": 0,
            "passed": True,
            "output": "passed",
        },
    )
    monkeypatch.setattr(
        stage4_workflow,
        "_run_numerical_probes",
        lambda _config, _checkpoint: {
            "classification": "PASS",
            "failed_gates": [],
        },
    )

    def create_racing_destination(_config: object) -> dict[str, object]:
        output.mkdir()
        return {
            "optimizer": {"steps_completed": 8},
            "frozen_measurement": {
                "model_unchanged": True,
                "measurement_sweeps": 16,
            },
        }

    monkeypatch.setattr(
        stage4_workflow, "_run_connectivity_cell", create_racing_destination
    )

    with pytest.raises(FileExistsError, match="overwrite"):
        run_stage4(Path("config/hard_goal/stage4_regression_v1.toml"), output)
    assert output.is_dir()
    assert not any(output.iterdir())
