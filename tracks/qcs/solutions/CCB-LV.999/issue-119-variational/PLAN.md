# Issue #119 变分问题实施设计

## 1. 决策与范围

本目录服务于 Quantum Harness challenge
[#119：Advantage or artifact? Hunt on the Quantum Advantage Tracker](https://github.com/QuantumBFS/quantum.harness/issues/119)。
团队采用“先建立可信基线，再攻击公开量子结果”的路线：

1. 用 DMRG 复现 2Fe–2S 的公开经典结果，打通 FCIDUMP、对称性、轨道排序、
   DMRG 收敛和结果记录的完整流程。
2. 将同一流程迁移到 four-impurity Anderson model，寻找比公开 SKQD 量子结果
   更低的**显式变分上界**。
3. 只有当前两个问题都形成可复现结果后，才评估 issue #119 中的 active
   candidate。active candidate 不属于本阶段的完成条件。

本文按可验收的 goal 组织，不按自然日组织。计算开始前，仍需按本仓库规则逐项确认
Hamiltonian、粒子数与自旋扇区、轨道表示、DMRG 精度参数和计算资源。

当前公开注册 PR 位于 `tracks/qcs/`，因此本设计先保存在已经注册的团队目录中。
如果最终工作完全采用 DMRG/MPS，是否把公开 PR 和目录迁移到 `tracks/mps/` 是一个
独立的对外变更，必须由团队确认后更新同一个 PR；本设计不擅自执行迁移。

## 2. 初学者需要先理解的四件事

### 2.1 什么是变分能量

对任意归一化试探态 |ψ⟩，能量

```text
E[ψ] = ⟨ψ|H|ψ⟩
```

不会低于真实基态能量 E₀。因此，有限键维 DMRG 得到的显式能量是一个严格的
**上界**：数值越低，试探态越好。

这带来两条报告规则：

- 最大键维计算直接得到的能量可以作为 headline，因为它对应一个具体、可复现的
  MPS 波函数。
- 将舍弃权重外推到零得到的能量只能作为辅助估计；外推值本身不一定对应一个显式
  波函数，不能冒充严格变分上界。

### 2.2 什么是 FCIDUMP

FCIDUMP 是保存电子结构 Hamiltonian 的标准文本格式。“FCI”指 full
configuration interaction，“DUMP”表示把积分数据写入文件。文件不包含答案，
而是包含：

- 空间轨道数 `NORB`；
- 电子数 `NELEC`；
- `MS2 = N↑ − N↓`，即总 Sᶻ 的两倍；
- 一电子积分 hᵢⱼ；
- 二电子积分 (ij|kl)；
- 常数能量。

因此，FCIDUMP 可以被 Hartree–Fock、selected CI、DMRG 等不同算法读取，使它们
在**完全相同的 Hamiltonian**上比较。

### 2.3 什么是 DMRG 和 MPS

完整波函数的系数数目随轨道数指数增长。DMRG 不保存所有系数，而是把波函数写成
matrix product state（MPS，矩阵乘积态）：一条由小张量组成的链。

相邻张量之间的键维 D 决定最多能保留多少纠缠：

- D 越大，试探态空间越大，变分能量通常越低；
- 主要时间成本近似随 D³ 增长；
- 轨道在线性 MPS 链上的排列会显著改变所需纠缠，因此轨道排序是算法的一部分，
  不是无关紧要的性能选项。

DMRG 通过来回 sweep，反复优化一个或两个相邻张量。我们同时记录能量变化和
discarded weight（舍弃权重），判断有限 D 误差是否仍然显著。

### 2.4 为什么先做 2Fe–2S

2Fe–2S 和 Anderson 实例都由 FCIDUMP 描述，也都适合使用 block2 的量子化学
DMRG 接口。先复现 2Fe–2S 能检验：

- FCIDUMP 读取和积分约定是否正确；
- 电子数、自旋和 SU(2) 对称性是否设置正确；
- Fiedler 轨道排序、DMRG sweep、restart 和结果记录是否可靠；
- 在攻击未知结果前，我们是否能复现一个公开、可比对的能量。

它不是“先做一个无关的小例子”，而是 Anderson 计算管线的校准问题。

## 3. Goal 总览

| Goal | 产出 | 验收条件 |
|---|---|---|
| G0：冻结输入与环境 | 数据清单、校验和、锁定环境、资源选择 | 两个 FCIDUMP 来源可追溯；block2 版本固定；cluster precheck 通过 |
| G1：复现 2Fe–2S | D 序列、显式变分能量、舍弃权重、收敛图 | 最大 D 能量与公开结果相差不超过 1×10⁻⁴ Eₕ；扇区正确 |
| G2：形成复用管线 | 公共 runner、配置文件、restart、结构化输出 | 不修改求解核心即可从 2Fe–2S 切换到 Anderson |
| G3：建立 Anderson 廉价基准 | FCIDUMP 审计、RHF/CAS 参考、低 D 试跑 | 能量低于 RHF；不同排序均保持粒子数和自旋 |
| G4：选择 Anderson 轨道表示 | Fiedler 与物理启发排序对比 | 用能量、舍弃权重、内存和 sweep 时间共同选出生产排序 |
| G5：推进 Anderson 变分上界 | 递增 D 的生产计算和 restart | headline 为最大 D 的显式能量；报告相对三个参考值的差 |
| G6：验证与写作 | 可运行脚本、run.json、图、短报告 | 结果可从干净环境重跑；负面结果也完整记录 |
| G7：active candidate 决策 | 下一阶段 go/no-go 记录 | 仅在 G1–G6 全部完成后启动，不阻塞本阶段完成 |

## 4. 问题 A：2Fe–2S DMRG 基线

### 4.1 物理问题是什么

目标体系是合成的铁硫簇 [Fe₂S₂(SCH₃)₄]²⁻。铁硫簇中的多个 Fe 3d 和 S 3p
轨道能量接近，电子不能被一个单独 Slater determinant 可靠描述，这就是
“strongly correlated”在这里的含义。

原始分子包含更多轨道。公开实例使用 active space：只显式保留决定低能物理的
20 个空间轨道和 30 个电子，其余轨道的影响已折叠进 FCIDUMP 的积分和常数项。
这些 active-space 轨道来自局域化 DFT 计算；公开数据说明采用 BP86 functional、
TZP-DKH basis 和 sf-X2C 标量相对论 Hamiltonian。

官方输入：

- 文件：`2fe_2s_30e_20o.fcidump`
- `NORB=20`
- `NELEC=30`
- `MS2=0`
- 目标：自旋 singlet 的基态能量

若只利用 N↑=N↓=15 的粒子数扇区，Slater determinant 数目已经是

```text
C(20,15)² = 240,374,016
```

这说明直接构造稠密 Hamiltonian 不合适，而 DMRG 可以通过 MPS 压缩低能态。

### 4.2 要复现的公开结果

公开方法证明使用 block2 0.5.3、SU(2) spin symmetry 和 Fiedler orbital
reordering。参考 DMRG 序列为：

| 键维 M | 能量 E（Eₕ） | discarded weight |
|---:|---:|---:|
| 250 | −116.52624 | 6.8×10⁻⁴ |
| 500 | −116.53577 | 3.3×10⁻⁴ |
| 1000 | −116.60505 | 7.7×10⁻⁵ |
| 1500 | **−116.60547666** | **3.0×10⁻⁵** |

零舍弃权重外推值 −116.605745 ± 2.7×10⁻⁴ Eₕ 只作辅助，不作为 headline。

来源：

- [官方 FCIDUMP](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/tree/main/data/variational-problems/hamiltonians/2fe_2s)
- [公开 DMRG 方法证明](https://github.com/MonitSharma/qat-2fe2s-submission)
- [Quantum Advantage Tracker submission #229](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/229)

### 4.3 具体复现方案

#### R1：数据与 provenance

实现一个输入获取步骤，而不是手工复制文件：

1. 从官方 tracker URL 下载 FCIDUMP。
2. 保存下载 URL、Git commit SHA、文件大小和 SHA-256。
3. 解析 header，并在计算前打印 `NORB=20, NELEC=30, MS2=0`。
4. header 与配置不一致时立即停止，禁止在错误扇区继续计算。

#### R2：可复现软件环境

使用 solution-local Python 环境，不修改 harness 的全局工具栈：

- Python 3.12；
- `block2==0.5.3`；
- 核心数值依赖与公开方法证明一致：`pyscf==2.13.1`、
  `numpy==2.5.1`、`scipy==1.18.0`、`matplotlib==3.11.0`、
  `psutil==7.2.2`；
- 生成并提交 lock file；
- 记录 block2、BLAS、线程数、CPU 型号和可用内存。

本仓库已有 block2 API 参考：
`.knowledge/software/block2-api.md`。block2 当前不在根 Makefile 的
`INSTALLABLE` 列表中，因此依赖必须由本 solution 的锁定环境明确拥有，不能假装
它已经由 `make install` 提供。

#### R3：DMRG 设置

复现优先遵循公开方法，而不是重新猜参数：

- symmetry：SU(2)，粒子数 30，总自旋 S=0；
- orbital ordering：Fiedler；
- 固定随机种子 1234；
- 键维序列：250 → 500 → 1000 → 1500；
- 小 M warmup 后逐步收紧 Davidson tolerance；
- 每个 M 的早期 sweep 加 white noise，最后两个 sweep 关闭 noise；
- 保存每个 M 的 MPS checkpoint，使后一个 M 从前一个状态继续；
- 每个 sweep 刷新输出：能量、能量变化、discarded weight、最大内存和耗时。

#### R4：验收

G1 通过必须同时满足：

1. `N=30`、`S=0` 扇区保持不变；
2. 最大 M 的显式能量不随继续 sweep 明显变化；
3. 每个 M 都完成既定收敛 sweep 后，M 增大时显式能量不升高；
4. M=1500 能量与 −116.60547666 Eₕ 的差不超过 1×10⁻⁴ Eₕ；
5. discarded weight 随 M 总体下降，并保存 E 对 discarded weight 的图；
6. headline 使用 M=1500 的显式能量；外推值单独标注。

若 M=1500 因资源限制未完成，G1 不伪装为通过。M=1000 的快速结果可以证明管线
工作，但只能标记为 partial reproduction。

## 5. 问题 B：four-impurity Anderson model

### 5.1 物理问题是什么

Anderson impurity model 描述少数强相互作用轨道与大量不相互作用 bath
轨道耦合的问题。它是研究强关联电子、Kondo screening 和材料 impurity solver
的基本模型。

本实例不是最简单的单杂质模型，而是：

- 4 个 interacting impurity，排成正方形；
- 每个 impurity 配 7 个 bath 轨道，共 28 个 bath 轨道；
- 总计 32 个空间轨道、32 个电子；
- 半填充，`MS2=0`；
- impurity onsite repulsion `U=10`；
- 正方形边 hopping `t=−1`；
- 对角 hopping `t′=−0.5`；
- bath energy 均匀覆盖 [−2,2]；
- hybridization amplitude `V=0.16`，能量依赖取 semicircle-like 形式。

Hamiltonian 分为三部分：

```text
H = H_impurity + H_bath + H_hybridization
```

- `H_impurity`：电子可在四个 impurity 间 hopping，并在同一 impurity 上受到 U；
- `H_bath`：28 个无相互作用 bath 轨道的单粒子能量；
- `H_hybridization`：每个 impurity 与自己的 7 个 bath 轨道交换电子。

具体符号和常数以官方 FCIDUMP 为唯一计算依据，不从文字说明重新生成积分：

- 文件：`anderson_impurity_model_4i_28b_32e.fcidump`
- `NORB=32`
- `NELEC=32`
- `MS2=0`

[官方 Hamiltonian 与参数说明](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/tree/main/data/variational-problems/hamiltonians/anderson_impurity_model)

### 5.2 为什么它值得做

当前有三个清晰的能量台阶：

| 方法 | 显式能量（Eₕ） | 用途 |
|---|---:|---|
| RHF | −57.52492815 | 最低成本的积分与符号检查 |
| CAS(4) exact diagonalization | −61.63174447 | 小 active-space 检查 |
| verified SKQD | **−62.25668182839704** | 需要挑战的 full-instance 量子结果 |

我们的最高目标是得到

```text
E_DMRG < −62.25668182839704 Eₕ
```

并且该 E_DMRG 必须是某个保存下来的、归一化有限 M MPS 的直接期望值。

相关 tracker 记录：

- [SKQD full-instance submission #5](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/5)
- [CAS(4) submission #124](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/124)

### 5.3 难点在哪里

32 个轨道本身不是 DMRG 的主要障碍。真正风险是轨道结构：

- 在 star basis 中，一个 impurity 同时连接 7 个 bath 轨道；
- 四个 impurity 又通过正方形 hopping 相连；
- 把这张图强行排成一条 MPS 链会产生长程耦合；
- 差的轨道顺序会让许多强关联跨越同一个 MPS cut，导致所需 M 急剧增大。

所以“选择轨道表示与顺序”是 Anderson 求解的核心科学工作。

## 6. Anderson 可行方法分析

| 方法 | 是否给严格变分上界 | 本问题的优点 | 主要风险 | 角色 |
|---|---|---|---|---|
| **block2 DMRG** | 是 | 直接读 FCIDUMP；支持 SU(2)；32 轨道规模合理；可系统增加 M | 对轨道顺序敏感；大 M 需要高内存 | **主方法** |
| Selected CI（HCI/ASCI/CIPSI） | selected-space 对角化能量是 | determinant 数可逐步扩张；与 DMRG 偏差来源不同 | 强关联时 determinant 数可能爆炸；PT2/外推不是严格上界；当前 harness 无锁定实现 | 独立备选/后续交叉检查 |
| RHF + 小 active-space ED | 是 | 快，适合检查积分、符号和数量级 | 不能代表完整 32 轨道关联 | 廉价 oracle |
| AFQMC | 通常不是严格上界 | 可能扩展到大 active space | phaseless constraint 有系统偏差；不适合本挑战的上界 headline | 不作主线 |
| NRG / CT-HYB | 不直接提供所需 T=0 变分上界 | 是 impurity physics 的标准工具 | 本实例是有限、多 impurity FCIDUMP；目标是可比变分能量 | 不作本次求解器 |
| VQE / SKQD 复做 | 可以构造变分能量 | 与公开量子路线最接近 | 本目标是建立经典基线；电路优化成本高 | 仅作背景 |

结论：主线使用 block2 DMRG；RHF 和小 active-space ED 是启动检查；若 DMRG
在合理资源内停滞，再评估 selected CI，而不是同时铺开多个重型方法。

### 6.1 DMRG 路线 A：直接 FCIDUMP + Fiedler ordering

这是最低工程风险路线：

1. 原样读取官方 FCIDUMP；
2. 使用一、二电子积分构造关联图；
3. 用 Fiedler vector 将强耦合轨道尽量排近；
4. 在 SU(2)、N=32、S=0 扇区运行低 M DMRG。

优点是可直接复用 2Fe–2S 管线。缺点是纯图排序可能没有充分利用
“每个 impurity 对应自己的 bath”这一物理结构。

### 6.2 DMRG 路线 B：物理启发的 impurity/bath ordering

构造并比较至少两种确定性顺序：

- **grouped-star**：每个 impurity 与其 7 个 bath 放在同一局部块，再排列四个块；
- **interleaved-chain**：将每组 bath 按能量或 hybridization 强度排序，impurity
  放在组内中心，同时让四个 impurity 在 MPS 上尽量相邻。

先在小 M 下比较，不凭直觉直接把某种 ordering 用于大计算。选择指标是：

- 同一 M 下谁的显式能量更低；
- discarded weight 谁更小；
- 最大 MPO/MPS 内存；
- 单 sweep 时间；
- impurity 间和 impurity–bath 的 mutual information 是否集中在短距离。

### 6.3 DMRG 路线 C：star-to-chain 变换

对每个 bath 做 Lanczos/tridiagonalization，把“一个 impurity 连接多个 bath”
变成“impurity 连接一条 bath chain”。这是 impurity solver 的常见表示，可能显著
减少 Hamiltonian 在 MPS 链上的非局域性。

但它比重新排序更高风险：

- 必须验证基变换后 Hamiltonian 与原 FCIDUMP 等价；
- 四条 bath chain 仍通过 impurity square 耦合；
- 转换后的积分和常数项必须保存并可审计。

因此它不是起点。只有路线 A/B 在低 M 下显示明显 entanglement wall 时，才进入
路线 C。进入条件是：连续提高 M 后能量改善很小，同时 discarded weight 和内存
仍然很大，且问题可追溯到长程 impurity–bath cut。

### 6.4 Anderson 计算 ladder

不预先承诺一个未经测量的最大 M。使用固定 gate：

1. **Smoke gate**：小 M 完成、粒子数和自旋正确、能量低于 RHF。
2. **Ordering gate**：至少三个排序在相同 M、相同 sweep budget 下公平比较。
3. **Timing gate**：用一个完整 sweep 测量时间和峰值内存，再决定后续 M。
4. **CAS gate**：显式能量低于 −61.63174447 Eₕ。
5. **Quantum gate**：显式能量低于 −62.25668182839704 Eₕ。
6. **Convergence gate**：最高两个 M 的能量差、discarded weight 和 restart
   结果足以说明当前误差趋势。

若未通过 Quantum gate，仍报告最好的显式上界、距离量子值的差、排序比较和资源
曲线。这是对量子优势候选的有效负面审计，不把“没有击败”写成失败的空结果。

## 7. 代码与数据边界

本目录最终采用以下结构：

```text
issue-119-variational/
├── README.md                   # 运行入口和当前最好结果
├── PLAN.md                     # 本设计文档
├── pyproject.toml              # solution-local 依赖
├── uv.lock                     # 精确软件锁
├── configs/
│   ├── 2fe2s-reproduce.toml
│   ├── anderson-smoke.toml
│   └── anderson-production.toml
├── src/
│   ├── fetch_instances.py
│   ├── fcidump_audit.py
│   ├── dmrg_runner.py
│   ├── orderings.py
│   └── render_convergence.py
└── tests/
    ├── test_fcidump_headers.py
    ├── test_ordering_is_permutation.py
    ├── test_small_fcidump_energy.py
    └── test_result_schema.py
```

大文件、MPS checkpoint 和计算结果不提交到 solution 目录。每次运行写入：

```text
tracks/qcs/results/<run-id>/
├── run.json
├── inputs/manifest.json
├── config.toml
├── checkpoints/
├── sweeps.csv
├── result.json
├── convergence.png
└── run.log
```

长计算每个 sweep 都刷新日志和结构化结果，避免作业中断后只剩一个空日志。

预期的统一入口为：

```text
uv run python -m src.dmrg_runner --config configs/<name>.toml
```

同一 runner 通过配置切换 FCIDUMP、对称扇区、排序、M 序列和资源限制；不为两个
问题复制两套求解器。

## 8. 资源策略

当前本机有 18 个逻辑 CPU、约 11 GiB 内存。它适合：

- FCIDUMP 审计；
- 单元测试；
- 很小 M 的 smoke run；
- 画图和报告。

公开 2Fe–2S 的 M=1500 运行使用 36 GiB Apple M3 Pro；Anderson 生产计算的内存
风险更高。因此完整基线和 Anderson D 序列默认使用 Slurm。

仓库已有两个 profile，但当前没有 `profiles/active.toml`：

- `scnet.toml`：CPU 节点，128 cores、约 510 GB，适合 block2 CPU DMRG；
- `qdeshell.toml`：必须申请 A800 GPU，而当前 block2 路线主要是 CPU，资源匹配较差。

所以资源设计推荐 SCNet，但真正提交前仍必须：

1. 通过 profile/SSH precheck；
2. 实时 probe partition；
3. 运行 exact request 的 `sbatch --test-only`；
4. 用户确认 partition、CPU、内存和 walltime；
5. 监控 pending→running、首个 sweep 日志和最终 result artifact。

不能把 `sbatch` 成功或作业状态 `COMPLETED` 当作物理结果；只有取回并通过验收的
`result.json`、`sweeps.csv` 和 checkpoint 才能关闭 goal。

## 9. 验证策略

### 9.1 每次运行都做

- FCIDUMP header 与配置一致；
- 轨道排序是 0…NORB−1 的严格 permutation；
- 电子数和目标 spin sector 不变；
- M 增大时显式变分能量不应升高；
- 记录 discarded weight、energy variance（可得时）、内存和时间；
- 保存随机种子、线程数、block2/BLAS 版本和输入 SHA-256。

### 9.2 2Fe–2S 特有

- 与公开 M 序列逐点比较；
- M=1500 与参考值的差 ≤1×10⁻⁴ Eₕ；
- 独立重新启动最高 M 的最后 sweep，排除只读错 checkpoint。

### 9.3 Anderson 特有

- RHF 能量检查积分符号和常数项；
- 小 active-space ED 检查局部关联能量方向；
- 不同 ordering 在相同预算下比较；
- headline 必须来自保存的有限 M MPS；
- 若宣称击败 SKQD，至少重新加载 checkpoint 计算一次独立能量期望值；
- 对外提交前，再选择一个独立实现或方法进行 reduced-instance 交叉检查。

## 10. 主要风险与响应

| 风险 | 可观察信号 | 响应 |
|---|---|---|
| 本地内存不足 | OOM、swap 持续增长 | 本地只做 smoke；生产转 SCNet |
| 轨道排序差 | discarded weight 大、能量随 M 改善慢 | 公平比较 Fiedler 和物理排序；必要时 star-to-chain |
| DMRG 卡在局部极小 | 不同 seed/restart 给出不同平台 | low-M noise、逐级 warm start、至少一次独立 restart |
| 过早相信外推 | 外推值低但显式能量未接近 | 外推仅辅助；headline 始终用有限 M |
| 线程比较不公平 | 运行时间不可复现 | 固定并记录 OpenMP/BLAS 线程和硬件 |
| Anderson 超出一周资源 | timing probe 推算超过预算 | 冻结最好显式上界和负面审计；不牺牲可复现性追求单点数字 |
| 同时开展太多方法 | 每条路线都没有完整证据 | DMRG 为唯一主线；selected CI 只在明确 go/no-go 后启动 |

## 11. 本阶段的完成定义

本阶段完成不是“必须击败量子结果”，而是：

1. 2Fe–2S 基线达到 G1 的数值和复现要求；
2. 公共 DMRG runner、配置、测试和结果 schema 可用；
3. Anderson 至少形成一个经过排序比较和 D 收敛分析的显式变分上界；
4. 清楚报告该上界相对 RHF、CAS(4) 和 SKQD 的位置；
5. 所有结论有脚本、输入 provenance、日志、图和资源记录支持。

如果 Anderson 显式能量低于 −62.25668182839704 Eₕ，则进入 tracker submission
准备；否则提交或保留一份诚实的经典负面审计。完成这些之后，团队再讨论 issue
#119 的 active candidate。
