from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.hard_goal_stage6_local import run_local_stage6, science_cell_state
from spinglass3d.equilibration import EquilibrationThresholds
from spinglass3d.science_pilot import PILOT_NEEDS_EXTENSION, SciencePilotSpec
from spinglass3d.stage6 import (
    EQUILIBRATION_CADENCE,
    LOCAL_EXECUTION_POLICY,
    MEASUREMENT_CADENCE,
    SelectedLadder,
    build_selected_science_run_spec,
    load_selected_ladder,
)
from spinglass3d.workflow import load_stage6_config
from vmcrg_ref.artifacts import sha256_file


TRACK = Path(__file__).resolve().parents[1]
CONFIG = TRACK / "config/hard_goal/stage6_pilot_v1.toml"


def _ladder(tmp_path: Path, length: int) -> SelectedLadder:
    selection = tmp_path / f"L{length}-selection.json"
    manifest = tmp_path / f"L{length}-manifest.json"
    selection.write_text("{}\n", encoding="ascii")
    manifest.write_text("{}\n", encoding="ascii")
    temperatures = {
        12: (2.0, 1.4, 1.0, 0.8),
        18: (2.0, 1.5, 1.1, 0.8),
        24: (2.0, 1.6, 1.2, 0.8),
        27: (2.0, 1.7, 1.3, 0.8),
    }[length]
    return SelectedLadder(
        length=length,
        temperatures=temperatures,
        selection_path=selection,
        selection_sha256=sha256_file(selection),
        selected_manifest_path=manifest,
        selected_manifest_sha256=sha256_file(manifest),
        selected_cell_id=f"L{length}-J0000-A035",
        target_acceptance=0.35,
        round_trips_min=2,
    )


def test_recalibrate_record_cannot_enter_science() -> None:
    selection = (
        TRACK
        / "results/hard_goal/stage6-status-20260730/L24-selection.json"
    )
    with pytest.raises(ValueError, match="SELECT"):
        load_selected_ladder(
            selection,
            expected_length=24,
            track_root=TRACK,
            repo_root=TRACK,
        )


def test_selected_science_matrix_uses_each_measured_length_ladder(
    tmp_path: Path,
) -> None:
    config = load_stage6_config(CONFIG)
    ladders = {length: _ladder(tmp_path, length) for length in config.lengths}

    spec = build_selected_science_run_spec(config, ladders, "stage6-local-science-v1")

    assert spec["phase"] == "selected_ladder_science_pilot"
    assert spec["array"] == {"count": 120, "index_origin": 1}
    assert spec["settings"]["sampling"]["measurement_cadence"] == MEASUREMENT_CADENCE
    assert spec["settings"]["sampling"]["equilibration_cadence"] == EQUILIBRATION_CADENCE
    assert spec["settings"]["execution"] == {
        "backend": "jax_cpu",
        "execution_policy": LOCAL_EXECUTION_POLICY,
        "remote_execution": False,
    }
    counts = {
        length: sum(cell["params"]["length"] == length for cell in spec["cells"])
        for length in config.lengths
    }
    assert counts == {12: 64, 18: 32, 24: 16, 27: 8}
    for cell in spec["cells"]:
        length = cell["params"]["length"]
        assert cell["params"]["temperatures"] == list(ladders[length].temperatures)
        assert "/science-cells/" in cell["params"]["output"]
    assert set(spec["provenance"]["ladder_selection_sha256"]) == {
        "12", "18", "24", "27"
    }
    assert "src/spinglass3d/stage6.py" in spec["provenance"]["source_sha256"]


def test_selected_science_matrix_rejects_missing_or_mismatched_ladder(
    tmp_path: Path,
) -> None:
    config = load_stage6_config(CONFIG)
    ladders = {length: _ladder(tmp_path, length) for length in config.lengths}
    del ladders[27]
    with pytest.raises(ValueError, match="every Stage 6 length"):
        build_selected_science_run_spec(config, ladders, "missing")

    ladders[27] = _ladder(tmp_path, 24)
    with pytest.raises(ValueError, match="mismatched length"):
        build_selected_science_run_spec(config, ladders, "mismatch")


def test_selected_ladder_rejects_path_outside_hard_goal(tmp_path: Path) -> None:
    outside = tmp_path / "selection.json"
    outside.write_text(json.dumps({"decision": "SELECT"}) + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="results/hard_goal"):
        load_selected_ladder(
            outside,
            expected_length=12,
            track_root=TRACK,
            repo_root=TRACK,
        )


def _science_spec() -> SciencePilotSpec:
    return SciencePilotSpec(
        cell_id="L12-J0000",
        length=12,
        temperatures=(2.0, 1.4, 1.0, 0.8),
        chain_pairs=4,
        calibration_sweeps=4,
        equilibration_initial_sweeps=8,
        equilibration_multiplier=2,
        equilibration_maximum_sweeps=32,
        measurement_sweeps=8,
        equilibration_cadence=2,
        measurement_cadence=2,
        j_seed=2026073601,
        thresholds=EquilibrationThresholds(
            swap_bottleneck=0.0,
            swap_target_min=0.0,
            swap_target_max=1.0,
            min_round_trips=1,
            max_rhat=2.0,
            min_ess=1.0,
            bin_sigma=2.0,
            max_thermal_error_fraction=1.0,
            min_chains=4,
        ),
        templates=("cube", "cross"),
        rg_levels=1,
        source_hashes={"test": "a" * 64},
    )


def _write_work_status(output: Path, spec: SciencePilotSpec, target: int) -> None:
    work = output.parent / f".{output.name}.science-work"
    checkpoint = work / "checkpoints/checkpoint-000000001"
    checkpoint.mkdir(parents=True)
    (checkpoint / "metadata.json").write_text("{}\n", encoding="ascii")
    status = {
        "schema_version": 1,
        "stage": "stage6",
        "scope": "scientific-stage6-pilot-cell",
        "classification": PILOT_NEEDS_EXTENSION,
        "cell_id": spec.cell_id,
        "spec_sha256": spec.sha256,
        "progress": {"equilibration_target": target},
    }
    (work / "status.json").write_text(
        json.dumps(status, sort_keys=True) + "\n",
        encoding="ascii",
    )


def test_local_cell_state_distinguishes_resume_from_maximum_negative(
    tmp_path: Path,
) -> None:
    spec = _science_spec()
    output = tmp_path / "cells" / spec.cell_id
    assert science_cell_state(spec, output)["state"] == "NEW"

    _write_work_status(output, spec, 8)
    state = science_cell_state(spec, output)
    assert state["state"] == "RESUME"
    assert state["resume"] is True

    status_path = output.parent / f".{output.name}.science-work/status.json"
    status = json.loads(status_path.read_text(encoding="ascii"))
    status["progress"]["equilibration_target"] = 32
    status_path.write_text(json.dumps(status) + "\n", encoding="ascii")
    terminal = science_cell_state(spec, output)
    assert terminal["state"] == "SCIENTIFIC_NEGATIVE"
    assert terminal["resume"] is False


def test_large_local_stage6_requires_explicit_authorization(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow-large-local"):
        run_local_stage6(
            tmp_path / "missing-run-spec.json",
            max_parallel=1,
            workers_per_cell=1,
            minimum_available_gib=1.0,
            checkpoint_every=1,
            resume=False,
            allow_large_local=False,
        )
