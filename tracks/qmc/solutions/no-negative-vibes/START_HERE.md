# 从这里开始

## 一句话目标

寻找新的、可映射回具体量子模型的矩阵结构，使辅助场量子蒙卡的每个构型权重
`det(I + exp(A_1) ... exp(A_L))` 始终非负；或者用精确反例排除一个看似可行的候选。

## 现在做到哪里

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
- 主办方候选仍未全部完成：TN 的文献史排重、超出普通一维开链的新 Hamiltonian、以及
  复 Majorana 简洁矩阵定理仍开放。

## 阅读顺序

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
7. [任意小夹角解析反例](docs/SMALL_ANGLE_COUNTEREXAMPLE.md)：看 Majorana 双锥的独立反例。
8. [Majorana 双锥结果](docs/MAJORANA_CONE_RESULTS.md)：看直接 Spin 迹、精确负分支和完整证据。
9. [主办方方向完成度](docs/ORGANIZER_DIRECTION_AUDIT.md)：区分已关闭、第一轮完成和仍开放。
10. [`U(p,q)` 相位结论](docs/PSEUDOUNITARY_PHASE_RESULTS.md)：看连续相位为何可解但仍有负号。
11. [下一阶段研究计划](docs/NEXT_RESEARCH_PLAN.md)：看主线、交付、停止条件和两人分工。
12. [AZ 十类结果](docs/AZ_TENFOLD_RESULTS.md)：看符号表、精确证书和约化结论。
13. [经典群基线](docs/BASELINE_RESULTS.md)：看已经排除了什么、什么只是复现已知结果。
14. [项目定性与算力策略](docs/COMPUTE_STRATEGY.md)：判断何时本地跑、何时值得上超算。
15. [2026 文献与空白](docs/LITERATURE_GAP_2026.md)：决定值得继续攻的研究缝隙。
16. [研究地基](docs/FOUNDATIONS.md)：需要公式、文献、精确证书或候选方向时再查。

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

外围宽扫已完成，不需要重复。现在围绕全非负路径类做三件事：

1. 沿 discrete/bond-channel HS 引用链排查精确非对称键门分解是否已有直接先例；
2. 请合作者/出题人复核已完成的 2024 contraction-semigroup 非归约证明；
3. 直接 TN 正和、逐扇区符号规范和普通 ancilla 偏迹都无法产生普通非相邻 hopping；
   下一步只攻击真正改变 Hilbert 空间的 gauge/ancilla 编码、带宇称串相关 hopping、
   pairing/Majorana 或更大半群。

现有一维构造本身可作为新辅助场算法候选继续测方差和条件数；如果正和路线仍不能产生
超出已知一维事实的模型，就把 TN 结果定位为新矩阵机制候选、算法分解和边界定理，继续
搜索比 TN 更大的主子式非负乘法半群，不冒充新 Hamiltonian。
