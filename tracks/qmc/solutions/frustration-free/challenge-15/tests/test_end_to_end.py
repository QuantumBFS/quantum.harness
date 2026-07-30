from __future__ import annotations

import json

import jax.numpy as jnp
import numpy as np

from challenge15.artifacts import verify_artifact
from challenge15.cli import _restore_parameters, main
from challenge15.model import ModelConfig, ProjectedPfaffianNQS
from challenge15.spec import SphereSpec


def test_n4_two_step_exact_smoke_is_reloadable_and_claim_safe(tmp_path):
    config = {
        "particles": 4,
        "ranks": [1],
        "seeds": [3],
        "steps": 2,
        "batch_size": 1,
        "hidden_width": 4,
        "depth": 0,
        "token_width": 2,
        "fourier_order": 1,
        "projection_block_size": 32,
    }
    config_path = tmp_path / "smoke.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    train_output = tmp_path / "train"
    evaluate_output = tmp_path / "evaluate"
    report_output = tmp_path / "report"

    assert main(
        ["train", "--config", str(config_path), "--output", str(train_output)]
    ) == 0
    checkpoint = verify_artifact(train_output / "checkpoint.json")
    assert checkpoint["records"][0]["shared_parameter_tree"] is True
    assert checkpoint["records"][0]["parameter_sha256"]
    assert checkpoint["records"][0]["prng_provenance"]

    assert main(
        [
            "evaluate",
            "--checkpoint",
            str(train_output / "checkpoint.json"),
            "--output",
            str(evaluate_output),
        ]
    ) == 0
    evaluation = verify_artifact(evaluate_output / "evaluation.json")
    exact = evaluation["evaluations"][0]
    assert np.isfinite(exact["energy_l0"])
    assert np.isfinite(exact["energy_l2"])
    assert exact["finite_size_l2_gap"] > 0
    assert exact["l2_residual_l0"] <= 1e-10
    assert exact["l2_residual_l2"] <= 1e-10
    assert exact["bare_potential_sampling_variance"] is None
    assert "hamiltonian_variance" not in exact
    assert "h_lll_variance_l0" in exact
    assert evaluation["production_accepted"] is False
    assert evaluation["chiral_graviton_claim"] is False

    assert main(
        [
            "report",
            "--evaluation",
            str(evaluate_output / "evaluation.json"),
            "--output",
            str(report_output),
        ]
    ) == 0
    report = verify_artifact(report_output / "report.json")
    assert report["chiral_graviton_claim"] is False
    assert report["production_accepted"] is False
    assert "thermodynamic" not in report

    spec = SphereSpec(4)
    parameters = _restore_parameters(spec, config, checkpoint["records"][0])
    model = ProjectedPfaffianNQS(
        ModelConfig(
            rank=1,
            hidden_width=4,
            depth=0,
            token_width=2,
            fourier_order=1,
            block_size=32,
        )
    )
    rng = np.random.default_rng(91)
    spinors = rng.normal(size=(4, 2)) + 1j * rng.normal(size=(4, 2))
    spinors /= np.linalg.norm(spinors, axis=1, keepdims=True)
    variables = {"params": parameters}
    for target_l in (0, 2):
        value = model.apply(variables, spec, jnp.asarray(spinors), target_l=target_l)
        exchanged = spinors.copy()
        exchanged[[0, 1]] = exchanged[[1, 0]]
        np.testing.assert_allclose(
            model.apply(
                variables, spec, jnp.asarray(exchanged), target_l=target_l
            ),
            -value,
            rtol=3e-10,
            atol=3e-11,
        )
        scale = 1.1 - 0.2j
        scaled = spinors.copy()
        scaled[0] *= scale
        np.testing.assert_allclose(
            model.apply(variables, spec, jnp.asarray(scaled), target_l=target_l),
            scale**spec.two_q * value,
            rtol=3e-10,
            atol=3e-11,
        )
