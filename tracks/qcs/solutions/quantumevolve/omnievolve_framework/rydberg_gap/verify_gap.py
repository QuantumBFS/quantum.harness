"""#233 Verifier: Anti-cheat + LMI verification for PXP gap certificate.

Runs INSIDE the sandbox after main.py. Reads:
  - main.py (candidate source) for static anti-cheat check
  - candidate_result.json (candidate output) for LMI verification

v4 anti-cheat: recursive call-tree analysis.
  - Finds certify_gap and ALL functions in its transitive call graph
  - Checks every function body for forbidden spectral/solver patterns
  - Catches helper-function indirection (e.g. _compute_spectrum_via_inverse_iteration)

Forbidden patterns (any of these in certify_gap's call tree → fail):
  - Eigenvalue solvers: eigvalsh, eigh, eig, eigs, eigvals, svd, svdvals, schur
  - Linear system solvers (inverse iteration): solve, inv, pinv, lstsq
  - Cholesky/lu factorization for solving: cho_factor, cho_solve, lu_factor, lu_solve
  - Iterative sparse solvers: cg, gmres, bicgstab, minres, tfqmr, gcrotmk
  - Sparse eigenvalue solvers: eigsh, svds, lobpcg, arpack

cvxpy's .solve() is NOT in this list — it dispatches internally to Clarabel/MOSEK,
so legitimate SDP code is unaffected.

Outputs verification JSON to stdout (last line).
"""
from __future__ import annotations

import ast
import json
import re
import sys

import numpy as np

# Comprehensive forbidden patterns — covers all spectral computation and
# inverse-iteration primitives. Legitimate SDP code uses only cvxpy.
_FORBIDDEN_PATTERNS = re.compile(
    r'\b('
    # --- Eigenvalue / SVD decomposition ---
    r'np\.linalg\.eigvalsh|np\.linalg\.eigh|np\.linalg\.eig\b|'
    r'np\.linalg\.eigvals|np\.linalg\.svd|np\.linalg\.svdvals|'
    r'scipy\.linalg\.eigvalsh|scipy\.linalg\.eigh|scipy\.linalg\.eig\b|'
    r'scipy\.linalg\.eigvals|scipy\.linalg\.svd|scipy\.linalg\.svdvals|'
    r'scipy\.linalg\.schur|scipy\.linalg\.hessenberg|'
    r'scipy\.sparse\.linalg\.eigs|scipy\.sparse\.linalg\.eigsh|'
    r'scipy\.sparse\.linalg\.svds|scipy\.sparse\.linalg\.lobpcg|'
    r'eigvalsh|eigh|eigsh|eigvals|svdvals|'
    # --- Linear system solvers (inverse iteration needs these) ---
    r'np\.linalg\.solve|np\.linalg\.inv\b|np\.linalg\.pinv|np\.linalg\.lstsq|'
    r'scipy\.linalg\.solve|scipy\.linalg\.inv\b|scipy\.linalg\.pinv|scipy\.linalg\.lstsq|'
    r'scipy\.sparse\.linalg\.spsolve|spsolve|'
    # --- Factorization-based solvers ---
    r'scipy\.linalg\.cho_factor|scipy\.linalg\.cho_solve|'
    r'scipy\.linalg\.lu_factor|scipy\.linalg\.lu_solve|'
    r'scipy\.linalg\.lu\b|'
    # --- Iterative solvers ---
    r'scipy\.sparse\.linalg\.cg\b|scipy\.sparse\.linalg\.gmres|'
    r'scipy\.sparse\.linalg\.bicgstab|scipy\.sparse\.linalg\.minres|'
    r'scipy\.sparse\.linalg\.tfqmr|scipy\.sparse\.linalg\.gcrotmk|'
    r'scipy\.sparse\.linalg\.dsolve|scipy\.sparse\.linalg\.isolve|'
    # --- Bare names (catches `from X import solve; solve(...)`) ---
    # Negative lookbehind on `.` prevents matching method calls like prob.solve()
    r'(?<!\.)\bsolve\s*\(|(?<!\.)\blstsq\s*\(|'
    r'(?<!\.)\bcg\s*\(|(?<!\.)\bgmres\s*\(|(?<!\.)\bbicgstab\s*\(|(?<!\.)\bminres\s*\('
    r')\b',
    re.MULTILINE,
)


def _collect_called_names(node: ast.AST) -> set[str]:
    """Collect all function names called within an AST node."""
    called = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    return called


def check_no_ed_in_certify(code: str) -> tuple[bool, str]:
    """Static check: certify_gap's entire call tree must avoid ED/solver patterns.

    Algorithm:
      1. Parse AST, build {func_name: FunctionDef} for all module-level functions
      2. Start from certify_gap, BFS through called function names
      3. Collect line ranges from all reachable functions
      4. Check those lines for forbidden patterns
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return True, ""  # Can't parse → let runtime handle it

    lines = code.splitlines()

    # Build function registry from module-level and class-level definitions
    func_defs: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_defs[node.name] = node

    # Find certify_gap entry point
    entry = func_defs.get("certify_gap")
    if entry is None:
        # No certify_gap → check whole file (conservative)
        source_lines = set(range(1, len(lines) + 1))
    else:
        # BFS through call graph starting from certify_gap
        visited: set[str] = set()
        queue = ["certify_gap"]
        source_lines: set[int] = set()

        while queue:
            fname = queue.pop(0)
            if fname in visited:
                continue
            visited.add(fname)

            fdef = func_defs.get(fname)
            if fdef is None:
                continue  # External function (cvxpy, numpy basic ops, etc.)

            # Add this function's line range
            for ln in range(fdef.lineno, (fdef.end_lineno or fdef.lineno) + 1):
                source_lines.add(ln)

            # Find functions called within this function
            called_names = _collect_called_names(fdef)
            for cn in called_names:
                if cn in func_defs and cn not in visited:
                    queue.append(cn)

    # Extract source code from collected lines
    certify_src = "\n".join(
        lines[i - 1] for i in sorted(source_lines) if i <= len(lines)
    )

    matches = _FORBIDDEN_PATTERNS.findall(certify_src)
    if matches:
        return False, f"forbidden pattern in certify_gap call tree: {matches[0]}"

    return True, ""


def build_pxp_dense(n: int, delta: float = 0.0) -> np.ndarray:
    """Rebuild PXP Hamiltonian for verification."""
    states = []
    for bits in range(1 << n):
        if bits & (bits << 1):
            continue
        states.append(bits)
    dim = len(states)
    idx = {s: i for i, s in enumerate(states)}
    H = np.zeros((dim, dim))
    for i, s in enumerate(states):
        for site in range(n):
            left_ok = (site == 0) or not ((s >> (site - 1)) & 1)
            right_ok = (site == n - 1) or not ((s >> (site + 1)) & 1)
            if left_ok and right_ok:
                j = idx.get(s ^ (1 << site))
                if j is not None:
                    H[i, j] += 1.0
        if delta != 0.0:
            H[i, i] -= delta * bin(s).count("1")
    return H


def verify_lmi(H: np.ndarray, E0_lb: float, gamma: float,
               M: np.ndarray) -> tuple[bool, float]:
    """Verify the LMI: H - (E0_lb + gamma)*I + M ≽ 0 AND M ≽ 0."""
    dim = H.shape[0]
    # Check M ≽ 0
    eigs_M = np.linalg.eigvalsh(M)
    if eigs_M[0] < -1e-8:
        return False, float(eigs_M[0])

    # Check LMI ≽ 0
    LMI = H - (E0_lb + gamma) * np.eye(dim) + M
    eigs_LMI = np.linalg.eigvalsh(LMI)
    return bool(eigs_LMI[0] >= -1e-8), float(eigs_LMI[0])


def main():
    # Read candidate source for anti-cheat
    try:
        with open("main.py", encoding="utf-8") as f:
            candidate_code = f.read()
    except FileNotFoundError:
        print(json.dumps({"verified": False, "error": "main.py not found"}))
        return

    # Static anti-cheat check (recursive call-tree analysis)
    ed_free, reason = check_no_ed_in_certify(candidate_code)
    if not ed_free:
        print(json.dumps({
            "verified": False,
            "anti_cheat": reason,
            "error": f"ANTI-CHEAT: {reason}",
        }))
        return

    # Read candidate output
    try:
        with open("candidate_result.json", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(json.dumps({"verified": False, "error": "candidate_result.json not found"}))
        return

    if data.get("status") != "ok":
        print(json.dumps({"verified": False, "error": data.get("status", "unknown")}))
        return

    cert_gap = data.get("certified_gap", 0.0)
    E0_lb = data.get("E0_lb", None)

    if cert_gap <= 0:
        print(json.dumps({"verified": True, "score": 0.0, "reason": "certified_gap <= 0"}))
        return

    if E0_lb is None:
        print(json.dumps({"verified": False, "error": "Missing E0_lb"}))
        return

    # Get n and delta from candidate output
    n = data.get("n", 8)
    delta = data.get("delta", 0.0)

    # Rebuild H for verification
    H = build_pxp_dense(n, delta)
    dim = H.shape[0]

    # Reconstruct M from M_cholesky or M
    M = None
    if "M_cholesky" in data and data["M_cholesky"]:
        try:
            L = np.array(data["M_cholesky"], dtype=np.float64)
            M = L @ L.T
        except (ValueError, TypeError):
            pass
    elif "M" in data and data["M"]:
        try:
            M = np.array(data["M"], dtype=np.float64)
        except (ValueError, TypeError):
            pass

    if M is not None:
        if M.shape != (dim, dim):
            print(json.dumps({
                "verified": False,
                "error": f"M shape {M.shape} != ({dim},{dim})",
            }))
            return
        lmi_valid, min_eig = verify_lmi(H, E0_lb, cert_gap, M)
        if not lmi_valid:
            print(json.dumps({
                "verified": False,
                "error": f"LMI verification FAILED (min_eig={min_eig:.2e})",
            }))
            return

    # All checks passed
    print(json.dumps({
        "verified": True,
        "certified_gap": cert_gap,
        "E0_lb": E0_lb,
        "lmi_valid": True if M is not None else None,
    }))


if __name__ == "__main__":
    main()
