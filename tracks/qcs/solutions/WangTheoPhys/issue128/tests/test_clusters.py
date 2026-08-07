from fractions import Fraction

import numpy as np

from trottercert.algebra import PauliString, PauliSum, to_dense
from trottercert.clusters import (
    _sqrt_fraction_upper,
    build_uniform_cluster_certificate,
    computational_row_sum_bound,
    computational_row_taxicab_bound,
    build_partitioned_operator_certificate,
    build_full_patch_operator_certificate,
    collatz_taxicab_certificate,
    greedy_anticommuting_certificate,
    paulis_anticommute,
    phase_partitioned_collatz_certificate,
)
from trottercert.lattice import SquareLattice
from trottercert.orbits import canonical_translation, translation_orbits


def test_rational_sqrt_upper_is_outward() -> None:
    bound = _sqrt_fraction_upper(Fraction(2), decimal_places=12)
    assert bound * bound >= 2
    assert float(bound) - np.sqrt(2) < 1e-11


def test_anticommuting_group_norm_bound() -> None:
    x = PauliString({0: "X"})
    y = PauliString({0: "Y"})
    z = PauliString({0: "Z"})
    assert paulis_anticommute(x, y)
    operator = PauliSum({x: 1, y: 2, z: 2})
    certificate = greedy_anticommuting_certificate(operator)
    assert len(certificate.groups) == 1
    assert certificate.bound * certificate.bound >= 9
    assert float(certificate.bound) < 3 + 1e-12


def test_row_sum_bound_upper_bounds_spectral_norm() -> None:
    operator = (
        PauliSum.term(PauliString({0: "X"}), Fraction(1, 3))
        + PauliSum.term(PauliString({0: "Z", 1: "Z"}), Fraction(2, 5))
    )
    bound = computational_row_sum_bound(operator, 2)
    norm = np.linalg.norm(to_dense(operator, 2), ord=2)
    assert float(bound) >= norm
    fast_bound = computational_row_taxicab_bound(operator, 2)
    assert float(fast_bound) >= norm
    collatz = collatz_taxicab_certificate(operator, 2, iterations=20)
    assert float(collatz.bound) >= norm
    assert collatz.bound <= fast_bound


def test_uniform_cluster_weights_reconstruct_orbit_density() -> None:
    lattice = SquareLattice(4)
    seed = PauliString({lattice.site(0, 0): "X", lattice.site(1, 0): "X"})
    _, members = canonical_translation(seed, lattice)
    orbits = translation_orbits(PauliSum({member: 1 for member in members}), lattice)
    certificate = build_uniform_cluster_certificate(orbits, 3, 2)
    assert certificate.placements[0].weights == (Fraction(1, 4),) * 4
    assert certificate.row_sum_bound > 0


def test_colored_orbit_placements_respect_unit_cell_stride() -> None:
    lattice = SquareLattice(4)
    seed = PauliString({lattice.site(1, 0): "X"})
    _, members = canonical_translation(seed, lattice, (2, 2))
    orbits = translation_orbits(
        PauliSum({member: 1 for member in members}),
        lattice,
        unit_cell=(2, 2),
    )
    certificate = build_uniform_cluster_certificate(orbits, 4, 3)
    assert certificate.placements[0].offsets == ((0, 0), (2, 0), (0, 2), (2, 2))


def test_partitioned_certificate_upper_bounds_small_operator_norm() -> None:
    lattice = SquareLattice(4)
    seed = PauliString({lattice.site(0, 0): "Z"})
    _, members = canonical_translation(seed, lattice, (2, 2))
    operator = PauliSum({member: 1 for member in members})
    certificate = build_partitioned_operator_certificate(operator, lattice)
    assert certificate.global_bound == 4
    full = build_full_patch_operator_certificate(operator, lattice)
    assert full.global_bound == 4
    phased = phase_partitioned_collatz_certificate(
        operator, lattice, iterations=10
    )
    assert phased.global_bound == 4
