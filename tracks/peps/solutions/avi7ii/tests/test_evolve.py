from dataclasses import replace
import json

import pytest

from qh147.compress import (
    CompressionBudget,
    CompressionDiagnostics,
    CompressionResult,
)
from qh147.evolve import ChainConfig, run_chain
from qh147.pepo import FinitePEPO


def _config(**changes) -> ChainConfig:
    config = ChainConfig(
        lx=2,
        ly=1,
        j=1.0,
        h=0.7,
        delta_beta=0.025,
        beta_stop=0.075,
        max_bond=4,
        teacher_bond=16,
        chi=16,
        cutoff=1e-10,
        max_iterations=50,
        optimizer="L-BFGS-B",
        epsilon_z=1e-5,
        epsilon_u=1e-4,
        contraction_noise=1e-7,
        lambda_z=1.0,
        lambda_u=1.0,
        lambda_hermiticity=1.0,
        hermiticity_tolerance=1e-6,
        loss_acceptance_tolerance=1e-10,
    )
    return replace(config, **changes)


def _diagnostics(total: float) -> CompressionDiagnostics:
    return CompressionDiagnostics(
        total=total,
        frobenius=total,
        z_penalty=0.0,
        u_penalty=0.0,
        hermiticity_penalty=0.0,
        z_difference=0.0,
        u_difference=0.0,
    )


class DeterministicCompressor:
    def __init__(self, config: ChainConfig, *, final_total: float = 0.0):
        self.config = config
        self.final_total = final_total

    def compress(self, teacher, *, max_bond, mode):
        return CompressionResult(
            pepo=FinitePEPO.identity(teacher.lx, teacher.ly),
            initial=_diagnostics(1.0),
            final=_diagnostics(self.final_total),
            iterations=1,
            loss_history=(1.0, self.final_total),
            max_bond=1,
            mode=mode,
            budget=CompressionBudget(
                chi=self.config.chi,
                cutoff=self.config.cutoff,
                max_iterations=self.config.max_iterations,
                optimizer=self.config.optimizer,
                requested_bond=max_bond,
            ),
        )


def _factory(config, mode):
    return DeterministicCompressor(config)


def test_chain_resumes_without_rewriting_accepted_points(tmp_path):
    config = _config()
    first = run_chain(
        config,
        tmp_path,
        mode="ordinary",
        compressor_factory=_factory,
        stop_after_steps=2,
    )
    assert first.latest is not None
    tensor_path = first.latest.path / "tensors.npz"
    before = tensor_path.read_bytes()

    second = run_chain(
        config,
        tmp_path,
        mode="ordinary",
        compressor_factory=_factory,
    )

    assert second.accepted_betas == (0.025, 0.05, 0.075)
    assert second.resumed_from == 0.05
    assert tensor_path.read_bytes() == before


@pytest.mark.parametrize("mode", ["ordinary", "thermodynamic"])
def test_modes_record_the_same_fixed_budget(tmp_path, mode):
    config = _config(beta_stop=0.025)

    result = run_chain(
        config,
        tmp_path,
        mode=mode,
        compressor_factory=_factory,
    )

    assert result.latest is not None
    budget = result.latest.diagnostics["budget"]
    assert budget == {
        "chi": 16,
        "cutoff": 1e-10,
        "max_iterations": 50,
        "optimizer": "L-BFGS-B",
        "requested_bond": 4,
    }


def test_failed_step_keeps_previous_checkpoint_and_writes_failure(tmp_path):
    config = _config(beta_stop=0.05)

    run_chain(
        config,
        tmp_path,
        mode="ordinary",
        compressor_factory=_factory,
        stop_after_steps=1,
    )

    def failing_factory(config, mode):
        return DeterministicCompressor(config, final_total=float("nan"))

    with pytest.raises(RuntimeError, match="beta 0.05"):
        run_chain(
            config,
            tmp_path,
            mode="ordinary",
            compressor_factory=failing_factory,
        )

    checkpoints = tmp_path / "ordinary" / "checkpoints"
    assert (checkpoints / "beta-0.025000" / "metadata.json").is_file()
    assert not (checkpoints / "beta-0.050000" / "metadata.json").exists()
    failure = json.loads(
        (tmp_path / "ordinary" / "failure.json").read_text(encoding="utf-8")
    )
    assert failure["beta"] == 0.05


def test_increasing_loss_is_rejected(tmp_path):
    config = _config(beta_stop=0.025)

    def increasing_factory(config, mode):
        return DeterministicCompressor(config, final_total=2.0)

    with pytest.raises(RuntimeError, match="objective loss increased"):
        run_chain(
            config,
            tmp_path,
            mode="ordinary",
            compressor_factory=increasing_factory,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"lx": 0},
        {"delta_beta": 0.0},
        {"beta_stop": 0.06},
        {"max_bond": 0},
        {"teacher_bond": 3},
        {"chi": 0},
        {"cutoff": -1.0},
        {"max_iterations": 0},
        {"epsilon_z": 1e-8},
    ],
)
def test_invalid_chain_configuration_fails(changes):
    with pytest.raises((TypeError, ValueError)):
        _config(**changes)


def test_chain_rejects_an_unknown_mode(tmp_path):
    with pytest.raises(ValueError, match="compression mode"):
        run_chain(
            _config(),
            tmp_path,
            mode="other",
            compressor_factory=_factory,
        )


def test_configuration_hash_is_stable_and_sensitive():
    config = _config()
    assert config.config_sha256() == _config().config_sha256()
    assert config.config_sha256() != _config(h=0.8).config_sha256()
