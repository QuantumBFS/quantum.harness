from __future__ import annotations

import ast
import importlib
import math
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.linalg import expm

from scalable_v1.contracts import StateHandle


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
SEEDS_MODULE = (
    SOLUTION_ROOT
    / "scalable_v1"
    / "routes"
    / "cf_operator_nqs"
    / "seeds.py"
)


def _seed_api() -> Any:
    return importlib.import_module("scalable_v1.routes.cf_operator_nqs.seeds")


def _normalized_spinors(seed: int, n_electrons: int = 6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    spinors = rng.normal(size=(n_electrons, 2)) + 1j * rng.normal(
        size=(n_electrons, 2)
    )
    return spinors / np.linalg.norm(spinors, axis=1, keepdims=True)


def _su2_matrix() -> np.ndarray:
    axis = np.asarray([0.31, -0.47, 0.826], dtype=float)
    axis /= np.linalg.norm(axis)
    angle = 0.713
    nx, ny, nz = axis
    cosine = math.cos(0.5 * angle)
    sine = math.sin(0.5 * angle)
    return np.asarray(
        [
            [cosine - 1j * nz * sine, (-1j * nx - ny) * sine],
            [(-1j * nx + ny) * sine, cosine + 1j * nz * sine],
        ],
        dtype=np.complex128,
    )


def _spin2_rotation_from_generators(axis: np.ndarray, angle: float) -> np.ndarray:
    """Independent spin-2 oracle in the ordered ``m=-2,...,2`` basis."""

    ell = 2
    components = np.arange(-ell, ell + 1, dtype=float)
    raising = np.zeros((2 * ell + 1, 2 * ell + 1), dtype=np.complex128)
    for source, m in enumerate(components[:-1]):
        raising[source + 1, source] = math.sqrt((ell - m) * (ell + m + 1.0))
    lowering = raising.T.conj()
    jx = 0.5 * (raising + lowering)
    jy = (raising - lowering) / (2.0j)
    jz = np.diag(components).astype(np.complex128)
    generator = axis[0] * jx + axis[1] * jy + axis[2] * jz
    return expm(-1j * angle * generator)


def _quaternion_axis_angle(quaternion: np.ndarray) -> tuple[np.ndarray, float]:
    vector_norm = float(np.linalg.norm(quaternion[1:]))
    if vector_norm == 0.0:
        return np.asarray([0.0, 0.0, 1.0]), 0.0
    return quaternion[1:] / vector_norm, 2.0 * math.atan2(
        vector_norm, float(quaternion[0])
    )


def _independent_log_rescaled_rotation_residual(
    tower: Any, *, n_electrons: int, seed: int, probes: int
) -> float:
    rng = np.random.default_rng(seed)
    maximum = 0.0
    for _ in range(probes):
        spinors = rng.normal(size=(n_electrons, 2)) + 1j * rng.normal(
            size=(n_electrons, 2)
        )
        spinors /= np.linalg.norm(spinors, axis=1, keepdims=True)
        quaternion = rng.normal(size=4)
        quaternion /= np.linalg.norm(quaternion)
        scalar, x, y, z = quaternion
        rotation = np.asarray(
            [
                [scalar - 1j * z, -y - 1j * x],
                [y - 1j * x, scalar + 1j * z],
            ],
            dtype=np.complex128,
        )
        rotated = np.einsum("ab,nb->na", rotation, spinors)
        before_logs = np.asarray(
            [complex(tower[m].logpsi(spinors)) for m in range(-2, 3)]
        )
        after_logs = np.asarray(
            [complex(tower[m].logpsi(rotated)) for m in range(-2, 3)]
        )
        finite_real_logs = np.concatenate(
            (before_logs.real[np.isfinite(before_logs.real)],
             after_logs.real[np.isfinite(after_logs.real)])
        )
        assert finite_real_logs.size > 0
        shared_shift = float(np.max(finite_real_logs))
        before = np.exp(before_logs - shared_shift)
        after = np.exp(after_logs - shared_shift)
        axis, angle = _quaternion_axis_angle(quaternion)
        expected = _spin2_rotation_from_generators(axis, angle) @ before
        scale = max(np.linalg.norm(after), np.linalg.norm(expected))
        assert scale > 0.0
        maximum = max(maximum, float(np.linalg.norm(after - expected) / scale))
    return maximum


def _relative_residual(actual: complex, expected: complex) -> float:
    return float(abs(actual - expected) / max(abs(actual), abs(expected), 1.0e-300))


def test_jk_seed_family_constructs_one_strict_l2_multiplet() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)

    tower = family.generate_multiplet()

    assert set(tower) == {-2, -1, 0, 1, 2}
    assert family.reduced_l2_state() is tower[0]
    assert family.generate_multiplet() is tower
    assert family.certificate.strict_lll
    assert family.certificate.antisymmetric
    assert family.certificate.projection == "Jain-Kamilla"
    assert "no full-basis" in family.certificate.statement.lower()
    assert "no direct" in family.certificate.statement.lower()
    assert api.finite_rotation_residual(tower, seed=3848, probes=2) <= 1.0e-8
    assert api.tower_ladder_residual(tower) <= 1.0e-10


def test_seed_metadata_and_state_selection_are_frozen_and_truthful() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    ground = family.ground_state()
    tower = family.generate_multiplet()

    assert isinstance(ground, api.CFSeed)
    assert isinstance(ground, StateHandle)
    assert (ground.label, ground.l, ground.m) == ("jk-cf-laughlin-l0-m0", 0, 0)
    assert ground.projection == "Jain-Kamilla"
    assert ground.two_q_star == 5
    assert family.state(0, 0) is ground
    assert all(family.state(2, m) is tower[m] for m in range(-2, 3))
    assert [(tower[m].l, tower[m].m) for m in range(-2, 3)] == [
        (2, m) for m in range(-2, 3)
    ]
    assert len({state.reduced_object_id for state in tower.values()}) == 1
    with pytest.raises(FrozenInstanceError):
        ground.label = "mutated"  # type: ignore[misc]
    with pytest.raises((TypeError, ValueError), match="only"):
        family.state(1, 0)
    with pytest.raises((TypeError, ValueError), match="m"):
        family.state(2, 3)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"n_electrons": 1, "two_q": 0}, "n_electrons"),
        ({"n_electrons": 6.0, "two_q": 15}, "n_electrons"),
        ({"n_electrons": True, "two_q": 0}, "n_electrons"),
        ({"n_electrons": 6, "two_q": 14}, "two_q.*3"),
        ({"n_electrons": 6, "two_q": 15.0}, "two_q"),
    ],
)
def test_seed_family_rejects_invalid_particle_number_and_flux(
    kwargs: dict[str, object], message: str
) -> None:
    api = _seed_api()
    with pytest.raises((TypeError, ValueError), match=message):
        api.JKCFSeedFamily(**kwargs)


def test_ground_seed_is_the_laughlin_polynomial_in_the_declared_gauge() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    spinors = _normalized_spinors(848)

    expected = 1.0 + 0.0j
    for i in range(6):
        for j in range(i + 1, 6):
            expected *= (
                spinors[i, 0] * spinors[j, 1]
                - spinors[i, 1] * spinors[j, 0]
            ) ** 3

    assert family.ground_state().amplitude(spinors) == pytest.approx(
        expected, rel=2.0e-13, abs=1.0e-300
    )


def test_small_n_jk_column_matches_direct_girvin_jach_differentiation() -> None:
    """Independent N=3 orbital projection; no determinant-basis projector."""

    api = _seed_api()
    spinors = _normalized_spinors(8848, n_electrons=3)
    jastrow, derivative_u, derivative_v = api._jastrow_and_derivatives(spinors)
    step = 2.0e-6
    twice_l = 4

    def local_jastrow(particle: int, u: complex, v: complex) -> complex:
        result = 1.0 + 0.0j
        for other in range(3):
            if other != particle:
                result *= u * spinors[other, 1] - v * spinors[other, 0]
        return result

    for twice_m in range(-twice_l, twice_l + 1, 2):
        a = (twice_l + twice_m) // 2
        b = (twice_l - twice_m) // 2
        expected = np.empty(3, dtype=np.complex128)
        for particle, (u, v) in enumerate(spinors):
            if b > 0:
                projected_ubar = (
                    (u + step) ** a
                    * v ** (b - 1)
                    * local_jastrow(particle, u + step, v)
                    - (u - step) ** a
                    * v ** (b - 1)
                    * local_jastrow(particle, u - step, v)
                ) / (2.0 * step)
            else:
                projected_ubar = 0.0
            if a > 0:
                projected_vbar = (
                    u ** (a - 1)
                    * (v + step) ** b
                    * local_jastrow(particle, u, v + step)
                    - u ** (a - 1)
                    * (v - step) ** b
                    * local_jastrow(particle, u, v - step)
                ) / (2.0 * step)
            else:
                projected_vbar = 0.0
            expected[particle] = math.sqrt(math.comb(twice_l, a)) * (
                b * projected_ubar - a * projected_vbar
            )
        actual = api._projected_n1_column(
            spinors,
            derivative_u,
            derivative_v,
            twice_l=twice_l,
            twice_m=twice_m,
        )
        np.testing.assert_allclose(actual, expected, rtol=3.0e-9, atol=3.0e-10)

    unnormalized_n0 = np.empty((3, 3), dtype=np.complex128)
    for orbital in range(3):
        unnormalized_n0[:, orbital] = (
            spinors[:, 0] ** orbital
            * spinors[:, 1] ** (2 - orbital)
            * jastrow
        )
    family = api.JKCFSeedFamily(n_electrons=3, two_q=6)
    assert np.linalg.det(unnormalized_n0) == pytest.approx(
        family.ground_state().amplitude(spinors), rel=2.0e-14
    )


def test_near_coincident_points_remain_the_exact_nonzero_polynomial() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=2, two_q=3)
    separation = 1.0e-16
    spinors = np.asarray(
        [[1.0, 0.0], [math.sqrt(1.0 - separation**2), separation]],
        dtype=np.complex128,
    )

    amplitude = family.ground_state().amplitude(spinors)

    assert amplitude != 0.0
    assert amplitude == pytest.approx(separation**3, rel=2.0e-15)


def test_logpsi_does_not_underflow_when_raw_large_n_amplitude_does() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=40, two_q=117)
    spinors = _normalized_spinors(40848, n_electrons=40)

    for state in (family.ground_state(), family.reduced_l2_state()):
        assert state.amplitude(spinors) == 0.0
        logpsi = state.logpsi(spinors)
        assert np.isfinite(logpsi.real)
        assert np.isfinite(logpsi.imag)


def test_all_seed_amplitudes_are_finite_nonzero_and_exchange_antisymmetric() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    states = (family.ground_state(), *family.generate_multiplet().values())
    spinors = _normalized_spinors(849)
    swapped = spinors.copy()
    swapped[[1, 4]] = swapped[[4, 1]]

    for state in states:
        amplitude = state.amplitude(spinors)
        assert np.isfinite(amplitude)
        assert abs(amplitude) > 1.0e-30
        assert state.amplitude(swapped) == pytest.approx(
            -amplitude, rel=2.0e-10, abs=1.0e-300
        )


@pytest.mark.parametrize("particle", range(6))
def test_every_particle_has_external_flux_homogeneity_and_local_spinor_gauge(
    particle: int,
) -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    states = (family.ground_state(), *family.generate_multiplet().values())
    spinors = _normalized_spinors(900 + particle)
    alpha = 0.137 * (particle + 1)
    gauged = spinors.copy()
    gauged[particle] *= np.exp(1j * alpha)
    expected_phase = np.exp(1j * family.two_q * alpha)

    for state in states:
        expected = expected_phase * state.amplitude(spinors)
        assert state.amplitude(gauged) == pytest.approx(
            expected, rel=5.0e-10, abs=1.0e-300
        )


def test_l2_tower_obeys_independent_finite_wigner_rotation_and_l0_is_invariant() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    tower = family.generate_multiplet()
    spinors = _normalized_spinors(1848)
    rotation = _su2_matrix()
    rotated = np.einsum("ab,nb->na", rotation, spinors)

    before = np.asarray([tower[m].amplitude(spinors) for m in range(-2, 3)])
    after = np.asarray([tower[m].amplitude(rotated) for m in range(-2, 3)])
    axis = np.asarray([0.31, -0.47, 0.826], dtype=float)
    axis /= np.linalg.norm(axis)
    wigner = _spin2_rotation_from_generators(axis, 0.713)

    np.testing.assert_allclose(after, wigner @ before, rtol=2.0e-9, atol=1.0e-25)
    ground = family.ground_state()
    assert ground.amplitude(rotated) == pytest.approx(
        ground.amplitude(spinors), rel=2.0e-11, abs=1.0e-300
    )


def test_spin2_generator_oracle_matches_the_spinor_rotation_convention() -> None:
    spinor = _normalized_spinors(18848, n_electrons=1)[0]
    rotation = _su2_matrix()
    rotated = rotation @ spinor
    axis = np.asarray([0.31, -0.47, 0.826], dtype=float)
    axis /= np.linalg.norm(axis)
    wigner = _spin2_rotation_from_generators(axis, 0.713)

    def spin2_polynomials(value: np.ndarray) -> np.ndarray:
        u, v = value
        return np.asarray(
            [
                math.sqrt(math.comb(4, 2 + m)) * u ** (2 + m) * v ** (2 - m)
                for m in range(-2, 3)
            ]
        )

    np.testing.assert_allclose(
        spin2_polynomials(rotated),
        wigner @ spin2_polynomials(spinor),
        rtol=2.0e-14,
        atol=2.0e-14,
    )


def test_rotation_residual_uses_log_amplitudes_without_large_n_false_zero() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=40, two_q=117)
    tower = family.generate_multiplet()
    expected = _independent_log_rescaled_rotation_residual(
        tower, n_electrons=40, seed=852, probes=1
    )

    actual = api.finite_rotation_residual(tower, seed=852, probes=1)

    assert np.isfinite(expected) and expected > 0.0
    assert np.isfinite(actual) and actual > 0.0
    assert actual == pytest.approx(expected, rel=2.0e-8, abs=2.0e-12)


def test_rotation_residual_never_accepts_all_zero_vectors_as_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    monkeypatch.setattr(
        api.CFSeed,
        "logpsi",
        lambda self, configs: np.asarray(complex(-math.inf, 0.0)),
    )

    with pytest.raises(RuntimeError, match="valid nonzero rotation probe"):
        api.finite_rotation_residual(family.generate_multiplet(), seed=3848, probes=1)


def test_m_labels_have_the_independent_analytic_z_rotation_phases() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    tower = family.generate_multiplet()
    spinors = _normalized_spinors(1948)
    angle = 0.419
    rotation = np.diag(
        [np.exp(-0.5j * angle), np.exp(0.5j * angle)]
    ).astype(np.complex128)
    rotated = np.einsum("ab,nb->na", rotation, spinors)

    for m, state in tower.items():
        assert state.amplitude(rotated) == pytest.approx(
            np.exp(-1j * m * angle) * state.amplitude(spinors),
            rel=2.0e-10,
            abs=1.0e-300,
        )


def test_batch_amplitude_and_logpsi_preserve_phase_and_zero_handling() -> None:
    api = _seed_api()
    family = api.JKCFSeedFamily(n_electrons=6, two_q=15)
    state = family.reduced_l2_state()
    first = _normalized_spinors(2848)
    second = _normalized_spinors(2849)
    coincident = first.copy()
    coincident[3] = coincident[0]
    batch = np.stack((first, second, coincident))

    amplitudes = state.amplitude(batch)
    logs = state.logpsi(batch)

    assert amplitudes.shape == logs.shape == (3,)
    np.testing.assert_allclose(np.exp(logs[:2]), amplitudes[:2], rtol=2.0e-14)
    assert abs(amplitudes[2]) < 1.0e-24
    assert np.isneginf(logs[2].real)
    assert logs[2].imag == 0.0
    with pytest.raises(NotImplementedError, match="Task 5"):
        state.sample(4, 848)
    with pytest.raises(NotImplementedError, match="Task 5"):
        state.local_energy(batch)
    with pytest.raises(NotImplementedError, match="Task 5"):
        state.local_l2(batch)


@pytest.mark.parametrize(
    ("bad_config", "message"),
    [
        (np.zeros((6, 3), dtype=np.complex128), "shape"),
        (np.zeros((5, 2), dtype=np.complex128), "n_electrons"),
        (np.zeros((2,), dtype=np.complex128), "shape"),
        (np.full((6, 2), np.nan + 0j), "finite"),
        (np.ones((6, 2), dtype=np.complex128), "normalized"),
    ],
)
def test_seed_state_rejects_malformed_spinor_configs(
    bad_config: np.ndarray, message: str
) -> None:
    api = _seed_api()
    state = api.JKCFSeedFamily(n_electrons=6, two_q=15).ground_state()
    with pytest.raises((TypeError, ValueError), match=message):
        state.amplitude(bad_config)


def test_seed_module_has_no_forbidden_ed_or_direct_projection_imports() -> None:
    tree = ast.parse(SEEDS_MODULE.read_text(encoding="utf-8"), filename=str(SEEDS_MODULE))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)

    forbidden = (
        "benchmark_v0.fock_ed",
        "benchmark_v0.ed_oracle",
        "benchmark_v0.projected_nqs",
        "benchmark_v0.nqs_benchmark",
    )
    assert not any(
        module == blocked or module.startswith(f"{blocked}.")
        for module in imported
        for blocked in forbidden
    )
    source = SEEDS_MODULE.read_text(encoding="utf-8").lower()
    assert "direct_projection" not in source
    assert "enumerate_determinant_basis" not in source
