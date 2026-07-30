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

## G5 active input audit

Checked on 2026-07-30 against both tracker issue
[`operator_loschmidt_echo_49x1296`](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/11)
and the current file in the Tracker repository.

| Field | Repository export used for G5 | Issue #11 attachment |
|---|---:|---:|
| format | OpenQASM 3.0 | OpenQASM 2.0 |
| bytes | `321769` | `297926` |
| lines | `9445` | `9440` |
| SHA-256 | `3748e2c026c118f9d6c7499093ea43e41a45251b6bf8d3adb6fb056f718f6cc0` | `d237a273c7cc233e9d64039ad06613af17eb472b19bda12f4ce458b9c4541645` |
| Git object | `829be362d1526ea9afe8e13fe1594e2e00eaa2e2` | `1c2f9d9f37b145bac07558196040e7f7ce372823` |
| OpenQASM register | `q[156]` | `q[156]` |
| active physical qubits | `49` | `49` |
| barrier-delimited layers | `145` | `145` |
| CZ gates | `1296` | `1296` |
| all non-barrier gates | `9292` | `9292` |

The repository export contains only three representational changes relevant
to parsing: the OpenQASM 3 header, an explicit standard `sxdg` definition, and
spaces after commas. After the parser's strict normalization of that prelude,
the two files produce exactly equal TNQS layer lists, including gate order,
physical labels, and floating-point angles. G5 uses the repository export so
the run is directly content-addressed by the Tracker Git blob; the older issue
attachment remains an independent input-equivalence check.

The active δ=0 control, when run in G6, will again replace exactly 24
`rz(0.3)` perturbation rotations and no other gate.
