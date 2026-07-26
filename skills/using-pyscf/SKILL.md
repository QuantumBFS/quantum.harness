---
name: using-pyscf
description: Use when a calculation needs molecular electronic-structure input or reference numbers from PySCF — one- and two-electron integrals, a FCIDUMP file, an active space (AVAS, PiOS, APC, DMET or localized orbitals), HF/DFT orbitals, or reference HF/FCI/CCSD/CASCI energies as an oracle. Also covers PySCF's DFT, geometry optimization and periodic (pbc) modules, and PySCF setup failures. Triggers on "FCIDUMP", "molecular integrals", "active space", "CAS(n,m)", "reference FCI energy", "quantum chemistry input for DMRG or ED", "PySCF".
---

# PySCF

PySCF produces the **molecular electronic Hamiltonian and the trusted reference
numbers** — integrals, FCIDUMP files, active spaces, and small-scale
HF/FCI/CCSD/CASCI energies. It is not the solver. Method judgment (which
method, which sectors, how large) belongs to the method cards; DMRG convergence
belongs to `/method-mps`. This skill owns expressing a chemistry setup in PySCF
and the package-level values.

## Sources

- Stack contract: `skills/using-pyscf/stack.toml`
- Install target: `make install pyscf` (isolated `.venv-pyscf`, Python 3.13)
- Smoke test: `.venv-pyscf/bin/python -c 'import pyscf; from pyblock2.driver.core import DMRGDriver; print(pyscf.__version__, "block2 OK")'`
- API + examples reference: `references/pyscf-api.md`
- FCIDUMP format and conventions: `references/fcidump.md`
- Active-space construction: `references/active-space.md`
- DFT and geometry optimization: `references/dft-geometry.md`
- Periodic systems: `references/periodic.md`
- Upstream quickstart (start here): https://pyscf.org/quickstart.html

## Workflow

Branch by the object you need, not by a fixed pipeline — different callers enter
the same machinery and leave with different deliverables.

| You need | Route |
|---|---|
| Full-space FCIDUMP + reference energies (an oracle) | `gto.M` → `scf.RHF` → `tools.fcidump.from_scf` → `fci` / `cc` for reference numbers |
| Active-space Hamiltonian on disk | build the space (`references/active-space.md`) → `mcscf.CASCI` → `tools.fcidump.from_mcscf` |
| Active-space Hamiltonian in memory, for block2 | `mc.get_h1eff() → (h1eff, ecore)`, `mc.get_h2eff() → g2e` → `DMRGDriver.get_qc_mpo(h1e, g2e, ecore)` |
| Orbitals, a geometry, or a DFT energy | `references/dft-geometry.md` |

Whichever branch you take, record in the run manifest: basis, `ncore`, `ncas`,
`nelecas`, charge and spin, the SCF energy, and the resolved package versions
(`pyscf.__version__` and the `uv pip list` line for block2). Versions float by
design, so the manifest is the only record of what actually ran.

**Confirm the setup before computing** (AGENTS.md:21): state the geometry source,
basis, charge, spin, frozen shells and active space, and get an explicit
confirm-or-correct. A chemistry setup that looks obvious usually encodes a silent
assumption — a unit, a spin convention, a frozen core.

## Parameter setup

- **Geometry and units.** `gto.M(atom=…, unit="Angstrom")`. State the unit
  explicitly; a geometry silently interpreted in Bohr gives a plausible, wrong
  energy.
- **Spin.** `mol.spin` is **2S — the number of unpaired electrons**, not S. A
  singlet is `spin=0`, a triplet `spin=2`. For an open shell choose `scf.ROHF`
  or `scf.UHF`; `scf.RHF` cannot represent it.
- **Frozen shells.** `ncore` in `mcscf.CASCI`, `frozen=` in `cc.CCSD`. These are
  independent of what a FCIDUMP contains — see `references/fcidump.md`.
- **Integral index ordering.** PySCF uses Mulliken `(pq|rs)`; much of many-body
  physics uses Dirac `⟨pq|rs⟩`. They differ by an index swap. Fix the convention
  before writing anything that touches integrals.
- **Symmetry.** `symmetry=True` enables point-group detection, populates
  `orbsym`, and lets you select orbitals by irrep. Use it when degeneracies are
  a physical check; disable it for a clean baseline.

## Knobs

Package-level values only; which values a given calculation needs is the method
card's call.

| Knob | Effect | Starting point |
|---|---|---|
| `basis` | the one-particle space; everything downstream scales off it | `6-31G` to reproduce the anchor below; `def2-SVP` / `cc-pVDZ` for larger systems |
| `symmetry` | point-group detection, `orbsym` in the FCIDUMP | `True` when degeneracies are a check |
| `spin` | 2S, unpaired electrons | `0` singlet, `2` triplet — for a singlet–triplet gap use **the same orbitals and ordering** for both sectors, or the error cancellation is lost |
| `conv_tol` (SCF) | SCF convergence | `1e-10` before exporting integrals; a loose SCF silently poisons every downstream number |
| `ncore` | frozen shells | `1` for water's O 1s |
| `max_memory` | MB PySCF may use | set explicitly; the 4000 MB default is rarely right for the machine |
| `tol` (fcidump) | integral write threshold | `1e-15` default |
| `verbose` | log level | `4` while debugging, `0` in scripts |

## Code shape

Verified against PySCF 2.14.0; reproduces the published FCI energy of Hirata &
Bartlett 2000 (Table 2 caption) in about six seconds.

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
```

**Verification step.** Reproducing −76.121174 Ha to ~1e-6 exercises the whole
spine — molecule input, SCF, integral transform, CI solver — against a published
number. Run it after any environment change before trusting a new result.

## Time estimate

- The anchor above: ~6 s total on a laptop (245 025 determinants).
- The four-index AO→MO transform scales as O(N⁵) in basis functions and usually
  dominates setup; `max_memory` decides whether it stays in core.
- FCI is limited by determinant count, roughly `C(ncas, nelecas/2)²`. Past
  ~18–20 active orbitals, FCI is out and the route is DMRG or selected CI.
- For both current challenges PySCF is never the bottleneck — it is the
  provider. Budget the solver, not this.

## Use Another Route When

- The Hamiltonian is a **lattice model** — PySCF is molecular. Use `/method-ed`,
  `/using-xdiag`, `/using-quspin`.
- The question is **DMRG convergence** (bond-dimension ramp, orbital ordering,
  discarded-weight extrapolation) — `/method-mps`.
- **Plane-wave periodic solids** — `/using-quantum-espresso` owns that path.
  PySCF's `pbc` module overlaps and is the unexercised route here.
- The **method choice itself** is still open — that belongs to a method card.
