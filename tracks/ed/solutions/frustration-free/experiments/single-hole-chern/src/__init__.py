"""Single-hole Chern number experiment.

Computes low-energy many-body spectrum and topological invariants
for one-hole doped Rice-Mele-Hubbard model.
"""

from .k_sectors import KSectorProjectors, build_k_projectors, build_t2, project_hamiltonian
from .model import OneHoleRMHModel, hermiticity_error
from .pump_path import pump_path, pump_delta, pump_Delta
from .spectrum import compute_k_resolved_spectrum, SpectrumResult
from .topology import (
    compute_fhs_nonabelian,
    compute_wilson_loop,
    compute_zak_phase,
    FHSDiagnostics,
    subspace_overlap_matrix,
    track_subspace,
)
from .io import save_spectrum_result, load_spectrum_result, save_chern_result, load_chern_result

__all__ = [
    "KSectorProjectors",
    "build_k_projectors",
    "build_t2",
    "project_hamiltonian",
    "OneHoleRMHModel",
    "hermiticity_error",
    "pump_path",
    "pump_delta",
    "pump_Delta",
    "compute_k_resolved_spectrum",
    "SpectrumResult",
    "compute_fhs_nonabelian",
    "compute_wilson_loop",
    "compute_zak_phase",
    "FHSDiagnostics",
    "subspace_overlap_matrix",
    "track_subspace",
    "save_spectrum_result",
    "load_spectrum_result",
    "save_chern_result",
    "load_chern_result",
]
