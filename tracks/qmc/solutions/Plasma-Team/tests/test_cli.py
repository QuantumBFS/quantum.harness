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
