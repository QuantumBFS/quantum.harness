"""
Variational Monte Carlo optimization with minSR (minimum Steepest Descent
with Stochastic Reconfiguration).

Implements the SR gradient preconditioner:
    S^{-1} * F
where S is the quantum Fisher matrix and F is the force (energy gradient).
"""

import torch
import math
import numpy as np
from .haldane_sphere import device, dtype_real, dtype_cplx


def compute_log_psi_derivatives(wf, theta, phi, xyz, log_psi=None, chunk_size=256):
    """
    Compute the logarithmic derivatives O_k = d log_psi / d theta_k
    for all variational parameters.

    Args:
        wf: wavefunction
        theta: [batch, N]
        phi:   [batch, N]
        xyz:   [batch, N, 3]
        log_psi: [batch] complex (optional, recomputed if None)
        chunk_size: number of samples per gradient chunk

    Returns:
        O: [n_params, batch] complex logarithmic derivatives
    """
    batch = theta.shape[0]
    params = wf.get_nn_params()

    if log_psi is None:
        log_psi = wf(theta, phi, xyz)

    # Compute gradients in chunks to manage memory
    O_list = []

    for i in range(0, batch, chunk_size):
        end = min(i + chunk_size, batch)
        b_size = end - i

        theta_c = theta[i:end].detach().requires_grad_(True)
        phi_c = phi[i:end].detach().requires_grad_(True)
        xyz_c = xyz[i:end].detach().requires_grad_(True)

        log_psi_c = wf(theta_c, phi_c, xyz_c)  # [b] complex

        grads = torch.autograd.grad(
            log_psi_c.sum(),
            params,
            create_graph=False,
            retain_graph=True,
            allow_unused=True
        )

        # Stack gradients: each [b, *shape] -> flatten -> [b, n_p]
        batch_grads = []
        for g in grads:
            if g is None:
                continue
            batch_grads.append(g.reshape(b_size, -1))

        O_c = torch.cat(batch_grads, dim=-1)  # [b, n_p]
        O_list.append(O_c)

        # Clean up
        del theta_c, phi_c, xyz_c, log_psi_c, grads
        torch.cuda.empty_cache()

    O = torch.cat(O_list, dim=0)  # [batch, n_params]
    return O.t()  # [n_params, batch]


def minSR_step(wf, optimizer, theta, phi, xyz, ham, Eloc=None,
               reg=1e-3, diag_shift=1e-5):
    """
    Perform one minSR (Stochastic Reconfiguration) optimization step.

    SR update: delta_theta = -tau * S^{-1} * F

    where:
      S_{kl} = <O_k^* O_l> - <O_k^*> <O_l>    (Quantum Fisher matrix)
      F_k = <O_k^* E_loc> - <O_k^*> <E_loc>    (Force)

    Args:
        wf: wavefunction
        optimizer: optimizer (for step size)
        theta: [batch, N]
        phi:   [batch, N]
        xyz:   [batch, N, 3]
        ham: Hamiltonian
        Eloc: precomputed local energies [batch] (optional)
        reg: regularization parameter for S^{-1}
        diag_shift: additional diagonal shift

    Returns:
        energy: mean energy after step
        delta_params: parameter update
    """
    batch = theta.shape[0]

    # Forward pass
    log_psi = wf(theta, phi, xyz)

    # Local energy
    if Eloc is None:
        Eloc_full = ham.local_energy(xyz, theta, phi, wf, log_psi)
        Eloc_raw = Eloc_full.detach()
    else:
        Eloc_raw = Eloc.detach()

    # Center energies (subtract mean for numerical stability)
    E_mean = Eloc_raw.mean()
    Eloc_centered = Eloc_raw - E_mean

    # Logarithmic derivatives O_k = d log_psi / d theta_k
    O = compute_log_psi_derivatives(wf, theta, phi, xyz, log_psi)
    # O: [n_params, batch]

    n_params = O.shape[0]

    # Build quantum Fisher matrix S and force F
    # O_mean: [n_params]
    O_mean = O.mean(dim=1)  # <O_k>
    O_centered = O - O_mean.unsqueeze(-1)  # [n_params, batch]

    # S_{kl} = <O_k^* O_l> - <O_k^*> <O_l>
    # = <(O_k - <O_k>)^* (O_l - <O_l>)>

    # For complex parameters, use the real part formulation
    O_r = O_centered.real  # [n_params, batch]
    O_i = O_centered.imag

    # Build real-valued Fisher matrix (2x2 block structure)
    # S_real = Re[<O_k^* O_l> - <O_k^*><O_l>]
    # Using the real representation:
    # We work with [Re(O); Im(O)] as 2n_params real vector

    # For efficiency: use the complex formulation but take real part
    S = (O_centered @ O_centered.conj().t()).real / batch  # [n_params, n_params]

    # Force F_k = <O_k^* E_loc> - <O_k^*> <E_loc>
    F = (O_centered.conj() @ Eloc_centered).real / batch  # [n_params]

    # Regularize S
    S_diag = S.diag().clamp(min=1e-10)
    S_reg = S + reg * S_diag.diag() + diag_shift * torch.eye(n_params, device=device, dtype=dtype_real)

    # Solve S * delta = F
    # Using Cholesky for small systems, otherwise use conjugate gradient
    try:
        L = torch.linalg.cholesky(S_reg)
        delta = torch.cholesky_solve(F.unsqueeze(-1), L).squeeze(-1)
    except RuntimeError:
        # Fallback to pseudo-inverse
        delta = torch.linalg.solve(S_reg, F)

    # Apply update (step size is 1 for SR, but we can scale)
    step_size = optimizer.param_groups[0].get('lr', 0.1)

    # Flatten all parameters
    all_params = []
    shapes = []
    for p in wf.get_nn_params():
        all_params.append(p.data.flatten())
        shapes.append(p.shape)

    params_flat = torch.cat(all_params)  # [n_params]

    # Update: theta -> theta - step_size * delta
    params_new = params_flat - step_size * delta

    # Scatter back
    offset = 0
    for idx, p in enumerate(wf.get_nn_params()):
        n = p.data.numel()
        p.data.copy_(params_new[offset:offset + n].reshape(shapes[idx]))
        offset += n

    return E_mean.item(), delta.norm().item()


class VMCOptimizer:
    """
    Full VMC training loop with optional minSR optimization.
    """

    def __init__(self, wf, ham, sampler, lr=0.1, use_minSR=True,
                 reg=1e-3, diag_shift=1e-5):
        self.wf = wf
        self.ham = ham
        self.sampler = sampler
        self.use_minSR = use_minSR
        self.reg = reg
        self.diag_shift = diag_shift

        # Standard PyTorch optimizer as fallback
        self.optimizer = torch.optim.Adam(wf.get_nn_params(), lr=lr)

        self.energy_history = []
        self.accept_history = []
        self.grad_norm_history = []

    def step(self, n_samples=512, n_warmup=50, n_thin=5):
        """Perform one VMC iteration."""
        # Sample
        theta_s, phi_s, xyz_s, log_psi_s, log_prob_s, accept = \
            self.sampler.sample(
                self.wf, n_samples, n_warmup, n_thin
            )

        self.accept_history.append(accept)

        if self.use_minSR:
            # minSR step
            # Use all samples in a batch (not sequential for minSR)
            theta_s = theta_s.unsqueeze(0) if theta_s.dim() == 1 else theta_s
            phi_s = phi_s.unsqueeze(0) if phi_s.dim() == 1 else phi_s
            xyz_s = xyz_s.unsqueeze(0) if xyz_s.dim() == 3 else xyz_s

            E_mean, grad_norm = minSR_step(
                self.wf, self.optimizer,
                theta_s, phi_s, xyz_s, self.ham,
                reg=self.reg, diag_shift=self.diag_shift
            )
            self.energy_history.append(E_mean)
            self.grad_norm_history.append(grad_norm)
            return E_mean, accept

        else:
            # Standard gradient descent
            theta_s = theta_s.unsqueeze(0) if theta_s.dim() == 1 else theta_s
            phi_s = phi_s.unsqueeze(0) if phi_s.dim() == 1 else phi_s
            xyz_s = xyz_s.unsqueeze(0) if xyz_s.dim() == 3 else xyz_s

            log_psi = self.wf(theta_s, phi_s, xyz_s)
            Eloc = self.ham.local_energy(xyz_s, theta_s, phi_s, self.wf, log_psi)

            E_mean = Eloc.mean()
            loss = E_mean

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.wf.get_nn_params(), 1.0)
            self.optimizer.step()

            E_val = E_mean.item()
            self.energy_history.append(E_val)
            return E_val, accept

    def train(self, n_iterations, n_samples=512, n_warmup=50,
              n_thin=5, verbose=True):
        """Run the full VMC training loop."""
        print(f"{'Iter':>6} {'Energy':>14} {'dE':>14} {'Accept':>8} {'|dθ|':>12}")
        print("-" * 60)

        prev_energy = None

        for it in range(n_iterations):
            energy, accept = self.step(n_samples, n_warmup, n_thin)

            dE = f"{energy - prev_energy:+.4f}" if prev_energy is not None else ""
            gnorm = self.grad_norm_history[-1] if self.grad_norm_history else 0

            if verbose and (it % max(1, n_iterations // 20) == 0 or it == n_iterations - 1):
                print(f"{it:>6} {energy:>14.6f} {dE:>14} {accept:>7.1%} {gnorm:>11.2e}")

            prev_energy = energy

        return self.energy_history
