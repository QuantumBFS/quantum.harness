import json

import pytest

from qh147.current_evidence import load_pepo_probe, load_qmc_validation


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _pepo_fixture(root):
    thermo = root / "thermodynamic"
    _write_json(
        thermo / "manifest.json",
        {
            "status": "complete",
            "mode": "thermodynamic",
            "config_sha256": "fixture",
            "accepted_betas": [0.025, 0.05],
        },
    )
    for beta in (0.025, 0.05):
        _write_json(
            thermo / "checkpoints" / f"beta-{beta:.6f}" / "metadata.json",
            {
                "beta": beta,
                "mode": "thermodynamic",
                "config_sha256": "fixture",
                "lattice": {"lx": 10, "ly": 10},
                "diagnostics": {
                    "budget": {"requested_bond": 4, "chi": 16},
                    "final": {
                        "total": 1e-8,
                        "frobenius": 1e-9,
                        "u_difference": 1e-7,
                        "z_difference": 1e-8,
                        "u_penalty": 1e-8,
                        "z_penalty": 1e-9,
                        "hermiticity_penalty": 0.0,
                    },
                    "u": -beta,
                    "z": 0.7,
                    "hermiticity_residual": 0.0,
                    "iterations": 0,
                    "max_bond": 4,
                    "peak_memory_bytes": 1024,
                    "wall_seconds": 1.0,
                },
            },
        )
    return root


def test_pepo_loader_accepts_only_the_declared_two_step_probe(tmp_path):
    root = _pepo_fixture(tmp_path / "pepo")

    result = load_pepo_probe(root)

    assert result["status"] == "two-step-probe"
    assert [point["beta"] for point in result["points"]] == [0.025, 0.05]
    assert result["D"] == 4
    assert result["chi"] == 16

    manifest = root / "thermodynamic" / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["accepted_betas"] = [0.025]
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly the two"):
        load_pepo_probe(root)


def test_qmc_loader_rejects_unaccepted_analysis(tmp_path):
    analysis = {
        "accepted": True,
        "finite_m": [
            {"M": m, "x": (0.5 / m) ** 2, "u": -2.9,
             "bootstrap_se": 0.003, "residual_sigma": 0.0}
            for m in (32, 64, 128)
        ],
        "diagnostics": [
            {"M": m, "rhat": 1.0, "max_split_half_z": 1.0}
            for m in (32, 64, 128)
        ],
        "fit": {
            "u_infinity": -2.91,
            "bootstrap_se": 0.003,
            "ci95": [-2.916, -2.904],
            "slope": 2.0,
            "reduced_chi2": 0.1,
        },
        "thresholds": {"rhat_max": 1.05, "split_half_z_max": 3.0},
    }
    _write_json(tmp_path / "analysis.json", analysis)

    assert load_qmc_validation(tmp_path)["fit"]["u_infinity"] == -2.91

    analysis["accepted"] = False
    _write_json(tmp_path / "analysis.json", analysis)
    with pytest.raises(ValueError, match="acceptance gates"):
        load_qmc_validation(tmp_path)
