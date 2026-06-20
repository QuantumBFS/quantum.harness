# TeNPy API + Examples Reference

Single-file usage reference for **TeNPy** (`physics-tenpy`), the Python tensor-network
library: MPS/MPO, finite & infinite DMRG, TEBD, iDMRG, single/two-site DMRG, VUMPS,
finite-temperature purification, and a YAML/dict simulation interface.

- Official docs: https://tenpy.readthedocs.io/en/latest/
- Import root is `tenpy`; install isolated (`make install tenpy` → `.venv-tenpy`), run with
  `.venv-tenpy/bin/python scripts/<name>.py`. TeNPy pins a numpy ABI — never share the main `.venv`/conda base.
- Harness method routing: `skills/method-mps/SKILL.md`; in-skill workflow: `skills/using-tenpy/SKILL.md`.

Common imports:

```python
import numpy as np
import tenpy
from tenpy.networks.mps import MPS
from tenpy.networks.site import SpinHalfSite, SpinSite, FermionSite, SpinHalfFermionSite, BosonSite
from tenpy.models.lattice import Chain, Square, Honeycomb, Kagome, Triangular, Ladder
from tenpy.models.spins import SpinChain, SpinModel
from tenpy.models.tf_ising import TFIChain
from tenpy.models.hubbard import FermiHubbardChain, BoseHubbardChain
from tenpy.models.model import CouplingMPOModel, NearestNeighborModel
from tenpy.algorithms import dmrg, tebd
```

---

## 1. Sites & charge conservation

A `Site` defines the local Hilbert space, the named local operators, and the conserved
charge (via `np_conserved`). `conserve` chooses the abelian symmetry that block-diagonalizes
tensors — it both pins the target sector and speeds things up. Pick `None` if unsure, then
turn on the strongest symmetry the Hamiltonian respects.

| Site | Constructor | `conserve` options | Operators provided |
|---|---|---|---|
| `SpinHalfSite` | `SpinHalfSite(conserve='Sz', sort_charge=True)` | `'Sz'`, `'parity'`, `None` | `Sz Sp Sm Sx Sy Sigmax Sigmay Sigmaz Id` |
| `SpinSite` | `SpinSite(S=0.5, conserve='Sz', sort_charge=True)` | `'Sz'`, `'parity'`, `None` | `Sz Sp Sm Sx Sy` (general spin S) |
| `FermionSite` | `FermionSite(conserve='N', filling=0.5)` | `'N'`, `'parity'`, `None` | `C Cd N JW Id` (JW = Jordan-Wigner string) |
| `SpinHalfFermionSite` | `SpinHalfFermionSite(cons_N='N', cons_Sz='Sz', filling=1.)` | `cons_N`: `'N'/'parity'/None`; `cons_Sz`: `'Sz'/'parity'/None` | `Cu Cdu Cd Cdd Nu Nd Ntot NuNd Sz Sp Sm JW` |
| `BosonSite` | `BosonSite(Nmax=3, conserve='N', filling=0.)` | `'N'`, `'parity'`, `None` | `B Bd N NN dN Id` |
| `GroupedSite` | `GroupedSite(sites, labels=None, charges='same')` | inherited from constituents | combined operators |

Notes:
- `sort_charge=True` is the modern default; set explicitly to silence deprecation warnings and keep charge-block ordering stable across versions.
- Operator names map to the charge structure: ladder ops (`Sp`/`Sm`, `Cd`/`C`) carry charge, so couplings using them usually need `plus_hc=True` to stay Hermitian and charge-conserving.
- `np_conserved` (`tenpy.linalg.np_conserved`) is the charged-tensor backend; `LegCharge`/`ChargeInfo` are built automatically by sites. You rarely touch it directly unless building a custom `Site`.

---

## 2. Lattices

Lattices order physical sites into a 1D MPS chain (the "snake"), expose neighbor pairs, and
carry the MPS boundary condition. `bc_MPS` is `'finite'`, `'infinite'`, or `'segment'`;
`bc` is the geometric boundary per direction (`'open'`/`'periodic'`).

| Lattice | Constructor | Notes |
|---|---|---|
| `Chain` | `Chain(L, site, bc='open', bc_MPS='finite')` | 1D chain of `L` equal sites |
| `Ladder` | `Ladder(L, sites, **kw)` | two coupled chains |
| `NLegLadder` | `NLegLadder(L, N, sites, **kw)` | N coupled chains |
| `Square` | `Square(Lx, Ly, site, order='default', bc='periodic', bc_MPS='infinite')` | 2D square; cylinder when one direction periodic |
| `Triangular` | `Triangular(Lx, Ly, site, **kw)` | triangular lattice |
| `Honeycomb` | `Honeycomb(Lx, Ly, sites, **kw)` | 2-site unit cell |
| `Kagome` | `Kagome(Lx, Ly, sites, **kw)` | 3-site unit cell |
| `HelicalLattice` | `HelicalLattice(regular_lattice, N_unit_cells)` | translation-invariant tilted 2D |
| `IrregularLattice` | `IrregularLattice(regular_lattice, remove=..., add=...)` | add/remove sites |

Key `Lattice` attributes / methods:
- `lat.pairs['nearest_neighbors']`, `lat.pairs['next_nearest_neighbors']` — lists of `(u1, u2, dx)` for `add_coupling`.
- `lat.mps_sites()` — ordered list of `Site` objects (pass to `MPS.from_product_state`).
- `lat.N_sites`, `lat.N_cells`, `lat.unit_cell` — counts / per-cell sites.
- `lat.position(lat_idx)`, `lat.order` — spatial coordinates and the MPS traversal order.
- For 2D: the **second** axis `Ly` is the wrapped (short, periodic) direction — keep it small (cylinder width).

---

## 3. Models

A model bundles a lattice, sites, and the Hamiltonian (as an MPO, and as bond terms for
TEBD). Two ways to get one: use a predefined model, or subclass `CouplingMPOModel`.

### 3.1 Predefined models + their `model_params`

All take a single `dict` (or `Config`) of `model_params`. Universal keys: `L`, `bc_MPS`
(`'finite'`/`'infinite'`), `conserve`, `lattice` (name or class), `bc_x`/`bc_y` for 2D.

| Model | Module | Key params (besides L/bc_MPS/conserve) |
|---|---|---|
| `TFIChain` / `TFIModel` | `tenpy.models.tf_ising` | `J` (coupling), `g` (transverse field) — H = −J ΣXX − g ΣZ (default conserve `'parity'`) |
| `SpinChain` / `SpinModel` | `tenpy.models.spins` | `S`, `Jx Jy Jz`, `hx hy hz`, `D` (single-ion), `E` |
| `XXZChain` | `tenpy.models.xxz_chain` | `Jxx`, `Jz`, `hz` |
| `FermiHubbardChain` / `FermiHubbardModel` | `tenpy.models.hubbard` | `t` (hop), `U`, `mu`, `V` |
| `BoseHubbardChain` / `BoseHubbardModel` | `tenpy.models.hubbard` | `t`, `U`, `mu`, `V`, `n_max` (Nmax), `conserve='N'` |
| `Haldane` (`FermionicHaldaneModel`) | `tenpy.models.haldane` | `t`, `t2`, `V`, `lattice='Honeycomb'` |

Example instantiations:

```python
M = TFIChain(dict(L=16, J=1.0, g=1.5, bc_MPS='finite', conserve=None))
M = SpinChain(dict(L=2, S=0.5, Jx=1., Jy=1., Jz=1., hz=0., bc_MPS='infinite', conserve='Sz'))
M = FermiHubbardChain(dict(L=10, t=1., U=8., mu=0., bc_MPS='finite', conserve='N'))
M = BoseHubbardChain(dict(L=12, t=1., U=10., n_max=3, bc_MPS='finite', conserve='N'))
```

Useful model attributes: `M.lat` (lattice), `M.H_MPO` (the MPO), `M.bond_energies(psi)`
(per-bond energy, used for TEBD ground-state energy: `np.mean(M.bond_energies(psi))`).

### 3.2 Custom model via `CouplingMPOModel`

Subclass and implement `init_sites` (build the `Site`), optionally `init_lattice`, and
`init_terms` (add the Hamiltonian). The framework assembles both MPO and bond terms.

- `add_onsite(strength, u, op, category=None, plus_hc=False)` — sum a single-site term over all cells at unit-cell index `u`.
- `add_coupling(strength, u1, op1, u2, op2, dx, op_string=None, plus_hc=False, category=None)` — sum a two-site term `op1(u1) ⊗ op2(u2+dx)` over the lattice. `dx` is the lattice-vector displacement; iterate `lat.pairs[...]`.
- `add_multi_coupling(strength, ops, ...)` — three-or-more-site terms (`ops` a list of `(opname, dx, u)`).
- `plus_hc=True` adds the Hermitian conjugate automatically — required for ladder ops (`Sp/Sm`, `Cd/C`) to keep H Hermitian and charge-conserving.
- **Fermions**: Jordan-Wigner strings are inserted automatically for fermionic operators; set `op_string='JW'` only for custom/non-default cases. The site's `JW` operator carries the sign string.
- `init_lattice` defaults: set `default_lattice = Chain` and `force_default_lattice = True` to lock geometry (see example in §5.5).

---

## 4. States, DMRG, TEBD, measurements

### 4.1 Building the initial MPS

```python
# p_state in MPS order: one entry per site (a label, or a vector for a superposition)
psi = MPS.from_product_state(M.lat.mps_sites(), ['up', 'down'] * (L // 2), bc=M.lat.bc_MPS)

# Lattice coordinates instead of MPS order (handy for 2D / multi-site cells):
psi = MPS.from_lat_product_state(M.lat, [['up'], ['down']])   # per-unit-cell pattern

# Singlet / dimer reference state:
psi = MPS.from_singlets(site, L, pairs=[(0, 1), (2, 3)], up='up', down='down')
```

`from_product_state(sites, p_state, bc='finite', ...)` — product state from per-site labels (or vectors for on-site superposition).
`from_lat_product_state(lat, p_state, allow_incommensurate=False, ...)` — same but indexed by lattice coordinates; wraps `from_product_state`.

### 4.2 DMRG (`tenpy.algorithms.dmrg`)

Two entry points, equivalent results:

```python
info = dmrg.run(psi, M, dmrg_params)          # convenience function, psi updated in place
E = info['E']
# or explicit engine (needed for SingleSiteDMRGEngine, segment runs, restart):
eng = dmrg.TwoSiteDMRGEngine(psi, M, dmrg_params)   # or SingleSiteDMRGEngine
E, psi = eng.run()
```

- `TwoSiteDMRGEngine` — optimizes 2 sites/step; grows χ naturally; mixer optional.
- `SingleSiteDMRGEngine` — 1 site/step; cheaper but **requires a mixer** to grow χ from a product state.

`dmrg_params` keys:

| Key | Meaning |
|---|---|
| `trunc_params` | dict: `chi_max` (max bond dim, the accuracy lever), `svd_min` (drop singular values below, e.g. `1e-10`), `trunc_cut` |
| `mixer` | `None` / `True` / a mixer name (`'SubspaceExpansion'`, `'DensityMatrixMixer'`) — escapes local minima, then decays off |
| `mixer_params` | dict: `amplitude`, `decay`, `disable_after` (sweep to turn mixer off) |
| `max_E_err` | energy convergence tolerance (e.g. `1e-10`) |
| `max_S_err` | entanglement-entropy convergence tolerance |
| `max_sweeps` / `min_sweeps` | sweep count bounds |
| `N_sweeps_check` | how often (in sweeps) convergence is checked |
| `combine` | merge physical legs into effective H for speed (`True` for 2-site) |
| `active_sites` | `2` (default for 2-site) or `1` |
| `lanczos_params` | dict for the local eigensolver (`N_min`, `N_max`, `E_tol`, `P_tol`) |
| `diag_method` | local eigensolver: `'lanczos'` (default), `'ED_block'`, ... |
| `update_env`, `start_env` | environment refresh / initialization controls |
| `norm_tol`, `P_tol_to_trunc`, `E_tol_to_trunc` | adaptive tolerance coupling between Lanczos and truncation |

### 4.3 TEBD (`tenpy.algorithms.tebd`)

```python
eng = tebd.TEBDEngine(psi, M, tebd_params)
eng.run_GS()        # imaginary-time -> ground state (uses delta_tau_list)
eng.run()           # real-time evolution by N_steps of dt
# low-level:
eng.calc_U(order=2, delta_t=0.01, type_evo='imag', E_offset=None)  # build Trotter gates
eng.evolve(N_steps=1000, dt=0.01)                                  # apply them
t = eng.evolved_time
```

`tebd_params` keys:

| Key | Meaning |
|---|---|
| `order` | Trotter order (2 typical; error ~ τ^order) |
| `dt` | real-time step (for `run()`) |
| `N_steps` | steps per `run()` call (gates reused between measurements) |
| `delta_tau_list` | imaginary-time schedule for `run_GS()`, e.g. `[0.1, 0.01, 1e-3, 1e-4, 1e-5]` |
| `max_error_E` | per-τ-stage energy-change stop criterion for `run_GS()` |
| `trunc_params` | `chi_max`, `svd_min`, `trunc_cut` (as in DMRG) |
| `start_time`, `preserve_norm` | bookkeeping / normalization control |

Related: `TimeDependentTEBD` (time-dependent H), `QRBasedTEBDEngine` (QR instead of SVD, faster at large χ).
Ground-state energy after TEBD: `E = np.mean(M.bond_energies(psi))` (per site for infinite).

### 4.4 Measurements on the MPS

```python
psi.expectation_value('Sz')                       # array of <Sz_i> over sites
psi.expectation_value('Sigmax')                   # single-site op by name
np.sum(psi.expectation_value('Sigmaz'))           # total magnetization (finite)
psi.correlation_function('Sz', 'Sz', sites1=range(10))   # <Sz_i Sz_j> matrix
psi.correlation_length(tol_ev0=1e-3)              # from transfer-matrix spectrum (infinite)
psi.entanglement_entropy()                        # von-Neumann S at every bond
psi.entanglement_entropy(n=2)                     # Rényi-2
psi.entanglement_spectrum(by_charge=True)         # Schmidt values by charge sector
psi.chi                                           # list of bond dimensions
psi.get_total_charge(only_physical_legs=True)     # check the sector landed in
psi.sample_measurements(first_site=0)             # computational-basis samples
psi.apply_local_op(i0, 'Sigmaz', unitary=True)    # in-place local operator (e.g. for quench)
```

Method signatures:
- `expectation_value(ops, sites=None, axes=None)` — ⟨ψ|op|ψ⟩ for 1- or n-site `ops`.
- `correlation_function(ops1, ops2, sites1=None, sites2=None, opstr=None, ...)` — two-point correlator; pass `opstr='JW'` for fermionic strings.
- `correlation_length(target=None, tol_ev0=None, ...)` — diagonalizes the transfer matrix (infinite MPS).
- `entanglement_entropy(n=1, bonds=None)` — n=1 von-Neumann, else Rényi-n.
- `canonical_form(**kw)` — restore canonical form in place (call before correlation_length on a copied state).

---

## 5. Worked examples (verbatim from docs)

### 5.1 Finite DMRG ground state — transverse-field Ising

Source: https://tenpy.readthedocs.io/en/latest/examples/d_dmrg.html

```python
import numpy as np

from tenpy.algorithms import dmrg
from tenpy.models.tf_ising import TFIChain
from tenpy.networks.mps import MPS


def example_DMRG_tf_ising_finite(L, g):
    print('finite DMRG, transverse field Ising model')
    print(f'L={L:d}, g={g:.2f}')
    model_params = dict(L=L, J=1.0, g=g, bc_MPS='finite', conserve=None)
    M = TFIChain(model_params)
    product_state = ['up'] * M.lat.N_sites
    psi = MPS.from_product_state(
        M.lat.mps_sites(), product_state, bc=M.lat.bc_MPS, unit_cell_width=M.lat.mps_unit_cell_width
    )
    dmrg_params = {
        'mixer': None,
        'max_E_err': 1.0e-10,
        'trunc_params': {'chi_max': 30, 'svd_min': 1.0e-10},
        'combine': True,
    }
    info = dmrg.run(psi, M, dmrg_params)
    E = info['E']
    print(f'E = {E:.13f}')
    print('final bond dimensions: ', psi.chi)
    mag_x = np.sum(psi.expectation_value('Sigmax'))
    mag_z = np.sum(psi.expectation_value('Sigmaz'))
    print(f'magnetization in X = {mag_x:.5f}')
    print(f'magnetization in Z = {mag_z:.5f}')
    if L < 20:
        from tfi_exact import finite_gs_energy
        E_exact = finite_gs_energy(L, 1.0, g)
        print(f'Exact diagonalization: E = {E_exact:.13f}')
        print('relative error: ', abs((E - E_exact) / E_exact))
    return E, psi, M
```

### 5.2 Infinite DMRG (iDMRG) — TFI and Heisenberg XXZ

Source: https://tenpy.readthedocs.io/en/latest/examples/d_dmrg.html

```python
def example_DMRG_tf_ising_infinite(g):
    print('infinite DMRG, transverse field Ising model')
    print(f'g={g:.2f}')
    model_params = dict(L=2, J=1.0, g=g, bc_MPS='infinite', conserve=None)
    M = TFIChain(model_params)
    product_state = ['up'] * M.lat.N_sites
    psi = MPS.from_product_state(
        M.lat.mps_sites(), product_state, bc=M.lat.bc_MPS, unit_cell_width=M.lat.mps_unit_cell_width
    )
    dmrg_params = {
        'mixer': True,
        'trunc_params': {'chi_max': 30, 'svd_min': 1.0e-10},
        'max_E_err': 1.0e-10,
    }
    eng = dmrg.TwoSiteDMRGEngine(psi, M, dmrg_params)
    E, psi = eng.run()
    print(f'E = {E:.13f}')
    print('final bond dimensions: ', psi.chi)
    mag_x = np.mean(psi.expectation_value('Sigmax'))
    mag_z = np.mean(psi.expectation_value('Sigmaz'))
    print(f'<sigma_x> = {mag_x:.5f}')
    print(f'<sigma_z> = {mag_z:.5f}')
    print('correlation length:', psi.correlation_length())
    from tfi_exact import infinite_gs_energy
    E_exact = infinite_gs_energy(1.0, g)
    print(f'Analytic result: E (per site) = {E_exact:.13f}')
    print('relative error: ', abs((E - E_exact) / E_exact))
    return E, psi, M
```

```python
from tenpy.models.spins import SpinModel

def example_DMRG_heisenberg_xxz_infinite(Jz, conserve='best'):
    print('infinite DMRG, Heisenberg XXZ chain')
    print(f'Jz={Jz:.2f}, conserve={conserve!r}')
    model_params = dict(
        L=2, S=0.5, Jx=1.0, Jy=1.0, Jz=Jz,
        bc_MPS='infinite', conserve=conserve,
    )
    M = SpinModel(model_params)
    product_state = ['up', 'down']
    psi = MPS.from_product_state(
        M.lat.mps_sites(), product_state, bc=M.lat.bc_MPS, unit_cell_width=M.lat.mps_unit_cell_width
    )
    dmrg_params = {
        'mixer': True,
        'trunc_params': {'chi_max': 100, 'svd_min': 1.0e-10},
        'max_E_err': 1.0e-10,
    }
    info = dmrg.run(psi, M, dmrg_params)
    E = info['E']
    print(f'E = {E:.13f}')
    print('final bond dimensions: ', psi.chi)
    Sz = psi.expectation_value('Sz')
    mag_z = np.mean(Sz)
    print(f'<S_z> = [{Sz[0]:.5f}, {Sz[1]:.5f}]; mean ={mag_z:.5f}')
    print('correlation length:', psi.correlation_length())
    corrs = psi.correlation_function('Sz', 'Sz', sites1=range(10))
    print('correlations <Sz_i Sz_j> =')
    print(corrs)
    return E, psi, M
```

Single-site iDMRG uses the same shape with `dmrg.SingleSiteDMRGEngine(psi, M, dmrg_params)`
and `'mixer': True` (mandatory for single-site).

### 5.3 TEBD imaginary-time ground state (finite & infinite)

Source: https://tenpy.readthedocs.io/en/latest/examples/c_tebd.html

```python
import numpy as np

from tenpy.algorithms import tebd
from tenpy.models.tf_ising import TFIChain
from tenpy.networks.mps import MPS


def example_TEBD_gs_tf_ising_finite(L, g):
    print('finite TEBD, imaginary time evolution, transverse field Ising')
    print(f'L={L:d}, g={g:.2f}')
    model_params = dict(L=L, J=1.0, g=g, bc_MPS='finite', conserve=None)
    M = TFIChain(model_params)
    product_state = ['up'] * M.lat.N_sites
    psi = MPS.from_product_state(
        M.lat.mps_sites(), product_state, bc=M.lat.bc_MPS,
        unit_cell_width=M.lat.mps_unit_cell_width
    )
    tebd_params = {
        'order': 2,
        'delta_tau_list': [0.1, 0.01, 0.001, 1.0e-4, 1.0e-5],
        'N_steps': 10,
        'max_error_E': 1.0e-6,
        'trunc_params': {'chi_max': 30, 'svd_min': 1.0e-10},
    }
    eng = tebd.TEBDEngine(psi, M, tebd_params)
    eng.run_GS()

    E = np.sum(M.bond_energies(psi))
    print(f'E = {E:.13f}')
    print('final bond dimensions: ', psi.chi)
    mag_x = np.sum(psi.expectation_value('Sigmax'))
    mag_z = np.sum(psi.expectation_value('Sigmaz'))
    print(f'magnetization in X = {mag_x:.5f}')
    print(f'magnetization in Z = {mag_z:.5f}')
    return E, psi, M
```

Infinite variant: `bc_MPS='infinite'`, `L=2`, `max_error_E=1e-8`, energy per site via
`np.mean(M.bond_energies(psi))`, plus `psi.correlation_length()`.

### 5.4 TEBD real-time evolution + measurement (light cone)

Source: https://tenpy.readthedocs.io/en/latest/examples/c_tebd.html

```python
def example_TEBD_tf_ising_lightcone(L, g, tmax, dt):
    print('finite TEBD, real time evolution')
    print(f'L={L:d}, g={g:.2f}, tmax={tmax:.2f}, dt={dt:.3f}')
    from d_dmrg import example_DMRG_tf_ising_finite
    print('(run DMRG to get the groundstate)')
    E, psi, M = example_DMRG_tf_ising_finite(L, g)
    print('(DMRG finished)')
    i0 = L // 2
    psi.apply_local_op(i0, 'Sigmaz', unitary=True)
    dt_measure = 0.05
    tebd_params = {
        'order': 2,
        'dt': dt,
        'N_steps': int(dt_measure / dt + 0.5),
        'trunc_params': {'chi_max': 50, 'svd_min': 1.0e-10, 'trunc_cut': None},
    }
    eng = tebd.TEBDEngine(psi, M, tebd_params)
    S = [psi.entanglement_entropy()]
    for n in range(int(tmax / dt_measure + 0.5)):
        eng.run()
        S.append(psi.entanglement_entropy())
    import matplotlib.pyplot as plt
    plt.figure()
    plt.imshow(
        S[::-1], vmin=0.0, aspect='auto', interpolation='nearest',
        extent=(0, L - 1.0, -0.5 * dt_measure, eng.evolved_time + 0.5 * dt_measure),
    )
    plt.xlabel('site $i$')
    plt.ylabel('time $t/J$')
    plt.ylim(0.0, tmax)
    plt.colorbar().set_label('entropy $S$')
    plt.savefig(f'c_tebd_lightcone_{g:.2f}.pdf')
```

### 5.5 Custom `CouplingMPOModel`

Source: https://tenpy.readthedocs.io/en/latest/examples/model_custom.html
Anisotropic spin-1 chain: H = J Σᵢ Sᵢ·Sᵢ₊₁ + B Σᵢ Sˣᵢ + D Σᵢ (Sᶻᵢ)²

```python
import numpy as np

from tenpy.linalg import np_conserved as npc
from tenpy.models.lattice import Chain
from tenpy.models.model import CouplingMPOModel, NearestNeighborModel
from tenpy.networks.mps import TransferMatrix
from tenpy.networks.site import SpinSite


class AnisotropicSpin1Chain(CouplingMPOModel, NearestNeighborModel):
    r"""An example for a custom model, implementing the Hamiltonian of :arxiv:`1204.0704`.

    .. math ::
        H = J \sum_i \vec{S}_i \cdot \vec{S}_{i+1} + B \sum_i S^x_i + D \sum_i (S^z_i)^2
    """

    default_lattice = Chain
    force_default_lattice = True

    def init_sites(self, model_params):
        conserve = model_params.get('conserve', 'best')
        if conserve == 'best':
            conserve = 'Sz' if not model_params.any_nonzero(['B']) else None
            self.logger.info('%s: set conserve to %s', self.name, conserve)
        sort_charge = model_params.get('sort_charge', True)
        return SpinSite(S=1.0, conserve=None, sort_charge=sort_charge)

    def init_terms(self, model_params):
        J = model_params.get('J', 1.0)
        B = model_params.get('B', 0.0)
        D = model_params.get('D', 0.0)

        for u1, u2, dx in self.lat.pairs['nearest_neighbors']:
            self.add_coupling(J / 2.0, u1, 'Sp', u2, 'Sm', dx, plus_hc=True)
            self.add_coupling(J, u1, 'Sz', u2, 'Sz', dx)

        for u in range(len(self.lat.unit_cell)):
            self.add_onsite(B, u, 'Sx')
            self.add_onsite(D, u, 'Sz Sz')
```

`add_coupling(J/2, u1, 'Sp', u2, 'Sm', dx, plus_hc=True)` builds the XY part Hermitian-ly
(the `+h.c.` supplies the `Sm Sp` term); `add_onsite(D, u, 'Sz Sz')` is the on-site (Sᶻ)².

---

## 6. YAML / dict simulation interface

The highest-level interface: describe model + algorithm + initial state in one config and let
TeNPy assemble and run the whole workflow, with HDF5 output and parameter-derived filenames.

Run a config:

```bash
python -m tenpy parameters.yml          # equivalent forms:
tenpy-run parameters.yml
tenpy-run -C GroundStateSearch parameters.yml   # override simulation class
```

From Python:

```python
import tenpy
sim_params = tenpy.load_yaml_with_py_eval("parameters.yml")  # supports !py_eval for python exprs
results = tenpy.run_simulation(**sim_params)
# or:  tenpy.console_main("parameters.yml")
# parameter sweeps / adiabatic chains:  tenpy.run_seq_simulations(**sim_params)

results['energy']                  # measured ground-state energy
results['measurements']            # all measurement outcomes
results['simulation_parameters']   # the full resolved config
# results['psi']                   # the state, if saved
```

Minimal DMRG config:

```yaml
simulation_class: GroundStateSearch
output_filename: results.h5

model_class: SpinChain
model_params:
    L: 32
    bc_MPS: finite
    Jz: 1.

initial_state_params:
    method: lat_product_state
    product_state: [[up], [down]]

algorithm_class: TwoSiteDMRGEngine
algorithm_params:
    trunc_params:
        svd_min: 1.e-10
        chi_max: 100
    mixer: True
```

Top-level config keys: `simulation_class` (`GroundStateSearch`, `RealTimeEvolution`,
`SpectralSimulation`, ...), `model_class` + `model_params`, `algorithm_class` +
`algorithm_params`, `initial_state_params`, `output_filename` / `directory`.

Parameter-derived filenames:

```yaml
directory: results
output_filename_params:
    prefix: dmrg
    parts:
        algorithm_params.trunc_params.chi_max: 'chi_{0:04d}'
        model_params.L: 'L_{0:d}'
    suffix: .h5            # -> results/dmrg_chi_0100_L_32.h5
```

Sequential sweep (run a ramp of χ in one call to `run_seq_simulations`):

```yaml
sequential:
    recursive_keys:
        - algorithm_params.trunc_params.chi_max
algorithm_params:
    trunc_params:
        chi_max: [128, 256, 512]
```

More config templates: `minimal_DMRG.yml`, `minimal_TEBD.yml`, `minimal_TDVP.yml`,
`minimal_ExpMPOEvolution.yml`, `minimal_SpectralSimulation.yml`, `sequential_chi_ramp.yml`
under https://tenpy.readthedocs.io/en/latest/examples/yaml/ .

---

## 7. Pitfalls

- **Charge conservation must match the Hamiltonian.** If a term breaks the symmetry (e.g. a transverse field `Sx` with `conserve='Sz'`), TeNPy errors or silently gives wrong charges. Use `conserve=None` when unsure, then turn on the strongest respected symmetry. Verify with `psi.get_total_charge(only_physical_legs=True)` that you landed in the intended sector. Custom-model idiom: auto-disable `'Sz'` when a symmetry-breaking field is nonzero (see §5.5 `init_sites`).
- **`sort_charge`** — set `sort_charge=True` explicitly to avoid deprecation warnings and keep block ordering reproducible across TeNPy versions.
- **`bc_MPS` finite vs infinite.** `'finite'`: total energy via `np.sum(...)`/`info['E']`; pick `L` = system size. `'infinite'`: energy is *per site* (`np.mean(M.bond_energies(psi))`); `L` is the **unit-cell** length and must hold the order period — 2-site for a Néel/dimerized pattern, 1-site only for uniform states. Néel initial state on a 1-site cell cannot represent the order.
- **`trunc_params` is where accuracy lives.** `chi_max` is the dominant lever (cost ~χ³) — run a χ-series until the energy asymptotes; for gapless/critical systems χ must grow with system size. `svd_min` (~`1e-10`–`1e-14`) is the soft floor. Under-converged χ looks like a clean but wrong energy.
- **Mixer to get unstuck.** Two-site DMRG can grow χ on its own, but still gets trapped in local minima from a product/symmetric start — set `mixer: True` and let it decay (`mixer_params: disable_after`). **Single-site DMRG/VUMPS *requires* a mixer** — without it χ cannot grow at all. Symptom of a missing/weak mixer: energy stalls above the true ground state, χ stays pinned at the initial bond dimension.
- **TEBD τ-refinement.** A small `dt`/`delta_tau` alone does not mean convergence — per-step ΔE shrinks with τ regardless. Run each τ-stage of `delta_tau_list` to its energy plateau; Trotter error scales ~τ^order. `run_GS()` handles the schedule; for manual control use `calc_U(...)` + `evolve(...)` and watch `bond_energies`.
- **TEBD needs a nearest-neighbor model.** `TEBDEngine` requires the Hamiltonian as bond terms — subclass `NearestNeighborModel` (or use a predefined NN model). Longer-range terms need MPO-based evolution (`ExpMPOEvolution`/TDVP) instead.
- **numpy ABI / threads.** Install isolated (`.venv-tenpy`); a shared conda base triggers ABI import errors. Set `OMP_NUM_THREADS` etc. **before** importing numpy; for a clean benchmark pin to `1` and confirm the count.
- **`correlation_length` needs canonical form** and an infinite MPS; copy and call `psi.canonical_form()` before measuring on a state mutated by hand.
- **Fermion signs.** Let `add_coupling`/`correlation_function` insert Jordan-Wigner strings automatically; only set `op_string='JW'` for custom cases. Forgetting the string gives wrong fermionic correlators/energies.

---

## 8. Source links

- Docs index: https://tenpy.readthedocs.io/en/latest/
- Examples list: https://tenpy.readthedocs.io/en/latest/examples.html
- Simulations interface: https://tenpy.readthedocs.io/en/latest/intro/simulations.html
- Models guide (add_coupling / add_onsite): https://tenpy.readthedocs.io/en/latest/intro/model.html
- DMRG protocol: https://tenpy.readthedocs.io/en/latest/intro/dmrg-protocol.html
- DMRG example (d_dmrg.py): https://tenpy.readthedocs.io/en/latest/examples/d_dmrg.html
- TEBD example (c_tebd.py): https://tenpy.readthedocs.io/en/latest/examples/c_tebd.html
- Custom model (model_custom.py): https://tenpy.readthedocs.io/en/latest/examples/model_custom.html
- Purification (finite-T): https://tenpy.readthedocs.io/en/latest/examples/purification.html
- MPS reference: https://tenpy.readthedocs.io/en/latest/reference/tenpy.networks.mps.MPS.html
- Sites reference: https://tenpy.readthedocs.io/en/latest/reference/tenpy.networks.site.html
- Lattices reference: https://tenpy.readthedocs.io/en/latest/reference/tenpy.models.lattice.html
- Models reference: https://tenpy.readthedocs.io/en/latest/reference/tenpy.models.html
- DMRG reference: https://tenpy.readthedocs.io/en/latest/reference/tenpy.algorithms.dmrg.html
- TEBD reference: https://tenpy.readthedocs.io/en/latest/reference/tenpy.algorithms.tebd.html
- np_conserved reference: https://tenpy.readthedocs.io/en/latest/reference/tenpy.linalg.np_conserved.html
- Notebooks (TEBD, DMRG, simulations, mixer, lattices): https://tenpy.readthedocs.io/en/latest/examples.html#jupyter-notebooks
