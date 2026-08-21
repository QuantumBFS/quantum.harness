from dataclasses import FrozenInstanceError

import pytest

from qh147.config import EvolutionConfig, ModelConfig


def test_model_defaults_are_the_ratified_setup():
    cfg = ModelConfig()
    assert (cfg.lx, cfg.ly, cfg.j) == (10, 10, 1.0)
    assert cfg.fields == (2.5, 3.0, 3.5)
    assert cfg.nsites == 100


def test_evolution_grid_is_exact_and_immutable():
    cfg = EvolutionConfig()
    assert cfg.output_betas() == tuple(i / 10 for i in range(1, 11))
    assert cfg.bond_dims == (4, 6, 8)
    with pytest.raises(FrozenInstanceError):
        cfg.delta_beta = 0.05


@pytest.mark.parametrize("kwargs", [{"lx": 0}, {"ly": -1}, {"j": 0.0}, {"fields": ()}])
def test_invalid_model_configuration_fails(kwargs):
    with pytest.raises(ValueError):
        ModelConfig(**kwargs)


@pytest.mark.parametrize(
    ("config_type", "kwargs"),
    [
        (ModelConfig, {"fields": [3.0]}),
        (EvolutionConfig, {"bond_dims": [4, 6, 8]}),
    ],
)
def test_mutable_sequences_are_rejected(config_type, kwargs):
    with pytest.raises(TypeError):
        config_type(**kwargs)


def test_output_grid_must_include_beta_max_exactly():
    with pytest.raises(ValueError, match="exact output grid"):
        EvolutionConfig(beta_min=0.1, beta_max=1.0, output_step=0.2)
