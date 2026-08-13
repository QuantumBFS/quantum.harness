# Exterior 正锥范畴与 Pfaffian 正性搜索设计

- 日期：2026-07-29
- 状态：已按讨论形成书面规格，等待实现前复核
- 负责人：籼至（GitHub `xianzhipan`，Codex 协助）
- 计划实现分支：`work/xianzhi/exterior-positive-category-search`

## 1. 为什么启动这一轮

现有项目已经证明 TN、odd monomial/block-TN 和 tensor-square 三套 determinant
恒正构造，但成功的物理映射都已知或可约化。ZiboJin 的 symmetric-oddcycle 连续族
虽然已经有任意深度严格证明和五模相互作用 transfer，最新完整共同度量审计又证明整个
区间属于已知的 Wei real indefinite-metric contraction 半群。这个结果提供了两条直接
经验：

1. 只枚举另一个固定群、固定度量或孤立矩阵，极易再次命中已知类；
2. exterior-grade 的正锥、尾部支配和连续区间证书确实能组成任意深度定理模板。

因此这一轮不再问“还有哪个群名没扫”，而搜索两个更大的对象：

- **A 主线：exterior-grade domination 与有类型正锥范畴**；
- **B 支线：Pfaffian-TN / positive-spinor 正性**。

目标既可以是一类新的原始正性矩阵，也可以是一条把 TN、外幂锥、Pfaffian 或已知半群
串联起来的更大“矿脉”。有限深度零反例只算候选，不算发现。

## 2. 数学对象

### 2.1 Exterior 分解

对数守恒费米子历史

```text
P = B_L ... B_1
```

使用恒等式

```text
det(I+P) = sum_(k=0)^n tr[(Lambda^k B_L)...(Lambda^k B_1)].
```

`Lambda^k B` 的矩阵元是 `B` 的 `k` 阶 minors。于是每个粒子数 grade 都可看成
subset-state 图上的闭路和。

搜索不要求每个 grade 都逐项正。允许：

- 一部分 grade 在显式有理锥中保持正；
- 一部分危险 grade 有可乘的范数或分块上界；
- 一个严格正的主导 grade 给出下界；
- 短词由精确穷举闭合，长词由 block/tail 不等式闭合。

候选只有在得到

```text
positive lower bound - sum(dangerous-grade upper bounds) > 0
```

的任意深度证书后，才能升级为定理。

### 2.2 有类型正锥范畴

固定一个共同正基只是单对象情形。本轮允许每个 Trotter 位置使用一个标号为 `a` 的
exterior/Fock 正锥 `C_(k,a)`，而时间片是

```text
Lambda^k B_(a->b): C_(k,a) -> C_(k,b)
```

的正映射。实际辅助场语言必须形成合法的闭合路径

```text
a_0 -> a_1 -> ... -> a_L = a_0.
```

只对这种已声明的周期 schedule 证明正性；不把“受限语言恒正”误写成“任意词恒正”。
单一 TN/gauge-TN 锥和固定 semigroup 都是这个结构的退化特例。

闭路“保持一个锥”本身不足以推出普通矩阵 trace 非负。每个被使用的 grade 必须额外满足
以下二者之一：

1. 对每个对象给出显式 simplicial chart `S_(k,a)`，使每条 typed edge 的坐标矩阵
   `S_(k,b)^(-1) Lambda^k(B_(a->b)) S_(k,a)` entrywise nonnegative；闭路回到同一
   chart 后，对角元和 trace 非负；
2. 给出一个在复合下封闭、对所有允许闭路取非负值且与普通 exterior trace 精确相等的
   trace-positive functional。

第一批只实现方案 1；方案 2 只有在先写出精确 functional identity 后才开放。

### 2.3 Pfaffian / Spin 支线

对带 pairing 的 Gaussian operator，不只检查 determinant。把 operator 提升到
full-Fock/Spin 表示后，其矩阵元由 sub-Pfaffians 控制。本轮搜索：

```text
一个固定或有类型的 Fock sign gauge
+ 每个允许时间片在相应 parity block 中逐项非负
+ 周期闭路的 Spin/Fock trace 非负。
```

首轮只做 `2–4` 个复费米模式，以 exact arithmetic、符号可满足性和小规模 SDP 为主。
输入冻结为反对称 Majorana kernel `A^T=-A` 和实际
`U(A)=exp(gamma^T A gamma/4)` Spin lift；固定 Majorana orientation、Fock 基顺序、
even/odd parity trace 与从恒等元连续延拓的 lift 分支。任何只验证
`det(I+D)=Tr_Spin(U)^2` 而没有固定 trace 符号的实现都不验收。

每个物理时间片还必须显式携带整体标量/HS 测度 `c(A)`。实际闭路权重按

```text
w(history) = [product_l c(A_l)] Tr_Spin[U(A_L)...U(A_1)]
```

验收；Spin 双覆盖的连续分支不能替代 `c(A)` 的符号或复相位。只有整个允许历史的
标量乘 Spin trace 为实且非负，才算物理正性。

## 3. 候选语法

### A1. 稀疏 typed exterior-domination edges

- 单粒子维数先取 `n=4,5,6`，只有幸存家族再升到 `7,8`；
- 每个 typed graph 先取 `2–3` 种边，四种边只用于幸存结构；
- 非零有理系数优先来自
  `{-2,-1,-1/2,1/2,1,2}`，另允许有理对角尺度；
- support 取有向路径、稀疏 chord、分块反馈和转置配对，但不复刻
  symmetric-oddcycle `B(p,q,r)` 语法；
- 每个候选必须有至少两个 cone/chart objects，正性依赖合法的 `a->b` 边和闭合
  schedule；若全部对象能合并成一个共同锥或共同 metric，立即降为校准结果；
- types 必须本质不可删除：忘掉 source/target labels 后，untyped alphabet 必须有一个
  满足 `det(I+P)<0` 的精确 forbidden word，或有解析证明说明自由词语言的**完整
  determinant** 并非恒非负；某个 exterior grade 为负、共同 cone/metric 失败或语言
  不闭合都不够。否则它只是给普通 joint alphabet 加标签，不进入本轮候选；
- 优先寻找“某些外幂阶有 typed 正锥、其余阶被主导”的结构，而不是要求原矩阵 TN。

### A2. Support-aware positroid 与多 chart

- 只约束 Cauchy–Binet 展开中实际可达的 minors；
- 允许未被任何合法闭路使用的 minors 为负；
- 用 signed permutation、有理 simplicial cone 和小型网络 chart 作为第一批基变换；
- 通过 `GF(2)`/SAT 检查边符号能否在各对象之间一致消去；
- 若所有 chart 可合并成一个固定 gauge-TN 基，则立即归入已知类。

### A3. 已知类校准

TN、tensor-square、oddcycle fixed/common-metric 家族、所有 untyped joint
`B(p,q,r)` alphabets、single/block exterior CQLF 或 coupled-tail automata，以及简单
sign-regular 两阶段乘积，只用作控制或统一结构校准，不作为新候选计数。ZiboJin 当前
领先的 untyped pair `{p=0.3,p=2.5}` 已完整检查全部 depth-12 words 和十万条
depth-40 随机词；它仍是缺任意深度证书的有限深度候选，归其分支继续推进。

### B1. Pfaffian-TN / positive-spinor

- `2–4` 个复模式；
- 主搜索必须包含真实 pairing；数守恒样本只作实现校准，不能用 determinant 平方代替
  Spin trace；
- 枚举稀疏实/复反对称生成元、固定 Fock gauge 和两 chart 交替；
- 对 sub-Pfaffian support 做与 A2 相同的可达闭路筛选；
- 简单 planar matchgate/Ising、标准 positive orthogonal Grassmannian 和
  type-D total-positive 子类只作校准。

## 4. 已知类前置排除门

任何候选在昂贵长词搜索前依次检查：

1. 偶 flavor 平方、复共轭模平方或显式 block square；
2. ordinary TN、固定 sign-gauge TN、positive monomial/block-TN；
3. 共同可交换代数、共同 invariant block 和静态扇区直和；
4. 固定 Kramers、split-orthogonal invariant form；
5. **完整共同度量可行性**：先在一粒子空间、再在 `2n` Majorana 表示上，对整个
   alphabet 同时求解 Wei/Majorana 型 contraction inequalities，不能只测试一个
   预选 metric；
6. tensor/exterior lift 的标准谱恒等式；
7. typed charts 是否只是时间依赖换基/coboundary，并且在具体物理 slice family 上
   望远镜约化到某个已知固定锥；只在得到显式约化时归入该已知类；
8. 明确记录它作为抽象证书与 constrained switching、automata-constrained products
   和 path-complete multiple-Lyapunov 框架的关系。有限 typed graph + simplicial
   charts 总能提升成对象直和上的固定非负块系统，因此不声称这个抽象框架本身新颖；
   可能的新颖性只能来自新的 fermionic/HS 嵌入、物理受限语言或更强的不可约定理；
9. Pfaffian 支线中的 Majorana reflection positivity、Kramers、split-O、
   Wei contraction、matchgate/Ising 和标准 type-D total positivity。

数值 SDP 找到严格 margin 可作为已知类正证据；数值 SDP 没找到 metric 只能标记为
“未排除”，不能当成不属于已知类的证明。被提升的候选必须补 exact rational
certificate 或可核查的不可行性证书。

## 5. 第一批扫描与算力

### 5.1 参数轴

```text
dimensions       = 4, 5, 6
alphabet sizes   = 2, 3
word depths      = 2, 4, 8, 16, 32
exact exhaustive = two-edge words through depth 8 when the typed graph permits
stress words     = alternating, palindromic, transpose-paired,
                   beam-search and seeded random
pilot budget     = 50,000–100,000 compound/determinant checks
full budget      = 2–5 million checks only after pilot acceptance
```

pilot 先验证 product order、吞吐量、内存、exact-replay 比例和候选漏斗；只有预计完整
批次仍低于十分钟/16 GB 才进入 full budget。每个负例立即用 exact rational 或高精度
路径重放；数值近零点进入隔离队列，不参与正性
统计。每个候选族最多保留 `10–20` 个有限深度幸存者进入小有理区间或
interval-arithmetic 鲁棒性测试。深度 `16,32` 只做 beam、谱目标和随机变异压力搜索，
绝不写成穷举。

### 5.2 计算资源

第一轮必须控制在单机约十分钟、16 GB 内；先用结构门和低维 exact 算法降低候选数。
只有出现下列任一条件才提交集群参数扫描：

- 通过前置门的独立候选超过 `10^5`；
- 预计检查量超过 `10^8`；
- interval/exact replay 预计单机超过十分钟；
- 维数提升需要超过 16 GB 内存。

超算只负责扩大已经有结构信号的搜索，不用于替代候选定义和新颖性排重。

## 6. 程序架构与数据流

计划新增以下职责清晰的模块：

```text
oracle/exterior_category_search.py
    候选语法、typed schedule 与逐词检查

oracle/compound_cones.py
    exterior powers、minors、cone/chart 映射和精确交叉检查

oracle/grade_domination.py
    block certificate、危险 grade 范数和主导下界

oracle/spinor_positive_search.py
    full-Fock/Spin lift、sub-Pfaffian 与 parity-block gauge

oracle/known_class_filters.py
    TN、split/Kramers、共同度量、tensor lift 与可约化性筛选

protocols/exterior-positive-category-v1/
    axes、settings、provenance、分片与恢复说明

tests/
    单元、精确恒等式、已知正负控制和恢复性回归
```

数据流为：

```text
结构化候选
-> 廉价代数/已知类门
-> 短词 exact/高精度反例搜索
-> typed-closure 与 exterior/Pfaffian 检查
-> 长词压力和区间鲁棒性
-> 任意深度证书尝试
-> Hamiltonian/HS 可达性与新颖性审计
```

大体积 cell 输出写入 gitignored 的
`tracks/qmc/results/no-negative-vibes/exterior-positive-category-v1/`。Git 只提交协议、
聚合摘要、最小反例和确认证书。

## 7. 可恢复运行与错误处理

- 每个 cell 原子写 manifest，记录 commit、seed、候选定义、深度和软件版本；
- 重启时只重算 missing/failed cells，不覆盖已完成记录；
- 矩阵乘积使用缩放/log-determinant 路径，避免 overflow；
- `abs(weight)` 或 SDP margin 接近容差时标为 `ambiguous`，转 exact/高精度重放；
- product order、transpose orientation 和 typed source/target 不匹配立即硬失败；
- SDP infeasible、超时和 solver error 分开记录；
- collector 必须检查轴完整性、重复 cell 和设置一致性后才汇总。

## 8. 测试与验收

实现前先冻结下列回归：

1. `Lambda^k` 实现与直接 minors 完全一致；
2. exterior character 总和与 `det(I+P)` 一致；
3. 乘积顺序和转置 convention 有非交换测试；
4. TN、tensor-square 和 oddcycle common-metric 为正控制；
5. 项目已存精确负词为负控制；
6. 非闭合 typed schedule 被拒绝，闭合 schedule 的 trace 可直接重构；
7. Pfaffian/Spin trace 与小 Fock 空间显式矩阵一致；
8. 每片 `c(A)`、HS measure、Spin-lift 分支和闭路总标量均进入显式小 Fock 权重交叉检查；
9. 中断再恢复与一次性运行得到相同汇总；
10. 每个浮点负例都能被 exact 或高精度重放，否则不进入结论。

## 9. 结果等级与停止条件

| 等级 | 含义 | 可说什么 |
|---|---|---|
| S0 | 有精确负例或结构门失败 | 该候选关闭 |
| S1 | 有限深度幸存 | 只是待证候选 |
| S2 | 任意深度 exact/analytic certificate | 已证矩阵或受限语言正性 |
| S3 | S2 + coboundary/已知物理类严格排除 + 完整 HS/受限语言嵌入 | 新 fermionic 受限语言机制强候选；不声称 automaton 框架新颖 |
| S4 | S3 + 有意义模型、可扩展性和独立文献审计 | 可讨论新无符号物理类 |

若第一批所有幸存者都被共同度量、固定 gauge-TN 或标准 Pfaffian 类吸收，停止当前语法，
不追加同分布样本。若 exterior 与 Pfaffian 两线都没有 S1，则保留精确反例地图，并重新
设计候选语法。只有 S2 以上结果才值得大规模扩维。

“发现一条矿脉”还必须同时满足：存在非零宽度的参数区域、至少两个不对易边、interval
certificate、可推广到更多 typed objects 或模式，以及已知类的精确非包含证书。一个
孤立 S2 矩阵不按矿脉报告。

## 10. 与协作者工作的边界

- ZiboJin 的 `work/zibo/representation-cones` 保留 oddcycle、untyped joint
  alphabets、block exterior contraction 与 coupled-tail 证书的原始贡献归属；
- ZiboJin 的 `work/zibojin/tensor-square-phase-diagram` 继续负责 tensor-square
  `m=3,4,6,8` 的 ED/DQMC 与相图工作；
- 本轮不复制两条分支代码，不重扫任何 untyped joint `B(p,q,r)` alphabet、single/block
  exterior CQLF 或 coupled-tail automaton，也不并行做 tensor-square 相图；
- 本轮只把这些结果作为正控制、已知类门和设计经验，新增代码与结论由籼至分支提交。

## 11. 第一轮交付

1. 可恢复的 `exterior-positive-category-v1` 协议；
2. 2–5 百万次低维筛选的聚合表；
3. 每个失败家族的最小精确反例；
4. 所有 S1 幸存者的 candidate card 与完整已知类筛选表；
5. 至少一次 arbitrary-depth certificate 尝试，成功或失败都记录；
6. 面向非专家的中文报告：我们试了什么、为什么淘汰、剩下什么以及是否值得上超算。

这份规格只冻结研究对象、排重门和第一批预算；不会预先把有限深度幸存者写成新发现。
