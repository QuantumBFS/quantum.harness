from __future__ import annotations

from dataclasses import dataclass

from .algebra import PauliSum
from .hamiltonian import heisenberg_bond
from .lattice import SquareLattice


@dataclass(frozen=True)
class LPathCluster:
    color: int
    center: int
    left: int
    up: int

    @property
    def sites(self) -> frozenset[int]:
        return frozenset((self.center, self.left, self.up))

    @property
    def bonds(self) -> frozenset[tuple[int, int]]:
        return frozenset(
            (
                tuple(sorted((self.center, self.left))),
                tuple(sorted((self.center, self.up))),
            )
        )


def three_color_l_path_clusters(
    lattice: SquareLattice,
) -> tuple[tuple[LPathCluster, ...], ...]:
    """Square-lattice local-SU(2) decomposition from arXiv:2605.16016.

    A cluster centered at ``(x,y)`` contains the incoming horizontal and
    vertical bonds and has color ``x-y mod 3``.
    """

    if lattice.length % 3:
        raise ValueError("periodic three-color L-path decomposition requires 3 | L")
    groups: list[list[LPathCluster]] = [[], [], []]
    for y in range(lattice.length):
        for x in range(lattice.length):
            color = (x - y) % 3
            groups[color].append(
                LPathCluster(
                    color=color,
                    center=lattice.site(x, y),
                    left=lattice.site(x - 1, y),
                    up=lattice.site(x, y - 1),
                )
            )
    return tuple(tuple(group) for group in groups)


def l_path_cluster_hamiltonian(cluster: LPathCluster) -> PauliSum:
    return heisenberg_bond(cluster.center, cluster.left) + heisenberg_bond(
        cluster.center, cluster.up
    )


def three_l_path_fragments(lattice: SquareLattice) -> tuple[PauliSum, ...]:
    return tuple(
        sum(
            (l_path_cluster_hamiltonian(cluster) for cluster in group),
            PauliSum.zero(),
        )
        for group in three_color_l_path_clusters(lattice)
    )
