"""Small exact oracles for fermionic determinant sign experiments.

The central map is A -> sum_ij A_ij c_i^dagger c_j.  It is evaluated
explicitly in the occupation-number basis, so the Fock-space trace and the
single-particle determinant are independent numerical calculations.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import resource
import time

import numpy as np
from scipy.linalg import expm


Array = np.ndarray


def _as_square_matrix(matrix: Array) -> Array:
    result = np.asarray(matrix)
    if result.ndim != 2 or result.shape[0] != result.shape[1]:
        raise ValueError("a generator must be a square matrix")
    return result


def split_metric(n: int) -> Array:
    """Return eta = diag(I_n, -I_n)."""
    if n < 1:
        raise ValueError("n must be positive")
    return np.diag(np.concatenate((np.ones(n), -np.ones(n))))


def o11_generator(rapidity: float) -> Array:
    """Return the general Lie-algebra generator in the identity component."""
    return np.array([[0.0, rapidity], [rapidity, 0.0]])


def o11_analytic_determinant(rapidities: Iterable[float]) -> float:
    """Analytic det(I + product exp(A_i)) for commuting o(1,1) boosts."""
    total = float(np.sum(np.asarray(list(rapidities), dtype=float)))
    return float(2.0 + 2.0 * np.cosh(total))


def product_of_exponentials(generators: Sequence[Array]) -> Array:
    """Multiply exp(A_1) exp(A_2) ... in the supplied order."""
    if not generators:
        raise ValueError("at least one generator is required")

    matrices = [_as_square_matrix(generator) for generator in generators]
    dimension = matrices[0].shape[0]
    if any(matrix.shape != (dimension, dimension) for matrix in matrices):
        raise ValueError("all generators must have the same shape")

    dtype = np.result_type(*(matrix.dtype for matrix in matrices), np.float64)
    product = np.eye(dimension, dtype=dtype)
    for matrix in matrices:
        product = product @ expm(matrix)
    return product


def product_with_split_group_residual(
    generators: Sequence[Array],
    eta: Array,
) -> tuple[Array, float]:
    """Multiply factors and evaluate M.T eta M-eta in extended precision.

    SciPy supplies each matrix exponential in double precision. Accumulating
    the factors and the quadratic-form residual in long double prevents the
    absolute residual from being dominated by condition-amplified matrix
    multiplication roundoff.
    """
    if not generators:
        raise ValueError("at least one generator is required")

    matrices = [_as_square_matrix(generator) for generator in generators]
    dimension = matrices[0].shape[0]
    if any(matrix.shape != (dimension, dimension) for matrix in matrices):
        raise ValueError("all generators must have the same shape")
    metric = _as_square_matrix(eta)
    if metric.shape != (dimension, dimension):
        raise ValueError("eta and the generators must have the same shape")

    is_complex = any(np.iscomplexobj(matrix) for matrix in matrices)
    extended_dtype = np.clongdouble if is_complex else np.longdouble
    output_dtype = np.complex128 if is_complex else np.float64
    product = np.eye(dimension, dtype=extended_dtype)
    for matrix in matrices:
        factor = np.asarray(expm(matrix), dtype=extended_dtype)
        product = product @ factor

    extended_metric = np.asarray(metric, dtype=extended_dtype)
    residual_matrix = product.T @ extended_metric @ product - extended_metric
    residual = float(np.sqrt(np.sum(np.abs(residual_matrix) ** 2)))
    return np.asarray(product, dtype=output_dtype), residual


def determinant_weight(generators: Sequence[Array]):
    """Compute det(I + exp(A_1) exp(A_2) ...)."""
    product = product_of_exponentials(generators)
    return np.linalg.det(np.eye(product.shape[0], dtype=product.dtype) + product)


def bilinear_fock_operator(generator: Array) -> Array:
    """Lift A to sum_ij A_ij c_i^dagger c_j in the full Fock space.

    Basis states are integers whose bit j is the occupation of orbital j.
    Hence the one-particle states appear in the order |10...>, |01...>, ...
    and the one-particle block of the returned operator is exactly A.
    """
    matrix = _as_square_matrix(generator)
    orbitals = matrix.shape[0]
    dimension = 1 << orbitals
    dtype = np.result_type(matrix.dtype, np.float64)
    lifted = np.zeros((dimension, dimension), dtype=dtype)

    for state in range(dimension):
        for j in range(orbitals):
            if not (state & (1 << j)):
                continue

            lower_j = state & ((1 << j) - 1)
            phase_annihilate = -1 if lower_j.bit_count() % 2 else 1
            intermediate = state ^ (1 << j)

            for i in range(orbitals):
                coefficient = matrix[i, j]
                if coefficient == 0 or (intermediate & (1 << i)):
                    continue

                lower_i = intermediate & ((1 << i) - 1)
                phase_create = -1 if lower_i.bit_count() % 2 else 1
                destination = intermediate | (1 << i)
                lifted[destination, state] += (
                    coefficient * phase_annihilate * phase_create
                )

    return lifted


def fock_trace_weight(generators: Sequence[Array]):
    """Compute Tr_Fock product exp(sum_ij A_ij c_i^dagger c_j)."""
    if not generators:
        raise ValueError("at least one generator is required")

    matrices = [_as_square_matrix(generator) for generator in generators]
    orbitals = matrices[0].shape[0]
    if any(matrix.shape != (orbitals, orbitals) for matrix in matrices):
        raise ValueError("all generators must have the same shape")

    dimension = 1 << orbitals
    dtype = np.result_type(*(matrix.dtype for matrix in matrices), np.float64)
    product = np.eye(dimension, dtype=dtype)
    for matrix in matrices:
        product = product @ expm(bilinear_fock_operator(matrix))
    return np.trace(product)


def random_split_generator(
    n: int,
    rng: np.random.Generator,
    *,
    scale: float = 1.0,
) -> Array:
    """Sample A = [[C, B], [B.T, D]] from the full o(n,n) algebra."""
    if n < 1:
        raise ValueError("n must be positive")
    b = rng.normal(size=(n, n))
    c_raw = rng.normal(size=(n, n))
    d_raw = rng.normal(size=(n, n))
    c = c_raw - c_raw.T
    d = d_raw - d_raw.T
    return float(scale) * np.block([[c, b], [b.T, d]])


def _split_dimension_and_metric(matrix: Array, eta: Array | None) -> tuple[int, Array]:
    square = _as_square_matrix(matrix)
    dimension = square.shape[0]
    if dimension % 2:
        raise ValueError("a split-orthogonal matrix must have even dimension")

    n = dimension // 2
    metric = split_metric(n) if eta is None else _as_square_matrix(eta)
    if metric.shape != square.shape:
        raise ValueError("eta and the matrix must have the same shape")
    return n, metric


def split_lie_residual(generator: Array, eta: Array | None = None) -> float:
    """Frobenius residual of A.T eta + eta A = 0."""
    matrix = _as_square_matrix(generator)
    _, metric = _split_dimension_and_metric(matrix, eta)
    residual = matrix.T @ metric + metric @ matrix
    return float(np.linalg.norm(residual, ord="fro"))


def split_group_residual(matrix: Array, eta: Array | None = None) -> float:
    """Frobenius residual of M.T eta M = eta."""
    square = _as_square_matrix(matrix)
    _, metric = _split_dimension_and_metric(square, eta)
    residual = square.T @ metric @ square - metric
    return float(np.linalg.norm(residual, ord="fro"))


def determinant_i_plus(matrix: Array):
    """Compute det(I + M) for an already formed evolution matrix M."""
    square = _as_square_matrix(matrix)
    identity = np.eye(square.shape[0], dtype=np.result_type(square.dtype, float))
    return np.linalg.det(identity + square)


def classify_split_component(
    matrix: Array,
    eta: Array | None = None,
    *,
    atol: float = 1e-9,
) -> str:
    """Classify M in O(n,n) by signs of det(M_11) and det(M_22)."""
    square = _as_square_matrix(matrix)
    n, metric = _split_dimension_and_metric(square, eta)
    if split_group_residual(square, metric) > atol:
        raise ValueError("matrix is not in O(n,n) within the requested tolerance")

    sign_11, _ = np.linalg.slogdet(square[:n, :n])
    sign_22, _ = np.linalg.slogdet(square[n:, n:])
    if sign_11 == 0 or sign_22 == 0:
        raise ValueError("a diagonal block is numerically singular")
    return ("+" if sign_11 > 0 else "-") + ("+" if sign_22 > 0 else "-")


def split_component_representative(n: int, component: str) -> Array:
    """Return a diagonal representative of one of the four O(n,n) components."""
    if n < 1:
        raise ValueError("n must be positive")
    if component not in {"++", "--", "-+", "+-"}:
        raise ValueError("component must be one of ++, --, -+, +-")

    diagonal = np.ones(2 * n)
    if component[0] == "-":
        diagonal[0] = -1.0
    if component[1] == "-":
        diagonal[n] = -1.0
    return np.diag(diagonal)


@dataclass(frozen=True)
class HubbardVertex:
    """One continuous-time auxiliary-field insertion."""

    tau: float
    site: int
    field: int


_HUBBARD_ORBITAL_ORDER = (
    (0, "up"),
    (2, "up"),
    (1, "down"),
    (3, "down"),
    (1, "up"),
    (3, "up"),
    (0, "down"),
    (2, "down"),
)


def four_site_orbital_order() -> tuple[tuple[int, str], ...]:
    """Return the (A up, B down | B up, A down) split ordering."""
    return _HUBBARD_ORBITAL_ORDER


def hubbard_orbital_index(site: int, spin: str) -> int:
    """Index a site-spin orbital in the split ordering."""
    try:
        return _HUBBARD_ORBITAL_ORDER.index((int(site), spin))
    except ValueError as exc:
        raise ValueError("site must be 0..3 and spin must be up or down") from exc


def four_site_hopping_matrix(*, t_up: float, t_down: float) -> Array:
    """Single-particle K for the PBC ring, with H_0 = c^dagger K c."""
    matrix = np.zeros((8, 8))
    edges = ((0, 1), (1, 2), (2, 3), (3, 0))
    for spin, hopping in (("up", t_up), ("down", t_down)):
        for site_i, site_j in edges:
            i = hubbard_orbital_index(site_i, spin)
            j = hubbard_orbital_index(site_j, spin)
            matrix[i, j] = -float(hopping)
            matrix[j, i] = -float(hopping)
    return matrix


def spin_flip_vertex(
    site: int,
    field: int,
    *,
    u: float,
    gamma: float,
) -> Array:
    """Return Lambda_i^s = s lambda (|up><down| + |down><up|)."""
    if field not in (-1, 1):
        raise ValueError("the auxiliary field must be -1 or +1")
    if u <= 0 or gamma <= 0:
        raise ValueError("this real spin-flip decomposition requires U,Gamma > 0")

    coupling = float(np.arccosh(1.0 + u / (2.0 * gamma)))
    up = hubbard_orbital_index(site, "up")
    down = hubbard_orbital_index(site, "down")
    vertex = np.zeros((8, 8))
    vertex[up, down] = field * coupling
    vertex[down, up] = field * coupling
    return vertex


def onsite_spin_flip_decomposition_residual(*, u: float, gamma: float) -> float:
    """Directly check -v = Gamma/2 sum_s exp(s lambda S_x) on one site."""
    if u <= 0 or gamma <= 0:
        raise ValueError("this real spin-flip decomposition requires U,Gamma > 0")

    number_up = np.diag([0.0, 1.0, 0.0, 1.0])
    number_down = np.diag([0.0, 0.0, 1.0, 1.0])
    identity = np.eye(4)
    interaction = (
        u * (number_up @ number_down - 0.5 * (number_up + number_down))
        - gamma * identity
    )

    spin_flip_one_body = np.array([[0.0, 1.0], [1.0, 0.0]])
    spin_flip_fock = bilinear_fock_operator(spin_flip_one_body)
    coupling = float(np.arccosh(1.0 + u / (2.0 * gamma)))
    auxiliary_sum = 0.5 * gamma * (
        expm(coupling * spin_flip_fock) + expm(-coupling * spin_flip_fock)
    )
    return float(np.linalg.norm(-interaction - auxiliary_sum, ord="fro"))


def generate_hubbard_configurations(
    *,
    count: int,
    beta: float,
    seed: int,
) -> tuple[tuple[HubbardVertex, ...], ...]:
    """Generate the preregistered k=index mod 9 configuration sequence."""
    if count < 1 or beta <= 0:
        raise ValueError("count and beta must be positive")

    rng = np.random.default_rng(seed)
    configurations: list[tuple[HubbardVertex, ...]] = []
    for index in range(count):
        order = index % 9
        times = np.sort(rng.uniform(0.0, beta, size=order))
        sites = rng.integers(0, 4, size=order)
        fields = rng.choice(np.array([-1, 1]), size=order)
        configurations.append(
            tuple(
                HubbardVertex(float(tau), int(site), int(field))
                for tau, site, field in zip(times, sites, fields, strict=True)
            )
        )
    return tuple(configurations)


def hubbard_configuration_generators(
    vertices: Sequence[HubbardVertex],
    *,
    beta: float,
    hopping: Array,
    u: float,
    gamma: float,
) -> tuple[Array, ...]:
    """Build e^{-(beta-tau_k)K} e^{Lambda_k} ... e^{-tau_1 K}."""
    hopping_matrix = _as_square_matrix(hopping)
    if hopping_matrix.shape != (8, 8):
        raise ValueError("the four-site hopping matrix must be 8 by 8")
    if beta <= 0:
        raise ValueError("beta must be positive")

    ordered = tuple(vertices)
    previous = 0.0
    for vertex in ordered:
        if not (previous <= vertex.tau <= beta):
            raise ValueError("vertices must be sorted within [0,beta]")
        previous = vertex.tau

    generators: list[Array] = []
    later_time = float(beta)
    for vertex in reversed(ordered):
        generators.append(-(later_time - vertex.tau) * hopping_matrix)
        generators.append(
            spin_flip_vertex(vertex.site, vertex.field, u=u, gamma=gamma)
        )
        later_time = vertex.tau
    generators.append(-later_time * hopping_matrix)
    return tuple(generators)


def four_site_free_propagator(
    delta_tau: float,
    *,
    t_up: float,
    t_down: float,
    dtype=np.longdouble,
) -> Array:
    """Analytic exp(-delta_tau K) for the four-site periodic ring."""
    if delta_tau < 0:
        raise ValueError("delta_tau must be nonnegative")

    cast = np.dtype(dtype).type
    propagator = np.eye(8, dtype=dtype)
    for spin, hopping in (("up", t_up), ("down", t_down)):
        amplitude = cast(str(delta_tau)) * cast(str(hopping))
        cosh_two = np.cosh(cast(2) * amplitude)
        sinh_two = np.sinh(cast(2) * amplitude)
        first_row = (
            (cosh_two + cast(1)) / cast(2),
            sinh_two / cast(2),
            (cosh_two - cast(1)) / cast(2),
            sinh_two / cast(2),
        )
        block = np.empty((4, 4), dtype=dtype)
        for row in range(4):
            for column in range(4):
                block[row, column] = first_row[(column - row) % 4]
        indices = [hubbard_orbital_index(site, spin) for site in range(4)]
        propagator[np.ix_(indices, indices)] = block
    return propagator


def spin_flip_propagator(
    site: int,
    field: int,
    *,
    u: float,
    gamma: float,
    dtype=np.longdouble,
) -> Array:
    """Analytic exp(Lambda_i^s) in its two-dimensional orbital block."""
    spin_flip_vertex(site, field, u=u, gamma=gamma)
    cast = np.dtype(dtype).type
    coupling = np.arccosh(
        cast(1) + cast(str(u)) / (cast(2) * cast(str(gamma)))
    )
    diagonal = np.cosh(coupling)
    off_diagonal = cast(field) * np.sinh(coupling)
    up = hubbard_orbital_index(site, "up")
    down = hubbard_orbital_index(site, "down")
    propagator = np.eye(8, dtype=dtype)
    propagator[up, up] = diagonal
    propagator[down, down] = diagonal
    propagator[up, down] = off_diagonal
    propagator[down, up] = off_diagonal
    return propagator


def hubbard_configuration_evolution(
    vertices: Sequence[HubbardVertex],
    *,
    beta: float,
    t_up: float,
    t_down: float,
    u: float,
    gamma: float,
) -> tuple[Array, float]:
    """Form the physical evolution and its absolute group residual in longdouble."""
    if beta <= 0:
        raise ValueError("beta must be positive")
    ordered = tuple(vertices)
    previous = 0.0
    for vertex in ordered:
        if not (previous <= vertex.tau <= beta):
            raise ValueError("vertices must be sorted within [0,beta]")
        previous = vertex.tau

    evolution = np.eye(8, dtype=np.longdouble)
    later_time = float(beta)
    for vertex in reversed(ordered):
        evolution = evolution @ four_site_free_propagator(
            later_time - vertex.tau,
            t_up=t_up,
            t_down=t_down,
        )
        evolution = evolution @ spin_flip_propagator(
            vertex.site,
            vertex.field,
            u=u,
            gamma=gamma,
        )
        later_time = vertex.tau
    evolution = evolution @ four_site_free_propagator(
        later_time,
        t_up=t_up,
        t_down=t_down,
    )

    eta = np.asarray(split_metric(4), dtype=np.longdouble)
    residual_matrix = evolution.T @ eta @ evolution - eta
    residual = float(np.sqrt(np.sum(residual_matrix * residual_matrix)))
    return np.asarray(evolution, dtype=np.float64), residual


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _atomic_write_json(path: Path, payload: object) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _configuration_to_json(vertices: Sequence[HubbardVertex]) -> list[dict]:
    return [
        {"tau": vertex.tau, "site": vertex.site, "field": vertex.field}
        for vertex in vertices
    ]


def _weights_svg(weights: Sequence[float], orders: Sequence[int]) -> str:
    width, height = 960, 500
    left, right, top, bottom = 78, 28, 38, 62
    plot_width = width - left - right
    plot_height = height - top - bottom
    logs = np.log10(np.maximum(np.asarray(weights, dtype=float), np.finfo(float).tiny))
    y_min = float(np.floor(np.min(logs)))
    y_max = float(np.ceil(np.max(logs)))
    if y_max <= y_min:
        y_max = y_min + 1.0

    palette = (
        "#355cde",
        "#00a6a6",
        "#00a65a",
        "#9aaf00",
        "#f0a000",
        "#ef6c35",
        "#d33f6a",
        "#8b52c7",
        "#4f6070",
    )
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="480" y="24" text-anchor="middle" font-family="sans-serif" font-size="17">Four-site Hubbard configuration weights</text>',
    ]
    for tick in range(int(y_min), int(y_max) + 1):
        y = top + (y_max - tick) / (y_max - y_min) * plot_height
        elements.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#e2e6ec" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{left-10}" y="{y+4:.2f}" text-anchor="end" font-family="monospace" font-size="12">{tick}</text>'
        )
    elements.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#1f2630" stroke-width="1.5"/>',
            f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#1f2630" stroke-width="1.5"/>',
        ]
    )
    count = len(weights)
    for index, (value, order) in enumerate(zip(logs, orders, strict=True)):
        x = left + (index / max(count - 1, 1)) * plot_width
        y = top + (y_max - float(value)) / (y_max - y_min) * plot_height
        elements.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.6" fill="{palette[order % len(palette)]}" opacity="0.82"/>'
        )
    for x_tick in (0, 64, 128, 192, 255):
        x = left + (x_tick / max(count - 1, 1)) * plot_width
        elements.append(
            f'<text x="{x:.2f}" y="{height-bottom+22}" text-anchor="middle" font-family="monospace" font-size="12">{x_tick}</text>'
        )
    elements.extend(
        [
            f'<text x="{left + plot_width/2:.2f}" y="{height-17}" text-anchor="middle" font-family="sans-serif" font-size="13">configuration index</text>',
            f'<text x="18" y="{top + plot_height/2:.2f}" text-anchor="middle" transform="rotate(-90 18 {top + plot_height/2:.2f})" font-family="sans-serif" font-size="13">log10 det(I + T)</text>',
            '<text x="780" y="48" font-family="sans-serif" font-size="11" fill="#4f6070">color: expansion order k=0,...,8</text>',
            "</svg>",
        ]
    )
    return "\n".join(elements) + "\n"


def _diagnostics_svg(diagnostics: Sequence[tuple[str, float, float]]) -> str:
    width, height = 960, 440
    left, right, top, bottom = 250, 40, 50, 45
    usable_width = width - left - right
    row_height = (height - top - bottom) / len(diagnostics)
    max_score = 18.0
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="480" y="26" text-anchor="middle" font-family="sans-serif" font-size="17">Structural residuals (longer bars are smaller errors)</text>',
    ]
    for index, (label, value, tolerance) in enumerate(diagnostics):
        score = min(max_score, max(0.0, -np.log10(max(value, 1e-18))))
        tolerance_score = min(max_score, max(0.0, -np.log10(tolerance)))
        y = top + index * row_height + 8
        bar_width = score / max_score * usable_width
        tolerance_x = left + tolerance_score / max_score * usable_width
        color = "#16856b" if value <= tolerance else "#c0392b"
        elements.extend(
            [
                f'<text x="{left-12}" y="{y+18:.2f}" text-anchor="end" font-family="sans-serif" font-size="13">{label}</text>',
                f'<rect x="{left}" y="{y:.2f}" width="{usable_width}" height="25" fill="#edf0f4" rx="3"/>',
                f'<rect x="{left}" y="{y:.2f}" width="{bar_width:.2f}" height="25" fill="{color}" rx="3"/>',
                f'<line x1="{tolerance_x:.2f}" y1="{y-3:.2f}" x2="{tolerance_x:.2f}" y2="{y+28:.2f}" stroke="#1f2630" stroke-width="2"/>',
                f'<text x="{left+8}" y="{y+17:.2f}" font-family="monospace" font-size="11" fill="#ffffff">{value:.3e}</text>',
            ]
        )
    elements.extend(
        [
            f'<text x="{left + usable_width/2:.2f}" y="{height-12}" text-anchor="middle" font-family="sans-serif" font-size="12">-log10(residual); black marker is preregistered tolerance</text>',
            "</svg>",
        ]
    )
    return "\n".join(elements) + "\n"


def _run_parameters(run: dict) -> dict[str, object]:
    couplings = run["model"]["couplings"]
    settings = run["method"]["settings"]
    cross_check_indices = [
        int(value)
        for value in re.findall(r"\d+", settings["fock_cross_checks"])
    ]
    parameters = {
        "t_up": float(couplings["$t_\\uparrow$"]),
        "t_down": float(couplings["$t_\\downarrow$"]),
        "u": float(couplings["$U$"]),
        "gamma": float(couplings["$\\Gamma$"]),
        "beta": float(couplings["$\\beta$"]),
        "mu": float(couplings["$\\mu$"]),
        "count": int(settings["configuration_count"]),
        "seed": int(settings["random_seed"]),
        "cross_check_indices": cross_check_indices,
        "lie_tolerance": float(settings["lie_tolerance"]),
        "group_tolerance": float(settings["group_tolerance"]),
        "trace_tolerance": float(settings["trace_determinant_tolerance"]),
        "weight_tolerance": float(settings["weight_tolerance"]),
    }
    if parameters["mu"] != 0.0:
        raise ValueError("the approved half-filled run requires mu=0")
    return parameters


def run_approved_hubbard_oracle(run_dir: Path) -> dict:
    """Execute the preregistered run and update its single source, run.json."""
    run_path = run_dir / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    parameters = _run_parameters(run)

    t_up = parameters["t_up"]
    t_down = parameters["t_down"]
    u = parameters["u"]
    gamma = parameters["gamma"]
    beta = parameters["beta"]
    count = parameters["count"]
    seed = parameters["seed"]
    lie_tolerance = parameters["lie_tolerance"]
    group_tolerance = parameters["group_tolerance"]
    trace_tolerance = parameters["trace_tolerance"]
    weight_tolerance = parameters["weight_tolerance"]
    cross_check_indices = parameters["cross_check_indices"]

    start_total = time.perf_counter()
    eta = split_metric(4)
    hopping = four_site_hopping_matrix(t_up=t_up, t_down=t_down)
    hopping_lie_residual = split_lie_residual(hopping, eta)
    vertex_lie_residuals = [
        split_lie_residual(
            spin_flip_vertex(site, field, u=u, gamma=gamma),
            eta,
        )
        for site in range(4)
        for field in (-1, 1)
    ]
    onsite_residual = onsite_spin_flip_decomposition_residual(u=u, gamma=gamma)
    configurations = generate_hubbard_configurations(
        count=count,
        beta=beta,
        seed=seed,
    )

    print(
        f"setup: L=4 beta={beta:g} U={u:g} Gamma={gamma:g} "
        f"configs={count} seed={seed}",
        flush=True,
    )
    determinant_start = time.perf_counter()
    records: list[dict] = []
    weights: list[float] = []
    orders: list[int] = []
    max_generator_residual = 0.0
    for index, vertices in enumerate(configurations):
        generators = hubbard_configuration_generators(
            vertices,
            beta=beta,
            hopping=hopping,
            u=u,
            gamma=gamma,
        )
        generator_residual = max(
            split_lie_residual(generator, eta) for generator in generators
        )
        max_generator_residual = max(max_generator_residual, generator_residual)
        evolution, group_residual = hubbard_configuration_evolution(
            vertices,
            beta=beta,
            t_up=t_up,
            t_down=t_down,
            u=u,
            gamma=gamma,
        )
        component = classify_split_component(
            evolution,
            eta,
            atol=max(group_tolerance * 10.0, 1e-9),
        )
        determinant = float(np.real_if_close(determinant_i_plus(evolution)))
        scalar_prefactor = float((gamma / 2.0) ** len(vertices))
        weight = scalar_prefactor * determinant
        weights.append(weight)
        orders.append(len(vertices))
        records.append(
            {
                "index": index,
                "order": len(vertices),
                "vertices": _configuration_to_json(vertices),
                "determinant": determinant,
                "scalar_prefactor": scalar_prefactor,
                "weight": weight,
                "component": component,
                "generator_lie_residual": generator_residual,
                "group_residual": group_residual,
            }
        )
        if (index + 1) % 64 == 0 or index + 1 == count:
            print(
                f"single-particle: {index + 1}/{count}; "
                f"min_weight={min(weights):.6e}; "
                f"max_group_residual={max(item['group_residual'] for item in records):.3e}",
                flush=True,
            )
    determinant_wall = time.perf_counter() - determinant_start

    fock_start = time.perf_counter()
    fock_checks: list[dict] = []
    for index in cross_check_indices:
        vertices = configurations[index]
        generators = hubbard_configuration_generators(
            vertices,
            beta=beta,
            hopping=hopping,
            u=u,
            gamma=gamma,
        )
        fock_trace = float(np.real_if_close(fock_trace_weight(generators)))
        determinant = records[index]["determinant"]
        absolute_error = abs(fock_trace - determinant)
        relative_error = absolute_error / max(1.0, abs(determinant))
        fock_checks.append(
            {
                "index": index,
                "order": len(vertices),
                "fock_trace": fock_trace,
                "determinant": determinant,
                "absolute_error": absolute_error,
                "relative_error": relative_error,
            }
        )
        print(
            f"fock-check: index={index} k={len(vertices)} "
            f"relative_error={relative_error:.3e}",
            flush=True,
        )
    fock_wall = time.perf_counter() - fock_start
    total_wall = time.perf_counter() - start_total

    component_counts = {
        component: sum(record["component"] == component for record in records)
        for component in ("++", "--", "-+", "+-")
    }
    negative_count = sum(weight < -weight_tolerance for weight in weights)
    near_zero_count = sum(abs(weight) <= weight_tolerance for weight in weights)
    max_group_residual = max(record["group_residual"] for record in records)
    max_trace_relative_error = max(
        check["relative_error"] for check in fock_checks
    )
    max_vertex_lie_residual = max(vertex_lie_residuals)
    max_memory_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0**2)

    checks = {
        "onsite_decomposition": onsite_residual <= lie_tolerance,
        "hopping_lie_algebra": hopping_lie_residual <= lie_tolerance,
        "vertex_lie_algebra": max_vertex_lie_residual <= lie_tolerance,
        "all_generator_lie_algebra": max_generator_residual <= lie_tolerance,
        "group_preservation": max_group_residual <= group_tolerance,
        "identity_component": component_counts["++"] == count,
        "nonnegative_weight": negative_count == 0,
        "fock_trace_identity": max_trace_relative_error <= trace_tolerance,
    }
    passed = all(checks.values())

    numerical_change = (
        "Initial SciPy double-precision factors exposed condition-amplified "
        "roundoff in the absolute group residual. The final evaluation uses "
        "the analytic C4 free propagator and analytic 2x2 spin-flip propagator, "
        "accumulated in NumPy longdouble; the model, configurations, determinant "
        "definition, and preregistered 1e-10 threshold stay fixed."
    )
    result = {
        "status": "passed" if passed else "failed",
        "parameters": parameters,
        "checks": checks,
        "changes": [numerical_change],
        "diagnostics": {
            "onsite_decomposition_residual": onsite_residual,
            "hopping_lie_residual": hopping_lie_residual,
            "max_vertex_lie_residual": max_vertex_lie_residual,
            "max_generator_lie_residual": max_generator_residual,
            "max_group_residual": max_group_residual,
            "max_fock_trace_relative_error": max_trace_relative_error,
            "min_weight": min(weights),
            "max_weight": max(weights),
            "negative_weight_count": negative_count,
            "near_zero_weight_count": near_zero_count,
            "component_counts": component_counts,
        },
        "theorem_anchors": {
            "o11_identity_component_weight": 16.0 / 3.0,
            "o11_negative_component_weight": -4.0 / 3.0,
            "o11_mixed_component_weight": 0.0,
        },
        "timing": {
            "single_particle_wall_seconds": determinant_wall,
            "fock_wall_seconds": fock_wall,
            "total_wall_seconds": total_wall,
            "max_memory_gb": max_memory_gb,
        },
        "fock_checks": fock_checks,
        "configurations": records,
    }

    _atomic_write_json(run_dir / "data" / "results.json", result)
    _atomic_write_text(
        run_dir / "figs" / "configuration_weights.svg",
        _weights_svg(weights, orders),
    )
    diagnostics_for_plot = (
        ("on-site HS identity", onsite_residual, lie_tolerance),
        ("hopping Lie residual", hopping_lie_residual, lie_tolerance),
        ("vertex Lie residual", max_vertex_lie_residual, lie_tolerance),
        ("product group residual", max_group_residual, group_tolerance),
        ("Fock/determinant error", max_trace_relative_error, trace_tolerance),
    )
    _atomic_write_text(
        run_dir / "figs" / "diagnostic_residuals.svg",
        _diagnostics_svg(diagnostics_for_plot),
    )

    rerun = f"python {Path(__file__)} --run-dir {run_dir}"
    run["actual"] = [
        {
            "point": "256 single-particle configurations",
            "wall": f"{determinant_wall:.3f} s",
            "memory": f"{max_memory_gb:.3f} GB peak process RSS",
        },
        {
            "point": "3 direct 256-dimensional Fock checks",
            "wall": f"{fock_wall:.3f} s",
            "memory": f"{max_memory_gb:.3f} GB peak process RSS",
        },
    ]
    verdict = "yes" if passed else "no"
    run["figures"][0]["results"] = {
        "figure": "figs/configuration_weights.svg",
        "numbers": {
            "configurations": count,
            "O++ configurations": component_counts["++"],
            "negative weights": negative_count,
            "minimum weight": f"{min(weights):.12e}",
            "maximum weight": f"{max(weights):.12e}",
            "max group residual": f"{max_group_residual:.3e}",
            "max Fock relative error": f"{max_trace_relative_error:.3e}",
        },
        "match": verdict,
        "why": (
            "All preregistered physical configurations stayed in O++(4,4), "
            "had nonnegative weights, and the independent Fock checks passed."
            if passed
            else "At least one preregistered structural or sign check failed."
        ),
        "wall": f"{total_wall:.3f} s total",
        "changes": [numerical_change],
        "rerun": rerun,
    }
    run["figures"][1]["results"] = {
        "figure": "figs/diagnostic_residuals.svg",
        "numbers": {
            "on-site HS residual": f"{onsite_residual:.3e}",
            "hopping Lie residual": f"{hopping_lie_residual:.3e}",
            "max vertex Lie residual": f"{max_vertex_lie_residual:.3e}",
            "max generator Lie residual": f"{max_generator_residual:.3e}",
            "max group residual": f"{max_group_residual:.3e}",
            "max Fock relative error": f"{max_trace_relative_error:.3e}",
        },
        "match": verdict,
        "why": (
            "The interaction identity, every generator, every group product, "
            "and the Fock-space trace all met their preregistered tolerances."
            if passed
            else "At least one preregistered residual exceeded its tolerance."
        ),
        "wall": f"{total_wall:.3f} s total",
        "changes": [numerical_change],
        "rerun": rerun,
    }
    _atomic_write_json(run_path, run)

    print(
        f"complete: status={result['status']} total={total_wall:.3f}s "
        f"min_weight={min(weights):.6e} negatives={negative_count}",
        flush=True,
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the approved four-site Hubbard sign-problem oracle."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Directory containing the approved run.json.",
    )
    args = parser.parse_args(argv)
    result = run_approved_hubbard_oracle(args.run_dir.resolve())
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
