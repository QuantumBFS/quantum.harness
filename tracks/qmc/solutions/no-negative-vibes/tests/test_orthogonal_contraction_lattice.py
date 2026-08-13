from __future__ import annotations

import numpy as np

from oracle.odd_block_tn_effective import effective_hamiltonian_audit
from oracle.orthogonal_contraction_candidate import (
    embed_orthogonal_plaquette_atoms,
    orthogonal_plaquette_generators,
    stoquastic_cycle_audit,
)
from oracle.orthogonal_contraction_majorana import (
    majorana_square_word_audit,
)
from oracle.semigroup_model_factory import (
    enumerate_semigroup_words,
    hermitian_semigroup_model,
)


def test_two_overlapping_plaquettes_keep_all_survival_properties() -> None:
    atoms = embed_orthogonal_plaquette_atoms(
        modes=6,
        plaquettes=((0, 1, 2, 3), (2, 3, 4, 5)),
    )
    model = hermitian_semigroup_model(
        atoms,
        coefficients=(1.0, 0.8, 1.0, 0.8),
    )
    body = effective_hamiltonian_audit(model.hamiltonian)
    signs = stoquastic_cycle_audit(model.hamiltonian)
    words = tuple(enumerate_semigroup_words(model, maximum_depth=3))

    assert model.hamiltonian.shape == (64, 64)
    assert body.maximum_density_body_order == 4
    assert abs(body.full_support_density_coefficient) < 1e-12
    assert body.nonzero_density_terms_by_order == (1, 6, 11, 8, 2, 0, 0)
    assert not signs.gauge_exists
    assert signs.frustrated_cycle == (8, 1, 2, 4, 8)
    assert signs.component_sizes == (1, 1, 6, 6, 15, 15, 20)
    assert signs.component_particle_numbers == (
        (0,),
        (6,),
        (1,),
        (5,),
        (2,),
        (4,),
        (3,),
    )
    assert len(words) == sum(8**depth for depth in range(1, 4))
    assert min(word.total_weight for word in words) > 0.0
    assert max(word.trace_identity_residual for word in words) < 3e-14


def test_known_majorana_double_copy_identity_is_recorded() -> None:
    generators = orthogonal_plaquette_generators()
    words = (
        ((0, False),),
        ((1, False),),
        ((0, False), (1, False)),
        ((0, False), (1, True), (0, False)),
        ((0, False), (1, False), (0, True), (1, True)),
    )
    for word in words:
        audit = majorana_square_word_audit(generators, word)
        assert audit.classification == "positive"
        assert audit.determinant_weight > 0.0
        assert audit.spin_trace_residual < 1e-12
        assert audit.square_residual < 1e-11
