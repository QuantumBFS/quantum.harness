from __future__ import annotations

import itertools

import numpy as np
import pytest

from spinglass3d.model import EABonds
from spinglass3d.templates import TemplateEncoder
from spinglass3d.tensor_train import LocalTensorTrain, SymmetricLocalTT, TTGradient


@pytest.mark.parametrize(
    "tokens,chi,count",
    [
        (13, 2, 96),
        (13, 4, 368),
        (13, 8, 1440),
        (19, 2, 144),
        (31, 4, 944),
        (55, 8, 6816),
    ],
)
def test_declared_parameter_counts(tokens: int, chi: int, count: int) -> None:
    model = LocalTensorTrain.random(tokens, chi, seed=3)
    assert model.parameter_count == count


def test_tt_value_matches_direct_matrix_product() -> None:
    model = LocalTensorTrain.random(13, 4, seed=4)
    tokens = np.array([1, -1] * 6 + [1], dtype=np.int8)
    product = np.ones((1, 1), dtype=np.float64)
    for core, token in zip(model.cores, tokens, strict=True):
        product = product @ core[:, 0 if token == -1 else 1, :]
    assert model.value(tokens) == pytest.approx(
        float(product[0, 0]),
        abs=2e-14,
        rel=0.0,
    )


def test_tt_gradient_matches_finite_difference() -> None:
    model = LocalTensorTrain.random(13, 2, seed=5)
    rng = np.random.default_rng(6)
    tokens = rng.choice(np.array([-1, 1], dtype=np.int8), size=(7, 13))
    weights = rng.normal(size=7)
    analytic = model.gradient(tokens, weights)
    core_index = 4
    index = (1, 0, 1)
    epsilon = 1.0e-6
    plus = model.copy()
    minus = model.copy()
    plus.cores[core_index][index] += epsilon
    minus.cores[core_index][index] -= epsilon
    numeric = (
        float(weights @ plus.values(tokens))
        - float(weights @ minus.values(tokens))
    ) / (2.0 * epsilon)
    assert analytic.cores[core_index][index] == pytest.approx(
        numeric,
        abs=2e-6,
        rel=0.0,
    )
    assert np.isfinite(analytic.norm())


@pytest.mark.parametrize("chi", (2, 4, 8))
def test_left_canonicalization_preserves_values(chi: int) -> None:
    model = LocalTensorTrain.random(13, chi, seed=10 + chi)
    rng = np.random.default_rng(20 + chi)
    tokens = rng.choice(np.array([-1, 1], dtype=np.int8), size=(64, 13))
    before = model.values(tokens)
    canonical = model.left_canonicalize()
    after = canonical.values(tokens)
    np.testing.assert_allclose(after, before, atol=1e-12, rtol=0.0)
    assert np.isfinite(canonical.parameter_norm)


def test_gradient_algebra_and_array_round_trip() -> None:
    model = LocalTensorTrain.random(19, 2, seed=31)
    tokens = np.ones((2, 19), dtype=np.int8)
    gradient = model.gradient(tokens, np.array([0.25, 0.75]))
    zero = gradient.add(gradient.scale(-1.0))
    assert isinstance(zero, TTGradient)
    assert zero.norm() == pytest.approx(0.0, abs=2e-15, rel=0.0)
    restored = LocalTensorTrain.from_arrays(model.save_arrays())
    np.testing.assert_array_equal(restored.values(tokens), model.values(tokens))


def test_structural_oh_and_q_inversion_symmetry() -> None:
    rng = np.random.default_rng(2026072913)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    encoder = TemplateEncoder("cube", True, 1)
    tokens = encoder.encode(q, bonds, (0, 0, 0))
    symmetric = SymmetricLocalTT(
        LocalTensorTrain.random(encoder.token_count, 4, seed=32),
        encoder,
    )
    reference = symmetric.value(tokens)
    for image in encoder.symmetry_images(tokens):
        assert symmetric.value(image) == pytest.approx(
            reference,
            abs=5e-14,
            rel=0.0,
        )
    assert symmetric.value(encoder.flip_q_tokens(tokens)) == pytest.approx(
        reference,
        abs=5e-14,
        rel=0.0,
    )


@pytest.mark.parametrize("kind", ("cube", "cross"))
def test_uniform_target_mean_matches_complete_small_q_enumeration(kind: str) -> None:
    rng = np.random.default_rng(2026072914)
    q = np.ones((3, 3, 3), dtype=np.int8)
    bonds = EABonds.sample(9, rng)
    encoder = TemplateEncoder(kind, True, 1)
    tokens = encoder.encode(q, bonds, (0, 0, 0))
    symmetric = SymmetricLocalTT(
        LocalTensorTrain.random(encoder.token_count, 2, seed=33),
        encoder,
    )
    q_indices = np.asarray(encoder.q_token_indices, dtype=np.int64)
    values = []
    for signs in itertools.product((-1, 1), repeat=encoder.q_token_count):
        sample = tokens.copy()
        sample[q_indices] = signs
        values.append(symmetric.value(sample))
    exact = float(np.mean(values, dtype=np.float64))
    assert symmetric.uniform_target_mean(tokens) == pytest.approx(
        exact,
        abs=1e-13,
        rel=0.0,
    )
    assert symmetric.centered_value(tokens) == pytest.approx(
        symmetric.value(tokens) - exact,
        abs=2e-14,
        rel=0.0,
    )
    centered = []
    for signs in itertools.product((-1, 1), repeat=encoder.q_token_count):
        sample = tokens.copy()
        sample[q_indices] = signs
        centered.append(symmetric.centered_value(sample))
    assert float(np.mean(centered, dtype=np.float64)) == pytest.approx(
        0.0,
        abs=1e-13,
        rel=0.0,
    )


def test_tt_rejects_bad_tokens_shapes_and_nonfinite_cores() -> None:
    model = LocalTensorTrain.random(13, 2, seed=34)
    with pytest.raises(ValueError, match="token"):
        model.value(np.ones(12, dtype=np.int8))
    with pytest.raises(ValueError, match=r"-1 and \+1"):
        model.value(np.zeros(13, dtype=np.int8))
    arrays = list(model.save_arrays())
    arrays[3] = arrays[3].copy()
    arrays[3][0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        LocalTensorTrain.from_arrays(arrays)
