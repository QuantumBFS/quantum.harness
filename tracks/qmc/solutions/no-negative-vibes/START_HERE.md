# 从这里开始

## 一句话目标

寻找新的、可映射回具体量子模型的矩阵结构，使辅助场量子蒙卡的每个构型权重
`det(I + exp(A_1) ... exp(A_L))` 始终非负；或者用精确反例排除一个看似可行的候选。

要一次看完全部尝试、矩阵构造、Hamiltonian、失败路线和最新结论，直接阅读
[项目完整总结](docs/PROJECT_MASTER_SUMMARY.zh-CN.md)。它是当前唯一自包含总报告。

## 当前结论

先看 [成果总账](docs/RESULTS_LEDGER.md)。截至 2026-07-29：

- 三套纯 determinant 正性机制和一套 graded 正权机制已经严格证明；
- 五组局域相互作用 Hamiltonian 已完成映射，但尚无一组能确认是新的无符号物理类；
- graded monomial 已约化到已知 Majorana 正性，odd block-TN 的自然局域化有精确负权；
- tensor-square 四模式模型约化到 split `O(2,2)`，一般提升有条带非局域障碍；
- 第一版 gauge/cocycle 能精确消号，但会形成随系统增长的 Wilson string；
- ZiboJin 的独立 exterior-cone 分支把 oddcycle seeds `117/132/147` 分别精确推进到
  全部 depth-27 words，并完成 448 个长度 60–1800 的对抗重放；它们仍是有限深度候选；
- 另一套 symmetric-oddcycle 连续字母表已经有任意深度严格定理和五模相互作用
  transfer，但最新 exact common-metric 证书又把整个区间归入已知
  Wei 不定度量收缩半群（signature `(1,4)`），所以它是完整的已知类实例，不是新机制；
- ZiboJin 随后找到一个新的 **untyped joint-alphabet 有限深度候选**：
  `{p=0.3,p=2.5}`（`q=r=1`，含各自转置）。每个点单独有严格 metric，但联合 alphabet
  没有数值严格共同底层 metric；全部 22,369,620 个 depth<=12 非空 words 和十万条
  depth<=40 随机词都严格正。它还缺任意深度 tail certificate，不能称新机制；
- 第一批已经得到一个通用 Hermitian 半群模型工厂和八种严格/精确可约化模型；
  后续排查已把 adjoint lift 归入已知 split-orthogonal 类，并证明 grade-charge
  full trace 只是静态 ancilla 扇区直和。
- Tensor-square 的 `m=3` 已从 ED 异常推进到 DQMC/ED 定量交叉验证：三种 Trotter
  步长下能量、密度和通道涨落均在 `1.5 sigma` 内一致，低温伪负号也已由 SVD
  稳定化修复；这证明工具可用于相图扫描，但还没有发现新相。该相图线由 ZiboJin
  的独立分支推进。
- 籼至下一轮不重复 oddcycle 单字母表或 tensor-square 相图，而搜索真正多状态的
  typed exterior 正锥范畴，以及含真实 pairing 的 Pfaffian/Spin 正性；完整共同度量
  排重放在第一道门。types 必须本质不可删除，避免与上述 untyped joint alphabet 重合。
- 单向 Stark 链的 Hermitian partner 不唯一：同一非厄米链既可对应对角模型，也可经
  任意 unitary 换基写成长程模型，所以它只保留为方法校准。
- **确认的新无符号物理类仍为零。** 完整结论与贡献归属见
  [项目完整总结](docs/PROJECT_MASTER_SUMMARY.zh-CN.md)。

下面的长清单用于审计数字，日常不需要逐条阅读。

<details>
<summary>展开完整扫描与证明快照</summary>

- 已完成题目拆解、主要已知定理和新颖性边界的调研。
- determinant oracle、Majorana 直接 Fock/Spin 迹 oracle、25 个基线结构生成器、可恢复参数
  扫描和汇总绘图已经实现并通过自动测试。
- 19 组正、负、零或复相位证书已保存为机器可读的精确符号数据，并通过 SymPy 验证。
- `classical-groups-v1` 已完成 900 个参数格点、90 万个矩阵乘积，运行记录无缺失。
- `az-tenfold-hermitian-v1` 已完成 720 个格点、72 万个乘积；六个失败类均从深度 3 开始，
  并已得到五组 Hermitian 正定三因子精确证书。
- 扫描和精确证书已排除 `SL(2/3,R)`、`Sp(2/4,R)`、`SU(1,1)`、`SU(2,1)`、
  `SU(3)` 的普遍非负性；`U(2)`、`U(1,1)` 的单 flavor 权重一般为复数。
- 零负例的 `O(p,q)` 恒等分支、`SO(3)`、`SU(2)`、`USp(2/4)` 都能归入已知机制，
  不能当成新发现。
- 标准 Hermitian AZ 十类没有产生新类：BDI 约化到 split-orthogonal，
  AII/DIII/CII 约化到 Kramers，其余六类有精确负权或复权。
- 已完成 448,000 个“共享 `J1`、旋转 `J2`”Majorana 双锥权重和 252,000 个小角压力样本：
  共同实结构只保证实权，不能保证非负；相反锥已有 `p=2-2*cosh(1)<0` 的深度二精确证书。
- 已找到任意小非零夹角的两层解析反例
  `p(theta,q)=-4*sin(theta)*sinh(q)^2<0`，完整旋转双锥并集方向已关闭。
- `U(p,q)` 连续相位已经理论闭合：
  `arg det(I+D)=arg det(D)/2 mod pi`，但剩余正负号不受保护，因此不是新无符号类。
- 新完成 15 个半群候选的 720,000 权重广扫和 672,000 权重压力扫描；环、星形、稠密
  Metzler 图、逐片换规范和双向分块耦合均已有负权。
- 找到全非负路径半群：三对角 Metzler 生成元的指数及任意乘积全非负，因此一般性地有
  `det(I+D)>=1`；这不是零负例猜想，而是任意维数、深度的严格证明。
- 已完成 TN 矩阵类的核心新颖性排重：利用类中同时包含 `+D/-D`，严格排除固定
  split metric、实收缩锥和 Kramers；在 Majorana 表示中进一步排除 Wei 2024 条件，
  包括任意固定复正交换基。
- 已把它映射到掺杂开放 Hubbard 链和单 flavor 排斥 `t-V` 开放链的离散 HS 时间片，并
  穷举两个小系统的全部辅助场构型。
- 新得到排斥 `t-V` 局部键门的精确两场分解：两个场值都是非对称 TN 高斯传播子，正系数
  平均严格还原物理键门；重叠键集合不存在固定全局 Hermitian 化度量，因而确实进入 TN
  的非对称区域，但物理 Hamiltonian 仍是已知一维链。
- 又证明了更强的物理边界：TN 数守恒高斯算符的 Fock 矩阵元都是非负子式，因此任意正和
  也无法表示普通非相邻 hopping 的占据依赖符号；不加 ancilla 时，环和真正分支仍被关闭。
- 把条件放宽到“每个粒子数扇区有独立固定符号规范”后，2–6 站点所有连通图穷举仍只有
  标号开放路径幸存；一般 forbidden motifs 是环和三支星形中的费米交换负闭环。
- 两个不同旋转 split cones 的完整并集也已解析关闭：四维两层权重
  `16[1-q^2 sin^2(theta)]`，所以任意非平凡主夹角都有负权。
- 新完成 BDI/AII/DIII/CII 幸存类的七族半群锥、14 万权重初筛：三个零失败族都严格
  保留已知 split/Kramers 机制；BDI 两面锥有 4,219 个负权，DIII/CII 的非平凡放松在
  深度 2 或 3 即产生复权，并由 80 位重放确认；BDI 另有两层解析反例
  `16(1-q^2)<0`。
- 新完成 12 个激进结构的 192,000 权重筛选。奇数阶 positive-monomial 和 block-TN
  路由已有循环分解的一般正性证明，且包含 ordinary TN 之外的矩阵，并排除固定
  Kramers 和公共范数收缩解释；
  偶阶路由、逐片改变收缩 metric、双向 reciprocal coupling 和 near-commuting 并集均
  已由 80 位负例排除。`D_4` Lusztig 锥约化到已知 split `SO(4,4)`。
- 新完成 640 条 Majorana auxiliary-field 历史；每条分别计算 even、odd 和完整 Fock 迹。
  在 canonical `J1/J2` 与当前 Jordan-Wigner 取向下，猜想
  `pi_*=(-1)^[m(m+1)/2]` 指定的扇区在 `m=2..6` 零失败，互补扇区每个维数都观察到
  数值负权；这是 convention-dependent ensemble-level 猜想，不是已完成定理。
- 已证明一个 pure-TN 之外的 graded-monomial crossing 恒等式：
  `sgn(P) det(I+P D)>=0`（`D_ii>=1`），并构造了奇环上的吸引 spinless-fermion
  Hamiltonian、逐历史正权和 real-exponential grade ancilla。
- 随后的已知类排重给出明确降级：`r=1` 顶点精确等于 `su(1|1)` graded
  permutation；`r>1` Hamiltonian 的 centered 一体 kernel 逐边负半定、密度作用全为
  吸引，因而严格包含在 2016 Majorana reflection positivity 类中。它是有用的矩阵
  表述和特殊 CT 分解，不是新的无符号 Hamiltonian 类。进一步文献核对还确认，所用
  cycle factor 是已知 monomial 特征多项式分解的直接推论，因此矩阵端也不主张新定理。
- 对旧的 odd block-TN 候选完成最关键的局域闭环：两个格点、三个 flavor 上，
  independent local `C3` routes 与 flavor-preserving 对称正定 TN hopping 各自都是
  实指数时间片，但两层精确满足 `det(I+XR)=-2`。固定全局分块定理仍正确；自然局域
  Hamiltonian 推广已关闭。
- 当前总集成分支完整自动测试为 `370 passed`。ZiboJin 的
  `representation-cones@838f428` 忽略一个旧的未实现 R01 classifier 测试模块后为
  `499 passed, 2 skipped`；两个 skip 都因未安装可选 `cvxpy`。Tensor-square phase
  分支 `efb2e18` 为 `13 passed`。
- 主办方候选仍未全部完成：TN 的文献史排重、超出普通一维开链的新 Hamiltonian、完整
  复 Majorana/BdG/Pfaffian 表述、比 TN 更大的半群仍开放。

</details>

## 阅读顺序

日常只需：

1. [项目完整总结](docs/PROJECT_MASTER_SUMMARY.zh-CN.md)：全部尝试、矩阵、模型和结论；
2. [成果总账](docs/RESULTS_LEDGER.md)：只核对数量和当前状态；
3. [中文零基础导读](docs/ONBOARDING.zh-CN.md)：补齐术语；
4. [下一阶段研究计划](docs/NEXT_RESEARCH_PLAN.md)：只看接下来做什么；
5. 与某个结论有关时，再进入对应专题文档。

<details>
<summary>展开专题复核索引</summary>

1. [中文零基础导读](docs/ONBOARDING.zh-CN.md)：先理解问题、术语和我们为什么这样做。
2. [全非负路径类](docs/TOTAL_NONNEGATIVE_PATH_CLASS.md)：看当前严格恒正主候选、三步证明和
   两个物理 HS 最小模型。
3. [TN 新机制审计](docs/TN_NOVELTY_AUDIT.md)：看它为什么不约化到 Kramers、
   split/contraction metric 或 Wei 2024 Majorana 条件，以及目前还不能声称什么。
4. [TN 物理映射前沿](docs/TN_PHYSICAL_MAPPING_FRONTIER.md)：看连续路径 no-go、排斥
   `t-V` 键门的精确非对称高斯分解，以及为何当前仍不是新物理模型。
5. [复合矩阵规范 no-go](docs/COMPOUND_GAUGE_NO_GO.md)：看为什么即使每个粒子数扇区
   独立换符号规范，普通 hopping 图仍只有开放路径。
6. [新半群初筛结果](docs/FRONTIER_SEMIGROUP_RESULTS.md)：看 139.2 万权重淘汰表、80 位
   反例和任意小 split-cone 夹角解析反例。
7. [AZ 幸存类半群锥](docs/AZ_SURVIVOR_CONE_RESULTS.md)：看七族、14 万权重、80 位反例和
   为什么零失败者仍只是已知机制。
8. [激进候选首批结果](docs/SPECULATIVE_STRUCTURE_RESULTS.md)：看奇数阶 monomial 的一般
   证明、四类 80 位反例和 Majorana 宇称猜想。
9. [graded monomial 排重结果](docs/GRADED_MONOMIAL_RESULTS.md)：看 crossing
   cycle 定理、奇环模型，以及为什么它最终属于已知 Majorana 正性类。
10. [odd block-TN 局域闭环](docs/ODD_BLOCK_TN_LOCALITY_AUDIT.md)：看固定分块
   定理为何不能无代价局域化，以及两层整数反例。
11. [gauge/cocycle 第一轮](docs/GAUGE_COCYCLE_RESULTS.md)：看四/六模式精确消号和
   `2 x L` Wilson-string 局域性障碍。
12. [激进候选清单](docs/SPECULATIVE_CANDIDATE_BATCH.md)：看已占位的下一批
   spinor/exterior-cone 方向。
13. [任意小夹角解析反例](docs/SMALL_ANGLE_COUNTEREXAMPLE.md)：看 Majorana 双锥的独立反例。
14. [Majorana 双锥结果](docs/MAJORANA_CONE_RESULTS.md)：看直接 Spin 迹、精确负分支和完整证据。
15. [主办方方向完成度](docs/ORGANIZER_DIRECTION_AUDIT.md)：区分已关闭、第一轮完成和仍开放。
16. [`U(p,q)` 相位结论](docs/PSEUDOUNITARY_PHASE_RESULTS.md)：看连续相位为何可解但仍有负号。
17. [下一阶段研究计划](docs/NEXT_RESEARCH_PLAN.md)：看主线、交付、停止条件和两人分工。
18. [AZ 十类结果](docs/AZ_TENFOLD_RESULTS.md)：看符号表、精确证书和约化结论。
19. [经典群基线](docs/BASELINE_RESULTS.md)：看已经排除了什么、什么只是复现已知结果。
20. [项目定性与算力策略](docs/COMPUTE_STRATEGY.md)：判断何时本地跑、何时值得上超算。
21. [2026 文献与空白](docs/LITERATURE_GAP_2026.md)：决定值得继续攻的研究缝隙。
22. [研究地基](docs/FOUNDATIONS.md)：需要公式、文献、精确证书或候选方向时再查。

</details>

不需要阅读 `quantum.harness` 的其他 track、skill 或主办方开发文件。

## 工作区边界

```text
signfree-qmc/                 你平时看到的干净入口
├── START_HERE.md             当前状态、阅读顺序、下一步
├── README.md                 队伍和挑战登记
├── docs/                     导读、证据标准和开工板
├── fixtures/                 语言无关的精确测试数据
├── oracle/                   数值 oracle、结构生成器和报告代码
├── protocols/                固定参数轴、种子和软件来源
└── tests/                    精确证书和数值回归测试
```

大体积扫描输出遵守比赛仓库约定，写入
`tracks/qmc/results/no-negative-vibes/`，不会混进源码，也不会提交进 Git。

## 唯一日常入口

```bash
cd /home/volper/harness_quantum/signfree-qmc
```

`signfree-qmc` 是一个指向比赛规定 solution 目录的本地入口，因此没有两份文件，也不需要手工同步。

## 下一步

外围宽扫和第一批激进结构筛选已完成，不需要重复。现在按以下收尾和开工顺序推进：

1. graded monomial、odd block-TN 和 R01 fixed Klein-Hodge 都转为已知类或
   exact no-go 回归，不再作为新物理主线；
2. 六模式 Fock–CP 的 13 个 depth-2 Klein 电路首轮已完成，520 个单元都没有
   Hermiticity-preserving bridge；一般 non-Klein Choi 锥仍开放；
3. tensor-square 已得到四模式局域 HS，但该模型属于 split `O(2,2)`；一般维数的
   直接提升又产生非局域行列条带；
4. edge-electric gauge/cocycle 在四/六模式上精确消号，但扩展后产生 system-size
   Wilson string；该对象现在作为允许的非常规模型来源，而不是立即淘汰；
5. Majorana 宇称 period-4 猜想作为独立支线继续，不阻塞新机制搜索。
6. 非常规模型第一批和三个候选的首轮排重已经完成：adjoint lift 归入已知 split 类，
   grade-charge 降为静态扇区直和；tensor-square 的 ED/DQMC 相图线由 ZiboJin
   继续推进，本分支不做重复扫描。
7. 下一轮先搜索 typed exterior 正锥范畴，再以小预算并行搜索含真实 pairing 的
   Pfaffian/Spin 正性；单 alphabet exterior metric、`B(p,q,r)` 和 tensor-square
   都只作已知控制。设计见
   [新搜索规格](../../../../docs/superpowers/specs/2026-07-29-exterior-positive-category-search-design.md)。

TN 一维构造和 graded monomial 都是严格矩阵机制；前者物理上仍是一维已知模型，
后者已明确约化到 Majorana reflection positivity。后续候选必须同时通过数学证明、
物理映射和已知类排重，才升级为新的物理无符号类。

本轮候选定义、严格恒等式、已知反例和停止条件见
[自底向上正性候选](docs/BOTTOM_UP_POSITIVITY_CANDIDATES.md)。
Fock–CP 第一批 520 个线性系统见
[六模式 Fock–CP 首轮结果](docs/FOCK_CP_SCREEN_RESULTS.md)。
Tensor-square 的严格定理、四模式 HS、split 约化和局域性障碍见
[tensor-square 结果](docs/TENSOR_SQUARE_RESULTS.md)。
Gauge/cocycle 的精确 GF(2) 解和 Wilson-string 障碍见
[gauge/cocycle 第一轮结果](docs/GAUGE_COCYCLE_RESULTS.md)。
放宽短程、局域和 Hermitian 限制后的新主线见
[非常规模型发现](docs/UNCONVENTIONAL_MODEL_DISCOVERY.md)。
