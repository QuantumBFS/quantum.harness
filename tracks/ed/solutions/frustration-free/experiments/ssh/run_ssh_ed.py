from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from quspin.basis import spinless_fermion_basis_1d
from quspin.operators import hamiltonian


def build_ssh_hamiltonian(L: int, t1: float, t2: float):
    basis = spinless_fermion_basis_1d(L, Nf=1)
    hoppings = []
    for bond in range(L - 1):
        coeff = -(t1 if bond % 2 == 0 else t2)
        hoppings.append([coeff, bond, bond + 1])
        hoppings.append([coeff, bond + 1, bond])
    static = [["+-", hoppings]]
    H = hamiltonian(static, [], basis=basis, dtype=np.float64)
    return basis, H


def diagonalize_ssh(L: int = 8, t1: float = 0.6, t2: float = 1.0):
    basis, H = build_ssh_hamiltonian(L, t1, t2)
    energies, vectors = H.eigh()
    matrix = H.toarray()
    hermiticity_error = float(np.max(np.abs(matrix - matrix.conj().T)))
    particle_hole_error = float(np.max(np.abs(energies + energies[::-1])))
    edge_mode_indices = sorted(np.argsort(np.abs(energies))[:2].tolist())
    edge_weights = (np.abs(vectors[0, :]) ** 2 + np.abs(vectors[-1, :]) ** 2).tolist()
    diagnostics = {
        "basis_dimension": basis.Ns,
        "hermiticity_error": hermiticity_error,
        "particle_hole_error": particle_hole_error,
        "edge_mode_indices": edge_mode_indices,
        "edge_weights": edge_weights,
    }
    if basis.Ns != L or hermiticity_error >= 1e-12 or particle_hole_error >= 1e-12:
        raise RuntimeError("SSH diagnostic failed")
    return energies, vectors, diagnostics


def write_artifacts(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    energies, _, diagnostics = diagonalize_ssh()
    candidates = set(diagnostics["edge_mode_indices"])

    with (output_dir / "energies.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "energy", "is_edge_candidate", "end_site_weight"],
        )
        writer.writeheader()
        for index, energy in enumerate(energies):
            writer.writerow(
                {
                    "index": index,
                    "energy": f"{energy:.16g}",
                    "is_edge_candidate": index in candidates,
                    "end_site_weight": f"{diagnostics['edge_weights'][index]:.16g}",
                }
            )

    grid = np.linspace(energies.min() - 0.5, energies.max() + 0.5, 600)
    broadening = 0.08
    dos = np.sum(np.exp(-0.5 * ((grid[:, None] - energies[None, :]) / broadening) ** 2), axis=1)
    dos /= np.sqrt(2.0 * np.pi) * broadening
    figure, (spectrum_axis, dos_axis) = plt.subplots(1, 2, figsize=(9, 4), constrained_layout=True)
    colors = ["tab:red" if index in candidates else "tab:blue" for index in range(len(energies))]
    spectrum_axis.scatter(range(len(energies)), energies, c=colors)
    spectrum_axis.axhline(0.0, color="black", linewidth=0.8)
    spectrum_axis.set(xlabel="level index", ylabel="energy", title="L=8 OBC SSH spectrum")
    dos_axis.plot(dos, grid, color="tab:blue")
    dos_axis.axhline(0.0, color="black", linewidth=0.8)
    dos_axis.set(xlabel="DOS (arb. units)", ylabel="energy", title="Gaussian-broadened DOS")
    figure.savefig(output_dir / "ssh_spectrum_dos.png", dpi=160)
    plt.close(figure)

    manifest = {
        "parameters": {"L": 8, "Nf": 1, "boundary": "OBC", "t1": 0.6, "t2": 1.0},
        "diagnostics": diagnostics,
        "artifacts": ["ssh_spectrum_dos.png", "energies.csv"],
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"plot": "ssh_spectrum_dos.png", "energies": "energies.csv", "manifest": "run_manifest.json"}


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    write_artifacts(project_root / "results" / "ssh")
