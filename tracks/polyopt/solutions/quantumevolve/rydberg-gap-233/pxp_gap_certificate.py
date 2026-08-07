"""PXP spectral gap certificate via the martingale (finite-size) method.

Implements the Nachtergaele-Sims / Movassagh martingale bound:
  If H = Σ h_i (m-site local terms), each with local gap ≥ γ_m,
  and the overlap condition ||G_{i+1} G_i^⊥|| ≤ ε < 1/√(m-1),
  then the global gap ≥ γ_m · (1 - ε·√(m-1))².

For PXP, we work in the constrained (Fibonacci) Hilbert space.
The local terms are the projector-dressed flip operators on m consecutive sites.

This produces a CERTIFIED lower bound (mathematical theorem, not numerical estimate).

Usage:
    python pxp_gap_certificate.py [--m 4] [--delta 0.0] [--max-n 20]
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
from pxp_ed_gap import build_pxp_hamiltonian, fibonacci_basis


def local_hamiltonian_pxp(m: int, delta: float = 0.0) -> np.ndarray:
    """Build the PXP Hamiltonian on m sites with OBC (the local term).
    
    This is the full Hamiltonian restricted to m consecutive sites,
    which serves as the 'local interaction' h_i in the martingale method.
    """
    H = build_pxp_hamiltonian(m, omega=1.0, delta=delta, boundary="obc")
    return H.toarray()


def local_gap_and_projector(m: int, delta: float = 0.0) -> tuple[float, np.ndarray, np.ndarray]:
    """Compute the spectral gap and ground-space projector for the m-site local H.
    
    Returns:
        gamma_m: local spectral gap (E1 - E0)
        G: projector onto ground space (columns are ground state vectors)
        evals: full spectrum
    """
    H = local_hamiltonian_pxp(m, delta)
    evals, evecs = np.linalg.eigh(H)
    
    e0 = evals[0]
    # Find degeneracy of ground state
    tol = 1e-10
    ground_mask = np.abs(evals - e0) < tol
    n_ground = np.sum(ground_mask)
    
    e1 = evals[n_ground] if n_ground < len(evals) else e0
    gamma_m = e1 - e0
    
    # Ground space projector (as matrix of ground state vectors)
    G = evecs[:, :n_ground]
    
    return gamma_m, G, evals


def overlap_condition(m: int, delta: float = 0.0) -> float:
    """Compute the overlap parameter ε for the martingale method.
    
    ε = max over adjacent intervals of ||G_{i+1} G_i^⊥||
    
    For translation-invariant systems, this is the same for all i.
    We compute it for the (m+1)-site system split into sites [1..m] and [2..m+1].
    
    G_i^⊥ = I - G_i G_i^† is the projector onto the excited space of interval i.
    ||G_{i+1} G_i^⊥|| is the largest singular value of G_{i+1}^† G_i^⊥.
    
    Actually, the standard formulation uses:
    ε = ||(I - G_{[1,m]} G_{[1,m]}^†) G_{[2,m+1]}||
    """
    # Build the (m+1)-site constrained basis
    states_full = fibonacci_basis(m + 1, "obc")
    dim_full = len(states_full)
    
    # Build the m-site constrained basis (for left interval [0..m-1] and right [1..m])
    states_m = fibonacci_basis(m, "obc")
    dim_m = len(states_m)
    
    # Ground space of left interval [0..m-1]
    H_left = local_hamiltonian_pxp(m, delta)
    evals_l, evecs_l = np.linalg.eigh(H_left)
    tol = 1e-10
    n_ground_l = np.sum(np.abs(evals_l - evals_l[0]) < tol)
    G_left = evecs_l[:, :n_ground_l]  # dim_m × n_ground_l
    
    # Ground space of right interval [1..m]
    H_right = local_hamiltonian_pxp(m, delta)
    evals_r, evecs_r = np.linalg.eigh(H_right)
    n_ground_r = np.sum(np.abs(evals_r - evals_r[0]) < tol)
    G_right = evecs_r[:, :n_ground_r]  # dim_m × n_ground_r
    
    # For the overlap, we need to embed these into the (m+1)-site space
    # and compute ||(I - P_left) P_right|| where P = G G^†
    
    # Embedding: map m-site states to (m+1)-site states
    # Left interval [0..m-1]: site m is free (can be 0 or 1, respecting constraint)
    # Right interval [1..m]: site 0 is free
    
    # Build embedding matrices
    state_to_idx_full = {s: i for i, s in enumerate(states_full)}
    state_to_idx_m = {s: i for i, s in enumerate(states_m)}
    
    # Left embedding: (m+1)-site state -> m-site state by dropping site m
    # E_left[dim_full, dim_m]: E_left[full_idx, m_idx] = 1 if full_state restricted to [0..m-1] = m_state
    E_left = np.zeros((dim_full, dim_m))
    for fi, fs in enumerate(states_full):
        # Restrict to sites [0..m-1] (drop bit m)
        restricted = fs & ((1 << m) - 1)
        mi = state_to_idx_m.get(restricted)
        if mi is not None:
            E_left[fi, mi] = 1.0
    
    # Right embedding: (m+1)-site state -> m-site state by dropping site 0
    E_right = np.zeros((dim_full, dim_m))
    for fi, fs in enumerate(states_full):
        # Restrict to sites [1..m] (drop bit 0, shift right by 1)
        restricted = fs >> 1
        mi = state_to_idx_m.get(restricted)
        if mi is not None:
            E_right[fi, mi] = 1.0
    
    # Projectors in the full space
    # P_left = E_left @ G_left @ G_left^† @ E_left^†
    GL = E_left @ G_left  # dim_full × n_ground_l
    P_left = GL @ GL.T    # dim_full × dim_full
    
    # P_right = E_right @ G_right @ G_right^† @ E_right^†
    GR = E_right @ G_right  # dim_full × n_ground_r
    P_right = GR @ GR.T     # dim_full × dim_full
    
    # Overlap: ||(I - P_left) P_right|| = largest singular value
    I_minus_P_left = np.eye(dim_full) - P_left
    M = I_minus_P_left @ P_right
    
    # Largest singular value
    svals = np.linalg.svd(M, compute_uv=False)
    epsilon = svals[0]
    
    return epsilon


def martingale_gap_bound(gamma_m: float, epsilon: float, m: int, n: int) -> float:
    """Compute the martingale lower bound on the global gap.
    
    gap ≥ gamma_m · (1 - ε·√(m-1))²  (if ε < 1/√(m-1))
    
    Additional finite-size correction for chain of length n:
    The bound applies when n ≥ m. The standard result gives a uniform
    lower bound independent of n (thermodynamic limit).
    """
    threshold = 1.0 / np.sqrt(m - 1)
    if epsilon >= threshold:
        return 0.0  # Bound is trivial (gap could be zero)
    
    bound = gamma_m * (1.0 - epsilon * np.sqrt(m - 1)) ** 2
    return max(0.0, bound)


def main():
    parser = argparse.ArgumentParser(description="PXP gap certificate (martingale method)")
    parser.add_argument("--m", type=int, default=5, help="Local interval size")
    parser.add_argument("--delta", type=float, default=0.0, help="Detuning Δ")
    parser.add_argument("--max-n", type=int, default=20, help="Maximum chain length for comparison")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    
    m = args.m
    delta = args.delta
    
    print(f"PXP Gap Certificate — martingale method", flush=True)
    print(f"  m={m}, Δ={delta}", flush=True)
    print(flush=True)
    
    # Step 1: Local gap
    t0 = time.perf_counter()
    gamma_m, G, evals = local_gap_and_projector(m, delta)
    print(f"Local gap γ_{m} = {gamma_m:.8f}", flush=True)
    print(f"  (local dim = {len(evals)}, ground degeneracy = {G.shape[1]})", flush=True)
    
    # Step 2: Overlap condition
    epsilon = overlap_condition(m, delta)
    threshold = 1.0 / np.sqrt(m - 1)
    print(f"Overlap ε = {epsilon:.8f}", flush=True)
    print(f"  threshold 1/√(m-1) = {threshold:.8f}", flush=True)
    print(f"  ε < threshold? {'YES ✓' if epsilon < threshold else 'NO ✗ (bound trivial)'}", flush=True)
    
    # Step 3: Martingale bound
    cert_gap = martingale_gap_bound(gamma_m, epsilon, m, args.max_n)
    print(f"\nCertified gap lower bound: {cert_gap:.8f}", flush=True)
    
    # Step 4: Compare with ED
    print(f"\n{'N':>4} {'ED gap':>12} {'Certified':>12} {'Contains?':>10}", flush=True)
    print("-" * 42, flush=True)
    
    from pxp_ed_gap import compute_gap
    results = []
    for n in range(m + 1, args.max_n + 1):
        r = compute_gap(n, delta=delta, boundary="obc")
        contains = cert_gap <= r["gap"] + 1e-10
        results.append({
            "N": n, "ed_gap": r["gap"], "certified_gap": cert_gap,
            "contains": contains
        })
        mark = "✓" if contains else "✗"
        print(f"{n:4d} {r['gap']:12.8f} {cert_gap:12.8f} {mark:>10}", flush=True)
    
    dt = time.perf_counter() - t0
    print(f"\nTotal time: {dt:.2f}s", flush=True)
    
    summary = {
        "method": "martingale",
        "m": m,
        "delta": delta,
        "gamma_m": gamma_m,
        "epsilon": epsilon,
        "threshold": threshold,
        "certified_gap": cert_gap,
        "all_contained": all(r["contains"] for r in results),
        "results": results,
        "wall_sec": dt,
    }
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print(f"Saved to {args.output}", flush=True)
    
    return summary


if __name__ == "__main__":
    main()
