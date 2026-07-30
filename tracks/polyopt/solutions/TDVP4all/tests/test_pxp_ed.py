import csv
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import warnings


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import numpy as np
    import quspin  # noqa: F401
except ImportError:
    HAS_QUSPIN = False
else:
    HAS_QUSPIN = True


@unittest.skipUnless(HAS_QUSPIN, "optional QuSpin runtime is unavailable")
class PXPBasisTests(unittest.TestCase):
    def test_periodic_blockade_basis_has_lucas_dimension(self):
        from challenge233.basis.pxp import build_constrained_basis

        expected_dimensions = {
            4: 7,
            5: 11,
            6: 18,
            7: 29,
            8: 47,
            9: 76,
            10: 123,
        }

        for size, expected in expected_dimensions.items():
            with self.subTest(size=size):
                self.assertEqual(build_constrained_basis(size).Ns, expected)


@unittest.skipUnless(HAS_QUSPIN, "optional QuSpin runtime is unavailable")
class PXPHamiltonianTests(unittest.TestCase):
    def test_user_basis_build_does_not_emit_unimplemented_check_warnings(self):
        from challenge233.ed.pxp_gap import build_pxp_hamiltonian

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            build_pxp_hamiltonian(size=4, detuning=0.3)

        self.assertEqual([str(item.message) for item in caught], [])

    def test_quspin_hamiltonian_matches_independent_bitstring_matrix(self):
        from challenge233.ed.pxp_gap import build_pxp_hamiltonian

        size = 4
        detuning = 0.3
        legal_states = [
            state
            for state in range(1 << size)
            if all(
                not (
                    (state >> site) & 1
                    and (state >> ((site + 1) % size)) & 1
                )
                for site in range(size)
            )
        ]
        state_index = {state: index for index, state in enumerate(legal_states)}
        expected = np.zeros((len(legal_states), len(legal_states)))

        for column, state in enumerate(legal_states):
            expected[column, column] = (
                -detuning * bin(state).count("1")
            )
            for site in range(size):
                target = state ^ (1 << site)
                if target in state_index:
                    expected[state_index[target], column] += 1.0

        quspin_operator, energy_shift = build_pxp_hamiltonian(size, detuning)
        actual_eigenvalues = (
            np.linalg.eigvalsh(quspin_operator.toarray()) + energy_shift
        )

        np.testing.assert_allclose(
            actual_eigenvalues,
            np.linalg.eigvalsh(expected),
            atol=1e-12,
            rtol=0.0,
        )

    def test_exact_polynomial_spectrum_matches_quspin(self):
        from challenge233.ed.pxp_gap import build_pxp_hamiltonian
        from challenge233.sdp.constraints import (
            pxp_hamiltonian_polynomial,
        )

        size = 4
        detuning = Fraction(3, 10)
        legal_states = [
            state
            for state in range(1 << size)
            if all(
                not (
                    (state >> site) & 1
                    and (state >> ((site + 1) % size)) & 1
                )
                for site in range(size)
            )
        ]
        state_index = {
            state: index
            for index, state in enumerate(legal_states)
        }
        exact = np.zeros(
            (len(legal_states), len(legal_states)),
            dtype=np.complex128,
        )
        polynomial = pxp_hamiltonian_polynomial(
            size,
            detuning,
        )
        for column, state in enumerate(legal_states):
            for word, coefficient in polynomial.terms:
                target = state
                amplitude = 1 + 0j
                for site, label in word.factors:
                    bit = (target >> site) & 1
                    if label == "X":
                        target ^= 1 << site
                    elif label == "Y":
                        amplitude *= 1j if bit else -1j
                        target ^= 1 << site
                    elif label == "Z":
                        amplitude *= 1 if bit else -1
                    else:
                        raise AssertionError(label)
                if target in state_index:
                    exact[state_index[target], column] += (
                        complex(
                            float(coefficient.real),
                            float(coefficient.imag),
                        )
                        * amplitude
                    )

        quspin_operator, energy_shift = build_pxp_hamiltonian(
            size=size,
            detuning=float(detuning),
        )
        quspin_eigenvalues = (
            np.linalg.eigvalsh(quspin_operator.toarray())
            + energy_shift
        )
        np.testing.assert_allclose(
            np.linalg.eigvalsh(exact),
            quspin_eigenvalues,
            atol=1e-12,
            rtol=0.0,
        )

    def test_sparse_low_spectrum_matches_tiny_dense_reference(self):
        from challenge233.ed.pxp_gap import (
            build_pxp_hamiltonian,
            solve_low_spectrum,
        )

        size = 6
        detuning = 0.4
        operator, energy_shift = build_pxp_hamiltonian(size, detuning)
        dense_eigenvalues = (
            np.linalg.eigvalsh(operator.toarray()) + energy_shift
        )

        result = solve_low_spectrum(
            size=size,
            detuning=detuning,
            eigenpairs=4,
            tolerance=1e-12,
            random_seed=233,
        )

        np.testing.assert_allclose(
            result.eigenvalues,
            dense_eigenvalues[:4],
            atol=1e-10,
            rtol=0.0,
        )
        self.assertAlmostEqual(
            result.gap,
            dense_eigenvalues[1] - dense_eigenvalues[0],
            delta=1e-10,
        )
        self.assertEqual(result.basis_dimension, 18)
        self.assertLess(max(result.residual_norms), 1e-10)
        self.assertEqual(result.hermiticity_max_abs, 0.0)
        self.assertTrue(hasattr(result, "matrix_nnz"))
        self.assertGreater(result.matrix_nnz, 0)
        self.assertLess(result.matrix_nnz, result.basis_dimension**2)
        self.assertGreater(result.wall_seconds, 0.0)

    def test_sweep_exports_all_points_and_physical_provenance(self):
        from challenge233.ed.pxp_gap import run_sweep

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            run_sweep(
                sizes=[4, 5],
                detunings=[0.0, 0.1],
                output_directory=output_directory,
                eigenpairs=4,
                tolerance=1e-12,
                random_seed=233,
            )

            with (output_directory / "ed-gap.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            manifest = json.loads(
                (output_directory / "manifest.json").read_text()
            )
            data_hash = hashlib.sha256(
                (output_directory / "ed-gap.csv").read_bytes()
            ).hexdigest()

        self.assertEqual(
            [(int(row["size"]), float(row["detuning"])) for row in rows],
            [(4, 0.0), (4, 0.1), (5, 0.0), (5, 0.1)],
        )
        self.assertTrue(all(float(row["gap"]) > 0.0 for row in rows))
        self.assertEqual(manifest["boundary"], "periodic")
        self.assertEqual(manifest["local_state_convention"], "0=down, 1=up")
        self.assertEqual(manifest["blockade_constraint"], "n_i n_{i+1}=0")
        self.assertEqual(manifest["target_gap"], "E_1-E_0, all momenta")
        self.assertEqual(manifest["sizes"], [4, 5])
        self.assertEqual(manifest["detunings"], [0.0, 0.1])
        self.assertEqual(
            set(manifest["runtime"]["thread_environment"]),
            {"OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"},
        )
        self.assertEqual(
            manifest["trusted_basis_sha256"],
            "1dddefa1b616fad7eb57702deb30a192479507dbb617929c744b1d43d7b652fe",
        )
        for relative_path in (
            "src/challenge233/basis/pxp.py",
            "src/challenge233/ed/pxp_gap.py",
        ):
            self.assertEqual(
                manifest["source_file_sha256"][relative_path],
                hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest(),
            )
        self.assertEqual(
            manifest["data_sha256"],
            data_hash,
        )

    def test_sweep_exports_exact_basis_state_ordering(self):
        from challenge233.basis.pxp import build_constrained_basis
        from challenge233.ed.pxp_gap import run_sweep

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            run_sweep(
                sizes=[4],
                detunings=[0.0],
                output_directory=output_directory,
            )
            states_path = output_directory / "basis-states-N0004.npy"
            self.assertTrue(states_path.is_file())
            exported_states = np.load(states_path)
            manifest = json.loads(
                (output_directory / "manifest.json").read_text()
            )
            exported_hash = hashlib.sha256(states_path.read_bytes()).hexdigest()

        np.testing.assert_array_equal(
            exported_states,
            build_constrained_basis(4).states,
        )
        self.assertEqual(
            manifest["basis_state_files"]["4"],
            {
                "path": "basis-states-N0004.npy",
                "count": 7,
                "sha256": exported_hash,
            },
        )

    def test_module_cli_runs_an_inclusive_grid(self):
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "challenge233.ed.pxp_gap",
                    "--output-dir",
                    str(output_directory),
                    "--min-size",
                    "4",
                    "--max-size",
                    "5",
                    "--detuning-min",
                    "0",
                    "--detuning-max",
                    "0.1",
                    "--detuning-step",
                    "0.1",
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_directory / "ed-gap.csv").is_file())
            with (output_directory / "ed-gap.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 4)
        self.assertIn("completed 4 ED points", completed.stdout)


if __name__ == "__main__":
    unittest.main()
