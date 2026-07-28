"""Regenerate the synthetic public contract fixtures deterministically."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION_ROOT))

import gate

CONFIG = {
    "valid-finite": {
        "reference_id": "finite-tfim-l8-open-j1-g0.8-ed",
        "reference": -8.749171017567908,
        "primary": -8.749171017567908,
        "previous": -8.749171007567907,
        "repeat": -8.749170997567908,
        "repeat_previous": -8.749170987567907,
        "normalization": "total",
        "method": "exact_diagonalization",
        "citation": (
            "Exact diagonalization anchor for the preregistered open L=8 "
            "TFIM Hamiltonian with J=1 and g=0.8."
        ),
        "primary_handle": "fixture:finite:primary",
        "repeat_handle": "fixture:finite:repeat",
    },
    "valid-infinite": {
        "reference_id": "infinite-heisenberg-delta1-bethe-ansatz",
        "reference": -0.4431471805599453,
        "primary": -0.4431,
        "previous": -0.443,
        "repeat": -0.44311,
        "repeat_previous": -0.44301,
        "normalization": "per-site",
        "method": "analytic_bethe_ansatz",
        "citation": (
            "Thermodynamic-limit spin-1/2 antiferromagnetic Heisenberg-chain "
            "ground-state energy per site, 1/4-ln(2)."
        ),
        "primary_handle": "fixture:infinite:primary",
        "repeat_handle": "fixture:infinite:repeat",
    },
}


def encoded(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def file_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def semantic(value: dict[str, object]) -> dict[str, object]:
    content = {key: item for key, item in value.items() if key != "result_digest"}
    return {**content, "result_digest": gate.canonical_digest(content)}


def artifact(
    *,
    relative_path: str,
    role: str,
    media_type: str,
    raw: bytes,
) -> dict[str, object]:
    return {
        "relative_path": relative_path,
        "digest": file_digest(raw),
        "size_bytes": len(raw),
        "media_type": media_type,
        "role": role,
    }


def set_policy(experiment: dict[str, object]) -> None:
    validators = experiment["validators"]
    assert isinstance(validators, list)
    for validator in validators:
        assert isinstance(validator, dict)
        identifier = validator["id"]
        if identifier in {
            "canonical_form",
            "symmetry_check",
            "reproducibility",
        } or (
            identifier == "variance"
            and experiment["backend_binding"]["capability_id"]  # type: ignore[index]
            == "tenpy.finite_1d.dmrg"
        ):
            validator["policy"] = "reported_only"
            validator["operator"] = None
            validator["threshold"] = None
    required = [
        str(validator["id"])
        for validator in validators
        if isinstance(validator, dict) and validator["policy"] == "required_pass"
    ]
    limited = [
        str(validator["id"])
        for validator in validators
        if isinstance(validator, dict) and validator["policy"] == "backend_limited"
    ]
    reported = [
        str(validator["id"])
        for validator in validators
        if isinstance(validator, dict) and validator["policy"] == "reported_only"
    ]
    acceptance = experiment["acceptance"]
    assert isinstance(acceptance, dict)
    acceptance["required_validator_ids"] = required
    acceptance["allowed_backend_limited_ids"] = limited
    acceptance["reported_only_validator_ids"] = reported


def make_raw(
    template: dict[str, object],
    *,
    request_digest: str,
    plan_id: str,
    energy: float,
    previous_energy: float,
) -> dict[str, object]:
    raw = copy.deepcopy(template)
    raw["request_digest"] = request_digest
    raw["plan_id"] = plan_id
    observables = raw["observables"]
    convergence = raw["convergence"]
    assert isinstance(observables, dict)
    assert isinstance(convergence, list)
    energy_observable = observables["energy"]
    assert isinstance(energy_observable, dict)
    energy_observable["value"] = energy
    previous = convergence[-2]
    latest = convergence[-1]
    assert isinstance(previous, dict)
    assert isinstance(latest, dict)
    previous_metrics = previous["metrics"]
    latest_metrics = latest["metrics"]
    assert isinstance(previous_metrics, dict)
    assert isinstance(latest_metrics, dict)
    previous_metrics["energy"] = previous_energy
    latest["metrics"] = {
        "energy": energy,
        "canonical_residual": latest_metrics["canonical_residual"],
        "symmetry_residual": latest_metrics["symmetry_residual"],
    }
    return raw


def write_fixture(name: str, config: dict[str, object]) -> None:
    fixture_root = SOLUTION_ROOT / "fixtures" / name
    artifact_root = fixture_root / "artifacts"
    experiment = json.loads((fixture_root / "experiment.json").read_text())
    raw_template = json.loads((artifact_root / "backend-raw-result.json").read_text())
    binding = experiment["backend_binding"]
    numerics = experiment["numerics"]
    assert isinstance(binding, dict)
    assert isinstance(numerics, dict)
    if binding["capability_id"] == "tenpy.finite_1d.dmrg":
        experiment["numerics"] = {
            key: value
            for key, value in numerics.items()
            if key not in {"min_sweeps", "entropy_tolerance"}
        }
    set_policy(experiment)

    reference_record = semantic(
        {
            "schema_version": "wangtheophys.tn-energy-reference.v1",
            "reference_id": config["reference_id"],
            "capability_id": experiment["backend_binding"]["capability_id"],
            "physics_digest": gate.canonical_digest(experiment["physics"]),
            "observable": "energy",
            "value": config["reference"],
            "units": "J",
            "normalization": config["normalization"],
            "method": config["method"],
            "citation": config["citation"],
        }
    )
    reference_raw = encoded(reference_record)
    experiment["reference"] = {
        "observable": "energy",
        "value": config["reference"],
        "units": "J",
        "normalization": config["normalization"],
        "source": {
            "kind": "registered_artifact",
            "uri": "energy-reference.json",
            "sha256": file_digest(reference_raw),
        },
    }
    experiment_raw = encoded(experiment)
    (fixture_root / "experiment.json").write_bytes(experiment_raw)

    experiment_digest = gate.canonical_digest(experiment)
    plan_id = gate._expected_plan_id(experiment, experiment_digest)
    request = gate._expected_request(experiment, experiment_digest, plan_id)
    request_raw = encoded(request)
    request_digest = gate.canonical_digest(request)

    primary_raw_value = make_raw(
        raw_template,
        request_digest=request_digest,
        plan_id=plan_id,
        energy=float(config["primary"]),
        previous_energy=float(config["previous"]),
    )
    repeat_raw_value = make_raw(
        raw_template,
        request_digest=request_digest,
        plan_id=plan_id,
        energy=float(config["repeat"]),
        previous_energy=float(config["repeat_previous"]),
    )
    primary_raw = encoded(primary_raw_value)
    repeat_raw = encoded(repeat_raw_value)
    primary_raw_artifact = artifact(
        relative_path="backend-raw-result.json",
        role="backend_raw_result",
        media_type="application/json",
        raw=primary_raw,
    )
    repeat_raw_artifact = artifact(
        relative_path="backend-repeat-raw-result.json",
        role="backend_repeat_raw_result",
        media_type="application/json",
        raw=repeat_raw,
    )

    primary_stdout = f"{name} primary ok\n".encode()
    primary_stderr = f"{name} primary log\n".encode()
    repeat_stdout = f"{name} repeat ok\n".encode()
    repeat_stderr = f"{name} repeat log\n".encode()
    execution = {
        "schema_version": "tn-agent.execution-evidence.v1",
        "status": "succeeded",
        "return_code": 0,
        "execution_handle": config["primary_handle"],
        "retryable": False,
        "stdout_digest": file_digest(primary_stdout),
        "stderr_digest": file_digest(primary_stderr),
        "stdout_truncated": False,
        "stderr_truncated": False,
    }
    repeat_execution = {
        "schema_version": "tn-agent.execution-evidence.v1",
        "status": "succeeded",
        "return_code": 0,
        "execution_handle": config["repeat_handle"],
        "retryable": False,
        "stdout_digest": file_digest(repeat_stdout),
        "stderr_digest": file_digest(repeat_stderr),
        "stdout_truncated": False,
        "stderr_truncated": False,
    }
    binding = experiment["backend_binding"]
    assert isinstance(binding, dict)
    primary_bundle = gate._reconstruct_backend_bundle(
        request_digest=request_digest,
        binding=binding,
        raw=primary_raw_value,
        execution=execution,
        raw_artifact=primary_raw_artifact,
    )
    repeat_bundle = gate._reconstruct_backend_bundle(
        request_digest=request_digest,
        binding=binding,
        raw=repeat_raw_value,
        execution=repeat_execution,
        raw_artifact=repeat_raw_artifact,
    )
    primary_bundle_raw = encoded(primary_bundle)
    repeat_bundle_raw = encoded(repeat_bundle)
    primary_bundle_artifact = artifact(
        relative_path="backend-result.json",
        role="backend_result",
        media_type="application/json",
        raw=primary_bundle_raw,
    )
    repeat_bundle_artifact = artifact(
        relative_path="backend-repeat-result.json",
        role="backend_repeat_result",
        media_type="application/json",
        raw=repeat_bundle_raw,
    )

    validator_results = gate._derived_validator_results(
        primary_raw_value,
        repeat_raw=repeat_raw_value,
        reference=reference_record,
    )
    validator_evidence = semantic(
        {
            "schema_version": "wangtheophys.tn-validator-evidence.v1",
            "request_digest": request_digest,
            "backend_result_digest": primary_bundle["result_digest"],
            "repeat_backend_result_digest": repeat_bundle["result_digest"],
            "reference_artifact_digest": file_digest(reference_raw),
            "results": validator_results,
        }
    )
    validator_raw = encoded(validator_evidence)
    validator_artifact = artifact(
        relative_path="validator-evidence.json",
        role="validator_evidence",
        media_type="application/json",
        raw=validator_raw,
    )

    artifacts = [
        artifact(
            relative_path="backend-request.json",
            role="backend_request",
            media_type="application/json",
            raw=request_raw,
        ),
        primary_raw_artifact,
        primary_bundle_artifact,
        repeat_raw_artifact,
        repeat_bundle_artifact,
        artifact(
            relative_path="energy-reference.json",
            role="energy_reference",
            media_type="application/json",
            raw=reference_raw,
        ),
        validator_artifact,
        artifact(
            relative_path="backend-stdout.log",
            role="backend_stdout",
            media_type="text/plain",
            raw=primary_stdout,
        ),
        artifact(
            relative_path="backend-stderr.log",
            role="backend_stderr",
            media_type="text/plain",
            raw=primary_stderr,
        ),
        artifact(
            relative_path="backend-repeat-stdout.log",
            role="backend_repeat_stdout",
            media_type="text/plain",
            raw=repeat_stdout,
        ),
        artifact(
            relative_path="backend-repeat-stderr.log",
            role="backend_repeat_stderr",
            media_type="text/plain",
            raw=repeat_stderr,
        ),
    ]
    observable_statuses = gate.ROUTES[str(binding["capability_id"])][
        "observable_statuses"
    ]
    assert isinstance(observable_statuses, dict)
    validators = experiment["validators"]
    assert isinstance(validators, list)
    metrics = {str(item["id"]): item["value"] for item in validator_results}
    public_validator_results: list[dict[str, object]] = []
    for validator in validators:
        assert isinstance(validator, dict)
        policy = validator["policy"]
        if policy == "required_pass":
            status = "pass"
            reason_code = "VALIDATOR_PASS"
        elif policy == "reported_only":
            status = "reported_only"
            reason_code = "REPORTED_ONLY"
        else:
            status = "backend_limited"
            reason_code = "BACKEND_LIMITED"
        public_validator_results.append(
            {
                "id": validator["id"],
                "status": status,
                "reason_code": reason_code,
                "metric_value": metrics[str(validator["id"])],
                "evidence_digest": validator_artifact["digest"],
            }
        )
    evidence = semantic(
        {
            "schema_version": "wangtheophys.tn-evidence.v1",
            "experiment_digest": experiment_digest,
            "binding": binding,
            "execution": execution,
            "repeat_execution": repeat_execution,
            "artifacts": artifacts,
            "observables": [
                {
                    "name": name,
                    "status": observable_statuses[name],
                    "evidence_digest": primary_bundle_artifact["digest"],
                }
                for name in experiment["observables"]
            ],
            "validator_results": public_validator_results,
            "provenance": {
                "plan_id": plan_id,
                "request_digest": request_digest,
                "backend_result_digest": primary_bundle_artifact["digest"],
                "repeat_backend_result_digest": repeat_bundle_artifact["digest"],
                "generated_by": "fixtures/regenerate.py",
                "generated_at": "2026-07-29T00:01:00Z",
            },
        }
    )

    files = {
        "backend-request.json": request_raw,
        "backend-raw-result.json": primary_raw,
        "backend-result.json": primary_bundle_raw,
        "backend-repeat-raw-result.json": repeat_raw,
        "backend-repeat-result.json": repeat_bundle_raw,
        "energy-reference.json": reference_raw,
        "validator-evidence.json": validator_raw,
        "backend-stdout.log": primary_stdout,
        "backend-stderr.log": primary_stderr,
        "backend-repeat-stdout.log": repeat_stdout,
        "backend-repeat-stderr.log": repeat_stderr,
    }
    for relative_path, raw in files.items():
        (artifact_root / relative_path).write_bytes(raw)
    (fixture_root / "evidence.json").write_bytes(encoded(evidence))


def main() -> int:
    for name, config in CONFIG.items():
        write_fixture(name, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
