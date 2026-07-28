# PEPO / Heisenberg-picture OLE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a deterministic Heisenberg-picture PEPO
calculation of the 49-active-qubit operator Loschmidt echo, first against a
seven-qubit dense oracle and then against the completed BP-TN baseline.

**Architecture:** A pinned Python/quimb project independently parses the
audited QASM, initializes the nonlocal product observable as a bond-one PEPO,
and reuses quimb's arbitrary-geometry simple-update evolution. A separate
contraction layer computes `2⁻ⁿ Tr[O C† O C]`; generic repository scan and
Slurm helpers own grid enumeration and remote execution.

**Tech Stack:** Python 3.11+, NumPy, SciPy, quimb at
`3c89529fe0a3487133a3928201691161e110abdf`, cotengra, uv, pytest, Julia 1.10
for the independent protocol-digest comparison, and the repository
`parameter_scan.py` / `harness_slurm.sh` helpers.

## Global Constraints

- Work only under
  `tracks/qcs/solutions/CCB-LV.999/issue-119-ole/`, except when invoking
  existing repository helpers.
- Keep the completed Julia BP-TN numerical path unchanged.
- Pin quimb to
  `3c89529fe0a3487133a3928201691161e110abdf`; do not accept PyPI quimb 1.14.0
  as a substitute.
- Validate input bytes `150686` and SHA-256
  `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455`.
- Preserve the full protocol: 49 active sites, 73 layers, 648 CZ gates,
  `L=3`, `b=0.25`, `δ=0.15`, and `O=Z52 Z59 Z72`.
- The seven-qubit dense/PEPO agreement tolerance is `10⁻¹⁰`.
- Full-system internal convergence requires
  `ΔDop + Δχenv ≤ 10⁻³`.
- Cross-method comparison uses `εBP=0.0044` and passes when
  `|FPEPO−FBP|≤εPEPO+εBP`.
- Never launch a full 49-qubit cell before the small-oracle manifest passes.
- Treat every full 49-qubit cell as remote unless a measured run is below
  10 minutes and 16 GB.
- Do not submit to SCNet. The intended remote account is
  `zyli@172.16.42.215`, selected through a local Slurm profile and re-ratified
  before submission.
- Runtime data stays under the repository-standard ignored
  `<workspace>/results/issue119-pepo-*` tree so the existing scan and Slurm
  fetch/classify helpers work unchanged; committed issue reports contain the
  durable conclusions.
- Every long-running loop flushes progress and atomically updates a partial
  manifest approximately every 100 causal gates.

---

## Planned file map

### Create

```text
tracks/qcs/solutions/CCB-LV.999/issue-119-ole/
├── pepo/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/ole_pepo/
│   │   ├── __init__.py
│   │   ├── qasm.py
│   │   ├── gates.py
│   │   ├── exact.py
│   │   ├── engine.py
│   │   ├── contraction.py
│   │   └── records.py
│   └── tests/
│       ├── test_environment.py
│       ├── test_qasm.py
│       ├── test_protocol_digest.py
│       ├── test_gate_conventions.py
│       ├── test_exact.py
│       ├── test_engine.py
│       ├── test_contraction.py
│       ├── test_records.py
│       ├── test_small_validation_cli.py
│       ├── test_full_runner.py
│       └── test_analysis.py
├── configs/
│   ├── pepo-pilot-axes.json
│   ├── pepo-delta0-control-axes.json
│   ├── pepo-settings.json
│   └── pepo-provenance.json
├── scripts/
│   ├── export_protocol_digest.jl
│   ├── validate_pepo_small.py
│   ├── run_pepo.py
│   ├── run_pepo_array_cell.py
│   └── analyze_pepo.py
├── PEPO_SMALL_VALIDATION.md
└── PEPO_49Q_VALIDATION.md
```

### Modify

```text
tracks/qcs/solutions/CCB-LV.999/issue-119-ole/.gitignore
tracks/qcs/solutions/CCB-LV.999/issue-119-ole/README.md
```

### Runtime-only, ignored at the repository root

```text
results/
├── issue119-pepo-small-oracle/
├── issue119-pepo-49q-pilot/
├── issue119-pepo-49q-delta0/
└── issue119-pepo-49q-wave-*/
```

Command convention: a block using `--project pepo` runs from the issue
directory; a block using
`--project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo` runs from the
repository root. Every `git add` / `git commit`, generic scan, and Slurm-helper
block runs from the repository root.

---

### Task 1: Pin the Python environment and expose the required upstream API

**Files:**

- Create: `pepo/pyproject.toml`
- Create: `pepo/src/ole_pepo/__init__.py`
- Create: `pepo/tests/test_environment.py`
- Generate: `pepo/uv.lock`
- Modify: `.gitignore`

**Interfaces:**

- Produces: `ole_pepo.PINNED_QUIMB_COMMIT: str`
- Guarantees: `quimb.tensor.CircuitPEPOSimpleUpdate` is importable from the
  locked environment.

- [ ] **Step 1: Add the package and dependency contract**

Create `pepo/pyproject.toml` with this complete contract:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "issue119-ole-pepo"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "quimb @ git+https://github.com/jcmgray/quimb.git@3c89529fe0a3487133a3928201691161e110abdf",
  "cotengra>=0.7",
  "numpy>=1.26",
  "scipy>=1.12",
]

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-cov>=5",
]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
testpaths = ["tests"]

[tool.hatch.build.targets.wheel]
packages = ["src/ole_pepo"]
```

Add `/pepo/.venv/` to the issue-local `.gitignore`.
Create `pepo/src/ole_pepo/__init__.py` with only:

```python
"""Heisenberg-picture PEPO implementation for issue 119."""
```

- [ ] **Step 2: Write the failing environment test**

Create `pepo/tests/test_environment.py`:

```python
import quimb.tensor as qtn

import ole_pepo


def test_pinned_quimb_pepo_api_is_available():
    assert (
        ole_pepo.PINNED_QUIMB_COMMIT
        == "3c89529fe0a3487133a3928201691161e110abdf"
    )
    assert hasattr(qtn, "CircuitPEPOSimpleUpdate")
```

- [ ] **Step 3: Lock and sync the environment, then verify the test fails**

Run:

```bash
cd tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv lock --project pepo
uv sync --project pepo --frozen
uv run --project pepo pytest pepo/tests/test_environment.py -q
```

Expected: collection fails because `PINNED_QUIMB_COMMIT` is absent.

- [ ] **Step 4: Add the minimal package constant**

Modify `pepo/src/ole_pepo/__init__.py`:

```python
"""Heisenberg-picture PEPO implementation for issue 119."""

PINNED_QUIMB_COMMIT = "3c89529fe0a3487133a3928201691161e110abdf"

__all__ = ["PINNED_QUIMB_COMMIT"]
```

- [ ] **Step 5: Verify the locked upstream API**

Run from the issue directory:

```bash
uv run --project pepo pytest pepo/tests/test_environment.py -q
uv run --project pepo python -c \
  'import quimb.tensor as qtn; print(qtn.CircuitPEPOSimpleUpdate)'
```

Expected: one passing test and a class imported from
`quimb.tensor.circuit.pepo`.

- [ ] **Step 6: Commit the isolated environment change**

```bash
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/.gitignore \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/pyproject.toml \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/uv.lock \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/__init__.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_environment.py
git commit -m "build: pin quimb PEPO environment"
```

---

### Task 2: Implement the strict independent OpenQASM parser

**Files:**

- Create: `pepo/src/ole_pepo/qasm.py`
- Create: `pepo/tests/test_qasm.py`
- Reference: `configs/baseline-49x648.toml`
- Reference: `inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm`

**Interfaces:**

- Produces:
  - `QASMGate(name, qubits, angle, layer_index, gate_index)`
  - `OLEProtocol(register_size, layers, active_sites, barrier_count)`
  - `parse_qasm(text: str) -> OLEProtocol`
  - `read_validated_qasm(path, expected_sha256, expected_bytes) -> OLEProtocol`
  - `replace_perturbations(protocol, source_angle, expected_count,
    replacement_angle=0.0) -> OLEProtocol`
  - `crop_protocol(protocol, sites) -> OLEProtocol`

- [ ] **Step 1: Write parser tests for the supported subset**

Create a tiny fixture inside `pepo/tests/test_qasm.py`:

```python
TINY_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[80];
rx(pi/2) q[52];
sx q[53];
cz q[52],q[53];
barrier q[52],q[53];
rz(0.3) q[33];
sdg q[52];
"""


def test_parse_qasm_preserves_layers_labels_and_angles():
    protocol = parse_qasm(TINY_QASM)
    assert protocol.register_size == 80
    assert protocol.barrier_count == 1
    assert protocol.active_sites == (33, 52, 53)
    assert [g.name for g in protocol.gates] == [
        "rx", "sx", "cz", "rz", "sdg"
    ]
    assert protocol.layers[0][0].angle == pytest.approx(np.pi / 2)
    assert protocol.layers[1][0].angle == pytest.approx(0.3)


def test_parser_rejects_unknown_gate():
    with pytest.raises(ValueError, match="unsupported OpenQASM"):
        parse_qasm(TINY_QASM.replace("sx q[53];", "h q[53];"))
```

Also add tests for a changed SHA, a qubit outside the register, a repeated CZ
endpoint, and nested angle expressions such as `sin(pi/2)`.

- [ ] **Step 2: Run the focused test to see the missing module failure**

```bash
uv run --project pepo pytest pepo/tests/test_qasm.py -q
```

Expected: FAIL because `ole_pepo.qasm` does not exist.

- [ ] **Step 3: Implement immutable protocol records and strict parsing**

Use frozen dataclasses:

```python
@dataclass(frozen=True, slots=True)
class QASMGate:
    name: str
    qubits: tuple[int, ...]
    angle: float | None
    layer_index: int
    gate_index: int


@dataclass(frozen=True, slots=True)
class OLEProtocol:
    register_size: int
    layers: tuple[tuple[QASMGate, ...], ...]
    active_sites: tuple[int, ...]
    barrier_count: int

    @property
    def gates(self) -> tuple[QASMGate, ...]:
        return tuple(gate for layer in self.layers for gate in layer)
```

Implement angle parsing from only:

```text
signed decimal
signed pi
signed coefficient*pi
any of the above divided by a nonzero decimal
```

Accept only `rx`, `rz`, `s`, `sdg`, `sx`, `sxdg`, `cz`, `barrier`, the exact
header, one `qelib1.inc`, and one `qreg q[N]`. Strip `//` comments before
matching. Preserve only nonempty gate layers, matching the existing Julia
parser.

- [ ] **Step 4: Implement identity validation and protocol transformations**

`read_validated_qasm` must compare byte length and SHA before parsing.

`replace_perturbations` must use an absolute tolerance of
`8*np.finfo(float).eps`, replace exactly `expected_count` matching `rz` gates,
and preserve every other field.

`crop_protocol` must:

```python
site_set = frozenset(sites)
keep = lambda gate: all(q in site_set for q in gate.qubits)
```

It preserves source `layer_index` and `gate_index`, drops empty layers, sets
`active_sites` to the sorted requested sites that occur in retained gates, and
keeps the source `barrier_count` as provenance.

- [ ] **Step 5: Add full-input audit assertions**

Add:

```python
def test_full_qasm_matches_audited_counts(ole_root):
    protocol = read_validated_qasm(
        ole_root / "inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm",
        expected_sha256=(
            "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455"
        ),
        expected_bytes=150686,
    )
    assert len(protocol.active_sites) == 49
    assert len(protocol.layers) == 73
    assert protocol.barrier_count == 73
    assert sum(g.name == "cz" for g in protocol.gates) == 648
    assert sum(
        g.name == "rz"
        and g.angle is not None
        and np.isclose(g.angle, 0.3, atol=8 * np.finfo(float).eps, rtol=0)
        for g in protocol.gates
    ) == 24
    assert len(protocol.gates) == 4756
```

Define `ole_root` as a pytest fixture resolved from `Path(__file__)`, never
from the caller's working directory.

- [ ] **Step 6: Run parser tests and commit**

```bash
uv run --project pepo pytest pepo/tests/test_qasm.py -q
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/qasm.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_qasm.py
git commit -m "feat: add strict PEPO QASM parser"
```

Expected: all parser tests pass.

---

### Task 3: Cross-check the Python gate manifest against Julia

**Files:**

- Create: `scripts/export_protocol_digest.jl`
- Create: `pepo/tests/test_protocol_digest.py`
- Modify: `pepo/src/ole_pepo/qasm.py`
- Reference: `src/OLEProtocol.jl`

**Interfaces:**

- Produces:
  - `canonical_gate_records(protocol) -> tuple[str, ...]`
  - `canonical_gate_digest(protocol) -> str`
- CLI contract:
  - `julia --project=. scripts/export_protocol_digest.jl INPUT.qasm`
  - stdout is one JSON object with `digest`, `gates`, `layers`, and
    `active_sites`.

- [ ] **Step 1: Write the cross-language failing test**

Create `pepo/tests/test_protocol_digest.py`:

```python
def test_full_protocol_digest_matches_julia(ole_root):
    qasm_path = ole_root / "inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm"
    protocol = parse_qasm(qasm_path.read_text(encoding="utf-8"))
    completed = subprocess.run(
        [
            "julia",
            f"--project={ole_root}",
            str(ole_root / "scripts/export_protocol_digest.jl"),
            str(qasm_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    julia = json.loads(completed.stdout)
    assert julia["digest"] == canonical_gate_digest(protocol)
    assert julia["gates"] == len(protocol.gates)
    assert julia["layers"] == len(protocol.layers)
    assert julia["active_sites"] == list(protocol.active_sites)
```

- [ ] **Step 2: Run it to verify the missing digest implementation**

```bash
uv run --project pepo pytest pepo/tests/test_protocol_digest.py -q
```

Expected: FAIL because the Python function and Julia script are absent.

- [ ] **Step 3: Implement the Python canonical record**

For every gate, emit exactly:

```python
def _angle_bits(angle: float | None) -> str:
    if angle is None:
        return "-"
    return struct.pack(">d", float(angle)).hex()


def canonical_gate_records(protocol: OLEProtocol) -> tuple[str, ...]:
    return tuple(
        (
            f"{gate.layer_index}|{gate.gate_index}|{gate.name}|"
            f"{','.join(map(str, gate.qubits))}|{_angle_bits(gate.angle)}"
        )
        for gate in protocol.gates
    )


def canonical_gate_digest(protocol: OLEProtocol) -> str:
    payload = "\n".join(canonical_gate_records(protocol)) + "\n"
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
```

- [ ] **Step 4: Implement the independent Julia exporter**

The script must include `src/OLEProtocol.jl`, parse the input, generate the
same zero-based layer and within-layer gate indices, format angle bits using
`@sprintf("%016x", reinterpret(UInt64, Float64(angle)))`, hash the ASCII
records with `SHA.sha256`, and print JSON through a small explicit encoder.

The output must contain no logging before or after the JSON object. Do not add
the digest function to the BP runner or alter its numerical behavior.

- [ ] **Step 5: Verify both the tiny and full digests**

Add a tiny-QASM digest test with known Python records, then run:

```bash
uv run --project pepo pytest \
  pepo/tests/test_protocol_digest.py \
  pepo/tests/test_qasm.py -q
julia --project=. tests/runtests.jl
```

Run the Julia command from the issue directory. Expected: Python tests and all
existing Julia tests pass.

- [ ] **Step 6: Commit**

```bash
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/export_protocol_digest.jl \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/qasm.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_protocol_digest.py
git commit -m "test: cross-check PEPO protocol digest"
```

---

### Task 4: Implement audited gate matrices and quimb conversion

**Files:**

- Create: `pepo/src/ole_pepo/gates.py`
- Create: `pepo/tests/test_gate_conventions.py`

**Interfaces:**

- Consumes: `QASMGate`, `OLEProtocol`
- Produces:
  - `gate_matrix(gate: QASMGate) -> np.ndarray`
  - `to_quimb_gate(gate: QASMGate) -> qtn.Gate`
  - `quimb_gates(protocol: OLEProtocol) -> tuple[qtn.Gate, ...]`
  - `interaction_edges(protocol: OLEProtocol) -> tuple[tuple[int, int], ...]`

- [ ] **Step 1: Write analytic matrix tests**

Test:

```python
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("s", np.diag([1.0, 1.0j])),
        ("sdg", np.diag([1.0, -1.0j])),
        (
            "sx",
            0.5 * np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]]),
        ),
        (
            "sxdg",
            0.5 * np.array([[1 - 1j, 1 + 1j], [1 + 1j, 1 - 1j]]),
        ),
    ],
)
def test_fixed_gate_matrices(name, expected):
    gate = QASMGate(name, (7,), None, 0, 0)
    np.testing.assert_allclose(gate_matrix(gate), expected, atol=1e-15)
```

Also test:

```text
Rx(θ)=cos(θ/2)I−i sin(θ/2)X
Rz(θ)=diag(exp(−iθ/2),exp(+iθ/2))
CZ=diag(1,1,1,−1)
```

For every gate, assert `G†G=I`. Verify `to_quimb_gate(gate).qubits` preserves
physical-label order.

- [ ] **Step 2: Run the test to verify the module is missing**

```bash
uv run --project pepo pytest pepo/tests/test_gate_conventions.py -q
```

Expected: FAIL importing `ole_pepo.gates`.

- [ ] **Step 3: Implement matrices without Qiskit**

Use `np.complex128` throughout. Reject a parameterized gate with no angle and a
fixed gate with an unexpected angle. Return a new array rather than a shared
mutable constant.

`to_quimb_gate` must use:

```python
qtn.Gate.from_raw(
    gate_matrix(gate),
    qubits=gate.qubits,
)
```

`interaction_edges` must collect CZ endpoints as sorted pairs and return the
lexicographically sorted unique tuple.

- [ ] **Step 4: Add a qubit-order regression**

Apply the converted CZ to each computational-basis column and assert only
`|11⟩` changes sign. Add a nonsymmetric two-qubit test matrix to confirm that
the first QASM label maps to the first matrix index.

- [ ] **Step 5: Run tests and commit**

```bash
uv run --project pepo pytest pepo/tests/test_gate_conventions.py -q
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/gates.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_gate_conventions.py
git commit -m "feat: translate audited QASM gates to quimb"
```

---

### Task 5: Build the independent dense oracle and seven-site crop

**Files:**

- Create: `pepo/src/ole_pepo/exact.py`
- Create: `pepo/tests/test_exact.py`
- Modify: `pepo/src/ole_pepo/qasm.py`

**Interfaces:**

- Consumes: `OLEProtocol`
- Produces:
  - `dense_gate_matrix(gate: QASMGate) -> np.ndarray`
  - `dense_unitary(protocol, site_order=None, max_sites=12) -> np.ndarray`
  - `pauli_product_dense(site_order, observable_sites) -> np.ndarray`
  - `normalized_ole_dense(protocol, observable_sites) -> complex`
  - `seven_site_oracle_protocol(full_protocol, delta_zero=False)
    -> OLEProtocol`

- [ ] **Step 1: Write dense-evolution tests before implementation**

Add:

```python
def test_dense_single_qubit_rotation():
    protocol = parse_qasm(
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
rx(pi/2) q[0];
"""
    )
    expected = (
        np.cos(np.pi / 4) * np.eye(2)
        - 1j * np.sin(np.pi / 4) * np.array([[0, 1], [1, 0]])
    )
    np.testing.assert_allclose(dense_unitary(protocol), expected, atol=1e-14)


def test_dense_ole_identity_is_one():
    protocol = parse_qasm(IDENTITY_ECHO_QASM)
    value = normalized_ole_dense(protocol, (0,))
    assert value == pytest.approx(1.0, abs=1e-14)
```

Add a non-nearest-label two-qubit test using physical labels 7 and 52.

- [ ] **Step 2: Run it to verify the exact module is absent**

```bash
uv run --project pepo pytest pepo/tests/test_exact.py -q
```

Expected: FAIL importing `ole_pepo.exact`.

- [ ] **Step 3: Implement a NumPy-only dense gate path**

Duplicate the small analytic formulas in `exact.py`; do not call
`ole_pepo.gates.gate_matrix` or a quimb circuit. This intentional duplication
keeps the oracle independent.

Apply each local gate to the left side of the accumulated unitary with:

```python
def _left_apply(
    unitary: np.ndarray,
    gate: np.ndarray,
    targets: tuple[int, ...],
    nsites: int,
) -> np.ndarray:
    untouched = tuple(i for i in range(nsites) if i not in targets)
    permutation = targets + untouched + tuple(range(nsites, 2 * nsites))
    inverse = np.argsort(permutation)
    tensor = unitary.reshape((2,) * (2 * nsites)).transpose(permutation)
    front = tensor.reshape(2 ** len(targets), -1)
    updated = (gate @ front).reshape((2,) * (2 * nsites))
    return updated.transpose(inverse).reshape(unitary.shape)
```

Map physical labels to tensor positions through the explicit `site_order`.
Refuse more than `max_sites` before allocating the dense matrix.

- [ ] **Step 4: Implement the normalized dense trace**

Build the product Pauli by Kronecker multiplying `Z` on requested sites and
`I` elsewhere in `site_order`. Compute:

```python
evolved = unitary.conj().T @ observable @ unitary
value = np.trace(observable @ evolved) / (2 ** len(site_order))
```

Return the complex value without dropping the imaginary part.

- [ ] **Step 5: Implement the exact seven-site fixture**

Use:

```python
SEVEN_SITE_ORACLE = frozenset({33, 39, 53, 52, 51, 50, 49})
SEVEN_SITE_OBSERVABLE = (52,)
```

Crop the full protocol, assert the induced CZ edge set is exactly:

```python
{
    (33, 39),
    (39, 53),
    (52, 53),
    (51, 52),
    (50, 51),
    (49, 50),
}
```

Assert the crop contains exactly two `rz(0.3)` perturbations, on 33 and 49.
For `delta_zero=True`, replace exactly those two angles by zero.

- [ ] **Step 6: Run dense tests and record the actual seven-site values**

```bash
uv run --project pepo pytest pepo/tests/test_exact.py -q
uv run --project pepo python -c \
  'from pathlib import Path; from ole_pepo.qasm import parse_qasm; from ole_pepo.exact import seven_site_oracle_protocol, normalized_ole_dense; p=Path("inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm"); q=parse_qasm(p.read_text()); print(normalized_ole_dense(seven_site_oracle_protocol(q, delta_zero=True), (52,))); print(normalized_ole_dense(seven_site_oracle_protocol(q), (52,)))'
```

Run from the issue directory. Expected: the first printed value differs from
`1+0j` by at most `10⁻¹⁰`; both imaginary parts are at most `10⁻¹²`. The
nonzero-δ value is recorded in the small-oracle manifest rather than copied
into source as an unaudited literal.

- [ ] **Step 7: Commit**

```bash
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/exact.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/qasm.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_exact.py
git commit -m "feat: add seven-qubit dense OLE oracle"
```

---

### Task 6: Generalize upstream PEPO evolution to product observables

**Files:**

- Create: `pepo/src/ole_pepo/engine.py`
- Create: `pepo/tests/test_engine.py`

**Interfaces:**

- Consumes: quimb gates and graph edges from Task 4.
- Produces:
  - `ProgressRecord`
  - `EvolutionDiagnostics`
  - `EvolutionResult`
  - `ProductObservablePEPO.evolve_product(
    operators: Mapping[int, np.ndarray], *,
    max_bond: int | None = None,
    cutoff: float | None = None,
    progress_every: int = 100,
    progress_callback: Callable[[ProgressRecord], None] | None = None
    ) -> EvolutionResult`
  - `build_pepo_circuit(protocol, max_bond, cutoff)
    -> ProductObservablePEPO`

- [ ] **Step 1: Write upstream-parity and product-observable tests**

The first test records the same three-site chain gates in both
`CircuitPEPOSimpleUpdate` and `ProductObservablePEPO`, evolves a one-site `Z`,
and compares dense operator arrays:

```python
np.testing.assert_allclose(
    product_result.operator.to_dense(
        tuple(product_result.operator.upper_ind(i) for i in (0, 1, 2)),
        tuple(product_result.operator.lower_ind(i) for i in (0, 1, 2)),
    ),
    upstream_operator.to_dense(
        tuple(upstream_operator.upper_ind(i) for i in (0, 1, 2)),
        tuple(upstream_operator.lower_ind(i) for i in (0, 1, 2)),
    ),
    atol=1e-12,
)
```

The second test uses no gates and operators `{0: Z, 2: Z}`; its dense result
must equal `Z⊗I⊗Z`.

- [ ] **Step 2: Run to verify the engine module is absent**

```bash
uv run --project pepo pytest pepo/tests/test_engine.py -q
```

Expected: FAIL importing `ole_pepo.engine`.

- [ ] **Step 3: Define immutable diagnostics**

Use:

```python
@dataclass(frozen=True, slots=True)
class ProgressRecord:
    processed_causal_gates: int
    total_causal_gates: int
    support_size: int
    max_realized_bond: int
    retained_tail_ratio: float | None
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class EvolutionDiagnostics:
    total_recorded_gates: int
    causal_gates: int
    final_support: tuple[int, ...]
    max_realized_bond: int
    max_retained_tail_ratio: float | None


@dataclass(frozen=True, slots=True)
class EvolutionResult:
    operator: qtn.TensorNetworkGenOperator
    diagnostics: EvolutionDiagnostics
```

The progress callback type is
`Callable[[ProgressRecord], None] | None`.

- [ ] **Step 4: Implement the reverse light cone as a pure helper**

```python
def reverse_lightcone_indices(
    gates: Sequence[qtn.Gate],
    initial_support: Collection[int],
) -> tuple[int, ...]:
    support = set(initial_support)
    selected: list[int] = []
    for index in range(len(gates) - 1, -1, -1):
        where = tuple(gates[index].qubits)
        if support.isdisjoint(where):
            continue
        support.update(where)
        selected.append(index)
    return tuple(selected)
```

Test that gates outside the cone are excluded and that support grows only
through selected two-site gates.

- [ ] **Step 5: Implement `ProductObservablePEPO`**

Subclass the pinned `qtn.CircuitPEPOSimpleUpdate`. Initialize the first local
operator with upstream `_initial_operator`, then apply remaining product
factors with
`gate_upper_(np.asarray(local_operator), site, contract=True)`.

Use this exact public declaration:

```python
class ProductObservablePEPO(qtn.CircuitPEPOSimpleUpdate):
    def evolve_product(
        self,
        operators: Mapping[int, np.ndarray],
        *,
        max_bond: int | None = None,
        cutoff: float | None = None,
        progress_every: int = 100,
        progress_callback: Callable[[ProgressRecord], None] | None = None,
    ) -> EvolutionResult:
        """Evolve a product observable through the recorded circuit."""
```

For every selected gate in reverse order:

```python
array = np.asarray(gate.array)
dimension = int(round(array.size ** 0.5))
gate_dagger = array.reshape(dimension, dimension).conj().T
local_info: dict[object, np.ndarray] = {}
operator.gate_simple_(
    gate_dagger,
    gate.qubits,
    gauges,
    info=local_info,
    **options,
)
```

This uses quimb's operator-sandwich behavior, so passing `G†` implements
`O ← G† O G`. Keep upstream `renorm=False`.

After the loop call `operator.gauge_simple_insert(gauges)`. Compute the
retained tail ratio for a nonempty singular-value vector as
`abs(s[-1])/abs(s[0])`, treating a zero leading value as infinity. This is a
diagnostic proxy, not an error bound.

Call the progress callback on the first gate, every `progress_every` gates,
and the final gate. Use `time.monotonic`.

- [ ] **Step 6: Implement circuit construction**

`build_pepo_circuit` must:

```python
circuit = ProductObservablePEPO(
    edges=interaction_edges(protocol),
    max_bond=max_bond,
    cutoff=cutoff,
    gate_opts={"renorm": False},
)
circuit.apply_gates(quimb_gates(protocol))
return circuit
```

Refuse a protocol with no CZ geometry and validate that every two-site gate is
on a declared edge.

- [ ] **Step 7: Run focused tests and commit**

```bash
uv run --project pepo pytest pepo/tests/test_engine.py -q
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/engine.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_engine.py
git commit -m "feat: evolve product observables as PEPOs"
```

---

### Task 7: Contract the normalized operator overlap and close the exact oracle

**Files:**

- Create: `pepo/src/ole_pepo/contraction.py`
- Create: `pepo/tests/test_contraction.py`
- Modify: `pepo/tests/test_engine.py`

**Interfaces:**

- Consumes: `EvolutionResult.operator`
- Produces:
  - `product_overlap_network(operator, operators) -> qtn.TensorNetwork`
  - `normalized_overlap_exact(operator, operators, optimize="auto-hq")
    -> complex`
  - `normalized_overlap_compressed(operator, operators, chi_env, cutoff,
    optimize="auto-hq", progress=False) -> complex`

- [ ] **Step 1: Write exact and compressed contraction tests**

For a three-site chain with a two-site gate, compute the dense reference with
Task 5 and require:

```python
assert normalized_overlap_exact(operator, {1: Z}) == pytest.approx(
    dense_value,
    abs=1e-11,
)
assert normalized_overlap_compressed(
    operator,
    {1: Z},
    chi_env=64,
    cutoff=0.0,
) == pytest.approx(dense_value, abs=1e-10)
```

Add a product-observable test using `{0: Z, 2: Z}`.

- [ ] **Step 2: Run to verify the contraction module is missing**

```bash
uv run --project pepo pytest pepo/tests/test_contraction.py -q
```

Expected: FAIL importing `ole_pepo.contraction`.

- [ ] **Step 3: Build the closed overlap network**

Copy the evolved operator. For each observable site in sorted order:

```python
network.gate_upper_(
    np.asarray(operators[site], dtype=np.complex128),
    site,
    contract=True,
)
```

Then reindex every upper physical index to its corresponding lower physical
index:

```python
mapping = {
    network.upper_ind(site): network.lower_ind(site)
    for site in network.gen_sites_present()
}
return network.reindex(mapping)
```

Validate that the operator contains every observable site.

- [ ] **Step 4: Implement exact and compressed scalar contraction**

Exact:

```python
closed = product_overlap_network(operator, operators)
raw = complex(closed.contract(all, optimize=optimize))
scale = math.ldexp(1.0, -len(tuple(operator.gen_sites_present())))
return raw * scale
```

Compressed:

```python
closed = product_overlap_network(operator, operators)
raw = complex(
    closed.contract_compressed(
        max_bond=chi_env,
        cutoff=cutoff,
        optimize=optimize,
        progbar=progress,
    )
)
scale = math.ldexp(1.0, -len(tuple(operator.gen_sites_present())))
return raw * scale
```

Require positive integer `chi_env`, nonnegative cutoff, finite real and
imaginary components, and leave physical-range enforcement to the runner.

- [ ] **Step 5: Add the seven-qubit exact PEPO test**

Using the real cropped QASM:

```python
@pytest.mark.parametrize("delta_zero", [True, False])
def test_seven_site_exact_pepo_matches_dense(ole_root, delta_zero):
    full = parse_qasm(FULL_QASM.read_text())
    protocol = seven_site_oracle_protocol(full, delta_zero=delta_zero)
    dense = normalized_ole_dense(protocol, (52,))
    circuit = build_pepo_circuit(protocol, max_bond=None, cutoff=0.0)
    evolved = circuit.evolve_product({52: Z}, cutoff=0.0)
    pepo = normalized_overlap_exact(evolved.operator, {52: Z})
    assert pepo == pytest.approx(dense, abs=1e-10)
```

Also require both δ=0 values to equal one within `10⁻¹⁰`.

- [ ] **Step 6: Run all numerical unit tests and commit**

```bash
uv run --project pepo pytest \
  pepo/tests/test_exact.py \
  pepo/tests/test_engine.py \
  pepo/tests/test_contraction.py -q
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/contraction.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_contraction.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_engine.py
git commit -m "feat: contract normalized PEPO OLE"
```

---

### Task 8: Add atomic records and the mandatory small-validation CLI

**Files:**

- Create: `pepo/src/ole_pepo/records.py`
- Create: `pepo/tests/test_records.py`
- Create: `scripts/validate_pepo_small.py`
- Create: `pepo/tests/test_small_validation_cli.py`
- Generate: `PEPO_SMALL_VALIDATION.md`
- Generate runtime:
  `<workspace>/results/issue119-pepo-small-oracle/manifest.json`

**Interfaces:**

- Produces:
  - `atomic_write_json(path, document) -> None`
  - `confirmation_token(document) -> str`
  - `core_source_digest(ole_root) -> str`
  - `peak_rss_bytes() -> int`
  - `SmallOracleStatus`
- CLI:
  - inspect: `uv run --project pepo python scripts/validate_pepo_small.py`
  - execute:
    `uv run --project pepo python scripts/validate_pepo_small.py
    --execute --confirm TOKEN`
  - optional output override: `--output-dir PATH`, defaulting to
    `<workspace>/results/issue119-pepo-small-oracle`

- [ ] **Step 1: Write record tests**

Test that:

```python
def test_atomic_write_json_replaces_complete_document(tmp_path):
    target = tmp_path / "manifest.json"
    atomic_write_json(target, {"status": "success", "value": 1.0})
    assert json.loads(target.read_text()) == {
        "status": "success",
        "value": 1.0,
    }
    assert not target.with_suffix(".json.tmp").exists()


def test_confirmation_token_is_order_independent():
    assert confirmation_token({"a": 1, "b": 2}) == confirmation_token(
        {"b": 2, "a": 1}
    )


def test_core_source_digest_changes_with_core_file(tmp_path):
    core = tmp_path / "pepo/src/ole_pepo"
    core.mkdir(parents=True)
    for name in ("qasm.py", "gates.py", "exact.py",
                 "engine.py", "contraction.py"):
        (core / name).write_text(name, encoding="utf-8")
    (tmp_path / "pepo/uv.lock").write_text("lock", encoding="utf-8")
    before = core_source_digest(tmp_path)
    (core / "engine.py").write_text("changed", encoding="utf-8")
    assert core_source_digest(tmp_path) != before
```

Define the token as the first 16 hexadecimal characters of SHA-256 over
compact, sorted-key UTF-8 JSON.

- [ ] **Step 2: Run to verify the records module is missing**

```bash
uv run --project pepo pytest pepo/tests/test_records.py -q
```

Expected: FAIL importing `ole_pepo.records`.

- [ ] **Step 3: Implement atomic records and resource readings**

Write to `path.with_suffix(path.suffix + ".tmp")`, flush, call `os.fsync`, then
replace with `os.replace`. Return Linux `ru_maxrss * 1024` and document that
macOS already reports bytes.

Define:

```python
@dataclass(frozen=True, slots=True)
class SmallOracleStatus:
    success: bool
    qasm_sha256: str
    quimb_commit: str
    core_source_digest: str
    dense_delta_zero: float
    pepo_delta_zero: float
    dense_delta_015: float
    pepo_delta_015: float
    max_absolute_error: float
```

`core_source_digest` hashes the relative path, one NUL byte, and file bytes
for these sorted paths:

```text
pepo/uv.lock
pepo/src/ole_pepo/qasm.py
pepo/src/ole_pepo/gates.py
pepo/src/ole_pepo/exact.py
pepo/src/ole_pepo/engine.py
pepo/src/ole_pepo/contraction.py
```

The full runner compares this digest with the small-oracle certificate. Report
or CLI-only changes therefore do not invalidate the numerical precondition.

- [ ] **Step 4: Write the CLI tests before the CLI**

Test inspect mode:

```python
completed = subprocess.run(
    [sys.executable, str(SCRIPT)],
    cwd=ole_root,
    text=True,
    capture_output=True,
    check=True,
)
assert re.search(r"^confirmation_token=[0-9a-f]{16}$",
                 completed.stdout, re.MULTILINE)
workspace_root = ole_root.parents[4]
assert not (
    workspace_root / "results/issue119-pepo-small-oracle/manifest.json"
).exists()
```

For execute mode, run against a temporary output root and assert the manifest
contains both δ values, exact errors, timings, and `status="success"`.

- [ ] **Step 5: Implement `validate_pepo_small.py`**

The dry run must print:

```text
sites=33,39,49,50,51,52,53
observable=Z52
delta_modes=0,0.15
exact_tolerance=1e-10
confirmation_token=<16 hex>
```

Execution must:

1. validate and parse the full QASM;
2. build both seven-site protocols;
3. compute both dense values;
4. compute both untruncated PEPO values;
5. run truncated `Dop={1,2,4}` exact contractions for δ=0.15;
6. enforce `10⁻¹⁰`, imaginary-part, and physical-range checks;
7. atomically write the JSON manifest;
8. render `PEPO_SMALL_VALIDATION.md` with the exact commands, values, errors,
   environment revision, wall time, and peak RSS.

Use `print(..., flush=True)` for every progress line.
Resolve the workspace root from the script location, not the caller's current
directory.

- [ ] **Step 6: Run tests, then execute the real local oracle**

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv run --project "$OLE_ROOT/pepo" pytest \
  "$OLE_ROOT/pepo/tests/test_records.py" \
  "$OLE_ROOT/pepo/tests/test_small_validation_cli.py" -q
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py"
```

Copy the printed token into:

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py" \
  --execute --confirm "$PEPO_CONFIRMATION_TOKEN"
```

Expected: exit 0, `status=success`, max exact error at most `10⁻¹⁰`, and local
resource use below 10 minutes / 16 GB. If any exact condition fails, stop here
and use `superpowers:systematic-debugging`; do not continue to Task 9.

- [ ] **Step 7: Verify the manifest and commit code plus the short report**

```bash
uv run --project "$OLE_ROOT/pepo" python -c \
  'import json; p="results/issue119-pepo-small-oracle/manifest.json"; d=json.load(open(p)); assert d["status"]=="success"; assert d["validation"]["max_absolute_error"] <= 1e-10; print(d["validation"])'
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/records.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_records.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_small_validation_cli.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/validate_pepo_small.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_SMALL_VALIDATION.md
git commit -m "feat: validate PEPO against seven-qubit oracle"
```

---

### Task 9: Implement the full deterministic runner and scan-cell adapter

**Files:**

- Create: `scripts/run_pepo.py`
- Create: `scripts/run_pepo_array_cell.py`
- Create: `pepo/tests/test_full_runner.py`

**Interfaces:**

- Direct CLI:
  - dry run:
    `run_pepo.py --dop D --chi-env E --delta {0,0.15} --output PATH`
  - execute: add `--execute --confirm TOKEN`
  - exact-certificate override: `--oracle-manifest PATH`, defaulting to
    `<workspace>/results/issue119-pepo-small-oracle/manifest.json`
- Array CLI:
  - `run_pepo_array_cell.py --run-spec PATH --selector N`
  - environment fallbacks: `HARNESS_RUN_SPEC` and `SLURM_ARRAY_TASK_ID`
- Manifest result fields:
  - `result.value_real`
  - `result.value_imag`
  - `result.wall_seconds`
  - `result.peak_rss_bytes`
  - `diagnostics.causal_gates`
  - `diagnostics.final_support_size`
  - `diagnostics.max_realized_bond`
  - `diagnostics.max_retained_tail_ratio`

- [ ] **Step 1: Write dry-run and precondition tests**

Use dependency injection so tests replace the expensive evolution function
with a fake returning a known scalar. Test:

```text
missing small-oracle manifest → refused
stale QASM, quimb revision, or core-source digest in small manifest → refused
dry run → one confirmation token and no final manifest
wrong token → refused
successful fake run → atomic success manifest
imaginary part above 1e-8 → failed manifest
real part outside [−1−1e-8,1+1e-8] → failed manifest
```

- [ ] **Step 2: Run to verify both scripts are absent**

```bash
uv run --project pepo pytest pepo/tests/test_full_runner.py -q
```

Expected: FAIL loading the runner modules.

- [ ] **Step 3: Implement the direct runner**

The confirmation payload contains:

```python
{
    "qasm_sha256": EXPECTED_QASM_SHA256,
    "observable_sites": [52, 59, 72],
    "delta": args.delta,
    "dop": args.dop,
    "chi_env": args.chi_env,
    "evolution_cutoff": args.evolution_cutoff,
    "contraction_cutoff": args.contraction_cutoff,
    "quimb_commit": PINNED_QUIMB_COMMIT,
    "core_source_digest": core_source_digest(OLE_ROOT),
    "output": str(args.output),
}
```

Execution must:

1. revalidate the small-oracle manifest;
2. parse the original QASM and optionally zero exactly 24 perturbation gates;
3. construct a full 49-site PEPO circuit;
4. evolve `{52: Z, 59: Z, 72: Z}` at `Dop`;
5. contract the overlap at `χenv`;
6. retain the raw complex result;
7. enforce finite, imaginary-part, and physical-range checks;
8. atomically write `.partial.json` progress and the final manifest.

The progress callback writes after the first causal gate, every 100 causal
gates, and the final causal gate. It prints the same record with
`flush=True`.

- [ ] **Step 4: Implement the generic scan-cell adapter**

Reuse the established `run_bp_array_cell.py` structure. `selected_payload`
must merge:

```python
settings = {**run_spec.get("settings", {}), **cell.get("settings", {})}
params = cell["params"]
delta = params.get("delta", settings["delta"])
```

The adapter:

1. calls `run_pepo.py` in dry-run mode;
2. extracts exactly one 16-hex token;
3. calls it again with `--execute --confirm`;
4. validates the returned result against the selected payload;
5. stores the direct-runner document at
   `<run_dir>/cells/<cell_id>/pepo-result.json`;
6. writes the scan cell manifest to
   `<run_dir>/cells/<cell_id>/manifest.json`;
7. echoes `params`, `settings`, and `provenance` unchanged.

- [ ] **Step 5: Add array-selection tests**

Test one-based selectors, environment-variable fallbacks, out-of-range
selectors, merged settings, output paths, and `--inspect-only`. Use temporary
run specs; no tensor contraction occurs in these tests.

- [ ] **Step 6: Run tests and inspect a real full dry run**

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv run --project "$OLE_ROOT/pepo" \
  pytest "$OLE_ROOT/pepo/tests/test_full_runner.py" -q
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/run_pepo.py" \
  --dop 2 \
  --chi-env 16 \
  --delta 0.15 \
  --output results/issue119-pepo-dry-run/manifest.json
```

Expected: a setup summary and token, no PEPO evolution, and no final
`manifest.json`.

- [ ] **Step 7: Commit**

```bash
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/run_pepo.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/run_pepo_array_cell.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_full_runner.py
git commit -m "feat: add deterministic full PEPO runner"
```

---

### Task 10: Plan, collect, analyze, and plot the two-axis scan

**Files:**

- Create: `configs/pepo-pilot-axes.json`
- Create: `configs/pepo-delta0-control-axes.json`
- Create: `configs/pepo-settings.json`
- Create: `configs/pepo-provenance.json`
- Create: `scripts/analyze_pepo.py`
- Create: `pepo/tests/test_analysis.py`

**Interfaces:**

- Consumes: generic parameter-scan CSV and cell manifests.
- Produces:
  - `assess_convergence(records, bp_mean, bp_budget, target) -> dict`
  - `PEPO_49Q_VALIDATION.md`
  - `pepo-convergence.png`

- [ ] **Step 1: Add the fixed pilot configuration**

`configs/pepo-pilot-axes.json`:

```json
{
  "dop": [2, 4],
  "chi_env": [16, 32]
}
```

`configs/pepo-delta0-control-axes.json`:

```json
{
  "dop": [4],
  "chi_env": [32],
  "delta": [0]
}
```

`configs/pepo-settings.json`:

```json
{
  "delta": 0.15,
  "observable_sites": [52, 59, 72],
  "evolution_cutoff": 1e-12,
  "contraction_cutoff": 1e-12,
  "imaginary_tolerance": 1e-8,
  "physical_tolerance": 1e-8,
  "progress_every": 100
}
```

`configs/pepo-provenance.json`:

```json
{
  "qasm_sha256": "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455",
  "quimb_commit": "3c89529fe0a3487133a3928201691161e110abdf",
  "design_commit": "3b83bfb"
}
```

- [ ] **Step 2: Write synthetic convergence tests**

Use three points on each cut through the largest corner:

```python
records = [
    {"dop": 2, "chi_env": 64, "value": 0.8179},
    {"dop": 4, "chi_env": 64, "value": 0.8182},
    {"dop": 8, "chi_env": 16, "value": 0.8180},
    {"dop": 8, "chi_env": 32, "value": 0.8183},
    {"dop": 8, "chi_env": 64, "value": 0.8185},
]
assessment = assess_convergence(
    records,
    bp_mean=0.8183229131612796,
    bp_budget=0.0044,
    target=0.001,
)
assert assessment["delta_dop"] == pytest.approx(0.0003)
assert assessment["delta_chi_env"] == pytest.approx(0.0002)
assert assessment["epsilon_pepo"] == pytest.approx(0.0005)
assert assessment["internally_converged"] is True
assert assessment["agrees_with_bp"] is True
```

Add failure cases for missing corner cells, fewer than three distinct levels
per axis, a growing last difference, and `εPEPO>0.001`.

- [ ] **Step 3: Run to verify the analyzer is missing**

```bash
uv run --project pepo pytest pepo/tests/test_analysis.py -q
```

Expected: FAIL loading `scripts/analyze_pepo.py`.

- [ ] **Step 4: Implement convergence assessment**

The analyzer must:

1. load all successful manifests across one or more run directories;
2. reject inconsistent QASM, quimb, observable, cutoffs, or δ;
3. identify the maximum completed corner and its immediate lower neighbor on
   each axis;
4. compute `ΔDop`, `Δχenv`, and their sum;
5. require at least three distinct values on both axes;
6. mark a trend unresolved if the newest difference on either axis exceeds
   the preceding difference by more than `10⁻¹²`;
7. compare with BP using `εBP=0.0044`;
8. write a machine-readable `assessment.json`.

- [ ] **Step 5: Render the convergence plot and report**

Use two cuts sharing the converged corner:

```text
left:  F versus Dop at the largest χenv
right: F versus χenv at the largest Dop
```

Draw the BP-TN mean and its `±0.0044` band. Label computed points, do not draw
an infinite-bond extrapolation, and state when a point is missing or failed.
Use the `scientific-visualization` skill at execution time.

The report leads with `FPEPO`, `εPEPO`, internal convergence status, and
cross-method status. It must call the budget empirical rather than rigorous.

- [ ] **Step 6: Exercise the generic scan planner locally**

From the repository root:

```bash
python3 scripts/parameter_scan.py plan \
  --axes tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-pilot-axes.json \
  --settings tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-settings.json \
  --provenance tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-provenance.json \
  --run-id issue119-pepo-49q-pilot \
  --run-dir results/issue119-pepo-49q-pilot
```

Expected: exactly four cells in `run_spec.json`. Run every array cell with
`--inspect-only` and verify the payloads are the Cartesian product.

- [ ] **Step 7: Run tests and commit**

```bash
uv run \
  --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo \
  pytest \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_analysis.py -q
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-pilot-axes.json \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-delta0-control-axes.json \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-settings.json \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-provenance.json \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/analyze_pepo.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests/test_analysis.py
git commit -m "feat: analyze PEPO bond convergence"
```

---

### Task 11: Complete local regression verification and documentation

**Files:**

- Modify: `README.md`
- Verify: every Python and Julia test

**Interfaces:**

- Produces: fresh-checkout setup, small validation, scan planning, dry-run,
  collection, and analysis commands in the issue README.

- [ ] **Step 1: Add the PEPO workflow to the README**

Document these exact phases:

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv sync --project "$OLE_ROOT/pepo" --frozen
uv run --project "$OLE_ROOT/pepo" pytest "$OLE_ROOT/pepo/tests" -q
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py"
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/run_pepo.py" \
  --dop 2 --chi-env 16 --delta 0.15 \
  --output results/issue119-pepo-dry-run/manifest.json
```

Explain `Dop`, `χenv`, the absence of seed, the exact-oracle gate, ignored
workspace-root runtime results, and the two report files.

- [ ] **Step 2: Run the complete PEPO suite**

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv run --project "$OLE_ROOT/pepo" pytest "$OLE_ROOT/pepo/tests" -q
```

Expected: zero failures and zero unexpected skips.

- [ ] **Step 3: Run the existing issue Julia suite**

```bash
julia --project=. tests/runtests.jl
```

Run from the issue directory. Expected: all existing BP-TN tests still pass.

- [ ] **Step 4: Run the repository test suite**

From the repository root:

```bash
make test
```

Expected: exit 0. If an unrelated pre-existing failure appears, capture its
test name and reproduce it before deciding whether it is in scope.

- [ ] **Step 5: Verify the source tree and commit**

```bash
git status --short
git diff --check
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/README.md
git commit -m "docs: add PEPO OLE workflow"
```

Do not stage ignored `results/` or unrelated existing changes.

---

### Task 12: Run and certify the local seven-qubit oracle

**Files:**

- Update generated: `PEPO_SMALL_VALIDATION.md`
- Inspect runtime: `<workspace>/results/issue119-pepo-small-oracle/manifest.json`

**Interfaces:**

- Produces the exact-oracle success evidence required by every full runner.

- [ ] **Step 1: Reconfirm the exact compute setup**

Before executing, print and ratify:

```text
sites={33,39,53,52,51,50,49}
edges={(33,39),(39,53),(53,52),(52,51),(51,50),(50,49)}
observable=Z52
delta={0,0.15}
target=2^-7 Tr[O C† O C]
dense/PEPO tolerance=1e-10
```

This is the already approved setup; stop only if the user corrects it.

- [ ] **Step 2: Run the dry setup and exact calculation**

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py"
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py" \
  --execute --confirm "$PEPO_CONFIRMATION_TOKEN"
```

Set `PEPO_CONFIRMATION_TOKEN` to the exact token printed by the immediately
preceding dry run.

- [ ] **Step 3: Inspect evidence, not only the exit code**

```bash
uv run --project "$OLE_ROOT/pepo" python -c \
  'import json; d=json.load(open("results/issue119-pepo-small-oracle/manifest.json")); print(json.dumps({"status":d["status"],"validation":d["validation"],"wall_seconds":d["resources"]["wall_seconds"],"peak_rss_bytes":d["resources"]["peak_rss_bytes"]},indent=2))'
```

Required:

```text
status=success
max_absolute_error≤1e-10
|dense_delta_zero−1|≤1e-10
|pepo_delta_zero−1|≤1e-10
wall_seconds<600
peak_rss_bytes<16 GiB
```

- [ ] **Step 4: Re-run the exact scalar once**

Repeat the execution into a temporary ignored result directory and require
both exact PEPO scalars to agree with the first run within `10⁻¹²`. This
confirms determinism before remote work.

Use:

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py" \
  --output-dir results/issue119-pepo-small-oracle-repeat
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py" \
  --output-dir results/issue119-pepo-small-oracle-repeat \
  --execute --confirm "$PEPO_REPEAT_TOKEN"
```

Set `PEPO_REPEAT_TOKEN` from the immediately preceding dry run.

- [ ] **Step 5: Commit the evidence report**

```bash
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_SMALL_VALIDATION.md
git commit -m "docs: record PEPO exact-oracle validation"
```

Do not proceed if any required field fails.

---

### Task 13: Configure the approved remote target and run the pilot

**Files:**

- Local-only: `skills/using-slurm/profiles/zyli.toml`
- Local-only: `skills/using-slurm/profiles/active.toml`
- Runtime: `<workspace>/results/issue119-pepo-49q-pilot/`
- Runtime: `<workspace>/results/issue119-pepo-49q-delta0/`

**Interfaces:**

- Consumes: successful small-oracle manifest and four-cell pilot run spec.
- Produces: fetched per-cell manifests with scheduler `Elapsed` and `MaxRSS`.

- [ ] **Step 1: Use the cluster setup skill for the exact target**

Invoke `setup-cluster` for `zyli@172.16.42.215`, using WSL's native `ssh`.
Do not use Windows OpenSSH and do not set SCNet active. The created profile is
local-only and must identify:

```text
ssh alias/user/host
remote repository path
Slurm scheduler
visible partitions
per-partition cores and memory
network availability
hard and soft limits
allowed result paths
```

After creation, run `git status --short -- skills/using-slurm/profiles`. If
`zyli.toml` appears, add that exact path to the repository-local
`.git/info/exclude` with filesystem approval; never commit the host, user, or
key-path profile.

- [ ] **Step 2: Run the required read-only prechecks**

From the repository root:

```bash
HARNESS_CLUSTER_PROFILE=zyli scripts/harness_slurm.sh precheck
HARNESS_CLUSTER_PROFILE=zyli scripts/harness_slurm.sh probe-partitions
```

State: “about to act on cluster `zyli` as account `zyli`.” Present the real
partition table and ask the user to ratify one partition before submission.

- [ ] **Step 3: Ship only authorized code**

Capture `git status --porcelain` and check whether the QASM and baseline
configuration are tracked:

```bash
git ls-files --error-unmatch \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/baseline-49x648.toml
```

If both are tracked, prefer the git strategy after the user authorizes
push/pull of the implementation commits. If either is untracked, preview and
request approval for an exact rsync set containing only:

```text
issue-119-ole/pepo/                  excluding .venv and caches
issue-119-ole/scripts/export_protocol_digest.jl
issue-119-ole/scripts/validate_pepo_small.py
issue-119-ole/scripts/run_pepo.py
issue-119-ole/scripts/run_pepo_array_cell.py
issue-119-ole/scripts/analyze_pepo.py
issue-119-ole/configs/baseline-49x648.toml
issue-119-ole/configs/pepo-*.json
issue-119-ole/inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm
results/issue119-pepo-small-oracle/manifest.json
```

Preserve paths relative to the repository root. The last file is ignored but
required as the machine-readable exact-oracle certificate. Never silently
commit, push, or rsync dirty user files.

- [ ] **Step 4: Recreate the pinned environment remotely**

If the profile confirms login-node internet:

```bash
uv sync \
  --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo \
  --frozen
```

If the profile confirms no remote internet, use `build-apptainer-image` to
build an image locally from the locked environment, transfer the image, and
run the same environment smoke test inside it.

In either route, verify on the remote target:

```bash
uv run --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo \
  python -c 'import quimb.tensor as qtn; print(qtn.CircuitPEPOSimpleUpdate)'
```

Also run `scripts/run_pepo.py` in dry-run mode remotely. It must accept the
shipped small-oracle manifest and core-source digest before any Slurm
submission.

- [ ] **Step 5: Generate and inspect the pilot run spec**

Use the Task 10 planning command. Then:

```bash
uv run \
  --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo \
  python tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/run_pepo_array_cell.py \
  --run-spec results/issue119-pepo-49q-pilot/run_spec.json \
  --selector 1 \
  --inspect-only
```

Inspect all four selectors and verify only `Dop` and `χenv` vary.
Transfer the exact ignored `run_spec.json` to the same
`results/issue119-pepo-49q-pilot/` path under the remote repository before
test-only submission.

- [ ] **Step 6: Run Slurm test-only feasibility**

Set `PEPO_PARTITION` to the exact partition ratified after the live probe.
Before the request, reprint and confirm:

```text
49 active heavy-hex sites; finite QASM graph
C = audited 73-layer, 648-CZ echo circuit
O = Z52 Z59 Z72
δ = 0.15
target = 2^-49 Tr[O C† O C]
pilot = Dop {2,4} × χenv {16,32}
```

Use the initial pilot request:

```bash
HARNESS_CLUSTER_PROFILE=zyli scripts/harness_slurm.sh submit \
  --test-only \
  --array 4 \
  --run-spec results/issue119-pepo-49q-pilot/run_spec.json \
  --command 'uv run --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo python tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/run_pepo_array_cell.py' \
  --partition "$PEPO_PARTITION" \
  --time 02:00:00 \
  --cpus 8 \
  --extra '--mem=32G'
```

Read the scheduler response. If it rejects or estimates an impractical start,
present wait/change/stop and obtain ratification before a real submit.

- [ ] **Step 7: Submit and monitor the four-cell pilot**

After ratification:

```bash
HARNESS_CLUSTER_PROFILE=zyli scripts/harness_slurm.sh submit \
  --array 4 \
  --run-spec results/issue119-pepo-49q-pilot/run_spec.json \
  --command 'uv run --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo python tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/run_pepo_array_cell.py' \
  --partition "$PEPO_PARTITION" \
  --time 02:00:00 \
  --cpus 8 \
  --extra '--mem=32G'
```

Record the returned job ID. Follow the `using-slurm` settle-time sequence:

1. pending/running transition;
2. first real progress line;
3. periodic 30–60 minute pulse for a long run;
4. `sacct` classification after completion.

- [ ] **Step 8: Fetch and classify all cells**

```bash
HARNESS_CLUSTER_PROFILE=zyli scripts/harness_slurm.sh fetch \
  issue119-pepo-49q-pilot
HARNESS_CLUSTER_PROFILE=zyli scripts/harness_slurm.sh classify \
  issue119-pepo-49q-pilot "$PEPO_JOB_ID"
```

Confirm every one of four cell manifests exists. Scheduler completion without
a success manifest is a failed scientific cell.

- [ ] **Step 9: Run the δ=0 control at the pilot corner**

Plan the one-cell control with
`configs/pepo-delta0-control-axes.json`, repeat test-only feasibility with
resources updated from pilot measurements, submit, monitor, fetch, and require
the control to enter its declared PEPO convergence behavior. A low-`Dop`
control may differ from one; it is evidence about truncation, not automatically
a code defect after the exact oracle has passed.

The planning command is:

```bash
python3 scripts/parameter_scan.py plan \
  --axes tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-delta0-control-axes.json \
  --settings tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-settings.json \
  --provenance tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-provenance.json \
  --run-id issue119-pepo-49q-delta0 \
  --run-dir results/issue119-pepo-49q-delta0
```

Because `delta` is present in the cell parameters, it overrides the shared
`delta=0.15` setting in the array adapter.

---

### Task 14: Extend adaptively, compare methods, and issue the final report

**Files:**

- Update generated: `PEPO_49Q_VALIDATION.md`
- Modify: `README.md`
- Runtime: `<workspace>/results/issue119-pepo-49q-wave-*/`
- Runtime:
  `<workspace>/results/issue119-pepo-49q-*/pepo-convergence.png`

**Interfaces:**

- Produces the final PEPO value, empirical error, convergence plot, resource
  record, and qualified BP-TN agreement classification.

- [ ] **Step 1: Measure the pilot before choosing later resources**

Create a table:

```text
Dop | χenv | status | F | causal gates | max bond | wall | MaxRSS
```

Use actual `Elapsed` and `MaxRSS` to set the next request. Do not request more
than 24 hours, 32 CPUs, or 256 GB per cell without a new design discussion.

- [ ] **Step 2: Run the mandatory third level on both fixed-axis cuts**

Create two one-axis run specs:

```text
issue119-pepo-49q-wave-1-dop:
  Dop  ∈ {2,4,8}
  χenv = 64
  δ    = 0.15

issue119-pepo-49q-wave-1-env:
  Dop  = 8
  χenv ∈ {16,32,64}
  δ    = 0.15
```

Together with the pilot, these supply three points on each cut through the new
largest corner. The duplicated `(8,64)` cell is the deterministic cross-run
check. Submit each three-cell array only after test-only feasibility and
resource ratification, then fetch and classify all six manifests.

Create the ignored file
`results/issue119-pepo-49q-wave-1-dop/axes.json`:

```json
{"dop": [2, 4, 8], "chi_env": [64]}
```

Create
`results/issue119-pepo-49q-wave-1-env/axes.json`:

```json
{"dop": [8], "chi_env": [16, 32, 64]}
```

Plan them from the repository root:

```bash
python3 scripts/parameter_scan.py plan \
  --axes results/issue119-pepo-49q-wave-1-dop/axes.json \
  --settings tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-settings.json \
  --provenance tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-provenance.json \
  --run-id issue119-pepo-49q-wave-1-dop \
  --run-dir results/issue119-pepo-49q-wave-1-dop

python3 scripts/parameter_scan.py plan \
  --axes results/issue119-pepo-49q-wave-1-env/axes.json \
  --settings tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-settings.json \
  --provenance tracks/qcs/solutions/CCB-LV.999/issue-119-ole/configs/pepo-provenance.json \
  --run-id issue119-pepo-49q-wave-1-env \
  --run-dir results/issue119-pepo-49q-wave-1-env
```

- [ ] **Step 3: Assess the first three-level convergence**

Collect pilot plus wave manifests and run:

```bash
python3 scripts/parameter_scan.py collect \
  --run-spec results/issue119-pepo-49q-wave-1-dop/run_spec.json \
  --success-field status \
  --success-value success \
  --value-field result.value_real \
  --value-field result.wall_seconds \
  --value-field result.peak_rss_bytes

python3 scripts/parameter_scan.py collect \
  --run-spec results/issue119-pepo-49q-wave-1-env/run_spec.json \
  --success-field status \
  --success-value success \
  --value-field result.value_real \
  --value-field result.wall_seconds \
  --value-field result.peak_rss_bytes

uv run \
  --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo \
  python tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/analyze_pepo.py \
  --run-dir results/issue119-pepo-49q-pilot \
  --run-dir results/issue119-pepo-49q-wave-1-dop \
  --run-dir results/issue119-pepo-49q-wave-1-env
```

The analyzer must see three distinct levels `{2,4,8}` and `{16,32,64}` before
it may return `internally_converged=true`.

- [ ] **Step 4: Apply the exact adaptive rule**

At each completed largest corner:

```text
ΔDop  = |F(Dmax,χmax)−F(Dprev,χmax)|
Δχenv = |F(Dmax,χmax)−F(Dmax,χprev)|
```

- Stop if their sum is at most `0.001` and neither newest difference grows.
- If `Dop` is extended to `Dnew`, run the three-cell row
  `Dop=Dnew` at the current three largest `χenv` values. This preserves the
  environment cut at the new largest `Dop`.
- If `χenv` is extended to `χnew`, run the three-cell column
  `χenv=χnew` at the current three largest `Dop` values. This preserves the
  operator-bond cut at the new largest `χenv`.
- If both axes extend, use separate row and column run specs; their duplicated
  new corner is a determinism check.
- Extend `Dop` through `16`, then `32`, and `χenv` through `128`.
- Stop unresolved at `Dop=32` or `χenv=128`; do not extrapolate.

Each changed grid receives a new
`issue119-pepo-49q-wave-N-{dop|env}` run ID.

- [ ] **Step 5: Perform the approved BP-TN comparison**

Use:

```text
FBP = 0.8183229131612796
εBP = 0.0044
εPEPO = ΔDop + Δχenv
agreement iff |FPEPO−FBP| ≤ εPEPO+εBP
```

If PEPO is unresolved, label the comparison “diagnostic.” If
`εPEPO≤0.0005`, add the approved high-precision label. Do not average PEPO,
BP-TN, or either public value.

- [ ] **Step 6: Generate and inspect the final artifacts**

The analyzer writes:

```text
PEPO_49Q_VALIDATION.md
assessment.json
parameter-scan.csv
pepo-convergence.png
```

The report must include:

```text
problem and trace definition
QASM and software provenance
Dop and χenv physical/numerical meanings
all successful and failed cells
δ=0 control
FPEPO and εPEPO
BP-TN value and εBP
agreement classification
public values as contextual references
wall time and peak memory
remaining non-rigorous uncertainty
```

Use `scientific-visualization` to inspect the plot at its final rendered size.

- [ ] **Step 7: Run final verification**

```bash
uv run \
  --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo \
  pytest tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/tests -q
(cd tracks/qcs/solutions/CCB-LV.999/issue-119-ole && \
  julia --project=. tests/runtests.jl)
python3 scripts/parameter_scan.py collect \
  --run-spec results/issue119-pepo-49q-wave-1-dop/run_spec.json \
  --success-field status \
  --success-value success \
  --value-field result.value_real
git diff --check
```

Run from the repository root. Inspect the final assessment and every cell
classification; do not infer scientific success from test or scheduler status
alone.

- [ ] **Step 8: Update the README and commit durable conclusions**

Link `PEPO_SMALL_VALIDATION.md`, `PEPO_49Q_VALIDATION.md`, and the ignored
local plot path from `README.md`.

```bash
git add \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/README.md \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_49Q_VALIDATION.md
git commit -m "docs: report PEPO validation of OLE baseline"
```

Do not stage ignored raw results, unrelated files, credentials, or local
cluster profiles.

---

## Completion gate

The implementation is complete only if one of these two honest outcomes is
documented:

1. **Converged validation:** seven-qubit exact tests pass,
   `εPEPO≤10⁻³`, and the approved BP-TN comparison is classified.
2. **Resource-bounded unresolved result:** seven-qubit exact tests pass, all
   attempted full cells and failures are preserved, the adaptive scan reaches
   its approved cap, and no unsupported high-precision or agreement claim is
   made.

Passing unit tests alone is not completion. A running or completed Slurm job
alone is not evidence. Fetched manifests, the convergence assessment, and the
two durable reports close the work.
