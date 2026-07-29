import json

from chiral_graviton.cli import main


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
