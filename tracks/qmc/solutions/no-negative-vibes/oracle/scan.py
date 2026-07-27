"""Deterministic scan cells for candidate matrix families."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

import numpy as np

from . import __version__
from . import az_families, families
from .weights import classify_product, product_exponentials


_CLASSIFICATIONS = ("positive", "negative", "zero", "complex", "uncertain")


def _available_cases() -> dict[str, families.FamilyCase]:
    classical = families.available_cases()
    az = az_families.available_cases()
    overlap = classical.keys() & az.keys()
    if overlap:
        raise RuntimeError(f"duplicate candidate case names: {sorted(overlap)}")
    return {**classical, **az}


def _candidate_module(case: str):
    if case in az_families.available_cases():
        return az_families
    return families


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_spec(path: str | Path) -> dict[str, int]:
    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    declared_run_dir = Path(spec.get("run_dir", spec_path.parent))
    run_dir = declared_run_dir if declared_run_dir.is_absolute() else spec_path.parent
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
            depth=int(params["depth"]),
            scale=float(params["scale"]),
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
                f"scan progress: {index}/{len(spec['cells'])} cells "
                f"({completed} completed, {skipped} reused)",
                flush=True,
            )

    return {"completed": completed, "skipped": skipped}


def _encode_matrix(matrix: np.ndarray) -> object:
    matrix = np.asarray(matrix)
    if np.iscomplexobj(matrix):
        return {
            "real": matrix.real.tolist(),
            "imag": matrix.imag.tolist(),
        }
    return matrix.tolist()


def _encode_example(
    generators: list[np.ndarray],
    product: np.ndarray,
    *,
    phase: complex,
    log_abs: float,
    sigma_min: float,
    condition_number: float,
) -> dict[str, object]:
    return {
        "generators": [_encode_matrix(generator) for generator in generators],
        "product": _encode_matrix(product),
        "phase": {"real": phase.real, "imag": phase.imag},
        "log_abs_weight": log_abs if math.isfinite(log_abs) else None,
        "sigma_min_I_plus_D": sigma_min,
        "condition_number_I_plus_D": (
            condition_number if math.isfinite(condition_number) else None
        ),
    }


def scan_cell(
    *,
    case: str,
    depth: int,
    scale: float,
    seed: int,
    samples: int,
) -> dict[str, object]:
    cases = _available_cases()
    if case not in cases:
        raise ValueError(f"unknown case: {case}")
    if depth < 1 or samples < 1:
        raise ValueError("depth and samples must be positive")

    candidate_module = _candidate_module(case)
    rng = np.random.default_rng(seed)
    counts = {classification: 0 for classification in _CLASSIFICATIONS}
    max_residual = 0.0
    min_sigma_min = math.inf
    examples: dict[str, dict[str, object]] = {}
    example_margins: dict[str, float] = {}

    for _ in range(samples):
        generators = [
            candidate_module.random_generator(case, rng, scale=scale)
            for _ in range(depth)
        ]
        max_residual = max(
            max_residual,
            *(
                candidate_module.structure_residual(case, generator)
                for generator in generators
            ),
        )
        product = product_exponentials(generators)
        result = classify_product(product)
        counts[result.classification] += 1
        min_sigma_min = min(min_sigma_min, result.sigma_min)

        if result.classification in {"negative", "complex", "uncertain"}:
            margin = (
                0.0
                if not math.isfinite(result.condition_number)
                else 1.0 / result.condition_number
            )
            if margin > example_margins.get(result.classification, -1.0):
                example_margins[result.classification] = margin
                examples[result.classification] = _encode_example(
                    generators,
                    product,
                    phase=result.phase,
                    log_abs=result.log_abs,
                    sigma_min=result.sigma_min,
                    condition_number=result.condition_number,
                )

    spec = cases[case]
    return {
        "schema_version": 1,
        "completed": True,
        "params": {
            "case": case,
            "depth": depth,
            "scale": scale,
            "seed": seed,
        },
        "settings": {"samples": samples},
        "provenance": {
            "oracle_version": __version__,
            "family": spec.family,
            "prior_status": spec.prior_status,
            "generator": "oracle.families.random_generator",
            "weight": "det(I + product_l exp(A_l))",
            "precision": "numpy/scipy float64",
        },
        "counts": counts,
        "max_structure_residual": max_residual,
        "min_sigma_min_I_plus_D": min_sigma_min,
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_spec", help="path to parameter-scan run_spec.json")
    args = parser.parse_args()
    summary = run_spec(args.run_spec)
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
