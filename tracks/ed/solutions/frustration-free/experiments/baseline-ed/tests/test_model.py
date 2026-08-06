from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.diagonalization import diagonalize_full
from src.io_utils import deterministic_filename, load_config, model_from_config, save_result
from src.model import RiceMeleModel


def load_legacy_module():
    legacy_path = PROJECT_ROOT / "run_rice_mele_ed.py"
    spec = importlib.util.spec_from_file_location("legacy_run_rice_mele_ed", legacy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load legacy module from {legacy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def default_model(**overrides) -> RiceMeleModel:
    parameters = {
        "L": 6,
        "t": 1.0,
        "delta": 0.5,
        "Delta": 0.3,
        "theta": 2.0 * np.pi,
        "N_up": 3,
        "N_down": 3,
    }
    parameters.update(overrides)
    return RiceMeleModel(**parameters)


@pytest.fixture(scope="module")
def default_result():
    return diagonalize_full(default_model())


def test_l6_half_filled_basis_has_dimension_400():
    assert default_model().basis.Ns == 400


def test_hamiltonian_is_hermitian():
    assert default_model().hermiticity_error() < 1e-12


def test_model_parameters_cannot_diverge_from_constructed_hamiltonian():
    model = default_model()

    with pytest.raises(FrozenInstanceError):
        model.delta = 0.75


@pytest.mark.parametrize("name,value", [("t", "1.0"), ("theta", True)])
def test_model_rejects_non_numeric_continuous_parameters(name, value):
    with pytest.raises(ValueError, match=f"{name} must be a real number"):
        default_model(**{name: value})


def test_theta_zero_and_two_pi_hamiltonians_are_periodic():
    zero = default_model(theta=0.0).hamiltonian.toarray()
    period = default_model(theta=2.0 * np.pi).hamiltonian.toarray()

    assert np.allclose(zero, period, atol=1e-12)


def test_nontrivial_twist_matrix_matches_legacy_mvp_exactly():
    parameters = {
        "L": 6,
        "t": 1.2,
        "delta": 0.41,
        "Delta": -0.23,
        "theta": 0.37,
    }
    new_matrix = RiceMeleModel(
        **parameters,
        N_up=3,
        N_down=3,
    ).hamiltonian.toarray()
    legacy = load_legacy_module()
    _, legacy_hamiltonian = legacy.build_rice_mele_hamiltonian(**parameters)

    assert np.array_equal(new_matrix, legacy_hamiltonian.toarray())


def test_full_diagonalization_shapes_and_ordering(default_result):
    assert default_result.eigenvalues.shape == (400,)
    assert default_result.eigenvectors.shape == (400, 400)
    assert np.all(np.diff(default_result.eigenvalues) >= -1e-12)


def test_full_diagonalization_is_orthonormal_and_satisfies_eigenproblem(default_result):
    assert default_result.orthogonality_error < 1e-10
    assert default_result.maximum_residual < 1e-10


def test_validated_eigensystem_arrays_are_read_only(default_result):
    assert not default_result.eigenvalues.flags.writeable
    assert not default_result.eigenvectors.flags.writeable
    with pytest.raises(ValueError):
        default_result.eigenvalues[0] = 0.0


def test_theta_zero_and_two_pi_spectra_are_periodic():
    zero = diagonalize_full(default_model(theta=0.0)).eigenvalues
    period = diagonalize_full(default_model(theta=2.0 * np.pi)).eigenvalues

    assert np.allclose(zero, period, atol=1e-12)


def test_default_config_preserves_delta_case():
    config = load_config(PROJECT_ROOT / "configs" / "default.yaml")

    assert config["delta"] == 0.5
    assert config["Delta"] == 0.3
    assert model_from_config(config).parameters() == {
        "L": 6,
        "t": 1.0,
        "delta": 0.5,
        "Delta": 0.3,
        "theta": 2.0 * np.pi,
        "N_up": 3,
        "N_down": 3,
    }


def test_yaml_duplicate_keys_are_rejected(tmp_path):
    config_path = tmp_path / "duplicate.yaml"
    config_path.write_text(
        "L: 6\n"
        "t: 1.0\n"
        "delta: 0.5\n"
        "delta: 0.6\n"
        "Delta: 0.3\n"
        "theta: 6.283185307179586\n"
        "N_up: 3\n"
        "N_down: 3\n"
        "full_spectrum: true\n"
        "output_dir: results\n"
    )

    with pytest.raises(ValueError, match="duplicate YAML key: delta"):
        load_config(config_path)


def test_output_filename_is_deterministic():
    model = default_model()

    assert deterministic_filename(model) == deterministic_filename(model)
    assert deterministic_filename(model).endswith(".npz")


def test_distinct_float_parameters_have_distinct_filenames():
    first = default_model(theta=1.0)
    second = default_model(theta=1.0 + 1e-13)

    assert deterministic_filename(first) != deterministic_filename(second)


def test_npz_contains_complete_eigensystem(tmp_path, default_result):
    model = default_model()
    output = save_result(model, default_result, tmp_path)

    with np.load(output) as data:
        assert data["eigenvalues"].shape == (400,)
        assert data["eigenvectors"].shape == (400, 400)
        assert json.loads(str(data["parameters_json"])) == model.parameters()
        diagnostics = json.loads(str(data["diagnostics_json"]))
        assert diagnostics["orthogonality_error"] < 1e-10
        assert diagnostics["maximum_residual"] < 1e-10


def test_run_script_writes_complete_npz(tmp_path):
    config = load_config(PROJECT_ROOT / "configs" / "default.yaml")
    config["output_dir"] = str(tmp_path / "results")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_ed.py"),
            "--config",
            str(config_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Hilbert space dimension: 400" in completed.stdout
    outputs = list((tmp_path / "results").glob("*.npz"))
    assert len(outputs) == 1
    with np.load(outputs[0]) as data:
        assert data["eigenvalues"].shape == (400,)
        assert data["eigenvectors"].shape == (400, 400)
