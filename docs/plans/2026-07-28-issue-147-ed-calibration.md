# Issue 147 4x4 ED Calibration Implementation Plan

> **For agents:** Use task-by-task execution with checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a symmetry-complete 4x4 full-spectrum TFIM reference at `h = 3.0`, with exact small-cluster tests and a resumable SCNet runner.

**Architecture:** Explicit `D4 x Z2` orbit projectors produce orthonormal sector bases. The two-dimensional `E` irrep is reduced by a fixed axis reflection and restored with spectral multiplicity two. Each cluster task diagonalizes one real symmetric block and writes an atomic manifest; a strict assembler accepts only all ten logical sectors before producing thermodynamics.

**Tech Stack:** Python 3.11, NumPy, SciPy sparse matrices and LAPACK, pytest, Slurm, existing `qh147.exact.thermal_from_spectrum`.

---

## File map

- Create `tracks/peps/solutions/avi7ii/qh147/symmetry_ed.py`: `D4 x Z2` actions, orbit projectors, reduced `E` bases, dimension metadata.
- Create `tracks/peps/solutions/avi7ii/qh147/ed.py`: sparse TFIM construction, sector projection, Hermiticity diagnostics, eigenvalues.
- Create `tracks/peps/solutions/avi7ii/qh147/run_ed.py`: configuration parsing, rehearsal, one-cell execution, atomic result manifests.
- Create `tracks/peps/solutions/avi7ii/qh147/ed_thermo.py`: strict ten-sector loading, multiplicity recovery, thermal CSV assembly.
- Create `tracks/peps/solutions/avi7ii/configs/ed-4x4.json`: ratified physical and beta-grid settings.
- Create `tracks/peps/solutions/avi7ii/scripts/issue147-ed.sbatch`: partition-neutral CPU entrypoint.
- Create `tracks/peps/solutions/avi7ii/tests/test_symmetry_ed.py`: group, orthogonality, completeness, and `E` reduction tests.
- Create `tracks/peps/solutions/avi7ii/tests/test_ed.py`: 2x2 and 3x3 direct-spectrum comparisons.
- Create `tracks/peps/solutions/avi7ii/tests/test_run_ed.py`: rehearsal, manifest, hash, and resume tests.
- Create `tracks/peps/solutions/avi7ii/tests/test_ed_thermo.py`: complete assembly and rejection tests.
- Create `tracks/peps/solutions/avi7ii/tests/test_ed_sbatch.py`: static resource and progress checks.
- Modify `tracks/peps/solutions/avi7ii/README.md`: local test, rehearsal, assembly, and cluster commands.

### Task 1: Build the `D4 x Z2` sector bases

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/symmetry_ed.py`
- Test: `tracks/peps/solutions/avi7ii/tests/test_symmetry_ed.py`

- [ ] **Step 1: Write failing group and basis tests**

```python
import numpy as np
import pytest

from qh147.model import tfim_dense
from qh147.symmetry_ed import IRREPS, d4_elements, sector_basis, state_action


def test_d4_actions_are_unique_symmetries_on_2x2_and_3x3():
    for l in (2, 3):
        elements = d4_elements(l)
        assert len(elements) == 8
        assert len({element.permutation for element in elements}) == 8
        hmat = tfim_dense(l, l, j=1.0, h=3.0)
        for element in elements:
            mapping = np.array([
                state_action(state, element.permutation)
                for state in range(hmat.shape[0])
            ])
            assert np.allclose(hmat[np.ix_(mapping, mapping)], hmat, atol=1e-12)


@pytest.mark.parametrize("l", [2, 3])
def test_sector_bases_are_orthonormal_disjoint_and_complete(l):
    blocks = [
        sector_basis(l, irrep, parity)
        for irrep in IRREPS
        for parity in (1, -1)
    ]
    for block in blocks:
        gram = (block.q.T @ block.q).toarray()
        assert np.allclose(gram, np.eye(block.q.shape[1]), atol=1e-12)
        assert block.recovered_dimension == block.q.shape[1] * block.spectral_multiplicity
    assert sum(block.recovered_dimension for block in blocks) == 1 << (l * l)
    for index, left in enumerate(blocks):
        for right in blocks[index + 1:]:
            assert np.linalg.norm((left.q.T @ right.q).toarray()) < 1e-12


def test_e_uses_one_reflection_component_with_multiplicity_two():
    plus = sector_basis(3, "E", 1, e_reflection=1)
    minus = sector_basis(3, "E", 1, e_reflection=-1)
    assert plus.spectral_multiplicity == minus.spectral_multiplicity == 2
    assert plus.q.shape == minus.q.shape
    assert np.linalg.norm((plus.q.T @ minus.q).toarray()) < 1e-12
```

- [ ] **Step 2: Run the focused test and verify the missing module**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_symmetry_ed.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'qh147.symmetry_ed'`.

- [ ] **Step 3: Implement orbit-local character projectors and the reduced `E` basis**

Add `symmetry_ed.py` with these interfaces and exact construction:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import scipy.sparse as sp

IRREPS = ("A1", "A2", "B1", "B2", "E")
IRREP_DIMS = {"A1": 1, "A2": 1, "B1": 1, "B2": 1, "E": 2}
CHARACTERS = {
    "A1": {"e": 1, "r2": 1, "r": 1, "axis": 1, "diag": 1},
    "A2": {"e": 1, "r2": 1, "r": 1, "axis": -1, "diag": -1},
    "B1": {"e": 1, "r2": 1, "r": -1, "axis": 1, "diag": -1},
    "B2": {"e": 1, "r2": 1, "r": -1, "axis": -1, "diag": 1},
    "E": {"e": 2, "r2": -2, "r": 0, "axis": 0, "diag": 0},
}


@dataclass(frozen=True)
class D4Element:
    name: str
    character_class: str
    permutation: tuple[int, ...]


@dataclass(frozen=True)
class SectorBasis:
    q: sp.csr_matrix
    spectral_multiplicity: int
    recovered_dimension: int


def d4_elements(l: int) -> tuple[D4Element, ...]:
    transforms: tuple[tuple[str, str, Callable[[int, int], tuple[int, int]]], ...] = (
        ("e", "e", lambda x, y: (x, y)),
        ("r90", "r", lambda x, y: (y, l - 1 - x)),
        ("r180", "r2", lambda x, y: (l - 1 - x, l - 1 - y)),
        ("r270", "r", lambda x, y: (l - 1 - y, x)),
        ("axis_x", "axis", lambda x, y: (l - 1 - x, y)),
        ("axis_y", "axis", lambda x, y: (x, l - 1 - y)),
        ("diag_main", "diag", lambda x, y: (y, x)),
        ("diag_anti", "diag", lambda x, y: (l - 1 - y, l - 1 - x)),
    )
    return tuple(
        D4Element(
            name,
            character_class,
            tuple(
                transform(x, y)[0] * l + transform(x, y)[1]
                for x in range(l)
                for y in range(l)
            ),
        )
        for name, character_class, transform in transforms
    )


def state_action(state: int, permutation: tuple[int, ...], flip: bool = False) -> int:
    result = 0
    for source, target in enumerate(permutation):
        result |= ((state >> source) & 1) << target
    if flip:
        result ^= (1 << len(permutation)) - 1
    return result


def _operator_on_orbit(orbit, index, permutation, flip=False):
    matrix = np.zeros((len(orbit), len(orbit)), dtype=np.float64)
    for column, state in enumerate(orbit):
        matrix[index[state_action(state, permutation, flip)], column] = 1.0
    return matrix


def _deterministic_columns(matrix: np.ndarray) -> np.ndarray:
    result = matrix.copy()
    for column in range(result.shape[1]):
        pivot = int(np.argmax(np.abs(result[:, column])))
        if result[pivot, column] < 0:
            result[:, column] *= -1
    return result


def sector_basis(
    l: int,
    irrep: str,
    parity: int,
    *,
    e_reflection: int = 1,
) -> SectorBasis:
    if irrep not in IRREPS or parity not in (-1, 1):
        raise ValueError("invalid D4 x Z2 sector")
    if e_reflection not in (-1, 1):
        raise ValueError("e_reflection must be +1 or -1")
    elements = d4_elements(l)
    reflection = next(item for item in elements if item.name == "axis_x")
    full_dimension = 1 << (l * l)
    unseen = set(range(full_dimension))
    rows: list[int] = []
    columns: list[int] = []
    data: list[float] = []
    output_column = 0
    while unseen:
        seed = min(unseen)
        orbit = sorted({
            state_action(seed, element.permutation, flip)
            for element in elements
            for flip in (False, True)
        })
        unseen.difference_update(orbit)
        index = {state: position for position, state in enumerate(orbit)}
        projector = np.zeros((len(orbit), len(orbit)), dtype=np.float64)
        prefactor = IRREP_DIMS[irrep] / 16.0
        for element in elements:
            for flip in (False, True):
                coefficient = (
                    prefactor
                    * CHARACTERS[irrep][element.character_class]
                    * parity ** int(flip)
                )
                projector += coefficient * _operator_on_orbit(
                    orbit, index, element.permutation, flip
                )
        projector = 0.5 * (projector + projector.T)
        values, vectors = np.linalg.eigh(projector)
        local_basis = vectors[:, values > 0.5]
        if irrep == "E" and local_basis.shape[1]:
            reflection_matrix = _operator_on_orbit(
                orbit, index, reflection.permutation
            )
            restricted = local_basis.T @ reflection_matrix @ local_basis
            reflection_values, reflection_vectors = np.linalg.eigh(
                0.5 * (restricted + restricted.T)
            )
            keep = reflection_values > 0.0 if e_reflection == 1 else reflection_values < 0.0
            local_basis = local_basis @ reflection_vectors[:, keep]
        local_basis = _deterministic_columns(local_basis)
        for local_column in range(local_basis.shape[1]):
            for local_row, state in enumerate(orbit):
                value = float(local_basis[local_row, local_column])
                if abs(value) > 1e-14:
                    rows.append(state)
                    columns.append(output_column)
                    data.append(value)
            output_column += 1
    q = sp.csr_matrix(
        (data, (rows, columns)),
        shape=(full_dimension, output_column),
        dtype=np.float64,
    )
    multiplicity = 2 if irrep == "E" else 1
    return SectorBasis(q, multiplicity, q.shape[1] * multiplicity)
```

- [ ] **Step 4: Run the basis tests**

Run the command from Step 2.

Expected: `4 passed` with no warnings.

- [ ] **Step 5: Commit the symmetry basis**

```bash
git add tracks/peps/solutions/avi7ii/qh147/symmetry_ed.py tracks/peps/solutions/avi7ii/tests/test_symmetry_ed.py
git commit -m "feat(ed): add D4 Z2 sector bases"
```

### Task 2: Project and diagonalize every exact sector

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/ed.py`
- Test: `tracks/peps/solutions/avi7ii/tests/test_ed.py`

- [ ] **Step 1: Write failing spectrum-union tests**

```python
import numpy as np
import pytest

from qh147.ed import _validated_symmetric, sector_eigenvalues
from qh147.model import tfim_dense
from qh147.symmetry_ed import IRREPS


@pytest.mark.parametrize("l", [2, 3])
def test_recovered_sector_union_matches_direct_dense_spectrum(l):
    direct = np.linalg.eigvalsh(tfim_dense(l, l, j=1.0, h=3.0))
    recovered = []
    for irrep in IRREPS:
        for parity in (1, -1):
            result = sector_eigenvalues(l, j=1.0, h=3.0, irrep=irrep, parity=parity)
            recovered.append(np.repeat(result.eigenvalues, result.spectral_multiplicity))
    assert np.allclose(np.sort(np.concatenate(recovered)), direct, atol=1e-10)


def test_two_e_reflection_components_have_the_same_spectrum():
    plus = sector_eigenvalues(3, j=1.0, h=3.0, irrep="E", parity=1, e_reflection=1)
    minus = sector_eigenvalues(3, j=1.0, h=3.0, irrep="E", parity=1, e_reflection=-1)
    assert np.allclose(plus.eigenvalues, minus.eigenvalues, atol=1e-10)


def test_non_hermitian_projected_matrix_is_rejected():
    with pytest.raises(FloatingPointError, match="non-Hermitian"):
        _validated_symmetric(np.array([[0.0, 1.0], [0.0, 0.0]]))
```

- [ ] **Step 2: Run the test and verify the missing module**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_ed.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'qh147.ed'`.

- [ ] **Step 3: Implement sparse construction, projection, and eigenvalues**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.linalg
import scipy.sparse as sp

from .model import obc_bonds
from .symmetry_ed import sector_basis


@dataclass(frozen=True)
class SectorSpectrum:
    eigenvalues: np.ndarray
    matrix_dimension: int
    recovered_dimension: int
    spectral_multiplicity: int
    hermiticity_residual: float


def tfim_sparse(l: int, *, j: float, h: float) -> sp.csr_matrix:
    nsites = l * l
    dimension = 1 << nsites
    bonds = obc_bonds(l, l)
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for state in range(dimension):
        diagonal = 0.0
        for left, right in bonds:
            same = ((state >> left) & 1) == ((state >> right) & 1)
            diagonal += -j if same else j
        rows.append(state)
        columns.append(state)
        values.append(diagonal)
        for site in range(nsites):
            rows.append(state ^ (1 << site))
            columns.append(state)
            values.append(-h)
    return sp.csr_matrix((values, (rows, columns)), shape=(dimension, dimension))


def _validated_symmetric(projected: np.ndarray) -> tuple[np.ndarray, float]:
    scale = max(float(np.linalg.norm(projected)), 1.0)
    residual = float(np.linalg.norm(projected - projected.T) / scale)
    if not np.isfinite(residual) or residual > 1e-12:
        raise FloatingPointError(f"non-Hermitian sector projection: {residual}")
    return 0.5 * (projected + projected.T), residual


def sector_matrix(
    l: int,
    *,
    j: float,
    h: float,
    irrep: str,
    parity: int,
    e_reflection: int = 1,
):
    basis = sector_basis(l, irrep, parity, e_reflection=e_reflection)
    projected = (basis.q.T @ tfim_sparse(l, j=j, h=h) @ basis.q).toarray()
    matrix, residual = _validated_symmetric(projected)
    return matrix, basis, residual


def sector_eigenvalues(
    l: int,
    *,
    j: float,
    h: float,
    irrep: str,
    parity: int,
    e_reflection: int = 1,
) -> SectorSpectrum:
    matrix, basis, residual = sector_matrix(
        l,
        j=j,
        h=h,
        irrep=irrep,
        parity=parity,
        e_reflection=e_reflection,
    )
    eigenvalues = scipy.linalg.eigvalsh(
        matrix, overwrite_a=True, check_finite=False, driver="evd"
    )
    if not np.isfinite(eigenvalues).all():
        raise FloatingPointError("eigensolver returned non-finite values")
    return SectorSpectrum(
        eigenvalues,
        matrix.shape[0],
        basis.recovered_dimension,
        basis.spectral_multiplicity,
        residual,
    )
```

- [ ] **Step 4: Run the exact spectrum tests**

Run the command from Step 2.

Expected: `4 passed`; both direct-spectrum comparisons meet `1e-10`.

- [ ] **Step 5: Commit the exact sector solver**

```bash
git add tracks/peps/solutions/avi7ii/qh147/ed.py tracks/peps/solutions/avi7ii/tests/test_ed.py
git commit -m "feat(ed): diagonalize symmetry sectors"
```

### Task 3: Add resumable one-sector runs and rehearsal

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/run_ed.py`
- Create: `tracks/peps/solutions/avi7ii/configs/ed-4x4.json`
- Test: `tracks/peps/solutions/avi7ii/tests/test_run_ed.py`

- [ ] **Step 1: Add the ratified configuration**

```json
{
  "l": 4,
  "j": 1.0,
  "field": 3.0,
  "boundary": "open",
  "operator": "pauli",
  "irreps": ["A1", "A2", "B1", "B2", "E"],
  "parities": [1, -1],
  "beta_grid": {"start": 0.025, "stop": 1.0, "step": 0.025}
}
```

- [ ] **Step 2: Write failing rehearsal, manifest, and resume tests**

```python
import hashlib
import json

from qh147.run_ed import main


def _config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "l": 2, "j": 1.0, "field": 3.0,
        "boundary": "open", "operator": "pauli",
        "irreps": ["A1", "A2", "B1", "B2", "E"],
        "parities": [1, -1],
        "beta_grid": {"start": 0.025, "stop": 0.1, "step": 0.025},
    }), encoding="utf-8")
    return path


def test_rehearsal_lists_ten_cells_and_complete_dimension(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "run"
    assert main(["--config", str(config), "--run-root", str(root), "--rehearse-all"]) == 0
    payload = json.loads((root / "h-3" / "rehearsal.json").read_text())
    assert len(payload["cells"]) == 10
    assert sum(cell["recovered_dimension"] for cell in payload["cells"]) == 16


def test_one_cell_writes_a_hashed_success_manifest_and_reuses_it(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "run"
    args = ["--config", str(config), "--run-root", str(root), "--cell-index", "1"]
    assert main(args) == 0
    cell = root / "h-3" / "A1-p+1"
    manifest = json.loads((cell / "manifest.json").read_text())
    spectrum = cell / "eigenvalues.npz"
    assert manifest["status"] == "success"
    assert manifest["provenance"]["spectrum_sha256"] == hashlib.sha256(spectrum.read_bytes()).hexdigest()
    before = spectrum.stat().st_mtime_ns
    assert main(args) == 0
    assert spectrum.stat().st_mtime_ns == before
```

- [ ] **Step 3: Run the test and verify the missing runner**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_run_ed.py -q
```

Expected: collection fails because `qh147.run_ed` does not exist.

- [ ] **Step 4: Implement the runner with these exact contracts**

`run_ed.py` must define:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np
import psutil
import scipy

from .ed import sector_eigenvalues
from .symmetry_ed import sector_basis


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"l", "j", "field", "boundary", "operator", "irreps", "parities", "beta_grid"}
    if set(config) != required or config["boundary"] != "open" or config["operator"] != "pauli":
        raise ValueError("invalid ED configuration")
    return config


def logical_sectors(config: dict):
    return tuple((irrep, parity) for irrep in config["irreps"] for parity in config["parities"])


def field_directory(root: Path, field: float) -> Path:
    return root / f"h-{field:g}"


def sector_directory(root: Path, field: float, irrep: str, parity: int) -> Path:
    return field_directory(root, field) / f"{irrep}-p{parity:+d}"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _atomic_spectrum(path: Path, eigenvalues: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, eigenvalues=eigenvalues)
    os.replace(temporary, path)


def _config_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _peak_memory() -> int:
    if os.name == "posix":
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    return int(psutil.Process().memory_info().rss)


def _rehearse(config_path: Path, config: dict, root: Path) -> int:
    cells = []
    for index, (irrep, parity) in enumerate(logical_sectors(config), start=1):
        basis = sector_basis(config["l"], irrep, parity)
        dimension = basis.q.shape[1]
        cells.append({
            "cell_index": index,
            "irrep": irrep,
            "parity": parity,
            "matrix_dimension": dimension,
            "recovered_dimension": basis.recovered_dimension,
            "spectral_multiplicity": basis.spectral_multiplicity,
            "matrix_bytes": 8 * dimension * dimension,
            "dense_flops_upper": 4 * dimension ** 3 / 3,
        })
        print(json.dumps(cells[-1]), flush=True)
    if sum(cell["recovered_dimension"] for cell in cells) != 1 << (config["l"] ** 2):
        raise ValueError("rehearsal sector dimensions are incomplete")
    _atomic_json(field_directory(root, config["field"]) / "rehearsal.json", {
        "status": "rehearsed", "config_sha256": _config_hash(config_path), "cells": cells
    })
    return 0


def _existing_success(output: Path, expected_hash: str) -> bool:
    manifest_path = output / "manifest.json"
    spectrum_path = output / "eigenvalues.npz"
    if not manifest_path.exists() or not spectrum_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return (
        manifest.get("status") == "success"
        and manifest.get("provenance", {}).get("config_sha256") == expected_hash
        and manifest.get("provenance", {}).get("spectrum_sha256")
        == hashlib.sha256(spectrum_path.read_bytes()).hexdigest()
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--cell-index", type=int)
    parser.add_argument("--rehearse-all", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.rehearse_all:
        return _rehearse(args.config, config, args.run_root)
    raw_index = (
        args.cell_index
        if args.cell_index is not None
        else int(os.environ["SLURM_ARRAY_TASK_ID"])
    )
    sectors = logical_sectors(config)
    if not 1 <= raw_index <= len(sectors):
        raise ValueError("cell index is outside the ten logical sectors")
    irrep, parity = sectors[raw_index - 1]
    output = sector_directory(args.run_root, config["field"], irrep, parity)
    output.mkdir(parents=True, exist_ok=True)
    config_hash = _config_hash(args.config)
    if _existing_success(output, config_hash):
        print(json.dumps({"status": "reused", "cell_index": raw_index}), flush=True)
        return 0
    started = time.perf_counter()
    try:
        basis = sector_basis(config["l"], irrep, parity)
        dimension = basis.q.shape[1]
        print(json.dumps({
            "event": "preflight", "cell_index": raw_index, "irrep": irrep,
            "parity": parity, "matrix_dimension": dimension,
            "matrix_bytes": 8 * dimension * dimension,
            "dense_flops_upper": 4 * dimension ** 3 / 3,
        }), flush=True)
        result = sector_eigenvalues(
            config["l"], j=config["j"], h=config["field"], irrep=irrep, parity=parity
        )
        spectrum_path = output / "eigenvalues.npz"
        _atomic_spectrum(spectrum_path, result.eigenvalues)
        manifest = {
            "status": "success",
            "params": {"field": config["field"], "irrep": irrep, "parity": parity},
            "settings": {
                "l": config["l"], "j": config["j"], "boundary": config["boundary"],
                "operator": config["operator"],
            },
            "diagnostics": {
                "matrix_dimension": result.matrix_dimension,
                "recovered_dimension": result.recovered_dimension,
                "spectral_multiplicity": result.spectral_multiplicity,
                "hermiticity_residual": result.hermiticity_residual,
            },
            "resources": {
                "wall_seconds": time.perf_counter() - started,
                "peak_memory_bytes": _peak_memory(),
            },
            "provenance": {
                "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "config_sha256": config_hash,
                "spectrum_sha256": hashlib.sha256(spectrum_path.read_bytes()).hexdigest(),
                "numpy": np.__version__, "scipy": scipy.__version__,
            },
        }
        _atomic_json(output / "manifest.json", manifest)
        print(json.dumps({"status": "success", "cell_index": raw_index}), flush=True)
        return 0
    except Exception as error:
        _atomic_json(output / "manifest.json", {
            "status": "failed", "error": type(error).__name__, "traceback": traceback.format_exc()
        })
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run runner tests and the prior exact tests**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_run_ed.py tracks/peps/solutions/avi7ii/tests/test_ed.py -q
```

Expected: `6 passed`; the second invocation reuses rather than rewrites the spectrum.

- [ ] **Step 6: Commit the one-sector runner**

```bash
git add tracks/peps/solutions/avi7ii/qh147/run_ed.py tracks/peps/solutions/avi7ii/configs/ed-4x4.json tracks/peps/solutions/avi7ii/tests/test_run_ed.py
git commit -m "feat(ed): add resumable sector runner"
```

### Task 4: Assemble the complete spectrum and thermal curve

**Files:**
- Create: `tracks/peps/solutions/avi7ii/qh147/ed_thermo.py`
- Test: `tracks/peps/solutions/avi7ii/tests/test_ed_thermo.py`

- [ ] **Step 1: Write complete-assembly and rejection tests**

```python
import csv
import json

import numpy as np
import pytest

from qh147.ed_thermo import assemble
from qh147.exact import thermal_from_spectrum
from qh147.model import tfim_dense
from qh147.run_ed import main as run_ed


def _complete_run(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "l": 2, "j": 1.0, "field": 3.0,
        "boundary": "open", "operator": "pauli",
        "irreps": ["A1", "A2", "B1", "B2", "E"], "parities": [1, -1],
        "beta_grid": {"start": 0.025, "stop": 0.1, "step": 0.025},
    }), encoding="utf-8")
    root = tmp_path / "run"
    for index in range(1, 11):
        assert run_ed(["--config", str(config), "--run-root", str(root), "--cell-index", str(index)]) == 0
    return config, root


def test_complete_assembly_matches_direct_thermodynamics(tmp_path):
    config, root = _complete_run(tmp_path)
    output = tmp_path / "assembled"
    assert assemble(config, root, output) == 0
    rows = list(csv.DictReader((output / "thermodynamics.csv").open()))
    spectrum = np.linalg.eigvalsh(tfim_dense(2, 2, j=1.0, h=3.0))
    for row in rows:
        direct = thermal_from_spectrum(spectrum, beta=float(row["beta"]), nsites=4)
        assert np.isclose(float(row["log_z_per_site"]), direct.log_z / 4)
        assert np.isclose(float(row["u"]), direct.u)
        assert np.isclose(float(row["c"]), direct.c)


def test_assembly_rejects_a_missing_sector(tmp_path):
    config, root = _complete_run(tmp_path)
    (root / "h-3" / "E-p-1" / "manifest.json").unlink()
    with pytest.raises(ValueError, match="missing successful sector"):
        assemble(config, root, tmp_path / "assembled")


def test_assembly_rejects_a_corrupt_spectrum(tmp_path):
    config, root = _complete_run(tmp_path)
    path = root / "h-3" / "A1-p+1" / "eigenvalues.npz"
    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        assemble(config, root, tmp_path / "assembled")
```

- [ ] **Step 2: Run the tests and verify the missing assembler**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_ed_thermo.py -q
```

Expected: collection fails because `qh147.ed_thermo` does not exist.

- [ ] **Step 3: Implement strict loading, multiplicity restoration, and CSV output**

```python
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .exact import thermal_from_spectrum
from .run_ed import load_config, logical_sectors, sector_directory


def _beta_grid(config: dict) -> np.ndarray:
    grid = config["beta_grid"]
    count = int(round((grid["stop"] - grid["start"]) / grid["step"])) + 1
    values = grid["start"] + np.arange(count) * grid["step"]
    if not np.isclose(values[-1], grid["stop"], atol=1e-14):
        raise ValueError("beta grid does not end exactly at stop")
    return values


def _complete_spectrum(config_path: Path, config: dict, root: Path) -> np.ndarray:
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    pieces = []
    recovered = 0
    sectors = logical_sectors(config)
    if len(set(sectors)) != len(sectors):
        raise ValueError("duplicate logical sector")
    for irrep, parity in sectors:
        directory = sector_directory(root, config["field"], irrep, parity)
        manifest_path = directory / "manifest.json"
        spectrum_path = directory / "eigenvalues.npz"
        if not manifest_path.exists() or not spectrum_path.exists():
            raise ValueError(f"missing successful sector {irrep},{parity}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "success":
            raise ValueError(f"missing successful sector {irrep},{parity}")
        if manifest["params"] != {"field": config["field"], "irrep": irrep, "parity": parity}:
            raise ValueError("sector parameter mismatch")
        expected_settings = {
            "l": config["l"], "j": config["j"],
            "boundary": config["boundary"], "operator": config["operator"],
        }
        if manifest["settings"] != expected_settings:
            raise ValueError("sector convention mismatch")
        if manifest["provenance"]["config_sha256"] != config_hash:
            raise ValueError("configuration hash mismatch")
        actual_hash = hashlib.sha256(spectrum_path.read_bytes()).hexdigest()
        if actual_hash != manifest["provenance"]["spectrum_sha256"]:
            raise ValueError("spectrum hash mismatch")
        with np.load(spectrum_path) as payload:
            eigenvalues = np.asarray(payload["eigenvalues"], dtype=np.float64)
        diagnostics = manifest["diagnostics"]
        multiplicity = int(diagnostics["spectral_multiplicity"])
        expected_multiplicity = 2 if irrep == "E" else 1
        if multiplicity != expected_multiplicity:
            raise ValueError("spectral multiplicity mismatch")
        if len(eigenvalues) != diagnostics["matrix_dimension"]:
            raise ValueError("stored matrix dimension mismatch")
        if diagnostics["recovered_dimension"] != len(eigenvalues) * multiplicity:
            raise ValueError("recovered sector dimension mismatch")
        if not np.isfinite(eigenvalues).all() or np.any(np.diff(eigenvalues) < 0):
            raise ValueError("invalid sector spectrum")
        pieces.append(np.repeat(eigenvalues, multiplicity))
        recovered += len(eigenvalues) * multiplicity
    if recovered != 1 << (config["l"] ** 2):
        raise ValueError("recovered spectrum is incomplete")
    return np.sort(np.concatenate(pieces))


def assemble(config_path: Path, run_root: Path, output: Path) -> int:
    config_path, run_root, output = map(Path, (config_path, run_root, output))
    config = load_config(config_path)
    spectrum = _complete_spectrum(config_path, config, run_root)
    rows = []
    for beta in _beta_grid(config):
        point = thermal_from_spectrum(spectrum, beta=float(beta), nsites=config["l"] ** 2)
        rows.append({
            "beta": point.beta,
            "log_z_per_site": point.log_z / (config["l"] ** 2),
            "f": point.f,
            "u": point.u,
            "c": point.c,
        })
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "thermodynamics.csv"
    temporary = destination.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("beta", "log_z_per_site", "f", "u", "c"))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, destination)
    manifest = {
        "status": "success", "state_count": len(spectrum),
        "field": config["field"],
        "thermodynamics_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
    manifest_path = output / "manifest.json"
    temp_manifest = manifest_path.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_manifest, manifest_path)
    return 0


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    return assemble(args.config, args.run_root, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add convention-mismatch and duplicate-sector cases**

Append these exact tests to `test_ed_thermo.py`:

```python
def test_assembly_rejects_a_convention_mismatch(tmp_path):
    config, root = _complete_run(tmp_path)
    path = root / "h-3" / "A1-p+1" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["settings"]["j"] = 0.5
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="sector convention mismatch"):
        assemble(config, root, tmp_path / "assembled")


def test_assembly_rejects_duplicate_logical_sectors(tmp_path):
    config, root = _complete_run(tmp_path)
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["irreps"] = ["A1", "A1", "A2", "B1", "B2", "E"]
    config.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate logical sector"):
        assemble(config, root, tmp_path / "assembled")
```

- [ ] **Step 5: Run assembler tests and the complete focused ED suite**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_symmetry_ed.py tracks/peps/solutions/avi7ii/tests/test_ed.py tracks/peps/solutions/avi7ii/tests/test_run_ed.py tracks/peps/solutions/avi7ii/tests/test_ed_thermo.py -q -W error
```

Expected: all focused tests pass with warnings treated as errors.

- [ ] **Step 6: Commit exact thermodynamic assembly**

```bash
git add tracks/peps/solutions/avi7ii/qh147/ed_thermo.py tracks/peps/solutions/avi7ii/tests/test_ed_thermo.py
git commit -m "feat(ed): assemble exact thermodynamics"
```

### Task 5: Add the partition-neutral SCNet entrypoint

**Files:**
- Create: `tracks/peps/solutions/avi7ii/scripts/issue147-ed.sbatch`
- Create: `tracks/peps/solutions/avi7ii/tests/test_ed_sbatch.py`
- Modify: `tracks/peps/solutions/avi7ii/README.md`

- [ ] **Step 1: Write the static Slurm contract test**

```python
from pathlib import Path


def test_ed_sbatch_has_ratified_resources_and_no_partition():
    path = Path(__file__).parents[1] / "scripts" / "issue147-ed.sbatch"
    text = path.read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=32" in text
    assert "#SBATCH --mem=128G" in text
    assert "#SBATCH --time=06:00:00" in text
    assert "#SBATCH --partition" not in text
    assert "#SBATCH --gres" not in text
    assert "PYTHONUNBUFFERED=1" in text
    assert "SLURM_ARRAY_TASK_ID" in text
    assert "python -u -m qh147.run_ed" in text
```

- [ ] **Step 2: Run the test and verify the missing script**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_ed_sbatch.py -q
```

Expected: failure because `issue147-ed.sbatch` does not exist.

- [ ] **Step 3: Add the exact Slurm entrypoint**

```bash
#!/usr/bin/env bash
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=06:00:00
set -euo pipefail
cd "$HOME/quantum.harness"
source .venv/bin/activate
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OPENBLAS_NUM_THREADS="$SLURM_CPUS_PER_TASK"
: "${SLURM_ARRAY_TASK_ID:?submit this script with --array or set a task id}"
printf '{"event":"start","cell":%s,"host":"%s"}\n' "$SLURM_ARRAY_TASK_ID" "$(hostname)"
python -u -m qh147.run_ed \
  --config tracks/peps/solutions/avi7ii/configs/ed-4x4.json \
  --run-root tracks/peps/results/issue147-ed
```

- [ ] **Step 4: Document the local and remote commands**

Append to `README.md`:

````markdown
## 4x4 exact calibration

Run the small exact tests locally:

```text
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests/test_symmetry_ed.py tracks/peps/solutions/avi7ii/tests/test_ed.py tracks/peps/solutions/avi7ii/tests/test_run_ed.py tracks/peps/solutions/avi7ii/tests/test_ed_thermo.py -q -W error
```

On SCNet, rehearse all ten sectors before submitting any eigensolver task:

```text
python -u -m qh147.run_ed --config tracks/peps/solutions/avi7ii/configs/ed-4x4.json --run-root tracks/peps/results/issue147-ed --rehearse-all
```

Submit cell 1 (`A1,+`) as the timing probe. Submit the remaining cells only after the measured cubic wall-time estimate passes the six-hour gate. Assemble a complete run with:

```text
python -m qh147.ed_thermo --config tracks/peps/solutions/avi7ii/configs/ed-4x4.json --run-root tracks/peps/results/issue147-ed --output tracks/peps/results/issue147-ed/assembled
```
````

- [ ] **Step 5: Run the static test and the complete local package suite**

```powershell
.venv\Scripts\python.exe -m pytest tracks/peps/solutions/avi7ii/tests -q -W error
```

Expected: all existing 46 tests plus the new ED tests pass; no warning is emitted.

- [ ] **Step 6: Commit the cluster entrypoint and documentation**

```bash
git add tracks/peps/solutions/avi7ii/scripts/issue147-ed.sbatch tracks/peps/solutions/avi7ii/tests/test_ed_sbatch.py tracks/peps/solutions/avi7ii/README.md
git commit -m "ops(ed): add SCNet calibration entrypoint"
```

## SCNet execution checkpoint

Do not run this checkpoint during implementation tests. After Tasks 1-5 are committed on an execution branch:

1. Select `skills/using-slurm/profiles/scnet-wangjieren.toml` as the active profile without modifying the profile contents.
2. Run `scripts/harness_slurm.sh precheck` and `scripts/harness_slurm.sh probe-partitions`; preserve the dirty-worktree and live-partition output.
3. Run the 4x4 `--rehearse-all` command on the login node and confirm recovered dimensions sum to 65536.
4. Obtain explicit partition and resource ratification from the user.
5. Submit only array cell 1, corresponding to `A1,+`, and monitor until its success manifest is fetched and hash-validated.
6. Compute each target estimate as `t_A1+ * (D_target / D_A1+)^3`. Stop if the largest reduced `E` task exceeds six hours.
7. Submit the remaining one-dimensional sectors, then the two `E` sectors. Monitor pending-to-running transition and the first flushed progress line.
8. Fetch every result, run `python -m qh147.ed_thermo ...`, and accept the run only when the assembly manifest reports 65536 states.

No `h = 2.5`, `h = 3.5`, PEPO, or QMC job is part of this implementation plan.
