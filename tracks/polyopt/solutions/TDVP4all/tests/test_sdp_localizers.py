from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    PauliWord,
    adjoint_polynomial,
    multiply_polynomials,
    polynomial_from_word,
)
from challenge233.sdp.constraints import (  # noqa: E402
    blockade_polynomial,
)
from challenge233.sdp.localizers import (  # noqa: E402
    SafeWord,
    SandwichLocalizer,
    SupportLocalizer,
    build_safe_sandwich_localizers,
    build_support_localizers,
    expand_safe_word,
)


ZERO = GaussianRational(Fraction(0), Fraction(0))
ONE = GaussianRational(Fraction(1), Fraction(0))
POS_I = GaussianRational(Fraction(0), Fraction(1))
NEG_I = GaussianRational(Fraction(0), Fraction(-1))


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


def apply_pauli_word(word, state):
    target = state
    amplitude = ONE
    for site, label in word.factors:
        bit = (target >> site) & 1
        if label == "X":
            target ^= 1 << site
        elif label == "Y":
            amplitude = amplitude * (POS_I if bit else NEG_I)
            target ^= 1 << site
        elif label == "Z":
            amplitude = amplitude * (
                ONE if bit else GaussianRational(Fraction(-1))
            )
        else:
            raise AssertionError(f"unexpected Pauli label: {label}")
    return target, amplitude


def diagonal_polynomial_element(polynomial, state):
    value = ZERO
    for word, coefficient in polynomial.terms:
        target, amplitude = apply_pauli_word(word, state)
        if target == state:
            value = value + coefficient * amplitude
    return value


class SoundBlockadeLocalizerTests(unittest.TestCase):
    def test_arbitrary_bare_pauli_sandwich_is_not_zero(self):
        state = 0b0000
        blockade = blockade_polynomial(0, 4)
        flip_pair = polynomial_from_word(
            PauliWord(((0, "X"), (1, "X")))
        )
        sandwich = multiply_polynomials(
            multiply_polynomials(
                adjoint_polynomial(flip_pair),
                blockade,
            ),
            flip_pair,
        )
        self.assertEqual(
            diagonal_polynomial_element(sandwich, state),
            ONE,
        )

    def test_support_and_safe_sandwich_localizers_are_typed(self):
        support = build_support_localizers(
            size=4,
            test_basis=(
                PauliWord(),
                PauliWord(((2, "X"),)),
            ),
            sites=range(4),
        )
        safe = (
            SafeWord(),
            SafeWord(((0, "F"),)),
            SafeWord(((0, "Z"),)),
        )
        sandwich = build_safe_sandwich_localizers(
            size=4,
            safe_basis=safe,
            sites=range(4),
        )
        self.assertTrue(
            all(isinstance(row, SupportLocalizer) for row in support)
        )
        self.assertTrue(
            all(
                isinstance(row, SandwichLocalizer)
                for row in sandwich
            )
        )
        self.assertEqual({row.side for row in support}, {"left", "right"})
        self.assertEqual({row.site for row in support}, {0, 1, 2, 3})
        self.assertEqual({row.site for row in sandwich}, {0, 1, 2, 3})
        self.assertEqual(
            len(sandwich),
            4 * len(safe) * (len(safe) + 1) // 2,
        )
        self.assertTrue(
            all(row.row <= row.column for row in sandwich)
        )

    def test_safe_word_rejects_arbitrary_pauli_labels(self):
        with self.assertRaisesRegex(
            ValueError,
            "only F, Z, P, and n",
        ):
            SafeWord(((0, "X"),))
        with self.assertRaisesRegex(TypeError, "SafeWord"):
            build_safe_sandwich_localizers(
                size=4,
                safe_basis=(PauliWord(),),
                sites=range(4),
            )

    def test_safe_word_expands_f_to_blockade_preserving_flip(self):
        self.assertEqual(
            expand_safe_word(SafeWord(((0, "F"),)), 4),
            multiply_polynomials(
                multiply_polynomials(
                    expand_safe_word(SafeWord(((3, "P"),)), 4),
                    polynomial_from_word(PauliWord(((0, "X"),))),
                ),
                expand_safe_word(SafeWord(((1, "P"),)), 4),
            ),
        )

    def test_valid_rows_vanish_on_every_legal_n4_basis_state(self):
        support = build_support_localizers(
            size=4,
            test_basis=(
                PauliWord(),
                PauliWord(((0, "X"),)),
                PauliWord(((1, "Y"),)),
                PauliWord(((2, "Z"),)),
            ),
            sites=range(4),
        )
        safe_basis = (
            SafeWord(),
            SafeWord(((0, "F"),)),
            SafeWord(((0, "Z"),)),
            SafeWord(((1, "P"),)),
            SafeWord(((2, "n"),)),
            SafeWord(((0, "F"), (2, "Z"))),
        )
        sandwiches = build_safe_sandwich_localizers(
            size=4,
            safe_basis=safe_basis,
            sites=range(4),
        )
        for state in periodic_blockade_states(4):
            for row in (*support, *sandwiches):
                with self.subTest(
                    state=state,
                    site=row.site,
                    row=row,
                ):
                    self.assertEqual(
                        diagonal_polynomial_element(
                            row.polynomial,
                            state,
                        ),
                        ZERO,
                    )


if __name__ == "__main__":
    unittest.main()
