"""Generate and verify the canonical Challenge 81 CT-HYB production input."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from jsonschema import Draft202012Validator

from artifacts import (
    atomic_write_bytes,
    canonical_json,
    sha256_bytes,
    strict_json_load,
)
from source_manifest import build_source_manifest, verify_source_manifest


SCHEMA_VERSION = 2
N_IW = 2049
N_TAU = 4001
BETA = 16.0
COMMON_REAL_FREQUENCY = {
    "omega": [-1.0, 0.0, 1.0],
    "Gamma": [0.0, 0.1, 0.0],
}
COMMON_REAL_FREQUENCY_SHA256 = sha256_bytes(
    canonical_json(COMMON_REAL_FREQUENCY)
)
_MODEL = {
    "model_id": "challenge-81-spinful-anderson-semicircular",
    "D": 1.0,
    "U": 0.8,
    "Gamma": 0.1,
    "epsilon_d": -0.4,
    "mu": 0.0,
    "beta": BETA,
}
_MODEL_ASSERTIONS = {
    "spin_symmetric": True,
    "grand_canonical": True,
    "spin_qn_enabled": False,
}
_MODEL_CONVENTIONS = {
    "hamiltonian": (
        "K = (epsilon_d-mu) sum_sigma n_dsigma + U n_dup n_ddown + "
        "sum_k,sigma (epsilon_k-mu) n_ksigma + sum_k,sigma V_k "
        "(d_sigma^dag c_ksigma + h.c.)"
    ),
    "green_function": (
        "G_sigma(tau) = -Tr[exp(-(beta-tau)K) d_sigma exp(-tau K) "
        "d_sigma^dag] / Z"
    ),
    "hybridization": (
        "Gamma(omega) = pi * sum_k V_k^2 * delta(omega - epsilon_k)"
    ),
    "quadrature": "Gauss-Chebyshev quadrature of the second kind",
    "target_continuum": (
        "Gamma_target(omega) = gamma * sqrt(1 - (omega / bandwidth)^2) "
        "for |omega| <= bandwidth; 0 otherwise"
    ),
    "ordering": "k = 1..n_bath; epsilon in descending order",
    "epsilon": "bandwidth * cos(k * pi / (n_bath + 1))",
    "V_squared": (
        "gamma * bandwidth / (n_bath + 1) * "
        "sin(k * pi / (n_bath + 1))^2"
    ),
    "gamma_normalization": (
        "pi * sum_k V_k^2 = pi * gamma * bandwidth / 2"
    ),
}
_TRIQS_RELATIVE = Path("tracks/mps/solutions/frustration-free/triqs")


def _repository_root(solution_dir: Path) -> Path:
    resolved = solution_dir.resolve()
    if resolved.as_posix().endswith(_TRIQS_RELATIVE.as_posix()):
        return resolved.parents[4]
    raise ValueError(f"unexpected CT-HYB solution directory: {solution_dir}")


def _load_model(solution_dir: Path) -> tuple[dict[str, object], dict[str, str]]:
    model_path = solution_dir.parent / "model.json"
    value = strict_json_load(model_path)
    expected = {
        "schema_version": 1,
        "model_id": _MODEL["model_id"],
        "parameters": {
            "D": 1.0,
            "U": 0.8,
            "Gamma": 0.1,
            "epsilon_d": -0.4,
            "mu": 0.0,
        },
        "assertions": _MODEL_ASSERTIONS,
        "conventions": _MODEL_CONVENTIONS,
    }
    if canonical_json(value) != canonical_json(expected):
        raise ValueError(
            "model.json physics, assertions, or conventions disagree with "
            "the authoritative production model"
        )
    return dict(_MODEL), dict(_MODEL_CONVENTIONS)


def _production_conventions(
    model_conventions: dict[str, str],
) -> dict[str, str]:
    return {
        "green_function": model_conventions["green_function"],
        "hybridization_spectrum": "Gamma(omega) = -Im Delta^R(omega)",
        "matsubara_transform": (
            "Delta(z) = integral_-D^D d epsilon Gamma(epsilon) / "
            "(pi * (z-epsilon))"
        ),
        "noninteracting_inverse": (
            "G0_sigma^-1(z) = z + mu - epsilon_d - Delta(z)"
        ),
    }


def _matsubara_data() -> tuple[list[float], dict[str, object]]:
    omega = [(2 * index + 1) * math.pi / BETA for index in range(-N_IW, N_IW)]
    imaginary = [
        0.1
        * (
            value
            - math.copysign(math.sqrt(value * value + 1.0), value)
        )
        for value in omega
    ]
    split: dict[str, object] = {
        "real": [0.0] * len(omega),
        "imag": imaginary,
    }
    split["sha256"] = sha256_bytes(canonical_json(split))
    return omega, split


def _validate_calibration(
    calibration: object,
    *,
    source_manifest: dict[str, str],
) -> str:
    if not isinstance(calibration, dict) or set(calibration) != {"payload", "sha256"}:
        raise ValueError("calibration artifact must contain only payload and sha256")
    payload = calibration["payload"]
    digest = calibration["sha256"]
    if not isinstance(payload, dict) or not isinstance(digest, str):
        raise ValueError("invalid calibration artifact")
    if digest != sha256_bytes(canonical_json(payload)) or digest == "0" * 64:
        raise ValueError("calibration payload hash mismatch")
    required = {
        "artifact_type",
        "schema_version",
        "status",
        "model",
        "source_manifest",
        "source_manifest_sha256",
        "conda_lock_sha256",
        "environment_yml_sha256",
        "model_json_sha256",
    }
    if set(payload) != required:
        raise ValueError("calibration payload has unexpected keys")
    if (
        payload["artifact_type"] != "cthyb_calibration"
        or payload["schema_version"] != 2
        or payload["status"] != "accepted"
        or canonical_json(payload["model"]) != canonical_json(_MODEL)
        or canonical_json(payload["source_manifest"])
        != canonical_json(source_manifest)
        or payload["source_manifest_sha256"]
        != sha256_bytes(canonical_json(source_manifest))
    ):
        raise ValueError("calibration is not accepted for this production input")
    expected_hashes = _provenance_hashes(source_manifest)
    for key, expected in expected_hashes.items():
        if key != "source_manifest" and key != "source_manifest_sha256":
            if payload[key] != expected:
                raise ValueError(f"calibration provenance mismatch: {key}")
    return digest


def _provenance_hashes(source_manifest: dict[str, str]) -> dict[str, object]:
    prefix = "tracks/mps/solutions/frustration-free"
    return {
        "source_manifest": source_manifest,
        "source_manifest_sha256": sha256_bytes(canonical_json(source_manifest)),
        "conda_lock_sha256": source_manifest[
            f"{prefix}/triqs/conda-linux-64.lock"
        ],
        "environment_yml_sha256": source_manifest[
            f"{prefix}/triqs/environment.yml"
        ],
        "model_json_sha256": source_manifest[f"{prefix}/model.json"],
    }


def _build_input(
    solution_dir: Path,
    calibration: object,
) -> dict[str, object]:
    repository_root = _repository_root(solution_dir)
    model, model_conventions = _load_model(solution_dir)
    source_manifest = build_source_manifest(repository_root)
    calibration_sha256 = _validate_calibration(
        calibration,
        source_manifest=source_manifest,
    )
    omega, delta = _matsubara_data()
    common = {
        **COMMON_REAL_FREQUENCY,
        "sha256": COMMON_REAL_FREQUENCY_SHA256,
    }
    payload: dict[str, object] = {
        "artifact_type": "cthyb_production_input",
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "conventions": _production_conventions(model_conventions),
        "hybridization": {
            "kind": "analytic_semicircle",
            "formula": (
                "Delta(iw) = i*(Gamma/D)*(w-sign(w)*sqrt(w*w+D*D))"
            ),
            "dtype": "complex128",
            "n_iw": N_IW,
            "matsubara_omega": omega,
            "delta_iw": delta,
            "common_real_frequency": common,
        },
        "meshes": {
            "n_tau": N_TAU,
            "reported_tau": [0.0, 4.0, 8.0, 12.0, 16.0],
        },
        "chains": {
            "count": 4,
            "random_generator": "mt19937",
            "master_seed": 810000,
            "seeds": [810001, 810002, 810003, 810004],
        },
        "monte_carlo": {
            "warmup_cycles": 50000,
            "measurement_cycles": 1000000,
            "cycle_length": 50,
            "measure_G_tau": True,
            "measure_density_matrix": True,
            "use_norm_as_weight": True,
            "measure_pert_order": True,
        },
        "gates": {
            "minimum_average_sign": 0.99,
            "require_autocorrelation_converged": True,
            "maximum_integrated_autocorrelation_cycles": 5.0,
            "minimum_effective_samples_per_chain": 100000,
            "minimum_effective_samples_total": 400000,
            "maximum_spin_asymmetry": 0.005,
            "maximum_half_filling_error": 0.005,
            "minimum_completed_chains": 4,
        },
        "runtime": {
            "mpi_ranks_per_chain": 1,
            "threads_per_rank": 1,
        },
        "calibration": {"artifact_sha256": calibration_sha256},
        "provenance_inputs": _provenance_hashes(source_manifest),
    }
    artifact: dict[str, object] = {
        "payload": payload,
        "sha256": sha256_bytes(canonical_json(payload)),
    }
    verify_input(artifact, solution_dir)
    return artifact


def make_production_input(solution_dir: Path) -> dict[str, object]:
    calibration_path = solution_dir / "calibration.json"
    # Manifest construction intentionally happens first, so the real tree
    # fails on absent later-task sources before anyone can create input.
    build_source_manifest(_repository_root(solution_dir))
    return _build_input(solution_dir, strict_json_load(calibration_path))


def _schema(solution_dir: Path) -> dict[str, object]:
    value = strict_json_load(solution_dir / "cthyb-production-input.schema.json")
    if not isinstance(value, dict):
        raise ValueError("production input schema must be an object")
    Draft202012Validator.check_schema(value)
    return value


def _require_finite(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("input contains a non-finite number")
    if isinstance(value, dict):
        for item in value.values():
            _require_finite(item)
    elif isinstance(value, list):
        for item in value:
            _require_finite(item)


def verify_input(
    artifact: object,
    solution_dir: Path | None = None,
) -> dict[str, object]:
    directory = solution_dir or Path(__file__).resolve().parent
    _require_finite(artifact)
    validator = Draft202012Validator(_schema(directory))
    errors = sorted(validator.iter_errors(artifact), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"production input schema validation failed: {errors[0].message}")
    assert isinstance(artifact, dict)
    payload = artifact["payload"]
    assert isinstance(payload, dict)
    if artifact["sha256"] != sha256_bytes(canonical_json(payload)):
        raise ValueError("production input payload hash mismatch")

    repository_root = _repository_root(directory)
    model, model_conventions = _load_model(directory)
    provenance = payload["provenance_inputs"]
    assert isinstance(provenance, dict)
    manifest = provenance["source_manifest"]
    verify_source_manifest(manifest, repository_root)
    assert isinstance(manifest, dict)
    expected_provenance = _provenance_hashes(manifest)
    if provenance != expected_provenance:
        raise ValueError("production input provenance hash mismatch")

    expected_omega, expected_delta = _matsubara_data()
    expected_payload = {
        "artifact_type": "cthyb_production_input",
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "conventions": _production_conventions(model_conventions),
        "hybridization": {
            "kind": "analytic_semicircle",
            "formula": (
                "Delta(iw) = i*(Gamma/D)*(w-sign(w)*sqrt(w*w+D*D))"
            ),
            "dtype": "complex128",
            "n_iw": N_IW,
            "matsubara_omega": expected_omega,
            "delta_iw": expected_delta,
            "common_real_frequency": {
                **COMMON_REAL_FREQUENCY,
                "sha256": sha256_bytes(canonical_json(COMMON_REAL_FREQUENCY)),
            },
        },
        "meshes": {
            "n_tau": N_TAU,
            "reported_tau": [0.0, 4.0, 8.0, 12.0, 16.0],
        },
        "chains": {
            "count": 4,
            "random_generator": "mt19937",
            "master_seed": 810000,
            "seeds": [810001, 810002, 810003, 810004],
        },
        "monte_carlo": {
            "warmup_cycles": 50000,
            "measurement_cycles": 1000000,
            "cycle_length": 50,
            "measure_G_tau": True,
            "measure_density_matrix": True,
            "use_norm_as_weight": True,
            "measure_pert_order": True,
        },
        "gates": {
            "minimum_average_sign": 0.99,
            "require_autocorrelation_converged": True,
            "maximum_integrated_autocorrelation_cycles": 5.0,
            "minimum_effective_samples_per_chain": 100000,
            "minimum_effective_samples_total": 400000,
            "maximum_spin_asymmetry": 0.005,
            "maximum_half_filling_error": 0.005,
            "minimum_completed_chains": 4,
        },
        "runtime": {
            "mpi_ranks_per_chain": 1,
            "threads_per_rank": 1,
        },
        "calibration": payload["calibration"],
        "provenance_inputs": expected_provenance,
    }
    if canonical_json(payload) != canonical_json(expected_payload):
        raise ValueError(
            "production input differs from canonical intended values or encodings"
        )
    return payload


def _publish_input(
    path: Path,
    solution_dir: Path,
    calibration: object,
) -> dict[str, object]:
    artifact = _build_input(solution_dir, calibration)
    encoded = canonical_json(artifact) + b"\n"
    atomic_write_bytes(path, encoded)
    verify_input(strict_json_load(path), solution_dir)
    return artifact


def write_production_input(
    path: Path,
    solution_dir: Path,
) -> dict[str, object]:
    return _publish_input(
        path,
        solution_dir,
        strict_json_load(solution_dir / "calibration.json"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--expected-calibration-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    solution_dir = Path(__file__).resolve().parent
    calibration = strict_json_load(arguments.calibration)
    if (
        not isinstance(calibration, dict)
        or calibration.get("sha256") != arguments.expected_calibration_sha256
    ):
        raise ValueError("calibration digest does not match the expected digest")
    _publish_input(arguments.output, solution_dir, calibration)


if __name__ == "__main__":
    main()
