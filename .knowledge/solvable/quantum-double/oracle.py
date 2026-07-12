"""Kitaev quantum-double D(G) oracle: anyon census + torus GSD for finite G.

The quantum double D(G) of a finite group G is the exactly solvable
commuting-projector (stabilizer-like) lattice gauge theory whose anyons are
the irreducible representations of the Drinfeld double. They are labelled by
pairs ([c], pi) where [c] runs over the conjugacy classes of G and pi over the
irreducible representations of the centralizer Z(c) of a representative c. Hence

    #anyons = sum_{[c]}  #Irr(Z(c))  =  sum_{[c]}  #conjugacy-classes(Z(c)),

using #Irr(H) = #conjugacy-classes(H) for any finite group H. On the torus the
ground-state degeneracy equals the number of anyon types, GSD = #anyons.

This script computes that census ALGEBRAICALLY from a group multiplication
table (conjugacy classes, centralizers, and the class-number of each
centralizer). It is a PARTIAL (P) oracle: the anyon count and torus GSD are
exact, but the full commuting-projector lattice Hamiltonian H = -sum_v A_v -
sum_p B_p (with G-valued edge dof), the ribbon operators, and the non-abelian
fusion/braiding data are exact-but-NOT-built here -- see ORACLE.md.

D(Z2) is precisely Kitaev's toric code: 4 anyons {1, e, m, eps}, GSD = 4. This
is cross-checked at runtime against toric-code/oracle.py [@Kitaev2003].
"""
import importlib.util
import sys
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def _cyclic(n):
    """Z_n: elements 0..n-1 under addition mod n (abelian)."""
    elems = list(range(n))
    return elems, (lambda a, b: (a + b) % n)


def _symmetric3():
    """S3 as permutations of (0,1,2); mul is composition (a*b)(i) = a[b[i]]."""
    elems = [tuple(p) for p in permutations(range(3))]
    return elems, (lambda a, b: tuple(a[b[i]] for i in range(3)))


GROUPS = {
    "Z2": lambda: _cyclic(2),
    "Z3": lambda: _cyclic(3),
    "Z4": lambda: _cyclic(4),
    "S3": _symmetric3,
}


def _inverse(g, elems, mul, identity):
    for h in elems:
        if mul(g, h) == identity:
            return h
    raise ValueError(f"no inverse for {g}")


def _identity(elems, mul):
    for e in elems:
        if all(mul(e, g) == g and mul(g, e) == g for g in elems):
            return e
    raise ValueError("no identity element")


def _conjugacy_classes(elems, mul):
    """Partition elems into conjugacy classes {h g h^-1 : h in G}."""
    ident = _identity(elems, mul)
    inv = {g: _inverse(g, elems, mul, ident) for g in elems}
    seen = set()
    classes = []
    for g in elems:
        if g in seen:
            continue
        cls = set()
        for h in elems:
            cls.add(mul(mul(h, g), inv[h]))
        seen |= cls
        classes.append(sorted(cls, key=repr))
    return classes


def _centralizer(g, elems, mul):
    """Elements commuting with g: {h : h g = g h}."""
    return [h for h in elems if mul(h, g) == mul(g, h)]


def _n_irreps(subgroup, mul):
    """#Irr(H) = #conjugacy-classes(H) (H a subgroup, using the ambient mul)."""
    return len(_conjugacy_classes(subgroup, mul))


def compute(G="S3"):
    """Quantum-double D(G) anyon census + torus GSD, computed from group data."""
    if G not in GROUPS:
        raise ValueError(f"unknown group {G!r}; choose from {sorted(GROUPS)}")
    elems, mul = GROUPS[G]()
    classes = _conjugacy_classes(elems, mul)
    # #anyons = sum over conjugacy classes of #Irr(centralizer of a representative)
    n_anyons = 0
    for cls in classes:
        rep = cls[0]
        Zc = _centralizer(rep, elems, mul)
        n_anyons += _n_irreps(Zc, mul)
    abelian = all(mul(a, b) == mul(b, a) for a in elems for b in elems)
    return {
        "n_anyons": n_anyons,        # #anyon types of D(G) = sum_[c] #Irr(Z(c))
        "gsd_torus": n_anyons,       # torus ground-state degeneracy = #anyons
        "abelian": abelian,          # abelian G -> |G|^2 abelian anyons; S3 -> 8, non-abelian
        "n_group": len(elems),       # |G|
    }


def _load_toric_code():
    path = Path(__file__).resolve().parents[1] / "toric-code" / "oracle.py"
    spec = importlib.util.spec_from_file_location("oracle_toric_code", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def self_test():
    # Abelian D(Z_n): all centralizers = G, so #anyons = n * n.
    assert compute(G="Z2")["gsd_torus"] == 4, "D(Z2) = toric code"
    assert compute(G="Z3")["gsd_torus"] == 9
    assert compute(G="Z4")["gsd_torus"] == 16
    assert compute(G="Z2")["abelian"] and compute(G="Z3")["abelian"]
    # Non-abelian D(S3): classes {e},{3 transpositions},{2 three-cycles} with
    # centralizers S3 (3 irreps), Z2 (2), Z3 (3) -> 3 + 2 + 3 = 8 anyons.
    s3 = compute(G="S3")
    assert s3["gsd_torus"] == 8 and s3["n_anyons"] == 8, s3
    assert s3["abelian"] is False and s3["n_group"] == 6, s3
    # n_anyons == gsd_torus for every group (torus GSD = anyon count).
    for g in ("Z2", "Z3", "Z4", "S3"):
        r = compute(G=g)
        assert r["n_anyons"] == r["gsd_torus"], g
    # Cross-card anchor: D(Z2) IS the toric code -- match toric-code/oracle.py GSD.
    toric = _load_toric_code()
    assert compute(G="Z2")["gsd_torus"] == toric.compute(L=3)["gsd"], "D(Z2) == toric code GSD"


if __name__ == "__main__":
    oracle_main(compute, {"G": (str, "S3")})
