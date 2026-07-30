# Challenge Report: #232 Noncommutative Polynomial Optimization

## Issue
**#232** — 非对易多项式优化：利用 moment-SOS / SOHS 层级，
对量子图参数 β(G)（Lovász ψ 函数的非对易推广）给出严格的上界证书。
目标图来自 arXiv:2310.00612 Table 4。

## 官方要求 vs 达成情况

| 要求 | 状态 |
|------|------|
| 注册（PR #181） | ✅ 已注册 |
| 精确闭合常数（upper = lower） | ✅ **25 个精确闭合** |
| hope signal（gap < 10⁻⁶） | ✅ atlas#878 gap=10⁻⁸ |
| 收紧文献上界 | ✅ graph33: 文献 2.0013 → 我们 2.0000169 |
| 量子优势发现（β > α） | ✅ comp(C₇), Clebsch 图 |

## 进化统计

| 指标 | 值 |
|------|-----|
| OmniEvolve DB 数 | 3（graph33 + bell×2）|
| 总评估次数 | 45 |
| LLM 调用 | 83 |
| Token 消耗 | ~392K（仅 graph33）|
| 最高 evaluator score | 0.9161 |
| 精确闭合常数 | **25 个** |
| 证书文件 | `tracks/polyopt/solutions/quantumevolve/certificates/` |

## 迭代轨迹（graph33，41 evals）

```
gen= 0  score=0.500  upper=2.00249  ← 种子（degree-2 松弛）
gen= 1  score=0.586  upper=2.00195
gen= 2  score=0.875  upper=2.00046  ← 大幅提升
gen= 3  score=0.619  upper=2.00168  ← 回退
gen= 6  score=0.890  upper=2.00030
gen= 9  score=0.916  upper=2.00017  ← 最高分（degree-3 最优）
gen=11-14 score≈0.91  upper≈2.0002   ← 停滞
（后续手工做 degree-4 → 2.0000169 → 冻结）
```

## 成功原因
1. **种子策略正确**：从 level-1 SOHS 松弛开始，逐步增加基词——LLM 能在已有
   结构上增加约束，每次添加几个三次/四次基词来收紧上界
2. **OmniEvolve + 人工后处理协同**：OmniEvolve 找到数值最优解（gen=9, upper=2.00017），
   然后人工执行精确有理化（Fraction 舍入 + LDL 验证）得到机器复核的严格证书
3. **独立验证器不信任 solver**：verify_dual_certificate.py 用纯 Fraction 算术
   重建代数，225 条仿射恒等式 + 45 个正 LDL 主元——这是证书可信度的关键
4. **批量闭合策略有效**：对 Table 4 的 25 个图逐一跑 level-1 松弛 + 有理化，
   利用无限族结构（Kₙ, Kₘ,ₙ, C₂ₖ 等）快速闭合

## 失败原因
1. **graph33 精确闭合不可能**：degree-4 (99×99 SDP) 给 gap=1.7×10⁻⁵，
   奇异对偶 + 无理最优解（含 √5）排除了标准 SOHS 框架下的精确闭合
2. **OmniEvolve 进化在上界 ~2.0002 处停滞**：score 从 0.92 无法继续提升，
   因为 LLM 无法自主发现需要更深的代数结构（如 odd-hole 不等式、对称性约化）
3. **score 设计偏惩罚性**：gen 4/7/8/10 的 score=0 是因为 SDP 求解失败
   （基词过多导致数值不稳定），LLM 没有从这些失败中获得有用信息

## 反思与体会
- **OmniEvolve 擅长"搜索空间探索"而非"代数证明"**：它能自动发现哪些基词组合
  给出更紧的上界，但无法发明新的数学技术（如 odd-hole 分解）
- **人工+AI 协同是正确模式**：AI 做数值搜索 → 人工做精确化 → AI 验证。
  纯 AI 无法完成精确闭合的最后一步
- **Solver 选择至关重要**：SCS（ADMM）在奇异问题上给出正确结果，而 Clarabel
  （内点法）在 upper=2 时报假阴性——这个发现完全来自人工实验
- **无限族闭合是高 ROI 策略**：一次发现（如"Kₘ,ₙ 都可以 level-1 闭合"）
  直接给出无限多个常数，比逐图进化高效得多
