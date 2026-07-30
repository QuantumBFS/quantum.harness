"""#233 Seed: SDP gap certificate for PXP (blockaded Rydberg) chain.

Evolves the SDP construction to maximize certified_gap / ED_gap.

Mathematical formulation:
  SDP: max γ  s.t.  H + M - (E0_lb + γ)·I ≽ 0,  M ≽ 0
  Optimal γ* = E₁ - E0_lb (bounded; M acts as ground-state witness).
  certified_gap = γ* - (E0_ub - E0_lb)

  The SDP exploits the fact that M ≽ 0 can only "help" the ground state
  direction. For excited states orthogonal to range(M), the LMI directly
  gives E_i ≥ E0_lb + γ. The trace of M at optimum equals E₁ - E₀.

Candidate contract:
  - certify_gap(n, delta) → {"certified_gap": float, "E0_lb": float,
    "M_cholesky": [[...]], "status": "ok"}
  - When run as __main__, writes candidate_result.json and prints JSON to stdout.

Seed strategy (deliberately weak — score ≈ 0):
  - E0_lb: Gershgorin disc bound (E0 ≥ -n, very loose)
  - E0_ub: ⟨Z2|H|Z2⟩ = 0 (product state, no variational optimization)
  - SDP: single-shot, no symmetry reduction, no NPA hierarchy

Evolution targets:
  - Tighter E0_lb via NPA/moment hierarchy or iterative bounds
  - Better E0_ub via Lanczos / variational Krylov from |Z2⟩
  - Translation-invariant or block-diagonal M reduction
  - Higher-level moment constraints (level-2 NPA)
  - Direct gap SDP with approximate ground-state projector
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np


def fibonacci_basis(n: int) -> list[int]:
    """All bitstrings with no adjacent 1s (OBC blockade constraint)."""
    states = []
    for bits in range(1 << n):
        if bits & (bits << 1):
            continue
        states.append(bits)
    return states


def build_pxp_hamiltonian(n: int, delta: float = 0.0) -> np.ndarray:
    """Dense PXP Hamiltonian in Fibonacci basis."""
    basis = fibonacci_basis(n)
    dim = len(basis)
    idx = {s: i for i, s in enumerate(basis)}
    H = np.zeros((dim, dim))
    for i, s in enumerate(basis):
        for site in range(n):
            left_ok = (site == 0) or not ((s >> (site - 1)) & 1)
            right_ok = (site == n - 1) or not ((s >> (site + 1)) & 1)
            if left_ok and right_ok:
                j = idx.get(s ^ (1 << site))
                if j is not None:
                    H[i, j] += 1.0
        if delta != 0.0:
            H[i, i] -= delta * bin(s).count('1')
    return H


def ed_reference(n: int, delta: float = 0.0) -> tuple[float, float]:
    """Exact E0 and gap (for reporting only — NOT used in certification)."""
    H = build_pxp_hamiltonian(n, delta)
    evals = np.linalg.eigvalsh(H)
    return float(evals[0]), float(evals[1] - evals[0])


def certify_gap(n: int, delta: float = 0.0) -> dict:
    """Certified spectral gap via SDP relaxation.

    Formulation:
      max γ  s.t.  H + M - (E0_lb + γ)·I ≽ 0,  M ≽ 0

    The optimal γ* = E₁ - E0_lb. The certified gap is:
      certified_gap = γ* - (E0_ub - E0_lb)

    This is a valid lower bound on the true gap E₁ - E₀ because:
      E₁ - E₀ ≥ γ* - (E0_ub - E0_lb) = (E₁ - E0_lb) - (E0_ub - E0_lb) = E₁ - E0_ub

    Returns dict with certified_gap, E0_lb, M_cholesky, status.
    """
    import cvxpy as cp

    H = build_pxp_hamiltonian(n, delta)
    dim = H.shape[0]
    basis = fibonacci_basis(n)

    # --- E0 lower bound: Gershgorin (deliberately weak) ---
    # Each row has ≤ n off-diagonal entries of magnitude 1 → E0 ≥ -n
    E0_lb = -float(n)

    # --- E0 upper bound: ⟨Z2|H|Z2⟩ (product state, no optimization) ---
    z2_state = 0
    for i in range(0, n, 2):
        z2_state |= (1 << i)
    if z2_state in basis:
        idx_z2 = basis.index(z2_state)
        E0_ub = float(H[idx_z2, idx_z2])  # = 0 for Δ=0 (H purely off-diagonal)
    else:
        E0_ub = 0.0

    # --- SDP: max γ s.t. H + M - (E0_lb + γ)·I ≽ 0, M ≽ 0 ---
    gamma = cp.Variable(name="gamma")
    M = cp.Variable((dim, dim), PSD=True, name="M")

    constraints = [
        H + M - (E0_lb + gamma) * np.eye(dim) >> 0,
    ]

    prob = cp.Problem(cp.Maximize(gamma), constraints)
    try:
        prob.solve(solver=cp.CLARABEL, verbose=False, max_iter=10000)
        if prob.status in ("optimal", "optimal_inaccurate"):
            gamma_val = float(gamma.value) if gamma.value is not None else 0.0
            slack = E0_ub - E0_lb
            cert_gap = max(0.0, gamma_val - slack)

            result = {
                "certified_gap": cert_gap,
                "gamma_sdp": gamma_val,
                "E0_lb": E0_lb,
                "E0_ub": E0_ub,
                "slack": slack,
                "status": "ok",
                "sdp_status": prob.status,
                "dim": dim,
            }

            # Output Cholesky factor of M for evaluator LMI verification
            if cert_gap > 0 and M.value is not None:
                M_val = np.array(M.value)
                M_val = 0.5 * (M_val + M_val.T)  # enforce symmetry
                try:
                    L = np.linalg.cholesky(M_val + 1e-10 * np.eye(dim))
                    result["M_cholesky"] = L.tolist()
                except np.linalg.LinAlgError:
                    result["M"] = M_val.tolist()

            return result
        else:
            return {"certified_gap": 0.0, "E0_lb": E0_lb, "E0_ub": E0_ub,
                    "status": f"sdp_{prob.status}"}
    except Exception as e:
        return {"certified_gap": 0.0, "E0_lb": E0_lb, "E0_ub": E0_ub,
                "status": f"error: {e}"}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    delta = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0

    t0 = time.time()
    result = certify_gap(n, delta)
    wall = time.time() - t0

    # ED reference for reporting only (not used in certification)
    E0_ed, gap_ed = ed_reference(n, delta)
    result["gap_ed"] = gap_ed
    result["E0_ed"] = E0_ed
    result["n"] = n
    result["delta"] = delta
    result["wall_sec"] = round(wall, 3)

    # Score: certified_gap / ED_gap (1.0 = perfect certificate)
    if gap_ed > 0 and result["certified_gap"] > 0:
        result["score"] = min(result["certified_gap"] / gap_ed, 1.0)
    else:
        result["score"] = 0.0

    # Write to file for verifier
    with open("candidate_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f)

    print(json.dumps(result), flush=True)
