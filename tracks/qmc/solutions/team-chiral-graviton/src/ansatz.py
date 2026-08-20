"""
SO(3)-equivariant neural network ansatz for FQH states on the sphere.

Full wavefunction:
    Ψ(θ, φ) = Ψ_J(θ, φ) × exp(f_NN({d_ij}))

where:
- Ψ_J is the Laughlin Jastrow (m=3) — handles fermionic antisymmetry
- f_NN is a permutation-invariant, SO(3)-equivariant neural network
  that takes chord distances {d_ij} as features (which are SO(3) invariant)

Architecture:
    chord distances → DeepSet / Equivariant MLP → log|Ψ| + i arg(Ψ)
"""

import torch
import math
import numpy as np
from .haldane_sphere import device, dtype_real, dtype_cplx, chord_distance_matrix


def _init_weights(tensor, scale=0.1):
    """Initialize weights with Xavier-like uniform distribution."""
    with torch.no_grad():
        bound = scale / math.sqrt(tensor.shape[-1])
        tensor.uniform_(-bound, bound)
    return tensor


class EquivariantNN(torch.nn.Module):
    """
    SO(3)-equivariant neural network correction to the Laughlin state.

    Uses chord distances (SO(3)-invariant) as inputs with a permutation-invariant
    architecture (DeepSets-style) to produce a complex-valued wavefunction correction.

    Architecture:
        chord_distances [N, N]
            → per-particle features via neighbor-net
            → permutation-invariant pooling
            → complex MLP head
            → log|Ψ_NN| + i arg(Ψ_NN)  [scalar per config]
    """

    def __init__(self, n_elec: int, hidden_dim: int = 64, n_layers: int = 3,
                 use_minSR: bool = True):
        super().__init__()
        self.N = n_elec
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.use_minSR = use_minSR

        # ── Feature embedding: chord distances → per-pair features ──
        self.pair_net = torch.nn.Sequential(
            torch.nn.Linear(1, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, hidden_dim),
        )

        # ── Per-particle aggregation net ──
        self.particle_net = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
        )

        # ── Global readout: pooled particle features → log ψ ──
        self.readout_re = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, 1),
        )
        self.readout_im = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, 1),
        )

        # ── Log-amplitude scale factor (trainable) ──
        self.log_scale_re = torch.nn.Parameter(torch.zeros(1, device=device, dtype=dtype_real))
        self.log_scale_im = torch.nn.Parameter(torch.zeros(1, device=device, dtype=dtype_real))

        # Geometry is evaluated in float64 throughout the Haldane-sphere code,
        # so keep the network parameters on the same device and dtype.
        self.to(device=device, dtype=dtype_real)
        self._init_all_weights()

    def _init_all_weights(self):
        for layer in self.pair_net:
            if isinstance(layer, torch.nn.Linear):
                _init_weights(layer.weight, 0.1)
                if layer.bias is not None:
                    layer.bias.data.zero_()
        for layer in self.particle_net:
            if isinstance(layer, torch.nn.Linear):
                _init_weights(layer.weight, 0.1)
                if layer.bias is not None:
                    layer.bias.data.zero_()
        for layer in self.readout_re:
            if isinstance(layer, torch.nn.Linear):
                _init_weights(layer.weight, 0.01)
                if layer.bias is not None:
                    layer.bias.data.zero_()
        for layer in self.readout_im:
            if isinstance(layer, torch.nn.Linear):
                _init_weights(layer.weight, 0.01)
                if layer.bias is not None:
                    layer.bias.data.zero_()

    def forward(self, xyz: torch.Tensor) -> tuple:
        """
        Compute log|Ψ| and arg(Ψ) correction.

        Args:
            xyz: [batch, N, 3] electron positions on sphere

        Returns:
            log_ampl_corr: [batch] log|Ψ| correction (real)
            phase_corr:    [batch] arg(Ψ) correction (real, in radians)
        """
        batch, N, _ = xyz.shape

        chord = chord_distance_matrix(xyz)  # [batch, N, N]
        # Remove diagonal and reshape to pairs
        # chord_flat: [batch, N*(N-1)/2]
        triu = torch.triu_indices(N, N, offset=1, device=device)
        chord_pairs = chord[:, triu[0], triu[1]]   # [batch, n_pairs]

        # ── Per-pair embedding ──
        pair_feat = self.pair_net(chord_pairs.unsqueeze(-1))  # [batch, n_pairs, H]

        # ── Aggregate to per-particle features ──
        # Each particle i connects to N-1 neighbors
        # Build per-particle feature by summing over connected pairs
        particle_feat = torch.zeros(batch, N, self.hidden_dim,
                                    device=device, dtype=dtype_real)

        # For each pair (i,j), add to both particle i and particle j
        idx_i = triu[0]  # row indices of upper triangle
        idx_j = triu[1]  # col indices

        # Scatter-add pair features to particles
        particle_feat = particle_feat.index_add(1, idx_i, pair_feat)
        particle_feat = particle_feat.index_add(1, idx_j, pair_feat)
        # Normalize by number of neighbors
        particle_feat = particle_feat / (N - 1)

        # ── Per-particle transform ──
        particle_feat = self.particle_net(particle_feat)  # [batch, N, H]

        # ── Global pooling (sum over particles) ──
        global_feat = particle_feat.sum(dim=1)  # [batch, H]

        # ── Readout ──
        log_ampl_corr = self.readout_re(global_feat).squeeze(-1) * torch.exp(self.log_scale_re)
        phase_corr = self.readout_im(global_feat).squeeze(-1) * torch.exp(self.log_scale_im)

        return log_ampl_corr, phase_corr

    def get_parameters(self) -> torch.Tensor:
        """Return all parameters flat for minSR."""
        params = []
        for p in self.parameters():
            if p.requires_grad:
                params.append(p.data.flatten())
        return torch.cat(params)

    def set_parameters(self, params_flat: torch.Tensor):
        """Set all parameters from flat vector."""
        offset = 0
        for p in self.parameters():
            if p.requires_grad:
                n = p.data.numel()
                p.data.copy_(params_flat[offset:offset + n].reshape(p.shape))
                offset += n


class FullWavefunction(torch.nn.Module):
    """
    Full NQS wavefunction: Ψ = Ψ_J × exp(f_NN)

    Combines the Laughlin Jastrow with the NN correction.
    """

    def __init__(self, n_elec: int, hidden_dim: int = 64, n_layers: int = 3,
                 m_laughlin: int = 3, use_minSR: bool = True):
        super().__init__()
        self.N = n_elec
        self.m = m_laughlin

        self.nn = EquivariantNN(n_elec, hidden_dim, n_layers, use_minSR)

    def forward(self, theta: torch.Tensor, phi: torch.Tensor,
                xyz: torch.Tensor) -> torch.Tensor:
        """
        Compute log Ψ = log Ψ_J + f_NN (complex-valued).

        Args:
            theta: [batch, N]
            phi:   [batch, N]
            xyz:   [batch, N, 3]

        Returns:
            log_psi: [batch] complex log-wavefunction
        """
        from .laughlin_wf import lauglin_jastrow

        # Laughlin part
        log_psi_J = lauglin_jastrow(theta, phi, self.m)  # [batch] complex

        # NN correction
        log_ampl_corr, phase_corr = self.nn(xyz)  # [batch], [batch]

        log_psi = log_psi_J + log_ampl_corr + 1j * phase_corr  # [batch] complex
        return log_psi

    def log_prob(self, theta: torch.Tensor, phi: torch.Tensor,
                 xyz: torch.Tensor) -> torch.Tensor:
        """Return log|Ψ|² = 2 Re(log Ψ)."""
        log_psi = self.forward(theta, phi, xyz)
        return 2 * log_psi.real

    def __call__(self, theta, phi, xyz):
        """Convenience alias to match sampler patterns."""
        return self.forward(theta, phi, xyz)

    def get_nn_params(self):
        """Return all trainable parameters."""
        return list(self.nn.parameters())

    def count_params(self) -> int:
        """Count number of trainable parameters."""
        return sum(p.numel() for p in self.get_nn_params())
