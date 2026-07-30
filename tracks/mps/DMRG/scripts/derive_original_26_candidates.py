from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

from vmcrg_ref.operators import EVEN_SHAPES, Vertex, d4_orbit


def canonical(vertices: tuple[Vertex, ...]) -> tuple[Vertex, ...]:
    """Choose one translation- and D4-invariant representative."""
    return min(d4_orbit(vertices))


def pair_candidates(max_component: int = 6) -> list[tuple[int, Vertex]]:
    """Return D4-inequivalent pair displacements ordered by squared range."""
    result = []
    for a in range(1, max_component + 1):
        for b in range(a + 1):
            result.append((a * a + b * b, (a, b)))
    return sorted(result, key=lambda item: (item[0], -item[1][0], item[1][1]))


@dataclass(frozen=True)
class FourSpinCandidate:
    vertices: tuple[Vertex, ...]
    diameter_squared: int
    pair_distance_sum: int
    pair_distances_squared: tuple[int, ...]


def four_spin_candidates() -> list[FourSpinCandidate]:
    """Enumerate four-site D4 orbits that fit in a 3 x 3 window.

    Every orbit with squared diameter at most eight fits in this window, so
    this finite enumeration is complete through the thirteenth candidate.
    """
    sites = tuple(product(range(3), repeat=2))
    orbits = {canonical(tuple(vertices)) for vertices in combinations(sites, 4)}
    result = []
    for vertices in orbits:
        distances = tuple(
            sorted(
                (x1 - x2) ** 2 + (y1 - y2) ** 2
                for (x1, y1), (x2, y2) in combinations(vertices, 2)
            )
        )
        result.append(
            FourSpinCandidate(
                vertices=vertices,
                diameter_squared=max(distances),
                pair_distance_sum=sum(distances),
                pair_distances_squared=distances,
            )
        )
    return sorted(
        result,
        key=lambda item: (
            item.diameter_squared,
            item.pair_distance_sum,
            item.pair_distances_squared,
            item.vertices,
        ),
    )


def format_vertices(vertices: tuple[Vertex, ...]) -> str:
    return ",".join(f"({x},{y})" for x, y in vertices)


def main() -> None:
    retained_pairs = {
        canonical(shape.vertices) for shape in EVEN_SHAPES[:7]
    }
    retained_fours = {
        canonical(shape.vertices): shape.name for shape in EVEN_SHAPES[7:]
    }

    pairs = pair_candidates()
    cutoff_distance = pairs[12][0]
    tied_at_cutoff = [item for item in pairs if item[0] == cutoff_distance]

    print("TWO-SPIN RECONSTRUCTION")
    print("The first 12 displacement orbits are unique. The 13th has a tie.")
    for index, (distance, displacement) in enumerate(pairs[:12], start=1):
        vertices = canonical(((0, 0), displacement))
        status = "published-retained" if vertices in retained_pairs else "candidate"
        print(
            f"T{index:02d} r2={distance:2d} {format_vertices(vertices):28s} {status}"
        )
    print(f"T13 r2={cutoff_distance:2d} has these equally short candidates:")
    for _, displacement in tied_at_cutoff:
        print(f"    {format_vertices(canonical(((0, 0), displacement)))}")

    fours = four_spin_candidates()[:13]
    print("\nFOUR-SPIN RECONSTRUCTION")
    for index, candidate in enumerate(fours, start=1):
        retained_name = retained_fours.get(candidate.vertices)
        status = retained_name or "candidate"
        print(
            f"F{index:02d} D2={candidate.diameter_squared:2d} "
            f"Q={candidate.pair_distance_sum:2d} "
            f"{format_vertices(candidate.vertices):40s} {status}"
        )

    overlap = set(item.vertices for item in fours) & set(retained_fours)
    if overlap != set(retained_fours):
        raise AssertionError("the reconstructed four-spin set lost a retained operator")
    if len(overlap) != 6:
        raise AssertionError("unexpected reconstructed/published overlap")
    print("\nCHECK: reconstructed four-spin set contains exactly all 6 published survivors.")
    print("This is a consistency check, not proof that the 7 discarded shapes are exact.")


if __name__ == "__main__":
    main()
