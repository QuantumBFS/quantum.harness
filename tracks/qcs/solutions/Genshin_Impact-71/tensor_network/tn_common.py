#!/usr/bin/env python3
"""Shared, dependency-minimal utilities for the issue-71 tensor-network arm.

Security boundary:
* Reads only strict two-column official CSV files and our own NPZ models.
* Does not execute input text, import competitor code, invoke subprocesses, or
  access the network.
* Truth-function evaluation deliberately lives in tn_truth.py and is not
  imported by the training program.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


INSTANCE_SPECS = {
    "practice-add-n4": {"n": 4, "m": 5},
    "practice-mul-n4": {"n": 4, "m": 8},
    "mystery-A": {"n": 8, "m": 9},
    "mystery-B": {"n": 7, "m": 7},
    "mystery-C": {"n": 6, "m": 12},
    "mystery-D": {"n": 5, "m": 11},
}

ORDER_NAMES = (
    "blocked_lsb",
    "blocked_msb",
    "interleaved_lsb",
    "interleaved_msb",
)


def stable_seed(root_seed: int, *parts: object) -> int:
    """Derive deterministic independent streams from root seed 42."""
    payload = ":".join([str(root_seed), *(str(p) for p in parts)]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little") % (2**32)


def variable_order(n: int, name: str) -> list[int]:
    if name == "blocked_lsb":
        return list(range(2 * n))
    if name == "blocked_msb":
        return list(range(n - 1, -1, -1)) + list(range(2 * n - 1, n - 1, -1))
    if name == "interleaved_lsb":
        return [j for i in range(n) for j in (i, n + i)]
    if name == "interleaved_msb":
        return [j for i in range(n - 1, -1, -1) for j in (i, n + i)]
    raise ValueError(f"unsupported variable order: {name!r}")


def parse_bitstring(text: str, width: int, field: str, line_no: int) -> list[int]:
    if len(text) != width or any(ch not in "01" for ch in text):
        raise ValueError(
            f"line {line_no}: {field} must be exactly {width} ASCII bits"
        )
    return [ord(ch) - ord("0") for ch in text]


def load_train_csv(path: Path, instance: str) -> tuple[np.ndarray, np.ndarray]:
    """Strictly parse an official train.csv, rejecting duplicate inputs."""
    if instance not in INSTANCE_SPECS:
        raise ValueError(f"unknown instance {instance!r}")
    n = int(INSTANCE_SPECS[instance]["n"])
    m = int(INSTANCE_SPECS[instance]["m"])
    xs: list[list[int]] = []
    ys: list[list[int]] = []
    seen: set[str] = set()
    with path.open("r", encoding="ascii", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != ["input", "output"]:
            raise ValueError(f"{path}: expected header input,output")
        for line_no, row in enumerate(reader, 2):
            if len(row) != 2:
                raise ValueError(f"line {line_no}: expected exactly two CSV fields")
            x_text, y_text = row
            if x_text in seen:
                raise ValueError(f"line {line_no}: duplicate input")
            seen.add(x_text)
            xs.append(parse_bitstring(x_text, 2 * n, "input", line_no))
            ys.append(parse_bitstring(y_text, m, "output", line_no))
    if not xs:
        raise ValueError(f"{path}: no training rows")
    return np.asarray(xs, dtype=np.int8), np.asarray(ys, dtype=np.int8)


def rank_profile(n_sites: int, max_bond: int) -> list[int]:
    if n_sites < 1 or max_bond < 1:
        raise ValueError("n_sites and max_bond must be positive")
    return [
        min(max_bond, 2**min(i, n_sites - i))
        for i in range(n_sites + 1)
    ]


def initialize_mps(
    n_sites: int, max_bond: int, rng: np.random.Generator
) -> list[np.ndarray]:
    ranks = rank_profile(n_sites, max_bond)
    cores = []
    for site in range(n_sites):
        r_left, r_right = ranks[site], ranks[site + 1]
        scale = 1.0 / np.sqrt(max(1, 2 * r_left))
        cores.append(
            rng.normal(0.0, scale, size=(r_left, 2, r_right)).astype(np.float64)
        )
    # Put the random model in a stable left-canonical gauge.
    for site in range(n_sites - 1):
        left_canonicalize(cores, site)
    return cores


def predict_scores(cores: list[np.ndarray], x_ordered: np.ndarray) -> np.ndarray:
    if x_ordered.ndim != 2 or x_ordered.shape[1] != len(cores):
        raise ValueError("input/model site mismatch")
    state = np.ones((x_ordered.shape[0], 1), dtype=np.float64)
    for site, core in enumerate(cores):
        selected = np.transpose(core[:, x_ordered[:, site], :], (1, 0, 2))
        state = np.einsum("ni,nij->nj", state, selected, optimize=True)
    return state[:, 0]


def predict_bits(cores: list[np.ndarray], x_ordered: np.ndarray) -> np.ndarray:
    return (predict_scores(cores, x_ordered) >= 0.0).astype(np.int8)


def left_canonicalize(cores: list[np.ndarray], site: int) -> None:
    core = cores[site]
    r_left, _, r_right = core.shape
    q_mat, r_mat = np.linalg.qr(core.reshape(r_left * 2, r_right), mode="reduced")
    if q_mat.shape[1] != r_right:
        raise RuntimeError("invalid MPS rank profile during left QR")
    cores[site] = q_mat.reshape(r_left, 2, r_right)
    cores[site + 1] = np.einsum(
        "ab,bic->aic", r_mat, cores[site + 1], optimize=True
    )


def right_canonicalize(cores: list[np.ndarray], site: int) -> None:
    core = cores[site]
    r_left, _, r_right = core.shape
    q_mat, r_mat = np.linalg.qr(
        core.reshape(r_left, 2 * r_right).T, mode="reduced"
    )
    if q_mat.shape[1] != r_left:
        raise RuntimeError("invalid MPS rank profile during right QR")
    cores[site] = q_mat.T.reshape(r_left, 2, r_right)
    cores[site - 1] = np.einsum(
        "aib,bc->aic", cores[site - 1], r_mat.T, optimize=True
    )


def site_environments(
    cores: list[np.ndarray], x_ordered: np.ndarray, site: int
) -> tuple[np.ndarray, np.ndarray]:
    n_rows = x_ordered.shape[0]
    left = np.ones((n_rows, 1), dtype=np.float64)
    for j in range(site):
        selected = np.transpose(cores[j][:, x_ordered[:, j], :], (1, 0, 2))
        left = np.einsum("ni,nij->nj", left, selected, optimize=True)
    right = np.ones((n_rows, 1), dtype=np.float64)
    for j in range(len(cores) - 1, site, -1):
        selected = np.transpose(cores[j][:, x_ordered[:, j], :], (1, 0, 2))
        right = np.einsum("nij,nj->ni", selected, right, optimize=True)
    return left, right


def ridge_cg(
    features: np.ndarray,
    targets: np.ndarray,
    ridge: float,
    initial: np.ndarray,
    max_iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Solve ridge least squares by deterministic diagonally-preconditioned CG."""
    if features.shape[0] == 0:
        return initial.copy(), {"iterations": 0, "relative_residual": 0.0}
    rhs = features.T @ targets
    diagonal = np.sum(features * features, axis=0) + ridge

    def matvec(vector: np.ndarray) -> np.ndarray:
        return features.T @ (features @ vector) + ridge * vector

    solution = initial.copy()
    residual = rhs - matvec(solution)
    rhs_norm = max(float(np.linalg.norm(rhs)), 1.0)
    relative = float(np.linalg.norm(residual)) / rhs_norm
    if relative <= tolerance:
        return solution, {"iterations": 0, "relative_residual": relative}
    preconditioned = residual / np.maximum(diagonal, 1e-15)
    direction = preconditioned.copy()
    rz_old = float(residual @ preconditioned)
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        image = matvec(direction)
        denominator = float(direction @ image)
        if denominator <= 0.0 or not np.isfinite(denominator):
            break
        alpha = rz_old / denominator
        solution += alpha * direction
        residual -= alpha * image
        relative = float(np.linalg.norm(residual)) / rhs_norm
        if relative <= tolerance:
            break
        preconditioned = residual / np.maximum(diagonal, 1e-15)
        rz_new = float(residual @ preconditioned)
        if rz_old == 0.0 or not np.isfinite(rz_new):
            break
        direction = preconditioned + (rz_new / rz_old) * direction
        rz_old = rz_new
    if not np.all(np.isfinite(solution)):
        raise FloatingPointError("non-finite ridge solution")
    return solution, {"iterations": iterations, "relative_residual": relative}


def update_one_site(
    cores: list[np.ndarray],
    x_ordered: np.ndarray,
    targets_pm1: np.ndarray,
    site: int,
    ridge: float,
    cg_iterations: int,
    cg_tolerance: float,
) -> dict[str, float | int]:
    left, right = site_environments(cores, x_ordered, site)
    core = cores[site].copy()
    total_iterations = 0
    worst_residual = 0.0
    for physical in (0, 1):
        selected_rows = np.flatnonzero(x_ordered[:, site] == physical)
        if selected_rows.size == 0:
            continue
        features = np.einsum(
            "ni,nj->nij",
            left[selected_rows],
            right[selected_rows],
            optimize=True,
        ).reshape(selected_rows.size, -1)
        solution, diagnostics = ridge_cg(
            features,
            targets_pm1[selected_rows],
            ridge,
            core[:, physical, :].reshape(-1),
            cg_iterations,
            cg_tolerance,
        )
        core[:, physical, :] = solution.reshape(core.shape[0], core.shape[2])
        total_iterations += int(diagnostics["iterations"])
        worst_residual = max(worst_residual, float(diagnostics["relative_residual"]))
    cores[site] = core
    return {
        "cg_iterations": total_iterations,
        "worst_relative_residual": worst_residual,
    }


def classification_metrics(
    models: list[list[np.ndarray]], x_ordered: np.ndarray, y_bits: np.ndarray
) -> dict[str, float | int]:
    scores = np.column_stack(
        [predict_scores(output_model, x_ordered) for output_model in models]
    )
    predictions = (scores >= 0.0).astype(np.int8)
    targets_pm1 = 2.0 * y_bits.astype(np.float64) - 1.0
    return {
        "rows": int(y_bits.shape[0]),
        "bit_accuracy": float(np.mean(predictions == y_bits)),
        "exact_accuracy": float(np.mean(np.all(predictions == y_bits, axis=1))),
        "rmse_pm1": float(np.sqrt(np.mean((scores - targets_pm1) ** 2))),
    }


@dataclass
class SavedMPS:
    metadata: dict
    models: list[list[np.ndarray]]


def save_models(path: Path, metadata: dict, models: list[list[np.ndarray]]) -> None:
    arrays: dict[str, np.ndarray] = {
        "metadata_utf8": np.frombuffer(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            dtype=np.uint8,
        )
    }
    for output_index, output_model in enumerate(models):
        for site, core in enumerate(output_model):
            arrays[f"o{output_index:03d}_c{site:03d}"] = core
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def load_models(path: Path) -> SavedMPS:
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(bytes(archive["metadata_utf8"].tolist()).decode("utf-8"))
        n_outputs = int(metadata["n_outputs"])
        n_sites = int(metadata["n_sites"])
        models = [
            [
                np.asarray(archive[f"o{output_index:03d}_c{site:03d}"]).copy()
                for site in range(n_sites)
            ]
            for output_index in range(n_outputs)
        ]
    return SavedMPS(metadata=metadata, models=models)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def comma_ints(text: str) -> list[int]:
    values = [int(piece) for piece in text.split(",") if piece]
    if not values or any(value < 1 for value in values):
        raise ValueError("expected comma-separated positive integers")
    return values


def comma_words(text: str, allowed: Iterable[str]) -> list[str]:
    allowed_set = set(allowed)
    values = [piece for piece in text.split(",") if piece]
    if not values or any(value not in allowed_set for value in values):
        raise ValueError(f"unsupported values in {text!r}")
    return values
