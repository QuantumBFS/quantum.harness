from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.dual_certificate import (  # noqa: E402
    build_dual_certificate,
)
from challenge233.sdp.kyfan import (  # noqa: E402
    build_global_kyfan_problem,
)
from challenge233.sdp.kyfan_artifact import (  # noqa: E402
    export_kyfan_problem,
)
from challenge233.sdp.kyfan_presolve import (  # noqa: E402
    build_kyfan_solver_reduction,
    solver_reduction_payload,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
    build_kyfan_instance,
)
from challenge233.sdp.kyfan_v2_artifact import (  # noqa: E402
    export_kyfan_instance,
    export_shared_structure,
    export_solver_reduction,
    logical_structure_sha256,
)
from challenge233.sdp.variational_upper import (  # noqa: E402
    TrialVector,
    write_trial_vector,
)
from challenge233.sdp.verify_kyfan_certificate import (  # noqa: E402
    verify_kyfan_certificate,
)


def json_bytes(value):
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_bytes(json_bytes(value))


def write_solver_fixture(problem_directory, solver_directory):
    problem_directory = Path(problem_directory)
    solver_directory = Path(solver_directory)
    solver_directory.mkdir(parents=True)
    problem = json.loads(
        (problem_directory / "problem.json").read_text(encoding="utf-8")
    )
    problem_manifest = json.loads(
        (problem_directory / "manifest.json").read_text(encoding="utf-8")
    )
    duals = []
    files = []
    for block_index, block in enumerate(problem["psd_blocks"]):
        dimension = block["dimension"]
        payload = bytearray(8 * dimension * dimension)
        if block_index == 0:
            struct.pack_into("<d", payload, 0, 1.0)
        path = solver_directory / f"dual-{block['identifier']}.f64le"
        path.write_bytes(payload)
        metadata = {
            "block": block["identifier"],
            "dimension": dimension,
            "file": path.name,
            "layout": "row-major",
            "scalar_format": "float64-little-endian",
            "byte_count": len(payload),
            "sha256": sha256(path),
            "numerical_asymmetry_max": "0",
        }
        duals.append(metadata)
        files.append(
            {
                "file": path.name,
                "byte_count": len(payload),
                "sha256": metadata["sha256"],
            }
        )
    result = {
        "schema_version": 1,
        "purpose": "numerical-ky-fan-dual",
        "success": True,
        "problem_sha256": problem_manifest["problem_sha256"],
        "problem_manifest_sha256": sha256(
            problem_directory / "manifest.json"
        ),
        "termination_status": "OPTIMAL",
        "primal_status": "FEASIBLE_POINT",
        "dual_status": "FEASIBLE_POINT",
        "raw_status": "Solved",
        "objective": -1.0,
        "dual_objective": -1.0,
        "dual_cone": "triangle-psd",
        "dual_identity_sign_calibrated": True,
        "offdiagonal_scaling_calibrated": True,
        "equality_multipliers": [
            {"identifier": row["identifier"], "value": "0"}
            for row in problem["equalities"]
        ],
        "psd_duals": duals,
        "versions": {"fixture": "1"},
        "settings": {"fixture": True},
    }
    result_path = solver_directory / "solver-result.json"
    write_json(result_path, result)
    files.insert(
        0,
        {
            "file": result_path.name,
            "byte_count": result_path.stat().st_size,
            "sha256": sha256(result_path),
        },
    )
    manifest = {
        "schema_version": 1,
        "purpose": "numerical-ky-fan-solve-manifest",
        "success": True,
        "problem_sha256": problem_manifest["problem_sha256"],
        "problem_manifest_sha256": sha256(
            problem_directory / "manifest.json"
        ),
        "solver_result_file": result_path.name,
        "solver_result_sha256": sha256(result_path),
        "files": files,
        "selection": {"mode": "fixture"},
    }
    write_json(solver_directory / "solver-manifest.json", manifest)


def write_v2_solver_fixture(
    problem_directory,
    solver_directory,
    reduction,
):
    problem_directory = Path(problem_directory)
    solver_directory = Path(solver_directory)
    solver_directory.mkdir(parents=True)
    problem_manifest_path = problem_directory / "manifest.json"
    problem_manifest = json.loads(
        problem_manifest_path.read_text(encoding="utf-8")
    )
    reduction_payload = solver_reduction_payload(reduction)
    spatial = {
        item["identifier"]: item
        for item in reduction_payload["spatial"]
    }
    duals = []
    files = []
    for index, block in enumerate(reduction.psd_blocks, start=1):
        dimension = block.dimension
        payload = bytearray(8 * dimension * dimension)
        if index == 1:
            struct.pack_into("<d", payload, 0, 1.0)
        payload = bytes(payload)
        path = (
            solver_directory
            / f"dual-reduced-{index:04d}.f64le"
        )
        path.write_bytes(payload)
        spatial_payload = spatial[block.spatial_block]
        transform_sha256 = hashlib.sha256(
            json.dumps(
                spatial_payload["transform"],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        metadata = {
            "block": block.identifier,
            "dimension": dimension,
            "file": path.name,
            "layout": "row-major",
            "scalar_format": "float64-little-endian",
            "byte_count": len(payload),
            "sha256": sha256(path),
            "numerical_asymmetry_max": "0",
            "source_effect": block.source_block,
            "spatial_block": block.spatial_block,
            "irrep_label": spatial_payload["irrep_label"],
            "irrep_degree": spatial_payload["irrep_degree"],
            "transform_sha256": transform_sha256,
            "transform_hash_encoding": (
                "sha256-json3-compact-source-order"
            ),
        }
        duals.append(metadata)
        files.append(
            {
                "file": path.name,
                "byte_count": len(payload),
                "sha256": metadata["sha256"],
            }
        )
    result = {
        "schema_version": 2,
        "purpose": "numerical-ky-fan-reduced-dual-v2",
        "success": True,
        "problem_manifest_sha256": sha256(problem_manifest_path),
        "structure_sha256": problem_manifest["structure_sha256"],
        "instance_sha256": problem_manifest["instance_sha256"],
        "reduction_sha256": problem_manifest["reduction_sha256"],
        "solver_view": reduction.selected_view,
        "termination_status": "OPTIMAL",
        "primal_status": "FEASIBLE_POINT",
        "dual_status": "FEASIBLE_POINT",
        "raw_status": "Solved",
        "objective": 0.0,
        "dual_objective": 0.0,
        "dual_cone": "triangle-psd",
        "dual_identity_sign_calibrated": True,
        "offdiagonal_scaling_calibrated": True,
        "equality_multipliers": [],
        "psd_duals": duals,
        "versions": {"fixture": "2"},
        "settings": {"fixture": True},
    }
    result_path = solver_directory / "solver-result.json"
    write_json(result_path, result)
    files.insert(
        0,
        {
            "file": result_path.name,
            "byte_count": result_path.stat().st_size,
            "sha256": sha256(result_path),
        },
    )
    manifest = {
        "schema_version": 2,
        "purpose": "numerical-ky-fan-solve-manifest",
        "success": True,
        "problem_manifest_sha256": sha256(problem_manifest_path),
        "structure_sha256": problem_manifest["structure_sha256"],
        "instance_sha256": problem_manifest["instance_sha256"],
        "reduction_sha256": problem_manifest["reduction_sha256"],
        "solver_view": reduction.selected_view,
        "solver_result_file": result_path.name,
        "solver_result_sha256": sha256(result_path),
        "files": files,
        "selection": {"mode": "fixture-v2"},
    }
    write_json(solver_directory / "solver-manifest.json", manifest)


def write_trial_fixture(trial_directory):
    trusted_path = ROOT / "external/1d-basis/pxpbasis.py"
    trial = TrialVector(
        size=4,
        detuning=Fraction(1, 2),
        bits=0,
        states=(0,),
        coefficients=(1,),
        basis_dimension=7,
        basis_state_order_sha256=(
            "3e34272e6c3a6c8f1c64a9a4193c601c"
            "366ff34bafc8baaf3bec331f66e0887d"
        ),
        guidance_energy=0.0,
        residual_norm=0.0,
        arpack_tolerance=1e-12,
        random_seed=233,
        quspin_version="fixture",
        numpy_version="fixture",
        scipy_version="fixture",
        trusted_basis_path="external/1d-basis/pxpbasis.py",
        trusted_basis_sha256=hashlib.sha256(
            trusted_path.read_bytes()
        ).hexdigest(),
    )
    write_trial_vector(trial, trial_directory)


def update_certificate_hash(certificate_directory):
    certificate_directory = Path(certificate_directory)
    manifest_path = certificate_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    certificate_path = certificate_directory / "certificate.json"
    manifest["certificate_sha256"] = sha256(certificate_path)
    write_json(manifest_path, manifest)


class KyFanCertificateVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.base = Path(cls.temporary.name) / "cell"
        problem = cls.base / "problem"
        solver = cls.base / "solver"
        trial = cls.base / "trial"
        certificate = cls.base / "certificate"
        export_kyfan_problem(
            build_global_kyfan_problem(4, Fraction(1, 2), 2),
            problem,
        )
        write_solver_fixture(problem, solver)
        write_trial_fixture(trial)
        build_dual_certificate(
            problem,
            solver,
            trial,
            certificate,
            factor_bits=8,
            multiplier_bits=8,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def copy_fixture(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        copied = Path(temporary.name) / "cell"
        shutil.copytree(self.base, copied)
        return copied

    def test_valid_artifact_is_independently_recomputed(self):
        summary = verify_kyfan_certificate(self.base)
        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["certificate_status"], "not_certified")
        self.assertEqual(summary["b_var"], "0/1")
        self.assertLessEqual(
            Fraction(summary["delta_cert"]),
            Fraction(0),
        )

    def test_checker_does_not_import_candidate_certificate_modules(self):
        source = (
            ROOT
            / "src/challenge233/sdp/verify_kyfan_certificate.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "challenge233.sdp.algebra",
            "challenge233.sdp.kyfan",
            "challenge233.sdp.dual_certificate",
            "challenge233.sdp.dual_lift",
            "challenge233.sdp.variational_upper",
        ):
            self.assertNotIn(forbidden, source)

    def test_module_cli_prints_recomputed_summary_without_warning(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "challenge233.sdp.verify_kyfan_certificate",
                str(self.base),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "verified")
        self.assertEqual(result.stderr, "")

    def test_rejects_changed_factor_numerator_even_with_updated_hashes(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        factor = next(
            item
            for item in certificate["factors"]
            if item["columns"] > 0
        )
        factor_path = certificate_directory / factor["file"]
        payload = bytearray(factor_path.read_bytes())
        value = struct.unpack_from("<q", payload, 0)[0]
        struct.pack_into("<q", payload, 0, value + 1)
        factor_path.write_bytes(payload)
        factor["sha256"] = sha256(factor_path)
        factor["overflow_bound"] = str(
            factor["columns"] * (value + 1) ** 2
        )
        write_json(certificate_path, certificate)
        manifest_path = certificate_directory / "manifest.json"
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        for item in manifest["files"]:
            if item["file"] == factor["file"]:
                item["sha256"] = factor["sha256"]
        write_json(manifest_path, manifest)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "residual"):
            verify_kyfan_certificate(cell)

    def test_rejects_changed_factor_layout(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        certificate["factors"][0]["layout"] = "column-major"
        write_json(certificate_path, certificate)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "factor layout"):
            verify_kyfan_certificate(cell)

    def test_rejects_changed_equality_multiplier(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        target = next(
            item
            for item in certificate["equality_multipliers"]
            if item["identifier"] != "trace-gamma-equals-2"
        )
        target["value"] = "1/2"
        write_json(certificate_path, certificate)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "residual"):
            verify_kyfan_certificate(cell)

    def test_rejects_changed_affine_problem_coefficient(self):
        cell = self.copy_fixture()
        problem_path = cell / "problem/problem.json"
        problem = json.loads(problem_path.read_text(encoding="utf-8"))
        variable, coefficient = problem["objective"]["terms"][0]
        problem["objective"]["terms"][0] = [variable, "99/1"]
        write_json(problem_path, problem)
        manifest_path = cell / "problem/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["problem_sha256"] = sha256(problem_path)
        write_json(manifest_path, manifest)

        with self.assertRaises(ValueError):
            verify_kyfan_certificate(cell)

    def test_rejects_changed_residual_even_with_updated_hashes(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        residual_path = certificate_directory / "dual-residuals.json"
        residuals = json.loads(
            residual_path.read_text(encoding="utf-8")
        )
        residuals["residuals"][0]["value"] = "123/1"
        write_json(residual_path, residuals)
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        certificate["dual_residuals_sha256"] = sha256(residual_path)
        write_json(certificate_path, certificate)
        manifest_path = certificate_directory / "manifest.json"
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        manifest["dual_residuals_sha256"] = sha256(residual_path)
        write_json(manifest_path, manifest)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "residual"):
            verify_kyfan_certificate(cell)

    def test_rejects_changed_trial_state(self):
        cell = self.copy_fixture()
        state_path = cell / "trial/trial-states.u64le"
        state_path.write_bytes(struct.pack("<Q", 1))
        metadata_path = cell / "trial/trial-vector.json"
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        metadata["state_file_sha256"] = sha256(state_path)
        metadata["rayleigh_numerator"] = "-1/2"
        metadata["rayleigh_denominator"] = "1"
        metadata["b_var"] = "-1/2"
        write_json(metadata_path, metadata)
        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        certificate["trial_vector_sha256"] = sha256(metadata_path)
        write_json(certificate_path, certificate)
        manifest_path = certificate_directory / "manifest.json"
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        manifest["trial_vector_sha256"] = sha256(metadata_path)
        write_json(manifest_path, manifest)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "B_var"):
            verify_kyfan_certificate(cell)

    def test_rejects_solver_manifest_hash_mismatch(self):
        cell = self.copy_fixture()
        manifest_path = cell / "solver/solver-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["solver_result_sha256"] = "0" * 64
        write_json(manifest_path, manifest)

        with self.assertRaisesRegex(ValueError, "solver-result SHA-256"):
            verify_kyfan_certificate(cell)

    def test_rejects_claimed_status_or_gap(self):
        for field, value in (
            ("status", "certified"),
            ("delta_cert", "1/1"),
        ):
            with self.subTest(field=field):
                cell = self.copy_fixture()
                certificate_directory = cell / "certificate"
                certificate_path = (
                    certificate_directory / "certificate.json"
                )
                certificate = json.loads(
                    certificate_path.read_text(encoding="utf-8")
                )
                certificate[field] = value
                write_json(certificate_path, certificate)
                update_certificate_hash(certificate_directory)

                with self.assertRaisesRegex(ValueError, field):
                    verify_kyfan_certificate(cell)


class KyFanV2CertificateVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.run_directory = Path(cls.temporary.name) / "run"
        cls.cell = cls.run_directory / "cells/cell-0001"
        structure = build_global_kyfan_structure(4, 2, "sound")
        structure_binding = export_shared_structure(
            structure,
            cls.run_directory / "shared",
        )
        reduction = build_kyfan_solver_reduction(
            structure,
            logical_structure_sha256(structure),
        )
        reduction_binding = export_solver_reduction(
            reduction,
            structure_binding,
        )
        trial = cls.cell / "trial"
        write_trial_fixture(trial)
        instance = build_kyfan_instance(
            structure,
            Fraction(1, 2),
            trial_manifest=sha256(trial / "trial-vector.json"),
        )
        problem = cls.cell / "problem"
        export_kyfan_instance(
            instance,
            structure_binding,
            problem,
            reduction_binding,
        )
        solver = cls.cell / "solver"
        write_v2_solver_fixture(problem, solver, reduction)
        build_dual_certificate(
            problem,
            solver,
            trial,
            cls.cell / "certificate",
            factor_bits=8,
            multiplier_bits=8,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def copy_fixture(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        copied_run = Path(temporary.name) / "run"
        shutil.copytree(self.run_directory, copied_run)
        return copied_run / "cells/cell-0001"

    def rebind_v2_trial_mutation(self, cell):
        state_path = cell / "trial/trial-states.u64le"
        state_path.write_bytes(struct.pack("<Q", 1))
        trial_path = cell / "trial/trial-vector.json"
        trial = json.loads(trial_path.read_text(encoding="utf-8"))
        trial["state_file_sha256"] = sha256(state_path)
        trial["rayleigh_numerator"] = "-1/2"
        trial["rayleigh_denominator"] = "1"
        trial["b_var"] = "-1/2"
        write_json(trial_path, trial)
        trial_sha256 = sha256(trial_path)

        instance_path = cell / "problem/instance.json"
        instance = json.loads(
            instance_path.read_text(encoding="utf-8")
        )
        instance["trial_manifest_sha256"] = trial_sha256
        write_json(instance_path, instance)
        instance_sha256 = sha256(instance_path)

        problem_manifest_path = cell / "problem/manifest.json"
        problem_manifest = json.loads(
            problem_manifest_path.read_text(encoding="utf-8")
        )
        problem_manifest["instance_sha256"] = instance_sha256
        write_json(problem_manifest_path, problem_manifest)
        problem_manifest_sha256 = sha256(problem_manifest_path)

        solver_result_path = cell / "solver/solver-result.json"
        solver_result = json.loads(
            solver_result_path.read_text(encoding="utf-8")
        )
        solver_result["problem_manifest_sha256"] = (
            problem_manifest_sha256
        )
        solver_result["instance_sha256"] = instance_sha256
        write_json(solver_result_path, solver_result)
        solver_result_sha256 = sha256(solver_result_path)

        solver_manifest_path = cell / "solver/solver-manifest.json"
        solver_manifest = json.loads(
            solver_manifest_path.read_text(encoding="utf-8")
        )
        solver_manifest["problem_manifest_sha256"] = (
            problem_manifest_sha256
        )
        solver_manifest["instance_sha256"] = instance_sha256
        solver_manifest["solver_result_sha256"] = solver_result_sha256
        result_metadata = next(
            item
            for item in solver_manifest["files"]
            if item["file"] == "solver-result.json"
        )
        result_metadata["byte_count"] = solver_result_path.stat().st_size
        result_metadata["sha256"] = solver_result_sha256
        write_json(solver_manifest_path, solver_manifest)
        solver_manifest_sha256 = sha256(solver_manifest_path)

        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        certificate.update(
            {
                "problem_manifest_sha256": problem_manifest_sha256,
                "instance_sha256": instance_sha256,
                "solver_result_sha256": solver_result_sha256,
                "solver_manifest_sha256": solver_manifest_sha256,
                "trial_vector_sha256": trial_sha256,
            }
        )
        write_json(certificate_path, certificate)

        manifest_path = certificate_directory / "manifest.json"
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        manifest.update(
            {
                "problem_manifest_sha256": problem_manifest_sha256,
                "instance_sha256": instance_sha256,
                "solver_result_sha256": solver_result_sha256,
                "solver_manifest_sha256": solver_manifest_sha256,
                "trial_vector_sha256": trial_sha256,
                "certificate_sha256": sha256(certificate_path),
            }
        )
        write_json(manifest_path, manifest)

    def test_valid_v2_artifact_is_lifted_and_independently_recomputed(self):
        summary = verify_kyfan_certificate(self.cell)

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["schema_version"], 2)
        self.assertEqual(summary["certificate_status"], "not_certified")
        self.assertEqual(summary["factor_count"], 10)
        self.assertIn(
            summary["residual_route"],
            {"pseudo-moment", "physical-operator"},
        )

    def test_reduced_accuracy_seed_is_accepted_only_after_exact_check(self):
        cell = self.copy_fixture()
        shutil.rmtree(cell / "certificate")
        result_path = cell / "solver/solver-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result.update(
            {
                "termination_status": "ALMOST_OPTIMAL",
                "primal_status": "NEARLY_FEASIBLE_POINT",
                "dual_status": "NEARLY_FEASIBLE_POINT",
                "raw_status": "ALMOST_SOLVED",
                "numerical_diagnostics": {
                    "iterations": 10,
                    "cost_primal": "-1.00000001",
                    "cost_dual": "-1.00000002",
                    "res_primal": "1e-10",
                    "res_dual": "1e-11",
                    "gap_abs": "1e-8",
                    "gap_rel": "1e-8",
                    "ktratio": "1e-10",
                    "has_values": True,
                    "has_duals": True,
                },
            }
        )
        write_json(result_path, result)
        manifest_path = cell / "solver/solver-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["solver_result_sha256"] = sha256(result_path)
        result_metadata = next(
            item
            for item in manifest["files"]
            if item["file"] == "solver-result.json"
        )
        result_metadata["byte_count"] = result_path.stat().st_size
        result_metadata["sha256"] = sha256(result_path)
        write_json(manifest_path, manifest)

        build_dual_certificate(
            cell / "problem",
            cell / "solver",
            cell / "trial",
            cell / "certificate",
            factor_bits=8,
            multiplier_bits=8,
        )
        summary = verify_kyfan_certificate(cell)

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["schema_version"], 2)

    def test_v2_rejects_changed_factor_numerator(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        factor = next(
            item
            for item in certificate["factor_orbits"]
            if item["columns"] > 0
        )
        factor_path = certificate_directory / factor["file"]
        payload = bytearray(factor_path.read_bytes())
        value = struct.unpack_from("<q", payload, 0)[0]
        struct.pack_into("<q", payload, 0, value + 1)
        factor_path.write_bytes(payload)
        values = tuple(
            item[0] for item in struct.iter_unpack("<q", payload)
        )
        factor["sha256"] = sha256(factor_path)
        factor["overflow_bound"] = str(
            factor["columns"] * max(map(abs, values)) ** 2
        )
        write_json(certificate_path, certificate)
        manifest_path = certificate_directory / "manifest.json"
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        target = next(
            item for item in manifest["files"]
            if item["file"] == factor["file"]
        )
        target["sha256"] = factor["sha256"]
        write_json(manifest_path, manifest)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "residual"):
            verify_kyfan_certificate(cell)

    def test_v2_rejects_incomplete_group_average_or_wrong_weight(self):
        for mutation in ("delete-image", "change-weight"):
            with self.subTest(mutation=mutation):
                cell = self.copy_fixture()
                certificate_directory = cell / "certificate"
                certificate_path = (
                    certificate_directory / "certificate.json"
                )
                certificate = json.loads(
                    certificate_path.read_text(encoding="utf-8")
                )
                generic = next(
                    item
                    for item in certificate["factor_orbits"]
                    if item["irrep_degree"] == 2
                )
                if mutation == "delete-image":
                    generic["group_images"].pop()
                else:
                    generic["weight"] = "1/7"
                write_json(certificate_path, certificate)
                update_certificate_hash(certificate_directory)

                with self.assertRaisesRegex(
                    ValueError,
                    "group image|weight",
                ):
                    verify_kyfan_certificate(cell)

    def test_v2_rejects_changed_phase_or_transform_hash(self):
        for mutation in ("phase", "transform"):
            with self.subTest(mutation=mutation):
                cell = self.copy_fixture()
                certificate_directory = cell / "certificate"
                certificate_path = (
                    certificate_directory / "certificate.json"
                )
                certificate = json.loads(
                    certificate_path.read_text(encoding="utf-8")
                )
                factor = certificate["factor_orbits"][0]
                if mutation == "phase":
                    factor["phase_exponents"][0] ^= 1
                else:
                    factor["transform_sha256"] = "0" * 64
                write_json(certificate_path, certificate)
                update_certificate_hash(certificate_directory)

                with self.assertRaisesRegex(
                    ValueError,
                    "phase|transform",
                ):
                    verify_kyfan_certificate(cell)

    def test_v2_rejects_changed_reconstructed_multiplier(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        certificate["equality_multipliers"][0]["value"] = "1/3"
        write_json(certificate_path, certificate)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "equality multiplier"):
            verify_kyfan_certificate(cell)

    def test_v2_rejects_changed_correction_or_route(self):
        for field, value in (
            ("rho_mom", "123/1"),
            ("rho_op", "123/1"),
            ("residual_route", "physical-operator"),
        ):
            with self.subTest(field=field):
                cell = self.copy_fixture()
                certificate_directory = cell / "certificate"
                certificate_path = (
                    certificate_directory / "certificate.json"
                )
                certificate = json.loads(
                    certificate_path.read_text(encoding="utf-8")
                )
                if (
                    field == "residual_route"
                    and certificate[field] == value
                ):
                    value = "pseudo-moment"
                certificate[field] = value
                write_json(certificate_path, certificate)
                update_certificate_hash(certificate_directory)

                with self.assertRaisesRegex(
                    ValueError,
                    "rho_mom|rho_op|residual route",
                ):
                    verify_kyfan_certificate(cell)

    def test_v2_rejects_scalar_residual_coordinate(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        residual_path = certificate_directory / "dual-residuals.json"
        residual = json.loads(
            residual_path.read_text(encoding="utf-8")
        )
        residual["r0"] = "0/1"
        write_json(residual_path, residual)
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        certificate["dual_residuals_sha256"] = sha256(residual_path)
        write_json(certificate_path, certificate)
        manifest_path = certificate_directory / "manifest.json"
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        manifest["dual_residuals_sha256"] = sha256(residual_path)
        write_json(manifest_path, manifest)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "invalid coordinate"):
            verify_kyfan_certificate(cell)

    def test_v2_rejects_changed_trial_after_all_outer_hashes_refresh(self):
        cell = self.copy_fixture()
        self.rebind_v2_trial_mutation(cell)

        with self.assertRaisesRegex(ValueError, "B_var"):
            verify_kyfan_certificate(cell)

    def test_v2_rejects_claimed_gap(self):
        cell = self.copy_fixture()
        certificate_directory = cell / "certificate"
        certificate_path = certificate_directory / "certificate.json"
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        certificate["delta_cert"] = "1/1"
        write_json(certificate_path, certificate)
        update_certificate_hash(certificate_directory)

        with self.assertRaisesRegex(ValueError, "delta_cert"):
            verify_kyfan_certificate(cell)


if __name__ == "__main__":
    unittest.main()
