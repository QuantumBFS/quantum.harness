from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import platform
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).parents[1] / "bath.py"
SPEC = importlib.util.spec_from_file_location("bath", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
bath = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bath)


def test_discretization_matches_second_kind_gauss_chebyshev_formula():
    gamma, bandwidth, n_bath = 0.1, 2.0, 5

    epsilon, coupling = bath.discretize_semicircular_bath(
        gamma=gamma, bandwidth=bandwidth, n_bath=n_bath
    )

    angles = [k * math.pi / (n_bath + 1) for k in range(1, n_bath + 1)]
    assert epsilon == pytest.approx(
        [bandwidth * math.cos(angle) for angle in angles]
    )
    assert coupling == pytest.approx(
        [
            math.sqrt(
                gamma
                * bandwidth
                / (n_bath + 1)
                * math.sin(angle) ** 2
            )
            for angle in angles
        ]
    )


def test_authoritative_model_definition_drives_bath_constants_and_conventions():
    definition = bath.load_model_definition()

    assert definition["model_id"] == "challenge-81-spinful-anderson-semicircular"
    assert definition["parameters"] == {
        "D": 1.0,
        "U": 0.8,
        "Gamma": 0.1,
        "epsilon_d": -0.4,
        "mu": 0.0,
    }
    assert definition["conventions"]["hybridization"] == (
        bath.SUPPORTED_BATH_CONVENTIONS["hybridization"]
    )
    assert definition["conventions"]["quadrature"] == (
        bath.SUPPORTED_BATH_CONVENTIONS["quadrature"]
    )
    assert definition["conventions"]["gamma_normalization"] == (
        "pi * sum_k V_k^2 = pi * gamma * bandwidth / 2"
    )


@pytest.mark.parametrize(
    ("gamma", "bandwidth", "n_bath"),
    [
        (-0.1, 1.0, 4),
        (True, 1.0, 4),
        ("0.1", 1.0, 4),
        (math.inf, 1.0, 4),
        (math.nan, 1.0, 4),
        (0.1, 0.0, 4),
        (0.1, -1.0, 4),
        (0.1, True, 4),
        (0.1, "1.0", 4),
        (0.1, math.inf, 4),
        (0.1, math.nan, 4),
        (0.1, 1.0, 0),
        (0.1, 1.0, -1),
        (0.1, 1.0, 2.5),
        (0.1, 1.0, True),
    ],
)
def test_discretization_rejects_invalid_parameters(gamma, bandwidth, n_bath):
    with pytest.raises((TypeError, ValueError)):
        bath.discretize_semicircular_bath(
            gamma=gamma, bandwidth=bandwidth, n_bath=n_bath
        )


def test_discretization_is_ordered_symmetric_and_has_nonnegative_couplings():
    epsilon, coupling = bath.discretize_semicircular_bath(
        gamma=0.2, bandwidth=1.0, n_bath=8
    )

    assert epsilon == sorted(epsilon, reverse=True)
    assert all(value > 0.0 for value in coupling)
    assert epsilon == pytest.approx([-value for value in reversed(epsilon)], abs=1e-15)
    assert coupling == pytest.approx(list(reversed(coupling)), abs=1e-15)

    _, zero_coupling = bath.discretize_semicircular_bath(
        gamma=0.0, bandwidth=1.0, n_bath=3
    )
    assert zero_coupling == [0.0, 0.0, 0.0]


@pytest.mark.parametrize("n_bath", [1, 2, 4, 17, 64])
def test_quadrature_has_exact_semicircle_spectral_weight(n_bath):
    gamma, bandwidth = 0.17, 1.3
    exact_weight = math.pi * gamma * bandwidth / 2.0

    _, coupling = bath.discretize_semicircular_bath(
        gamma=gamma, bandwidth=bandwidth, n_bath=n_bath
    )

    assert math.pi * math.fsum(value**2 for value in coupling) == pytest.approx(
        exact_weight, abs=2e-15
    )


def test_artifact_is_deterministic_auditable_and_records_broadening_conventions():
    grid = [-1.5, -0.75, 0.0, 0.75, 1.5]

    first = bath.make_bath_artifact(
        gamma=0.1, bandwidth=1.0, n_bath=4, frequency_grid=grid
    )
    second = bath.make_bath_artifact(
        gamma=0.1, bandwidth=1.0, n_bath=4, frequency_grid=grid
    )

    assert first == second
    payload = first["payload"]
    assert payload["schema_version"] == 2
    assert payload["parameters"] == {
        "gamma": 0.1,
        "bandwidth": 1.0,
        "n_bath": 4,
    }
    assert payload["conventions"]["hybridization"] == (
        "Gamma(omega) = pi * sum_k V_k^2 * delta(omega - epsilon_k)"
    )
    assert payload["conventions"]["quadrature"] == (
        "Gauss-Chebyshev quadrature of the second kind"
    )
    assert payload["conventions"]["target_continuum"] == (
        "Gamma_target(omega) = gamma * sqrt(1 - (omega / bandwidth)^2) "
        "for |omega| <= bandwidth; 0 otherwise"
    )
    assert payload["provenance"] == {
        "module": "bath",
        "module_version": bath.MODULE_VERSION,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "schema_version": 2,
    }
    assert payload["broadening"] == {
        "kernel": "normalized_gaussian",
        "width": 0.2,
        "width_rule": "bandwidth / (n_bath + 1)",
        "interpretation": (
            "broadened finite-bath realization; not the fitted continuum"
        ),
    }
    assert payload["frequency_grid"] == grid
    assert len(payload["epsilon"]) == 4
    assert len(payload["V"]) == 4
    assert payload["target_continuum_hybridization"] == pytest.approx(
        [0.0, 0.1 * math.sqrt(1.0 - 0.75**2), 0.1,
         0.1 * math.sqrt(1.0 - 0.75**2), 0.0]
    )
    broadened = payload["broadened_finite_bath_hybridization"]
    assert len(broadened) == len(grid)
    assert all(value >= 0.0 for value in broadened)

    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    assert first["sha256"] == hashlib.sha256(canonical).hexdigest()
    assert bath.verify_bath_artifact(first) is None


def test_artifact_verification_rejects_tampering_and_malformed_structure():
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=3,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact["payload"]["epsilon"][0] = 123.0
    with pytest.raises(ValueError, match="SHA256"):
        bath.verify_bath_artifact(artifact)

    for malformed in [None, {}, {"payload": {}, "sha256": "0" * 64}]:
        with pytest.raises((TypeError, ValueError)):
            bath.verify_bath_artifact(malformed)

    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=3,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    del artifact["payload"]["V"]
    artifact["sha256"] = hashlib.sha256(
        json.dumps(
            artifact["payload"],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="missing required keys"):
        bath.verify_bath_artifact(artifact)

    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=3,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact["payload"]["schema_version"] = 999
    artifact["sha256"] = hashlib.sha256(
        json.dumps(
            artifact["payload"],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="unsupported schema version"):
        bath.verify_bath_artifact(artifact)


def _rehash_artifact(artifact):
    artifact["sha256"] = hashlib.sha256(
        json.dumps(
            artifact["payload"],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return artifact


@pytest.mark.parametrize(
    "field",
    [
        "hybridization",
        "quadrature",
        "target_continuum",
        "ordering",
        "epsilon",
        "V_squared",
    ],
)
def test_verifier_rejects_every_validly_rehashed_convention_corruption(field):
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact["payload"]["conventions"][field] += " (corrupt)"

    with pytest.raises(ValueError, match="conventions"):
        bath.verify_bath_artifact(_rehash_artifact(artifact))


def test_artifact_emits_the_single_supported_convention_mapping():
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )

    assert artifact["payload"]["conventions"] == dict(
        bath.SUPPORTED_BATH_CONVENTIONS
    )


@pytest.mark.parametrize(
    ("path", "corrupt_value"),
    [
        (("broadening", "kernel"), "lorentzian"),
        (("broadening", "width_rule"), "arbitrary"),
        (("broadening", "interpretation"), "the fitted continuum"),
        (("broadening", "width"), 0.0),
        (("broadening", "width"), 0.123),
        (("provenance", "module"), "other_module"),
        (("provenance", "module_version"), ""),
        (("provenance", "python_version"), 3.12),
        (("provenance", "numpy_version"), "not a version"),
        (("provenance", "schema_version"), True),
    ],
)
def test_verifier_rejects_validly_rehashed_broadening_and_provenance_corruption(
    path, corrupt_value
):
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact = copy.deepcopy(artifact)
    artifact["payload"][path[0]][path[1]] = corrupt_value

    with pytest.raises((TypeError, ValueError)):
        bath.verify_bath_artifact(_rehash_artifact(artifact))


@pytest.mark.parametrize(
    ("array_name", "corrupt_value"),
    [
        ("target_continuum_hybridization", [0.0, 0.1]),
        ("broadened_finite_bath_hybridization", [0.0, "invalid", 0.0]),
    ],
)
def test_verifier_rejects_validly_rehashed_invalid_hybridization_arrays(
    array_name, corrupt_value
):
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact["payload"][array_name] = corrupt_value

    with pytest.raises((TypeError, ValueError)):
        bath.verify_bath_artifact(_rehash_artifact(artifact))


def test_verifier_requires_exact_integer_payload_schema_version():
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact["payload"]["schema_version"] = float(bath.SCHEMA_VERSION)

    with pytest.raises(ValueError, match="unsupported schema version"):
        bath.verify_bath_artifact(_rehash_artifact(artifact))


@pytest.mark.parametrize(
    ("array_name", "mutation"),
    [
        ("epsilon", "all_zero"),
        ("epsilon", "perturbed"),
        ("V", "all_zero"),
        ("V", "perturbed"),
        ("target_continuum_hybridization", "all_zero"),
        ("target_continuum_hybridization", "perturbed"),
        ("broadened_finite_bath_hybridization", "all_zero"),
        ("broadened_finite_bath_hybridization", "perturbed"),
    ],
)
def test_verifier_recomputes_every_derived_array(array_name, mutation):
    artifact = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=4,
        frequency_grid=[-1.2, -0.7, 0.0, 0.8, 1.2],
    )
    values = artifact["payload"][array_name]
    if mutation == "all_zero":
        artifact["payload"][array_name] = [0.0] * len(values)
    else:
        index = max(range(len(values)), key=lambda item: abs(values[item]))
        values[index] += max(1.0, abs(values[index])) * 1e-10

    with pytest.raises(ValueError, match=array_name):
        bath.verify_bath_artifact(_rehash_artifact(artifact))


@pytest.mark.parametrize(
    ("container", "field"),
    [
        ("broadening", "width"),
        ("payload", "target_continuum_hybridization"),
        ("payload", "broadened_finite_bath_hybridization"),
    ],
)
def test_verifier_rejects_nonfinite_broadening_data(container, field):
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    if container == "broadening":
        artifact["payload"][container][field] = math.inf
    else:
        artifact[container][field][1] = math.inf

    with pytest.raises(ValueError):
        bath.verify_bath_artifact(artifact)


def test_broadened_finite_bath_matches_independent_gaussian_calculation():
    gamma, bandwidth, n_bath = 0.2, 1.0, 3
    grid = [-0.6, 0.0, 0.7]
    artifact = bath.make_bath_artifact(
        gamma=gamma,
        bandwidth=bandwidth,
        n_bath=n_bath,
        frequency_grid=grid,
    )
    epsilon, coupling = bath.discretize_semicircular_bath(
        gamma=gamma, bandwidth=bandwidth, n_bath=n_bath
    )
    width = bandwidth / (n_bath + 1)

    expected = [
        math.pi
        * math.fsum(
            value**2
            * math.exp(-0.5 * ((omega - energy) / width) ** 2)
            / (math.sqrt(2.0 * math.pi) * width)
            for energy, value in zip(epsilon, coupling)
        )
        for omega in grid
    ]
    assert artifact["payload"][
        "broadened_finite_bath_hybridization"
    ] == pytest.approx(expected)


def test_broadened_finite_bath_integrates_to_discrete_spectral_weight():
    gamma, bandwidth, n_bath = 0.2, 1.0, 4
    width = bandwidth / (n_bath + 1)
    grid = np.linspace(-bandwidth - 8 * width, bandwidth + 8 * width, 20001)
    artifact = bath.make_bath_artifact(
        gamma=gamma,
        bandwidth=bandwidth,
        n_bath=n_bath,
        frequency_grid=grid.tolist(),
    )

    broadened = artifact["payload"]["broadened_finite_bath_hybridization"]
    integral = np.trapezoid(broadened, grid)
    assert integral == pytest.approx(math.pi * gamma * bandwidth / 2.0, rel=1e-12)


@pytest.mark.parametrize(
    "grid",
    [
        [],
        [0.0],
        [0.0, 0.0],
        [1.0, 0.0],
        [0.0, math.inf],
        [0.0, math.nan],
        [0.0, True],
        [0.0, "1.0"],
    ],
)
def test_artifact_rejects_unsafe_malformed_frequency_grids(grid):
    with pytest.raises((TypeError, ValueError)):
        bath.make_bath_artifact(
            gamma=0.1, bandwidth=1.0, n_bath=4, frequency_grid=grid
        )


def test_write_bath_json_uses_atomic_replace_and_canonical_json(tmp_path, monkeypatch):
    destination = tmp_path / "bath.json"
    replacements = []
    opened_directories = []
    fsynced = []
    real_replace = bath.os.replace
    real_open = bath.os.open
    real_fsync = bath.os.fsync

    def recording_replace(source, target):
        source = Path(source)
        target = Path(target)
        assert source.parent == target.parent
        assert source != target
        assert source.exists()
        replacements.append((source, target))
        real_replace(source, target)

    def recording_open(path, flags, mode=0o777):
        if Path(path) == tmp_path:
            opened_directories.append((Path(path), flags))
        return real_open(path, flags, mode)

    def recording_fsync(fd):
        fsynced.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(bath.os, "replace", recording_replace)
    monkeypatch.setattr(bath.os, "open", recording_open)
    monkeypatch.setattr(bath.os, "fsync", recording_fsync)

    artifact = bath.write_bath_json(
        destination,
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )

    assert replacements and replacements[0][1] == destination
    assert json.loads(destination.read_text(encoding="utf-8")) == artifact
    assert destination.read_bytes() == (
        json.dumps(
            artifact, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        + b"\n"
    )
    assert list(tmp_path.iterdir()) == [destination]
    assert opened_directories == [
        (tmp_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    ]
    assert len(fsynced) == 2


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
        raise OSError("injected write failure")

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def _existing_destination(tmp_path):
    destination = tmp_path / "bath.json"
    destination.write_bytes(b"original")
    return destination


def _assert_destination_preserved_without_temporary_files(tmp_path, destination):
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [destination]


def test_write_failure_preserves_destination_and_cleans_temporary(
    tmp_path, monkeypatch
):
    destination = _existing_destination(tmp_path)
    real_named_temporary_file = bath.tempfile.NamedTemporaryFile

    def failing_named_temporary_file(*args, **kwargs):
        return _FailingWriteFile(real_named_temporary_file(*args, **kwargs))

    monkeypatch.setattr(
        bath.tempfile, "NamedTemporaryFile", failing_named_temporary_file
    )
    with pytest.raises(OSError, match="injected write failure"):
        bath.write_bath_json(
            destination,
            gamma=0.1,
            bandwidth=1.0,
            n_bath=4,
            frequency_grid=[-1.0, 0.0, 1.0],
        )
    _assert_destination_preserved_without_temporary_files(tmp_path, destination)


def test_file_fsync_failure_preserves_destination_and_cleans_temporary(
    tmp_path, monkeypatch
):
    destination = _existing_destination(tmp_path)

    def failing_fsync(_fd):
        raise OSError("injected file fsync failure")

    monkeypatch.setattr(bath.os, "fsync", failing_fsync)
    with pytest.raises(OSError, match="injected file fsync failure"):
        bath.write_bath_json(
            destination,
            gamma=0.1,
            bandwidth=1.0,
            n_bath=4,
            frequency_grid=[-1.0, 0.0, 1.0],
        )
    _assert_destination_preserved_without_temporary_files(tmp_path, destination)


def test_replace_failure_preserves_destination_and_cleanup_cannot_mask_it(
    tmp_path, monkeypatch
):
    destination = _existing_destination(tmp_path)
    real_unlink = Path.unlink
    cleanup_attempted = False

    def failing_replace(_source, _target):
        raise OSError("injected replace failure")

    def failing_cleanup(path, *args, **kwargs):
        nonlocal cleanup_attempted
        cleanup_attempted = True
        real_unlink(path, *args, **kwargs)
        raise RuntimeError("injected cleanup failure")

    monkeypatch.setattr(bath.os, "replace", failing_replace)
    monkeypatch.setattr(Path, "unlink", failing_cleanup)
    with pytest.raises(OSError, match="injected replace failure"):
        bath.write_bath_json(
            destination,
            gamma=0.1,
            bandwidth=1.0,
            n_bath=4,
            frequency_grid=[-1.0, 0.0, 1.0],
        )
    assert cleanup_attempted
    _assert_destination_preserved_without_temporary_files(tmp_path, destination)


@pytest.mark.parametrize("existing", [False, True])
def test_parent_directory_fsync_failure_rolls_back_transaction(
    tmp_path, monkeypatch, existing
):
    destination = tmp_path / "bath.json"
    if existing:
        destination.write_bytes(b"original")
    directory_fsync_calls = []

    def fail_publication_fsync(directory):
        directory_fsync_calls.append(Path(directory))
        if len(directory_fsync_calls) == 1:
            raise OSError("injected parent fsync failure")

    monkeypatch.setattr(bath, "_fsync_directory", fail_publication_fsync)
    with pytest.raises(OSError, match="injected parent fsync failure"):
        bath.write_bath_json(
            destination,
            gamma=0.1,
            bandwidth=1.0,
            n_bath=4,
            frequency_grid=[-1.0, 0.0, 1.0],
        )

    assert directory_fsync_calls == [tmp_path, tmp_path]
    if existing:
        assert destination.read_bytes() == b"original"
        assert list(tmp_path.iterdir()) == [destination]
    else:
        assert not destination.exists()
        assert list(tmp_path.iterdir()) == []


def test_post_replace_failure_preserves_inode_metadata_and_external_hardlink(
    tmp_path, monkeypatch
):
    destination = _existing_destination(tmp_path)
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
            raise OSError("injected parent fsync failure")

    monkeypatch.setattr(bath, "_fsync_directory", fail_publication_fsync)
    with pytest.raises(OSError, match="injected parent fsync failure"):
        bath.write_bath_json(
            destination,
            gamma=0.1,
            bandwidth=1.0,
            n_bath=4,
            frequency_grid=[-1.0, 0.0, 1.0],
        )

    restored = destination.stat()
    assert directory_fsync_calls == [tmp_path, tmp_path]
    assert restored.st_ino == original.st_ino == external_link.stat().st_ino
    assert restored.st_mode == original.st_mode
    assert restored.st_mtime_ns == original.st_mtime_ns
    assert destination.read_bytes() == external_link.read_bytes() == b"original"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "bath.json",
        "external-link.json",
    ]


def test_existing_destination_success_cleans_backup_and_fsyncs_cleanup(
    tmp_path, monkeypatch
):
    destination = _existing_destination(tmp_path)
    directory_fsync_calls = []

    def recording_directory_fsync(directory):
        directory_fsync_calls.append(Path(directory))

    monkeypatch.setattr(bath, "_fsync_directory", recording_directory_fsync)
    bath.write_bath_json(
        destination,
        gamma=0.1,
        bandwidth=1.0,
        n_bath=4,
        frequency_grid=[-1.0, 0.0, 1.0],
    )

    assert directory_fsync_calls == [tmp_path, tmp_path]
    assert list(tmp_path.iterdir()) == [destination]
    assert destination.read_bytes() != b"original"


@pytest.mark.parametrize("destination_kind", ["directory", "symlink"])
def test_write_rejects_unsupported_existing_destination_types(
    tmp_path, destination_kind
):
    destination = tmp_path / "bath.json"
    if destination_kind == "directory":
        destination.mkdir()
    else:
        target = tmp_path / "target.json"
        target.write_bytes(b"target")
        destination.symlink_to(target)

    with pytest.raises(ValueError, match="regular file"):
        bath.write_bath_json(
            destination,
            gamma=0.1,
            bandwidth=1.0,
            n_bath=4,
            frequency_grid=[-1.0, 0.0, 1.0],
        )
