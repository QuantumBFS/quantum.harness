from __future__ import annotations

from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from challenge15.carriers import (
    carrier_amplitudes as jax_carrier_amplitudes,
)
from challenge15.spec import SphereSpec
from challenge15.torch_carriers import (
    batched_carrier_amplitudes,
    carrier_amplitudes,
    raw_north_lll_polynomials,
)

jax.config.update("jax_enable_x64", True)

RTOL = 2e-10
ATOL = 2e-11
MODULE_PATH = (
    Path(__file__).parents[1] / "src" / "challenge15" / "torch_carriers.py"
)
FROZEN_VALUES = {
    2: -35.83404052038025 - 35.34710205528693j,
    3: -315693304.00782686 - 1020505469.0776263j,
    4: 8.205793747237146e21 - 2.7973025055084867e22j,
}
FROZEN_FIRST_ORBITALS = {
    2: np.asarray(
        [
            4.378111168330588 + 1.349541483846233j,
            3.8110995928427753 + 1.0719939111150065j,
            1.9141003403796888 + 0.4875031562511384j,
            0.5546688843253879 + 0.12670463881768598j,
        ],
        dtype=np.complex128,
    ),
    3: np.asarray(
        [
            13.32394094476311 + 53.768316082717526j,
            10.399968089977339 + 68.81596575554278j,
            3.219743586405155 + 56.351471910013814j,
            -1.1979539883542267 + 33.40822606741591j,
            -1.9067507400792543 + 14.726618131092724j,
            -1.0591372588198653 + 4.699306989574963j,
            -0.3121275287724035 + 0.9592071829202552j,
        ],
        dtype=np.complex128,
    ),
    4: np.asarray(
        [
            -763.4795763070094 + 85.49741712940082j,
            -1251.269612329056 - 92.31064455552473j,
            -1320.5503133944635 - 349.5980619566698j,
            -1025.8243682965979 - 487.9089043544871j,
            -612.3680816795116 - 445.6604116000798j,
            -282.99936102783755 - 299.83625292315634j,
            -99.10334560372897 - 154.1535197853026j,
            -24.60079199573714 - 60.50083767293374j,
            -3.5498915163628384 - 17.419111236893656j,
            -0.0512260067898718 - 3.22545404075726j,
        ],
        dtype=np.complex128,
    ),
}


def _parity_case(
    particles: int,
) -> tuple[np.ndarray, np.ndarray, np.complex128]:
    spec = SphereSpec(particles)
    base = np.arange(1, 2 * particles + 1, dtype=np.float64).reshape(
        particles, 2
    )
    spinors = np.asarray(
        base + 1j * (base[::-1] * 0.125 - 0.3), dtype=np.complex128
    )
    channel_count = sum(two_m > 0 for two_m in spec.two_m_values)
    channels = np.arange(1, channel_count + 1)
    weights = np.asarray(
        channels * (0.3 + 0.2j)
        + np.arange(channel_count)[::-1] * (-0.1 + 0.05j),
        dtype=np.complex128,
    )
    return spinors, weights, np.complex128(-0.7 + 0.4j)


def _random_case(
    particles: int, seed: int
) -> tuple[np.ndarray, np.ndarray, np.complex128]:
    spec = SphereSpec(particles)
    rng = np.random.default_rng(seed)
    spinors = np.asarray(
        rng.normal(size=(particles, 2))
        + 1j * rng.normal(size=(particles, 2)),
        dtype=np.complex128,
    )
    channel_count = sum(two_m > 0 for two_m in spec.two_m_values)
    weights = np.asarray(
        rng.normal(size=channel_count) + 1j * rng.normal(size=channel_count),
        dtype=np.complex128,
    )
    border = np.complex128(rng.normal() + 1j * rng.normal())
    return spinors, weights, border


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_raw_orbitals_and_carrier_match_frozen_jax_values(particles):
    spec = SphereSpec(particles)
    spinors, weights, border = _parity_case(particles)
    torch_spinors = torch.tensor(spinors, dtype=torch.complex128)

    orbitals = raw_north_lll_polynomials(torch_spinors, spec)
    amplitude = carrier_amplitudes(
        torch_spinors,
        spec,
        torch.tensor(weights, dtype=torch.complex128),
        torch.tensor(border, dtype=torch.complex128),
    )

    assert orbitals.shape == (particles, spec.orbital_count)
    assert orbitals.dtype == torch.complex128
    assert amplitude.shape == torch.Size([])
    np.testing.assert_allclose(
        orbitals[0].detach().numpy(),
        FROZEN_FIRST_ORBITALS[particles],
        rtol=RTOL,
        atol=ATOL,
    )
    np.testing.assert_allclose(
        amplitude.detach().numpy(),
        FROZEN_VALUES[particles],
        rtol=RTOL,
        atol=ATOL,
    )


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_carrier_matches_live_jax_oracle_and_exchange_sign(particles):
    spec = SphereSpec(particles)
    spinors, weights, border = _random_case(particles, 100 + particles)
    actual = carrier_amplitudes(
        torch.tensor(spinors),
        spec,
        torch.tensor(weights),
        torch.tensor(border),
    )
    expected = jax_carrier_amplitudes(
        jnp.asarray(spinors), spec, jnp.asarray(weights), border
    )
    np.testing.assert_allclose(
        actual.detach().numpy(), expected, rtol=RTOL, atol=ATOL
    )

    exchanged = spinors.copy()
    exchanged[[0, 1]] = exchanged[[1, 0]]
    exchanged_value = carrier_amplitudes(
        torch.tensor(exchanged),
        spec,
        torch.tensor(weights),
        torch.tensor(border),
    )
    np.testing.assert_allclose(
        exchanged_value.detach().numpy(),
        -actual.detach().numpy(),
        rtol=RTOL,
        atol=ATOL,
    )


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_each_particle_has_exact_nonunit_holomorphic_degree(particles):
    spec = SphereSpec(particles)
    spinors, weights, border = _random_case(particles, 200 + particles)
    scale = -0.73 + 0.41j
    baseline = carrier_amplitudes(
        torch.tensor(spinors), spec, torch.tensor(weights), border
    )
    scaled = spinors.copy()
    scaled[1] *= scale
    transformed = carrier_amplitudes(
        torch.tensor(scaled), spec, torch.tensor(weights), border
    )
    np.testing.assert_allclose(
        transformed.detach().numpy(),
        scale**spec.two_q * baseline.detach().numpy(),
        rtol=RTOL,
        atol=ATOL,
    )


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_spinor_jvp_is_complex_linear(particles):
    spec = SphereSpec(particles)
    spinors, weights, border = _random_case(particles, 300 + particles)
    tangent, _, _ = _random_case(particles, 400 + particles)
    spinors_tensor = torch.tensor(spinors)
    tangent_tensor = torch.tensor(tangent)
    weights_tensor = torch.tensor(weights)

    def evaluate(value):
        return carrier_amplitudes(value, spec, weights_tensor, border)

    _, real_direction = torch.func.jvp(
        evaluate, (spinors_tensor,), (tangent_tensor,)
    )
    _, imaginary_direction = torch.func.jvp(
        evaluate, (spinors_tensor,), (1j * tangent_tensor,)
    )
    np.testing.assert_allclose(
        imaginary_direction.detach().numpy(),
        1j * real_direction.detach().numpy(),
        rtol=RTOL,
        atol=ATOL,
    )


def test_odd_border_is_zero_orbital_in_final_column_with_correct_sign():
    spec = SphereSpec(3)
    spinors, weights, border_weight = _random_case(3, 503)
    orbitals = raw_north_lll_polynomials(torch.tensor(spinors), spec)
    positive = [index for index, value in enumerate(spec.two_m_values) if value > 0]
    negative = [
        spec.two_m_values.index(-spec.two_m_values[index]) for index in positive
    ]
    positive_values = orbitals[:, positive]
    negative_values = orbitals[:, negative]
    forward = torch.einsum(
        "ik,k,jk->ij", positive_values, torch.tensor(weights), negative_values
    )
    pair_matrix = forward - forward.T
    border = border_weight * orbitals[:, spec.two_m_values.index(0)]
    expected = (
        pair_matrix[0, 1] * border[2]
        - pair_matrix[0, 2] * border[1]
        + border[0] * pair_matrix[1, 2]
    )

    actual = carrier_amplitudes(
        torch.tensor(spinors), spec, torch.tensor(weights), border_weight
    )

    torch.testing.assert_close(actual, expected, rtol=RTOL, atol=ATOL)
    torch.testing.assert_close(
        carrier_amplitudes(
            torch.tensor(spinors), spec, torch.tensor(weights), -border_weight
        ),
        -actual,
        rtol=RTOL,
        atol=ATOL,
    )


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_zero_and_singular_weights_return_exact_zero(particles):
    spec = SphereSpec(particles)
    spinors, weights, _ = _random_case(particles, 600 + particles)
    zeros = torch.zeros_like(torch.tensor(weights))
    border = 0.0 if particles % 2 else 1.0

    actual = carrier_amplitudes(torch.tensor(spinors), spec, zeros, border)

    assert actual.dtype == torch.complex128
    assert actual.item() == 0j


def test_real_and_complex_weight_semantics_preserve_complex128():
    spec = SphereSpec(3)
    spinors, _, _ = _random_case(3, 703)
    real_weights = torch.tensor([0.5, -1.25, 0.75], dtype=torch.float64)
    complex_weights = real_weights.to(torch.complex128)

    real_result = carrier_amplitudes(
        torch.tensor(spinors), spec, real_weights, border_weight=2.0
    )
    complex_result = carrier_amplitudes(
        torch.tensor(spinors),
        spec,
        complex_weights,
        border_weight=torch.tensor(2.0 + 0.0j, dtype=torch.complex128),
    )

    assert real_result.dtype == torch.complex128
    torch.testing.assert_close(real_result, complex_result, rtol=0.0, atol=0.0)


def test_carrier_bank_and_walker_batch_have_exact_jax_shapes_and_values():
    spec = SphereSpec(3)
    first_spinors, first_weights, first_border = _random_case(3, 801)
    second_spinors, _, _ = _random_case(3, 802)
    weights = np.stack(
        (
            first_weights,
            (0.25 - 0.5j) * first_weights,
            np.zeros_like(first_weights),
        )
    )
    borders = np.asarray(
        [first_border, -0.3 + 0.7j, 2.0], dtype=np.complex128
    )
    walkers = np.stack((first_spinors, second_spinors))

    single_bank = carrier_amplitudes(
        torch.tensor(first_spinors),
        spec,
        torch.tensor(weights),
        torch.tensor(borders),
    )
    batched = batched_carrier_amplitudes(
        torch.tensor(walkers),
        spec,
        torch.tensor(weights),
        torch.tensor(borders),
    )
    expected = np.stack(
        [
            np.asarray(
                jax_carrier_amplitudes(
                    jnp.asarray(walker),
                    spec,
                    jnp.asarray(weights),
                    jnp.asarray(borders),
                )
            )
            for walker in walkers
        ]
    )

    assert single_bank.shape == (3,)
    assert batched.shape == (2, 3)
    np.testing.assert_allclose(
        single_bank.detach().numpy(), expected[0], rtol=RTOL, atol=ATOL
    )
    np.testing.assert_allclose(
        batched.detach().numpy(), expected, rtol=RTOL, atol=ATOL
    )


def test_scalar_border_broadcasts_over_carriers_and_walkers():
    spec = SphereSpec(3)
    first_spinors, weights, _ = _random_case(3, 901)
    second_spinors, _, _ = _random_case(3, 902)
    carrier_weights = torch.stack(
        (torch.tensor(weights), 2.0 * torch.tensor(weights))
    )
    walkers = torch.tensor(np.stack((first_spinors, second_spinors)))

    actual = batched_carrier_amplitudes(
        walkers, spec, carrier_weights, border_weight=-0.2 + 0.9j
    )
    expected = torch.stack(
        [
            torch.stack(
                [
                    carrier_amplitudes(
                        walker, spec, weight, border_weight=-0.2 + 0.9j
                    )
                    for weight in carrier_weights
                ]
            )
            for walker in walkers
        ]
    )

    torch.testing.assert_close(actual, expected, rtol=RTOL, atol=ATOL)


def test_noncontiguous_spinors_weights_and_borders_are_supported():
    spec = SphereSpec(3)
    spinors, weights, border = _random_case(3, 1003)
    spinor_storage = torch.empty((3, 4), dtype=torch.complex128)
    spinor_storage[:, ::2] = torch.tensor(spinors)
    noncontiguous_spinors = spinor_storage[:, ::2]
    weight_storage = torch.empty((2, 6), dtype=torch.complex128)
    weight_storage[:, ::2] = torch.stack(
        (torch.tensor(weights), 0.4j * torch.tensor(weights))
    )
    noncontiguous_weights = weight_storage[:, ::2]
    border_storage = torch.tensor(
        [border, 0.0, -border, 0.0], dtype=torch.complex128
    )
    noncontiguous_borders = border_storage[::2]
    assert not noncontiguous_spinors.is_contiguous()
    assert not noncontiguous_weights.is_contiguous()
    assert not noncontiguous_borders.is_contiguous()

    actual = carrier_amplitudes(
        noncontiguous_spinors,
        spec,
        noncontiguous_weights,
        noncontiguous_borders,
    )
    expected = carrier_amplitudes(
        noncontiguous_spinors.contiguous(),
        spec,
        noncontiguous_weights.contiguous(),
        noncontiguous_borders.contiguous(),
    )

    torch.testing.assert_close(actual, expected, rtol=0.0, atol=0.0)


def test_outputs_and_orbital_table_materialization_follow_input_device():
    spec = SphereSpec(2)
    spinors, weights, _ = _random_case(2, 1102)
    input_tensor = torch.tensor(spinors)

    orbitals = raw_north_lll_polynomials(input_tensor, spec)
    amplitude = carrier_amplitudes(
        input_tensor, spec, torch.tensor(weights), border_weight=1.0
    )

    assert orbitals.device == input_tensor.device
    assert amplitude.device == input_tensor.device


@pytest.mark.parametrize(
    ("function", "spinors", "message"),
    [
        (
            raw_north_lll_polynomials,
            np.ones((2, 2), dtype=np.complex128),
            "torch.Tensor",
        ),
        (
            raw_north_lll_polynomials,
            torch.ones((2, 2), dtype=torch.complex64),
            "complex128",
        ),
        (
            raw_north_lll_polynomials,
            torch.ones((2, 3), dtype=torch.complex128),
            "last axis",
        ),
        (
            carrier_amplitudes,
            torch.ones((1, 2, 2), dtype=torch.complex128),
            "shape",
        ),
        (
            batched_carrier_amplitudes,
            torch.ones((2, 2), dtype=torch.complex128),
            "shape",
        ),
    ],
)
def test_spinor_dtype_and_shape_validation(function, spinors, message):
    spec = SphereSpec(2)
    weights = torch.ones((1, 2), dtype=torch.complex128)
    if function is raw_north_lll_polynomials:
        with pytest.raises((TypeError, ValueError), match=message):
            function(spinors, spec)
    else:
        with pytest.raises((TypeError, ValueError), match=message):
            function(spinors, spec, weights)


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        (np.ones(2, dtype=np.complex128), "torch.Tensor"),
        (torch.ones(2, dtype=torch.complex64), "float64 or complex128"),
        (torch.ones(2, dtype=torch.int64), "float64 or complex128"),
        (torch.ones((2, 2, 2), dtype=torch.complex128), "one or two dimensions"),
        (torch.ones(1, dtype=torch.complex128), "positive-m channel"),
    ],
)
def test_pair_weight_dtype_and_shape_validation(weights, message):
    spec = SphereSpec(3)
    spinors, _, _ = _random_case(3, 1203)
    with pytest.raises((TypeError, ValueError), match=message):
        carrier_amplitudes(torch.tensor(spinors), spec, weights)


@pytest.mark.parametrize(
    ("border", "message"),
    [
        (torch.ones(2, dtype=torch.float32), "float64 or complex128"),
        (torch.ones((2, 1), dtype=torch.complex128), "scalar or have one entry"),
        (torch.ones(3, dtype=torch.complex128), "scalar or have one entry"),
    ],
)
def test_border_dtype_and_shape_validation(border, message):
    spec = SphereSpec(3)
    spinors, weights, _ = _random_case(3, 1303)
    carrier_weights = torch.stack(
        (torch.tensor(weights), 2.0 * torch.tensor(weights))
    )
    with pytest.raises((TypeError, ValueError), match=message):
        carrier_amplitudes(
            torch.tensor(spinors), spec, carrier_weights, border_weight=border
        )


def test_batched_api_requires_leading_carrier_axis():
    spec = SphereSpec(3)
    spinors, weights, _ = _random_case(3, 1403)
    walkers = torch.tensor(np.stack((spinors, spinors)))
    with pytest.raises(ValueError, match="leading carrier axis"):
        batched_carrier_amplitudes(walkers, spec, torch.tensor(weights))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA-compatible device")
def test_device_mismatch_is_rejected_when_accelerator_is_available():
    spec = SphereSpec(2)
    spinors, weights, _ = _random_case(2, 1502)
    with pytest.raises(ValueError, match="same device"):
        carrier_amplitudes(
            torch.tensor(spinors, device="cuda"),
            spec,
            torch.tensor(weights, device="cpu"),
        )


def test_production_module_has_no_jax_import():
    source = MODULE_PATH.read_text()
    assert "import jax" not in source
    assert "from jax" not in source
