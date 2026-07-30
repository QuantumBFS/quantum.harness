from __future__ import annotations

from collections import Counter, deque
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pytest

import large_lattice_ctqmc as ctqmc
import large_lattice_ed as ed


EPSILON = 1.0 / 100.0
KAPPA = 1.0 / 50.0
VERTEX_STRENGTH = 1.0 / 4.0
G_A = 1.0 / 4.0
G_B = 1.0 / 4.0
CONDITION_MAX = 1.0e12


def _geometry(lx: int = 4, ly: int = 3) -> ctqmc.TriangularGeometry:
    return ctqmc.build_triangular_geometry(lx, ly)


def _catalog() -> list[ctqmc.LocalVertex]:
    return ctqmc.build_vertex_catalog(
        EPSILON,
        KAPPA,
        VERTEX_STRENGTH,
        G_A,
        G_B,
    )


def _event(value: tuple[int, int]) -> ctqmc.Event:
    return ctqmc.Event(int(value[0]), int(value[1]))


def _events(word: Sequence[tuple[int, int]]) -> list[ctqmc.Event]:
    return [_event(value) for value in word]


def _sites(
    geometry: ctqmc.TriangularGeometry,
    value: tuple[int, int],
) -> tuple[int, int, int]:
    return geometry.triangles[value[0]].sites


def _embedded_factor(
    geometry: ctqmc.TriangularGeometry,
    catalog: Sequence[ctqmc.LocalVertex],
    value: tuple[int, int],
    *,
    inverse: bool = False,
) -> np.ndarray:
    result = np.eye(geometry.n_sites)
    sites = _sites(geometry, value)
    vertex = catalog[value[1]]
    block = vertex.block_inv if inverse else vertex.block
    result[np.ix_(sites, sites)] = np.asarray(block)
    return result


def _full_product(
    geometry: ctqmc.TriangularGeometry,
    catalog: Sequence[ctqmc.LocalVertex],
    word: Sequence[tuple[int, int]],
) -> np.ndarray:
    product = np.eye(geometry.n_sites)
    for value in word:
        product = _embedded_factor(geometry, catalog, value) @ product
    return product


def _proposal(
    factors: ctqmc.DenseFactors,
    geometry: ctqmc.TriangularGeometry,
    catalog: Sequence[ctqmc.LocalVertex],
    value: tuple[int, int],
    *,
    inverse: bool = False,
) -> ctqmc.LowRankProposal:
    vertex = catalog[value[1]]
    block = vertex.block_inv if inverse else vertex.block
    return ctqmc.low_rank_left_proposal(
        factors,
        _sites(geometry, value),
        block,
        condition_max=CONDITION_MAX,
    )


def _acceptance(log_acceptance: float) -> float:
    return math.exp(float(log_acceptance))


def _word_weight(
    beta: float,
    catalog: Sequence[ctqmc.LocalVertex],
    word: Sequence[tuple[int, int]],
    logdet: float,
) -> float:
    activity_product = math.prod(
        float(catalog[value[1]].activity) for value in word
    )
    return (
        beta ** len(word)
        / math.factorial(len(word))
        * activity_product
        * math.exp(logdet)
    )


def _manifest(
    *,
    lx: int = 2,
    ly: int = 2,
    steps: int = 20,
    warmup: int = 2,
    seed: int = 121_2026,
    mode: str = "cold",
    initial_order: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "lattice": {"Lx": lx, "Ly": ly},
        "model": {
            "epsilon": EPSILON,
            "kappa": KAPPA,
            "vertex_strength": VERTEX_STRENGTH,
            "g_A": G_A,
            "g_B": G_B,
            "beta": 0.5,
        },
        "monte_carlo": {
            "steps": steps,
            "warmup": warmup,
            "measure_every": 1,
            "checkpoint_every": max(1, steps // 2),
            "rebuild_every": 7,
            "seed": seed,
            "woodbury_condition_max": CONDITION_MAX,
            "move_probabilities": {
                "insert": 0.35,
                "delete": 0.35,
                "rotate_left_to_right": 0.15,
                "rotate_right_to_left": 0.15,
            },
            "initialization": {
                "mode": mode,
                "initial_order": initial_order,
            },
        },
        "measurements": {
            "momenta": [[0, 0], [1, 0], [0, 1]],
            "displacements": [[0, 0], [1, 0], [0, 1]],
        },
        "exact_diagonalization": {"hermitian_tolerance": 1.0e-10},
    }


def _sampler(
    tmp_path: Path,
    *,
    mode: str = "cold",
    initial_order: int = 0,
    seed: int = 121_2026,
) -> ctqmc.CTQMC:
    return ctqmc.CTQMC.from_manifest(
        _manifest(
            mode=mode,
            initial_order=initial_order,
            seed=seed,
        ),
        tmp_path,
        manifest_sha256="unit-test-manifest",
    )


def _oracle_input(
    geometry: ctqmc.TriangularGeometry,
    catalog: Sequence[ctqmc.LocalVertex],
) -> ed.OracleInput:
    return ed.OracleInput(
        "unit-test-manifest",
        geometry,
        tuple(catalog),
        {
            "epsilon": EPSILON,
            "kappa": KAPPA,
            "vertex_strength": VERTEX_STRENGTH,
            "g_A": G_A,
            "g_B": G_B,
            "beta": 0.5,
        },
        ((0, 0), (1, 0), (0, 1)),
        1.0e-10,
    )


def _assert_complex_pair_close(
    actual: Sequence[float],
    expected: Sequence[float],
    *,
    atol: float,
) -> None:
    np.testing.assert_allclose(
        np.asarray(actual, dtype=float),
        np.asarray(expected, dtype=float),
        rtol=0.0,
        atol=atol,
    )


def test_triangular_geometry_vertex_count_and_g0() -> None:
    geometry = _geometry(4, 3)
    catalog = _catalog()

    assert geometry.n_sites == 12
    assert geometry.n_triangles == 2 * geometry.n_sites == 24
    assert [triangle.triangle_id for triangle in geometry.triangles] == list(
        range(geometry.n_triangles)
    )
    assert len({triangle.sites for triangle in geometry.triangles}) == 24
    assert all(
        len(set(triangle.sites)) == 3 for triangle in geometry.triangles
    )
    assert all(
        0 <= site < geometry.n_sites
        for triangle in geometry.triangles
        for site in triangle.sites
    )

    assert len(catalog) == 2 * math.factorial(3) == 12
    assert {vertex.family for vertex in catalog} == {"A", "B"}
    assert [vertex.vertex_id for vertex in catalog] == list(range(12))
    assert all(vertex.activity > 0.0 for vertex in catalog)
    assert all(vertex.block.shape == (3, 3) for vertex in catalog)
    assert all(vertex.block_inv.shape == (3, 3) for vertex in catalog)

    resolved_event_count = geometry.n_triangles * len(catalog)
    assert resolved_event_count == 24 * 12
    g0 = geometry.n_triangles * sum(
        vertex.activity for vertex in catalog
    )
    expected_g0 = geometry.n_triangles * (G_A + G_B)
    assert g0 == pytest.approx(expected_g0, rel=0.0, abs=1.0e-14)


def test_l2_periodic_fixture_keeps_directed_triangle_multiplicity() -> None:
    geometry = _geometry(2, 2)

    assert geometry.n_sites == 4
    assert geometry.n_triangles == 8
    assert all(
        len(set(triangle.sites)) == 3 for triangle in geometry.triangles
    )
    undirected = Counter(
        frozenset(triangle.sites) for triangle in geometry.triangles
    )
    assert len(undirected) == 4
    assert set(undirected.values()) == {2}
    assert Counter(
        triangle.orientation for triangle in geometry.triangles
    ) == {"up": 4, "down": 4}


def test_l3_triangles_are_unique_and_each_site_has_incidence_six() -> None:
    geometry = _geometry(3, 3)

    assert geometry.n_sites == 9
    assert geometry.n_triangles == 18
    assert len({triangle.sites for triangle in geometry.triangles}) == 18
    assert len(
        {frozenset(triangle.sites) for triangle in geometry.triangles}
    ) == 18
    incidence = Counter(
        site
        for triangle in geometry.triangles
        for site in triangle.sites
    )
    assert incidence == {site: 6 for site in range(geometry.n_sites)}


@pytest.mark.parametrize("depth", [0, 1, 2, 5, 13])
def test_structured_product_matches_full_embedded_factors(
    depth: int,
) -> None:
    geometry = _geometry()
    catalog = _catalog()
    rng = np.random.default_rng(121_000 + depth)
    word = [
        (
            int(rng.integers(geometry.n_triangles)),
            int(rng.integers(len(catalog))),
        )
        for _ in range(depth)
    ]

    structured = ctqmc.structured_product(
        geometry.n_sites,
        geometry.triangles,
        catalog,
        _events(word),
    )
    full = _full_product(geometry, catalog, word)
    np.testing.assert_allclose(
        structured,
        full,
        rtol=3.0e-13,
        atol=3.0e-13,
    )


def test_insert_delete_small_determinant_ratio_matches_full() -> None:
    geometry = _geometry(3, 3)
    catalog = _catalog()
    word = [(0, 0), (2, 7), (5, 3), (1, 10)]
    value = (4, 5)
    product = _full_product(geometry, catalog, word)
    factors = ctqmc.factor_dense(product)

    insertion = _proposal(factors, geometry, catalog, value)
    inserted = ctqmc.apply_low_rank_proposal(factors, insertion)
    full_inserted = _embedded_factor(
        geometry,
        catalog,
        value,
    ) @ product
    old_det = np.linalg.det(np.eye(geometry.n_sites) + product)
    new_det = np.linalg.det(np.eye(geometry.n_sites) + full_inserted)

    assert math.exp(insertion.log_det_ratio) == pytest.approx(
        new_det / old_det,
        rel=2.0e-11,
        abs=2.0e-12,
    )
    assert inserted.logdet == pytest.approx(
        math.log(new_det),
        rel=2.0e-11,
    )
    np.testing.assert_allclose(
        inserted.T,
        full_inserted,
        rtol=2.0e-12,
        atol=2.0e-12,
    )

    deletion = _proposal(
        inserted,
        geometry,
        catalog,
        value,
        inverse=True,
    )
    restored = ctqmc.apply_low_rank_proposal(inserted, deletion)
    assert math.exp(deletion.log_det_ratio) == pytest.approx(
        old_det / new_det,
        rel=2.0e-11,
        abs=2.0e-12,
    )
    np.testing.assert_allclose(
        restored.T,
        product,
        rtol=3.0e-12,
        atol=3.0e-12,
    )
    np.testing.assert_allclose(
        restored.Q,
        factors.Q,
        rtol=3.0e-11,
        atol=3.0e-12,
    )


def test_woodbury_q_matches_direct_inverse() -> None:
    geometry = _geometry(3, 3)
    catalog = _catalog()
    word = [(0, 1), (1, 4), (3, 9), (5, 2), (2, 11)]
    factors = ctqmc.factor_dense(
        _full_product(geometry, catalog, word)
    )
    value = (4, 8)

    proposal = _proposal(factors, geometry, catalog, value)
    assert proposal.T_new is not None
    assert proposal.Q_new is not None
    expected_q = np.linalg.inv(
        np.eye(geometry.n_sites) + proposal.T_new
    )
    np.testing.assert_allclose(
        proposal.Q_new,
        expected_q,
        rtol=3.0e-11,
        atol=3.0e-12,
    )
    assert proposal.local_solve_residual_inf <= 1.0e-9

    applied = ctqmc.apply_low_rank_proposal(factors, proposal)
    np.testing.assert_allclose(
        applied.Q,
        expected_q,
        rtol=3.0e-11,
        atol=3.0e-12,
    )
    assert ctqmc.inverse_residual_inf(applied.T, applied.Q) <= 1.0e-9


def test_both_cyclic_rotation_matrix_directions() -> None:
    geometry = _geometry(3, 3)
    catalog = _catalog()
    word = [(0, 0), (2, 5), (4, 9), (1, 3)]
    product = _full_product(geometry, catalog, word)
    factors = ctqmc.factor_dense(product)

    left_value = word[-1]
    left_factor = _embedded_factor(geometry, catalog, left_value)
    expected_ltr = np.linalg.inv(left_factor) @ product @ left_factor
    ltr = ctqmc.rotate_left_factor_to_right(
        factors,
        _event(left_value),
        geometry.triangles,
        catalog,
    )
    np.testing.assert_allclose(
        ltr.T,
        expected_ltr,
        rtol=3.0e-11,
        atol=3.0e-12,
    )
    np.testing.assert_allclose(
        ltr.Q,
        np.linalg.inv(left_factor) @ factors.Q @ left_factor,
        rtol=3.0e-11,
        atol=3.0e-12,
    )
    assert ltr.logdet == pytest.approx(factors.logdet, abs=3.0e-12)

    right_value = word[0]
    right_factor = _embedded_factor(geometry, catalog, right_value)
    expected_rtl = right_factor @ product @ np.linalg.inv(right_factor)
    rtl = ctqmc.rotate_right_factor_to_left(
        factors,
        _event(right_value),
        geometry.triangles,
        catalog,
    )
    np.testing.assert_allclose(
        rtl.T,
        expected_rtl,
        rtol=3.0e-11,
        atol=3.0e-12,
    )
    np.testing.assert_allclose(
        rtl.Q,
        right_factor @ factors.Q @ np.linalg.inv(right_factor),
        rtol=3.0e-11,
        atol=3.0e-12,
    )
    assert rtl.logdet == pytest.approx(factors.logdet, abs=3.0e-12)


def test_word_deque_rotation_matches_product_convention(
    tmp_path: Path,
) -> None:
    sampler = _sampler(tmp_path)
    original = [_event(value) for value in [(0, 0), (2, 5), (4, 9)]]
    sampler.word = deque(original)
    sampler.rebuild("rotation-fixture", compare_fast=False)

    assert sampler._rotate_ltr()
    assert list(sampler.word) == [original[-1], *original[:-1]]
    expected = ctqmc.structured_product(
        sampler.geometry.n_sites,
        sampler.geometry.triangles,
        sampler.catalog,
        list(sampler.word),
    )
    np.testing.assert_allclose(
        sampler.factors.T,
        expected,
        rtol=3.0e-11,
        atol=3.0e-12,
    )

    assert sampler._rotate_rtl()
    assert list(sampler.word) == original
    expected_original = ctqmc.structured_product(
        sampler.geometry.n_sites,
        sampler.geometry.triangles,
        sampler.catalog,
        original,
    )
    np.testing.assert_allclose(
        sampler.factors.T,
        expected_original,
        rtol=3.0e-11,
        atol=3.0e-12,
    )


def test_microscopic_forward_reverse_acceptance_flux() -> None:
    geometry = _geometry(3, 3)
    catalog = _catalog()
    beta = 0.7
    word = [(0, 0), (2, 7), (3, 4)]
    value = (5, 10)
    old = ctqmc.factor_dense(_full_product(geometry, catalog, word))
    insertion = _proposal(old, geometry, catalog, value)
    new = ctqmc.apply_low_rank_proposal(old, insertion)
    deletion = _proposal(
        new,
        geometry,
        catalog,
        value,
        inverse=True,
    )

    label_probability = (
        catalog[value[1]].activity
        / (
            geometry.n_triangles
            * sum(vertex.activity for vertex in catalog)
        )
    )
    p_insert = 0.41
    p_delete = 0.37
    activity = float(catalog[value[1]].activity)
    log_forward = ctqmc.log_accept_insert(
        beta,
        activity,
        len(word),
        insertion.log_det_ratio,
        p_insert,
        p_delete,
        label_probability,
    )
    log_reverse = ctqmc.log_accept_delete(
        beta,
        activity,
        len(word) + 1,
        deletion.log_det_ratio,
        p_insert,
        p_delete,
        label_probability,
    )

    old_weight = _word_weight(beta, catalog, word, old.logdet)
    new_word = [*word, value]
    new_weight = _word_weight(beta, catalog, new_word, new.logdet)
    forward_flux = (
        old_weight
        * p_insert
        * label_probability
        * _acceptance(log_forward)
    )
    reverse_flux = (
        new_weight
        * p_delete
        * _acceptance(log_reverse)
    )
    assert forward_flux == pytest.approx(
        reverse_flux,
        rel=2.0e-11,
        abs=1.0e-14,
    )


def test_empty_word_boundary_keeps_delete_as_self_loop(
    tmp_path: Path,
) -> None:
    sampler = _sampler(tmp_path)
    before_t = sampler.factors.T.copy()
    before_q = sampler.factors.Q.copy()
    before_logdet = sampler.factors.logdet

    assert len(sampler.word) == 0
    assert not sampler._delete()
    assert len(sampler.word) == 0
    np.testing.assert_array_equal(sampler.factors.T, before_t)
    np.testing.assert_array_equal(sampler.factors.Q, before_q)
    assert sampler.factors.logdet == before_logdet
    assert sampler.counters["moves"]["delete"] == {
        "attempted": 1,
        "accepted": 0,
    }

    with pytest.raises(ValueError, match="m>=1"):
        ctqmc.log_accept_delete(
            1.0,
            1.0 / 24.0,
            0,
            0.0,
            0.35,
            0.35,
            1.0 / 96.0,
        )


def test_observable_formulas_momenta_real_space_and_compressibility() -> None:
    geometry = _geometry(2, 2)
    catalog = _catalog()
    word = [(0, 0), (2, 7), (5, 3)]
    factors = ctqmc.factor_dense(
        _full_product(geometry, catalog, word)
    )
    beta = 0.5
    g0 = geometry.n_triangles * (G_A + G_B)
    momenta = [(0, 0), (1, 0)]
    displacements = [(0, 0), (1, 0), (0, 1)]
    observed = ctqmc.measure_configuration(
        factors,
        geometry,
        beta,
        g0,
        len(word),
        momenta,
        displacements,
    )

    green = (np.eye(geometry.n_sites) - factors.Q).T
    density = np.diag(green)
    density_pair = np.outer(density, density) - green * green.T
    np.fill_diagonal(density_pair, density)
    particle_number = float(density.sum())
    particle_number_squared = float(density_pair.sum())

    assert observed["energy_density"] == pytest.approx(
        (g0 - len(word) / beta) / geometry.n_sites
    )
    assert observed["particle_number"] == pytest.approx(particle_number)
    assert observed["particle_number_squared"] == pytest.approx(
        particle_number_squared
    )
    assert observed["particle_density"] == pytest.approx(
        particle_number / geometry.n_sites
    )

    x = geometry.coordinates[:, 0]
    y = geometry.coordinates[:, 1]
    for kx, ky in momenta:
        phase = np.exp(
            2.0j
            * math.pi
            * (kx * x / geometry.Lx + ky * y / geometry.Ly)
        )
        expected_one = np.vdot(phase, green @ phase) / geometry.n_sites
        expected_raw = (
            np.vdot(phase, density_pair @ phase) / geometry.n_sites
        )
        expected_mode = (
            np.vdot(phase, density) / math.sqrt(geometry.n_sites)
        )
        values = observed["momenta"][f"{kx},{ky}"]
        _assert_complex_pair_close(
            values["one_body"],
            [expected_one.real, expected_one.imag],
            atol=3.0e-12,
        )
        _assert_complex_pair_close(
            values["density_raw"],
            [expected_raw.real, expected_raw.imag],
            atol=3.0e-12,
        )
        _assert_complex_pair_close(
            values["density_mode"],
            [expected_mode.real, expected_mode.imag],
            atol=3.0e-12,
        )

    for dx, dy in displacements:
        expected = 0.0
        for sx in range(geometry.Lx):
            for sy in range(geometry.Ly):
                i = sx * geometry.Ly + sy
                j = (
                    ((sx + dx) % geometry.Lx) * geometry.Ly
                    + (sy + dy) % geometry.Ly
                )
                expected += float(green[i, j])
        expected /= geometry.n_sites
        _assert_complex_pair_close(
            observed["real_space_green"][f"{dx},{dy}"],
            [expected, 0.0],
            atol=3.0e-12,
        )

    accumulator = ctqmc.ObservableAccumulator()
    accumulator.add(observed)
    summary = accumulator.summary(beta, geometry.n_sites)
    expected_compressibility = (
        beta
        * (particle_number_squared - particle_number**2)
        / geometry.n_sites
    )
    assert summary["compressibility"] == pytest.approx(
        expected_compressibility,
        abs=3.0e-12,
    )
    assert summary["primary_traces"]["particle_number"] == [
        particle_number
    ]
    zero_momentum = summary["momentum"]["0,0"]
    raw = zero_momentum["density_raw"]["mean"]
    mode = zero_momentum["density_mode"]["mean"]
    assert zero_momentum["density_connected_from_means"] == pytest.approx(
        [raw[0] - mode[0] ** 2 - mode[1] ** 2, raw[1]]
    )


def test_fock_gamma_one_particle_block_has_destination_source_orientation() -> None:
    geometry = _geometry(2, 2)
    catalog = _catalog()
    matrix = _embedded_factor(geometry, catalog, (0, 7))
    layout = ed.build_fock_layout(geometry.n_sites)

    gamma, residual = ed.fock_gamma(matrix, layout)
    one_particle_masks = list(layout.sectors[1].masks)
    one_particle_block = gamma[
        np.ix_(one_particle_masks, one_particle_masks)
    ]
    np.testing.assert_allclose(
        one_particle_block,
        matrix,
        rtol=0.0,
        atol=2.0e-14,
    )
    assert residual <= 2.0e-14
    destination = 2
    source = 1
    assert one_particle_block[destination, source] == pytest.approx(
        matrix[destination, source]
    )


def test_ed_hamiltonian_is_hermitian_and_uses_all_resolved_terms() -> None:
    geometry = _geometry(2, 2)
    catalog = _catalog()
    oracle = _oracle_input(geometry, catalog)
    layout = ed.build_fock_layout(geometry.n_sites)

    hamiltonian, diagnostics = ed.build_hamiltonian(oracle, layout)
    np.testing.assert_allclose(
        hamiltonian,
        hamiltonian.conj().T,
        rtol=0.0,
        atol=2.0e-11,
    )
    assert diagnostics["resolved_term_count"] == (
        geometry.n_triangles * len(catalog)
    )
    assert diagnostics["G0"] == pytest.approx(
        geometry.n_triangles * (G_A + G_B)
    )
    assert diagnostics["hermitian_residual_relative_inf"] <= 1.0e-10


def test_ed_conditional_gaussian_matches_sampler_observable_conventions() -> None:
    geometry = _geometry(2, 2)
    catalog = _catalog()
    word = [(0, 1), (2, 8), (7, 4)]
    product = _full_product(geometry, catalog, word)
    factors = ctqmc.factor_dense(product)
    layout = ed.build_fock_layout(geometry.n_sites)
    gamma, orientation_residual = ed.fock_gamma(product, layout)
    density_matrix = gamma / np.trace(gamma)

    green = ed.one_body_green(density_matrix, geometry.n_sites)
    density, density_pair, number, number2 = ed.density_moments(
        density_matrix,
        geometry.n_sites,
    )
    momenta = [(0, 0), (1, 0), (0, 1)]
    exact_momentum = ed.momentum_observables(
        geometry,
        green,
        density,
        density_pair,
        momenta,
    )
    measured = ctqmc.measure_configuration(
        factors,
        geometry,
        0.5,
        geometry.n_triangles * (G_A + G_B),
        len(word),
        momenta,
    )

    assert orientation_residual <= 2.0e-14
    assert measured["particle_number"] == pytest.approx(
        number,
        abs=3.0e-12,
    )
    assert measured["particle_number_squared"] == pytest.approx(
        number2,
        abs=3.0e-12,
    )
    for momentum in exact_momentum:
        for name in ("one_body", "density_raw", "density_mode"):
            _assert_complex_pair_close(
                measured["momenta"][momentum][name],
                exact_momentum[momentum][name],
                atol=4.0e-12,
            )


def test_ed_hard_rejects_more_than_nine_sites() -> None:
    with pytest.raises(ed.EDOracleError, match="1<=N<=9"):
        ed.build_fock_layout(10)


def test_hot_cold_initialization_and_pcg64dxsm(tmp_path: Path) -> None:
    cold = _sampler(tmp_path / "cold")
    hot = _sampler(
        tmp_path / "hot",
        mode="hot",
        initial_order=7,
        seed=121_2027,
    )

    assert isinstance(cold.rng.bit_generator, np.random.PCG64DXSM)
    assert isinstance(hot.rng.bit_generator, np.random.PCG64DXSM)
    assert len(cold.word) == 0
    assert cold.initialization == {"mode": "cold", "initial_order": 0}
    assert len(hot.word) == 7
    assert hot.initialization == {"mode": "hot", "initial_order": 7}
    hot_product = ctqmc.structured_product(
        hot.geometry.n_sites,
        hot.geometry.triangles,
        hot.catalog,
        list(hot.word),
    )
    np.testing.assert_allclose(
        hot.factors.T,
        hot_product,
        rtol=0.0,
        atol=2.0e-14,
    )

    bad_cold = _manifest(mode="cold", initial_order=1)
    with pytest.raises(ctqmc.ManifestError, match="cold"):
        ctqmc.CTQMC.from_manifest(bad_cold, tmp_path / "bad-cold")
    bad_hot = _manifest(mode="hot", initial_order=0)
    with pytest.raises(ctqmc.ManifestError, match="hot"):
        ctqmc.CTQMC.from_manifest(bad_hot, tmp_path / "bad-hot")


def test_rebuild_records_logdet_t_q_and_residual_drift(
    tmp_path: Path,
) -> None:
    sampler = _sampler(
        tmp_path,
        mode="hot",
        initial_order=5,
    )
    value = (3, 6)
    proposal = _proposal(
        sampler.factors,
        sampler.geometry,
        sampler.catalog,
        value,
    )
    sampler.factors = ctqmc.apply_low_rank_proposal(
        sampler.factors,
        proposal,
    )
    sampler.word.append(_event(value))

    fast = sampler.factors
    rebuilt_product = ctqmc.structured_product(
        sampler.geometry.n_sites,
        sampler.geometry.triangles,
        sampler.catalog,
        list(sampler.word),
    )
    expected = ctqmc.factor_dense(rebuilt_product)
    expected_delta = expected.logdet - fast.logdet
    expected_t_drift = (
        np.linalg.norm(expected.T - fast.T, ord=np.inf)
        / max(1.0, np.linalg.norm(expected.T, ord=np.inf))
    )
    expected_q_drift = (
        np.linalg.norm(expected.Q - fast.Q, ord=np.inf)
        / max(1.0, np.linalg.norm(expected.Q, ord=np.inf))
    )
    expected_fast_residual = ctqmc.inverse_residual_inf(
        fast.T,
        fast.Q,
    )

    sampler.rebuild("unit-drift")
    diagnostic = sampler.rebuild_diagnostics[-1]
    assert diagnostic["reason"] == "unit-drift"
    assert diagnostic["fast_inverse_residual_inf"] == pytest.approx(
        expected_fast_residual
    )
    assert diagnostic["rebuilt_inverse_residual_inf"] == pytest.approx(
        expected.inverse_residual_inf
    )
    assert diagnostic["delta_logdet"] == pytest.approx(expected_delta)
    assert diagnostic["relative_T_drift_inf"] == pytest.approx(
        expected_t_drift
    )
    assert diagnostic["relative_Q_drift_inf"] == pytest.approx(
        expected_q_drift
    )
    np.testing.assert_allclose(sampler.factors.T, expected.T)
    np.testing.assert_allclose(sampler.factors.Q, expected.Q)


def test_checkpoint_roundtrip_preserves_word_rng_and_primary_traces(
    tmp_path: Path,
) -> None:
    sampler = _sampler(
        tmp_path,
        mode="hot",
        initial_order=6,
        seed=121_2030,
    )
    sampler.moves_since_rebuild = 5
    sampler.completed_steps = 3
    observation = ctqmc.measure_configuration(
        sampler.factors,
        sampler.geometry,
        sampler.beta,
        sampler.G0,
        len(sampler.word),
        sampler.momenta,
        sampler.displacements,
    )
    sampler.accumulator.add(observation)
    sampler.save_checkpoint("running")

    saved = json.loads(
        (tmp_path / "checkpoint.json").read_text(encoding="utf-8")
    )
    assert saved["rng_state"]["bit_generator"] == "PCG64DXSM"
    assert saved["moves_since_rebuild"] == 5
    assert saved["accumulator"]["primary_traces"] == (
        sampler.accumulator.primary_traces
    )
    expected_random = sampler.rng.random(8)

    restored = _sampler(
        tmp_path,
        mode="hot",
        initial_order=6,
        seed=121_2030,
    )
    restored.load_checkpoint()
    actual_random = restored.rng.random(8)

    assert restored.completed_steps == 3
    assert restored.moves_since_rebuild == 5
    assert list(restored.word) == list(sampler.word)
    assert restored.accumulator.state() == sampler.accumulator.state()
    np.testing.assert_array_equal(actual_random, expected_random)
    expected_t = ctqmc.structured_product(
        restored.geometry.n_sites,
        restored.geometry.triangles,
        restored.catalog,
        list(restored.word),
    )
    np.testing.assert_allclose(
        restored.factors.T,
        expected_t,
        rtol=0.0,
        atol=2.0e-14,
    )
    np.testing.assert_allclose(
        restored.factors.Q,
        np.linalg.inv(np.eye(restored.geometry.n_sites) + expected_t),
        rtol=3.0e-12,
        atol=3.0e-13,
    )


@pytest.mark.slow
def test_n4_ed_mcmc_interface_and_complete_protocol(
    tmp_path: Path,
) -> None:
    manifest = _manifest(
        lx=2,
        ly=2,
        steps=30_000,
        warmup=3_000,
        seed=121_2040,
        mode="hot",
        initial_order=2,
    )
    manifest_path = tmp_path / "manifest.json"
    ctqmc.atomic_write_json(manifest_path, manifest)
    exact = ed.run_oracle(manifest_path)

    run_dir = tmp_path / "mcmc"
    sampler = ctqmc.CTQMC.from_manifest(
        manifest,
        run_dir,
        manifest_sha256=exact["runner_manifest_sha256"],
    )
    result = sampler.run()

    assert result["status"] == "run_complete_unvalidated"
    assert result["scope"] == "single_chain_execution_only"
    assert result["geometry"]["n_sites"] == 4
    assert set(result["move_acceptance"]) == {
        "insert",
        "delete",
        "rotate_left_to_right",
        "rotate_right_to_left",
    }
    for values in result["move_acceptance"].values():
        assert values["attempted"] >= values["accepted"] >= 0
        if values["attempted"]:
            assert values["rate"] == pytest.approx(
                values["accepted"] / values["attempted"]
            )
        else:
            assert values["rate"] is None
    assert result["timing"]["wall_seconds"] >= 0.0
    max_rss_kb = result["resource_usage"]["max_rss_kb"]
    assert max_rss_kb is None or max_rss_kb > 0
    assert result["observables"]["count"] > 0
    traces = result["observables"]["primary_traces"]
    assert all(
        len(values) == result["observables"]["count"]
        for values in traces.values()
    )

    scalar = result["observables"]["scalar"]
    exact_scalar = exact["observables"]["scalar"]
    for name in ("energy_density", "particle_density"):
        tolerance = max(
            8.0 * scalar[name]["naive_stderr"],
            0.08,
        )
        assert scalar[name]["mean"] == pytest.approx(
            exact_scalar[name],
            abs=tolerance,
        )
    assert result["observables"]["compressibility"] == pytest.approx(
        exact_scalar["compressibility"],
        abs=0.12,
    )

    for momentum, exact_values in exact["observables"]["momentum"].items():
        sampled = result["observables"]["momentum"][momentum]
        for name in ("one_body", "density_raw", "density_mode"):
            tolerance = max(
                8.0 * sampled[name]["naive_stderr_abs"],
                0.12,
            )
            _assert_complex_pair_close(
                sampled[name]["mean"],
                exact_values[name],
                atol=tolerance,
            )
        _assert_complex_pair_close(
            sampled["density_connected_from_means"],
            exact_values["density_connected_from_means"],
            atol=0.15,
        )

    complete_path = run_dir / "CHAIN_COMPLETE"
    assert complete_path.is_file()
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    result_bytes = (run_dir / "result.json").read_bytes()
    assert complete == {
        "schema_version": 1,
        "status": "run_complete_unvalidated",
        "scope": "single_chain_execution_only",
        "algorithm_id": ctqmc.ALGORITHM_ID,
        "manifest_sha256": exact["runner_manifest_sha256"],
        "result_json_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "completed_steps": manifest["monte_carlo"]["steps"],
    }


def test_manifest_helpers_do_not_mutate_input(tmp_path: Path) -> None:
    manifest = _manifest()
    original = deepcopy(manifest)
    ctqmc.CTQMC.from_manifest(manifest, tmp_path)
    assert manifest == original

def test_complete_validation_is_hash_bound_and_idempotent(tmp_path: Path) -> None:
    manifest = _manifest(steps=8, warmup=1)
    manifest_path = tmp_path / "manifest.json"
    ctqmc.atomic_write_json(manifest_path, manifest)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    output = tmp_path / "run"
    sampler = ctqmc.CTQMC.from_manifest(
        manifest, output, manifest_sha256=digest
    )
    result = sampler.run()
    assert ctqmc.validate_existing_complete(output, digest, 8) == result
    assert ctqmc.main([
        "--manifest", str(manifest_path), "--output", str(output)
    ]) == 0
    complete = json.loads((output / "CHAIN_COMPLETE").read_text())
    complete["result_json_sha256"] = "0" * 64
    ctqmc.atomic_write_json(output / "CHAIN_COMPLETE", complete)
    with pytest.raises(ctqmc.ManifestError, match="hash"):
        ctqmc.validate_existing_complete(output, digest, 8)


def test_only_recoverable_failed_marker_is_archived(tmp_path: Path) -> None:
    failed = tmp_path / "FAILED"
    ctqmc.atomic_write_json(
        failed,
        {"determinant_failure_kind": None, "error_type": "OSError"},
    )
    archive = ctqmc.archive_recoverable_failure(failed)
    assert not failed.exists()
    assert archive.is_file()
    scientific = tmp_path / "FAILED"
    ctqmc.atomic_write_json(
        scientific,
        {"determinant_failure_kind": "negative"},
    )
    with pytest.raises(ctqmc.ManifestError, match="scientific"):
        ctqmc.archive_recoverable_failure(scientific)
    assert scientific.is_file()


def test_resume_without_checkpoint_preserves_active_failed(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ctqmc.atomic_write_json(manifest_path, _manifest())
    output = tmp_path / "run"
    output.mkdir()
    failed = output / "FAILED"
    ctqmc.atomic_write_json(
        failed,
        {"determinant_failure_kind": None, "error_type": "OSError"},
    )
    original = failed.read_bytes()

    with pytest.raises(ctqmc.ManifestError, match="needs checkpoint"):
        ctqmc.main([
            "--manifest", str(manifest_path),
            "--output", str(output),
            "--resume",
        ])

    assert failed.read_bytes() == original
    assert not (output / "failures").exists()


def test_load_checkpoint_rejects_accumulator_count_mismatch(
    tmp_path: Path,
) -> None:
    sampler = _sampler(tmp_path)
    sampler.completed_steps = 3
    observation = ctqmc.measure_configuration(
        sampler.factors,
        sampler.geometry,
        sampler.beta,
        sampler.G0,
        len(sampler.word),
        sampler.momenta,
        sampler.displacements,
    )
    sampler.accumulator.add(observation)
    sampler.save_checkpoint("running")
    path = tmp_path / "checkpoint.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["accumulator"]["count"] = 0
    ctqmc.atomic_write_json(path, payload)

    restored = _sampler(tmp_path)
    with pytest.raises(ctqmc.ManifestError, match="accumulator count"):
        restored.load_checkpoint()
