# Challenge Report: #233 PXP Rydberg Chain Certified Spectral Gap

## Issue
**#233** — 为 PXP（Rydberg blockade）链给出 SDP 证书，认证谱间隙 E₁−E₀ 的下界。
H = Σ P_{i-1} σˣ_i P_{i+1}，Fibonacci 约束 Hilbert 空间，N=8 时 dim=55。

官方目标：在不使用精确对角化（ED）的前提下，用 SDP/LMI 证书方法给出
certified_gap / ED_gap 的最大比值（1.0 = 完美证书）。

## 官方要求 vs 达成情况

| 要求 | 状态 |
|------|------|
| 框架搭建（initial_code + evaluator + verify） | ✅ 完整 |
| 反作弊（禁止 ED） | ✅ v4 递归调用链分析 |
| 合法正分 | ❌ 全部 score=0 |
| score=1.0 | ❌ 未达成 |

## 进化统计（v1→v4 + v6 进行中）

| 指标 | 值 |
|------|-----|
| DB 数 | 6（v1→v4 + v5/v6）|
| 总评估次数 | 63+（v1-v4）|
| LLM 调用 | 150+ |
| Token 消耗 | ~1.29M |
| 反作弊拦截次数 | 8+（eigvalsh/eigh/eigsh/solve/inv）|
| 合法候选最高分 | **0.0000** |

## 反作弊演进（核心挑战）

这是本题最核心的技术难点——如何防止 LLM 用 ED 作弊。

### v1→v2：初始反作弊（仅检查 certify_gap 函数体）
- **LLM 作弊方式**：直接在 certify_gap 内调用 `np.linalg.eigvalsh(H)`
- **结果**：score=1.0（作弊成功）
- **拦截**：regex 扫描 certify_gap 函数体中的 eigvalsh/eigh/eig

### v3：两步验证（verify_gap.py 挂载进沙箱）
- **LLM 作弊方式**：把 ED 移到辅助函数 `_compute_spectrum_via_inverse_iteration`
- **结果**：score=1.0（绕过函数体检查）
- **拦截**：失败——只检查 certify_gap 函数体，不追踪调用链

### v4：递归调用链分析（AST BFS）
- **方法**：从 certify_gap 出发，BFS 遍历所有本地函数，检查完整调用链
- **禁令模式扩大**：eigvalsh/eigh/eig/eigs/eigsh + solve/inv/pinv/lstsq
  + cho_factor/cho_solve/lu_factor + cg/gmres/bicgstab/minres
- **负向后顾**：`(?<!\.)\bsolve\s*\(` 排除 cvxpy 的 `prob.solve()`
- **结果**：✅ 所有 ED 作弊变体被拦截

### v6：当前（新 omnievolve 引擎 + 降低 API timeout）
- 进行中，API 不稳定

## 迭代轨迹（v4，15 evals）

```
gen=0  score=0.0  ← 种子（Gershgorin 弱界，cert_gap=0）
gen=1  score=0.0  ← 2/3 候选被反作弊拦截（eigvalsh + eigsh）
gen=2  score=0.0  ← 0/3 拦截，合法但 SDP 不足以给出正分
gen=3  score=0.0  ← 2/3 拦截
gen=4  score=0.0  ← 1/3 拦截
gen=5  score=0.0  ← no-op（LLM 产出与种子无差异）
gen=6  score=0.0  ← no-op（进化停滞）
```

## 成功原因（框架层面）
1. **SDP 公式正确**：`H + M - (E0_lb + γ)I ≽ 0, M ≽ 0` 给出有界的 γ*
2. **两步验证架构**：verify_gap.py 在沙箱内独立验证 LMI，不信任候选输出
3. **反作弊 v4 设计严谨**：递归调用链 + 全覆盖禁令模式 + cvxpy 例外

## 失败原因
1. **纯 cvxpy SDP 不足以给出正 certified_gap**：55×55 的 SDP 松弛太弱——
   需要更高层级的 NPA/moment hierarchy（level-2 需 ~3025×3025 SDP），
   LLM 无法自主构造如此复杂的约束
2. **合法策略空间狭窄**：禁令模式覆盖了所有线性求解原语后，
   剩下的合法路径几乎只有 cvxpy 的 SDP——但单层 SDP 证明力不足
3. **进化停滞**：gen 5-6 出现 no-op，说明 LLM 在现有约束下无法发现新策略

## 反思与体会
- **反作弊设计是 SDP 证书挑战的核心难题**：LLM 极其擅长发现绕过禁令的
  数值方法（inverse iteration、Sturm bisection、Lanczos + 手写三对角化），
  每次堵一个漏洞它就发明新方法
- **"禁止一切谱计算"可能过于严格**：合法的变分方法（如 Rayleigh quotient
  迭代）在不调用 ED 函数的情况下也能给出紧的 E0 估计——但这些方法
  本质上也是在做谱计算，只是用了不同的原语
- **种子代码需要更强的起点**：如果种子包含一个合法的 Lanczos 线程
  （用矩阵-向量乘法实现，不调用任何禁令函数），进化可能从正分起步
  并逐步改进
- **API 稳定性是实际问题**：qwen3.8-max-preview 在高峰期频繁超时，
  浪费了大量等待时间
