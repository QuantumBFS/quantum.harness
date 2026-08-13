from __future__ import annotations

import sympy as sp

from oracle.exterior_exact5_polyhedral_cone import (
    _rationalize_ray,
    exact_polyhedral_certificate,
    polyhedral_column_generation,
)


def test_exact_polyhedral_certificate_replays_redundant_rays() -> None:
    normalized_tiny = _rationalize_ray(
        (1.0e-12, -2.0e-12),
        max_denominator=32,
    )
    assert normalized_tiny == sp.ImmutableMatrix([1, -2])

    rays = tuple(
        sp.ImmutableMatrix(ray)
        for ray in ((1, 0), (0, 1), (1, 1))
    )
    atoms = (
        sp.ImmutableMatrix([[1, 1], [0, 1]]),
        sp.ImmutableMatrix([[1, 0], [1, 1]]),
    )

    certificate = exact_polyhedral_certificate(atoms, rays)

    assert certificate is not None
    assert certificate["status"] == "exact-certificate"
    assert certificate["ray_count"] == 3
    assert certificate["rank"] == 2
    assert certificate["minimum_action_entry"] == {
        "numerator": 0,
        "denominator": 1,
    }


def test_column_generation_closes_a_four_ray_square_cone_exactly() -> None:
    rotation = sp.ImmutableMatrix([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    rays = tuple(
        sp.ImmutableMatrix(ray)
        for ray in ((1, 1, 1), (-1, 1, 1), (-1, -1, 1))
    )

    result = polyhedral_column_generation(
        (rotation, rotation.T),
        rays,
        ray_counts=(3, 4),
    )

    assert result["status"] == "exact-certificate"
    assert result["certificate"]["ray_count"] == 4
    assert result["certificate"]["rank"] == 3
