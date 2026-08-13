from __future__ import annotations

import numpy as np

from oracle.orthogonal_contraction_physics import (
    build_overlapping_plaquette_model,
    exact_diagonalization_audit,
    group_algebra_audit,
)


def test_six_mode_group_algebra_has_only_hodge_reduction() -> None:
    model = build_overlapping_plaquette_model(6)
    audit = group_algebra_audit(model)

    assert audit.one_particle_lie_dimension == 15
    assert tuple(item.dimension for item in audit.sectors) == (
        1,
        6,
        15,
        20,
        15,
        6,
        1,
    )
    assert tuple(item.commutant_nullity for item in audit.sectors) == (
        1,
        1,
        1,
        2,
        1,
        1,
        1,
    )
    assert min(
        item.smallest_nonzero_singular_value
        for item in audit.sectors
        if item.dimension > 1
    ) > 1e-3
    assert audit.middle_hodge_square_residual < 1e-12
    assert audit.middle_hodge_commutator_residual < 1e-12
    assert audit.middle_chiral_dimensions == (10, 10)
    assert audit.middle_chiral_commutant_nullities == (1, 1)


def test_small_chain_ed_observables_are_nontrivial_and_reproducible() -> None:
    audits = tuple(
        exact_diagonalization_audit(modes)
        for modes in (4, 6, 8)
    )

    assert tuple(item.sector_dimension for item in audits) == (6, 20, 70)
    assert tuple(item.ground_multiplicity for item in audits) == (1, 2, 1)
    assert np.allclose(
        [item.ground_energy for item in audits],
        [-3.2506712298193565, -5.8558079887390075, -9.545572656828034],
        atol=1e-11,
    )
    assert np.allclose(
        [item.first_distinct_gap for item in audits],
        [0.49779416271696864, 0.39812535587063547, 0.011900162512203494],
        atol=1e-10,
    )
    assert all(
        abs(sum(item.plaquette_energy_profile) - item.ground_energy)
        < 1e-10
        for item in audits
    )
    assert abs(
        audits[1].chiral_ground_energies[0]
        - audits[1].chiral_ground_energies[1]
    ) < 1e-11
    assert all(
        min(item.chiral_internal_gaps) > 0.1 for item in audits
    )
    assert all(
        min(item.chiral_ground_wick_residuals) > 1e-2
        for item in audits
    )
    assert all(
        item.staggered_density_structure_factor >= -1e-12
        for item in audits
    )
    for audit in audits:
        assert np.isclose(
            sum(audit.density_profile),
            audit.particle_number,
            atol=1e-12,
        )
        assert max(
            abs(value - 0.5) for value in audit.density_profile
        ) < 1e-9
