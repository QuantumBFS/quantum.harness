import json
from pathlib import Path

import numpy as np
import pytest

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
