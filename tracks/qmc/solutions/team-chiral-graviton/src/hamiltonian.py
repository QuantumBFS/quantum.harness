"""
Hamiltonian for electrons on the Haldane sphere.

For the LLL on a sphere:
- Kinetic energy is constant (all LLL states are degenerate)
- Only Coulomb interaction matters for energy differences

H = sum_{i<j} e^2 / (epsilon |r_i - r_j|)

In Haldane units (l_B = 1, e^2/(epsilon l_B) = 1):
H = sum_{i<j} 1 / (sqrt(Q) * d_{ij})

where d_{ij} = 2 sin(theta_{ij}/2) is the chord distance on unit sphere.
"""

import torch
from .haldane_sphere import device, dtype_real, chord_distance_matrix


class Hamiltonian:
    """
    Coulomb Hamiltonian on the Haldane sphere.

    Energy is reported in units of e^2 / (epsilon l_B).
    """

    def __init__(self, sphere):
        self.sphere = sphere
        self.N = sphere.N
        self.Q = sphere.Q
        self.R = sphere.R

    def local_energy(self, xyz, theta, phi, wf, log_psi=None):
        """
        Compute the local energy E_loc = <Psi|H|Psi>/Psi for each configuration.

        In the LLL (no kinetic energy variation):
            E_loc = sum_{i<j} V(r_ij)

        Args:
            xyz:     [batch, N, 3]
            theta:   [batch, N]
            phi:     [batch, N]
            wf:      wavefunction module
            log_psi: [batch] precomputed log-psi (optional)

        Returns:
            E_loc: [batch] local energy per configuration
        """
        chord = chord_distance_matrix(xyz)  # [batch, N, N]

        N = self.N
        triu = torch.triu_indices(N, N, offset=1, device=device)
        chord_pairs = chord[:, triu[0], triu[1]]  # [batch, n_pairs]

        # Coulomb: V_ij = 1/(sqrt(Q) * chord_ij) in units of e^2/(epsilon l_B)
        V_config = (1.0 / (self.R * chord_pairs)).sum(dim=-1)  # [batch]

        return V_config
