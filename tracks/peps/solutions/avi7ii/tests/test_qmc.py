import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import qh147.qmc as qmc_module
from qh147.qmc import QMCConfig, main, run_chain


CONFIG = Path(__file__).parents[1] / "configs" / "qmc-reference.json"


def _small_config(**overrides):
    values = {
        "lx": 2,
        "ly": 1,
        "beta": 0.2,
        "h": 1.0,
        "j": 1.0,
        "m": 4,
        "thermal_sweeps": 20,
        "measure_sweeps": 40,
        "bins": 4,
        "seed": 17,
    }
    values.update(overrides)
    return QMCConfig(**values)


def test_qmc_chain_is_reproducible_and_resumable(tmp_path):
    cfg = _small_config()
    full = run_chain(cfg, tmp_path / "full")
    partial = run_chain(cfg, tmp_path / "split", stop_after=20)
    resumed = run_chain(cfg, tmp_path / "split")

    assert len(partial.bin_energy) == 2
    assert np.array_equal(full.bin_energy, resumed.bin_energy)
    assert len(full.bin_energy) == 4
    assert np.all(np.isfinite(full.bin_energy))
    assert 0.0 < full.mean_cluster_fraction <= 1.0


def test_one_spin_chain_matches_the_exact_quantum_energy(tmp_path):
    cfg = QMCConfig(
        lx=1,
        ly=1,
        beta=0.7,
        h=1.3,
        j=1.0,
        m=16,
        thermal_sweeps=1000,
        measure_sweeps=8000,
        bins=80,
        seed=37,
    )

    result = run_chain(cfg, tmp_path)
    exact = -cfg.h * np.tanh(cfg.beta * cfg.h)

    assert result.mean_energy == pytest.approx(exact, abs=4 * result.stderr_energy)


def test_resume_rejects_a_configuration_change(tmp_path):
    output = tmp_path / "chain"
    run_chain(_small_config(), output, stop_after=10)

    with pytest.raises(ValueError, match="configuration"):
        run_chain(_small_config(h=1.1), output)


@pytest.mark.parametrize(
    "overrides",
    [
        {"lx": 0},
        {"ly": 0},
        {"beta": 0.0},
        {"h": 0.0},
        {"j": 0.0},
        {"m": 1},
        {"bins": 1},
        {"measure_sweeps": 41},
        {"seed": 0},
    ],
)
def test_qmc_config_rejects_invalid_values(overrides):
    with pytest.raises(ValueError):
        _small_config(**overrides)


def test_production_configuration_is_the_ratified_h3_setup():
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert raw["model"] == {
        "lx": 10,
        "ly": 10,
        "j": 1.0,
        "fields": [3.0],
        "boundary": "open",
        "operator": "pauli",
    }
    assert raw["trotter_slices"] == [32, 64, 128]
    assert raw["chains"] == 4
    assert (raw["thermal_sweeps"], raw["measure_sweeps"], raw["bins"]) == (
        1000,
        8000,
        80,
    )


def test_cli_dry_run_writes_the_selected_cell(tmp_path):
    code = main(
        [
            "--config",
            str(CONFIG),
            "--run-dir",
            str(tmp_path),
            "--field",
            "3.0",
            "--beta",
            "0.5",
            "--M",
            "64",
            "--chain",
            "2",
            "--dry-run",
        ]
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert code == 0
    assert manifest["status"] == "rehearsed"
    assert manifest["params"]["seed"] == 148912
    assert manifest["params"]["thermal_sweeps"] == 1000


def test_cli_thermal_sweeps_override_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(
        qmc_module,
        "run_chain",
        lambda cfg, output: qmc_module.QMCResult(
            bin_energy=np.asarray([-1.0, -1.1]),
            mean_energy=-1.05,
            stderr_energy=0.05,
            mean_cluster_fraction=0.25,
        ),
    )

    assert main(
        [
            "--config",
            str(CONFIG),
            "--run-dir",
            str(tmp_path),
            "--field",
            "3.0",
            "--beta",
            "0.5",
            "--M",
            "128",
            "--chain",
            "0",
            "--thermal-sweeps",
            "16000",
        ]
    ) == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["settings"]["thermal_sweeps"] == 16000


def test_cli_measure_sweeps_override_is_recorded(tmp_path, monkeypatch):
    captured = {}

    def fake_run_chain(cfg, output):
        captured["cfg"] = cfg
        return qmc_module.QMCResult(
            bin_energy=np.asarray([-1.0, -1.1]),
            mean_energy=-1.05,
            stderr_energy=0.05,
            mean_cluster_fraction=0.25,
        )

    monkeypatch.setattr(qmc_module, "run_chain", fake_run_chain)
    assert main(
        [
            "--config",
            str(CONFIG),
            "--run-dir",
            str(tmp_path),
            "--field",
            "3.0",
            "--beta",
            "0.5",
            "--M",
            "32",
            "--chain",
            "0",
            "--measure-sweeps",
            "32000",
        ]
    ) == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert captured["cfg"].measure_sweeps == 32000
    assert manifest["settings"]["measure_sweeps"] == 32000
    sources = manifest["provenance"]["source_sha256"]
    assert sources == {
        "qh147/qmc.py": hashlib.sha256(qmc_module.Path(qmc_module.__file__).read_bytes()).hexdigest(),
        "qh147/qmc_mapping.py": hashlib.sha256(
            qmc_module.Path(qmc_module.__file__).with_name("qmc_mapping.py").read_bytes()
        ).hexdigest(),
        "configs/qmc-reference.json": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
    }
    assert isinstance(manifest["provenance"]["git_dirty"], bool)


@pytest.mark.parametrize("value", ("0", "-1", "32001"))
def test_cli_rejects_invalid_measure_sweeps_override(tmp_path, value):
    with pytest.raises(ValueError, match="measure_sweeps"):
        main(
            [
                "--config",
                str(CONFIG),
                "--run-dir",
                str(tmp_path),
                "--field",
                "3.0",
                "--beta",
                "0.5",
                "--M",
                "32",
                "--chain",
                "0",
                "--measure-sweeps",
                value,
                "--dry-run",
            ]
        )


@pytest.mark.parametrize("value", ("0", "-1"))
def test_cli_rejects_nonpositive_thermal_sweeps_override(tmp_path, value):
    with pytest.raises(ValueError, match="thermal_sweeps"):
        main(
            [
                "--config",
                str(CONFIG),
                "--run-dir",
                str(tmp_path),
                "--field",
                "3.0",
                "--beta",
                "0.5",
                "--M",
                "32",
                "--chain",
                "0",
                "--thermal-sweeps",
                value,
                "--dry-run",
            ]
        )
