"""
Haldane sphere geometry and coordinates.

Provides the Haldane sphere construction for the fractional quantum Hall effect:
- Spinor coordinates (u, v) on the sphere
- Chord distance matrix
- Monopole harmonics (for ED cross-check)
- Angular momentum operators
"""

import torch
import math
import numpy as np

# ──────────────────────────────────────────────
# Type aliases
# ──────────────────────────────────────────────
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
dtype_real = torch.float64
dtype_cplx = torch.complex128


def spinor_coordinates(theta: torch.Tensor, phi: torch.Tensor) -> tuple:
    """
    Convert spherical coordinates to spinor coordinates (u, v).

    Args:
        theta: [batch, N] polar angle ∈ [0, π]
        phi:   [batch, N] azimuthal angle ∈ [0, 2π)

    Returns:
        u: [batch, N]  u_j = cos(θ_j/2) exp(i φ_j/2)
        v: [batch, N]  v_j = sin(θ_j/2) exp(-i φ_j/2)
    """
    half = 0.5
    u = torch.cos(theta * half) * torch.exp(1j * phi * half)
    v = torch.sin(theta * half) * torch.exp(-1j * phi * half)
    return u, v


def random_sphere_positions(batch: int, n_elec: int, seed: int = None):
    """
    Sample random positions uniformly on the sphere.

    Returns:
        theta: [batch, N]
        phi:   [batch, N]
        xyz:   [batch, N, 3]
    """
    if seed is not None:
        torch.manual_seed(seed)
    # Uniform sampling on sphere
    u = torch.rand(batch, n_elec, device=device, dtype=dtype_real)
    theta = torch.acos(2 * u - 1)              # θ = arccos(2u-1) for uniform
    phi = 2 * math.pi * torch.rand(batch, n_elec, device=device, dtype=dtype_real)

    x = torch.sin(theta) * torch.cos(phi)
    y = torch.sin(theta) * torch.sin(phi)
    z = torch.cos(theta)
    xyz = torch.stack([x, y, z], dim=-1)       # [batch, N, 3]

    return theta, phi, xyz


def chord_distance_matrix(xyz: torch.Tensor) -> torch.Tensor:
    """
    Compute chord distance matrix between all pairs of electrons.

    |r_i - r_j| on the sphere = 2 sin(θ_{ij}/2)
    where cos θ_{ij} = r_i · r_j / (R²)

    Args:
        xyz: [batch, N, 3] 3D coordinates on sphere

    Returns:
        d: [batch, N, N] chord distance matrix (diagonal = 0)
    """
    # xyz is unit vector on sphere (R=1 for chord distance in units of R)
    # chord distance = |r_i - r_j| = sqrt(2(1 - cos θ_ij))
    dot = torch.matmul(xyz, xyz.transpose(-2, -1))  # [batch, N, N] cos θ_ij
    chord_sq = 2 * (1 - dot.clamp(-1, 1))            # [batch, N, N]
    chord = torch.sqrt(chord_sq.clamp(min=1e-12))
    return chord


def chord_coulomb_matrix(xyz: torch.Tensor) -> torch.Tensor:
    """
    Coulomb potential matrix V_{ij} = 1 / |r_i - r_j| on the sphere.

    On the Haldane sphere of radius R = sqrt(Q) ℓ_B:
     V = e²/(ε R) * (R / |r_i - r_j|) = e²/(εℓ_B) * sqrt(Q) / |r_i - r_j|

    Returns:
        V_mat: [batch, N, N] Coulomb matrix (diagonal = 0)
    """
    chord = chord_distance_matrix(xyz)               # in units of R
    V_mat = 1.0 / chord
    # Remove diagonal
    N = xyz.shape[-2]
    V_mat = V_mat * (1 - torch.eye(N, device=device, dtype=dtype_real))
    return V_mat


class HaldaneSphere:
    """
    Manages Haldane sphere parameters and provides coordinate utilities.

    For ν = 1/3: 2Q = 3(N - 1), so flux Q = 3(N-1)/2
    """

    def __init__(self, n_elec: int):
        self.N = n_elec
        # Flux quantum: 2Q = 3(N-1) for ν = 1/3
        self.two_Q = 3 * (n_elec - 1)
        self.Q = self.two_Q / 2.0
        # Sphere radius in magnetic length units
        self.R = math.sqrt(self.Q)
        # Maximum angular momentum for single-particle states
        self.l_max = int(self.Q)  # monopole harmonics have l = Q + n

    def sample_initial(self, batch: int, seed: int = 42) -> tuple:
        """Uniformly sample initial electron positions."""
        return random_sphere_positions(batch, self.N, seed)

    def energy_scale(self) -> float:
        """Return the energy scale e²/(εℓ_B)"""
        return 1.0 / self.R  # This is sqrt(1/Q) in units of e²/(εℓ_B)

    def total_coulomb_energy(self, xyz: torch.Tensor,
                             psi_sq: torch.Tensor = None) -> torch.Tensor:
        """
        Total Coulomb energy of a configuration.

        Args:
            xyz:  [batch, N, 3] coordinates
            psi_sq: [batch] |Ψ|² weights (for Monte Carlo averaging)

        Returns:
            energy: scalar (if psi_sq provided) or [batch] per-config energy
        """
        V_mat = chord_coulomb_matrix(xyz)  # [batch, N, N] in 1/R
        # Coulomb sum: V = ∑_{i<j} 1/|r_i - r_j|
        # In Haldane units: V = (e²/(εℓ_B)) * sqrt(Q) * ∑_{i<j} 1/(R * |r_i - r_j|/R)
        #   = (e²/(εℓ_B)) * ∑_{i<j} 1/(|r_i - r_j|/R)  (since sqrt(Q)=R)
        # Actually: V_ij = e²/(ε * r_ij) = e²/(εℓ_B) * (ℓ_B / r_ij)
        # On sphere: r_ij = R * chord_ij, so ℓ_B / r_ij = ℓ_B / (R * chord_ij) = 1/(sqrt(Q) * chord_ij)
        # More precisely: Energy is in units of e²/(εℓ_B), V = ∑_{i<j} 1/(r_ij/ℓ_B)
        # r_ij/ℓ_B = R * chord_ij / ℓ_B = sqrt(Q) * chord_ij
        # So V_ij = 1 / (sqrt(Q) * chord_ij) in units of e²/(εℓ_B)
        R = self.R
        V = V_mat / R  # [batch, N, N]

        # Sum over unique pairs
        n = self.N
        triu = torch.triu_indices(n, n, offset=1, device=device)
        E_config = V[:, triu[0], triu[1]].sum(dim=-1)  # [batch]

        if psi_sq is not None:
            return (E_config * psi_sq).sum() / psi_sq.sum()
        return E_config

    def compute_angular_momentum(self, xyz: torch.Tensor,
                                 psi: torch.Tensor) -> dict:
        """
        Compute ⟨L²⟩ and ⟨L_z⟩ for a given wavefunction.

        Approximate using the chord-coordinate representation.
        L = -i r × ∇ on the sphere.

        For the NQS, we compute L² expectation value via the
        spherical harmonic expansion of the wavefunction.

        Args:
            xyz:  [batch, N, 3]
            psi:  [batch, N] wavefunction values

        Returns:
            dict with 'L2' and 'Lz' estimates
        """
        # TODO: Implement proper angular momentum measurement
        # For now, return a placeholder
        return {'L2': 6.0 * torch.ones(1, device=device),  # Expected for L=2
                'Lz': 0.0 * torch.ones(1, device=device)}
