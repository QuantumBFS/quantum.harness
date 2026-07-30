import pytest

from floquet_if_manybody.config import ModelConfig, RunConfig


def test_default_normalization_and_units():
    cfg = RunConfig()
    assert cfg.model.omega == 1.0
    assert cfg.model.normalization == "bounded"
    assert cfg.model.eta == 1 / cfg.model.n


def test_normalizations():
    assert ModelConfig(n=3, normalization="bounded").eta == pytest.approx(1 / 3)
    assert ModelConfig(n=3, normalization="kac").eta == pytest.approx(1 / 3**0.5)
    assert ModelConfig(n=3, normalization="collective").eta == 1


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError, match="omega"):
        ModelConfig(omega=0)
