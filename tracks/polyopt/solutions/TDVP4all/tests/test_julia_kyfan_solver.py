import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "src/challenge233/sdp/solve_kyfan.jl"


def _fraction(value):
    return f"{value}/1"


def _form(constant=0, terms=()):
    return {
        "constant": _fraction(constant),
        "terms": [
            [index, _fraction(coefficient)]
            for index, coefficient in terms
        ],
    }


def _write_toy_problem(directory):
    directory = Path(directory)
    directory.mkdir(parents=True)
    problem = {
        "schema_version": 1,
        "purpose": "finite-N-ky-fan-effect-moment-problem",
        "variables": [{"index": 0}],
        "objective": _form(terms=((0, 2),)),
        "equalities": [
            {
                "identifier": "trace-gamma-equals-2",
                "form": _form(),
            }
        ],
        "psd_blocks": [
            {
                "identifier": "toy",
                "dimension": 2,
                "entries": [
                    [_form(1), _form(terms=((0, 1),))],
                    [_form(terms=((0, 1),)), _form(1)],
                ],
            }
        ],
    }
    problem_bytes = (
        json.dumps(problem, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (directory / "problem.json").write_bytes(problem_bytes)
    manifest = {
        "schema_version": 1,
        "purpose": "finite-N-ky-fan-effect-moment-problem",
        "problem_file": "problem.json",
        "problem_sha256": hashlib.sha256(problem_bytes).hexdigest(),
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical_bytes(value):
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_toy_v2_problem(
    run,
    objective_coefficient=1,
    detuning="0/1",
):
    run = Path(run)
    shared = run / "shared"
    structure_directory = shared / "structure"
    reduction_directory = shared / "reduction"
    problem = run / "cells/toy/problem"
    for directory in (structure_directory, reduction_directory, problem):
        directory.mkdir(parents=True)

    structure = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-effect-moment-structure",
        "fixture": "tiny-reduced-solver-input",
    }
    structure_bytes = _canonical_bytes(structure)
    structure_sha256 = hashlib.sha256(structure_bytes).hexdigest()
    (structure_directory / "structure.json").write_bytes(structure_bytes)
    structure_manifest = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-shared-structure",
        "structure_file": "structure.json",
        "structure_sha256": structure_sha256,
        "structure_bytes": len(structure_bytes),
    }
    structure_manifest_bytes = _canonical_bytes(structure_manifest)
    (structure_directory / "manifest.json").write_bytes(
        structure_manifest_bytes
    )

    reduction = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-solver-reduction",
        "structure_sha256": structure_sha256,
        "selected_view": "parameterized",
        "statistics": {"solver_variable_count": 1},
        "equality": {"kept_rows": []},
        "objective_components": {
            "rabi": _form(terms=((0, 1),)),
            "minus-number": _form(),
        },
        "spatial": [
            {
                "identifier": "toy-spatial",
                "irrep_label": "trivial",
                "irrep_degree": 1,
                "transform": {
                    "rows": 1,
                    "columns": 1,
                    "entries": [[0, 0, "1/1"]],
                },
            }
        ],
        "psd_blocks": [
            {
                "identifier": "toy",
                "dimension": 1,
                "source_block": "gamma",
                "spatial_block": "toy-spatial",
                "upper_entries": [
                    {
                        "row": 0,
                        "column": 0,
                        "form": _form(-1, ((0, 1),)),
                    }
                ],
            }
        ],
    }
    reduction_bytes = _canonical_bytes(reduction)
    reduction_sha256 = hashlib.sha256(reduction_bytes).hexdigest()
    (reduction_directory / "solver-reduction.json").write_bytes(
        reduction_bytes
    )
    reduction_manifest = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-shared-solver-reduction",
        "reduction_file": "solver-reduction.json",
        "reduction_sha256": reduction_sha256,
        "reduction_bytes": len(reduction_bytes),
        "structure_sha256": structure_sha256,
    }
    reduction_manifest_bytes = _canonical_bytes(reduction_manifest)
    (reduction_directory / "manifest.json").write_bytes(
        reduction_manifest_bytes
    )

    instance = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-effect-moment-instance",
        "structure_sha256": structure_sha256,
        "detuning": detuning,
        "objective": _form(terms=((0, objective_coefficient),)),
    }
    instance_bytes = _canonical_bytes(instance)
    instance_sha256 = hashlib.sha256(instance_bytes).hexdigest()
    (problem / "instance.json").write_bytes(instance_bytes)
    manifest = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-instance-binding",
        "instance_file": "instance.json",
        "instance_sha256": instance_sha256,
        "structure_reference": "../../../shared/structure/structure.json",
        "structure_sha256": structure_sha256,
        "structure_manifest_reference": "../../../shared/structure/manifest.json",
        "structure_manifest_sha256": hashlib.sha256(
            structure_manifest_bytes
        ).hexdigest(),
        "reduction_reference": (
            "../../../shared/reduction/solver-reduction.json"
        ),
        "reduction_sha256": reduction_sha256,
        "reduction_manifest_reference": (
            "../../../shared/reduction/manifest.json"
        ),
        "reduction_manifest_sha256": hashlib.sha256(
            reduction_manifest_bytes
        ).hexdigest(),
    }
    manifest_bytes = _canonical_bytes(manifest)
    (problem / "manifest.json").write_bytes(manifest_bytes)
    return {
        "problem": problem,
        "problem_manifest_sha256": hashlib.sha256(
            manifest_bytes
        ).hexdigest(),
        "structure_sha256": structure_sha256,
        "instance_sha256": instance_sha256,
        "reduction_sha256": reduction_sha256,
    }


def _rewrite_v2_reduction(binding, mutate):
    problem = binding["problem"]
    cell_manifest_path = problem / "manifest.json"
    cell_manifest = json.loads(
        cell_manifest_path.read_text(encoding="utf-8")
    )
    reduction_path = (
        problem / cell_manifest["reduction_reference"]
    ).resolve()
    reduction = json.loads(reduction_path.read_text(encoding="utf-8"))
    mutate(reduction)
    reduction_bytes = _canonical_bytes(reduction)
    reduction_path.write_bytes(reduction_bytes)
    reduction_sha256 = hashlib.sha256(reduction_bytes).hexdigest()

    shared_manifest_path = (
        problem / cell_manifest["reduction_manifest_reference"]
    ).resolve()
    shared_manifest = json.loads(
        shared_manifest_path.read_text(encoding="utf-8")
    )
    shared_manifest["reduction_sha256"] = reduction_sha256
    shared_manifest["reduction_bytes"] = len(reduction_bytes)
    shared_manifest_bytes = _canonical_bytes(shared_manifest)
    shared_manifest_path.write_bytes(shared_manifest_bytes)

    cell_manifest["reduction_sha256"] = reduction_sha256
    cell_manifest["reduction_manifest_sha256"] = hashlib.sha256(
        shared_manifest_bytes
    ).hexdigest()
    cell_manifest_path.write_bytes(_canonical_bytes(cell_manifest))


class JuliaKyFanSolverTests(unittest.TestCase):
    def _run_solver(self, *arguments, environment=None):
        return subprocess.run(
            [
                "julia",
                f"--project={ROOT / 'julia-env'}",
                str(SOLVER),
                *map(str, arguments),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_solver_self_test_calibrates_psd_dual(self):
        result = self._run_solver("--self-test")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertAlmostEqual(payload["scalar_objective"], 1.0, places=8)
        self.assertAlmostEqual(payload["matrix_objective"], -2.0, places=8)
        self.assertEqual(payload["dual_cone"], "triangle-psd")
        self.assertTrue(payload["dual_identity_sign_calibrated"])
        self.assertTrue(payload["offdiagonal_scaling_calibrated"])

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_direct_solve_exports_row_major_full_dual(self):
        with TemporaryDirectory() as directory:
            problem = Path(directory) / "problem"
            output = Path(directory) / "solver"
            _write_toy_problem(problem)

            result = self._run_solver(
                "--problem-dir",
                problem,
                "--output-dir",
                output,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(
                (output / "solver-result.json").read_text(encoding="utf-8")
            )
            self.assertAlmostEqual(payload["objective"], -2.0, places=8)
            self.assertEqual(payload["dual_cone"], "triangle-psd")
            self.assertEqual(
                payload["equality_multipliers"][0]["identifier"],
                "trace-gamma-equals-2",
            )
            dual = payload["psd_duals"][0]
            self.assertEqual(dual["layout"], "row-major")
            self.assertEqual(
                dual["scalar_format"],
                "float64-little-endian",
            )
            raw = (output / dual["file"]).read_bytes()
            self.assertEqual(len(raw), 4 * 8)
            for entry in struct.unpack("<4d", raw):
                self.assertAlmostEqual(entry, 1.0, places=7)
            self.assertTrue((output / "solver-manifest.json").is_file())

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_array_mode_uses_spec_location_not_foreign_run_dir(self):
        with TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            problem = run / "cells/cell-0001/problem"
            _write_toy_problem(problem)
            run_spec = {
                "run_id": "toy",
                "run_dir": (
                    "/different-host/worktree/results/foreign-run"
                ),
                "cells": [{"cell_id": "cell-0001", "params": {}}],
            }
            spec_path = run / "run_spec.json"
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text(
                json.dumps(run_spec, indent=2) + "\n",
                encoding="utf-8",
            )
            environment = {
                **os.environ,
                "HARNESS_RUN_SPEC": str(spec_path),
                "SLURM_ARRAY_TASK_ID": "1",
            }

            result = self._run_solver(environment=environment)

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(
                (
                    run
                    / "cells/cell-0001/solver/solver-manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["selection"]["cell_id"],
                "cell-0001",
            )
            self.assertEqual(manifest["selection"]["cell_index"], 1)

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_solver_rejects_problem_hash_mismatch(self):
        with TemporaryDirectory() as directory:
            problem = Path(directory) / "problem"
            output = Path(directory) / "solver"
            _write_toy_problem(problem)
            with (problem / "problem.json").open("ab") as stream:
                stream.write(b" ")

            result = self._run_solver(
                "--problem-dir",
                problem,
                "--output-dir",
                output,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("problem SHA-256 mismatch", result.stderr)

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_direct_v2_solve_consumes_sparse_reduced_problem(self):
        with TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            binding = _write_toy_v2_problem(run)
            output = run / "cells/toy/solver"

            result = self._run_solver(
                "--problem-dir",
                binding["problem"],
                "--output-dir",
                output,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(
                (output / "solver-result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                payload["purpose"],
                "numerical-ky-fan-reduced-dual-v2",
            )
            for key in (
                "problem_manifest_sha256",
                "structure_sha256",
                "instance_sha256",
                "reduction_sha256",
            ):
                self.assertEqual(payload[key], binding[key])
            self.assertEqual(payload["solver_view"], "parameterized")
            self.assertEqual(payload["psd_duals"][0]["dimension"], 1)
            self.assertAlmostEqual(payload["objective"], 1.0, places=8)

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_v2_accepts_new_instance_with_same_shared_artifacts(self):
        with TemporaryDirectory() as directory:
            first_run = Path(directory) / "first"
            first = _write_toy_v2_problem(first_run, 1)
            first_result = self._run_solver(
                "--problem-dir",
                first["problem"],
                "--output-dir",
                first_run / "cells/toy/solver",
            )
            second_run = Path(directory) / "second"
            second = _write_toy_v2_problem(second_run, 2)
            second_result = self._run_solver(
                "--problem-dir",
                second["problem"],
                "--output-dir",
                second_run / "cells/toy/solver",
            )

            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertEqual(
                first["structure_sha256"],
                second["structure_sha256"],
            )
            self.assertEqual(
                first["reduction_sha256"],
                second["reduction_sha256"],
            )
            self.assertNotEqual(
                first["instance_sha256"],
                second["instance_sha256"],
            )
            for run in (first_run, second_run):
                payload = json.loads(
                    (
                        run / "cells/toy/solver/solver-result.json"
                    ).read_text(encoding="utf-8")
                )
                self.assertAlmostEqual(payload["objective"], 1.0, places=8)

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_v2_loader_accepts_delta_three_endpoint(self):
        with TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            binding = _write_toy_v2_problem(
                run,
                detuning="3/1",
            )
            result = self._run_solver(
                "--problem-dir",
                binding["problem"],
                "--output-dir",
                run / "cells/toy/solver",
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(
        os.environ.get("CHALLENGE233_RUN_JULIA_TESTS") == "1",
        "set CHALLENGE233_RUN_JULIA_TESTS=1 after make install kyfan-sdp",
    )
    def test_v2_loader_rejects_unsafe_or_inconsistent_reductions(self):
        mutations = (
            (
                "detuning independent",
                lambda binding: _rewrite_v2_reduction(
                    binding,
                    lambda reduction: reduction.update(
                        {"detuning": "0/1"}
                    ),
                ),
            ),
            (
                "solver view",
                lambda binding: _rewrite_v2_reduction(
                    binding,
                    lambda reduction: reduction.update(
                        {"selected_view": "invented"}
                    ),
                ),
            ),
            (
                "contiguous",
                lambda binding: _rewrite_v2_reduction(
                    binding,
                    lambda reduction: reduction["statistics"].update(
                        {"solver_variable_count": 2}
                    ),
                ),
            ),
            (
                "structure/reduction hash mismatch",
                lambda binding: _rewrite_v2_reduction(
                    binding,
                    lambda reduction: reduction.update(
                        {"structure_sha256": "0" * 64}
                    ),
                ),
            ),
            (
                "must be relative",
                lambda binding: (
                    lambda path, payload: path.write_bytes(
                        _canonical_bytes(
                            {
                                **payload,
                                "reduction_reference": str(
                                    (
                                        binding["problem"]
                                        / payload[
                                            "reduction_reference"
                                        ]
                                    ).resolve()
                                ),
                            }
                        )
                    )
                )(
                    binding["problem"] / "manifest.json",
                    json.loads(
                        (
                            binding["problem"] / "manifest.json"
                        ).read_text(encoding="utf-8")
                    ),
                ),
            ),
        )
        for index, (message, mutate) in enumerate(mutations):
            with self.subTest(message=message):
                with TemporaryDirectory() as directory:
                    run = Path(directory) / f"run-{index}"
                    binding = _write_toy_v2_problem(run)
                    mutate(binding)

                    result = self._run_solver(
                        "--problem-dir",
                        binding["problem"],
                        "--output-dir",
                        run / "cells/toy/solver",
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)


if __name__ == "__main__":
    unittest.main()
