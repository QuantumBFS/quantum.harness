# G2 input audit

Checked against the current attachment on tracker issue
[`operator_loschmidt_echo_49x648`](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/10)
on 2026-07-27.

| Field | Current downloaded attachment |
|---|---:|
| file id | `23483330` |
| bytes | `150686` |
| SHA-256 | `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455` |
| OpenQASM register | `q[156]` |
| active physical qubits | `49` |
| barrier-delimited layers | `73` |
| CZ gates | `648` |
| all non-barrier gates | `4756` |

The planning document records 162721 bytes and Git blob
`716305eb99ed9fafb356bf971269ff1d8d66b03e`. Those values do not match the
current issue attachment: the downloaded content has the Git object hash
`17e3228416f13c438f803623f69260c959dea690`. The runner therefore pins the
current attachment by SHA-256 and byte count and refuses changed content.
Production results must cite this audit rather than silently mixing the two
identities.

The δ=0 control is derived from the same validated QASM by replacing exactly
24 `rz(0.3)` perturbation rotations with `rz(0.0)`. The count is mandatory;
if the circuit layout changes, construction of the control stops.
