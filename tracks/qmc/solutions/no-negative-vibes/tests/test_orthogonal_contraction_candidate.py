from __future__ import annotations

import numpy as np

from oracle.odd_block_tn_effective import effective_hamiltonian_audit
from oracle.orthogonal_contraction_candidate import (
    build_orthogonal_plaquette_model,
    embed_orthogonal_plaquette_atoms,
    orthogonal_plaquette_atoms,
    orthogonal_plaquette_generators,
    stoquastic_cycle_audit,
)
from oracle.semigroup_model_factory import enumerate_semigroup_words


def test_explicit_plaquette_atoms_are_noncommuting_so4_matrices() -> None:
    generators = orthogonal_plaquette_generators()
    atoms = orthogonal_plaquette_atoms()
    for generator, atom in zip(generators, atoms, strict=True):
        assert np.allclose(generator.T, -generator, atol=1e-14)
        assert np.allclose(atom.T @ atom, np.eye(4), atol=1e-13)
        assert abs(np.linalg.det(atom) - 1.0) < 1e-13
    assert np.linalg.norm(atoms[0] @ atoms[1] - atoms[1] @ atoms[0]) > 1.8


def test_plaquette_hamiltonian_is_interacting_and_sign_frustrated() -> None:
    model = build_orthogonal_plaquette_model()
    body = effective_hamiltonian_audit(model.hamiltonian)
    signs = stoquastic_cycle_audit(model.hamiltonian)

    assert body.hermiticity_residual < 1e-14
    assert body.number_conservation_residual < 1e-14
    assert body.maximum_density_body_order == 4
    assert abs(
        body.full_support_density_coefficient.real
        - (-1.0636412654618002)
    ) < 1e-12
    assert not signs.gauge_exists
    assert signs.frustrated_cycle == (8, 1, 2, 4, 8)
    assert tuple(np.sign(signs.cycle_matrix_elements)) == (-1.0, -1.0, 1.0, -1.0)
    required_product = np.prod(
        [-np.sign(value) for value in signs.cycle_matrix_elements]
    )
    assert required_product == -1.0
    assert signs.component_sizes == (1, 1, 4, 4, 6)
    assert signs.component_particle_numbers == ((0,), (4,), (1,), (3,), (2,))


def test_every_short_vertex_word_has_nonnegative_determinant_weight() -> None:
    model = build_orthogonal_plaquette_model()
    words = tuple(enumerate_semigroup_words(model, maximum_depth=5))

    assert len(words) == sum(4**depth for depth in range(1, 6))
    assert min(word.total_weight for word in words) > 0.0
    assert max(word.trace_identity_residual for word in words) < 1e-12


def test_overlapping_plaquette_embedding_remains_orthogonal_and_local() -> None:
    atoms = embed_orthogonal_plaquette_atoms(
        modes=6,
        plaquettes=((0, 1, 2, 3), (2, 3, 4, 5)),
    )
    assert len(atoms) == 4
    for atom in atoms:
        assert np.allclose(atom.T @ atom, np.eye(6), atol=1e-13)

    # The first plaquette is exactly the identity outside its support.
    for atom in atoms[:2]:
        assert np.allclose(atom[4:, 4:], np.eye(2), atol=1e-14)
        assert np.allclose(atom[:4, 4:], 0.0, atol=1e-14)
        assert np.allclose(atom[4:, :4], 0.0, atol=1e-14)

    product = atoms[0] @ atoms[2].T @ atoms[1] @ atoms[3].T
    assert np.allclose(product.T @ product, np.eye(6), atol=1e-12)
    assert np.linalg.det(np.eye(6) + product) >= -1e-12
