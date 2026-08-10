import hashlib
import json
import re
from dataclasses import fields
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import expm
from scipy.special import eval_genlaguerre
from sympy import Rational
from sympy.physics.wigner import clebsch_gordan

import challenge15
from challenge15.chiral_source import (
    PairReducedSource,
    _minus_pair_source_tensor,
    lhyr_pair_reduced_source,
    pair_source_tensor,
    planar_coulomb_reduced_amplitudes,
)
from challenge15.coulomb import orbital_coulomb_tensor
from challenge15.spec import SphereSpec


FIXTURE_PATH = (
    Path(__file__).with_name("fixtures") / "chiral_covariant_pair_large_q.json"
)
ROOT_KEYS = {"schema", "definition", "cases"}
CASE_KEYS = {
    "two_q",
    "orientation",
    "spatial_geometry",
    "spatial_metric_varied",
    "area_varied",
    "chord_coulomb_varied",
    "source_definition",
    "metric_coordinates",
    "landau_level_derivative_used",
    "relative_m",
    "minus",
    "plus",
    "selected_minus_family",
    "diagnostics",
    "payload_sha256",
}
DIRECTION_KEYS = {
    "direction",
    "raw_values_E_C",
    "raw_euclidean_norm_E_C",
    "normalized_values",
}
DECIMAL_PATTERN = re.compile(
    r"(?:0e\+0|-?[1-9]\.\d{69}e[+-](?:0|[1-9]\d*))\Z"
)


def test_chiral_source_stable_root_exports_preserve_identity():
    assert challenge15.PairReducedSource is PairReducedSource
    assert challenge15.lhyr_pair_reduced_source is lhyr_pair_reduced_source


def test_chiral_internal_helpers_remain_module_qualified():
    for name in (
        "planar_coulomb_reduced_amplitudes",
        "pair_source_tensor",
        "tensor_commutator_residuals",
        "adjoint_residual",
        "monopole_reversal_matrix",
        "monopole_reversal_residual",
        "group_degenerate_poles",
        "validate_response_families",
        "_response_payload",
    ):
        assert name not in challenge15.__all__
        assert not hasattr(challenge15, name)


def test_design_section_10_fixed_claim_boundary_and_implementation_status():
    design = Path(__file__).parents[1].joinpath("DESIGN.md").read_text(
        encoding="utf-8"
    )
    section_10 = design.split(
        "## 10. Chiral LHYR-response extension", maxsplit=1
    )[1].split("## 11. Scaling policy", maxsplit=1)[0]

    for required in (
        "round spatial sphere",
        "Coulomb chord",
        "Wigner–Eckart covariantization",
        "|r+2⟩ -> |r⟩",
        "σ=±",
        "M=-2,...,2",
        "forbids claiming",
    ):
        assert required in section_10

    for required in (
        "### 10.1 Implementation status and bounded runbook",
        "challenge15.cli response --particles",
        "challenge15.cli response --oracle",
        "--generation",
        "--checkpoint",
        "--rank",
        "--seed",
        "DIR/response.json",
        "challenge15.chiral-response.v1",
        "2 <= N <= 8",
        "mixed estimator",
        "NQS `L=0` initial state",
        "exact ED `L=2` final states",
        "1e-10",
        "1e-12",
        "recovered_fraction>=0.99",
        "approved compute infrastructure",
        "for n in 2 3 4 5 6 7 8; do",
    ):
        assert required in section_10


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_fixture():
    return json.loads(
        FIXTURE_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON constant: {value}")
        ),
    )


def _assert_canonical_decimal(value):
    assert isinstance(value, str)
    assert DECIMAL_PATTERN.fullmatch(value), value
    assert not value.startswith("-0")
    assert Decimal(value).is_finite()


def _complex_pairs(values):
    return [(Decimal(real), Decimal(imaginary)) for real, imaginary in values]


def test_large_q_fixture_fixes_minus_as_m_plus_two_to_m():
    fixture = _load_fixture()
    assert fixture["schema"] == (
        "challenge15.chiral-covariant-pair-fixture.v1"
    )
    assert [case["two_q"] for case in fixture["cases"]] == [15, 31, 63]
    for case in fixture["cases"]:
        assert case["selected_minus_family"] == "m_plus_2_to_m"
        assert case["minus"]["direction"] == "m_plus_2_to_m"
        assert case["plus"]["direction"] == "m_to_m_plus_2"
        assert case["orientation"] == {
            "sphere": "outward",
            "electron_charge": "-e",
            "monopole_sign": 1,
        }
        assert case["spatial_metric_varied"] is False
        assert case["area_varied"] is False
        assert case["chord_coulomb_varied"] is False
        assert case["landau_level_derivative_used"] is False


def test_fixture_has_exact_schema_and_physical_convention():
    fixture = _load_fixture()
    assert set(fixture) == ROOT_KEYS
    assert fixture["definition"] == {
        "convention_document": (
            ".superpowers/sdd/chiral-microscopic-source-resolution.md"
        ),
        "oracle": (
            "planar-lhyr-coulomb-source-wigner-eckart-covariantization"
        ),
        "curved_sphere_effective_mass_claim": False,
        "energy_unit": "E_C",
        "relative_m_order": "ascending-positive-odd",
        "global_components": [-2, -1, 0, 1, 2],
    }
    for case in fixture["cases"]:
        assert set(case) == CASE_KEYS
        assert set(case["minus"]) == DIRECTION_KEYS
        assert set(case["plus"]) == DIRECTION_KEYS
        assert case["spatial_geometry"] == "fixed-round-sphere"
        assert case["source_definition"] == "equations-5.1-through-6.3"
        assert case["metric_coordinates"] == {
            "inverse_mass_linearization": "[[1+h1,h2],[h2,1-h1]]",
            "h_plus": "h1+i*h2",
            "h_minus": "h1-i*h2",
            "curved_sphere_metric_used": False,
        }
        assert case["diagnostics"]["formula"] == "gamma-finite-sum-5.6"
        assert case["diagnostics"]["first_nonzero_normalized_positive_real"] is True


def test_fixture_relative_m_and_decimal_vectors_are_canonical():
    fixture = _load_fixture()
    for case in fixture["cases"]:
        expected_relative_m = list(range(1, case["two_q"] - 1, 2))
        assert case["relative_m"] == expected_relative_m
        assert all(relative_m + 2 <= case["two_q"] for relative_m in expected_relative_m)
        for family_name in ("minus", "plus"):
            family = case[family_name]
            assert len(family["raw_values_E_C"]) == len(expected_relative_m)
            assert len(family["normalized_values"]) == len(expected_relative_m)
            _assert_canonical_decimal(family["raw_euclidean_norm_E_C"])
            for pair in family["raw_values_E_C"] + family["normalized_values"]:
                assert isinstance(pair, list) and len(pair) == 2
                _assert_canonical_decimal(pair[0])
                _assert_canonical_decimal(pair[1])
        _assert_canonical_decimal(case["diagnostics"]["adjoint_residual"])


def test_fixture_raw_norms_normalization_and_adjoint_are_consistent():
    fixture = _load_fixture()
    with localcontext() as context:
        context.prec = 100
        for case in fixture["cases"]:
            minus_raw = _complex_pairs(case["minus"]["raw_values_E_C"])
            plus_raw = _complex_pairs(case["plus"]["raw_values_E_C"])
            assert minus_raw == plus_raw
            assert all(real > 0 and imaginary == 0 for real, imaginary in minus_raw)

            raw_norm = sum(
                real * real + imaginary * imaginary
                for real, imaginary in minus_raw
            ).sqrt()
            recorded_norm = Decimal(case["minus"]["raw_euclidean_norm_E_C"])
            assert recorded_norm == Decimal(case["plus"]["raw_euclidean_norm_E_C"])
            assert abs(raw_norm - recorded_norm) <= Decimal("1e-69")

            for family_name in ("minus", "plus"):
                normalized = _complex_pairs(
                    case[family_name]["normalized_values"]
                )
                norm_squared = sum(
                    real * real + imaginary * imaginary
                    for real, imaginary in normalized
                )
                assert abs(norm_squared - Decimal(1)) <= Decimal("1e-30")
                assert normalized[0][0] > 0
                assert normalized[0][1] == 0
            assert case["minus"]["normalized_values"] == case["plus"][
                "normalized_values"
            ]
            assert Decimal(case["diagnostics"]["adjoint_residual"]) == 0


def test_fixture_case_digests_and_terminal_newline_are_canonical():
    raw_root = FIXTURE_PATH.read_bytes()
    assert raw_root.endswith(b"\n")
    assert not raw_root.endswith(b"\n\n")
    assert b"\r" not in raw_root
    fixture = _load_fixture()
    canonical_root = json.dumps(
        fixture,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    assert raw_root == canonical_root

    for case in fixture["cases"]:
        assert re.fullmatch(r"[0-9a-f]{64}", case["payload_sha256"])
        unsigned_case = {
            key: value for key, value in case.items() if key != "payload_sha256"
        }
        canonical_case = json.dumps(
            unsigned_case,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        assert hashlib.sha256(canonical_case).hexdigest() == case[
            "payload_sha256"
        ]


def _fixture_case(two_q):
    return next(case for case in _load_fixture()["cases"] if case["two_q"] == two_q)


def _fixture_complex(values):
    return np.asarray(
        [complex(float(real), float(imaginary)) for real, imaginary in values],
        dtype=np.complex128,
    )


def _pair_coefficients(spec, total_j, total_m):
    coefficients = np.zeros(
        (spec.orbital_count, spec.orbital_count), dtype=np.complex128
    )
    q = Rational(spec.two_q, 2)
    for a, two_ma in enumerate(spec.two_m_values):
        for b, two_mb in enumerate(spec.two_m_values):
            coefficients[a, b] = complex(
                clebsch_gordan(
                    q,
                    q,
                    total_j,
                    Rational(two_ma, 2),
                    Rational(two_mb, 2),
                    total_m,
                )
            )
    return coefficients


def _coupled_matrix_element(tensor, bra, ket):
    return np.einsum("ab,abcd,cd->", bra.conj(), tensor, ket)


@pytest.mark.parametrize("helicity", ["x", "", 1, None])
def test_pair_source_validation_rejects_invalid_helicity(helicity):
    with pytest.raises(ValueError, match="helicity"):
        lhyr_pair_reduced_source(SphereSpec(2), helicity)


@pytest.mark.parametrize("orientation", [-2, 0, 2, True])
def test_pair_source_validation_rejects_invalid_orientation(orientation):
    with pytest.raises(ValueError, match="orientation"):
        lhyr_pair_reduced_source(SphereSpec(2), "-", orientation=orientation)


@pytest.mark.parametrize("component_m", [-3, 3, 0.0, True, "0"])
def test_pair_source_validation_rejects_invalid_component(component_m):
    source = lhyr_pair_reduced_source(SphereSpec(2), "-")
    with pytest.raises(ValueError, match="component"):
        pair_source_tensor(source, component_m)


def test_minus_tensor_validation_rejects_plus_source():
    source = lhyr_pair_reduced_source(SphereSpec(2), "+")
    with pytest.raises(ValueError, match="minus"):
        _minus_pair_source_tensor(source, 0)


def test_plus_tensor_validation_rejects_rescaled_physical_amplitudes():
    source = lhyr_pair_reduced_source(SphereSpec(2), "+")
    rescaled = PairReducedSource(
        spec=source.spec,
        orientation=source.orientation,
        helicity=source.helicity,
        values={channel: 2.0 * value for channel, value in source.values.items()},
        normalization=source.normalization,
    )
    with pytest.raises(ValueError, match="physical amplitudes"):
        pair_source_tensor(rescaled, 0)


@pytest.mark.parametrize("two_q", [15, 31, 63])
def test_production_pair_source_matches_independent_large_q_fixture(two_q):
    expected = _fixture_case(two_q)
    actual = planar_coulomb_reduced_amplitudes(two_q)
    assert [r for r, _ in actual] == expected["relative_m"]
    np.testing.assert_allclose(
        [value for _, value in actual],
        _fixture_complex(expected["minus"]["raw_values_E_C"]),
        atol=1e-13,
        rtol=1e-13,
    )
    actual_values = np.asarray([value for _, value in actual])
    np.testing.assert_allclose(
        actual_values / np.linalg.norm(actual_values),
        _fixture_complex(expected["minus"]["normalized_values"]),
        atol=1e-12,
        rtol=1e-12,
    )
    assert all(value.real > 0.0 and value.imag == 0.0 for value in actual_values)
    assert expected["selected_minus_family"] == "m_plus_2_to_m"


def test_production_pair_source_uses_exact_channel_mapping_and_raw_normalization():
    spec = SphereSpec(6)
    amplitudes = dict(planar_coulomb_reduced_amplitudes(spec.two_q))
    minus = lhyr_pair_reduced_source(spec, "-")
    plus = lhyr_pair_reduced_source(spec, "+")
    expected_minus = {
        (spec.two_q - r, spec.two_q - r - 2): amplitude
        for r, amplitude in amplitudes.items()
    }
    expected_plus = {
        (ket, bra): amplitude for (bra, ket), amplitude in expected_minus.items()
    }
    assert dict(minus.values) == expected_minus
    assert dict(plus.values) == expected_plus
    assert minus.normalization == (
        "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6"
    )
    assert plus.normalization == minus.normalization


def test_displacement_ladder_formula_has_required_minus_phase():
    relative_m = 1
    k_x, k_y = 0.17, -0.11
    k_plus = k_x + 1j * k_y
    alpha = 1j * (k_x - 1j * k_y)
    dimension = 24
    lowering = np.zeros((dimension, dimension), dtype=np.complex128)
    for n in range(1, dimension):
        lowering[n - 1, n] = np.sqrt(n)
    displacement = expm(alpha * lowering.conj().T - alpha.conjugate() * lowering)
    actual = displacement[relative_m, relative_m + 2]
    expected = (
        -(k_plus**2)
        * eval_genlaguerre(relative_m, 2, k_x**2 + k_y**2)
        * np.exp(-(k_x**2 + k_y**2) / 2)
        / np.sqrt((relative_m + 1) * (relative_m + 2))
    )
    np.testing.assert_allclose(actual, expected, atol=1e-13, rtol=1e-13)


def test_n2_stretched_adjoint_uses_a1_not_forbidden_a1_over_sqrt_five():
    spec = SphereSpec(2)
    amplitude = dict(planar_coulomb_reduced_amplitudes(spec.two_q))[1]
    minus = pair_source_tensor(lhyr_pair_reduced_source(spec, "-"), 2)
    plus = pair_source_tensor(lhyr_pair_reduced_source(spec, "+"), -2)
    j2_m2 = _pair_coefficients(spec, 2, 2)
    j0_m0 = _pair_coefficients(spec, 0, 0)
    minus_element = _coupled_matrix_element(minus, j2_m2, j0_m0)
    plus_element = _coupled_matrix_element(plus, j0_m0, j2_m2)
    forbidden_coefficient = complex(clebsch_gordan(2, 2, 0, 2, -2, 0))
    np.testing.assert_allclose(minus_element, amplitude, atol=1e-13, rtol=1e-13)
    np.testing.assert_allclose(plus_element, amplitude, atol=1e-13, rtol=1e-13)
    np.testing.assert_allclose(forbidden_coefficient, 1 / np.sqrt(5), atol=1e-15)
    np.testing.assert_allclose(
        plus_element / (amplitude * forbidden_coefficient),
        np.sqrt(5),
        atol=1e-13,
        rtol=1e-13,
    )


def test_all_n6_stretched_minus_elements_and_plus_partners_equal_raw_amplitudes():
    spec = SphereSpec(6)
    minus = pair_source_tensor(lhyr_pair_reduced_source(spec, "-"), 2)
    plus = pair_source_tensor(lhyr_pair_reduced_source(spec, "+"), -2)
    for relative_m, amplitude in planar_coulomb_reduced_amplitudes(spec.two_q):
        j_bra = spec.two_q - relative_m
        j_ket = j_bra - 2
        bra = _pair_coefficients(spec, j_bra, j_bra)
        ket = _pair_coefficients(spec, j_ket, j_ket)
        np.testing.assert_allclose(
            _coupled_matrix_element(minus, bra, ket),
            amplitude,
            atol=1e-12,
            rtol=1e-12,
        )
        np.testing.assert_allclose(
            _coupled_matrix_element(plus, ket, bra),
            amplitude,
            atol=1e-12,
            rtol=1e-12,
        )


@pytest.mark.parametrize("component_m", [-2, -1, 0, 1, 2])
def test_plus_components_are_exclusively_minus_adjoint(component_m):
    spec = SphereSpec(2)
    plus = pair_source_tensor(lhyr_pair_reduced_source(spec, "+"), component_m)
    minus = pair_source_tensor(lhyr_pair_reduced_source(spec, "-"), -component_m)
    expected = (-1) ** component_m * minus.conj().transpose(2, 3, 0, 1)
    np.testing.assert_allclose(plus, expected, atol=1e-13, rtol=1e-13)


@pytest.mark.parametrize("component_m", [-2, -1, 0, 1, 2])
def test_pair_tensor_has_exact_component_selection_rule_zeros(component_m):
    spec = SphereSpec(2)
    tensor = pair_source_tensor(lhyr_pair_reduced_source(spec, "-"), component_m)
    for a, two_ma in enumerate(spec.two_m_values):
        for b, two_mb in enumerate(spec.two_m_values):
            for c, two_mc in enumerate(spec.two_m_values):
                for d, two_md in enumerate(spec.two_m_values):
                    if two_ma + two_mb - two_mc - two_md != 2 * component_m:
                        assert tensor[a, b, c, d] == 0.0


def test_chiral_source_leaves_scalar_coulomb_tensor_bitwise_unchanged():
    spec = SphereSpec(2)
    before = orbital_coulomb_tensor(spec).copy()
    for component_m in range(-2, 3):
        pair_source_tensor(lhyr_pair_reduced_source(spec, "-"), component_m)
        pair_source_tensor(lhyr_pair_reduced_source(spec, "+"), component_m)
    after = orbital_coulomb_tensor(spec)
    assert np.array_equal(after, before)


def test_pair_source_has_no_landau_level_derivative_field():
    assert [field.name for field in fields(PairReducedSource)] == [
        "spec",
        "orientation",
        "helicity",
        "values",
        "normalization",
    ]
    source = lhyr_pair_reduced_source(SphereSpec(2), "-")
    assert not hasattr(source, "landau_level_derivative")
    assert not hasattr(source, "adiabatic_lll_generator")
