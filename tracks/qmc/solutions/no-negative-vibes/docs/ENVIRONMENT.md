# 环境与复现准备

这是 2026-07-27 的本机快照，用来防止明天从错误的 Python 环境启动。

## 当前可用环境

```text
Platform: WSL2 Linux x86_64
Python:   3.13.12 (Anaconda)
Git:      2.43.0

numpy       2.4.4
scipy       1.18.0
sympy       1.14.0
mpmath      1.3.0
pytest      9.1.1
pandas      3.0.2
matplotlib  3.10.8
```

系统 `python3` 已具备小型 oracle、精确证书、测试和绘图所需的基础包。当前不需要安装 Julia；
是否使用 Julia 属于候选和实现路线讨论，不应提前锁定。

## 容易踩的坑

harness 根目录的 `.venv` 目前只有 NumPy，缺少 SciPy、SymPy、mpmath、pytest、pandas 和
matplotlib。正式实现前应在队伍工作区建立独立环境；在此之前，验证命令明确使用系统
`python3`，不要误用 `quantum.harness/.venv/bin/python`。

原始 harness 没有为本挑战提供现成 Python 包或 oracle 测试。仓库的 `make test` 测试的是
harness 自身脚本，不能代替队伍 solution 的测试。

## 已完成的精确自检

用 SymPy 有理运算重新验证了：

- 三个 `O(1,1)` 矩阵的度量保持关系及 `16/3`、`-4/3`、`0` 权重；
- 四个辛剪切因子的乘积精确等于 `diag(-2,-1/2)`，权重 `-1/2`；
- `SU(1,1)` 有理矩阵满足伪酉关系、行列式为一，权重 `-1/2`。

数据已固化在 [exact_certificates.json](../fixtures/exact_certificates.json)。

## 计算资源边界

初始精确测试和小维度基线扫描应在本机完成，目标单次运行少于十分钟。扩大维数、乘积深度或
样本数之前先测量单样本成本；预计超过十分钟或 16 GB 内存时，再决定是否使用集群。

## 正式实现时再确定

- Python 包布局和支持的最低 Python 版本；
- 依赖范围与锁文件；
- 双精度到任意精度的升级策略；
- 本地/集群扫描的分界；
- 图表和最终 challenge report 的格式。

这些选择不会影响当前的数学证书和候选评估卡。
