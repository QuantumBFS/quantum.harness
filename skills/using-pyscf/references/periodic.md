# Periodic systems (`pbc`)

> Reference only — not exercised by any current challenge. Builds on
> quickstart §17 (periodic boundary conditions) —
> https://pyscf.org/quickstart.html
> User guide: https://pyscf.org/user/pbc.html
> Examples: https://github.com/pyscf/pyscf/tree/master/examples/pbc

## 1. `pbc.gto.Cell`

`pbc.gto.Cell` extends `gto.Mole` with lattice vectors. Construct it directly
or with the `pbc.gto.M` shortcut, the periodic analogue of `gto.M`:

```python
import numpy
from pyscf.pbc import gto, scf

cell = gto.M(
    a=numpy.eye(3) * 3.5668,          # lattice vectors, one per row
    atom="""C 0.      0.      0.
            C 0.8917  0.8917  0.8917""",
    basis="gth-szv",
    pseudo="gth-pade",
    verbose=0,
)
mf = scf.RHF(cell).run()
```

Verified on 2.14.0: this diamond-lattice example (`gth-szv`/`gth-pade`, the
usual pairing for a norm-conserving pseudopotential PBC calculation) gives
`E(gamma-point RHF) = -10.71006209 Ha`.

**Default length unit — verified, not assumed.** `Cell().unit` and
`Mole().unit` both default to `"angstrom"` on 2.14.0, and this applies to
`a` (the lattice vectors) exactly as it does to `atom` — confirmed by
building the cell above with no `unit` set and comparing its volume against
building it with `unit="Angstrom"` explicit (identical) and `unit="Bohr"`
explicit (different, as expected). **`pbc.gto.Cell` does not default to Bohr
while `gto.M` defaults to Angstrom** — a difference sometimes assumed by
analogy with `lattice_vectors()`, whose *return* value defaults to Bohr
(`Cell.lattice_vectors(unit='Bohr')`) but whose *input* interpretation of
`self.a` still follows `self.unit`. State `unit=` explicitly on `Cell`
construction anyway — the input/output asymmetry above is exactly the kind
of thing worth not relying on implicitly.

## 2. k-point sampling

`cell.make_kpts([nx, ny, nz])` builds a Monkhorst-Pack k-point mesh;
`pbc.scf.KRHF`/`KUHF`/`KROHF` (and `pbc.dft.KRKS`/etc.) take the cell and the
k-point array in place of the gamma-point-only `RHF`/`RKS`:

```python
kpts = cell.make_kpts([2, 2, 2])
kmf = scf.KRHF(cell, kpts).run()
```

Verified on 2.14.0: `cell.make_kpts([2, 1, 1])` returns a `(2, 3)` array and
`scf.KRHF(cell, kpts)` builds without error. The upstream examples note the
default FFT-based two-electron integral builder (`FFTDF`) is slow for `KRHF`
— a 2×2×2 mesh on the two-atom cell above did not finish gamma-quality SCF
in several minutes on a laptop; density fitting or the `rsjk` builder (see
`examples/pbc/21-k_points_all_electron_scf.py`) is the documented remedy for
anything beyond a quick smoke test.

## 3. Correlated periodic methods

`pbc.mp` and `pbc.cc` mirror the molecular `mp`/`cc` modules — `MP2` and
`CCSD` built on a converged `pbc.scf` mean-field object, gamma-point or
k-point sampled. Both import cleanly on 2.14.0 (`pyscf.pbc.mp`,
`pyscf.pbc.cc`); no separate install is needed beyond the base `pyscf`
package.

## 4. Boundary: this is not the harness's periodic route

**`/using-quantum-espresso` owns the plane-wave periodic path in this
harness**, including the `pw2qmcpack` orbital-generation route that feeds
QMCPACK's Slater-Jastrow VMC/DMC workflow. PySCF's `pbc` module — Gaussian
basis sets, all-electron or GTH pseudopotentials, `FFTDF`/`GDF`-based
integrals — solves the same class of periodic problem with a different basis
and a different toolchain, and it overlaps that path rather than extending
it. It is **not** the harness's default route to a periodic result.

Reach for PySCF `pbc` specifically when a Gaussian basis is wanted for its
own sake — for example, comparing a periodic result against the same
molecular-basis machinery `pyscf-api.md` and `active-space.md` already use,
or a correlated (`pbc.mp`/`pbc.cc`) periodic calculation for which no
plane-wave equivalent is being run. Otherwise, route to
`/using-quantum-espresso`.

---

## Source links

- Quickstart: https://pyscf.org/quickstart.html
- Periodic (pbc) user guide: https://pyscf.org/user/pbc.html
- PBC examples: https://github.com/pyscf/pyscf/tree/master/examples/pbc
- k-point SCF example (used in §2): `examples/pbc/20-k_points_scf.py`,
  https://github.com/pyscf/pyscf/tree/master/examples/pbc
- Install: https://pyscf.org/user/install.html
- Harness's plane-wave periodic route: `skills/using-quantum-espresso/SKILL.md`
