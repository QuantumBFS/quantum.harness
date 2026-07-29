"""Evidence collection and a dependency-free QR stability plot for stage 1."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from .blocking import StreamingBlockAccumulator
from .casimir_fit import fit_casimir
from .checkpoint import load_checkpoint, save_checkpoint
from .lyapunov import LyapunovQR
from .rng import StreamKey, make_rng


def _matrix_sequence(count: int, dimension: int) -> list[np.ndarray]:
    rng = make_rng(
        StreamKey(20260727, "stage1-metrics", dimension, 0, "transfers")
    )
    return [
        np.eye(dimension) + 0.01 * rng.normal(size=(dimension, dimension))
        for _ in range(count)
    ]


def _run_product(
    matrices: list[np.ndarray], interval: int, repeats: int = 1
) -> tuple[np.ndarray, float]:
    product = LyapunovQR(matrices[0].shape[0], interval)
    for _ in range(repeats):
        for matrix in matrices:
            product.push(matrix)
    return product.finalize(), product.max_orthogonality_error


def _checkpoint_metric() -> tuple[float, float, float]:
    key = StreamKey(8675309, "stage1-metrics", 3, 0, "checkpoint")

    def advance(
        rng: np.random.Generator,
        blocks: StreamingBlockAccumulator,
        lyapunov: LyapunovQR,
        steps: int,
    ) -> None:
        for _ in range(steps):
            noise = rng.normal(size=(3, 3))
            lyapunov.push(np.eye(3) + 0.01 * noise)
            blocks.add([float(np.mean(noise)), float(np.std(noise))])

    direct_rng = make_rng(key)
    direct_blocks = StreamingBlockAccumulator(7, 2)
    direct_lyapunov = LyapunovQR(3, 5)
    advance(direct_rng, direct_blocks, direct_lyapunov, 100)

    split_rng = make_rng(key)
    split_blocks = StreamingBlockAccumulator(7, 2)
    split_lyapunov = LyapunovQR(3, 5)
    advance(split_rng, split_blocks, split_lyapunov, 37)
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "state.npz"
        save_checkpoint(
            checkpoint,
            rng=split_rng,
            blocks=split_blocks,
            lyapunov=split_lyapunov,
            gaussian_state=np.array(
                [[0.0, 1.0j], [-1.0j, 0.0]], dtype=np.complex128
            ),
            extra={"stage": 1, "step": 37},
        )
        bundle = load_checkpoint(checkpoint)
        advance(bundle.rng, bundle.blocks, bundle.lyapunov, 63)
        exponent_error = float(
            np.max(
                np.abs(
                    direct_lyapunov.finalize()
                    - bundle.lyapunov.finalize()
                )
            )
        )
        block_error = float(
            np.max(
                np.abs(
                    direct_blocks.completed_blocks
                    - bundle.blocks.completed_blocks
                )
            )
        )
        rng_error = float(
            np.max(np.abs(direct_rng.random(32) - bundle.rng.random(32)))
        )
    return exponent_error, block_error, rng_error


def collect_stage1_metrics() -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    matrices = _matrix_sequence(500, 4)
    interval_exponents: dict[int, np.ndarray] = {}
    interval_orthogonality: dict[int, float] = {}
    for interval in (1, 2, 5):
        exponents, orthogonality = _run_product(matrices, interval)
        interval_exponents[interval] = exponents
        interval_orthogonality[interval] = orthogonality
    interval_error = max(
        float(
            np.max(
                np.abs(interval_exponents[1] - interval_exponents[interval])
            )
        )
        for interval in (2, 5)
    )

    long_matrices = _matrix_sequence(17, 2)
    long_product = LyapunovQR(2, 5)
    for index in range(100_000):
        long_product.push(long_matrices[index % len(long_matrices)])
    long_exponents = long_product.finalize()

    checkpoint_exponent_error, checkpoint_block_error, checkpoint_rng_error = (
        _checkpoint_metric()
    )

    sizes = np.array([6, 8, 10, 12, 16, 20, 24, 32], dtype=np.float64)
    errors = np.full(sizes.shape, 1.0e-6)
    phi_target = 0.464
    phi_values = (
        1.234
        + np.pi * phi_target / (6.0 * sizes**2)
        + 0.17 / sizes**4
    )
    phi_fit = fit_casimir(
        sizes,
        phi_values,
        errors=errors,
        model="M1",
        quantity="phi",
    )
    shannon_target = 0.447
    shannon_values = (
        0.81
        - np.pi * shannon_target / (6.0 * sizes**2)
        - 0.04 / sizes**4
    )
    shannon_fit = fit_casimir(
        sizes,
        shannon_values,
        errors=errors,
        model="M1",
        quantity="shannon",
    )

    metrics: dict[str, Any] = {
        "qr_interval_max_exponent_abs_difference": interval_error,
        "qr_interval_max_orthogonality_error": max(
            interval_orthogonality.values()
        ),
        "long_smoke_layers": 100_000,
        "long_smoke_all_finite": bool(np.all(np.isfinite(long_exponents))),
        "long_smoke_max_orthogonality_error": (
            long_product.max_orthogonality_error
        ),
        "checkpoint_exponent_abs_error": checkpoint_exponent_error,
        "checkpoint_block_abs_error": checkpoint_block_error,
        "checkpoint_rng_abs_error": checkpoint_rng_error,
        "m1_phi_central_charge_abs_error": abs(
            phi_fit.central_charge - phi_target
        ),
        "m1_shannon_central_charge_abs_error": abs(
            shannon_fit.central_charge - shannon_target
        ),
        "m1_phi_design_condition_number": phi_fit.design_condition_number,
        "m1_shannon_design_condition_number": (
            shannon_fit.design_condition_number
        ),
        "qr_interval_exponents": {
            str(interval): values.tolist()
            for interval, values in interval_exponents.items()
        },
    }
    return metrics, interval_exponents


def write_qr_stability_svg(
    path: str | Path, interval_exponents: dict[int, np.ndarray]
) -> None:
    """Write a compact SVG of all exponents against QR interval."""

    destination = Path(path)
    width, height = 800, 480
    left, right, top, bottom = 90, 35, 55, 75
    plot_width = width - left - right
    plot_height = height - top - bottom
    intervals = sorted(interval_exponents)
    values = np.concatenate([interval_exponents[item] for item in intervals])
    value_min = float(np.min(values))
    value_max = float(np.max(values))
    padding = max(1.0e-6, 0.08 * (value_max - value_min))
    y_min = value_min - padding
    y_max = value_max + padding

    def x_position(interval: int) -> float:
        return left + (interval - intervals[0]) / (
            intervals[-1] - intervals[0]
        ) * plot_width

    def y_position(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed"]
    elements = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        (
            f'<text x="{width / 2}" y="30" text-anchor="middle" '
            'font-family="sans-serif" font-size="20">'
            "Stage 1: QR-interval stability</text>"
        ),
        (
            f'<line x1="{left}" y1="{top + plot_height}" '
            f'x2="{left + plot_width}" y2="{top + plot_height}" '
            'stroke="#111827"/>'
        ),
        (
            f'<line x1="{left}" y1="{top}" x2="{left}" '
            f'y2="{top + plot_height}" stroke="#111827"/>'
        ),
    ]
    for interval in intervals:
        x_value = x_position(interval)
        elements.append(
            f'<line x1="{x_value:.3f}" y1="{top + plot_height}" '
            f'x2="{x_value:.3f}" y2="{top + plot_height + 6}" '
            'stroke="#111827"/>'
        )
        elements.append(
            f'<text x="{x_value:.3f}" y="{top + plot_height + 25}" '
            'text-anchor="middle" font-family="sans-serif" font-size="14">'
            f"{interval}</text>"
        )
    for index in range(5):
        value = y_min + index * (y_max - y_min) / 4
        y_value = y_position(value)
        elements.append(
            f'<line x1="{left - 6}" y1="{y_value:.3f}" x2="{left}" '
            f'y2="{y_value:.3f}" stroke="#111827"/>'
        )
        elements.append(
            f'<text x="{left - 10}" y="{y_value + 5:.3f}" '
            'text-anchor="end" font-family="monospace" font-size="12">'
            f"{value:.5e}</text>"
        )
    dimension = len(next(iter(interval_exponents.values())))
    for exponent_index in range(dimension):
        points = [
            (
                x_position(interval),
                y_position(float(interval_exponents[interval][exponent_index])),
            )
            for interval in intervals
        ]
        point_text = " ".join(f"{x:.3f},{y:.3f}" for x, y in points)
        color = colors[exponent_index % len(colors)]
        elements.append(
            f'<polyline points="{point_text}" fill="none" stroke="{color}" '
            'stroke-width="2"/>'
        )
        for x_value, y_value in points:
            elements.append(
                f'<circle cx="{x_value:.3f}" cy="{y_value:.3f}" r="4" '
                f'fill="{color}"/>'
            )
    elements.extend(
        [
            (
                f'<text x="{left + plot_width / 2}" y="{height - 22}" '
                'text-anchor="middle" font-family="sans-serif" font-size="15">'
                "QR interval</text>"
            ),
            (
                f'<text x="22" y="{top + plot_height / 2}" '
                'text-anchor="middle" font-family="sans-serif" font-size="15" '
                f'transform="rotate(-90 22 {top + plot_height / 2})">'
                "finite-product exponent</text>"
            ),
        ]
    )
    destination.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        + "".join(elements)
        + "</svg>\n",
        encoding="utf-8",
    )
