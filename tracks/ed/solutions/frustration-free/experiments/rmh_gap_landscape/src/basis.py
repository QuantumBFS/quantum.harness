"""Thin factory for QuSpin sector bases."""

from quspin.basis import spinful_fermion_basis_1d


def make_sector_basis(L: int, N_up: int, N_down: int):
    """Return a QuSpin spinful_fermion_basis_1d for fixed (N_up, N_down)."""
    return spinful_fermion_basis_1d(L, Nf=(N_up, N_down))
