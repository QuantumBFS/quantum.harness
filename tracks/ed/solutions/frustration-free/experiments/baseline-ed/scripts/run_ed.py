#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.diagonalization import diagonalize_full
from src.io_utils import load_config, model_from_config, save_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full Rice-Mele exact diagonalization")
    parser.add_argument("--config", type=Path, required=True, help="YAML configuration path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    model = model_from_config(config)
    result = diagonalize_full(model)

    output_dir = Path(config["output_dir"])
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_path = save_result(model, result, output_dir)

    print("Parameters:", json.dumps(model.parameters(), sort_keys=True))
    print(f"Hilbert space dimension: {model.basis.Ns}")
    print("Lowest eigenvalues:", result.eigenvalues[:8])
    print(f"Orthogonality error: {result.orthogonality_error:.3e}")
    print(f"Maximum eigenproblem residual: {result.maximum_residual:.3e}")
    print(f"Saved result: {output_path}")


if __name__ == "__main__":
    main()
