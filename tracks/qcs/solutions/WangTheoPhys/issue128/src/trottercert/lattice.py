from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SquareLattice:
    length: int

    def __post_init__(self) -> None:
        if self.length < 4 or self.length % 2:
            raise ValueError("periodic matching lattice requires even L >= 4")

    @property
    def n_sites(self) -> int:
        return self.length * self.length

    def site(self, x: int, y: int) -> int:
        return (y % self.length) * self.length + (x % self.length)

    def coordinates(self, site: int) -> tuple[int, int]:
        if not 0 <= site < self.n_sites:
            raise ValueError("site outside lattice")
        return site % self.length, site // self.length

    @staticmethod
    def canonical_bond(u: int, v: int) -> tuple[int, int]:
        if u == v:
            raise ValueError("self bonds are not allowed")
        return (u, v) if u < v else (v, u)

    def bonds(self) -> tuple[tuple[int, int], ...]:
        edges: set[tuple[int, int]] = set()
        for y in range(self.length):
            for x in range(self.length):
                u = self.site(x, y)
                edges.add(self.canonical_bond(u, self.site(x + 1, y)))
                edges.add(self.canonical_bond(u, self.site(x, y + 1)))
        return tuple(sorted(edges))

    def four_matchings(self) -> tuple[tuple[tuple[int, int], ...], ...]:
        groups: list[list[tuple[int, int]]] = [[], [], [], []]
        for y in range(self.length):
            for x in range(0, self.length, 2):
                groups[0].append(self.canonical_bond(self.site(x, y), self.site(x + 1, y)))
                groups[1].append(
                    self.canonical_bond(self.site(x + 1, y), self.site(x + 2, y))
                )
        for x in range(self.length):
            for y in range(0, self.length, 2):
                groups[2].append(self.canonical_bond(self.site(x, y), self.site(x, y + 1)))
                groups[3].append(
                    self.canonical_bond(self.site(x, y + 1), self.site(x, y + 2))
                )
        return tuple(tuple(sorted(set(group))) for group in groups)
