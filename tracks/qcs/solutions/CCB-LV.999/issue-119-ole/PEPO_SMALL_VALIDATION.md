# PEPO small-oracle validation

Status: success — the seven-site PEPO result agrees with the independent dense oracle within 1e-10.

## Commands

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv run --project "$OLE_ROOT/pepo" python "$OLE_ROOT/scripts/validate_pepo_small.py"
uv run --project "$OLE_ROOT/pepo" python "$OLE_ROOT/scripts/validate_pepo_small.py" --execute --confirm "c9457cb9056bdb5b" --output-dir "/home/peter0627/project/quantum.harness/results/issue119-pepo-small-oracle"
```

## Results

| quantity | value |
| --- | ---: |
| dense δ=0 | 0.99999999999997846 |
| PEPO δ=0 | 0.99999999999998535 |
| dense δ=0.15 | 0.96509609391749107 |
| PEPO δ=0.15 | 0.96509609391749729 |
| exact error δ=0 | 6.883e-15 |
| exact error δ=0.15 | 6.217e-15 |
| maximum exact error | 6.883e-15 |

## Truncated δ=0.15 contractions

| Dop | value | absolute error from dense |
| ---: | ---: | ---: |
| 1 | 3.05041498393646e-06 | 9.651e-01 |
| 2 | 0.001519203623421933 | 9.636e-01 |
| 4 | 0.068810381415524438 | 8.963e-01 |

## Provenance and resources

- QASM SHA-256: `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455`
- quimb revision: `3c89529fe0a3487133a3928201691161e110abdf`
- numerical-core digest: `4b07886e968661b20424523deb9fb2a3d5deae062392016f6922c74f1ac1e300`
- wall time: 19.688 s
- peak RSS: 296583168 bytes
