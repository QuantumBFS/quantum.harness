from __future__ import annotations

import json

import sympy as sp

from oracle.exterior_exact5_full_fock_cone import (
    _trace_compatible_column_generation,
    exact_fock_lift,
    exact_trace_compatible_certificate,
    main,
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


def test_cli_promotes_arbitrary_target_grade_only_through_trace_gate(
    capsys: object,
) -> None:
    exit_code = main(
        [
            "--target",
            "exact5-oddcycle-block-pair:132",
            "--grades",
            "4",
            "--attempts",
            "0",
            "--maxiter",
            "1",
            "--ray-counts",
            "5",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["candidate"] == "exact5-oddcycle-block-pair:132"
    assert payload["grades"] == [4]
    assert payload["status"] == "exact-trace-compatible-certificate"
    assert payload["certificate"]["right_inverse_replay"] is True
    assert payload["certificate"]["positive_retract_replay"] is True


def test_column_generation_promotes_exact_closure_between_milestones() -> None:
    atoms = (sp.ImmutableMatrix([[1, 0], [0, 0]]),)

    result = _trace_compatible_column_generation(
        atoms,
        [[1.0, 0.0], [1.0, 1.0]],
        ray_counts=(2, 4),
        tolerance=1.0e-9,
        max_denominator=32,
    )

    assert result["status"] == "exact-trace-compatible-certificate"
    assert result["certificate"]["ray_count"] == 3
