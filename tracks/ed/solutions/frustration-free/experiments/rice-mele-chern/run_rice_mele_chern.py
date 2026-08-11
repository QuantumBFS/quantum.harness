from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian


@dataclass(frozen=True)
class FHSDiagnostics:
    chern_raw: float
    chern_integer: int
    integer_deviation: float
    minimum_overlap: float
    maximum_link_modulus_error: float
    maximum_absolute_flux: float
    flux: np.ndarray


@dataclass(frozen=True)
class VertexResult:
    state: np.ndarray
    energies: tuple[float, float]
    gap: float
    hermiticity_error: float
    basis_fingerprint: str


@dataclass(frozen=True)
class GridScanResult:
    size: int
    states: np.ndarray
    gaps: np.ndarray
    fhs: FHSDiagnostics
    minimum_gap: float
    maximum_hermiticity_error: float
    new_diagonalizations: int
    total_diagonalizations: int


def compute_fhs(
    states: np.ndarray,
    overlap_threshold: float = 1e-12,
    admissibility_margin: float = 1e-8,
) -> FHSDiagnostics:
    """Compute oriented FHS fluxes for states indexed by (phi, theta)."""
    if states.ndim != 3:
        raise ValueError("states must have shape (N_phi, N_theta, basis_dimension)")

    phi_neighbor = np.roll(states, -1, axis=0)
    theta_neighbor = np.roll(states, -1, axis=1)
    phi_overlap = np.einsum("mni,mni->mn", states.conj(), phi_neighbor)
    theta_overlap = np.einsum("mni,mni->mn", states.conj(), theta_neighbor)
    magnitudes = np.concatenate((np.abs(phi_overlap).ravel(), np.abs(theta_overlap).ravel()))
    if not np.all(np.isfinite(magnitudes)) or np.min(magnitudes) <= overlap_threshold:
        raise ValueError("neighbor overlap is non-finite or below threshold")

    u_phi = phi_overlap / np.abs(phi_overlap)
    u_theta = theta_overlap / np.abs(theta_overlap)
    plaquette = (
        u_phi
        * np.roll(u_theta, -1, axis=0)
        * np.conj(np.roll(u_phi, -1, axis=1))
        * np.conj(u_theta)
    )
    flux = np.angle(plaquette)
    maximum_absolute_flux = float(np.max(np.abs(flux)))
    if maximum_absolute_flux >= np.pi - admissibility_margin:
        raise ValueError("plaquette flux reaches the principal-branch boundary")

    chern_raw = float(np.sum(flux) / (2.0 * np.pi))
    chern_integer = round(chern_raw)
    maximum_link_modulus_error = float(
        max(
            np.max(np.abs(np.abs(u_phi) - 1.0)),
            np.max(np.abs(np.abs(u_theta) - 1.0)),
        )
    )
    return FHSDiagnostics(
        chern_raw=chern_raw,
        chern_integer=chern_integer,
        integer_deviation=abs(chern_raw - chern_integer),
        minimum_overlap=float(np.min(magnitudes)),
        maximum_link_modulus_error=maximum_link_modulus_error,
        maximum_absolute_flux=maximum_absolute_flux,
        flux=flux,
    )


def verify_gauge_invariance(result: GridScanResult, seed: int = 20260728) -> float:
    """Return the largest FHS change after independent random grid-point phases."""
    rng = np.random.default_rng(seed)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=result.states.shape[:2])
    phased_states = result.states * np.exp(1j * phases)[:, :, None]
    transformed = compute_fhs(phased_states)
    return float(
        max(
            np.max(np.abs(transformed.flux - result.fhs.flux)),
            abs(transformed.chern_raw - result.fhs.chern_raw),
        )
    )


class RiceMeleChernScanner:
    """Cached exact-diagonalization scan with one shared many-body basis."""

    def __init__(
        self,
        L: int = 6,
        t: float = 1.0,
        delta0: float = 0.5,
        Delta0: float = 0.3,
    ) -> None:
        if L % 2:
            raise ValueError("L must be even at half filling")
        self.L = L
        self.t = t
        self.delta0 = delta0
        self.Delta0 = Delta0
        particles_per_spin = L // 2
        self.basis = spinful_fermion_basis_1d(
            L,
            Nf=(particles_per_spin, particles_per_spin),
        )
        self.basis_fingerprint = hashlib.sha256(self.basis.states.tobytes()).hexdigest()
        self.cache: dict[tuple[Fraction, Fraction], VertexResult] = {}
        self.diagonalization_count = 0

    @property
    def parameters(self) -> dict[str, float | int]:
        return {
            "L": self.L,
            "t": self.t,
            "delta0": self.delta0,
            "Delta0": self.Delta0,
            "U": 0.0,
            "N_up": self.L // 2,
            "N_down": self.L // 2,
        }

    def build_hamiltonian(self, phi: float, theta: float):
        delta = self.delta0 * np.cos(phi)
        Delta = self.Delta0 * np.sin(phi)
        up_hopping = []
        down_hopping = []
        for j in range(self.L - 1):
            coefficient = -(self.t + (-1) ** (j + 1) * delta)
            up_hopping.extend([[coefficient, j, j + 1], [coefficient, j + 1, j]])
            down_hopping.extend([[coefficient, j, j + 1], [coefficient, j + 1, j]])

        boundary_coefficient = -(self.t + (-1) ** self.L * delta)
        forward_boundary = boundary_coefficient * np.exp(1j * theta)
        backward_boundary = boundary_coefficient * np.exp(-1j * theta)
        up_hopping.extend(
            [[forward_boundary, self.L - 1, 0], [backward_boundary, 0, self.L - 1]]
        )
        down_hopping.extend(
            [[forward_boundary, self.L - 1, 0], [backward_boundary, 0, self.L - 1]]
        )
        onsite = [[Delta * (-1) ** (j + 1), j] for j in range(self.L)]
        static = [
            ["+-|", up_hopping],
            ["|+-", down_hopping],
            ["n|", onsite],
            ["|n", onsite],
        ]
        return hamiltonian(
            static,
            [],
            basis=self.basis,
            dtype=np.complex128,
            check_herm=False,
            check_symm=False,
            check_pcon=False,
        )

    def _vertex(self, key: tuple[Fraction, Fraction]) -> VertexResult:
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        phi_fraction, theta_fraction = key
        phi = 2.0 * np.pi * float(phi_fraction)
        theta = 2.0 * np.pi * float(theta_fraction)
        H = self.build_hamiltonian(phi, theta)
        matrix = H.toarray()
        hermiticity_error = float(np.max(np.abs(matrix - matrix.conj().T)))
        if hermiticity_error >= 1e-12:
            raise RuntimeError(f"Hamiltonian is not Hermitian: error={hermiticity_error:.3e}")

        energies, vectors = H.eigsh(k=2, which="SA")
        order = np.argsort(energies)
        energies = np.asarray(energies[order].real)
        state = np.asarray(vectors[:, order[0]], dtype=np.complex128)
        state /= np.linalg.norm(state)
        result = VertexResult(
            state=state,
            energies=(float(energies[0]), float(energies[1])),
            gap=float(energies[1] - energies[0]),
            hermiticity_error=hermiticity_error,
            basis_fingerprint=self.basis_fingerprint,
        )
        self.cache[key] = result
        self.diagonalization_count += 1
        return result

    def scan_grid(self, size: int) -> GridScanResult:
        if size < 2:
            raise ValueError("grid size must be at least 2")
        before = self.diagonalization_count
        vertices = [
            [self._vertex((Fraction(m, size), Fraction(n, size))) for n in range(size)]
            for m in range(size)
        ]
        states = np.asarray([[vertex.state for vertex in row] for row in vertices])
        gaps = np.asarray([[vertex.gap for vertex in row] for row in vertices])
        hermiticity_errors = [vertex.hermiticity_error for row in vertices for vertex in row]
        return GridScanResult(
            size=size,
            states=states,
            gaps=gaps,
            fhs=compute_fhs(states),
            minimum_gap=float(np.min(gaps)),
            maximum_hermiticity_error=float(max(hermiticity_errors)),
            new_diagonalizations=self.diagonalization_count - before,
            total_diagonalizations=self.diagonalization_count,
        )


def _grid_summary(result: GridScanResult, gauge_error: float) -> dict[str, float | int]:
    return {
        "grid_size": result.size,
        "chern_raw": result.fhs.chern_raw,
        "chern_integer": result.fhs.chern_integer,
        "integer_deviation": result.fhs.integer_deviation,
        "minimum_gap_on_grid": result.minimum_gap,
        "minimum_neighbor_overlap": result.fhs.minimum_overlap,
        "maximum_link_modulus_error": result.fhs.maximum_link_modulus_error,
        "maximum_absolute_plaquette_flux": result.fhs.maximum_absolute_flux,
        "maximum_hermiticity_error": result.maximum_hermiticity_error,
        "random_gauge_invariance_error": gauge_error,
        "new_diagonalizations": result.new_diagonalizations,
        "total_diagonalizations": result.total_diagonalizations,
    }


def run_nested_scan(
    grid_sizes: tuple[int, ...] = (5, 10, 20),
    output_path: Path | None = None,
) -> dict[str, object]:
    """Run nested grids, print diagnostics, and optionally persist a JSON summary."""
    scanner = RiceMeleChernScanner()
    results = [scanner.scan_grid(size) for size in grid_sizes]
    summaries = [
        _grid_summary(result, verify_gauge_invariance(result, seed=20260728 + result.size))
        for result in results
    ]
    payload: dict[str, object] = {
        "parameters": scanner.parameters,
        "basis": {
            "dimension": scanner.basis.Ns,
            "ordering_fingerprint": scanner.basis_fingerprint,
            "shared_across_all_grid_points": all(
                vertex.basis_fingerprint == scanner.basis_fingerprint
                for vertex in scanner.cache.values()
            ),
        },
        "grid_results": summaries,
        "cache": {"unique_diagonalizations": scanner.diagonalization_count},
    }

    print(
        "grid  C_raw          C_int  deviation   min_gap    min_overlap  "
        "max|flux|  new  total"
    )
    for row in summaries:
        print(
            f"{row['grid_size']:>4}  {row['chern_raw']:>+13.10f}  "
            f"{row['chern_integer']:>5}  {row['integer_deviation']:.2e}  "
            f"{row['minimum_gap_on_grid']:.8f}  "
            f"{row['minimum_neighbor_overlap']:.8f}  "
            f"{row['maximum_absolute_plaquette_flux']:.8f}  "
            f"{row['new_diagonalizations']:>3}  {row['total_diagonalizations']:>5}"
        )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"Saved summary: {output_path}")
    return payload


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    run_nested_scan(
        output_path=project_root / "results" / "rice-mele-chern" / "rice_mele_chern.json"
    )
