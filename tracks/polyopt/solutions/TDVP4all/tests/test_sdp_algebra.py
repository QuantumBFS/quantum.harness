from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    PauliPolynomial,
    PauliTerm,
    PauliWord,
    add_polynomials,
    adjoint_polynomial,
    canonical_relation_table_json,
    canonicalize_word,
    expand_word,
    multiply_polynomials,
    polynomial_from_word,
    scale_polynomial,
)


ONE = GaussianRational(Fraction(1), Fraction(0))
NEG_I = GaussianRational(Fraction(0), Fraction(-1))
POS_I = GaussianRational(Fraction(0), Fraction(1))
HALF = GaussianRational(Fraction(1, 2), Fraction(0))
NEG_HALF = GaussianRational(Fraction(-1, 2), Fraction(0))
HALF_I = GaussianRational(Fraction(0), Fraction(1, 2))
NEG_HALF_I = GaussianRational(Fraction(0), Fraction(-1, 2))


def _matrix_multiply(left, right):
    return tuple(
        tuple(
            sum(left[row][inner] * right[inner][column] for inner in range(2))
            for column in range(2)
        )
        for row in range(2)
    )


def _matrix_scale(coefficient, matrix):
    return tuple(
        tuple(coefficient * value for value in row)
        for row in matrix
    )


def _matrix_adjoint(matrix):
    return tuple(
        tuple(matrix[column][row].conjugate() for column in range(2))
        for row in range(2)
    )


def _square_matrix_multiply(left, right):
    dimension = len(left)
    return tuple(
        tuple(
            sum(
                left[row][inner] * right[inner][column]
                for inner in range(dimension)
            )
            for column in range(dimension)
        )
        for row in range(dimension)
    )


def _kronecker(left, right):
    return tuple(
        tuple(
            left[left_row][left_column]
            * right[right_row][right_column]
            for left_column in range(len(left[0]))
            for right_column in range(len(right[0]))
        )
        for left_row in range(len(left))
        for right_row in range(len(right))
    )


def _term_matrix(term, matrices):
    matrix = matrices["I"]
    for _, label in term.word.factors:
        matrix = _matrix_multiply(matrix, matrices[label])
    coefficient = complex(
        float(term.coefficient.real),
        float(term.coefficient.imag),
    )
    return _matrix_scale(coefficient, matrix)


class PauliCanonicalizationTests(unittest.TestCase):
    def test_package_exports_the_exact_algebra_boundary(self):
        from challenge233.sdp import (
            PauliTerm as ExportedPauliTerm,
            PauliWord as ExportedPauliWord,
            canonicalize_word as exported_canonicalize_word,
        )

        self.assertEqual(
            exported_canonicalize_word(
                ((0, "X"), (0, "Z"))
            ),
            ExportedPauliTerm(
                NEG_I,
                ExportedPauliWord(((0, "Y"),)),
            ),
        )

    def test_same_site_xz_and_zx_have_opposite_imaginary_phases(self):
        y0 = PauliWord(((0, "Y"),))
        self.assertEqual(
            canonicalize_word(((0, "X"), (0, "Z"))),
            PauliTerm(NEG_I, y0),
        )
        self.assertEqual(
            canonicalize_word(((0, "Z"), (0, "X"))),
            PauliTerm(POS_I, y0),
        )

    def test_different_sites_commute_without_a_phase(self):
        expected = PauliTerm(
            ONE,
            PauliWord(((0, "X"), (1, "Z"))),
        )
        self.assertEqual(
            canonicalize_word(((1, "Z"), (0, "X"))),
            expected,
        )
        self.assertEqual(
            canonicalize_word(((0, "X"), (1, "Z"))),
            expected,
        )
        for left in ("X", "Y", "Z", "P", "n"):
            for right in ("X", "Y", "Z", "P", "n"):
                with self.subTest(left=left, right=right):
                    self.assertEqual(
                        expand_word(((1, left), (0, right))),
                        expand_word(((0, right), (1, left))),
                    )

    def test_complete_nontrivial_pauli_product_table(self):
        expected = {
            ("X", "Y"): (POS_I, "Z"),
            ("Y", "Z"): (POS_I, "X"),
            ("Z", "X"): (POS_I, "Y"),
            ("Y", "X"): (NEG_I, "Z"),
            ("Z", "Y"): (NEG_I, "X"),
            ("X", "Z"): (NEG_I, "Y"),
        }
        for (left, right), (phase, result) in expected.items():
            with self.subTest(left=left, right=right):
                self.assertEqual(
                    canonicalize_word(((0, left), (0, right))),
                    PauliTerm(
                        phase,
                        PauliWord(((0, result),)),
                    ),
                )

    def test_projector_z_and_flip_relations_are_derived(self):
        projector = PauliPolynomial(
            (
                (PauliWord(), HALF),
                (PauliWord(((0, "Z"),)), NEG_HALF),
            )
        )
        occupation = PauliPolynomial(
            (
                (PauliWord(), HALF),
                (PauliWord(((0, "Z"),)), HALF),
            )
        )
        self.assertEqual(expand_word(((0, "P"),)), projector)
        self.assertEqual(expand_word(((0, "n"),)), occupation)
        self.assertEqual(
            expand_word(((0, "P"), (0, "Z"))),
            -projector,
        )
        self.assertEqual(
            expand_word(((0, "n"), (0, "Z"))),
            occupation,
        )
        expected_px = PauliPolynomial(
            (
                (PauliWord(((0, "X"),)), HALF),
                (PauliWord(((0, "Y"),)), NEG_HALF_I),
            )
        )
        expected_xp = PauliPolynomial(
            (
                (PauliWord(((0, "X"),)), HALF),
                (PauliWord(((0, "Y"),)), HALF_I),
            )
        )
        self.assertEqual(
            expand_word(((0, "P"), (0, "X"))),
            expected_px,
        )
        self.assertEqual(
            expand_word(((0, "P"), (0, "X"))),
            expand_word(((0, "X"), (0, "n"))),
        )
        self.assertEqual(
            expand_word(((0, "X"), (0, "P"))),
            expected_xp,
        )
        self.assertEqual(
            expand_word(((0, "X"), (0, "P"))),
            expand_word(((0, "n"), (0, "X"))),
        )

    def test_adjoint_reverses_same_site_product(self):
        xz = PauliPolynomial(
            ((PauliWord(((0, "Y"),)), NEG_I),)
        )
        zx = PauliPolynomial(
            ((PauliWord(((0, "Y"),)), POS_I),)
        )
        self.assertEqual(
            expand_word(((0, "X"), (0, "Z"))),
            xz,
        )
        self.assertEqual(
            adjoint_polynomial(xz),
            zx,
        )

    def test_projector_completeness_idempotence_and_orthogonality(self):
        projector = expand_word(((0, "P"),))
        occupation = expand_word(((0, "n"),))
        self.assertEqual(
            projector,
            PauliPolynomial(
                (
                    (PauliWord(), HALF),
                    (PauliWord(((0, "Z"),)), NEG_HALF),
                )
            ),
        )
        self.assertEqual(
            occupation,
            PauliPolynomial(
                (
                    (PauliWord(), HALF),
                    (PauliWord(((0, "Z"),)), HALF),
                )
            ),
        )
        identity = polynomial_from_word(PauliWord())
        self.assertEqual(
            add_polynomials(projector, occupation),
            identity,
        )
        self.assertEqual(
            multiply_polynomials(projector, projector),
            projector,
        )
        self.assertEqual(
            multiply_polynomials(occupation, occupation),
            occupation,
        )
        self.assertEqual(
            multiply_polynomials(projector, occupation).terms,
            (),
        )
        self.assertEqual(adjoint_polynomial(projector), projector)
        self.assertEqual(adjoint_polynomial(occupation), occupation)

    def test_exact_scaling_preserves_rational_coefficients(self):
        half = GaussianRational(Fraction(1, 2), Fraction(0))
        scaled = scale_polynomial(
            half,
            polynomial_from_word(PauliWord(((2, "X"),))),
        )
        self.assertEqual(
            scaled.terms,
            ((PauliWord(((2, "X"),)), half),),
        )

    def test_noncanonical_pauli_word_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique and sorted"):
            PauliWord(((1, "X"), (0, "Z")))
        with self.assertRaisesRegex(ValueError, "labels"):
            PauliWord(((0, "P"),))
        with self.assertRaisesRegex(ValueError, "non-negative"):
            PauliWord(((-1, "X"),))

    def test_relation_table_json_is_deterministic_and_complete(self):
        first = canonical_relation_table_json()
        second = canonical_relation_table_json()
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(
            payload.get("definitions"),
            {
                "P": "(I-Z)/2",
                "Y": "iXZ",
                "n": "(I+Z)/2",
            },
        )
        self.assertEqual(payload.get("different_site"), "commute")
        products = payload.get("local_products", {})
        self.assertEqual(
            products.get("X,Z"),
            {
                "phase": {"real": "0/1", "imag": "-1/1"},
                "result": "Y",
            },
        )
        self.assertEqual(
            products.get("Z,X"),
            {
                "phase": {"real": "0/1", "imag": "1/1"},
                "result": "Y",
            },
        )


class ExplicitMatrixConventionTests(unittest.TestCase):
    def test_down_up_matrices_realize_the_symbolic_xz_relations(self):
        identity = ((1 + 0j, 0j), (0j, 1 + 0j))
        x_matrix = ((0j, 1 + 0j), (1 + 0j, 0j))
        y_matrix = ((0j, 1j), (-1j, 0j))
        z_matrix = ((-1 + 0j, 0j), (0j, 1 + 0j))
        matrices = {
            "I": identity,
            "X": x_matrix,
            "Y": y_matrix,
            "Z": z_matrix,
        }

        self.assertEqual(
            _term_matrix(
                canonicalize_word(((0, "X"), (0, "Z"))),
                matrices,
            ),
            _matrix_multiply(x_matrix, z_matrix),
        )
        self.assertEqual(
            _term_matrix(
                canonicalize_word(((0, "Z"), (0, "X"))),
                matrices,
            ),
            _matrix_multiply(z_matrix, x_matrix),
        )
        self.assertEqual(_matrix_adjoint(y_matrix), y_matrix)
        self.assertEqual(
            _term_matrix(
                canonicalize_word(((0, "Y"), (0, "Y"))),
                matrices,
            ),
            identity,
        )

    def test_two_site_word_matches_explicit_kronecker_product(self):
        identity = ((1 + 0j, 0j), (0j, 1 + 0j))
        x_matrix = ((0j, 1 + 0j), (1 + 0j, 0j))
        y_matrix = ((0j, 1j), (-1j, 0j))
        z_matrix = ((-1 + 0j, 0j), (0j, 1 + 0j))
        matrices = {
            "I": identity,
            "X": x_matrix,
            "Y": y_matrix,
            "Z": z_matrix,
        }
        factors = (
            (1, "Z"),
            (0, "X"),
            (0, "Z"),
            (1, "X"),
        )
        raw_matrix = _kronecker(identity, identity)
        for site, label in factors:
            local = (
                _kronecker(matrices[label], identity)
                if site == 0
                else _kronecker(identity, matrices[label])
            )
            raw_matrix = _square_matrix_multiply(
                raw_matrix,
                local,
            )

        canonical = canonicalize_word(factors)
        local_labels = dict(canonical.word.factors)
        canonical_matrix = _kronecker(
            matrices[local_labels.get(0, "I")],
            matrices[local_labels.get(1, "I")],
        )
        coefficient = complex(
            float(canonical.coefficient.real),
            float(canonical.coefficient.imag),
        )
        canonical_matrix = _matrix_scale(
            coefficient,
            canonical_matrix,
        )

        self.assertEqual(canonical.word, PauliWord(((0, "Y"), (1, "Y"))))
        self.assertEqual(canonical.coefficient, ONE)
        self.assertEqual(canonical_matrix, raw_matrix)


if __name__ == "__main__":
    unittest.main()
