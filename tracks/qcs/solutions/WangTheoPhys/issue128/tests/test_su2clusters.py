from trottercert.hamiltonian import full_heisenberg_hamiltonian
from trottercert.lattice import SquareLattice
from trottercert.su2clusters import (
    three_color_l_path_clusters,
    three_l_path_fragments,
)


def test_three_color_decomposition_requires_compatible_torus() -> None:
    try:
        three_color_l_path_clusters(SquareLattice(10))
    except ValueError as error:
        assert "requires 3 | L" in str(error)
    else:
        raise AssertionError("expected incompatible periodic coloring to fail")


def test_same_color_clusters_are_site_disjoint_l6() -> None:
    lattice = SquareLattice(6)
    groups = three_color_l_path_clusters(lattice)
    assert all(len(group) == lattice.n_sites // 3 for group in groups)
    for group in groups:
        all_sites = [site for cluster in group for site in cluster.sites]
        assert len(all_sites) == len(set(all_sites))


def test_three_color_clusters_cover_every_bond_once() -> None:
    lattice = SquareLattice(6)
    clusters = three_color_l_path_clusters(lattice)
    covered = [bond for group in clusters for cluster in group for bond in cluster.bonds]
    assert len(covered) == len(set(covered))
    assert set(covered) == set(lattice.bonds())
    assert sum(three_l_path_fragments(lattice)[1:], three_l_path_fragments(lattice)[0]) == (
        full_heisenberg_hamiltonian(lattice)
    )
