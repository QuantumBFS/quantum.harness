# 从这里开始

## 一句话目标

寻找新的、可映射回具体量子模型的矩阵结构，使辅助场量子蒙卡的每个构型权重
`det(I + exp(A_1) ... exp(A_L))` 始终非负；或者用精确反例排除一个看似可行的候选。

## 现在做到哪里

- 已完成题目拆解、主要已知定理和新颖性边界的调研。
- determinant oracle、Majorana 直接 Fock/Spin 迹 oracle、25 个基线结构生成器、可恢复参数
  扫描和汇总绘图已经实现并通过自动测试。
- 17 组正、负、零或复相位证书已保存为机器可读的精确符号数据，并通过 SymPy 验证。
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
- 下一步不是重复普通 AZ 或双锥宽扫，而是转向小角解析/约束优化、其他非平凡锥交集和具体
  DQMC 映射。

## 阅读顺序

1. [中文零基础导读](docs/ONBOARDING.zh-CN.md)：先理解问题、术语和我们为什么这样做。
2. [Majorana 双锥结果](docs/MAJORANA_CONE_RESULTS.md)：看直接 Spin 迹、精确负分支和小角边界。
3. [AZ 十类结果](docs/AZ_TENFOLD_RESULTS.md)：看符号表、精确证书和约化结论。
4. [经典群基线](docs/BASELINE_RESULTS.md)：看已经排除了什么、什么只是复现已知结果。
5. [项目定性与算力策略](docs/COMPUTE_STRATEGY.md)：判断何时本地跑、何时值得上超算。
6. [2026 文献与空白](docs/LITERATURE_GAP_2026.md)：决定值得继续攻的研究缝隙。
7. [研究地基](docs/FOUNDATIONS.md)：需要公式、文献、精确证书或候选方向时再查。
8. [明日开工板](docs/KICKOFF.md)：组队后直接照此确定主候选、分工和第一轮交付。

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

普通经典群、标准 Hermitian AZ 表和普通 Majorana 双锥宽扫都已经跑完，不需要重复。下一步
应满足至少一个条件：

1. 解析或约束优化小角 Majorana 双锥，判断是否存在角度/范数联合界；
2. 是不约化到同一已知收缩半群的其他对称约束与半正定锥交集；
3. 直接来自一个明确的 Hamiltonian 和 HS 分解。

对新候选仍按小维度反例搜索 → 精确证书 → 已知类约化 → 扩大扫描 → 证明 → 物理映射推进。
