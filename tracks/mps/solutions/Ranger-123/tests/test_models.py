from numpy.testing import assert_allclose

from floquet_if_manybody.config import ModelConfig
from floquet_if_manybody.models import (
    coupling_operator,
    drive_operator,
    ising_hamiltonian,
)


def test_n3_ising_diagonal_is_open_boundary():
    cfg = ModelConfig(n=3, j=1, omega=1)
    assert_allclose(
        ising_hamiltonian(cfg).diagonal(),
        [-2, 0, 2, 0, 0, 2, 0, -2],
    )


def test_counterterm_has_explicit_physical_coefficient():
    bare = ModelConfig(n=2, counterterm_strength=0)
    dressed = ModelConfig(n=2, counterterm=True, counterterm_strength=0.125)
    s = coupling_operator(bare)
    assert_allclose(
        ising_hamiltonian(dressed) - ising_hamiltonian(bare),
        0.125 * (s @ s),
    )


def test_per_spin_drive_is_independent_of_bath_normalization() -> None:
    bounded = ModelConfig(
        n=3,
        normalization="bounded",
        drive_normalization="per_spin",
    )
    kac = ModelConfig(
        n=3,
        normalization="kac",
        drive_normalization="per_spin",
    )
    assert_allclose(drive_operator(bounded), drive_operator(kac))
    assert_allclose(drive_operator(bounded), 3 * coupling_operator(bounded))


def test_default_drive_operator_preserves_existing_semantics() -> None:
    config = ModelConfig(n=3, normalization="bounded")
    assert_allclose(drive_operator(config), coupling_operator(config))
