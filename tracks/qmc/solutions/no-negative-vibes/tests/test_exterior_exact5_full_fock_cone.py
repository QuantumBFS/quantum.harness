from __future__ import annotations

import sympy as sp

from oracle.exterior_exact5_full_fock_cone import (
    exact_fock_lift,
    exact_trace_compatible_certificate,
    particle_hole_pair_lift,
)


def test_full_fock_and_particle_hole_lifts_use_one_fixed_grade_basis() -> None:
    atom = sp.ImmutableMatrix([[1, 2], [3, 7]])

    full = exact_fock_lift(atom)
    paired = particle_hole_pair_lift(atom, 0)

    assert full == sp.ImmutableMatrix(
        sp.diag(
            sp.ImmutableMatrix([[1]]),
            atom,
            sp.ImmutableMatrix([[1]]),
        )
    )
    assert paired == sp.ImmutableMatrix(sp.diag(1, 1))


def test_trace_gate_requires_exact_positive_retract_not_only_invariance() -> None:
    atoms = (
        sp.ImmutableMatrix([[1, 1], [0, 1]]),
        sp.ImmutableMatrix([[1, 0], [1, 1]]),
    )
    trace_compatible_rays = tuple(
        sp.ImmutableMatrix(ray)
        for ray in ((1, 0), (0, 1), (1, 1))
    )

    hit = exact_trace_compatible_certificate(atoms, trace_compatible_rays)

    assert hit is not None
    assert hit["status"] == "exact-trace-compatible-certificate"
    assert hit["ray_count"] == 3
    assert hit["right_inverse_replay"] is True
    assert hit["positive_retract_replay"] is True

    # This redundant invariant cone spans R, but its two opposite rays admit
    # no C with R C = 1 and C R >= 0.
    rejected = exact_trace_compatible_certificate(
        (sp.ImmutableMatrix([[1]]),),
        (sp.ImmutableMatrix([1]), sp.ImmutableMatrix([-1])),
    )
    assert rejected is None
