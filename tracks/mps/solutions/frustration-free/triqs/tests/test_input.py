import copy
import json
from pathlib import Path
import sys

import pytest


TRIQS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TRIQS_DIR.parents[4]
sys.path.insert(0, str(TRIQS_DIR))

from artifacts import canonical_json, sha256_bytes, strict_json_load
from make_input import (
    COMMON_REAL_FREQUENCY,
    COMMON_REAL_FREQUENCY_SHA256,
    make_production_input,
    verify_input,
    write_production_input,
)
from source_manifest import REQUIRED_SOURCE_PATHS, build_source_manifest


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _complete_repository(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    root = tmp_path / "repository"
    solution_dir = root / "tracks/mps/solutions/frustration-free/triqs"
    for relative in REQUIRED_SOURCE_PATHS:
        source = REPOSITORY_ROOT / relative
        _write(root / relative, source.read_bytes() if source.is_file() else b"fixture\n")

    model_source = REPOSITORY_ROOT / "tracks/mps/solutions/frustration-free/model.json"
    _write(root / "tracks/mps/solutions/frustration-free/model.json", model_source.read_bytes())

    manifest = build_source_manifest(root)
    calibration_payload = {
        "artifact_type": "cthyb_calibration",
        "schema_version": 2,
        "status": "accepted",
        "model": {
            "model_id": "challenge-81-spinful-anderson-semicircular",
            "D": 1.0,
            "U": 0.8,
            "Gamma": 0.1,
            "epsilon_d": -0.4,
            "mu": 0.0,
            "beta": 16.0,
        },
        "source_manifest": manifest,
        "source_manifest_sha256": sha256_bytes(canonical_json(manifest)),
        "conda_lock_sha256": manifest[
            "tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock"
        ],
        "environment_yml_sha256": manifest[
            "tracks/mps/solutions/frustration-free/triqs/environment.yml"
        ],
        "model_json_sha256": manifest[
            "tracks/mps/solutions/frustration-free/model.json"
        ],
    }
    calibration = {
        "payload": calibration_payload,
        "sha256": sha256_bytes(canonical_json(calibration_payload)),
    }
    _write(
        solution_dir / "calibration.json",
        canonical_json(calibration) + b"\n",
    )
    return solution_dir, calibration


def test_canonical_json_is_sorted_compact_finite_and_has_no_newline():
    assert canonical_json({"z": 1, "a": [2.0]}) == b'{"a":[2.0],"z":1}'
    with pytest.raises(ValueError, match="finite"):
        canonical_json({"bad": float("nan")})
    with pytest.raises(ValueError, match="finite"):
        canonical_json({"bad": float("inf")})


def test_strict_json_rejects_duplicate_keys_and_nonstandard_numbers(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a":1,"a":2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        strict_json_load(duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a":NaN}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        strict_json_load(nonfinite)


def test_two_clean_generations_are_identical_and_fully_bound(tmp_path):
    solution_dir, calibration = _complete_repository(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    artifact = write_production_input(first, solution_dir)
    write_production_input(second, solution_dir)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == canonical_json(artifact) + b"\n"
    assert first.read_bytes().endswith(b"\n")
    assert not first.read_bytes().endswith(b"\n\n")
    assert artifact["sha256"] == sha256_bytes(canonical_json(artifact["payload"]))

    payload = verify_input(artifact, solution_dir)
    assert payload["model"] == {
        "model_id": "challenge-81-spinful-anderson-semicircular",
        "D": 1.0,
        "U": 0.8,
        "Gamma": 0.1,
        "epsilon_d": -0.4,
        "mu": 0.0,
        "beta": 16.0,
    }
    assert payload["chains"]["seeds"] == [810001, 810002, 810003, 810004]
    assert len(set(payload["chains"]["seeds"])) == 4
    assert payload["meshes"]["reported_tau"] == [0.0, 4.0, 8.0, 12.0, 16.0]
    assert [
        round(tau * (payload["meshes"]["n_tau"] - 1) / payload["model"]["beta"])
        for tau in payload["meshes"]["reported_tau"]
    ] == [0, 1000, 2000, 3000, 4000]
    assert payload["hybridization"]["common_real_frequency"] == {
        **COMMON_REAL_FREQUENCY,
        "sha256": COMMON_REAL_FREQUENCY_SHA256,
    }
    assert COMMON_REAL_FREQUENCY_SHA256 == (
        "d424a7438f1b7da8938256f2cae9812a2b52c737d34f6026453ca4aa15f55b0f"
    )

    omega = payload["hybridization"]["matsubara_omega"]
    delta = payload["hybridization"]["delta_iw"]
    assert len(omega) == len(delta["real"]) == len(delta["imag"]) == 4098
    assert all(value == 0.0 for value in delta["real"])
    assert omega == sorted(omega)
    assert delta["sha256"] == sha256_bytes(
        canonical_json({"real": delta["real"], "imag": delta["imag"]})
    )
    assert payload["calibration"]["artifact_sha256"] == calibration["sha256"]

    provenance = payload["provenance_inputs"]
    assert provenance["source_manifest"] == build_source_manifest(solution_dir.parents[4])
    assert provenance["source_manifest_sha256"] == sha256_bytes(
        canonical_json(provenance["source_manifest"])
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), 1),
        (("chains", "count"), True),
        (("chains", "seeds"), [810004, 810003, 810002, 810001]),
        (("provenance_inputs", "conda_lock_sha256"), "0" * 64),
    ],
)
def test_verifier_rejects_schema_seed_boolean_and_placeholder_mutations(
    tmp_path, path, value
):
    solution_dir, _ = _complete_repository(tmp_path)
    artifact = make_production_input(solution_dir)
    mutated = copy.deepcopy(artifact)
    target = mutated["payload"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    mutated["sha256"] = sha256_bytes(canonical_json(mutated["payload"]))
    with pytest.raises(ValueError):
        verify_input(mutated, solution_dir)


def test_verifier_rejects_unknown_keys_and_changed_model(tmp_path):
    solution_dir, _ = _complete_repository(tmp_path)
    artifact = make_production_input(solution_dir)
    for mutate in (
        lambda value: value["payload"].update({"unknown": 1}),
        lambda value: value["payload"]["model"].update({"U": 0.9}),
    ):
        changed = copy.deepcopy(artifact)
        mutate(changed)
        changed["sha256"] = sha256_bytes(canonical_json(changed["payload"]))
        with pytest.raises(ValueError):
            verify_input(changed, solution_dir)


def test_manifest_rejects_missing_extra_and_changed_sources(tmp_path):
    solution_dir, _ = _complete_repository(tmp_path)
    artifact = make_production_input(solution_dir)
    root = solution_dir.parents[4]

    missing = copy.deepcopy(artifact)
    missing["payload"]["provenance_inputs"]["source_manifest"].pop(
        REQUIRED_SOURCE_PATHS[0]
    )
    missing["sha256"] = sha256_bytes(canonical_json(missing["payload"]))
    with pytest.raises(ValueError, match="manifest"):
        verify_input(missing, solution_dir)

    extra = copy.deepcopy(artifact)
    extra["payload"]["provenance_inputs"]["source_manifest"]["extra.py"] = "1" * 64
    extra["sha256"] = sha256_bytes(canonical_json(extra["payload"]))
    with pytest.raises(ValueError, match="manifest"):
        verify_input(extra, solution_dir)

    (root / REQUIRED_SOURCE_PATHS[0]).write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="hash"):
        verify_input(artifact, solution_dir)


def test_atomic_publication_reuses_identical_and_rejects_different(tmp_path):
    solution_dir, _ = _complete_repository(tmp_path)
    output = tmp_path / "cthyb-input.json"
    artifact = write_production_input(output, solution_dir)
    assert write_production_input(output, solution_dir) == artifact
    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="different"):
        write_production_input(output, solution_dir)


def test_real_generation_fails_until_transitive_sources_exist():
    missing = [
        relative
        for relative in REQUIRED_SOURCE_PATHS
        if not (REPOSITORY_ROOT / relative).is_file()
    ]
    assert missing
    with pytest.raises(FileNotFoundError, match="required source"):
        make_production_input(TRIQS_DIR)


def test_schema_one_remains_permanently_nonproduction():
    schema = json.loads((TRIQS_DIR / "cthyb-production.schema.json").read_text())
    assert "non-production" in schema["$comment"].lower()
    assert schema["properties"]["production_ready"] == {"const": False}
    assert schema["properties"]["scientific_comparison"] == {"const": False}
