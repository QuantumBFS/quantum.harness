from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest


SOLUTION_DIR = Path(__file__).parents[1]


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SOLUTION_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bath = _load_module("chain_mapping_test_bath", "bath.py")
chain = _load_module("chain_mapping", "chain_mapping.py")


def _canonical_json(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _rehash_mapping(mapping):
    mapping["sha256"] = hashlib.sha256(
        _canonical_json(mapping["payload"])
    ).hexdigest()
    return mapping


def synthetic_star_artifact(epsilon, coupling):
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=len(epsilon),
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact = copy.deepcopy(artifact)
    artifact["payload"]["epsilon"] = list(epsilon)
    artifact["payload"]["V"] = list(coupling)
    artifact["payload"]["parameters"]["n_bath"] = len(epsilon)
    artifact["sha256"] = hashlib.sha256(
        _canonical_json(artifact["payload"])
    ).hexdigest()
    return artifact


def mapped_semicircle(n_bath):
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=n_bath,
        frequency_grid=[-1.2, -0.47, 0.0, 0.63, 1.2],
    )
    payload = chain.derive_chain_mapping(star)["payload"]
    epsilon = np.asarray(star["payload"]["epsilon"])
    coupling = np.asarray(star["payload"]["V"])
    Q = np.asarray(payload["Q"])
    return star, payload, np.diag(epsilon), coupling, Q.T @ np.diag(epsilon) @ Q


def continued_fraction(z, onsite, hopping):
    result = 1.0 / (z - onsite[-1])
    for index in range(len(onsite) - 2, -1, -1):
        result = 1.0 / (z - onsite[index] - hopping[index] ** 2 * result)
    return result


@pytest.mark.parametrize("n_bath", range(1, 7))
def test_mapping_has_binding_orthogonality_chain_and_coupling_invariants(n_bath):
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=n_bath,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    mapping = chain.derive_chain_mapping(star)
    payload = mapping["payload"]
    epsilon = np.asarray(star["payload"]["epsilon"])
    coupling = np.asarray(star["payload"]["V"])
    Q = np.asarray(payload["Q"])
    T = Q.T @ np.diag(epsilon) @ Q
    target = np.zeros(n_bath)
    target[0] = np.linalg.norm(coupling)

    assert Q.T @ Q == pytest.approx(np.eye(n_bath), abs=2e-13)
    assert T == pytest.approx(np.triu(np.tril(T, 1), -1), abs=2e-13)
    assert Q.T @ coupling == pytest.approx(target, abs=2e-13)
    assert payload["lambda"] == pytest.approx(np.linalg.norm(coupling))
    assert all(value >= 0.0 for value in payload["chain_hopping"])
    assert chain.verify_chain_mapping_artifact(mapping, star) is None


def test_zero_coupling_is_exact_identity_mapping():
    star = bath.make_bath_artifact(
        gamma=0.0,
        bandwidth=1.0,
        n_bath=6,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    payload = chain.derive_chain_mapping(star)["payload"]
    assert payload["lambda"] == 0.0
    assert payload["Q"] == np.eye(6).tolist()
    assert payload["chain_onsite"] == star["payload"]["epsilon"]
    assert payload["chain_hopping"] == [0.0] * 5


def test_repeated_energy_breakdown_uses_canonical_deflation(monkeypatch):
    star = synthetic_star_artifact(
        epsilon=[-0.5, -0.5, 0.5, 0.5],
        coupling=[0.5, 0.5, 0.0, 0.0],
    )
    monkeypatch.setattr(chain.bath, "verify_bath_artifact", lambda _artifact: None)

    first = chain.derive_chain_mapping(star)
    second = chain.derive_chain_mapping(star)

    assert first == second
    assert first["payload"]["deflation_boundaries"]
    assert any(
        first["payload"]["chain_hopping"][index] == 0.0
        for index in first["payload"]["deflation_boundaries"]
    )


def test_mapping_requires_a_verified_star_artifact():
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=3,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    star["payload"]["V"][0] = -1.0

    with pytest.raises(ValueError):
        chain.derive_chain_mapping(star)


@pytest.mark.parametrize("n_bath", range(1, 7))
def test_star_and_chain_moments_match_through_twice_size_minus_one(n_bath):
    _star, payload, E, coupling, T = mapped_semicircle(n_bath)
    e0 = np.eye(n_bath)[:, 0]
    for power in range(2 * n_bath):
        expected = float(coupling @ np.linalg.matrix_power(E, power) @ coupling)
        actual = float(
            payload["lambda"] ** 2
            * e0
            @ np.linalg.matrix_power(T, power)
            @ e0
        )
        assert actual == pytest.approx(expected, abs=4e-12)


@pytest.mark.parametrize("n_bath", range(1, 7))
def test_complex_hybridization_matches_matrix_and_continued_fraction(n_bath):
    _star, payload, E, coupling, T = mapped_semicircle(n_bath)
    identity = np.eye(n_bath)
    for z in (complex(-0.7, 0.03), complex(0.2, 0.11), complex(1.4, 0.5)):
        expected = coupling @ np.linalg.solve(z * identity - E, coupling)
        matrix_chain = payload["lambda"] ** 2 * np.linalg.inv(
            z * identity - T
        )[0, 0]
        fraction_chain = payload["lambda"] ** 2 * continued_fraction(
            z, payload["chain_onsite"], payload["chain_hopping"]
        )
        assert matrix_chain == pytest.approx(expected, abs=3e-12)
        assert fraction_chain == pytest.approx(expected, abs=3e-12)


@pytest.mark.parametrize("n_bath", range(1, 7))
def test_chain_eigenpairs_reproduce_broadened_finite_bath_hybridization(n_bath):
    star, payload, _E, _coupling, T = mapped_semicircle(n_bath)
    energies, eigenvectors = np.linalg.eigh(T)
    weights = payload["lambda"] ** 2 * np.abs(eigenvectors[0, :]) ** 2
    width = star["payload"]["broadening"]["width"]
    normalization = 1.0 / (math.sqrt(2.0 * math.pi) * width)
    broadened = [
        math.pi
        * math.fsum(
            float(weight)
            * normalization
            * math.exp(-0.5 * ((omega - float(energy)) / width) ** 2)
            for energy, weight in zip(energies, weights)
        )
        for omega in star["payload"]["frequency_grid"]
    ]
    assert broadened == pytest.approx(
        star["payload"]["broadened_finite_bath_hybridization"], abs=4e-12
    )


def _mapping_fixture():
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=4,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    return star, chain.derive_chain_mapping(star)


_CORRUPTIONS = [
    (("schema_version",), 2),
    (("source_bath_sha256",), "0" * 64),
    (("source_bath_schema_version",), 999),
    (("n_bath",), 3),
    (("representation",), "direct_star"),
    (("lambda",), 0.0),
    (("Q",), [[1.0]]),
    (("chain_onsite",), [0.0] * 4),
    (("chain_hopping",), [0.0] * 3),
    (("deflation_boundaries",), [0]),
    (("numerics", "algorithm"), "unverified"),
    (("numerics", "breakdown_tolerance"), 0.0),
    (("numerics", "breakdown_tolerance_rule"), "unverified"),
    (("numerics", "orthogonality_max_error"), 1.0),
    (("numerics", "off_tridiagonal_max_abs"), 1.0),
    (("numerics", "coupling_max_error"), 1.0),
    (("provenance", "module"), "other"),
    (("provenance", "module_version"), "9.9.9"),
    (("provenance", "python_version"), "0.0.0"),
    (("provenance", "numpy_version"), "0.0.0"),
    (("provenance", "schema_version"), 999),
] + [
    (("conventions", key), f"{value} (corrupt)")
    for key, value in chain._CONVENTIONS.items()
]


@pytest.mark.parametrize(("path", "corrupt_value"), _CORRUPTIONS)
def test_verifier_rejects_validly_rehashed_semantic_corruption(path, corrupt_value):
    star, mapping = _mapping_fixture()
    corrupted = copy.deepcopy(mapping)
    target = corrupted["payload"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = corrupt_value

    with pytest.raises((TypeError, ValueError)):
        chain.verify_chain_mapping_artifact(_rehash_mapping(corrupted), star)


@pytest.mark.parametrize("operation", ["add", "remove"])
def test_verifier_requires_exact_payload_keys(operation):
    star, mapping = _mapping_fixture()
    corrupted = copy.deepcopy(mapping)
    if operation == "add":
        corrupted["payload"]["unexpected"] = None
    else:
        del corrupted["payload"]["representation"]

    with pytest.raises((TypeError, ValueError)):
        chain.verify_chain_mapping_artifact(_rehash_mapping(corrupted), star)


def test_writer_emits_canonical_verified_mapping(tmp_path):
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=3,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    destination = tmp_path / "chain-mapping.json"

    mapping = chain.write_chain_mapping_json(destination, bath_artifact=star)

    assert destination.read_bytes() == _canonical_json(mapping) + b"\n"
    assert chain.verify_chain_mapping_artifact(mapping, star) is None


def _writer_star():
    return bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=4,
        frequency_grid=[-1.2, 0.0, 1.2],
    )


def test_writer_uses_atomic_replace_and_fsyncs_file_and_directory(
    tmp_path, monkeypatch
):
    destination = tmp_path / "chain-mapping.json"
    replacements = []
    opened_directories = []
    fsynced = []
    real_replace = chain.os.replace
    real_open = chain.os.open
    real_fsync = chain.os.fsync

    def recording_replace(source, target):
        replacements.append((Path(source), Path(target)))
        real_replace(source, target)

    def recording_open(path, flags, mode=0o777):
        if Path(path) == tmp_path:
            opened_directories.append((Path(path), flags))
        return real_open(path, flags, mode)

    def recording_fsync(descriptor):
        fsynced.append(descriptor)
        real_fsync(descriptor)

    monkeypatch.setattr(chain.os, "replace", recording_replace)
    monkeypatch.setattr(chain.os, "open", recording_open)
    monkeypatch.setattr(chain.os, "fsync", recording_fsync)

    mapping = chain.write_chain_mapping_json(
        destination, bath_artifact=_writer_star()
    )

    assert replacements and replacements[0][1] == destination
    assert destination.read_bytes() == _canonical_json(mapping) + b"\n"
    assert opened_directories == [
        (tmp_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    ]
    assert len(fsynced) == 2
    assert list(tmp_path.iterdir()) == [destination]


class _FailingWriteFile:
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __enter__(self):
        self._wrapped.__enter__()
        return self

    def __exit__(self, *args):
        return self._wrapped.__exit__(*args)

    @property
    def name(self):
        return self._wrapped.name

    def write(self, _payload):
        raise OSError("injected mapping write failure")

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def _existing_mapping_destination(tmp_path):
    destination = tmp_path / "chain-mapping.json"
    destination.write_bytes(b"original")
    return destination


def _assert_original_without_transaction_files(tmp_path, destination):
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [destination]


def test_writer_failure_preserves_destination_and_cleans_temporary(
    tmp_path, monkeypatch
):
    destination = _existing_mapping_destination(tmp_path)
    real_named_temporary_file = chain.tempfile.NamedTemporaryFile

    def failing_named_temporary_file(*args, **kwargs):
        return _FailingWriteFile(real_named_temporary_file(*args, **kwargs))

    monkeypatch.setattr(
        chain.tempfile, "NamedTemporaryFile", failing_named_temporary_file
    )
    with pytest.raises(OSError, match="injected mapping write failure"):
        chain.write_chain_mapping_json(destination, bath_artifact=_writer_star())
    _assert_original_without_transaction_files(tmp_path, destination)


def test_writer_file_fsync_failure_preserves_destination_and_cleans_temporary(
    tmp_path, monkeypatch
):
    destination = _existing_mapping_destination(tmp_path)

    def failing_fsync(_descriptor):
        raise OSError("injected mapping file fsync failure")

    monkeypatch.setattr(chain.os, "fsync", failing_fsync)
    with pytest.raises(OSError, match="injected mapping file fsync failure"):
        chain.write_chain_mapping_json(destination, bath_artifact=_writer_star())
    _assert_original_without_transaction_files(tmp_path, destination)


def test_writer_replace_failure_preserves_destination_and_cleans_temporary(
    tmp_path, monkeypatch
):
    destination = _existing_mapping_destination(tmp_path)

    def failing_replace(_source, _target):
        raise OSError("injected mapping replace failure")

    monkeypatch.setattr(chain.os, "replace", failing_replace)
    with pytest.raises(OSError, match="injected mapping replace failure"):
        chain.write_chain_mapping_json(destination, bath_artifact=_writer_star())
    _assert_original_without_transaction_files(tmp_path, destination)


@pytest.mark.parametrize("existing", [False, True])
def test_writer_parent_fsync_failure_rolls_back_transaction(
    tmp_path, monkeypatch, existing
):
    destination = tmp_path / "chain-mapping.json"
    if existing:
        destination.write_bytes(b"original")
    directory_fsync_calls = []

    def fail_publication_fsync(directory):
        directory_fsync_calls.append(Path(directory))
        if len(directory_fsync_calls) == 1:
            raise OSError("injected mapping parent fsync failure")

    monkeypatch.setattr(
        chain, "_fsync_directory", fail_publication_fsync, raising=False
    )
    with pytest.raises(OSError, match="injected mapping parent fsync failure"):
        chain.write_chain_mapping_json(destination, bath_artifact=_writer_star())

    assert directory_fsync_calls == [tmp_path, tmp_path]
    if existing:
        _assert_original_without_transaction_files(tmp_path, destination)
    else:
        assert not destination.exists()
        assert list(tmp_path.iterdir()) == []


def test_writer_post_replace_failure_restores_original_inode(tmp_path, monkeypatch):
    destination = _existing_mapping_destination(tmp_path)
    destination.chmod(0o640)
    fixed_mtime_ns = 1_700_000_000_123_456_789
    os.utime(destination, ns=(fixed_mtime_ns, fixed_mtime_ns))
    external_link = tmp_path / "external-link.json"
    os.link(destination, external_link)
    original = destination.stat()
    directory_fsync_calls = []

    def fail_publication_fsync(directory):
        directory_fsync_calls.append(Path(directory))
        if len(directory_fsync_calls) == 1:
            raise OSError("injected mapping parent fsync failure")

    monkeypatch.setattr(
        chain, "_fsync_directory", fail_publication_fsync, raising=False
    )
    with pytest.raises(OSError, match="injected mapping parent fsync failure"):
        chain.write_chain_mapping_json(destination, bath_artifact=_writer_star())

    restored = destination.stat()
    assert directory_fsync_calls == [tmp_path, tmp_path]
    assert restored.st_ino == original.st_ino == external_link.stat().st_ino
    assert restored.st_mode == original.st_mode
    assert restored.st_mtime_ns == original.st_mtime_ns
    assert destination.read_bytes() == external_link.read_bytes() == b"original"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "chain-mapping.json",
        "external-link.json",
    ]


def test_writer_existing_destination_success_cleans_backup_and_fsyncs_cleanup(
    tmp_path, monkeypatch
):
    destination = _existing_mapping_destination(tmp_path)
    directory_fsync_calls = []

    def recording_directory_fsync(directory):
        directory_fsync_calls.append(Path(directory))

    monkeypatch.setattr(
        chain, "_fsync_directory", recording_directory_fsync, raising=False
    )
    mapping = chain.write_chain_mapping_json(
        destination, bath_artifact=_writer_star()
    )

    assert directory_fsync_calls == [tmp_path, tmp_path]
    assert list(tmp_path.iterdir()) == [destination]
    assert destination.read_bytes() == _canonical_json(mapping) + b"\n"


@pytest.mark.parametrize("destination_kind", ["directory", "symlink"])
def test_writer_rejects_directory_and_symlink_destinations(
    tmp_path, destination_kind
):
    destination = tmp_path / "chain-mapping.json"
    if destination_kind == "directory":
        destination.mkdir()
    else:
        target = tmp_path / "target.json"
        target.write_bytes(b"target")
        destination.symlink_to(target)

    with pytest.raises(ValueError, match="regular file"):
        chain.write_chain_mapping_json(destination, bath_artifact=_writer_star())
