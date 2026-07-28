"""Cross-language canonical gate-manifest checks for the audited OLE circuit."""

import json
from pathlib import Path
import subprocess

import pytest

from ole_pepo.qasm import canonical_gate_digest, canonical_gate_records, parse_qasm


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


@pytest.fixture
def ole_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_tiny_protocol_digest_uses_stable_gate_records():
    """Breaks if gate identity or IEEE-754 angle serialization changes."""
    protocol = parse_qasm(TINY_QASM)

    assert canonical_gate_records(protocol) == (
        "0|0|rx|52|3ff921fb54442d18",
        "0|1|sx|53|-",
        "0|2|cz|52,53|-",
        "1|3|rz|33|3fd3333333333333",
        "1|4|sdg|52|-",
    )
    assert canonical_gate_digest(protocol) == (
        "0f7755e1726cefcb6d54805e9efffff5c87d9e6ce7b0e2a03688e653516c4008"
    )


def test_full_protocol_digest_matches_julia(ole_root: Path):
    """Breaks if either parser changes the full audited gate manifest."""
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
