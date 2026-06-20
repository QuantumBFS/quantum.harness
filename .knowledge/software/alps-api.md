# ALPS — API + Usage Reference

**ALPS** (Algorithms and Libraries for Physics Simulations) is an open-source meta-framework
for simulating strongly correlated quantum (and classical) lattice models — quantum magnets,
lattice bosons, correlated fermions. It bundles several independent solver applications behind
a *common model + lattice + parameter input layer* and a Python post-processing package
(**pyalps**). You define a Hamiltonian by name (e.g. `"spin"`, `"boson Hubbard"`) plus a lattice
name (e.g. `"chain lattice"`, `"square lattice"`), pick an application (`loop`, `dirloop_sse`,
`worm`, `sparsediag`, `fulldiag`, `dmrg`, `spinmc`, `dmft`, …), and the same input drives all of
them. This is its defining feature: *one model/lattice description, many methods*, so the same
problem can be cross-checked with QMC, ED, and DMRG with minimal re-specification.

Data is stored in XML (text) and HDF5 (binary, default). `pyalps` reads the results into
`DataSet` objects (NumPy `x`/`y` arrays + a `props` metadata dict) for evaluation and plotting.

## Source links

- Home: https://alps.comp-phys.org/
- Getting started: https://alps.comp-phys.org/start
- Installation: https://alps.comp-phys.org/install
- Tutorials index: https://alps.comp-phys.org/tutorials
- Documentation: https://alps.comp-phys.org/documentation
- ALPS using Python (pyalps): https://alps.comp-phys.org/documentation/intro/runalps/usepython/
- Models in ALPS: https://alps.comp-phys.org/documentation/models/
- Lattice how-tos: https://alps.comp-phys.org/documentation/intro/latticehowtos/
- Model definitions: https://alps.comp-phys.org/documentation/intro/modeldef/
- Tutorials by method: MC https://alps.comp-phys.org/tutorials/mcs/ · ED https://alps.comp-phys.org/tutorials/ed/ · DMRG https://alps.comp-phys.org/tutorials/dmrg/ · DMFT https://alps.comp-phys.org/tutorials/dmft/ · TEBD https://alps.comp-phys.org/tutorials/tebd/ · custom lattices/models https://alps.comp-phys.org/tutorials/lm/
- QMC tutorial (MC-09): https://alps.comp-phys.org/tutorials/mcs/qmc/
- Classical MC tutorial (MC-01a): https://alps.comp-phys.org/tutorials/mcs/mc01a/
- ED tutorial (ED-01): https://alps.comp-phys.org/tutorials/ed/ed01/
- DMRG tutorial (DMRG-01): https://alps.comp-phys.org/tutorials/dmrg/dmrg01/
- GitHub (active fork/maintenance): https://github.com/ALPSim/ALPS
- XML schema spec: http://xml.comp-phys.org/
- Release paper: arXiv:1101.2646, J. Stat. Mech. (2011) P05001, DOI 10.1088/1742-5468/2011/05/P05001
- Local rendered paper: `.knowledge/literature/software/1101.2646_*.md`

> Maintenance note (verify before use): ALPS 2.0 (2011) is the canonical release described by
> the paper; the project is now in maintenance, with a modernized fork and rebuilt static
> docs/tutorials under the `ALPSim` GitHub org. The historical wiki at
> `alps.comp-phys.org/mediawiki/...` returns 404 — the live docs are the static
> `alps.comp-phys.org/{documentation,tutorials}/...` pages linked above.

---

## What ALPS bundles (applications)

| Application | Method | Best for |
|---|---|---|
| `spinmc` | Classical Monte Carlo (local + cluster updates) | Ising / XY / Heisenberg / Potts classical magnets |
| `loop` | Loop-cluster QMC (path-integral & SSE) | Isotropic/anisotropic quantum magnets, transverse/longitudinal fields; *no sign problem regime* |
| `dirloop_sse` | Directed-loop SSE QMC | Spin models in fields, frustrated spins, hard-core bosons |
| `worm` | Worm-algorithm QMC | Bosonic (soft-core) models |
| `qwl` | Quantum Wang–Landau (extended ensemble) | Thermodynamics over wide temperature ranges |
| `sparsediag` | Lanczos sparse ED | Ground + low-lying excited states; momentum-resolved spectra |
| `fulldiag` | Full ED (all eigenvalues) | Complete spectrum → all thermodynamics vs T |
| `dmrg` | DMRG (static) | Ground/low-lying states of quasi-1D systems; local + 2-point observables |
| `tebd` | Time-Evolving Block Decimation | 1D real/imaginary-time dynamics; entanglement, Loschmidt echo |
| `dmft` | DMFT self-consistency + CT-QMC / Hirsch–Fye impurity solvers | Fermionic lattice models (local self-energy) |

Each app has its **own scope**: not every model/lattice works with every app (e.g. sign problem
restricts which QMC codes apply; `dmrg`/`tebd` are quasi-1D; `dmft`/`tebd` use non-XML input
files written by `pyalps`). The apps share file formats so a model can be attacked with more than
one method.

---

## Core workflow

```text
1. Define Hamiltonian by name (MODEL=...) + lattice by name (LATTICE=...)
2. Write a parameter file (or a pyalps list-of-dicts) with couplings, T/beta, sizes, sweeps
3. Run an application on the input (command line: parameter2xml + app; or pyalps.runApplication)
4. Post-process with pyalps: load results -> DataSet -> collectXY / evaluate -> plot
```

The model and lattice definitions live in XML libraries (`models.xml`, `lattices.xml`) shipped
with ALPS; you reference entries by name. You only write XML by hand for *custom* lattices/models.

### Model & lattice XML libraries

The **lattice library** (`lattices.xml`) defines Bravais lattices and graphs. A finite lattice
specifies dimension, extent (`EXTENT size="L"`), boundary (`periodic`/`open`), and a unit cell of
`VERTEX` (sites) and `EDGE` (bonds). Example — a square lattice (from the paper, Fig. D3):

```xml
<LATTICEGRAPH name = "square">
  <FINITELATTICE>
    <LATTICE dimension="2"/>
    <EXTENT dimension="1" size="L"/>
    <EXTENT dimension="2" size="L"/>
    <BOUNDARY type="periodic"/>
  </FINITELATTICE>
  <UNITCELL>
    <VERTEX/>
    <EDGE><SOURCE vertex="1" offset="0 0"/><TARGET vertex="1" offset="0 1"/></EDGE>
    <EDGE><SOURCE vertex="1" offset="0 0"/><TARGET vertex="1" offset="1 0"/></EDGE>
  </UNITCELL>
</LATTICEGRAPH>
```

Lattices may be **inhomogeneous** (per-site/per-bond couplings, e.g. trapping potentials) and
**site-depleted** (`<DEPLETION>` with a `probability` parameter and a random `seed`) for disorder.

The **model library** (`models.xml`) defines, per model: a `BASIS` (local Hilbert space via
`SITEBASIS`, `QUANTUMNUMBER`s, and `OPERATOR`s) and a `HAMILTONIAN` (`SITETERM` + `BONDTERM`
written as symbolic expressions). Example — spin-½ XXZ (paper Fig. D4),
`H = −h Σᵢ Sᵢᶻ + Σ⟨i,j⟩ [ (Jxy/2)(Sᵢ⁺Sⱼ⁻ + Sᵢ⁻Sⱼ⁺) + Jz SᵢᶻSⱼᶻ ]`:

```xml
<BASIS name="spin">
  <SITEBASIS>
    <QUANTUMNUMBER name="S" min="1/2" max="1/2"/>
    <QUANTUMNUMBER name="Sz" min="-S" max="S"/>
    <OPERATOR name="Splus" matrixelement="sqrt(S*(S+1)-Sz*(Sz+1))">
      <CHANGE quantumnumber="Sz" change="1"/>
    </OPERATOR>
    <OPERATOR name="Sminus" matrixelement="sqrt(S*(S+1)-Sz*(Sz-1))">
      <CHANGE quantumnumber="Sz" change="-1"/>
    </OPERATOR>
    <OPERATOR name="Sz" matrixelement="Sz"/>
  </SITEBASIS>
</BASIS>

<HAMILTONIAN name="spin">
  <BASIS ref="spin"/>
  <SITETERM>-h*Sz</SITETERM>
  <BONDTERM source="i" target="j">
    Jxy/2*(Splus(i)*Sminus(j) + Sminus(i)*Splus(j)) + Jz*Sz(i)*Sz(j)
  </BONDTERM>
</HAMILTONIAN>
```

Composite operators can be predefined (e.g. `double_occupancy`, `boson_hop`) and reused in both
the Hamiltonian and in measurements. To point an app at custom files, set the parameters
`LATTICE_LIBRARY` and `MODEL_LIBRARY` to your XML file paths.

### Built-in models and their operators

Models in ALPS (see `/documentation/models/`):

| MODEL name | Couplings (key params) | Operators provided |
|---|---|---|
| `"spin"` (Heisenberg/XXZ) | `J` (or `Jxy`,`Jz`), `h`, `Gamma`, `D`; `local_S` sets spin S | `Sz`, `Splus`, `Sminus`, `Sx` |
| `"Ising"` | `J`, `h` | `Sz` |
| transverse-field Ising | `J`, `Gamma` (field) | `Sz`, `Sx` |
| `"boson Hubbard"` (Bose–Hubbard) | `t`, `U`, `mu`, `V`, `Nmax` | `n`, `b`, `bdag` |
| `"hardcore boson"` | `t`, `V`, `mu` | `n`, `b`, `bdag` |
| `"spinless fermions"` | `t`, `V`, `mu` | `n`, `c`, `cdag` |
| `"fermion Hubbard"` | `t`, `U`, `mu` | `n`, `c`, `cdag`, `n_up`, `n_down` |
| `"t-J"` | `t`, `J` | spin + constrained fermion operators |
| `"Kondo lattice"` | `t`, `J` | conduction + localized spin operators |

`local_S` selects the spin (e.g. `0.5`, `1`); site-type-dependent values use `local_S0`,
`local_S1`, … (e.g. spin-1 bulk with spin-½ boundary sites). `Nmax` caps boson occupation.

### Built-in lattices

`"chain lattice"`, `"open chain lattice"`, `"square lattice"`, `"open square lattice"`,
`"ladder"` (use `L` and `W=2`), `"triangular lattice"`, `"honeycomb lattice"`,
`"simple cubic lattice"`, etc. Size set by `L` (and `W`/`L2` for higher dimensions). Use
`"open ..."` variants for DMRG (open boundary conditions).

---

## Key parameters (meaning)

| Parameter | Meaning |
|---|---|
| `LATTICE` | Lattice name from the lattice library (e.g. `"chain lattice"`). |
| `MODEL` | Model name from the model library (e.g. `"spin"`, `"boson Hubbard"`). |
| `L`, `W`, `L2` | Linear extent(s) / system size; `W` is the second dimension (ladder width, etc.). |
| `local_S` / `local_Sn` | Spin magnitude S per site (per site-type n). |
| `J`, `Jxy`, `Jz`, `J0`, `J1` | Exchange couplings (uniform / XY / Ising-axis / inter- vs intra-unit-cell). |
| `t`, `U`, `mu`, `V` | Hopping, on-site interaction, chemical potential, nearest-neighbor interaction. |
| `h`, `Gamma`, `D` | Longitudinal field, transverse field, single-ion anisotropy. |
| `Nmax` | Maximum boson number per site (truncates the local boson Hilbert space). |
| `T` | Temperature (QMC/classical MC). Many apps accept `beta = 1/T` instead. |
| `Tmin`, `Tmax` | (runApplication option / `--Tmin`) min/max seconds between checking convergence. |
| `THERMALIZATION` | Number of MC sweeps discarded before measuring (equilibration). |
| `SWEEPS` | Number of measurement MC sweeps. |
| `UPDATE` | MC update type: `"local"` or `"cluster"` (classical `spinmc`). |
| `ALGORITHM` | QMC representation selector for `loop` (e.g. `"loop"`, `"sse"`). |
| `CONSERVED_QUANTUMNUMBERS` | Comma-separated conserved QNs to block-diagonalize, e.g. `'Sz'`, `'N,Sz'`. |
| `Sz_total`, `N_total` | Fix the target sector value of a conserved quantum number. |
| `SWEEPS` (DMRG) | Number of DMRG finite-system sweeps. |
| `MAXSTATES` / `STATES` | Max kept DMRG states (bond dimension); `STATES` can be a per-sweep schedule. |
| `NUMBER_EIGENVALUES` | How many lowest eigenstates DMRG/ED targets (1 = ground state). |
| `TRUNCATION_ERROR` | DMRG truncated-weight threshold (alternative to fixing MAXSTATES). |
| `MEASURE_AVERAGE[name]` | Custom averaged operator measurement, value = operator expression. |
| `MEASURE_LOCAL[name]` | Per-site local operator measurement. |
| `MEASURE_CORRELATIONS[name]` | Two-point correlation, e.g. `'Sz'` or `'Splus:Sminus'`. |
| `MEASURE_STRUCTURE_FACTOR[name]` | Fourier-space structure factor of an operator. |
| `LATTICE_LIBRARY`, `MODEL_LIBRARY` | Paths to custom lattice/model XML files. |
| `DEPLETION`, `DEPLETION_SEED` | Fraction of depleted sites (disorder) and RNG seed. |

Custom measurement example (paper, ED of bosonic Hubbard):

```text
MEASURE_AVERAGE[Double] = double_occupancy
MEASURE_LOCAL[Local density] = n
MEASURE_CORRELATION[Density correlation] = n
MEASURE_CORRELATION[Green function] = "bdag:b"
MEASURE_STRUCTURE_FACTOR[Density Structure Factor] = n
```

A scan over a parameter is done by listing multiple parameter blocks. Command-line plain-text
parameter file (paper Fig. 4) — each `{ ... }` is one simulation in the scan:

```text
LATTICE="chain lattice"
MODEL="spin"
local_S=1/2
L=60
J=1
THERMALIZATION=5000
SWEEPS=50000
ALGORITHM="loop"
{ T=0.05; }
{ T=0.1;  }
{ T=0.2;  }
...
{ T=2.0;  }
```

Run from the command line:

```bash
parameter2xml parm                          # text params -> parm.in.xml + per-task XML
loop --auto-evaluate --write-xml parm.in.xml
```

`parameter2xml` converts a text parameter file into the XML the apps read; `--write-xml` also
emits results as XML (default output is HDF5); `--auto-evaluate` runs the app's built-in
evaluation.

---

## pyalps API

`import pyalps` and (for plotting) `import pyalps.plot`. Core functions:

| Function | Purpose |
|---|---|
| `pyalps.writeInputFiles(prefix, parms)` | Write XML input files from a list of parameter dicts. Returns the master input filename (`prefix.in.xml`). For non-XML apps (`dmft`, `tebd`) it writes their special input files. |
| `pyalps.runApplication(appname, inputfile, Tmin=None, Tmax=None, writexml=False, MPI=None)` | Run application `appname` (e.g. `'loop'`, `'spinmc'`, `'sparsediag'`, `'dmrg'`) on `inputfile`. `Tmin`/`Tmax` set convergence-check cadence (seconds); `writexml=True` also writes XML results; `MPI=n` runs in parallel on n processes. Returns the result-file info / exit status. |
| `pyalps.getResultFiles(prefix=..., dirname=..., pattern=...)` | List result files (HDF5/XML) matching a prefix/pattern. Fed into the load functions. |
| `pyalps.loadObservableList(files)` | List which observables are available in result files. |
| `pyalps.loadMeasurements(files, what=None)` | Load Monte Carlo / scalar observables into `DataSet`s. `what` is one name or a list of names; omit to load all. Each `DataSet` carries `y` (value + error) and `props` (parameters/metadata). |
| `pyalps.loadEigenstateMeasurements(files, what=None)` | Load ED/DMRG eigenstate observables (energies, local/correlation measurements per sector). Returns nested lists of `DataSet`s keyed by quantum-number sector / eigenstate. |
| `pyalps.loadSpectra(files)` | Load eigenvalue spectra (e.g. momentum-resolved energies) from ED. |
| `pyalps.loadBinningAnalysis(files, what)` | Load per-bin Monte Carlo data for autocorrelation/error analysis. |
| `pyalps.collectXY(data, x, y, foreach=[])` | Build (x, y) `DataSet`s for plotting: pick `x` from `props` (a parameter, e.g. `'T'`) and `y` (an observable). `foreach` groups into separate curves by listed parameter names. |
| `pyalps.mergeMeasurements(data)` | Merge measurements from runs that belong together (e.g. parallel tempering / split runs) into combined `DataSet`s. |
| `pyalps.flatten(nested)` | Flatten nested lists of `DataSet`s into a single list. |
| `pyalps.dict_intersect(dicts)` | Common key/value pairs across a list of `props` dicts (shared parameters). |
| `pyalps.plot.plot(datasets)` | matplotlib wrapper; auto-labels axes/legend from `props`. |
| `pyalps.plot.convertToText / makeGracePlot / makeGnuplotPlot(datasets)` | Export `DataSet`s to text / Grace / gnuplot. |
| `pyalps.DataSet()` | The core data container: `.x`, `.y` (NumPy arrays) and `.props` (dict). Build your own for custom plots. |

`DataSet`: members `x`, `y` (NumPy arrays) and `props` (dict of metadata, including the
simulation parameters plus keys like `'observable'`, `'xlabel'`, `'ylabel'`, `'label'`).

---

## Worked example 1 — quantum spin QMC (Heisenberg chain susceptibility)

Verbatim from the release paper (Fig. 5): compute the uniform susceptibility χ(T) of a
spin-½ Heisenberg chain (L=60) across temperatures with the `loop` QMC code, then plot.

```python
import pyalps
import matplotlib.pyplot as plt
import pyalps.plot

# prepare the input parameters
parms = []
for t in [0.05,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.25,1.5,1.75,2.0]:
    parms.append(
        {
          'LATTICE'         : "chain lattice",
          'MODEL'           : "spin",
          'local_S'         : 0.5,
          'T'               : t,
          'J'               : 1,
          'THERMALIZATION'  : 5000,
          'SWEEPS'          : 50000,
          'L'               : 60,
          'ALGORITHM'       : "loop"
        }
    )

# write the input file and run the simulation
input_file = pyalps.writeInputFiles('parm2c', parms)
pyalps.runApplication('loop', input_file)

# load the susceptibility and collect it as function of temperature T
data = pyalps.loadMeasurements(pyalps.getResultFiles(prefix='parm2c'), 'Susceptibility')
susceptibility = pyalps.collectXY(data, x='T', y='Susceptibility')

# make plot
plt.figure()
pyalps.plot.plot(susceptibility)
plt.xlabel('Temperature $T/J$')
plt.ylabel('Susceptibility $\\chi J$')
plt.title('Quantum Heisenberg chain')
plt.show()
```

### Variant — magnetization curve with directed-loop SSE (MC-09 tutorial)

```python
chain_parms = [{
    'LATTICE'        : "chain lattice", 'L': 20,
    'MODEL'          : "spin",          'local_S': 0.5, 'J': 1,
    'T'              : 0.08,
    'THERMALIZATION' : 1000, 'SWEEPS': 5000,
    'h'              : h               # magnetic field, scanned
} for h in field_values]

input_file = pyalps.writeInputFiles('qmc_chain', chain_parms)
res = pyalps.runApplication('dirloop_sse', input_file, Tmin=5)

data = pyalps.loadMeasurements(pyalps.getResultFiles(prefix='qmc_chain'),
                               'Magnetization Density')
magnetization = pyalps.collectXY(data, x='h', y='Magnetization Density')
pyalps.plot.plot(magnetization)
```

---

## Worked example 2 — exact diagonalization (ED-01, sparse Lanczos)

S=1 chain (L=4), measuring correlations and structure factor, in the Sz-conserving sectors.

```python
import pyalps

parms = [{
    'LATTICE' : "chain lattice",
    'MODEL'   : "spin",
    'local_S' : 1,
    'J'       : 1,
    'L'       : 4,
    'CONSERVED_QUANTUMNUMBERS'                       : 'Sz',
    'MEASURE_STRUCTURE_FACTOR[Structure Factor Sz]' : 'Sz',
    'MEASURE_CORRELATIONS[Diagonal spin correlations]'    : 'Sz',
    'MEASURE_CORRELATIONS[Offdiagonal spin correlations]' : 'Splus:Sminus'
}]

input_file = pyalps.writeInputFiles('parm1a', parms)
res = pyalps.runApplication('sparsediag', input_file)

# eigenstate observables, grouped by sector (Sz, momentum, ...)
data = pyalps.loadEigenstateMeasurements(pyalps.getResultFiles(prefix='parm1a'))
for sector in data[0]:
    print(sector.props['observable'], sector.props.get('Sz'),
          sector.props.get('TOTAL_MOMENTUM'), sector.y, sector.x)
```

`fulldiag` is used the same way but returns the full spectrum (and thermodynamics vs T). For
momentum-resolved spectra use `pyalps.loadSpectra(...)`.

---

## Worked example 3 — DMRG (DMRG-01, Heisenberg chain ground state)

Antiferromagnetic Heisenberg chain ground-state energy with the static `dmrg` code, on an
**open** chain in the Sz=0 sector.

```python
import pyalps
import matplotlib.pyplot as plt
import pyalps.plot

parms = [{
    'LATTICE'                  : "open chain lattice",
    'MODEL'                    : "spin",
    'CONSERVED_QUANTUMNUMBERS' : 'N,Sz',
    'Sz_total'                 : 0,
    'J'                        : 1,
    'SWEEPS'                   : 4,
    'NUMBER_EIGENVALUES'       : 1,
    'L'                        : 32,
    'MAXSTATES'                : 100
}]

input_file = pyalps.writeInputFiles('parm_spin_one_half', parms)
res = pyalps.runApplication('dmrg', input_file, writexml=True)

# eigenstate (ground-state) observables
data = pyalps.loadEigenstateMeasurements(
    pyalps.getResultFiles(prefix='parm_spin_one_half'))
for s in data[0]:
    print(s.props['observable'], ':', s.y[0])

# DMRG convergence: energy and truncation error per sweep iteration
iter_data = pyalps.loadMeasurements(
    pyalps.getResultFiles(prefix='parm_spin_one_half'),
    what=['Iteration Energy', 'Iteration Truncation Error'])

plt.figure()
pyalps.plot.plot(iter_data[0][0])
plt.ylabel('$E_0$')
plt.show()
```

For a spin-1 chain (gapped, Haldane), set `'local_S0': '0.5'` on boundary sites and
`'local_S1': '1'` in the bulk (open-chain spin-½ edge spins regularize the boundary). Use
`'STATES'` (a schedule) or `'TRUNCATION_ERROR'` instead of a fixed `MAXSTATES` for adaptive bond
dimension.

---

## Worked example 4 — classical Monte Carlo (MC-01a, 2D Ising)

```python
import pyalps, pyalps.plot

parms = [{
    'LATTICE'        : "square lattice",
    'MODEL'          : "Ising",
    'T'              : 2.269186,   # near Tc
    'J'              : 1,
    'THERMALIZATION' : 10000,
    'SWEEPS'         : 50000,
    'UPDATE'         : "local",    # or "cluster"
    'L'              : l
} for l in [4, 8, 16, 32]]

input_file = pyalps.writeInputFiles('parm1a', parms)
res = pyalps.runApplication('spinmc', input_file, Tmin=5, writexml=True)

binning = pyalps.loadBinningAnalysis(
    pyalps.getResultFiles(prefix='parm1a'), '|Magnetization|')
binning = pyalps.flatten(binning)
pyalps.plot.plot(binning)
```

---

## Conserved quantum numbers (setup)

ED and DMRG block-diagonalize using `CONSERVED_QUANTUMNUMBERS` (e.g. `'Sz'`, `'N,Sz'`,
`'N'`). This is required for tractable ED and for DMRG to target the right symmetry sector.
Fix the sector with `Sz_total`, `N_total`, etc. The names must match the quantum numbers the
model defines (`Sz`, `N`, …). ED additionally exploits translation symmetry to compute
momentum-resolved spectra (each momentum gives a separate energy list). Getting this wrong is a
common failure mode: omit the conserved QN and ED blows up in memory; fix the wrong sector and
you measure an excited state instead of the ground state.

---

## Pitfalls

- **Each app has its own scope.** Not every model/lattice is valid for every application. QMC
  apps are sign-problem-free only in restricted regimes (no frustration / sign-problematic
  fermions); `dmrg`/`tebd` are quasi-1D; `dmft` and `tebd` use special non-XML input files
  written by `pyalps`, not the standard XML path. Pick the app to the problem.
- **Maintenance status.** ALPS 2.0 (2011) is the documented release; the project is in
  maintenance. The historical MediaWiki (`/mediawiki/...`) is gone (404); use the rebuilt static
  docs/tutorials and the `ALPSim` GitHub fork. Newer codes (ITensor, TeNPy, QuSpin, XDiag,
  block2, TRIQS) supersede individual ALPS apps for serious new work, but ALPS remains useful as
  a cross-method reference and for its uniform model/lattice input layer.
- **Build/install complexity.** Source builds need CMake ≥ 2.8, Boost ≥ 1.43, HDF5 1.8,
  BLAS/LAPACK, and (for `pyalps`) Python 2.5/2.6 + NumPy/SciPy/matplotlib — the original release
  targeted Python 2. Binary installers existed for macOS/Windows; on Linux a source/CMake build
  is recommended. Link against optimized BLAS/LAPACK (MKL) — it materially affects ED/`fulldiag`
  performance. The modern `ALPSim` fork updates the toolchain (Python 3); check its README for
  current build steps.
- **Conserved-QN setup** (see above) is the most common correctness/feasibility pitfall.
- **Default output is HDF5**, not XML. Use `--write-xml` (CLI) or `writexml=True`
  (`runApplication`) if you need text output for external tools; `pyalps` reads HDF5 directly.
- **Sweeps/thermalization** are the QMC accuracy knobs — too few `THERMALIZATION` sweeps biases
  results; `SWEEPS` controls statistical error. Use `loadBinningAnalysis` to check autocorrelation
  before trusting error bars.
- **Boson truncation.** Bose–Hubbard needs `Nmax` set; too small biases the result, too large
  wastes Hilbert space.
- **Spin convention.** `local_S` is the spin magnitude S (0.5, 1, …); the spin Hamiltonian sign
  and field convention follow `models.xml` (e.g. `−h·Sz` site term) — verify against your
  intended sign convention before running.
