from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.variational_upper import (  # noqa: E402
    exact_rayleigh_quotient,
    generate_quspin_trial,
    round_trial_vector,
    write_trial_vector,
)


def periodic_legal_states(size):
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


def literal_dense_quotient(size, detuning, states, coefficients):
    legal = periodic_legal_states(size)
    index = {state: position for position, state in enumerate(legal)}
    matrix = [
        [Fraction(0) for _ in legal]
        for _ in legal
    ]
    for column, state in enumerate(legal):
        matrix[column][column] -= (
            detuning * bin(state).count("1")
        )
        for site in range(size):
            target = state ^ (1 << site)
            if target in index:
                matrix[index[target]][column] += 1
    vector = [0 for _ in legal]
    for state, coefficient in zip(states, coefficients):
        vector[index[state]] = coefficient
    numerator = sum(
        vector[row] * matrix[row][column] * vector[column]
        for row in range(len(legal))
        for column in range(len(legal))
    )
    denominator = sum(coefficient * coefficient for coefficient in vector)
    return numerator / denominator


class ExactRayleighTests(unittest.TestCase):
    def test_exact_rayleigh_uses_directed_sparse_pxp_action(self):
        self.assertEqual(
            exact_rayleigh_quotient(
                4,
                Fraction(1, 2),
                (0b0000, 0b0001),
                (1, -1),
            ),
            Fraction(-5, 4),
        )

    def test_rejects_invalid_integer_vector(self):
        cases = (
            ((0b0000, 0b1001), (1, 1), "illegal periodic"),
            ((0b0000, 0b0000), (1, 1), "duplicate"),
            ((0b0000,), (0,), "zero vector"),
            ((0b0000, 0b0001), (1,), "same length"),
        )
        for states, coefficients, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    exact_rayleigh_quotient(
                        4,
                        Fraction(1, 2),
                        states,
                        coefficients,
                    )

    def test_detuning_must_be_exact(self):
        with self.assertRaisesRegex(TypeError, "Fraction"):
            exact_rayleigh_quotient(4, 0.5, (0,), (1,))

    def test_matches_literal_dense_matrix_for_integer_vectors(self):
        legal = periodic_legal_states(4)
        random_generator = random.Random(233)
        vectors = []
        while len(vectors) < 20:
            coefficients = tuple(
                random_generator.randint(-3, 3)
                for _ in legal
            )
            if any(coefficients):
                vectors.append(coefficients)

        for detuning in (Fraction(0), Fraction(1, 2), Fraction(1)):
            for coefficients in vectors:
                expected = literal_dense_quotient(
                    4,
                    detuning,
                    legal,
                    coefficients,
                )
                with self.subTest(
                    detuning=detuning,
                    coefficients=coefficients,
                ):
                    self.assertEqual(
                        exact_rayleigh_quotient(
                            4,
                            detuning,
                            legal,
                            coefficients,
                        ),
                        expected,
                    )

    def test_round_trial_vector_uses_signed_dyadic_integers(self):
        self.assertEqual(
            round_trial_vector((0.5, -0.25, 0.0), bits=3),
            (4, -2, 0),
        )
        with self.assertRaisesRegex(ValueError, "bits"):
            round_trial_vector((1.0,), bits=63)


def _quspin_available():
    try:
        import numpy  # noqa: F401
        import quspin  # noqa: F401
        import scipy  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(
    _quspin_available(),
    "optional QuSpin runtime is unavailable",
)
class QuSpinTrialTests(unittest.TestCase):
    def test_generation_exports_an_exact_independently_addressable_trial(self):
        trial = generate_quspin_trial(
            4,
            Fraction(1, 2),
            bits=40,
            tolerance=1e-12,
            seed=233,
        )
        self.assertEqual(trial.basis_dimension, 7)
        self.assertEqual(trial.detuning, Fraction(1, 2))
        self.assertLess(trial.residual_norm, 1e-10)
        self.assertEqual(
            trial.b_var,
            exact_rayleigh_quotient(
                trial.size,
                trial.detuning,
                trial.states,
                trial.coefficients,
            ),
        )

        with TemporaryDirectory() as directory:
            summary = write_trial_vector(trial, directory)
            output = Path(directory)
            metadata = json.loads(
                (output / "trial-vector.json").read_text(
                    encoding="utf-8"
                )
            )
            state_bytes = (
                output / "trial-states.u64le"
            ).read_bytes()
            coefficient_bytes = (
                output / "trial-coefficients.i64le"
            ).read_bytes()

        self.assertEqual(
            len(state_bytes),
            8 * metadata["nonzero_count"],
        )
        self.assertEqual(
            len(coefficient_bytes),
            8 * metadata["nonzero_count"],
        )
        self.assertEqual(
            hashlib.sha256(state_bytes).hexdigest(),
            metadata["state_file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(coefficient_bytes).hexdigest(),
            metadata["coefficient_file_sha256"],
        )
        decoded_states = struct.unpack(
            f"<{metadata['nonzero_count']}Q",
            state_bytes,
        )
        decoded_coefficients = struct.unpack(
            f"<{metadata['nonzero_count']}q",
            coefficient_bytes,
        )
        self.assertEqual(decoded_states, trial.states)
        self.assertEqual(decoded_coefficients, trial.coefficients)
        self.assertEqual(summary["b_var"], metadata["b_var"])
        self.assertEqual(
            metadata["trusted_basis_sha256"],
            "1dddefa1b616fad7eb57702deb30a192479507dbb617929c744b1d43d7b652fe",
        )
        self.assertEqual(
            metadata["thread_environment"],
            {
                name: os.environ.get(name)
                for name in (
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                )
            },
        )


if __name__ == "__main__":
    unittest.main()
