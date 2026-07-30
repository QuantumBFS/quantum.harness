## 🏆 评委入口（Start here）

> ### [▶ 直接打开自包含 HTML 技术报告](https://raw.githack.com/Avi7ii/quantum.harness/a963de5358949443cb860f6878dedd135f9d7854/tracks/qmc/solutions/yanwang/report/report.html)
>
> 核心结论、5 张矢量图、有限尺寸标度、独立 QMC 验证、误差预算与复现命令均集中在此。

[GitHub 内报告文件（备用）](https://github.com/Avi7ii/quantum.harness/blob/a963de5358949443cb860f6878dedd135f9d7854/tracks/qmc/solutions/yanwang/report/report.html) · [Challenge #148](https://github.com/QuantumBFS/quantum.harness/issues/148)

## Team

| | |
|---|---|
| **Team name** | yanwang |
| **Contributor for #148** | 赵志轩 |

## Challenge

| Row | |
|---|---|
| **Challenge** | Can sign-free QMC determine the triangular- and honeycomb-lattice transverse-field Ising critical fields with at least five times smaller total uncertainty than the 2002 benchmarks and deliver a pre-registered, independently cross-checked verdict on whether their ratio is exactly √5? |
| **Catalog issue** | `Addresses #148` — “Is the ratio of transverse-field Ising critical points on the triangular and honeycomb lattices exactly √5?”, released by Xiao-Yan Xu, Shanghai Jiao Tong University. |
| **Track** | `tracks/qmc/` — selected from the challenge issue's `Method: Quantum Monte Carlo` field. |

## Current outcome

This submission reports a controlled **baseline-stage result**, not a
final-production claim:

| Quantity | Estimate |
|---|---:|
| \(h_c^\triangle/J\) | `4.7682138 ± 0.0000640 (stat) ± 0.0002799 (sys)` |
| \(h_c^\hexagon/J\) | `2.1324944 ± 0.0000168 (stat) ± 0.0000251 (sys)` |
| \(R=h_c^\triangle/h_c^\hexagon\) | `2.2359795 ± 0.0000348 (stat) ± 0.0001573 (sys)` |
| \(R-\sqrt5\) | `-0.0000885 ± 0.0001611 (total)` |

The pre-registered verdict is **inconclusive**. The displacement from
\(\sqrt5\) is only `0.55σ`, the total ratio uncertainty exceeds the target
`1.2e-5`, and the triangular narrow scan does not satisfy the frozen
all-adjacent-size crossing gate. Thus the numerical result is fully
**consistent with \(\sqrt5\)** and the conjecture survives this baseline
test, although the present precision cannot establish exact equality.

See [RESULTS.md](RESULTS.md) for methods, diagnostics, limitations, and
provenance. The literature survey and frozen analysis rules are in
[`research/`](research/); reviewed code and tests are in
[`scripts/`](scripts/) and [`tests/`](tests/).
The status of a possible exact derivation is discussed in
[`research/ANALYTIC_RELATION.md`](research/ANALYTIC_RELATION.md).

## Reproduce the ratio calculation

From this solution directory:

```bash
workdir="$(mktemp -d)"
python3 scripts/compute-baseline-ratio.py \
  --triangle-summary results/triangular/summary.json \
  --triangle-robustness results/triangular/robustness.csv \
  --honeycomb-summary results/honeycomb/summary.json \
  --honeycomb-robustness results/honeycomb/robustness.csv \
  --independent-summary results/independent/summary.json \
  --out "$workdir/baseline.json"
```

Large raw chain data remain on the compute cluster; compact fits, robustness
tables, plots, hashes, and scheduler provenance are included here.

The packaged checks run with:

```bash
python3 tests/test_honeycomb_baseline_analysis.py
python3 tests/test_triangular_baseline_analysis.py
python3 tests/test_compute_baseline_ratio.py
julia --project=julia-env -e 'using Pkg; Pkg.instantiate()'
julia --project=julia-env --startup-file=no tests/test_dedicated_sse.jl
```
