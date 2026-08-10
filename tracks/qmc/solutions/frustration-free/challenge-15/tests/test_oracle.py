from copy import deepcopy

import jax
import numpy as np
import pytest

import challenge15.oracle as oracle
from challenge15.fermions import DeterminantBasis
from challenge15.model import ModelConfig, ProjectedPfaffianNQS
from challenge15.oracle import (
    _ground_diagnostics,
    oracle_cache_payload,
    oracle_from_cache_payload,
    solve_required_target_sectors_sparse,
    solve_target_sectors,
)
from challenge15.spec import SphereSpec


def test_oracle_returns_ground_l0_and_lowest_l2():
    result = solve_target_sectors(SphereSpec(4))
    assert result.energy_l2 > result.energy_l0
    assert result.gap == result.energy_l2 - result.energy_l0
    assert result.residual_l0 < 1e-11
    assert result.residual_l2 < 1e-11
    assert result.l2_variance_l0 < 1e-20
    assert result.l2_variance_l2 < 1e-20


def test_sparse_required_sector_solver_cross_checks_dense_small_n():
    dense = solve_target_sectors(SphereSpec(4))
    sparse_target = solve_required_target_sectors_sparse(SphereSpec(4))

    assert tuple(item.angular_momentum for item in sparse_target.sectors) == (0, 2)
    assert sparse_target.energy_l0 == pytest.approx(dense.energy_l0, abs=1e-10)
    assert sparse_target.energy_l2 == pytest.approx(dense.energy_l2, abs=1e-10)
    assert sparse_target.absolute_excitation_energy == pytest.approx(
        dense.absolute_excitation_energy, abs=1e-10
    )
    assert sparse_target.absolute_excitation_l == dense.absolute_excitation_l
    assert sparse_target.absolute_excitation_gap == pytest.approx(
        dense.absolute_excitation_gap, abs=1e-10
    )
    assert len(sparse_target.low_energy_states) >= 2
    assert all(item.eigenpair_residual <= 1e-10 for item in sparse_target.low_energy_states)
    assert all(item.l2_residual <= 1e-11 for item in sparse_target.low_energy_states)
    assert all(item.l2_variance <= 1e-20 for item in sparse_target.low_energy_states)
    for diagnostic in sparse_target.sparse_symmetry_diagnostics:
        assert diagnostic.gram_defect <= 1e-12
        assert diagnostic.l2_target_residual <= 1e-11
        assert diagnostic.ladder_intertwining_residual <= 1e-11


def test_oracle_cache_recomputes_hashes_and_symmetry_diagnostics():
    result = solve_required_target_sectors_sparse(SphereSpec(4))
    cache = oracle_cache_payload(result)
    assert cache["schema"] == "challenge15.oracle-cache.v2"
    assert cache["solver_mode"] == "sparse-production"
    assert cache["summary"]["sparse_symmetry_diagnostics"]
    assert cache["summary"]["low_energy_scan"]
    assert cache["low_energy_vectors"]
    assert set(cache["operators"]) == {"hamiltonian", "l2"}
    restored = oracle_from_cache_payload(cache)
    assert restored.energy_l0 == result.energy_l0
    assert restored.energy_l2 == result.energy_l2
    assert restored.absolute_excitation_l == result.absolute_excitation_l
    assert dict(restored.array_hash_items) == cache["summary"]["array_hashes"]

    forged_hash = deepcopy(cache)
    key = next(iter(forged_hash["summary"]["array_hashes"]))
    forged_hash["summary"]["array_hashes"][key] = "0" * 64
    with pytest.raises(ValueError, match="declared array hash"):
        oracle_from_cache_payload(forged_hash)

    forged_diagnostics = deepcopy(cache)
    forged_diagnostics["summary"]["sparse_symmetry_diagnostics"][0][
        "gram_defect"
    ] = 5e-13
    with pytest.raises(ValueError, match="symmetry diagnostics"):
        oracle_from_cache_payload(forged_diagnostics)


@pytest.mark.parametrize(
    "field",
    ["solver_mode", "exact_sectors", "operators", "low_energy_vectors"],
)
def test_sparse_oracle_cache_rejects_omitted_required_fields(field):
    cache = oracle_cache_payload(
        solve_required_target_sectors_sparse(SphereSpec(4))
    )
    cache.pop(field)
    with pytest.raises(ValueError, match="schema|required|missing"):
        oracle_from_cache_payload(cache)


@pytest.mark.parametrize(
    "field", ["sparse_symmetry_diagnostics", "low_energy_scan"]
)
def test_sparse_oracle_cache_rejects_omitted_required_diagnostics(field):
    cache = oracle_cache_payload(
        solve_required_target_sectors_sparse(SphereSpec(4))
    )
    cache["summary"].pop(field)
    with pytest.raises(ValueError, match="required"):
        oracle_from_cache_payload(cache)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("row_pivots", [17, 16], "row pivots"),
        ("multiplicity", 99, "multiplicity"),
        ("workspace_elements_upper_bound", 1, "workspace"),
        ("dense_projector_allocated", True, "allocation"),
    ],
)
def test_sparse_oracle_cache_recomputes_structural_metadata(
    field, replacement, message
):
    cache = oracle_cache_payload(
        solve_required_target_sectors_sparse(SphereSpec(4))
    )
    cache["summary"]["sparse_symmetry_diagnostics"][0][field] = replacement
    with pytest.raises(ValueError, match=message):
        oracle_from_cache_payload(cache)


def test_sparse_oracle_cache_rejects_low_energy_vector_and_hash_tamper():
    cache = oracle_cache_payload(
        solve_required_target_sectors_sparse(SphereSpec(4))
    )
    forged_vector = deepcopy(cache)
    forged_vector["low_energy_vectors"][0]["data_base64"] = (
        forged_vector["low_energy_vectors"][1]["data_base64"]
    )
    with pytest.raises(ValueError, match="SHA256"):
        oracle_from_cache_payload(forged_vector)

    forged_hash = deepcopy(cache)
    forged_hash["low_energy_vectors"][0]["array_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="declared array hash"):
        oracle_from_cache_payload(forged_hash)

    forged_diagnostic = deepcopy(cache)
    forged_diagnostic["summary"]["low_energy_scan"][0][
        "eigenpair_residual"
    ] = 5e-11
    with pytest.raises(ValueError, match="low-energy diagnostics"):
        oracle_from_cache_payload(forged_diagnostic)


def test_dense_oracle_cache_requires_distinct_dense_diagnostics():
    cache = oracle_cache_payload(solve_target_sectors(SphereSpec(4)))
    assert cache["solver_mode"] == "dense-small-n"
    assert cache["summary"]["dense_diagnostics"]
    assert cache["summary"]["sparse_symmetry_diagnostics"] == []
    assert cache["summary"]["low_energy_scan"] == []
    oracle_from_cache_payload(cache)

    cache["summary"]["dense_diagnostics"] = None
    with pytest.raises(ValueError, match="dense diagnostics"):
        oracle_from_cache_payload(cache)


@pytest.mark.parametrize(
    "solver",
    [solve_target_sectors, solve_required_target_sectors_sparse],
    ids=["dense", "sparse"],
)
def test_oracle_cache_recomputes_top_level_energy_aggregates(solver):
    cache = oracle_cache_payload(solver(SphereSpec(4)))
    energy_fields = cache["summary"]["energies"]["electron_electron"]
    tampered_values = {
        "l2": energy_fields["l2"] + 1e-5,
        "delta_l2": energy_fields["delta_l2"] + 1e-5,
        "absolute_excitation": energy_fields["absolute_excitation"] + 1e-5,
        "absolute_gap": energy_fields["absolute_gap"] + 1e-5,
        "absolute_excitation_l": energy_fields["absolute_excitation_l"] + 1,
    }
    for field, value in tampered_values.items():
        forged = deepcopy(cache)
        forged["summary"]["energies"]["electron_electron"][field] = value
        with pytest.raises(ValueError, match="energy|gap|excitation"):
            oracle_from_cache_payload(forged)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("delete-sector", "complete"),
        ("delete-metadata", "metadata"),
        ("extra-sector", "complete"),
        ("mismatched-multiplicity", "multiplicity"),
    ],
)
def test_dense_oracle_cache_requires_complete_sector_decomposition(
    mutation, message
):
    cache = oracle_cache_payload(solve_target_sectors(SphereSpec(4)))
    sectors = cache["summary"]["sectors"]
    non_target = next(
        item for item in sectors if item["angular_momentum"] not in (0, 2)
    )
    if mutation == "delete-sector":
        sectors.remove(non_target)
    elif mutation == "delete-metadata":
        cache["summary"]["dimensions"]["sector_multiplicities"].pop(
            str(non_target["angular_momentum"])
        )
    elif mutation == "extra-sector":
        extra = deepcopy(non_target)
        extra["angular_momentum"] = SphereSpec(4).l_max + 1
        sectors.append(extra)
    else:
        non_target["multiplicity"] += 1
        cache["summary"]["dimensions"]["sector_multiplicities"][
            str(non_target["angular_momentum"])
        ] += 1
    with pytest.raises(ValueError, match=message):
        oracle_from_cache_payload(cache)


def test_quadrature_rotation_cache_reuses_input_hashed_intermediates():
    oracle.clear_quadrature_cache()
    spec = SphereSpec(2)
    first = oracle._cached_beta_rotations(spec, 5)
    second = oracle._cached_beta_rotations(spec, 5)

    assert first is second
    assert oracle.quadrature_cache_info() == {
        "hits": 1,
        "misses": 1,
        "entries": 1,
    }


def test_oracle_scans_every_accessible_sector_and_diagonalizes_each_once(monkeypatch):
    calls = 0
    original = np.linalg.eigh

    def counting_eigh(matrix):
        nonlocal calls
        calls += 1
        return original(matrix)

    monkeypatch.setattr(oracle.np.linalg, "eigh", counting_eigh)
    spec = SphereSpec(4)
    result = solve_target_sectors(spec)

    expected_l = tuple(
        target_l
        for target_l in range(spec.l_max + 1)
        if DeterminantBasis.with_two_m(spec, 2 * target_l).dimension
        > (
            DeterminantBasis.with_two_m(spec, 2 * (target_l + 1)).dimension
            if target_l < spec.l_max
            else 0
        )
    )
    assert tuple(sector.angular_momentum for sector in result.sectors) == expected_l
    assert all(sector.multiplicity > 0 for sector in result.sectors)
    # One full L2 solve, then one r×r thin-Gram solve and one projected
    # Hamiltonian solve per accessible sector.
    assert calls == 1 + 2 * len(result.sectors)
    candidates = [
        (energy, sector.angular_momentum)
        for sector in result.sectors
        for index, energy in enumerate(sector.spectrum)
        if not (sector.angular_momentum == 0 and index == 0)
    ]
    assert result.absolute_excitation_l == min(candidates)[1]


def test_payload_is_strict_finite_and_provenance_bound():
    payload = solve_target_sectors(SphereSpec(4)).to_payload()

    assert payload["schema"] == "challenge15.oracle-result.v1"
    assert payload["physical_conventions"]["two_q"] == 9
    assert payload["dimensions"]["m_zero"] > 0
    assert payload["git_revision"]
    assert payload["package_versions"]["numpy"]
    assert payload["source_hashes"]
    assert payload["array_hashes"]
    assert payload["pair_pseudopotentials"]
    assert payload["diagnostics"]["mean_l2_l0"] == pytest.approx(0.0, abs=1e-12)
    assert payload["diagnostics"]["mean_l2_l2"] == pytest.approx(6.0, abs=1e-12)
    assert "l2_target_deviation_squared_l0" in payload["diagnostics"]
    assert "l2_target_deviation_squared_l2" in payload["diagnostics"]
    assert "hamiltonian.dense" in payload["array_hashes"]
    assert "l2.eigenvectors" in payload["array_hashes"]
    assert all(
        f"sector.{sector['angular_momentum']}.eigenvectors" in payload["array_hashes"]
        for sector in payload["sectors"]
    )
    assert all(len(digest) == 64 for digest in payload["array_hashes"].values())


def test_l2_variance_is_centered_not_target_residual_squared():
    l2 = np.diag([0.0, 2.0]).astype(np.complex128)
    isometry = np.eye(2, dtype=np.complex128)
    eigenvalues = np.array([0.0, 1.0])
    eigenvectors = np.array(
        [[1.0, 1.0], [1.0, -1.0]],
        dtype=np.complex128,
    ) / np.sqrt(2.0)
    hamiltonian = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.conj().T

    diagnostics = _ground_diagnostics(
        hamiltonian,
        l2,
        isometry,
        eigenvalues,
        eigenvectors,
        target_l=0,
    )

    assert diagnostics.mean_l2 == pytest.approx(1.0)
    assert diagnostics.l2_variance == pytest.approx(1.0)
    assert diagnostics.l2_target_deviation_squared == pytest.approx(2.0)
    assert diagnostics.l2_variance != diagnostics.l2_target_deviation_squared


def test_exact_nqs_uses_public_sector_coefficient_path(monkeypatch):
    spec = SphereSpec(2)
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=2, hidden_width=7, depth=1, token_width=3)
    )
    spinors = np.asarray(
        [[1.0, 0.1j], [0.4 - 0.2j, 0.9]],
        dtype=np.complex128,
    )
    parameters = model.init(jax.random.key(7015), spec, spinors, target_l=0)
    exact_oracle = solve_target_sectors(spec)
    calls = []
    original = oracle.nqs_sector_coefficients

    def observed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append((kwargs["target_l"], result.copy()))
        return result

    monkeypatch.setattr(oracle, "nqs_sector_coefficients", observed)
    metrics = oracle.evaluate_exact_nqs(
        spec,
        parameters,
        exact_oracle,
        determinant_block=1,
        carrier_block=1,
    )

    assert [target_l for target_l, _ in calls] == [0, 2]
    for target_l, coefficients in calls:
        np.testing.assert_allclose(
            coefficients,
            metrics.normalized_sector_coefficients(target_l),
            atol=2e-12,
            rtol=0.0,
        )
