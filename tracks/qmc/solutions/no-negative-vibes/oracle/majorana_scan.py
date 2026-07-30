"""Resumable scans of Majorana-positive cones and controlled relaxations."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

import numpy as np

from . import __version__
from .majorana import (
    canonical_reflection_structures,
    plane_rotation,
    random_reflection_generator,
    reflection_structure_residual,
    shared_reality_rotation,
    spin_trace_weight,
)


_CASES = {
    "mrp_common",
    "mrp_rotated_common",
    "mrp_shared_j1_mixed",
    "mrp_broken_j1_mixed",
    "mrp_indefinite",
}
_CLASSIFICATIONS = ("positive", "negative", "zero", "complex", "uncertain")


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _encode_matrix(matrix: np.ndarray) -> dict[str, object]:
    array = np.asarray(matrix)
    return {"real": array.real.tolist(), "imag": array.imag.tolist()}


def _sample_generators(
    *,
    case: str,
    rng: np.random.Generator,
    block_size: int,
    depth: int,
    scale: float,
    angle: float,
) -> tuple[list[np.ndarray], list[tuple[np.ndarray, np.ndarray]]]:
    j1, j2 = canonical_reflection_structures(block_size)
    shared_rotation = shared_reality_rotation(block_size, angle=angle)
    broken_rotation = plane_rotation(2 * block_size, angle=angle)
    generators: list[np.ndarray] = []
    structures: list[tuple[np.ndarray, np.ndarray]] = []

    for level in range(depth):
        cone = "indefinite" if case == "mrp_indefinite" else "positive"
        generator = random_reflection_generator(
            rng,
            block_size=block_size,
            scale=scale,
            cone=cone,
        )
        rotation: np.ndarray | None = None
        if case == "mrp_rotated_common":
            rotation = shared_rotation
        elif case == "mrp_shared_j1_mixed" and level % 2:
            rotation = shared_rotation
        elif case == "mrp_broken_j1_mixed" and level % 2:
            rotation = broken_rotation

        if rotation is not None:
            generator = rotation @ generator @ rotation.T
            structures.append(
                (rotation @ j1 @ rotation.T, rotation @ j2 @ rotation.T)
            )
        else:
            structures.append((j1, j2))
        generators.append(generator)

    return generators, structures


def scan_cell(
    *,
    case: str,
    block_size: int,
    depth: int,
    scale: float,
    angle: float,
    seed: int,
    samples: int,
) -> dict[str, object]:
    if case not in _CASES:
        raise ValueError(f"unknown case: {case}")
    if block_size < 2:
        raise ValueError("block_size must be at least two")
    if depth < 1 or samples < 1:
        raise ValueError("depth and samples must be positive")

    rng = np.random.default_rng(seed)
    counts = {classification: 0 for classification in _CLASSIFICATIONS}
    max_structure_residual = 0.0
    max_common_reality_residual = 0.0
    max_square_identity_residual = 0.0
    max_reliable_square_identity_residual = 0.0
    unreliable_determinant_checks = 0
    nonfinite_determinant_diagnostics = 0
    min_cancellation_ratio = math.inf
    examples: dict[str, dict[str, object]] = {}
    example_margins: dict[str, float] = {}
    common_j1, _ = canonical_reflection_structures(block_size)

    for _ in range(samples):
        generators, structures = _sample_generators(
            case=case,
            rng=rng,
            block_size=block_size,
            depth=depth,
            scale=scale,
            angle=angle,
        )
        require_cone = case != "mrp_indefinite"
        for generator, (j1, j2) in zip(generators, structures):
            max_structure_residual = max(
                max_structure_residual,
                reflection_structure_residual(
                    generator,
                    j1=j1,
                    j2=j2,
                    require_cone=require_cone,
                ),
            )
            scale_norm = max(1.0, float(np.linalg.norm(generator)))
            max_common_reality_residual = max(
                max_common_reality_residual,
                float(
                    np.linalg.norm(
                        common_j1.T @ generator @ common_j1
                        - generator.conj()
                    )
                )
                / scale_norm,
            )

        result = spin_trace_weight(generators)
        counts[result.classification] += 1
        if math.isfinite(result.square_identity_residual):
            max_square_identity_residual = max(
                max_square_identity_residual,
                result.square_identity_residual,
            )
        else:
            nonfinite_determinant_diagnostics += 1
        min_cancellation_ratio = min(
            min_cancellation_ratio,
            result.cancellation_ratio,
        )
        if result.determinant_check_reliable:
            max_reliable_square_identity_residual = max(
                max_reliable_square_identity_residual,
                result.square_identity_residual,
            )
        else:
            unreliable_determinant_checks += 1

        if result.classification in {"negative", "complex", "uncertain"}:
            margin = abs(result.value.real)
            if result.classification == "complex":
                margin = abs(result.value.imag)
            if margin > example_margins.get(result.classification, -1.0):
                example_margins[result.classification] = margin
                examples[result.classification] = {
                    "generators": [
                        _encode_matrix(generator) for generator in generators
                    ],
                    "trace_weight": {
                        "real": result.value.real,
                        "imag": result.value.imag,
                    },
                    "trace_phase": {
                        "real": result.phase.real,
                        "imag": result.phase.imag,
                    },
                    "log_abs_trace_weight": (
                        result.log_abs if math.isfinite(result.log_abs) else None
                    ),
                    "cancellation_ratio": result.cancellation_ratio,
                    "determinant_square": {
                        "real": (
                            result.determinant_square.real
                            if math.isfinite(result.determinant_square.real)
                            else None
                        ),
                        "imag": (
                            result.determinant_square.imag
                            if math.isfinite(result.determinant_square.imag)
                            else None
                        ),
                    },
                    "determinant_phase": {
                        "real": result.determinant_phase.real,
                        "imag": result.determinant_phase.imag,
                    },
                    "log_abs_determinant": (
                        result.log_abs_determinant
                        if math.isfinite(result.log_abs_determinant)
                        else None
                    ),
                    "square_identity_residual": (
                        result.square_identity_residual
                        if math.isfinite(result.square_identity_residual)
                        else None
                    ),
                    "determinant_condition_number": (
                        result.determinant_condition_number
                        if math.isfinite(result.determinant_condition_number)
                        else None
                    ),
                    "determinant_check_reliable": (
                        result.determinant_check_reliable
                    ),
                }

    return {
        "schema_version": 1,
        "completed": True,
        "params": {
            "case": case,
            "block_size": block_size,
            "depth": depth,
            "scale": scale,
            "angle": angle,
            "seed": seed,
        },
        "settings": {"samples": samples},
        "provenance": {
            "oracle_version": __version__,
            "family": "majorana_reflection_cones",
            "generator": "oracle.majorana.random_reflection_generator",
            "weight": "Tr(product_l exp(gamma^T A_l gamma / 4))",
            "determinant_identity": (
                "weight^2 = det(I + product_l exp(A_l))"
            ),
            "precision": "numpy-scipy-float64",
        },
        "counts": counts,
        "max_structure_residual": max_structure_residual,
        "max_common_reality_residual": max_common_reality_residual,
        "max_square_identity_residual": max_square_identity_residual,
        "max_reliable_square_identity_residual": (
            max_reliable_square_identity_residual
        ),
        "unreliable_determinant_checks": unreliable_determinant_checks,
        "nonfinite_determinant_diagnostics": (
            nonfinite_determinant_diagnostics
        ),
        "min_cancellation_ratio": min_cancellation_ratio,
        "examples": examples,
    }


def run_spec(path: str | Path) -> dict[str, int]:
    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    declared_run_dir = Path(spec.get("run_dir", spec_path.parent))
    run_dir = (
        declared_run_dir if declared_run_dir.is_absolute() else spec_path.parent
    )
    shared_settings = spec.get("settings", {})
    shared_provenance = spec.get("provenance", {})
    progress_every = int(shared_settings.get("progress_every", 20))
    completed = 0
    skipped = 0

    for index, cell in enumerate(spec["cells"], start=1):
        cell_id = cell["cell_id"]
        manifest_path = run_dir / "cells" / cell_id / "manifest.json"
        if manifest_path.is_file():
            skipped += 1
            continue

        params = cell["params"]
        settings = {**shared_settings, **cell.get("settings", {})}
        started = time.perf_counter()
        manifest = scan_cell(
            case=str(params["case"]),
            block_size=int(params["block_size"]),
            depth=int(params["depth"]),
            scale=float(params["scale"]),
            angle=float(params["angle"]),
            seed=int(params["seed"]),
            samples=int(settings["samples"]),
        )
        oracle_provenance = manifest["provenance"]
        manifest.update(
            {
                "cell_id": cell_id,
                "settings": settings,
                "provenance": shared_provenance,
                "oracle_provenance": oracle_provenance,
                "runtime_seconds": time.perf_counter() - started,
            }
        )
        _write_json_atomic(manifest_path, manifest)
        completed += 1
        if completed % progress_every == 0 or index == len(spec["cells"]):
            print(
                f"Majorana scan progress: {index}/{len(spec['cells'])} cells "
                f"({completed} completed, {skipped} reused)",
                flush=True,
            )

    return {"completed": completed, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_spec", help="path to parameter-scan run_spec.json")
    args = parser.parse_args()
    summary = run_spec(args.run_spec)
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
