## Team

| | |
|---|---|
| **Team name** | OrbitBreakers |
| **Members** | Qingyun Qian, Muchu Chen, Huaiming Yu |

## Challenge

| Row | |
|---|---|
| **Challenge** | Test whether an explicit simplicity bias can recover hidden arithmetic functions from polynomially many examples, going beyond training-set memorization by requiring exact held-out prediction and compact Boolean circuits. |
| **Catalog issue** | Addresses #71 — “Occam's Circuit,” released by Jin-Guo Liu, HKUST(Guangzhou). |
| **Track** | `qcs`, from issue #71's explicit instruction to work under `tracks/qcs/solutions/<your-team>/`; this overrides its `MPS Based Algorithm` method field. |

## Solution repository

[hmyuuu/BooleanRazor](https://github.com/hmyuuu/BooleanRazor)

## Team SOTA

| Instance | Disclosed control function | Test rows | Exact accuracy | Reachable gates |
|---|---|---:|---:|---:|
| mystery-A | `x + y` | 2,000 | 1.0 | 37 |
| mystery-B | `abs(x - y)` | 2,000 | 1.0 | 49 |
| mystery-C | `x * y` | 1,500 | 1.0 | 168 |
| mystery-D | `x² + y²` | 624 | 1.0 | 127 |
| **Informational total** | — | **6,124** | **1.0 micro** | **381** |
