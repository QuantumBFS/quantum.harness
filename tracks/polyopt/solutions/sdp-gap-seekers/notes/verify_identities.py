"""
Independent verification of the Problem B strengthening identities
from theory-problems-offloading-crosscheck.md.

Method: construct spin-1/2 operators on the FULL 2^n Hilbert space and
check each identity as an operator matrix equality (Frobenius norm of
LHS - RHS ~ machine epsilon). An identity that holds on the full Hilbert
space of the involved sites is exact; spectator sites only tensor on
identity, so n=2 for the bond and n=3 for the triangle/shared-site
identities is a complete check.

Run:  python3 verify_identities.py
"""
import numpy as np


def pauli():
    sx = np.array([[0, 1], [1, 0]], dtype=complex)
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex)
    sz = np.array([[1, 0], [0, -1]], dtype=complex)
    i2 = np.eye(2, dtype=complex)
    return sx, sy, sz, i2


def site_op(op, k, n):
    """Place op at site k (0-indexed) in an n-site chain, identity elsewhere."""
    _, _, _, i2 = pauli()
    factors = [i2] * n
    factors[k] = op
    out = factors[0]
    for f in factors[1:]:
        out = np.kron(out, f)
    return out


def spin_ops(n):
    """S^a[k] = (1/2) sigma^a on site k, full 2^n x 2^n matrices."""
    sx, sy, sz, _ = pauli()
    paulis = {"x": sx, "y": sy, "z": sz}
    S = {"x": [], "y": [], "z": []}
    for k in range(n):
        for a in "xyz":
            S[a].append(0.5 * site_op(paulis[a], k, n))
    return S


def dot(S, i, j):
    return S["x"][i] @ S["x"][j] + S["y"][i] @ S["y"][j] + S["z"][i] @ S["z"][j]


def fnorm(M):
    return float(np.linalg.norm(M))


def check(name, lhs, rhs, n, tol=1e-9):
    I = np.eye(2 ** n, dtype=complex)
    # also verify rhs shape matches; assume square 2^n
    d = fnorm(lhs - rhs)
    rel = d / max(fnorm(rhs), 1e-30)
    status = "PASS" if d < tol else "FAIL"
    print(f"  [{status}] {name}")
    print(f"         |LHS-RHS|_F = {d:.3e}  (rel {rel:.3e})")
    return d < tol


def main():
    print("=== spin-1/2 strengthening identity verification (full Hilbert space) ===")
    all_ok = True

    # --- B1: bond identity, n=2 ---
    print("\n[B1] Bond: (S_i.S_j)^2 = 3/16 I - (1/2)(S_i.S_j)")
    n = 2
    S = spin_ops(n)
    I = np.eye(2 ** n, dtype=complex)
    X12 = dot(S, 0, 1)
    all_ok &= check("(S1.S2)^2 = 3/16 I - 1/2 (S1.S2)",
                    X12 @ X12, (3 / 16) * I - 0.5 * X12, n)
    ev = np.sort(np.linalg.eigvalsh(X12))
    print(f"         eig(S1.S2) = {np.round(ev, 4)}  (expect -0.75, +0.25 x3)")

    # --- B2: triangle sum identity, n=3 ---
    print("\n[B2] Triangle: (X12+X23+X31)^2 = 9/16 I")
    n = 3
    S = spin_ops(n)
    I = np.eye(2 ** n, dtype=complex)
    X12 = dot(S, 0, 1)
    X23 = dot(S, 1, 2)
    X31 = dot(S, 2, 0)
    X13 = dot(S, 0, 2)
    sig3 = X12 + X23 + X31
    all_ok &= check("(X12+X23+X31)^2 = 9/16 I",
                    sig3 @ sig3, (9 / 16) * I, n)
    ev = np.sort(np.linalg.eigvalsh(sig3))
    print(f"         eig(sigma_3) = {np.round(ev, 4)}  (expect -0.75 x4, +0.75 x4)")

    # --- B3: shared-site symmetric identity, n=3 ---
    # {X_ij, X_ik} = (1/2) X_jk  (i shared)
    print("\n[B3] Shared-site symmetric: {X_ij, X_ik} = (1/2) X_jk")
    all_ok &= check("{X12,X13} = 1/2 X23",
                    X12 @ X13 + X13 @ X12, 0.5 * X23, n)
    all_ok &= check("{X23,X21} = 1/2 X31",
                    X23 @ X12 + X12 @ X23, 0.5 * X31, n)
    all_ok &= check("{X31,X32} = 1/2 X12",
                    X31 @ X23 + X23 @ X31, 0.5 * X12, n)

    # --- BONUS: commutator [X_ij, X_ik] = i S_i.(S_j x S_k) ---
    print("\n[BONUS] Commutator: [X12, X13] = i S1.(S2 x S3)")
    eps = {(0, 1, 2): 1, (1, 2, 0): 1, (2, 0, 1): 1,
           (0, 2, 1): -1, (2, 1, 0): -1, (1, 0, 2): -1}
    axes = ["x", "y", "z"]
    cross_dot = np.zeros((2 ** n, 2 ** n), dtype=complex)
    for a in range(3):
        for b in range(3):
            for c in range(3):
                if (a, b, c) in eps:
                    cross_dot += eps[(a, b, c)] * (S[axes[a]][0] @ S[axes[b]][1] @ S[axes[c]][2])
    comm = X12 @ X13 - X13 @ X12
    all_ok &= check("[X12,X13] = i S1.(S2 x S3)", comm, 1j * cross_dot, n)

    # --- plaquette Casimir spot-check (B4), n=4: minimal poly of sigma_4 ---
    print("\n[B4 spot] Plaquette: sigma_4^3 + 1/2 sigma_4^2 - 9/4 sigma_4 - 9/8 I = 0")
    n = 4
    S = spin_ops(n)
    I = np.eye(2 ** n, dtype=complex)
    pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    sig4 = sum(dot(S, i, j) for i, j in pairs)
    poly = sig4 @ sig4 @ sig4 + 0.5 * sig4 @ sig4 - 2.25 * sig4 - 1.125 * I
    all_ok &= check("minimal polynomial of sigma_4 (all 6 plaquette pairs)",
                    poly, np.zeros_like(poly), n)
    ev = np.sort(np.linalg.eigvalsh(sig4))
    print(f"         eig(sigma_4) unique = {np.round(np.unique(np.round(ev, 6)), 4)}  (expect -1.5, -0.5, +1.5)")

    print("\n" + "=" * 70)
    print("RESULT: " + ("ALL IDENTITIES VERIFIED on full Hilbert space"
                        if all_ok else "SOME CHECKS FAILED — re-examine cross-check doc"))


if __name__ == "__main__":
    main()
