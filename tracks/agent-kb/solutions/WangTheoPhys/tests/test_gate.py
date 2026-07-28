from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SOLUTION_ROOT.parents[3]
STARTER_ROOT = REPOSITORY_ROOT.parent / "Agents" / "Tensor_Network" / "tn-agent-starter"
sys.path.insert(0, str(SOLUTION_ROOT))

import gate


class GateContractTests(unittest.TestCase):
    def fixture(self, relative: str) -> Path:
        return SOLUTION_ROOT / "fixtures" / relative

    def load(self, relative: str) -> dict[str, object]:
        value = gate.load_json_document(self.fixture(relative))
        self.assertIsInstance(value, dict)
        return value

    def load_regenerator(self) -> types.ModuleType:
        path = SOLUTION_ROOT / "fixtures" / "regenerate.py"
        spec = importlib.util.spec_from_file_location(
            "wangtheophys_fixture_regenerator",
            path,
        )
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertIsNotNone(spec.loader)
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def assert_reason(self, expected: str, callback: object) -> None:
        with self.assertRaises(gate.GateError) as caught:
            callback()  # type: ignore[operator]
        self.assertEqual(caught.exception.reason_code, expected)

    def redigest_evidence(self, evidence: dict[str, object]) -> None:
        evidence["result_digest"] = gate.canonical_digest(
            {key: value for key, value in evidence.items() if key != "result_digest"}
        )

    def replace_backend_bundle(
        self,
        directory: Path,
        evidence: dict[str, object],
        bundle: bytes,
    ) -> None:
        backend_path = directory / "backend-result.json"
        backend_path.write_bytes(bundle)
        digest = "sha256:" + hashlib.sha256(bundle).hexdigest()
        artifacts = evidence["artifacts"]
        self.assertIsInstance(artifacts, list)
        backend_artifact = next(
            item
            for item in artifacts
            if isinstance(item, dict) and item.get("role") == "backend_result"
        )
        backend_artifact["digest"] = digest
        backend_artifact["size_bytes"] = len(bundle)
        observables = evidence["observables"]
        self.assertIsInstance(observables, list)
        for item in observables:
            self.assertIsInstance(item, dict)
            item["evidence_digest"] = digest
        provenance = evidence["provenance"]
        self.assertIsInstance(provenance, dict)
        provenance["backend_result_digest"] = digest
        self.redigest_evidence(evidence)

    def write_backend_bundle(
        self,
        directory: Path,
        evidence: dict[str, object],
        bundle: dict[str, object],
    ) -> None:
        bundle["result_digest"] = gate.canonical_digest(
            {key: value for key, value in bundle.items() if key != "result_digest"}
        )
        raw = (
            json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode()
        self.replace_backend_bundle(directory, evidence, raw)

    def replace_artifact(
        self,
        directory: Path,
        evidence: dict[str, object],
        *,
        role: str,
        raw: bytes,
    ) -> str:
        artifacts = evidence["artifacts"]
        self.assertIsInstance(artifacts, list)
        artifact = next(
            item
            for item in artifacts
            if isinstance(item, dict) and item.get("role") == role
        )
        relative_path = artifact["relative_path"]
        self.assertIsInstance(relative_path, str)
        (directory / relative_path).write_bytes(raw)
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        artifact["digest"] = digest
        artifact["size_bytes"] = len(raw)
        if role == "validator_evidence":
            validator_results = evidence["validator_results"]
            self.assertIsInstance(validator_results, list)
            for result in validator_results:
                self.assertIsInstance(result, dict)
                result["evidence_digest"] = digest
        self.redigest_evidence(evidence)
        return digest

    def coherently_rebuild_primary_evidence(
        self,
        *,
        directory: Path,
        experiment: dict[str, object],
        evidence: dict[str, object],
        raw_result: dict[str, object],
    ) -> None:
        raw = (json.dumps(raw_result, indent=2) + "\n").encode()
        self.replace_artifact(
            directory,
            evidence,
            role="backend_raw_result",
            raw=raw,
        )
        summary = gate.validate_experiment(experiment)
        binding = experiment["backend_binding"]
        self.assertIsInstance(binding, dict)
        plan_id = gate._expected_plan_id(
            experiment,
            str(summary["experiment_digest"]),
        )
        request = gate._expected_request(
            experiment,
            str(summary["experiment_digest"]),
            plan_id,
        )
        manifest = evidence["artifacts"]
        self.assertIsInstance(manifest, list)
        by_role = {
            str(item["role"]): item for item in manifest if isinstance(item, dict)
        }
        parsed_raw = gate._validate_raw_result(
            raw,
            request=request,
            request_digest=gate.canonical_digest(request),
            binding=binding,
            route=gate.ROUTES[str(binding["capability_id"])],
        )
        execution = evidence["execution"]
        self.assertIsInstance(execution, dict)
        reconstructed = gate._reconstruct_backend_bundle(
            request_digest=gate.canonical_digest(request),
            binding=binding,
            raw=parsed_raw,
            execution=execution,
            raw_artifact=by_role["backend_raw_result"],
        )
        self.write_backend_bundle(directory, evidence, reconstructed)

        repeat_raw_bytes = (directory / "backend-repeat-raw-result.json").read_bytes()
        repeat_raw = gate._validate_raw_result(
            repeat_raw_bytes,
            request=request,
            request_digest=gate.canonical_digest(request),
            binding=binding,
            route=gate.ROUTES[str(binding["capability_id"])],
        )
        reference = gate._validate_energy_reference(
            (directory / "energy-reference.json").read_bytes(),
            experiment=experiment,
        )
        derived = gate._derived_validator_results(
            parsed_raw,
            repeat_raw=repeat_raw,
            reference=reference,
        )
        repeat_bundle = json.loads(
            (directory / "backend-repeat-result.json").read_text()
        )
        validator_content = {
            "schema_version": "wangtheophys.tn-validator-evidence.v1",
            "request_digest": gate.canonical_digest(request),
            "backend_result_digest": reconstructed["result_digest"],
            "repeat_backend_result_digest": repeat_bundle["result_digest"],
            "reference_artifact_digest": by_role["energy_reference"]["digest"],
            "results": derived,
        }
        validator = {
            **validator_content,
            "result_digest": gate.canonical_digest(validator_content),
        }
        validator_raw = (json.dumps(validator, indent=2) + "\n").encode()
        self.replace_artifact(
            directory,
            evidence,
            role="validator_evidence",
            raw=validator_raw,
        )
        metrics = {str(item["id"]): item["value"] for item in derived}
        validator_results = evidence["validator_results"]
        self.assertIsInstance(validator_results, list)
        for result in validator_results:
            self.assertIsInstance(result, dict)
            result["metric_value"] = metrics[str(result["id"])]
        self.redigest_evidence(evidence)

    def coherently_rebuild_repeat_evidence(
        self,
        *,
        directory: Path,
        experiment: dict[str, object],
        evidence: dict[str, object],
        repeat_raw_bytes: bytes,
    ) -> None:
        self.replace_artifact(
            directory,
            evidence,
            role="backend_repeat_raw_result",
            raw=repeat_raw_bytes,
        )
        summary = gate.validate_experiment(experiment)
        binding = experiment["backend_binding"]
        self.assertIsInstance(binding, dict)
        plan_id = gate._expected_plan_id(
            experiment,
            str(summary["experiment_digest"]),
        )
        request = gate._expected_request(
            experiment,
            str(summary["experiment_digest"]),
            plan_id,
        )
        request_digest = gate.canonical_digest(request)
        manifest = evidence["artifacts"]
        self.assertIsInstance(manifest, list)
        by_role = {
            str(item["role"]): item for item in manifest if isinstance(item, dict)
        }
        parsed_repeat = gate._validate_raw_result(
            repeat_raw_bytes,
            request=request,
            request_digest=request_digest,
            binding=binding,
            route=gate.ROUTES[str(binding["capability_id"])],
        )
        repeat_execution = evidence["repeat_execution"]
        self.assertIsInstance(repeat_execution, dict)
        repeat_bundle = gate._reconstruct_backend_bundle(
            request_digest=request_digest,
            binding=binding,
            raw=parsed_repeat,
            execution=repeat_execution,
            raw_artifact=by_role["backend_repeat_raw_result"],
        )
        repeat_bundle_raw = (
            json.dumps(repeat_bundle, ensure_ascii=False, indent=2, allow_nan=False)
            + "\n"
        ).encode()
        repeat_bundle_digest = self.replace_artifact(
            directory,
            evidence,
            role="backend_repeat_result",
            raw=repeat_bundle_raw,
        )
        provenance = evidence["provenance"]
        self.assertIsInstance(provenance, dict)
        provenance["repeat_backend_result_digest"] = repeat_bundle_digest

        primary_raw_bytes = (directory / "backend-raw-result.json").read_bytes()
        primary_raw = gate._validate_raw_result(
            primary_raw_bytes,
            request=request,
            request_digest=request_digest,
            binding=binding,
            route=gate.ROUTES[str(binding["capability_id"])],
        )
        primary_bundle = json.loads((directory / "backend-result.json").read_text())
        reference = gate._validate_energy_reference(
            (directory / "energy-reference.json").read_bytes(),
            experiment=experiment,
        )
        derived = gate._derived_validator_results(
            primary_raw,
            repeat_raw=parsed_repeat,
            reference=reference,
        )
        validator_content = {
            "schema_version": "wangtheophys.tn-validator-evidence.v1",
            "request_digest": request_digest,
            "backend_result_digest": primary_bundle["result_digest"],
            "repeat_backend_result_digest": repeat_bundle["result_digest"],
            "reference_artifact_digest": by_role["energy_reference"]["digest"],
            "results": derived,
        }
        validator = {
            **validator_content,
            "result_digest": gate.canonical_digest(validator_content),
        }
        validator_raw = (
            json.dumps(validator, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode()
        self.replace_artifact(
            directory,
            evidence,
            role="validator_evidence",
            raw=validator_raw,
        )
        metrics = {str(item["id"]): item["value"] for item in derived}
        validator_results = evidence["validator_results"]
        self.assertIsInstance(validator_results, list)
        for result in validator_results:
            self.assertIsInstance(result, dict)
            result["metric_value"] = metrics[str(result["id"])]
        self.redigest_evidence(evidence)

    def test_valid_finite_and_infinite_experiments(self) -> None:
        for relative in (
            "valid-finite/experiment.json",
            "valid-infinite/experiment.json",
        ):
            with self.subTest(relative=relative):
                experiment = self.load(relative)
                summary = gate.validate_experiment(experiment)
                self.assertEqual(summary["reason_code"], "OK")

    def test_routes_close_over_gate_dependencies_and_expected_requests(self) -> None:
        for directory in ("valid-finite", "valid-infinite"):
            with self.subTest(directory=directory):
                experiment = self.load(f"{directory}/experiment.json")
                summary = gate.validate_experiment(experiment)
                plan_id = gate._expected_plan_id(
                    experiment,
                    str(summary["experiment_digest"]),
                )
                request = gate._expected_request(
                    experiment,
                    str(summary["experiment_digest"]),
                    plan_id,
                )
                numerics = experiment["numerics"]
                request_numerics = request["numerics"]
                self.assertIsInstance(numerics, dict)
                self.assertIsInstance(request_numerics, dict)
                if directory == "valid-finite":
                    self.assertNotIn("min_sweeps", numerics)
                    self.assertNotIn("entropy_tolerance", numerics)
                    self.assertEqual(request_numerics["min_sweeps"], 0)
                    self.assertIsNone(request_numerics["entropy_tolerance"])
                else:
                    fit = experiment["numerics"]["finite_entanglement_fit"]
                    self.assertEqual(fit["max_chi"], numerics["max_bond_dim"])
                    self.assertEqual(
                        request_numerics["chi_schedule"][-1],
                        numerics["max_bond_dim"],
                    )
                verdict = gate.evaluate(
                    experiment,
                    self.load(f"{directory}/evidence.json"),
                    artifact_root=self.fixture(f"{directory}/artifacts"),
                )
                self.assertEqual(verdict["reason_code"], "ACCEPTANCE_PASSED")

    def test_missing_gate_observable_dependencies_are_stable_rejections(self) -> None:
        for directory in ("valid-finite", "valid-infinite"):
            for dependency in ("energy", "variance"):
                with self.subTest(directory=directory, dependency=dependency):
                    experiment = self.load(f"{directory}/experiment.json")
                    observables = experiment["observables"]
                    self.assertIsInstance(observables, list)
                    observables.remove(dependency)
                    self.assert_reason(
                        "OBSERVABLE_SET_MISMATCH",
                        lambda experiment=experiment: gate.validate_experiment(
                            experiment
                        ),
                    )

    def test_route_numerics_are_exact_and_fail_closed(self) -> None:
        finite = self.load("valid-finite/experiment.json")
        finite_numerics = finite["numerics"]
        self.assertIsInstance(finite_numerics, dict)
        for name, value in (("min_sweeps", 1), ("entropy_tolerance", None)):
            with self.subTest(finite_field=name):
                mutated = copy.deepcopy(finite)
                mutated["numerics"][name] = value
                self.assert_reason(
                    "UNKNOWN_FIELD",
                    lambda mutated=mutated: gate.validate_experiment(mutated),
                )

        infinite = self.load("valid-infinite/experiment.json")
        infinite["numerics"]["finite_entanglement_fit"]["max_chi"] = 16
        self.assert_reason(
            "UNSUPPORTED_ROUTE",
            lambda: gate.validate_experiment(infinite),
        )

    def test_nonunit_jxy_is_outside_the_standalone_capsule_trust_root(self) -> None:
        experiment = self.load("valid-infinite/experiment.json")
        couplings = experiment["physics"]["model"]["couplings"]
        couplings["Jxy"] = 2.0
        couplings["Delta"] = 1.5
        couplings["h"] = 0.25
        self.assert_reason(
            "UNSUPPORTED_ROUTE",
            lambda: gate.validate_experiment(experiment),
        )

    def test_valid_finite_and_infinite_evaluations(self) -> None:
        for directory in ("valid-finite", "valid-infinite"):
            with self.subTest(directory=directory):
                experiment = self.load(f"{directory}/experiment.json")
                evidence = self.load(f"{directory}/evidence.json")
                verdict = gate.evaluate(
                    experiment,
                    evidence,
                    artifact_root=self.fixture(f"{directory}/artifacts"),
                )
                self.assertEqual(verdict["reason_code"], "ACCEPTANCE_PASSED")
                self.assertTrue(verdict["accepted"])

    def test_synthetic_candidate_cannot_self_report_scientific_acceptance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            fixture_root = temporary_root / "fixtures" / "valid-finite"
            shutil.copytree(self.fixture("valid-finite"), fixture_root)
            experiment_path = fixture_root / "experiment.json"
            experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
            experiment["problem"]["status"] = "candidate"
            experiment_path.write_text(
                json.dumps(experiment, ensure_ascii=False),
                encoding="utf-8",
            )

            regenerate = self.load_regenerator()
            regenerate.SOLUTION_ROOT = temporary_root
            regenerate.write_fixture(
                "valid-finite",
                copy.deepcopy(regenerate.CONFIG["valid-finite"]),
            )

            candidate = gate.load_json_document(experiment_path)
            candidate_summary = gate.validate_experiment(candidate)
            self.assertEqual(candidate_summary["reason_code"], "OK")
            self.assertEqual(candidate_summary["problem_status"], "candidate")
            with self.assertRaises(gate.GateError) as caught:
                gate.evaluate(
                    candidate,
                    gate.load_json_document(fixture_root / "evidence.json"),
                    artifact_root=fixture_root / "artifacts",
                )
            self.assertEqual(
                caught.exception.reason_code,
                "SCIENTIFIC_EVIDENCE_UNATTESTED",
            )
            self.assertEqual(caught.exception.exit_code, 3)
            self.assertIs(caught.exception.as_dict()["accepted"], False)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SOLUTION_ROOT / "gate.py"),
                    "evaluate",
                    str(experiment_path),
                    str(fixture_root / "evidence.json"),
                    "--artifact-root",
                    str(fixture_root / "artifacts"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 3, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(
                payload["reason_code"],
                "SCIENTIFIC_EVIDENCE_UNATTESTED",
            )
            self.assertIs(payload["accepted"], False)
            self.assertEqual(completed.stderr, "")

    def test_fixtures_match_main_repository_request_and_result_models(self) -> None:
        starter = Path(os.environ.get("TN_AGENT_STARTER_ROOT", STARTER_ROOT))
        if not (starter / "src" / "tn_agent").is_dir():
            self.skipTest("optional TN-Agent source checkout is not available")
        configured_python = os.environ.get("TN_AGENT_INTEGRATION_PYTHON")
        python = (
            Path(configured_python)
            if configured_python
            else starter / ".venv" / "bin" / "python"
        )
        if not python.is_file():
            python = Path(sys.executable)
        probe = subprocess.run(
            [
                str(python),
                "-c",
                (
                    "import pathlib,sys;"
                    "sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'src'));"
                    "from tn_agent.backends.models import BackendResultBundleV1;"
                    "from tn_agent.backends.tenpy.requests import "
                    "parse_tenpy_request_json"
                ),
                str(starter),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0 and configured_python is None:
            self.skipTest("optional TN-Agent integration dependencies are unavailable")
        self.assertEqual(probe.returncode, 0, probe.stderr)
        script = """
import json
import pathlib
import sys
starter = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(starter / "src"))
from tn_agent.backends.models import BackendResultBundleV1
from tn_agent.backends.models import audited_validate_json
from tn_agent.backends.tenpy.adapter import _RAW_RESULT_ADAPTER
from tn_agent.backends.tenpy.requests import parse_tenpy_request_json
from tn_agent.backends.tenpy.worker import _infinite_xxz_model_parameters
from tn_agent.backends.tenpy.worker import _validate_finite_request
from tn_agent.backends.tenpy.worker import _validate_infinite_request
for directory in sys.argv[2:]:
    root = pathlib.Path(directory)
    request = parse_tenpy_request_json(
        (root / "artifacts" / "backend-request.json").read_bytes()
    )
    if request.capability_id == "tenpy.finite_1d.dmrg":
        _validate_finite_request(request)
    else:
        _validate_infinite_request(request)
    bundle = BackendResultBundleV1.model_validate_json(
        (root / "artifacts" / "backend-result.json").read_bytes()
    )
    assert BackendResultBundleV1.model_validate(
        bundle.model_dump(mode="python")
    ) == bundle
    raw_result = audited_validate_json(
        _RAW_RESULT_ADAPTER,
        (root / "artifacts" / "backend-raw-result.json").read_bytes(),
    )
    repeat_bundle = BackendResultBundleV1.model_validate_json(
        (root / "artifacts" / "backend-repeat-result.json").read_bytes()
    )
    repeat_raw = audited_validate_json(
        _RAW_RESULT_ADAPTER,
        (root / "artifacts" / "backend-repeat-raw-result.json").read_bytes(),
    )
    assert bundle.request_digest.startswith("sha256:")
    assert request.plan_id == bundle.provenance.plan_id
    assert raw_result.request_digest == bundle.request_digest
    assert repeat_raw.request_digest == repeat_bundle.request_digest
infinite_root = pathlib.Path(sys.argv[-1])
unit_request = parse_tenpy_request_json(
    (infinite_root / "artifacts" / "backend-request.json").read_bytes()
)
_validate_infinite_request(unit_request)
parameters = _infinite_xxz_model_parameters(unit_request)
assert unit_request.coupling_jxy == 1.0
assert parameters["Jxx"] == 1.0
assert parameters["Jz"] == unit_request.anisotropy_delta
assert parameters["hz"] == unit_request.field_h
"""
        completed = subprocess.run(
            [
                str(python),
                "-c",
                script,
                str(starter),
                str(self.fixture("valid-finite")),
                str(self.fixture("valid-infinite")),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_duplicate_keys_and_nonfinite_numbers_fail_before_shape_validation(
        self,
    ) -> None:
        self.assert_reason(
            "DOCUMENT_DUPLICATE_KEY",
            lambda: gate.load_json_document(self.fixture("invalid/duplicate-key.json")),
        )
        self.assert_reason(
            "DOCUMENT_NONFINITE",
            lambda: gate.load_json_document(self.fixture("invalid/nonfinite.json")),
        )

    def test_unknown_and_missing_fields_fail_closed(self) -> None:
        self.assert_reason(
            "UNKNOWN_FIELD",
            lambda: gate.validate_experiment(self.load("invalid/unknown-field.json")),
        )
        self.assert_reason(
            "MISSING_FIELD",
            lambda: gate.validate_experiment(self.load("invalid/missing-field.json")),
        )

    def test_unrepresentable_numbers_and_impossible_timestamps_fail_closed(
        self,
    ) -> None:
        huge_number = self.load("valid-finite/experiment.json")
        physics = huge_number["physics"]
        self.assertIsInstance(physics, dict)
        model = physics["model"]
        self.assertIsInstance(model, dict)
        couplings = model["couplings"]
        self.assertIsInstance(couplings, dict)
        couplings["J"] = 10**4000
        self.assert_reason(
            "VALUE_INVALID",
            lambda: gate.validate_experiment(huge_number),
        )

        impossible_date = self.load("valid-finite/experiment.json")
        provenance = impossible_date["provenance"]
        self.assertIsInstance(provenance, dict)
        provenance["created_at"] = "2026-02-30T12:00:00Z"
        self.assert_reason(
            "VALUE_INVALID",
            lambda: gate.validate_experiment(impossible_date),
        )

    def test_unsupported_route_is_not_rewritten(self) -> None:
        experiment = self.load("valid-finite/experiment.json")
        experiment["capability"] = {
            "capability_id": "quimb.finite_1d.dmrg",
            "maturity": "catalogued",
            "known_limitations": ["No promoted adapter binding."],
        }
        self.assert_reason(
            "UNSUPPORTED_ROUTE",
            lambda: gate.validate_experiment(experiment),
        )

        finite = self.load("valid-finite/experiment.json")
        capability = finite["capability"]
        self.assertIsInstance(capability, dict)
        capability["known_limitations"] = ["none"]
        self.assert_reason(
            "UNSUPPORTED_ROUTE",
            lambda: gate.validate_experiment(finite),
        )

    def test_bad_experiment_digest_and_binding_are_distinct(self) -> None:
        finite = self.load("valid-finite/experiment.json")
        bad_digest = self.load("valid-finite/evidence.json")
        bad_digest["experiment_digest"] = "sha256:" + ("0" * 64)
        self.assert_reason(
            "EXPERIMENT_DIGEST_MISMATCH",
            lambda: gate.evaluate(
                finite,
                bad_digest,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

        bad_binding = self.load("valid-finite/evidence.json")
        binding = bad_binding["binding"]
        self.assertIsInstance(binding, dict)
        binding["adapter_id"] = "unapproved.adapter"
        self.assert_reason(
            "BINDING_MISMATCH",
            lambda: gate.evaluate(
                finite,
                bad_binding,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

    def test_result_digest_is_checked(self) -> None:
        finite = self.load("valid-finite/experiment.json")
        evidence = self.load("valid-finite/evidence.json")
        evidence["result_digest"] = "sha256:" + ("0" * 64)
        self.assert_reason(
            "RESULT_DIGEST_MISMATCH",
            lambda: gate.evaluate(
                finite,
                evidence,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

    def test_artifact_digest_is_recomputed_from_raw_bytes(self) -> None:
        finite = self.load("valid-finite/experiment.json")
        evidence = self.load("valid-finite/evidence.json")
        artifacts = evidence["artifacts"]
        self.assertIsInstance(artifacts, list)
        self.assertIsInstance(artifacts[0], dict)
        artifacts[0]["digest"] = "sha256:" + ("0" * 64)
        evidence["result_digest"] = gate.canonical_digest(
            {key: value for key, value in evidence.items() if key != "result_digest"}
        )
        self.assert_reason(
            "ARTIFACT_DIGEST_MISMATCH",
            lambda: gate.evaluate(
                finite,
                evidence,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

    def test_artifact_paths_must_be_canonical_relative_posix_paths(self) -> None:
        for relative_path in (
            ".",
            "\x00",
            "artifacts/\x00",
            "/backend-result.json",
            "../backend-result.json",
            "artifacts/../backend-result.json",
            "./backend-result.json",
            "artifacts/./backend-result.json",
            "artifacts//backend-result.json",
            "artifacts/",
            r"artifacts\backend-result.json",
            "C:backend-result.json",
        ):
            with self.subTest(relative_path=relative_path):
                self.assert_reason(
                    "ARTIFACT_UNSAFE_PATH",
                    lambda relative_path=relative_path: gate._validate_relative_path(
                        relative_path,
                        "$.artifacts[0].relative_path",
                    ),
                )

    def test_artifact_path_errors_are_stable_json_without_tracebacks(self) -> None:
        evidence = self.load("valid-finite/evidence.json")
        artifacts = evidence["artifacts"]
        self.assertIsInstance(artifacts, list)
        self.assertIsInstance(artifacts[0], dict)
        artifacts[0]["relative_path"] = "."
        self.redigest_evidence(evidence)
        with tempfile.TemporaryDirectory() as temporary:
            evidence_path = Path(temporary) / "evidence.json"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SOLUTION_ROOT / "gate.py"),
                    "evaluate",
                    str(self.fixture("valid-finite/experiment.json")),
                    str(evidence_path),
                    "--artifact-root",
                    str(self.fixture("valid-finite/artifacts")),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(
            json.loads(completed.stdout)["reason_code"],
            "ARTIFACT_UNSAFE_PATH",
        )
        self.assertEqual(completed.stderr, "")

    def test_artifact_root_symlink_and_fifo_are_rejected_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            symlink = root / "artifact-root"
            symlink.symlink_to(
                self.fixture("valid-finite/artifacts"),
                target_is_directory=True,
            )
            self.assert_reason(
                "ARTIFACT_UNSAFE_PATH",
                lambda: gate.evaluate(
                    self.load("valid-finite/experiment.json"),
                    self.load("valid-finite/evidence.json"),
                    artifact_root=symlink,
                ),
            )

            fifo_root = root / "fifo-root"
            fifo_root.mkdir()
            os.mkfifo(fifo_root / "fifo")
            script = (
                "import pathlib,sys;"
                f"sys.path.insert(0,{str(SOLUTION_ROOT)!r});"
                "import gate;"
                "gate._read_artifact_file(pathlib.Path(sys.argv[1]),'fifo',1024)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(fifo_root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                self.fail("FIFO artifact open blocked before file-type validation")
            self.assertNotEqual(process.returncode, 0)

    def test_hardlinked_artifacts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary) / "artifacts"
            shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
            os.link(
                artifacts / "backend-request.json",
                Path(temporary) / "backend-request-hardlink.json",
            )
            self.assert_reason(
                "ARTIFACT_UNSAFE_PATH",
                lambda: gate.evaluate(
                    self.load("valid-finite/experiment.json"),
                    self.load("valid-finite/evidence.json"),
                    artifact_root=artifacts,
                ),
            )

    def test_backend_result_artifact_must_contain_normalized_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary) / "artifacts"
            shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
            evidence = self.load("valid-finite/evidence.json")
            self.replace_backend_bundle(artifacts, evidence, b"")
            self.assert_reason(
                "DOCUMENT_INVALID_JSON",
                lambda: gate.evaluate(
                    self.load("valid-finite/experiment.json"),
                    evidence,
                    artifact_root=artifacts,
                ),
            )

    def test_backend_bundle_json_is_strict_for_every_contract_boundary(self) -> None:
        original = self.fixture(
            "valid-finite/artifacts/backend-result.json"
        ).read_bytes()
        for mutation, expected in (
            ("duplicate", "DOCUMENT_DUPLICATE_KEY"),
            ("nonfinite", "DOCUMENT_NONFINITE"),
            ("unknown", "UNKNOWN_FIELD"),
            ("missing", "MISSING_FIELD"),
        ):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary,
            ):
                artifacts = Path(temporary) / "artifacts"
                shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
                evidence = self.load("valid-finite/evidence.json")
                if mutation == "duplicate":
                    raw = original.replace(
                        b"{\n",
                        b'{\n  "schema_version": "tn-agent.backend-result.v1",\n',
                        1,
                    )
                elif mutation == "nonfinite":
                    raw = original.replace(b'"value": 1e-10', b'"value": NaN', 1)
                else:
                    bundle = json.loads(original)
                    if mutation == "unknown":
                        bundle["unexpected"] = True
                    else:
                        del bundle["backend"]
                    bundle["result_digest"] = gate.canonical_digest(
                        {
                            key: value
                            for key, value in bundle.items()
                            if key != "result_digest"
                        }
                    )
                    raw = (json.dumps(bundle, indent=2) + "\n").encode()
                self.replace_backend_bundle(artifacts, evidence, raw)
                self.assert_reason(
                    expected,
                    lambda evidence=evidence, artifacts=artifacts: gate.evaluate(
                        self.load("valid-finite/experiment.json"),
                        evidence,
                        artifact_root=artifacts,
                    ),
                )

    def test_raw_result_and_plan_id_must_match_the_normalized_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary) / "artifacts"
            shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
            evidence = self.load("valid-finite/evidence.json")
            raw_path = artifacts / "backend-raw-result.json"
            raw = raw_path.read_bytes() + b"\n"
            raw_path.write_bytes(raw)
            manifest = evidence["artifacts"]
            self.assertIsInstance(manifest, list)
            raw_artifact = next(
                item
                for item in manifest
                if isinstance(item, dict) and item.get("role") == "backend_raw_result"
            )
            raw_artifact["digest"] = "sha256:" + hashlib.sha256(raw).hexdigest()
            raw_artifact["size_bytes"] = len(raw)
            self.redigest_evidence(evidence)
            self.assert_reason(
                "RESULT_DIGEST_MISMATCH",
                lambda: gate.evaluate(
                    self.load("valid-finite/experiment.json"),
                    evidence,
                    artifact_root=artifacts,
                ),
            )

        evidence = self.load("valid-finite/evidence.json")
        provenance = evidence["provenance"]
        self.assertIsInstance(provenance, dict)
        provenance["plan_id"] = "sha256:" + ("f" * 64)
        self.redigest_evidence(evidence)
        self.assert_reason(
            "PROVENANCE_MISMATCH",
            lambda: gate.evaluate(
                self.load("valid-finite/experiment.json"),
                evidence,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

    def test_raw_failed_status_and_forged_energy_cannot_reuse_normalized_pass(
        self,
    ) -> None:
        for mutation, expected in (
            ("failed_status", "PROVENANCE_MISMATCH"),
            ("energy_999", "RESULT_DIGEST_MISMATCH"),
        ):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary,
            ):
                artifacts = Path(temporary) / "artifacts"
                shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
                evidence = self.load("valid-finite/evidence.json")
                raw_result = json.loads(
                    (artifacts / "backend-raw-result.json").read_text()
                )
                if mutation == "failed_status":
                    raw_result["status"] = "failed"
                else:
                    raw_result["observables"]["energy"]["value"] = 999.0
                raw = (json.dumps(raw_result, indent=2) + "\n").encode()
                self.replace_artifact(
                    artifacts,
                    evidence,
                    role="backend_raw_result",
                    raw=raw,
                )
                self.assert_reason(
                    expected,
                    lambda evidence=evidence, artifacts=artifacts: gate.evaluate(
                        self.load("valid-finite/experiment.json"),
                        evidence,
                        artifact_root=artifacts,
                    ),
                )

    def test_reported_energy_drift_cannot_override_derived_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary) / "artifacts"
            shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
            experiment = self.load("valid-finite/experiment.json")
            evidence = self.load("valid-finite/evidence.json")
            raw_result = json.loads((artifacts / "backend-raw-result.json").read_text())
            raw_result["convergence"][-1]["metrics"]["energy_drift"] = 999.0
            raw = (json.dumps(raw_result, indent=2) + "\n").encode()
            self.replace_artifact(
                artifacts,
                evidence,
                role="backend_raw_result",
                raw=raw,
            )
            summary = gate.validate_experiment(experiment)
            binding = experiment["backend_binding"]
            self.assertIsInstance(binding, dict)
            plan_id = gate._expected_plan_id(
                experiment,
                str(summary["experiment_digest"]),
            )
            request = gate._expected_request(
                experiment,
                str(summary["experiment_digest"]),
                plan_id,
            )
            manifest = evidence["artifacts"]
            self.assertIsInstance(manifest, list)
            raw_artifact = next(
                item
                for item in manifest
                if isinstance(item, dict) and item.get("role") == "backend_raw_result"
            )
            parsed_raw = gate._validate_raw_result(
                raw,
                request=request,
                request_digest=gate.canonical_digest(request),
                binding=binding,
                route=gate.ROUTES[str(binding["capability_id"])],
            )
            execution = evidence["execution"]
            self.assertIsInstance(execution, dict)
            reconstructed = gate._reconstruct_backend_bundle(
                request_digest=gate.canonical_digest(request),
                binding=binding,
                raw=parsed_raw,
                execution=execution,
                raw_artifact=raw_artifact,
            )
            self.write_backend_bundle(artifacts, evidence, reconstructed)
            self.assert_reason(
                "VALIDATOR_STATUS_INVALID",
                lambda: gate.evaluate(
                    experiment,
                    evidence,
                    artifact_root=artifacts,
                ),
            )

    def test_coherent_energy_forgery_fails_against_preregistered_reference(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary) / "artifacts"
            shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
            experiment = self.load("valid-finite/experiment.json")
            evidence = self.load("valid-finite/evidence.json")
            raw_result = json.loads((artifacts / "backend-raw-result.json").read_text())
            raw_result["observables"]["energy"]["value"] = 999.0
            raw_result["convergence"][-2]["metrics"]["energy"] = 998.99999999
            raw_result["convergence"][-1]["metrics"]["energy"] = 999.0
            raw_result["convergence"][-1]["metrics"]["canonical_residual"] = 0.0
            raw_result["convergence"][-1]["metrics"]["symmetry_residual"] = 0.0
            self.coherently_rebuild_primary_evidence(
                directory=artifacts,
                experiment=experiment,
                evidence=evidence,
                raw_result=raw_result,
            )
            self.assert_reason(
                "VALIDATOR_THRESHOLD_FAILED",
                lambda: gate.evaluate(
                    experiment,
                    evidence,
                    artifact_root=artifacts,
                ),
            )

    def test_repeat_execution_and_raw_identity_must_be_distinct(self) -> None:
        missing_repeat = self.load("valid-finite/evidence.json")
        manifest = missing_repeat["artifacts"]
        self.assertIsInstance(manifest, list)
        manifest[:] = [
            item
            for item in manifest
            if not (
                isinstance(item, dict) and item.get("role") == "backend_repeat_stderr"
            )
        ]
        self.redigest_evidence(missing_repeat)
        self.assert_reason(
            "VALUE_INVALID",
            lambda: gate.evaluate(
                self.load("valid-finite/experiment.json"),
                missing_repeat,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

        evidence = self.load("valid-finite/evidence.json")
        evidence["repeat_execution"] = copy.deepcopy(evidence["execution"])
        self.redigest_evidence(evidence)
        self.assert_reason(
            "PROVENANCE_MISMATCH",
            lambda: gate.evaluate(
                self.load("valid-finite/experiment.json"),
                evidence,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary) / "artifacts"
            shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
            evidence = self.load("valid-finite/evidence.json")
            primary_raw = (artifacts / "backend-raw-result.json").read_bytes()
            self.replace_artifact(
                artifacts,
                evidence,
                role="backend_repeat_raw_result",
                raw=primary_raw,
            )
            self.assert_reason(
                "PROVENANCE_MISMATCH",
                lambda: gate.evaluate(
                    self.load("valid-finite/experiment.json"),
                    evidence,
                    artifact_root=artifacts,
                ),
            )

    def test_repeat_cosmetic_differences_remain_reported_only(self) -> None:
        primary_bytes = self.fixture(
            "valid-finite/artifacts/backend-raw-result.json"
        ).read_bytes()
        repeat_bytes = self.fixture(
            "valid-finite/artifacts/backend-repeat-raw-result.json"
        ).read_bytes()
        cosmetic_warning = json.loads(repeat_bytes)
        cosmetic_warning["warnings"] = ["cosmetic repeat warning"]
        physics_equal = json.loads(primary_bytes)
        physics_equal["warnings"] = ["physics-equal structural rebuild"]
        cases = {
            "trailing_whitespace": repeat_bytes + b" \n",
            "cosmetic_warning": (
                json.dumps(cosmetic_warning, indent=2, allow_nan=False) + "\n"
            ).encode(),
            "physics_equal_full_rebuild": (
                json.dumps(physics_equal, indent=2, allow_nan=False) + "\n"
            ).encode(),
        }
        for name, mutated_repeat in cases.items():
            with (
                self.subTest(case=name),
                tempfile.TemporaryDirectory() as temporary,
            ):
                artifacts = Path(temporary) / "artifacts"
                shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
                experiment = self.load("valid-finite/experiment.json")
                evidence = self.load("valid-finite/evidence.json")
                self.coherently_rebuild_repeat_evidence(
                    directory=artifacts,
                    experiment=experiment,
                    evidence=evidence,
                    repeat_raw_bytes=mutated_repeat,
                )
                verdict = gate.evaluate(
                    experiment,
                    evidence,
                    artifact_root=artifacts,
                )
                self.assertEqual(verdict["reason_code"], "ACCEPTANCE_PASSED")
                reproduction = next(
                    result
                    for result in evidence["validator_results"]
                    if result["id"] == "reproducibility"
                )
                self.assertEqual(reproduction["status"], "reported_only")
                self.assertEqual(reproduction["reason_code"], "REPORTED_ONLY")
                if name == "physics_equal_full_rebuild":
                    self.assertEqual(reproduction["metric_value"], 0.0)

    def test_reported_only_diagnostics_cannot_enter_required_acceptance(self) -> None:
        experiment = self.load("valid-finite/experiment.json")
        validators = experiment["validators"]
        acceptance = experiment["acceptance"]
        self.assertIsInstance(validators, list)
        self.assertIsInstance(acceptance, dict)
        variance = next(
            item
            for item in validators
            if isinstance(item, dict) and item.get("id") == "variance"
        )
        variance["policy"] = "required_pass"
        variance["operator"] = "max"
        variance["threshold"] = 1.0
        acceptance["reported_only_validator_ids"].remove("variance")
        acceptance["required_validator_ids"].append("variance")
        self.assert_reason(
            "VALIDATOR_POLICY_MISMATCH",
            lambda: gate.validate_experiment(experiment),
        )

    def test_validator_artifact_metric_is_recomputed_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary) / "artifacts"
            shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
            evidence = self.load("valid-finite/evidence.json")
            validator = json.loads((artifacts / "validator-evidence.json").read_text())
            convergence = next(
                item for item in validator["results"] if item["id"] == "convergence"
            )
            convergence["value"] = 0.0
            validator["result_digest"] = gate.canonical_digest(
                {
                    key: value
                    for key, value in validator.items()
                    if key != "result_digest"
                }
            )
            raw = (json.dumps(validator, indent=2) + "\n").encode()
            self.replace_artifact(
                artifacts,
                evidence,
                role="validator_evidence",
                raw=raw,
            )
            self.assert_reason(
                "VALIDATOR_STATUS_INVALID",
                lambda: gate.evaluate(
                    self.load("valid-finite/experiment.json"),
                    evidence,
                    artifact_root=artifacts,
                ),
            )

    def test_backend_bundle_is_the_source_of_observable_and_validator_semantics(
        self,
    ) -> None:
        finite = self.load("valid-finite/experiment.json")
        for mutation, expected in (
            ("observable_status", "OBSERVABLE_STATUS_INVALID"),
            ("validator_metric", "VALIDATOR_STATUS_INVALID"),
        ):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary,
            ):
                artifacts = Path(temporary) / "artifacts"
                shutil.copytree(self.fixture("valid-finite/artifacts"), artifacts)
                evidence = self.load("valid-finite/evidence.json")
                if mutation == "observable_status":
                    observable_results = evidence["observables"]
                    self.assertIsInstance(observable_results, list)
                    for item in observable_results:
                        self.assertIsInstance(item, dict)
                        item["status"] = "derived"
                else:
                    validator_results = evidence["validator_results"]
                    self.assertIsInstance(validator_results, list)
                    convergence = next(
                        item
                        for item in validator_results
                        if isinstance(item, dict) and item.get("id") == "convergence"
                    )
                    convergence["metric_value"] = 0.0
                self.redigest_evidence(evidence)
                self.assert_reason(
                    expected,
                    lambda evidence=evidence, artifacts=artifacts: gate.evaluate(
                        finite,
                        evidence,
                        artifact_root=artifacts,
                    ),
                )

    def test_validator_metric_contracts_are_exact_and_nonnegative(self) -> None:
        experiment = self.load("valid-finite/experiment.json")
        validators = experiment["validators"]
        self.assertIsInstance(validators, list)
        convergence = next(
            item
            for item in validators
            if isinstance(item, dict) and item.get("id") == "convergence"
        )
        convergence["metric"] = "invented_metric"
        self.assert_reason(
            "VALIDATOR_POLICY_MISMATCH",
            lambda: gate.validate_experiment(experiment),
        )

        evidence = self.load("valid-finite/evidence.json")
        results = evidence["validator_results"]
        self.assertIsInstance(results, list)
        convergence_result = next(
            item
            for item in results
            if isinstance(item, dict) and item.get("id") == "convergence"
        )
        convergence_result["metric_value"] = -1.0
        self.redigest_evidence(evidence)
        self.assert_reason(
            "VALIDATOR_STATUS_INVALID",
            lambda: gate.evaluate(
                self.load("valid-finite/experiment.json"),
                evidence,
                artifact_root=self.fixture("valid-finite/artifacts"),
            ),
        )

    def test_metric_cannot_claim_pass_above_preregistered_threshold(self) -> None:
        finite = self.load("valid-finite/experiment.json")
        validators = finite["validators"]
        self.assertIsInstance(validators, list)
        convergence = next(
            item
            for item in validators
            if isinstance(item, dict) and item.get("id") == "convergence"
        )
        self.assert_reason(
            "VALIDATOR_THRESHOLD_FAILED",
            lambda: gate._evaluate_threshold(
                "convergence",
                convergence,
                {"metric_value": 1.0},
            ),
        )

    def test_library_is_append_only_and_cross_references_prior_records(self) -> None:
        summary = gate.validate_library(SOLUTION_ROOT / "library" / "heuristics.jsonl")
        self.assertEqual(summary["reason_code"], "OK")
        self.assertGreaterEqual(summary["records"], 3)

        first = json.loads(
            (SOLUTION_ROOT / "library" / "heuristics.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        first["revision"] = 2
        first["record_id"] = f"{first['heuristic_id']}@2"
        with tempfile.TemporaryDirectory() as temporary:
            bad_library = Path(temporary) / "heuristics.jsonl"
            bad_library.write_text(
                json.dumps(first, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            self.assert_reason(
                "LIBRARY_SEQUENCE_INVALID",
                lambda: gate.validate_library(bad_library),
            )

    def test_library_revision_must_supersede_immediately_prior_record(self) -> None:
        first = json.loads(
            (SOLUTION_ROOT / "library" / "heuristics.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        second = json.loads(json.dumps(first))
        second["record_id"] = f"{first['heuristic_id']}@2"
        second["revision"] = 2
        second["recorded_at"] = "2026-07-29T00:00:01Z"
        second["supersedes"] = [first["record_id"]]
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "heuristics.jsonl"
            library.write_text(
                "\n".join(
                    json.dumps(item, separators=(",", ":")) for item in (first, second)
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(gate.validate_library(library)["records"], 2)
            second["supersedes"] = []
            library.write_text(
                "\n".join(
                    json.dumps(item, separators=(",", ":")) for item in (first, second)
                )
                + "\n",
                encoding="utf-8",
            )
            self.assert_reason(
                "LIBRARY_SEQUENCE_INVALID",
                lambda: gate.validate_library(library),
            )

    def test_library_revision_cannot_supersede_an_unrelated_heuristic(self) -> None:
        records = [
            json.loads(line)
            for line in (SOLUTION_ROOT / "library" / "heuristics.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        revision = copy.deepcopy(records[0])
        revision["record_id"] = f"{revision['heuristic_id']}@2"
        revision["revision"] = 2
        revision["recorded_at"] = "2026-07-29T00:03:00Z"
        revision["supersedes"] = [records[0]["record_id"], records[1]["record_id"]]
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "heuristics.jsonl"
            library.write_text(
                "\n".join(
                    json.dumps(item, separators=(",", ":"))
                    for item in (records[0], records[1], revision)
                )
                + "\n",
                encoding="utf-8",
            )
            self.assert_reason(
                "LIBRARY_SEQUENCE_INVALID",
                lambda: gate.validate_library(library),
            )

    def test_library_grounding_rejects_tamper_traversal_and_missing_files(
        self,
    ) -> None:
        original = json.loads(
            (SOLUTION_ROOT / "library" / "heuristics.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        mutations = {
            "source_tamper": ("source", "sha256", "sha256:" + ("0" * 64)),
            "source_traversal": ("source", "uri", "../skills/method-mps/SKILL.md"),
            "source_missing": ("source", "uri", "skills/missing/SKILL.md"),
            "evidence_tamper": ("evidence", "sha256", "sha256:" + ("f" * 64)),
            "evidence_traversal": (
                "evidence",
                "uri",
                "../skills/method-mps/SKILL.md",
            ),
            "evidence_missing": ("evidence", "uri", "skills/missing/SKILL.md"),
        }
        for name, (section, key, value) in mutations.items():
            with (
                self.subTest(case=name),
                tempfile.TemporaryDirectory() as temporary,
            ):
                record = copy.deepcopy(original)
                record[section][key] = value
                library = Path(temporary) / "heuristics.jsonl"
                library.write_text(
                    json.dumps(record, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                self.assert_reason(
                    "LIBRARY_RECORD_INVALID",
                    lambda library=library: gate.validate_library(library),
                )

    def test_library_kind_and_path_must_match(self) -> None:
        original = json.loads(
            (SOLUTION_ROOT / "library" / "heuristics.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        mutations = (
            ("source", "repository_skill", "README.md", REPOSITORY_ROOT),
            ("evidence", "method_card", "README.md", REPOSITORY_ROOT),
            ("evidence", "workflow_card", "README.md", REPOSITORY_ROOT),
            ("evidence", "contract_audit", "README.md", SOLUTION_ROOT),
        )
        for section, kind, uri, root in mutations:
            with (
                self.subTest(section=section, kind=kind),
                tempfile.TemporaryDirectory() as temporary,
            ):
                record = copy.deepcopy(original)
                grounded_file = root / uri
                record[section]["kind"] = kind
                record[section]["uri"] = uri
                record[section]["sha256"] = (
                    "sha256:" + hashlib.sha256(grounded_file.read_bytes()).hexdigest()
                )
                library = Path(temporary) / "heuristics.jsonl"
                library.write_text(
                    json.dumps(record, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                self.assert_reason(
                    "LIBRARY_RECORD_INVALID",
                    lambda library=library: gate.validate_library(library),
                )

    def test_public_cli_emits_one_machine_readable_verdict(self) -> None:
        command = [
            sys.executable,
            str(SOLUTION_ROOT / "gate.py"),
            "evaluate",
            str(self.fixture("valid-finite/experiment.json")),
            str(self.fixture("valid-finite/evidence.json")),
            "--artifact-root",
            str(self.fixture("valid-finite/artifacts")),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["reason_code"], "ACCEPTANCE_PASSED")
        self.assertEqual(completed.stderr, "")

    def test_public_cli_usage_errors_are_also_machine_readable(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SOLUTION_ROOT / "gate.py"), "evaluate"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["reason_code"], "CLI_USAGE_ERROR")
        self.assertEqual(completed.stderr, "")

    def test_schema_files_are_json_and_fail_closed_at_every_object(self) -> None:
        schema_paths = (
            SOLUTION_ROOT / "contracts" / "experiment-v1.schema.json",
            SOLUTION_ROOT / "contracts" / "evidence-v1.schema.json",
            SOLUTION_ROOT / "contracts" / "backend-result-v1.schema.json",
            SOLUTION_ROOT / "contracts" / "validator-evidence-v1.schema.json",
            SOLUTION_ROOT / "contracts" / "energy-reference-v1.schema.json",
            SOLUTION_ROOT / "library" / "heuristic-v1.schema.json",
        )
        for schema_path in schema_paths:
            with self.subTest(schema=schema_path.name):
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
                )
                self.assertEqual(schema["additionalProperties"], False)
                for definition in schema.get("$defs", {}).values():
                    if (
                        isinstance(definition, dict)
                        and definition.get("type") == "object"
                    ):
                        additional = definition.get("additionalProperties")
                        self.assertTrue(
                            additional is False or isinstance(additional, dict),
                            f"unbounded object definition: {definition}",
                        )

    def test_public_json_schemas_accept_all_promoted_fixtures(self) -> None:
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("optional jsonschema package is not installed")
        from jsonschema import Draft202012Validator

        pairs: list[tuple[Path, Path]] = []
        for directory in ("valid-finite", "valid-infinite"):
            for schema_name, fixture_name in (
                ("experiment-v1.schema.json", "experiment.json"),
                ("evidence-v1.schema.json", "evidence.json"),
                ("backend-result-v1.schema.json", "artifacts/backend-result.json"),
                (
                    "backend-result-v1.schema.json",
                    "artifacts/backend-repeat-result.json",
                ),
                (
                    "validator-evidence-v1.schema.json",
                    "artifacts/validator-evidence.json",
                ),
                (
                    "energy-reference-v1.schema.json",
                    "artifacts/energy-reference.json",
                ),
            ):
                pairs.append(
                    (
                        SOLUTION_ROOT / "contracts" / schema_name,
                        self.fixture(f"{directory}/{fixture_name}"),
                    )
                )
        for schema_path, fixture_path in pairs:
            with self.subTest(fixture=fixture_path):
                schema = json.loads(schema_path.read_text())
                fixture = json.loads(fixture_path.read_text())
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(fixture)

        experiment_schema = json.loads(
            (SOLUTION_ROOT / "contracts" / "experiment-v1.schema.json").read_text()
        )
        experiment_validator = Draft202012Validator(experiment_schema)
        for directory in ("valid-finite", "valid-infinite"):
            for dependency in ("energy", "variance"):
                with self.subTest(
                    schema_route=directory,
                    missing_dependency=dependency,
                ):
                    experiment = self.load(f"{directory}/experiment.json")
                    experiment["observables"].remove(dependency)
                    self.assertFalse(experiment_validator.is_valid(experiment))
        finite_with_sweeps = self.load("valid-finite/experiment.json")
        finite_with_sweeps["numerics"]["min_sweeps"] = 1
        self.assertFalse(experiment_validator.is_valid(finite_with_sweeps))
        infinite_without_sweeps = self.load("valid-infinite/experiment.json")
        del infinite_without_sweeps["numerics"]["min_sweeps"]
        self.assertFalse(experiment_validator.is_valid(infinite_without_sweeps))
        infinite_nonunit_jxy = self.load("valid-infinite/experiment.json")
        infinite_nonunit_jxy["physics"]["model"]["couplings"]["Jxy"] = 2.0
        self.assertFalse(experiment_validator.is_valid(infinite_nonunit_jxy))

        library_schema = json.loads(
            (SOLUTION_ROOT / "library" / "heuristic-v1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(library_schema)
        library_validator = Draft202012Validator(library_schema)
        for line in (
            (SOLUTION_ROOT / "library" / "heuristics.jsonl").read_text().splitlines()
        ):
            library_validator.validate(json.loads(line))
        library_record = json.loads(
            (SOLUTION_ROOT / "library" / "heuristics.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        for section, kind in (
            ("source", "repository_skill"),
            ("evidence", "method_card"),
            ("evidence", "workflow_card"),
            ("evidence", "contract_audit"),
        ):
            with self.subTest(schema_section=section, schema_kind=kind):
                mutation = copy.deepcopy(library_record)
                mutation[section]["kind"] = kind
                mutation[section]["uri"] = "README.md"
                self.assertFalse(library_validator.is_valid(mutation))

    def test_fixture_provenance_digests_bind_repository_sources(self) -> None:
        experiment = self.load("valid-finite/experiment.json")
        provenance = experiment["provenance"]
        self.assertIsInstance(provenance, dict)
        sources = provenance["sources"]
        self.assertIsInstance(sources, list)
        for source in sources:
            self.assertIsInstance(source, dict)
            source_path = REPOSITORY_ROOT / source["uri"]
            observed = "sha256:" + hashlib.sha256(source_path.read_bytes()).hexdigest()
            self.assertEqual(observed, source["sha256"])

    def test_reason_code_document_covers_the_executable_registry(self) -> None:
        documentation = (SOLUTION_ROOT / "contracts" / "reason-codes.md").read_text(
            encoding="utf-8"
        )
        for reason_code in gate.GATE_REASON_CODES:
            with self.subTest(reason_code=reason_code):
                self.assertIn(f"`{reason_code}`", documentation)


if __name__ == "__main__":
    unittest.main()
