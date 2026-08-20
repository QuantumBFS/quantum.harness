"""
Metropolis-Hastings sampler on the Haldane sphere.

Proposes new positions by rotating electrons by small random angles
on the sphere, then accepts/rejects based on |Psi|^2.
"""

import torch
import math
from .haldane_sphere import device, dtype_real, random_sphere_positions


class SphereSampler:
    """
    Metropolis-Hastings Monte Carlo on the sphere.

    Proposes moves by rotating each electron by a random angle
    drawn from a Gaussian distribution in the tangent plane.
    """

    def __init__(self, n_elec, step_size=0.1):
        self.N = n_elec
        self.step_size = step_size
        self.accept_rate = 0.0
        self._n_accept = 0
        self._n_total = 0

    def set_step_size(self, step_size):
        self.step_size = step_size

    def _propose(self, theta, phi):
        """Propose new positions by small rotations in the tangent plane."""
        # Random direction in tangent plane
        # Random rotation axis (perpendicular to current position)
        # Simple approach: perturb theta and phi

        dtheta = self.step_size * torch.randn_like(theta)
        dphi = self.step_size * torch.randn_like(phi) / torch.sin(theta + 1e-10).clamp(min=0.1)

        theta_new = theta + dtheta
        phi_new = phi + dphi

        # Wrap angles
        theta_new = torch.clamp(theta_new, 0, math.pi)
        phi_new = phi_new % (2 * math.pi)

        return theta_new, phi_new

    def _propose_rotation(self, xyz):
        """Propose by small 3D rotation of each electron's position."""
        batch, N, _ = xyz.shape

        # Random rotation axis (uniform on sphere)
        axis = torch.randn(batch, N, 3, device=device, dtype=dtype_real)
        axis = axis / torch.norm(axis, dim=-1, keepdim=True).clamp(min=1e-10)

        # Random rotation angle
        angle = self.step_size * torch.randn(batch, N, 1, device=device, dtype=dtype_real)

        # Rodrigues rotation formula
        cos_a = torch.cos(angle)
        sin_a = torch.sin(angle)

        # Cross product matrix part
        cross = torch.cross(axis, xyz, dim=-1)
        dot = (axis * xyz).sum(dim=-1, keepdim=True)

        xyz_new = (xyz * cos_a + cross * sin_a +
                   axis * dot * (1 - cos_a))
        return xyz_new

    def sample(self, wf, n_samples, n_warmup=1000, n_thin=10,
               theta_init=None, phi_init=None, xyz_init=None):
        """
        Generate samples from |Psi|^2 using Metropolis-Hastings.

        Args:
            wf: wavefunction (callable: theta, phi, xyz -> log_psi)
            n_samples: number of samples to generate
            n_warmup: number of warmup steps
            n_thin: thinning interval
            theta_init, phi_init, xyz_init: initial positions

        Returns:
            theta: [n_samples, N]
            phi:   [n_samples, N]
            xyz:   [n_samples, N, 3]
            log_psi: [n_samples] (complex)
            log_prob: [n_samples] log|Psi|^2
            accept_rate: float
        """
        batch = 1  # Single-chain sampling

        # Initialize
        if xyz_init is not None:
            xyz = xyz_init.clone()
            theta = torch.acos(xyz[..., 2].clamp(-1, 1))
            phi = torch.atan2(xyz[..., 1], xyz[..., 0])
            phi = phi % (2 * math.pi)
        elif theta_init is not None and phi_init is not None:
            theta = theta_init.clone()
            phi = phi_init.clone()
            x = torch.sin(theta) * torch.cos(phi)
            y = torch.sin(theta) * torch.sin(phi)
            z = torch.cos(theta)
            xyz = torch.stack([x, y, z], dim=-1)
        else:
            theta, phi, xyz = random_sphere_positions(1, self.N)

        theta = theta.unsqueeze(0) if theta.dim() == 1 else theta
        phi = phi.unsqueeze(0) if phi.dim() == 1 else phi
        if xyz.dim() == 2:
            xyz = xyz.unsqueeze(0)

        # Warmup
        self._n_accept = 0
        self._n_total = 0

        n_total = n_warmup + n_samples * n_thin

        # Storage for collected samples
        theta_samples = []
        phi_samples = []
        xyz_samples = []
        log_psi_samples = []

        with torch.no_grad():
            for step in range(n_total):
                # Propose
                xyz_new = self._propose_rotation(xyz)

                # Get new theta, phi
                theta_new = torch.acos(xyz_new[..., 2].clamp(-1, 1))
                phi_new = torch.atan2(xyz_new[..., 1], xyz_new[..., 0])
                phi_new = phi_new % (2 * math.pi)

                # Compute |Psi|^2 ratio
                log_psi_old = wf(theta, phi, xyz)
                log_psi_new = wf(theta_new, phi_new, xyz_new)

                log_prob_old = 2 * log_psi_old.real
                log_prob_new = 2 * log_psi_new.real

                # Accept/reject
                log_ratio = log_prob_new - log_prob_old
                accept = torch.exp(log_ratio) > torch.rand(1, device=device, dtype=dtype_real)
                accept = accept.squeeze()

                if accept:
                    xyz = xyz_new
                    theta = theta_new
                    phi = phi_new
                    log_psi = log_psi_new
                    self._n_accept += 1
                else:
                    log_psi = log_psi_old

                self._n_total += 1

                # Collect sample after thinning
                if step >= n_warmup and (step - n_warmup) % n_thin == 0:
                    theta_samples.append(theta.clone())
                    phi_samples.append(phi.clone())
                    xyz_samples.append(xyz.clone())
                    log_psi_samples.append(log_psi.clone())

        self.accept_rate = self._n_accept / max(self._n_total, 1)

        theta_out = torch.cat(theta_samples, dim=0)
        phi_out = torch.cat(phi_samples, dim=0)
        xyz_out = torch.cat(xyz_samples, dim=0)
        log_psi_out = torch.cat(log_psi_samples, dim=0)
        log_prob_out = 2 * log_psi_out.real

        return theta_out, phi_out, xyz_out, log_psi_out, log_prob_out, self.accept_rate
