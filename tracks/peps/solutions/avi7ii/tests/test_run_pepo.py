import json
from pathlib import Path

import pytest

import qh147.run as run_module
from qh147.evolve import ChainResult
from qh147.run import load_production_config, main


CONFIG = Path(__file__).parents[1] / "configs" / "pepo-h3-d4.json"
PROBE_CONFIG = Path(__file__).parents[1] / "configs" / "pepo-h3-d4-probe.json"
TWO_STEP_PROBE_CONFIG = (
    Path(__file__).parents[1]
    / "configs"
    / "pepo-h3-d4-probe-two-step.json"
)


def test_production_configuration_is_the_ratified_setup():
    production = load_production_config(CONFIG)
    chain = production.chain

    assert (chain.lx, chain.ly, chain.j, chain.h) == (10, 10, 1.0, 3.0)
    assert (production.boundary, production.operator) == ("open", "pauli")
    assert (chain.delta_beta, chain.beta_stop) == (0.025, 1.0)
    assert (chain.max_bond, chain.teacher_bond) == (4, 16)
    assert (chain.chi, production.measurement_chis) == (16, (16, 32))
    assert chain.cutoff == 1e-10
    assert (chain.optimizer, chain.max_iterations) == ("L-BFGS-B", 50)
    assert (chain.epsilon_z, chain.epsilon_u, chain.contraction_noise) == (
        1e-5,
        1e-4,
        1e-7,
    )
    assert (
        chain.lambda_z,
        chain.lambda_u,
        chain.lambda_hermiticity,
    ) == (1.0, 1.0, 1.0)
    assert chain.hermiticity_tolerance == 1e-6
    assert chain.loss_acceptance_tolerance == 1e-10
    assert production.public_step == 0.1


def test_probe_configuration_is_isolated_and_bounded():
    probe = load_production_config(PROBE_CONFIG)

    assert (probe.chain.lx, probe.chain.ly, probe.chain.h) == (10, 10, 3.0)
    assert (probe.chain.delta_beta, probe.chain.beta_stop) == (0.025, 0.025)
    assert (probe.chain.max_bond, probe.chain.teacher_bond) == (4, 16)
    assert probe.chain.chi == 16
    assert probe.chain.max_iterations == 1


def test_two_step_probe_reaches_first_nontrivial_compression():
    probe = load_production_config(TWO_STEP_PROBE_CONFIG)

    assert probe.chain.steps == 2
    assert probe.chain.beta_stop == 0.05
    assert probe.chain.max_iterations == 1


def test_production_configuration_rejects_unknown_keys(tmp_path):
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload["model"]["periodic"] = True
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown or missing model keys"):
        load_production_config(path)


def test_dry_run_reports_steps_modes_and_storage_without_evolution(
    tmp_path,
    capsys,
    monkeypatch,
):
    monkeypatch.setattr(
        run_module,
        "run_chain",
        lambda *args, **kwargs: pytest.fail("dry-run constructed an evolution"),
    )

    code = main(
        [
            "dry-run",
            "--config",
            str(CONFIG),
            "--run-root",
            str(tmp_path),
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["steps"] == 40
    assert payload["modes"] == ["ordinary", "thermodynamic"]
    assert payload["checkpoint_count"] == 80
    assert payload["one_checkpoint_bytes"] > 0
    assert payload["all_checkpoint_bytes"] == (
        payload["one_checkpoint_bytes"] * 80
    )
    assert payload["model"] == {
        "lx": 10,
        "ly": 10,
        "j": 1.0,
        "h": 3.0,
        "boundary": "open",
        "operator": "pauli",
    }


def test_evolve_dispatches_exactly_one_mode(tmp_path, monkeypatch):
    calls = []

    def fake_run_chain(config, run_root, *, mode, stop_after_steps):
        calls.append((config, run_root, mode, stop_after_steps))
        return ChainResult(accepted_betas=(), resumed_from=0.0, latest=None)

    monkeypatch.setattr(run_module, "run_chain", fake_run_chain)

    code = main(
        [
            "evolve",
            "--config",
            str(CONFIG),
            "--run-root",
            str(tmp_path),
            "--compression-mode",
            "thermodynamic",
            "--stop-after-steps",
            "1",
        ]
    )

    assert code == 0
    assert len(calls) == 1
    assert calls[0][1:] == (tmp_path, "thermodynamic", 1)


def test_measure_rejects_chi_outside_the_configuration(tmp_path):
    with pytest.raises(ValueError, match="measurement chi"):
        main(
            [
                "measure",
                "--config",
                str(CONFIG),
                "--run-root",
                str(tmp_path),
                "--compression-mode",
                "ordinary",
                "--chi",
                "64",
            ]
        )
