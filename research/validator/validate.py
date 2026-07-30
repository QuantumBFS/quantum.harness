#!/usr/bin/env python3
"""Independent validator for finite-abelian symmetry-reduction candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "research/database/generate_corpus.py"
SANDBOX = Path(__file__).with_name("sandbox_runner.py")
MANIFEST = Path(__file__).with_name("manifest.json")
ENVIRONMENT = {"kind": "fallback", "image_or_lock": "python-venv:numpy-2.5.1"}
VALUE_TOL = 1e-7
RESIDUAL_TOL = 1e-10
TIME_LIMIT = 8.0

sys.path.insert(0, str(GENERATOR.parent))
from generate_corpus import generate_instance  # noqa: E402


def _report(status, score=None, per_instance=None, errors=None):
    return {
        "status": status,
        "score": score,
        "per_instance": per_instance or [],
        "errors": errors or [],
        "environment": ENVIRONMENT,
    }


def _error(where, what, hint):
    return {"where": where, "what": what, "hint": hint}


def _decode_matrix(value, name):
    array = np.asarray(value, dtype=float)
    if array.ndim != 3 or array.shape[2] != 2:
        raise ValueError(f"{name} must encode a matrix as [real, imag] pairs")
    return array[..., 0] + 1j * array[..., 1]


def _elements(moduli):
    import itertools

    return itertools.product(*(range(int(n)) for n in moduli))


def _projector(generators, moduli, character):
    n = generators.shape[1]
    result = np.zeros((n, n), dtype=np.complex128)
    for element in _elements(moduli):
        rho = np.eye(n, dtype=np.complex128)
        for generator, power in zip(generators, element):
            rho = rho @ np.linalg.matrix_power(generator, power)
        phase = sum(k * g / int(order) for k, g, order in zip(character, element, moduli))
        result += np.exp(-2j * np.pi * phase) * rho
    return result / int(np.prod(moduli))


def _runtime_probe(instance_set):
    digest = hashlib.sha256(f"issue-229:{instance_set}:guard-v1".encode()).digest()
    return {
        "id": f"runtime-probe-{instance_set}",
        "family": "product-cyclic",
        "seed": int.from_bytes(digest[:4], "little"),
        "moduli": [2, 3],
        "populated_characters": 6,
        "multiplicity": 3,
    }


def _load_specs(instance_set):
    path = ROOT / "research/benchmark" / instance_set / "specs.json"
    return json.loads(path.read_text())["instances"]


def _check_instance(spec, data, candidate):
    ident = spec["id"]
    matrix, generators, moduli = data["matrix"], data["generators"], data["moduli"]
    if candidate.get("method") != "character_projectors":
        raise ValueError("method must be character_projectors; dense passthrough is rejected")
    sectors = candidate.get("sectors")
    if not isinstance(sectors, list) or not sectors:
        raise ValueError("sectors must be a non-empty list")

    expected_characters = set()
    expected_ranks = {}
    for character in _elements(moduli):
        rank = int(round(np.trace(_projector(generators, moduli, character)).real))
        if rank:
            expected_characters.add(tuple(character))
            expected_ranks[tuple(character)] = rank
    observed = {tuple(sector.get("character", [])) for sector in sectors}
    if observed != expected_characters or len(observed) != len(sectors):
        raise ValueError(f"populated characters differ: observed={sorted(observed)}, expected={sorted(expected_characters)}")

    bases, blocks, reduced_spectrum = [], [], []
    max_projector = max_block = 0.0
    for sector in sectors:
        character = tuple(sector["character"])
        basis = _decode_matrix(sector["basis"], "basis")
        block = _decode_matrix(sector["block"], "block")
        rank = expected_ranks[character]
        if basis.shape != (matrix.shape[0], rank) or block.shape != (rank, rank):
            raise ValueError(f"wrong sector shape for character {character}")
        projector = _projector(generators, moduli, character)
        max_projector = max(max_projector, float(np.linalg.norm(projector @ basis - basis)))
        expected_block = basis.conj().T @ matrix @ basis
        max_block = max(max_block, float(np.linalg.norm(block - expected_block)))
        reported = np.asarray(sector.get("eigenvalues", []), dtype=float)
        actual = np.linalg.eigvalsh(block)
        if reported.shape != actual.shape or np.any(np.abs(reported - actual) > VALUE_TOL * (1 + np.abs(actual))):
            raise ValueError(f"reported sector eigenvalues are wrong for character {character}")
        bases.append(basis)
        blocks.append(block)
        reduced_spectrum.extend(actual.tolist())

    basis = np.concatenate(bases, axis=1)
    orthonormal = float(np.linalg.norm(basis.conj().T @ basis - np.eye(matrix.shape[0])))
    reconstructed = np.zeros_like(matrix)
    for sector_basis, block in zip(bases, blocks):
        reconstructed += sector_basis @ block @ sector_basis.conj().T
    reconstruction = float(np.linalg.norm(matrix - reconstructed))
    commutator = max(float(np.linalg.norm(matrix @ g - g @ matrix)) for g in generators)
    dense_spectrum = np.linalg.eigvalsh(matrix)
    reduced_spectrum = np.sort(np.asarray(reduced_spectrum))
    spectrum_error = float(np.max(np.abs(dense_spectrum - reduced_spectrum)))
    minimum_error = float(abs(dense_spectrum[0] - reduced_spectrum[0]))
    value_limit = VALUE_TOL * (1 + np.max(np.abs(dense_spectrum)))
    residuals = {
        "projector": max_projector,
        "orthonormal": orthonormal,
        "block": max_block,
        "reconstruction": reconstruction,
        "commutator": commutator,
    }
    bad = {name: value for name, value in residuals.items() if value > RESIDUAL_TOL}
    if bad:
        raise ValueError(f"residual tolerance exceeded: {bad}")
    if spectrum_error > value_limit or minimum_error > VALUE_TOL * (1 + abs(dense_spectrum[0])):
        raise ValueError(f"spectrum mismatch: full={spectrum_error:.3e}, minimum={minimum_error:.3e}")

    cubic_reduction = matrix.shape[0] ** 3 / sum(block.shape[0] ** 3 for block in blocks)
    threshold = 3.0 if spec["family"] == "z2" else 10.0
    if spec["family"] == "product-cyclic" and len(sectors) < 4:
        raise ValueError("product-cyclic case has fewer than four populated characters")
    if cubic_reduction + 1e-12 < threshold:
        raise ValueError(f"cubic proxy reduction {cubic_reduction:.6g} is below {threshold:g}x")
    return cubic_reduction, residuals, spectrum_error


def _run_candidate(candidate_dir, instance_set, output):
    specs = _load_specs(instance_set)
    all_specs = specs + [_runtime_probe(instance_set)]
    with tempfile.TemporaryDirectory(prefix="abelian-validator-") as temp:
        temp_path = Path(temp)
        input_dir = temp_path / "instances"
        input_dir.mkdir()
        generated = {}
        for spec in all_specs:
            generated[spec["id"]] = generate_instance(spec)
            np.savez_compressed(input_dir / f"{spec['id']}.npz", **generated[spec["id"]])
        artifact = temp_path / "artifact.json"
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
        started = time.monotonic()
        try:
            process = subprocess.run(
                [sys.executable, str(SANDBOX), str(candidate_dir.resolve()), str(input_dir), str(artifact)],
                cwd=temp_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=TIME_LIMIT,
            )
        except subprocess.TimeoutExpired:
            return _report("rejected", errors=[_error("execution", f"candidate exceeded {TIME_LIMIT:.1f}s timeout", "remove non-terminating or superfluous work")])
        elapsed = time.monotonic() - started
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()[-1000:]
            return _report("rejected", errors=[_error("execution", f"candidate failed in sandbox: {detail}", "check blocked I/O, network, subprocess use, and the CLI contract")])
        if not artifact.exists():
            return _report("rejected", errors=[_error("artifact", "candidate produced no artifact.json", "write the requested JSON output path")])
        try:
            payload = json.loads(artifact.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            return _report("rejected", errors=[_error("artifact", f"invalid JSON artifact: {exc}", "emit schema_version 1 JSON")])
        if payload.get("schema_version") != 1 or not isinstance(payload.get("instances"), list):
            return _report("rejected", errors=[_error("artifact", "expected schema_version=1 and instances list", "follow the candidate artifact schema")])
        by_id = {item.get("id"): item for item in payload["instances"] if isinstance(item, dict)}
        expected_ids = {spec["id"] for spec in all_specs}
        if set(by_id) != expected_ids or len(by_id) != len(payload["instances"]):
            return _report("rejected", errors=[_error("artifact", f"instance ids differ from supplied inputs; got {sorted(by_id)}, expected {sorted(expected_ids)}", "process every supplied NPZ generically; do not use a corpus lookup")])

        per_instance, errors, ratios = [], [], []
        for spec in all_specs:
            ident = spec["id"]
            try:
                ratio, residuals, spectrum_error = _check_instance(spec, generated[ident], by_id[ident])
                ratios.append(ratio)
                per_instance.append({"instance": ident, "result": "pass", "seconds": elapsed / len(all_specs), "detail": f"cubic_reduction={ratio:.6g}; max_residual={max(residuals.values()):.3e}; spectrum_error={spectrum_error:.3e}"})
            except (ValueError, KeyError, TypeError) as exc:
                per_instance.append({"instance": ident, "result": "fail", "seconds": elapsed / len(all_specs), "detail": str(exc)})
                errors.append(_error(ident, str(exc), "check projector convention, orthonormal sector bases, blocks, and full reconstruction"))
                break
        status = "rejected" if errors else "scored"
        score = min(ratios) if ratios and not errors else None
        return _report(status, score, per_instance, errors)


def _record_holdout(report):
    manifest = json.loads(MANIFEST.read_text())
    queries = manifest.setdefault("holdout_queries", [])
    queries.append(
        {
            "date": time.strftime("%Y-%m-%d"),
            "result": report["status"],
            "aggregate_score": report["score"],
        }
    )
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--precheck", action="store_true")
    parser.add_argument("--instances", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--out", type=Path, default=Path("report.json"))
    args = parser.parse_args()
    instance_set = "private" if args.instances == "holdout" else args.instances
    if args.instances == "holdout":
        manifest = json.loads(MANIFEST.read_text())
        if len(manifest.get("holdout_queries", [])) >= manifest["holdout_query_budget"]:
            report = _report(
                "rejected",
                errors=[
                    _error(
                        "holdout",
                        "holdout query budget exhausted",
                        "continue on development instances; changing the budget requires explicit approval",
                    )
                ],
            )
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            return 1
    if not (args.candidate_dir / "run.py").is_file():
        report = _report("rejected", errors=[_error("precheck", "candidate_dir/run.py is missing", "provide the required candidate entrypoint")])
    elif args.precheck:
        report = _report("scored", score=None, per_instance=[{"instance": "precheck", "result": "pass", "seconds": 0.0, "detail": "run.py entrypoint present"}])
    else:
        report = _run_candidate(args.candidate_dir, instance_set, args.out)
    if args.instances == "holdout":
        _record_holdout(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "scored" else 1


if __name__ == "__main__":
    raise SystemExit(main())
