import json

import pytest

import chiral_graviton.cli as cli
from chiral_graviton.cli import main


def _valid_nqs_payload() -> dict:
    """Schema-v1 N=9-like payload at the largest accepted error scale."""

    return {
        "schema_version": 1,
        "method": "symmetry_projected_mlp_nqs_sparse",
        "n_electrons": 9,
        "two_q": 24,
        "e_l0": 7.771021392119608,
        "e_l2": 7.90153063632868,
        "gap": 0.13050924420907162,
        "l2_excited": 5.999999999999988,
        "energy_unit": "e^2/(epsilon*l_B)",
        "optimizer_success": True,
        "optimizer_message": "converged",
        "variance_l0": 6.153740948943307e-13,
        "variance_l2": 4.527516030858809e-12,
        "projection_certificate": {
            "l0": {"raising_residual": 1.9233407997950644e-10},
            "l2": {"raising_residual": 4.0478910009776134e-11},
        },
    }


def test_multiplet_command_writes_five_degenerate_components(tmp_path):
    output = tmp_path / "multiplet.json"
    code = main(["multiplet", "--n", "3", "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["m_values"] == [2, 1, 0, -1, -2]
    assert len(payload["energies"]) == 5
    assert payload["energy_spread"] < 1e-10
    assert payload["rotation_equivariance_error"] < 1e-10


def test_chirality_command_identifies_v1_dark_channel(tmp_path):
    output = tmp_path / "chirality.json"
    code = main(
        ["chirality", "--n", "3", "--interaction", "v1", "--output", str(output)]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["bright_minus_weight"] > 0.0
    assert payload["dark_plus_weight"] < 1e-20


def test_nqs_multiplet_command_rotates_neural_state(tmp_path):
    output = tmp_path / "nqs-multiplet.json"
    code = main(
        [
            "nqs-multiplet",
            "--n",
            "3",
            "--max-iterations",
            "5",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["m_values"] == [2, 1, 0, -1, -2]
    assert payload["energy_spread"] < 1e-10
    assert payload["rotation_equivariance_error"] < 1e-10


def test_nqs_command_fails_closed_when_optimizer_does_not_converge(tmp_path):
    output = tmp_path / "unconverged.json"
    code = main(
        [
            "nqs",
            "--n",
            "4",
            "--max-iterations",
            "0",
            "--samples",
            "10",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["optimizer_success"] is False
    assert payload["status"] == "failed"
    assert "sampled_gap" not in payload
    assert code == 3


def test_nqs_multiplet_fails_closed_when_optimizer_does_not_converge(tmp_path):
    output = tmp_path / "unconverged-multiplet.json"
    code = main(
        [
            "nqs-multiplet",
            "--n",
            "4",
            "--max-iterations",
            "0",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["optimizer_success"] is False
    assert payload["status"] == "failed"
    assert "m_values" not in payload
    assert code == 3


@pytest.mark.parametrize("status", ["partial", "failed"])
def test_validate_rejects_noncomplete_status(tmp_path, status):
    payload = _valid_nqs_payload()
    payload["status"] = status
    result = tmp_path / f"{status}.json"
    result.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(result)]) == 6


def test_validate_rejects_nonfinite_projection_certificate(tmp_path):
    payload = _valid_nqs_payload()
    payload["projection_certificate"]["l2"]["raising_residual"] = float("nan")
    result = tmp_path / "nonfinite-certificate.json"
    result.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(result)]) == 4


def test_validate_accepts_existing_n9_error_scale(tmp_path):
    result = tmp_path / "accepted.json"
    result.write_text(json.dumps(_valid_nqs_payload()), encoding="utf-8")
    assert main(["validate", str(result)]) == 0


def test_validate_rejects_optimizer_failure(tmp_path):
    payload = _valid_nqs_payload()
    payload["optimizer_success"] = False
    payload["optimizer_message"] = "iteration limit reached"
    result = tmp_path / "optimizer-failed.json"
    result.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(result)]) == 3


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), -float("inf")])
def test_validate_rejects_nonfinite_values(tmp_path, nonfinite):
    payload = _valid_nqs_payload()
    payload["variance_l2"] = nonfinite
    result = tmp_path / "nonfinite.json"
    result.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(result)]) == 4


@pytest.mark.parametrize(
    ("field", "value"),
    [("variance_l2", 1.01e-8), ("residual_l2", 1.01e-4)],
)
def test_validate_rejects_nqs_accuracy_threshold_failures(tmp_path, field, value):
    payload = _valid_nqs_payload()
    payload[field] = value
    result = tmp_path / "bad-accuracy.json"
    result.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(result)]) == 3


def test_ed_command_rejects_nonfinite_result_without_writing_json(tmp_path, monkeypatch):
    class NonfiniteResult:
        @staticmethod
        def to_dict():
            return {
                "n_electrons": 3,
                "two_q": 6,
                "e_l0": float("nan"),
                "e_l2": 1.2,
                "gap": float("nan"),
                "l2_excited": 6.0,
                "energy_unit": "e^2/(epsilon*l_B)",
                "interaction": "coulomb",
                "residual_l0": 1e-12,
                "residual_l2": 1e-12,
            }

    monkeypatch.setattr(cli, "neutral_gap", lambda *_args, **_kwargs: NonfiniteResult())
    output = tmp_path / "nonfinite-command.json"
    assert main(["ed", "--n", "3", "--output", str(output)]) == 4
    assert not output.exists()


def test_ed_command_fails_closed_on_large_residual(tmp_path, monkeypatch):
    class InaccurateResult:
        @staticmethod
        def to_dict():
            return {
                "n_electrons": 3, "two_q": 6, "e_l0": 1.0, "e_l2": 1.1,
                "gap": 0.1, "l2_excited": 6.0,
                "energy_unit": "e^2/(epsilon*l_B)", "interaction": "coulomb",
                "residual_l0": 1e-12, "residual_l2": 2e-8,
            }

    monkeypatch.setattr(cli, "neutral_gap", lambda *_args, **_kwargs: InaccurateResult())
    output = tmp_path / "inaccurate-ed.json"
    assert main(["ed", "--n", "3", "--output", str(output)]) == 3
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"


def test_nqs_chirality_uses_trained_nqs_states(tmp_path):
    output = tmp_path / "nqs-chirality.json"
    code = main(
        [
            "nqs-chirality",
            "--n",
            "3",
            "--interaction",
            "v1",
            "--hidden-width",
            "6",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["state_source"] == "trained_projected_nqs"
    assert payload["method"].startswith("nqs_rank2_parent_channel_chirality")
    assert payload["projected_irrep_error"] < 1e-7
    assert payload["bright_lowest_l2_weight"] > 0.0
    assert payload["dark_plus_weight"] < 1e-20
    assert "provenance" in payload


def test_nqs_chirality_fails_closed_when_optimizer_does_not_converge(tmp_path):
    output = tmp_path / "nqs-chirality-failed.json"
    code = main(
        [
            "nqs-chirality",
            "--n",
            "4",
            "--max-iterations",
            "0",
            "--output",
            str(output),
        ]
    )
    assert code == 3
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["failure_stage"] == "nqs_training"
    assert payload["quality_errors"]


def test_independent_oracle_command_is_validatable(tmp_path):
    output = tmp_path / "oracle-n3.json"
    assert main(["oracle", "--n", "3", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["method"] == "independent_first_quantized_chord_coulomb_oracle"
    assert payload["status"] == "complete"
    assert abs(payload["gap"] - 0.1189915765) < 2e-5
    assert main(["validate", str(output)]) == 0
