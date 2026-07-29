import hashlib
import json
from pathlib import Path


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_synthetic_run(root: Path, widths=(6, 8, 10), streams=2, blocks=4) -> Path:
    run = root / "run"
    raw = run / "raw"
    config = {
        "widths": list(widths),
        "theta": 0.7853981633974483,
        "beta": 0.881373587019543,
        "base_seed": 122447,
        "production_gates": False,
        "refinement_level": 0,
        "sampling": {
            "streams_per_width": streams,
            "burn_in_layers_per_width": 2,
            "measurement_layers_per_width": blocks * 2,
            "block_layers_per_width": 2,
            "stabilize_every_layers": 1,
            "invariant_tolerance": 1.0e-9,
        },
    }
    hashes = {}
    for width in widths:
        for stream in range(streams):
            gamma0 = (
                0.73 * width
                - 3.141592653589793 * 0.447 / (6.0 * width)
                + 1.2 / width**3
            )
            artifact = {
                "schema_version": 3,
                "config": config,
                "estimate": {
                    "width": width,
                    "stream": stream,
                    "seed": 1000 + width * 10 + stream,
                    "burn_in_layers": 2 * width,
                    "measurement_layers": blocks * 2 * width,
                    "block_layers": 2 * width,
                    "sector_wilson_loop": 1,
                    "sector_fermion_parity": 1,
                    "blocks": [
                        {
                            "block_index": block,
                            "gamma": gamma0 + (stream - 0.5) * 2e-4 + (block - 1.5) * 1e-5,
                            "electric_count": 75 + block,
                            "magnetic_count": 75 + block,
                            "faces_per_species": 200,
                            "min_probability": 0.1,
                            "max_invariant_error": 1.0e-12,
                        }
                        for block in range(blocks)
                    ],
                },
                "elapsed_s": 0.1,
            }
            key = f"stream-L{width:02}-{stream:03}"
            path = raw / "streams" / f"{key}.json"
            _write_json(path, artifact)
            hashes[key] = _sha256(path)
    oracle = {
        "schema_version": 3,
        "config": config,
        "born_enumeration": {
            "max_probability_error": 1e-14,
            "max_parity_error": 1e-14,
            "max_covariance_error": 1e-14,
        },
        "gauge_equivalence": {
            "max_probability_error": 1e-14,
            "max_observable_error": 1e-14,
        },
        "clean_positive": {"max_covariance_error": 1e-14},
        "elapsed_s": 0.1,
    }
    oracle_path = raw / "oracles.json"
    _write_json(oracle_path, oracle)
    hashes["oracles"] = _sha256(oracle_path)
    manifest = {
        "schema_version": 3,
        "config": config,
        "artifact_sha256": hashes,
        "oracle_elapsed_s": 0.1,
        "simulation_elapsed_s": 0.2,
        "analysis_elapsed_s": None,
        "total_elapsed_s": None,
    }
    _write_json(run / "manifest.json", manifest)
    return run
