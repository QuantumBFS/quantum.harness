"""PXP chain exact diagonalization — spectral gap reference for #233.

Computes the full spectrum of the constrained PXP Hamiltonian:
    H = Ω Σ_i P_{i-1} σ^x_i P_{i+1} - Δ Σ_i n_i

in the Fibonacci-constrained Hilbert space (no two adjacent Rydberg excitations).
Outputs E0, E1, gap = E1 - E0 for N = 4..26 (OBC and PBC).

Usage:
    python pxp_ed_gap.py [--delta 0.0] [--boundary obc] [--max-n 26]
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
from scipy.sparse.linalg import eigsh


def fibonacci_basis(n: int, boundary: str = "obc") -> list[int]:
    """Generate all computational-basis states satisfying the blockade constraint.
    
    No two adjacent 1s (Rydberg excitations). For PBC, also forbid site 0 and site N-1
    both being 1.
    
    Returns list of integer bitstrings.
    """
    states = []
    for bits in range(1 << n):
        # Check no two adjacent 1s
        if bits & (bits >> 1):
            continue
        # PBC: also check wraparound
        if boundary == "pbc" and n > 2:
            if (bits & 1) and (bits >> (n - 1)) & 1:
                continue
        states.append(bits)
    return states


def build_pxp_hamiltonian(n: int, omega: float = 1.0, delta: float = 0.0,
                          boundary: str = "obc") -> csr_matrix:
    """Build the PXP Hamiltonian in the constrained basis.
    
    H = Ω Σ_i P_{i-1} σ^x_i P_{i+1} - Δ Σ_i n_i
    
    P_i = |0><0|_i projects neighbor onto ground state.
    σ^x_i flips site i (if both neighbors are in |0>).
    n_i = |1><1|_i is the Rydberg number operator.
    """
    states = fibonacci_basis(n, boundary)
    dim = len(states)
    state_to_idx = {s: i for i, s in enumerate(states)}
    
    H = lil_matrix((dim, dim), dtype=np.float64)
    
    for idx, bits in enumerate(states):
        # Diagonal: -Δ Σ n_i
        if delta != 0.0:
            n_exc = bin(bits).count('1')
            H[idx, idx] += -delta * n_exc
        
        # Off-diagonal: Ω Σ P_{i-1} σ^x_i P_{i+1}
        for i in range(n):
            # Check if site i can be flipped (both neighbors in |0>)
            # Left neighbor
            if boundary == "obc":
                if i > 0 and (bits >> (i - 1)) & 1:
                    continue  # left neighbor is excited, blocked
                if i < n - 1 and (bits >> (i + 1)) & 1:
                    continue  # right neighbor is excited, blocked
            else:  # pbc
                left = (i - 1) % n
                right = (i + 1) % n
                if (bits >> left) & 1:
                    continue
                if (bits >> right) & 1:
                    continue
            
            # Flip site i
            flipped = bits ^ (1 << i)
            j = state_to_idx.get(flipped)
            if j is not None:
                H[idx, j] += omega
    
    return H.tocsr()


def compute_gap(n: int, delta: float = 0.0, boundary: str = "obc",
                full: bool = False) -> dict:
    """Compute spectral gap for PXP chain of length n.
    
    Returns dict with N, dim, E0, E1, gap, and optionally full spectrum info.
    """
    H = build_pxp_hamiltonian(n, delta=delta, boundary=boundary)
    dim = H.shape[0]
    
    if dim <= 2 or full:
        # Full diagonalization for small systems
        H_dense = H.toarray()
        evals = np.linalg.eigvalsh(H_dense)
        e0 = evals[0]
        e1 = evals[1] if len(evals) > 1 else e0
        gap = e1 - e0
        result = {
            "N": n, "dim": dim, "boundary": boundary, "delta": delta,
            "E0": float(e0), "E1": float(e1), "gap": float(gap),
        }
        if full:
            result["spectrum"] = evals.tolist()
        return result
    else:
        # Lanczos for larger systems (get 2 lowest eigenvalues)
        try:
            evals, _ = eigsh(H, k=2, which='SA')
            evals = np.sort(evals)
            e0, e1 = evals[0], evals[1]
        except Exception:
            # Fallback to dense if Lanczos fails
            H_dense = H.toarray()
            evals = np.linalg.eigvalsh(H_dense)
            e0, e1 = evals[0], evals[1]
        
        return {
            "N": n, "dim": dim, "boundary": boundary, "delta": delta,
            "E0": float(e0), "E1": float(e1), "gap": float(e1 - e0),
        }


def main():
    parser = argparse.ArgumentParser(description="PXP chain ED gap computation")
    parser.add_argument("--delta", type=float, default=0.0, help="Detuning Δ")
    parser.add_argument("--boundary", choices=["obc", "pbc"], default="obc")
    parser.add_argument("--max-n", type=int, default=26, help="Maximum chain length")
    parser.add_argument("--min-n", type=int, default=4, help="Minimum chain length")
    parser.add_argument("--full-spectrum", action="store_true", help="Output full spectrum (small N only)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file")
    args = parser.parse_args()
    
    results = []
    print(f"PXP ED Gap — Δ={args.delta}, boundary={args.boundary}", flush=True)
    print(f"{'N':>4} {'dim':>8} {'E0':>12} {'E1':>12} {'gap':>12} {'time(s)':>8}", flush=True)
    print("-" * 60, flush=True)
    
    for n in range(args.min_n, args.max_n + 1):
        t0 = time.perf_counter()
        try:
            r = compute_gap(n, delta=args.delta, boundary=args.boundary,
                          full=(args.full_spectrum and n <= 14))
            dt = time.perf_counter() - t0
            r["wall_sec"] = dt
            results.append(r)
            print(f"{r['N']:4d} {r['dim']:8d} {r['E0']:12.6f} {r['E1']:12.6f} "
                  f"{r['gap']:12.6f} {dt:8.2f}", flush=True)
        except Exception as e:
            print(f"{n:4d} {'FAILED':>8} — {e}", flush=True)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved to {args.output}", flush=True)
    
    return results


if __name__ == "__main__":
    main()
