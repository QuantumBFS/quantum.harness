from contextlib import redirect_stdout
import csv
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.run_kyfan import (  # noqa: E402
    _checked_ed_oracle_payload,
    _load_selection,
    _validate_ed_oracle_binding,
    assembly_probe,
    certify_cell,
    certify_run,
    estimate_v2_solve_resources,
    plan_escalation,
    plan_v2_run,
    prepare_cell,
    prepare_v2_run,
    remote_solve_command,
    select_cell,
    solve_local_cell,
    main as runner_main,
)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class FakeBlock:
    dimension: int


@dataclass(frozen=True)
class FakeProblem:
    size: int
    detuning: Fraction
    hierarchy: str
    localizer_mode: str
    statistics: dict
    psd_blocks: tuple


class FakeTrial:
    pass


def fake_export_problem(problem, output_directory):
    output = Path(output_directory)
    output.mkdir(parents=True)
    payload = {
        "size": problem.size,
        "detuning": (
            f"{problem.detuning.numerator}/"
            f"{problem.detuning.denominator}"
        ),
        "hierarchy": problem.hierarchy,
        "localizer_mode": problem.localizer_mode,
        "statistics": problem.statistics,
    }
    problem_path = output / "problem.json"
    write_json(problem_path, payload)
    write_json(
        output / "manifest.json",
        {
            "problem_file": problem_path.name,
            "problem_sha256": sha256(problem_path),
        },
    )


def fake_write_trial(trial, output_directory):
    del trial
    output = Path(output_directory)
    output.mkdir(parents=True)
    write_json(
        output / "trial-vector.json",
        {
            "purpose": "fixture",
            "b_var": "0/1",
        },
    )
    return {"status": "written", "b_var": "0/1"}


def fake_ed_oracle(cell):
    return {
        "purpose": "verified-finite-N-ed-oracle",
        "directory": (
            "../../../shared/ed-oracles/"
            f"n{cell.size:04d}-delta-"
            f"{cell.detuning.numerator}-over-{cell.detuning.denominator}"
        ),
        "size": cell.size,
        "detuning": (
            f"{cell.detuning.numerator}/"
            f"{cell.detuning.denominator}"
        ),
        "manifest_sha256": "a" * 64,
        "data_sha256": "b" * 64,
    }


def write_ed_oracle_fixture(directory, detuning=0.5):
    directory = Path(directory)
    directory.mkdir(parents=True)
    data_path = directory / "ed-gap.csv"
    fieldnames = [
        "size",
        "detuning",
        "basis_dimension",
        "e0",
        "e1",
        "e2",
        "e3",
        "gap",
        "residual_0",
        "residual_1",
        "residual_2",
        "residual_3",
        "max_residual",
        "hermiticity_max_abs",
        "matrix_nnz",
        "wall_seconds",
    ]
    with data_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "size": 4,
                "detuning": detuning,
                "basis_dimension": 7,
                "e0": -2.0,
                "e1": -1.5,
                "e2": -1.0,
                "e3": -0.5,
                "gap": 0.5,
                "residual_0": 1e-13,
                "residual_1": 2e-13,
                "residual_2": 3e-13,
                "residual_3": 4e-13,
                "max_residual": 4e-13,
                "hermiticity_max_abs": 0.0,
                "matrix_nnz": 12,
                "wall_seconds": 0.01,
            }
        )
    states_path = directory / "basis-states-N0004.npy"
    states_path.write_bytes(b"fixture basis ordering")
    write_json(
        directory / "manifest.json",
        {
            "hamiltonian": (
                "H_N(delta)=sum_i P_{i-1} X_i P_{i+1}"
                "-delta sum_i n_i"
            ),
            "rabi_coefficient": 1.0,
            "detuning_sign": "-delta",
            "boundary": "periodic",
            "local_state_convention": "0=down, 1=up",
            "blockade_constraint": "n_i n_{i+1}=0",
            "symmetry_sector": "full constrained Hilbert space",
            "target_gap": "E_1-E_0, all momenta",
            "point_count": 1,
            "sizes": [4],
            "detunings": [detuning],
            "data_file": data_path.name,
            "data_sha256": sha256(data_path),
            "basis_state_files": {
                "4": {
                    "path": states_path.name,
                    "count": 7,
                    "sha256": sha256(states_path),
                }
            },
            "source_file_sha256": {
                relative: sha256(ROOT / relative)
                for relative in (
                    "src/challenge233/basis/pxp.py",
                    "src/challenge233/ed/pxp_gap.py",
                )
            },
        },
    )


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run_directory = Path(self.temporary.name) / "run"
        self.run_spec_path = self.run_directory / "run_spec.json"
        self.run_spec = {
            "run_id": "runner-test",
            "run_dir": str(self.run_directory),
            "settings": {
                "hierarchy": "L0",
                "localizer_mode": "sound",
                "trial_bits": 40,
            },
            "provenance": {"physical_contract": "periodic-pxp-v1"},
            "cells": [
                {
                    "cell_id": "cell-0001",
                    "params": {
                        "size": 4,
                        "detuning_tenths": 0,
                    },
                },
                {
                    "cell_id": "cell-0002",
                    "params": {
                        "size": 5,
                        "detuning_tenths": 7,
                    },
                },
                {
                    "cell_id": "cell-0003",
                    "params": {
                        "size": 20,
                        "detuning_tenths": 10,
                    },
                },
            ],
        }
        write_json(self.run_spec_path, self.run_spec)

    def fake_problem(self, cell):
        return FakeProblem(
            size=cell.size,
            detuning=cell.detuning,
            hierarchy=cell.hierarchy,
            localizer_mode=cell.localizer_mode,
            statistics={
                "variable_count": 3,
                "equality_count": 4,
                "affine_nonzero_count": 10,
            },
            psd_blocks=(FakeBlock(6), FakeBlock(6)),
        )

    def prepare_first_cell(self):
        with (
            patch(
                "challenge233.sdp.run_kyfan.build_problem_for_cell",
                side_effect=self.fake_problem,
            ),
            patch(
                "challenge233.sdp.run_kyfan.export_kyfan_problem",
                side_effect=fake_export_problem,
            ),
            patch(
                "challenge233.sdp.run_kyfan.verify_kyfan_problem",
                return_value={"status": "verified"},
            ),
            patch(
                "challenge233.sdp.run_kyfan.generate_quspin_trial",
                return_value=FakeTrial(),
            ),
            patch(
                "challenge233.sdp.run_kyfan.write_trial_vector",
                side_effect=fake_write_trial,
            ),
        ):
            return prepare_cell(self.run_spec_path, 1)

    def test_cell_selection_is_one_based_and_detuning_is_exact(self):
        first = select_cell(self.run_spec, 1)
        last = select_cell(self.run_spec, 3)
        middle = select_cell(self.run_spec, 2)

        self.assertEqual(first.cell_id, "cell-0001")
        self.assertEqual(last.cell_id, "cell-0003")
        self.assertEqual(middle.detuning, Fraction(7, 10))
        for invalid in (0, 4):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "one-based"):
                    select_cell(self.run_spec, invalid)

    def test_cell_selection_accepts_delta_three_endpoint(self):
        extended = json.loads(json.dumps(self.run_spec))
        extended["cells"][2]["params"]["detuning_tenths"] = 30

        selected = select_cell(extended, 3)

        self.assertEqual(selected.detuning, Fraction(3))

    def test_relative_run_directory_is_root_relative(self):
        repository = Path(self.temporary.name) / "repository"
        run_directory = repository / "results/relative-run"
        spec_path = run_directory / "run_spec.json"
        relative_spec = {
            **self.run_spec,
            "run_dir": "results/relative-run",
        }
        write_json(spec_path, relative_spec)

        with patch(
            "challenge233.sdp.run_kyfan.ROOT",
            repository,
        ):
            _, selected = _load_selection(spec_path, 1)

        self.assertEqual(selected.run_directory, run_directory.resolve())

    def test_prepare_writes_only_problem_and_trial_stages(self):
        summary = self.prepare_first_cell()
        cell = self.run_directory / "cells/cell-0001"

        self.assertEqual(summary["status"], "prepared")
        self.assertTrue((cell / "problem/problem.json").is_file())
        self.assertTrue((cell / "trial/trial-vector.json").is_file())
        self.assertTrue((cell / "prepare-manifest.json").is_file())
        self.assertFalse((cell / "solver").exists())
        self.assertFalse((cell / "certificate").exists())
        self.assertFalse((cell / "manifest.json").exists())

    def test_local_solve_refuses_a_changed_problem_hash(self):
        self.prepare_first_cell()
        problem_path = (
            self.run_directory
            / "cells/cell-0001/problem/problem.json"
        )
        with problem_path.open("a", encoding="utf-8") as stream:
            stream.write(" ")

        with self.assertRaisesRegex(ValueError, "problem hash changed"):
            solve_local_cell(self.run_spec_path, 1)

    def test_certify_refuses_a_missing_solver_manifest(self):
        self.prepare_first_cell()

        with self.assertRaisesRegex(FileNotFoundError, "solver manifest"):
            certify_cell(self.run_spec_path, 1)

    def test_certify_refuses_a_failed_solver_manifest(self):
        self.prepare_first_cell()
        solver = self.run_directory / "cells/cell-0001/solver"
        solver.mkdir()
        write_json(
            solver / "solver-manifest.json",
            {
                "success": False,
                "operational_status": "numerical-failure",
            },
        )

        with self.assertRaisesRegex(ValueError, "report success"):
            certify_cell(self.run_spec_path, 1)

    def test_slurm_solver_without_accounting_is_uncertifiable(self):
        self.prepare_first_cell()
        cell = self.run_directory / "cells/cell-0001"
        solver = cell / "solver"
        solver.mkdir()
        problem_sha = json.loads(
            (cell / "problem/manifest.json").read_text(encoding="utf-8")
        )["problem_sha256"]
        write_json(
            solver / "solver-result.json",
            {
                "success": True,
                "problem_sha256": problem_sha,
                "selection": {
                    "mode": "slurm-array",
                    "cell_id": "cell-0001",
                    "cell_index": 1,
                },
            },
        )
        write_json(
            solver / "solver-manifest.json",
            {
                "success": True,
                "problem_sha256": problem_sha,
                "solver_result_file": "solver-result.json",
                "solver_result_sha256": sha256(
                    solver / "solver-result.json"
                ),
            },
        )

        with self.assertRaisesRegex(
            FileNotFoundError,
            "Slurm task accounting",
        ):
            certify_cell(self.run_spec_path, 1)

    def test_remote_solve_command_is_pure_julia(self):
        command = remote_solve_command()
        joined = " ".join(command).lower()

        self.assertIn("julia", joined)
        self.assertIn("solve_kyfan.jl", joined)
        for forbidden in ("python", "conda", "quspin"):
            self.assertNotIn(forbidden, joined)

    def test_v2_resource_gate_requires_same_formulation_benchmark(self):
        reduction = {
            "resource_estimate": {
                "clarabel_hs_bytes": 1024,
                "estimated_rss_bytes": 2 * (1 << 30),
                "requires_wall_benchmark": True,
            }
        }

        without_benchmark = estimate_v2_solve_resources(reduction)
        with_benchmark = estimate_v2_solve_resources(
            reduction,
            benchmark_wall_seconds=17,
        )
        old_raw_shape = estimate_v2_solve_resources(
            {
                "resource_estimate": {
                    "clarabel_hs_bytes": 2 * (1 << 30),
                    "estimated_rss_bytes": 15 * (1 << 30),
                    "requires_wall_benchmark": True,
                }
            },
            benchmark_wall_seconds=17,
        )

        self.assertFalse(without_benchmark["automatic_local_allowed"])
        self.assertTrue(with_benchmark["automatic_local_allowed"])
        self.assertFalse(old_raw_shape["automatic_local_allowed"])
        self.assertEqual(with_benchmark["benchmark_wall_seconds"], 17)

    def test_plan_v2_run_uses_exact_cartesian_cells(self):
        output = Path(self.temporary.name) / "planned-v2"

        summary = plan_v2_run(
            output,
            sizes=(4, 5),
            detunings=(Fraction(0), Fraction(1, 2), Fraction(3)),
            levels=("global-d2",),
            localizer_mode="sound",
            exactness_tolerance=Fraction(1, 10**8),
        )
        planned = json.loads(
            (output / "run_spec.json").read_text(encoding="utf-8")
        )

        self.assertEqual(summary["cell_count"], 6)
        self.assertEqual(planned["schema_version"], 2)
        self.assertEqual(
            [cell["params"]["detuning"] for cell in planned["cells"]],
            ["0/1", "1/2", "3/1", "0/1", "1/2", "3/1"],
        )
        self.assertEqual(
            planned["settings"]["exactness_tolerance"],
            "1/100000000",
        )

    def test_plan_v2_run_rejects_floats_duplicates_and_contract_escape(self):
        cases = (
            {
                "sizes": (4,),
                "detunings": (0.5,),
                "levels": ("global-d2",),
                "message": "exact rational",
            },
            {
                "sizes": (4, 4),
                "detunings": (Fraction(0),),
                "levels": ("global-d2",),
                "message": "duplicate",
            },
            {
                "sizes": (21,),
                "detunings": (Fraction(0),),
                "levels": ("global-d2",),
                "message": "4 <= N <= 20",
            },
            {
                "sizes": (4,),
                "detunings": (Fraction(61, 20),),
                "levels": ("global-d2",),
                "message": r"\[0,3\]",
            },
        )
        for index, case in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, case["message"]):
                    plan_v2_run(
                        Path(self.temporary.name) / f"invalid-{index}",
                        case["sizes"],
                        case["detunings"],
                        case["levels"],
                        "sound",
                    )

    def test_plan_v2_cli_accepts_only_exact_comma_arguments(self):
        output = Path(self.temporary.name) / "cli-v2"
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            status = runner_main(
                [
                    "plan-v2-run",
                    "--output",
                    str(output),
                    "--sizes",
                    "4,5",
                    "--detunings",
                    "0,1/2",
                    "--levels",
                    "global-d2",
                    "--exactness-tolerance",
                    "1/1000",
                ]
            )

        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue())["cell_count"], 4)
        with self.assertRaisesRegex(ValueError, "numerator/denominator"):
            runner_main(
                [
                    "plan-v2-run",
                    "--output",
                    str(Path(self.temporary.name) / "float-v2"),
                    "--sizes",
                    "4",
                    "--detunings",
                    "0.5",
                    "--levels",
                    "global-d2",
                ]
            )

    def test_schema_v2_probe_reports_reduction_without_solver_status(self):
        output = Path(self.temporary.name) / "probe-v2.json"

        payload = assembly_probe(
            4,
            "global-d2",
            Fraction(1, 2),
            "sound",
            schema_version=2,
            output=output,
        )

        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["purpose"], "presolve-readiness-v2")
        self.assertEqual(payload["status"], "verified")
        for section in (
            "structure",
            "quotient",
            "equality",
            "spatial_blocks",
            "serialization",
            "memory",
        ):
            self.assertIn(section, payload["inventories"])
        self.assertIn(
            "action_rank",
            payload["inventories"]["quotient"],
        )
        self.assertIn(
            "row_rank",
            payload["inventories"]["equality"],
        )
        self.assertIn(
            "clarabel_hs_bytes",
            payload["inventories"]["memory"],
        )
        self.assertIn(
            "estimated_rss_bytes",
            payload["inventories"]["memory"],
        )
        self.assertEqual(
            payload["inventories"]["memory"]["wall_anchor_status"],
            "missing",
        )
        self.assertIn("serialization", payload["inventories"])
        self.assertNotIn("solver_status", json.dumps(payload))
        self.assertEqual(json.loads(output.read_text()), payload)

    def test_ed_oracle_binding_checks_the_identical_physical_point(self):
        run = Path(self.temporary.name) / "ed-binding-v2"
        plan_v2_run(
            run,
            sizes=(4,),
            detunings=(Fraction(1, 2),),
            levels=("global-d2",),
            localizer_mode="sound",
        )
        _, cell = _load_selection(run / "run_spec.json", 1)
        directory = (
            run
            / "shared/ed-oracles/n0004-delta-1-over-2"
        )
        write_ed_oracle_fixture(directory)

        binding = _checked_ed_oracle_payload(cell, directory)
        checked = _validate_ed_oracle_binding(cell, binding)

        self.assertEqual(checked["size"], 4)
        self.assertEqual(checked["detuning"], "1/2")
        self.assertEqual(checked["gap"], "0.5")
        manifest_path = directory / "manifest.json"
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        manifest["target_gap"] = "E_2-E_0"
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "target_gap"):
            _checked_ed_oracle_payload(cell, directory)

    def test_prepare_v2_run_shares_structure_and_reduction(self):
        run = Path(self.temporary.name) / "shared-v2"
        plan_v2_run(
            run,
            sizes=(4,),
            detunings=(Fraction(0), Fraction(1, 2)),
            levels=("global-d2",),
            localizer_mode="sound",
        )

        with (
            patch(
                "challenge233.sdp.run_kyfan.generate_quspin_trial",
                return_value=FakeTrial(),
            ),
            patch(
                "challenge233.sdp.run_kyfan.write_trial_vector",
                side_effect=fake_write_trial,
            ),
            patch(
                "challenge233.sdp.run_kyfan._ensure_v2_ed_oracle",
                side_effect=fake_ed_oracle,
            ),
        ):
            summaries = prepare_v2_run(run / "run_spec.json")

        self.assertEqual(len(summaries), 2)
        manifests = [
            json.loads(
                (
                    run
                    / "cells"
                    / f"cell-{index:04d}"
                    / "problem/manifest.json"
                ).read_text(encoding="utf-8")
            )
            for index in (1, 2)
        ]
        self.assertEqual(
            manifests[0]["structure_reference"],
            manifests[1]["structure_reference"],
        )
        self.assertEqual(
            manifests[0]["reduction_reference"],
            manifests[1]["reduction_reference"],
        )
        self.assertNotEqual(
            manifests[0]["instance_sha256"],
            manifests[1]["instance_sha256"],
        )
        for index in (1, 2):
            prepare = json.loads(
                (
                    run
                    / "cells"
                    / f"cell-{index:04d}"
                    / "prepare-manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                prepare["ed_oracle"]["purpose"],
                "verified-finite-N-ed-oracle",
            )
        staging = json.loads(
            (run / "slurm-staging-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(staging["cells"]), 2)
        staged_names = {
            item["file"] for item in staging["source_files"]
        }
        self.assertIn(
            "src/challenge233/sdp/solve_kyfan.jl",
            staged_names,
        )
        self.assertFalse(
            any(name.endswith(".py") for name in staged_names)
        )
        self.assertNotIn(".git", json.dumps(staging))
        first_problem = run / "cells/cell-0001/problem"
        with (first_problem / "instance.json").open(
            "ab"
        ) as stream:
            stream.write(b" ")
        with self.assertRaisesRegex(ValueError, "instance hash changed"):
            solve_local_cell(run / "run_spec.json", 1)

        second_problem = run / "cells/cell-0002/problem"
        shared_structure = (
            second_problem / manifests[1]["structure_reference"]
        ).resolve()
        with shared_structure.open("ab") as stream:
            stream.write(b" ")
        with self.assertRaisesRegex(ValueError, "structure hash changed"):
            solve_local_cell(run / "run_spec.json", 2)

    def test_runner_interfaces_are_lazy_package_exports(self):
        import challenge233.sdp as sdp

        self.assertIs(sdp.prepare_cell, prepare_cell)
        self.assertIs(sdp.prepare_v2_run, prepare_v2_run)
        self.assertIs(sdp.plan_v2_run, plan_v2_run)
        self.assertIs(sdp.certify_cell, certify_cell)
        self.assertIs(sdp.certify_run, certify_run)
        self.assertIs(sdp.plan_escalation, plan_escalation)

    def test_local_solve_invokes_julia_and_records_stage_hashes(self):
        self.prepare_first_cell()
        cell = self.run_directory / "cells/cell-0001"

        def fake_run(command, **kwargs):
            self.assertIn("julia", Path(command[0]).name)
            self.assertNotIn("python", " ".join(command).lower())
            solver = cell / "solver"
            solver.mkdir()
            write_json(
                solver / "solver-result.json",
                {
                    "success": True,
                    "problem_sha256": json.loads(
                        (
                            cell / "problem/manifest.json"
                        ).read_text(encoding="utf-8")
                    )["problem_sha256"],
                },
            )
            write_json(
                solver / "solver-manifest.json",
                {
                    "success": True,
                    "problem_sha256": json.loads(
                        (
                            cell / "problem/manifest.json"
                        ).read_text(encoding="utf-8")
                    )["problem_sha256"],
                    "solver_result_file": "solver-result.json",
                    "solver_result_sha256": sha256(
                        solver / "solver-result.json"
                    ),
                },
            )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"status":"solved"}\n',
                stderr="",
            )

        with patch(
            "challenge233.sdp.run_kyfan.subprocess.run",
            side_effect=fake_run,
        ):
            summary = solve_local_cell(self.run_spec_path, 1)

        self.assertEqual(summary["status"], "solved")
        record = json.loads(
            (cell / "solve-local-record.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["operational_status"], "success")
        self.assertEqual(
            record["solver_manifest_sha256"],
            sha256(cell / "solver/solver-manifest.json"),
        )

    def test_local_solve_dispatches_schema_v2_hash_bindings(self):
        cell = self.run_directory / "cells/cell-0001"
        cell.mkdir(parents=True)
        prepare = {
            "schema_version": 2,
            "problem_manifest_sha256": "1" * 64,
            "structure_sha256": "2" * 64,
            "instance_sha256": "3" * 64,
            "reduction_sha256": "4" * 64,
            "solver_view": "parameterized",
            "resource_estimate": {
                "estimated_rss_bytes": 1 << 30,
                "benchmark_wall_seconds": 10,
                "automatic_local_allowed": True,
            },
        }

        def fake_run(command, **kwargs):
            del kwargs
            solver = cell / "solver"
            solver.mkdir()
            write_json(
                solver / "solver-result.json",
                {
                    "success": True,
                    "problem_manifest_sha256": "1" * 64,
                    "structure_sha256": "2" * 64,
                    "instance_sha256": "3" * 64,
                    "reduction_sha256": "4" * 64,
                    "solver_view": "parameterized",
                },
            )
            write_json(
                solver / "solver-manifest.json",
                {
                    "success": True,
                    "problem_manifest_sha256": "1" * 64,
                    "structure_sha256": "2" * 64,
                    "instance_sha256": "3" * 64,
                    "reduction_sha256": "4" * 64,
                    "solver_view": "parameterized",
                    "solver_result_file": "solver-result.json",
                    "solver_result_sha256": sha256(
                        solver / "solver-result.json"
                    ),
                },
            )
            return subprocess.CompletedProcess(command, 0, "ok", "")

        with (
            patch(
                "challenge233.sdp.run_kyfan._validated_prepare",
                return_value=prepare,
            ),
            patch(
                "challenge233.sdp.run_kyfan.subprocess.run",
                side_effect=fake_run,
            ),
        ):
            summary = solve_local_cell(self.run_spec_path, 1)

        self.assertEqual(summary["status"], "solved")
        self.assertEqual(
            json.loads(
                (cell / "solve-local-record.json").read_text(
                    encoding="utf-8"
                )
            )["operational_status"],
            "success",
        )

    def test_local_timeout_writes_operational_record_only(self):
        self.prepare_first_cell()
        cell = self.run_directory / "cells/cell-0001"

        with patch(
            "challenge233.sdp.run_kyfan.subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                ["julia", "solve_kyfan.jl"],
                17,
                output="partial stdout",
                stderr="partial stderr",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                solve_local_cell(
                    self.run_spec_path,
                    1,
                    timeout_seconds=17,
                )

        record = json.loads(
            (cell / "solve-local-record.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(record["operational_status"], "timeout")
        self.assertEqual(record["timeout_seconds"], 17)
        self.assertFalse((cell / "certificate").exists())
        self.assertFalse((cell / "manifest.json").exists())

    def test_certify_writes_hash_bound_final_manifest(self):
        self.prepare_first_cell()
        cell = self.run_directory / "cells/cell-0001"
        solver = cell / "solver"
        solver.mkdir()
        problem_sha = json.loads(
            (cell / "problem/manifest.json").read_text(encoding="utf-8")
        )["problem_sha256"]
        write_json(
            solver / "solver-result.json",
            {
                "success": True,
                "problem_sha256": problem_sha,
                "termination_status": "OPTIMAL",
                "primal_status": "FEASIBLE_POINT",
                "dual_status": "FEASIBLE_POINT",
                "raw_status": "Solved",
                "versions": {"fixture": "1"},
                "settings": {"fixture": True},
                "selection": {
                    "mode": "slurm-array",
                    "cell_id": "cell-0001",
                    "cell_index": 1,
                    "run_spec_sha256": "fixture-run-spec-sha",
                },
            },
        )
        write_json(
            solver / "solver-manifest.json",
            {
                "success": True,
                "problem_sha256": problem_sha,
                "solver_result_file": "solver-result.json",
                "solver_result_sha256": sha256(
                    solver / "solver-result.json"
                ),
            },
        )
        write_json(
            cell / "solve-local-record.json",
            {
                "schema_version": 1,
                "purpose": "local-ky-fan-solve-record",
                "operational_status": "timeout",
                "timeout_seconds": 480,
                "elapsed_seconds": 480.1,
            },
        )
        write_json(
            cell / "slurm-task-record.json",
            {
                "schema_version": 1,
                "purpose": "slurm-array-task-accounting",
                "cell_id": "cell-0001",
                "cell_index": 1,
                "job_id": "12345",
                "array_task_id": 1,
                "state": "COMPLETED",
                "exit_code": "0:0",
                "classification": "success",
                "elapsed": "00:12:34",
                "max_rss": "7340032K",
                "allocated_cpus": 4,
                "requested_memory": "3931Mc",
                "partition": "cpu",
                "node_list": "node001",
            },
        )

        def fake_build(*arguments, **kwargs):
            del arguments, kwargs
            certificate = cell / "certificate"
            certificate.mkdir()
            write_json(
                certificate / "certificate.json",
                {
                    "a": "-1/1",
                    "a_cert": "-2/1",
                    "b_var": "0/1",
                    "rho": "1/1",
                    "delta_cert": "-2/1",
                    "status": "not_certified",
                    "dual_residuals_file": "dual-residuals.json",
                    "dual_residuals_sha256": "",
                },
            )
            write_json(
                certificate / "dual-residuals.json",
                {
                    "purpose": "exact-ky-fan-dual-residuals",
                    "a": "-1/1",
                    "residuals": [
                        {
                            "variable": 0,
                            "value": "1/4",
                            "bound": "2/1",
                            "correction": "1/2",
                        },
                        {
                            "variable": 1,
                            "value": "-1/4",
                            "bound": "2/1",
                            "correction": "1/2",
                        },
                    ],
                    "rho": "1/1",
                    "a_cert": "-2/1",
                },
            )
            certificate_payload = json.loads(
                (certificate / "certificate.json").read_text(
                    encoding="utf-8"
                )
            )
            certificate_payload["dual_residuals_sha256"] = sha256(
                certificate / "dual-residuals.json"
            )
            write_json(
                certificate / "certificate.json",
                certificate_payload,
            )
            write_json(
                certificate / "manifest.json",
                {
                    "certificate_file": "certificate.json",
                    "certificate_sha256": sha256(
                        certificate / "certificate.json"
                    ),
                },
            )
            return {"status": "not_certified"}

        with (
            patch(
                "challenge233.sdp.run_kyfan.build_dual_certificate",
                side_effect=fake_build,
            ),
            patch(
                "challenge233.sdp.run_kyfan.verify_kyfan_certificate",
                return_value={
                    "status": "verified",
                    "a_cert": "-2/1",
                    "b_var": "0/1",
                    "delta_cert": "-2/1",
                    "certificate_status": "not_certified",
                },
            ),
        ):
            summary = certify_cell(self.run_spec_path, 1)

        self.assertEqual(summary["status"], "not_certified")
        final = json.loads(
            (cell / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertTrue(final["independent_check_passed"])
        self.assertEqual(final["certificate_status"], "not_certified")
        self.assertEqual(final["problem_sha256"], problem_sha)
        self.assertEqual(
            final["prepare_manifest_sha256"],
            sha256(cell / "prepare-manifest.json"),
        )
        self.assertEqual(
            final["solver_manifest_sha256"],
            sha256(solver / "solver-manifest.json"),
        )
        self.assertEqual(
            final["certificate_manifest_sha256"],
            sha256(cell / "certificate/manifest.json"),
        )
        self.assertEqual(
            final["certificate"]["dual_residuals_sha256"],
            sha256(cell / "certificate/dual-residuals.json"),
        )
        self.assertEqual(
            final["certificate"]["residual_diagnostics"],
            {
                "nonzero_count": 2,
                "raw_constant_a": "-1/1",
                "residual_count": 2,
                "residual_correction_rho": "1/1",
                "maximum_absolute_residual": "1/4",
            },
        )
        self.assertEqual(
            final["resource_provenance"]["placement"],
            "slurm",
        )
        self.assertEqual(
            final["resource_provenance"]["prior_local_attempt"][
                "operational_status"
            ],
            "timeout",
        )
        self.assertEqual(
            final["resource_provenance"]["solver_selection"]["mode"],
            "slurm-array",
        )
        self.assertEqual(
            final["resource_provenance"]["slurm_task_record"]["job_id"],
            "12345",
        )
        self.assertEqual(
            final["resource_provenance"]["slurm_task_record_sha256"],
            sha256(cell / "slurm-task-record.json"),
        )

    def test_certify_schema_v2_binds_reduction_and_both_corrections(self):
        cell = self.run_directory / "cells/cell-0001"
        solver = cell / "solver"
        solver.mkdir(parents=True)
        prepare = {
            "schema_version": 2,
            "problem_manifest_sha256": "1" * 64,
            "structure_sha256": "2" * 64,
            "instance_sha256": "3" * 64,
            "reduction_sha256": "4" * 64,
            "solver_view": "parameterized",
            "trial_vector_sha256": "5" * 64,
            "resource_estimate": {},
            "ed_oracle": {
                "purpose": "verified-finite-N-ed-oracle",
                "directory": (
                    "../../../shared/ed-oracles/"
                    "n0004-delta-1-over-2"
                ),
            },
        }
        write_json(cell / "prepare-manifest.json", prepare)
        result = {
            "success": True,
            "problem_manifest_sha256": "1" * 64,
            "structure_sha256": "2" * 64,
            "instance_sha256": "3" * 64,
            "reduction_sha256": "4" * 64,
            "solver_view": "parameterized",
            "selection": {"mode": "external-direct"},
            "termination_status": "OPTIMAL",
            "primal_status": "FEASIBLE_POINT",
            "dual_status": "FEASIBLE_POINT",
        }
        write_json(solver / "solver-result.json", result)
        write_json(
            solver / "solver-manifest.json",
            {
                **{
                    key: prepare[key]
                    for key in (
                        "problem_manifest_sha256",
                        "structure_sha256",
                        "instance_sha256",
                        "reduction_sha256",
                        "solver_view",
                    )
                },
                "success": True,
                "solver_result_file": "solver-result.json",
                "solver_result_sha256": sha256(
                    solver / "solver-result.json"
                ),
            },
        )

        def fake_build(*arguments, **kwargs):
            del arguments, kwargs
            certificate = cell / "certificate"
            certificate.mkdir()
            residual = {
                "a": "-1/1",
                "residuals": [
                    {"variable": 0, "value": "1/4"},
                ],
                "rho_mom": "1/2",
                "rho_op": "1/4",
                "rho": "1/4",
                "residual_route": "physical-operator",
                "a_cert": "-5/4",
            }
            write_json(certificate / "dual-residuals.json", residual)
            payload = {
                "a": "-1/1",
                "a_cert": "-5/4",
                "b_var": "0/1",
                "rho_mom": "1/2",
                "rho_op": "1/4",
                "rho": "1/4",
                "residual_route": "physical-operator",
                "delta_cert": "-5/4",
                "status": "not_certified",
                "dual_residuals_file": "dual-residuals.json",
                "dual_residuals_sha256": sha256(
                    certificate / "dual-residuals.json"
                ),
            }
            write_json(certificate / "certificate.json", payload)
            write_json(
                certificate / "manifest.json",
                {
                    "certificate_file": "certificate.json",
                    "certificate_sha256": sha256(
                        certificate / "certificate.json"
                    ),
                },
            )

        with (
            patch(
                "challenge233.sdp.run_kyfan._validated_prepare",
                return_value=prepare,
            ),
            patch(
                "challenge233.sdp.run_kyfan.build_dual_certificate",
                side_effect=fake_build,
            ),
            patch(
                "challenge233.sdp.run_kyfan.verify_kyfan_certificate",
                return_value={
                    "status": "verified",
                    "schema_version": 2,
                    "a_cert": "-5/4",
                    "b_var": "0/1",
                    "delta_cert": "-5/4",
                    "rho_mom": "1/2",
                    "rho_op": "1/4",
                    "residual_route": "physical-operator",
                    "certificate_status": "not_certified",
                },
            ),
        ):
            summary = certify_cell(self.run_spec_path, 1)

        self.assertEqual(summary["status"], "not_certified")
        final = json.loads(
            (cell / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(final["schema_version"], 2)
        self.assertEqual(final["structure_sha256"], "2" * 64)
        self.assertEqual(final["instance_sha256"], "3" * 64)
        self.assertEqual(final["reduction_sha256"], "4" * 64)
        self.assertEqual(
            final["certificate"]["rho_mom"],
            "1/2",
        )
        self.assertEqual(
            final["certificate"]["rho_op"],
            "1/4",
        )
        self.assertEqual(
            final["certificate"]["residual_route"],
            "physical-operator",
        )

    def test_escalation_selects_scientific_failures_not_retries(self):
        source = Path(self.temporary.name) / "source"
        cells = [
            {
                "cell_id": f"cell-{index:04d}",
                "params": {
                    "size": index + 3,
                    "detuning_tenths": index,
                },
            }
            for index in range(1, 6)
        ]
        write_json(
            source / "run_spec.json",
            {
                "run_id": "source",
                "run_dir": str(source),
                "settings": {
                    "hierarchy": "L0",
                    "localizer_mode": "sound",
                },
                "provenance": {"physical_contract": "fixture"},
                "cells": cells,
            },
        )
        final_payloads = {
            "cell-0001": {
                "independent_check_passed": True,
                "certificate_status": "certified",
                "certificate": {"delta_cert": "1/5"},
            },
            "cell-0002": {
                "independent_check_passed": True,
                "certificate_status": "not_certified",
                "certificate": {"delta_cert": "0/1"},
            },
            "cell-0003": {
                "independent_check_passed": True,
                "certificate_status": "certified",
                "certificate": {"delta_cert": "1/20"},
            },
            "cell-0004": {
                "independent_check_passed": False,
                "certificate_status": "not_certified",
                "certificate": {"delta_cert": "0/1"},
            },
        }
        for cell_id, payload in final_payloads.items():
            write_json(
                source / "cells" / cell_id / "manifest.json",
                payload,
            )

        output = Path(self.temporary.name) / "escalated"
        summary = plan_escalation(
            source,
            "L1",
            output,
            robustness_margin=Fraction(1, 10),
        )
        escalated = json.loads(
            (output / "run_spec.json").read_text(encoding="utf-8")
        )

        self.assertEqual(summary["selected_cells"], 3)
        self.assertEqual(summary["retry_candidates"], 1)
        self.assertEqual(escalated["settings"]["hierarchy"], "L1")
        self.assertEqual(
            [
                cell["params"]["source_cell_id"]
                for cell in escalated["cells"]
            ],
            ["cell-0002", "cell-0003", "cell-0004"],
        )
        self.assertEqual(
            escalated["operational_retry_candidates"],
            [
                {
                    "source_cell_id": "cell-0005",
                    "reason": "missing-final-manifest",
                }
            ],
        )
        self.assertEqual(
            escalated["cells"][1]["params"]["detuning_tenths"],
            3,
        )

    def write_anchor_final_manifests(self, run):
        run_spec = json.loads(
            (run / "run_spec.json").read_text(encoding="utf-8")
        )
        levels = ("global-d2", "global-d3", "global-d4")
        deltas = ("1/10", "1/5", "3/10")
        a_values = ("-37/10", "-18/5", "-7/2")
        for index, (level, delta, a_cert) in enumerate(
            zip(levels, deltas, a_values),
            start=1,
        ):
            cell = run / "cells" / f"cell-{index:04d}"
            write_json(
                cell / "manifest.json",
                {
                    "schema_version": 2,
                    "cell_id": f"cell-{index:04d}",
                    "cell_index": index,
                    "physical_contract": {
                        "hamiltonian": (
                            "H_N(delta)=sum_i P_{i-1} X_i "
                            "P_{i+1}-delta sum_i n_i"
                        ),
                        "size": 4,
                        "detuning": "1/2",
                        "hierarchy": level,
                        "localizer_mode": "sound",
                        "boundary": "periodic",
                        "target": (
                            "multiplicity-counted global E1-E0"
                        ),
                    },
                    "params": run_spec["cells"][index - 1]["params"],
                    "structure_sha256": str(index) * 64,
                    "instance_sha256": str(index + 3) * 64,
                    "reduction_sha256": str(index + 6) * 64,
                    "solver_manifest_sha256": str(index + 1) * 64,
                    "solver_result_sha256": str(index + 2) * 64,
                    "trial_vector_sha256": str(index + 4) * 64,
                    "certificate_manifest_sha256": (
                        str(index + 5) * 64
                    ),
                    "certificate_sha256": str(index + 6) * 64,
                    "prepare_manifest_sha256": str(index + 7) * 64,
                    "certificate": {
                        "a_cert": a_cert,
                        "b_var": "-19/10",
                        "delta_cert": delta,
                        "rho_mom": "1/10",
                        "rho_op": "1/20",
                        "rho": "1/20",
                        "residual_route": "physical-operator",
                    },
                    "certificate_status": "certified",
                    "independent_check_passed": True,
                    "ed_oracle": {
                        "purpose": "verified-finite-N-ed-oracle",
                        "directory": (
                            "../../../shared/ed-oracles/"
                            "n0004-delta-1-over-2"
                        ),
                    },
                    "resource_provenance": {
                        "placement": "local",
                        "prior_local_attempt": {
                            "purpose": "local-ky-fan-solve-record",
                            "operational_status": "success",
                            "elapsed_seconds": 12 + index,
                            "peak_rss_bytes": 1 << 30,
                            "solver_manifest_sha256": (
                                str(index + 1) * 64
                            ),
                            "solver_result_sha256": (
                                str(index + 2) * 64
                            ),
                        },
                        "slurm_task_record": None,
                        "slurm_task_record_sha256": None,
                    },
                },
            )

    def test_certify_run_rejects_incomplete_n4_anchor_inventory(self):
        run = Path(self.temporary.name) / "incomplete-anchor"
        plan_v2_run(
            run,
            sizes=(4,),
            detunings=(Fraction(1, 2),),
            levels=("global-d2", "global-d3"),
            localizer_mode="sound",
            exactness_tolerance=Fraction(1, 10**8),
        )

        with self.assertRaisesRegex(ValueError, "d2/d3/d4"):
            certify_run(run / "run_spec.json")

    def test_certify_run_requires_ed_and_accounting_for_every_cell(self):
        for missing in ("ed", "accounting"):
            with self.subTest(missing=missing):
                run = (
                    Path(self.temporary.name)
                    / f"missing-{missing}-anchor"
                )
                plan_v2_run(
                    run,
                    sizes=(4,),
                    detunings=(Fraction(1, 2),),
                    levels=(
                        "global-d2",
                        "global-d3",
                        "global-d4",
                    ),
                    localizer_mode="sound",
                    exactness_tolerance=Fraction(1, 10**8),
                )
                self.write_anchor_final_manifests(run)
                first = run / "cells/cell-0001/manifest.json"
                payload = json.loads(first.read_text(encoding="utf-8"))
                if missing == "ed":
                    payload.pop("ed_oracle")
                else:
                    payload["resource_provenance"] = {
                        "placement": "external-direct",
                    }
                write_json(first, payload)

                with (
                    patch(
                        "challenge233.sdp.run_kyfan."
                        "verify_kyfan_certificate",
                        return_value={
                            "status": "verified",
                            "schema_version": 2,
                            "a_cert": "-37/10",
                            "b_var": "-19/10",
                            "delta_cert": "1/10",
                            "rho_mom": "1/10",
                            "rho_op": "1/20",
                            "residual_route": "physical-operator",
                            "certificate_status": "certified",
                        },
                    ),
                    patch(
                        "challenge233.sdp.run_kyfan."
                        "_validate_ed_oracle_binding",
                        return_value={
                            "size": 4,
                            "detuning": "1/2",
                            "e0": "-2.0",
                            "e1": "-1.5",
                            "gap": "0.5",
                            "maximum_residual": "4e-13",
                            "manifest_sha256": "a" * 64,
                            "data_sha256": "b" * 64,
                        },
                    ),
                    self.assertRaisesRegex(
                        ValueError,
                        "ED oracle|accounting",
                    ),
                ):
                    certify_run(run / "run_spec.json")

    def test_certify_run_summarizes_checked_anchor_without_thermodynamics(
        self,
    ):
        run = Path(self.temporary.name) / "complete-anchor"
        plan_v2_run(
            run,
            sizes=(4,),
            detunings=(Fraction(1, 2),),
            levels=("global-d2", "global-d3", "global-d4"),
            localizer_mode="sound",
            exactness_tolerance=Fraction(1, 10**8),
        )
        self.write_anchor_final_manifests(run)

        checked_by_cell = {
            f"cell-{index:04d}": {
                "status": "verified",
                "schema_version": 2,
                "a_cert": a_cert,
                "b_var": "-19/10",
                "delta_cert": delta,
                "rho_mom": "1/10",
                "rho_op": "1/20",
                "residual_route": "physical-operator",
                "certificate_status": "certified",
            }
            for index, (a_cert, delta) in enumerate(
                zip(
                    ("-37/10", "-18/5", "-7/2"),
                    ("1/10", "1/5", "3/10"),
                ),
                start=1,
            )
        }

        def fake_check(cell_directory):
            return checked_by_cell[Path(cell_directory).name]

        with (
            patch(
                "challenge233.sdp.run_kyfan."
                "verify_kyfan_certificate",
                side_effect=fake_check,
            ),
            patch(
                "challenge233.sdp.run_kyfan."
                "_validate_ed_oracle_binding",
                return_value={
                    "size": 4,
                    "detuning": "1/2",
                    "e0": "-2.0",
                    "e1": "-1.5",
                    "gap": "0.5",
                    "maximum_residual": "4e-13",
                    "manifest_sha256": "a" * 64,
                    "data_sha256": "b" * 64,
                },
            ),
        ):
            summary = certify_run(run / "run_spec.json")

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(
            summary["hierarchy_monotonicity"],
            "global-d2 <= global-d3 <= global-d4",
        )
        self.assertEqual(
            summary["thermodynamic_limit_conclusion"],
            "none; finite-N positivity is not a thermodynamic certificate",
        )
        self.assertTrue(
            (run / "certification-summary.json").is_file()
        )


if __name__ == "__main__":
    unittest.main()
