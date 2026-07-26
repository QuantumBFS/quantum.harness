# FCIDUMP: export, format, and the frozen-core trap

> Exercised by: issues #83 and #129. No upstream quickstart section covers
> FCIDUMP export — this file has no upstream equivalent to defer to.
> Examples: https://github.com/pyscf/pyscf/tree/master/examples/tools

FCIDUMP is a plain-text file format that records a molecular Hamiltonian in
second-quantized form: the one- and two-electron integrals in an orbital
basis, plus a header giving the orbital count, electron count, spin, and
symmetry. It is the shared record both harness challenges depend on: #129
grades a Rust parser against its grammar, and #83 uses it as the Hamiltonian
an independent solver (DMRG, SHCI, ED) can check against another solver's
in-memory route. `references/pyscf-api.md` §4 owns the general
`mcscf`/`cc`/`fci` API surface this file builds on; this file owns the
on-disk FCIDUMP format and the `pyscf.tools.fcidump` module specifically.

---

## 1. The eleven entry points

Verified against PySCF 2.14.0 with `inspect.signature`; every name below
exists in `dir(pyscf.tools.fcidump)`.

```python
from pyscf.tools import fcidump

fcidump.from_scf(mf, filename, tol=1e-15, float_format=' %.16g', molpro_orbsym=False)
fcidump.from_mo(mol, filename, mo_coeff, orbsym=None, tol=1e-15, float_format=' %.16g', molpro_orbsym=False, ms=0)
fcidump.from_mcscf(mc, filename, tol=1e-15, float_format=' %.16g', molpro_orbsym=False)
fcidump.from_integrals(filename, h1e, h2e, nmo, nelec, nuc=0, ms=0, orbsym=None, tol=1e-15, float_format=' %.16g')
fcidump.from_chkfile(filename, chkfile, tol=1e-15, float_format=' %.16g', molpro_orbsym=False, orbsym=None)
fcidump.read(filename, molpro_orbsym=False, verbose=True)
fcidump.to_scf(filename, molpro_orbsym=False, mf=None, **kwargs)
fcidump.scf_from_fcidump(mf, filename, molpro_orbsym=False)
fcidump.write_head(fout, nmo, nelec, ms=0, orbsym=None)
fcidump.write_hcore(fout, h, nmo, tol=1e-15, float_format=' %.16g')
fcidump.write_eri(fout, eri, nmo, tol=1e-15, float_format=' %.16g')
```

The first five (`from_*`) write a complete FCIDUMP from a different starting
object. `read`/`to_scf`/`scf_from_fcidump` are the reverse direction — file
back into arrays or into a mean-field object. `write_head`/`write_hcore`/
`write_eri` are the low-level pieces the `from_*` functions call internally;
reach for them only when assembling a FCIDUMP from integrals that do not fit
one of the `from_*` shapes.

**Which one to use:**

| Goal | Call |
|---|---|
| Full MO space from a converged SCF | `from_scf(mf, "FCIDUMP")` |
| Active space from a CASCI/CASSCF object | `from_mcscf(mc, "FCIDUMP")` |
| Integrals you built yourself (custom `h1e`/`h2e`) | `from_integrals(filename, h1e, h2e, nmo, nelec)` |
| Read one back into arrays | `read(filename)` |
| Read one back into a mean-field object | `to_scf(filename)` |

---

## 2. The frozen-core trap — the most important thing in this file

`from_scf` writes the **full** MO space — every orbital SCF produced, with
**every** electron in `NELEC`. It does not know about, and cannot record, a
frozen core: freezing is a *solver-level* choice (`mcscf.CASCI(ncore=...)`,
`cc.CCSD(frozen=...)`), applied after the FCIDUMP already exists.

Verified on 2.14.0: exporting the water/6-31G anchor from `references/pyscf-api.md`
§5.1 with plain `fcidump.from_scf(mf, "FCIDUMP.water")` produces:

```
&FCI NORB=  13,NELEC=10,MS2=0,
 ORBSYM=1,1,1,1,1,1,1,1,1,1,1,1,1,
 ISYM=1,
```

`NORB=13` is all 13 basis functions of 6-31G water; `NELEC=10` is *all ten*
electrons, oxygen 1s included. There is no frozen core anywhere in this
header or in this file.

But the published −76.121174 Ha for this system (`references/pyscf-api.md`
§5.1, Hirata & Bartlett 2000) is a **frozen-core** number: CAS(8,12) with the
oxygen 1s orbital frozen (`ncore=1`). The freeze happens inside
`mcscf.CASCI`, never touching the FCIDUMP. A consumer who reads
`FCIDUMP.water`, sees `NELEC=10`, and correlates all ten electrons is not
misreading the file — they are correctly reproducing a *different* physical
calculation (all-electron FCI, not frozen-core FCI-in-CAS), and will get a
different, still-correct energy for that different problem.

**Consequence: state the frozen-core convention alongside every FCIDUMP you
ship.** The file alone does not carry it. Two ways to be explicit:

- Put the freeze in the file itself: build `mcscf.CASCI(mf, ncas, nelecas,
  ncore=1)` and export with `from_mcscf(mc, "FCIDUMP")` instead of
  `from_scf`. The resulting header's `NORB`/`NELEC` then already reflect the
  active space, and no separate convention statement travels with the file.
- Or keep `from_scf`'s full-space file and record `ncore` (and which
  orbitals) as metadata alongside it — in the run manifest, a comment, or a
  paired JSON record — so a downstream solver knows what to freeze.

Building the active space itself (which orbitals, `ncas`/`nelecas`) is
`references/active-space.md`; this file only covers what does or does not
end up recorded in the FCIDUMP.

---

## 3. Format facts (#129 grades a parser against these)

- **Mulliken `(pq|rs)` ordering** for the two-electron block — not Dirac
  `⟨pq|rs⟩`. See `references/pyscf-api.md` §1 for the index-swap relation
  `(pq|rs) = ⟨pr|qs⟩`.
- **8-fold permutation symmetry**: only symmetry-unique integrals are
  written, one line per unique `(pq|rs)`.
- **1-based orbital indices** in the integral lines, not 0-based.
- **Spatial orbitals**, not spin-orbitals — `NORB` counts spatial MOs; a
  closed-shell determinant places two electrons (α and β) per occupied
  spatial orbital.
- **Header keys**: `NORB`, `NELEC`, `MS2` (2×Sz, matching the `mol.spin`
  convention in `references/pyscf-api.md` §1), `ORBSYM` (one entry per
  orbital, irrep labels or all-`1` with symmetry off), `ISYM`.

Rather than paraphrase the exact grammar (namelist syntax, integral-line
layout, the core-energy sentinel line `0 0 0 0`), point a parser at the
source: `pyscf/tools/fcidump.py`,
https://github.com/pyscf/pyscf/blob/master/pyscf/tools/fcidump.py —
`write_head`, `write_hcore`, and `write_eri` are the three functions that
emit every line in the file.

---

## 4. Worked example

Full-space FCIDUMP for H₂/STO-3G, plus the reference energies #129's Level 0
asks for as a JSON oracle.

Source: harness-verified against PySCF 2.14.0 in this repository's
`.venv-pyscf`.

```python
import json
from pyscf import gto, scf, cc, mcscf
from pyscf.tools import fcidump

mol = gto.M(atom="H 0 0 0; H 0 0 0.74", basis="sto-3g", unit="Angstrom", verbose=0)
mf = scf.RHF(mol).run()
fcidump.from_scf(mf, "FCIDUMP.h2", tol=1e-12)
ref = {"e_hf": float(mf.e_tot),
       "e_ccsd": float(cc.CCSD(mf).run().e_tot),
       "e_fci": float(mcscf.CASCI(mf, mol.nao, mol.nelectron).kernel()[0]),
       "pyscf_version": __import__("pyscf").__version__}
json.dump(ref, open("reference.json", "w"), indent=2)
```

Verified output on 2.14.0. `FCIDUMP.h2` begins:

```
 &FCI NORB=   2,NELEC= 2,MS2=0,
  ORBSYM=1,1,
  ISYM=1,
```

and `reference.json`:

```json
{
  "e_hf": -1.1167593073964253,
  "e_ccsd": -1.1372839986104397,
  "e_fci": -1.1372838344885023,
  "pyscf_version": "2.14.0"
}
```

H₂/STO-3G has only 2 electrons in 2 orbitals, so there is no frozen core to
worry about here — `NELEC=2` is the whole system. The trap in §2 appears only
once there are core orbitals to freeze, as in the water anchor.

---

## 5. The in-memory alternative

When the consumer is block2 in the same interpreter, a round-trip through
disk is unnecessary — feed `mcscf`'s effective integrals straight into
`DMRGDriver.get_qc_mpo`:

```python
h1eff, ecore = mc.get_h1eff()
g2e = mc.get_h2eff()

from pyblock2.driver.core import DMRGDriver
mpo = driver.get_qc_mpo(h1e=h1eff, g2e=g2e, ecore=ecore)
```

Verified against block2 0.5.3: `DMRGDriver.get_qc_mpo(self, h1e, g2e,
ecore=0.0, ...)` accepts `h1e`/`g2e`/`ecore` positionally or by keyword, so
`mc.get_h1eff() -> (h1eff, ecore)` and `mc.get_h2eff() -> g2e` feed it
directly with no file in between.

**Write the FCIDUMP anyway as the shared record.** Even when one solver
consumes the Hamiltonian in memory, the FCIDUMP is what lets an independent
solver — a different DMRG run, an SHCI code, a hand-rolled ED — check that it
is solving the *same* Hamiltonian, not a re-derivation of it through a
different interface. This is the point of issue #83: two solvers agreeing on
an energy is only meaningful if they agreed on the file first.

---

## 6. Source links

- `pyscf.tools` API: https://pyscf.org/pyscf_api_docs/pyscf.tools.html
- Tools examples (`examples/tools`, includes FCIDUMP round-trips):
  https://github.com/pyscf/pyscf/tree/master/examples/tools
- Source of truth for the grammar: `pyscf/tools/fcidump.py` in
  https://github.com/pyscf/pyscf
- MCSCF / active-space integrals: `references/pyscf-api.md` §4,
  `references/active-space.md`
