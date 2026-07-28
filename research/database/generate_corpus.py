#!/usr/bin/env python3
"""Generate deterministic invariant-Hermitian benchmark instances from seed specs."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np


def _unitary(rng: np.random.Generator, n: int) -> np.ndarray:
    raw = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    q, r = np.linalg.qr(raw)
    phases = np.diag(r)
    phases = np.where(np.abs(phases) > 0, phases / np.abs(phases), 1.0)
    return q * phases.conj()


def generate_instance(spec: dict) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(spec["seed"])
    moduli = np.asarray(spec["moduli"], dtype=np.int64)
    characters = list(itertools.product(*(range(int(n)) for n in moduli)))
    populated = characters[: spec["populated_characters"]]
    labels = [character for character in populated for _ in range(spec["multiplicity"])]
    dimension = len(labels)

    symmetry_basis = _unitary(rng, dimension)
    generators = []
    for axis, modulus in enumerate(moduli):
        phases = np.asarray(
            [np.exp(2j * np.pi * character[axis] / int(modulus)) for character in labels]
        )
        generators.append(symmetry_basis @ np.diag(phases) @ symmetry_basis.conj().T)

    symmetry_matrix = np.zeros((dimension, dimension), dtype=np.complex128)
    offset = 0
    for _character in populated:
        size = spec["multiplicity"]
        raw = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
        block = (raw + raw.conj().T) / 2
        symmetry_matrix[offset : offset + size, offset : offset + size] = block
        offset += size
    matrix = symmetry_basis @ symmetry_matrix @ symmetry_basis.conj().T
    matrix = (matrix + matrix.conj().T) / 2
    return {
        "matrix": matrix,
        "generators": np.asarray(generators),
        "moduli": moduli,
    }


def build_specs(start: int, count: int) -> list[dict]:
    specs = []
    product_families = ([2, 2], [2, 3], [3, 3], [2, 2, 2])
    for index in range(count):
        global_index = start + index
        if global_index % 2 == 0:
            specs.append(
                {
                    "id": f"z2-{global_index:03d}",
                    "family": "z2",
                    "seed": 229_000 + global_index,
                    "moduli": [2],
                    "populated_characters": 2,
                    "multiplicity": 8 + global_index % 3,
                }
            )
        else:
            moduli = product_families[(global_index // 2) % len(product_families)]
            order = int(np.prod(moduli))
            specs.append(
                {
                    "id": f"product-{global_index:03d}",
                    "family": "product-cyclic",
                    "seed": 229_000 + global_index,
                    "moduli": list(moduli),
                    "populated_characters": order,
                    "multiplicity": 3 + global_index % 2,
                }
            )
    return specs


def write_corpus(spec_path: Path, output_dir: Path) -> None:
    specs = json.loads(spec_path.read_text())["instances"]
    output_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        np.savez_compressed(output_dir / f"{spec['id']}.npz", **generate_instance(spec))


def write_specs(path: Path, start: int, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "instances": build_specs(start, count)}, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--write-spec", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int)
    args = parser.parse_args()
    if args.write_spec:
        if args.count is None:
            parser.error("--write-spec requires --count")
        write_specs(args.write_spec, args.start, args.count)
    elif args.spec and args.output_dir:
        write_corpus(args.spec, args.output_dir)
    else:
        parser.error("provide --write-spec/--count or --spec/--output-dir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
