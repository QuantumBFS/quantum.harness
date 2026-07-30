"""Build #71 circuit and hidden-test prediction artifacts from the evolved synthesizer."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
HARNESS = HERE.parents[3]
OCCAM = HARNESS / "challenges" / "omnievolve" / "examples" / "occam_circuit"
DATASETS = OCCAM / "datasets"
INSTANCES = ("mystery-A", "mystery-B", "mystery-C", "mystery-D")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    synth = load_module("occam_submission_synth", OCCAM / "initial_code.py")
    verifier = load_module("occam_submission_verify", OCCAM / "verify_circuit.py")
    manifest = {
        "challenge": 71,
        "team": "quantumevolve",
        "encoding": "LSB-first",
        "instances": {},
    }
    predictions = HERE / "predictions"
    predictions.mkdir(exist_ok=True)

    for instance in INSTANCES:
        dataset = DATASETS / instance
        circuit_path = HERE / f"{instance}.txt"
        synth.TRAIN_FILE = str(dataset / "train.csv")
        synth.CIRCUIT_FILE = str(circuit_path)
        synth.run()

        n_inputs, gates, outputs = verifier.parse_netlist(circuit_path.read_text(encoding="utf-8"))
        with (dataset / "train.csv").open(newline="", encoding="utf-8") as handle:
            train_rows = list(csv.DictReader(handle))
        train_correct = sum(
            verifier.simulate(n_inputs, gates, outputs, row["input"]) == row["output"]
            for row in train_rows
        )
        if train_correct != len(train_rows):
            raise RuntimeError(f"{instance}: generated circuit does not fit all training rows")

        with (dataset / "test_inputs.csv").open(newline="", encoding="utf-8") as handle:
            test_inputs = [row["input"] for row in csv.DictReader(handle)]
        prediction_path = predictions / f"{instance}-test_outputs.csv"
        with prediction_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["output"])
            writer.writeheader()
            writer.writerows(
                {"output": verifier.simulate(n_inputs, gates, outputs, bits)}
                for bits in test_inputs
            )

        n, m, parsed = synth.read_train(str(dataset / "train.csv"))
        manifest["instances"][instance] = {
            "semantic_function": synth.detect(parsed, n, m),
            "input_bits": n_inputs,
            "output_bits": len(outputs),
            "train_exact": f"{train_correct}/{len(train_rows)}",
            "predicted_test_rows": len(test_inputs),
            "gates": len(gates),
            "circuit_sha256": sha256(circuit_path),
            "predictions_sha256": sha256(prediction_path),
            "commitment_file": (dataset / "commitment.sha256").read_text(
                encoding="utf-8"
            ).strip(),
        }

    (HERE / "submission_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
