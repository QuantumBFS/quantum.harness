"""Instantaneous eigenbasis current-channel decomposition for the RMH pump.

Diagnoses whether pump failure comes from:
  - A_J drop: current-channel amplitude or matrix-element suppression
  - R_J drop: phase decoherence across channels
  - cos(Φ_J) < 0: net reverse current
  - J_ee < 0: excited-state cancellation of ground-state current

All metrics are gauge-invariant under |n⟩ → e^{iθ_n}|n⟩.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from scipy.sparse import csr_matrix, linalg as spla

from .current import _build_current_operators


# ---------------------------------------------------------------------------
# Diagonalization dispatch
# ---------------------------------------------------------------------------

def _diagonalize_hamiltonian(H_sparse, k: int):
    """Return (eigvals[:k], eigvecs[:, :k]) for the lowest k eigenpairs.

    Uses dense eigh for dim ≤ 5000, sparse eigsh for larger systems.
    """
    dim = H_sparse.shape[0]

    if dim <= 5000:
        H_dense = H_sparse.toarray()
        # Hamiltonian is real-symmetric for this model; use eigh for speed
        if np.allclose(H_dense.imag, 0):
            eigvals, eigvecs = np.linalg.eigh(H_dense.real)
        else:
            eigvals, eigvecs = np.linalg.eigh(H_dense)
        return eigvals[:k], eigvecs[:, :k]

    # Sparse eigsh for larger systems
    k_request = min(k + 10, dim - 2)
    try:
        eigvals, eigvecs = spla.eigsh(
            H_sparse, k=k_request, which="SA",
            maxiter=20000, tol=1e-6, return_eigenvectors=True,
        )
    except spla.ArpackNoConvergence:
        # Fall back with more iterations
        try:
            eigvals, eigvecs = spla.eigsh(
                H_sparse, k=k_request, which="SA",
                maxiter=50000, tol=1e-4, return_eigenvectors=True,
            )
        except spla.ArpackNoConvergence as e:
            # Extract whatever converged
            eigvals = e.eigenvalues
            eigvecs = e.eigenvectors
            if eigvals.size < k:
                raise RuntimeError(
                    f"eigsh: only {eigvals.size}/{k} eigenvalues converged"
                ) from e

    idx = np.argsort(eigvals.real)
    return eigvals[idx[:k]].real, eigvecs[:, idx[:k]]


# ---------------------------------------------------------------------------
# Total current operator
# ---------------------------------------------------------------------------

def _build_total_current_operator(model, delta: float):
    """Build sparse total current Ĵ(t) = (1/L) Σ_j (J0_j + δ(t)·J1_j).

    Returns CSR matrix of shape (dim, dim).
    """
    L = model.L
    J0_ops, J1_ops = _build_current_operators(model)
    dim = model.dim

    J_total = csr_matrix((dim, dim), dtype=np.complex128)
    for j in range(L):
        J_total = J_total + J0_ops[j]._static + delta * J1_ops[j]._static
    return J_total / L


# ---------------------------------------------------------------------------
# J_mn matrix computation
# ---------------------------------------------------------------------------

def _compute_J_matrix(eigvecs: np.ndarray, J_total) -> np.ndarray:
    """Compute J_{mn} = ⟨m|Ĵ|n⟩ for all m,n < N_eig.

    For dense: J_mat = V^H @ J_total @ V (one matrix product).
    For sparse: sparse matvec per column, then dot products.
    """
    N_eig = eigvecs.shape[1]
    dim = eigvecs.shape[0]

    if dim <= 5000:
        J_dense = J_total.toarray()
        JV = J_dense @ eigvecs  # (dim, N_eig)
        J_mat = eigvecs.conj().T @ JV  # (N_eig, N_eig)
    else:
        J_mat = np.empty((N_eig, N_eig), dtype=np.complex128)
        for n in range(N_eig):
            Jv = J_total @ eigvecs[:, n]  # sparse matvec
            for m in range(N_eig):
                J_mat[m, n] = np.dot(eigvecs[:, m].conj(), Jv)

    return J_mat


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CoherenceResult:
    """Current-channel decomposition and coherence metrics at each save point."""

    tau: np.ndarray                 # (n_save,)
    tau_over_T: np.ndarray          # (n_save,)
    N_eig: int
    capture_weight: np.ndarray      # (n_save,)  W_cap(t)
    weights: np.ndarray             # (n_save, N_eig)  |c_n(t)|²
    energies: list[np.ndarray]      # list of (N_eig,) eigenvalue arrays per save point
    J_direct: np.ndarray            # (n_save,)  ⟨ψ|Ĵ|ψ⟩
    J_diag: np.ndarray              # (n_save,)  Σ|c_n|² J_nn
    J_off: np.ndarray               # (n_save,)  2Re Σ_{m<n} z_mn
    J_0e: np.ndarray                # (n_save,)  2Re Σ_{n>0} c_0* c_n J_{0n}
    J_ee: np.ndarray                # (n_save,)  2Re Σ_{1≤m<n} c_m* c_n J_mn
    A_J: np.ndarray                 # (n_save,)  2 Σ|z_mn|
    R_J: np.ndarray                 # (n_save,)  |Σ z_mn| / Σ|z_mn|
    Phi_J: np.ndarray               # (n_save,)  arg(Σ z_mn)
    Z_J_real: np.ndarray            # (n_save,)  Re(Σ z_mn)
    Z_J_imag: np.ndarray            # (n_save,)  Im(Σ z_mn)
    reconstruction_error: np.ndarray  # (n_save,)  |J_direct - J_diag - J_off|
    convergence: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main computation: eigenbasis + coherence at each time point
# ---------------------------------------------------------------------------

def compute_coherence(
    model,
    times: np.ndarray,
    states: list[np.ndarray],
    delta_of_tau,
    Delta_of_tau,
    N_eig: int = 20,
    verbose: bool = True,
) -> CoherenceResult:
    """Compute eigenbasis decomposition and current-channel coherence metrics.

    Parameters
    ----------
    model : SplitRMHModel
    times : np.ndarray, shape (n_save,)
    states : list of np.ndarray
        State vectors |ψ(τ)⟩ at each save point.
    delta_of_tau, Delta_of_tau : callable
        Pump path functions.
    N_eig : int
        Number of instantaneous eigenstates to keep.
    verbose : bool
        Print progress.

    Returns
    -------
    CoherenceResult
    """
    n_save = len(states)
    T = times[-1]
    dim = model.dim

    # Pre-allocate output arrays
    capture_weight = np.empty(n_save)
    J_direct_arr = np.empty(n_save)
    J_diag_arr = np.empty(n_save)
    J_off_arr = np.empty(n_save)
    J_0e_arr = np.empty(n_save)
    J_ee_arr = np.empty(n_save)
    A_J_arr = np.empty(n_save)
    R_J_arr = np.empty(n_save)
    Phi_J_arr = np.empty(n_save)
    Z_real_arr = np.empty(n_save)
    Z_imag_arr = np.empty(n_save)
    recon_err = np.empty(n_save)

    # Adjust N_eig for small dims
    N_eig_actual = min(N_eig, dim - 1)
    weights = np.empty((n_save, N_eig_actual))
    energies: list[np.ndarray] = []

    # Pre-build current operator basis (J0, J1) — same for all times
    J0_ops, J1_ops = _build_current_operators(model)

    t0 = time.perf_counter()
    n_failed = 0

    for t_idx in range(n_save):
        tau = times[t_idx]
        psi = np.asarray(states[t_idx], dtype=np.complex128).ravel()

        delta = delta_of_tau(tau)
        Delta = Delta_of_tau(tau)
        H = model.hamiltonian_at(delta, Delta)

        # --- Diagonalize ---
        try:
            eigvals, eigvecs = _diagonalize_hamiltonian(H, N_eig_actual)
        except Exception:
            n_failed += 1
            # Fill with NaN and continue
            capture_weight[t_idx] = np.nan
            J_direct_arr[t_idx] = np.nan
            J_diag_arr[t_idx] = np.nan
            J_off_arr[t_idx] = np.nan
            J_0e_arr[t_idx] = np.nan
            J_ee_arr[t_idx] = np.nan
            A_J_arr[t_idx] = np.nan
            R_J_arr[t_idx] = np.nan
            Phi_J_arr[t_idx] = np.nan
            Z_real_arr[t_idx] = np.nan
            Z_imag_arr[t_idx] = np.nan
            recon_err[t_idx] = np.nan
            weights[t_idx, :] = np.nan
            energies.append(np.full(N_eig_actual, np.nan))
            continue

        Ne = len(eigvals)
        energies.append(eigvals)

        # --- Project state onto eigenbasis ---
        # eigvecs[:, n] is the n-th eigenvector
        c_n = eigvecs.conj().T @ psi  # shape (Ne,)
        w = np.abs(c_n) ** 2
        weights[t_idx, :Ne] = w
        capture_weight[t_idx] = np.sum(w)

        # --- Build total current operator ---
        J_total = csr_matrix((dim, dim), dtype=np.complex128)
        for j in range(model.L):
            J_total = J_total + J0_ops[j]._static + delta * J1_ops[j]._static
        J_total = J_total / model.L

        # --- Direct current expectation ---
        J_direct_arr[t_idx] = float(np.dot(psi.conj(), J_total @ psi).real)

        # --- J_{mn} matrix in eigenbasis ---
        J_mat = _compute_J_matrix(eigvecs[:, :Ne], J_total)

        # --- Current channel decomposition ---
        # Diagonal contribution
        J_diag_arr[t_idx] = float(np.sum(w * J_mat[:Ne, :Ne].diagonal()).real)

        # Off-diagonal contributions: z_{mn} = c_m* c_n J_{mn}
        z_sum = 0.0j
        z_abs_sum = 0.0
        j_0e_sum = 0.0j
        j_ee_sum = 0.0j

        for m in range(Ne):
            for n in range(m + 1, Ne):
                z = np.conj(c_n[m]) * c_n[n] * J_mat[m, n]
                z_sum += z
                z_abs_sum += abs(z)
                if m == 0:
                    j_0e_sum += z
                else:
                    j_ee_sum += z

        J_off_arr[t_idx] = float(2.0 * z_sum.real)
        J_0e_arr[t_idx] = float(2.0 * j_0e_sum.real)
        J_ee_arr[t_idx] = float(2.0 * j_ee_sum.real)
        A_J_arr[t_idx] = 2.0 * z_abs_sum
        R_J_arr[t_idx] = abs(z_sum) / z_abs_sum if z_abs_sum > 0 else 0.0
        Phi_J_arr[t_idx] = float(np.angle(z_sum))
        Z_real_arr[t_idx] = float(z_sum.real)
        Z_imag_arr[t_idx] = float(z_sum.imag)

        # --- Reconstruction error ---
        recon_err[t_idx] = abs(
            J_direct_arr[t_idx] - J_diag_arr[t_idx] - J_off_arr[t_idx]
        )

        if verbose and (t_idx % 100 == 0 or t_idx == n_save - 1):
            print(
                f"  t={t_idx:4d}/{n_save}  tau/T={tau/T:.3f}  "
                f"W_cap={capture_weight[t_idx]:.6f}  "
                f"J_direct={J_direct_arr[t_idx]:.4f}  "
                f"A_J={A_J_arr[t_idx]:.4f}  R_J={R_J_arr[t_idx]:.4f}  "
                f"recon_err={recon_err[t_idx]:.2e}"
            )

    elapsed = time.perf_counter() - t0
    max_W_cap = np.nanmax(capture_weight)
    min_W_cap = np.nanmin(capture_weight)
    max_recon = np.nanmax(recon_err)

    if verbose:
        print(f"  Diagonalization + coherence: {elapsed:.1f}s")
        print(f"  W_cap ∈ [{min_W_cap:.6f}, {max_W_cap:.6f}]")
        print(f"  max reconstruction error = {max_recon:.2e}")
        if n_failed > 0:
            print(f"  WARNING: {n_failed}/{n_save} diagonalizations failed")

    return CoherenceResult(
        tau=times,
        tau_over_T=times / T,
        N_eig=N_eig_actual,
        capture_weight=capture_weight,
        weights=weights,
        energies=energies,
        J_direct=J_direct_arr,
        J_diag=J_diag_arr,
        J_off=J_off_arr,
        J_0e=J_0e_arr,
        J_ee=J_ee_arr,
        A_J=A_J_arr,
        R_J=R_J_arr,
        Phi_J=Phi_J_arr,
        Z_J_real=Z_real_arr,
        Z_J_imag=Z_imag_arr,
        reconstruction_error=recon_err,
        convergence={
            "min_W_cap": float(min_W_cap),
            "max_W_cap": float(max_W_cap),
            "max_reconstruction_error": float(max_recon),
            "n_failed_diag": n_failed,
            "wall_time_s": elapsed,
        },
    )


# ---------------------------------------------------------------------------
# Gauge invariance check
# ---------------------------------------------------------------------------

def check_gauge_invariance(
    model,
    times: np.ndarray,
    states: list[np.ndarray],
    delta_of_tau,
    Delta_of_tau,
    N_eig: int = 20,
    n_check: int = 3,
    seed: int = 42,
) -> dict:
    """Verify coherence metrics are invariant under eigenvector phase rotations.

    At n_check randomly-selected time points, applies a random unitary diagonal
    gauge transform U_{mn} = δ_{mn} exp(i θ_n) to the eigenvectors and verifies
    all output metrics are unchanged to within machine precision.
    """
    rng = np.random.RandomState(seed)
    indices = sorted(rng.choice(len(states), size=min(n_check, len(states)),
                                replace=False))

    results = {}
    for idx in indices:
        tau = times[idx]
        psi = np.asarray(states[idx], dtype=np.complex128).ravel()
        delta = delta_of_tau(tau)
        Delta = Delta_of_tau(tau)
        H = model.hamiltonian_at(delta, Delta)

        eigvals, eigvecs = _diagonalize_hamiltonian(H, min(N_eig, H.shape[0] - 1))
        Ne = len(eigvals)

        # Reference result (no gauge transform)
        ref = _compute_single_point(eigvecs, psi, model, delta, Ne)

        # Apply random phases
        phases = rng.uniform(0, 2 * np.pi, size=Ne)
        gauge = np.diag(np.exp(1j * phases))
        eigvecs_g = eigvecs @ gauge  # each column gets a phase

        # Gauged result
        gd = _compute_single_point(eigvecs_g, psi, model, delta, Ne)

        # Compare
        diffs = {}
        for key in ["J_diag", "J_off", "J_0e", "J_ee", "A_J", "R_J"]:
            diffs[key] = abs(ref[key] - gd[key])
        # Phi_J can differ by multiples of 2π; check cos/sin
        diffs["cos_Phi"] = abs(np.cos(ref["Phi_J"]) - np.cos(gd["Phi_J"]))
        diffs["sin_Phi"] = abs(np.sin(ref["Phi_J"]) - np.sin(gd["Phi_J"]))
        results[idx] = diffs

    # Report max differences
    max_diffs = {}
    for key in ["J_diag", "J_off", "J_0e", "J_ee", "A_J", "R_J", "cos_Phi", "sin_Phi"]:
        max_diffs[key] = max(results[i][key] for i in indices)

    return {"per_point": results, "max_diffs": max_diffs}


def _compute_single_point(eigvecs, psi, model, delta, N_eig) -> dict:
    """Compute coherence metrics for a single time point (internal helper)."""
    L = model.L
    dim = model.dim
    J0_ops, J1_ops = _build_current_operators(model)

    c_n = eigvecs.conj().T @ psi
    w = np.abs(c_n) ** 2

    J_total = csr_matrix((dim, dim), dtype=np.complex128)
    for j in range(L):
        J_total = J_total + J0_ops[j]._static + delta * J1_ops[j]._static
    J_total = J_total / L

    J_direct = float(np.dot(psi.conj(), J_total @ psi).real)
    J_mat = _compute_J_matrix(eigvecs, J_total)

    J_diag = float(np.sum(w * J_mat.diagonal()).real)

    z_sum = 0.0j
    z_abs_sum = 0.0
    j_0e_sum = 0.0j
    j_ee_sum = 0.0j

    for m in range(N_eig):
        for n in range(m + 1, N_eig):
            z = np.conj(c_n[m]) * c_n[n] * J_mat[m, n]
            z_sum += z
            z_abs_sum += abs(z)
            if m == 0:
                j_0e_sum += z
            else:
                j_ee_sum += z

    return {
        "J_direct": J_direct,
        "J_diag": J_diag,
        "J_off": float(2.0 * z_sum.real),
        "J_0e": float(2.0 * j_0e_sum.real),
        "J_ee": float(2.0 * j_ee_sum.real),
        "A_J": 2.0 * z_abs_sum,
        "R_J": abs(z_sum) / z_abs_sum if z_abs_sum > 0 else 0.0,
        "Phi_J": float(np.angle(z_sum)),
        "recon_err": abs(J_direct - J_diag - float(2.0 * z_sum.real)),
    }


# ---------------------------------------------------------------------------
# Hold-time evolution
# ---------------------------------------------------------------------------

@dataclass
class HoldTimeResult:
    """Results of hold-time interferometry scan."""

    t_star: float                    # hold position τ
    t_star_over_T: float
    tau_h: np.ndarray                # (n_hold,) hold durations
    Q_post: np.ndarray               # (n_hold,) pumped charge after restart
    A_J_hold: np.ndarray             # (n_hold,) A_J at hold point
    R_J_hold: np.ndarray             # (n_hold,) R_J at hold point
    Phi_J_hold: np.ndarray           # (n_hold,) Φ_J at hold point
    cos_Phi_hold: np.ndarray         # (n_hold,) cos(Φ_J) at hold point
    weights_hold: np.ndarray         # (n_hold, N_eig) |c_n|² (should be constant)


def run_hold_time_scan(
    model,
    psi0: np.ndarray,
    T: float,
    dt: float,
    delta_of_tau,
    Delta_of_tau,
    t_star: float,
    tau_h_values: np.ndarray,
    N_eig: int = 20,
    save_interval: float = 0.2,
    verbose: bool = True,
) -> HoldTimeResult:
    """Scan hold time τ_h at a fixed hold position t_star.

    Flow:
    1. Evolve from 0 to t_star (normal pump)
    2. Diagonalize H(t_star) → {E_n, |n⟩}
    3. For each τ_h:
       a. |ψ(τ_h)⟩ = Σ_n c_n e^{-iE_n τ_h} |n⟩  (analytical, exact)
       b. Continue pump from t_star to T (numerical)
       c. Compute Q_post = charge pumped from t_star+τ_h to T+τ_h

    Parameters
    ----------
    t_star : float
        Hold position in τ.
    tau_h_values : np.ndarray
        Hold durations to scan.

    Returns
    -------
    HoldTimeResult
    """
    from .evolution import evolve_midpoint_krylov

    dim = model.dim
    n_hold = len(tau_h_values)

    if verbose:
        print(f"\n  Hold-time scan: t_star = {t_star:.1f} (τ/T = {t_star/T:.3f})")
        print(f"  Scanning {n_hold} τ_h values in [{tau_h_values[0]:.1f}, {tau_h_values[-1]:.1f}]")

    # --- Step 1: Evolve to t_star ---
    n_steps_to_star = int(round(t_star / dt))
    psi = np.asarray(psi0, dtype=np.complex128).copy()
    for m in range(1, n_steps_to_star + 1):
        tau_mid = (m - 0.5) * dt
        H_mid = model.hamiltonian_at(delta_of_tau(tau_mid), Delta_of_tau(tau_mid))
        psi = spla.expm_multiply(-1j * dt * H_mid, psi, traceA=0.0)
        psi /= np.linalg.norm(psi)

    psi_star = psi.copy()

    # --- Step 2: Diagonalize H(t_star) ---
    delta_s = delta_of_tau(t_star)
    Delta_s = Delta_of_tau(t_star)
    H_star = model.hamiltonian_at(delta_s, Delta_s)
    eigvals, eigvecs = _diagonalize_hamiltonian(H_star, min(N_eig, dim - 1))
    Ne = len(eigvals)

    # Project state at t_star onto eigenbasis
    c_n_0 = eigvecs.conj().T @ psi_star  # shape (Ne,)
    weights_0 = np.abs(c_n_0) ** 2

    # Build current operator at t_star for coherence metrics
    J_total_star = csr_matrix((dim, dim), dtype=np.complex128)
    J0_ops, J1_ops = _build_current_operators(model)
    for j in range(model.L):
        J_total_star = J_total_star + J0_ops[j]._static + delta_s * J1_ops[j]._static
    J_total_star = J_total_star / model.L

    # Compute J_direct at hold point
    J_direct_star = float(np.dot(psi_star.conj(), J_total_star @ psi_star).real)
    J_mat_star = _compute_J_matrix(eigvecs[:, :Ne], J_total_star)

    # --- Step 3: Compute number of steps from t_star to T ---
    n_steps_after = int(round((T - t_star) / dt))

    # Pre-allocate
    Q_post = np.empty(n_hold)
    A_J_arr = np.empty(n_hold)
    R_J_arr = np.empty(n_hold)
    Phi_J_arr = np.empty(n_hold)
    cos_Phi_arr = np.empty(n_hold)
    weights_arr = np.empty((n_hold, Ne))

    t0 = time.perf_counter()

    for ih, tau_h in enumerate(tau_h_values):
        # --- Step 3a: Analytical free evolution during hold ---
        # |ψ(τ_h)⟩ = Σ_n c_n(0) e^{-iE_n τ_h} |n⟩
        c_n_h = c_n_0 * np.exp(-1j * eigvals * tau_h)
        psi_hold = eigvecs[:, :Ne] @ c_n_h  # reconstruct state

        # Compute coherence metrics at hold point
        w_h = np.abs(c_n_h) ** 2
        weights_arr[ih, :Ne] = w_h

        z_sum = 0.0j
        z_abs_sum = 0.0
        for m in range(Ne):
            for n in range(m + 1, Ne):
                z = np.conj(c_n_h[m]) * c_n_h[n] * J_mat_star[m, n]
                z_sum += z
                z_abs_sum += abs(z)
        A_J_arr[ih] = 2.0 * z_abs_sum
        R_J_arr[ih] = abs(z_sum) / z_abs_sum if z_abs_sum > 0 else 0.0
        Phi_J_arr[ih] = float(np.angle(z_sum))
        cos_Phi_arr[ih] = float(np.cos(np.angle(z_sum)))

        # --- Step 3b: Continue pump from t_star to T ---
        # The pump clock is paused during hold:
        #   For τ ∈ [0, t_star]: δ(τ), Δ(τ) as usual
        #   For τ ∈ [t_star, t_star+τ_h]: frozen at H(t_star) (already done analytically)
        #   For τ > t_star+τ_h: δ(τ-τ_h), Δ(τ-τ_h)
        psi_cont = psi_hold.copy()
        Q_after = 0.0

        for m in range(1, n_steps_after + 1):
            tau_phys = t_star + m * dt  # physical time (shifted by τ_h for pump params)
            tau_pump = tau_phys - tau_h  # pump parameter clock (paused during hold)
            tau_mid = tau_pump - 0.5 * dt

            H_mid = model.hamiltonian_at(delta_of_tau(tau_mid), Delta_of_tau(tau_mid))
            psi_cont = spla.expm_multiply(-1j * dt * H_mid, psi_cont, traceA=0.0)
            psi_cont /= np.linalg.norm(psi_cont)

            # Accumulate current (trapezoidal)
            J_inst = float(np.dot(psi_cont.conj(), J_total_star @ psi_cont).real)
            # Actually we need J(tau_pump) not J(t_star). Let's use the correct operator.
            # This is computed below after the loop. We'll compute Q_post differently.

        # --- Step 3c: Compute Q_post ---
        # For efficiency, compute Q_post as the difference between final and initial
        # pumped charge. Use a simplified approach: compute ⟨n_j⟩ at the end and
        # compare with ⟨n_j⟩ at t_star.
        #
        # Actually, the simplest correct approach: Q_post = ∫_{t_star}^{T} J(τ') dτ'
        # where J is measured during the continuation evolution.
        # We need to save the current at each step of the continuation to integrate.
        #
        # For now: use the cumulative transport computed via density change.
        # The charge pumped is (1/L) Σ_j j · Δ⟨n_j⟩ integrated over the path.
        # But the simplest approach is to compute current at each step and integrate.

        # Re-do continuation with current measurement
        psi_cont = psi_hold.copy()
        Q_after = 0.0
        for m in range(1, n_steps_after + 1):
            tau_pump = t_star + m * dt - tau_h
            tau_mid = tau_pump - 0.5 * dt

            H_mid = model.hamiltonian_at(delta_of_tau(tau_mid), Delta_of_tau(tau_mid))
            psi_cont = spla.expm_multiply(-1j * dt * H_mid, psi_cont, traceA=0.0)
            psi_cont /= np.linalg.norm(psi_cont)

            # Build current operator at this pump position
            delta_m = delta_of_tau(tau_pump)
            J_t = csr_matrix((dim, dim), dtype=np.complex128)
            for j in range(model.L):
                J_t = J_t + J0_ops[j]._static + delta_m * J1_ops[j]._static
            J_t = J_t / model.L
            J_m = float(np.dot(psi_cont.conj(), J_t @ psi_cont).real)
            Q_after += J_m * dt

        Q_post[ih] = Q_after

        if verbose and (ih % 20 == 0 or ih == n_hold - 1):
            print(f"    τ_h={tau_h:6.1f}  Q_post={Q_post[ih]:.6f}  "
                  f"R_J={R_J_arr[ih]:.4f}  cosΦ={cos_Phi_arr[ih]:.4f}")

    elapsed = time.perf_counter() - t0
    if verbose:
        print(f"  Hold-time scan complete: {elapsed:.1f}s")

    return HoldTimeResult(
        t_star=t_star,
        t_star_over_T=t_star / T,
        tau_h=tau_h_values,
        Q_post=Q_post,
        A_J_hold=A_J_arr,
        R_J_hold=R_J_arr,
        Phi_J_hold=Phi_J_arr,
        cos_Phi_hold=cos_Phi_arr,
        weights_hold=weights_arr,
    )


# ---------------------------------------------------------------------------
# Full coherence pipeline (evolution + measurement in one pass)
# ---------------------------------------------------------------------------

def run_coherence_pipeline(
    model,
    psi0: np.ndarray,
    T: float,
    dt: float,
    delta_of_tau,
    Delta_of_tau,
    N_eig: int = 20,
    save_interval: float = 0.2,
    measure_currents_fn=None,
    verbose: bool = True,
):
    """Run full pump evolution with inline coherence measurement.

    Combines evolution and coherence computation to avoid storing all state
    vectors in memory (important for L=10 with dim=63504).

    Returns (EvolutionResult, CurrentResult, CoherenceResult).
    """
    from .evolution import EvolutionResult

    t0 = time.perf_counter()
    n_steps = int(round(T / dt))
    dim = model.dim

    # Pre-build current operator components
    J0_ops, J1_ops = _build_current_operators(model)

    psi = np.asarray(psi0, dtype=np.complex128).copy()

    # Save points
    save_times = np.arange(0, T + 1e-12, save_interval)
    if save_times[-1] < T - 1e-12:
        save_times = np.append(save_times, T)
    save_indices = {int(round(t / dt)) for t in save_times}
    save_indices.add(0)

    n_save = len(save_times)
    N_eig_actual = min(N_eig, dim - 1)

    # Pre-allocate coherence arrays
    capture_weight = np.empty(n_save)
    J_direct_arr = np.empty(n_save)
    J_diag_arr = np.empty(n_save)
    J_off_arr = np.empty(n_save)
    J_0e_arr = np.empty(n_save)
    J_ee_arr = np.empty(n_save)
    A_J_arr = np.empty(n_save)
    R_J_arr = np.empty(n_save)
    Phi_J_arr = np.empty(n_save)
    Z_real_arr = np.empty(n_save)
    Z_imag_arr = np.empty(n_save)
    recon_err = np.empty(n_save)
    weights = np.empty((n_save, N_eig_actual))
    energies: list[np.ndarray] = []

    # Current measurement arrays
    current_mean = np.empty(n_save)
    bond_current = np.empty((n_save, model.L))

    # Save index counter
    save_idx = 0

    # --- Initial save point (τ=0) ---
    save_idx = _process_save_point(
        model, psi, 0.0, delta_of_tau, Delta_of_tau, J0_ops, J1_ops,
        N_eig_actual, capture_weight, J_direct_arr, J_diag_arr,
        J_off_arr, J_0e_arr, J_ee_arr, A_J_arr, R_J_arr, Phi_J_arr,
        Z_real_arr, Z_imag_arr, recon_err, weights, energies,
        current_mean, bond_current, save_idx,
    )
    if verbose:
        print(f"  t=0/{n_save}  W_cap={capture_weight[0]:.6f}")

    # --- Time evolution loop ---
    norm_errors: list[float] = []
    for m in range(1, n_steps + 1):
        tau_mid = (m - 0.5) * dt
        H_mid = model.hamiltonian_at(delta_of_tau(tau_mid), Delta_of_tau(tau_mid))
        psi = spla.expm_multiply(-1j * dt * H_mid, psi, traceA=0.0)

        nrm = float(np.linalg.norm(psi))
        norm_errors.append(abs(nrm - 1.0))
        psi /= nrm

        if m in save_indices:
            tau = m * dt
            save_idx = _process_save_point(
                model, psi, tau, delta_of_tau, Delta_of_tau, J0_ops, J1_ops,
                N_eig_actual, capture_weight, J_direct_arr, J_diag_arr,
                J_off_arr, J_0e_arr, J_ee_arr, A_J_arr, R_J_arr, Phi_J_arr,
                Z_real_arr, Z_imag_arr, recon_err, weights, energies,
                current_mean, bond_current, save_idx,
            )
            if verbose and (save_idx % 100 == 0 or save_idx == n_save):
                print(
                    f"  t={save_idx:4d}/{n_save}  tau/T={tau/T:.3f}  "
                    f"W_cap={capture_weight[save_idx-1]:.6f}  "
                    f"A_J={A_J_arr[save_idx-1]:.4f}  "
                    f"R_J={R_J_arr[save_idx-1]:.4f}"
                )

    elapsed = time.perf_counter() - t0

    # Build EvolutionResult
    # We don't store all states in this pipeline mode,
    # but we can reconstruct from save files if needed
    ev_result = EvolutionResult(
        times=save_times,
        states=[],  # not stored
        norm_errors=norm_errors,
        wall_time_s=elapsed,
        n_steps=n_steps,
    )

    # Build CoherenceResult
    max_recon = float(np.nanmax(recon_err))
    min_W = float(np.nanmin(capture_weight))

    coh_result = CoherenceResult(
        tau=save_times,
        tau_over_T=save_times / T,
        N_eig=N_eig_actual,
        capture_weight=capture_weight,
        weights=weights,
        energies=energies,
        J_direct=J_direct_arr,
        J_diag=J_diag_arr,
        J_off=J_off_arr,
        J_0e=J_0e_arr,
        J_ee=J_ee_arr,
        A_J=A_J_arr,
        R_J=R_J_arr,
        Phi_J=Phi_J_arr,
        Z_J_real=Z_real_arr,
        Z_J_imag=Z_imag_arr,
        reconstruction_error=recon_err,
        convergence={
            "min_W_cap": float(min_W),
            "max_W_cap": float(np.nanmax(capture_weight)),
            "max_reconstruction_error": float(max_recon),
            "n_failed_diag": 0,
            "wall_time_s": elapsed,
        },
    )

    if verbose:
        print(f"  Pipeline complete: {elapsed:.1f}s")
        print(f"  W_cap ∈ [{min_W:.6f}, {np.nanmax(capture_weight):.6f}]")
        print(f"  max reconstruction error = {max_recon:.2e}")

    return ev_result, coh_result


def _process_save_point(
    model, psi, tau, delta_of_tau, Delta_of_tau, J0_ops, J1_ops,
    N_eig, capture_weight, J_direct_arr, J_diag_arr,
    J_off_arr, J_0e_arr, J_ee_arr, A_J_arr, R_J_arr, Phi_J_arr,
    Z_real_arr, Z_imag_arr, recon_err, weights, energies,
    current_mean, bond_current, save_idx,
) -> int:
    """Process one save point: diagonalize, project, compute metrics."""
    dim = model.dim
    L = model.L
    delta = delta_of_tau(tau)
    Delta = Delta_of_tau(tau)
    H = model.hamiltonian_at(delta, Delta)

    # Diagonalize
    eigvals, eigvecs = _diagonalize_hamiltonian(H, N_eig)
    Ne = len(eigvals)
    energies.append(eigvals)

    # Project
    c_n = eigvecs.conj().T @ psi
    w = np.abs(c_n) ** 2
    weights[save_idx, :Ne] = w
    capture_weight[save_idx] = float(np.sum(w))

    # Total current operator
    J_total = csr_matrix((dim, dim), dtype=np.complex128)
    for j in range(L):
        J_total = J_total + J0_ops[j]._static + delta * J1_ops[j]._static
    J_total = J_total / L

    # Direct current
    J_direct_arr[save_idx] = float(np.dot(psi.conj(), J_total @ psi).real)

    # Bond currents (for diagnostics)
    for j in range(L):
        J_j = J0_ops[j]._static + delta * J1_ops[j]._static
        bond_current[save_idx, j] = float(np.dot(psi.conj(), J_j @ psi).real)
    current_mean[save_idx] = float(np.mean(bond_current[save_idx, :]))

    # J_mn matrix
    J_mat = _compute_J_matrix(eigvecs[:, :Ne], J_total)

    # Decompose
    J_diag_arr[save_idx] = float(np.sum(w * J_mat.diagonal().real))

    z_sum = 0.0j
    z_abs_sum = 0.0
    j_0e_sum = 0.0j
    j_ee_sum = 0.0j

    for m in range(Ne):
        for n in range(m + 1, Ne):
            z = np.conj(c_n[m]) * c_n[n] * J_mat[m, n]
            z_sum += z
            z_abs_sum += abs(z)
            if m == 0:
                j_0e_sum += z
            else:
                j_ee_sum += z

    J_off_arr[save_idx] = float(2.0 * z_sum.real)
    J_0e_arr[save_idx] = float(2.0 * j_0e_sum.real)
    J_ee_arr[save_idx] = float(2.0 * j_ee_sum.real)
    A_J_arr[save_idx] = 2.0 * z_abs_sum
    R_J_arr[save_idx] = abs(z_sum) / z_abs_sum if z_abs_sum > 0 else 0.0
    Phi_J_arr[save_idx] = float(np.angle(z_sum))
    Z_real_arr[save_idx] = float(z_sum.real)
    Z_imag_arr[save_idx] = float(z_sum.imag)
    recon_err[save_idx] = abs(
        J_direct_arr[save_idx] - J_diag_arr[save_idx] - J_off_arr[save_idx]
    )

    return save_idx + 1
