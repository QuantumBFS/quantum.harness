# PySCF API + Examples Reference

> Exercised by: issues #83 and #129. Builds on quickstart §1–3, §8, §10–12 —
> read https://pyscf.org/quickstart.html first; this file adds harness
> conventions, the traps, and a verified anchor.

PySCF is an open-source **Python quantum-chemistry framework**: molecule and
basis-set input, one- and two-electron integrals, mean-field (HF/DFT),
post-HF (MP2, CCSD, FCI), multiconfigurational SCF (CASCI/CASSCF), and
periodic (`pbc`) systems, built on NumPy/SciPy with compiled extensions for
the integral and tensor work. In this harness PySCF is the **provider** of
molecular electronic-structure input, not a solver: one- and two-electron
integrals, FCIDUMP files handed to DMRG/ED/SHCI solvers, active-space
construction, and small-system reference energies (HF, FCI, CCSD, CASCI) used
as oracles.

- **Quickstart (start here):** https://pyscf.org/quickstart.html
- Homepage / docs: https://pyscf.org/
- Install: https://pyscf.org/user/install.html
- User guide index: https://pyscf.org/user/index.html
- Molecules (`gto`): https://pyscf.org/user/gto.html
- Mean field (`scf`): https://pyscf.org/user/scf.html
- MCSCF / CASSCF: https://pyscf.org/user/mcscf.html
- CI / FCI: https://pyscf.org/user/ci.html
- Coupled cluster: https://pyscf.org/user/cc.html
- Orbital localization: https://pyscf.org/user/lo.html
- Geometry optimization: https://pyscf.org/user/geomopt.html
- Periodic (pbc): https://pyscf.org/user/pbc.html
- Full API docs: https://pyscf.org/pyscf_api_docs/pyscf.html
- `pyscf.tools` API: https://pyscf.org/pyscf_api_docs/pyscf.tools.html
- `pyscf.mcscf` API: https://pyscf.org/pyscf_api_docs/pyscf.mcscf.html
- Examples index: https://github.com/pyscf/pyscf/tree/master/examples
  (`scf`, `mcscf`, `fci`, `cc`, `tools`, `local_orb`, `geomopt`, `pbc` subdirectories)
- Source: https://github.com/pyscf/pyscf
- Paper: Sun et al., WIREs Comput. Mol. Sci. 8, e1340 (2018)

---

## 1. The convention users get wrong most

**Integral index ordering.** PySCF's electron-repulsion integrals are stored
in **Mulliken** (chemist's) notation `(pq|rs)`, the convention used throughout
quantum chemistry. Much of many-body physics writes the same integral in
**Dirac** (physicist's) notation `⟨pq|rs⟩`. The two differ by an index swap:

```
(pq|rs) = ⟨pr|qs⟩
```

Building a Hamiltonian with the wrong convention does not raise an error — it
silently assembles a *different, still-Hermitian* two-body term that runs to
completion and looks plausible. Fix the convention before writing anything
that consumes PySCF integrals; see `references/fcidump.md` for how this shows
up in the FCIDUMP two-electron block.

**`mol.spin` is 2S**, i.e. the number of unpaired electrons — not the total
spin quantum number S. A singlet is `spin=0`, a doublet radical is `spin=1`, a
triplet is `spin=2`. Verified against 2.14.0 below.

```python
from pyscf import gto
mol = gto.M(atom="O 0 0 0; O 0 0 1.2", basis="sto-3g", spin=2, verbose=0)
print("mol.spin (2S):", mol.spin)          # 2, not 1 — triplet O2 has 2 unpaired electrons
```

---

## 2. Molecule construction

`gto.M(**kwargs)` is a thin wrapper that builds a `gto.Mole` and calls
`.build(**kwargs)`; the keywords below come straight from
`inspect.signature(gto.Mole.build)` on 2.14.0.

| Keyword | Meaning | Default |
|---|---|---|
| `atom` | geometry — list-of-tuples, a semicolon-separated string, or a path to a file (`.xyz` detected) | — (required) |
| `basis` | basis set name or per-element dict | — (required) |
| `unit` | `"Angstrom"` or `"Bohr"`/`"B"` for the geometry above | `"Angstrom"` |
| `charge` | net molecular charge | `0` |
| `spin` | **2S**, unpaired electrons (§1) | `0` |
| `symmetry` | point-group detection; populates `orbsym` | `None` (off) |
| `verbose` | log level (`0` quiet … `4`+ debug) | `3` |
| `max_memory` | MB PySCF may use for integrals/arrays | `4000` |
| `ecp` | effective core potential, by element | `None` |

Three equivalent ways to give the same geometry — verified to build the same
molecule (same nuclear-repulsion energy) on 2.14.0:

```python
from pyscf import gto

# 1. list-of-tuples
mol_a = gto.M(
    atom=[["O", (0.0, 0.0, 0.0)],
          ["H", (0.0, 0.757, 0.587)],
          ["H", (0.0, -0.757, 0.587)]],
    basis="sto-3g", unit="Angstrom", verbose=0,
)

# 2. semicolon-separated string
mol_b = gto.M(
    atom="O 0 0 0; H 0 0.757 0.587; H 0 -0.757 0.587",
    basis="sto-3g", unit="Angstrom", verbose=0,
)

# 3. an XYZ file on disk (atom= a path is detected and read)
with open("/tmp/_water.xyz", "w") as f:
    f.write("3\nwater\nO 0.0 0.0 0.0\nH 0.0 0.757 0.587\nH 0.0 -0.757 0.587\n")
mol_c = gto.M(atom="/tmp/_water.xyz", basis="sto-3g", verbose=0)

assert abs(mol_a.energy_nuc() - mol_b.energy_nuc()) < 1e-10
assert abs(mol_a.energy_nuc() - mol_c.energy_nuc()) < 1e-10
print("all three geometries agree:", mol_a.energy_nuc())
```

---

## 3. Mean field

`scf.RHF` / `scf.ROHF` / `scf.UHF` (import from `pyscf.scf`) and `dft.RKS`
(import from `pyscf.dft`) build the mean-field object; `.run()` or `.kernel()`
converges it.

- **`scf.RHF` is a dispatcher, not always what it says.** On 2.14.0,
  `scf.RHF(mol)` checks `mol.spin`: if it is `0` it returns a genuine
  restricted `RHF`; if it is **nonzero it silently returns an `ROHF`
  instance instead of raising**. That is convenient, but it means calling
  `scf.RHF` on an open-shell molecule never tells you that you got ROHF, not
  RHF — state plainly: **an open-shell target needs `scf.ROHF` or `scf.UHF`**,
  and call one of those explicitly rather than relying on the dispatch.
- `dft.RKS(mol, xc=...)` — same idea for restricted Kohn-Sham; default
  `xc="LDA,VWN"`.
- Convergence knobs: `conv_tol` (default `1e-9`), `max_cycle` (default `50`),
  `init_guess` (default `"minao"`).
- `.newton()` wraps the mean-field object for a second-order (Newton-Raphson)
  SCF solver — use it when the default SCF iteration stalls or oscillates.
- `.density_fit(auxbasis=None)` turns on density fitting (resolution of the
  identity) for the two-electron integrals — trades a small accuracy loss for
  much cheaper integral evaluation on larger systems.

```python
from pyscf import gto, scf

mol = gto.M(atom="O 0 0 0; O 0 0 1.2", basis="sto-3g", spin=2, verbose=0)
mf_rohf = scf.ROHF(mol).run()
mf_uhf = scf.UHF(mol).run()
print("ROHF E =", mf_rohf.e_tot)
print("UHF  E =", mf_uhf.e_tot)
print("scf.RHF on this spin=2 molecule actually returns:", type(scf.RHF(mol)).__name__)
```

---

## 4. Correlated methods and integral tools

Signature table, verified against 2.14.0 with `inspect.signature`:

```
mcscf.CASCI(mf_or_mol, ncas, nelecas, ncore=None)   # NOTE: a factory FUNCTION, not a class.
                                                     # The class is pyscf.mcscf.casci.CASCI
mcscf.CASSCF(mf_or_mol, ncas, nelecas, ncore=None, frozen=None)
  mc.kernel(mo_coeff=None, ci0=None, verbose=None)
                                        -> (e_tot, e_cas, fcivec, mo_coeff, mo_energy)
  mc.get_h1eff(mo_coeff=None, ncas=None, ncore=None) -> (h1eff, ecore)
  mc.get_h2eff(mo_coeff=None)           -> g2e         # aliases: get_h1cas, get_h2cas, h1e_for_cas
fci.FCI(mol_or_mf, mo=None, singlet=False)
cc.CCSD(mf, frozen=None, mo_coeff=None, mo_occ=None)   # .ccsd_t() for perturbative triples
mp.MP2(mf, frozen=None, mo_coeff=None, mo_occ=None)
ao2mo.kernel(eri_or_mol, mo_coeffs, erifile=None, dataname='eri_mo', intor='int2e')  # four-index transform
```

`get_h1cas`/`get_h2cas`/`h1e_for_cas` are the same computation under different
names kept for historical compatibility — verified to return identical
arrays on 2.14.0. `mc.get_h1eff()`/`mc.get_h2eff()` feeding a solver directly
(no file round-trip) is the in-memory route to block2's `DMRGDriver.get_qc_mpo`
noted in `SKILL.md`; the on-disk route is `references/fcidump.md`, and
building `ncas`/`nelecas` itself is `references/active-space.md`.

**`from pyscf import dmrgscf` fails on a clean install.** The upstream
quickstart's §13 documents `dmrgscf` as PySCF's DMRG interface, so following
that section verbatim in this harness's `.venv-pyscf` raises `ImportError` —
`dmrgscf` is a **separate package** (https://github.com/pyscf/dmrgscf), not
part of the `pyscf` distribution and not installed by `make install pyscf`.
Issue #83 deliberately routes around it: it prefers explicit integrals
(`get_h1eff`/`get_h2eff` or a FCIDUMP) handed directly to block2's
`DMRGDriver`, so that SHCI and DMRG solve the *same recorded Hamiltonian*
rather than each rebuilding it through a different interface.

```python
try:
    from pyscf import dmrgscf
    print("dmrgscf imported (unexpected — check the environment)")
except ImportError as e:
    print("dmrgscf is a separate package, not installed here:", e)
```

---

## 5. Worked examples (verbatim)

### 5.1 The water anchor (from `SKILL.md`)

Source: harness-verified, Hirata & Bartlett, Chem. Phys. Lett. 321, 216
(2000), Table 2 caption.

```python
import numpy as np
from pyscf import gto, scf, mcscf

r, ang = 0.967, 107.6                      # Hirata 2000 water geometry
h = np.deg2rad(ang / 2.0)
mol = gto.M(
    atom=[["O", (0.0, 0.0, 0.0)],
          ["H", (0.0,  r * np.sin(h), r * np.cos(h))],
          ["H", (0.0, -r * np.sin(h), r * np.cos(h))]],
    basis="6-31G", unit="Angstrom", verbose=0,
)
mf = scf.RHF(mol).run()                    # E(HF)  = −75.984503 Ha
ncore = 1                                  # frozen oxygen 1s
mc = mcscf.CASCI(mf, mol.nao - ncore, mol.nelectron - 2 * ncore)
e_fci = mc.kernel()[0]                     # E(FCI) = −76.121174 Ha, CAS(8,12), 245 025 dets
print("E(HF)  =", mf.e_tot)
print("E(FCI) =", e_fci)
```

### 5.2 Upstream SCF example (`examples/scf/00-simple_hf.py`)

Source: https://github.com/pyscf/pyscf/tree/master/examples/scf

```python
#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

'''
A simple example to run HF calculation.

.kernel() function is the simple way to call HF driver.
.analyze() function calls the Mulliken population analysis etc.
'''

import pyscf

mol = pyscf.M(
    atom = 'H 0 0 0; F 0 0 1.1',  # in Angstrom
    basis = 'ccpvdz',
    symmetry = True,
)

myhf = mol.HF()
myhf.kernel()

# Orbital energies, Mulliken population etc.
myhf.analyze()


#
# myhf object can also be created using the APIs of gto, scf module
#
from pyscf import gto, scf
mol = gto.M(
    atom = 'H 0 0 0; F 0 0 1.1',  # in Angstrom
    basis = 'ccpvdz',
    symmetry = True,
)
myhf = scf.HF(mol)
myhf.kernel()
```

### 5.3 Upstream CASCI example (`examples/mcscf/00-simple_casci.py`)

Source: https://github.com/pyscf/pyscf/tree/master/examples/mcscf

```python
#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

'''
A simple example to run CASCI calculation.
'''

import pyscf

mol = pyscf.M(
    atom = 'O 0 0 0; O 0 0 1.2',
    basis = 'ccpvdz',
    spin = 2)

myhf = mol.RHF().run()

# 6 orbitals, 8 electrons
mycas = myhf.CASCI(6, 8).run()
#
# Note this mycas object can also be created using the APIs of mcscf module:
#
# from pyscf import mcscf
# mycas = mcscf.CASCI(myhf, 6, 8).run()

# Natural occupancy in CAS space, Mulliken population etc.
mycas.verbose = 4
mycas.analyze()
```

---

## 6. Pitfalls

- **Mulliken vs Dirac ordering.** `(pq|rs) = ⟨pr|qs⟩` — building integrals or
  a FCIDUMP with the wrong convention assembles a different, still-Hermitian
  Hamiltonian that runs without error. See §1 and `references/fcidump.md`.
- **`mol.spin` is 2S, not S.** Singlet `spin=0`, doublet `spin=1`, triplet
  `spin=2`. A silent off-by-factor-of-2 here still builds *a* molecule, just
  the wrong multiplicity.
- **Unit default.** `gto.M(atom=...)` interprets coordinates in **Angstrom**
  unless `unit="Bohr"` is given — this default matches the harness convention,
  but a geometry pasted from a Bohr-unit source will silently give a
  plausible, wrong energy if `unit` is left unset.
- **A loose SCF poisons every downstream number.** `conv_tol` defaults to
  `1e-9`; for integrals or FCIDUMPs meant to be re-consumed elsewhere, tighten
  it (e.g. `1e-10`) before exporting anything — CASCI/CASSCF, CCSD, and any
  FCIDUMP built on top inherit the SCF orbitals' error.
- **`scf.RHF` silently becomes `ROHF` on an open-shell molecule** rather than
  raising (§3, verified on 2.14.0). If you need genuine RHF-only behavior
  (e.g. to assert the molecule is closed-shell), check `mol.spin == 0`
  yourself rather than trusting `scf.RHF` to enforce it.
- **`mcscf.CASCI` is a factory function, not a class.** `isinstance(obj,
  mcscf.CASCI)` raises `TypeError` (`isinstance() arg 2 must be a type, a
  tuple of types, or a union`) — verified on 2.14.0. Check against
  `pyscf.mcscf.casci.CASCI` (or `pyscf.mcscf.mc1step.CASSCF`) instead, or
  duck-type on `hasattr(obj, "get_h1eff")`.
- **`dmrgscf` is not bundled.** `make install pyscf` installs `pyscf` +
  `block2` (via `pyblock2`) + `geometric`, not the separate `dmrgscf`
  interface package that upstream quickstart §13 describes. Use `pyblock2`'s
  `DMRGDriver` directly, fed by `get_h1eff`/`get_h2eff` or a FCIDUMP (§4).
- **`block2` has no `__version__`.** `import block2; block2.__version__` does
  not exist on 0.5.3. Record the resolved version for the run manifest with
  `importlib.metadata.version("block2")` instead.

```python
from pyscf import gto, scf, mcscf
mol = gto.M(atom="O 0 0 0; H 0 0.757 0.587; H 0 -0.757 0.587", basis="sto-3g", verbose=0)
mc = mcscf.CASCI(scf.RHF(mol).run(), 4, 4)
try:
    isinstance(mc, mcscf.CASCI)
except TypeError as e:
    print("isinstance against mcscf.CASCI raises:", e)

import importlib.metadata
print("block2 version (via importlib.metadata):", importlib.metadata.version("block2"))
```

---

## 7. Source links

- Quickstart: https://pyscf.org/quickstart.html
- Homepage / docs: https://pyscf.org/
- Install: https://pyscf.org/user/install.html
- User guide index: https://pyscf.org/user/index.html
- Molecules (`gto`): https://pyscf.org/user/gto.html
- Mean field (`scf`): https://pyscf.org/user/scf.html
- MCSCF / CASSCF: https://pyscf.org/user/mcscf.html
- CI / FCI: https://pyscf.org/user/ci.html
- Coupled cluster: https://pyscf.org/user/cc.html
- Orbital localization: https://pyscf.org/user/lo.html
- Geometry optimization: https://pyscf.org/user/geomopt.html
- Periodic (pbc): https://pyscf.org/user/pbc.html
- Full API docs: https://pyscf.org/pyscf_api_docs/pyscf.html
- `pyscf.tools` API: https://pyscf.org/pyscf_api_docs/pyscf.tools.html
- `pyscf.mcscf` API: https://pyscf.org/pyscf_api_docs/pyscf.mcscf.html
- Examples index: https://github.com/pyscf/pyscf/tree/master/examples
- SCF examples (used in §5.2): https://github.com/pyscf/pyscf/tree/master/examples/scf
- MCSCF examples (used in §5.3): https://github.com/pyscf/pyscf/tree/master/examples/mcscf
- `dmrgscf` (separate package, not installed here): https://github.com/pyscf/dmrgscf
- Source: https://github.com/pyscf/pyscf
- Paper: Sun et al., WIREs Comput. Mol. Sci. 8, e1340 (2018)
