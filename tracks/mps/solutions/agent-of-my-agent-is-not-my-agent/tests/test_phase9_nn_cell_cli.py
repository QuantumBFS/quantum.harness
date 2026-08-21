from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from scripts import run_phase9_nn_cell


class _FakeState:
    def __init__(self, sector: str):
        self.energy = -7.0 if sector == "even" else -6.8
        self.variance = 1.0e-12
        self.max_chi = 12
        self.max_discarded_weight = 2.0e-9
        self.sweep_statistics = {"sweep": [1, 2, 3]}
        self.psi = object()


def _args(output_dir: Path, sector: str = "even") -> SimpleNamespace:
    return SimpleNamespace(
        length=8,
        gamma=1.0,
        sector=sector,
        chi=64,
        max_sweeps=30,
        output_dir=output_dir,
    )


def _patch_runtime(monkeypatch):
    fake_mpo = SimpleNamespace(chi=[1, 4, 1])
    monkeypatch.setattr(
        run_phase9_nn_cell,
        "build_rotated_nearest_neighbor_tfim_mpo",
        lambda length, gamma: fake_mpo,
    )
    monkeypatch.setattr(
        run_phase9_nn_cell,
        "build_mpo_model",
        lambda mpo: object(),
    )
    calls = []

    def fake_run(model, options, sector):
        calls.append(sector)
        return _FakeState(sector)

    monkeypatch.setattr(run_phase9_nn_cell, "_run_sector", fake_run)
    monkeypatch.setattr(
        run_phase9_nn_cell,
        "physical_correlations_rotated",
        lambda psi: np.asarray([1.0, 0.6, 0.4, 0.3, 0.2, 0.3, 0.4, 0.6]),
    )
    monkeypatch.setattr(
        run_phase9_nn_cell,
        "second_moment_ratio",
        lambda correlations: SimpleNamespace(
            s_zero=3.8,
            s_k_min=1.2,
            k_min=np.pi / 4,
            xi=2.4,
            r_xi=0.3,
        ),
    )
    saved = []

    def fake_save(directory, psi, provenance, diagnostics):
        saved.append((directory, provenance, diagnostics))

    monkeypatch.setattr(run_phase9_nn_cell, "save_checkpoint", fake_save)
    monkeypatch.setattr(run_phase9_nn_cell, "code_tree_hash", lambda root: "code")
    return calls, saved


def test_even_cell_writes_auditable_summary_and_checkpoint_metadata(
    tmp_path: Path,
    monkeypatch,
):
    calls, saved = _patch_runtime(monkeypatch)

    run_phase9_nn_cell.run_cell(_args(tmp_path))

    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["status"] == "success"
    assert summary["settings"]["model"] == "nearest-neighbor-tfim"
    assert summary["settings"]["sigma"] is None
    assert summary["settings"]["chi_schedule"] == [64]
    assert summary["model"]["exact_model_hash"]
    assert summary["model"]["operator_convention"] == "rotated-xz-parity-v1"
    assert summary["mpo"]["approximate_compression"] is False
    assert summary["raw_observables"]["r_xi"] == 0.3
    assert len(summary["raw_observables"]["correlations"]) == 8
    assert calls == ["even"]
    assert len(saved) == 1
    provenance = saved[0][1]
    assert provenance.sigma is None
    assert provenance.fit_hash == summary["model"]["exact_model_hash"]
    assert provenance.active_channels == ()


def test_odd_cell_records_energy_without_even_observables(
    tmp_path: Path,
    monkeypatch,
):
    calls, _ = _patch_runtime(monkeypatch)

    run_phase9_nn_cell.run_cell(_args(tmp_path, sector="odd"))

    summary = json.loads((tmp_path / "summary.json").read_text())
    assert calls == ["odd"]
    assert set(summary["direct"]) == {"odd"}
    assert summary["raw_observables"] == {}


def test_successful_cell_is_reused_without_running_dmrg(
    tmp_path: Path,
    monkeypatch,
):
    calls, _ = _patch_runtime(monkeypatch)
    arguments = _args(tmp_path)
    run_phase9_nn_cell.run_cell(arguments)
    before = (tmp_path / "summary.json").read_text()

    run_phase9_nn_cell.run_cell(arguments)

    assert calls == ["even"]
    assert (tmp_path / "summary.json").read_text() == before
