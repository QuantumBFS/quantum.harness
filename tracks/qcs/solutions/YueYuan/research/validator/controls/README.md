# Validator Controls

These fixtures exercise the YueYuan challenge #113 validator before any generated research results are trusted.

| Control | Expected result | Purpose |
|---|---:|---|
| `passing-synthetic` | accepted | Smoke-test a minimal valid result table. |
| `cheater` | rejected | Blocks lookup-table and private-truth style source. |
| `wrong-answer` | rejected | Blocks exact true infidelity above `1e-3`. |
| `timeout` | rejected | Blocks candidates that exceed wall-clock budget. |
| `env-escape` | rejected | Blocks network/private-path escape attempts. |
| `lucky-noisy-fidelity` | rejected | Blocks stopping on noisy fidelity without exact final check. |
| `weak-baseline` | rejected | Requires full raw and random-subspace controls. |
| `cherry-picked-k` | rejected | Requires the agreed Hessian `k` sweep. |
| `one-seed` | rejected | Requires five seeds per method/gap cell. |
| `too-easy-gap` | rejected | Requires at least two nonzero model-truth gaps. |

Run all controls with:

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py --write-manifest
```
