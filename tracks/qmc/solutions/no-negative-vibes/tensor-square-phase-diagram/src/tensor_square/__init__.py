"""Tensor-square phase-diagram research code."""

from .algebra import (
    exterior_square,
    kron_sum,
    tensor_square_weight_direct,
    tensor_square_weight_eigenvalues,
    tensor_square_weight_factorized,
)
from .fock import (
    basis_states,
    d_gamma,
    many_body_hamiltonian,
    normal_ordered_q_square,
)
from .ed import build_sector_operators, edge_matrix, sector_result

__all__ = [
    "basis_states",
    "build_sector_operators",
    "d_gamma",
    "edge_matrix",
    "exterior_square",
    "kron_sum",
    "many_body_hamiltonian",
    "normal_ordered_q_square",
    "sector_result",
    "tensor_square_weight_direct",
    "tensor_square_weight_eigenvalues",
    "tensor_square_weight_factorized",
]
