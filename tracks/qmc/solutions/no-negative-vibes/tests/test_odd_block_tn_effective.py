from __future__ import annotations

from itertools import product

import numpy as np
from scipy.linalg import expm

from oracle.odd_block_tn_effective import (
    branch_history_audit,
    build_continuous_time_model,
    build_minimal_continuous_time_model,
    build_minimal_model,
    continuous_time_taylor_audit,
    effective_hamiltonian_audit,
    fixed_c3_block_tn_factor,
    is_tn2_contraction,
    is_tn2_matrix,
    minimal_tn_blocks,
    transpose_family_blocks,
)
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


def test_minimal_branches_share_one_fixed_c3_block_tn_family() -> None:
    model = build_minimal_model()

    assert all(is_tn2_contraction(block) for block in model.blocks)
    assert np.allclose(model.permutation @ model.permutation @ model.permutation, np.eye(6))
    assert np.allclose(
        model.branch,
        fixed_c3_block_tn_factor(model.blocks),
    )

    # This explicit rewrite is essential: B^T does not introduce a moving
    # partition.  It is the reverse C3 grade with transposed, cyclically
    # permuted TN blocks.
    rewritten = fixed_c3_block_tn_factor(
        transpose_family_blocks(model.blocks),
        direction=-1,
    )
    assert np.allclose(model.branch.T, rewritten, atol=1e-14)
    assert np.allclose(model.transpose_branch, rewritten, atol=1e-14)

    assert abs(np.linalg.norm(model.branch, 2) - 0.75) < 1e-13
    commutator = (
        model.branch @ model.branch.T
        - model.branch.T @ model.branch
    )
    assert abs(np.linalg.norm(commutator) - np.sqrt(581.0) / 50.0) < 1e-13
    assert (
        abs(
            np.linalg.det(np.eye(6) + model.branch)
            - 15193.0 / 12800.0
        )
        < 1e-13
    )
    assert (
        abs(
            np.linalg.det(
                np.eye(6) + model.branch @ model.branch.T
            )
            - 3705269.0 / 1310720.0
        )
        < 1e-12
    )


def test_minimal_transfer_is_hermitian_spd_with_recorded_anchors() -> None:
    model = build_minimal_model(beta=0.25)
    transfer = model.transfer
    eigenvalues = np.linalg.eigvalsh(transfer)

    assert np.allclose(transfer, transfer.T, atol=1e-14)
    assert eigenvalues[0] > 0.0
    assert eigenvalues[0] >= 1.0 - 2.0 * model.beta - 1e-13
    assert eigenvalues[-1] <= 1.0 + 2.0 * model.beta + 1e-13
    assert abs(eigenvalues[0] - 0.8113692907988211) < 1e-13
    assert abs(eigenvalues[-1] - 1.5) < 1e-13
    assert abs(np.linalg.cond(transfer) - 1.8487266119268542) < 1e-12

    expected = np.eye(64) + model.beta * (
        model.fock_branch + model.fock_branch.T
    )
    assert np.allclose(transfer, expected, atol=1e-14)


def test_direct_continuous_time_hamiltonian_is_six_mode_hermitian() -> None:
    model = build_minimal_continuous_time_model(coupling=1.0)
    hamiltonian = model.hamiltonian
    audit = effective_hamiltonian_audit(hamiltonian)

    assert model.branches[0].shape == (6, 6)
    assert hamiltonian.shape == (64, 64)
    assert np.allclose(
        hamiltonian,
        -(model.fock_branches[0] + model.fock_branches[0].T),
        atol=1e-14,
    )
    assert audit.hermiticity_residual < 1e-14
    assert audit.number_conservation_residual < 1e-14
    assert audit.off_diagonal_norm > 1.9
    assert audit.maximum_density_body_order == 6
    assert audit.nonzero_density_terms_by_order == (1, 6, 15, 20, 15, 6, 1)
    assert (
        abs(
            audit.full_support_density_coefficient.real
            - (-1.63640625)
        )
        < 1e-12
    )
    assert abs(audit.full_support_density_coefficient.imag) < 1e-13

    eigenvalues = np.linalg.eigvalsh(hamiltonian)
    assert abs(eigenvalues[0] - (-2.0)) < 1e-13
    assert abs(eigenvalues[-1] - 0.7545228368047133) < 1e-13


def test_continuous_time_taylor_words_reconstruct_physical_powers() -> None:
    model = build_minimal_continuous_time_model(coupling=1.0)
    audit = continuous_time_taylor_audit(model, max_order=5)

    # There are two branches, B and B^T, at each positive Taylor order.
    # The fixed-partition theorem proves all orders; this is only a short
    # executable guard plus an independent Fock-level reconstruction.
    assert audit.histories == sum(2**order for order in range(6))
    assert audit.negative_histories == 0
    assert audit.minimum_word_weight > 0.0
    assert audit.minimum_weighted_contribution > 0.0
    assert audit.maximum_imaginary_part == 0.0
    assert audit.maximum_trace_residual < 1e-11
    assert np.allclose(
        audit.order_weight_sums,
        audit.direct_fock_traces,
        atol=1e-11,
    )
    assert np.allclose(
        np.real(audit.direct_fock_traces),
        (
            64.0,
            2.37390625,
            7.711480883789062,
            9.374264806621554,
            18.379026128446057,
            33.852820467751584,
        ),
        atol=1e-12,
    )


def test_continuous_time_allows_multiple_atoms_and_large_couplings() -> None:
    first_blocks = minimal_tn_blocks()
    second_blocks = tuple(2.0 * block for block in first_blocks)
    assert not is_tn2_contraction(second_blocks[0])
    assert all(is_tn2_matrix(block) for block in second_blocks)

    model = build_continuous_time_model(
        (first_blocks, second_blocks),
        couplings=(0.75, 2.0),
        directions=(1, -1),
    )
    audit = continuous_time_taylor_audit(model, max_order=3)
    hamiltonian_audit = effective_hamiltonian_audit(model.hamiltonian)

    # Four branches (B_a and B_a^T for two atoms) appear at every order.
    # Coupling 2 and noncontractive TN blocks are both legal here: unlike the
    # discrete transfer, continuous time needs no beta<1/2 SPD bound.
    assert audit.histories == sum(4**order for order in range(4))
    assert audit.negative_histories == 0
    assert audit.minimum_word_weight > 0.0
    assert audit.minimum_weighted_contribution > 0.0
    assert audit.maximum_trace_residual < 1e-8
    assert hamiltonian_audit.hermiticity_residual < 1e-14
    assert hamiltonian_audit.number_conservation_residual < 1e-14
    for branch, transpose_branch in zip(
        model.branches,
        model.transpose_branches,
        strict=True,
    ):
        assert np.allclose(branch.T, transpose_branch, atol=1e-14)


def test_short_history_words_regress_the_arbitrary_depth_theorem() -> None:
    model = build_minimal_model()
    audit = branch_history_audit(model, max_depth=5)

    # The module-level fixed-partition theorem, not this finite enumeration,
    # is the reason every depth is nonnegative.
    assert audit.histories == sum(3**depth for depth in range(1, 6))
    assert audit.negative_histories == 0
    assert audit.minimum_weight > 0.0
    assert audit.maximum_imaginary_part == 0.0

    # Cross-check the determinant and direct Fock-trace languages on
    # representative noncommuting branch words.
    one_particle = (
        np.eye(6),
        model.branch,
        model.transpose_branch,
    )
    fock = (
        np.eye(64),
        model.fock_branch,
        model.fock_branch.T,
    )
    for word in ((1,), (2,), (1, 2), (2, 1, 1), (1, 2, 1, 2)):
        one_particle_product = np.eye(6)
        fock_product = np.eye(64)
        for branch_index in word:
            one_particle_product = (
                one_particle_product @ one_particle[branch_index]
            )
            fock_product = fock_product @ fock[branch_index]
        determinant_weight = np.linalg.det(
            np.eye(6) + one_particle_product
        )
        assert determinant_weight >= -1e-12
        assert abs(np.trace(fock_product) - determinant_weight) < 1e-11

        reconstructed_fock = number_conserving_gaussian_fock_matrix(
            one_particle_product
        )
        assert np.allclose(fock_product, reconstructed_fock, atol=1e-11)


def test_effective_minus_log_is_hermitian_and_has_six_body_support() -> None:
    model = build_minimal_model(beta=0.25, time_step=1.0)
    hamiltonian = model.effective_hamiltonian
    audit = effective_hamiltonian_audit(hamiltonian)

    assert audit.hermiticity_residual < 1e-13
    assert audit.number_conservation_residual < 1e-13
    assert audit.off_diagonal_norm > 0.46
    assert audit.maximum_density_body_order == 6
    assert audit.nonzero_density_terms_by_order == (1, 6, 15, 20, 15, 6, 1)
    assert (
        abs(
            audit.full_support_density_coefficient.real
            - (-0.3622850663875639)
        )
        < 1e-12
    )
    assert abs(audit.full_support_density_coefficient.imag) < 1e-13

    # The transfer really is exp(-H_eff) at dt=1.  The nonzero six-density
    # Möbius coefficient is a lower-bound body-support certificate, not a
    # claim that the diagonal audit exhausts all normal-ordered terms.
    assert np.allclose(expm(-hamiltonian), model.transfer, atol=1e-12)


def test_all_depth_three_branch_words_have_nonnegative_direct_fock_trace() -> None:
    """Small exhaustive Fock-level guard independent of the theorem proof."""

    model = build_minimal_model()
    branches = (
        np.eye(64),
        model.fock_branch,
        model.fock_branch.T,
    )
    for word in product(range(3), repeat=3):
        propagation = np.eye(64)
        for branch_index in word:
            propagation = propagation @ branches[branch_index]
        assert np.trace(propagation) >= -1e-12
