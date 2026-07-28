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
- 已把它映射到掺杂开放 Hubbard 链和单 flavor 排斥 `t-V` 开放链的离散 HS 时间片，并
  穷举两个小系统的全部辅助场构型。
- 两个不同旋转 split cones 的完整并集也已解析关闭：四维两层权重
  `16[1-q^2 sin^2(theta)]`，所以任意非平凡主夹角都有负权。
- 主办方候选仍未全部完成：全非负路径类的 QMC 新颖性排重、超出普通一维开链的物理模型、
  以及复 Majorana 简洁矩阵定理仍开放。

## 阅读顺序

1. [中文零基础导读](docs/ONBOARDING.zh-CN.md)：先理解问题、术语和我们为什么这样做。
2. [全非负路径类](docs/TOTAL_NONNEGATIVE_PATH_CLASS.md)：看当前严格恒正主候选、三步证明和
   两个物理 HS 最小模型。
3. [新半群初筛结果](docs/FRONTIER_SEMIGROUP_RESULTS.md)：看 139.2 万权重淘汰表、80 位
   反例和任意小 split-cone 夹角解析反例。
4. [任意小夹角解析反例](docs/SMALL_ANGLE_COUNTEREXAMPLE.md)：看 Majorana 双锥的独立反例。
5. [Majorana 双锥结果](docs/MAJORANA_CONE_RESULTS.md)：看直接 Spin 迹、精确负分支和完整证据。
6. [主办方方向完成度](docs/ORGANIZER_DIRECTION_AUDIT.md)：区分已关闭、第一轮完成和仍开放。
7. [`U(p,q)` 相位结论](docs/PSEUDOUNITARY_PHASE_RESULTS.md)：看连续相位为何可解但仍有负号。
8. [下一阶段研究计划](docs/NEXT_RESEARCH_PLAN.md)：看主线、交付、停止条件和两人分工。
9. [AZ 十类结果](docs/AZ_TENFOLD_RESULTS.md)：看符号表、精确证书和约化结论。
10. [经典群基线](docs/BASELINE_RESULTS.md)：看已经排除了什么、什么只是复现已知结果。
11. [项目定性与算力策略](docs/COMPUTE_STRATEGY.md)：判断何时本地跑、何时值得上超算。
12. [2026 文献与空白](docs/LITERATURE_GAP_2026.md)：决定值得继续攻的研究缝隙。
13. [研究地基](docs/FOUNDATIONS.md)：需要公式、文献、精确证书或候选方向时再查。

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

1. 深查“total nonnegativity + AFQMC/DQMC”及单 flavor `t-V` 开链任意化学势是否已有直接先例；
2. 判断它是否被 2024 contraction-semigroup 条件经固定 Majorana 变换完整包含；
3. 从 TN 的双对角/平面网络分解构造一个不只是普通 Jordan--Wigner 开链的物理 HS 模型。

如果第三步不能产生超出已知一维事实的模型，就把 TN 结果作为漂亮的充分条件和边界定理，
继续搜索比 TN 更大的主子式非负乘法半群，不冒充新发现。
