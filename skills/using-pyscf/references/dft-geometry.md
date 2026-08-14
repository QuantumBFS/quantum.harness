# DFT and geometry optimization

> Reference only — not exercised by any current challenge. Builds on quickstart
> §3 (Kohn-Sham DFT) and §14 (geometry optimization) —
> https://pyscf.org/quickstart.html
> User guide: https://pyscf.org/user/geomopt.html
> Examples: https://github.com/pyscf/pyscf/tree/master/examples/geomopt

## 1. Kohn-Sham DFT

`dft.RKS` / `dft.UKS` / `dft.ROKS` (import from `pyscf.dft`) mirror
`scf.RHF`/`UHF`/`ROHF`: build the molecule, wrap it in the KS object, set `xc`,
call `.kernel()` or `.run()`.

```python
from pyscf import gto, dft

mol = gto.M(atom="O 0 0 0; H 0 0.757 0.587; H 0 -0.757 0.587",
            basis="6-31g", verbose=0)
mf = dft.RKS(mol)
mf.xc = "b3lyp"
mf.kernel()
```

Verified on 2.14.0: `E(RKS/b3lyp) = -76.38494654 Ha` for this geometry/basis,
with the default numerical-integration grid (`mf.grids.level == 3`).

- `xc` takes a shorthand functional name (`"b3lyp"`, `"pbe"`, `"pbe0"`,
  `"m06"`, ...) or an explicit `"x,c"` pair (`"b88,lyp"`); see
  `pyscf/dft/libxc.py` for the full table.
- `mf.grids.level` (integer `0`-`9`, default `3`) trades grid density for
  cost; raise it when a DFT energy needs to be converged tightly, not just
  compared qualitatively.
- `.density_fit()` works on KS objects the same way it does on `scf.RHF` —
  resolution-of-identity two-electron integrals, cheaper at some accuracy
  cost.
- **`pyscf.dft` needs nothing beyond the base install** — libxc is bundled
  with `pyscf`, so no separate functional library has to be installed or
  configured.

## 2. Geometry optimization — `pyscf.geomopt` ships only wrappers

`pyscf.geomopt` does not implement an optimizer itself; each submodule wraps a
separate third-party package and needs that package importable. Verified in
this harness's `.venv-pyscf` (pyscf 2.14.0):

```
pyscf.geomopt.geometric_solver  -> OK        (geometric 1.1.1 present)
pyscf.geomopt.berny_solver      -> ImportError: No module named 'berny'
pyscf.geomopt.ase_solver        -> ImportError: No module named 'ase'
```

`make install pyscf` installs `geometric` alongside `pyscf` and `block2`, so
the geomeTRIC route works out of the box in `.venv-pyscf`; `pyberny` and ASE
do not, and need `uv pip install pyberny` / `uv pip install ase` before
`berny_solver` / `ase_solver` will import.

```python
from pyscf import gto, scf
from pyscf.geomopt.geometric_solver import optimize

mol = gto.M(atom="N 0 0 0; N 0 0 1.2", basis="ccpvdz", verbose=0)
mf = scf.RHF(mol)
mol_eq = optimize(mf, maxsteps=50)
```

Verified on 2.14.0/geometric 1.1.1: converges in 5 macro steps to an N-N bond
length of 1.0773 Å (RHF/cc-pVDZ). `optimize()` accepts any mean-field or
CASCI/CASSCF object with a `.Gradients()` method; the equivalent call via the
gradients API is `mf.Gradients().optimizer(solver="geomeTRIC").kernel()`.

## 3. Fullerene geometries (#83) are not optimized here

For issue #83, the fullerene cage geometries come from the Liu 2024
supplementary data, not from a `geomopt` run in this harness. Fix one
geometry per cage, commit it as an XYZ file, and reuse that same file for
every solver (AVAS, PiOS, APC, ...) and both spin states being compared — a
geometry re-optimized per solver would confound the comparison the challenge
is actually asking for. `pyscf.geomopt` above is documented for cases that do
need an in-harness optimization; #83 is not one of them.

---

## Source links

- Quickstart: https://pyscf.org/quickstart.html
- Geometry optimization user guide: https://pyscf.org/user/geomopt.html
- DFT examples: https://github.com/pyscf/pyscf/tree/master/examples/dft
- Geomopt examples: https://github.com/pyscf/pyscf/tree/master/examples/geomopt
- Install: https://pyscf.org/user/install.html
- Active-space construction (#83 route comparison): `references/active-space.md`
