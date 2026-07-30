# 最小有限 PEPS + METTS 示例

这个目录是完整实现 `FinitePEPS_METTS_Ising/` 的独立精简版，不引用也不修改原目录代码。

仅保留以下核心流程：

1. 从 Z/X 基乘积态构造有限开边界 Γ-Λ PEPS；
2. 用二阶 Trotter simple update 近似作用 `exp(-βH/2)`；
3. 用 boundary-MPS（最大边界维数 `chi`）收缩范数、能量和 collapse 条件概率；
4. 第奇数次 collapse 使用 Z 基，第偶数次使用 X 基；
5. X 基概率使用正确的投影密度矩阵 `ρ±=(I±X)/2`；
6. 丢弃前 `burn_in` 步后，对剩余 METTS 样本求能量均值和朴素标准误差。

## 文件

- `minimal_metts_tfim.jl`：全部算法和一个可直接运行的 2×2 示例。

张量指标统一为：

```text
gamma[left, top, physical, right, bottom]
```

模型为开边界二维横场 Ising 模型：

```math
H=-J\sum_{\langle ij\rangle} Z_iZ_j-h\sum_i X_i.
```

## 直接运行

在仓库根目录执行：

```bash
julia --project=PEPS_TensorKit-main \
  PEPS_TensorKit-main/FinitePEPS_METTS_Ising_Minimal/minimal_metts_tfim.jl
```

脚本末尾的快速示例使用 `Lx=Ly=2`、`D=2`、`chi=16`、链长 12，并丢弃前 2 步。

## 在 Julia 中调用

```julia
include("PEPS_TensorKit-main/FinitePEPS_METTS_Ising_Minimal/minimal_metts_tfim.jl")
using .MinimalFinitePEPSMETTS

params = Params(
    J=1.0,
    h=0.5,
    beta=1.0,
    D=2,
    chi=16,
    tau=0.05,
    chain_length=110,
    burn_in=10,
    seed=20260728,
)
result = run_metts(params; Lx=2, Ly=2)

result.samples          # 第 11--110 步的 100 个总能量样本
result.energy           # 平均总能量
result.energy_per_site  # 平均每格点能量
result.standard_error   # std(samples)/sqrt(N)，未修正自相关
```

## 精简范围

这个版本有意删除 ED、β 扫描、CSV、长程关联函数、分块/自相关统计、截断误差诊断和多文件模块结构。若用于正式数值研究，应使用完整实现，并检查 `D`、`chi`、`tau`、系统尺寸、热化长度和自相关的收敛性。
