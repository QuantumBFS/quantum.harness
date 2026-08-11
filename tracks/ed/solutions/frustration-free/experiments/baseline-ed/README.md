# Rice-Mele Exact Diagonalization

Reusable exact-diagonalization project for the spinful Rice-Mele chain in a fixed particle-number
sector. This refactor preserves the Hamiltonian and boundary-twist conventions of the verified MVP.
It does not include Hubbard interactions, pump-cycle scans, Chern-number calculations, or real-time
evolution.

## Model

The Hamiltonian is

$$
H = -\sum_{j,\sigma}\left[t+(-1)^{j+1}\delta\right]
\left(c^\dagger_{j\sigma}c_{j+1,\sigma}+\mathrm{h.c.}\right)
+\Delta\sum_{j,\sigma}(-1)^{j+1} n_{j\sigma},
$$

implemented with the same zero-based indexing convention as the legacy code. The periodic boundary
bond uses

$$
c^\dagger_{L-1,\sigma}c_{0,\sigma}\,e^{+i\theta}
+c^\dagger_{0,\sigma}c_{L-1,\sigma}\,e^{-i\theta}.
$$

Both spin components receive the same charge twist. Particle numbers `N_up` and `N_down` are fixed
when the QuSpin basis is created.

`delta` is the hopping dimerization. `Delta` is the staggered onsite potential. YAML keys are
case-sensitive, so these names are deliberately distinct.

## Structure

```text
experiments/baseline-ed/
├── src/
│   ├── __init__.py
│   ├── model.py              # parameters, basis, Hamiltonian, Hermiticity
│   ├── diagonalization.py    # complete eigensystem and numerical checks
│   └── io_utils.py           # YAML loading and deterministic NPZ output
├── scripts/
│   └── run_ed.py             # command-line workflow only
├── tests/
│   └── test_model.py
├── configs/
│   └── default.yaml
├── results/                  # generated NPZ files are ignored by Git
├── requirements.txt
└── README.md
```

`src/model.py` is the only module that constructs the Hamiltonian in this
historical baseline. Its output is kept separate from the canonical
`hubbard-pump/src/model.py` implementation.

## Installation

From this directory, install dependencies in an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

A domestic mirror can be selected when needed:

```bash
.venv/bin/python -m pip install \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  -r requirements.txt
```

## Configuration

The default configuration is:

```yaml
L: 6
t: 1.0
delta: 0.5
Delta: 0.3
theta: 6.283185307179586
N_up: 3
N_down: 3
full_spectrum: true
output_dir: ../../results/baseline-ed
```

This project currently accepts only `full_spectrum: true`. A relative `output_dir` is resolved from
the project root, independent of the shell's current directory.

## Run

Execute from the project root:

```bash
python scripts/run_ed.py --config configs/default.yaml
```

The command prints the model parameters, Hilbert-space dimension, lowest eight eigenvalues,
orthogonality error, maximum eigenproblem residual, and output path.

## Output

Results use a deterministic filename containing all physical parameters. Re-running the same
configuration writes the same path. Each compressed `.npz` contains:

- `eigenvalues`: complete ascending spectrum, shape `(400,)` for the default configuration;
- `eigenvectors`: column eigenvectors, shape `(400, 400)` by default;
- `parameters_json`: serialized model parameters;
- `diagnostics_json`: basis dimension, Hermiticity error, orthogonality error, and maximum residual.

Degenerate eigenvectors may rotate within a degenerate subspace across eigensolver implementations.
Numerical regression therefore compares eigenvalues element by element and validates the eigenspace
through orthogonality and residual checks.

## Tests

Run from the project root:

```bash
python -m pytest -q tests
```

The suite verifies the 400-dimensional half-filled basis, Hermiticity, `theta=0` versus
`theta=2*pi` periodicity, complete eigensystem shapes, eigenvector orthogonality, eigenproblem
residuals, YAML handling, deterministic output naming, and the command-line workflow.
