import json
from pathlib import Path

from scripts.plan_ceffflow_production import build_run_spec


def _build(axes, tmp_path):
    return build_run_spec(
        axes,
        run_id="test",
        run_dir=tmp_path / "run",
        axes_source=tmp_path / "axes.json",
    )


def test_production_axes_regenerate_committed_cells(tmp_path):
    project = Path(__file__).parents[1]
    axes_path = project / "configs/ceffflow/production_axes.json"
    committed = json.loads(
        (project / "results/ceffflow-production/run_spec.json").read_text()
    )
    regenerated = build_run_spec(
        json.loads(axes_path.read_text()),
        run_id=committed["run_id"],
        run_dir=Path(committed["run_dir"]),
        axes_source=Path(committed["axes_source"]),
    )
    assert regenerated == committed


def test_optional_models_and_particle_count_order(tmp_path):
    axes = {
        "lengths": [6, 8, 10],
        "seeds": [0, 1],
        "self_dual": {
            "channels": {
                "identity": [0.0],
                "confusion": [0.1],
                "erasure": [0.9],
            },
            "steps": 20,
            "burn_in": 0,
            "block_size": 10,
            "particle_counts": [64, 256],
        },
    }
    cells = _build(axes, tmp_path)["cells"]
    assert len(cells) == 10
    assert [cell["settings"]["particles"] for cell in cells[:2]] == [1, 1]
    assert {cell["settings"]["particles"] for cell in cells[2:6]} == {64}
    assert {cell["settings"]["particles"] for cell in cells[6:]} == {256}
    assert all(
        cell["settings"]["model"] == "self_dual" for cell in cells
    )


def test_nishimori_can_be_planned_without_self_dual(tmp_path):
    cells = _build(
        {
            "lengths": [6, 8, 10],
            "seeds": [3, 5],
            "nishimori": {
                "steps": 100,
                "burn_in": 10,
                "block_size": 10,
            },
        },
        tmp_path,
    )["cells"]
    assert len(cells) == 2
    assert [cell["settings"]["seed"] for cell in cells] == [3, 5]
    assert all(cell["settings"]["model"] == "nishimori" for cell in cells)


def test_particle_counts_must_be_nonempty_and_unique(tmp_path):
    axes = {
        "lengths": [6, 8, 10],
        "seeds": [0],
        "self_dual": {
            "channels": {"confusion": [0.1]},
            "steps": 20,
            "burn_in": 0,
            "block_size": 10,
            "particle_counts": [64, 64],
        },
    }
    try:
        _build(axes, tmp_path)
    except ValueError as exc:
        assert str(exc) == "particle_counts must be nonempty and unique"
    else:
        raise AssertionError("duplicate particle counts were accepted")
