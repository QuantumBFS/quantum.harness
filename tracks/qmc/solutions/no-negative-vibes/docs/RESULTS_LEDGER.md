# 无符号 QMC 项目成果总账

更新时间：2026-07-29
用途：这是项目结论和计数口径的唯一简明入口。详细推导仍保留在专题文档中。

## 当前总分

| 项目 | 数量 | 口径 |
|---|---:|---|
| 纯 `det(I+D)>=0` 的独立机制 | 2 | TN 路径；odd monomial（含 block-TN 推广） |
| 额外的 graded 正权机制 | 1 | scalar/vertex grade 抵消 determinant parity |
| 局域 Hermitian Hamiltonian 构造 | 4 | 两个一维基线、TN parity-string、graded monomial |
| 已确认的新无符号物理类 | 0 | 所有成功物理映射均已知或可约化 |
| 当前开放的研究程序 | 4 | Majorana 宇称；Fock–CP；tensor-square 物理闭环；gauge/cocycle |

“按文档名字”会看到 TN、odd monomial、block-TN 和 graded monomial 四项；
但 odd monomial 与 block-TN 是同一个循环机制的标量版和分块版，而 graded monomial
又不是普通的恒正 determinant 类。因此科研计数采用上表，不把名字数当发现数。

## 三套已证明机制

| 机制 | 数学状态 | 物理映射 | 最终判定 |
|---|---|---|---|
| TN 路径半群 | 任意维数、任意深度严格正 | 开放 Hubbard、排斥 `t-V`、TN parity-string 顶点 | 矩阵条件严格；物理上为已知一维或 stoquastic 类 |
| odd positive-monomial / block-TN | 固定循环/分区严格正 | 没有成功的自然连通局域模型 | cycle factor 已知；自然局域闭包有精确 `-2` 反例 |
| graded monomial | 逐历史 grade 补偿严格正 | 奇环吸引 spinless 模型 | 已知 monomial factorization；模型属于 Majorana reflection positivity |

### 1. TN 路径半群

三对角 Metzler 生成元的指数为全非负矩阵；乘积仍全非负，因此

```text
det(I+D) = sum of principal minors >= 1.
```

这给出一个不依赖偶 flavor 平方、Kramers、固定 split metric 或 Wei 2024
Majorana contraction 条件的矩阵充分条件。但全非负矩阵理论本身是经典数学，
目前不主张一个新的纯矩阵定理。

物理落地包括：

1. 掺杂开放 Hubbard 链；
2. 单 flavor 排斥 `t-V` 开链，以及精确非对称两场键门分解；
3. 三站点 density-assisted/parity-string hopping 顶点。

前两项是已知一维无符号物理；第三项 Jordan-Wigner 后等价于 stoquastic
ferromagnetic XY/hard-core-boson 模型。精确 HS 分解仍可能有算法表达价值。

详细证据：

- [全非负路径类](TOTAL_NONNEGATIVE_PATH_CLASS.md)
- [TN 新颖性审计](TN_NOVELTY_AUDIT.md)
- [TN 物理映射边界](TN_PHYSICAL_MAPPING_FRONTIER.md)
- [复合矩阵规范 no-go](COMPOUND_GAUGE_NO_GO.md)

### 2. Odd monomial 与 block-TN

奇数阶 positive-monomial 的权重可按 permutation cycles 分解为正因子；固定 block
partition 的 block-TN 推广同样严格正。但底层 monomial 特征多项式分解是已知矩阵事实。

最自然的局域化使用站点内独立 `C3` route 和跨站 flavor-preserving TN hopping。
两个时间片各自都是合法实指数，但六模式、两层已经精确满足

```text
det(I+XR) = -2.
```

所以固定全局分区的抽象定理仍成立，自然局域 Hamiltonian 路线则已关闭。

详细证据：

- [激进结构结果](SPECULATIVE_STRUCTURE_RESULTS.md)
- [odd block-TN 局域审计](ODD_BLOCK_TN_LOCALITY_AUDIT.md)

### 3. Graded monomial

我们证明并实现

```text
sgn(P) det(I+P D) >= 0,    D_ii >= 1,
```

并构造逐历史正权、局域 Hamiltonian 和 real-exponential grade ancilla。但后续排重表明：

- `r=1` 顶点是已知 `su(1|1)` graded permutation；
- 一般物理 Hamiltonian 属于 2016 Majorana reflection positivity；
- cycle factor 本身是已知 monomial 公式。

因此它是一个有用的连续时间展开和可执行约化证书，不是新矩阵定理或新无符号物理类。

详细证据：

- [graded monomial 结果](GRADED_MONOMIAL_RESULTS.md)

## 四组 Hamiltonian 的最终归属

| Hamiltonian/顶点 | 是否局域、Hermitian、相互作用 | 无符号原因 | 是否新物理类 |
|---|---|---|---|
| 开放 Hubbard 链 | 是 | 一维 TN 路径 | 否 |
| 排斥 `t-V` 开链 | 是 | 一维 TN 路径 | 否 |
| 三站点 parity-string hopping | 是 | Jordan-Wigner 后 stoquastic XY | 否 |
| graded-monomial 奇环模型 | 是 | Majorana reflection positivity | 否 |

“不是新物理类”不等于所有公式都已在相同形式下发表。我们保留非对称 `t-V` HS 分解、
TN inverse-HS 顶点、已知类非包含证书和各类 no-go；但在文献首创性完成核查前，不把
算法表达升级为新物理发现。

## 已关闭的大方向

以下不再做同分布随机扩扫：

- 普通经典群和标准 Hermitian AZ 十类；
- 仅共享一个实结构的旋转 Majorana 双锥；
- 任意两个不同旋转的完整 split cones；
- BDI/AII/DIII/CII 的自然数守恒放松锥；
- 环、分支、稠密 Metzler 图和逐片独立符号规范；
- ordinary TN Gaussian 正和产生非-stoquastic hopping；
- graded monomial 作为新物理类；
- odd block-TN 的自然局域 crossed-partition 推广。

关闭可能来自精确负权、复相位、已知类约化或一般 no-go。扫描数字和逐项证据见
[合作者进展说明](COLLABORATOR_UPDATE.zh-CN.md)。

## 仍开放但尚不能计作成果

### Majorana 宇称分辨猜想

canonical convention 下的 640 条历史支持一个 period-4 受保护宇称规律，但它仍缺：

1. 互补扇区最小负例的精确重放；
2. 任意深度证明或反例；
3. 与固定宇称 ensemble 的明确物理用途。

### R01 fixed Klein-Hodge 与后续表示锥

合作者分支已完成 R01 的六模式重叠审计：数守恒和 BdG 两族、两个 support masks 中，
24 个 bridge hopping/pairing 坐标全部由 exact double-dual/Farkas 证书判为
`certified-zero`。这关闭的是固定 `U_6`、双 parity-block Metzler 的 R01，不是所有
Fock/spinor 表示锥。

下一轮不再延伸同一个 fixed transform，而是测试 Choi/完全正映射锥、表示提升半群、
非诱导 exterior cone 和真正改变 Hilbert 空间的 gauge/cocycle 编码。候选定义和最小
实验见 [自底向上正性候选](BOTTOM_UP_POSITIVITY_CANDIDATES.md)。

这些开放项只有通过“定义与排重、反例搜索、一般证明、Hamiltonian/HS 映射”四关后，
才会改变本总账中的发现数量。

## 文档怎么读

只想知道结论：

1. 本总账；
2. [下一阶段计划](NEXT_RESEARCH_PLAN.md)。

想复核某个结果：从上面的专题链接进入，不需要顺序阅读全部文档。

想运行代码：

- `oracle/`：权重、精确重放和候选生成器；
- `tests/`：数学恒等式、反例和物理映射回归；
- `protocols/`：正式扫描参数与可复现协议；
- `fixtures/`：机器可读精确证书。

历史候选卡和早期计划继续保留，作为研究审计记录；它们不代表当前结论。当前状态以本总账、
`START_HERE.md` 和相应专题结果文档为准。
