import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock


TRIQS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TRIQS_DIR.parents[4]
sys.path.insert(0, str(TRIQS_DIR))

from artifacts import (
    atomic_write_bytes,
    canonical_json,
    sha256_bytes,
    sha256_file,
    strict_json_load,
)
from make_input import (
    COMMON_REAL_FREQUENCY,
    COMMON_REAL_FREQUENCY_SHA256,
    make_production_input,
    verify_input,
    write_production_input,
)
from source_manifest import REQUIRED_SOURCE_PATHS, build_source_manifest
import make_input as make_input_module
from calibrate import (
    OBSERVABLES,
    analyze_estimator_qualification,
    build_calibration_artifact,
    build_calibration_plan,
    build_estimator_plan,
)


_ASSERTIONS = unittest.TestCase()


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
    model = {
            "model_id": "challenge-81-spinful-anderson-semicircular",
            "D": 1.0,
            "U": 0.8,
            "Gamma": 0.1,
            "epsilon_d": -0.4,
            "mu": 0.0,
            "beta": 16.0,
        }
    bindings = {
        "model": model,
        "meshes": {"n_iw": 2049, "n_tau": 12297},
        "formulas": {
            "delta_iw": "Delta(iw) = i*(Gamma/D)*(w-sign(w)*sqrt(w*w+D*D))"
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
    estimator_plan = build_estimator_plan(bindings, measurement_cycles=1_000_000)
    estimator_results = []
    for cell_artifact in estimator_plan["payload"]["cells"]:
        cell = dict(cell_artifact["payload"])
        cell["truncated_values"] = {
            str(cutoff): {name: 0.0 for name in OBSERVABLES}
            for cutoff in cell["cutoffs"]
        }
        estimator_results.append(
            {"payload": cell, "sha256": sha256_bytes(canonical_json(cell))}
        )
    qualification = analyze_estimator_qualification(
        estimator_results, estimator_plan
    )
    plan = build_calibration_plan(bindings, qualification)
    results = []
    for cell_artifact in plan["payload"]["cells"]:
        cell = dict(cell_artifact["payload"])
        if cell["cell_kind"] in {"warmup", "increment"}:
            cell["values"] = {name: 0.0 for name in OBSERVABLES}
        else:
            cell["auto_corr_time"] = 1.0
            cell["auto_corr_time_converged"] = True
        results.append({"payload": cell, "sha256": sha256_bytes(canonical_json(cell))})
    calibration = build_calibration_artifact(plan, results)
    _write(
        solution_dir / "calibration.json",
        canonical_json(calibration) + b"\n",
    )
    return solution_dir, calibration


def test_canonical_json_is_sorted_compact_finite_and_has_no_newline():
    assert canonical_json({"z": 1, "a": [2.0]}) == b'{"a":[2.0],"z":1}'
    with _ASSERTIONS.assertRaisesRegex(ValueError, "finite"):
        canonical_json({"bad": float("nan")})
    with _ASSERTIONS.assertRaisesRegex(ValueError, "finite"):
        canonical_json({"bad": float("inf")})


def test_strict_json_rejects_duplicate_keys_and_nonstandard_numbers(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a":1,"a":2}\n', encoding="utf-8")
    with _ASSERTIONS.assertRaisesRegex(ValueError, "duplicate"):
        strict_json_load(duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a":NaN}\n', encoding="utf-8")
    with _ASSERTIONS.assertRaisesRegex(ValueError, "non-finite"):
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
    ] == [0, 3074, 6148, 9222, 12296]
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


def test_verifier_rejects_schema_seed_boolean_and_placeholder_mutations(tmp_path):
    mutations = [
        (("schema_version",), 1),
        (("chains", "count"), True),
        (("chains", "seeds"), [810004, 810003, 810002, 810001]),
        (("provenance_inputs", "conda_lock_sha256"), "0" * 64),
    ]
    solution_dir, _ = _complete_repository(tmp_path)
    artifact = make_production_input(solution_dir)
    for path, value in mutations:
        mutated = copy.deepcopy(artifact)
        target = mutated["payload"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        mutated["sha256"] = sha256_bytes(canonical_json(mutated["payload"]))
        with _ASSERTIONS.subTest(path=path):
            with _ASSERTIONS.assertRaises(ValueError):
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
        with _ASSERTIONS.assertRaises(ValueError):
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
    with _ASSERTIONS.assertRaisesRegex(ValueError, "manifest"):
        verify_input(missing, solution_dir)

    extra = copy.deepcopy(artifact)
    extra["payload"]["provenance_inputs"]["source_manifest"]["extra.py"] = "1" * 64
    extra["sha256"] = sha256_bytes(canonical_json(extra["payload"]))
    with _ASSERTIONS.assertRaisesRegex(ValueError, "manifest"):
        verify_input(extra, solution_dir)

    (root / REQUIRED_SOURCE_PATHS[0]).write_bytes(b"changed\n")
    with _ASSERTIONS.assertRaisesRegex(ValueError, "hash"):
        verify_input(artifact, solution_dir)


def test_atomic_publication_reuses_identical_and_rejects_different(tmp_path):
    solution_dir, _ = _complete_repository(tmp_path)
    output = tmp_path / "cthyb-input.json"
    artifact = write_production_input(output, solution_dir)
    assert write_production_input(output, solution_dir) == artifact
    output.write_text("{}\n", encoding="utf-8")
    with _ASSERTIONS.assertRaisesRegex(FileExistsError, "different"):
        write_production_input(output, solution_dir)


def test_hashing_traverses_execute_only_cluster_parent(tmp_path):
    parent = tmp_path / "execute-only"
    child = parent / "owned"
    child.mkdir(parents=True)
    target = child / "value.bin"
    target.write_bytes(b"cluster")
    os.chmod(parent, 0o111)
    try:
        assert sha256_file(target) == sha256(b"cluster").hexdigest()
    finally:
        os.chmod(parent, 0o700)


def test_real_tree_has_complete_transitive_sources_and_still_requires_calibration():
    missing = [
        relative
        for relative in REQUIRED_SOURCE_PATHS
        if not (REPOSITORY_ROOT / relative).is_file()
    ]
    assert missing == []
    manifest = build_source_manifest(REPOSITORY_ROOT)
    assert set(manifest) == set(REQUIRED_SOURCE_PATHS)
    with _ASSERTIONS.assertRaisesRegex(FileNotFoundError, "calibration.json"):
        make_production_input(TRIQS_DIR)


def test_solver_mesh_satisfies_real_triqs_constructor_and_reported_nodes():
    import make_input

    assert make_input.N_TAU >= 6 * make_input.N_IW
    assert (make_input.N_TAU - 1) % 4 == 0


def test_schema_one_remains_permanently_nonproduction():
    schema = json.loads((TRIQS_DIR / "cthyb-production.schema.json").read_text())
    assert "non-production" in schema["$comment"].lower()
    assert schema["properties"]["production_ready"] == {"const": False}
    assert schema["properties"]["scientific_comparison"] == {"const": False}


def _refresh_calibration(solution_dir: Path) -> None:
    manifest = build_source_manifest(solution_dir.parents[4])
    model = json.loads((solution_dir.parent / "model.json").read_text(encoding="utf-8"))
    payload = {
        "artifact_type": "cthyb_calibration",
        "schema_version": 2,
        "status": "accepted",
        "model": {
            "model_id": model["model_id"],
            **model["parameters"],
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
    artifact = {"payload": payload, "sha256": sha256_bytes(canonical_json(payload))}
    _write(solution_dir / "calibration.json", canonical_json(artifact) + b"\n")


class InputHardeningTests(unittest.TestCase):
    def test_matsubara_generation_uses_shared_hybridization_contract(self):
        from hybridization import (
            delta_iw as analytic_delta_iw,
            serialize_complex128 as analytic_serialize_complex128,
        )

        with mock.patch.object(
            make_input_module,
            "delta_iw",
            wraps=analytic_delta_iw,
        ) as delta_mock, mock.patch.object(
            make_input_module,
            "serialize_complex128",
            wraps=analytic_serialize_complex128,
        ) as serialize_mock:
            omega, serialized = make_input_module._matsubara_data()

        delta_mock.assert_called_once()
        serialize_mock.assert_called_once()
        self.assertEqual(len(omega), 4098)
        self.assertEqual(len(serialized["real"]), 4098)

    def test_numeric_aliases_do_not_bypass_exact_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            solution_dir, _ = _complete_repository(Path(temporary))
            artifact = make_production_input(solution_dir)
            for path, replacement in (
                (("model", "D"), 1),
                (("model", "mu"), 0),
                (("meshes", "reported_tau"), [0, 4, 8, 12, 16]),
                (
                    ("hybridization", "common_real_frequency", "omega"),
                    [-1, 0, 1],
                ),
            ):
                with self.subTest(path=path):
                    changed = copy.deepcopy(artifact)
                    target = changed["payload"]
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = replacement
                    changed["sha256"] = sha256_bytes(canonical_json(changed["payload"]))
                    with self.assertRaises(ValueError):
                        verify_input(changed, solution_dir)

    def test_all_embedded_digests_are_recomputed(self):
        with tempfile.TemporaryDirectory() as temporary:
            solution_dir, _ = _complete_repository(Path(temporary))
            artifact = make_production_input(solution_dir)
            stale_top_level = copy.deepcopy(artifact)
            stale_top_level["sha256"] = "1" * 64
            with self.assertRaises(ValueError):
                verify_input(stale_top_level, solution_dir)

            digest_paths = (
                ("hybridization", "delta_iw", "sha256"),
                ("hybridization", "common_real_frequency", "sha256"),
                ("provenance_inputs", "source_manifest_sha256"),
                ("provenance_inputs", "conda_lock_sha256"),
                ("provenance_inputs", "environment_yml_sha256"),
                ("provenance_inputs", "model_json_sha256"),
            )
            for path in digest_paths:
                with self.subTest(path=path):
                    changed = copy.deepcopy(artifact)
                    target = changed["payload"]
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = "1" * 64
                    changed["sha256"] = sha256_bytes(canonical_json(changed["payload"]))
                    with self.assertRaises(ValueError):
                        verify_input(changed, solution_dir)

            alternate_delta = copy.deepcopy(artifact)
            split = alternate_delta["payload"]["hybridization"]["delta_iw"]
            split["real"] = [0] * len(split["real"])
            split["sha256"] = sha256_bytes(
                canonical_json({"real": split["real"], "imag": split["imag"]})
            )
            alternate_delta["sha256"] = sha256_bytes(
                canonical_json(alternate_delta["payload"])
            )
            with self.assertRaises(ValueError):
                verify_input(alternate_delta, solution_dir)

    def test_model_assertions_and_conventions_are_authoritative(self):
        mutations = (
            ("assertions", "spin_symmetric", False),
            ("assertions", "grand_canonical", False),
            ("assertions", "spin_qn_enabled", True),
            ("conventions", "green_function", "conflicting"),
            ("conventions", "hybridization", "conflicting"),
            ("conventions", "hamiltonian", "conflicting"),
        )
        for section, key, value in mutations:
            with self.subTest(section=section, key=key):
                with tempfile.TemporaryDirectory() as temporary:
                    solution_dir, _ = _complete_repository(Path(temporary))
                    model_path = solution_dir.parent / "model.json"
                    model = json.loads(model_path.read_text(encoding="utf-8"))
                    model[section][key] = value
                    model_path.write_text(json.dumps(model), encoding="utf-8")
                    _refresh_calibration(solution_dir)
                    with self.assertRaises(ValueError):
                        make_production_input(solution_dir)

    def test_schema_change_after_generation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            solution_dir, _ = _complete_repository(Path(temporary))
            artifact = make_production_input(solution_dir)
            schema = solution_dir / "cthyb-production-input.schema.json"
            schema.write_text(
                '{"$schema":"https://json-schema.org/draft/2020-12/schema"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "hash"):
                verify_input(artifact, solution_dir)

    def test_descriptor_read_rejects_lstat_open_symlink_swap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            victim = root / "victim"
            attacker = root / "attacker"
            victim.write_bytes(b"trusted")
            attacker.write_bytes(b"attacker")
            original_open = Path.open

            def swap_then_open(path, *args, **kwargs):
                if path == victim:
                    victim.unlink()
                    victim.symlink_to(attacker)
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", swap_then_open):
                self.assertEqual(
                    sha256_file(victim),
                    sha256(b"trusted").hexdigest(),
                )
            self.assertFalse(victim.is_symlink())

    def test_descriptor_reads_and_publication_reject_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attacker = root / "attacker"
            attacker.write_bytes(b"attacker")
            victim = root / "victim"
            victim.symlink_to(attacker)
            with self.assertRaises(ValueError):
                sha256_file(victim)
            with self.assertRaises(ValueError):
                atomic_write_bytes(victim, b"trusted")
            self.assertEqual(attacker.read_bytes(), b"attacker")

    def test_atomic_publication_never_overwrites_different_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact.json"
            atomic_write_bytes(output, b"first")
            with self.assertRaises(FileExistsError):
                atomic_write_bytes(output, b"second")
            self.assertEqual(output.read_bytes(), b"first")

    def test_concurrent_publication_has_one_winner_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact.json"
            barrier = threading.Barrier(2)
            outcomes = []

            def publish(value):
                barrier.wait()
                try:
                    atomic_write_bytes(output, value)
                    outcomes.append(("published", value))
                except FileExistsError:
                    outcomes.append(("rejected", value))

            threads = [
                threading.Thread(target=publish, args=(b"first",)),
                threading.Thread(target=publish, args=(b"second",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(
                sorted(outcome for outcome, _ in outcomes),
                ["published", "rejected"],
            )
            winner = next(value for outcome, value in outcomes if outcome == "published")
            self.assertEqual(output.read_bytes(), winner)


def load_tests(loader, tests, pattern):
    del loader, pattern
    no_fixture = (
        test_canonical_json_is_sorted_compact_finite_and_has_no_newline,
        test_real_generation_fails_until_transitive_sources_exist,
        test_schema_one_remains_permanently_nonproduction,
    )
    temporary_fixture = (
        test_strict_json_rejects_duplicate_keys_and_nonstandard_numbers,
        test_two_clean_generations_are_identical_and_fully_bound,
        test_verifier_rejects_schema_seed_boolean_and_placeholder_mutations,
        test_verifier_rejects_unknown_keys_and_changed_model,
        test_manifest_rejects_missing_extra_and_changed_sources,
        test_atomic_publication_reuses_identical_and_rejects_different,
    )
    for function in no_fixture:
        tests.addTest(unittest.FunctionTestCase(function))
    for function in temporary_fixture:
        def run_with_temporary_directory(function=function):
            with tempfile.TemporaryDirectory() as temporary:
                function(Path(temporary))

        tests.addTest(
            unittest.FunctionTestCase(
                run_with_temporary_directory,
                description=function.__name__,
            )
        )
    return tests
