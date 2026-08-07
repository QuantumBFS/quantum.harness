from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import types
from pathlib import Path

import jsonschema
import pytest

from challenge148.acceptance import (
    AcceptanceRunFailed,
    AdapterLaunchError,
    _adapter_build_info,
    _create_fd_project_view,
    _discover_julia_runtime_closure,
    _discover_python_runtime_closure,
    _parse_julia_discovery,
    _runtime_artifact_identity,
    _snapshot_authoritative_closure,
    _validate_bin_cross_fields,
    _verify_authoritative_closure,
    _adapter_request_hash,
    evaluate_adapter,
    evaluate_matrix_median,
    launch_adapter,
    run_acceptance,
    validate_acceptance_request,
    validate_archived_adapter_run,
    validate_adapter_run,
)
from challenge148.lattice import graph_sha256, honeycomb_graph, triangular_graph, write_graph_json
from challenge148.provenance import canonical_json


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
HEX_A = "a" * 64
HEX_B = "b" * 64
PREREG_SHA256 = "4a28d43824fa162eba639f32d820e5ba0500585c297858f50fbcddfa8bc76cc5"


def _settings(seed: int) -> dict[str, int]:
    return {
        "seed": seed,
        "thermalization_sweeps": 500,
        "retained_samples": 1_600,
        "thinning": 2,
        "serial_measurement_stride_samples": 1,
        "analysis_bin_length_samples": 100,
        "checkpoint_analysis_bins": 8,
    }


def acceptance_request(tmp_path: Path, *, mode: str = "scientific") -> dict:
    cells = []
    seeds = iter(range(148_001, 148_017))
    for lattice, length, graph in (
        ("honeycomb", 2, honeycomb_graph(2)),
        ("triangular", 3, triangular_graph(3)),
    ):
        graph_path = tmp_path / f"{lattice}.json"
        write_graph_json(graph, graph_path)
        for point, (beta, field) in enumerate(((0.55, 1.2), (0.8, 1.5))):
            cell_id = (
                f"{lattice}-l{length}-b{int(beta * 100):03d}-h{int(field * 100):03d}"
            )
            cells.append(
                {
                    "cell_id": cell_id,
                    "lattice": lattice,
                    "length": length,
                    "graph_path": str(graph_path.resolve()),
                    "graph_sha256": graph_sha256(graph),
                    "beta": beta,
                    "coupling": 1.0,
                    "field": field,
                    "adapters": {
                        "qmc_sse": {
                            "seed_domain": "QMC_SSE:qmc-sse-seed-v1",
                            "seed_derivation": "sha256:qmc-sse-seed-v1||u64be",
                            "chains": [_settings(next(seeds)), _settings(next(seeds))],
                        },
                        "qmc_ltfim": {
                            "seed_domain": "QMC_LTFIM:qmc-ltfim-seed-v1",
                            "seed_derivation": "sha256:qmc-ltfim-seed-v1||u64be",
                            "chains": [_settings(next(seeds)), _settings(next(seeds))],
                        },
                    },
                }
            )
    return {
        "schema_version": "acceptance-request-v1",
        "mode": mode,
        "preregistration_sha256": PREREG_SHA256,
        "launch_timeout_seconds": 600,
        "observables": [
            "energy",
            "transverse_magnetization",
            "m2",
            "m4",
            "binder_ratio",
        ],
        "thresholds": {
            "max_normalized_residual": 4,
            "median_normalized_residual": 1.5,
            "agreement_sigma": 3,
        },
        "analysis": {
            "analysis_bin_length_samples": 100,
            "serial_measurement_stride_samples": 1,
            "minimum_analysis_bin_tau_ratio": 10,
            "autocorrelation_estimator": "geyer-ips-rho0-pairs-sokal-window-c5-unbiased-autocovariance-v2",
            "binder_estimator": "delete-one-analysis-bin-jackknife-pseudovalue-v1",
        },
        "ed_oracle": "full-thermal-dense-eigensystem-v1",
        "build_closure": {
            "qmc_sse": {
                "expected_source_hash": HEX_A,
                "expected_build_hash": HEX_B,
            },
            "qmc_ltfim": {
                "expected_source_hash": HEX_B,
                "expected_build_hash": HEX_A,
            },
        },
        "cells": cells,
    }


def test_closed_schema_fixes_scientific_thresholds_and_rejects_extra_keys(tmp_path):
    request = acceptance_request(tmp_path)
    validate_acceptance_request(request)
    schema = json.loads((SCHEMAS / "acceptance.schema.json").read_text())
    weakened = json.loads(json.dumps(request))
    weakened["thresholds"]["max_normalized_residual"] = 4.1
    with pytest.raises((jsonschema.ValidationError, ValueError)):
        validate_acceptance_request(weakened)
    extra = json.loads(json.dumps(request))
    extra["unknown"] = True
    with pytest.raises((jsonschema.ValidationError, ValueError)):
        jsonschema.validate(extra, schema)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request: request.update(preregistration_sha256="0" * 64),
        lambda request: request["cells"][0].update(beta=0.54),
        lambda request: request["cells"][0]["adapters"]["qmc_sse"]["chains"][0].update(
            seed=999
        ),
        lambda request: request["cells"][0]["adapters"]["qmc_ltfim"]["chains"][0].update(
            retained_samples=3200
        ),
        lambda request: request["analysis"].update(
            serial_measurement_stride_samples=2
        ),
        lambda request: request.update(observables=["energy"]),
    ],
)
def test_scientific_request_must_exactly_match_committed_preregistration(
    tmp_path, mutate
):
    request = acceptance_request(tmp_path)
    mutate(request)
    with pytest.raises(ValueError, match="preregistration"):
        validate_acceptance_request(request)


def test_request_requires_full_matrix_and_globally_unique_adapter_seeds(tmp_path):
    request = acceptance_request(tmp_path, mode="characterization")
    request["cells"][1]["adapters"]["qmc_ltfim"]["chains"][0]["seed"] = (
        request["cells"][0]["adapters"]["qmc_sse"]["chains"][0]["seed"]
    )
    with pytest.raises(ValueError, match="seed"):
        validate_acceptance_request(request)
    request = acceptance_request(tmp_path, mode="characterization")
    request["cells"] = request["cells"][:3]
    with pytest.raises((jsonschema.ValidationError, ValueError)):
        validate_acceptance_request(request)


def test_launch_failure_is_immutably_published_then_returned_as_failure(
    tmp_path, monkeypatch
):
    request = acceptance_request(tmp_path)
    fake_info = {
        "QMC_SSE": {"info": {"source_hash": HEX_A, "build_hash": HEX_B}},
        "QMC_LTFIM": {"info": {"source_hash": HEX_B, "build_hash": HEX_A}},
    }
    monkeypatch.setattr(
        "challenge148.acceptance._absolute_owned_environment",
        lambda: (ROOT, Path(sys.executable), Path(sys.executable)),
    )
    monkeypatch.setattr(
        "challenge148.acceptance._adapter_build_info",
        lambda adapter, solution, executable, julia, timeout, **kwargs: fake_info[
            adapter
        ],
    )
    monkeypatch.setattr(
        "challenge148.acceptance._dependency_closure",
        lambda *args: {
            "schema_version": "test-dependency-closure",
            "files": {
                relative: {"sha256": HEX_A, "size": 1}
                for relative in (
                    "src/challenge148/acceptance.py",
                    "src/challenge148/statistics.py",
                    "schemas/acceptance.schema.json",
                    "scripts/run_acceptance.py",
                )
            },
        },
    )
    monkeypatch.setattr(
        "challenge148.acceptance._runtime_artifact_identity",
        lambda *args: {"schema_version": "test-runtime-identity"},
    )
    monkeypatch.setattr(
        "challenge148.acceptance._verify_runtime_artifact_identity",
        lambda *args: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "challenge148.ed",
        types.SimpleNamespace(
            exact_thermal_observables=lambda *args, **kwargs: types.SimpleNamespace(
                energy=0.0,
                transverse_magnetization=0.0,
                m2=0.0,
                m4=0.0,
                binder_ratio=0.0,
            )
        ),
    )
    launch_evidence = {
        "adapter": "QMC_SSE",
        "command": ["/owned/qmc-sse"],
        "elapsed_seconds": 1.25,
        "launch_nonce": "nonce",
        "request": {"schema_version": "qmc-request-v1"},
        "returncode": 9,
        "stderr": "broken",
        "stdout": "partial",
        "timed_out": False,
    }
    monkeypatch.setattr(
        "challenge148.acceptance.launch_adapter",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AdapterLaunchError("adapter subprocess exit 9", launch_evidence)
        ),
    )
    with pytest.raises(AcceptanceRunFailed) as caught:
        run_acceptance(request, tmp_path / "published")
    run_path = caught.value.run_path
    summary = json.loads((run_path / "summary.json").read_text())
    failure = json.loads((run_path / "failure.json").read_text())
    assert summary["passed"] is False
    assert summary["scientific_acceptance"] is False
    assert failure["error"] == "adapter subprocess exit 9"
    assert failure["launch"] == launch_evidence
    assert (run_path / "completion.json").is_file()


def test_schema_valid_prelaunch_failure_is_durably_published(tmp_path, monkeypatch):
    request = acceptance_request(tmp_path)
    monkeypatch.setitem(
        sys.modules,
        "challenge148.ed",
        types.SimpleNamespace(exact_thermal_observables=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        "challenge148.acceptance._absolute_owned_environment",
        lambda: (_ for _ in ()).throw(ValueError("owned runtime missing")),
    )
    with pytest.raises(AcceptanceRunFailed) as caught:
        run_acceptance(request, tmp_path / "prelaunch-failure")
    summary = json.loads((caught.value.run_path / "summary.json").read_text())
    failure = json.loads((caught.value.run_path / "failure.json").read_text())
    assert summary["passed"] is False
    assert summary["scientific_acceptance"] is False
    assert failure["error"] == "owned runtime missing"
    assert failure["phase"] == "prelaunch"


def test_stale_raw_root_is_durably_published_as_prelaunch_failure(
    tmp_path, monkeypatch
):
    request = acceptance_request(tmp_path)
    output_root = tmp_path / "stale-publication"
    (output_root / "raw-adapter-runs" / "fixed-nonce").mkdir(parents=True)
    monkeypatch.setitem(
        sys.modules,
        "challenge148.ed",
        types.SimpleNamespace(exact_thermal_observables=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        "challenge148.acceptance.uuid.uuid4",
        lambda: types.SimpleNamespace(hex="fixed-nonce"),
    )
    monkeypatch.setattr(
        "challenge148.acceptance._absolute_owned_environment",
        lambda: (ROOT, Path(sys.executable), Path(sys.executable)),
    )
    monkeypatch.setattr(
        "challenge148.acceptance._runtime_artifact_identity",
        lambda *args: {"schema_version": "test-runtime-identity"},
    )
    with pytest.raises(AcceptanceRunFailed) as caught:
        run_acceptance(request, output_root)
    failure = json.loads((caught.value.run_path / "failure.json").read_text())
    assert failure["phase"] == "prelaunch"
    assert failure["error"] == "stale pre-existing raw acceptance root"


def test_python_discovery_is_isolated_and_captures_file_cache_native_and_distribution(
    tmp_path, monkeypatch
):
    owned = tmp_path / "owned"
    package = owned / "site-packages" / "demo"
    package.mkdir(parents=True)
    source = package / "__init__.py"
    cache = package / "__pycache__" / "__init__.pyc"
    native = package / "native.so"
    cache.parent.mkdir()
    for path in (source, cache, native):
        path.write_bytes(path.name.encode())
    payload = {
        "schema_version": "python-science-discovery-v1",
        "authority": (
            "isolated scientific-path loaded module files and complete owning "
            "distributions under explicit owned roots"
        ),
        "owned_roots": [str(owned)],
        "module_paths": [str(source), str(cache), str(native)],
        "distribution_roots": [str(owned / "site-packages")],
        "distribution_names": ["demo"],
        "distributions": {"demo": "1.0"},
        "executable_paths": [str(source)],
        "environment": {"version": "fixture"},
    }
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", fake_run)
    monkeypatch.setitem(
        sys.modules, "arbitrary_preload", types.SimpleNamespace(__file__="/tmp/evil.py")
    )
    closure = _discover_python_runtime_closure(
        tmp_path, Path(sys.executable), timeout=1
    )
    assert seen["command"][1] == "-I"
    assert closure["module_paths"] == sorted(
        str(path.absolute()) for path in (source, cache, native)
    )
    assert "/tmp/evil.py" not in closure["module_paths"]
    assert closure["distribution_names"] == ["demo"]
    assert closure["authority"].startswith("isolated scientific-path")
    del payload["authority"]
    with pytest.raises(ValueError, match="authority"):
        _discover_python_runtime_closure(tmp_path, Path(sys.executable), timeout=1)


def test_complete_runtime_identity_accepts_closed_python_authority(
    tmp_path, monkeypatch
):
    solution = tmp_path / "solution"
    for relative in (
        "src/challenge148",
        "adapters/qmc-sse/bin",
        "adapters/qmc-sse/src",
        "adapters/qmc-ltfim/src",
    ):
        (solution / relative).mkdir(parents=True)
    fixed_files = {
        "adapters/qmc-sse/bin/qmc-sse": b"rust",
        "adapters/qmc-ltfim/bin-julia": b"julia",
        "adapters/qmc-ltfim/run_independent.jl": b"runner",
        "adapters/qmc-ltfim/src/Challenge148LTFIM.jl": b"module",
        "adapters/qmc-ltfim/Project.toml": b"project",
        "adapters/qmc-ltfim/Manifest.toml": b"manifest",
        "src/challenge148/owned.py": b"owned",
    }
    for relative, payload in fixed_files.items():
        path = solution / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    executable = solution / "adapters/qmc-sse/bin/qmc-sse"
    julia = solution / "adapters/qmc-ltfim/bin-julia"
    distribution = tmp_path / "python-dist"
    package = tmp_path / "julia-package"
    artifact = tmp_path / "julia-artifact"
    runtime = tmp_path / "julia-runtime"
    for root in (distribution, package, artifact, runtime):
        root.mkdir()
        (root / "member").write_bytes(root.name.encode())
    sysimage = runtime / "sys.so"
    sysimage.write_bytes(b"sysimage")
    python_discovery = {
        "schema_version": "python-science-discovery-v1",
        "authority": (
            "isolated scientific-path loaded module files and complete owning "
            "distributions under explicit owned roots"
        ),
        "owned_roots": [str(tmp_path), str(solution)],
        "module_paths": [str(solution / "src/challenge148/owned.py")],
        "distribution_files": [str(distribution / "member")],
        "distribution_roots": [str(distribution)],
        "distribution_names": ["fixture"],
        "distributions": {"fixture": "1.0"},
        "executable_paths": [str(julia)],
        "environment": {"version": "fixture"},
    }
    julia_discovery = {
        "schema_version": "julia-science-discovery-v1",
        "project_root": str(solution / "adapters/qmc-ltfim"),
        "depot_roots": [str(tmp_path)],
        "source_roots": [str(package)],
        "packages": {},
        "artifacts": [],
        "artifact_roots": [str(artifact)],
        "julia_root": str(runtime),
        "sysimage": str(sysimage),
        "owned_libraries": [],
        "external_abi_libraries": [],
        "authority": "fixture Julia authority",
    }
    initial = {}

    def fake_bound_discovery(runtime_identity, descriptors, project_view, timeout):
        initial["descriptors"] = tuple(descriptors.values())
        initial["temp_root"] = Path(project_view["root"])
        assert Path(
            f"/proc/self/fd/{descriptors['julia_executable']}"
        ).read_bytes() == b"julia"
        assert Path(
            f"/proc/self/fd/{descriptors['julia_project']}"
        ).read_bytes() == b"project"
        assert Path(
            f"/proc/self/fd/{descriptors['julia_manifest']}"
        ).read_bytes() == b"manifest"
        assert Path(
            f"/proc/self/fd/{descriptors['julia_module']}"
        ).read_bytes() == b"module"
        return julia_discovery

    monkeypatch.setattr(
        "challenge148.acceptance._discover_python_runtime_closure",
        lambda *args, **kwargs: python_discovery,
    )
    monkeypatch.setattr(
        "challenge148.acceptance._run_bound_julia_discovery",
        fake_bound_discovery,
    )
    monkeypatch.setattr(
        "challenge148.acceptance._dynamic_abi_metadata", lambda paths: {}
    )
    monkeypatch.setattr(
        "challenge148.acceptance._dependency_relative_paths",
        lambda: sorted(fixed_files),
    )
    monkeypatch.setattr(
        "challenge148.acceptance.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    identity = _runtime_artifact_identity(solution, executable, julia)
    assert identity["closure_boundary"]["python"] == python_discovery["authority"]
    assert identity["owned_runtime_closure"]["root_descriptors"]
    assert not initial["temp_root"].exists()
    for descriptor in initial["descriptors"]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize(
    "mutation", ["addition", "deletion", "type-change", "content"]
)
def test_authoritative_tree_membership_drift_fails_closed(tmp_path, mutation):
    root = tmp_path / "owned"
    root.mkdir()
    member = root / "member"
    member.write_bytes(b"v1")
    snapshot = _snapshot_authoritative_closure(
        [{"label": "fixture", "path": str(root.absolute())}], []
    )
    if mutation == "addition":
        (root / "added").write_bytes(b"new")
    elif mutation == "deletion":
        member.unlink()
    elif mutation == "type-change":
        member.unlink()
        member.mkdir()
    else:
        member.write_bytes(b"v2")
    with pytest.raises(ValueError, match="runtime closure drift"):
        _verify_authoritative_closure(snapshot)


def test_authoritative_symlink_retarget_escape_and_loop_fail_closed(tmp_path):
    root = tmp_path / "owned"
    root.mkdir()
    first = root / "first"
    second = root / "second"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    link = root / "current"
    link.symlink_to(first.name)
    snapshot = _snapshot_authoritative_closure(
        [{"label": "fixture", "path": str(root.absolute())}], []
    )
    link.unlink()
    link.symlink_to(second.name)
    with pytest.raises(ValueError, match="runtime closure drift"):
        _verify_authoritative_closure(snapshot)
    link.unlink()
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes authoritative roots"):
        _snapshot_authoritative_closure(
            [{"label": "fixture", "path": str(root.absolute())}], []
        )
    link.unlink()
    link.symlink_to(link.name)
    with pytest.raises(ValueError, match="symlink"):
        _snapshot_authoritative_closure(
            [{"label": "fixture", "path": str(root.absolute())}], []
        )


def test_authoritative_root_symlink_is_rejected_by_nofollow_anchor(tmp_path):
    first = tmp_path / "first-root"
    second = tmp_path / "second-root"
    first.mkdir()
    second.mkdir()
    (first / "member").write_bytes(b"one")
    (second / "member").write_bytes(b"two")
    root_link = tmp_path / "owned-root"
    root_link.symlink_to(first.name)
    with pytest.raises(ValueError, match="root"):
        _snapshot_authoritative_closure(
            [{"label": "fixture", "path": str(root_link.absolute())}],
            [],
            [str(tmp_path.absolute())],
        )


@pytest.mark.parametrize("event", ["after_entry_stat", "after_file_open"])
def test_anchored_file_race_never_accepts_outside_bytes(tmp_path, event):
    root = tmp_path / "owned"
    root.mkdir()
    member = root / "member"
    member.write_bytes(b"inside")
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside-secret")
    fired = False

    def race_hook(name, details):
        nonlocal fired
        if not fired and name == event and details.get("relative_path") == "member":
            fired = True
            member.unlink()
            member.symlink_to(outside)

    with pytest.raises(ValueError, match="runtime closure"):
        _snapshot_authoritative_closure(
            [{"label": "fixture", "path": str(root)}],
            [],
            race_hook=race_hook,
        )
    assert fired


def test_anchored_file_change_during_read_is_rejected(tmp_path):
    root = tmp_path / "owned"
    root.mkdir()
    member = root / "member"
    member.write_bytes(b"inside")
    fired = False

    def race_hook(name, details):
        nonlocal fired
        if not fired and name == "after_file_open":
            fired = True
            member.write_bytes(b"outside-secret")

    with pytest.raises(ValueError, match="changed during hashing"):
        _snapshot_authoritative_closure(
            [{"label": "fixture", "path": str(root)}],
            [],
            race_hook=race_hook,
        )
    assert fired


@pytest.mark.parametrize("event", ["after_root_open", "after_directory_open"])
def test_anchored_directory_or_root_replacement_is_rejected(tmp_path, event):
    root = tmp_path / "owned"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "member").write_bytes(b"inside")
    fired = False

    def race_hook(name, details):
        nonlocal fired
        if fired or name != event:
            return
        if event == "after_directory_open" and details.get("relative_path") != "nested":
            return
        fired = True
        victim = root if event == "after_root_open" else nested
        saved = tmp_path / f"saved-{event}"
        victim.rename(saved)
        victim.mkdir()
        (victim / "outside").write_bytes(b"outside-secret")

    with pytest.raises(ValueError, match="runtime closure"):
        _snapshot_authoritative_closure(
            [{"label": "fixture", "path": str(root)}],
            [],
            race_hook=race_hook,
        )
    assert fired


def test_anchor_identity_failure_closes_untransferred_descriptor(
    tmp_path, monkeypatch
):
    root = tmp_path / "owned"
    root.mkdir()
    closed = []
    monkeypatch.setattr(
        "challenge148.acceptance._open_absolute_directory", lambda path: 901
    )
    monkeypatch.setattr(
        "challenge148.acceptance._assert_anchor_path_identity",
        lambda path, descriptor: (_ for _ in ()).throw(
            ValueError("identity failure")
        ),
    )
    monkeypatch.setattr(
        "challenge148.acceptance.os.close", lambda descriptor: closed.append(descriptor)
    )
    for _ in range(4):
        with pytest.raises(ValueError, match="identity failure"):
            _snapshot_authoritative_closure(
                [{"label": "fixture", "path": str(root)}], []
            )
    assert closed == [901, 901, 901, 901]


def test_julia_discovery_requires_every_applicable_artifact_and_splits_external_abi(
    tmp_path, monkeypatch
):
    runtime = tmp_path / "julia"
    package = tmp_path / "packages" / "Demo"
    artifact = tmp_path / "artifacts" / ("a" * 40)
    for root in (runtime, package, artifact):
        root.mkdir(parents=True)
    artifacts_toml = package / "Artifacts.toml"
    artifacts_toml.write_text("[demo]\n", encoding="utf-8")
    owned_library = artifact / "libowned.so"
    owned_library.write_bytes(b"owned")
    payload = {
        "schema_version": "julia-science-discovery-v1",
        "project_root": str(tmp_path),
        "depot_roots": [str(tmp_path)],
        "source_roots": [str(package)],
        "packages": {},
        "artifacts": [
            {
                "name": "demo",
                "artifacts_toml": str(artifacts_toml),
                "hash": "a" * 40,
                "applicable": True,
                "path": str(artifact),
            }
        ],
        "julia_root": str(runtime),
        "sysimage": str(runtime / "sys.so"),
        "loaded_libraries": [str(owned_library), "/usr/lib/libexternal.so"],
    }
    (runtime / "sys.so").write_bytes(b"sys")
    julia = tmp_path / "bin/julia"
    julia.parent.mkdir()
    _write_fake_executable(julia, "print('unused')\n")
    runner = tmp_path / "run_independent.jl"
    project_file = tmp_path / "Project.toml"
    manifest = tmp_path / "Manifest.toml"
    module = tmp_path / "src/Challenge148LTFIM.jl"
    module.parent.mkdir()
    for path in (runner, project_file, manifest, module):
        path.write_text("fixture\n", encoding="utf-8")
    identity = {
        "julia_executable": _launch_identity_entry(julia),
        "julia_runner": _launch_identity_entry(runner),
        "julia_project": _launch_identity_entry(project_file),
        "julia_manifest": _launch_identity_entry(manifest),
        "julia_module": _launch_identity_entry(module),
    }
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", fake_run)
    parsed = _discover_julia_runtime_closure(
        tmp_path, julia, timeout=1, runtime_identity=identity
    )
    discovery_script = seen["command"][-2]
    assert "HostPlatform()" in discovery_script
    assert "artifact_meta(" in discovery_script
    assert "artifact_hash(" in discovery_script
    assert "artifact_path(" in discovery_script
    assert parsed["owned_libraries"] == [str(owned_library.absolute())]
    assert parsed["external_abi_libraries"] == ["/usr/lib/libexternal.so"]
    payload["artifacts"][0]["path"] = None
    with pytest.raises(ValueError, match="applicable Julia artifact is missing"):
        _parse_julia_discovery(payload)


def test_julia_discovery_uses_bound_executable_and_fd_project_view(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    module = project / "src/Challenge148LTFIM.jl"
    module.parent.mkdir(parents=True)
    julia = tmp_path / "julia"
    runner = project / "run_independent.jl"
    project_file = project / "Project.toml"
    manifest = project / "Manifest.toml"
    _write_fake_executable(julia, "print('unused')\n")
    _write_fake_executable(runner, "print('unused')\n")
    project_file.write_text("name = \"validated\"\n", encoding="utf-8")
    manifest.write_text("manifest_format = \"2.0\"\n", encoding="utf-8")
    module.write_text("module Validated end\n", encoding="utf-8")
    identity = {
        "julia_executable": _launch_identity_entry(julia),
        "julia_runner": _launch_identity_entry(runner),
        "julia_project": _launch_identity_entry(project_file),
        "julia_manifest": _launch_identity_entry(manifest),
        "julia_module": _launch_identity_entry(module),
    }
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["pass_fds"] = kwargs["pass_fds"]
        project_path = Path(command[1].split("=", 1)[1])
        observed["temp_path"] = Path(os.readlink(project_path))
        _replace_fake_executable(julia, "raise SystemExit('evil')\n")
        project_file.replace(project_file.with_suffix(".replaced"))
        project_file.write_text("name = \"evil\"\n", encoding="utf-8")
        manifest.replace(manifest.with_suffix(".replaced"))
        manifest.write_text("manifest_format = \"evil\"\n", encoding="utf-8")
        module.replace(module.with_suffix(".replaced"))
        module.write_text("module Evil end\n", encoding="utf-8")
        assert project_path.joinpath("Project.toml").read_text() == (
            "name = \"validated\"\n"
        )
        assert project_path.joinpath("Manifest.toml").read_text() == (
            "manifest_format = \"2.0\"\n"
        )
        assert project_path.joinpath(
            "src/Challenge148LTFIM.jl"
        ).read_text() == "module Validated end\n"
        assert Path(command[0]).read_text().endswith("print('unused')\n")
        return subprocess.CompletedProcess(command, 0, '{"fixture": true}', "")

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", fake_run)
    monkeypatch.setattr(
        "challenge148.acceptance._parse_julia_discovery", lambda value: value
    )
    assert _discover_julia_runtime_closure(
        project.parent, julia, runtime_identity=identity
    ) == {"fixture": True}
    assert not observed["temp_path"].exists()
    for descriptor in observed["pass_fds"]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_fd_project_view_setup_failure_removes_private_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "ephemeral-project"

    def fake_mkdtemp(**kwargs):
        root.mkdir(mode=0o700)
        return str(root)

    monkeypatch.setattr(
        "challenge148.acceptance.tempfile.mkdtemp", fake_mkdtemp
    )
    monkeypatch.setattr(
        "challenge148.acceptance.os.symlink",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("symlink forbidden")
        ),
    )
    with pytest.raises(ValueError, match="project view setup failed"):
        _create_fd_project_view(
            {
                "julia_project": 101,
                "julia_manifest": 102,
                "julia_module": 103,
            }
        )
    assert not root.exists()


def test_julia_discovery_failure_closes_all_fds_and_project_view(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    module = project / "src/Challenge148LTFIM.jl"
    module.parent.mkdir(parents=True)
    files = {
        "julia_executable": tmp_path / "julia",
        "julia_runner": project / "run_independent.jl",
        "julia_project": project / "Project.toml",
        "julia_manifest": project / "Manifest.toml",
        "julia_module": module,
    }
    for path in files.values():
        path.write_text("fixture\n", encoding="utf-8")
    identity = {
        label: _launch_identity_entry(path) for label, path in files.items()
    }
    observed = {}

    def fail(runtime_identity, descriptors, project_view, timeout):
        observed["descriptors"] = tuple(
            [*descriptors.values(), project_view["descriptor"]]
        )
        observed["temp_root"] = Path(project_view["root"])
        raise RuntimeError("discovery failure")

    monkeypatch.setattr(
        "challenge148.acceptance._run_bound_julia_discovery", fail
    )
    with pytest.raises(RuntimeError, match="discovery failure"):
        _discover_julia_runtime_closure(
            project.parent,
            files["julia_executable"],
            runtime_identity=identity,
        )
    assert not observed["temp_root"].exists()
    for descriptor in observed["descriptors"]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_request_hashing_respects_distinct_adapter_canonical_contracts():
    request = {"adapter": "QMC_LTFIM", "coupling": 1.0, "seed": 148}
    julia_bytes = b'{"adapter":"QMC_LTFIM","coupling":1,"seed":148}\n'
    assert _adapter_request_hash(request, "QMC_LTFIM") == hashlib.sha256(
        julia_bytes
    ).hexdigest()
    assert _adapter_request_hash(request, "QMC_SSE") == hashlib.sha256(
        canonical_json(request)
    ).hexdigest()


def _canonical_file(path: Path, value: object) -> str:
    payload = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _qmc_request(tmp_path: Path, adapter: str) -> dict:
    graph = honeycomb_graph(2)
    graph_path = tmp_path / "graph.json"
    write_graph_json(graph, graph_path)
    return {
        "schema_version": "qmc-request-v1",
        "adapter": adapter,
        "graph_path": str(graph_path.resolve()),
        "graph_sha256": graph_sha256(graph),
        "beta": 0.55,
        "coupling": 1.0,
        "field": 1.2,
        "seed": 148_001,
        "thermalization_sweeps": 1_000,
        "retained_samples": 1_600,
        "thinning": 2,
        "serial_measurement_stride_samples": 1,
        "bin_length": 100,
        "checkpoint_bins": 8,
        "expected_source_hash": HEX_A,
        "expected_build_hash": HEX_B,
    }


def _bin(adapter: str, index: int) -> dict:
    energy = (-100.0 + index) / 100
    transverse = (40.0 + index / 10) / 100
    m2 = (25.0 + index / 10) / 100
    m4 = (10.0 + index / 20) / 100
    common = {
        "adapter": adapter,
        "bin_index": index,
        "cluster_accepted_count": 100,
        "cluster_attempt_count": 200,
        "energy_sum": -100.0 + index,
        "energy_sum_squares": 100 * energy**2,
        "m2_sum": 25.0 + index / 10,
        "m2_sum_squares": 100 * m2**2,
        "m4_sum": 10.0 + index / 20,
        "m4_sum_squares": 100 * m4**2,
        "operator_count_sum": 100,
        "sample_count": 100,
        "sweep_count": 200,
        "time_slice_count_sum": 100,
        "transverse_magnetization_sum": 40.0 + index / 10,
        "transverse_magnetization_sum_squares": 100 * transverse**2,
        "serial_measurement_stride_samples": 1,
        "serial_observations": {
            "energy": [energy] * 100,
            "transverse_magnetization": [transverse] * 100,
            "m2": [m2] * 100,
            "m4": [m4] * 100,
        },
    }
    if adapter == "QMC_SSE":
        return common | {
            "schema_version": "qmc-sse-bin-v1",
            "cluster_attempts_per_sweep": 8,
            "rng": "rand-0.9.5-SmallRng-Xoshiro256PlusPlus",
            "seed_derivation": "sha256:qmc-sse-seed-v1||u64be",
            "seed_namespace": "QMC_SSE:qmc-sse-seed-v1",
        }
    return common | {
        "schema_version": "qmc-ltfim-bin-v1",
        "cluster_count_sum": 200,
        "cluster_list_size_observation_count": 200,
        "cluster_list_size_sum": 400,
        "cluster_size_observation_count": 200,
        "cluster_size_sum": 300.0,
        "rng": "Julia-1.11.6-Random.Xoshiro-xoshiro256++",
        "seed_derivation": "sha256:qmc-ltfim-seed-v1||u64be",
        "seed_namespace": "QMC_LTFIM:qmc-ltfim-seed-v1",
    }


def adapter_fixture(tmp_path: Path, adapter: str) -> tuple[Path, dict]:
    output = (tmp_path / adapter.lower()).resolve()
    output.mkdir()
    request = _qmc_request(tmp_path, adapter)
    request_hash = _adapter_request_hash(request, adapter)
    state_name = ".qmc-sse-lock-state" if adapter == "QMC_SSE" else ".qmc-ltfim-lock-state"
    lock_name = ".qmc-sse.lock" if adapter == "QMC_SSE" else ".qmc-ltfim.lock"
    state = output / state_name
    state.mkdir()
    lock = state / lock_name
    lock.touch()
    identity = state / "identity.json"
    identity.touch()
    state_stat, lock_stat, identity_stat = state.stat(), lock.stat(), identity.stat()

    if adapter == "QMC_SSE":
        binding = {
            "identity_device": identity_stat.st_dev,
            "identity_inode": identity_stat.st_ino,
            "lock_device": lock_stat.st_dev,
            "lock_inode": lock_stat.st_ino,
            "output_namespace": str(output),
            "request_sha256": request_hash,
            "schema_version": "qmc-sse-lock-state-binding-v2",
            "state_device": state_stat.st_dev,
            "state_inode": state_stat.st_ino,
        }
        anchor = {
            key: value for key, value in binding.items() if key != "schema_version"
        } | {
            "schema_version": "qmc-sse-run-lock-anchor-v2",
            "lock_state_identity_sha256": hashlib.sha256(canonical_json(binding)).hexdigest(),
        }
    else:
        anchor = {
            "schema_version": "qmc-ltfim-run-lock-anchor-v1",
            "request_sha256": request_hash,
            "output_namespace": str(output),
            "state_device": state_stat.st_dev,
            "state_inode": state_stat.st_ino,
            "lock_device": lock_stat.st_dev,
            "lock_inode": lock_stat.st_ino,
        }
    anchor_payload = canonical_json(anchor) + b"\n"
    anchor_hash = hashlib.sha256(anchor_payload).hexdigest()
    anchor_path = output / "run-lock-anchors" / f"{anchor_hash}.json"
    anchor_path.parent.mkdir()
    anchor_path.write_bytes(anchor_payload)
    os.link(anchor_path, anchor_path.with_suffix(".pin"))
    selection = {
        "schema_version": (
            "qmc-sse-run-lock-anchor-selection-v1"
            if adapter == "QMC_SSE"
            else "qmc-ltfim-run-lock-anchor-selection-v1"
        ),
        "anchor_sha256": anchor_hash,
        "path": f"run-lock-anchors/{anchor_hash}.json",
    }
    if adapter == "QMC_SSE":
        anchor_stat = anchor_path.stat()
        selection |= {
            "anchor_device": anchor_stat.st_dev,
            "anchor_inode": anchor_stat.st_ino,
        }
    _canonical_file(output / "run-lock-anchor.json", selection)

    bin_hashes = []
    for index in range(16):
        record = _bin(adapter, index)
        payload = canonical_json(record) + b"\n"
        digest = hashlib.sha256(payload).hexdigest()
        (output / "bins").mkdir(exist_ok=True)
        (output / "bins" / f"{digest}.ndjson").write_bytes(payload)
        bin_hashes.append(digest)
    manifest = {
        "schema_version": "qmc-checkpoint-generation-v2",
        "anchor_sha256": anchor_hash,
        "request_sha256": request_hash,
        "adapter": adapter,
        "source_hash": HEX_A,
        "build_hash": HEX_B,
        "seed": request["seed"],
        "completed_bin_count": 16,
        "bin_object_hashes": bin_hashes,
        "previous_generation_sha256": None,
        "replay_update_count": 4_200,
    }
    manifest_payload = canonical_json(manifest) + b"\n"
    generation_hash = hashlib.sha256(manifest_payload).hexdigest()
    generation = output / "generations" / generation_hash
    generation.mkdir(parents=True)
    (generation / "manifest.json").write_bytes(manifest_payload)
    _canonical_file(
        output / "current-generation.json",
        {
            "schema_version": "qmc-current-generation-v2",
            "anchor_sha256": anchor_hash,
            "generation_sha256": generation_hash,
            "path": f"generations/{generation_hash}",
        },
    )
    return output, request


@pytest.mark.parametrize("adapter", ["QMC_SSE", "QMC_LTFIM"])
def test_minimal_v2_contract_validates_every_hash_and_anchor(adapter, tmp_path):
    output, request = adapter_fixture(tmp_path, adapter)
    records = validate_adapter_run(output, request, adapter)
    assert len(records) == 16


@pytest.mark.parametrize("adapter", ["QMC_SSE", "QMC_LTFIM"])
def test_anchor_pin_must_retain_canonical_inode(adapter, tmp_path):
    output, request = adapter_fixture(tmp_path, adapter)
    selection = json.loads((output / "run-lock-anchor.json").read_text())
    anchor = output / selection["path"]
    pin = anchor.with_suffix(".pin")
    pin.unlink()
    pin.write_bytes(anchor.read_bytes())

    with pytest.raises(ValueError, match="pin identity"):
        validate_adapter_run(output, request, adapter)


@pytest.mark.parametrize(
    "field",
    [
        "energy_sum_squares",
        "transverse_magnetization_sum_squares",
        "m2_sum_squares",
        "m4_sum_squares",
    ],
)
def test_serial_observations_must_reproduce_primitive_square_sums(field, tmp_path):
    request = _qmc_request(tmp_path, "QMC_SSE")
    record = _bin("QMC_SSE", 0)
    record[field] += 0.25
    with pytest.raises(ValueError, match="squares"):
        _validate_bin_cross_fields(record, request)


def test_bin_v1_without_serial_evidence_is_explicitly_rejected():
    record = _bin("QMC_SSE", 0)
    del record["serial_observations"]
    schema = json.loads((SCHEMAS / "qmc-sse-bin.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)


@pytest.mark.parametrize("adapter", ["QMC_SSE", "QMC_LTFIM"])
def test_archived_replay_uses_internal_graph_after_external_deletion(
    adapter, tmp_path
):
    live_root = tmp_path / "live"
    live_root.mkdir()
    live, request = adapter_fixture(live_root, adapter)
    archive_root = tmp_path / "published"
    archived_run = archive_root / "raw" / adapter.lower()
    archived_run.parent.mkdir(parents=True)
    shutil.copytree(live, archived_run)
    graph_object = archive_root / "graphs" / f"{request['graph_sha256']}.json"
    graph_object.parent.mkdir()
    shutil.copy2(request["graph_path"], graph_object)
    replay = {
        "schema_version": "acceptance-replay-request-v1",
        "adapter": adapter,
        "launch_request": request,
        "launch_request_sha256": _adapter_request_hash(request, adapter),
        "authoritative_graph": {
            "path": graph_object.relative_to(archive_root).as_posix(),
            "sha256": request["graph_sha256"],
        },
    }
    Path(request["graph_path"]).unlink()
    assert len(
        validate_archived_adapter_run(archived_run, replay, archive_root)
    ) == 16
    graph_object.write_text("{}\n")
    with pytest.raises(ValueError, match="graph"):
        validate_archived_adapter_run(archived_run, replay, archive_root)


@pytest.mark.parametrize(
    "damage",
    [
        "v1",
        "missing-anchor",
        "missing-bin",
        "bin-hash",
        "generation-hash",
        "current-anchor",
        "pointer-extra",
        "source",
        "adapter",
    ],
)
def test_adapter_contract_damage_fails_closed(damage, tmp_path):
    output, request = adapter_fixture(tmp_path, "QMC_SSE")
    pointer_path = output / "current-generation.json"
    pointer = json.loads(pointer_path.read_text())
    generation_path = output / pointer["path"] / "manifest.json"
    manifest = json.loads(generation_path.read_text())
    if damage == "v1":
        pointer["schema_version"] = "qmc-current-generation-v1"
        _canonical_file(pointer_path, pointer)
    elif damage == "missing-anchor":
        (output / "run-lock-anchor.json").unlink()
    elif damage == "missing-bin":
        digest = manifest["bin_object_hashes"][0]
        (output / "bins" / f"{digest}.ndjson").unlink()
    elif damage == "bin-hash":
        digest = manifest["bin_object_hashes"][0]
        (output / "bins" / f"{digest}.ndjson").write_text("{}\n")
    elif damage == "generation-hash":
        generation_path.write_text("{}\n")
    elif damage == "current-anchor":
        pointer["anchor_sha256"] = "0" * 64
        _canonical_file(pointer_path, pointer)
    elif damage == "pointer-extra":
        pointer["extra"] = True
        _canonical_file(pointer_path, pointer)
    elif damage == "source":
        manifest["source_hash"] = "0" * 64
        generation_path.write_bytes(canonical_json(manifest) + b"\n")
    else:
        manifest["adapter"] = "QMC_LTFIM"
        generation_path.write_bytes(canonical_json(manifest) + b"\n")
    with pytest.raises(ValueError):
        validate_adapter_run(output, request, "QMC_SSE")


def test_executable_specific_adapter_mismatch_fails_closed(tmp_path):
    output, request = adapter_fixture(tmp_path, "QMC_SSE")
    with pytest.raises(ValueError, match="adapter"):
        validate_adapter_run(output, request, "QMC_LTFIM")


def _chain_summary(mean: float, error: float = 1.0) -> dict:
    return {
        "observables": {
            name: {
                "mean": mean if name == "m4" else 0.0,
                "standard_error": error,
                "half_agreement_z": 0.0,
            }
            for name in ("energy", "transverse_magnetization", "m2", "m4", "binder_ratio")
        }
    }


def test_one_observable_over_four_sigma_fails_without_other_adapter_masking():
    exact = {name: 0.0 for name in ("energy", "transverse_magnetization", "m2", "m4", "binder_ratio")}
    result = evaluate_adapter(
        "primary_qmc_sse",
        [_chain_summary(4.1), _chain_summary(4.1)],
        exact,
        {
            "max_normalized_residual": 4,
            "median_normalized_residual": 1.5,
            "agreement_sigma": 3,
            "minimum_bin_tau": 10,
        },
    )
    assert result["failures"] == ["primary_qmc_sse.m4.normalized_residual"]


def test_adapter_matrix_median_above_one_point_five_fails_independently():
    result = evaluate_matrix_median(
        "primary_qmc_sse", [0.2, 1.6, 1.7, 2.0], threshold=1.5
    )
    assert result == {
        "median": 1.65,
        "failure": "primary_qmc_sse.matrix_median_normalized_residual",
    }


def test_launch_rejects_stale_output_and_nonzero_exit(monkeypatch, tmp_path):
    request_path = tmp_path / "request.json"
    request_path.write_text("{}")
    stale = tmp_path / "stale"
    stale.mkdir()
    with pytest.raises(ValueError, match="stale"):
        launch_adapter(
            "QMC_SSE",
            request_path,
            stale,
            timeout=1,
            launch_nonce="nonce",
            runtime_identity={},
        )

    class Failed:
        returncode = 9
        stdout = "out"
        stderr = "failed"

    executable = tmp_path / "qmc-sse"
    executable.touch()
    identity = {"qmc_sse_executable": _launch_identity_entry(executable)}
    monkeypatch.setattr(
        "challenge148.acceptance._absolute_owned_environment",
        lambda: (ROOT, executable, Path(sys.executable)),
    )
    monkeypatch.setattr("challenge148.acceptance.subprocess.run", lambda *args, **kwargs: Failed())
    with pytest.raises(RuntimeError, match="exit"):
        launch_adapter(
            "QMC_SSE",
            request_path,
            tmp_path / "new",
            timeout=1,
            launch_nonce="nonce",
            runtime_identity=identity,
        )


def test_launch_binding_accepts_atomic_pretty_printed_request(monkeypatch, tmp_path):
    request_path = tmp_path / "request.json"
    request_path.write_text('{\n  "adapter": "QMC_SSE",\n  "seed": 148\n}\n')
    executable = tmp_path / "qmc-sse"
    executable.touch()
    identity = {"qmc_sse_executable": _launch_identity_entry(executable)}
    monkeypatch.setattr(
        "challenge148.acceptance._absolute_owned_environment",
        lambda: (ROOT, executable, Path(sys.executable)),
    )
    output = tmp_path / "nested" / "fresh"

    class Succeeded:
        returncode = 0
        stdout = "out"
        stderr = ""

    def fake_run(*args, **kwargs):
        time.sleep(0.01)
        output.mkdir()
        (output / "current-generation.json").write_text("{}\n")
        return Succeeded()

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", fake_run)
    evidence = launch_adapter(
        "QMC_SSE",
        request_path,
        output,
        timeout=1,
        launch_nonce="nonce",
        runtime_identity=identity,
    )
    binding = json.loads((output / "acceptance-launch-binding.json").read_text())
    assert evidence["binding"] == binding
    assert binding["request_sha256"] == hashlib.sha256(
        canonical_json({"adapter": "QMC_SSE", "seed": 148})
    ).hexdigest()


def _write_fake_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env python3\n{body}", encoding="utf-8")
    path.chmod(0o755)


def _replace_fake_executable(path: Path, body: str) -> None:
    replacement = path.with_name(f"{path.name}.replacement")
    _write_fake_executable(replacement, body)
    os.replace(replacement, path)


def _replace_file(path: Path, contents: str) -> None:
    replacement = path.with_name(f"{path.name}.replacement")
    replacement.write_text(contents, encoding="utf-8")
    os.replace(replacement, path)


def _launch_identity_entry(path: Path) -> dict:
    snapshot = _snapshot_authoritative_closure(
        [{"label": path.parent.name, "path": str(path.parent)}],
        [str(path)],
    )
    binding = snapshot["explicit_entries"][str(path)]
    file_entry = binding.get("target_file", binding)
    return {
        "path": str(path),
        "binding": binding,
        "sha256": file_entry["sha256"],
        "size": file_entry["size"],
    }


def _rust_build_info() -> dict:
    return {
        "adapter": "QMC_SSE",
        "build_hash": HEX_A,
        "codegen_units": "1",
        "compiler": "fixture",
        "encoded_rustflags": "",
        "features": "",
        "lto": "off",
        "panic": "unwind",
        "profile": "test",
        "qmc_revision": "fixture",
        "rng": "fixture",
        "seed_derivation": "fixture",
        "source_hash": HEX_B,
        "sweep_semantics": "fixture",
        "target": "fixture",
    }


def _julia_build_info() -> dict:
    return {
        "adapter": "QMC_LTFIM",
        "build_hash": HEX_A,
        "julia": "fixture",
        "qmc_license": "fixture",
        "qmc_revision": "fixture",
        "rng": "fixture",
        "seed_derivation": "fixture",
        "seed_namespace": "fixture",
        "source_hash": HEX_B,
        "sweep_semantics": "fixture",
    }


@pytest.mark.parametrize("adapter", ["QMC_SSE", "QMC_LTFIM"])
def test_build_info_executes_validated_fd_bytes_after_path_replacement(
    tmp_path, monkeypatch, adapter
):
    solution = tmp_path / "solution"
    project = solution / "adapters/qmc-ltfim"
    project.mkdir(parents=True)
    (project / "Project.toml").write_text("[deps]\n", encoding="utf-8")
    (project / "Manifest.toml").write_text(
        "manifest_format = \"2.0\"\n", encoding="utf-8"
    )
    module = project / "src/Challenge148LTFIM.jl"
    module.parent.mkdir()
    module.write_text("module Fixture end\n", encoding="utf-8")
    rust = tmp_path / "qmc-sse"
    julia = tmp_path / "julia"
    runner = project / "run_independent.jl"
    rust_info = _rust_build_info()
    julia_info = _julia_build_info()
    _write_fake_executable(rust, f"print({json.dumps(rust_info)!r})\n")
    _write_fake_executable(
        runner,
        f"print({json.dumps(julia_info)!r})\n",
    )
    _write_fake_executable(
        julia,
        """
import os, pathlib, sys
project = pathlib.Path(sys.argv[1].split("=", 1)[1])
assert (project / "Project.toml").read_text() == "[deps]\\n"
assert (project / "Manifest.toml").read_text() == 'manifest_format = "2.0"\\n'
assert (project / "src/Challenge148LTFIM.jl").read_text() == "module Fixture end\\n"
os.execv(sys.argv[3], [sys.argv[3], sys.argv[1], *sys.argv[4:]])
""",
    )
    identity = {
        "qmc_sse_executable": _launch_identity_entry(rust),
        "julia_executable": _launch_identity_entry(julia),
        "julia_runner": _launch_identity_entry(runner),
        "julia_project": _launch_identity_entry(project / "Project.toml"),
        "julia_manifest": _launch_identity_entry(project / "Manifest.toml"),
        "julia_module": _launch_identity_entry(module),
    }
    real_run = subprocess.run
    observed = {}

    def replace_then_run(command, **kwargs):
        observed["command"] = command
        observed["pass_fds"] = kwargs["pass_fds"]
        if adapter == "QMC_SSE":
            _replace_fake_executable(rust, "print('evil')\n")
        else:
            _replace_fake_executable(julia, "print('evil-julia')\n")
            _replace_fake_executable(runner, "print('evil-runner')\n")
            _replace_file(project / "Project.toml", "evil-project\n")
            _replace_file(project / "Manifest.toml", "evil-manifest\n")
            _replace_file(module, "evil-module\n")
        return real_run(command, **kwargs)

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", replace_then_run)
    result = _adapter_build_info(
        adapter, solution, rust, julia, timeout=5, runtime_identity=identity
    )
    assert result["info"]["adapter"] == adapter
    assert observed["command"][0].startswith("/proc/self/fd/")
    assert result["fd_bound_launch"] is True
    for descriptor in observed["pass_fds"]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_real_qmc_launch_uses_validated_executable_fd_and_closes_it(
    tmp_path, monkeypatch
):
    executable = tmp_path / "qmc-sse"
    _write_fake_executable(
        executable,
        """
import pathlib, sys
output = pathlib.Path(sys.argv[sys.argv.index("--output-directory") + 1])
output.mkdir(parents=True)
(output / "current-generation.json").write_text("{}")
(output / "validated.txt").write_text("validated")
""",
    )
    request_path = tmp_path / "request.json"
    request_path.write_text('{"adapter":"QMC_SSE","seed":148}\n')
    identity = {"qmc_sse_executable": _launch_identity_entry(executable)}
    real_run = subprocess.run
    observed = {}

    def replace_then_run(command, **kwargs):
        observed["pass_fds"] = kwargs["pass_fds"]
        _replace_fake_executable(executable, "raise SystemExit('evil')\n")
        return real_run(command, **kwargs)

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", replace_then_run)
    output = tmp_path / "output"
    evidence = launch_adapter(
        "QMC_SSE",
        request_path,
        output,
        timeout=5,
        launch_nonce="nonce",
        runtime_identity=identity,
    )
    assert (output / "validated.txt").read_text() == "validated"
    assert evidence["fd_bound_launch"] is True
    for descriptor in observed["pass_fds"]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_real_julia_launch_uses_validated_executable_and_runner_fds(
    tmp_path, monkeypatch
):
    project = tmp_path / "adapters/qmc-ltfim"
    project.mkdir(parents=True)
    project_file = project / "Project.toml"
    project_file.write_text("[deps]\n", encoding="utf-8")
    manifest = project / "Manifest.toml"
    manifest.write_text("manifest_format = \"2.0\"\n", encoding="utf-8")
    module = project / "src/Challenge148LTFIM.jl"
    module.parent.mkdir()
    module.write_text("module Validated end\n", encoding="utf-8")
    julia = tmp_path / "julia"
    runner = project / "run_independent.jl"
    _write_fake_executable(
        julia,
        "import os, sys\nos.execv(sys.argv[3], [sys.argv[3], sys.argv[1], *sys.argv[4:]])\n",
    )
    _write_fake_executable(
        runner,
        """
import pathlib, sys
project = pathlib.Path(sys.argv[1].split("=", 1)[1])
output = pathlib.Path(sys.argv[sys.argv.index("--output-directory") + 1])
output.mkdir(parents=True)
(output / "current-generation.json").write_text("{}")
(output / "validated.txt").write_text("validated-julia")
(output / "project-bytes.txt").write_text(
    (project / "Project.toml").read_text()
    + (project / "Manifest.toml").read_text()
    + (project / "src/Challenge148LTFIM.jl").read_text()
)
""",
    )
    identity = {
        "julia_executable": _launch_identity_entry(julia),
        "julia_runner": _launch_identity_entry(runner),
        "julia_project": _launch_identity_entry(project_file),
        "julia_manifest": _launch_identity_entry(manifest),
        "julia_module": _launch_identity_entry(module),
    }
    request_path = tmp_path / "request.json"
    request_path.write_text('{"adapter":"QMC_LTFIM","seed":149}\n')
    real_run = subprocess.run
    observed = {}

    def replace_then_run(command, **kwargs):
        observed["command"] = command
        observed["pass_fds"] = kwargs["pass_fds"]
        _replace_fake_executable(julia, "raise SystemExit('evil-julia')\n")
        _replace_fake_executable(runner, "raise SystemExit('evil-runner')\n")
        _replace_file(project_file, "evil-project\n")
        _replace_file(manifest, "evil-manifest\n")
        _replace_file(module, "evil-module\n")
        return real_run(command, **kwargs)

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", replace_then_run)
    output = tmp_path / "output"
    evidence = launch_adapter(
        "QMC_LTFIM",
        request_path,
        output,
        timeout=5,
        launch_nonce="nonce",
        runtime_identity=identity,
    )
    assert (output / "validated.txt").read_text() == "validated-julia"
    assert observed["command"][1].startswith("--project=/proc/self/fd/")
    assert (output / "project-bytes.txt").read_text() == (
        "[deps]\nmanifest_format = \"2.0\"\nmodule Validated end\n"
    )
    assert evidence["diagnostic_command"][:4] == [
        str(julia),
        f"--project={project}",
        "--compiled-modules=no",
        str(runner),
    ]
    for descriptor in observed["pass_fds"]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize("outcome", ["timeout", "nonzero", "exception"])
def test_launch_closes_bound_fd_on_every_subprocess_outcome(
    tmp_path, monkeypatch, outcome
):
    executable = tmp_path / "qmc-sse"
    _write_fake_executable(executable, "print('unused')\n")
    identity = {"qmc_sse_executable": _launch_identity_entry(executable)}
    request_path = tmp_path / "request.json"
    request_path.write_text('{"adapter":"QMC_SSE","seed":148}\n')
    observed = {}

    def fail(command, **kwargs):
        observed["pass_fds"] = kwargs["pass_fds"]
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        if outcome == "exception":
            raise RuntimeError("spawn failure")
        return types.SimpleNamespace(returncode=9, stdout="", stderr="failed")

    monkeypatch.setattr("challenge148.acceptance.subprocess.run", fail)
    with pytest.raises((AdapterLaunchError, RuntimeError)):
        launch_adapter(
            "QMC_SSE",
            request_path,
            tmp_path / "output",
            timeout=1,
            launch_nonce="nonce",
            runtime_identity=identity,
        )
    for descriptor in observed["pass_fds"]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize("failure_mode", ["timeout", "malformed-output"])
def test_launch_timeout_and_malformed_output_preserve_failure_evidence(
    failure_mode, monkeypatch, tmp_path
):
    request_path = tmp_path / "request.json"
    request_path.write_text('{"adapter":"QMC_SSE","seed":148}\n')
    executable = tmp_path / "qmc-sse"
    executable.touch()
    identity = {"qmc_sse_executable": _launch_identity_entry(executable)}
    monkeypatch.setattr(
        "challenge148.acceptance._absolute_owned_environment",
        lambda: (ROOT, executable, Path(sys.executable)),
    )
    if failure_mode == "timeout":
        monkeypatch.setattr(
            "challenge148.acceptance.subprocess.run",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(
                    cmd=args[0], timeout=1, output=b"partial", stderr=b"slow"
                )
            ),
        )
    else:
        monkeypatch.setattr(
            "challenge148.acceptance.subprocess.run",
            lambda *args, **kwargs: types.SimpleNamespace(
                returncode=0, stdout="partial", stderr=""
            ),
        )
    with pytest.raises(AdapterLaunchError) as caught:
        launch_adapter(
            "QMC_SSE",
            request_path,
            tmp_path / failure_mode,
            timeout=1,
            launch_nonce="nonce",
            runtime_identity=identity,
        )
    assert caught.value.evidence["stdout"] == "partial"
    if failure_mode == "timeout":
        assert caught.value.evidence["timed_out"] is True
    else:
        assert "current generation pointer" in str(caught.value)
