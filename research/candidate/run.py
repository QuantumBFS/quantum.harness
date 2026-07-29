#!/usr/bin/env python3
"""Candidate CLI: reduce every NPZ instance and emit one JSON artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from reducer import decompose_by_template, reduce_invariant_hermitian


def _complex_matrix(value: np.ndarray) -> list:
    return [[[float(z.real), float(z.imag)] for z in row] for row in value]


def _json_sector(sector: dict) -> dict:
    return {
        "label": sector["label"],
        "multiplicity": sector["multiplicity"],
        "irrep_dimension": sector["irrep_dimension"],
        "basis": _complex_matrix(sector["basis"]),
        "block": _complex_matrix(sector["block"]),
        "eigenvalues": [float(x) for x in np.linalg.eigvalsh(sector["block"])],
    }


def _write_template_result(output: Path, payload: dict, sectors: list[dict]) -> None:
    if output.suffix == ".json":
        output.write_text(json.dumps(payload, indent=2) + "\n")
        return
    if output.suffix == ".npz":
        metadata = {key: value for key, value in payload.items() if key != "sectors"}
        metadata["sectors"] = [
            {
                "label": sector["label"],
                "multiplicity": sector["multiplicity"],
                "irrep_dimension": sector["irrep_dimension"],
            }
            for sector in sectors
        ]
        arrays = {"metadata": np.asarray(json.dumps(metadata))}
        for index, sector in enumerate(sectors):
            arrays[f"sector_{index}_basis"] = sector["basis"]
            arrays[f"sector_{index}_block"] = sector["block"]
            arrays[f"sector_{index}_eigenvalues"] = np.linalg.eigvalsh(sector["block"])
        np.savez_compressed(output, **arrays)
        return
    raise ValueError("output must have a .json or .npz suffix")


def _run_template(args) -> int:
    path = Path(args.hamiltonian)
    if path.suffix == ".npy":
        matrix = np.load(path)
    elif path.suffix == ".npz":
        with np.load(path) as data:
            key = "H" if "H" in data else "matrix"
            matrix = data[key]
    else:
        raise ValueError("Hamiltonian input must be .npy or .npz")
    result = decompose_by_template(
        matrix, args.symmetry, local_dim=args.local_dim, sites=args.sites,
        tolerance=args.tolerance,
    )
    payload = {
        "schema_version": 1,
        "input": str(path),
        "symmetry": result["symmetry"],
        "dimension": result["dimension"],
        "local_dim": result["local_dim"],
        "sites": result["sites"],
        "commutator_residual": result["commutator_residual"],
        "spectrum_reconstruction_error": result["spectrum_reconstruction_error"],
        "sectors": [_json_sector(sector) for sector in result["sectors"]],
    }
    output = Path(args.output)
    _write_template_result(output, payload, result["sectors"])
    print(
        f'matched {result["symmetry"]}: {result["sites"]} sites x '
        f'local_dim={result["local_dim"]}; residual={result["commutator_residual"]:.3e}',
        flush=True,
    )
    for sector in result["sectors"]:
        print(
            f'{sector["label"]}: multiplicity={sector["multiplicity"]}, '
            f'irrep_dim={sector["irrep_dimension"]}, block={sector["block"].shape[0]}x'
            f'{sector["block"].shape[1]}',
            flush=True,
        )
    print(f"wrote {output}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("hamiltonian", nargs="?", help="Hamiltonian .npy/.npz for automatic template matching")
    parser.add_argument("--symmetry", choices=("su2", "u1", "z2", "translation", "auto"))
    parser.add_argument("--local-dim", type=int)
    parser.add_argument("--sites", type=int)
    parser.add_argument("--tolerance", type=float, default=1e-10)
    parser.add_argument("--input-dir")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.hamiltonian:
        if not args.symmetry:
            parser.error("Hamiltonian mode requires --symmetry")
        if args.input_dir:
            parser.error("choose a Hamiltonian or --input-dir, not both")
        return _run_template(args)
    if not args.input_dir:
        parser.error("provide a Hamiltonian or --input-dir")

    results = []
    for path in sorted(Path(args.input_dir).glob("*.npz")):
        with np.load(path) as data:
            reduction = reduce_invariant_hermitian(data["matrix"], data["generators"], data["moduli"])
        results.append(
            {
                "id": path.stem,
                "method": "character_projectors",
                "dimension": reduction["dimension"],
                "moduli": reduction["moduli"],
                "sectors": [
                    {
                        "character": sector["character"],
                        "basis": _complex_matrix(sector["basis"]),
                        "block": _complex_matrix(sector["block"]),
                        "eigenvalues": [float(x) for x in sector["eigenvalues"]],
                    }
                    for sector in reduction["sectors"]
                ],
            }
        )
    Path(args.output).write_text(json.dumps({"schema_version": 1, "instances": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
