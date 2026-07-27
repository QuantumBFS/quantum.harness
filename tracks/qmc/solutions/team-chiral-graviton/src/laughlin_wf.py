"""
Laughlin wavefunction on the Haldane sphere.

Ψ_J(m) = ∏_{i<j} (u_i v_j - u_j v_i)^m

For ν = 1/3, m = 3.
This is the exact zero-energy ground state for the short-range interaction
and an excellent baseline for the Coulomb interaction.
"""

import torch
import math
from .haldane_sphere import device, dtype_cplx, spinor_coordinates


def lauglin_jastrow(theta: torch.Tensor, phi: torch.Tensor,
                    m: int = 3) -> torch.Tensor:
    """
    Compute the Laughlin Jastrow factor for a batch of configurations.

    ψ_J = ∏_{i<j} (u_i v_j - u_j v_i)^m

    where u_j = cos(θ_j/2) e^{iφ_j/2}, v_j = sin(θ_j/2) e^{-iφ_j/2}.

    Args:
        theta: [batch, N] polar angles
        phi:   [batch, N] azimuthal angles
        m:     Laughlin exponent (m = 3 for ν = 1/3)

    Returns:
        log_psi: [batch] complex log-wavefunction
    """
    batch, N = theta.shape

    # Spinor coordinates
    half = 0.5
    u = torch.cos(theta * half) * torch.exp(1j * phi * half)
    v = torch.sin(theta * half) * torch.exp(-1j * phi * half)

    # (u_i v_j - u_j v_i) for all i<j
    # We compute this efficiently using pairwise differences
    # (u_i v_j - u_j v_i) = u_i * v_j - u_j * v_i
    ui = u.unsqueeze(-1)  # [batch, N, 1]
    uj = u.unsqueeze(-2)  # [batch, 1, N]
    vi = v.unsqueeze(-1)
    vj = v.unsqueeze(-2)

    # Anti-symmetric pair factor
    pair_factor = ui * vj - uj * vi  # [batch, N, N]
    # Zero diagonal
    diag_mask = 1 - torch.eye(N, device=device, dtype=dtype_cplx).unsqueeze(0)
    pair_factor = pair_factor * diag_mask

    # For each configuration, sum log over upper triangle
    triu_idx = torch.triu_indices(N, N, offset=1, device=device)
    pair_upper = pair_factor[:, triu_idx[0], triu_idx[1]]  # [batch, N*(N-1)/2]

    # log ψ = m * ∑ log(pair_factor)
    # ``clamp`` is undefined for complex tensors.  Regularize only exact
    # coincidences while preserving the complex phase of every nonzero pair.
    safe_pair = torch.where(
        pair_upper.abs() < 1e-30,
        torch.full_like(pair_upper, 1e-30),
        pair_upper,
    )
    log_pair = torch.log(safe_pair)
    log_psi = m * log_pair.sum(dim=-1)  # [batch]

    return log_psi


def lauglin_wf_amplitude(theta: torch.Tensor, phi: torch.Tensor,
                          m: int = 3) -> torch.Tensor:
    """
    Return the Laughlin wavefunction amplitude as a complex tensor.

    Args:
        theta: [batch, N] or [N]
        phi:   [batch, N] or [N]

    Returns:
        psi: [batch] complex wavefunction values
    """
    if theta.dim() == 1:
        theta = theta.unsqueeze(0)
        phi = phi.unsqueeze(0)

    log_psi = lauglin_jastrow(theta, phi, m)
    return torch.exp(log_psi)


def lauglin_probability(theta: torch.Tensor, phi: torch.Tensor,
                        m: int = 3) -> torch.Tensor:
    """Return |Ψ|² for a batch of configurations."""
    log_psi = lauglin_jastrow(theta, phi, m)
    return torch.exp(2 * log_psi.real)
