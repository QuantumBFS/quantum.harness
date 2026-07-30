from __future__ import annotations

import copy
from pathlib import Path
import pickle
import sys

import h5py
import numpy as np
import pytest


TRIQS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TRIQS_DIR.parents[4]
sys.path.insert(0, str(TRIQS_DIR))

from artifacts import canonical_json, sha256_bytes, strict_json_load
from make_input import make_production_input, verify_input
from source_manifest import REQUIRED_SOURCE_PATHS, build_source_manifest
import run_chain as runner


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _complete_repository(tmp_path: Path) -> Path:
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
    return solution_dir


def _input_fixture(tmp_path: Path, monkeypatch) -> tuple[Path, dict[str, object], Path]:
    solution_dir = _complete_repository(tmp_path)
    artifact = make_production_input(solution_dir)
    input_path = tmp_path / "cthyb-input.json"
    input_path.write_bytes(canonical_json(artifact) + b"\n")
    monkeypatch.setattr(runner, "SOLUTION_DIR", solution_dir)
    return input_path, artifact, solution_dir


class FakeArchive:
    def __init__(self, path: str, mode: str):
        self.path = path
        self.mode = mode
        self.handle = None

    def __enter__(self):
        self.handle = h5py.File(self.path, self.mode)
        return self

    def __exit__(self, *args):
        self.handle.close()

    def __setitem__(self, key: str, value: object) -> None:
        encoded = np.frombuffer(pickle.dumps(value, protocol=5), dtype=np.uint8)
        self.handle.create_dataset(key, data=encoded)

    def __getitem__(self, key: str) -> object:
        return pickle.loads(bytes(self.handle[key][...]))

    def keys(self):
        return self.handle.keys()


class FakeMesh:
    def __init__(self, omega: np.ndarray, beta: float):
        self.omega = omega
        self.beta = beta

    def __iter__(self):
        return iter(1j * self.omega)


class FakeBlock:
    def __init__(self, size: int, mesh):
        self.mesh = mesh
        self.data = np.zeros((size, 1, 1), dtype=np.complex128)


class FakeBlocks:
    indices = ("up", "down")

    def __init__(self, size: int, mesh):
        self.blocks = {spin: FakeBlock(size, mesh) for spin in self.indices}

    def __getitem__(self, spin: str):
        return self.blocks[spin]


class FakeOperator:
    def __init__(self, name: str):
        self.name = name

    def __mul__(self, other):
        return FakeOperator(f"{self.name}*{other.name}")

    def __rmul__(self, coefficient):
        assert coefficient == 0.8
        return self


class FakeSolver:
    instances: list["FakeSolver"] = []

    def __init__(self, *, beta, gf_struct, n_iw, n_tau):
        self.constructor = {
            "beta": beta,
            "gf_struct": gf_struct,
            "n_iw": n_iw,
            "n_tau": n_tau,
        }
        omega = (2 * np.arange(-n_iw, n_iw) + 1) * np.pi / beta
        self.G0_iw = FakeBlocks(2 * n_iw, FakeMesh(omega, beta))
        self.G_iw = FakeBlocks(2 * n_iw, FakeMesh(omega, beta))
        tau = np.linspace(0.0, beta, n_tau)
        self.G_tau = FakeBlocks(n_tau, tau)
        self.G_tau["up"].data[:, 0, 0] = -0.53 + 0.06 * tau / beta
        self.G_tau["down"].data[:, 0, 0] = -0.52 + 0.04 * tau / beta
        self.Delta_iw = {
            spin: np.zeros(2 * n_iw, dtype=np.complex128)
            for spin in ("up", "down")
        }
        self.density_matrix = {"n_up": 0.47, "n_down": 0.48, "double": 0.12}
        self.h_loc_diagonalization = {"basis": "fake"}
        self.perturbation_order = {"up": [1, 2], "down": [1, 2]}
        self.average_sign = 0.999
        self.auto_corr_time = 2.0
        self.auto_corr_time_converged = True
        self.solve_status = "normal"
        self.last_configuration = {"order": 2}
        self.solve_parameters = None
        self.solve_calls = []
        type(self).instances.append(self)

    def solve(self, **parameters):
        self.solve_calls.append(parameters)
        self.solve_parameters = dict(parameters)


TRACE_CALLS: list[str] = []


def fake_n(spin: str, orbital: int) -> FakeOperator:
    assert orbital == 0
    return FakeOperator(spin)


def fake_trace(density_matrix, operator, h_loc_diagonalization):
    TRACE_CALLS.append(operator.name)
    assert h_loc_diagonalization == {"basis": "fake"}
    return {
        "up": density_matrix["n_up"],
        "down": density_matrix["n_down"],
        "up*down": density_matrix["double"],
    }[operator.name]


@pytest.fixture
def fake_runtime(monkeypatch):
    FakeSolver.instances.clear()
    TRACE_CALLS.clear()
    monkeypatch.setattr(runner, "_solver_class", lambda: FakeSolver)
    monkeypatch.setattr(runner, "_archive_class", lambda: FakeArchive)
    monkeypatch.setattr(runner, "_number_operator", fake_n)
    monkeypatch.setattr(runner, "_trace_rho_op", fake_trace)
    monkeypatch.setattr(runner, "_mpi_size", lambda: 1)
    monkeypatch.setattr(
        runner,
        "_runtime_identity",
        lambda: {
            "python": "3.12.13",
            "numpy": np.__version__,
            "triqs": "4.0.0",
            "triqs_cthyb": "4.0.0",
            "hdf5": h5py.version.hdf5_version,
        },
    )
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        monkeypatch.setenv(name, "1")


def test_run_chain_binds_solver_controls_raw_evidence_and_reload(
    tmp_path, monkeypatch, fake_runtime
):
    input_path, artifact, _ = _input_fixture(tmp_path, monkeypatch)
    output_root = tmp_path / "results"

    bundle = runner.run_chain(input_path, 0, output_root)

    assert bundle == (
        output_root / "work" / artifact["sha256"] / "chain-000"
    )
    solver = FakeSolver.instances[0]
    assert solver.constructor == {
        "beta": 16.0,
        "gf_struct": [("up", 1), ("down", 1)],
        "n_iw": 2049,
        "n_tau": 4001,
    }
    parameters = solver.solve_calls[0]
    assert parameters["random_seed"] == 810001
    assert parameters["random_name"] == "mt19937"
    assert parameters["n_warmup_cycles"] == 50000
    assert parameters["n_cycles"] == 1000000
    assert parameters["length_cycle"] == 50
    assert parameters["measure_G_tau"] is True
    assert parameters["measure_density_matrix"] is True
    assert parameters["use_norm_as_weight"] is True
    assert parameters["measure_pert_order"] is True
    assert parameters["performance_analysis"] is False
    assert parameters["h_int"].name == "up*down"
    assert TRACE_CALLS.count("up") >= 2
    assert TRACE_CALLS.count("down") >= 2
    assert TRACE_CALLS.count("up*down") >= 2

    summary = strict_json_load(bundle / "chain-summary.json")
    payload = runner.validate_chain_bundle(bundle, artifact, 0)
    assert payload == summary["payload"]
    assert payload["seed"] == 810001
    assert payload["observables"]["n_up"] == 0.47
    assert payload["observables"]["n_down"] == 0.48
    assert payload["observables"]["double_occupancy"] == 0.12
    assert payload["observables"]["G_up"] == pytest.approx(
        [-0.53, -0.515, -0.5, -0.485, -0.47]
    )
    assert payload["observables"]["G_down"] == pytest.approx(
        [-0.52, -0.51, -0.5, -0.49, -0.48]
    )
    assert payload["raw_h5_sha256"] == runner.sha256_file(bundle / "raw.h5")
    assert payload["provenance"]["runtime"]["triqs"] == "4.0.0"
    assert payload["provenance"]["source_manifest"] == artifact["payload"][
        "provenance_inputs"
    ]["source_manifest"]
    with h5py.File(bundle / "raw.h5", "r") as archive:
        assert set(archive) == set(runner.RAW_ARCHIVE_MEMBERS)
    with FakeArchive(str(bundle / "raw.h5"), "r") as archive:
        assert bytes(archive["input_bytes"]) == input_path.read_bytes()
    assert strict_json_load(bundle / "completion.json")["payload"][
        "chain_summary_sha256"
    ] == summary["sha256"]
    assert not list(bundle.parent.glob(".attempt-*"))


def test_valid_completed_chain_is_reused_without_solver(
    tmp_path, monkeypatch, fake_runtime
):
    input_path, _, _ = _input_fixture(tmp_path, monkeypatch)
    first = runner.run_chain(input_path, 1, tmp_path / "results")
    second = runner.run_chain(input_path, 1, tmp_path / "results")
    assert second == first
    assert len(FakeSolver.instances) == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda solver: setattr(solver, "density_matrix", None), "density"),
        (lambda solver: setattr(solver, "solve_status", "max_time"), "status"),
        (
            lambda solver: setattr(solver, "auto_corr_time_converged", False),
            "autocorrelation",
        ),
        (lambda solver: setattr(solver, "average_sign", float("nan")), "finite"),
    ],
)
def test_runner_rejects_incomplete_or_invalid_solver_evidence(
    tmp_path, monkeypatch, fake_runtime, mutation, message
):
    class InvalidSolver(FakeSolver):
        def solve(self, **parameters):
            super().solve(**parameters)
            mutation(self)

    monkeypatch.setattr(runner, "_solver_class", lambda: InvalidSolver)
    input_path, _, _ = _input_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match=message):
        runner.run_chain(input_path, 0, tmp_path / "results")
    assert not list((tmp_path / "results").rglob("chain-000"))


def test_runner_rejects_wrong_index_mpi_threads_and_false_controls(
    tmp_path, monkeypatch, fake_runtime
):
    input_path, artifact, solution_dir = _input_fixture(tmp_path, monkeypatch)
    for index in (-1, 4, True):
        with pytest.raises((TypeError, ValueError)):
            runner.run_chain(input_path, index, tmp_path / f"index-{index}")

    monkeypatch.setattr(runner, "_mpi_size", lambda: 2)
    with pytest.raises(RuntimeError, match="MPI"):
        runner.run_chain(input_path, 0, tmp_path / "mpi")
    monkeypatch.setattr(runner, "_mpi_size", lambda: 1)

    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(RuntimeError, match="OMP_NUM_THREADS"):
        runner.run_chain(input_path, 0, tmp_path / "threads")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    changed = copy.deepcopy(artifact)
    changed["payload"]["monte_carlo"]["use_norm_as_weight"] = False
    changed["sha256"] = sha256_bytes(canonical_json(changed["payload"]))
    bad_input = tmp_path / "bad-input.json"
    bad_input.write_bytes(canonical_json(changed) + b"\n")
    monkeypatch.setattr(runner, "SOLUTION_DIR", solution_dir)
    with pytest.raises(ValueError):
        runner.run_chain(bad_input, 0, tmp_path / "false-control")


def test_validation_rejects_corruption_missing_member_symlink_and_rederived_mismatch(
    tmp_path, monkeypatch, fake_runtime
):
    input_path, artifact, _ = _input_fixture(tmp_path, monkeypatch)

    corrupt = runner.run_chain(input_path, 0, tmp_path / "corrupt")
    with (corrupt / "raw.h5").open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(ValueError, match="raw.h5"):
        runner.validate_chain_bundle(corrupt, artifact, 0)

    missing = runner.run_chain(input_path, 0, tmp_path / "missing")
    with h5py.File(missing / "raw.h5", "a") as archive:
        del archive["G_tau"]
    _rehash_raw_references(missing)
    with pytest.raises(ValueError, match="member"):
        runner.validate_chain_bundle(missing, artifact, 0)

    symlinked = runner.run_chain(input_path, 0, tmp_path / "symlinked")
    raw = symlinked / "raw.h5"
    saved = tmp_path / "saved.h5"
    raw.rename(saved)
    raw.symlink_to(saved)
    with pytest.raises(ValueError, match="symlink"):
        runner.validate_chain_bundle(symlinked, artifact, 0)

    mismatch = runner.run_chain(input_path, 0, tmp_path / "mismatch")
    summary_path = mismatch / "chain-summary.json"
    summary = strict_json_load(summary_path)
    summary["payload"]["observables"]["n_up"] = 0.25
    summary["sha256"] = sha256_bytes(canonical_json(summary["payload"]))
    summary_path.write_bytes(canonical_json(summary) + b"\n")
    completion = strict_json_load(mismatch / "completion.json")
    completion["payload"]["chain_summary_sha256"] = summary["sha256"]
    completion["sha256"] = sha256_bytes(canonical_json(completion["payload"]))
    (mismatch / "completion.json").write_bytes(canonical_json(completion) + b"\n")
    with pytest.raises(ValueError, match="reproduc"):
        runner.validate_chain_bundle(mismatch, artifact, 0)


def _rehash_raw_references(bundle: Path) -> None:
    digest = runner.sha256_file(bundle / "raw.h5")
    summary = strict_json_load(bundle / "chain-summary.json")
    summary["payload"]["raw_h5_sha256"] = digest
    summary["sha256"] = sha256_bytes(canonical_json(summary["payload"]))
    (bundle / "chain-summary.json").write_bytes(canonical_json(summary) + b"\n")
    completion = strict_json_load(bundle / "completion.json")
    completion["payload"]["raw_h5_sha256"] = digest
    completion["payload"]["chain_summary_sha256"] = summary["sha256"]
    completion["sha256"] = sha256_bytes(canonical_json(completion["payload"]))
    (bundle / "completion.json").write_bytes(canonical_json(completion) + b"\n")


def test_wrong_seed_summary_and_corrupt_completed_bundle_fail_closed(
    tmp_path, monkeypatch, fake_runtime
):
    input_path, artifact, _ = _input_fixture(tmp_path, monkeypatch)
    bundle = runner.run_chain(input_path, 0, tmp_path / "results")
    summary = strict_json_load(bundle / "chain-summary.json")
    summary["payload"]["seed"] = 810004
    summary["sha256"] = sha256_bytes(canonical_json(summary["payload"]))
    (bundle / "chain-summary.json").write_bytes(canonical_json(summary) + b"\n")
    completion = strict_json_load(bundle / "completion.json")
    completion["payload"]["chain_summary_sha256"] = summary["sha256"]
    completion["sha256"] = sha256_bytes(canonical_json(completion["payload"]))
    (bundle / "completion.json").write_bytes(canonical_json(completion) + b"\n")

    with pytest.raises(ValueError, match="seed"):
        runner.validate_chain_bundle(bundle, artifact, 0)
    with pytest.raises(ValueError, match="seed"):
        runner.run_chain(input_path, 0, tmp_path / "results")
    assert len(FakeSolver.instances) == 1


def test_stale_source_or_schema_blocks_execution_before_solver(
    tmp_path, monkeypatch, fake_runtime
):
    for relative in (
        "tracks/mps/solutions/frustration-free/triqs/run_chain.py",
        "tracks/mps/solutions/frustration-free/triqs/cthyb-chain.schema.json",
    ):
        case = tmp_path / Path(relative).name
        input_path, _, solution_dir = _input_fixture(case, monkeypatch)
        (solution_dir.parents[4] / relative).write_bytes(b"changed\n")
        with pytest.raises(ValueError, match="hash"):
            runner.run_chain(input_path, 0, case / "results")
    assert not FakeSolver.instances


def test_startup_archives_abandoned_attempt(tmp_path, monkeypatch, fake_runtime):
    input_path, artifact, _ = _input_fixture(tmp_path, monkeypatch)
    work = tmp_path / "results" / "work" / artifact["sha256"]
    attempt = work / ".attempt-chain-000-old"
    attempt.mkdir(parents=True)
    (attempt / "partial").write_text("partial", encoding="utf-8")

    runner.run_chain(input_path, 0, tmp_path / "results")

    abandoned = list(work.glob(".abandoned-chain-000-*"))
    assert len(abandoned) == 1
    assert (abandoned[0] / "partial").read_text(encoding="utf-8") == "partial"


def test_test_pilot_profile_is_bounded_and_production_rejects_it(
    tmp_path, monkeypatch, fake_runtime
):
    _, production, solution_dir = _input_fixture(tmp_path, monkeypatch)
    pilot = runner.make_test_pilot_input(production)
    with pytest.raises(ValueError):
        verify_input(pilot, solution_dir)
    assert pilot["payload"]["artifact_type"] == "cthyb_test_input"
    assert pilot["payload"]["monte_carlo"]["warmup_cycles"] == 50
    assert pilot["payload"]["monte_carlo"]["measurement_cycles"] == 200
    assert pilot["payload"]["gates"]["minimum_effective_samples_per_chain"] == 1
    assert pilot["payload"]["gates"]["minimum_effective_samples_total"] == 4

    path = tmp_path / "pilot-input.json"
    path.write_bytes(canonical_json(pilot) + b"\n")
    bundle = runner.run_chain(path, 0, tmp_path / "pilot")

    call = FakeSolver.instances[0].solve_calls[0]
    assert call["n_warmup_cycles"] == 50
    assert call["n_cycles"] == 200
    summary = strict_json_load(bundle / "chain-summary.json")
    assert summary["payload"]["input_sha256"] == pilot["sha256"]


def test_exact_bounded_locked_prefix_pilot_command_is_available():
    command = runner.locked_prefix_pilot_command(
        Path("/opt/ch81/triqs-4.0.0"),
        Path("/data/ch81/cthyb-input.json"),
        0,
        Path("/tmp/ch81-cthyb-chain-pilot"),
    )
    assert command == [
        "/usr/bin/env",
        "OMP_NUM_THREADS=1",
        "OPENBLAS_NUM_THREADS=1",
        "MKL_NUM_THREADS=1",
        "/opt/ch81/micromamba",
        "run",
        "--offline",
        "--prefix",
        "/opt/ch81/triqs-4.0.0",
        "python",
        str(TRIQS_DIR / "run_chain.py"),
        "--input",
        "/data/ch81/cthyb-input.json",
        "--chain-index",
        "0",
        "--output-root",
        "/tmp/ch81-cthyb-chain-pilot",
        "--test-pilot",
    ]
