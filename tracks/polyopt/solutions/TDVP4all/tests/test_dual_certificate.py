from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.dual_certificate import (  # noqa: E402
    DyadicFactor,
    exact_dual_identity,
    positive_dyadic_factor,
)


def form(constant=0, terms=()):
    return {
        "constant": f"{constant}/1",
        "terms": [
            [variable, f"{coefficient}/1"]
            for variable, coefficient in terms
        ],
    }


def toy_problem(equalities=(), witness_bound="2/1"):
    return {
        "variables": [{"index": 0}],
        "objective": form(terms=((0, 2),)),
        "equalities": list(equalities),
        "psd_blocks": [
            {
                "identifier": "toy",
                "dimension": 2,
                "entries": [
                    [form(1), form(terms=((0, 1),))],
                    [form(terms=((0, 1),)), form(1)],
                ],
            }
        ],
        "magnitude_witnesses": [
            {"variable": 0, "bound": witness_bound}
        ],
    }


class ExactDualIdentityTests(unittest.TestCase):
    def test_exact_rank_one_gram_recovers_the_toy_lower_bound(self):
        factor = DyadicFactor(
            rows=2,
            columns=1,
            requested_bits=0,
            used_bits=0,
            numerators=((1,), (1,)),
            storage="int64",
            overflow_bound=1,
        )

        identity = exact_dual_identity(
            toy_problem(),
            {"toy": factor},
            {},
        )

        self.assertEqual(identity.a, Fraction(-2))
        self.assertEqual(identity.residuals, (Fraction(0),))
        self.assertEqual(identity.rho, Fraction(0))
        self.assertEqual(identity.a_cert, Fraction(-2))

    def test_residual_correction_uses_checked_variable_bounds(self):
        equality = {
            "identifier": "fix-x",
            "form": form(terms=((0, 1),)),
        }
        factor = DyadicFactor(
            rows=2,
            columns=1,
            requested_bits=0,
            used_bits=0,
            numerators=((1,), (1,)),
            storage="int64",
            overflow_bound=1,
        )

        identity = exact_dual_identity(
            toy_problem(equalities=(equality,)),
            {"toy": factor},
            {"fix-x": Fraction(1, 2)},
        )

        self.assertEqual(identity.a, Fraction(-2))
        self.assertEqual(identity.residuals, (Fraction(-1, 2),))
        self.assertEqual(identity.rho, Fraction(1))
        self.assertEqual(identity.a_cert, Fraction(-3))

    def test_unsupported_witness_bound_is_rejected(self):
        factor = DyadicFactor(
            rows=2,
            columns=1,
            requested_bits=0,
            used_bits=0,
            numerators=((1,), (1,)),
            storage="int64",
            overflow_bound=1,
        )
        with self.assertRaisesRegex(ValueError, "magnitude witness"):
            exact_dual_identity(
                toy_problem(witness_bound="3/1"),
                {"toy": factor},
                {},
            )


try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipUnless(np is not None, "NumPy factorization runtime unavailable")
class NumericalFactorizationTests(unittest.TestCase):
    def test_positive_part_is_rounded_to_an_exact_dyadic_factor(self):
        factor = positive_dyadic_factor(
            np.array([[1.0, 1.0], [1.0, 1.0]]),
            requested_bits=20,
        )

        numerator = np.array(factor.numerators, dtype=float)
        reconstructed = (
            numerator @ numerator.T
        ) / float(1 << (2 * factor.used_bits))
        np.testing.assert_allclose(
            reconstructed,
            np.ones((2, 2)),
            atol=2e-6,
            rtol=0.0,
        )
        self.assertEqual(factor.storage, "int64")
        self.assertLess(factor.overflow_bound, 1 << 62)

    def test_negative_eigenvalues_are_clamped(self):
        factor = positive_dyadic_factor(
            np.diag([-1.0, 4.0]),
            requested_bits=12,
        )
        numerator = np.array(factor.numerators, dtype=float)
        reconstructed = (
            numerator @ numerator.T
        ) / float(1 << (2 * factor.used_bits))
        np.testing.assert_allclose(
            reconstructed,
            np.diag([0.0, 4.0]),
            atol=1e-12,
            rtol=0.0,
        )


if __name__ == "__main__":
    unittest.main()
