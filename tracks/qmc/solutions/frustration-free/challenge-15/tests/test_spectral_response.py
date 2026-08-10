from __future__ import annotations

import json
import hashlib
from dataclasses import FrozenInstanceError, replace
from types import MappingProxyType

import numpy as np
import pytest
from scipy import sparse

import challenge15
import challenge15.spectral_response as spectral_response
from challenge15.angular import verify_ladder_multiplet
from challenge15.fermions import DeterminantBasis
from challenge15.oracle import solve_target_sectors
from challenge15.response_operator import ResponseFamily, build_response_family
from challenge15.spec import SphereSpec
from challenge15.spectral_response import (
    ChannelSpectrum,
    ChiralSpectrum,
    PoleGroup,
    exact_chiral_spectrum,
    exact_chiral_spectrum_for_size,
    group_degenerate_poles,
)


def test_spectral_response_stable_root_exports_preserve_identity():
    assert challenge15.PoleGroup is PoleGroup
    assert challenge15.ChannelSpectrum is ChannelSpectrum
    assert challenge15.ChiralSpectrum is ChiralSpectrum
    assert challenge15.exact_chiral_spectrum is exact_chiral_spectrum
    assert (
        challenge15.exact_chiral_spectrum_for_size
        is exact_chiral_spectrum_for_size
    )


def _rotated_block_weights(unitary: np.ndarray) -> np.ndarray:
    eigenvectors = np.eye(3, dtype=np.complex128)
    eigenvectors[:, :2] = eigenvectors[:, :2] @ unitary
    source = np.asarray([1.0 + 2.0j, -0.5 + 0.25j, 3.0j])
    return np.abs(eigenvectors.conj().T @ source) ** 2


def test_grouped_degenerate_weight_is_basis_rotation_invariant():
    energies = np.asarray([1.0, 1.0, 2.0])
    reference = group_degenerate_poles(
        energies, _rotated_block_weights(np.eye(2))
    )
    rng = np.random.default_rng(1505)

    for _ in range(8):
        matrix = rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))
        q, r = np.linalg.qr(matrix)
        phases = np.diag(r)
        unitary = q * (phases / np.abs(phases)).conj()
        actual = group_degenerate_poles(
            energies, _rotated_block_weights(unitary)
        )
        np.testing.assert_allclose(
            [pole.energy for pole in actual],
            [pole.energy for pole in reference],
            rtol=0.0,
            atol=1e-13,
        )
        np.testing.assert_allclose(
            [pole.weight for pole in actual],
            [pole.weight for pole in reference],
            rtol=0.0,
            atol=1e-13,
        )


def test_degeneracy_grouping_uses_first_energy_anchor_not_last_member():
    energies = np.asarray([1.0, 1.0 + 0.6e-10, 1.0 + 1.2e-10])
    groups = group_degenerate_poles(
        energies,
        np.asarray([2.0, 3.0, 5.0]),
        atol=1e-10,
        rtol=0.0,
    )

    assert tuple(group.member_indices for group in groups) == ((0, 1), (2,))
    assert tuple(group.degeneracy for group in groups) == (2, 1)
    np.testing.assert_allclose(
        [group.weight for group in groups], [5.0, 5.0], rtol=0.0, atol=0.0
    )


def test_degeneracy_grouping_rejects_nonfinite_group_sum():
    with np.errstate(over="ignore"):
        with pytest.raises(ValueError, match="finite"):
            group_degenerate_poles(
                np.asarray([1.0, 1.0]),
                np.asarray([np.finfo(np.float64).max] * 2),
            )


def _manual_channel_weights(oracle, family):
    ground_sector = oracle.exact_sector(0)
    excited_sector = oracle.exact_sector(2)
    ground = ground_sector.isometry @ ground_sector.eigenvectors[:, 0]
    ladder = verify_ladder_multiplet(
        DeterminantBasis.with_two_m(oracle.spec, 0),
        target_l=2,
        isometry=excited_sector.isometry,
    )
    weights = np.zeros(excited_sector.eigenvalues.shape, dtype=np.float64)
    direct = 0.0
    for component_m in range(-2, 3):
        source = np.asarray(family.components[component_m] @ ground)
        states = ladder["vectors"][2 * component_m] @ excited_sector.eigenvectors
        weights += np.abs(states.conj().T @ source) ** 2
        direct += float(np.vdot(source, source).real)
    return weights, direct


@pytest.fixture(scope="module", params=[2, 3, 4])
def exact_case(request):
    spec = SphereSpec(request.param)
    oracle = solve_target_sectors(spec)
    families = {
        helicity: build_response_family(spec, helicity)
        for helicity in ("+", "-")
    }
    return oracle, families


def test_exact_spectrum_contracts_all_five_components_and_all_l2_copies(
    exact_case,
):
    oracle, families = exact_case
    result = exact_chiral_spectrum(oracle, families)

    assert result.particles == oracle.spec.particles
    assert result.orientation == 1
    assert result.ground_energy == pytest.approx(
        oracle.exact_sector(0).eigenvalues[0], abs=1e-13
    )
    for helicity in ("+", "-"):
        manual_weights, direct = _manual_channel_weights(
            oracle, families[helicity]
        )
        channel = result.channels[helicity]
        assert sum(pole.degeneracy for pole in channel.poles) == len(
            oracle.exact_sector(2).eigenvalues
        )
        assert channel.total_weight == pytest.approx(
            float(np.sum(manual_weights)), rel=1e-12, abs=1e-14
        )
        assert channel.direct_sum_weight == pytest.approx(
            direct, rel=1e-12, abs=1e-14
        )
        assert channel.recovered_fraction >= 0.99
        assert channel.lowest_weight == channel.poles[0].weight
        assert channel.poles[0].energy == pytest.approx(
            oracle.exact_sector(2).eigenvalues[0] - result.ground_energy,
            abs=1e-13,
        )
        expected_fraction = (
            channel.lowest_weight / channel.total_weight
            if channel.total_weight > 0.0
            else 0.0
        )
        assert channel.pole_fraction == pytest.approx(
            expected_fraction, rel=1e-13, abs=1e-15
        )


def test_chiral_scalars_use_lowest_pole_helicity_weights(exact_case):
    oracle, families = exact_case
    result = exact_chiral_spectrum(oracle, families)
    minus = result.channels["-"].lowest_weight
    plus = result.channels["+"].lowest_weight

    assert result.delta_weight == pytest.approx(minus - plus, abs=1e-14)
    assert result.contrast == pytest.approx(
        (minus - plus) / (minus + plus), abs=1e-14
    )


def _assert_spectra_equal(actual, expected):
    assert actual.particles == expected.particles
    assert actual.orientation == expected.orientation
    assert actual.ground_energy == expected.ground_energy
    assert actual.delta_weight == pytest.approx(expected.delta_weight, abs=1e-14)
    assert actual.contrast == pytest.approx(expected.contrast, abs=1e-14)
    for helicity in ("+", "-"):
        actual_channel = actual.channels[helicity]
        expected_channel = expected.channels[helicity]
        np.testing.assert_allclose(
            [
                actual_channel.total_weight,
                actual_channel.direct_sum_weight,
                actual_channel.recovered_fraction,
                actual_channel.lowest_weight,
                actual_channel.pole_fraction,
            ],
            [
                expected_channel.total_weight,
                expected_channel.direct_sum_weight,
                expected_channel.recovered_fraction,
                expected_channel.lowest_weight,
                expected_channel.pole_fraction,
            ],
            rtol=1e-13,
            atol=1e-14,
        )
        np.testing.assert_allclose(
            [pole.weight for pole in actual_channel.poles],
            [pole.weight for pole in expected_channel.poles],
            rtol=1e-13,
            atol=1e-14,
        )


def test_supplied_coefficients_are_scale_and_global_phase_invariant(exact_case):
    oracle, families = exact_case
    ground = oracle.exact_sector(0).eigenvectors[:, 0]
    reference = exact_chiral_spectrum(
        oracle, families, initial_sector_coefficients=ground
    )

    scaled = exact_chiral_spectrum(
        oracle,
        families,
        initial_sector_coefficients=ground * (17.0 - 9.0j),
    )
    huge = exact_chiral_spectrum(
        oracle,
        families,
        initial_sector_coefficients=ground * (1e308 + 0.0j),
    )

    _assert_spectra_equal(scaled, reference)
    _assert_spectra_equal(huge, reference)


@pytest.mark.parametrize(
    "coefficients",
    [
        np.asarray([0.0j]),
        np.asarray([np.nan + 0.0j]),
        np.asarray([np.inf + 0.0j]),
        np.asarray([[1.0 + 0.0j]]),
        np.asarray([1.0 + 0.0j, 0.0j]),
    ],
)
def test_invalid_supplied_coefficients_are_rejected(coefficients):
    spec = SphereSpec(2)
    oracle = solve_target_sectors(spec)
    families = {
        helicity: build_response_family(spec, helicity)
        for helicity in ("+", "-")
    }

    with pytest.raises(ValueError, match="coefficients"):
        exact_chiral_spectrum(
            oracle,
            families,
            initial_sector_coefficients=coefficients,
        )


def test_spectral_outputs_are_immutable(exact_case):
    oracle, families = exact_case
    result = exact_chiral_spectrum(oracle, families)

    with pytest.raises(TypeError):
        result.channels["+"] = result.channels["-"]
    with pytest.raises(FrozenInstanceError):
        result.delta_weight = 0.0
    with pytest.raises(FrozenInstanceError):
        result.channels["+"].total_weight = 0.0
    with pytest.raises(FrozenInstanceError):
        result.channels["+"].poles[0].weight = 0.0


def test_nonfinite_contraction_weights_fail_closed():
    spec = SphereSpec(2)
    oracle = solve_target_sectors(spec)
    families = {
        helicity: build_response_family(spec, helicity)
        for helicity in ("+", "-")
    }
    overflowing = families["-"]
    families["-"] = ResponseFamily(
        spec=spec,
        orientation=1,
        helicity="-",
        components={
            component_m: operator * np.finfo(np.float64).max
            for component_m, operator in overflowing.components.items()
        },
    )

    with np.errstate(over="ignore", invalid="ignore"):
        with pytest.raises(ArithmeticError, match="finite"):
            exact_chiral_spectrum(oracle, families)


def test_noncanonical_zero_sources_fail_operator_gates_before_contraction():
    spec = SphereSpec(2)
    oracle = solve_target_sectors(spec)
    families = {}
    for helicity in ("+", "-"):
        template = build_response_family(spec, helicity)
        families[helicity] = ResponseFamily(
            spec=spec,
            orientation=1,
            helicity=helicity,
            components={
                component_m: sparse.csr_matrix(operator.shape)
                for component_m, operator in template.components.items()
            },
        )

    with pytest.raises(ArithmeticError, match="tensor-commutator"):
        exact_chiral_spectrum(
            oracle,
            MappingProxyType(families),
            contrast_floor=1e-14,
        )


def _routing_result(particles):
    channels = {
        helicity: ChannelSpectrum(
            helicity=helicity,
            component_weights=MappingProxyType(
                {component: (2.0 if helicity == "-" else 1.0) / 5.0
                 for component in range(-2, 3)}
            ),
            poles=(
                PoleGroup(
                    energy=0.5,
                    degeneracy=1,
                    member_indices=(0,),
                    member_weights=(2.0 if helicity == "-" else 1.0,),
                    weight=2.0 if helicity == "-" else 1.0,
                ),
            ),
            total_weight=2.0 if helicity == "-" else 1.0,
            direct_sum_weight=2.0 if helicity == "-" else 1.0,
            recovered_fraction=1.0,
            lowest_weight=2.0 if helicity == "-" else 1.0,
            pole_fraction=1.0,
        )
        for helicity in ("+", "-")
    }
    return ChiralSpectrum(
        particles=particles,
        orientation=1,
        ground_energy=-1.0,
        channels=channels,
        delta_weight=1.0,
        contrast=1.0 / 3.0,
        contrast_floor=1e-14,
        tensor_commutator_residual_max=0.0,
        adjoint_residual=0.0,
        reversal_residual_max=0.0,
        eigenpair_residual_max=0.0,
    )


@pytest.mark.parametrize("particles", range(2, 5))
def test_exact_chiral_size_routes_small_sizes_to_dense_solver(
    monkeypatch, particles
):
    calls = []
    sentinel = _routing_result(particles)

    monkeypatch.setattr(
        spectral_response,
        "solve_target_sectors",
        lambda spec: calls.append(("dense", spec.particles)) or spec,
    )
    monkeypatch.setattr(
        spectral_response,
        "solve_required_target_sectors_sparse",
        lambda spec: pytest.fail("small sizes must not use sparse solver"),
    )
    monkeypatch.setattr(
        spectral_response,
        "build_response_family",
        lambda spec, helicity: (spec, helicity),
    )
    monkeypatch.setattr(
        spectral_response,
        "exact_chiral_spectrum",
        lambda oracle, families: (
            calls.append(("contract", tuple(families))) or sentinel
        ),
    )
    monkeypatch.setattr(
        spectral_response,
        "oracle_cache_payload",
        lambda oracle: {"particles": oracle.particles},
    )
    monkeypatch.setattr(
        spectral_response,
        "oracle_from_cache_payload",
        lambda payload: calls.append(("verify-cache", payload["particles"]))
        or object(),
    )

    result = exact_chiral_spectrum_for_size(particles)
    assert result.particles == sentinel.particles
    assert result.oracle_cache_sha256 == hashlib.sha256(
        json.dumps(
            {"particles": particles},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    assert calls == [
        ("dense", particles),
        ("contract", ("+", "-")),
        ("verify-cache", particles),
    ]


@pytest.mark.parametrize("particles", range(5, 9))
def test_exact_chiral_size_routing_uses_sparse_solver_without_large_solve(
    monkeypatch, particles
):
    calls = []
    sentinel = _routing_result(particles)

    monkeypatch.setattr(
        spectral_response,
        "solve_target_sectors",
        lambda spec: pytest.fail("large sizes must not use dense solver"),
    )
    monkeypatch.setattr(
        spectral_response,
        "solve_required_target_sectors_sparse",
        lambda spec: calls.append(("sparse", spec.particles)) or spec,
    )
    monkeypatch.setattr(
        spectral_response,
        "build_response_family",
        lambda spec, helicity: (spec, helicity),
    )
    monkeypatch.setattr(
        spectral_response,
        "exact_chiral_spectrum",
        lambda oracle, families: (
            calls.append(("contract", tuple(families))) or sentinel
        ),
    )
    monkeypatch.setattr(
        spectral_response,
        "oracle_cache_payload",
        lambda oracle: {"particles": oracle.particles},
    )
    monkeypatch.setattr(
        spectral_response,
        "oracle_from_cache_payload",
        lambda payload: calls.append(("verify-cache", payload["particles"]))
        or object(),
    )

    result = exact_chiral_spectrum_for_size(particles)

    assert result.particles == sentinel.particles
    assert result.to_payload()["schema"] == "challenge15.chiral-spectrum.v1"
    assert calls == [
        ("sparse", particles),
        ("contract", ("+", "-")),
        ("verify-cache", particles),
    ]


@pytest.mark.parametrize("particles", [1, 9])
def test_exact_chiral_size_rejects_values_outside_supported_interval(particles):
    with pytest.raises(
        ValueError,
        match=r"^exact chiral response requires 2 <= particles <= 8$",
    ):
        exact_chiral_spectrum_for_size(particles)


@pytest.mark.slow
@pytest.mark.parametrize("particles", range(2, 9))
def test_exact_chiral_spectrum_n2_through_n8(particles):
    result = exact_chiral_spectrum_for_size(particles)
    assert set(result.channels) == {"+", "-"}
    assert all(c.recovered_fraction >= 0.99 for c in result.channels.values())


def test_chiral_payload_is_deterministic_strict_json_and_complete(exact_case):
    oracle, families = exact_case
    result = exact_chiral_spectrum(oracle, families)

    payload = result.to_payload()
    encoded = json.dumps(
        payload,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    assert encoded == json.dumps(
        result.to_payload(),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert payload["schema"] == "challenge15.chiral-spectrum.v1"
    assert payload["particles"] == oracle.spec.particles
    assert payload["orientation"] == 1
    assert payload["units"] == {
        "energies": "E_C",
        "raw_weights": "E_C^2",
        "pole_fractions": "dimensionless",
    }
    assert (
        payload["source_normalization"]
        == "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6"
    )
    assert payload["tolerances"] == {
        "tensor_commutator": 1e-10,
        "adjoint": 1e-12,
        "eigenpair": 1e-10,
        "degeneracy_absolute_E_C": 1e-10,
        "degeneracy_relative": 1e-9,
        "contrast_denominator_floor": 1e-14,
        "recovered_sum_rule_fraction_min": 0.99,
        "monopole_reversal": 1e-12,
    }
    for helicity in ("+", "-"):
        channel = result.channels[helicity]
        serialized = payload["channels"][helicity]
        assert serialized["raw_total_weight_E_C2"] == channel.total_weight
        assert (
            serialized["sum_rule"]["direct_sum_weight_E_C2"]
            == channel.direct_sum_weight
        )
        assert (
            serialized["sum_rule"]["recovered_fraction"]
            == channel.recovered_fraction
        )
        assert serialized["sum_rule"]["passed"] is (
            channel.recovered_fraction >= 0.99
        )
        assert [pole["member_indices"] for pole in serialized["poles"]] == [
            list(pole.member_indices) for pole in channel.poles
        ]
        np.testing.assert_allclose(
            [pole["normalized_fraction"] for pole in serialized["poles"]],
            [
                pole.weight / channel.total_weight
                if channel.total_weight > 0.0
                else 0.0
                for pole in channel.poles
            ],
            rtol=0.0,
            atol=0.0,
        )
    assert payload["chirality_resolved"] is (
        result.contrast is not None
        and result.delta_weight > 0.0
        and payload["diagnostics"]["monopole_reversal"]["passed"]
    )


def test_chiral_payload_fail_closed_resolution_and_null_contrast():
    base = _routing_result(2)

    no_contrast = replace(base, contrast=None, delta_weight=0.0)
    assert no_contrast.to_payload()["contrast"] is None
    assert no_contrast.to_payload()["chirality_resolved"] is False

    negative_delta = replace(base, delta_weight=-1.0)
    assert negative_delta.to_payload()["chirality_resolved"] is False

    failed_reversal = replace(base, reversal_residual_max=2e-12)
    assert failed_reversal.to_payload()["diagnostics"]["monopole_reversal"] == {
        "residual_max": 2e-12,
        "tolerance": 1e-12,
        "passed": False,
    }
    assert failed_reversal.to_payload()["chirality_resolved"] is False
