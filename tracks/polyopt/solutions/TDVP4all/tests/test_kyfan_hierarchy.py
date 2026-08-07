from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.hierarchy import (  # noqa: E402
    LOCAL_LEVELS,
    HierarchyLevel,
    clique_orbit,
    global_pauli_basis,
    local_pauli_basis,
    safe_localizer_basis,
    validate_nested_levels,
)
from challenge233.sdp.localizers import expand_safe_word  # noqa: E402


class KyFanHierarchyTests(unittest.TestCase):
    def test_n4_global_pauli_counts(self):
        self.assertEqual(
            [
                len(global_pauli_basis(4, degree))
                for degree in (2, 3, 4)
            ],
            [67, 175, 256],
        )

    def test_scalable_level_counts_for_n20(self):
        self.assertEqual(
            {
                level.name: len(local_pauli_basis(20, 0, level))
                for level in LOCAL_LEVELS
            },
            {"L0": 37, "L1": 67, "L2": 175, "L3": 376},
        )

    def test_levels_are_nested_as_actual_word_sets(self):
        bases = [
            set(local_pauli_basis(20, 0, level))
            for level in LOCAL_LEVELS
        ]
        for lower, upper in zip(bases, bases[1:]):
            self.assertTrue(lower <= upper)
        validate_nested_levels(LOCAL_LEVELS)

    def test_safe_localizer_polynomials_are_nested_and_window_local(self):
        polynomial_sets = []
        for level in LOCAL_LEVELS:
            window = set(range(level.range_sites))
            basis = safe_localizer_basis(20, 0, level)
            expanded = {
                expand_safe_word(word, 20)
                for word in basis
            }
            self.assertEqual(len(expanded), len(basis))
            for polynomial in expanded:
                support = {
                    site
                    for word, _ in polynomial.terms
                    for site, _ in word.factors
                }
                self.assertTrue(support <= window)
            polynomial_sets.append(expanded)

        for lower, upper in zip(
            polynomial_sets,
            polynomial_sets[1:],
        ):
            self.assertTrue(lower <= upper)

    def test_clique_orbits_cover_odd_even_and_wrapped_windows(self):
        cases = (
            (5, 0, 3, 5),
            (6, 1, 4, 6),
            (4, 2, 5, 1),
        )
        for size, start, range_sites, expected_count in cases:
            with self.subTest(
                size=size,
                start=start,
                range_sites=range_sites,
            ):
                orbit = clique_orbit(
                    size,
                    start,
                    range_sites,
                )
                self.assertEqual(len(orbit), expected_count)
                self.assertEqual(len(orbit), len(set(orbit)))
                self.assertTrue(
                    all(tuple(sorted(image)) == image for image in orbit)
                )
                self.assertEqual(
                    {
                        site
                        for image in orbit
                        for site in image
                    },
                    set(range(size)),
                )
                self.assertTrue(
                    all(len(image) == min(size, range_sites) for image in orbit)
                )

    def test_level_validation_rejects_non_nested_sequence(self):
        levels = (
            HierarchyLevel("wide", 4, 2, 1),
            HierarchyLevel("narrow", 3, 2, 1),
        )
        with self.assertRaisesRegex(ValueError, "nested"):
            validate_nested_levels(levels)

    def test_package_exports_hierarchy_boundary(self):
        from challenge233.sdp import (
            LOCAL_LEVELS as exported_levels,
            global_pauli_basis as exported_global,
        )

        self.assertIs(exported_levels, LOCAL_LEVELS)
        self.assertIs(exported_global, global_pauli_basis)


if __name__ == "__main__":
    unittest.main()
