from fractions import Fraction
from itertools import product
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    PauliPolynomial,
    PauliWord,
)
from challenge233.sdp.constrained_trace import (  # noqa: E402
    constrained_pauli_trace,
    constrained_polynomial_trace,
    periodic_blockade_dimension,
)


def periodic_blockade_states(size):
    return tuple(
        state
        for state in range(1 << size)
        if all(
            not (
                (state >> site) & 1
                and (state >> ((site + 1) % size)) & 1
            )
            for site in range(size)
        )
    )


def literal_pauli_trace(size, word):
    if any(label in {"X", "Y"} for _, label in word.factors):
        return 0
    z_sites = {site for site, label in word.factors if label == "Z"}
    total = 0
    for state in periodic_blockade_states(size):
        value = 1
        for site in z_sites:
            value *= 1 if (state >> site) & 1 else -1
        total += value
    return total


def all_pauli_words(size):
    for labels in product(("I", "X", "Y", "Z"), repeat=size):
        yield PauliWord(
            tuple(
                (site, label)
                for site, label in enumerate(labels)
                if label != "I"
            )
        )


class ConstrainedTraceTests(unittest.TestCase):
    def test_periodic_dimensions_are_lucas_numbers(self):
        self.assertEqual(
            {
                size: periodic_blockade_dimension(size)
                for size in (4, 5, 20)
            },
            {4: 7, 5: 11, 20: 15127},
        )

    def test_n4_literal_pauli_traces(self):
        self.assertEqual(
            constrained_pauli_trace(4, PauliWord()),
            7,
        )
        self.assertEqual(
            constrained_pauli_trace(
                4,
                PauliWord(((0, "Z"),)),
            ),
            -3,
        )
        self.assertEqual(
            constrained_pauli_trace(
                4,
                PauliWord(((0, "X"),)),
            ),
            0,
        )

    def test_every_n4_and_n5_pauli_word_matches_literal_trace(self):
        for size in (4, 5):
            for word in all_pauli_words(size):
                with self.subTest(size=size, word=word):
                    self.assertEqual(
                        constrained_pauli_trace(size, word),
                        literal_pauli_trace(size, word),
                    )

    def test_every_n6_z_word_matches_literal_trace(self):
        for occupied in product((False, True), repeat=6):
            word = PauliWord(
                tuple(
                    (site, "Z")
                    for site, present in enumerate(occupied)
                    if present
                )
            )
            with self.subTest(word=word):
                self.assertEqual(
                    constrained_pauli_trace(6, word),
                    literal_pauli_trace(6, word),
                )

    def test_polynomial_trace_preserves_exact_gaussian_coefficients(self):
        polynomial = PauliPolynomial(
            (
                (
                    PauliWord(),
                    GaussianRational(Fraction(2, 3), Fraction(1, 5)),
                ),
                (
                    PauliWord(((0, "Z"),)),
                    GaussianRational(Fraction(-1, 7), Fraction(2, 9)),
                ),
                (
                    PauliWord(((0, "X"),)),
                    GaussianRational(Fraction(11), Fraction(13)),
                ),
            )
        )
        self.assertEqual(
            constrained_polynomial_trace(4, polynomial),
            GaussianRational(
                Fraction(107, 21),
                Fraction(11, 15),
            ),
        )

    def test_rejects_out_of_range_words(self):
        with self.assertRaisesRegex(ValueError, "range"):
            constrained_pauli_trace(
                4,
                PauliWord(((4, "Z"),)),
            )

    def test_package_exports_constrained_trace_boundary(self):
        from challenge233.sdp import (
            constrained_pauli_trace as exported_trace,
            periodic_blockade_dimension as exported_dimension,
        )

        self.assertIs(exported_trace, constrained_pauli_trace)
        self.assertIs(exported_dimension, periodic_blockade_dimension)


if __name__ == "__main__":
    unittest.main()
