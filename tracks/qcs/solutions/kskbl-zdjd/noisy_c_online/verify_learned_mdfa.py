"""Independently reload and exhaustively verify a learned MDFA network."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from compile_learned_mdfa import evaluate_network
from hidden_oracle import CleanDomainEvaluator, DOMAIN_SIZE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", type=Path, required=True)
    args = parser.parse_args()

    network = json.loads(args.network.read_text(encoding="utf-8"))
    prediction = evaluate_network(network)
    targets = (
        CleanDomainEvaluator(torch.device("cpu"))
        .targets.cpu()
        .numpy()
        .astype(np.uint8)
    )
    matches = prediction == targets
    result = {
        "network": args.network.as_posix(),
        "domain_size": DOMAIN_SIZE,
        "gate_count": len(network["gates"]),
        "gate_breakdown": network["stats"]["gate_breakdown"],
        "bit_accuracy": float(matches.mean()),
        "word_accuracy": float(matches.all(axis=1).mean()),
        "exact_matches": int(matches.all(axis=1).sum()),
        "status": "verified" if matches.all() else "failed",
    }
    print(json.dumps(result, indent=2))
    if not matches.all():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
