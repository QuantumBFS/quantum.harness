# 无符号 QMC 项目成果总账

> **正式提交更新（2026-07-30）：**最终跨分支口径见
> [完整挑战报告](../CHALLENGE_REPORT.md)。本账本中的严格正/负结论仍有效；
> ZiboJin 的最终四字母 oddcycle alphabet 是论文主结果，不能与已归入 Wei 类的
> 早期 symmetric continuum 混同：前者有任意深度 path-metric 定理、精确
> no-common-quadratic-metric 与固定 `J1,J2` Wei 排重、以及五模相互作用 transfer。
> 后续 shared 提交把 local orthogonal-contraction plaquette 升级为
> `active-qnc-candidate`，但尚缺一般复杂性定理和热力学相图，所以它是活跃候选，
> 不是已经确认的新无符号物理类。

更新时间：2026-07-30
用途：这是项目结论和计数口径的简明账本，不再承担全部构造细节。
正式提交级叙述见[完整挑战报告](../CHALLENGE_REPORT.md)；更细的历史叙述见
[项目完整总结](PROJECT_MASTER_SUMMARY.zh-CN.md)。

## 当前总分

| 项目 | 数量 | 口径 |
|---|---:|---|
| 已严格证明的 `det(I+D)>=0` 具体构造族 | 5 | TN 路径；odd monomial（含 block-TN）；tensor-square；symmetric-oddcycle 连续族；four-letter Lorentz path-metric alphabet。continuum 已归入已知 Wei 类；四字母结果是主论文候选 |
| 额外的 graded 正权机制 | 1 | scalar/vertex grade 抵消 determinant parity |
| 早期局域 Hermitian Hamiltonian 映射 | 5 | Hubbard、`t-V`、parity-string、graded 奇环、tensor-square 四模式 plaquette |
| 后期非常规模型试制品 | 8 | 与早期模型有重叠，不能相加成 13 个独立模型 |
| 协作者相互作用 transfer | 2 | 旧 symmetric-continuum transfer 属已知 Wei 类；最终四字母 positive-field transfer 超出共同实二次 metric 与所检查固定 `J1,J2` Wei 充分类 |
| 已确认的新可扩展局域无符号物理类 | 0 | 四字母结果是通常非局域的五模 cluster；局域 family 与热力学 scaling 未宣称 |
| 活跃 QNC 模型候选 | 1 | local orthogonal-contraction plaquettes；正性为 doubled-Majorana square，但完整扇区代数和非 Gaussian 低能态已排除最直接的传统模拟路线 |
| 当前开放的研究程序 | 7 | orthogonal-contraction 相图/复杂性；typed exterior；Pfaffian/Spin；tensor-square 相图；oddcycle finite-depth seeds；non-Klein Fock–CP；Majorana 工具 |

“按文档名字”会看到 TN、odd monomial、block-TN、graded monomial、tensor-square 和
symmetric-oddcycle 六项；但 odd monomial 与 block-TN 是同一个循环机制的标量版和
分块版，graded monomial 又不是普通的恒正 determinant 类，symmetric-oddcycle 则被
共同 metric 归入已知 Wei 不定度量收缩半群。最终四字母 alphabet 是独立的第五套
determinant 构造，不能由 continuum 的共同 metric 结论覆盖。因此科研计数采用上表，
不把名字数当发现数。

贡献归属：除特别标注的协作 exterior/R01 外，本账中的经典群、AZ、Majorana、TN、
graded、tensor-square、gauge 和非常规模型结果来自籼至
（GitHub `xianzhipan`）分支；R01 和 exterior exact-card/long-word 结果来自
ZiboJin 的[草稿 PR #3](https://github.com/no-negative-vibes/quantum.harness/pull/3)。
完整分工表见[项目完整总结](PROJECT_MASTER_SUMMARY.zh-CN.md)。

## 7 月 30 日最终 oddcycle 更新

这里有两个必须分开的 ZiboJin 结果。

最终主结果是

```text
{B(1/1000),B(1/1000)^T,B(4/5),B(4/5)^T}.
```

四个有理 Lorentz path metrics、16 条 transition gaps 与 time orientations 给出
任意深度 `det(I+W)>0` 的精确定理。Exact Gordan--Stiemke dual 排除共同实对称
quadratic split-contraction metric；Nambu-space pullback 排除任意固定复正交
Majorana 基变换后的固定 `J1,J2` Wei 充分类。同一 alphabet 以正场系数
`(37,1,1,1,1)/41` 给出 Hermitian、数守恒、非 Gaussian 的相互作用五模 transfer。
这是当前论文主结果；其限制是通常非局域、仅 cluster/grand-canonical 层面，局域性、
固定 filling 与热力学 scaling 未宣称。

早期对照结果则是：

1. symmetric-oddcycle 连续字母表
   `{B(z),B(z)^T:0.99<=z<=1.01}` 已严格证明任意有限 word 权重为正，并在 `z=1`
   构造了 Hermitian、数守恒、真正相互作用的五模 transfer；
2. 随后的完整共同度量审计找到
   `R=2ww^T/83-I`、`w=(4,4,1,-5,5)^T`，其 signature 为 `(1,4)`，而且整个区间
   同时满足严格 contraction inequalities。

因此这套连续族的数学定理和相互作用模型都保留，但**正性的原因属于已知
Wei indefinite-metric contraction semigroup**，不能计作新的正性机制或新无符号
物理类。这个归约不适用于上面的最终四字母 alphabet。一个漂亮的
exterior 证明并不自动意味着机制新颖。

同一贡献人的 tensor-square phase 分支也完成了 `m=3,4` 的 DQMC/ED 首轮交叉验证；
这是“计算工具已验收、可以开始粗相图”的进展，不是“已发现新相”。

固定 theorem 被归类后，ZiboJin 当时又转向多个矩阵组成的联合 alphabet。历史领先 pair
`{p=0.3,p=2.5}`（`q=r=1`，含转置）满足：

- 每个单点各自有严格 contraction metric；
- 联合 alphabet 的共同底层 metric SDP margin 数值塌到零；
- 全部 `22,369,620` 个 depth<=12 非空 words 和 `100,000` 个 depth<=40 随机词
  都严格正，最小值仍为单字母的 `33.5`；
- 现有 one-block exterior CQLF/tail 不足以给出任意深度证明。

所以它在当时是高质量**有限深度候选**，不是已确认新机制；这条历史搜索后来导向
上面的最终四字母 path-metric 结果。原始贡献和后续 state-dependent/coupled
certificate 均属于 ZiboJin 分支。

## 六套已证明构造（五套 determinant + 一套 graded）

| 机制 | 数学状态 | 物理映射 | 最终判定 |
|---|---|---|---|
| TN 路径半群 | 任意维数、任意深度严格正 | 开放 Hubbard、排斥 `t-V`、TN parity-string 顶点 | 矩阵条件严格；物理上为已知一维或 stoquastic 类 |
| odd positive-monomial / block-TN | 固定循环/分区严格正 | 没有成功的自然连通局域模型 | cycle factor 已知；自然局域闭包有精确 `-2` 反例 |
| graded monomial | 逐历史 grade 补偿严格正 | 奇环吸引 spinless 模型 | 已知 monomial factorization；模型属于 Majorana reflection positivity |
| tensor-square | `det(I+X tensor X)>=0` 任意实 `X`；权重可分解为模平方乘实平方 | 四模式方形 hopping、多通道连续模型和精确 `-log` transfer | 恒正构造严格但不是不可约新机制；`m=3,4` DQMC/ED 已验收，phase/新颖性开放 |
| symmetric-oddcycle（ZiboJin） | 独立变化的连续区间字母表有任意深度严格定理 | 五模、非局域、最多五体的相互作用 transfer | 完整共同 signature `(1,4)` metric 已找到；属于已知 Wei 不定度量收缩半群 |
| four-letter Lorentz path metrics（ZiboJin） | 四个 rational path metrics 与全部 16 条 transition/orientation gates 给出任意深度严格定理 | 正场 Hermitian、数守恒、非 Gaussian 的相互作用五模 transfer | 主论文结果；无共同实二次 metric，且排除所检查固定 `J1,J2` Wei 充分类；局域/scaling 开放 |

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

### 4. Tensor-square

对任意实方阵 `X`，

```text
det(I+X tensor X)
 = |det(I+iX)|^2 det(I+Lambda^2 X)^2
 >= 0.
```

一般证明来自 Kronecker 本征值配对，最新分解又表明它在代数上是模平方乘实平方。
四模式正系数 HS 和非交换方形 hopping 已完整构造，但 `2 x 2` 底空间自动保存
signature `(2,2)` 的 split metric，因而属于已知 split-orthogonal 类。对 `m=3`
完整表示，固定伪正交 metric 的精确线性系统满秩，因此最简单的固定 `O(p,q)` 解释
被排除；更一般 Majorana/Pfaffian 排重仍开放。

详细证据：

- [tensor-square 结果](TENSOR_SQUARE_RESULTS.md)

### 5. Symmetric-oddcycle 连续族（ZiboJin）

对 `{B(z),B(z)^T:0.99<=z<=1.01}`，每个时间片的 `z` 可独立变化，任意有限 word
都有严格正 determinant。`z=1` 又给出

```text
exp(-H) = [19 I + Gamma(B) + Gamma(B)^T] / 21,
```

即 Hermitian、数守恒且非 Gaussian 的五模相互作用 transfer。它通常非局域并含最高
五体项。后续 exact 审计找到整个连续 alphabet 的共同 signature `(1,4)` contraction
metric，所以这是已知 Wei 不定度量收缩机制的高质量实例，不是新的正性类。
`ODDCYCLE_CHALLENGE_AUDIT.md` 的较早版本写于共同度量发现之前；当前文件已更新为
最终四字母结果的完成审计。

### 6. Four-letter Lorentz path-metric alphabet（ZiboJin）

最终 alphabet

```text
{B(1/1000),B(1/1000)^T,B(4/5),B(4/5)^T}
```

有 solver-independent exact rational 任意深度证书。它的四状态 Lorentz
path-metric 构造在该 alphabet 上严格强于一状态共同二次 metric：exact
Gordan--Stiemke dual 证明后者不存在。独立的 Majorana/Nambu 审计还排除了所检查的
固定 `J1,J2` Wei contraction 充分类，但不声称排除所有 nonquadratic cone、
fermion-bag、loop 或 worldline 机制。

同一 alphabet 给出精确正场系数 `(37,1,1,1,1)/41` 的五模相互作用 transfer。
它是 grand-canonical、通常非局域的 cluster 结果，因此“主论文结果”与“已确认的
可扩展局域新物理类”是两种不同口径。详细证据见
[论文草稿](ODDCYCLE_PAPER_DRAFT.md)、
[path certificate](ODDCYCLE_PATH_METRIC_CERTIFICATE.md)、
[metric separation](ODDCYCLE_NO_COMMON_METRIC_CERTIFICATE.md)和
[Wei audit](ODDCYCLE_MAJORANA_WEI_AUDIT.md)。

## 早期五组局域 Hamiltonian 的最终归属

| Hamiltonian/顶点 | 是否局域、Hermitian、相互作用 | 无符号原因 | 是否新物理类 |
|---|---|---|---|
| 开放 Hubbard 链 | 是 | 一维 TN 路径 | 否 |
| 排斥 `t-V` 开链 | 是 | 一维 TN 路径 | 否 |
| 三站点 parity-string hopping | 是 | Jordan-Wigner 后 stoquastic XY | 否 |
| graded-monomial 奇环模型 | 是 | Majorana reflection positivity | 否 |
| tensor-square 四模式 plaquette | 是 | split `O(2,2)` | 否 |

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

ZiboJin 分支已完成 R01 的六模式重叠审计：数守恒和 BdG 两族、两个 support masks 中，
24 个 bridge hopping/pairing 坐标全部由 exact double-dual/Farkas 证书判为
`certified-zero`。这关闭的是固定 `U_6`、双 parity-block Metzler 的 R01，不是所有
Fock/spinor 表示锥。

下一轮不再延伸同一个 fixed transform，而是测试 Choi/完全正映射锥、表示提升半群、
非诱导 exterior cone 和真正改变 Hilbert 空间的 gauge/cocycle 编码。候选定义和最小
实验见 [自底向上正性候选](BOTTOM_UP_POSITIVITY_CANDIDATES.md)。

Fock–CP 的第一批自然变换也已完成：identity 与所有深度不超过 2 的连续
Klein–Hodge 电路，在 20 种 tensorization、数守恒/BdG 两族共 520 个单元中，
所有 bridge 都在 Hermiticity-preserving 线性门被迫为零。该有限库已关闭；一般
non-Klein Choi 锥仍开放。见 [Fock–CP 首轮结果](FOCK_CP_SCREEN_RESULTS.md)。

ZiboJin 随后完成了独立的 non-induced exterior exact-card/pressure 流水线。
seed61 虽曾通过较浅锥检验，最终在长度 150 找到精确负 determinant，已永久关闭。
oddcycle seeds `117/132/147` 则分别穷尽全部非空二进制 words 到长度 27：
每个 `268,435,454` 个 raw words，三者合计 `805,306,362`；另有 448 个长度
60–1800 的精确/高精度对抗 winners 全部为正。它们目前是高质量有限深度候选，
但没有任意深度定理，不能计作新的无符号类。实现与证据保留在
[ZiboJin 草稿 PR #3](https://github.com/no-negative-vibes/quantum.harness/pull/3)。

与这三个 seed 分开，fixed symmetric-oddcycle `B(2,1)` 及其
`z in [0.99,1.01]` 连续扩展已有任意深度定理和相互作用 transfer；但最新 exact
common-metric 证书把它完整归入已知 Wei 不定度量收缩半群。`(p,q,r)` 的 2,744 点扫描中
15 个 exterior-certificate 幸存者也全部共享一个严格 metric；因此这批不再作为新机制
候选。

再与上述历史结果分开，最终四字母 alphabet 已有任意深度 theorem、exact
no-common-quadratic-metric dual、固定 `J1,J2` Wei 排重与相互作用 transfer；它不是
有限深度候选，也不受 continuum 的共同 metric 归类覆盖。

但网格外的远距离联合 alphabet 不能被这句话覆盖。历史领先 pair
`{(0.3,1,1),(2.5,1,1)}` 的联合共同底层 metric 只得到数值零 margin，并已通过全部
depth-12 words 与十万条 depth<=40 随机词；当前 coupled exterior profile 在 depth 12
仍未达到 tail gate，所以准确状态是“有限深度幸存、定理开放”。

Tensor-square 已完成一般恒正证明和四模式物理闭环：
`det(I+X tensor X)>=0` 对任意实 `X` 成立，且存在非交换、ordinary TN 之外的
两值正系数 HS，产生方形 hopping 加排斥对角作用。但 `m=2` 严格保存
`eta=epsilon tensor epsilon`，属于已知 split `O(2,2)`；`m>=3` 的直接局域操作
提升为随系统长度增长的行列条带，独立 onsite 场又有精确负例 `-155085/32`。
因此保留矩阵定理，不增加“新无符号物理类”计数。见
[tensor-square 结果](TENSOR_SQUARE_RESULTS.md)。

Gauge/cocycle 第一版也已完成。edge-electric Gauss law 加 affine link phase 在四模式
方环和六模式共边方环上能精确抵消全部 fermion signs，深度 1–8 的闭合 histories
也零失败；但在 `2 x L` 梯子中，中央 hop 的 phase 必须读取其余全部 `L-1` 条竖边，
形成 system-size Wilson string。该简单 ansatz 已关闭；modified-Gauss-law
projected cone 仍开放，但只有给出逐构型正 transfer matrix 才重开。见
[gauge/cocycle 第一轮结果](GAUGE_COCYCLE_RESULTS.md)。

新的独立主线不再与合作者重复 exterior 大筛选，而是重新开采上述严格机制：允许长程、
多体、全局约束、Wilson string、准 Hermitian 和一般 nonunitary transfer models，
先记录严格 L1 模型，再寻找相似变换、对偶、投影和低能约化。该方向目前是研究程序，
尚未增加成果计数。见
[非常规模型发现](UNCONVENTIONAL_MODEL_DISCOVERY.md)。

第一批反推现已完成：我们证明了一个通用构造——任何乘法、转置封闭且历史
`det(I+D)>=0` 的实矩阵半群，都可通过

```text
H = -sum_a q_a [Gamma(B_a)+Gamma(B_a)^dagger]
```

生成逐 Taylor word 非负的 Hermitian 相互作用模型。基于它和精确相似/投影变换，
已经得到八种长程、全局、多体、ancilla、Wilson-string 或 pseudo-Hermitian 模型。
其中 Wilson gauge、Stark similarity、star-to-chain 已明确降为 L2/已知校准。
随后的三个候选审计又得到：adjoint lift 完整位于已知 `O(p,q)` 恒等分支；
grade-charge full trace 是守恒 ancilla-bit 扇区的静态直和；tensor-square 权重可
分解为 `|det(I+iX)|^2 det(I+Lambda^2 X)^2`，但 `m=3` 完整表示不存在固定
pseudo-orthogonal 度量。tensor-square 多通道 Hamiltonian 已由 ZiboJin 独立分支
推进到 DQMC/ED 验证，`m=3` 的 gap valley 是待做尺寸标度的物理信号，不是新相结论；
oddcycle seeds `117/132/147` 仍是有限深度候选。籼至下一轮转向 typed exterior
category 与真实 pairing 的 Pfaffian/Spin 搜索。这些线都仍不增加“确认的新无符号
物理类”计数。见
[非常规模型第一批结果](UNCONVENTIONAL_MODEL_BATCH1_RESULTS.md)和
[三个候选的排查结果](THREE_CANDIDATE_AUDIT_RESULTS.md)。

这些开放项只有通过“定义与排重、反例搜索、一般证明、Hamiltonian/HS 映射”四关后，
才会改变本总账中的发现数量。

## 文档怎么读

只想知道结论：

1. [项目完整总结](PROJECT_MASTER_SUMMARY.zh-CN.md)；
2. 本总账；
3. [下一阶段计划](NEXT_RESEARCH_PLAN.md)。

想复核某个结果：从上面的专题链接进入，不需要顺序阅读全部文档。

想运行代码：

- `oracle/`：权重、精确重放和候选生成器；
- `tests/`：数学恒等式、反例和物理映射回归；
- `protocols/`：正式扫描参数与可复现协议；
- `fixtures/`：机器可读精确证书。

历史候选卡和早期计划继续保留，作为研究审计记录；它们不代表当前结论。当前状态以本总账、
`START_HERE.md` 和相应专题结果文档为准。
