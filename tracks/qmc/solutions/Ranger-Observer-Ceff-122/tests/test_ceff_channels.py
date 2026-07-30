import numpy as np
import pytest
from pydantic import ValidationError

from ceffflow.channels import ConfusionChannel, ErasureChannel
from ceffflow.schema import CellConfig, ChannelSpec


def test_erasure_channel_uses_declared_null_symbol():
    channel = ErasureChannel(0.5)
    outcomes = np.array([1, -1, 1, -1], dtype=np.int8)
    observed = channel.apply(
        outcomes,
        np.array([0.1, 0.8, 0.2, 0.9]),
    )
    assert np.array_equal(observed, np.array([1, 0, 1, 0], dtype=np.int8))


def test_erasure_channels_nest_for_fixed_uniform_construction():
    outcomes = np.array([1, -1, 1, -1], dtype=np.int8)
    fine = ErasureChannel(0.8).apply(
        outcomes,
        np.array([0.1, 0.2, 0.9, 0.7]),
    )
    nested = ErasureChannel(0.5).apply(
        fine,
        np.array([0.1, 0.8, 0.2, 0.9]),
    )
    assert np.array_equal(nested, np.array([1, 0, 0, 0], dtype=np.int8))


def test_confusion_log_probability_marginalizes_latent_outcome():
    channel = ConfusionChannel(0.1)
    value = channel.log_observed_probability(1, latent_prob_plus=0.7)
    assert np.isclose(np.exp(value), 0.7 * 0.9 + 0.3 * 0.1)


def test_confusion_minus_probability_is_complement():
    channel = ConfusionChannel(0.2)
    plus = np.exp(channel.log_observed_probability(1, 0.73))
    minus = np.exp(channel.log_observed_probability(-1, 0.73))
    assert np.isclose(plus + minus, 1.0)


def test_confusion_rejects_nonbinary_observation():
    with pytest.raises(ValueError, match="must be"):
        ConfusionChannel(0.1).log_observed_probability(0, 0.7)


def test_channel_spec_rejects_parameter_outside_channel_domain():
    with pytest.raises(ValidationError):
        ChannelSpec(kind="confusion", parameter=0.7)


def test_cell_config_requires_integral_blocks():
    with pytest.raises(ValidationError):
        CellConfig(
            model="self_dual",
            lengths=[4, 6, 8, 10],
            channel=ChannelSpec(kind="identity", parameter=0.0),
            steps=101,
            burn_in=10,
            block_size=20,
            seed=0,
        )
