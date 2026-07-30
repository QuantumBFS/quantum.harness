# Glaudex — Challenge #123

## Team

| | |
|---|---|
| **Team name** | Glaudex |
| **Members** | 施昊哲、谢昀城 |

## Challenge

| Row | |
|---|---|
| **Challenge** | Investigate how many-body interactions reshape frequency-resolved heat transport in a driven spin chain coupled to a common non-Markovian bath, going beyond the single-spin setting. |
| **Catalog issue** | Addresses #123 — released by Zhuocheng Ma, Peking University. |
| **Track** | `mps` — the team's current choice, based on the issue's `uniTEMPO` method and proposed IF-MPS/MPO route. |

## Final submission

- **Reproducible repository:** [xyc2718/glaudex-floquet-heat](https://github.com/xyc2718/glaudex-floquet-heat)
- **Frozen version:** [`challenge-2026-final-v5`](https://github.com/xyc2718/glaudex-floquet-heat/tree/challenge-2026-final-v5)
- **Fixed commit:** [`d657e6f4f7c02f0bd9f46e26db1d51aab4f8eb47`](https://github.com/xyc2718/glaudex-floquet-heat/commit/d657e6f4f7c02f0bd9f46e26db1d51aab4f8eb47)
- **Paper:** [《有限 Floquet 自旋链与公共浴耦合体系的对称性与热流分析》](https://github.com/xyc2718/glaudex-floquet-heat/blob/challenge-2026-final-v5/paper/final_report_zh.pdf)
- **Authors:** 施昊哲、谢昀城（Glaudex）

The external repository contains the calculation code, frozen plotting data,
Slurm templates, numerical checks, and figure-reproduction scripts. From a
fresh clone, run `make instantiate && make smoke` for the quick physical check,
or `make figures PYTHON=.venv/bin/python` after installing `requirements.txt`
to regenerate the submitted figures.
