# 截至 2026-07-27 的文献边界与研究空白

## 总判断

这个方向没有被“榨干”，但最直接的充分条件已经相当成熟。只换一个经典群然后随机试数，
大概率得到快速反例或重新发现已知谱配对；真正值得投入的是：

1. 把散落条件组织成 AZ 十重对称类的可复核行列式符号表；
2. 给 Majorana positivity 的复数结果建立简洁的矩阵语言；
3. 对真正存活且不约化到已知机制的项寻找半群锥；
4. 把新结构映射到不局限于半填充二分格子的具体 DQMC 模型。

这是“成熟核心旁边仍有明确空白”，不是完全空白，也不是已经封闭。

## 已知结果把哪些路封住了

- 2015 年 split-orthogonal 工作严格给出 `O(n,n)` 各连通分支的行列式符号结构，并把它用于
  无符号费米子模拟。
- 2016 年 Majorana positivity 给出 Majorana reflection/Kramers positivity 两类充分条件；
  Majorana time-reversal 工作在其对称性设定中得到 Majorana 与 Kramers 两个基本无符号类。
- 2024 年发表的 contraction-semigroup 框架把许多先前结果纳入更一般的半群充分条件，并给出
  不能由早期框架直接理解的模型。
- 2019 年综述已经系统整理 Majorana、Kramers 和模型应用；任何“新类”都必须先做相似变换、
  flavor 配对和半群约化检查。

这些都是充分条件的广泛统一，不是对所有可能结构化集合的必要充分分类。因此“已有统一框架”
不能推出“再无新结果”。

## 为什么仍值得做

挑战发布者在 2026-07-23 的正式问题中明确列出尚未完成的方向：

- AZ 十重对称类对应经典群的行列式符号周期表；
- 每个存活群条目的半群锥；
- `arXiv:1601.01994v2` 复数结果的简洁矩阵表述；
- AI 生成的线性子空间与锥，但必须通过新颖性过滤；
- 最终映射到具体费米子格点模型。

正式问题还明确说：精确反例表本身也是可报告的基础工作。我们随后已完成一张标准
Hermitian 时间片约定下的 [AZ 十类侦察表](AZ_TENFOLD_RESULTS.md)：六类由深度三精确证书
排除，四类约化到已知 split-orthogonal 或 Kramers 机制。它不是完整的 BdG/Pfaffian 分类，
也还没有物理映射。

## 定向检索的结果与边界

本轮只用原始论文、正式挑战说明和综述作结论依据。针对“AZ/tenfold determinant sign
table”“complex Majorana simple matrix formulation”“semigroup determinant positivity”
等交叉词做了定向检索，没有找到一篇直接完成本挑战所述 AZ 行列式符号表或复矩阵 addendum
的论文。

这只是“本轮检索未命中”，不是数学意义上的不存在证明。选定下一个窄题后，仍需做作者、
引用链、相邻术语和最新预印本的二次排重。

## 近期文献说明领域仍在生长

- 2025/2026 的无符号核量子蒙卡工作构造了对偶偶核严格无符号的格点核力，说明物理模型层面
  仍能产生有分量的新结果。
- 2026 年的三角格 M 点 moiré 工作找到了三电子/胞元的自然无符号 DQMC 点，说明无符号结构
  仍在新材料模型中出现。
- 2025 年关于二维玻色拓扑序的工作给出大量 intrinsic sign problem 的 no-go 指标；它与
  当前费米子行列式分类相邻，但不能替代本挑战的矩阵结构分析。

这些论文不能直接成为我们的答案；它们说明“新物理映射”和“不可无符号的边界”仍是活跃方向。

## 推荐的三档路线

| 路线 | 新颖性潜力 | 明天可做性 | 风险 | 建议 |
|---|---|---|---|---|
| AZ Hermitian 行列式表 | 已完成第一版 | 已完成 | 物理 BdG 权重边界 | 作为地基，不再重复 |
| 复杂 Majorana 矩阵表述 | 高 | 中低 | 数学难、短期无结果 | 高价值主线/备选 |
| 存活项半群 + 物理模型 | 最高 | 低 | 同时需要定理与 HS 映射 | 第二阶段 |

对零基础团队，下一组合应是：用已完成的 AZ 表作为回归地基，主攻复杂 Majorana 表述或一个
明确的“对称约束交半正定锥”；只有发现不约化的存活格后，才把计算与证明资源集中到半群和
物理模型。

## 主要来源

- [正式挑战 issue #121](https://github.com/QuantumBFS/quantum.harness/issues/121)
- [Wang et al., split orthogonal group](https://arxiv.org/abs/1506.05349)
- [Wei et al., Majorana positivity](https://arxiv.org/abs/1601.01994)
- [Li, Jiang, Yao, Majorana time-reversal classes](https://arxiv.org/abs/1601.05780)
- [Wei, contraction semigroups](https://arxiv.org/abs/1712.09412)
- [Li and Yao, 2019 review](https://arxiv.org/abs/1805.08219)
- [Niu and Lu, sign-problem-free nuclear QMC](https://arxiv.org/abs/2506.12874)
- [Vasiliou et al., sign-free moiré DQMC](https://arxiv.org/abs/2606.12530)
- [Seo et al., bosonic topological-order no-go](https://arxiv.org/abs/2503.21925)
