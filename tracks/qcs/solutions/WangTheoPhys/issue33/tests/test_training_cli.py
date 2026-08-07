import json

from vqetape.training_cli import main
from vqetape.training_spec import VQETrainingResult


def test_training_cli_writes_round_trip_result(tmp_path):
    output = tmp_path / "training.json"

    exit_code = main(
        [
            "--nqubits",
            "2",
            "--depth",
            "1",
            "--program",
            "z2-native",
            "--optimizer",
            "adam",
            "--initialization",
            "zeros",
            "--target-error",
            "0.3",
            "--max-steps",
            "2",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output.read_text())
    result = VQETrainingResult.from_dict(payload)
    assert result.converged
    assert result.request.program.symmetry == "z2-native"
