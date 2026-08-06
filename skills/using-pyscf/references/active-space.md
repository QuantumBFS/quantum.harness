# Active-space construction

> Exercised by: issue #83. Builds on quickstart §5 (localization) and §12
> (CASCI/CASSCF) — https://pyscf.org/quickstart.html. This file adds the
> route comparison and the curved-cage case.
> Examples: https://github.com/pyscf/pyscf/tree/master/examples/mcscf and
> https://github.com/pyscf/pyscf/tree/master/examples/local_orb

**What an active space is.** A subset of orbitals and electrons correlated
exactly while the rest stay frozen (doubly occupied) or empty. `CAS(n,m)` means
n electrons in m orbitals; the FCI dimension inside it is about `C(m, n/2)²`.
Every route below is a **unitary rotation within the occupied space and,
separately, within the virtual space** — so the HF determinant, and the HF
energy, are unchanged. You are re-expressing the reference, not changing it.

`references/pyscf-api.md` §4 owns the general `mcscf` API (`CASCI`/`CASSCF`,
`get_h1eff`/`get_h2eff`); `references/fcidump.md` owns writing the resulting
space to disk (`from_mcscf`). This file owns only how `ncas`/`nelecas` and the
orbital coefficients get chosen in the first place.

---

## 1. The nine routes

All verified importable in PySCF 2.14.0 (`.venv-pyscf`); signatures verified
with `inspect.signature`.

| Route | API | Selection |
|---|---|---|
| Atomic valence projection | `mcscf.avas.avas(mf, aolabels, threshold=0.2, minao='minao', with_iao=False, openshell_option=2, canonicalize=True, ncore=0, verbose=None)` | automatic, σ ≥ threshold |
| π-orbital space | `mcscf.PiOS.MakePiOS(mol, mf, PiAtomsList, nPiOcc=None, nPiVirt=None)` | automatic from a π-atom list |
| Ranked orbital (APC) | `mcscf.apc.APC(mf, max_size=(8,8), n=2, fixed=False, eps=0.001, verbose=4)`, `.kernel()`; `apc.Chooser` | automatic, size-targeted, by orbital entropy |
| DMET bath | `mcscf.dmet_cas.dmet_cas(mf, dm, aolabels_or_baslst, threshold=0.05, ...)`; `guess_cas`, `search_for_degeneracy`, `symmetrize` | automatic around chosen atoms |
| Localize then pick | `lo.Boys`, `lo.PipekMezey`, `lo.EdmistonRuedenberg`, `lo.iao`, `lo.ibo` | manual, per-atom criterion |
| Correlated natural orbitals | `mcscf.addons.make_natural_orbitals(method_obj)` (MP2 or CCSD), `addons.cas_natorb(casscf, mo_coeff=None, ci=None, sort=False)` | by occupation number |
| By symmetry | `addons.sort_mo_by_irrep`, `addons.caslst_by_irrep`, `addons.select_mo_by_irrep` | by irrep counts |
| By index | `addons.sort_mo(casscf, mo_coeff, caslst, base=1)` | fully manual (**`base=1`**: 1-indexed by default) |
| Inherit from a smaller run | `addons.project_init_guess(casscf, mo_init, prev_mol=None, priority=None, use_hf_core=None)` | reuse |

**The `base=1` trap is not unique to `sort_mo`.** `caslst_by_irrep` and
`select_mo_by_irrep` also default to `base=1` (verified on 2.14.0) — every
index-based selector in `addons` is 1-indexed unless told otherwise. Passing a
0-based Python index straight in silently selects the orbital one below the
intended one; nothing raises.

**`avas.avas` returns a 3-tuple** — `(ncas, nelecas, mo_coeff)` — not the σ
weights. To read the σ spectrum (§2), construct `avas.AVAS(mf, aolabels,
...)` and call its `.kernel()` directly; the instance then exposes
`.occ_weights` and `.vir_weights` after the call. The module-level
`avas.avas(...)` convenience function discards them.

---

## 2. AVAS in detail

It builds the projector onto AO-labelled target orbitals from a minimal
reference basis, then diagonalizes that projector **separately in the
occupied and virtual blocks** — verified in `pyscf/mcscf/avas.py`:

```python
# avas.py:138 (occupied block)
wocc, u = numpy.linalg.eigh(sa[:(nocc-ncore), :(nocc-ncore)])
# avas.py:145 (virtual block)
wvir, u = numpy.linalg.eigh(sa[(nocc-ncore):, (nocc-ncore):])
```

Each eigenvalue σ ∈ [0,1] is the fraction of that rotated orbital lying in the
target AO space; σ ≥ `threshold` selects it. Because the two blocks are
diagonalized independently, the occupied-manifold and virtual-manifold
subspaces spanned before AVAS runs are each preserved — the union of the new
occupied-block orbitals still spans exactly the old occupied space, likewise
for virtual. That is *why* the HF determinant, and so the HF energy, is
provably unchanged (§4): AVAS only rotates a basis within each block, it never
mixes occupied into virtual.

`aolabels` is a string or list of strings — **AO labels only** (e.g. `'C
2pz'`, `['Fe 3d', 'Fe 4s']`). A label names an AO by element and shell; it
cannot express an arbitrary direction. That is exactly the limitation §3
below runs into.

**AVAS is not localization.** Localization (`lo.Boys` etc.) optimizes a
locality functional and leaves selection to you; AVAS declares a target
subspace and selects automatically, and ships a diagnostic — the σ spectrum —
that localization has no analogue for.

---

## 3. The curved-cage case (#83)

On a fullerene the σ–π separation is not exact: curvature pyramidalizes each
carbon, so each atom's π direction is its own radial axis and no global
z-axis exists. A label like `'C 2pz'` is meaningless on a cage — there is no
single z that is "the π direction" for every atom at once, and `aolabels`
cannot encode a per-atom direction anyway (§2). Three routes:

1. **Hand-built directed reference orbitals, projected manually** — the route
   #83 describes. Construct a per-atom p-like reference vector along each
   carbon's local radial axis (e.g. from the vector connecting the atom to
   the cage centroid), then project the HF orbitals onto that reference set
   the way AVAS projects onto AO labels, but with a direction AVAS cannot
   express.
2. **`mcscf.PiOS.MakePiOS`**, which derives per-atom p axes itself via its
   `GetPzOrientation` and `MakePzMinaoVectors` helpers (both present in
   `pyscf.mcscf.PiOS` on 2.14.0). It was developed and validated for
   conjugated planar/near-planar systems (Sayfutyarova & Hammes-Schiffer,
   J. Chem. Theory Comput. 15, 1679 (2019)) — **its behaviour on a closed
   curved cage is untested**. Do not assume it works or that it fails;
   verify before trusting a fullerene result built on it, and either outcome
   (it generalizes / it breaks down) is a reportable result for #83.
3. **Localize occupied and virtual separately** (`lo.Boys` or
   `lo.PipekMezey` on each block independently, matching AVAS's occ/virtual
   split in §2), **then keep the most radial orbital per carbon** by
   projecting each localized orbital's dipole or centroid onto that atom's
   radial axis. The axis enters only in this final selection step, not in
   the localization itself.

Because the σ/occ-virtual framework in §2 is frozen (the diagnostic still
applies), this choice moves the *correlated* (CASCI/DMRG) energy, not just
the representation — the
three routes above can select different orbitals for the same cage, and each
choice is a different physical active space. Report the construction actually
used and its effect on the energy, not just the final number.

---

## 4. Diagnostics that apply to every route

- **HF energy unchanged by the rotation and freeze** — if it moves, the space
  is not a valid partition of the reference (occupied mixed with virtual, or
  a determinant that was never re-derived from the same density). This is
  the single most useful check and applies identically to all nine routes,
  since every one is occ-block/vir-block unitary (§2).
- **Orbital count matches intent** — one per atom, where that is the intent
  (e.g. one π orbital per carbon on a cage).
- **Degeneracies consistent with the point group** — an active space that
  splits a symmetry-required degeneracy usually means the rotation broke a
  symmetry the construction should have respected.
- **Where a σ spectrum exists** (AVAS, and the projection in curved-cage
  route 1), a clean gap between kept and discarded orbitals. A smeared
  spectrum means the separation is failing — report it rather than raising
  `threshold` until the count looks right; a forced count on a smeared
  spectrum hides the physics, it does not fix it.
- **A cheap CASCI on a small subspace is an exact check** a larger solver
  (DMRG, SHCI) must reproduce — run it before trusting the large calculation.

---

## 5. Worked example

AVAS on ethylene (C₂H₄, planar π system), 6-31G, showing the σ spectrum, the
`(ncas, nelecas)` handoff, and the HF-invariance diagnostic recomputed
explicitly from the rotated density matrix (not just read off `mf.e_tot`,
which the construction never touches).

Source: harness-verified against PySCF 2.14.0 in `.venv-pyscf`; pattern from
`examples/mcscf` (AVAS usage) and the AVAS docstring's own Cr₂ example.

```python
import numpy as np
from pyscf import gto, scf, mcscf
from pyscf.mcscf import avas

mol = gto.M(
    atom="""
    C  0.0000  0.0000  0.0000
    C  1.3300  0.0000  0.0000
    H -0.5800  0.9400  0.0000
    H -0.5800 -0.9400  0.0000
    H  1.9100  0.9400  0.0000
    H  1.9100 -0.9400  0.0000
    """,
    basis="6-31g", unit="Angstrom", verbose=0,
)
mf = scf.RHF(mol).run()
e_hf_before = mf.e_tot

# Construct the AVAS object directly (not the avas.avas() convenience
# function) to keep the sigma spectrum on avas_obj.occ_weights/.vir_weights.
avas_obj = avas.AVAS(mf, "C 2pz", threshold=0.2)
ncas, nelecas, mo = avas_obj.kernel()
print("sigma, occupied block:", avas_obj.occ_weights)
print("sigma, virtual block :", avas_obj.vir_weights)
print("(ncas, nelecas) =", (ncas, nelecas))

# HF-invariance diagnostic (Section 4): rebuild the HF energy from the
# ROTATED orbitals' density matrix and confirm it against the untouched one.
nocc = mol.nelectron // 2
dm_rotated = 2 * mo[:, :nocc].dot(mo[:, :nocc].T)
e_hf_rotated = mf.energy_tot(dm=dm_rotated)
print("E(HF) original          :", e_hf_before)
print("E(HF) from rotated basis:", e_hf_rotated)
print("abs diff                :", abs(e_hf_before - e_hf_rotated))

mc = mcscf.CASCI(mf, ncas, nelecas)
mc.kernel(mo)
print("E(CASCI) =", mc.e_tot)
```

Verified output on 2.14.0:

```
sigma, occupied block: [~0, ~0, ~0, ~0, ~0, ~0, ~0, 0.9977]
sigma, virtual block : [0.9990, ~0, ..., ~0, 9.2e-05]
(ncas, nelecas) = (2, 2)
E(HF) original          : -78.00179573901002
E(HF) from rotated basis: -78.00179573901008
abs diff                : 5.68e-14
E(CASCI) = -78.03179043512773
```

Two orbitals stand out at σ ≈ 0.998 and σ ≈ 0.999 — one per carbon's `2pz`,
occupied (π) and virtual (π*) — with the rest of both blocks at σ well below
`threshold=0.2` (every other weight is 0 to machine precision except one
stray in the virtual block at 9.2e-05). That gap is the clean-separation
diagnostic from §4: `CAS(2,2)`
is the unambiguous π/π* active space for ethylene. The HF energy agrees to
5.68 × 10⁻¹⁴, far inside the ~10⁻¹⁰ target — confirming AVAS rotated the
occupied and virtual blocks internally without mixing them (§2).

---

## 6. Source links

- Quickstart §5 (localization), §12 (CASCI/CASSCF): https://pyscf.org/quickstart.html
- MCSCF / CASSCF user guide: https://pyscf.org/user/mcscf.html
- Orbital localization user guide: https://pyscf.org/user/lo.html
- `pyscf.mcscf` API: https://pyscf.org/pyscf_api_docs/pyscf.mcscf.html
- MCSCF examples (AVAS, natural orbitals, sort_mo): https://github.com/pyscf/pyscf/tree/master/examples/mcscf
- Localization examples: https://github.com/pyscf/pyscf/tree/master/examples/local_orb
- AVAS reference: Sayfutyarova, Sun, Chan & Knizia, arXiv:1701.07862
- PiOS reference: Sayfutyarova & Hammes-Schiffer, J. Chem. Theory Comput. 15,
  1679 (2019)
- APC references: DOI 10.1021/acs.jctc.1c00037 and DOI 10.1021/acs.jctc.2c00630
- Source: https://github.com/pyscf/pyscf
- Integral/FCIDUMP handoff: `references/pyscf-api.md` §4, `references/fcidump.md`
